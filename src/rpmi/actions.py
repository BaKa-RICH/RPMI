"""Boundary-speed RCMV action selection for Phase 5A.

Wave 5A deliberately implements only single boundary-speed actions.  Lane
change, action bundles, rolling horizon, and fallback repair remain outside
this module.
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
from rpmi.state import TrafficState


ActionType = Literal["none", "front_acc", "rear_dec", "front_rear"]


@dataclass(frozen=True)
class ActionConfig:
    """Phase 5A action-selection parameters."""

    H: float = 1.0
    dt: float = 0.5
    dt_merge: float = 1.0
    target_lane: int = 0
    W_min_buffer: float = 5.0
    RD_max: float = 1.0
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
    action_mode: str = "additive_clip"
    event_min_gap: float = 0.0


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
    cost_components: dict[str, float] | None = None
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
            {
                "near_miss_delta_W_max": values.near_miss_delta_W_max,
                "near_miss_RD_max": values.near_miss_RD_max,
            },
        )
        if not label.is_near_miss:
            continue
        near_misses.append(_near_miss_from_label(label, quality, edge, boundary_type))
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
    for near_miss in near_misses:
        edge = edge_map.get(near_miss.edge_id)
        if edge is None:
            continue
        for mode in near_miss.available_modes:
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
            cost_components={"invalid_action": 1.0},
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
    """Return overlay commands active within the production window."""

    values = coerce_action_config(params)
    if action.action_type == "none" or not action.controlled_cavs:
        return {}
    profile = action.control_profile
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
    }
    return {**dict(log_context or {}), **row}


def action_evaluation_to_row(
    evaluation: ActionEvaluation,
    log_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
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
        "cost_components_json": json.dumps(
            evaluation.cost_components or {},
            sort_keys=True,
            separators=(",", ":"),
        ),
        "matched_rd_sum": evaluation.matched_rd_sum,
    }
    return {**dict(log_context or {}), **row}


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
        "action_mode": _config_value(config, "action_mode", "additive_clip"),
        "event_min_gap": _config_value(config, "event_min_gap", 0.0),
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
    "NearMissEdge",
    "ablation_without_action_conditioned_reservation",
    "action_conditioned_rollout",
    "action_evaluation_to_row",
    "action_to_row",
    "boundary_type_for_edge",
    "build_boundary_speed_profile",
    "coerce_action_config",
    "commands_for_action",
    "compute_matched_recovery_debt",
    "compute_objective",
    "compute_production_cost",
    "controlled_cavs_for_mode",
    "edge_metadata",
    "evaluate_action",
    "evaluate_rollout_inventory",
    "find_near_miss_edges",
    "generate_candidate_actions",
    "run_action_selection",
    "select_action",
    "slot_inventory_params",
    "validate_single_action",
]
