"""RCMV production action selection for deterministic Python V0.

Wave 7 extends the previous single boundary-speed action set with a deterministic
lane-change proxy.  Action bundles, rolling horizon, MOBIL, SUMO, stochastic IDM,
and fallback repair remain outside this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence
import json
import math

from rpmi.config import RunConfig
from rpmi.dynamics import step_traffic
from rpmi.ids import make_action_id
from rpmi.matching import (
    DemandRecord,
    MatchingConfig,
    MatchingEdge,
    MatchingResult,
    build_matching_edges,
    solve_matching_v0_greedy_conflict,
)
from rpmi.scenarios import NearMissLabel, ScenarioConfig, classify_near_miss
from rpmi.slots import (
    Edge,
    EdgeQuality,
    Slot,
    SlotInventoryParams,
    build_edges,
    compute_edge_qualities,
    generate_slots,
)
from rpmi.state import TrafficState, VehicleState


ActionType = Literal["none", "front_acc", "rear_dec", "front_rear", "lane_change"]


@dataclass(frozen=True)
class ActionConfig:
    """Single-decision action-selection parameters."""

    H: float = 1.0
    dt: float = 0.5
    dt_merge: float = 1.0
    target_lane: int = 0
    W_min_buffer: float = 5.0
    RD_max: float = 1.0
    d0: float = 0.0
    T_safe: float = 0.0
    T_front_CAV_following: float | None = None
    T_rear_HDV_following: float | None = None
    b_safe: float | None = None
    u_min: float = -4.5
    u_max: float = 2.0
    v_max: float = 40.0
    T_prod: float = 3.0
    production_width_buffer: float = 0.5
    lambda_D: float = 1.0
    lambda_C: float = 1.0
    theta: float = 0.05
    u_max_comfort: float = 2.0
    u_min_comfort: float = -4.5
    rd_speed_scale: float = 10.0
    ramp_end_x: float | None = None
    T_merge: float = 1.0
    T_buffer: float = 0.0
    conflict_mode: str = "time_window_default"
    near_miss_delta_W_max: float = 8.0
    near_miss_RD_max: float = 1.0
    action_mode: str = "override"
    event_min_gap: float = 0.0
    lanes: int = 2
    enable_boundary_speed: bool = True
    enable_lane_change: bool = False
    lc_duration: float = 1.0
    lc_min_front_margin: float = 3.0
    lc_min_rear_margin: float = 3.0
    lc_base_cost: float = 0.05
    lc_duration_penalty_weight: float = 0.02
    lc_margin_risk_weight: float = 0.10
    lc_disturbance_weight: float = 0.05
    lc_allow_exceed_T_prod: bool = False
    lc_mode: str = "discrete_switch_at_end"
    lc_upstream_search_distance: float = 80.0

    def __post_init__(self) -> None:
        _validate_action_mode(self.action_mode)


@dataclass(frozen=True)
class LaneChangeCandidate:
    candidate_id: str
    edge_id: str
    cav_id: int
    from_lane: int
    to_lane: int
    start_time: float
    end_time: float
    expected_gap_effect: str
    receiving_gap_front_id: int | None
    receiving_gap_rear_id: int | None
    feasibility_pass: bool
    reject_reason: str
    feasibility_margin_front: float = -math.inf
    feasibility_margin_rear: float = -math.inf


@dataclass(frozen=True)
class NearMissEdge:
    edge_id: str
    near_miss_type: str
    delta_W_req: float
    available_modes: tuple[str, ...]
    screen_score: float
    selected_for_rollout: bool
    ramp_id: int
    slot_id: str
    front_id: int
    rear_id: int
    tau: float
    boundary_type: str
    W: float
    RD: float
    reason: str = ""


@dataclass(frozen=True)
class Action:
    action_id: str
    action_type: ActionType
    nominal_edge_id: str | None
    controlled_cavs: tuple[int, ...]
    target_gap_id: tuple[int, int] | None
    control_profile: dict[str, Any]
    estimated_cost: float
    boundary_type: str = ""
    rejected_before_rollout: bool = False
    reject_reason: str = ""


@dataclass(frozen=True)
class ActionEvaluation:
    action_id: str
    J: float
    Z_bar: float
    D_bar: float
    C_bar: float
    RCMV: float
    S_R: float
    Z_R: float
    D_H: float
    matched_edge_ids: list[str]
    selected: bool
    rejected_by_theta: bool
    matched_count: int = 0
    invalid_count: int = 0
    rank: int = 0
    cost_components: dict[str, Any] | None = None
    matched_rd_sum: float = 0.0
    matching_result: MatchingResult | None = None
    slots: tuple[Slot, ...] = ()
    edges: tuple[Edge, ...] = ()
    edge_qualities: tuple[EdgeQuality, ...] = ()
    matching_edges: tuple[MatchingEdge, ...] = ()
    rollout: Mapping[float, TrafficState] | None = None


@dataclass(frozen=True)
class ActionSelectionResult:
    baseline_evaluation: ActionEvaluation
    evaluations: list[ActionEvaluation]
    selected_action: Action
    selected_evaluation: ActionEvaluation


def find_near_miss_edges(
    qualities: Sequence[EdgeQuality],
    edge_map: Mapping[str, Edge],
    state: TrafficState,
    params: ActionConfig | Mapping[str, Any] | Any | None = None,
) -> list[NearMissEdge]:
    """Find Phase 5A near misses using the shared read-only classifier."""

    values = coerce_action_config(params)
    near_misses: list[NearMissEdge] = []
    for quality in qualities:
        edge = edge_map.get(quality.edge_id)
        if edge is None:
            continue
        boundary_type = boundary_type_for_edge(state, edge)
        label = classify_near_miss(
            quality,
            boundary_type,
            values,
        )
        modes = list(label.available_modes)
        lc_candidate_exists = values.enable_lane_change and (
            label.is_near_miss or label.reason == "no_boundary_cav_mode"
        )
        if lc_candidate_exists and lane_change_control_cav_for_edge(None, edge, state, values) is not None:
            if "lane_change" not in modes:
                modes.append("lane_change")
        if not modes:
            continue
        reason = label.reason
        if "lane_change" in modes and not label.available_modes:
            reason = "lc_upstream_blocking;lc_can_reorder_boundary"
        near_misses.append(
            _near_miss_from_label(
                NearMissLabel(
                    is_near_miss=True,
                    near_miss_type=label.near_miss_type,
                    delta_W_req=label.delta_W_req,
                    available_modes=tuple(modes),
                    screen_score=label.screen_score,
                    reason=reason,
                ),
                quality,
                edge,
                boundary_type,
            )
        )
    return near_misses


def generate_candidate_actions(
    near_misses: Sequence[NearMissEdge],
    edge_map: Mapping[str, Edge],
    state: TrafficState,
    params: ActionConfig | Mapping[str, Any] | Any | None = None,
) -> list[Action]:
    """Generate all valid single-action candidates without cross-candidate CAV de-dup."""

    values = coerce_action_config(params)
    actions = [
        Action(
            action_id="a0_none",
            action_type="none",
            nominal_edge_id=None,
            controlled_cavs=(),
            target_gap_id=None,
            control_profile={
                "requested_delta_W": 0.0,
                "delta_W_target": 0.0,
                "T_prod": 0.0,
                "u_front": 0.0,
                "u_rear": 0.0,
                "profile_clip_flag": False,
                "estimated_delta_W_after_clip": 0.0,
                "action_profile_feasible": True,
            },
            estimated_cost=0.0,
        )
    ]
    index = 0
    lane_change_index = 0
    for near_miss in near_misses:
        edge = edge_map.get(near_miss.edge_id)
        if edge is None:
            continue
        for mode in near_miss.available_modes:
            if mode == "lane_change":
                if not values.enable_lane_change:
                    continue
                candidate = build_lane_change_candidate(
                    near_miss,
                    edge,
                    state,
                    values,
                    lane_change_index,
                )
                lane_change_index += 1
                if candidate is None:
                    continue
                profile = build_lane_change_profile(candidate, values)
                action = Action(
                    action_id=make_action_id("lane_change", lane_change_index - 1),
                    action_type="lane_change",
                    nominal_edge_id=edge.edge_id,
                    controlled_cavs=(candidate.cav_id,),
                    target_gap_id=(
                        None
                        if candidate.receiving_gap_front_id is None
                        or candidate.receiving_gap_rear_id is None
                        else (
                            candidate.receiving_gap_front_id,
                            candidate.receiving_gap_rear_id,
                        )
                    ),
                    control_profile=profile,
                    estimated_cost=compute_lane_change_cost(profile, values)["C_bar"],
                    boundary_type=near_miss.boundary_type,
                    rejected_before_rollout=not candidate.feasibility_pass,
                    reject_reason=candidate.reject_reason,
                )
                actions.append(action)
                continue
            if not values.enable_boundary_speed:
                continue
            if mode not in {"front_acc", "rear_dec", "front_rear"}:
                continue
            controlled = controlled_cavs_for_mode(mode, edge, state)
            profile = build_boundary_speed_profile(mode, near_miss, edge, state, values)
            action = Action(
                action_id=make_action_id(mode, index),
                action_type=mode,  # type: ignore[arg-type]
                nominal_edge_id=edge.edge_id,
                controlled_cavs=controlled,
                target_gap_id=edge.physical_gap_id,
                control_profile=profile,
                estimated_cost=compute_profile_cost(profile, values),
                boundary_type=near_miss.boundary_type,
            )
            ok, reason = validate_single_action(action, state)
            if ok:
                actions.append(action)
                index += 1
            else:
                actions.append(
                    Action(
                        action_id=action.action_id,
                        action_type=action.action_type,
                        nominal_edge_id=action.nominal_edge_id,
                        controlled_cavs=action.controlled_cavs,
                        target_gap_id=action.target_gap_id,
                        control_profile=action.control_profile,
                        estimated_cost=action.estimated_cost,
                        boundary_type=action.boundary_type,
                        rejected_before_rollout=True,
                        reject_reason=reason,
                    )
                )
                index += 1
    return actions


def find_lane_change_candidates(
    near_misses: Sequence[NearMissEdge],
    edge_map: Mapping[str, Edge],
    state: TrafficState,
    params: ActionConfig | Mapping[str, Any] | Any | None = None,
) -> list[LaneChangeCandidate]:
    """Build auditable lane-change feasibility candidates for logging/tests."""

    values = coerce_action_config(params)
    candidates = []
    for index, near_miss in enumerate(near_misses):
        if "lane_change" not in near_miss.available_modes:
            continue
        edge = edge_map.get(near_miss.edge_id)
        if edge is None:
            continue
        candidate = build_lane_change_candidate(near_miss, edge, state, values, index)
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def build_lane_change_candidate(
    near_miss: NearMissEdge,
    edge: Edge,
    state: TrafficState,
    params: ActionConfig | Mapping[str, Any] | Any | None = None,
    index: int = 0,
) -> LaneChangeCandidate | None:
    """Return one deterministic upstream-CAV lane-change feasibility record."""

    values = coerce_action_config(params)
    if not values.enable_lane_change:
        return None
    start_time = state.time
    duration = max(float(values.lc_duration), values.dt)
    end_time = start_time + duration
    candidates = lane_change_control_cavs_for_edge(near_miss, edge, state, values)
    if not candidates:
        return None

    rejected: LaneChangeCandidate | None = None
    for cav in candidates:
        to_lane = _receiving_lane_for_cav(cav, values)
        front, rear, margin_front, margin_rear = receiving_gap_for_vehicle(
            state,
            cav,
            to_lane,
        )
        feasibility_pass, reject_reason = validate_lane_change_candidate_fields(
            cav,
            to_lane,
            front,
            rear,
            margin_front,
            margin_rear,
            duration,
            values,
        )
        candidate = LaneChangeCandidate(
            candidate_id=f"lc_{index}_{near_miss.edge_id}",
            edge_id=near_miss.edge_id,
            cav_id=cav.id,
            from_lane=cav.lane,
            to_lane=to_lane,
            start_time=start_time,
            end_time=end_time,
            expected_gap_effect="move_target_lane_cav_to_inner_lane_reorder_boundary",
            receiving_gap_front_id=None if front is None else front.id,
            receiving_gap_rear_id=None if rear is None else rear.id,
            feasibility_pass=feasibility_pass,
            reject_reason=reject_reason,
            feasibility_margin_front=margin_front,
            feasibility_margin_rear=margin_rear,
        )
        if feasibility_pass:
            return candidate
        if rejected is None:
            rejected = candidate
    return rejected


def build_lane_change_profile(
    candidate: LaneChangeCandidate,
    params: ActionConfig | Mapping[str, Any] | Any | None = None,
) -> dict[str, Any]:
    values = coerce_action_config(params)
    duration = max(candidate.end_time - candidate.start_time, 0.0)
    profile = {
        "mode": "lane_change",
        "action_profile_feasible": candidate.feasibility_pass,
        "lane_change_candidate_id": candidate.candidate_id,
        "lc_from_lane": candidate.from_lane,
        "lc_to_lane": candidate.to_lane,
        "lc_start_time": candidate.start_time,
        "lc_end_time": candidate.end_time,
        "lc_duration": duration,
        "receiving_gap_id": _receiving_gap_id(
            candidate.receiving_gap_front_id,
            candidate.receiving_gap_rear_id,
        ),
        "receiving_gap_front_id": candidate.receiving_gap_front_id,
        "receiving_gap_rear_id": candidate.receiving_gap_rear_id,
        "lc_feasibility_margin_front": candidate.feasibility_margin_front,
        "lc_feasibility_margin_rear": candidate.feasibility_margin_rear,
        "lc_feasibility_pass": candidate.feasibility_pass,
        "lc_reject_reason": candidate.reject_reason,
        "lc_mode": values.lc_mode,
        "lc_expected_gap_effect": candidate.expected_gap_effect,
    }
    profile.update(compute_lane_change_cost(profile, values))
    return profile


def receiving_gap_for_vehicle(
    state: TrafficState,
    cav: VehicleState,
    to_lane: int,
) -> tuple[VehicleState | None, VehicleState | None, float, float]:
    """Find the receiving-lane gap around the CAV's current longitudinal x."""

    receiving = [
        vehicle
        for vehicle in state.vehicles.values()
        if vehicle.active and vehicle.lane == to_lane and vehicle.id != cav.id
    ]
    front = min((vehicle for vehicle in receiving if vehicle.x > cav.x), key=lambda item: item.x, default=None)
    rear = max((vehicle for vehicle in receiving if vehicle.x < cav.x), key=lambda item: item.x, default=None)
    if front is None or rear is None:
        return front, rear, -math.inf, -math.inf
    margin_front = front.x - front.length - cav.x
    margin_rear = cav.x - cav.length - rear.x
    return front, rear, margin_front, margin_rear


