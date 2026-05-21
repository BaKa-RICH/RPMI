import csv
import json

import pytest

from rpmi.actions import (
    ActionConfig,
    action_conditioned_rollout,
    build_lane_change_candidate,
    find_near_miss_edges,
    generate_candidate_actions,
    receiving_gap_for_vehicle,
    run_action_selection,
)
from rpmi.analysis import build_wave7_evidence_package
from rpmi.runner import run_wave7_s5_suite
from rpmi.slots import build_edges, compute_edge_qualities, generate_slots
from rpmi.state import TrafficState, VehicleState


def vehicle(
    vehicle_id: int,
    *,
    role: str = "mainline",
    veh_type: str = "HDV",
    lane: int = 0,
    x: float,
    v: float = 0.0,
) -> VehicleState:
    return VehicleState(
        id=vehicle_id,
        role=role,
        veh_type=veh_type,
        lane=lane,
        x=x,
        v=v,
        a=0.0,
        idm_params={"a_max": 0.0},
        cav_limits={"u_min": -100.0, "u_max": 100.0, "v_max": 100.0},
    )


def lc_state(*, lc_cav_lane: int = 0, inner_rear_x: float = 10.0) -> TrafficState:
    return TrafficState(
        time=0.0,
        step=0,
        vehicles={
            1: vehicle(1, veh_type="HDV", lane=0, x=105.0),
            2: vehicle(2, veh_type="CAV", lane=lc_cav_lane, x=100.0),
            3: vehicle(3, veh_type="HDV", lane=0, x=88.0),
            11: vehicle(11, veh_type="HDV", lane=1, x=140.0),
            12: vehicle(12, veh_type="HDV", lane=1, x=inner_rear_x),
            100: vehicle(100, role="ramp", veh_type="CAV", lane=-1, x=90.0),
        },
    )


def lc_params(**overrides) -> ActionConfig:
    values = {
        "H": 1.0,
        "dt": 1.0,
        "dt_merge": 1.0,
        "target_lane": 0,
        "lanes": 2,
        "W_min_buffer": 5.0,
        "u_min": -100.0,
        "u_max": 100.0,
        "u_min_comfort": -100.0,
        "u_max_comfort": 100.0,
        "production_width_buffer": 0.0,
        "lambda_C": 0.001,
        "theta": 0.0,
        "ramp_end_x": 140.0,
        "near_miss_delta_W_max": 12.0,
        "enable_boundary_speed": False,
        "enable_lane_change": True,
        "lc_duration": 1.0,
        "lc_min_front_margin": 3.0,
        "lc_min_rear_margin": 3.0,
        "lc_base_cost": 0.01,
        "lc_duration_penalty_weight": 0.0,
        "lc_margin_risk_weight": 0.1,
        "lc_disturbance_weight": 0.0,
    }
    values.update(overrides)
    return ActionConfig(**values)


def baseline_inventory(state: TrafficState, params: ActionConfig):
    rollout = {0.0: state, 1.0: state}
    slots = generate_slots(
        rollout,
        t=state.time,
        H=params.H,
        dt_merge=params.dt_merge,
        target_lane=params.target_lane,
    )
    ramps = [item for item in state.vehicles.values() if item.role == "ramp"]
    edges = build_edges(ramps, slots)
    qualities = compute_edge_qualities(
        edges,
        rollout,
        state,
        __import__("rpmi.actions", fromlist=["slot_inventory_params"]).slot_inventory_params(params),
    )
    return slots, edges, qualities, {edge.edge_id: edge for edge in edges}


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def test_w7_no_target_lane_cav_means_no_lane_change_candidate():
    state = lc_state(lc_cav_lane=1)
    params = lc_params()
    _, _, qualities, edge_map = baseline_inventory(state, params)

    near_misses = find_near_miss_edges(qualities, edge_map, state, params)
    actions = generate_candidate_actions(near_misses, edge_map, state, params)

    assert [action.action_type for action in actions] == ["none"]


def test_w7_inner_lane_cav_is_not_inserted_into_target_lane():
    state = lc_state(lc_cav_lane=1)
    params = lc_params()
    _, edges, qualities, edge_map = baseline_inventory(state, params)
    near_misses = find_near_miss_edges(qualities, edge_map, state, params)
    edge = edge_map[qualities[0].edge_id]

    assert not near_misses
    assert build_lane_change_candidate(
        __import__("rpmi.actions", fromlist=["NearMissEdge"]).NearMissEdge(
            edge_id=edge.edge_id,
            near_miss_type="buffer_width",
            delta_W_req=1.0,
            available_modes=("lane_change",),
            screen_score=1.0,
            selected_for_rollout=True,
            ramp_id=edge.ramp_id,
            slot_id=edge.slot_id,
            front_id=edge.front_id,
            rear_id=edge.rear_id,
            tau=edge.tau,
            boundary_type="HDV-HDV",
            W=0.0,
            RD=0.0,
        ),
        edge,
        state,
        params,
    ) is None


def test_w7_feasible_lane_change_candidate_moves_target_lane_cav_inward():
    state = lc_state()
    params = lc_params()
    _, _, qualities, edge_map = baseline_inventory(state, params)
    near_misses = find_near_miss_edges(qualities, edge_map, state, params)
    actions = generate_candidate_actions(near_misses, edge_map, state, params)

    lane_change = next(action for action in actions if action.action_type == "lane_change")

    assert lane_change.controlled_cavs == (2,)
    assert lane_change.control_profile["lc_from_lane"] == 0
    assert lane_change.control_profile["lc_to_lane"] == 1
    assert lane_change.control_profile["lc_feasibility_pass"] is True
    assert lane_change.rejected_before_rollout is False


