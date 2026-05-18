"""Global units, join-key, and ID conventions for Phase 0."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from rpmi.config import RunConfig


UNITS_VERSION = "rpmi_units_v1"
CONVENTIONS_VERSION = "rpmi_global_conventions_v1"


def build_global_conventions(config: RunConfig) -> dict[str, Any]:
    """Build the global dictionary required by Phase 0."""

    return {
        "conventions_version": CONVENTIONS_VERSION,
        "units_version": UNITS_VERSION,
        "units": {
            "distance": "meter",
            "time": "second",
            "speed": "m/s",
            "acceleration": "m/s^2",
        },
        "position": {
            "x": "front_bumper_position",
            "occupied_interval": "[x - length, x]",
            "same_lane_order": "larger x is further downstream/front",
        },
        "lanes": {
            "target_lane": config.sim.target_lane,
            "ramp_lane": config.sim.ramp_lane,
        },
        "time_indexing": {
            "time": "absolute simulation time",
            "step": "integer simulation step",
            "dt": config.sim.dt,
        },
        "ids": {
            "decision_context_id": "dc_{run_id}_{step}",
            "slot_id": "slot_{front_id}_{rear_id}_k{k}_{action_context}",
            "edge_id": "edge_{ramp_id}_{front_id}_{rear_id}_k{k}_{action_context}",
            "action_id": "act_{action_type}_{index}",
            "reservation_id": "res_{action_id}_{edge_id}",
        },
        "hashes": {
            "state_hash": "canonical JSON hash of initial state",
            "config_hash": "canonical JSON hash of RunConfig",
        },
        "code_version": "git commit if available, otherwise local_dirty",
        "forbidden_phase0_scope": [
            "traffic_dynamics",
            "slot_generation",
            "edge_generation",
            "matching",
            "RCMV",
            "SUMO",
            "MOBIL",
            "RL",
            "action_bundle",
        ],
    }


def write_global_conventions(path: str | Path, config: RunConfig) -> dict[str, Any]:
    """Write global_conventions.json and return the dictionary."""

    conventions = build_global_conventions(config)
    Path(path).write_text(
        json.dumps(conventions, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return conventions

