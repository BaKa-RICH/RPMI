"""Action-conditioned reservation lifecycle for Phase 5A."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Literal, Mapping, Sequence

from rpmi.actions import ActionEvaluation
from rpmi.ids import make_reservation_id
from rpmi.slots import Edge, compute_feasible_interval
from rpmi.state import TrafficState


ReservationStatus = Literal[
    "planned",
    "active_guidance",
    "merged",
    "expired",
    "failed_unreachable",
    "failed_invalid_slot",
    "failed_unsafe_margin",
]


@dataclass
class Reservation:
    reservation_id: str
    decision_context_id: str
    ramp_id: int
    edge_id: str
    slot_id: str
    action_id: str
    planned_tau: float
    planned_merge_x: float
    planned_interval_lower: float
    planned_interval_upper: float
    status: ReservationStatus = "planned"
    failure_reason: str = ""
    actual_x_at_tau: float | None = None
    actual_margin_front: float | None = None
    actual_margin_rear: float | None = None
    stale_flag: bool = False


def create_reservations(
    selected_eval: ActionEvaluation,
    edge_map: Mapping[str, Edge] | None = None,
    *,
    decision_context_id: str = "dc_wave5a",
    stale_flag: bool = False,
) -> list[Reservation]:
    """Create reservations from the selected action-conditioned matching."""

    del edge_map
    edge_by_id = {edge.edge_id: edge for edge in selected_eval.edges}
    quality_by_id = {quality.edge_id: quality for quality in selected_eval.edge_qualities}
    state_by_tau = dict(selected_eval.rollout or {})
    reservations: list[Reservation] = []
    for edge_id in selected_eval.matched_edge_ids:
        edge = edge_by_id.get(edge_id)
        quality = quality_by_id.get(edge_id)
        state_tau = state_by_tau.get(round(edge.tau, 10)) if edge is not None else None
        if edge is None or quality is None or state_tau is None:
            continue
        interval = compute_feasible_interval(edge, state_tau)
        planned_x = (interval.lower + interval.upper) / 2.0
        reservations.append(
            Reservation(
                reservation_id=make_reservation_id(selected_eval.action_id, edge.edge_id),
                decision_context_id=decision_context_id,
                ramp_id=edge.ramp_id,
                edge_id=edge.edge_id,
                slot_id=edge.slot_id,
                action_id=selected_eval.action_id,
                planned_tau=edge.tau,
                planned_merge_x=planned_x,
                planned_interval_lower=interval.lower,
                planned_interval_upper=interval.upper,
                stale_flag=stale_flag,
            )
        )
    return reservations


def execute_reservation_guidance(
    state: TrafficState,
    reservations: Sequence[Reservation],
    t: float,
    *,
    guidance_gain: float = 1.0,
    u_min: float = -4.5,
    u_max: float = 2.0,
) -> tuple[dict[int, dict[str, Any]], list[Reservation]]:
    """Issue simple ramp guidance commands before tau without hidden repair."""

    commands: dict[int, dict[str, Any]] = {}
    updated: list[Reservation] = []
    for reservation in reservations:
        if reservation.status not in {"planned", "active_guidance"}:
            updated.append(reservation)
            continue
        if t >= reservation.planned_tau:
            updated.append(reservation)
            continue
        ramp = state.vehicles.get(reservation.ramp_id)
        if ramp is None or not ramp.active:
            updated.append(
                replace(
                    reservation,
                    status="failed_unreachable",
                    failure_reason="ramp_missing_or_inactive",
                )
            )
            continue
        remaining = max(reservation.planned_tau - t, 1e-9)
        a_req = 2.0 * (
            reservation.planned_merge_x - ramp.x - ramp.v * remaining
        ) / (remaining * remaining)
        a_cmd = max(u_min, min(u_max, guidance_gain * a_req))
        commands[reservation.ramp_id] = {
            "a_action": a_cmd,
            "reservation_id": reservation.reservation_id,
        }
        updated.append(replace(reservation, status="active_guidance"))
    return commands, updated


def update_reservation_at_tau(
    state: TrafficState,
    reservation: Reservation,
    edge: Edge,
    *,
    tolerance: float = 1e-6,
    unsafe_margin_epsilon: float = 1e-9,
) -> Reservation:
    """Evaluate merge success/failure at tau and record only."""

    if reservation.status in {"merged", "expired"} or reservation.status.startswith("failed_"):
        return reservation
    if state.time > reservation.planned_tau + tolerance:
        return replace(reservation, status="expired", failure_reason="missed_tau")
    if abs(state.time - reservation.planned_tau) > tolerance:
        return reservation

    ramp = state.vehicles.get(reservation.ramp_id)
    front = state.vehicles.get(edge.front_id)
    rear = state.vehicles.get(edge.rear_id)
    if ramp is None or front is None or rear is None:
        return replace(reservation, status="failed_invalid_slot", failure_reason="missing_vehicle_at_tau")
    interval = compute_feasible_interval(edge, state)
    actual_x = ramp.x
    margin_front = interval.upper - actual_x
    margin_rear = actual_x - interval.lower
    base = replace(
        reservation,
        actual_x_at_tau=actual_x,
        actual_margin_front=margin_front,
        actual_margin_rear=margin_rear,
    )
    if interval.V_phys_theory == 0:
        return replace(base, status="failed_invalid_slot", failure_reason="physical_width_negative")
    if margin_front < -unsafe_margin_epsilon or margin_rear < -unsafe_margin_epsilon:
        return replace(base, status="failed_unsafe_margin", failure_reason="negative_actual_margin")
    state.vehicles[reservation.ramp_id].lane = state.vehicles[edge.front_id].lane
    state.vehicles[reservation.ramp_id].reservation_id = reservation.reservation_id
    return replace(base, status="merged", failure_reason="")


def update_reservations_at_tau(
    state: TrafficState,
    reservations: Sequence[Reservation],
    edge_map: Mapping[str, Edge],
    *,
    tolerance: float = 1e-6,
) -> list[Reservation]:
    """Update every reservation at the current state time."""

    updated: list[Reservation] = []
    for reservation in reservations:
        edge = edge_map.get(reservation.edge_id)
        if edge is None:
            updated.append(
                replace(
                    reservation,
                    status="failed_invalid_slot",
                    failure_reason="edge_missing",
                )
            )
            continue
        updated.append(update_reservation_at_tau(state, reservation, edge, tolerance=tolerance))
    return updated


def reservation_to_row(
    reservation: Reservation,
    log_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    row = {
        "reservation_id": reservation.reservation_id,
        "decision_context_id": reservation.decision_context_id,
        "ramp_id": reservation.ramp_id,
        "edge_id": reservation.edge_id,
        "slot_id": reservation.slot_id,
        "action_id": reservation.action_id,
        "planned_tau": reservation.planned_tau,
        "planned_merge_x": reservation.planned_merge_x,
        "planned_interval_lower": reservation.planned_interval_lower,
        "planned_interval_upper": reservation.planned_interval_upper,
        "actual_x_at_tau": reservation.actual_x_at_tau,
        "actual_margin_front": reservation.actual_margin_front,
        "actual_margin_rear": reservation.actual_margin_rear,
        "status": reservation.status,
        "failure_reason": reservation.failure_reason,
        "stale_flag": reservation.stale_flag,
    }
    return {**dict(log_context or {}), **row}


__all__ = [
    "Reservation",
    "ReservationStatus",
    "create_reservations",
    "execute_reservation_guidance",
    "reservation_to_row",
    "update_reservation_at_tau",
    "update_reservations_at_tau",
]