def lane_change_control_cav_for_edge(
    near_miss: NearMissEdge | None,
    edge: Edge,
    state: TrafficState,
    params: ActionConfig | Mapping[str, Any] | Any | None = None,
) -> VehicleState | None:
    """Select one outer/target-lane CAV that can be moved inward by the LC proxy."""

    candidates = lane_change_control_cavs_for_edge(near_miss, edge, state, params)
    return None if not candidates else candidates[0]


def lane_change_control_cavs_for_edge(
    near_miss: NearMissEdge | None,
    edge: Edge,
    state: TrafficState,
    params: ActionConfig | Mapping[str, Any] | Any | None = None,
) -> list[VehicleState]:
    """Return deterministic target-lane CAV choices for Wave 7 lane-change production.

    In this V0 lane numbering, ``target_lane`` is the outer mainline lane next to
    the ramp and ``target_lane + 1`` is the receiving inner mainline lane.  Wave 7
    only supports moving a controlled CAV out of the target lane into that inner
    lane; it does not model adjacent-lane insertion into the target lane.
    """

    del near_miss
    values = coerce_action_config(params)
    front = state.vehicles.get(edge.front_id)
    rear = state.vehicles.get(edge.rear_id)
    if front is None or rear is None:
        return []
    search_low = rear.x - values.lc_upstream_search_distance
    search_high = front.x
    candidates = [
        vehicle
        for vehicle in state.vehicles.values()
        if vehicle.active
        and vehicle.role == "mainline"
        and vehicle.veh_type == "CAV"
        and vehicle.lane == values.target_lane
        and search_low <= vehicle.x <= search_high
    ]
    return sorted(candidates, key=lambda item: (-item.x, item.id))


