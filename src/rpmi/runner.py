"""Wave 6A single-decision experiment runner and baseline policies.

The runner keeps V0 narrow: every comparison starts from the same deterministic
scenario state, makes one decision at t0, records trace-first logs, and stops.
Rolling horizon, SUMO, MOBIL, RL, and fallback repair remain outside Wave 6A.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence
import csv
import json
import math
import shutil

from rpmi.actions import (
    Action,
    ActionConfig,
    ActionSelectionResult,
    ActionEvaluation,
    NearMissEdge,
    action_evaluation_to_row,
    action_to_row,
    boundary_type_for_edge,
    commands_for_action,
    coerce_action_config,
    compute_objective,
    edge_metadata,
    evaluate_action,
    evaluate_rollout_inventory,
    find_near_miss_edges,
    generate_candidate_actions,
    run_action_selection,
    select_action,
    slot_inventory_params,
)
from rpmi.analysis import (
    EVIDENCE_PACKAGE_VERSION,
    METRICS_SCHEMA_VERSION,
    READINESS_SCHEMA_VERSION,
    aggregate_failures,
    aggregate_metrics,
    build_evidence_package,
    build_wave7_evidence_package,
    collect_rcmv_trace,
    generate_summary_tables,
    write_state_hash_fairness_csv,
)
from rpmi.config import (
    AlgorithmConfig,
    FeatureFlags,
    RunConfig,
    SimConfig,
    config_to_canonical_dict,
    config_to_snapshot_dict,
    hash_config,
    stable_json,
    validate_v0_flags,
)
from rpmi.conventions import UNITS_VERSION
from rpmi.dynamics import step_traffic
from rpmi.ids import make_action_id, make_decision_context_id
from rpmi.ids import make_reservation_id
from rpmi.logging_schema import (
    append_action_evaluation_rows,
    append_action_rows,
    append_edge_rows,
    append_matching_rows,
    append_readiness_summary_rows,
    append_realized_event_rows,
    append_reservation_rows,
    append_slot_rows,
    append_vehicle_step_rows,
)
from rpmi.matching import (
    DemandRecord,
    MatchingEdge,
    MatchingResult,
    build_matching_edges,
    matching_result_to_rows,
    solve_matching_v0_greedy_conflict,
)
from rpmi.reservations import (
    Reservation,
    create_reservations,
    execute_reservation_guidance,
    reservation_to_row,
    update_reservations_at_tau,
)
from rpmi.run import RunArtifacts, init_run
from rpmi.scenarios import (
    ReadinessReport,
    ScenarioConfig,
    compute_readiness_metrics,
    diagnostic_rows_for_readiness,
    generate_state,
    load_scenario_config,
    make_scenario_config,
    no_action_rollout,
    readiness_allows_comparison,
    readiness_check,
    readiness_report_to_row,
    scenario_config_hash,
    write_scenario_manifest,
)
from rpmi.slots import (
    Edge,
    EdgeQuality,
    build_edges,
    compute_feasible_interval,
    edge_quality_to_row,
    slot_to_row,
)
from rpmi.state import TrafficState, hash_state


DecisionMode = Literal["single_t0_micro_episode"]
ProductionMode = Literal["none", "raw_gap", "density", "speed", "rpmi"]
ActionSetMode = Literal["boundary_speed_only", "lane_change_only", "full_action_set"]
RunMode = Literal["mechanism", "comparison"]


@dataclass(frozen=True)
class AblationConfig:
    """Wave 6A ablation switches.

    ``without_action_conditioned_reservation`` deliberately keeps the selected
    action but creates reservations from the baseline no-action inventory.
    """

    without_rd: bool = False
    without_rcmv: bool = False
    without_cbar: bool = False
    without_theta: bool = False
    forced_accommodation: bool = False
    without_action_conditioned_reservation: bool = False
    boundary_speed_only: bool = False
    lane_change_only: bool = False
    no_near_miss_screening: bool = False
    slot_only_matching: bool = False


@dataclass(frozen=True)
class BaselineConfig:
    baseline_id: str
    uses_inventory: bool
    uses_rd: bool
    uses_near_miss: bool
    production_mode: ProductionMode
    action_conditioned_reservation: bool
    ablations: AblationConfig = AblationConfig()
    action_set_mode: ActionSetMode = "boundary_speed_only"


@dataclass(frozen=True)
class ExperimentRunSpec:
    scenario_config_path: str | None
    algorithm_id: str
    seed: int
    output_root: str | Path
    mode: RunMode = "comparison"
    scenario_id: str | None = None
    run_id: str | None = None
    batch_id: str | None = None
    ablations: AblationConfig = AblationConfig()


@dataclass(frozen=True)
class EpisodeResult:
    metrics: dict[str, Any]
    status: str
    selected_action: Action
    selected_evaluation: ActionEvaluation
    evaluations: list[ActionEvaluation]
    reservations: list[Reservation]
    events: list[dict[str, Any]]


@dataclass(frozen=True)
class BatchResult:
    batch_id: str
    run_ids: list[str]
    run_dirs: list[str]
    aggregate_metrics_path: str
    failure_summary_path: str
    rcmv_trace_path: str
    baseline_comparison_summary_path: str
    ablation_comparison_summary_path: str
    batch_manifest_path: str
    fairness_report_path: str
    evidence_package_path: str = ""
    evidence_index_path: str = ""
    gate_D0_input_path: str = ""
    gate_D1_input_path: str = ""


BASELINE_CONFIGS: dict[str, BaselineConfig] = {
    "fifo_no_production": BaselineConfig(
        baseline_id="fifo_no_production",
        uses_inventory=False,
        uses_rd=False,
        uses_near_miss=False,
        production_mode="none",
        action_conditioned_reservation=False,
    ),
    "raw_gap_reservation": BaselineConfig(
        baseline_id="raw_gap_reservation",
        uses_inventory=True,
        uses_rd=False,
        uses_near_miss=False,
        production_mode="raw_gap",
        action_conditioned_reservation=False,
    ),
    "density_triggered": BaselineConfig(
        baseline_id="density_triggered",
        uses_inventory=True,
        uses_rd=False,
        uses_near_miss=False,
        production_mode="density",
        action_conditioned_reservation=False,
    ),
    "speed_benefit": BaselineConfig(
        baseline_id="speed_benefit",
        uses_inventory=False,
        uses_rd=False,
        uses_near_miss=False,
        production_mode="speed",
        action_conditioned_reservation=False,
    ),
    "rpmi_cmv": BaselineConfig(
        baseline_id="rpmi_cmv",
        uses_inventory=True,
        uses_rd=True,
        uses_near_miss=True,
        production_mode="rpmi",
        action_conditioned_reservation=True,
    ),
    "rpmi_cmv_boundary_speed_only": BaselineConfig(
        baseline_id="rpmi_cmv_boundary_speed_only",
        uses_inventory=True,
        uses_rd=True,
        uses_near_miss=True,
        production_mode="rpmi",
        action_conditioned_reservation=True,
        ablations=AblationConfig(boundary_speed_only=True),
        action_set_mode="boundary_speed_only",
    ),
    "rpmi_cmv_lane_change_only": BaselineConfig(
        baseline_id="rpmi_cmv_lane_change_only",
        uses_inventory=True,
        uses_rd=True,
        uses_near_miss=True,
        production_mode="rpmi",
        action_conditioned_reservation=True,
        ablations=AblationConfig(lane_change_only=True),
        action_set_mode="lane_change_only",
    ),
    "rpmi_cmv_full_action_set": BaselineConfig(
        baseline_id="rpmi_cmv_full_action_set",
        uses_inventory=True,
        uses_rd=True,
        uses_near_miss=True,
        production_mode="rpmi",
        action_conditioned_reservation=True,
        action_set_mode="full_action_set",
    ),
    "rpmi_cmv_without_rd": BaselineConfig(
        baseline_id="rpmi_cmv_without_rd",
        uses_inventory=True,
        uses_rd=False,
        uses_near_miss=True,
        production_mode="rpmi",
        action_conditioned_reservation=True,
        ablations=AblationConfig(without_rd=True),
    ),
    "rpmi_cmv_without_cbar": BaselineConfig(
        baseline_id="rpmi_cmv_without_cbar",
        uses_inventory=True,
        uses_rd=True,
        uses_near_miss=True,
        production_mode="rpmi",
        action_conditioned_reservation=True,
        ablations=AblationConfig(without_cbar=True),
    ),
    "rpmi_cmv_without_theta": BaselineConfig(
        baseline_id="rpmi_cmv_without_theta",
        uses_inventory=True,
        uses_rd=True,
        uses_near_miss=True,
        production_mode="rpmi",
        action_conditioned_reservation=True,
        ablations=AblationConfig(without_theta=True),
    ),
    "forced_accommodation": BaselineConfig(
        baseline_id="forced_accommodation",
        uses_inventory=True,
        uses_rd=False,
        uses_near_miss=True,
        production_mode="rpmi",
        action_conditioned_reservation=True,
        ablations=AblationConfig(forced_accommodation=True),
    ),
    "rpmi_cmv_without_rcmv": BaselineConfig(
        baseline_id="rpmi_cmv_without_rcmv",
        uses_inventory=True,
        uses_rd=True,
        uses_near_miss=True,
        production_mode="rpmi",
        action_conditioned_reservation=True,
        ablations=AblationConfig(without_rcmv=True),
    ),
    "rpmi_cmv_without_action_conditioned_reservation": BaselineConfig(
        baseline_id="rpmi_cmv_without_action_conditioned_reservation",
        uses_inventory=True,
        uses_rd=True,
        uses_near_miss=True,
        production_mode="rpmi",
        action_conditioned_reservation=False,
        ablations=AblationConfig(without_action_conditioned_reservation=True),
    ),
    "rpmi_cmv_without_near_miss": BaselineConfig(
        baseline_id="rpmi_cmv_without_near_miss",
        uses_inventory=True,
        uses_rd=True,
        uses_near_miss=False,
        production_mode="rpmi",
        action_conditioned_reservation=True,
        ablations=AblationConfig(no_near_miss_screening=True),
    ),
}

DEFAULT_BASELINE_IDS = (
    "fifo_no_production",
    "raw_gap_reservation",
    "density_triggered",
    "speed_benefit",
    "rpmi_cmv",
)


def initialize_run(
    config: RunConfig,
    output_root: str | Path,
    *,
    run_id: str | None = None,
    code_version: str | None = None,
) -> RunArtifacts:
    """Create an empty run directory."""

    return init_run(
        config,
        output_root,
        run_id=run_id,
        code_version=code_version,
    )


def run_experiment(run_spec: ExperimentRunSpec) -> Path:
    """Run one Wave 6A single-decision experiment and return its run directory."""

    baseline = resolve_baseline_config(run_spec.algorithm_id, run_spec.ablations)
    scenario_config = _load_or_make_scenario(run_spec)
    config = _run_config_for(scenario_config, baseline, run_spec.seed)
    validate_v0_flags(config)
    if config.sim.decision_mode != "single_t0_micro_episode":
        raise NotImplementedError("rolling horizon is Phase 6B, not the Wave 6A default")

    output_root = Path(run_spec.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    run_id = run_spec.run_id or _experiment_run_id(config)
    artifacts = init_run(config, output_root, run_id=run_id)
    state = generate_state(scenario_config)
    state_digest = hash_state(state)
    decision_context_id = make_decision_context_id(artifacts.run_id, 0)
    log_context = _log_context(
        artifacts,
        decision_context_id,
        state_digest,
        batch_id=run_spec.batch_id or "",
    )

    readiness_metrics = compute_readiness_metrics(state, scenario_config)
    readiness = readiness_check(readiness_metrics, scenario_config)
    _write_run_state_hash(artifacts.run_dir, state_digest)
    write_scenario_manifest(
        artifacts.run_dir / "scenario_manifest.json",
        scenario_config,
        state,
        readiness,
    )
    append_readiness_summary_rows(
        artifacts.run_dir / "readiness_summary.csv",
        [
            readiness_report_to_row(
                readiness,
                log_context,
                algorithm_id="readiness_no_action_diagnostic",
            )
        ],
    )
    _write_readiness_diagnostics(artifacts.run_dir, readiness_metrics, log_context)

    if run_spec.mode == "comparison" and not readiness_allows_comparison(readiness):
        metrics = _readiness_failed_metrics(
            artifacts,
            config,
            scenario_config,
            state_digest,
            readiness,
            batch_id=run_spec.batch_id or "",
        )
        _write_episode_metrics(artifacts.run_dir, metrics)
        return artifacts.run_dir

    result = run_single_t0_episode(
        config,
        state,
        artifacts.run_dir,
        scenario_config=scenario_config,
        baseline_config=baseline,
        decision_context_id=decision_context_id,
        state_hash=state_digest,
        config_hash=artifacts.config_hash,
        code_version=artifacts.code_version,
        run_id=artifacts.run_id,
        batch_id=run_spec.batch_id or "",
    )
    _write_episode_metrics(artifacts.run_dir, result.metrics)
    return artifacts.run_dir


def run_single_t0_episode(
    config: RunConfig,
    state: TrafficState,
    run_dir: str | Path,
    *,
    scenario_config: ScenarioConfig | None = None,
    baseline_config: BaselineConfig | None = None,
    decision_context_id: str = "dc_single_t0",
    state_hash: str | None = None,
    config_hash: str | None = None,
    code_version: str = "local_dirty",
    run_id: str | None = None,
    batch_id: str = "",
) -> EpisodeResult:
    """Execute one t0 policy decision and write Wave 6A logs."""

    if config.sim.decision_mode != "single_t0_micro_episode":
        raise NotImplementedError("rolling horizon is Phase 6B, not the Wave 6A default")
    scenario = scenario_config or make_scenario_config(config.scenario_id, seed=config.seed)
    baseline = baseline_config or resolve_baseline_config(config.algorithm_id)
    run_path = Path(run_dir)
    resolved_run_id = run_id or run_path.name
    state_digest = state_hash or hash_state(state)
    log_context = {
        "batch_id": batch_id,
        "run_id": resolved_run_id,
        "unique_run_id": resolved_run_id,
        "step": state.step,
        "time": state.time,
        "decision_context_id": decision_context_id,
        "state_hash": state_digest,
        "config_hash": config_hash or hash_config(config_to_canonical_dict(config)),
        "code_version": code_version,
        "metrics_schema_version": METRICS_SCHEMA_VERSION,
        "readiness_schema_version": READINESS_SCHEMA_VERSION,
        "evidence_package_version": EVIDENCE_PACKAGE_VERSION,
        "units_version": UNITS_VERSION,
    }

    context = build_decision_context(state, scenario, baseline)
    decision = apply_policy(baseline, state, context)
    append_action_rows(
        run_path / "actions.csv",
        [action_to_row(action, log_context) for action in decision["actions_to_log"]],
    )
    append_action_evaluation_rows(
        run_path / "action_evaluations.csv",
        [action_evaluation_to_row(item, log_context) for item in decision["evaluations"]],
    )

    final_eval = decision["selected_evaluation"]
    final_edge_map = {edge.edge_id: edge for edge in final_eval.edges}
    reservations = _reservations_for_decision(
        baseline,
        decision,
        decision_context_id,
    )
    append_reservation_rows(
        run_path / "reservations.csv",
        [reservation_to_row(item, log_context) for item in reservations],
    )
    _write_final_inventory_logs(run_path, final_eval, log_context)

    execution = execute_episode_until_horizon(
        state,
        decision["selected_action"],
        reservations,
        final_edge_map,
        coerce_action_config(config),
        log_context,
    )
    event_rows = [
        *_lane_change_rejection_events(decision, log_context),
        *execution["event_rows"],
    ]
    append_vehicle_step_rows(run_path / "vehicles_step.csv", execution["vehicle_rows"])
    append_realized_event_rows(run_path / "realized_events.csv", event_rows)
    append_reservation_rows(
        run_path / "reservations.csv",
        [reservation_to_row(item, log_context) for item in execution["reservations"]],
    )

    metrics = compute_episode_metrics(
        config,
        baseline,
        scenario,
        state_digest,
        decision,
        reservations,
        execution["reservations"],
        event_rows,
        run_id=resolved_run_id,
        decision_context_id=decision_context_id,
        config_hash=str(log_context["config_hash"]),
        code_version=code_version,
        batch_id=batch_id,
    )
    return EpisodeResult(
        metrics=metrics,
        status=str(metrics["status"]),
        selected_action=decision["selected_action"],
        selected_evaluation=final_eval,
        evaluations=list(decision["evaluations"]),
        reservations=list(execution["reservations"]),
        events=list(event_rows),
    )


def readiness_filter(config: ScenarioConfig, state: TrafficState) -> ReadinessReport:
    """Run the algorithm-independent no-action readiness gate."""

    return readiness_check(compute_readiness_metrics(state, config), config)


def build_decision_context(
    state: TrafficState,
    scenario_config: ScenarioConfig,
    baseline_config: BaselineConfig,
) -> dict[str, Any]:
    """Build shared no-action diagnostics once for fair baseline decisions."""

    metrics = compute_readiness_metrics(state, scenario_config)
    diagnostic = metrics.get("_diagnostic", {})
    rollout = no_action_rollout(state, scenario_config)
    qualities = list(diagnostic.get("qualities", []))
    edges = list(diagnostic.get("edges", []))
    slots = list(diagnostic.get("slots", []))
    matching = diagnostic.get("matching")
    matching_edges = list(diagnostic.get("matching_edges", []))
    action_params = _action_config_for_scenario(
        scenario_config,
        baseline_config.ablations,
        baseline_config.action_set_mode,
    )
    baseline_action = Action(
        action_id="a0_none",
        action_type="none",
        nominal_edge_id=None,
        controlled_cavs=(),
        target_gap_id=None,
        control_profile={
            "requested_delta_W": 0.0,
            "delta_W_target": 0.0,
            "T_prod": 0.0,
            "u_front": 0.0,
            "u_rear": 0.0,
            "profile_clip_flag": False,
            "estimated_delta_W_after_clip": 0.0,
            "action_profile_feasible": True,
        },
        estimated_cost=0.0,
    )
    baseline_eval = _evaluation_from_matching(
        baseline_action,
        qualities,
        edges,
        matching_edges,
        matching,
        slots,
        params=action_params,
        rollout=rollout,
    )
    return {
        "readiness_metrics": metrics,
        "diagnostic": diagnostic,
        "slots": slots,
        "edges": edges,
        "qualities": qualities,
        "edge_map": {edge.edge_id: edge for edge in edges},
        "matching_edges": matching_edges,
        "matching": matching,
        "rollout": rollout,
        "baseline_action": baseline_action,
        "baseline_evaluation": baseline_eval,
        "action_params": action_params,
    }


def apply_policy(
    baseline_config: BaselineConfig,
    state: TrafficState,
    context: Mapping[str, Any],
) -> dict[str, Any]:
    """Dispatch to a baseline/proposed policy without leaking proposed info."""

    if baseline_config.production_mode == "rpmi":
        return apply_rpmi_policy(state, context, baseline_config)
    return apply_baseline_policy(baseline_config, state, context)


def apply_baseline_policy(
    policy: BaselineConfig | str,
    state: TrafficState,
    context: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply one non-proposed baseline using only its allowed information."""

    baseline = resolve_baseline_config(policy) if isinstance(policy, str) else policy
    baseline_eval: ActionEvaluation = context["baseline_evaluation"]
    action = context["baseline_action"]
    if baseline.production_mode == "none":
        selected = _select_fifo_evaluation(context, action)
        return _baseline_result_from_selected(action, baseline_eval, selected)

    if baseline.production_mode == "raw_gap":
        selected = _select_raw_gap_evaluation(context, action)
    elif baseline.production_mode == "density":
        selected = _select_density_evaluation(context, action)
    elif baseline.production_mode == "speed":
        selected = _select_speed_evaluation(state, context, action)
    else:
        raise ValueError(f"Unsupported baseline production mode: {baseline.production_mode!r}")
    return _baseline_result_from_selected(action, baseline_eval, selected)


