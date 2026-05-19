import csv

import pytest

from rpmi.actions import (
    ActionConfig,
    ablation_without_action_conditioned_reservation,
    action_evaluation_to_row,
    action_to_row,
    find_near_miss_edges,
    generate_candidate_actions,
    run_action_selection,
)
from rpmi.logging_schema import (
    CSV_LOG_SCHEMAS,
    append_action_evaluation_rows,
    append_action_rows,
    append_reservation_rows,
    write_empty_csv,
)
from rpmi.reservations import (
    create_reservations,
    reservation_to_row,
    update_reservation_at_tau,
)
from rpmi.slots import (
    build_edges,
    compute_edge_qualities,
    generate_slots,
)
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


def front_acc_state() -> TrafficState:
    return TrafficState(
        time=0.0,
        step=0,
        vehicles={
            1: vehicle(1, veh_type="CAV", x=100.0),
            2: vehicle(2, veh_type="HDV", x=90.0),
            100: vehicle(100, role="ramp", veh_type="CAV", lane=-1, x=80.0),
        },
    )


def shared_cav_state() -> TrafficState:
    return TrafficState(
        time=0.0,
        step=0,
        vehicles={
            1: vehicle(1, veh_type="CAV", x=100.0),
            2: vehicle(2, veh_type="CAV", x=90.0),
            100: vehicle(100, role="ramp", veh_type="CAV", lane=-1, x=80.0),
        },
    )


def phase5_params(**overrides) -> ActionConfig:
    values = {
        "H": 1.0,
        "dt": 1.0,
        "dt_merge": 1.0,
        "target_lane": 0,
        "W_min_buffer": 2.0,
        "u_min": -100.0,
        "u_max": 100.0,
        "u_min_comfort": -100.0,
        "u_max_comfort": 100.0,
        "production_width_buffer": 0.0,
        "lambda_C": 0.001,
        "theta": 0.0,
        "ramp_end_x": 140.0,
        "near_miss_delta_W_max": 8.0,
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
    ramps = [vehicle for vehicle in state.vehicles.values() if vehicle.role == "ramp"]
    edges = build_edges(ramps, slots)
    qualities = compute_edge_qualities(edges, rollout, state, __import__("rpmi.actions", fromlist=["slot_inventory_params"]).slot_inventory_params(params))
    return slots, edges, qualities, {edge.edge_id: edge for edge in edges}


def test_front_acc_toy_rcmv_positive_and_selects_action_conditioned_reservation():
    state = front_acc_state()
    params = phase5_params()
    _, edges, qualities, edge_map = baseline_inventory(state, params)

    result = run_action_selection(state, qualities, edge_map, params)
    selected = result.selected_evaluation

    assert result.selected_action.action_type == "front_acc"
    assert selected.RCMV > 0.0
    assert selected.S_R == pytest.approx(1.0)
    assert selected.Z_R == pytest.approx(0.0)

    reservations = create_reservations(selected, decision_context_id="dc_test")

    assert len(reservations) == 1
    assert reservations[0].action_id == selected.action_id
    assert "_act_front_acc_0" in reservations[0].edge_id


def test_high_cost_action_rejected_by_theta():
    state = front_acc_state()
    params = phase5_params(lambda_C=30.0, theta=0.05)
    _, edges, qualities, edge_map = baseline_inventory(state, params)

    result = run_action_selection(state, qualities, edge_map, params)
    action_eval = next(evaluation for evaluation in result.evaluations if evaluation.action_id != "a0_none")

    assert result.selected_action.action_type == "none"
    assert action_eval.rejected_by_theta


def test_alternative_actions_sharing_same_cav_are_generated():
    state = shared_cav_state()
    params = phase5_params()
    _, edges, qualities, edge_map = baseline_inventory(state, params)
    near_misses = find_near_miss_edges(qualities, edge_map, state, params)

    actions = generate_candidate_actions(near_misses, edge_map, state, params)
    controlled_by_action = {
        action.action_id: action.controlled_cavs
        for action in actions
        if action.action_id != "a0_none"
    }

    assert len(actions) == 4
    assert sum(2 in controlled for controlled in controlled_by_action.values()) >= 2


def test_action_conditioned_reservation_differs_from_stale_ablation():
    state = front_acc_state()
    params = phase5_params()
    _, edges, qualities, edge_map = baseline_inventory(state, params)
    result = run_action_selection(state, qualities, edge_map, params)

    report = ablation_without_action_conditioned_reservation(
        result.baseline_evaluation,
        result.selected_evaluation,
    )

    assert report["stale_flag"] is True
    assert report["baseline_matched_edge_ids"] == []
    assert report["action_conditioned_matched_edge_ids"]
    assert report["reservation_differs"] is True


def test_failed_unsafe_merge_is_recorded_but_not_repaired():
    state = front_acc_state()
    params = phase5_params()
    _, edges, qualities, edge_map = baseline_inventory(state, params)
    result = run_action_selection(state, qualities, edge_map, params)
    reservation = create_reservations(result.selected_evaluation, decision_context_id="dc_test")[0]
    edge = {edge.edge_id: edge for edge in result.selected_evaluation.edges}[reservation.edge_id]

    tau_state = result.selected_evaluation.rollout[1.0]
    tau_state.vehicles[reservation.ramp_id].x = reservation.planned_interval_upper + 10.0
    updated = update_reservation_at_tau(tau_state, reservation, edge)

    assert updated.status == "failed_unsafe_margin"
    assert updated.failure_reason == "negative_actual_margin"
    assert tau_state.vehicles[reservation.ramp_id].lane == -1


def test_phase5_log_rows_are_writable(tmp_path):
    state = front_acc_state()
    params = phase5_params()
    _, edges, qualities, edge_map = baseline_inventory(state, params)
    result = run_action_selection(state, qualities, edge_map, params)
    reservations = create_reservations(result.selected_evaluation, decision_context_id="dc_test")

    actions_path = tmp_path / "actions.csv"
    evals_path = tmp_path / "action_evaluations.csv"
    reservations_path = tmp_path / "reservations.csv"
    write_empty_csv(actions_path, CSV_LOG_SCHEMAS["actions.csv"])
    write_empty_csv(evals_path, CSV_LOG_SCHEMAS["action_evaluations.csv"])
    write_empty_csv(reservations_path, CSV_LOG_SCHEMAS["reservations.csv"])

    log_context = {"run_id": "run_test", "decision_context_id": "dc_test"}
    append_action_rows(actions_path, [action_to_row(result.selected_action, log_context)])
    append_action_evaluation_rows(
        evals_path,
        [action_evaluation_to_row(result.selected_evaluation, log_context)],
    )
    append_reservation_rows(
        reservations_path,
        [reservation_to_row(reservation, log_context) for reservation in reservations],
    )

    with actions_path.open(newline="", encoding="utf-8") as file:
        action_rows = list(csv.DictReader(file))
    with evals_path.open(newline="", encoding="utf-8") as file:
        eval_rows = list(csv.DictReader(file))
    with reservations_path.open(newline="", encoding="utf-8") as file:
        reservation_rows = list(csv.DictReader(file))

    assert action_rows[0]["action_type"] == "front_acc"
    assert float(eval_rows[0]["RCMV"]) > 0.0
    assert reservation_rows[0]["status"] == "planned"
