"""Traffic state primitives and stable state hashing."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal
from typing import Any
import hashlib

from rpmi.config import stable_json


@dataclass
class VehicleState:
    """One vehicle represented by front-bumper position."""

    id: int
    role: Literal["mainline", "ramp"]
    veh_type: Literal["CAV", "HDV"]
    lane: int
    x: float
    v: float
    a: float
    length: float = 5.0
    active: bool = True
    idm_params: dict[str, float] | None = None
    cav_limits: dict[str, float] | None = None
    reservation_id: str | None = None


@dataclass(frozen=True)
class RoadConfig:
    """Minimal road geometry used by deterministic Python V0 dynamics."""

    lanes: int
    target_lane: int
    ramp_lane: int = -1
    merge_zone: tuple[float, float] = (300.0, 420.0)
    ramp_end_x: float = 420.0


@dataclass
class TrafficState:
    """Simulation state at one absolute time and integer step."""

    time: float
    step: int
    vehicles: dict[int, VehicleState]


def state_to_canonical_dict(state: TrafficState | dict[str, Any]) -> dict[str, Any]:
    """Convert a traffic state or plain mapping into a stable hash payload."""

    if isinstance(state, TrafficState):
        payload = asdict(state)
        payload["vehicles"] = {
            str(vehicle_id): payload["vehicles"][vehicle_id]
            for vehicle_id in sorted(payload["vehicles"])
        }
        return payload
    return state


def hash_state(state: TrafficState | dict[str, Any], n: int = 12) -> str:
    """Hash canonical state JSON.

    Phase 0 does not define traffic dynamics or scenario generation. This helper
    only provides the stable hash contract later phases will reuse for fairness
    checks across baseline/proposed runs.
    """

    payload = state_to_canonical_dict(state)
    return hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()[:n]
