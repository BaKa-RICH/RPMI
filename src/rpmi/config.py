"""Configuration dataclasses and stable serialization for Phase 0."""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any, Literal
import hashlib
import json

import yaml


@dataclass(frozen=True)
class SimConfig:
    dt: float = 0.1
    H: float = 12.0
    dt_merge: float = 0.5
    total_time: float = 30.0
    decision_mode: Literal["single_t0_micro_episode", "rolling"] = (
        "single_t0_micro_episode"
    )
    target_lane: int = 0
    ramp_lane: int = -1


@dataclass(frozen=True)
class AlgorithmConfig:
    RD_max: float = 1.0
    W_min_buffer: float = 0.0
    production_width_buffer: float = 0.5
    W_prod_bar: float = 6.0
    lambda_D: float = 1.0
    lambda_C: float = 1.0
    theta: float = 0.05
    top_k_actions: int = 8
    T_prod: float = 3.0
    conflict_mode: Literal[
        "time_window_default", "whole_horizon_debug", "slot_only_debug"
    ] = "time_window_default"


@dataclass(frozen=True)
class DemandWeightConfig:
    chi_w: float = 0.0
    chi_d: float = 0.0
    d_crit: float = 120.0
    epsilon_D: float = 1e-9
    default_omega: float = 1.0


@dataclass(frozen=True)
class FeatureFlags:
    stochastic_idm: bool = False
    sumo: bool = False
    mobil: bool = False
    action_bundle: bool = False
    learning: bool = False
    lane_change_production: bool = False
    rolling_reservation: bool = False


@dataclass(frozen=True)
class RunConfig:
    scenario_id: str = "phase0_empty"
    algorithm_id: str = "rpmi_v0_phase0"
    seed: int = 0
    sim: SimConfig = SimConfig()
    algorithm: AlgorithmConfig = AlgorithmConfig()
    demand: DemandWeightConfig = DemandWeightConfig()
    flags: FeatureFlags = FeatureFlags()
    log_level: Literal["summary", "trace", "debug"] = "trace"


DISALLOWED_V0_FLAGS = {
    "stochastic_idm": "stochastic IDM is reserved for Phase 7.",
    "sumo": "SUMO integration is not part of deterministic Python V0 Wave 0.",
    "mobil": "MOBIL lane-change behavior is not part of deterministic Python V0.",
    "action_bundle": "Action bundle logic is forbidden before later phases.",
    "learning": "Learning/RL is outside deterministic Python V0.",
    "lane_change_production": "Lane-change production is reserved for Phase 5B.",
    "rolling_reservation": "Rolling reservation is reserved for Phase 6B.",
}


class FeatureFlagError(ValueError):
    """Raised when a forbidden V0 feature flag is enabled."""


def _coerce_dataclass(cls: type[Any], value: Any) -> Any:
    if isinstance(value, cls):
        return value
    if value is None:
        return cls()
    if not isinstance(value, dict):
        raise TypeError(f"{cls.__name__} must be built from a mapping")
    return cls(**value)


def run_config_from_dict(data: dict[str, Any]) -> RunConfig:
    """Build a RunConfig from a plain mapping."""

    values = dict(data)
    values["sim"] = _coerce_dataclass(SimConfig, values.get("sim"))
    values["algorithm"] = _coerce_dataclass(
        AlgorithmConfig, values.get("algorithm")
    )
    values["demand"] = _coerce_dataclass(DemandWeightConfig, values.get("demand"))
    values["flags"] = _coerce_dataclass(FeatureFlags, values.get("flags"))
    return RunConfig(**values)


def load_config(path: str | Path) -> RunConfig:
    """Load a YAML or JSON config file into RunConfig."""

    config_path = Path(path)
    text = config_path.read_text(encoding="utf-8")
    if config_path.suffix.lower() == ".json":
        raw = json.loads(text)
    elif config_path.suffix.lower() in {".yaml", ".yml"}:
        raw = yaml.safe_load(text) or {}
    else:
        raise ValueError(f"Unsupported config file type: {config_path.suffix}")
    if not isinstance(raw, dict):
        raise TypeError("Run config file must contain a mapping")
    return run_config_from_dict(raw)


def validate_v0_flags(config: RunConfig) -> None:
    """Reject features explicitly forbidden for deterministic Python V0 Wave 0."""

    enabled: list[str] = []
    for name in DISALLOWED_V0_FLAGS:
        if getattr(config.flags, name):
            enabled.append(f"{name}: {DISALLOWED_V0_FLAGS[name]}")
    if enabled:
        joined = "; ".join(enabled)
        raise FeatureFlagError(f"Forbidden V0 feature flag(s) enabled: {joined}")
    if config.sim.decision_mode != "single_t0_micro_episode":
        raise FeatureFlagError(
            "Phase 0 locks decision_mode to single_t0_micro_episode; "
            f"got {config.sim.decision_mode!r}."
        )


def stable_json(obj: dict[str, Any]) -> str:
    """Serialize a JSON-compatible mapping with stable ordering."""

    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _canonicalize(value: Any) -> Any:
    if is_dataclass(value):
        return _canonicalize(asdict(value))
    if isinstance(value, dict):
        return {str(key): _canonicalize(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_canonicalize(item) for item in value]
    return value


def config_to_snapshot_dict(config: RunConfig) -> dict[str, Any]:
    """Return the complete deterministic config snapshot saved with each run."""

    return _canonicalize(config)


def config_to_canonical_dict(
    config: RunConfig,
    *,
    include_seed: bool = False,
) -> dict[str, Any]:
    """Return a deterministic config dictionary suitable for hashing.

    By default the random seed is stored separately and excluded from the config
    hash, so the same scenario/algorithm parameters can be grouped across seeds.
    """

    canonical = config_to_snapshot_dict(config)
    if not include_seed:
        canonical.pop("seed", None)
    return canonical


def hash_config(config_dict: dict[str, Any], n: int = 12) -> str:
    """Hash a canonical config dictionary."""

    return hashlib.sha256(stable_json(config_dict).encode("utf-8")).hexdigest()[:n]