def apply_rpmi_policy(
    state: TrafficState,
    context: Mapping[str, Any],
    baseline_config: BaselineConfig | None = None,
) -> dict[str, Any]:
    """Apply proposed RPMI-CMV or its Wave 6A ablation variants."""

    baseline = baseline_config or BASELINE_CONFIGS["rpmi_cmv"]
    params: ActionConfig = context["action_params"]
    if baseline.ablations.without_rcmv:
        return _baseline_result_from_selected(
            context["baseline_action"],
            context["baseline_evaluation"],
            _select_density_evaluation(context, context["baseline_action"]),
            uses_proposed=True,
        )

    if baseline.ablations.no_near_miss_screening:
        selection = _run_rpmi_selection_without_near_miss_screening(
            state,
            context,
            params,
        )
    elif baseline.ablations.forced_accommodation:
        selection = _run_forced_accommodation_selection(
            state,
            context,
            params,
        )
    else:
        selection = run_action_selection(
            state,
            context["qualities"],
            context["edge_map"],
            params,
        )
    actions = _candidate_actions_for_logging(
        state,
        context,
        params,
        no_near_miss_screening=baseline.ablations.no_near_miss_screening,
    )
    if all(action.action_id != selection.selected_action.action_id for action in actions):
        actions.append(selection.selected_action)
    return {
        "selected_action": selection.selected_action,
        "selected_evaluation": selection.selected_evaluation,
        "baseline_evaluation": selection.baseline_evaluation,
        "evaluations": selection.evaluations,
        "actions_to_log": actions,
        "uses_proposed_information": True,
    }