def validate_lane_change_candidate_fields(
    cav: VehicleState,
    to_lane: int,
    front: VehicleState | None,
    rear: VehicleState | None,
    margin_front: float,
    margin_rear: float,
    duration: float,
    params: ActionConfig,
) -> tuple[bool, str]:
    if cav.veh_type != "CAV":
        return False, "controlled_vehicle_not_cav"
    if cav.lane != params.target_lane:
        return False, "controlled_vehicle_not_in_target_lane"
    if to_lane < 0 or to_lane >= params.lanes:
        return False, "receiving_lane_missing"
    if to_lane != params.target_lane + 1:
        return False, "unsupported_lane_change_direction"
    if front is None or rear is None:
        return False, "receiving_gap_missing"
    if margin_front < params.lc_min_front_margin:
        return False, "front_margin_insufficient"
    if margin_rear < params.lc_min_rear_margin:
        return False, "rear_margin_insufficient"
    if duration > params.T_prod and not params.lc_allow_exceed_T_prod:
        return False, "duration_exceeds_T_prod"
    return True, ""


def _receiving_lane_for_cav(cav: VehicleState, values: ActionConfig) -> int:
    del cav
    return values.target_lane + 1


def _receiving_gap_id(front_id: int | None, rear_id: int | None) -> str:
    if front_id is None or rear_id is None:
        return ""
    return f"{front_id}-{rear_id}"


def compute_lane_change_cost(
    profile: Mapping[str, Any],
    params: ActionConfig | Mapping[str, Any] | Any | None = None,
) -> dict[str, float]:
    values = coerce_action_config(params)
    duration = float(profile.get("lc_duration", values.lc_duration))
    front_margin = float(profile.get("lc_feasibility_margin_front", -math.inf))
    rear_margin = float(profile.get("lc_feasibility_margin_rear", -math.inf))
    duration_penalty = values.lc_duration_penalty_weight * max(duration, 0.0)
    margin_front_short = max(values.lc_min_front_margin - front_margin, 0.0)
    margin_rear_short = max(values.lc_min_rear_margin - rear_margin, 0.0)
    margin_risk = values.lc_margin_risk_weight * (margin_front_short + margin_rear_short)
    disturbance = 0.0
    if bool(profile.get("lc_feasibility_pass", False)):
        disturbance = values.lc_disturbance_weight
    C_bar = values.lc_base_cost + duration_penalty + margin_risk + disturbance
    return {
        "lc_base_cost": values.lc_base_cost,
        "lc_duration_penalty": duration_penalty,
        "lc_margin_risk_penalty": margin_risk,
        "lc_disturbance_proxy": disturbance,
        "lc_cost": C_bar,
        "C_bar": C_bar,
    }


