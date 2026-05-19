"""Formal scenario generators and readiness diagnostics for Wave 4."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
import copy
import csv
import hashlib
import json
import random

from rpmi.config import stable_json
from rpmi.dynamics import step_traffic
from rpmi.matching import (
    DemandRecord,
    MatchingConfig,
    build_matching_edges,
    matching_result_to_rows,
    solve_matching_v0_greedy_conflict,
)
from rpmi.slots import (
    Edge,
    EdgeQuality,
    Slot,
    SlotInventoryParams,
    build_edges,
    compute_edge_qualities,
    edge_quality_to_row,
    generate_slots,
    slot_to_row,
)
from rpmi.state import RoadConfig, TrafficState, VehicleState, hash_state


@dataclass(frozen=True)
class ScenarioConfig:
    scenario_id: str
    seed: int
    road: dict[str, Any]
    simulation: dict[str, Any]
    vehicles: dict[str, Any]
    ramp: dict[str, Any]
    mechanism_targets: dict[str, Any]
    readiness_targets: dict[str, Any]


@dataclass(frozen=True)
class ReadinessReport:
    scenario_id: str
    seed: int
    readiness_pass: bool
    fail_reason: str
    metrics: dict[str, Any]
    recommended_adjustments: list[str]
    algorithm_independent: bool = True


@dataclass(frozen=True)
class NearMissLabel:
    is_near_miss: bool
    near_miss_type: str
    delta_W_req: float
    available_modes: tuple[str, ...]
    screen_score: float
    reason: str


def load_scenario_config(path: str | Path) -> ScenarioConfig:
    """Load a JSON scenario config.

    YAML run configs remain owned by Phase 0. Wave 4 keeps scenario templates
    JSON-only so manifest payloads are exactly reproducible.
    """

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise TypeError("Scenario config file must contain a mapping")
    return scenario_config_from_dict(payload)


def scenario_config_from_dict(data: Mapping[str, Any]) -> ScenarioConfig:
    """Build a scenario config while preserving unknown nested knobs."""

    return ScenarioConfig(
        scenario_id=str(data.get("scenario_id", "S0")),
        seed=int(data.get("seed", 0)),
        road=dict(data.get("road", {})),
        simulation=dict(data.get("simulation", {})),
        vehicles=dict(data.get("vehicles", {})),
        ramp=dict(data.get("ramp", {})),
        mechanism_targets=dict(data.get("mechanism_targets", {})),
        readiness_targets=dict(data.get("readiness_targets", {})),
    )


def make_scenario_config(
    scenario_id: str,
    *,
    seed: int = 0,
    road: Mapping[str, Any] | None = None,
    simulation: Mapping[str, Any] | None = None,
    vehicles: Mapping[str, Any] | None = None,
    ramp: Mapping[str, Any] | None = None,
    mechanism_targets: Mapping[str, Any] | None = None,
    readiness_targets: Mapping[str, Any] | None = None,
) -> ScenarioConfig:
    """Return one controlled template config for S0/S2/S5/S6."""

    base = _base_template(scenario_id)
    _deep_update(base["road"], dict(road or {}))
    _deep_update(base["simulation"], dict(simulation or {}))
    _deep_update(base["vehicles"], dict(vehicles or {}))
    _deep_update(base["ramp"], dict(ramp or {}))
    _deep_update(base["mechanism_targets"], dict(mechanism_targets or {}))
    _deep_update(base["readiness_targets"], dict(readiness_targets or {}))
    base["seed"] = seed
    return scenario_config_from_dict(base)


def generate_initial_vehicles(
    config: ScenarioConfig,
    rng: random.Random | None = None,
) -> list[VehicleState]:
    """Build the deterministic micro-state before seed perturbation."""

    values = _template_values(config)
    vehicles: list[VehicleState] = []
    boundary_pairs = values["boundary_pairs"]
    speed = values["target_speed"]
    x0 = values["front_x"]
    next_id = 1
    for index, pair in enumerate(boundary_pairs):
        front_type, rear_type = _boundary_pair_types(pair)
        front_x = x0 - index * values["pair_spacing"]
        rear_x = front_x - 5.0 - values["gap_widths"][index % len(values["gap_widths"])]
        vehicles.append(
            VehicleState(
                id=next_id,
                role="mainline",
                veh_type=front_type,
                lane=values["target_lane"],
                x=front_x,
                v=speed + values["front_speed_offsets"][index % len(values["front_speed_offsets"])],
                a=0.0,
            )
        )
        next_id += 1
        vehicles.append(
            VehicleState(
                id=next_id,
                role="mainline",
                veh_type=rear_type,
                lane=values["target_lane"],
                x=rear_x,
                v=speed + values["rear_speed_offsets"][index % len(values["rear_speed_offsets"])],
                a=0.0,
            )
        )
        next_id += 1

    for index in range(values["inner_receiving_gap_count"] + 1):
        vehicles.append(
            VehicleState(
                id=next_id,
                role="mainline",
                veh_type="CAV" if index % 2 == 0 else "HDV",
                lane=values["target_lane"] + 1,
                x=x0 - index * 35.0,
                v=speed,
                a=0.0,
            )
        )
        next_id += 1

    ramp_count = values["ramp_count"]
    for index in range(ramp_count):
        vehicles.append(
            VehicleState(
                id=100 + index,
                role="ramp",
                veh_type="CAV",
                lane=values["ramp_lane"],
                x=values["ramp_start_x"] - index * values["ramp_spacing"],
                v=values["ramp_speed"] + index * values["ramp_speed_step"],
                a=0.0,
            )
        )
    return apply_template_perturbation(vehicles, rng or random.Random(config.seed), config)


def apply_template_perturbation(
    vehicles: Sequence[VehicleState],
    rng: random.Random,
    config: ScenarioConfig,
) -> list[VehicleState]:
    """Apply deterministic seed perturbation without changing vehicle identity."""

    values = _template_values(config)
    x_jitter = values["x_jitter"]
    v_jitter = values["v_jitter"]
    if x_jitter == 0.0 and v_jitter == 0.0:
        return list(vehicles)
    out: list[VehicleState] = []
    for vehicle in vehicles:
        out.append(
            replace(
                vehicle,
                x=vehicle.x + rng.uniform(-x_jitter, x_jitter),
                v=max(0.0, vehicle.v + rng.uniform(-v_jitter, v_jitter)),
            )
        )
    return out


def generate_s0_samples(config: ScenarioConfig, N: int = 16) -> list[TrafficState]:
    """Generate stratified S0 inventory-mechanism samples."""

    return [generate_state(sample_config) for sample_config in generate_s0_sample_configs(config, N)]


def generate_s0_sample_configs(config: ScenarioConfig, N: int = 16) -> list[ScenarioConfig]:
    """Generate stratified S0 configs with raw-gap and deficit factors crossed."""

    states: list[TrafficState] = []
    configs: list[ScenarioConfig] = []
    for index in range(N):
        raw_high = index % 2 == 0
        deficit_high = (index // 2) % 2 == 0
        configs.append(
            make_scenario_config(
                "S0",
                seed=config.seed + index,
                road=config.road,
                simulation=config.simulation,
                vehicles={
                    **config.vehicles,
                    "gap_widths": [30.0, 28.0] if raw_high else [12.0, 10.0],
                    "ramp_start_x": -500.0 if deficit_high else 78.0,
                    "ramp_speed": 0.0 if deficit_high else 12.0,
                    "ramp_count": 2 if deficit_high else 1,
                    "ramp_end_x": 120.0,
                },
                ramp=config.ramp,
                mechanism_targets={
                    **config.mechanism_targets,
                    "s0_factor_controls": {
                        "raw_gap": "high" if raw_high else "low",
                        "deficit": "high" if deficit_high else "low",
                        "density": "template",
                        "speed": "template",
                    },
                    "s0_sample_mode": "formal_stratified",
                },
                readiness_targets=config.readiness_targets,
            )
        )
    return configs


def generate_s0_deconfounded_samples(config: ScenarioConfig, N: int = 32) -> list[TrafficState]:
    """Generate S0 evidence-hardening states with crossed control factors."""

    return [generate_state(sample_config) for sample_config in generate_s0_deconfounded_sample_configs(config, N)]


def generate_s0_deconfounded_sample_configs(config: ScenarioConfig, N: int = 32) -> list[ScenarioConfig]:
    """Generate S0 configs crossing raw gap, deficit, density, and speed controls.

    The generator still uses deterministic no-action diagnostics. Seeded jitter is
    deliberately enabled so repeated factor cells have distinct state hashes.
    """

    configs: list[ScenarioConfig] = []
    for index in range(N):
        raw_high = index % 2 == 0
        deficit_high = (index // 2) % 2 == 0
        density_high = (index // 4) % 2 == 0
        speed_high = (index // 8) % 2 == 0
        replicate = index // 16
        vehicles = {
            **config.vehicles,
            "gap_widths": [30.0, 28.0] if raw_high else [12.0, 10.0],
            "ramp_start_x": -500.0 if deficit_high else 78.0,
            "ramp_speed": 0.0 if deficit_high else 12.0,
            "ramp_count": 2 if deficit_high else 1,
            "ramp_end_x": 120.0,
            "inner_receiving_gap_count": 0 if density_high else 3,
            "front_speed_offsets": [1.0, 0.0] if speed_high else [0.0, -0.5],
            "rear_speed_offsets": [-1.0, 0.0] if speed_high else [0.5, 0.0],
            "x_jitter": max(float(config.vehicles.get("x_jitter", 0.0)), 0.35),
            "v_jitter": max(float(config.vehicles.get("v_jitter", 0.0)), 0.08),
        }
        configs.append(
            make_scenario_config(
                "S0",
                seed=config.seed + index,
                road=config.road,
                simulation=config.simulation,
                vehicles=vehicles,
                ramp=config.ramp,
                mechanism_targets={
                    **config.mechanism_targets,
                    "s0_factor_controls": {
                        "raw_gap": "high" if raw_high else "low",
                        "deficit": "high" if deficit_high else "low",
                        "density": "high" if density_high else "low",
                        "speed": "high" if speed_high else "low",
                        "replicate": replicate,
                    },
                    "s0_sample_mode": "deconfounded",
                },
                readiness_targets=config.readiness_targets,
            )
        )
    return configs


def generate_s2_near_critical(config: ScenarioConfig) -> TrafficState:
    """Generate one S2 near-critical outer-lane state."""

    return generate_state(_with_template(config, "S2"))


def generate_s5_boundary_templates(config: ScenarioConfig) -> list[TrafficState]:
    """Generate boundary type coverage states for S5."""

    states: list[TrafficState] = []
    for index, boundary_type in enumerate(["CAV-HDV", "HDV-CAV", "CAV-CAV", "HDV-HDV"]):
        states.append(
            generate_state(
                make_scenario_config(
                    "S5",
                    seed=config.seed + index,
                    road=config.road,
                    simulation=config.simulation,
                    vehicles={**config.vehicles, "boundary_pairs": [boundary_type]},
                    ramp=config.ramp,
                    mechanism_targets=config.mechanism_targets,
                    readiness_targets=config.readiness_targets,
                )
            )
        )
    return states


def generate_s6_raw_gap_illusion(config: ScenarioConfig) -> TrafficState:
    """Generate a state with many raw gaps but low recoverable supply."""

    return generate_state(_with_template(config, "S6"))


def generate_state(config: ScenarioConfig) -> TrafficState:
    vehicles = generate_initial_vehicles(config, random.Random(config.seed))
    return TrafficState(time=0.0, step=0, vehicles={vehicle.id: vehicle for vehicle in vehicles})


def classify_near_miss(
    edge_quality: EdgeQuality,
    boundary_type: str = "unknown",
    params: Mapping[str, Any] | Any | None = None,
) -> NearMissLabel:
    """Classify read-only near-miss availability shared with later phases."""

    threshold = float(_config_value(params, "near_miss_delta_W_max", 8.0))
    rd_max = float(_config_value(params, "near_miss_RD_max", 1.0))
    if edge_quality.is_reservable:
        return NearMissLabel(
            is_near_miss=False,
            near_miss_type="already_reservable",
            delta_W_req=edge_quality.delta_W_req,
            available_modes=(),
            screen_score=0.0,
            reason="edge_already_reservable",
        )
    buffer_near = (
        edge_quality.V_phys_theory == 1
        and edge_quality.V_phys_buffer == 0
        and edge_quality.delta_W_req <= threshold
    )
    rd_near = edge_quality.I_reach == 1 and edge_quality.I_safe == 1 and edge_quality.RD <= rd_max
    if not (buffer_near or rd_near):
        return NearMissLabel(
            is_near_miss=False,
            near_miss_type="none",
            delta_W_req=edge_quality.delta_W_req,
            available_modes=(),
            screen_score=0.0,
            reason=edge_quality.fail_reason_priority,
        )

    modes = _available_modes_for_boundary(boundary_type)
    near_type = "buffer_width" if buffer_near else "recovery_debt"
    score = 1.0 / (1.0 + max(edge_quality.delta_W_req, 0.0) + max(edge_quality.RD, 0.0))
    return NearMissLabel(
        is_near_miss=bool(modes),
        near_miss_type=near_type,
        delta_W_req=edge_quality.delta_W_req,
        available_modes=modes,
        screen_score=score,
        reason="near_miss_available" if modes else "no_boundary_cav_mode",
    )


def compute_readiness_metrics(
    state: TrafficState,
    config: ScenarioConfig,
) -> dict[str, Any]:
    """Compute algorithm-independent readiness metrics with no-action diagnostics."""

    rollout = no_action_rollout(state, config)
    values = _template_values(config)
    params = _slot_params(config)
    slots = generate_slots(
        rollout,
        t=state.time,
        H=params.H,
        dt_merge=params.dt_merge,
        target_lane=params.target_lane,
        eval_context="baseline",
        action_id=None,
    )
    ramps = [vehicle for vehicle in state.vehicles.values() if vehicle.active and vehicle.role == "ramp"]
    edges = build_edges(ramps, slots)
    qualities = compute_edge_qualities(edges, rollout, state, params)
    demand = {ramp.id: DemandRecord(ramp.id) for ramp in ramps}
    matching_edges = build_matching_edges(
        qualities,
        demand,
        edge_metadata={
            edge.edge_id: {"physical_gap_id": edge.physical_gap_id, "tau": edge.tau}
            for edge in edges
        },
    )
    matching = solve_matching_v0_greedy_conflict(
        matching_edges,
        demand,
        MatchingConfig(
            T_merge=float(values["T_merge"]),
            T_buffer=float(values["T_buffer"]),
            conflict_mode=str(values["conflict_mode"]),
        ),
    )
    quality_by_edge_id = {quality.edge_id: quality for quality in qualities}
    edge_by_id = {edge.edge_id: edge for edge in edges}
    near_labels = []
    for quality in qualities:
        edge = edge_by_id.get(quality.edge_id)
        boundary_type = "unknown" if edge is None else _boundary_type_for_edge(state, edge)
        near_labels.append(classify_near_miss(quality, boundary_type, values))

    near_miss_by_type: dict[str, int] = {}
    for label in near_labels:
        if label.is_near_miss:
            near_miss_by_type[label.near_miss_type] = near_miss_by_type.get(label.near_miss_type, 0) + 1
    boundary_counts = _boundary_counts(slots, state)
    invalid_reasons = _reason_counts(qualities)
    raw_gap_illusion_count = sum(
        1
        for quality in qualities
        if quality.V_phys_theory == 1 and not quality.is_reservable
    )
    metrics = {
        "scenario_id": config.scenario_id,
        "seed": config.seed,
        "state_hash": hash_state(state),
        "G_H": sum(1 for slot in slots if slot.gap_at_tau >= float(values["raw_gap_width_min"])),
        "raw_time_expanded_slot_count": len(slots),
        "D_H": matching.D_H,
        "S_R_0": matching.S_R,
        "Z_R_0": matching.Z_R,
        "reservable_edge_count": sum(1 for quality in qualities if quality.is_reservable),
        "matched_edge_count": len(matching.selected_edges),
        "total_edge_count": len(qualities),
        "near_miss_edge_count": sum(1 for label in near_labels if label.is_near_miss),
        "near_miss_by_type": near_miss_by_type,
        "boundary_CAV_HDV": boundary_counts.get("CAV-HDV", 0),
        "boundary_HDV_CAV": boundary_counts.get("HDV-CAV", 0),
        "boundary_CAV_CAV": boundary_counts.get("CAV-CAV", 0),
        "boundary_HDV_HDV": boundary_counts.get("HDV-HDV", 0),
        "boundary_cav_available_count": sum(
            count
            for boundary, count in boundary_counts.items()
            if "CAV" in boundary
        ),
        "inner_receiving_gap_count": _inner_receiving_gap_count(state, values["target_lane"] + 1),
        "raw_gap_illusion_count": raw_gap_illusion_count,
        "dominant_invalid_reasons": invalid_reasons,
        "matching_id": matching.matching_id,
        "solver_name": matching.solver_name,
        "algorithm_independent": True,
        "used_proposed_action_rollout": False,
        "_diagnostic": {
            "slots": slots,
            "edges": edges,
            "qualities": qualities,
            "matching": matching,
            "matching_edges": matching_edges,
            "near_labels": near_labels,
            "quality_by_edge_id": quality_by_edge_id,
        },
    }
    return metrics


def readiness_check(metrics: Mapping[str, Any], config: ScenarioConfig) -> ReadinessReport:
    """Gate scenario readiness without reading proposed action outcomes."""

    targets = dict(config.readiness_targets)
    failures: list[str] = []
    if float(metrics.get("G_H", 0.0)) < float(targets.get("raw_gap_count_min", 0.0)):
        failures.append("raw_gap_count_too_low")
    if float(metrics.get("Z_R_0", 0.0)) < float(targets.get("baseline_ZR_min", 0.0)):
        failures.append("baseline_deficit_too_low")
    if int(metrics.get("near_miss_edge_count", 0)) < int(targets.get("near_miss_count_min", 0)):
        failures.append("near_miss_too_low")
    if int(metrics.get("boundary_cav_available_count", 0)) < int(targets.get("boundary_cav_min", 0)):
        failures.append("boundary_cav_unavailable")
    if int(metrics.get("raw_gap_illusion_count", 0)) < int(targets.get("raw_gap_illusion_min", 0)):
        failures.append("raw_gap_illusion_too_low")
    report = ReadinessReport(
        scenario_id=config.scenario_id,
        seed=config.seed,
        readiness_pass=not failures,
        fail_reason=";".join(failures),
        metrics=_public_metrics(metrics),
        recommended_adjustments=suggest_adjustments(failures),
        algorithm_independent=True,
    )
    report.metrics["readiness_pass"] = report.readiness_pass
    report.metrics["fail_reason"] = report.fail_reason
    return report


def parameter_sweep_for_readiness(
    config: ScenarioConfig,
    grid: Mapping[str, Sequence[Any]] | Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Search deterministic perturbations and record accepted and rejected attempts."""

    attempts: list[dict[str, Any]] = []
    for index, overrides in enumerate(_grid_records(grid)):
        candidate = _apply_sweep_override(config, overrides, seed_offset=index)
        state = generate_state(candidate)
        metrics = compute_readiness_metrics(state, candidate)
        report = readiness_check(metrics, candidate)
        attempts.append(
            {
                "scenario_id": candidate.scenario_id,
                "seed": candidate.seed,
                "overrides": dict(overrides),
                "readiness_pass": report.readiness_pass,
                "fail_reason": report.fail_reason,
                "metrics": report.metrics,
            }
        )
    accepted = [attempt for attempt in attempts if attempt["readiness_pass"]]
    rejected = [attempt for attempt in attempts if not attempt["readiness_pass"]]
    return {
        "scenario_id": config.scenario_id,
        "attempt_count": len(attempts),
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "accepted": accepted,
        "rejected": rejected,
        "attempts": attempts,
    }