def verify_state_hash_fairness(run_dirs: Sequence[str | Path]) -> dict[str, Any]:
    """Check identical initial state_hash for each scenario/seed comparison group."""

    groups: dict[tuple[str, str], set[str]] = {}
    rows: list[dict[str, Any]] = []
    for run_dir in run_dirs:
        metrics_path = Path(run_dir) / "metrics_episode.json"
        if not metrics_path.exists():
            continue
        payload = json.loads(metrics_path.read_text(encoding="utf-8"))
        metrics = payload.get("metrics", payload)
        key = (str(metrics.get("scenario_id", "")), str(metrics.get("seed", "")))
        state_digest = str(metrics.get("state_hash", ""))
        groups.setdefault(key, set()).add(state_digest)
        rows.append(
            {
                "run_id": metrics.get("run_id", Path(run_dir).name),
                "scenario_id": key[0],
                "seed": key[1],
                "algorithm_id": metrics.get("algorithm_id", ""),
                "state_hash": state_digest,
                "status": metrics.get("status", ""),
            }
        )
    mismatches = [
        {
            "scenario_id": scenario_id,
            "seed": seed,
            "state_hashes": sorted(hashes),
        }
        for (scenario_id, seed), hashes in groups.items()
        if len(hashes) > 1
    ]
    return {
        "fairness_pass": not mismatches,
        "group_count": len(groups),
        "rows": rows,
        "mismatches": mismatches,
    }