def lane_change_trace_fields(profile: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "lane_change_candidate_id": profile.get("lane_change_candidate_id", ""),
        "lc_feasibility_margin_front": profile.get("lc_feasibility_margin_front", ""),
        "lc_feasibility_margin_rear": profile.get("lc_feasibility_margin_rear", ""),
        "lc_expected_gap_effect": profile.get("lc_expected_gap_effect", ""),
    }


def build_boundary_speed_profile(
    mode: str,
    near_miss: NearMissEdge,
    edge: Edge,
    state: TrafficState,
    params: ActionConfig | Mapping[str, Any] | Any | None = None,
) -> dict[str, Any]:
    """Build a reproducible front/rear boundary-speed production profile."""

    values = coerce_action_config(params)
    requested = max(float(near_miss.delta_W_req), 0.0)
    delta_target = requested + values.production_width_buffer
    T_prod = max(0.0, min(values.T_prod, edge.tau - state.time))
    if T_prod <= 1e-9:
        return _profile(
            requested,
            delta_target,
            T_prod,
            0.0,
            0.0,
            True,
            0.0,
            False,
            mode,
        )
    if mode == "front_acc":
        raw_front = 2.0 * delta_target / (T_prod * T_prod)
        u_front = _clip(raw_front, 0.0, values.u_max_comfort)
        estimated = 0.5 * u_front * T_prod * T_prod
        return _profile(
            requested,
            delta_target,
            T_prod,
            u_front,
            0.0,
            abs(u_front - raw_front) > 1e-9,
            estimated,
            estimated + 1e-9 >= delta_target,
            mode,
        )
    if mode == "rear_dec":
        raw_rear = -2.0 * delta_target / (T_prod * T_prod)
        u_rear = _clip(raw_rear, values.u_min_comfort, 0.0)
        estimated = 0.5 * abs(u_rear) * T_prod * T_prod
        return _profile(
            requested,
            delta_target,
            T_prod,
            0.0,
            u_rear,
            abs(u_rear - raw_rear) > 1e-9,
            estimated,
            estimated + 1e-9 >= delta_target,
            mode,
        )
    if mode == "front_rear":
        candidates: list[dict[str, Any]] = []
        for alpha in (0.25, 0.5, 0.75):
            raw_front = 2.0 * (alpha * delta_target) / (T_prod * T_prod)
            raw_rear = -2.0 * ((1.0 - alpha) * delta_target) / (T_prod * T_prod)
            u_front = _clip(raw_front, 0.0, values.u_max_comfort)
            u_rear = _clip(raw_rear, values.u_min_comfort, 0.0)
            estimated = 0.5 * (u_front + abs(u_rear)) * T_prod * T_prod
            candidates.append(
                _profile(
                    requested,
                    delta_target,
                    T_prod,
                    u_front,
                    u_rear,
                    abs(u_front - raw_front) > 1e-9 or abs(u_rear - raw_rear) > 1e-9,
                    estimated,
                    estimated + 1e-9 >= delta_target,
                    mode,
                    alpha=alpha,
                )
            )
        feasible = [candidate for candidate in candidates if candidate["action_profile_feasible"]]
        pool = feasible or candidates
        return min(pool, key=lambda item: _normalized_effort(item, values))
    raise ValueError(f"Unknown Phase 5A action mode: {mode!r}")


def validate_single_action(action: Action, state: TrafficState) -> tuple[bool, str]:
    """Reject only invalid action-internal controls, not cross-candidate sharing."""

    if action.action_type == "none":
        return True, ""
    if not action.controlled_cavs:
        return False, "no_controlled_cav"
    if len(set(action.controlled_cavs)) != len(action.controlled_cavs):
        return False, "duplicate_cav_within_action"
    for vehicle_id in action.controlled_cavs:
        vehicle = state.vehicles.get(vehicle_id)
        if vehicle is None:
            return False, "controlled_vehicle_missing"
        if vehicle.veh_type != "CAV":
            return False, "controlled_vehicle_not_cav"
    return True, ""


def action_conditioned_rollout(
    action: Action,
    state: TrafficState,
    params: ActionConfig | Mapping[str, Any] | Any | None = None,
) -> dict[float, TrafficState]:
    """Roll out one action from the same current state with no fallback repair."""

    values = coerce_action_config(params)
    steps = max(1, int(round(values.H / values.dt)))
    rollout = {round(state.time, 10): state}
    current = state
    for _ in range(steps):
        commands = commands_for_action(action, current.time, values)
        current, _, _ = step_traffic(current, commands, _dynamics_config(values))
        rollout[round(current.time, 10)] = current
    return rollout


def evaluate_action(
    action: Action,
    state: TrafficState,
    params: ActionConfig | Mapping[str, Any] | Any | None = None,
    *,
    baseline_J: float | None = None,
) -> ActionEvaluation:
    """Regenerate slots, edges, and matching after one action-conditioned rollout."""

    values = coerce_action_config(params)
    if action.rejected_before_rollout:
        invalid_cost = {"invalid_action": 1.0}
        if action.action_type == "lane_change":
            invalid_cost = {
                **invalid_cost,
                **compute_lane_change_cost(action.control_profile, values),
                **lane_change_trace_fields(action.control_profile),
            }
        return ActionEvaluation(
            action_id=action.action_id,
            J=math.inf,
            Z_bar=math.inf,
            D_bar=math.inf,
            C_bar=math.inf,
            RCMV=-math.inf,
            S_R=0.0,
            Z_R=0.0,
            D_H=0.0,
            matched_edge_ids=[],
            selected=False,
            rejected_by_theta=True,
            cost_components=invalid_cost,
        )

    rollout = action_conditioned_rollout(action, state, values)
    slots, edges, qualities, matching_edges, matching = evaluate_rollout_inventory(
        rollout,
        state,
        action,
        values,
    )
    matched_rd_sum = compute_matched_recovery_debt(matching, qualities)
    cost = compute_production_cost(action, rollout, values)
    if action.action_type == "lane_change":
        cost = {**cost, **lane_change_trace_fields(action.control_profile)}
    objective = compute_objective(
        matching.Z_R,
        matching.D_H,
        matched_rd_sum,
        cost["C_bar"],
        values.lambda_D,
        values.lambda_C,
    )
    J = objective["J"]
    return ActionEvaluation(
        action_id=action.action_id,
        J=J,
        Z_bar=objective["Z_bar"],
        D_bar=objective["D_bar"],
        C_bar=objective["C_bar"],
        RCMV=0.0 if baseline_J is None else baseline_J - J,
        S_R=matching.S_R,
        Z_R=matching.Z_R,
        D_H=matching.D_H,
        matched_edge_ids=list(matching.selected_edge_ids),
        selected=False,
        rejected_by_theta=False,
        matched_count=len(matching.selected_edges),
        invalid_count=sum(1 for quality in qualities if not quality.is_reservable),
        cost_components=cost,
        matched_rd_sum=matched_rd_sum,
        matching_result=matching,
        slots=tuple(slots),
        edges=tuple(edges),
        edge_qualities=tuple(qualities),
        matching_edges=tuple(matching_edges),
        rollout=rollout,
    )


