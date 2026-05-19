"""Diagnostic conflict-aware matching for Phase 3A."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Literal, Mapping, Sequence
import math

from rpmi.slots import EdgeQuality


ConflictMode = Literal[
    "time_window_default",
    "whole_horizon_debug",
    "slot_only_debug",
]


@dataclass(frozen=True)
class MatchingConfig:
    T_merge: float = 1.0
    T_buffer: float = 0.0
    conflict_mode: ConflictMode = "time_window_default"
    epsilon_RD: float = 1e-6
    matching_id: str = "m_greedy_conflict"


@dataclass(frozen=True)
class DemandRecord:
    ramp_id: int
    omega: float = 1.0
    wait_time: float = 0.0
    distance_to_ramp_end: float = 0.0
    in_R_H: bool = True
    chi_w: float = 0.0
    chi_d: float = 0.0
    d_crit: float = 120.0


@dataclass(frozen=True)
class MatchingEdge:
    edge_id: str
    ramp_id: int
    slot_id: str
    physical_gap_id: tuple[int, int]
    tau: float
    P_R: float
    RD: float
    weight: float


@dataclass
class MatchingResult:
    matching_id: str
    selected_edges: list[MatchingEdge]
    selected_edge_ids: list[str]
    S_R: float
    Z_R: float
    D_H: float
    unmatched_ramps: list[int]
    conflict_mode: str
    solver_name: str
    objective_value: float


@dataclass(frozen=True)
class ToyS0Sample:
    sample_id: str
    scenario_id: str
    seed: int
    edge_qualities: tuple[EdgeQuality, ...]
    demand_records: tuple[DemandRecord, ...]
    raw_gap_count: int
    raw_time_expanded_slot_count: int
    density_imbalance: float
    speed_difference: float
    future_ramp_waiting: float
    failed_reservation_count: int
    slot_expiration_count: int
    hard_brake_count: int
    recovery_time: float
    speed_wave_amplitude: float
    invalid_event_count: int


def compute_demand_weights(
    ramps: Iterable[int | Any],
    config: Any | Mapping[str, Any] | None = None,
) -> dict[int, DemandRecord]:
    """Compute demand weights, defaulting to omega_r=1."""

    chi_w = float(_config_value(config, "chi_w", _nested_config_value(config, "demand", "chi_w", 0.0)))
    chi_d = float(_config_value(config, "chi_d", _nested_config_value(config, "demand", "chi_d", 0.0)))
    d_crit = float(_config_value(config, "d_crit", _nested_config_value(config, "demand", "d_crit", 120.0)))
    default_omega = float(
        _config_value(config, "default_omega", _nested_config_value(config, "demand", "default_omega", 1.0))
    )
    demand: dict[int, DemandRecord] = {}
    for ramp in ramps:
        ramp_id = int(_config_value(ramp, "id", ramp))
        wait_time = float(_config_value(ramp, "wait_time", 0.0))
        distance = float(_config_value(ramp, "distance_to_ramp_end", d_crit))
        if chi_w == 0.0 and chi_d == 0.0:
            omega = default_omega
        else:
            omega = default_omega + chi_w * wait_time
            omega += chi_d * max(d_crit - distance, 0.0) / max(d_crit, 1e-9)
        demand[ramp_id] = DemandRecord(
            ramp_id=ramp_id,
            omega=omega,
            wait_time=wait_time,
            distance_to_ramp_end=distance,
            in_R_H=True,
            chi_w=chi_w,
            chi_d=chi_d,
            d_crit=d_crit,
        )
    return demand


def build_matching_edges(
    edge_qualities: Sequence[EdgeQuality],
    demand: Mapping[int, DemandRecord | float],
    *,
    epsilon_RD: float = 1e-6,
    edge_metadata: Mapping[str, Any] | None = None,
) -> list[MatchingEdge]:
    """Convert reservable edge qualities into weighted matching edges."""

    edges: list[MatchingEdge] = []
    for quality in edge_qualities:
        if not quality.is_reservable:
            continue
        omega = _omega_for_ramp(demand, quality.ramp_id)
        metadata = {} if edge_metadata is None else edge_metadata.get(quality.edge_id, {})
        edges.append(
            MatchingEdge(
                edge_id=quality.edge_id,
                ramp_id=quality.ramp_id,
                slot_id=quality.slot_id,
                physical_gap_id=_physical_gap_from_metadata(metadata, quality.slot_id),
                tau=_tau_from_metadata(metadata, quality),
                P_R=quality.P_R,
                RD=quality.RD,
                weight=omega * quality.P_R - epsilon_RD * quality.RD,
            )
        )
    return edges


def edges_conflict(
    e1: MatchingEdge,
    e2: MatchingEdge,
    mode: ConflictMode | str = "time_window_default",
    *,
    T_merge: float = 1.0,
    T_buffer: float = 0.0,
) -> bool:
    """Return whether two edges conflict under the requested diagnostic mode."""

    if e1.ramp_id == e2.ramp_id:
        return True
    if e1.slot_id == e2.slot_id:
        return True
    if mode == "whole_horizon_debug":
        return e1.physical_gap_id == e2.physical_gap_id
    if mode == "time_window_default":
        return (
            e1.physical_gap_id == e2.physical_gap_id
            and abs(e1.tau - e2.tau) < T_merge + T_buffer
        )
    if mode == "slot_only_debug":
        return False
    raise ValueError(f"Unknown conflict mode: {mode!r}")


def solve_matching_v0_greedy_conflict(
    edges: Sequence[MatchingEdge],
    demand: Mapping[int, DemandRecord | float],
    config: MatchingConfig | Mapping[str, Any] | Any | None = None,
    *,
    conflict_mode: ConflictMode | str | None = None,
) -> MatchingResult:
    """Default Phase 3A conflict-aware greedy matching solver."""

    params = coerce_matching_config(config)
    mode = conflict_mode or params.conflict_mode
    selected: list[MatchingEdge] = []
    for edge in sorted(edges, key=lambda item: (item.weight, item.P_R, -item.RD, item.edge_id), reverse=True):
        if any(
            edges_conflict(
                edge,
                chosen,
                mode,
                T_merge=params.T_merge,
                T_buffer=params.T_buffer,
            )
            for chosen in selected
        ):
            continue
        selected.append(edge)
    return _matching_result(
        params.matching_id,
        selected,
        demand,
        mode,
        "greedy_conflict",
        sum(edge.weight for edge in selected),
    )


def build_matching_cost_matrix(
    edges: Sequence[MatchingEdge],
    demand: Mapping[int, DemandRecord | float],
    conflict_mode: ConflictMode | str = "slot_only_debug",
) -> list[list[float]]:
    """Build a tiny debug matrix; only allowed for slot_only_debug."""

    if conflict_mode != "slot_only_debug":
        raise ValueError("Hungarian-style matrix is allowed only for slot_only_debug")
    ramp_ids = sorted(demand)
    by_ramp: dict[int, list[MatchingEdge]] = {ramp_id: [] for ramp_id in ramp_ids}
    for edge in edges:
        by_ramp.setdefault(edge.ramp_id, []).append(edge)
    columns = sorted({edge.slot_id for edge in edges})
    matrix: list[list[float]] = []
    for ramp_id in ramp_ids:
        row: list[float] = []
        for slot_id in columns:
            candidates = [edge for edge in by_ramp.get(ramp_id, []) if edge.slot_id == slot_id]
            row.append(max((edge.weight for edge in candidates), default=-math.inf))
        matrix.append(row)
    return matrix


def solve_matching_slot_only_debug(
    edges: Sequence[MatchingEdge],
    demand: Mapping[int, DemandRecord | float],
) -> MatchingResult:
    """Optional slot-only debug solver, not the default conflict-aware solver."""

    build_matching_cost_matrix(edges, demand, "slot_only_debug")
    selected: list[MatchingEdge] = []
    used_ramps: set[int] = set()
    used_slots: set[str] = set()
    for edge in sorted(edges, key=lambda item: (item.weight, item.edge_id), reverse=True):
        if edge.ramp_id in used_ramps or edge.slot_id in used_slots:
            continue
        selected.append(edge)
        used_ramps.add(edge.ramp_id)
        used_slots.add(edge.slot_id)
    return _matching_result(
        "m_slot_only_debug",
        selected,
        demand,
        "slot_only_debug",
        "slot_only_debug",
        sum(edge.weight for edge in selected),
    )


def compute_inventory_from_matching(result: MatchingResult) -> dict[str, float | int | str]:
    """Expose S/Z/D metrics recomputable from matching output."""

    return {
        "D_H": result.D_H,
        "S_H_R": result.S_R,
        "Z_H_R": result.Z_R,
        "matched_edge_count": len(result.selected_edges),
        "solver_name": result.solver_name,
        "conflict_mode": result.conflict_mode,
    }


def compute_predictor_row(
    sample: ToyS0Sample,
    matching_result: MatchingResult,
) -> dict[str, Any]:
    """Build one minimal S0 predictor row from diagnostic matching output."""

    qualities = list(sample.edge_qualities)
    matched_rds = [
        quality.RD
        for quality in qualities
        if quality.edge_id in matching_result.selected_edge_ids
    ]
    return {
        "sample_id": sample.sample_id,
        "scenario_id": sample.scenario_id,
        "seed": sample.seed,
        "G_H": sample.raw_gap_count,
        "raw_time_expanded_slot_count": sample.raw_time_expanded_slot_count,
        "density_imbalance": sample.density_imbalance,
        "speed_difference": sample.speed_difference,
        "D_H": matching_result.D_H,
        "S_H_R": matching_result.S_R,
        "Z_H_R": matching_result.Z_R,
        "reservable_edge_count": sum(1 for quality in qualities if quality.is_reservable),
        "matched_edge_count": len(matching_result.selected_edges),
        "mean_RD_all_edges": _mean([quality.RD for quality in qualities]),
        "mean_RD_matched": _mean(matched_rds),
        "near_miss_count_baseline": 0,
    }


def compute_future_outcome_row(sample: ToyS0Sample) -> dict[str, Any]:
    """Build one fixed-policy S0 future outcome row."""

    return {
        "sample_id": sample.sample_id,
        "label_policy": "FIFO_no_production",
        "future_ramp_waiting": sample.future_ramp_waiting,
        "failed_reservation_count": sample.failed_reservation_count,
        "slot_expiration_count": sample.slot_expiration_count,
        "hard_brake_count": sample.hard_brake_count,
        "recovery_time": sample.recovery_time,
        "speed_wave_amplitude": sample.speed_wave_amplitude,
        "invalid_event_count": sample.invalid_event_count,
    }


def join_predictor_outcome_rows(
    predictors: Sequence[Mapping[str, Any]],
    outcomes: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Join predictor and outcome rows by sample_id."""

    outcome_by_id = {row["sample_id"]: row for row in outcomes}
    joined: list[dict[str, Any]] = []
    for predictor in predictors:
        sample_id = predictor["sample_id"]
        if sample_id not in outcome_by_id:
            continue
        joined.append({**dict(predictor), **dict(outcome_by_id[sample_id])})
    return joined


