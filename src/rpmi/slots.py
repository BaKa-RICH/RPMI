"""Time-expanded slot and edge inventory for deterministic Python V0."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Literal, Mapping, Sequence
import json

from rpmi.dynamics import compute_gap_margin, sort_lane_vehicles
from rpmi.ids import make_edge_id as _make_edge_id
from rpmi.ids import make_slot_id as _make_slot_id
from rpmi.state import TrafficState, VehicleState


ReasonCode = Literal[
    "OK",
    "UNREACHABLE",
    "PHYS_WIDTH_NEGATIVE",
    "BUFFER_WIDTH_INSUFFICIENT",
    "SAFETY_MARGIN_NEGATIVE",
    "HIGH_RECOVERY_DEBT",
    "RAMP_END_INFEASIBLE",
    "SPEED_INCOMPATIBLE",
    "SURV_DISABLED_BY_MODE",
    "UNKNOWN_INVALID",
]


@dataclass(frozen=True)
class SlotInventoryParams:
    H: float = 12.0
    dt_merge: float = 0.5
    target_lane: int = 0
    W_min_buffer: float = 0.0
    RD_max: float = 1.0
    d0: float = 0.0
    T_safe: float = 0.0
    T_front_CAV_following: float | None = None
    T_rear_HDV_following: float | None = None
    b_safe: float | None = None
    u_min: float = -4.5
    u_max: float = 2.0
    rd_speed_scale: float = 10.0
    ramp_length_default: float = 5.0
    ramp_end_x: float | None = None


@dataclass(frozen=True)
class Slot:
    slot_id: str
    front_id: int
    rear_id: int
    k: int
    tau: float
    physical_gap_id: tuple[int, int]
    eval_context: Literal["baseline", "action"] | str
    action_id: str | None
    gap_at_tau: float
    boundary_type: str = "target_lane_adjacent_pair"


@dataclass(frozen=True)
class Edge:
    edge_id: str
    ramp_id: int
    front_id: int
    rear_id: int
    k: int
    tau: float
    slot_id: str
    physical_gap_id: tuple[int, int]
    eval_context: str
    action_id: str | None


@dataclass(frozen=True)
class IntervalResult:
    lower: float
    upper: float
    width: float
    d_front: float
    d_rear: float
    V_phys_theory: int
    V_phys_buffer: int
    delta_W_req: float


@dataclass(frozen=True)
class EdgeQuality:
    edge_id: str
    ramp_id: int
    slot_id: str
    I_reach: int
    I_surv: int
    I_safe: int
    I_rec: int
    P_R: float
    RD: float
    W: float
    V_phys_theory: int
    V_phys_buffer: int
    delta_W_req: float
    is_reservable: bool
    reason_not_reservable: str
    fail_reason_priority: str
    surv_mode: str
    validity_mode: str
    rd_components: dict[str, Any]
    min_safety_margin: float
    reachability: dict[str, float | int | str]


def generate_time_grid(t: float, H: float, dt_merge: float) -> list[tuple[int, float]]:
    """Generate candidate merge times ``k=1..K`` and exclude the current time."""

    if H < 0.0:
        raise ValueError("H must be non-negative")
    if dt_merge <= 0.0:
        raise ValueError("dt_merge must be positive")
    out: list[tuple[int, float]] = []
    k = 1
    while t + k * dt_merge <= t + H + 1e-9:
        out.append((k, round(t + k * dt_merge, 10)))
        k += 1
    return out


def get_target_lane_pairs(
    state_tau: TrafficState,
    lane: int,
) -> list[tuple[VehicleState, VehicleState]]:
    """Return adjacent target-lane boundary pairs as ``(front, rear)``."""

    vehicles = sort_lane_vehicles(state_tau, lane)
    return list(zip(vehicles, vehicles[1:]))


def make_slot_id(
    front_id: int | str,
    rear_id: int | str,
    k: int,
    action_context: str = "baseline",
) -> str:
    return _make_slot_id(str(front_id), str(rear_id), k, action_context)


def make_edge_id(
    ramp_id: int | str,
    front_id: int | str,
    rear_id: int | str,
    k: int,
    action_context: str = "baseline",
) -> str:
    return _make_edge_id(
        str(ramp_id),
        str(front_id),
        str(rear_id),
        k,
        action_context,
    )


def generate_slots(
    rollout: Mapping[float, TrafficState] | Sequence[TrafficState],
    *,
    t: float,
    H: float,
    dt_merge: float,
    target_lane: int,
    eval_context: Literal["baseline", "action"] | str = "baseline",
    action_id: str | None = None,
) -> list[Slot]:
    """Generate time-expanded slots from predicted states at each candidate tau."""

    slots: list[Slot] = []
    action_context = action_id or eval_context
    for k, tau in generate_time_grid(t, H, dt_merge):
        state_tau = _state_at_time(rollout, tau)
        if state_tau is None:
            continue
        for front, rear in get_target_lane_pairs(state_tau, target_lane):
            slots.append(
                Slot(
                    slot_id=make_slot_id(front.id, rear.id, k, action_context),
                    front_id=front.id,
                    rear_id=rear.id,
                    k=k,
                    tau=tau,
                    physical_gap_id=(front.id, rear.id),
                    eval_context=eval_context,
                    action_id=action_id,
                    gap_at_tau=compute_gap_margin(front, rear),
                )
            )
    return slots


def build_edges(
    ramps: Iterable[VehicleState | int],
    slots: Iterable[Slot],
) -> list[Edge]:
    """Build ramp-aware pair edges as the ramp-slot Cartesian product."""

    edges: list[Edge] = []
    for ramp in ramps:
        ramp_id = ramp if isinstance(ramp, int) else ramp.id
        for slot in slots:
            action_context = slot.action_id or slot.eval_context
            edges.append(
                Edge(
                    edge_id=make_edge_id(
                        ramp_id,
                        slot.front_id,
                        slot.rear_id,
                        slot.k,
                        action_context,
                    ),
                    ramp_id=int(ramp_id),
                    front_id=slot.front_id,
                    rear_id=slot.rear_id,
                    k=slot.k,
                    tau=slot.tau,
                    slot_id=slot.slot_id,
                    physical_gap_id=slot.physical_gap_id,
                    eval_context=slot.eval_context,
                    action_id=slot.action_id,
                )
            )
    return edges


def compute_safety_distances(
    edge: Edge,
    state_tau: TrafficState,
    params: SlotInventoryParams | Mapping[str, Any] | Any | None = None,
) -> tuple[float, float]:
    """Compute front and rear safety distances used by the interval formula."""

    values = coerce_inventory_params(params)
    front = state_tau.vehicles[edge.front_id]
    ramp = state_tau.vehicles[edge.ramp_id]
    rear = state_tau.vehicles[edge.rear_id]
    T_front = _safety_time_headway(values.T_front_CAV_following, values.T_safe)
    T_rear = _safety_time_headway(values.T_rear_HDV_following, values.T_safe)
    b_safe = None if values.b_safe is None else max(values.b_safe, 1e-9)
    closing_front = max(ramp.v - front.v, 0.0)
    closing_rear = max(rear.v - ramp.v, 0.0)
    front_closing_term = 0.0 if b_safe is None else closing_front * closing_front / (2.0 * b_safe)
    rear_closing_term = 0.0 if b_safe is None else closing_rear * closing_rear / (2.0 * b_safe)
    d_front = (
        values.d0
        + T_front * max(ramp.v, 0.0)
        + front_closing_term
    )
    d_rear = (
        values.d0
        + T_rear * max(rear.v, 0.0)
        + rear_closing_term
    )
    return d_front, d_rear


def compute_feasible_interval(
    edge: Edge,
    state_tau: TrafficState,
    params: SlotInventoryParams | Mapping[str, Any] | Any | None = None,
) -> IntervalResult:
    """Compute the feasible merge-position interval and width flags."""

    values = coerce_inventory_params(params)
    front = state_tau.vehicles[edge.front_id]
    rear = state_tau.vehicles[edge.rear_id]
    ramp = state_tau.vehicles[edge.ramp_id]
    d_front, d_rear = compute_safety_distances(edge, state_tau, values)
    ramp_length = ramp.length or values.ramp_length_default

    lower = rear.x + ramp_length + d_rear
    upper = front.x - front.length - d_front
    width = upper - lower
    return IntervalResult(
        lower=lower,
        upper=upper,
        width=width,
        d_front=d_front,
        d_rear=d_rear,
        V_phys_theory=int(width >= 0.0),
        V_phys_buffer=int(width >= values.W_min_buffer),
        delta_W_req=max(values.W_min_buffer - width, 0.0),
    )


def evaluate_reachability(
    ramp: VehicleState,
    interval: IntervalResult,
    delta_T: float,
    params: SlotInventoryParams | Mapping[str, Any] | Any | None = None,
) -> dict[str, float | int | str]:
    """Evaluate whether the ramp vehicle can reach the interval by tau."""

    values = coerce_inventory_params(params)
    if delta_T <= 0.0:
        return {
            "I_reach": 0,
            "x_min": ramp.x,
            "x_max": ramp.x,
            "a_req": 0.0,
            "reach_reason": "UNREACHABLE",
        }

    x_min = ramp.x + ramp.v * delta_T + 0.5 * values.u_min * delta_T * delta_T
    x_max = ramp.x + ramp.v * delta_T + 0.5 * values.u_max * delta_T * delta_T
    target_x = min(max((interval.lower + interval.upper) / 2.0, interval.lower), interval.upper)
    a_req = 2.0 * (target_x - ramp.x - ramp.v * delta_T) / (delta_T * delta_T)
    reachable = interval.width >= 0.0 and x_max >= interval.lower and x_min <= interval.upper
    reason = "OK" if reachable else "UNREACHABLE"
    if values.ramp_end_x is not None and interval.lower > values.ramp_end_x:
        reachable = False
        reason = "RAMP_END_INFEASIBLE"
    return {
        "I_reach": int(reachable),
        "x_min": x_min,
        "x_max": x_max,
        "a_req": a_req,
        "reach_reason": reason,
    }


def evaluate_survival(edge: Edge, mode: str = "deterministic_tau_generated") -> dict[str, int | str]:
    """Evaluate deterministic V0 survival for tau-generated slots."""

    if mode == "deterministic_tau_generated":
        return {
            "I_surv": 1,
            "surv_mode": "deterministic_tau_generated",
            "surv_reason": "slot_generated_from_state_at_tau",
        }
    return {
        "I_surv": 0,
        "surv_mode": mode,
        "surv_reason": "SURV_DISABLED_BY_MODE",
    }


def evaluate_safety(
    edge: Edge,
    state_tau: TrafficState,
    interval: IntervalResult,
) -> dict[str, float | int | str]:
    """Evaluate the explicit buffer safety screen without repairing the edge."""

    del edge, state_tau
    margin = interval.width
    if interval.V_phys_theory == 0:
        return {
            "I_safe": 0,
            "min_safety_margin": margin,
            "safety_reason": "PHYS_WIDTH_NEGATIVE",
        }
    if interval.V_phys_buffer == 0:
        return {
            "I_safe": 0,
            "min_safety_margin": margin,
            "safety_reason": "BUFFER_WIDTH_INSUFFICIENT",
        }
    return {
        "I_safe": 1,
        "min_safety_margin": margin,
        "safety_reason": "OK",
    }


def compute_recovery_debt(
    edge: Edge,
    state_tau: TrafficState,
    interval: IntervalResult,
    params: SlotInventoryParams | Mapping[str, Any] | Any | None = None,
) -> dict[str, Any]:
    """Compute the minimal deterministic V0 RD proxy and its components."""

    values = coerce_inventory_params(params)
    front = state_tau.vehicles[edge.front_id]
    rear = state_tau.vehicles[edge.rear_id]
    ramp = state_tau.vehicles[edge.ramp_id]
    scale = max(values.rd_speed_scale, 1e-9)
    buffer_scale = max(values.W_min_buffer, 1e-9)

    B = _clip01(max(0.0, rear.v - ramp.v) / scale)
    A = _clip01(abs(front.v - rear.v) / scale)
    T = _clip01(max(0.0, values.W_min_buffer - interval.width) / buffer_scale)
    RD = (B + A + T) / 3.0
    components = {
        "proxy_mode": "RD_proxy_v0_minimal",
        "B": B,
        "A": A,
        "T": T,
        "N_aff": None,
        "Q_loss": None,
        "W_min_buffer": values.W_min_buffer,
        "d0": values.d0,
        "T_safe": values.T_safe,
        "T_front_CAV_following": values.T_front_CAV_following,
        "T_rear_HDV_following": values.T_rear_HDV_following,
        "b_safe": values.b_safe,
    }
    return {"RD": RD, "rd_components": components}


def compute_edge_validity(
    edge: Edge,
    state_tau: TrafficState,
    current_state: TrafficState,
    params: SlotInventoryParams | Mapping[str, Any] | Any | None = None,
    *,
    survival_mode: str = "deterministic_tau_generated",
) -> EdgeQuality:
    """Evaluate deterministic Phase 2 edge validity cascade."""

    values = coerce_inventory_params(params)
    interval = compute_feasible_interval(edge, state_tau, values)
    delta_T = edge.tau - current_state.time
    ramp_current = current_state.vehicles[edge.ramp_id]
    reach = evaluate_reachability(ramp_current, interval, delta_T, values)
    surv = evaluate_survival(edge, survival_mode)
    safe = evaluate_safety(edge, state_tau, interval)
    rd = compute_recovery_debt(edge, state_tau, interval, values)

    I_reach = int(reach["I_reach"])
    I_surv = int(surv["I_surv"])
    I_safe = int(safe["I_safe"])
    RD = float(rd["RD"])
    I_rec = int(RD <= values.RD_max)
    P_R = float(I_reach * I_surv * I_safe * I_rec)
    reason = _reason_for_edge(
        reach_reason=str(reach["reach_reason"]),
        surv_reason=str(surv["surv_reason"]),
        safety_reason=str(safe["safety_reason"]),
        interval=interval,
        I_rec=I_rec,
        P_R=P_R,
    )
    return EdgeQuality(
        edge_id=edge.edge_id,
        ramp_id=edge.ramp_id,
        slot_id=edge.slot_id,
        I_reach=I_reach,
        I_surv=I_surv,
        I_safe=I_safe,
        I_rec=I_rec,
        P_R=P_R,
        RD=RD,
        W=interval.width,
        V_phys_theory=interval.V_phys_theory,
        V_phys_buffer=interval.V_phys_buffer,
        delta_W_req=interval.delta_W_req,
        is_reservable=(P_R == 1.0 and interval.V_phys_buffer == 1),
        reason_not_reservable=reason,
        fail_reason_priority=reason,
        surv_mode=str(surv["surv_mode"]),
        validity_mode="deterministic_v0_cascade_rd_proxy_v0_minimal",
        rd_components=dict(rd["rd_components"]),
        min_safety_margin=float(safe["min_safety_margin"]),
        reachability=reach,
    )


def compute_edge_qualities(
    edges: Iterable[Edge],
    rollout: Mapping[float, TrafficState] | Sequence[TrafficState],
    current_state: TrafficState,
    params: SlotInventoryParams | Mapping[str, Any] | Any | None = None,
) -> list[EdgeQuality]:
    """Evaluate qualities for edges whose tau state exists in the rollout."""

    qualities: list[EdgeQuality] = []
    for edge in edges:
        state_tau = _state_at_time(rollout, edge.tau)
        if state_tau is None:
            continue
        qualities.append(compute_edge_validity(edge, state_tau, current_state, params))
    return qualities


def compute_inventory_metrics(
    edge_qualities: Sequence[EdgeQuality],
    demand_weights: Mapping[int, float] | None = None,
    matching_hook: Callable[[Sequence[EdgeQuality], Mapping[int, float]], Any] | None = None,
) -> dict[str, Any]:
    """Compute Phase 2 inventory metrics through an optional matching hook."""

    ramp_ids = sorted({quality.ramp_id for quality in edge_qualities})
    weights = dict(demand_weights or {ramp_id: 1.0 for ramp_id in ramp_ids})
    D_H = float(sum(weights.values()))
    selected = _selected_qualities(edge_qualities, weights, matching_hook)
    S_H_R = float(sum(weights.get(quality.ramp_id, 1.0) * quality.P_R for quality in selected))
    Z_H_R = max(D_H - S_H_R, 0.0)
    reservable_edge_count = sum(1 for quality in edge_qualities if quality.is_reservable)
    reservable_slot_count = len(
        {quality.slot_id for quality in edge_qualities if quality.is_reservable}
    )
    matched_edge_count = len(selected)
    sanity_pass = (
        0.0 <= S_H_R <= D_H
        and Z_H_R == max(D_H - S_H_R, 0.0)
        and matched_edge_count <= min(len(weights), reservable_slot_count)
        and reservable_edge_count <= len(edge_qualities)
    )
    return {
        "D_H": D_H,
        "S_H_R": S_H_R,
        "Z_H_R": Z_H_R,
        "matched_edge_count": matched_edge_count,
        "reservable_edge_count": reservable_edge_count,
        "reservable_slot_count": reservable_slot_count,
        "total_edge_count": len(edge_qualities),
        "ramp_count": len(weights),
        "inventory_sanity_pass": sanity_pass,
        "sanity_rule": "0 <= S_H_R <= D_H; Z_H_R=max(D_H-S_H_R,0)",
    }


def slot_to_row(slot: Slot, log_context: Mapping[str, Any] | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {
        "slot_id": slot.slot_id,
        "front_id": slot.front_id,
        "rear_id": slot.rear_id,
        "k": slot.k,
        "tau": slot.tau,
        "physical_gap_id": slot.physical_gap_id,
        "eval_context": slot.eval_context,
        "action_id": slot.action_id,
        "gap_at_tau": slot.gap_at_tau,
        "boundary_type": slot.boundary_type,
    }
    return {**dict(log_context or {}), **row}


def edge_quality_to_row(
    edge: Edge,
    quality: EdgeQuality,
    log_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "edge_id": edge.edge_id,
        "ramp_id": edge.ramp_id,
        "slot_id": edge.slot_id,
        "front_id": edge.front_id,
        "rear_id": edge.rear_id,
        "k": edge.k,
        "tau": edge.tau,
        "eval_context": edge.eval_context,
        "action_id": edge.action_id,
        "physical_gap_id": edge.physical_gap_id,
        "I_reach": quality.I_reach,
        "I_surv": quality.I_surv,
        "I_safe": quality.I_safe,
        "I_rec": quality.I_rec,
        "P_R": quality.P_R,
        "V_phys_theory": quality.V_phys_theory,
        "V_phys_buffer": quality.V_phys_buffer,
        "W": quality.W,
        "delta_W_req": quality.delta_W_req,
        "RD": quality.RD,
        "rd_components_json": json.dumps(
            quality.rd_components,
            sort_keys=True,
            separators=(",", ":"),
        ),
        "is_reservable": quality.is_reservable,
        "reason_not_reservable": quality.reason_not_reservable,
        "fail_reason_priority": quality.fail_reason_priority,
        "surv_mode": quality.surv_mode,
        "validity_mode": quality.validity_mode,
    }
    return {**dict(log_context or {}), **row}


def coerce_inventory_params(
    params: SlotInventoryParams | Mapping[str, Any] | Any | None,
) -> SlotInventoryParams:
    if params is None:
        return SlotInventoryParams()
    if isinstance(params, SlotInventoryParams):
        return params

    data = {
        "H": _config_value(params, "H", _nested_config_value(params, "sim", "H", 12.0)),
        "dt_merge": _config_value(
            params,
            "dt_merge",
            _nested_config_value(params, "sim", "dt_merge", 0.5),
        ),
        "target_lane": _config_value(
            params,
            "target_lane",
            _nested_config_value(params, "sim", "target_lane", 0),
        ),
        "W_min_buffer": _config_value(
            params,
            "W_min_buffer",
            _nested_config_value(params, "algorithm", "W_min_buffer", 0.0),
        ),
        "RD_max": _config_value(
            params,
            "RD_max",
            _nested_config_value(params, "algorithm", "RD_max", 1.0),
        ),
        "d0": _config_value(params, "d0", 0.0),
        "T_safe": _config_value(params, "T_safe", 0.0),
        "T_front_CAV_following": _config_value(params, "T_front_CAV_following", None),
        "T_rear_HDV_following": _config_value(params, "T_rear_HDV_following", None),
        "b_safe": _config_value(params, "b_safe", None),
        "u_min": _config_value(params, "u_min", -4.5),
        "u_max": _config_value(params, "u_max", 2.0),
        "rd_speed_scale": _config_value(params, "rd_speed_scale", 10.0),
        "ramp_length_default": _config_value(params, "ramp_length_default", 5.0),
        "ramp_end_x": _config_value(params, "ramp_end_x", None),
    }
    return SlotInventoryParams(**data)


def _state_at_time(
    rollout: Mapping[float, TrafficState] | Sequence[TrafficState],
    tau: float,
) -> TrafficState | None:
    if isinstance(rollout, Mapping):
        if tau in rollout:
            return rollout[tau]
        rounded = round(tau, 10)
        return rollout.get(rounded)
    for state in rollout:
        if abs(state.time - tau) <= 1e-9:
            return state
    return None


def _selected_qualities(
    qualities: Sequence[EdgeQuality],
    weights: Mapping[int, float],
    matching_hook: Callable[[Sequence[EdgeQuality], Mapping[int, float]], Any] | None,
) -> list[EdgeQuality]:
    if matching_hook is None:
        return []
    result = matching_hook(qualities, weights)
    if result is None:
        return []
    if isinstance(result, Mapping):
        selected = result.get("selected_edges", [])
    else:
        selected = getattr(result, "selected_edges", result)
    selected_ids = {item for item in selected if isinstance(item, str)}
    if selected_ids:
        return [
            quality
            for quality in qualities
            if quality.edge_id in selected_ids and quality.is_reservable
        ]
    out: list[EdgeQuality] = []
    seen: set[str] = set()
    for item in selected:
        if not isinstance(item, EdgeQuality):
            continue
        if not item.is_reservable or item.edge_id in seen:
            continue
        seen.add(item.edge_id)
        out.append(item)
    return out


def _reason_for_edge(
    *,
    reach_reason: str,
    surv_reason: str,
    safety_reason: str,
    interval: IntervalResult,
    I_rec: int,
    P_R: float,
) -> ReasonCode:
    if interval.V_phys_theory == 0:
        return "PHYS_WIDTH_NEGATIVE"
    if surv_reason == "SURV_DISABLED_BY_MODE":
        return "SURV_DISABLED_BY_MODE"
    if reach_reason != "OK":
        return reach_reason if reach_reason in _REASON_CODES else "UNREACHABLE"
    if safety_reason == "BUFFER_WIDTH_INSUFFICIENT":
        return "BUFFER_WIDTH_INSUFFICIENT"
    if safety_reason != "OK":
        return safety_reason if safety_reason in _REASON_CODES else "SAFETY_MARGIN_NEGATIVE"
    if I_rec == 0:
        return "HIGH_RECOVERY_DEBT"
    if P_R == 1.0:
        return "OK"
    return "UNKNOWN_INVALID"


def _config_value(config: Any, name: str, default: Any = None) -> Any:
    if isinstance(config, Mapping):
        return config.get(name, default)
    value = getattr(config, name, None)
    return default if value is None else value


def _nested_config_value(config: Any, section: str, name: str, default: Any = None) -> Any:
    parent = _config_value(config, section)
    return _config_value(parent, name, default)


def _safety_time_headway(value: float | None, fallback: float) -> float:
    return fallback if value is None else float(value)


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, value))


_REASON_CODES = {
    "OK",
    "UNREACHABLE",
    "PHYS_WIDTH_NEGATIVE",
    "BUFFER_WIDTH_INSUFFICIENT",
    "SAFETY_MARGIN_NEGATIVE",
    "HIGH_RECOVERY_DEBT",
    "RAMP_END_INFEASIBLE",
    "SPEED_INCOMPATIBLE",
    "SURV_DISABLED_BY_MODE",
    "UNKNOWN_INVALID",
}


__all__ = [
    "Edge",
    "EdgeQuality",
    "IntervalResult",
    "ReasonCode",
    "Slot",
    "SlotInventoryParams",
    "build_edges",
    "coerce_inventory_params",
    "compute_edge_qualities",
    "compute_edge_validity",
    "compute_feasible_interval",
    "compute_inventory_metrics",
    "compute_recovery_debt",
    "compute_safety_distances",
    "edge_quality_to_row",
    "evaluate_reachability",
    "evaluate_safety",
    "evaluate_survival",
    "generate_slots",
    "generate_time_grid",
    "get_target_lane_pairs",
    "make_edge_id",
    "make_slot_id",
    "slot_to_row",
]