def readiness_allows_comparison(report: ReadinessReport) -> bool:
    """Return whether downstream baseline/proposed comparison may proceed."""

    return report.readiness_pass


def write_scenario_manifest(
    path: str | Path,
    config: ScenarioConfig,
    state: TrafficState,
    report: ReadinessReport | None = None,
) -> None:
    """Write a Phase 4 scenario manifest JSON."""

    payload = {
        "schema_version": "phase4_v1",
        "scenario": _scenario_manifest_entry(config, state, report),
    }
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_readiness_summary_rows(path: str | Path, rows: Sequence[Mapping[str, Any]]) -> None:
    """Append Phase 4 readiness rows to readiness_summary.csv."""

    columns = [
        "run_id",
        "step",
        "time",
        "decision_context_id",
        "state_hash",
        "config_hash",
        "code_version",
        "units_version",
        "scenario_id",
        "seed",
        "algorithm_id",
        "readiness_pass",
        "readiness_reason",
        "G_H",
        "D_H",
        "S_R_0",
        "Z_R_0",
        "near_miss_edge_count",
        "raw_gap_illusion_count",
        "failed_attempts",
        "algorithm_independent",
    ]
    file_path = Path(path)
    needs_header = not file_path.exists() or file_path.stat().st_size == 0
    with file_path.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns, extrasaction="ignore")
        if needs_header:
            writer.writeheader()
        for row in rows:
            writer.writerow({column: _csv_value(row.get(column)) for column in columns})


