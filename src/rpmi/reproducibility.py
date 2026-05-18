"""Seed, version, and run-id helpers for reproducible runs."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import random
import subprocess

import numpy as np

from rpmi.config import RunConfig


def set_global_seed(seed: int) -> np.random.Generator:
    """Set Python and NumPy global seeds, then return an explicit Generator."""

    random.seed(seed)
    np.random.seed(seed)
    return np.random.default_rng(seed)


def make_run_id(
    config: RunConfig,
    config_hash: str,
    timestamp: datetime | None = None,
) -> str:
    """Create a traceable run id."""

    stamp_time = timestamp or datetime.now(timezone.utc)
    stamp = stamp_time.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return (
        f"run_{stamp}_{config.scenario_id}_{config.algorithm_id}_"
        f"seed{config.seed:04d}_{config_hash}"
    )


def get_code_version(repo_root: str | Path | None = None) -> str:
    """Return git commit when available; otherwise use the Phase 0 fallback."""

    cwd = Path(repo_root) if repo_root is not None else None
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return "local_dirty"
    value = result.stdout.strip()
    return value or "local_dirty"


def deterministic_fake_state(seed: int, n: int = 5) -> dict[str, Any]:
    """Small deterministic state fixture for Phase 0 reproducibility tests."""

    rng = np.random.default_rng(seed)
    vehicles = []
    for idx in range(n):
        vehicles.append(
            {
                "vehicle_id": f"veh_{idx}",
                "x": round(float(rng.uniform(0.0, 500.0)), 6),
                "v": round(float(rng.uniform(5.0, 30.0)), 6),
                "lane": int(rng.choice([-1, 0])),
                "length": 4.5,
            }
        )
    return {"schema_version": "phase0_fake_state_v1", "vehicles": vehicles}