def test_w7_unsafe_receiving_gap_is_rejected_before_rollout():
    state = lc_state(inner_rear_x=98.0)
    params = lc_params()
    _, _, qualities, edge_map = baseline_inventory(state, params)
    near_misses = find_near_miss_edges(qualities, edge_map, state, params)
    actions = generate_candidate_actions(near_misses, edge_map, state, params)
    lane_change = next(action for action in actions if action.action_type == "lane_change")

    assert lane_change.rejected_before_rollout is True
    assert lane_change.reject_reason == "rear_margin_insufficient"


def test_w7_rollout_changes_target_lane_boundary_sequence():
    state = lc_state()
    params = lc_params()
    _, _, qualities, edge_map = baseline_inventory(state, params)
    near_misses = find_near_miss_edges(qualities, edge_map, state, params)
    lane_change = next(
        action
        for action in generate_candidate_actions(near_misses, edge_map, state, params)
        if action.action_type == "lane_change"
    )

    rollout = action_conditioned_rollout(lane_change, state, params)
    final_state = rollout[1.0]
    slots = generate_slots(
        rollout,
        t=state.time,
        H=params.H,
        dt_merge=params.dt_merge,
        target_lane=params.target_lane,
        eval_context="action",
        action_id=lane_change.action_id,
    )

    assert final_state.vehicles[2].lane == 1
    assert (1, 3) in {slot.physical_gap_id for slot in slots}


def test_w7_lane_change_can_be_selected_by_rcmv():
    state = lc_state()
    params = lc_params()
    _, _, qualities, edge_map = baseline_inventory(state, params)

    result = run_action_selection(state, qualities, edge_map, params)

    assert result.selected_action.action_type == "lane_change"
    assert result.selected_evaluation.RCMV > 0.0
    assert result.selected_evaluation.S_R == pytest.approx(1.0)
    assert result.selected_evaluation.Z_R == pytest.approx(0.0)


def test_w7_high_lane_change_cost_is_rejected_by_theta():
    state = lc_state()
    params = lc_params(lambda_C=10.0, lc_base_cost=10.0, theta=0.05)
    _, _, qualities, edge_map = baseline_inventory(state, params)

    result = run_action_selection(state, qualities, edge_map, params)
    lane_change_eval = next(
        evaluation for evaluation in result.evaluations if evaluation.action_id != "a0_none"
    )

    assert result.selected_action.action_type == "none"
    assert lane_change_eval.rejected_by_theta


def test_w7_receiving_gap_uses_nearest_front_and_rear():
    state = TrafficState(
        time=0.0,
        step=0,
        vehicles={
            2: vehicle(2, veh_type="CAV", lane=0, x=100.0),
            11: vehicle(11, lane=1, x=160.0),
            12: vehicle(12, lane=1, x=112.0),
            13: vehicle(13, lane=1, x=90.0),
            14: vehicle(14, lane=1, x=0.0),
        },
    )

    front, rear, margin_front, margin_rear = receiving_gap_for_vehicle(state, state.vehicles[2], 1)

    assert front.id == 12
    assert rear.id == 13
    assert margin_front == pytest.approx(7.0)
    assert margin_rear == pytest.approx(5.0)


def test_w7_evidence_package_contains_s5_summary_and_gate_d1_input(tmp_path):
    result = run_wave7_s5_suite(
        [7],
        tmp_path,
        batch_id="wave7_s5_test",
    )
    fairness = json.loads(open(result.fairness_report_path, encoding="utf-8").read())
    package_dir = tmp_path / "wave7_evidence"

    paths = build_wave7_evidence_package(
        result.run_dirs,
        package_dir=package_dir,
        batch_id=result.batch_id,
        fairness=fairness,
        batch_manifest_path=result.batch_manifest_path,
    )

    summary_rows = read_csv(paths["wave_7_s5_full_action_summary"])
    manifest = json.loads((paths["gate_D1_input"] / "gate_D1_manifest.json").read_text(encoding="utf-8"))

    assert (package_dir / "wave_7_report.md").exists()
    assert (package_dir / "wave_7_lane_change_trace_samples" / "lane_change_actions.csv").exists()
    assert (paths["gate_D1_input"] / "actions.csv").exists()
    assert manifest["decision_status"] == "not_run"
    assert {
        "rpmi_cmv_boundary_speed_only",
        "rpmi_cmv_lane_change_only",
        "rpmi_cmv_full_action_set",
    }.issubset({row["algorithm_id"] for row in summary_rows})
    assert {
        "failed_reservation_rate",
        "failed_reservation_denominator",
        "merge_success_rate_over_demand",
        "predicted_unserved_demand_rate",
        "realized_unserved_demand_rate",
    }.issubset(summary_rows[0])
    row_by_algorithm = {row["algorithm_id"]: row for row in summary_rows}
    assert row_by_algorithm["rpmi_cmv_boundary_speed_only"]["selected_action_type"] == "none"
    assert row_by_algorithm["rpmi_cmv_lane_change_only"]["selected_action_type"] == "lane_change"
    assert row_by_algorithm["rpmi_cmv_full_action_set"]["selected_action_type"] == "lane_change"
