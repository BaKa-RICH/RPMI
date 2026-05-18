"""Phase 0 ID convention helpers."""

from __future__ import annotations


def make_decision_context_id(run_id: str, step: int = 0) -> str:
    return f"dc_{run_id}_{step}"


def make_slot_id(
    front_id: str,
    rear_id: str,
    k: int,
    action_context: str = "baseline",
) -> str:
    return f"slot_{front_id}_{rear_id}_k{k}_{action_context}"


def make_edge_id(
    ramp_id: str,
    front_id: str,
    rear_id: str,
    k: int,
    action_context: str = "baseline",
) -> str:
    return f"edge_{ramp_id}_{front_id}_{rear_id}_k{k}_{action_context}"


def make_action_id(action_type: str, index: int) -> str:
    return f"act_{action_type}_{index}"


def make_reservation_id(action_id: str, edge_id: str) -> str:
    return f"res_{action_id}_{edge_id}"