def evaluate_rollout_inventory(
    rollout: Mapping[float, TrafficState],
    state: TrafficState,
    action: Action,
    params: ActionConfig | Mapping[str, Any] | Any | None = None,
) -> tuple[list[Slot], list[Edge], list[EdgeQuality], list[MatchingEdge], MatchingResult]:
    """Run the Phase 2/3 inventory pipeline for a specific action context."""

    values = coerce_action_config(params)
    slots = generate_slots(
        rollout,
        t=state.time,
        H=values.H,
        dt_merge=values.dt_merge,
        target_lane=values.target_lane,
        eval_context="baseline" if action.action_type == "none" else "action",
        action_id=None if action.action_type == "none" else action.action_id,
    )
    ramps = [
        vehicle
        for vehicle in state.vehicles.values()
        if vehicle.active and vehicle.role == "ramp"
    ]
    edges = build_edges(ramps, slots)
    qualities = compute_edge_qualities(edges, rollout, state, slot_inventory_params(values))
    demand = {ramp.id: DemandRecord(ramp.id) for ramp in ramps}
    matching_edges = build_matching_edges(
        qualities,
        demand,
        edge_metadata=edge_metadata(edges),
    )
    matching = solve_matching_v0_greedy_conflict(
        matching_edges,
        demand,
        MatchingConfig(
            T_merge=values.T_merge,
            T_buffer=values.T_buffer,
            conflict_mode=values.conflict_mode,
        ),
    )
    return slots, edges, qualities, matching_edges, matching


def compute_objective(
    Z_R: float,
    D_H: float,
    matched_rd_sum: float,
    C_bar: float,
    lambda_D: float,
    lambda_C: float,
    eps: float = 1e-9,
) -> dict[str, float]:
    """Compute the Phase 5 objective components."""

    denom = D_H + eps
    Z_bar = float(Z_R) / denom
    D_bar = float(matched_rd_sum) / denom
    J = Z_bar + lambda_D * D_bar + lambda_C * float(C_bar)
    return {"J": J, "Z_bar": Z_bar, "D_bar": D_bar, "C_bar": float(C_bar)}


def compute_matched_recovery_debt(
    matching: MatchingResult,
    qualities: Sequence[EdgeQuality],
) -> float:
    quality_by_id = {quality.edge_id: quality for quality in qualities}
    return float(
        sum(quality_by_id[edge_id].RD for edge_id in matching.selected_edge_ids if edge_id in quality_by_id)
    )


def compute_production_cost(
    action: Action,
    rollout: Mapping[float, TrafficState] | None,
    params: ActionConfig | Mapping[str, Any] | Any | None = None,
) -> dict[str, float]:
    """Compute production effort/disturbance only, not RD."""

    del rollout
    values = coerce_action_config(params)
    if action.action_type == "none":
        return {"effort": 0.0, "disturbance": 0.0, "C_bar": 0.0}
    if action.action_type == "lane_change":
        return compute_lane_change_cost(action.control_profile, values)
    profile = action.control_profile
    u_front = abs(float(profile.get("u_front", 0.0)))
    u_rear = abs(float(profile.get("u_rear", 0.0)))
    denom = max(abs(values.u_max_comfort), abs(values.u_min_comfort), 1e-9)
    effort = (u_front + u_rear) / denom
    disturbance = 0.0 if bool(profile.get("action_profile_feasible", False)) else 1.0
    return {"effort": effort, "disturbance": disturbance, "C_bar": effort + disturbance}


def select_action(
    actions: Sequence[Action],
    evaluations: Sequence[ActionEvaluation],
    theta: float = 0.05,
) -> ActionSelectionResult:
    """Select max-RCMV action if it clears theta, otherwise select a0."""

    if not actions or not evaluations:
        raise ValueError("actions and evaluations must be non-empty")
    action_by_id = {action.action_id: action for action in actions}
    baseline = next((item for item in evaluations if item.action_id == "a0_none"), evaluations[0])
    ranked = sorted(evaluations, key=lambda item: (item.RCMV, -item.J, item.action_id), reverse=True)
    best = ranked[0]
    selected = best if best.RCMV > theta and math.isfinite(best.RCMV) else baseline
    final_evaluations: list[ActionEvaluation] = []
    rank_by_id = {evaluation.action_id: index + 1 for index, evaluation in enumerate(ranked)}
    for evaluation in evaluations:
        final_evaluations.append(
            _copy_evaluation_flags(
                evaluation,
                selected=evaluation.action_id == selected.action_id,
                rejected_by_theta=evaluation.action_id != "a0_none" and evaluation.RCMV <= theta,
                rank=rank_by_id[evaluation.action_id],
            )
        )
    final_selected = next(
        evaluation for evaluation in final_evaluations if evaluation.action_id == selected.action_id
    )
    return ActionSelectionResult(
        baseline_evaluation=baseline,
        evaluations=final_evaluations,
        selected_action=action_by_id[final_selected.action_id],
        selected_evaluation=final_selected,
    )


def run_action_selection(
    state: TrafficState,
    qualities: Sequence[EdgeQuality],
    edge_map: Mapping[str, Edge],
    params: ActionConfig | Mapping[str, Any] | Any | None = None,
) -> ActionSelectionResult:
    """End-to-end Wave 5A candidate generation, evaluation, and selection."""

    values = coerce_action_config(params)
    near_misses = find_near_miss_edges(qualities, edge_map, state, values)
    actions = generate_candidate_actions(near_misses, edge_map, state, values)
    baseline = evaluate_action(actions[0], state, values)
    evaluations = [baseline]
    for action in actions[1:]:
        evaluations.append(evaluate_action(action, state, values, baseline_J=baseline.J))
    return select_action(actions, evaluations, values.theta)


