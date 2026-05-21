"""Deterministic no-fallback traffic dynamics for Python V0."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Literal, Mapping
import math

from rpmi.state import TrafficState, VehicleState


DEFAULT_IDM_PARAMS: dict[str, float] = {
    "a_max": 1.5,
    "b": 2.0,
    "v0": 30.0,
    "T": 1.2,
    "s0": 2.0,
    "delta": 4.0,
}
DEFAULT_CAV_PARAMS: dict[str, float] = {
    "a_max": 1.2,
    "b": 2.5,
    "v0": 30.0,
    "T": 1.0,
    "s0": 2.0,
    "delta": 4.0,
}
DEFAULT_LIMITS: dict[str, float] = {"u_min": -4.5, "u_max": 2.0, "v_max": 35.0}
HARD_BRAKE_THRESHOLD = -4.0


def occupied_interval(vehicle: VehicleState) -> tuple[float, float]:
    """Return the occupied front-bumper interval ``[x - length, x]``."""

    return (vehicle.x - vehicle.length, vehicle.x)


def sort_lane_vehicles(state: TrafficState, lane: int) -> list[VehicleState]:
    """Return active vehicles in a lane sorted by descending front-bumper x."""

    return sorted(
        [
            vehicle
            for vehicle in state.vehicles.values()
            if vehicle.active and vehicle.lane == lane
        ],
        key=lambda vehicle: (vehicle.x, -vehicle.id),
        reverse=True,
    )


def find_leader(state: TrafficState, vehicle_id: int) -> VehicleState | None:
    """Find the nearest active same-lane vehicle ahead of ``vehicle_id``."""

    vehicle = state.vehicles[vehicle_id]
    if not vehicle.active:
        return None
    leaders = [
        candidate
        for candidate in state.vehicles.values()
        if candidate.active
        and candidate.lane == vehicle.lane
        and candidate.id != vehicle.id
        and candidate.x > vehicle.x
    ]
    if not leaders:
        return None
    return min(leaders, key=lambda candidate: (candidate.x - vehicle.x, candidate.id))


def compute_gap_margin(front: VehicleState, rear: VehicleState) -> float:
    """Compute front-bumper geometric gap between ordered same-lane vehicles."""

    if front.lane != rear.lane:
        raise ValueError("front and rear vehicles must be in the same lane")
    if front.x < rear.x:
        raise ValueError("front/rear ordering is wrong")
    return front.x - front.length - rear.x


def _vehicle_idm_params(vehicle: VehicleState) -> dict[str, float]:
    defaults = DEFAULT_CAV_PARAMS if vehicle.veh_type == "CAV" else DEFAULT_IDM_PARAMS
    values = dict(defaults)
    if vehicle.idm_params:
        values.update(vehicle.idm_params)
    return values


def compute_idm_accel(
    vehicle: VehicleState,
    leader: VehicleState | None,
    params: dict[str, float] | None = None,
) -> float:
    """Compute deterministic IDM acceleration for one vehicle."""

    values = dict(_vehicle_idm_params(vehicle))
    if params:
        values.update(params)

    a_max = values["a_max"]
    b = values["b"]
    v0 = max(values["v0"], 1e-9)
    time_headway = values["T"]
    s0 = values["s0"]
    delta = values["delta"]

    free_term = (max(vehicle.v, 0.0) / v0) ** delta
    if leader is None:
        return a_max * (1.0 - free_term)

    gap = max(compute_gap_margin(leader, vehicle), 1e-9)
    dv = vehicle.v - leader.v
    braking_scale = 2.0 * math.sqrt(max(a_max * b, 1e-9))
    desired_gap = s0 + max(0.0, vehicle.v * time_headway + vehicle.v * dv / braking_scale)
    return a_max * (1.0 - free_term - (desired_gap / gap) ** 2)


def compute_nominal_accel(
    vehicle: VehicleState,
    leader: VehicleState | None,
    config: Any | None = None,
) -> float:
    """Compute HDV or CAV nominal car-following acceleration."""

    if vehicle.veh_type == "HDV":
        params = _config_mapping(config, "hdv_idm")
        return compute_idm_accel(vehicle, leader, params)
    if vehicle.veh_type == "CAV":
        params = _config_mapping(config, "cav_nominal_cf")
        return compute_idm_accel(vehicle, leader, params)
    raise ValueError(f"Unknown vehicle type: {vehicle.veh_type!r}")


def combine_nominal_and_action(
    a_nominal: float,
    a_action: float | None,
    mode: Literal["override", "additive_clip"] | str = "override",
) -> float:
    """Overlay an optional production command without safety repair."""

    if a_action is None:
        return a_nominal
    if mode == "override":
        return a_action
    if mode == "additive_clip":
        return a_nominal + a_action
    raise ValueError(f"Unknown action combine mode: {mode!r}")


def clip_accel_for_kinematics(
    v: float,
    a_cmd: float,
    dt: float,
    limits: Mapping[str, float] | float | None = None,
    u_max: float | None = None,
    *,
    u_min: float | None = None,
) -> tuple[float, bool]:
    """Clip acceleration limits and enforce speed floor through ``a_eff``."""

    if dt <= 0.0:
        raise ValueError("dt must be positive")
    values = dict(DEFAULT_LIMITS)
    if isinstance(limits, Mapping):
        values.update(limits)
    elif limits is not None:
        values["u_min"] = float(limits)
    if u_min is not None:
        values["u_min"] = float(u_min)
    if u_max is not None:
        values["u_max"] = float(u_max)
    a_eff = max(values["u_min"], min(values["u_max"], a_cmd))
    speed_floor_clip = False
    if v + a_eff * dt < 0.0:
        a_eff = -v / dt
        speed_floor_clip = True
    return a_eff, speed_floor_clip


def step_vehicle_kinematic(
    vehicle: VehicleState,
    a_eff: float,
    dt: float,
    limits: Mapping[str, float] | float | None = None,
    *,
    v_max: float | None = None,
) -> VehicleState:
    """Integrate one point-mass vehicle using effective acceleration."""

    if dt <= 0.0:
        raise ValueError("dt must be positive")
    values = dict(DEFAULT_LIMITS)
    if isinstance(limits, Mapping):
        values.update(limits)
    elif limits is not None:
        values["v_max"] = float(limits)
    if v_max is not None:
        values["v_max"] = float(v_max)
    x_new = vehicle.x + vehicle.v * dt + 0.5 * a_eff * dt * dt
    v_new = min(values["v_max"], max(0.0, vehicle.v + a_eff * dt))
    return replace(vehicle, x=x_new, v=v_new, a=a_eff)


def _limits_for_vehicle(vehicle: VehicleState, config: Any | None) -> dict[str, float]:
    limits = dict(DEFAULT_LIMITS)
    config_limits = _config_mapping(config, "limits")
    if config_limits:
        limits.update(config_limits)
    if vehicle.cav_limits:
        limits.update(vehicle.cav_limits)
    return limits


def _command_value(command: Any) -> float | None:
    if command is None:
        return None
    if isinstance(command, (int, float)):
        return float(command)
    if isinstance(command, dict):
        value = command.get("a_action", command.get("accel"))
        return None if value is None else float(value)
    return float(command)


def _command_action_id(command: Any) -> str | None:
    if isinstance(command, dict):
        value = command.get("action_id")
        return None if value is None else str(value)
    return None


def _command_lane_change(command: Any) -> dict[str, Any] | None:
    if not isinstance(command, dict) or not command.get("lane_change"):
        return None
    return command


def _config_value(config: Any | None, name: str, default: Any = None) -> Any:
    if config is None:
        return default
    if isinstance(config, Mapping):
        if name in config:
            return config[name]
        sim_config = config.get("sim")
        if sim_config is not None:
            return _config_value(sim_config, name, default)
        return default
    if hasattr(config, name):
        return getattr(config, name)
    sim_config = getattr(config, "sim", None)
    if sim_config is not None and hasattr(sim_config, name):
        return getattr(sim_config, name)
    return default


def _nested_config_value(
    config: Any | None,
    section: str,
    name: str,
    default: Any = None,
) -> Any:
    parent = _config_value(config, section)
    return _config_value(parent, name, default)


def _config_mapping(config: Any | None, name: str) -> Mapping[str, float] | None:
    value = _config_value(config, name)
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping when provided")
    return value


def _with_log_context(
    row: dict[str, Any],
    log_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if not log_context:
        return row
    return {**dict(log_context), **row}


def _first_action_id_for_event(
    event: dict[str, Any],
    action_ids_by_vehicle: Mapping[int, str | None],
) -> str | None:
    for vehicle_id in event.get("vehicle_ids", []):
        action_id = action_ids_by_vehicle.get(int(vehicle_id))
        if action_id is not None:
            return action_id
    return None


def step_traffic(
    state: TrafficState,
    commands_by_vehicle: dict[int, Any] | None = None,
    config: Any | None = None,
    log_context: Mapping[str, Any] | None = None,
) -> tuple[TrafficState, list[dict[str, Any]], list[dict[str, Any]]]:
    """Roll traffic forward one deterministic no-fallback step.

    Returns ``(next_state, vehicle_rows, event_rows)`` so callers can write CSV
    traces without embedding file I/O in the dynamics core.
    """

    commands = commands_by_vehicle or {}
    dt = float(_config_value(config, "dt", 0.1))
    action_mode = _config_value(config, "action_mode", "override")
    event_min_gap = float(
        _config_value(
            config,
            "min_gap",
            _config_value(
                config,
                "negative_margin_threshold",
                _nested_config_value(config, "algorithm", "W_min_buffer", 0.0),
            ),
        )
    )
    hard_brake_threshold = float(
        _config_value(config, "hard_brake_threshold", HARD_BRAKE_THRESHOLD)
    )
    next_time = state.time + dt
    next_step = state.step + 1
    next_vehicles: dict[int, VehicleState] = {}
    rows: list[dict[str, Any]] = []
    action_ids_by_vehicle: dict[int, str | None] = {}
    lane_change_events: list[dict[str, Any]] = []

    for vehicle_id in sorted(state.vehicles):
        vehicle = state.vehicles[vehicle_id]
        if not vehicle.active:
            next_vehicles[vehicle_id] = vehicle
            continue
        leader = find_leader(state, vehicle_id)
        a_nominal = compute_nominal_accel(vehicle, leader, config)
        command = commands.get(vehicle_id)
        lane_change_command = _command_lane_change(command)
        a_action = _command_value(command)
        action_ids_by_vehicle[vehicle_id] = _command_action_id(command)
        a_cmd = combine_nominal_and_action(a_nominal, a_action, action_mode)
        limits = _limits_for_vehicle(vehicle, config)
        a_eff, speed_floor_clip = clip_accel_for_kinematics(vehicle.v, a_cmd, dt, limits)
        updated = step_vehicle_kinematic(vehicle, a_eff, dt, limits)
        updated, lc_step_events = _apply_lane_change_proxy(
            vehicle,
            updated,
            state.time,
            next_time,
            lane_change_command,
            next_step,
        )
        lane_change_events.extend(lc_step_events)
        next_vehicles[vehicle_id] = updated
        rows.append(
            {
                "step": next_step,
                "time": next_time,
                "vehicle_id": vehicle.id,
                "role": vehicle.role,
                "veh_type": vehicle.veh_type,
                "lane": updated.lane,
                "x": updated.x,
                "v": updated.v,
                "a": updated.a,
                "length": updated.length,
                "a_nominal": a_nominal,
                "a_action": a_action,
                "a_eff": a_eff,
                "speed_floor_clip": speed_floor_clip,
                "leader_id": None,
                "gap_to_leader": None,
                "controlled_by_action_id": action_ids_by_vehicle[vehicle_id],
                "reservation_id": updated.reservation_id,
                "invalid_overlap_flag": False,
            }
        )

    next_state = TrafficState(time=next_time, step=next_step, vehicles=next_vehicles)
    for row in rows:
        vehicle_id = int(row["vehicle_id"])
        leader = find_leader(next_state, vehicle_id)
        row["leader_id"] = None if leader is None else leader.id
        row["gap_to_leader"] = (
            None
            if leader is None
            else compute_gap_margin(leader, next_state.vehicles[vehicle_id])
        )

    events = lane_change_events + detect_overlap(next_state, min_gap=event_min_gap) + detect_hard_brake(
        next_state,
        threshold=hard_brake_threshold,
    )
    for event in events:
        if event.get("linked_action_id") is None:
            event["linked_action_id"] = _first_action_id_for_event(
                event,
                action_ids_by_vehicle,
            )
    overlap_ids = {
        vehicle_id
        for event in events
        if event["event_type"] in {"overlap", "negative_margin"}
        for vehicle_id in event["vehicle_ids"]
    }
    for row in rows:
        row["invalid_overlap_flag"] = row["vehicle_id"] in overlap_ids
    return (
        next_state,
        [_with_log_context(row, log_context) for row in rows],
        [_with_log_context(event, log_context) for event in events],
    )


def _apply_lane_change_proxy(
    previous: VehicleState,
    updated: VehicleState,
    current_time: float,
    next_time: float,
    command: dict[str, Any] | None,
    next_step: int,
) -> tuple[VehicleState, list[dict[str, Any]]]:
    if command is None:
        return updated, []
    action_id = _command_action_id(command)
    from_lane = int(command.get("lc_from_lane", previous.lane))
    to_lane = int(command.get("lc_to_lane", previous.lane))
    start = float(command.get("lc_start_time", current_time))
    end = float(command.get("lc_end_time", next_time))
    events: list[dict[str, Any]] = []
    if current_time <= start < next_time + 1e-9:
        events.append(
            {
                "event_id": f"evt_{updated.id}_lane_change_started_{updated.id}_{round(start, 6)}",
                "event_type": "lane_change_started",
                "step": next_step,
                "time": start,
                "vehicle_ids": [updated.id],
                "min_gap": None,
                "min_margin": None,
                "severity": 0.0,
                "linked_reservation_id": updated.reservation_id,
                "linked_action_id": action_id,
                "linked_edge_id": None,
                "note": "lc_mode=discrete_switch_at_end",
            }
        )
    if current_time < end <= next_time + 1e-9 and previous.lane == from_lane:
        updated = replace(updated, lane=to_lane)
        events.append(
            {
                "event_id": f"evt_{updated.id}_lane_change_completed_{updated.id}_{round(end, 6)}",
                "event_type": "lane_change_completed",
                "step": next_step,
                "time": end,
                "vehicle_ids": [updated.id],
                "min_gap": None,
                "min_margin": None,
                "severity": 0.0,
                "linked_reservation_id": updated.reservation_id,
                "linked_action_id": action_id,
                "linked_edge_id": None,
                "note": "lc_mode=discrete_switch_at_end",
            }
        )
    return updated, events


def detect_overlap(state: TrafficState, min_gap: float = 0.0) -> list[dict[str, Any]]:
    """Detect overlap and negative-margin events without modifying state."""

    events: list[dict[str, Any]] = []
    lanes = sorted({vehicle.lane for vehicle in state.vehicles.values() if vehicle.active})
    for lane in lanes:
        vehicles = sort_lane_vehicles(state, lane)
        for front, rear in zip(vehicles, vehicles[1:]):
            gap = compute_gap_margin(front, rear)
            if gap < min_gap:
                event_type = "overlap" if gap < 0.0 else "negative_margin"
                events.append(
                    {
                        "event_id": f"evt_{state.step}_{event_type}_{front.id}_{rear.id}",
                        "event_type": event_type,
                        "step": state.step,
                        "time": state.time,
                        "vehicle_ids": [front.id, rear.id],
                        "min_gap": gap,
                        "min_margin": gap - min_gap,
                        "severity": abs(min(0.0, gap - min_gap)),
                        "linked_reservation_id": rear.reservation_id,
                        "linked_action_id": None,
                        "linked_edge_id": None,
                        "note": "no_fallback_record_only",
                    }
                )
    return events


def detect_hard_brake(
    state: TrafficState,
    threshold: float = HARD_BRAKE_THRESHOLD,
) -> list[dict[str, Any]]:
    """Detect hard braking events from realized effective acceleration."""

    events: list[dict[str, Any]] = []
    for vehicle in sorted(state.vehicles.values(), key=lambda item: item.id):
        if vehicle.active and vehicle.a <= threshold:
            events.append(
                {
                    "event_id": f"evt_{state.step}_hard_brake_{vehicle.id}",
                    "event_type": "hard_brake",
                    "step": state.step,
                    "time": state.time,
                    "vehicle_ids": [vehicle.id],
                    "min_gap": None,
                    "min_margin": vehicle.a - threshold,
                    "severity": abs(vehicle.a - threshold),
                    "linked_reservation_id": vehicle.reservation_id,
                    "linked_action_id": None,
                    "linked_edge_id": None,
                    "note": "no_fallback_record_only",
                }
            )
    return events


__all__ = [
    "DEFAULT_CAV_PARAMS",
    "DEFAULT_IDM_PARAMS",
    "DEFAULT_LIMITS",
    "HARD_BRAKE_THRESHOLD",
    "clip_accel_for_kinematics",
    "combine_nominal_and_action",
    "compute_gap_margin",
    "compute_idm_accel",
    "compute_nominal_accel",
    "detect_hard_brake",
    "detect_overlap",
    "find_leader",
    "occupied_interval",
    "sort_lane_vehicles",
    "step_traffic",
    "step_vehicle_kinematic",
]