def run_baseline_suite(
    scenarios: Sequence[str | Path | ScenarioConfig],
    seeds: Sequence[int],
    baselines: Sequence[str | BaselineConfig] = DEFAULT_BASELINE_IDS,
    output_root: str | Path = "outputs_batch",
    *,
    batch_id: str | None = None,
) -> BatchResult:
    """Run fair single-decision comparisons and generate batch artifacts."""

    output_path = Path(output_root)
    resolved_batch_id = batch_id or _batch_id(scenarios, seeds, baselines)
    batch_dir = output_path / resolved_batch_id
    if batch_dir.exists():
        shutil.rmtree(batch_dir)
    runs_root = batch_dir / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)

    scenario_paths = [_materialize_scenario(item, batch_dir / "scenarios") for item in scenarios]
    baseline_configs = [
        resolve_baseline_config(item) if isinstance(item, str) else item
        for item in baselines
    ]
    run_dirs: list[Path] = []
    for scenario_path in scenario_paths:
        scenario_for_path = load_scenario_config(scenario_path)
        for seed in seeds:
            for baseline in baseline_configs:
                spec = ExperimentRunSpec(
                    scenario_config_path=str(scenario_path),
                    algorithm_id=baseline.baseline_id,
                    seed=seed,
                    output_root=runs_root,
                    run_id=_batch_run_id(
                        resolved_batch_id,
                        scenario_for_path.scenario_id,
                        seed,
                        baseline.baseline_id,
                    ),
                    batch_id=resolved_batch_id,
                    ablations=baseline.ablations,
                )
                run_dirs.append(run_experiment(spec))

    fairness = verify_state_hash_fairness(run_dirs)
    fairness_path = batch_dir / "state_hash_fairness.json"
    fairness_path.write_text(
        json.dumps(fairness, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not fairness["fairness_pass"]:
        raise ValueError(f"state_hash fairness failed: {fairness['mismatches']}")

    manifest_path = batch_dir / "batch_manifest.csv"
    _write_batch_manifest(manifest_path, run_dirs)
    write_state_hash_fairness_csv(
        fairness,
        batch_dir / "state_hash_fairness.csv",
        batch_id=resolved_batch_id,
    )
    evidence_dir = batch_dir / "evidence_package"
    evidence_paths = build_evidence_package(
        run_dirs,
        package_dir=evidence_dir,
        batch_id=resolved_batch_id,
        fairness=fairness,
        batch_manifest_path=manifest_path,
    )
    aggregate_path = evidence_paths["aggregate_metrics_completed"]
    failure_path = evidence_paths["failure_summary_main_batch"]
    rcmv_path = evidence_paths["rcmv_trace"]
    tables = generate_summary_tables(
        run_dirs,
        batch_dir=batch_dir,
        aggregate_metrics_path=aggregate_path,
        failure_summary_path=failure_path,
        rcmv_trace_path=rcmv_path,
    )
    return BatchResult(
        batch_id=resolved_batch_id,
        run_ids=[path.name for path in run_dirs],
        run_dirs=[str(path) for path in run_dirs],
        aggregate_metrics_path=str(aggregate_path),
        failure_summary_path=str(failure_path),
        rcmv_trace_path=str(rcmv_path),
        baseline_comparison_summary_path=str(tables["baseline_comparison_summary"]),
        ablation_comparison_summary_path=str(tables["ablation_comparison_summary"]),
        batch_manifest_path=str(manifest_path),
        fairness_report_path=str(fairness_path),
        evidence_package_path=str(evidence_dir),
        evidence_index_path=str(evidence_paths["evidence_index"]),
        gate_D0_input_path=str(evidence_dir / "gate_D0_input"),
    )


def run_wave7_s5_suite(
    seeds: Sequence[int],
    output_root: str | Path = "outputs/wave7_lane_change_validation",
    *,
    batch_id: str | None = None,
) -> BatchResult:
    """Run the Wave 7 S5 action-set comparison and assemble Gate D1 inputs.

    This produces a Gate D1 input directory but deliberately does not execute
    Gate D1.
    """

    scenario = make_scenario_config(
        "S5",
        seed=0,
        road={"lanes": 2, "target_lane": 0},
        simulation={
            "enable_lane_change": True,
            "u_min": 0.0,
            "u_max": 0.0,
            "theta": 0.0,
            "lambda_C": 0.001,
            "W_min_buffer": 5.0,
            "near_miss_delta_W_max": 12.0,
            "lc_base_cost": 0.0,
            "lc_duration_penalty_weight": 0.0,
            "lc_disturbance_weight": 0.0,
        },
        vehicles={
            "boundary_pairs": ["HDV-CAV", "HDV-HDV"],
            "gap_widths": [7.0, 7.0],
            "pair_spacing": 18.0,
            "inner_receiving_gap_count": 2,
            "ramp_start_x": 110.0,
            "ramp_speed": 10.0,
            "ramp_count": 1,
        },
        readiness_targets={
            "raw_gap_count_min": 0,
            "near_miss_count_min": 1,
            "boundary_cav_min": 0,
            "baseline_ZR_min": 0.0,
        },
    )
    baselines = [
        "raw_gap_reservation",
        "density_triggered",
        "speed_benefit",
        "rpmi_cmv_boundary_speed_only",
        "rpmi_cmv_lane_change_only",
        "rpmi_cmv_full_action_set",
    ]
    output_path = Path(output_root)
    resolved_batch_id = batch_id or _batch_id([scenario], seeds, baselines)
    batch_dir = output_path / resolved_batch_id
    if batch_dir.exists():
        shutil.rmtree(batch_dir)
    runs_root = batch_dir / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)

    scenario_path = _materialize_scenario(scenario, batch_dir / "scenarios")
    baseline_configs = [resolve_baseline_config(item) for item in baselines]
    run_dirs: list[Path] = []
    for seed in seeds:
        for baseline in baseline_configs:
            spec = ExperimentRunSpec(
                scenario_config_path=str(scenario_path),
                algorithm_id=baseline.baseline_id,
                seed=seed,
                output_root=runs_root,
                run_id=_batch_run_id(
                    resolved_batch_id,
                    scenario.scenario_id,
                    seed,
                    baseline.baseline_id,
                ),
                batch_id=resolved_batch_id,
                ablations=baseline.ablations,
            )
            run_dirs.append(run_experiment(spec))

    fairness = verify_state_hash_fairness(run_dirs)
    fairness_path = batch_dir / "state_hash_fairness.json"
    fairness_path.write_text(
        json.dumps(fairness, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not fairness["fairness_pass"]:
        raise ValueError(f"state_hash fairness failed: {fairness['mismatches']}")

    manifest_path = batch_dir / "batch_manifest.csv"
    _write_batch_manifest(manifest_path, run_dirs)
    write_state_hash_fairness_csv(
        fairness,
        batch_dir / "state_hash_fairness.csv",
        batch_id=resolved_batch_id,
    )
    evidence_dir = batch_dir / "evidence_package"
    evidence_paths = build_wave7_evidence_package(
        run_dirs,
        package_dir=evidence_dir,
        batch_id=resolved_batch_id,
        fairness=fairness,
        batch_manifest_path=manifest_path,
    )
    aggregate_path = evidence_paths["aggregate_metrics_completed"]
    failure_path = evidence_paths["failure_summary_main_batch"]
    rcmv_path = evidence_paths["rcmv_trace"]
    tables = generate_summary_tables(
        run_dirs,
        batch_dir=batch_dir,
        aggregate_metrics_path=aggregate_path,
        failure_summary_path=failure_path,
        rcmv_trace_path=rcmv_path,
    )
    return BatchResult(
        batch_id=resolved_batch_id,
        run_ids=[path.name for path in run_dirs],
        run_dirs=[str(path) for path in run_dirs],
        aggregate_metrics_path=str(aggregate_path),
        failure_summary_path=str(failure_path),
        rcmv_trace_path=str(rcmv_path),
        baseline_comparison_summary_path=str(tables["baseline_comparison_summary"]),
        ablation_comparison_summary_path=str(tables["ablation_comparison_summary"]),
        batch_manifest_path=str(manifest_path),
        fairness_report_path=str(fairness_path),
        evidence_package_path=str(evidence_dir),
        evidence_index_path=str(evidence_paths["evidence_index"]),
        gate_D0_input_path=str(evidence_dir / "gate_D0_input"),
        gate_D1_input_path=str(evidence_dir / "gate_D1_input"),
    )


def compute_episode_metrics(
    config: RunConfig,
    baseline: BaselineConfig,
    scenario: ScenarioConfig,
    state_hash_value: str,
    decision: Mapping[str, Any],
    planned_reservations: Sequence[Reservation],
    final_reservations: Sequence[Reservation],
    events: Sequence[Mapping[str, Any]],
    *,
    run_id: str = "",
    decision_context_id: str = "",
    config_hash: str = "",
    code_version: str = "local_dirty",
    batch_id: str = "",
) -> dict[str, Any]:
    """Return the Phase 6A episode metrics JSON payload."""

    selected_eval: ActionEvaluation = decision["selected_evaluation"]
    baseline_eval: ActionEvaluation = decision["baseline_evaluation"]
    selected_action: Action = decision["selected_action"]
    failed_reservations = [
        item
        for item in final_reservations
        if item.status.startswith("failed_")
    ]
    expired = [item for item in final_reservations if item.status == "expired"]
    merged = [item for item in final_reservations if item.status == "merged"]
    stale = [item for item in final_reservations if item.stale_flag]
    reservation_count = len(final_reservations)
    planned_reservation_count = len(planned_reservations)
    generated_reservation_count = reservation_count if reservation_count > 0 else planned_reservation_count
    D_H = selected_eval.D_H
    hard_brakes = [item for item in events if item.get("event_type") == "hard_brake"]
    invalid_events = [
        item
        for item in events
        if item.get("event_type") in {"overlap", "negative_margin"}
    ]
    merge_success_count = len(merged)
    failed_count = len(failed_reservations)
    realized_unserved = max(D_H - merge_success_count, 0.0)
    predicted_unserved = selected_eval.Z_R
    no_reservation_due_to_invalid_supply = max(D_H - generated_reservation_count, 0.0) if generated_reservation_count <= 0 else 0.0
    denominator_warning = (
        failed_count == 0
        and D_H > 0.0
        and (merge_success_count == 0 or realized_unserved > 0.0)
    )
    positive_count = sum(1 for item in decision["evaluations"] if item.RCMV > 0.0)
    max_rcmv = max((item.RCMV for item in decision["evaluations"]), default=0.0)
    theta = float(config.algorithm.theta)
    selected_ids = set(selected_eval.matched_edge_ids)
    baseline_ids = set(baseline_eval.matched_edge_ids)
    stale_harm = (
        max(selected_eval.J - baseline_eval.J, 0.0)
        if baseline.ablations.without_action_conditioned_reservation
        else 0.0
    )
    stale_harm_reason = (
        "without_action_conditioned_reservation uses baseline inventory"
        if baseline.ablations.without_action_conditioned_reservation
        else "not_stale_ablation"
    )
    return {
        "schema_version": METRICS_SCHEMA_VERSION,
        "metrics_schema_version": METRICS_SCHEMA_VERSION,
        "readiness_schema_version": READINESS_SCHEMA_VERSION,
        "evidence_package_version": EVIDENCE_PACKAGE_VERSION,
        "status": "completed",
        "decision_mode": config.sim.decision_mode,
        "scenario_id": scenario.scenario_id,
        "seed": config.seed,
        "algorithm_id": baseline.baseline_id,
        "batch_id": batch_id,
        "run_id": run_id,
        "unique_run_id": run_id,
        "decision_context_id": decision_context_id,
        "config_hash": config_hash,
        "code_version": code_version,
        "state_hash": state_hash_value,
        "readiness_pass": True,
        "readiness_reason": "PASS",
        "readiness_fail_reason": "",
        "uses_inventory": baseline.uses_inventory,
        "uses_rd": baseline.uses_rd,
        "uses_near_miss": baseline.uses_near_miss,
        "production_mode": baseline.production_mode,
        "action_set_mode": baseline.action_set_mode,
        "action_conditioned_reservation": baseline.action_conditioned_reservation,
        "baseline_uses_proposed_information": bool(decision.get("uses_proposed_information", False))
        and baseline.production_mode != "rpmi",
        "ablation_without_rd": baseline.ablations.without_rd,
        "ablation_without_rcmv": baseline.ablations.without_rcmv,
        "ablation_without_cbar": baseline.ablations.without_cbar,
        "ablation_without_theta": baseline.ablations.without_theta,
        "diagnostic_forced_accommodation": baseline.ablations.forced_accommodation,
        "ablation_without_action_conditioned_reservation": baseline.ablations.without_action_conditioned_reservation,
        "ablation_no_near_miss_screening": baseline.ablations.no_near_miss_screening,
        "D_H": D_H,
        "mean_ramp_delay": _mean_delay(final_reservations, selected_eval),
        "merge_success_count": merge_success_count,
        "failed_reservation_count": failed_count,
        "generated_reservation_count": generated_reservation_count,
        "failed_reservation_rate": _rate(failed_count, generated_reservation_count),
        "failed_reservation_denominator": "generated_reservation_count",
        "merge_success_rate_over_demand": _rate(merge_success_count, D_H),
        "predicted_unserved_demand_count": predicted_unserved,
        "predicted_unserved_demand_rate": _rate(predicted_unserved, D_H),
        "realized_unserved_demand_count": realized_unserved,
        "realized_unserved_demand_rate": _rate(realized_unserved, D_H),
        "unserved_demand_count": realized_unserved,
        "no_reservation_due_to_invalid_supply_count": no_reservation_due_to_invalid_supply,
        "no_reservation_due_to_invalid_supply_rate": _rate(no_reservation_due_to_invalid_supply, D_H),
        "waiting_or_unserved_penalty": predicted_unserved,
        "denominator_warning_flag": denominator_warning,
        "denominator_notes": "failed_reservation_rate uses generated reservations; merge_success_rate_over_demand uses D_H.",
        "slot_expiration_count": len(expired),
        "slot_expiration_rate": _rate(len(expired), generated_reservation_count),
        "mean_RD_matched": selected_eval.D_bar,
        "hard_brake_count": len(hard_brakes),
        "max_wave_amplitude": _event_max_severity(events),
        "no_fallback_invalid_event_count": len(invalid_events),
        "failure_joinable_rate": _joinable_failure_rate(final_reservations, events),
        "failure_join_key": _failure_join_key_for_metrics(
            run_id=run_id,
            decision_context_id=decision_context_id,
            reservation_id=final_reservations[0].reservation_id if final_reservations else "",
            action_id=selected_action.action_id,
            edge_id=final_reservations[0].edge_id if final_reservations else "",
            slot_id=final_reservations[0].slot_id if final_reservations else "",
        ),
        "throughput_outflow": len(merged),
        "mean_Z_R": selected_eval.Z_R,
        "production_cost_sum": selected_eval.C_bar,
        "selected_action_id": selected_action.action_id,
        "selected_action_type": selected_action.action_type,
        "baseline_J": baseline_eval.J,
        "selected_J": selected_eval.J,
        "selected_RCMV": selected_eval.RCMV,
        "rcmv_positive_margin": max_rcmv - theta,
        "positive_RCMV_candidate_count": positive_count,
        "baseline_S_R": baseline_eval.S_R,
        "baseline_Z_R": baseline_eval.Z_R,
        "selected_S_R": selected_eval.S_R,
        "selected_Z_R": selected_eval.Z_R,
        "delta_S_R": selected_eval.S_R - baseline_eval.S_R,
        "delta_Z_R": baseline_eval.Z_R - selected_eval.Z_R,
        "candidate_action_count": len(decision["evaluations"]),
        "reservation_count": reservation_count,
        "planned_reservation_count": planned_reservation_count,
        "stale_reservation_count": len(stale),
        "stale_reservation_harm": stale_harm,
        "stale_reservation_harm_reason": stale_harm_reason,
        "action_conditioned_gain": baseline_eval.J - selected_eval.J,
        "action_conditioned_gain_reason": "baseline_J - selected_J for same initial state",
        "rd_decision_changed_flag": baseline.ablations.without_rd and selected_ids != baseline_ids,
        "raw_gap_illusion_flag": bool(selected_eval.invalid_count > 0 and baseline.production_mode == "raw_gap"),
        "selected_matched_edge_ids": list(selected_eval.matched_edge_ids),
        "lane_change_candidate_count": lane_change_candidate_count(decision),
        "lane_change_feasible_count": lane_change_feasible_count(decision),
        "lane_change_selected_count": int(selected_action.action_type == "lane_change"),
        "lane_change_success_count": lane_change_success_count(selected_action, merged),
        "lane_change_induced_failure_count": lane_change_induced_failure_count(selected_action, events),
    }


def execute_episode_until_horizon(
    state: TrafficState,
    action: Action,
    reservations: Sequence[Reservation],
    edge_map: Mapping[str, Edge],
    params: ActionConfig,
    log_context: Mapping[str, Any],
) -> dict[str, Any]:
    """Execute the selected action and ramp guidance until H, recording only."""

    current = state
    active_reservations = list(reservations)
    vehicle_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    steps = max(1, int(round(params.H / params.dt)))
    dyn_config = _dynamics_config(params)
    for _ in range(steps):
        action_commands = commands_for_action(action, current.time, params)
        guidance_commands, active_reservations = execute_reservation_guidance(
            current,
            active_reservations,
            current.time,
            u_min=params.u_min,
            u_max=params.u_max,
        )
        commands = {**action_commands, **guidance_commands}
        current, step_rows, step_events = step_traffic(
            current,
            commands,
            dyn_config,
            log_context,
        )
        for event in step_events:
            _link_event_to_reservation(event, active_reservations)
        active_reservations = update_reservations_at_tau(
            current,
            active_reservations,
            edge_map,
            tolerance=max(params.dt, 1e-9) / 2.0,
        )
        vehicle_rows.extend(step_rows)
        event_rows.extend(step_events)
    return {
        "final_state": current,
        "reservations": active_reservations,
        "vehicle_rows": vehicle_rows,
        "event_rows": event_rows,
    }


def _lane_change_rejection_events(
    decision: Mapping[str, Any],
    log_context: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows = []
    for action in decision.get("actions_to_log", []):
        if getattr(action, "action_type", "") != "lane_change":
            continue
        if not bool(getattr(action, "rejected_before_rollout", False)):
            continue
        profile = getattr(action, "control_profile", {}) or {}
        vehicle_ids = list(getattr(action, "controlled_cavs", ()))
        rows.append(
            {
                **dict(log_context),
                "event_id": f"evt_{action.action_id}_lane_change_rejected",
                "event_type": "lane_change_rejected",
                "step": log_context.get("step", 0),
                "time": profile.get("lc_start_time", log_context.get("time", 0.0)),
                "vehicle_ids": vehicle_ids,
                "min_gap": None,
                "min_margin": min(
                    _float_or_inf(profile.get("lc_feasibility_margin_front")),
                    _float_or_inf(profile.get("lc_feasibility_margin_rear")),
                ),
                "severity": 0.0,
                "linked_reservation_id": None,
                "linked_action_id": action.action_id,
                "linked_edge_id": getattr(action, "nominal_edge_id", None),
                "note": getattr(action, "reject_reason", "") or profile.get("lc_reject_reason", ""),
            }
        )
    return rows


def lane_change_candidate_count(decision: Mapping[str, Any]) -> int:
    return sum(
        1
        for action in decision.get("actions_to_log", [])
        if getattr(action, "action_type", "") == "lane_change"
    )


def lane_change_feasible_count(decision: Mapping[str, Any]) -> int:
    return sum(
        1
        for action in decision.get("actions_to_log", [])
        if getattr(action, "action_type", "") == "lane_change"
        and not bool(getattr(action, "rejected_before_rollout", False))
    )


def lane_change_success_count(
    selected_action: Action,
    merged_reservations: Sequence[Reservation],
) -> int:
    if selected_action.action_type != "lane_change":
        return 0
    return sum(1 for item in merged_reservations if item.status == "merged")


def lane_change_induced_failure_count(
    selected_action: Action,
    events: Sequence[Mapping[str, Any]],
) -> int:
    if selected_action.action_type != "lane_change":
        return 0
    return sum(
        1
        for item in events
        if item.get("event_type") in {"overlap", "negative_margin", "hard_brake", "lane_change_induced_failure"}
        and item.get("linked_action_id") == selected_action.action_id
    )


def resolve_baseline_config(
    baseline: str | BaselineConfig,
    ablations: AblationConfig | None = None,
) -> BaselineConfig:
    if isinstance(baseline, BaselineConfig):
        base = baseline
    else:
        if baseline not in BASELINE_CONFIGS:
            raise ValueError(f"Unknown Wave 6A baseline: {baseline!r}")
        base = BASELINE_CONFIGS[baseline]
    if ablations is None or ablations == AblationConfig():
        return base
    merged = _merge_ablations(base.ablations, ablations)
    action_set_mode = base.action_set_mode
    if merged.lane_change_only:
        action_set_mode = "lane_change_only"
    elif merged.boundary_speed_only:
        action_set_mode = "boundary_speed_only"
    return replace(
        base,
        uses_rd=base.uses_rd and not merged.without_rd,
        action_conditioned_reservation=base.action_conditioned_reservation
        and not merged.without_action_conditioned_reservation,
        ablations=merged,
        action_set_mode=action_set_mode,
    )


def _copy_eval_flags(
    evaluation: ActionEvaluation,
    *,
    selected: bool,
    rank: int,
    rcmv: float | None = None,
    rejected_by_theta: bool | None = None,
) -> ActionEvaluation:
    return ActionEvaluation(
        action_id=evaluation.action_id,
        J=evaluation.J,
        Z_bar=evaluation.Z_bar,
        D_bar=evaluation.D_bar,
        C_bar=evaluation.C_bar,
        RCMV=evaluation.RCMV if rcmv is None else rcmv,
        S_R=evaluation.S_R,
        Z_R=evaluation.Z_R,
        D_H=evaluation.D_H,
        matched_edge_ids=list(evaluation.matched_edge_ids),
        selected=selected,
        rejected_by_theta=evaluation.rejected_by_theta
        if rejected_by_theta is None
        else rejected_by_theta,
        matched_count=evaluation.matched_count,
        invalid_count=evaluation.invalid_count,
        rank=rank,
        cost_components=evaluation.cost_components,
        matched_rd_sum=evaluation.matched_rd_sum,
        matching_result=evaluation.matching_result,
        slots=evaluation.slots,
        edges=evaluation.edges,
        edge_qualities=evaluation.edge_qualities,
        matching_edges=evaluation.matching_edges,
        rollout=evaluation.rollout,
    )


def _evaluation_from_matching(
    action: Action,
    qualities: Sequence[EdgeQuality],
    edges: Sequence[Edge],
    matching_edges: Sequence[Any],
    matching: MatchingResult | None,
    slots: Sequence[Any],
    *,
    params: ActionConfig,
    rollout: Mapping[float, TrafficState] | None = None,
) -> ActionEvaluation:
    matched_ids = [] if matching is None else list(matching.selected_edge_ids)
    matched_rd_sum = float(
        sum(quality.RD for quality in qualities if quality.edge_id in set(matched_ids))
    )
    D_H = 0.0 if matching is None else matching.D_H
    Z_R = 0.0 if matching is None else matching.Z_R
    S_R = 0.0 if matching is None else matching.S_R
    objective = compute_objective(
        Z_R,
        D_H,
        matched_rd_sum if not _bool(action.control_profile.get("ignore_rd_objective")) else 0.0,
        action.estimated_cost,
        params.lambda_D,
        params.lambda_C,
    )
    return ActionEvaluation(
        action_id=action.action_id,
        J=objective["J"],
        Z_bar=objective["Z_bar"],
        D_bar=objective["D_bar"],
        C_bar=objective["C_bar"],
        RCMV=0.0,
        S_R=S_R,
        Z_R=Z_R,
        D_H=D_H,
        matched_edge_ids=matched_ids,
        selected=False,
        rejected_by_theta=False,
        matched_count=len(matched_ids),
        invalid_count=sum(1 for quality in qualities if not quality.is_reservable),
        rank=0,
        cost_components={"baseline_policy_cost": action.estimated_cost},
        matched_rd_sum=matched_rd_sum,
        matching_result=matching,
        slots=tuple(slots),
        edges=tuple(edges),
        edge_qualities=tuple(qualities),
        matching_edges=tuple(matching_edges),
        rollout=rollout,
    )


def _select_raw_gap_evaluation(context: Mapping[str, Any], action: Action) -> ActionEvaluation:
    edge_by_id = context["edge_map"]
    edges: Sequence[Edge] = context["edges"]
    qualities: Sequence[EdgeQuality] = context["qualities"]
    selected_edges: list[Edge] = []
    used_ramps: set[int] = set()
    used_slots: set[str] = set()
    for edge in sorted(
        edges,
        key=lambda item: (
            _quality_for_edge(qualities, item.edge_id).W
            if _quality_for_edge(qualities, item.edge_id)
            else -math.inf,
            -item.tau,
            item.edge_id,
        ),
        reverse=True,
    ):
        if edge.ramp_id in used_ramps or edge.slot_id in used_slots:
            continue
        selected_edges.append(edge)
        used_ramps.add(edge.ramp_id)
        used_slots.add(edge.slot_id)
    return _evaluation_for_selected_edge_ids(
        "raw_gap_policy",
        [edge.edge_id for edge in selected_edges],
        action,
        context,
        edge_by_id=edge_by_id,
    )


def _select_fifo_evaluation(context: Mapping[str, Any], action: Action) -> ActionEvaluation:
    return _evaluation_for_selected_edge_ids(
        "fifo_no_production_policy",
        _first_arrival_edge_ids(context),
        action,
        context,
        edge_by_id=context["edge_map"],
    )


def _select_density_evaluation(context: Mapping[str, Any], action: Action) -> ActionEvaluation:
    metrics = context["readiness_metrics"]
    target_lane_count = int(metrics.get("boundary_CAV_HDV", 0)) + int(metrics.get("boundary_HDV_CAV", 0))
    trigger = target_lane_count >= int(metrics.get("inner_receiving_gap_count", 0))
    selected_ids = _first_arrival_edge_ids(context) if trigger else []
    return _evaluation_for_selected_edge_ids(
        "density_policy",
        selected_ids,
        action,
        context,
        edge_by_id=context["edge_map"],
    )


def _select_speed_evaluation(
    state: TrafficState,
    context: Mapping[str, Any],
    action: Action,
) -> ActionEvaluation:
    candidates: list[tuple[float, str]] = []
    edge_by_id = context["edge_map"]
    for edge in context["edges"]:
        front = state.vehicles.get(edge.front_id)
        rear = state.vehicles.get(edge.rear_id)
        ramp = state.vehicles.get(edge.ramp_id)
        if front is None or rear is None or ramp is None:
            continue
        if front.veh_type != "CAV" and rear.veh_type != "CAV":
            continue
        del ramp
        speed_gain = max(
            front.v if front.veh_type == "CAV" else 0.0,
            rear.v if rear.veh_type == "CAV" else 0.0,
        )
        candidates.append((speed_gain, edge.edge_id))
    selected = [edge_id for _, edge_id in sorted(candidates, reverse=True)[:1]]
    return _evaluation_for_selected_edge_ids(
        "speed_policy",
        selected,
        action,
        context,
        edge_by_id=edge_by_id,
    )


def _evaluation_for_selected_edge_ids(
    matching_id: str,
    selected_ids: Sequence[str],
    action: Action,
    context: Mapping[str, Any],
    *,
    edge_by_id: Mapping[str, Edge],
) -> ActionEvaluation:
    demand = {
        vehicle.id: DemandRecord(vehicle.id)
        for vehicle in _ramps_from_edges(edge_by_id.values())
    }
    quality_by_id = {quality.edge_id: quality for quality in context["qualities"]}
    selected_matching_edges = []
    for edge_id in selected_ids:
        quality = quality_by_id.get(edge_id)
        edge = edge_by_id.get(edge_id)
        if quality is None or edge is None:
            continue
        selected_matching_edges.append(
            _matching_edge_for_quality(edge, quality)
        )
    selected_supply = float(sum(edge.P_R for edge in selected_matching_edges))
    matching = MatchingResult(
        matching_id=matching_id,
        selected_edges=selected_matching_edges,
        selected_edge_ids=[edge.edge_id for edge in selected_matching_edges],
        S_R=selected_supply,
        Z_R=max(float(len(demand)) - selected_supply, 0.0),
        D_H=float(len(demand)),
        unmatched_ramps=[
            ramp_id
            for ramp_id in sorted(demand)
            if ramp_id not in {edge.ramp_id for edge in selected_matching_edges}
        ],
        conflict_mode="baseline_policy_no_proposed_info",
        solver_name=matching_id,
        objective_value=float(len(selected_matching_edges)),
    )
    return _evaluation_from_matching(
        action,
        context["qualities"],
        context["edges"],
        selected_matching_edges,
        matching,
        context["slots"],
        params=context["action_params"],
        rollout=context.get("rollout"),
    )


def _baseline_result_from_selected(
    action: Action,
    baseline_eval: ActionEvaluation,
    selected_eval: ActionEvaluation,
    *,
    uses_proposed: bool = False,
) -> dict[str, Any]:
    selected = _copy_eval_flags(selected_eval, selected=True, rank=1, rcmv=0.0)
    baseline = _copy_eval_flags(baseline_eval, selected=False, rank=2, rcmv=0.0)
    evaluations = [selected] if selected.action_id == baseline.action_id else [baseline, selected]
    return _policy_result(action, [action], evaluations, selected, uses_proposed=uses_proposed)


def _policy_result(
    action: Action,
    actions: Sequence[Action],
    evaluations: Sequence[ActionEvaluation],
    selected: ActionEvaluation,
    *,
    uses_proposed: bool,
) -> dict[str, Any]:
    baseline_eval = next((item for item in evaluations if item.action_id == "a0_none"), evaluations[0])
    return {
        "selected_action": action,
        "selected_evaluation": selected,
        "baseline_evaluation": baseline_eval,
        "evaluations": list(evaluations),
        "actions_to_log": list(actions),
        "uses_proposed_information": uses_proposed,
    }


def _candidate_actions_for_logging(
    state: TrafficState,
    context: Mapping[str, Any],
    params: ActionConfig,
    *,
    no_near_miss_screening: bool = False,
) -> list[Action]:
    near_misses = (
        _bruteforce_boundary_edges_as_near_misses(state, context)
        if no_near_miss_screening
        else find_near_miss_edges(
            context["qualities"],
            context["edge_map"],
            state,
            params,
        )
    )
    return generate_candidate_actions(near_misses, context["edge_map"], state, params)


def _run_rpmi_selection_without_near_miss_screening(
    state: TrafficState,
    context: Mapping[str, Any],
    params: ActionConfig,
) -> Any:
    near_misses = _bruteforce_boundary_edges_as_near_misses(state, context)
    actions = generate_candidate_actions(near_misses, context["edge_map"], state, params)
    baseline = evaluate_action(actions[0], state, params)
    evaluations = [baseline]
    for action in actions[1:]:
        evaluations.append(evaluate_action(action, state, params, baseline_J=baseline.J))
    return select_action(actions, evaluations, params.theta)


def _run_forced_accommodation_selection(
    state: TrafficState,
    context: Mapping[str, Any],
    params: ActionConfig,
) -> Any:
    actions = _candidate_actions_for_logging(state, context, params)
    baseline = evaluate_action(actions[0], state, params)
    evaluations = [baseline]
    for action in actions[1:]:
        evaluations.append(evaluate_action(action, state, params, baseline_J=baseline.J))
    non_none = [
        item
        for item in evaluations
        if item.action_id != "a0_none" and item.matched_edge_ids and item.matched_count > 0
    ]
    if not non_none:
        return select_action(actions, evaluations, theta=0.0)
    selected = sorted(
        non_none,
        key=lambda item: (
            item.C_bar,
            item.matched_count,
            -item.D_bar,
            item.action_id,
        ),
        reverse=True,
    )[0]
    ranked = sorted(
        evaluations,
        key=lambda item: (item.action_id != selected.action_id, -item.RCMV, item.action_id),
    )
    final_evaluations = [
        _copy_eval_flags(
            evaluation,
            selected=evaluation.action_id == selected.action_id,
            rank=rank,
            rejected_by_theta=False,
        )
        for rank, evaluation in enumerate(ranked, start=1)
    ]
    final_selected = next(item for item in final_evaluations if item.action_id == selected.action_id)
    action_by_id = {action.action_id: action for action in actions}
    return ActionSelectionResult(
        baseline_evaluation=baseline,
        evaluations=final_evaluations,
        selected_action=action_by_id[final_selected.action_id],
        selected_evaluation=final_selected,
    )


def _bruteforce_boundary_edges_as_near_misses(
    state: TrafficState,
    context: Mapping[str, Any],
) -> list[NearMissEdge]:
    """Treat every controllable invalid boundary edge as an action candidate."""

    edge_map: Mapping[str, Edge] = context["edge_map"]
    near_misses: list[NearMissEdge] = []
    for quality in context["qualities"]:
        if quality.is_reservable:
            continue
        edge = edge_map.get(quality.edge_id)
        if edge is None:
            continue
        boundary_type = boundary_type_for_edge(state, edge)
        modes = _available_boundary_modes_for_ablation(boundary_type)
        if not modes:
            continue
        near_misses.append(
            NearMissEdge(
                edge_id=quality.edge_id,
                near_miss_type="no_screening_bruteforce",
                delta_W_req=max(float(quality.delta_W_req), 0.0),
                available_modes=modes,
                screen_score=0.0,
                selected_for_rollout=True,
                ramp_id=edge.ramp_id,
                slot_id=edge.slot_id,
                front_id=edge.front_id,
                rear_id=edge.rear_id,
                tau=edge.tau,
                boundary_type=boundary_type,
                W=quality.W,
                RD=quality.RD,
                reason="no_near_miss_screening",
            )
        )
    return near_misses


def _available_boundary_modes_for_ablation(boundary_type: str) -> tuple[str, ...]:
    if boundary_type == "CAV-HDV":
        return ("front_acc",)
    if boundary_type == "HDV-CAV":
        return ("rear_dec",)
    if boundary_type == "CAV-CAV":
        return ("front_acc", "rear_dec", "front_rear")
    return ()


def _reservations_for_decision(
    baseline: BaselineConfig,
    decision: Mapping[str, Any],
    decision_context_id: str,
) -> list[Reservation]:
    selected_eval: ActionEvaluation = decision["selected_evaluation"]
    if baseline.ablations.without_action_conditioned_reservation:
        baseline_eval: ActionEvaluation = decision["baseline_evaluation"]
        return _create_record_only_reservations(
            baseline_eval,
            decision_context_id=decision_context_id,
            stale_flag=True,
        )
    return _create_record_only_reservations(
        selected_eval,
        decision_context_id=decision_context_id,
        stale_flag=not baseline.action_conditioned_reservation
        and baseline.production_mode == "rpmi",
    )


def _create_record_only_reservations(
    evaluation: ActionEvaluation,
    *,
    decision_context_id: str,
    stale_flag: bool = False,
) -> list[Reservation]:
    edge_by_id = {edge.edge_id: edge for edge in evaluation.edges}
    quality_by_id = {quality.edge_id: quality for quality in evaluation.edge_qualities}
    state_by_tau = dict(evaluation.rollout or {})
    reservations: list[Reservation] = []
    for edge_id in evaluation.matched_edge_ids:
        edge = edge_by_id.get(edge_id)
        quality = quality_by_id.get(edge_id)
        state_tau = state_by_tau.get(round(edge.tau, 10)) if edge is not None else None
        if edge is None or quality is None or state_tau is None:
            continue
        interval = compute_feasible_interval(edge, state_tau)
        planned_x = (interval.lower + interval.upper) / 2.0
        status = "planned"
        reason = ""
        if not quality.is_reservable:
            status = (
                "failed_unreachable"
                if quality.fail_reason_priority in {"UNREACHABLE", "RAMP_END_INFEASIBLE"}
                else "failed_invalid_slot"
            )
            reason = quality.fail_reason_priority
        reservations.append(
            Reservation(
                reservation_id=make_reservation_id(evaluation.action_id, edge.edge_id),
                decision_context_id=decision_context_id,
                ramp_id=edge.ramp_id,
                edge_id=edge.edge_id,
                slot_id=edge.slot_id,
                action_id=evaluation.action_id,
                planned_tau=edge.tau,
                planned_merge_x=planned_x,
                planned_interval_lower=interval.lower,
                planned_interval_upper=interval.upper,
                status=status,
                failure_reason=reason,
                stale_flag=stale_flag,
            )
        )
    return reservations


def _write_final_inventory_logs(
    run_path: Path,
    evaluation: ActionEvaluation,
    log_context: Mapping[str, Any],
) -> None:
    append_slot_rows(
        run_path / "slots.csv",
        [slot_to_row(slot, log_context) for slot in evaluation.slots],
    )
    edge_by_id = {edge.edge_id: edge for edge in evaluation.edges}
    append_edge_rows(
        run_path / "edges.csv",
        [
            edge_quality_to_row(edge_by_id[quality.edge_id], quality, log_context)
            for quality in evaluation.edge_qualities
            if quality.edge_id in edge_by_id
        ],
    )
    if evaluation.matching_result is not None:
        append_matching_rows(
            run_path / "matching.csv",
            matching_result_to_rows(
                evaluation.matching_result,
                evaluation.matching_edges,
                log_context,
            ),
        )


def _write_readiness_diagnostics(
    run_path: Path,
    metrics: Mapping[str, Any],
    log_context: Mapping[str, Any],
) -> None:
    rows = diagnostic_rows_for_readiness(metrics, log_context)
    append_slot_rows(run_path / "slots.csv", rows["slots"])
    append_edge_rows(run_path / "edges.csv", rows["edges"])
    append_matching_rows(run_path / "matching.csv", rows["matching"])


def _write_episode_metrics(run_dir: Path, metrics: Mapping[str, Any]) -> None:
    payload = dict(metrics)
    payload["run_id"] = payload.get("run_id") or run_dir.name
    (run_dir / "metrics_episode.json").write_text(
        json.dumps(
            {"schema_version": METRICS_SCHEMA_VERSION, "metrics": payload},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _readiness_failed_metrics(
    artifacts: RunArtifacts,
    config: RunConfig,
    scenario: ScenarioConfig,
    state_digest: str,
    readiness: ReadinessReport,
    *,
    batch_id: str = "",
) -> dict[str, Any]:
    return {
        "schema_version": METRICS_SCHEMA_VERSION,
        "metrics_schema_version": METRICS_SCHEMA_VERSION,
        "readiness_schema_version": READINESS_SCHEMA_VERSION,
        "evidence_package_version": EVIDENCE_PACKAGE_VERSION,
        "status": "readiness_failed",
        "decision_mode": config.sim.decision_mode,
        "scenario_id": scenario.scenario_id,
        "seed": config.seed,
        "algorithm_id": config.algorithm_id,
        "action_set_mode": BASELINE_CONFIGS.get(
            config.algorithm_id,
            BASELINE_CONFIGS["rpmi_cmv"],
        ).action_set_mode,
        "batch_id": batch_id,
        "run_id": artifacts.run_id,
        "unique_run_id": artifacts.run_id,
        "config_hash": artifacts.config_hash,
        "code_version": artifacts.code_version,
        "state_hash": state_digest,
        "readiness_pass": False,
        "readiness_reason": readiness.fail_reason,
        "readiness_fail_reason": readiness.fail_reason,
        "D_H": readiness.metrics.get("D_H", 0.0),
        "mean_ramp_delay": 0.0,
        "merge_success_count": 0,
        "failed_reservation_count": 0,
        "generated_reservation_count": 0,
        "failed_reservation_rate": 0.0,
        "failed_reservation_denominator": "generated_reservation_count",
        "merge_success_rate_over_demand": 0.0,
        "predicted_unserved_demand_count": readiness.metrics.get("Z_R_0", 0.0),
        "predicted_unserved_demand_rate": _rate(readiness.metrics.get("Z_R_0", 0.0), readiness.metrics.get("D_H", 0.0)),
        "realized_unserved_demand_count": readiness.metrics.get("D_H", 0.0),
        "realized_unserved_demand_rate": _rate(readiness.metrics.get("D_H", 0.0), readiness.metrics.get("D_H", 0.0)),
        "unserved_demand_count": readiness.metrics.get("D_H", 0.0),
        "no_reservation_due_to_invalid_supply_count": readiness.metrics.get("D_H", 0.0),
        "no_reservation_due_to_invalid_supply_rate": _rate(readiness.metrics.get("D_H", 0.0), readiness.metrics.get("D_H", 0.0)),
        "waiting_or_unserved_penalty": readiness.metrics.get("Z_R_0", 0.0),
        "denominator_warning_flag": bool(readiness.metrics.get("D_H", 0.0)),
        "denominator_notes": "readiness_failed run is excluded from completed comparison; demand denominator retained for audit.",
        "slot_expiration_count": 0,
        "slot_expiration_rate": 0.0,
        "mean_RD_matched": 0.0,
        "hard_brake_count": 0,
        "max_wave_amplitude": 0.0,
        "no_fallback_invalid_event_count": 0,
        "failure_joinable_rate": 1.0,
        "failure_join_key": _failure_join_key_for_metrics(
            run_id=artifacts.run_id,
            decision_context_id=make_decision_context_id(artifacts.run_id, 0),
        ),
        "throughput_outflow": 0,
        "mean_Z_R": 0.0,
        "production_cost_sum": 0.0,
        "baseline_J": 0.0,
        "selected_J": 0.0,
        "selected_RCMV": 0.0,
        "rcmv_positive_margin": 0.0,
        "positive_RCMV_candidate_count": 0,
        "candidate_action_count": 0,
        "baseline_S_R": readiness.metrics.get("S_R_0", 0.0),
        "baseline_Z_R": readiness.metrics.get("Z_R_0", 0.0),
        "selected_S_R": 0.0,
        "selected_Z_R": readiness.metrics.get("Z_R_0", 0.0),
        "delta_S_R": 0.0,
        "delta_Z_R": 0.0,
        "selected_action_id": "",
        "selected_action_type": "",
        "reservation_count": 0,
        "planned_reservation_count": 0,
        "stale_reservation_count": 0,
        "stale_reservation_harm": 0.0,
        "stale_reservation_harm_reason": "readiness_failed",
        "action_conditioned_gain": 0.0,
        "action_conditioned_gain_reason": "readiness_failed",
        "rd_decision_changed_flag": False,
        "raw_gap_illusion_flag": bool(readiness.metrics.get("raw_gap_illusion_count", 0)),
        "lane_change_candidate_count": 0,
        "lane_change_feasible_count": 0,
        "lane_change_selected_count": 0,
        "lane_change_success_count": 0,
        "lane_change_induced_failure_count": 0,
    }


def _load_or_make_scenario(run_spec: ExperimentRunSpec) -> ScenarioConfig:
    if run_spec.scenario_config_path is not None:
        loaded = load_scenario_config(run_spec.scenario_config_path)
        data = asdict(loaded)
        data["seed"] = int(run_spec.seed)
        return ScenarioConfig(**data)
    return make_scenario_config(run_spec.scenario_id or "S5", seed=run_spec.seed)


def _run_config_for(
    scenario_config: ScenarioConfig,
    baseline: BaselineConfig,
    seed: int,
) -> RunConfig:
    sim_values = {
        "dt": float(scenario_config.simulation.get("dt", 0.5)),
        "H": float(scenario_config.simulation.get("H", 1.0)),
        "dt_merge": float(scenario_config.simulation.get("dt_merge", 1.0)),
        "total_time": float(scenario_config.simulation.get("H", 1.0)),
        "decision_mode": "single_t0_micro_episode",
        "target_lane": int(scenario_config.road.get("target_lane", 0)),
        "ramp_lane": int(scenario_config.road.get("ramp_lane", -1)),
    }
    algorithm_values = {
        "RD_max": float(scenario_config.simulation.get("RD_max", 1.0)),
        "W_min_buffer": float(scenario_config.simulation.get("W_min_buffer", 5.0)),
        "production_width_buffer": float(
            scenario_config.simulation.get("production_width_buffer", 0.5)
        ),
        "lambda_D": float(scenario_config.simulation.get("lambda_D", 1.0)),
        "lambda_C": float(scenario_config.simulation.get("lambda_C", 1.0)),
        "theta": float(scenario_config.simulation.get("theta", 0.05)),
        "T_prod": float(scenario_config.simulation.get("T_prod", 3.0)),
        "conflict_mode": str(
            scenario_config.simulation.get("conflict_mode", "time_window_default")
        ),
    }
    return RunConfig(
        scenario_id=scenario_config.scenario_id,
        algorithm_id=baseline.baseline_id,
        seed=int(seed),
        sim=SimConfig(**sim_values),
        algorithm=AlgorithmConfig(**algorithm_values),
        flags=FeatureFlags(),
    )


def _action_config_for_scenario(
    scenario_config: ScenarioConfig,
    ablations: AblationConfig,
    action_set_mode: ActionSetMode = "boundary_speed_only",
) -> ActionConfig:
    values = {
        **scenario_config.road,
        **scenario_config.simulation,
        **scenario_config.vehicles,
        **scenario_config.ramp,
    }
    values.setdefault("lambda_D", 1.0)
    if action_set_mode == "lane_change_only" or ablations.lane_change_only:
        values["enable_boundary_speed"] = False
        values["enable_lane_change"] = True
    elif action_set_mode == "full_action_set":
        values["enable_boundary_speed"] = True
        values["enable_lane_change"] = True
    elif action_set_mode == "boundary_speed_only" or ablations.boundary_speed_only:
        values["enable_boundary_speed"] = True
        values["enable_lane_change"] = False
    else:
        values["enable_boundary_speed"] = True
        values["enable_lane_change"] = bool(values.get("enable_lane_change", False))
    if ablations.without_rd:
        values["RD_max"] = 1e9
        values["lambda_D"] = 0.0
    if ablations.without_cbar:
        values["lambda_C"] = 0.0
    if ablations.without_theta:
        values["theta"] = 0.0
    if ablations.slot_only_matching:
        values["conflict_mode"] = "slot_only_debug"
    return coerce_action_config(values)


def _merge_ablations(left: AblationConfig, right: AblationConfig) -> AblationConfig:
    return AblationConfig(
        without_rd=left.without_rd or right.without_rd,
        without_rcmv=left.without_rcmv or right.without_rcmv,
        without_cbar=left.without_cbar or right.without_cbar,
        without_theta=left.without_theta or right.without_theta,
        forced_accommodation=left.forced_accommodation or right.forced_accommodation,
        without_action_conditioned_reservation=left.without_action_conditioned_reservation
        or right.without_action_conditioned_reservation,
        boundary_speed_only=left.boundary_speed_only or right.boundary_speed_only,
        lane_change_only=left.lane_change_only or right.lane_change_only,
        no_near_miss_screening=left.no_near_miss_screening or right.no_near_miss_screening,
        slot_only_matching=left.slot_only_matching or right.slot_only_matching,
    )


def _log_context(
    artifacts: RunArtifacts,
    decision_context_id: str,
    state_digest: str,
    *,
    batch_id: str = "",
) -> dict[str, Any]:
    return {
        "batch_id": batch_id,
        "run_id": artifacts.run_id,
        "unique_run_id": artifacts.run_id,
        "step": 0,
        "time": 0.0,
        "decision_context_id": decision_context_id,
        "state_hash": state_digest,
        "config_hash": artifacts.config_hash,
        "code_version": artifacts.code_version,
        "metrics_schema_version": METRICS_SCHEMA_VERSION,
        "readiness_schema_version": READINESS_SCHEMA_VERSION,
        "evidence_package_version": EVIDENCE_PACKAGE_VERSION,
        "units_version": UNITS_VERSION,
    }


def _write_run_state_hash(run_dir: Path, state_digest: str) -> None:
    (run_dir / "state_hash.txt").write_text(state_digest + "\n", encoding="utf-8")
    (run_dir / "state_hash.json").write_text(
        json.dumps({"state_hash": state_digest}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _experiment_run_id(config: RunConfig) -> str:
    config_hash = hash_config(config_to_canonical_dict(config))
    return f"run_{config.scenario_id}_{config.algorithm_id}_seed{config.seed:04d}_{config_hash}"


def _batch_id(
    scenarios: Sequence[Any],
    seeds: Sequence[int],
    baselines: Sequence[Any],
) -> str:
    payload = {
        "scenarios": [str(item) for item in scenarios],
        "seeds": list(seeds),
        "baselines": [
            item.baseline_id if isinstance(item, BaselineConfig) else str(item)
            for item in baselines
        ],
    }
    return f"batch_{hash_config(payload, n=10)}"


def _batch_run_id(
    batch_id: str,
    scenario_id: str,
    seed: int,
    algorithm_id: str,
) -> str:
    return f"{batch_id}__{scenario_id}__seed{int(seed)}__{algorithm_id}"


def _scenario_id_for_run_id(path: str | Path) -> str:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return Path(path).stem
    return str(payload.get("scenario_id") or Path(path).stem)


def _materialize_scenario(item: str | Path | ScenarioConfig, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    if isinstance(item, ScenarioConfig):
        path = directory / f"{item.scenario_id}_{scenario_config_hash(item)}.json"
        path.write_text(
            json.dumps(asdict(item), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return path
    return Path(item)


def _write_batch_manifest(path: Path, run_dirs: Sequence[Path]) -> None:
    rows = []
    for run_dir in run_dirs:
        metrics = json.loads((run_dir / "metrics_episode.json").read_text(encoding="utf-8"))["metrics"]
        rows.append(
            {
                "batch_id": metrics.get("batch_id", ""),
                "run_id": run_dir.name,
                "unique_run_id": metrics.get("unique_run_id", run_dir.name),
                "run_dir": str(run_dir),
                "scenario_id": metrics.get("scenario_id", ""),
                "seed": metrics.get("seed", ""),
                "algorithm_id": metrics.get("algorithm_id", ""),
                "decision_mode": metrics.get("decision_mode", ""),
                "state_hash": metrics.get("state_hash", ""),
                "config_hash": metrics.get("config_hash", ""),
                "code_version": metrics.get("code_version", ""),
                "metrics_schema_version": metrics.get("metrics_schema_version", METRICS_SCHEMA_VERSION),
                "readiness_schema_version": metrics.get("readiness_schema_version", READINESS_SCHEMA_VERSION),
                "evidence_package_version": metrics.get("evidence_package_version", EVIDENCE_PACKAGE_VERSION),
                "status": metrics.get("status", ""),
            }
        )
    _write_csv(
        path,
        rows,
        [
            "batch_id",
            "run_id",
            "unique_run_id",
            "run_dir",
            "scenario_id",
            "seed",
            "algorithm_id",
            "decision_mode",
            "state_hash",
            "config_hash",
            "code_version",
            "metrics_schema_version",
            "readiness_schema_version",
            "evidence_package_version",
            "status",
        ],
    )


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _csv_value(row.get(column)) for column in columns})


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return value


def _quality_for_edge(
    qualities: Sequence[EdgeQuality],
    edge_id: str,
) -> EdgeQuality | None:
    return next((quality for quality in qualities if quality.edge_id == edge_id), None)


def _first_baseline_matched_ids(context: Mapping[str, Any]) -> list[str]:
    matching = context.get("matching")
    if matching is None:
        return []
    return list(getattr(matching, "selected_edge_ids", []))


def _first_arrival_edge_ids(context: Mapping[str, Any]) -> list[str]:
    selected: list[Edge] = []
    used_ramps: set[int] = set()
    used_slots: set[str] = set()
    for edge in sorted(context["edges"], key=lambda item: (item.tau, item.ramp_id, item.edge_id)):
        if edge.ramp_id in used_ramps or edge.slot_id in used_slots:
            continue
        selected.append(edge)
        used_ramps.add(edge.ramp_id)
        used_slots.add(edge.slot_id)
    return [edge.edge_id for edge in selected]


def _ramps_from_edges(edges: Sequence[Edge]) -> list[Any]:
    class _Ramp:
        def __init__(self, ramp_id: int) -> None:
            self.id = ramp_id

    return [_Ramp(ramp_id) for ramp_id in sorted({edge.ramp_id for edge in edges})]


def _matching_edge_for_quality(edge: Edge, quality: EdgeQuality) -> Any:
    return MatchingEdge(
        edge_id=quality.edge_id,
        ramp_id=quality.ramp_id,
        slot_id=quality.slot_id,
        physical_gap_id=edge.physical_gap_id,
        tau=edge.tau,
        P_R=quality.P_R,
        RD=quality.RD,
        weight=quality.P_R,
    )


def _dynamics_config(values: ActionConfig) -> dict[str, Any]:
    return {
        "dt": values.dt,
        "action_mode": values.action_mode,
        "limits": {"u_min": values.u_min, "u_max": values.u_max, "v_max": values.v_max},
        "min_gap": values.event_min_gap,
    }


def _link_event_to_reservation(
    event: dict[str, Any],
    reservations: Sequence[Reservation],
) -> None:
    if event.get("linked_reservation_id"):
        return
    vehicle_ids = {int(value) for value in event.get("vehicle_ids", [])}
    for reservation in reservations:
        if reservation.ramp_id in vehicle_ids:
            event["linked_reservation_id"] = reservation.reservation_id
            event["linked_action_id"] = reservation.action_id
            event["linked_edge_id"] = reservation.edge_id
            return


def _mean_delay(
    reservations: Sequence[Reservation],
    selected_eval: ActionEvaluation,
) -> float:
    if not reservations:
        return max(selected_eval.Z_R, 0.0)
    return float(
        sum(max(item.planned_tau, 0.0) for item in reservations) / len(reservations)
    )


def _rate(numerator: int, denominator: int) -> float:
    return 0.0 if float(denominator) <= 0 else float(numerator) / float(denominator)


def _joinable_failure_rate(
    reservations: Sequence[Reservation],
    events: Sequence[Mapping[str, Any]],
) -> float:
    failure_count = sum(
        1
        for item in reservations
        if item.status.startswith("failed_") or item.status == "expired"
    ) + len(events)
    if failure_count == 0:
        return 1.0
    joinable = sum(
        1
        for item in reservations
        if (item.status.startswith("failed_") or item.status == "expired")
        and bool(item.reservation_id or item.action_id or item.edge_id or item.slot_id)
    )
    joinable += sum(
        1
        for item in events
        if bool(
            item.get("linked_reservation_id")
            or item.get("linked_action_id")
            or item.get("linked_edge_id")
            or item.get("event_id")
        )
    )
    return float(joinable) / float(failure_count)


def _failure_join_key_for_metrics(
    *,
    run_id: str,
    decision_context_id: str = "",
    reservation_id: str = "",
    action_id: str = "",
    edge_id: str = "",
    slot_id: str = "",
) -> str:
    return "|".join(
        part
        for part in [run_id, decision_context_id, reservation_id, action_id, edge_id, slot_id]
        if part
    )


def _event_max_severity(events: Sequence[Mapping[str, Any]]) -> float:
    return max((float(item.get("severity", 0.0) or 0.0) for item in events), default=0.0)


def _float_or_inf(value: Any) -> float:
    if value in (None, ""):
        return math.inf
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.inf


def _bool(value: Any) -> bool:
    return bool(value)


__all__ = [
    "AblationConfig",
    "BASELINE_CONFIGS",
    "BaselineConfig",
    "BatchResult",
    "DEFAULT_BASELINE_IDS",
    "EpisodeResult",
    "ExperimentRunSpec",
    "apply_baseline_policy",
    "apply_policy",
    "apply_rpmi_policy",
    "build_decision_context",
    "compute_episode_metrics",
    "execute_episode_until_horizon",
    "initialize_run",
    "readiness_filter",
    "resolve_baseline_config",
    "run_baseline_suite",
    "run_experiment",
    "run_wave7_s5_suite",
    "run_single_t0_episode",
    "verify_state_hash_fairness",
]