def ablation_without_action_conditioned_reservation(
    baseline_evaluation: ActionEvaluation,
    selected_evaluation: ActionEvaluation,
) -> dict[str, Any]:
    """Report the stale-reservation ablation without changing the selected action."""

    baseline_edges = list(baseline_evaluation.matched_edge_ids)
    selected_edges = list(selected_evaluation.matched_edge_ids)
    return {
        "stale_flag": True,
        "baseline_action_id": baseline_evaluation.action_id,
        "selected_action_id": selected_evaluation.action_id,
        "baseline_matched_edge_ids": baseline_edges,
        "action_conditioned_matched_edge_ids": selected_edges,
        "reservation_differs": baseline_edges != selected_edges,
    }


def controlled_cavs_for_mode(mode: str, edge: Edge, state: TrafficState) -> tuple[int, ...]:
    front = state.vehicles.get(edge.front_id)
    rear = state.vehicles.get(edge.rear_id)
    if mode == "front_acc" and front is not None and front.veh_type == "CAV":
        return (front.id,)
    if mode == "rear_dec" and rear is not None and rear.veh_type == "CAV":
        return (rear.id,)
    if mode == "front_rear":
        cavs: list[int] = []
        if front is not None and front.veh_type == "CAV":
            cavs.append(front.id)
        if rear is not None and rear.veh_type == "CAV":
            cavs.append(rear.id)
        return tuple(cavs)
    return ()


def commands_for_action(
    action: Action,
    current_time: float,
    params: ActionConfig | Mapping[str, Any] | Any | None = None,
) -> dict[int, dict[str, Any]]:
    """Return final production commands active within the production window."""

    values = coerce_action_config(params)
    if action.action_type == "none" or not action.controlled_cavs:
        return {}
    profile = action.control_profile
    if action.action_type == "lane_change":
        vehicle_id = action.controlled_cavs[0]
        start = float(profile.get("lc_start_time", 0.0))
        end = float(profile.get("lc_end_time", start))
        if current_time < start - 1e-9 or current_time > end + 1e-9:
            return {}
        command: dict[str, Any] = {
            "action_id": action.action_id,
            "lane_change": True,
            "lc_from_lane": profile.get("lc_from_lane"),
            "lc_to_lane": profile.get("lc_to_lane"),
            "lc_start_time": start,
            "lc_end_time": end,
            "lc_mode": profile.get("lc_mode", values.lc_mode),
        }
        return {vehicle_id: command}
    T_prod = float(profile.get("T_prod", values.T_prod))
    if current_time - 0.0 >= T_prod - 1e-9:
        return {}
    commands: dict[int, dict[str, Any]] = {}
    if action.action_type == "front_acc":
        commands[action.controlled_cavs[0]] = {
            "a_action": float(profile.get("u_front", 0.0)),
            "action_id": action.action_id,
        }
    elif action.action_type == "rear_dec":
        commands[action.controlled_cavs[-1]] = {
            "a_action": float(profile.get("u_rear", 0.0)),
            "action_id": action.action_id,
        }
    elif action.action_type == "front_rear":
        if len(action.controlled_cavs) >= 1:
            commands[action.controlled_cavs[0]] = {
                "a_action": float(profile.get("u_front", 0.0)),
                "action_id": action.action_id,
            }
        if len(action.controlled_cavs) >= 2:
            commands[action.controlled_cavs[1]] = {
                "a_action": float(profile.get("u_rear", 0.0)),
                "action_id": action.action_id,
            }
    return commands


def boundary_type_for_edge(state: TrafficState, edge: Edge) -> str:
    front = state.vehicles.get(edge.front_id)
    rear = state.vehicles.get(edge.rear_id)
    if front is None or rear is None:
        return "unknown"
    return f"{front.veh_type}-{rear.veh_type}"


def slot_inventory_params(params: ActionConfig | Mapping[str, Any] | Any | None = None) -> SlotInventoryParams:
    values = coerce_action_config(params)
    return SlotInventoryParams(
        H=values.H,
        dt_merge=values.dt_merge,
        target_lane=values.target_lane,
        W_min_buffer=values.W_min_buffer,
        RD_max=values.RD_max,
        d0=values.d0,
        T_safe=values.T_safe,
        T_front_CAV_following=values.T_front_CAV_following,
        T_rear_HDV_following=values.T_rear_HDV_following,
        b_safe=values.b_safe,
        u_min=values.u_min,
        u_max=values.u_max,
        rd_speed_scale=values.rd_speed_scale,
        ramp_end_x=values.ramp_end_x,
    )


def edge_metadata(edges: Sequence[Edge]) -> dict[str, dict[str, Any]]:
    return {
        edge.edge_id: {"physical_gap_id": edge.physical_gap_id, "tau": edge.tau}
        for edge in edges
    }