def readiness_report_to_row(
    report: ReadinessReport,
    log_context: Mapping[str, Any] | None = None,
    *,
    algorithm_id: str = "readiness_no_action_diagnostic",
    failed_attempts: int = 0,
) -> dict[str, Any]:
    """Convert a readiness report to a compact CSV row."""

    metrics = report.metrics
    row = {
        "scenario_id": report.scenario_id,
        "seed": report.seed,
        "algorithm_id": algorithm_id,
        "readiness_pass": report.readiness_pass,
        "readiness_reason": "PASS" if report.readiness_pass else report.fail_reason,
        "G_H": metrics.get("G_H", 0),
        "D_H": metrics.get("D_H", 0.0),
        "S_R_0": metrics.get("S_R_0", 0.0),
        "Z_R_0": metrics.get("Z_R_0", 0.0),
        "near_miss_edge_count": metrics.get("near_miss_edge_count", 0),
        "raw_gap_illusion_count": metrics.get("raw_gap_illusion_count", 0),
        "failed_attempts": failed_attempts,
        "algorithm_independent": report.algorithm_independent,
    }
    return {**dict(log_context or {}), **row}


def diagnostic_rows_for_readiness(
    metrics: Mapping[str, Any],
    log_context: Mapping[str, Any] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Return slots/edges/matching/near-miss rows from diagnostics."""

    diagnostic = metrics.get("_diagnostic", {})
    slots: Sequence[Slot] = diagnostic.get("slots", [])
    edges: Sequence[Edge] = diagnostic.get("edges", [])
    qualities: Sequence[EdgeQuality] = diagnostic.get("qualities", [])
    matching = diagnostic.get("matching")
    matching_edges = diagnostic.get("matching_edges", [])
    near_labels: Sequence[NearMissLabel] = diagnostic.get("near_labels", [])
    edge_rows = [
        edge_quality_to_row(edge, quality, log_context)
        for edge, quality in zip(edges, qualities)
    ]
    near_rows = []
    for quality, label in zip(qualities, near_labels):
        if not label.is_near_miss:
            continue
        near_rows.append(
            {
                **dict(log_context or {}),
                "edge_id": quality.edge_id,
                "near_miss_label": label.near_miss_type,
                "near_miss_reason": label.reason,
            }
        )
    return {
        "slots": [slot_to_row(slot, log_context) for slot in slots],
        "edges": edge_rows,
        "matching": [] if matching is None else matching_result_to_rows(matching, matching_edges, log_context),
        "near_miss_edges": near_rows,
    }


def no_action_rollout(
    state: TrafficState,
    config: ScenarioConfig,
) -> dict[float, TrafficState]:
    """Roll out nominal behavior only, never proposed actions."""

    values = _template_values(config)
    dt = float(values["dt"])
    H = float(values["H"])
    steps = max(1, int(round(H / dt)))
    rollout = {round(state.time, 10): state}
    current = state
    dyn_config = {
        "dt": dt,
        "limits": {
            "u_min": float(values["u_min"]),
            "u_max": float(values["u_max"]),
            "v_max": float(values["v_max"]),
        },
        "min_gap": float(values["event_min_gap"]),
    }
    for _ in range(steps):
        current, _, _ = step_traffic(current, {}, dyn_config)
        rollout[round(current.time, 10)] = current
    return rollout


def make_road_config(config: ScenarioConfig) -> RoadConfig:
    road = config.road
    return RoadConfig(
        lanes=int(road.get("lanes", 2)),
        target_lane=int(road.get("target_lane", 0)),
        ramp_lane=int(road.get("ramp_lane", -1)),
        merge_zone=tuple(road.get("merge_zone", (300.0, 420.0))),
        ramp_end_x=float(road.get("ramp_end_x", config.vehicles.get("ramp_end_x", 420.0))),
    )


def _base_template(scenario_id: str) -> dict[str, Any]:
    sid = scenario_id.upper()
    base = {
        "scenario_id": sid,
        "seed": 0,
        "road": {
            "lanes": 2,
            "target_lane": 0,
            "ramp_lane": -1,
            "merge_zone": (0.0, 140.0),
            "ramp_end_x": 140.0,
        },
        "simulation": {
            "dt": 0.5,
            "H": 1.0,
            "dt_merge": 1.0,
            "raw_gap_width_min": 15.0,
            "u_min": -4.5,
            "u_max": 200.0,
            "v_max": 40.0,
            "W_min_buffer": 5.0,
            "RD_max": 1.0,
            "rd_speed_scale": 10.0,
            "T_merge": 1.0,
            "T_buffer": 0.0,
            "conflict_mode": "time_window_default",
            "event_min_gap": 0.0,
        },
        "vehicles": {
            "boundary_pairs": ["CAV-HDV", "HDV-CAV", "CAV-CAV", "HDV-HDV"],
            "gap_widths": [8.0, 30.0, 28.0, 26.0],
            "front_x": 120.0,
            "pair_spacing": 90.0,
            "target_speed": 10.0,
            "front_speed_offsets": [0.0],
            "rear_speed_offsets": [0.0],
            "inner_receiving_gap_count": 1,
            "ramp_count": 1,
            "ramp_start_x": 75.0,
            "ramp_spacing": 14.0,
            "ramp_speed": 10.0,
            "ramp_speed_step": 0.0,
            "x_jitter": 0.0,
            "v_jitter": 0.0,
        },
        "ramp": {},
        "mechanism_targets": {"mechanism": sid},
        "readiness_targets": {
            "raw_gap_count_min": 1,
            "baseline_ZR_min": 0.0,
            "near_miss_count_min": 0,
            "boundary_cav_min": 1,
            "raw_gap_illusion_min": 0,
        },
    }
    if sid == "S0":
        base["vehicles"].update(
            {
                "boundary_pairs": ["CAV-HDV", "HDV-CAV", "CAV-CAV", "HDV-HDV"],
                "gap_widths": [8.0, 30.0, 28.0, 26.0],
                "ramp_start_x": 75.0,
                "ramp_count": 2,
            }
        )
    elif sid == "S2":
        base["vehicles"].update(
            {
                "boundary_pairs": ["CAV-HDV"],
                "gap_widths": [7.0],
                "ramp_start_x": 74.0,
                "ramp_count": 1,
            }
        )
        base["readiness_targets"].update(
            {
                "raw_gap_count_min": 0,
                "baseline_ZR_min": 1.0,
                "near_miss_count_min": 1,
                "boundary_cav_min": 1,
            }
        )
    elif sid == "S5":
        base["vehicles"].update(
            {
                "boundary_pairs": ["CAV-HDV", "HDV-CAV", "CAV-CAV", "HDV-HDV"],
                "gap_widths": [7.0, 7.0, 7.0, 7.0],
                "ramp_start_x": 74.0,
                "ramp_count": 1,
            }
        )
        base["readiness_targets"].update(
            {"raw_gap_count_min": 0, "near_miss_count_min": 1, "boundary_cav_min": 1}
        )
    elif sid == "S6":
        base["vehicles"].update(
            {
                "boundary_pairs": ["CAV-HDV", "HDV-CAV", "CAV-CAV", "HDV-HDV"],
                "gap_widths": [30.0, 28.0, 26.0, 24.0],
                "ramp_end_x": 80.0,
                "ramp_start_x": -500.0,
                "ramp_speed": 0.0,
                "ramp_count": 2,
            }
        )
        base["simulation"].update({"u_max": 1.0})
        base["readiness_targets"].update(
            {
                "raw_gap_count_min": 2,
                "baseline_ZR_min": 1.0,
                "raw_gap_illusion_min": 1,
                "near_miss_count_min": 0,
            }
        )
    return base


def _with_template(config: ScenarioConfig, scenario_id: str) -> ScenarioConfig:
    return make_scenario_config(
        scenario_id,
        seed=config.seed,
        road=config.road,
        simulation=config.simulation,
        vehicles=config.vehicles,
        ramp=config.ramp,
        mechanism_targets=config.mechanism_targets,
        readiness_targets=config.readiness_targets,
    )


def _template_values(config: ScenarioConfig) -> dict[str, Any]:
    base = _base_template(config.scenario_id)
    _deep_update(base["road"], config.road)
    _deep_update(base["simulation"], config.simulation)
    _deep_update(base["vehicles"], config.vehicles)
    _deep_update(base["ramp"], config.ramp)
    values = {**base["road"], **base["simulation"], **base["vehicles"], **base["ramp"]}
    values["target_lane"] = int(values.get("target_lane", 0))
    values["ramp_lane"] = int(values.get("ramp_lane", -1))
    values["ramp_end_x"] = float(values.get("ramp_end_x", 140.0))
    return values


def _slot_params(config: ScenarioConfig) -> SlotInventoryParams:
    values = _template_values(config)
    return SlotInventoryParams(
        H=float(values["H"]),
        dt_merge=float(values["dt_merge"]),
        target_lane=int(values["target_lane"]),
        W_min_buffer=float(values["W_min_buffer"]),
        RD_max=float(values["RD_max"]),
        u_min=float(values["u_min"]),
        u_max=float(values["u_max"]),
        rd_speed_scale=float(values["rd_speed_scale"]),
        ramp_end_x=float(values["ramp_end_x"]),
    )


def _boundary_pair_types(value: str) -> tuple[str, str]:
    parts = value.split("-", 1)
    if len(parts) != 2:
        return ("HDV", "HDV")
    front, rear = parts[0].upper(), parts[1].upper()
    return ("CAV" if front == "CAV" else "HDV", "CAV" if rear == "CAV" else "HDV")


def _boundary_type_for_edge(state: TrafficState, edge: Edge) -> str:
    front = state.vehicles.get(edge.front_id)
    rear = state.vehicles.get(edge.rear_id)
    if front is None or rear is None:
        return "unknown"
    return f"{front.veh_type}-{rear.veh_type}"


def _boundary_counts(slots: Sequence[Slot], state: TrafficState) -> dict[str, int]:
    counts = {"CAV-HDV": 0, "HDV-CAV": 0, "CAV-CAV": 0, "HDV-HDV": 0}
    for slot in slots:
        front = state.vehicles.get(slot.front_id)
        rear = state.vehicles.get(slot.rear_id)
        if front is None or rear is None:
            continue
        key = f"{front.veh_type}-{rear.veh_type}"
        counts[key] = counts.get(key, 0) + 1
    return counts


def _available_modes_for_boundary(boundary_type: str) -> tuple[str, ...]:
    if boundary_type == "CAV-HDV":
        return ("front_acc",)
    if boundary_type == "HDV-CAV":
        return ("rear_dec",)
    if boundary_type == "CAV-CAV":
        return ("front_acc", "rear_dec", "front_rear")
    return ()


def _inner_receiving_gap_count(state: TrafficState, lane: int) -> int:
    vehicles = sorted(
        [vehicle for vehicle in state.vehicles.values() if vehicle.active and vehicle.lane == lane],
        key=lambda item: item.x,
        reverse=True,
    )
    return max(0, len(vehicles) - 1)


def _reason_counts(qualities: Sequence[EdgeQuality]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for quality in qualities:
        if quality.fail_reason_priority == "OK":
            continue
        counts[quality.fail_reason_priority] = counts.get(quality.fail_reason_priority, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _public_metrics(metrics: Mapping[str, Any]) -> dict[str, Any]:
    return {key: _public_value(value) for key, value in metrics.items() if not key.startswith("_")}


def _public_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Mapping):
        return {str(key): _public_value(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_public_value(item) for item in value]
    return str(value)


def suggest_adjustments(failures: Iterable[str]) -> list[str]:
    suggestions = {
        "raw_gap_count_too_low": "increase target-lane gap widths or horizon",
        "baseline_deficit_too_low": "increase ramp demand or reduce baseline recoverability",
        "near_miss_too_low": "set a small positive buffer deficit near a CAV boundary",
        "boundary_cav_unavailable": "include CAV-HDV, HDV-CAV, or CAV-CAV boundary pairs",
        "raw_gap_illusion_too_low": "increase timing mismatch or recovery debt while keeping raw gaps large",
    }
    return [suggestions.get(reason, f"inspect {reason}") for reason in failures]


def _scenario_manifest_entry(
    config: ScenarioConfig,
    state: TrafficState,
    report: ReadinessReport | None,
) -> dict[str, Any]:
    return {
        "scenario_id": config.scenario_id,
        "seed": config.seed,
        "state_hash": hash_state(state),
        "config": asdict(config),
        "vehicle_count": len(state.vehicles),
        "readiness": None
        if report is None
        else {
            "readiness_pass": report.readiness_pass,
            "fail_reason": report.fail_reason,
            "algorithm_independent": report.algorithm_independent,
        },
    }


def _apply_sweep_override(
    config: ScenarioConfig,
    overrides: Mapping[str, Any],
    *,
    seed_offset: int,
) -> ScenarioConfig:
    data = asdict(config)
    data = copy.deepcopy(data)
    data["seed"] = int(overrides.get("seed", config.seed + seed_offset))
    for key, value in overrides.items():
        if key == "seed":
            continue
        if "." in key:
            section, name = key.split(".", 1)
            data.setdefault(section, {})[name] = value
        else:
            data.setdefault("vehicles", {})[key] = value
    return scenario_config_from_dict(data)


def _grid_records(grid: Mapping[str, Sequence[Any]] | Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(grid, Mapping):
        records = [dict()]
        for key, values in grid.items():
            records = [{**record, key: value} for record in records for value in values]
        return records
    return [dict(record) for record in grid]


def _deep_update(target: dict[str, Any], source: Mapping[str, Any]) -> None:
    for key, value in source.items():
        if isinstance(value, Mapping) and isinstance(target.get(key), dict):
            _deep_update(target[key], value)
        else:
            target[key] = value


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return value


def _config_value(config: Mapping[str, Any] | Any | None, name: str, default: Any = None) -> Any:
    if config is None:
        return default
    if isinstance(config, Mapping):
        return config.get(name, default)
    value = getattr(config, name, None)
    return default if value is None else value


def scenario_config_hash(config: ScenarioConfig, n: int = 12) -> str:
    return hashlib.sha256(stable_json(asdict(config)).encode("utf-8")).hexdigest()[:n]


__all__ = [
    "NearMissLabel",
    "ReadinessReport",
    "ScenarioConfig",
    "append_readiness_summary_rows",
    "apply_template_perturbation",
    "classify_near_miss",
    "compute_readiness_metrics",
    "diagnostic_rows_for_readiness",
    "generate_initial_vehicles",
    "generate_s0_deconfounded_sample_configs",
    "generate_s0_deconfounded_samples",
    "generate_s0_sample_configs",
    "generate_s0_samples",
    "generate_s2_near_critical",
    "generate_s5_boundary_templates",
    "generate_s6_raw_gap_illusion",
    "generate_state",
    "load_scenario_config",
    "make_road_config",
    "make_scenario_config",
    "no_action_rollout",
    "parameter_sweep_for_readiness",
    "readiness_allows_comparison",
    "readiness_check",
    "readiness_report_to_row",
    "scenario_config_from_dict",
    "scenario_config_hash",
    "suggest_adjustments",
    "write_scenario_manifest",
]