def analyze_predictor_outcome(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Return a small deterministic summary for S0 toy rows."""

    if not rows:
        return {"row_count": 0, "mean_Z_H_R": 0.0, "mean_future_ramp_waiting": 0.0}
    return {
        "row_count": len(rows),
        "mean_Z_H_R": _mean([float(row["Z_H_R"]) for row in rows]),
        "mean_future_ramp_waiting": _mean([float(row["future_ramp_waiting"]) for row in rows]),
        "raw_high_z_high_count": sum(
            1
            for row in rows
            if float(row["G_H"]) >= 2.0 and float(row["Z_H_R"]) > 0.0
        ),
        "label_policy": "FIFO_no_production",
    }


def build_minimal_s0_samples() -> list[ToyS0Sample]:
    """Return hand-crafted S0 toy samples; Phase 4 owns formal generation."""

    illusion_edges = (
        _toy_quality("edge_s0_illusion_a", 1, "slot_gap_a", (10, 20), 1.0, 0.0, False, 0.8),
        _toy_quality("edge_s0_illusion_b", 2, "slot_gap_b", (11, 21), 1.5, 0.0, False, 0.9),
    )
    recoverable_edges = (
        _toy_quality("edge_s0_ok", 1, "slot_ok", (30, 40), 1.0, 1.0, True, 0.1),
    )
    return [
        ToyS0Sample(
            sample_id="s0_raw_gap_illusion",
            scenario_id="S0_handcrafted",
            seed=101,
            edge_qualities=illusion_edges,
            demand_records=(DemandRecord(1), DemandRecord(2)),
            raw_gap_count=4,
            raw_time_expanded_slot_count=4,
            density_imbalance=0.1,
            speed_difference=1.0,
            future_ramp_waiting=8.0,
            failed_reservation_count=0,
            slot_expiration_count=2,
            hard_brake_count=0,
            recovery_time=6.0,
            speed_wave_amplitude=3.0,
            invalid_event_count=1,
        ),
        ToyS0Sample(
            sample_id="s0_recoverable",
            scenario_id="S0_handcrafted",
            seed=102,
            edge_qualities=recoverable_edges,
            demand_records=(DemandRecord(1),),
            raw_gap_count=1,
            raw_time_expanded_slot_count=1,
            density_imbalance=0.0,
            speed_difference=0.5,
            future_ramp_waiting=1.0,
            failed_reservation_count=0,
            slot_expiration_count=0,
            hard_brake_count=0,
            recovery_time=1.0,
            speed_wave_amplitude=0.5,
            invalid_event_count=0,
        ),
    ]


def matching_edge_to_row(
    matching_id: str,
    edge: MatchingEdge,
    *,
    matched: bool,
    conflict_mode: str,
    match_reason: str,
    log_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    row = {
        "matching_id": matching_id,
        "edge_id": edge.edge_id,
        "slot_id": edge.slot_id,
        "ramp_id": edge.ramp_id,
        "matched": matched,
        "conflict_mode": conflict_mode,
        "match_reason": match_reason,
        "tau": edge.tau,
        "physical_gap_id": edge.physical_gap_id,
        "P_R": edge.P_R,
        "RD": edge.RD,
        "weight": edge.weight,
    }
    return {**dict(log_context or {}), **row}


def matching_result_to_rows(
    result: MatchingResult,
    edges: Sequence[MatchingEdge],
    log_context: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    selected = set(result.selected_edge_ids)
    return [
        matching_edge_to_row(
            result.matching_id,
            edge,
            matched=edge.edge_id in selected,
            conflict_mode=result.conflict_mode,
            match_reason="selected" if edge.edge_id in selected else "not_selected_or_conflict",
            log_context=log_context,
        )
        for edge in edges
    ]


def coerce_matching_config(config: MatchingConfig | Mapping[str, Any] | Any | None) -> MatchingConfig:
    if config is None:
        return MatchingConfig()
    if isinstance(config, MatchingConfig):
        return config
    return MatchingConfig(
        T_merge=float(_config_value(config, "T_merge", 1.0)),
        T_buffer=float(_config_value(config, "T_buffer", 0.0)),
        conflict_mode=_config_value(
            config,
            "conflict_mode",
            _nested_config_value(config, "algorithm", "conflict_mode", "time_window_default"),
        ),
        epsilon_RD=float(_config_value(config, "epsilon_RD", 1e-6)),
        matching_id=str(_config_value(config, "matching_id", "m_greedy_conflict")),
    )


def _matching_result(
    matching_id: str,
    selected: Sequence[MatchingEdge],
    demand: Mapping[int, DemandRecord | float],
    conflict_mode: str,
    solver_name: str,
    objective_value: float,
) -> MatchingResult:
    D_H = float(sum(_omega_for_ramp(demand, ramp_id) for ramp_id in demand))
    S_R = float(sum(_omega_for_ramp(demand, edge.ramp_id) * edge.P_R for edge in selected))
    Z_R = max(D_H - S_R, 0.0)
    return MatchingResult(
        matching_id=matching_id,
        selected_edges=list(selected),
        selected_edge_ids=[edge.edge_id for edge in selected],
        S_R=S_R,
        Z_R=Z_R,
        D_H=D_H,
        unmatched_ramps=sorted(set(demand) - {edge.ramp_id for edge in selected}),
        conflict_mode=conflict_mode,
        solver_name=solver_name,
        objective_value=objective_value,
    )


def _omega_for_ramp(demand: Mapping[int, DemandRecord | float], ramp_id: int) -> float:
    record = demand[ramp_id]
    if isinstance(record, DemandRecord):
        return record.omega
    return float(record)


def _toy_quality(
    edge_id: str,
    ramp_id: int,
    slot_id: str,
    physical_gap_id: tuple[int, int],
    tau: float,
    P_R: float,
    is_reservable: bool,
    RD: float,
) -> EdgeQuality:
    return EdgeQuality(
        edge_id=edge_id,
        ramp_id=ramp_id,
        slot_id=_slot_id_with_gap(slot_id, physical_gap_id, tau),
        I_reach=int(P_R > 0.0),
        I_surv=1,
        I_safe=int(P_R > 0.0),
        I_rec=int(P_R > 0.0),
        P_R=P_R,
        RD=RD,
        W=10.0 if P_R > 0.0 else 2.0,
        V_phys_theory=1,
        V_phys_buffer=int(P_R > 0.0),
        delta_W_req=0.0 if P_R > 0.0 else 3.0,
        is_reservable=is_reservable,
        reason_not_reservable="OK" if is_reservable else "UNREACHABLE",
        fail_reason_priority="OK" if is_reservable else "UNREACHABLE",
        surv_mode="deterministic_tau_generated",
        validity_mode="deterministic_v0_cascade_rd_proxy_v0_minimal",
        rd_components={"proxy_mode": "RD_proxy_v0_minimal", "B": RD, "A": 0.0, "T": 0.0},
        min_safety_margin=10.0 if P_R > 0.0 else 2.0,
        reachability={"I_reach": int(P_R > 0.0), "x_min": 0.0, "x_max": 0.0, "a_req": 0.0},
    )


def _slot_id_with_gap(slot_id: str, physical_gap_id: tuple[int, int], tau: float) -> str:
    return f"{slot_id}|gap={physical_gap_id[0]}-{physical_gap_id[1]}|tau={tau}"


def _physical_gap_from_slot_id(slot_id: str) -> tuple[int, int]:
    marker = "|gap="
    if marker not in slot_id:
        parts = slot_id.split("_")
        if len(parts) >= 4 and parts[0] == "slot":
            try:
                return (int(parts[1]), int(parts[2]))
            except ValueError:
                return (0, 0)
        return (0, 0)
    value = slot_id.split(marker, 1)[1].split("|", 1)[0]
    front, rear = value.split("-", 1)
    return (int(front), int(rear))


def _tau_from_quality(quality: EdgeQuality) -> float:
    marker = "|tau="
    if marker not in quality.slot_id:
        parts = quality.slot_id.split("_")
        if len(parts) >= 4 and parts[3].startswith("k"):
            try:
                return float(parts[3][1:])
            except ValueError:
                return 0.0
        return 0.0
    return float(quality.slot_id.split(marker, 1)[1])


def _physical_gap_from_metadata(metadata: Any, slot_id: str) -> tuple[int, int]:
    value = _config_value(metadata, "physical_gap_id")
    if value is None:
        return _physical_gap_from_slot_id(slot_id)
    return (int(value[0]), int(value[1]))


def _tau_from_metadata(metadata: Any, quality: EdgeQuality) -> float:
    value = _config_value(metadata, "tau")
    if value is None:
        return _tau_from_quality(quality)
    return float(value)


def _config_value(config: Any, name: str, default: Any = None) -> Any:
    if config is None:
        return default
    if isinstance(config, Mapping):
        return config.get(name, default)
    value = getattr(config, name, None)
    return default if value is None else value


def _nested_config_value(config: Any, section: str, name: str, default: Any = None) -> Any:
    parent = _config_value(config, section)
    return _config_value(parent, name, default)


def _mean(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values) / len(values))


__all__ = [
    "ConflictMode",
    "DemandRecord",
    "MatchingConfig",
    "MatchingEdge",
    "MatchingResult",
    "ToyS0Sample",
    "analyze_predictor_outcome",
    "build_matching_cost_matrix",
    "build_matching_edges",
    "build_minimal_s0_samples",
    "coerce_matching_config",
    "compute_demand_weights",
    "compute_future_outcome_row",
    "compute_inventory_from_matching",
    "compute_predictor_row",
    "edges_conflict",
    "join_predictor_outcome_rows",
    "matching_edge_to_row",
    "matching_result_to_rows",
    "solve_matching_slot_only_debug",
    "solve_matching_v0_greedy_conflict",
]
