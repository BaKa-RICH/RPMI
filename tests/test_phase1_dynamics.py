import csv
from types import SimpleNamespace

import pytest

from rpmi.dynamics import (
    clip_accel_for_kinematics,
    combine_nominal_and_action,
    compute_gap_margin,
    compute_idm_accel,
    compute_nominal_accel,
    detect_hard_brake,
    detect_overlap,
    find_leader,
    occupied_interval,
    sort_lane_vehicles,
    step_traffic,
    step_vehicle_kinematic,
)
from rpmi.logging_schema import (
    CSV_LOG_SCHEMAS,
    append_realized_event_rows,
    append_vehicle_step_rows,
    write_empty_csv,
)
from rpmi.state import TrafficState, VehicleState


def make_vehicle(
    vehicle_id: int,
    *,
    x: float,
    v: float = 10.0,
    a: float = 0.0,
    lane: int = 0,
    role: str = "mainline",
    veh_type: str = "HDV",
    length: float = 5.0,
    **kwargs,
) -> VehicleState:
    return VehicleState(
        id=vehicle_id,
        role=role,
        veh_type=veh_type,
        lane=lane,
        x=x,
        v=v,
        a=a,
        length=length,
        **kwargs,
    )


def test_occupied_interval_and_lane_ordering_and_leader():
    front = make_vehicle(1, x=100.0)
    rear = make_vehicle(2, x=80.0)
    other_lane = make_vehicle(3, x=120.0, lane=1)
    state = TrafficState(time=0.0, step=0, vehicles={1: front, 2: rear, 3: other_lane})

    assert occupied_interval(front) == (95.0, 100.0)
    assert [vehicle.id for vehicle in sort_lane_vehicles(state, 0)] == [1, 2]
    assert find_leader(state, 2) == front
    assert find_leader(state, 1) is None


def test_front_bumper_gap_margin():
    front = make_vehicle(1, x=100.0, length=5.0)
    rear = make_vehicle(2, x=80.0)

    assert compute_gap_margin(front, rear) == 15.0


def test_single_vehicle_constant_speed_analytic_step():
    vehicle = make_vehicle(1, x=0.0, v=10.0, idm_params={"a_max": 0.0})
    state = TrafficState(time=0.0, step=0, vehicles={1: vehicle})
    config = SimpleNamespace(dt=2.0, limits={"u_min": -4.5, "u_max": 2.0, "v_max": 40.0})

    next_state, rows, events = step_traffic(state, {}, config)

    assert next_state.time == 2.0
    assert next_state.step == 1
    assert next_state.vehicles[1].x == pytest.approx(20.0)
    assert next_state.vehicles[1].v == pytest.approx(10.0)
    assert rows[0]["a_eff"] == pytest.approx(0.0)
    assert events == []


def test_single_vehicle_constant_accel_analytic_step_with_action_override():
    vehicle = make_vehicle(1, x=0.0, v=10.0, idm_params={"a_max": 0.0})
    state = TrafficState(time=0.0, step=0, vehicles={1: vehicle})
    config = SimpleNamespace(dt=2.0, action_mode="override", limits={"u_min": -4.5, "u_max": 2.0, "v_max": 40.0})

    next_state, rows, events = step_traffic(state, {1: {"a_action": 1.0, "action_id": "act_front_acc_0"}}, config)

    assert next_state.vehicles[1].x == pytest.approx(22.0)
    assert next_state.vehicles[1].v == pytest.approx(12.0)
    assert rows[0]["a_action"] == pytest.approx(1.0)
    assert rows[0]["controlled_by_action_id"] == "act_front_acc_0"
    assert events == []


def test_speed_floor_uses_effective_acceleration_for_x_and_v():
    vehicle = make_vehicle(1, x=0.0, v=1.0)

    a_eff, clipped = clip_accel_for_kinematics(
        vehicle.v,
        -100.0,
        0.1,
        {"u_min": -100.0, "u_max": 2.0, "v_max": 40.0},
    )
    updated = step_vehicle_kinematic(vehicle, a_eff, 0.1)

    assert a_eff == pytest.approx(-10.0)
    assert clipped is True
    assert updated.v == pytest.approx(0.0)
    assert updated.x == pytest.approx(0.05)


def test_overlap_is_recorded_but_not_repaired():
    front = make_vehicle(1, x=100.0)
    rear = make_vehicle(2, x=97.0)
    state = TrafficState(time=0.0, step=0, vehicles={1: front, 2: rear})

    events = detect_overlap(state)

    assert [event["event_type"] for event in events] == ["overlap"]
    assert events[0]["min_gap"] == pytest.approx(-2.0)
    assert state.vehicles[1].x == 100.0
    assert state.vehicles[2].x == 97.0


