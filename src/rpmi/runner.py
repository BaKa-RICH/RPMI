"""Phase 0 run initialization compatibility entry point.

No traffic dynamics, scenarios, slots, edges, matching, actions, reservations,
or RCMV behavior is implemented here.
"""

from __future__ import annotations

from pathlib import Path

from rpmi.config import RunConfig
from rpmi.run import RunArtifacts, init_run


def initialize_run(
    config: RunConfig,
    output_root: str | Path,
    *,
    run_id: str | None = None,
    code_version: str | None = None,
) -> RunArtifacts:
    """Create an empty Phase 0 run directory."""

    return init_run(
        config,
        output_root,
        run_id=run_id,
        code_version=code_version,
    )


__all__ = ["RunArtifacts", "initialize_run"]

