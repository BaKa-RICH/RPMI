import csv

import pytest

from rpmi.logging_schema import (
    CSV_LOG_SCHEMAS,
    append_edge_rows,
    append_slot_rows,
    write_empty_csv,
)
from rpmi.slots import (
    Edge,
    SlotInventoryParams,
    build_edges,
    compute_edge_validity,
    compute_feasible_interval,
    compute_safety_distances,
    compute_inventory_metrics,
    edge_quality_to_row,
    evaluate_survival,
    generate_slots,
    generate_time_grid,
    get_target_lane_pairs,
    make_edge_id,
    make_slot_id,
    slot_to_row,
)
from rpmi.state import TrafficState, VehicleState


def vehicle(
    vehicle_id: int,
    *,
    role: str = "mainline",
    veh_type: str = "HDV",
    lane: int = 0,
    x: float,
    v: float = 10.0,
    length: float = 5.0,
) -> VehicleState:
    return VehicleState(
        id=vehicle_id,
        role=role,
        veh_type=veh_type,
        lane=lane,
        x=x,
        v=v,
        a=0.0,
        length=length,
    )


def state_at(time: float, vehicles: list[VehicleState]) -> TrafficState:
    return TrafficState(time=time, step=int(round(time * 10)), vehicles={v.id: v for v in vehicles})


def basic_edge(tau: float = 1.0) -> Edge:
    slot_id = make_slot_id(1, 2, 1, "baseline")
    return Edge(
        edge_id=make_edge_id(9, 1, 2, 1, "baseline"),
        ramp_id=9,
        front_id=1,
        rear_id=2,
        k=1,
        tau=tau,
        slot_id=slot_id,
        physical_gap_id=(1, 2),
        eval_context="baseline",
        action_id=None,
    )


def test_generate_time_grid_excludes_current_time():
    assert generate_time_grid(10.0, H=1.0, dt_merge=0.5) == [(1, 10.5), (2, 11.0)]


def test_target_lane_pairs_and_action_context_ids():
    state = state_at(
        0.5,
        [
            vehicle(1, x=100.0),
            vehicle(2, x=80.0),
            vehicle(3, x=120.0, lane=1),
        ],
    )
    rollout = {0.5: state}

    slots = generate_slots(
        rollout,
        t=0.0,
        H=0.5,
        dt_merge=0.5,
        target_lane=0,
        eval_context="action",
        action_id="act_front_acc_0",
    )
    edges = build_edges([vehicle(9, role="ramp", lane=-1, x=0.0)], slots)

    assert [(front.id, rear.id) for front, rear in get_target_lane_pairs(state, 0)] == [(1, 2)]
    assert slots[0].slot_id == "slot_1_2_k1_act_front_acc_0"
    assert slots[0].gap_at_tau == pytest.approx(15.0)
    assert edges[0].edge_id == "edge_9_1_2_k1_act_front_acc_0"
    assert edges[0].slot_id == slots[0].slot_id


def test_raw_gap_but_unreachable_gives_zero_reach_and_pr():
    current = state_at(
        0.0,
        [
            vehicle(1, x=100.0),
            vehicle(2, x=70.0),
            vehicle(9, role="ramp", lane=-1, x=0.0, v=0.0),
        ],
    )
    tau_state = state_at(
        1.0,
        [
            vehicle(1, x=100.0),
            vehicle(2, x=70.0),
            vehicle(9, role="ramp", lane=-1, x=0.0, v=0.0),
        ],
    )
    quality = compute_edge_validity(
        basic_edge(),
        tau_state,
        current,
        SlotInventoryParams(W_min_buffer=5.0, u_max=1.0),
    )

    assert quality.V_phys_theory == 1
    assert quality.I_reach == 0
    assert quality.P_R == 0.0
    assert quality.fail_reason_priority == "UNREACHABLE"


def test_negative_width_has_separate_physical_reason():
    current = state_at(
        0.0,
        [
            vehicle(1, x=100.0),
            vehicle(2, x=98.0),
            vehicle(9, role="ramp", lane=-1, x=90.0, v=5.0),
        ],
    )
    quality = compute_edge_validity(
        basic_edge(),
        current,
        current,
        SlotInventoryParams(W_min_buffer=0.0),
    )

    assert quality.V_phys_theory == 0
    assert quality.V_phys_buffer == 0
    assert quality.P_R == 0.0
    assert quality.fail_reason_priority == "PHYS_WIDTH_NEGATIVE"


