"""State hashing placeholder for Phase 0 fairness checks."""

from __future__ import annotations

from typing import Any
import hashlib

from rpmi.config import stable_json


def hash_state(state: dict[str, Any], n: int = 12) -> str:
    """Hash canonical state JSON.

    Phase 0 does not define traffic dynamics or scenario generation. This helper
    only provides the stable hash contract later phases will reuse for fairness
    checks across baseline/proposed runs.
    """

    return hashlib.sha256(stable_json(state).encode("utf-8")).hexdigest()[:n]