def test_negative_margin_and_hard_brake_events_are_logged():
    front = make_vehicle(1, x=100.0, a=0.0)
    rear = make_vehicle(2, x=94.0, a=-4.5)
    state = TrafficState(time=1.0, step=10, vehicles={1: front, 2: rear})

    overlap_events = detect_overlap(state, min_gap=2.0)
    hard_brake_events = detect_hard_brake(state)

    assert [event["event_type"] for event in overlap_events] == ["negative_margin"]
    assert overlap_events[0]["min_gap"] == pytest.approx(1.0)
    assert [event["event_type"] for event in hard_brake_events] == ["hard_brake"]
    assert hard_brake_events[0]["severity"] == pytest.approx(0.5)


def test_idm_free_road_positive_and_close_slow_leader_negative():
    follower = make_vehicle(1, x=0.0, v=10.0)
    leader = make_vehicle(2, x=12.0, v=1.0)

    assert compute_idm_accel(follower, None) > 0.0
    assert compute_idm_accel(follower, leader) < 0.0


def test_cav_without_action_still_uses_nominal_following():
    cav = make_vehicle(1, x=0.0, v=20.0, veh_type="CAV")
    leader = make_vehicle(2, x=18.0, v=5.0)
    state = TrafficState(time=0.0, step=0, vehicles={1: cav, 2: leader})
    nominal = compute_nominal_accel(cav, leader)

    next_state, rows, events = step_traffic(
        state,
        {},
        SimpleNamespace(dt=0.1, limits={"u_min": -100.0, "u_max": 2.0, "v_max": 40.0}),
    )

    assert nominal < 0.0
    assert rows[0]["vehicle_id"] == 1
    assert rows[0]["a_action"] is None
    assert rows[0]["a_eff"] == pytest.approx(rows[0]["a_nominal"])
    assert next_state.vehicles[1].v < cav.v
    assert events


def test_combine_nominal_and_action_modes():
    assert combine_nominal_and_action(0.4, None, "override") == pytest.approx(0.4)
    assert combine_nominal_and_action(0.4, 1.0, "override") == pytest.approx(1.0)
    assert combine_nominal_and_action(0.4, 1.0, "additive_clip") == pytest.approx(1.4)

    with pytest.raises(ValueError, match="Unknown action"):
        combine_nominal_and_action(0.0, 1.0, "mystery")


def test_vehicle_and_event_csv_append_hooks(tmp_path):
    vehicles_path = tmp_path / "vehicles_step.csv"
    events_path = tmp_path / "realized_events.csv"
    write_empty_csv(vehicles_path, CSV_LOG_SCHEMAS["vehicles_step.csv"])
    write_empty_csv(events_path, CSV_LOG_SCHEMAS["realized_events.csv"])

    state = TrafficState(
        time=0.0,
        step=0,
        vehicles={1: make_vehicle(1, x=0.0, v=1.0, idm_params={"a_max": 0.0})},
    )
    log_context = {
        "run_id": "run_test",
        "decision_context_id": "dc_run_test_1",
        "state_hash": "statehash",
        "config_hash": "confighash",
        "code_version": "test",
        "units_version": "rpmi_units_v1",
    }
    _, vehicle_rows, event_rows = step_traffic(
        state,
        {1: -100.0},
        SimpleNamespace(dt=0.1, limits={"u_min": -100.0, "u_max": 2.0, "v_max": 40.0}),
        log_context=log_context,
    )
    event_rows.append(
        {
            **log_context,
            "step": 1,
            "time": 0.1,
            "event_id": "evt_test",
            "event_type": "hard_brake",
            "vehicle_ids": [1],
            "min_gap": None,
            "min_margin": -1.0,
            "severity": 1.0,
            "linked_reservation_id": None,
            "linked_action_id": "act_test",
            "linked_edge_id": None,
            "note": "no_fallback_record_only",
        }
    )

    append_vehicle_step_rows(vehicles_path, vehicle_rows)
    append_realized_event_rows(events_path, event_rows)

    with vehicles_path.open(newline="", encoding="utf-8") as file:
        vehicle_csv_rows = list(csv.DictReader(file))
    with events_path.open(newline="", encoding="utf-8") as file:
        event_csv_rows = list(csv.DictReader(file))

    assert vehicle_csv_rows[0]["run_id"] == "run_test"
    assert vehicle_csv_rows[0]["speed_floor_clip"] == "True"
    assert event_csv_rows[0]["event_type"] == "hard_brake"
    assert event_csv_rows[0]["vehicle_ids"] == "[1]"