def test_dynamic_safety_distances_use_side_headways_and_closing_terms():
    edge = basic_edge()
    equal_speed = state_at(
        1.0,
        [
            vehicle(1, veh_type="CAV", x=170.0, v=20.0),
            vehicle(2, veh_type="HDV", x=110.0, v=20.0),
            vehicle(9, role="ramp", veh_type="CAV", lane=-1, x=144.0, v=20.0),
        ],
    )
    params = SlotInventoryParams(
        d0=2.0,
        T_front_CAV_following=1.2,
        T_rear_HDV_following=1.6,
        b_safe=2.5,
    )

    d_front, d_rear = compute_safety_distances(edge, equal_speed, params)

    assert d_front == pytest.approx(26.0)
    assert d_rear == pytest.approx(34.0)

    ramp_faster = state_at(
        1.0,
        [
            vehicle(1, veh_type="CAV", x=170.0, v=18.0),
            vehicle(2, veh_type="HDV", x=110.0, v=20.0),
            vehicle(9, role="ramp", veh_type="CAV", lane=-1, x=144.0, v=20.0),
        ],
    )
    rear_faster = state_at(
        1.0,
        [
            vehicle(1, veh_type="CAV", x=170.0, v=20.0),
            vehicle(2, veh_type="HDV", x=110.0, v=23.0),
            vehicle(9, role="ramp", veh_type="CAV", lane=-1, x=144.0, v=20.0),
        ],
    )

    assert compute_safety_distances(edge, ramp_faster, params)[0] == pytest.approx(26.8)
    assert compute_safety_distances(edge, rear_faster, params)[1] == pytest.approx(40.6)


def test_dynamic_safety_distances_fall_back_to_legacy_t_safe():
    edge = basic_edge()
    tau_state = state_at(
        1.0,
        [
            vehicle(1, x=170.0, v=20.0),
            vehicle(2, x=110.0, v=20.0),
            vehicle(9, role="ramp", lane=-1, x=144.0, v=20.0),
        ],
    )

    assert compute_safety_distances(
        edge,
        tau_state,
        SlotInventoryParams(d0=2.0, T_safe=1.0),
    ) == pytest.approx((22.0, 22.0))


def test_db1_c5_gap55_has_negative_width_at_tau35_with_dynamic_safety():
    edge = basic_edge(tau=3.5)
    tau_state = state_at(
        3.5,
        [
            vehicle(1, veh_type="CAV", x=170.0, v=20.0),
            vehicle(2, veh_type="HDV", x=110.0, v=20.0),
            vehicle(9, role="ramp", veh_type="CAV", lane=-1, x=144.0, v=20.0),
        ],
    )
    interval = compute_feasible_interval(
        edge,
        tau_state,
        SlotInventoryParams(
            d0=2.0,
            T_front_CAV_following=1.2,
            T_rear_HDV_following=1.6,
            b_safe=2.5,
            W_min_buffer=0.0,
        ),
    )

    assert interval.d_front == pytest.approx(26.0)
    assert interval.d_rear == pytest.approx(34.0)
    assert interval.width == pytest.approx(-10.0)
    assert interval.V_phys_theory == 0
    assert interval.V_phys_buffer == 0


def test_theory_validity_is_separate_from_buffer_validity():
    tau_state = state_at(
        1.0,
        [
            vehicle(1, x=100.0),
            vehicle(2, x=90.0),
            vehicle(9, role="ramp", lane=-1, x=90.0, v=0.0),
        ],
    )
    edge = basic_edge()
    interval = compute_feasible_interval(edge, tau_state, SlotInventoryParams(W_min_buffer=3.0))
    quality = compute_edge_validity(
        edge,
        tau_state,
        state_at(
            0.0,
            [
                vehicle(1, x=100.0),
                vehicle(2, x=90.0),
                vehicle(9, role="ramp", lane=-1, x=90.0, v=0.0),
            ],
        ),
        SlotInventoryParams(W_min_buffer=3.0, u_max=20.0),
    )

    assert interval.width == pytest.approx(0.0)
    assert interval.V_phys_theory == 1
    assert interval.V_phys_buffer == 0
    assert interval.delta_W_req == pytest.approx(3.0)
    assert quality.fail_reason_priority == "BUFFER_WIDTH_INSUFFICIENT"