def action_to_row(
    action: Action,
    log_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    profile = action.control_profile
    lc_components = {
        key: profile.get(key, 0.0)
        for key in (
            "lc_base_cost",
            "lc_duration_penalty",
            "lc_margin_risk_penalty",
            "lc_disturbance_proxy",
        )
    }
    row = {
        "action_id": action.action_id,
        "action_type": action.action_type,
        "nominal_edge_id": action.nominal_edge_id,
        "controlled_cavs": action.controlled_cavs,
        "target_gap_id": action.target_gap_id,
        "boundary_type": action.boundary_type,
        "control_start": 0.0,
        "control_end": profile.get("T_prod", 0.0),
        "requested_delta_W": profile.get("requested_delta_W", 0.0),
        "delta_W_target": profile.get("delta_W_target", 0.0),
        "T_prod": profile.get("T_prod", 0.0),
        "u_front": profile.get("u_front", 0.0),
        "u_rear": profile.get("u_rear", 0.0),
        "profile_clip_flag": profile.get("profile_clip_flag", False),
        "estimated_delta_W_after_clip": profile.get("estimated_delta_W_after_clip", 0.0),
        "action_profile_feasible": profile.get("action_profile_feasible", False),
        "estimated_cost": action.estimated_cost,
        "rejected_before_rollout": action.rejected_before_rollout,
        "reject_reason": action.reject_reason,
        "lc_from_lane": profile.get("lc_from_lane", ""),
        "lc_to_lane": profile.get("lc_to_lane", ""),
        "lc_start_time": profile.get("lc_start_time", ""),
        "lc_end_time": profile.get("lc_end_time", ""),
        "lc_duration": profile.get("lc_duration", ""),
        "receiving_gap_id": profile.get("receiving_gap_id", ""),
        "lc_feasibility_pass": profile.get("lc_feasibility_pass", ""),
        "lc_reject_reason": profile.get("lc_reject_reason", ""),
        "lc_cost_components_json": _json_dumps_strict(lc_components),
        "lc_mode": profile.get("lc_mode", ""),
    }
    return {**dict(log_context or {}), **row}


def action_evaluation_to_row(
    evaluation: ActionEvaluation,
    log_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    cost = evaluation.cost_components or {}
    row = {
        "action_id": evaluation.action_id,
        "J": evaluation.J,
        "Z_bar": evaluation.Z_bar,
        "D_bar": evaluation.D_bar,
        "C_bar": evaluation.C_bar,
        "RCMV": evaluation.RCMV,
        "S_R": evaluation.S_R,
        "Z_R": evaluation.Z_R,
        "matched_count": evaluation.matched_count,
        "matched_edge_ids": evaluation.matched_edge_ids,
        "invalid_count": evaluation.invalid_count,
        "selected": evaluation.selected,
        "rank": evaluation.rank,
        "rejected_by_theta": evaluation.rejected_by_theta,
        "cost_components_json": _json_dumps_strict(evaluation.cost_components or {}),
        "matched_rd_sum": evaluation.matched_rd_sum,
        "lane_change_candidate_id": cost.get("lane_change_candidate_id", ""),
        "lc_cost": cost.get("lc_cost", cost.get("C_bar", "")),
        "lc_feasibility_margin_front": cost.get("lc_feasibility_margin_front", ""),
        "lc_feasibility_margin_rear": cost.get("lc_feasibility_margin_rear", ""),
        "lc_expected_gap_effect": cost.get("lc_expected_gap_effect", ""),
    }
    return {**dict(log_context or {}), **row}


def _json_dumps_strict(payload: Any) -> str:
    return json.dumps(
        _json_safe(payload),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _json_safe(value: Any) -> Any:
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def coerce_action_config(config: ActionConfig | Mapping[str, Any] | Any | None = None) -> ActionConfig:
    if config is None:
        return ActionConfig()
    if isinstance(config, ActionConfig):
        return config

    data = {
        "H": _config_value(config, "H", _nested_config_value(config, "sim", "H", 1.0)),
        "dt": _config_value(config, "dt", _nested_config_value(config, "sim", "dt", 0.5)),
        "dt_merge": _config_value(
            config,
            "dt_merge",
            _nested_config_value(config, "sim", "dt_merge", 1.0),
        ),
        "target_lane": _config_value(
            config,
            "target_lane",
            _nested_config_value(config, "sim", "target_lane", 0),
        ),
        "W_min_buffer": _config_value(
            config,
            "W_min_buffer",
            _nested_config_value(config, "algorithm", "W_min_buffer", 5.0),
        ),
        "RD_max": _config_value(
            config,
            "RD_max",
            _nested_config_value(config, "algorithm", "RD_max", 1.0),
        ),
        "d0": _config_value(config, "d0", 0.0),
        "T_safe": _config_value(config, "T_safe", 0.0),
        "T_front_CAV_following": _config_value(config, "T_front_CAV_following", None),
        "T_rear_HDV_following": _config_value(config, "T_rear_HDV_following", None),
        "b_safe": _config_value(config, "b_safe", None),
        "u_min": _config_value(config, "u_min", -4.5),
        "u_max": _config_value(config, "u_max", 2.0),
        "v_max": _config_value(config, "v_max", 40.0),
        "T_prod": _config_value(
            config,
            "T_prod",
            _nested_config_value(config, "algorithm", "T_prod", 3.0),
        ),
        "production_width_buffer": _config_value(
            config,
            "production_width_buffer",
            _nested_config_value(config, "algorithm", "production_width_buffer", 0.5),
        ),
        "lambda_D": _config_value(
            config,
            "lambda_D",
            _nested_config_value(config, "algorithm", "lambda_D", 1.0),
        ),
        "lambda_C": _config_value(
            config,
            "lambda_C",
            _nested_config_value(config, "algorithm", "lambda_C", 1.0),
        ),
        "theta": _config_value(
            config,
            "theta",
            _nested_config_value(config, "algorithm", "theta", 0.05),
        ),
        "u_max_comfort": _config_value(config, "u_max_comfort", _config_value(config, "u_max", 2.0)),
        "u_min_comfort": _config_value(config, "u_min_comfort", _config_value(config, "u_min", -4.5)),
        "rd_speed_scale": _config_value(config, "rd_speed_scale", 10.0),
        "ramp_end_x": _config_value(config, "ramp_end_x", None),
        "T_merge": _config_value(config, "T_merge", 1.0),
        "T_buffer": _config_value(config, "T_buffer", 0.0),
        "conflict_mode": _config_value(
            config,
            "conflict_mode",
            _nested_config_value(config, "algorithm", "conflict_mode", "time_window_default"),
        ),
        "near_miss_delta_W_max": _config_value(config, "near_miss_delta_W_max", 8.0),
        "near_miss_RD_max": _config_value(config, "near_miss_RD_max", 1.0),
        "action_mode": _validate_action_mode(_config_value(config, "action_mode", "override")),
        "event_min_gap": _config_value(config, "event_min_gap", 0.0),
        "lanes": _config_value(config, "lanes", _nested_config_value(config, "road", "lanes", 2)),
        "enable_boundary_speed": _config_value(config, "enable_boundary_speed", True),
        "enable_lane_change": _config_value(config, "enable_lane_change", False),
        "lc_duration": _config_value(config, "lc_duration", _config_value(config, "T_prod", 1.0)),
        "lc_min_front_margin": _config_value(config, "lc_min_front_margin", 3.0),
        "lc_min_rear_margin": _config_value(config, "lc_min_rear_margin", 3.0),
        "lc_base_cost": _config_value(config, "lc_base_cost", 0.05),
        "lc_duration_penalty_weight": _config_value(config, "lc_duration_penalty_weight", 0.02),
        "lc_margin_risk_weight": _config_value(config, "lc_margin_risk_weight", 0.10),
        "lc_disturbance_weight": _config_value(config, "lc_disturbance_weight", 0.05),
        "lc_allow_exceed_T_prod": _config_value(config, "lc_allow_exceed_T_prod", False),
        "lc_mode": _config_value(config, "lc_mode", "discrete_switch_at_end"),
        "lc_upstream_search_distance": _config_value(config, "lc_upstream_search_distance", 80.0),
    }
    return ActionConfig(**data)


def _near_miss_from_label(
    label: NearMissLabel,
    quality: EdgeQuality,
    edge: Edge,
    boundary_type: str,
) -> NearMissEdge:
    return NearMissEdge(
        edge_id=quality.edge_id,
        near_miss_type=label.near_miss_type,
        delta_W_req=label.delta_W_req,
        available_modes=label.available_modes,
        screen_score=label.screen_score,
        selected_for_rollout=True,
        ramp_id=edge.ramp_id,
        slot_id=edge.slot_id,
        front_id=edge.front_id,
        rear_id=edge.rear_id,
        tau=edge.tau,
        boundary_type=boundary_type,
        W=quality.W,
        RD=quality.RD,
        reason=label.reason,
    )


def _profile(
    requested_delta_W: float,
    delta_W_target: float,
    T_prod: float,
    u_front: float,
    u_rear: float,
    profile_clip_flag: bool,
    estimated_delta_W_after_clip: float,
    action_profile_feasible: bool,
    mode: str,
    *,
    alpha: float | None = None,
) -> dict[str, Any]:
    return {
        "mode": mode,
        "requested_delta_W": requested_delta_W,
        "delta_W_target": delta_W_target,
        "T_prod": T_prod,
        "u_front": u_front,
        "u_rear": u_rear,
        "profile_clip_flag": profile_clip_flag,
        "estimated_delta_W_after_clip": estimated_delta_W_after_clip,
        "action_profile_feasible": action_profile_feasible,
        "alpha": alpha,
    }


def _normalized_effort(profile: Mapping[str, Any], values: ActionConfig) -> float:
    return (
        abs(float(profile.get("u_front", 0.0))) / max(values.u_max_comfort, 1e-9)
        + abs(float(profile.get("u_rear", 0.0))) / max(abs(values.u_min_comfort), 1e-9)
    )


def compute_profile_cost(profile: Mapping[str, Any], params: ActionConfig) -> float:
    return _normalized_effort(profile, params) + (
        0.0 if bool(profile.get("action_profile_feasible", False)) else 1.0
    )


def _validate_action_mode(value: Any) -> str:
    mode = str(value)
    if mode != "override":
        raise ValueError(f"Unsupported action command mode: {mode!r}")
    return mode


def _dynamics_config(values: ActionConfig) -> dict[str, Any]:
    return {
        "dt": values.dt,
        "action_mode": values.action_mode,
        "limits": {"u_min": values.u_min, "u_max": values.u_max, "v_max": values.v_max},
        "min_gap": values.event_min_gap,
    }


def _copy_evaluation_flags(
    evaluation: ActionEvaluation,
    *,
    selected: bool,
    rejected_by_theta: bool,
    rank: int,
) -> ActionEvaluation:
    return ActionEvaluation(
        action_id=evaluation.action_id,
        J=evaluation.J,
        Z_bar=evaluation.Z_bar,
        D_bar=evaluation.D_bar,
        C_bar=evaluation.C_bar,
        RCMV=evaluation.RCMV,
        S_R=evaluation.S_R,
        Z_R=evaluation.Z_R,
        D_H=evaluation.D_H,
        matched_edge_ids=list(evaluation.matched_edge_ids),
        selected=selected,
        rejected_by_theta=rejected_by_theta,
        matched_count=evaluation.matched_count,
        invalid_count=evaluation.invalid_count,
        rank=rank,
        cost_components=evaluation.cost_components,
        matched_rd_sum=evaluation.matched_rd_sum,
        matching_result=evaluation.matching_result,
        slots=evaluation.slots,
        edges=evaluation.edges,
        edge_qualities=evaluation.edge_qualities,
        matching_edges=evaluation.matching_edges,
        rollout=evaluation.rollout,
    )


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _config_value(config: Any, name: str, default: Any = None) -> Any:
    if config is None:
        return default
    if isinstance(config, Mapping):
        return config.get(name, default)
    if isinstance(config, ScenarioConfig):
        merged = _scenario_values(config)
        return merged.get(name, default)
    if isinstance(config, RunConfig):
        return _run_config_value(config, name, default)
    value = getattr(config, name, None)
    return default if value is None else value


def _nested_config_value(config: Any, section: str, name: str, default: Any = None) -> Any:
    parent = _config_value(config, section)
    return _config_value(parent, name, default)


def _run_config_value(config: RunConfig, name: str, default: Any = None) -> Any:
    if hasattr(config, name):
        return getattr(config, name)
    for section in (config.sim, config.algorithm):
        value = _config_value(section, name, None)
        if value is not None:
            return value
    return default


def _scenario_values(config: ScenarioConfig) -> dict[str, Any]:
    return {**config.road, **config.simulation, **config.vehicles, **config.ramp}


__all__ = [
    "Action",
    "ActionConfig",
    "ActionEvaluation",
    "ActionSelectionResult",
    "LaneChangeCandidate",
    "NearMissEdge",
    "ablation_without_action_conditioned_reservation",
    "action_conditioned_rollout",
    "action_evaluation_to_row",
    "action_to_row",
    "boundary_type_for_edge",
    "build_boundary_speed_profile",
    "build_lane_change_candidate",
    "build_lane_change_profile",
    "coerce_action_config",
    "commands_for_action",
    "compute_lane_change_cost",
    "compute_matched_recovery_debt",
    "compute_objective",
    "compute_production_cost",
    "controlled_cavs_for_mode",
    "edge_metadata",
    "evaluate_action",
    "evaluate_rollout_inventory",
    "find_lane_change_candidates",
    "find_near_miss_edges",
    "generate_candidate_actions",
    "lane_change_control_cav_for_edge",
    "lane_change_control_cavs_for_edge",
    "lane_change_trace_fields",
    "receiving_gap_for_vehicle",
    "run_action_selection",
    "select_action",
    "slot_inventory_params",
    "validate_lane_change_candidate_fields",
    "validate_single_action",
]
