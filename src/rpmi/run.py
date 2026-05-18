"""Run directory creation and Phase 0 artifact initialization."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json

from rpmi.config import (
    RunConfig,
    config_to_canonical_dict,
    config_to_snapshot_dict,
    hash_config,
    stable_json,
    validate_v0_flags,
)
from rpmi.conventions import write_global_conventions
from rpmi.logging_schema import init_empty_logs
from rpmi.reproducibility import get_code_version, make_run_id, set_global_seed


@dataclass(frozen=True)
class RunArtifacts:
    run_id: str
    run_dir: Path
    config_hash: str
    code_version: str


def create_run_directory(output_root: str | Path, run_id: str) -> Path:
    """Create a new run directory and standard subdirectories."""

    run_dir = Path(output_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    for name in ["figures", "debug_snapshots", "tables"]:
        (run_dir / name).mkdir()
    return run_dir


def init_run(
    config: RunConfig,
    output_root: str | Path = "outputs",
    *,
    run_id: str | None = None,
    code_version: str | None = None,
) -> RunArtifacts:
    """Initialize a Phase 0 empty run and return its artifact paths."""

    validate_v0_flags(config)
    canonical_config = config_to_canonical_dict(config)
    snapshot_config = config_to_snapshot_dict(config)
    config_hash = hash_config(canonical_config)
    resolved_run_id = run_id or make_run_id(config, config_hash)
    resolved_code_version = code_version or get_code_version(Path.cwd())
    set_global_seed(config.seed)

    run_dir = create_run_directory(output_root, resolved_run_id)
    (run_dir / "run_config.json").write_text(
        json.dumps(snapshot_config, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "config_canonical.json").write_text(
        stable_json(canonical_config) + "\n",
        encoding="utf-8",
    )
    (run_dir / "config_hash.txt").write_text(config_hash + "\n", encoding="utf-8")
    (run_dir / "seed.txt").write_text(str(config.seed) + "\n", encoding="utf-8")
    (run_dir / "code_version.txt").write_text(
        resolved_code_version + "\n",
        encoding="utf-8",
    )
    write_global_conventions(run_dir / "global_conventions.json", config)
    init_empty_logs(run_dir)
    return RunArtifacts(
        run_id=resolved_run_id,
        run_dir=run_dir,
        config_hash=config_hash,
        code_version=resolved_code_version,
    )