def test_high_recovery_debt_blocks_rec_flag():
    current = state_at(
        0.0,
        [
            vehicle(1, x=100.0, v=30.0),
            vehicle(2, x=60.0, v=30.0),
            vehicle(9, role="ramp", lane=-1, x=50.0, v=0.0),
        ],
    )
    quality = compute_edge_validity(
        basic_edge(),
        current,
        current,
        SlotInventoryParams(W_min_buffer=5.0, RD_max=0.1, u_max=200.0, rd_speed_scale=10.0),
    )

    assert quality.I_rec == 0
    assert quality.P_R == 0.0
    assert quality.fail_reason_priority == "HIGH_RECOVERY_DEBT"
    assert quality.rd_components["proxy_mode"] == "RD_proxy_v0_minimal"


def test_deterministic_survival_mode_is_tau_generated():
    result = evaluate_survival(basic_edge())

    assert result["I_surv"] == 1
    assert result["surv_mode"] == "deterministic_tau_generated"


def test_inventory_metrics_uses_demand_sanity_not_raw_gap_gate():
    q1 = compute_edge_validity(
        basic_edge(),
        state_at(
            1.0,
            [
                vehicle(1, x=100.0),
                vehicle(2, x=60.0),
                vehicle(9, role="ramp", lane=-1, x=80.0, v=10.0),
            ],
        ),
        state_at(
            0.0,
            [
                vehicle(1, x=90.0),
                vehicle(2, x=50.0),
                vehicle(9, role="ramp", lane=-1, x=70.0, v=10.0),
            ],
        ),
        SlotInventoryParams(W_min_buffer=0.0, RD_max=1.0, u_max=10.0),
    )
    q2 = compute_edge_validity(
        basic_edge(),
        state_at(
            1.0,
            [
                vehicle(1, x=100.0),
                vehicle(2, x=98.0),
                vehicle(9, role="ramp", lane=-1, x=90.0, v=10.0),
            ],
        ),
        state_at(
            0.0,
            [
                vehicle(1, x=100.0),
                vehicle(2, x=98.0),
                vehicle(9, role="ramp", lane=-1, x=90.0, v=10.0),
            ],
        ),
        SlotInventoryParams(W_min_buffer=0.0),
    )

    def hook(qualities, weights):
        del weights
        return {"selected_edges": [quality.edge_id for quality in qualities if quality.is_reservable]}

    metrics = compute_inventory_metrics([q1, q2], {9: 1.0}, hook)

    assert 0.0 <= metrics["S_H_R"] <= metrics["D_H"]
    assert metrics["Z_H_R"] == pytest.approx(max(metrics["D_H"] - metrics["S_H_R"], 0.0))
    assert metrics["matched_edge_count"] <= min(metrics["ramp_count"], metrics["reservable_slot_count"])
    assert metrics["reservable_edge_count"] <= metrics["total_edge_count"]
    assert "raw_gap_count" not in metrics["sanity_rule"]


def test_slot_and_edge_csv_append_hooks(tmp_path):
    slots_path = tmp_path / "slots.csv"
    edges_path = tmp_path / "edges.csv"
    write_empty_csv(slots_path, CSV_LOG_SCHEMAS["slots.csv"])
    write_empty_csv(edges_path, CSV_LOG_SCHEMAS["edges.csv"])

    tau_state = state_at(
        1.0,
        [
            vehicle(1, x=100.0),
            vehicle(2, x=60.0),
            vehicle(9, role="ramp", lane=-1, x=80.0, v=10.0),
        ],
    )
    slot = generate_slots({1.0: tau_state}, t=0.0, H=1.0, dt_merge=1.0, target_lane=0)[0]
    edge = build_edges([tau_state.vehicles[9]], [slot])[0]
    quality = compute_edge_validity(edge, tau_state, tau_state, SlotInventoryParams())
    log_context = {
        "run_id": "run_test",
        "step": 1,
        "time": 1.0,
        "decision_context_id": "dc_run_test_1",
        "state_hash": "statehash",
        "config_hash": "confighash",
        "code_version": "test",
        "units_version": "rpmi_units_v1",
    }

    append_slot_rows(slots_path, [slot_to_row(slot, log_context)])
    append_edge_rows(edges_path, [edge_quality_to_row(edge, quality, log_context)])

    with slots_path.open(newline="", encoding="utf-8") as file:
        slot_rows = list(csv.DictReader(file))
    with edges_path.open(newline="", encoding="utf-8") as file:
        edge_rows = list(csv.DictReader(file))

    assert slot_rows[0]["slot_id"] == slot.slot_id
    assert slot_rows[0]["eval_context"] == "baseline"
    assert edge_rows[0]["edge_id"] == edge.edge_id
    assert edge_rows[0]["surv_mode"] == "deterministic_tau_generated"
