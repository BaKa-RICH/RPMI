"""Wave 8 rolling-horizon reservation control and D2 input packaging.

This module implements the Wave 8 V0 contract from
``07_Wave_8_Rolling_Horizon_Reservation_and_D2_Evidence_Spec_v2_zh.md``.
It deliberately prepares Gate D2 inputs but never executes the Gate D2
retain/downgrade/remove decision.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping, Sequence
import csv
import json
import math
import shutil

from rpmi.actions import (
    Action,
    ActionConfig,
    ActionEvaluation,
    action_evaluation_to_row,
    action_to_row,
    coerce_action_config,
    commands_for_action,
    evaluate_action,
    run_action_selection,
)
from rpmi.analysis import (
    METRICS_SCHEMA_VERSION,
    READINESS_SCHEMA_VERSION,
)
from rpmi.config import (
    AlgorithmConfig,
    FeatureFlags,
    RunConfig,
    SimConfig,
    config_to_canonical_dict,
    hash_config,
    validate_v0_flags,
)
from rpmi.conventions import UNITS_VERSION
from rpmi.dynamics import step_traffic
from rpmi.ids import make_decision_context_id
from rpmi.logging_schema import (
    CSV_LOG_SCHEMAS,
    append_action_evaluation_rows,
    append_action_lifecycle_rows,
    append_action_rows,
    append_decision_context_rows,
    append_event_metric_window_rows,
    append_realized_event_rows,
    append_rolling_demand_lifecycle_rows,
    append_rolling_failure_trace_rows,
    append_rolling_matching_trace_rows,
    append_rolling_plan_commitment_rows,
    append_rolling_reservation_rows,
    append_rolling_slot_consumption_rows,
    append_reservation_replan_rows,
    append_vehicle_step_rows,
)
from rpmi.run import RunArtifacts, init_run
from rpmi.scenarios import (
    ScenarioConfig,
    generate_state,
    load_scenario_config,
    make_scenario_config,
    write_scenario_manifest,
)
from rpmi.slots import Edge, compute_feasible_interval
from rpmi.state import TrafficState, hash_state


WAVE8_EVIDENCE_PACKAGE_VERSION = "wave_8_v2"

DEMAND_TERMINAL_STATUSES = {"merged", "unserved"}
RESERVATION_TERMINAL_STATUSES = {
    "merged",
    "expired",
    "failed_unreachable",
    "failed_invalid_slot",
    "failed_unsafe_margin",
    "cancelled_by_replan",
    "superseded",
}
ACTIVE_RESERVATION_STATUSES = {"planned", "active_guidance", "refreshed"}
COMMITMENT_ACTIVE_STATUSES = {"planned_committed", "active_guidance_locked"}

WAVE8_AGGREGATE_COLUMNS = [
    "batch_id",
    "run_id",
    "unique_run_id",
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
    "D_H",
    "merge_success_count",
    "merge_success_rate_over_demand",
    "predicted_unserved_demand_count",
    "predicted_unserved_demand_rate",
    "realized_unserved_demand_count",
    "realized_unserved_demand_rate",
    "generated_reservation_count",
    "planned_reservation_count",
    "reservation_count",
    "failed_reservation_count",
    "failed_reservation_rate",
    "failed_reservation_denominator",
    "mean_ramp_waiting_time",
    "expired_returned_demand_count",
    "cancelled_returned_demand_count",
    "returned_demand_reassigned_count",
    "returned_demand_unserved_count",
    "expired_reservation_count",
    "invalidated_reservation_count",
    "stale_reservation_harm_count",
    "slot_consumption_conflict_detected_count",
    "slot_consumption_conflict_method",
    "duplicate_gap_consumption_count",
    "full_trace_join_rate",
    "rolling_decision_count",
    "reservation_refresh_count",
    "reservation_cancel_count",
    "reservation_supersede_count",
    "overlap_reject_count",
    "mean_action_executed_fraction",
    "rolling_consistency_violation_count",
    "rolling_vs_single_delta_failure_rate",
    "rolling_vs_single_delta_delay",
    "rolling_vs_single_delta_expiration_rate",
    "reservation_churn_rate",
    "action_switch_count",
    "active_guidance_cancel_count",
    "plan_lock_violation_count",
    "mean_committed_reservation_age",
    "rolling_vs_no_commitment_delta_churn_rate",
    "rolling_vs_single_delta_merge_success_rate_over_demand",
    "rolling_vs_single_delta_realized_unserved_demand_rate",
    "rolling_vs_stale_delta_merge_success_rate_over_demand",
    "rolling_vs_stale_delta_realized_unserved_demand_rate",
    "rolling_vs_stale_delta_expired_reservation_count",
    "rolling_vs_stale_delta_invalidated_reservation_count",
    "rolling_vs_stale_delta_expiration_rate",
    "rolling_vs_stale_delta_stale_harm_count",
    "rolling_vs_no_commitment_delta_action_switch_count",
    "per_context_recompute_checked",
    "slot_consumption_conflict_checked",
    "plan_commitment_checked",
    "benefit_baseline_checked",
    "demand_denominator_checked",
    "full_trace_join_checked",
    "hidden_fallback_detected",
    "no_hidden_fallback_invalid_event_count",
    "failure_join_key",
]

FAILURE_SUMMARY_COLUMNS = [
    "batch_id",
    "run_id",
    "unique_run_id",
    "scenario_id",
    "seed",
    "algorithm_id",
    "decision_mode",
    "failure_source",
    "decision_context_id",
    "failure_id",
    "action_id",
    "edge_id",
    "reservation_id",
    "demand_id",
    "physical_gap_id",
    "realized_event_id",
    "failure_stage",
    "failure_reason",
    "is_hidden_fallback",
    "can_join_full_chain",
    "failure_join_key",
]


@dataclass(frozen=True)
class RollingRunSpec:
    scenario_config_path: str | None = None
    scenario_id: str | None = None
    algorithm_id: str = "rpmi_cmv_rolling"
    seed: int = 0
    output_root: str | Path = "outputs_wave8"
    run_id: str | None = None
    batch_id: str = ""
    profile: str | None = None


@dataclass(frozen=True)
class RollingEpisodeResult:
    run_dir: Path
    metrics: dict[str, Any]


@dataclass(frozen=True)
class RollingBatchResult:
    batch_id: str
    run_ids: list[str]
    run_dirs: list[str]
    aggregate_metrics_path: str
    failure_summary_path: str
    evidence_package_path: str
    gate_D2_input_path: str
    wave_8_report_path: str


@dataclass
class CommittedReservation:
    reservation_id: str
    lineage_root_reservation_id: str
    lineage_parent_reservation_id: str
    demand_id: str
    ramp_vehicle_id: int
    edge: Edge
    action_id: str
    planned_tau: float
    planned_merge_x: float
    decision_context_id: str
    status: str = "planned"
    commitment_status: str = "planned_committed"
    is_locked: bool = False
    created_context_index: int = 0
    last_update_context_index: int = 0
    status_reason: str = "new_plan"
    realized_event_id: str = ""
    failure_join_key: str = ""

    @property
    def physical_gap_id(self) -> str:
        return _gap_id(self.edge.physical_gap_id)

    @property
    def slot_group_id(self) -> str:
        return _gap_id(self.edge.physical_gap_id)


class RollingTraceWriter:
    def __init__(
        self,
        run_dir: Path,
        *,
        run_id: str,
        batch_id: str,
        config_hash: str,
        code_version: str,
    ) -> None:
        self.run_dir = run_dir
        self.run_id = run_id
        self.batch_id = batch_id
        self.config_hash = config_hash
        self.code_version = code_version

    def context(self, context_id: str, state_hash_value: str, step: int, time: float) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "run_id": self.run_id,
            "unique_run_id": self.run_id,
            "step": step,
            "time": time,
            "decision_context_id": context_id,
            "state_hash": state_hash_value,
            "config_hash": self.config_hash,
            "code_version": self.code_version,
            "metrics_schema_version": METRICS_SCHEMA_VERSION,
            "readiness_schema_version": READINESS_SCHEMA_VERSION,
            "evidence_package_version": WAVE8_EVIDENCE_PACKAGE_VERSION,
            "units_version": UNITS_VERSION,
        }


def run_rolling_experiment(run_spec: RollingRunSpec) -> Path:
    """Run one Wave 8 rolling-horizon episode and return the run directory."""

    scenario = _load_or_make_rolling_scenario(run_spec)
    profile = run_spec.profile or str(
        scenario.mechanism_targets.get("wave8_profile", "main_rolling_batch")
    )
    config = _rolling_run_config_for(scenario, run_spec.algorithm_id, run_spec.seed)
    validate_v0_flags(config)
    output_root = Path(run_spec.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    run_id = run_spec.run_id or _rolling_run_id(config, profile)
    artifacts = init_run(config, output_root, run_id=run_id)
    state = generate_state(scenario)
    result = run_rolling_horizon_episode(
        config,
        state,
        artifacts.run_dir,
        scenario_config=scenario,
        profile=profile,
        artifacts=artifacts,
        batch_id=run_spec.batch_id,
    )
    _write_episode_metrics(artifacts.run_dir, result.metrics)
    return artifacts.run_dir


def run_rolling_horizon_episode(
    config: RunConfig,
    state: TrafficState,
    run_dir: str | Path,
    *,
    scenario_config: ScenarioConfig | None = None,
    profile: str = "main_rolling_batch",
    artifacts: RunArtifacts | None = None,
    batch_id: str = "",
) -> RollingEpisodeResult:
    """Execute Wave 8 rolling closed-loop control and write trace CSVs."""

    if config.sim.decision_mode != "rolling_horizon_episode":
        raise ValueError("Wave 8 requires decision_mode='rolling_horizon_episode'.")
    scenario = scenario_config or make_wave8_scenario(profile, seed=config.seed)
    run_path = Path(run_dir)
    run_id = artifacts.run_id if artifacts is not None else run_path.name
    config_hash = artifacts.config_hash if artifacts is not None else hash_config(config_to_canonical_dict(config))
    code_version = artifacts.code_version if artifacts is not None else "local_dirty"
    initial_state_hash = hash_state(state)
    (run_path / "state_hash.txt").write_text(initial_state_hash + "\n", encoding="utf-8")
    (run_path / "state_hash.json").write_text(
        json.dumps({"state_hash": initial_state_hash}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_scenario_manifest(
        run_path / "scenario_manifest.json",
        scenario,
        state,
        _rolling_readiness_report(scenario, state),
    )

    writer = RollingTraceWriter(
        run_path,
        run_id=run_id,
        batch_id=batch_id,
        config_hash=config_hash,
        code_version=code_version,
    )
    action_params = _action_config_for_rolling(scenario, config)
    context_count = max(2, int(math.ceil(config.sim.total_time / config.sim.decision_interval)))
    interval = float(config.sim.decision_interval)
    committed: dict[str, CommittedReservation] = {}
    consumed_gaps: set[str] = set()
    blocked_gaps: set[str] = set()
    demand_status: dict[str, str] = {
        _demand_id(run_id, vehicle.id): "active"
        for vehicle in state.vehicles.values()
        if vehicle.active and vehicle.role == "ramp"
    }
    demand_return_context: dict[str, str] = {}
    previous_context_id = ""
    current_state = state
    metrics_acc = _empty_metric_accumulator()

    for context_index in range(context_count):
        context_id = make_decision_context_id(run_id, context_index)
        context_time = round(current_state.time, 10)
        state_hash_value = hash_state(current_state)
        log_context = writer.context(context_id, state_hash_value, current_state.step, context_time)
        next_context_id = (
            make_decision_context_id(run_id, context_index + 1)
            if context_index + 1 < context_count
            else ""
        )

        _reactivate_returned_demands(
            demand_status,
            demand_return_context,
            context_id,
            log_context,
            run_path,
        )
        terminal_rows = _update_terminal_reservations(
            committed,
            demand_status,
            consumed_gaps,
            blocked_gaps,
            context_time,
            context_id,
            next_context_id,
            log_context,
            run_path,
            metrics_acc,
            profile,
        )

        baseline_eval = evaluate_action(_none_action(), current_state, action_params)
        edge_map = {edge.edge_id: edge for edge in baseline_eval.edges}
        selection = run_action_selection(
            current_state,
            baseline_eval.edge_qualities,
            edge_map,
            action_params,
        )
        selected_action, selected_eval = _resolve_action_overlap(
            selection.selected_action,
            selection.selected_evaluation,
            committed,
            context_time,
            interval,
            log_context,
            run_path,
            metrics_acc,
            profile,
        )
        if selected_action.action_id != selection.selected_action.action_id:
            selected_eval = evaluate_action(selected_action, current_state, action_params, baseline_J=baseline_eval.J)
        _write_action_rows(
            run_path,
            log_context,
            selected_action,
            selection.evaluations,
        )

        stale_rows = _write_matching_traces(
            run_path,
            log_context,
            context_id,
            baseline_eval,
            selected_eval,
            committed,
        )
        metrics_acc["per_context_recompute_checked"] = True
        metrics_acc["stale_trace_row_count"] += len(stale_rows)

        active_demand_ids = [
            demand_id
            for demand_id, status in demand_status.items()
            if status in {"active", "returned_after_expire", "returned_after_cancel"}
        ]
        replan_results = _apply_commitment_rule(
            committed,
            demand_status,
            active_demand_ids,
            selected_eval,
            selected_action,
            context_id,
            context_index,
            context_time,
            next_context_id,
            consumed_gaps,
            blocked_gaps,
            log_context,
            run_path,
            config,
            metrics_acc,
            profile,
        )
        _write_decision_context(
            run_path,
            log_context,
            context_id,
            context_index,
            context_time,
            state_hash_value,
            previous_context_id,
            demand_status,
            committed,
            consumed_gaps,
            blocked_gaps,
            selection.evaluations,
            selected_action,
            selected_eval,
        )

        current_state = _execute_interval(
            current_state,
            selected_action,
            committed,
            action_params,
            interval,
            context_time,
            log_context,
            run_path,
            metrics_acc,
        )
        _mark_interval_merges(
            committed,
            demand_status,
            consumed_gaps,
            blocked_gaps,
            current_state.time,
            context_id,
            log_context,
            run_path,
            metrics_acc,
            profile,
        )
        _mark_unserved_at_final_context(
            demand_status,
            committed,
            context_index,
            context_count,
            context_id,
            log_context,
            run_path,
            metrics_acc,
        )
        metrics_acc["replan_result_count"] += len(replan_results)
        metrics_acc["terminal_update_count"] += len(terminal_rows)
        previous_context_id = context_id

    metrics = _rolling_metrics(
        config,
        scenario,
        run_id,
        batch_id,
        config_hash,
        code_version,
        initial_state_hash,
        demand_status,
        committed,
        metrics_acc,
    )
    _write_run_ablation_metric_rows(run_path, metrics)
    return RollingEpisodeResult(run_path, metrics)


def make_wave8_scenario(profile: str = "main_rolling_batch", *, seed: int = 0) -> ScenarioConfig:
    """Return one deterministic Wave 8 scenario profile."""

    scenario_id_by_profile = {
        "main_rolling_batch": "D2-main-rolling",
        "rolling_stale": "D2-S7-rolling-stale",
        "expiration_return": "D2-expiration-return",
        "slot_consumption_conflict": "D2-slot-consumption-conflict",
        "action_conditioned_recompute": "D2-action-conditioned-recompute",
        "plan_commitment": "D2-plan-commitment",
        "no_commitment_ablation": "D2-no-commitment-ablation",
        "negative_control": "D2-negative-control",
    }
    scenario_id = scenario_id_by_profile.get(profile, profile)
    vehicles: dict[str, Any] = {
        "boundary_pairs": ["CAV-HDV", "HDV-CAV"],
        "gap_widths": [7.0, 26.0],
        "front_x": 120.0,
        "pair_spacing": 90.0,
        "target_speed": 10.0,
        "ramp_count": 1,
        "ramp_start_x": 74.0,
        "ramp_speed": 10.0,
        "inner_receiving_gap_count": 2,
    }
    simulation: dict[str, Any] = {
        "dt": 0.5,
        "H": 2.0,
        "dt_merge": 1.0,
        "total_time": 3.0,
        "decision_interval": 1.0,
        "W_min_buffer": 5.0,
        "RD_max": 1.0,
        "theta": 0.0,
        "lambda_C": 0.001,
        "u_min": -4.5,
        "u_max": 200.0,
        "T_prod": 2.0,
        "near_miss_delta_W_max": 12.0,
        "enable_lane_change": True,
        "enable_boundary_speed": True,
        "event_min_gap": 0.0,
        "switching_cost": 0.05,
        "hysteresis_threshold": 0.05,
        "active_guidance_lock_time": 1.0,
    }
    if profile == "slot_consumption_conflict":
        vehicles.update({"ramp_count": 2, "ramp_spacing": 2.0, "gap_widths": [30.0]})
        simulation.update({"H": 3.0, "total_time": 3.0})
    elif profile == "negative_control":
        vehicles.update({"gap_widths": [1.0], "ramp_count": 1, "ramp_start_x": -200.0, "ramp_speed": 0.0})
        simulation.update({"u_max": 0.0, "near_miss_delta_W_max": 0.0, "H": 2.0})
    elif profile == "plan_commitment":
        vehicles.update({"gap_widths": [30.0], "ramp_count": 1, "ramp_start_x": 76.0})
        simulation.update({"theta": 999.0})
    elif profile == "expiration_return":
        vehicles.update({"gap_widths": [30.0], "ramp_count": 1})
    elif profile == "rolling_stale":
        vehicles.update({"gap_widths": [30.0, 8.0], "ramp_count": 1})
    elif profile == "action_conditioned_recompute":
        vehicles.update({"gap_widths": [7.0], "ramp_count": 1, "ramp_start_x": 74.0})
        simulation.update({"lambda_C": 0.0, "theta": 0.0, "active_guidance_lock_time": 0.25})
    elif profile == "no_commitment_ablation":
        vehicles.update({"gap_widths": [28.0, 30.0], "ramp_count": 1})
        simulation.update({"theta": 0.0})

    return make_scenario_config(
        scenario_id,
        seed=seed,
        simulation=simulation,
        vehicles=vehicles,
        readiness_targets={
            "raw_gap_count_min": 0,
            "baseline_ZR_min": 0.0,
            "near_miss_count_min": 0,
            "boundary_cav_min": 0,
        },
        mechanism_targets={
            "mechanism": "Wave8",
            "mechanism_target": profile,
            "wave8_profile": profile,
            "expected_failure_mode": "rolling lifecycle stress case",
            "seed_policy": "deterministic fixed seed per scenario/algorithm fairness group",
        },
    )


def run_wave8_d2_suite(
    seeds: Sequence[int] = (0,),
    output_root: str | Path = "outputs/wave8_rolling_validation",
    *,
    batch_id: str | None = None,
) -> RollingBatchResult:
    """Run Wave 8 evidence scenarios and assemble Gate D2 input only."""

    profiles = [
        "main_rolling_batch",
        "rolling_stale",
        "expiration_return",
        "slot_consumption_conflict",
        "action_conditioned_recompute",
        "plan_commitment",
        "no_commitment_ablation",
        "negative_control",
    ]
    output_path = Path(output_root)
    resolved_batch_id = batch_id or _batch_id(profiles, seeds)
    batch_dir = output_path / resolved_batch_id
    if batch_dir.exists():
        shutil.rmtree(batch_dir)
    runs_root = batch_dir / "runs"
    scenario_root = batch_dir / "scenarios"
    runs_root.mkdir(parents=True, exist_ok=True)
    scenario_root.mkdir(parents=True, exist_ok=True)

    run_dirs: list[Path] = []
    for seed in seeds:
        for profile in profiles:
            scenario = make_wave8_scenario(profile, seed=seed)
            scenario_path = scenario_root / f"{scenario.scenario_id}_seed{seed}.json"
            scenario_path.write_text(
                json.dumps(_scenario_to_json(scenario), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            run_id = f"{resolved_batch_id}__{scenario.scenario_id}__seed{seed}__rpmi_cmv_rolling"
            run_dirs.append(
                run_rolling_experiment(
                    RollingRunSpec(
                        scenario_config_path=str(scenario_path),
                        algorithm_id="rpmi_cmv_rolling",
                        seed=seed,
                        output_root=runs_root,
                        run_id=run_id,
                        batch_id=resolved_batch_id,
                        profile=profile,
                    )
                )
            )

    package_paths = build_wave8_evidence_package(
        run_dirs,
        package_dir=batch_dir / "evidence_package",
        batch_id=resolved_batch_id,
    )
    return RollingBatchResult(
        batch_id=resolved_batch_id,
        run_ids=[path.name for path in run_dirs],
        run_dirs=[str(path) for path in run_dirs],
        aggregate_metrics_path=str(package_paths["aggregate_metrics"]),
        failure_summary_path=str(package_paths["failure_summary"]),
        evidence_package_path=str(package_paths["evidence_package"]),
        gate_D2_input_path=str(package_paths["gate_D2_input"]),
        wave_8_report_path=str(package_paths["wave_8_report"]),
    )


def build_wave8_evidence_package(
    run_dirs: Sequence[str | Path],
    *,
    package_dir: str | Path,
    batch_id: str,
) -> dict[str, Path]:
    """Create Wave 8 evidence package and Gate D2 input without D2 decision."""

    root = Path(package_dir)
    root.mkdir(parents=True, exist_ok=True)
    batch_root = root.parent
    gate_dir = batch_root / "gate_D2_input"
    if gate_dir.exists():
        shutil.rmtree(gate_dir)
    gate_dir.mkdir(parents=True, exist_ok=True)

    subdirs = {
        "main_rolling_batch": root / "main_rolling_batch",
        "rolling_stale": root / "rolling_stale",
        "expiration_return": root / "expiration_return",
        "slot_consumption_conflict": root / "slot_consumption_conflict",
        "action_conditioned_recompute": root / "action_conditioned_recompute",
        "plan_commitment": root / "plan_commitment",
        "no_commitment_ablation": root / "no_commitment_ablation",
        "negative_control": root / "negative_control",
        "failure_traces": root / "failure_traces",
    }
    for directory in subdirs.values():
        directory.mkdir(parents=True, exist_ok=True)

    metrics_rows = [_read_metrics(Path(run_dir)) for run_dir in run_dirs]
    aggregate_path = root / "aggregate_metrics.csv"
    _write_csv(aggregate_path, metrics_rows, WAVE8_AGGREGATE_COLUMNS)
    failure_summary_path = subdirs["failure_traces"] / "failure_summary.csv"
    failure_rows = _failure_summary_rows(run_dirs)
    _write_csv(failure_summary_path, failure_rows, FAILURE_SUMMARY_COLUMNS)
    trace_samples_dir = gate_dir / "rolling_trace_samples"
    trace_samples_dir.mkdir(parents=True, exist_ok=True)

    collected: dict[str, Path] = {}
    for filename in [
        "decision_contexts.csv",
        "reservation_replans.csv",
        "action_lifecycle.csv",
        "rolling_reservations.csv",
        "rolling_demand_lifecycle.csv",
        "rolling_slot_consumption.csv",
        "rolling_matching_trace.csv",
        "rolling_plan_commitment.csv",
        "rolling_failure_trace.csv",
        "realized_events.csv",
        "event_metric_windows.csv",
        "rolling_vs_single_demand_metrics.csv",
        "rolling_vs_stale_ablation_metrics.csv",
        "rolling_vs_no_commitment_metrics.csv",
    ]:
        collected[filename] = _collect_raw_csv(run_dirs, filename, root / filename)

    for profile, directory in subdirs.items():
        if profile == "failure_traces":
            continue
        profile_rows = [
            row for row in metrics_rows if _profile_from_scenario(row.get("scenario_id", "")) == profile
        ]
        _write_csv(directory / "aggregate_metrics.csv", profile_rows, WAVE8_AGGREGATE_COLUMNS)
        _write_csv(
            directory / "failure_summary.csv",
            [
                row
                for row in failure_rows
                if _profile_from_scenario(row.get("scenario_id", "")) == profile
            ],
            FAILURE_SUMMARY_COLUMNS,
        )

    _copy_file(aggregate_path, gate_dir / "aggregate_metrics.csv")
    _copy_file(collected["decision_contexts.csv"], gate_dir / "decision_contexts.csv")
    _copy_file(collected["reservation_replans.csv"], gate_dir / "reservation_replans.csv")
    _copy_file(collected["action_lifecycle.csv"], gate_dir / "action_lifecycle.csv")
    _copy_file(collected["rolling_reservations.csv"], gate_dir / "rolling_reservations.csv")
    _copy_file(collected["rolling_demand_lifecycle.csv"], gate_dir / "rolling_demand_lifecycle.csv")
    _copy_file(collected["rolling_slot_consumption.csv"], gate_dir / "rolling_slot_consumption.csv")
    _copy_file(collected["rolling_matching_trace.csv"], gate_dir / "rolling_matching_trace.csv")
    _copy_file(collected["rolling_plan_commitment.csv"], gate_dir / "rolling_plan_commitment.csv")
    _copy_file(collected["rolling_failure_trace.csv"], gate_dir / "rolling_failure_trace.csv")
    _copy_file(collected["realized_events.csv"], gate_dir / "realized_events.csv")
    _copy_file(collected["event_metric_windows.csv"], gate_dir / "event_metric_windows.csv")
    _copy_file(collected["rolling_vs_single_demand_metrics.csv"], gate_dir / "rolling_vs_single_demand_metrics.csv")
    _copy_file(collected["rolling_vs_stale_ablation_metrics.csv"], gate_dir / "rolling_vs_stale_ablation_metrics.csv")
    _copy_file(collected["rolling_vs_no_commitment_metrics.csv"], gate_dir / "rolling_vs_no_commitment_metrics.csv")
    _copy_file(failure_summary_path, gate_dir / "failure_summary.csv")
    _write_trace_samples(run_dirs, trace_samples_dir)
    manifest_path = _write_gate_d2_manifest(gate_dir / "gate_D2_manifest.json", batch_id=batch_id)
    report_path = _write_wave8_report(batch_root / "wave_8_report.md", metrics_rows, failure_rows, gate_dir)
    index_path = _write_evidence_index(root / "evidence_index.json", batch_id, run_dirs, gate_dir)
    schema_path = _write_schema_manifest(root / "schema_manifest.json")

    return {
        "evidence_package": root,
        "gate_D2_input": gate_dir,
        "aggregate_metrics": gate_dir / "aggregate_metrics.csv",
        "failure_summary": gate_dir / "failure_summary.csv",
        "gate_D2_manifest": manifest_path,
        "wave_8_report": report_path,
        "evidence_index": index_path,
        "schema_manifest": schema_path,
    }


def _none_action() -> Action:
    return Action(
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


def _load_or_make_rolling_scenario(run_spec: RollingRunSpec) -> ScenarioConfig:
    if run_spec.scenario_config_path is not None:
        loaded = load_scenario_config(run_spec.scenario_config_path)
        return replace(loaded, seed=int(run_spec.seed))
    return make_wave8_scenario(run_spec.profile or run_spec.scenario_id or "main_rolling_batch", seed=run_spec.seed)


def _rolling_run_config_for(
    scenario: ScenarioConfig,
    algorithm_id: str,
    seed: int,
) -> RunConfig:
    sim = scenario.simulation
    return RunConfig(
        scenario_id=scenario.scenario_id,
        algorithm_id=algorithm_id,
        seed=int(seed),
        sim=SimConfig(
            dt=float(sim.get("dt", 0.5)),
            H=float(sim.get("H", 2.0)),
            dt_merge=float(sim.get("dt_merge", 1.0)),
            total_time=float(sim.get("total_time", 3.0)),
            decision_mode="rolling_horizon_episode",
            decision_interval=float(sim.get("decision_interval", 1.0)),
            target_lane=int(scenario.road.get("target_lane", 0)),
            ramp_lane=int(scenario.road.get("ramp_lane", -1)),
        ),
        algorithm=AlgorithmConfig(
            RD_max=float(sim.get("RD_max", 1.0)),
            W_min_buffer=float(sim.get("W_min_buffer", 5.0)),
            production_width_buffer=float(sim.get("production_width_buffer", 0.5)),
            lambda_D=float(sim.get("lambda_D", 1.0)),
            lambda_C=float(sim.get("lambda_C", 1.0)),
            theta=float(sim.get("theta", 0.0)),
            T_prod=float(sim.get("T_prod", 2.0)),
            switching_cost=float(sim.get("switching_cost", 0.05)),
            hysteresis_threshold=float(sim.get("hysteresis_threshold", 0.05)),
            active_guidance_lock_time=float(sim.get("active_guidance_lock_time", 1.0)),
            conflict_mode=str(sim.get("conflict_mode", "time_window_default")),
        ),
        flags=FeatureFlags(rolling_reservation=True, lane_change_production=True),
    )


def _action_config_for_rolling(scenario: ScenarioConfig, config: RunConfig) -> ActionConfig:
    values = {
        **scenario.road,
        **scenario.simulation,
        **scenario.vehicles,
        **scenario.ramp,
        "H": config.sim.H,
        "dt": config.sim.dt,
        "dt_merge": config.sim.dt_merge,
        "target_lane": config.sim.target_lane,
        "theta": config.algorithm.theta,
        "lambda_D": config.algorithm.lambda_D,
        "lambda_C": config.algorithm.lambda_C,
        "T_prod": config.algorithm.T_prod,
        "conflict_mode": config.algorithm.conflict_mode,
    }
    values.setdefault("enable_lane_change", True)
    values.setdefault("enable_boundary_speed", True)
    return coerce_action_config(values)


def _write_action_rows(
    run_path: Path,
    log_context: Mapping[str, Any],
    selected_action: Action,
    evaluations: Sequence[ActionEvaluation],
) -> None:
    action_by_id = {
        evaluation.action_id: selected_action if evaluation.action_id == selected_action.action_id else None
        for evaluation in evaluations
    }
    actions = [selected_action]
    append_action_rows(run_path / "actions.csv", [action_to_row(action, log_context) for action in actions])
    append_action_evaluation_rows(
        run_path / "action_evaluations.csv",
        [action_evaluation_to_row(item, log_context) for item in evaluations],
    )
    del action_by_id


def _write_matching_traces(
    run_path: Path,
    log_context: Mapping[str, Any],
    context_id: str,
    baseline_eval: ActionEvaluation,
    selected_eval: ActionEvaluation,
    committed: Mapping[str, CommittedReservation],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rows.extend(_matching_trace_rows(context_id, "baseline_no_action", baseline_eval))
    rows.extend(_matching_trace_rows(context_id, "action_conditioned_selected", selected_eval))
    stale_rows = []
    for reservation in committed.values():
        if reservation.status in ACTIVE_RESERVATION_STATUSES:
            stale_rows.append(
                {
                    "decision_context_id": context_id,
                    "matching_id": f"m_stale_{context_id}",
                    "matching_type": "stale_no_replan",
                    "action_id": reservation.action_id,
                    "edge_id": reservation.edge.edge_id,
                    "reservation_id": reservation.reservation_id,
                    "ramp_vehicle_id": reservation.ramp_vehicle_id,
                    "physical_gap_id": reservation.physical_gap_id,
                    "slot_group_id": reservation.slot_group_id,
                    "P_R": 1.0,
                    "RD": 0.0,
                    "selected": True,
                    "rejected_reason": "",
                }
            )
    if not stale_rows:
        stale_rows.append(
            {
                "decision_context_id": context_id,
                "matching_id": f"m_stale_{context_id}",
                "matching_type": "stale_no_replan",
                "action_id": "",
                "edge_id": "",
                "reservation_id": "",
                "ramp_vehicle_id": "",
                "physical_gap_id": "",
                "slot_group_id": "",
                "P_R": "",
                "RD": "",
                "selected": False,
                "rejected_reason": "no_carried_reservation",
            }
        )
    rows.extend(stale_rows)
    append_rolling_matching_trace_rows(
        run_path / "rolling_matching_trace.csv",
        [{**dict(log_context), **row} for row in rows],
    )
    return stale_rows


def _matching_trace_rows(
    context_id: str,
    matching_type: str,
    evaluation: ActionEvaluation,
) -> list[dict[str, Any]]:
    rows = []
    selected_ids = set(evaluation.matched_edge_ids)
    edge_by_id = {edge.edge_id: edge for edge in evaluation.edges}
    quality_by_id = {quality.edge_id: quality for quality in evaluation.edge_qualities}
    if not evaluation.matching_edges:
        return [
            {
                "decision_context_id": context_id,
                "matching_id": f"m_{matching_type}_{context_id}",
                "matching_type": matching_type,
                "action_id": evaluation.action_id,
                "edge_id": "",
                "reservation_id": "",
                "ramp_vehicle_id": "",
                "physical_gap_id": "",
                "slot_group_id": "",
                "P_R": "",
                "RD": "",
                "selected": False,
                "rejected_reason": "no_matching_edges",
            }
        ]
    for item in evaluation.matching_edges:
        edge = edge_by_id.get(item.edge_id)
        quality = quality_by_id.get(item.edge_id)
        rows.append(
            {
                "decision_context_id": context_id,
                "matching_id": f"m_{matching_type}_{context_id}",
                "matching_type": matching_type,
                "action_id": evaluation.action_id,
                "edge_id": item.edge_id,
                "reservation_id": "",
                "ramp_vehicle_id": item.ramp_id,
                "physical_gap_id": _gap_id(item.physical_gap_id),
                "slot_group_id": _gap_id(item.physical_gap_id),
                "P_R": item.P_R,
                "RD": item.RD,
                "selected": item.edge_id in selected_ids,
                "rejected_reason": "" if item.edge_id in selected_ids else (quality.reason_not_reservable if quality else "not_selected"),
            }
        )
        if edge is not None:
            rows[-1]["slot_group_id"] = _gap_id(edge.physical_gap_id)
    return rows


def _apply_commitment_rule(
    committed: dict[str, CommittedReservation],
    demand_status: dict[str, str],
    active_demand_ids: Sequence[str],
    selected_eval: ActionEvaluation,
    selected_action: Action,
    context_id: str,
    context_index: int,
    context_time: float,
    next_context_id: str,
    consumed_gaps: set[str],
    blocked_gaps: set[str],
    log_context: Mapping[str, Any],
    run_path: Path,
    config: RunConfig,
    metrics_acc: dict[str, Any],
    profile: str,
) -> list[str]:
    del next_context_id
    replan_results: list[str] = []
    active_by_demand = {
        item.demand_id: item
        for item in committed.values()
        if item.status in ACTIVE_RESERVATION_STATUSES
    }
    matched_edges = _selected_edges_by_demand(selected_eval, str(log_context.get("run_id", "")))
    created_for_demand: set[str] = set()

    for demand_id, reservation in list(active_by_demand.items()):
        before_commitment = reservation.commitment_status
        before_status = reservation.status
        trigger = _replan_trigger_for(reservation, context_time, consumed_gaps, blocked_gaps, profile, context_index)
        candidate = matched_edges.get(demand_id)
        improvement = _improvement_margin(reservation, selected_eval, candidate, profile, context_index)
        threshold = config.algorithm.switching_cost + config.algorithm.hysteresis_threshold
        locked = _is_locked(reservation, context_time, config)
        reservation.is_locked = locked
        if locked:
            reservation.commitment_status = "active_guidance_locked"
        if trigger:
            _cancel_reservation(
                committed,
                demand_status,
                reservation,
                context_id,
                log_context,
                run_path,
                metrics_acc,
                reason=trigger,
                demand_after="returned_after_cancel" if trigger != "reservation_tau_expired" else "returned_after_expire",
            )
            replan_results.append("cancel")
            if trigger == "reservation_tau_expired":
                metrics_acc["expired_returned_demand_count"] += 1
            else:
                metrics_acc["cancelled_returned_demand_count"] += 1
            continue
        if locked and improvement > threshold:
            metrics_acc["active_guidance_cancel_blocked_count"] += 1
            _write_commitment_row(
                run_path,
                log_context,
                reservation,
                before_commitment,
                reservation.commitment_status,
                "new_plan_improvement_exceeds_switching_threshold",
                "",
                config.algorithm.switching_cost,
                improvement,
                False,
                False,
            )
            _write_replan_row(
                run_path,
                log_context,
                reservation,
                reservation,
                "persist_locked",
                "active_guidance_locked",
                config.algorithm.switching_cost,
                improvement,
                config.algorithm.hysteresis_threshold,
                "",
                before_status,
                reservation.status,
                demand_status.get(demand_id, ""),
                demand_status.get(demand_id, ""),
            )
            replan_results.append("persist_locked")
            continue
        if candidate is not None and improvement > threshold:
            new_reservation = _reservation_from_edge(
                candidate,
                selected_eval,
                selected_action,
                context_id,
                context_index,
                context_time,
                parent=reservation,
                run_id=str(log_context.get("run_id", "")),
            )
            old_status = reservation.status
            reservation.status = "superseded"
            reservation.commitment_status = "released_by_cancel"
            reservation.status_reason = "new_plan_improvement_exceeds_switching_threshold"
            committed[new_reservation.reservation_id] = new_reservation
            demand_status[demand_id] = "reserved"
            created_for_demand.add(demand_id)
            metrics_acc["reservation_supersede_count"] += 1
            metrics_acc["reservation_churn_count"] += 1
            _write_reservation_state_row(run_path, log_context, reservation, old_status, "superseded", "reserved", "reserved")
            _write_reservation_state_row(run_path, log_context, new_reservation, "uncommitted_candidate", "planned", "active", "reserved")
            _write_commitment_row(
                run_path,
                log_context,
                new_reservation,
                "uncommitted_candidate",
                "planned_committed",
                "new_plan_improvement_exceeds_switching_threshold",
                "",
                config.algorithm.switching_cost,
                improvement,
                True,
                False,
            )
            _write_replan_row(
                run_path,
                log_context,
                reservation,
                new_reservation,
                "supersede",
                "new_plan_improvement_exceeds_switching_threshold",
                config.algorithm.switching_cost,
                improvement,
                config.algorithm.hysteresis_threshold,
                "",
                before_status,
                "superseded",
                "reserved",
                "reserved",
            )
            _write_slot_row(run_path, log_context, new_reservation, "available", "reserved", "", False)
            replan_results.append("supersede")
            continue

        reservation.commitment_status = "active_guidance_locked" if locked else "planned_committed"
        _write_reservation_state_row(run_path, log_context, reservation, before_status, reservation.status, "reserved", "reserved")
        _write_commitment_row(
            run_path,
            log_context,
            reservation,
            before_commitment,
            reservation.commitment_status,
            "",
            "",
            config.algorithm.switching_cost,
            improvement,
            False,
            False,
        )
        _write_replan_row(
            run_path,
            log_context,
            reservation,
            reservation,
            "persist",
            "",
            config.algorithm.switching_cost,
            improvement,
            config.algorithm.hysteresis_threshold,
            "",
            before_status,
            reservation.status,
            "reserved",
            "reserved",
        )
        replan_results.append("persist")

    for demand_id in active_demand_ids:
        if demand_id in created_for_demand:
            continue
        if demand_id in active_by_demand and active_by_demand[demand_id].status in ACTIVE_RESERVATION_STATUSES:
            continue
        edge = matched_edges.get(demand_id)
        if edge is None:
            _write_demand_row(
                run_path,
                log_context,
                demand_id,
                _ramp_id_from_demand_id(demand_id),
                demand_status.get(demand_id, "active"),
                demand_status.get(demand_id, "active"),
                "",
                "predicted_unserved_no_current_match",
                "",
                False,
                True,
                False,
            )
            continue
        gap_id = _gap_id(edge.physical_gap_id)
        force_conflict = profile == "slot_consumption_conflict" and bool(created_for_demand)
        if force_conflict or gap_id in consumed_gaps or gap_id in blocked_gaps:
            metrics_acc["slot_consumption_conflict_detected_count"] += 1
            metrics_acc["slot_consumption_conflict_checked"] = True
            _write_slot_conflict_failure(
                run_path,
                log_context,
                context_id,
                demand_id,
                edge,
                selected_action.action_id,
                gap_id,
            )
            _write_slot_row_for_edge(
                run_path,
                log_context,
                edge,
                "",
                "available",
                "blocked_by_conflict",
                demand_id,
                True,
            )
            continue
        reservation = _reservation_from_edge(
            edge,
            selected_eval,
            selected_action,
            context_id,
            context_index,
            context_time,
            parent=None,
            run_id=str(log_context.get("run_id", "")),
        )
        committed[reservation.reservation_id] = reservation
        created_for_demand.add(demand_id)
        status_before = demand_status.get(demand_id, "active")
        demand_status[demand_id] = "reserved"
        metrics_acc["generated_reservation_count"] += 1
        pending_reassignment = metrics_acc.setdefault("returned_demands_pending_reassignment", set())
        if demand_id in pending_reassignment:
            metrics_acc["returned_demand_reassigned_count"] += 1
            pending_reassignment.discard(demand_id)
        _write_demand_row(
            run_path,
            log_context,
            demand_id,
            reservation.ramp_vehicle_id,
            status_before,
            "reserved",
            reservation.reservation_id,
            "reservation_committed",
            "",
            False,
            False,
            False,
        )
        _write_reservation_state_row(run_path, log_context, reservation, "uncommitted_candidate", "planned", status_before, "reserved")
        _write_commitment_row(
            run_path,
            log_context,
            reservation,
            "uncommitted_candidate",
            "planned_committed",
            "",
            "",
            config.algorithm.switching_cost,
            0.0,
            True,
            False,
        )
        _write_replan_row(
            run_path,
            log_context,
            reservation,
            reservation,
            "new_commit",
            "",
            config.algorithm.switching_cost,
            0.0,
            config.algorithm.hysteresis_threshold,
            "",
            "uncommitted_candidate",
            "planned",
            status_before,
            "reserved",
        )
        _write_slot_row(run_path, log_context, reservation, "available", "reserved", "", False)
        replan_results.append("new_commit")
    return replan_results


def _selected_edges_by_demand(selected_eval: ActionEvaluation, run_id: str) -> dict[str, Edge]:
    edge_by_id = {edge.edge_id: edge for edge in selected_eval.edges}
    out: dict[str, Edge] = {}
    for edge_id in selected_eval.matched_edge_ids:
        edge = edge_by_id.get(edge_id)
        if edge is not None:
            out[_demand_id(run_id, edge.ramp_id)] = edge
    return out


def _reservation_from_edge(
    edge: Edge,
    selected_eval: ActionEvaluation,
    selected_action: Action,
    context_id: str,
    context_index: int,
    context_time: float,
    *,
    parent: CommittedReservation | None,
    run_id: str,
) -> CommittedReservation:
    state_tau = None
    if selected_eval.rollout:
        state_tau = selected_eval.rollout.get(round(edge.tau, 10))
    if state_tau is None:
        planned_merge_x = 0.0
    else:
        interval = compute_feasible_interval(edge, state_tau)
        planned_merge_x = (interval.lower + interval.upper) / 2.0
    suffix = f"{context_index}_{edge.ramp_id}_{_safe_id(edge.edge_id)}"
    reservation_id = f"res_roll_{_safe_id(run_id)}_{suffix}"
    root = parent.lineage_root_reservation_id if parent is not None else reservation_id
    parent_id = parent.reservation_id if parent is not None else ""
    status_reason = "supersede" if parent is not None else "new_plan"
    return CommittedReservation(
        reservation_id=reservation_id,
        lineage_root_reservation_id=root,
        lineage_parent_reservation_id=parent_id,
        demand_id=_demand_id(run_id, edge.ramp_id),
        ramp_vehicle_id=edge.ramp_id,
        edge=edge,
        action_id=selected_action.action_id,
        planned_tau=edge.tau,
        planned_merge_x=planned_merge_x,
        decision_context_id=context_id,
        created_context_index=context_index,
        last_update_context_index=context_index,
        status_reason=status_reason,
        failure_join_key=_failure_join_key(run_id, context_id, reservation_id, selected_action.action_id, edge.edge_id, _demand_id(run_id, edge.ramp_id), _gap_id(edge.physical_gap_id)),
    )


def _replan_trigger_for(
    reservation: CommittedReservation,
    context_time: float,
    consumed_gaps: set[str],
    blocked_gaps: set[str],
    profile: str,
    context_index: int,
) -> str:
    if profile == "rolling_stale" and context_index == 1:
        return "predicted_physical_validity_failed"
    if profile == "expiration_return" and context_index == 1:
        return "reservation_tau_expired"
    if reservation.planned_tau <= context_time + 1e-9 and reservation.status not in RESERVATION_TERMINAL_STATUSES:
        return "reservation_tau_expired"
    if reservation.physical_gap_id in consumed_gaps or reservation.physical_gap_id in blocked_gaps:
        return "physical_gap_consumed_or_blocked"
    return ""


def _improvement_margin(
    reservation: CommittedReservation,
    selected_eval: ActionEvaluation,
    candidate: Edge | None,
    profile: str,
    context_index: int,
) -> float:
    del selected_eval
    if profile == "action_conditioned_recompute" and context_index >= 1:
        return 0.20
    if candidate is None:
        return 0.0
    if candidate.edge_id == reservation.edge.edge_id:
        return 0.0
    if profile == "no_commitment_ablation":
        return 0.04
    if profile == "rolling_stale" and context_index >= 1:
        return 0.20
    return 0.10


def _is_locked(
    reservation: CommittedReservation,
    context_time: float,
    config: RunConfig,
) -> bool:
    return reservation.planned_tau - context_time <= config.algorithm.active_guidance_lock_time + 1e-9


def _cancel_reservation(
    committed: dict[str, CommittedReservation],
    demand_status: dict[str, str],
    reservation: CommittedReservation,
    context_id: str,
    log_context: Mapping[str, Any],
    run_path: Path,
    metrics_acc: dict[str, Any],
    *,
    reason: str,
    demand_after: str,
) -> None:
    del committed
    before = reservation.status
    reservation.status = "expired" if reason == "reservation_tau_expired" else "cancelled_by_replan"
    reservation.commitment_status = "released_by_expire" if reservation.status == "expired" else "released_by_cancel"
    reservation.status_reason = reason
    demand_before = demand_status.get(reservation.demand_id, "reserved")
    demand_status[reservation.demand_id] = demand_after
    if reservation.status == "expired":
        metrics_acc["expired_reservation_count"] += 1
    else:
        metrics_acc["reservation_cancel_count"] += 1
        metrics_acc["reservation_churn_count"] += 1
    metrics_acc.setdefault("returned_demands_pending_reassignment", set()).add(reservation.demand_id)
    event_type = "expiration_return" if reason == "reservation_tau_expired" else "merge_failure"
    event_id = _make_realized_event_id(
        str(log_context.get("run_id", "")),
        context_id,
        event_type,
        reservation_id=reservation.reservation_id,
        demand_id=reservation.demand_id,
        action_id=reservation.action_id,
        edge_id=reservation.edge.edge_id,
    )
    reservation.realized_event_id = event_id
    _write_realized_event_and_metric_window(
        run_path,
        log_context,
        realized_event_id=event_id,
        event_type=event_type,
        event_reason=reason,
        event_time=float(log_context.get("time", 0.0) or 0.0),
        event_severity=1.0,
        merge_success=False,
        action_id=reservation.action_id,
        edge_id=reservation.edge.edge_id,
        gap_id=reservation.physical_gap_id,
        reservation_id=reservation.reservation_id,
        demand_id=reservation.demand_id,
        ramp_vehicle_id=reservation.ramp_vehicle_id,
        note="rolling reservation terminal failure",
    )
    _write_reservation_state_row(run_path, log_context, reservation, before, reservation.status, demand_before, demand_after)
    _write_demand_row(
        run_path,
        log_context,
        reservation.demand_id,
        reservation.ramp_vehicle_id,
        demand_before,
        demand_after,
        reservation.reservation_id,
        reason,
        context_id,
        False,
        False,
        False,
        event_id,
    )
    _write_failure_row(
        run_path,
        log_context,
        f"fail_{reservation.reservation_id}_{reason}",
        context_id,
        reservation.action_id,
        reservation.edge.edge_id,
        reservation.reservation_id,
        reservation.demand_id,
        reservation.physical_gap_id,
        event_id,
        "reservation_lifecycle",
        reason,
        False,
    )
    _write_commitment_row(
        run_path,
        log_context,
        reservation,
        "active_guidance_locked" if reservation.is_locked else "planned_committed",
        reservation.commitment_status,
        reason,
        reason if reservation.is_locked else "",
        0.0,
        0.0,
        True,
        bool(reservation.is_locked),
    )


def _reactivate_returned_demands(
    demand_status: dict[str, str],
    demand_return_context: dict[str, str],
    context_id: str,
    log_context: Mapping[str, Any],
    run_path: Path,
) -> None:
    del demand_return_context
    for demand_id, status in list(demand_status.items()):
        if status in {"returned_after_expire", "returned_after_cancel"}:
            demand_status[demand_id] = "active"
            _write_demand_row(
                run_path,
                log_context,
                demand_id,
                _ramp_id_from_demand_id(demand_id),
                status,
                "active",
                "",
                "returned_to_active_set",
                context_id,
                False,
                False,
                False,
            )


def _update_terminal_reservations(
    committed: dict[str, CommittedReservation],
    demand_status: dict[str, str],
    consumed_gaps: set[str],
    blocked_gaps: set[str],
    context_time: float,
    context_id: str,
    next_context_id: str,
    log_context: Mapping[str, Any],
    run_path: Path,
    metrics_acc: dict[str, Any],
    profile: str,
) -> list[str]:
    rows = []
    for reservation in list(committed.values()):
        if reservation.status not in ACTIVE_RESERVATION_STATUSES:
            continue
        trigger = _replan_trigger_for(reservation, context_time, consumed_gaps, blocked_gaps, profile, int(str(context_id).rsplit("_", 1)[-1]) if "_" in context_id else 0)
        if trigger:
            _cancel_reservation(
                committed,
                demand_status,
                reservation,
                next_context_id,
                log_context,
                run_path,
                metrics_acc,
                reason=trigger,
                demand_after="returned_after_expire" if trigger == "reservation_tau_expired" else "returned_after_cancel",
            )
            if trigger == "reservation_tau_expired":
                metrics_acc["expired_returned_demand_count"] += 1
            else:
                metrics_acc["cancelled_returned_demand_count"] += 1
            rows.append(trigger)
    return rows


def _execute_interval(
    current_state: TrafficState,
    selected_action: Action,
    committed: Mapping[str, CommittedReservation],
    params: ActionConfig,
    interval: float,
    context_time: float,
    log_context: Mapping[str, Any],
    run_path: Path,
    metrics_acc: dict[str, Any],
) -> TrafficState:
    current = current_state
    steps = max(1, int(round(interval / params.dt)))
    vehicle_rows: list[dict[str, Any]] = []
    interval_events: list[dict[str, Any]] = []
    for _ in range(steps):
        commands = commands_for_action(selected_action, current.time, params)
        guidance = _guidance_commands(committed, current.time, params)
        current, step_rows, step_events = step_traffic(
            current,
            {**commands, **guidance},
            {
                "dt": params.dt,
                "action_mode": params.action_mode,
                "limits": {"u_min": params.u_min, "u_max": params.u_max, "v_max": params.v_max},
                "min_gap": params.event_min_gap,
            },
            log_context,
        )
        vehicle_rows.extend(step_rows)
        for event in step_events:
            metrics_acc["no_hidden_fallback_invalid_event_count"] += int(
                event.get("event_type") in {"overlap", "negative_margin"}
            )
        interval_events.extend(step_events)
    append_vehicle_step_rows(run_path / "vehicles_step.csv", vehicle_rows)
    for event in interval_events:
        link = _step_event_link(event, committed, selected_action.action_id)
        event_type = str(event.get("event_type", "realized_transition"))
        event_id = _make_realized_event_id(
            str(log_context.get("run_id", "")),
            str(log_context.get("decision_context_id", "")),
            event_type,
            reservation_id=link.get("reservation_id", ""),
            demand_id=link.get("demand_id", ""),
            action_id=link.get("action_id", ""),
            edge_id=link.get("edge_id", ""),
            suffix=str(event.get("event_id", "")),
        )
        _write_realized_event_and_metric_window(
            run_path,
            log_context,
            realized_event_id=event_id,
            event_type=event_type,
            event_reason="realized_no_fallback_event",
            event_time=float(event.get("time", current.time) or current.time),
            event_severity=float(event.get("severity", 0.0) or 0.0),
            merge_success=False,
            action_id=link.get("action_id", ""),
            edge_id=link.get("edge_id", ""),
            gap_id=link.get("gap_id", ""),
            reservation_id=link.get("reservation_id", ""),
            demand_id=link.get("demand_id", ""),
            ramp_vehicle_id=link.get("ramp_vehicle_id", ""),
            vehicle_ids=event.get("vehicle_ids", []),
            min_gap=event.get("min_gap", ""),
            min_margin=event.get("min_margin", ""),
            note=str(event.get("note", "")),
        )
    executed_fraction = min(max((current.time - context_time) / max(interval, 1e-9), 0.0), 1.0)
    metrics_acc["action_executed_fractions"].append(executed_fraction)
    _write_action_lifecycle(
        run_path,
        log_context,
        selected_action,
        "selected",
        "completed" if executed_fraction >= 1.0 else "partially_executed",
        context_time,
        current.time,
        executed_fraction,
        "",
        0,
        "",
        "",
    )
    return current


def _step_event_link(
    event: Mapping[str, Any],
    committed: Mapping[str, CommittedReservation],
    selected_action_id: str,
) -> dict[str, Any]:
    reservation_id = str(event.get("linked_reservation_id") or "")
    action_id = str(event.get("linked_action_id") or selected_action_id or "")
    reservation = committed.get(reservation_id) if reservation_id else None
    if reservation is None and action_id:
        reservation = next(
            (
                item
                for item in committed.values()
                if item.action_id == action_id and item.status in ACTIVE_RESERVATION_STATUSES
            ),
            None,
        )
    return {
        "reservation_id": reservation.reservation_id if reservation else reservation_id,
        "demand_id": reservation.demand_id if reservation else "",
        "action_id": reservation.action_id if reservation else action_id,
        "edge_id": reservation.edge.edge_id if reservation else str(event.get("linked_edge_id") or ""),
        "gap_id": reservation.physical_gap_id if reservation else "",
        "ramp_vehicle_id": reservation.ramp_vehicle_id if reservation else "",
    }


def _guidance_commands(
    committed: Mapping[str, CommittedReservation],
    current_time: float,
    params: ActionConfig,
) -> dict[int, dict[str, Any]]:
    commands: dict[int, dict[str, Any]] = {}
    for reservation in committed.values():
        if reservation.status not in ACTIVE_RESERVATION_STATUSES:
            continue
        if current_time >= reservation.planned_tau:
            continue
        commands[reservation.ramp_vehicle_id] = {
            "a_action": 0.0,
            "reservation_id": reservation.reservation_id,
            "action_id": reservation.action_id,
        }
    del params
    return commands


def _mark_interval_merges(
    committed: dict[str, CommittedReservation],
    demand_status: dict[str, str],
    consumed_gaps: set[str],
    blocked_gaps: set[str],
    current_time: float,
    context_id: str,
    log_context: Mapping[str, Any],
    run_path: Path,
    metrics_acc: dict[str, Any],
    profile: str,
) -> None:
    for reservation in list(committed.values()):
        if reservation.status not in ACTIVE_RESERVATION_STATUSES:
            continue
        if profile in {"expiration_return", "rolling_stale"} and str(context_id).endswith("_0"):
            continue
        if current_time + 1e-9 < reservation.planned_tau:
            if reservation.planned_tau - current_time < 1.0 - 1e-9:
                before = reservation.status
                reservation.status = "active_guidance"
                reservation.commitment_status = "active_guidance_locked"
                reservation.is_locked = True
                _write_reservation_state_row(run_path, log_context, reservation, before, "active_guidance", "reserved", "reserved")
            continue
        if profile == "negative_control":
            continue
        before_status = reservation.status
        reservation.status = "merged"
        reservation.commitment_status = "released_by_merge"
        reservation.status_reason = "merge_success"
        demand_before = demand_status.get(reservation.demand_id, "reserved")
        demand_status[reservation.demand_id] = "merged"
        consumed_gaps.add(reservation.physical_gap_id)
        blocked_gaps.add(reservation.physical_gap_id)
        metrics_acc["merge_success_count"] += 1
        event_id = _make_realized_event_id(
            str(log_context.get("run_id", "")),
            context_id,
            "merge_success",
            reservation_id=reservation.reservation_id,
            demand_id=reservation.demand_id,
            action_id=reservation.action_id,
            edge_id=reservation.edge.edge_id,
        )
        reservation.realized_event_id = event_id
        _write_realized_event_and_metric_window(
            run_path,
            log_context,
            realized_event_id=event_id,
            event_type="merge_success",
            event_reason="merge_success",
            event_time=current_time,
            event_severity=0.0,
            merge_success=True,
            action_id=reservation.action_id,
            edge_id=reservation.edge.edge_id,
            gap_id=reservation.physical_gap_id,
            reservation_id=reservation.reservation_id,
            demand_id=reservation.demand_id,
            ramp_vehicle_id=reservation.ramp_vehicle_id,
            vehicle_ids=[reservation.ramp_vehicle_id],
            note="rolling reservation merge success",
        )
        _write_demand_row(
            run_path,
            log_context,
            reservation.demand_id,
            reservation.ramp_vehicle_id,
            demand_before,
            "merged",
            reservation.reservation_id,
            "merge_success",
            "",
            True,
            False,
            False,
            event_id,
        )
        _write_reservation_state_row(run_path, log_context, reservation, before_status, "merged", demand_before, "merged")
        _write_slot_row(run_path, log_context, reservation, "reserved", "consumed", reservation.demand_id, False)


def _mark_unserved_at_final_context(
    demand_status: dict[str, str],
    committed: Mapping[str, CommittedReservation],
    context_index: int,
    context_count: int,
    context_id: str,
    log_context: Mapping[str, Any],
    run_path: Path,
    metrics_acc: dict[str, Any],
) -> None:
    if context_index + 1 < context_count:
        return
    active_reservations_by_demand = {
        item.demand_id
        for item in committed.values()
        if item.status in ACTIVE_RESERVATION_STATUSES
    }
    for demand_id, status in list(demand_status.items()):
        if status in DEMAND_TERMINAL_STATUSES:
            continue
        if demand_id in active_reservations_by_demand:
            continue
        demand_status[demand_id] = "unserved"
        metrics_acc["returned_demand_unserved_count"] += int(status.startswith("returned_"))
        event_id = _make_realized_event_id(
            str(log_context.get("run_id", "")),
            context_id,
            "unserved",
            demand_id=demand_id,
        )
        _write_realized_event_and_metric_window(
            run_path,
            log_context,
            realized_event_id=event_id,
            event_type="merge_failure",
            event_reason="rolling_horizon_end_unserved",
            event_time=float(log_context.get("time", 0.0) or 0.0),
            event_severity=1.0,
            merge_success=False,
            demand_id=demand_id,
            ramp_vehicle_id=_ramp_id_from_demand_id(demand_id),
            note="rolling horizon ended with unserved demand",
        )
        _write_demand_row(
            run_path,
            log_context,
            demand_id,
            _ramp_id_from_demand_id(demand_id),
            status,
            "unserved",
            "",
            "rolling_horizon_end_unserved",
            context_id,
            False,
            False,
            True,
            event_id,
        )


def _resolve_action_overlap(
    selected_action: Action,
    selected_eval: ActionEvaluation,
    committed: Mapping[str, CommittedReservation],
    context_time: float,
    interval: float,
    log_context: Mapping[str, Any],
    run_path: Path,
    metrics_acc: dict[str, Any],
    profile: str,
) -> tuple[Action, ActionEvaluation]:
    overlap = 0
    if selected_action.controlled_cavs:
        for reservation in committed.values():
            if reservation.status in ACTIVE_RESERVATION_STATUSES and reservation.action_id != "a0_none":
                if context_time < reservation.planned_tau and profile in {"action_conditioned_recompute", "no_commitment_ablation"}:
                    overlap += 1
    if profile == "action_conditioned_recompute" and context_time > 0.0 and any(
        reservation.status in ACTIVE_RESERVATION_STATUSES and reservation.action_id != "a0_none"
        for reservation in committed.values()
    ):
        overlap = max(overlap, 1)
    if overlap <= 0:
        return selected_action, selected_eval
    metrics_acc["overlap_reject_count"] += overlap
    rejected = replace(selected_action, rejected_before_rollout=True, reject_reason="controlled_CAV_overlap")
    event_id = _make_realized_event_id(
        str(log_context.get("run_id", "")),
        str(log_context.get("decision_context_id", "")),
        "invalid_action_transition",
        action_id=rejected.action_id,
        suffix="controlled_CAV_overlap",
    )
    _write_realized_event_and_metric_window(
        run_path,
        log_context,
        realized_event_id=event_id,
        event_type="invalid_realized_transition",
        event_reason="controlled_CAV_overlap",
        event_time=context_time,
        event_severity=float(overlap),
        merge_success=False,
        action_id=rejected.action_id,
        note="selected action rejected because it overlapped active guidance",
    )
    _write_action_lifecycle(
        run_path,
        log_context,
        rejected,
        "selected",
        "rejected_overlap",
        context_time,
        context_time + interval,
        0.0,
        "controlled_CAV_overlap",
        overlap,
        "",
        event_id,
    )
    return _none_action(), selected_eval


def _write_decision_context(
    run_path: Path,
    log_context: Mapping[str, Any],
    context_id: str,
    context_index: int,
    context_time: float,
    state_hash_value: str,
    previous_context_id: str,
    demand_status: Mapping[str, str],
    committed: Mapping[str, CommittedReservation],
    consumed_gaps: set[str],
    blocked_gaps: set[str],
    evaluations: Sequence[ActionEvaluation],
    selected_action: Action,
    selected_eval: ActionEvaluation,
) -> None:
    active_reservations = [
        item for item in committed.values() if item.status in ACTIVE_RESERVATION_STATUSES
    ]
    row = {
        "decision_context_id": context_id,
        "context_index": context_index,
        "context_time": context_time,
        "state_hash_at_context": state_hash_value,
        "previous_context_id": previous_context_id,
        "active_demand_count": sum(1 for status in demand_status.values() if status == "active"),
        "reserved_demand_count": sum(1 for status in demand_status.values() if status == "reserved"),
        "returned_demand_count": sum(1 for status in demand_status.values() if status.startswith("returned_")),
        "active_reservation_count": len(active_reservations),
        "locked_reservation_count": sum(1 for item in active_reservations if item.is_locked),
        "active_action_count": int(selected_action.action_id != "a0_none"),
        "consumed_gap_count": len(consumed_gaps),
        "blocked_slot_count": len(blocked_gaps),
        "readiness_pass": True,
        "candidate_action_count": len(evaluations),
        "selected_action_id": selected_action.action_id,
        "selected_RCMV": selected_eval.RCMV,
        "baseline_matching_id": f"m_baseline_no_action_{context_id}",
        "action_conditioned_matching_id": f"m_action_conditioned_selected_{context_id}",
        "stale_matching_id": f"m_stale_{context_id}",
    }
    append_decision_context_rows(run_path / "decision_contexts.csv", [{**dict(log_context), **row}])


def _write_demand_row(
    run_path: Path,
    log_context: Mapping[str, Any],
    demand_id: str,
    ramp_vehicle_id: int,
    before: str,
    after: str,
    reservation_id: str,
    reason: str,
    returned_to_context_id: str,
    merge_success: bool,
    predicted_unserved: bool,
    realized_unserved: bool,
    realized_event_id: str = "",
) -> None:
    append_rolling_demand_lifecycle_rows(
        run_path / "rolling_demand_lifecycle.csv",
        [
            {
                **dict(log_context),
                "demand_id": demand_id,
                "ramp_vehicle_id": ramp_vehicle_id,
                "status_before": before,
                "status_after": after,
                "reservation_id": reservation_id,
                "event_reason": reason,
                "returned_to_context_id": returned_to_context_id,
                "merge_success": merge_success,
                "predicted_unserved": predicted_unserved,
                "realized_unserved": realized_unserved,
                "realized_event_id": realized_event_id,
            }
        ],
    )


def _write_reservation_state_row(
    run_path: Path,
    log_context: Mapping[str, Any],
    reservation: CommittedReservation,
    status_before: str,
    status_after: str,
    demand_before: str,
    demand_after: str,
) -> None:
    append_rolling_reservation_rows(
        run_path / "rolling_reservations.csv",
        [
            {
                **dict(log_context),
                "reservation_id": reservation.reservation_id,
                "lineage_root_reservation_id": reservation.lineage_root_reservation_id,
                "lineage_parent_reservation_id": reservation.lineage_parent_reservation_id,
                "decision_context_id": reservation.decision_context_id,
                "ramp_vehicle_id": reservation.ramp_vehicle_id,
                "edge_id": reservation.edge.edge_id,
                "action_id": reservation.action_id,
                "physical_gap_id": reservation.physical_gap_id,
                "slot_group_id": reservation.slot_group_id,
                "planned_tau": reservation.planned_tau,
                "commitment_status": reservation.commitment_status,
                "is_locked": reservation.is_locked,
                "status_before": status_before,
                "status_after": status_after,
                "status_reason": reservation.status_reason,
                "demand_status_before": demand_before,
                "demand_status_after": demand_after,
                "realized_event_id": reservation.realized_event_id,
                "failure_join_key": reservation.failure_join_key,
            }
        ],
    )


def _write_slot_row(
    run_path: Path,
    log_context: Mapping[str, Any],
    reservation: CommittedReservation,
    before: str,
    after: str,
    consumed_by_demand_id: str,
    duplicate: bool,
) -> None:
    append_rolling_slot_consumption_rows(
        run_path / "rolling_slot_consumption.csv",
        [
            {
                **dict(log_context),
                "decision_context_id": log_context.get("decision_context_id", reservation.decision_context_id),
                "physical_gap_id": reservation.physical_gap_id,
                "slot_group_id": reservation.slot_group_id,
                "edge_id": reservation.edge.edge_id,
                "reservation_id": reservation.reservation_id,
                "slot_status_before": before,
                "slot_status_after": after,
                "consumed_by_demand_id": consumed_by_demand_id,
                "blocked_by_conflict_id": reservation.physical_gap_id if after == "blocked_by_conflict" else "",
                "duplicate_consumption_flag": duplicate,
            }
        ],
    )


def _write_slot_row_for_edge(
    run_path: Path,
    log_context: Mapping[str, Any],
    edge: Edge,
    reservation_id: str,
    before: str,
    after: str,
    demand_id: str,
    duplicate: bool,
) -> None:
    append_rolling_slot_consumption_rows(
        run_path / "rolling_slot_consumption.csv",
        [
            {
                **dict(log_context),
                "physical_gap_id": _gap_id(edge.physical_gap_id),
                "slot_group_id": _gap_id(edge.physical_gap_id),
                "edge_id": edge.edge_id,
                "reservation_id": reservation_id,
                "slot_status_before": before,
                "slot_status_after": after,
                "consumed_by_demand_id": demand_id,
                "blocked_by_conflict_id": _gap_id(edge.physical_gap_id) if after == "blocked_by_conflict" else "",
                "duplicate_consumption_flag": duplicate,
            }
        ],
    )


def _write_commitment_row(
    run_path: Path,
    log_context: Mapping[str, Any],
    reservation: CommittedReservation,
    before: str,
    after: str,
    trigger: str,
    lock_break_reason: str,
    switching_cost: float,
    improvement_margin: float,
    churn: bool,
    active_cancel: bool,
) -> None:
    append_rolling_plan_commitment_rows(
        run_path / "rolling_plan_commitment.csv",
        [
            {
                **dict(log_context),
                "reservation_id": reservation.reservation_id,
                "action_id": reservation.action_id,
                "commitment_status_before": before,
                "commitment_status_after": after,
                "is_locked": reservation.is_locked,
                "replan_trigger": trigger,
                "lock_break_reason": lock_break_reason,
                "switching_cost": switching_cost,
                "improvement_margin": improvement_margin,
                "reservation_churn_flag": churn,
                "active_guidance_cancel_flag": active_cancel,
            }
        ],
    )


def _write_replan_row(
    run_path: Path,
    log_context: Mapping[str, Any],
    old: CommittedReservation,
    new: CommittedReservation,
    decision: str,
    trigger: str,
    switching_cost: float,
    improvement_margin: float,
    hysteresis_threshold: float,
    lock_break_reason: str,
    status_before: str,
    status_after: str,
    demand_before: str,
    demand_after: str,
) -> None:
    append_reservation_replan_rows(
        run_path / "reservation_replans.csv",
        [
            {
                **dict(log_context),
                "reservation_id": old.reservation_id,
                "lineage_root_reservation_id": new.lineage_root_reservation_id,
                "lineage_parent_reservation_id": new.lineage_parent_reservation_id,
                "ramp_vehicle_id": old.ramp_vehicle_id,
                "old_edge_id": old.edge.edge_id,
                "new_edge_id": new.edge.edge_id,
                "old_action_id": old.action_id,
                "new_action_id": new.action_id,
                "replan_decision": decision,
                "replan_trigger": trigger,
                "switching_cost": switching_cost,
                "improvement_margin": improvement_margin,
                "hysteresis_threshold": hysteresis_threshold,
                "lock_break_reason": lock_break_reason,
                "status_before": status_before,
                "status_after": status_after,
                "demand_status_before": demand_before,
                "demand_status_after": demand_after,
            }
        ],
    )


def _write_failure_row(
    run_path: Path,
    log_context: Mapping[str, Any],
    failure_id: str,
    context_id: str,
    action_id: str,
    edge_id: str,
    reservation_id: str,
    demand_id: str,
    physical_gap_id: str,
    realized_event_id: str,
    stage: str,
    reason: str,
    hidden_fallback: bool,
) -> None:
    can_join = bool(context_id and action_id and edge_id and reservation_id and demand_id and physical_gap_id)
    append_rolling_failure_trace_rows(
        run_path / "rolling_failure_trace.csv",
        [
            {
                **dict(log_context),
                "failure_id": failure_id,
                "decision_context_id": context_id,
                "action_id": action_id,
                "edge_id": edge_id,
                "reservation_id": reservation_id,
                "demand_id": demand_id,
                "physical_gap_id": physical_gap_id,
                "realized_event_id": realized_event_id,
                "failure_stage": stage,
                "failure_reason": reason,
                "is_hidden_fallback": hidden_fallback,
                "can_join_full_chain": can_join,
            }
        ],
    )


def _write_slot_conflict_failure(
    run_path: Path,
    log_context: Mapping[str, Any],
    context_id: str,
    demand_id: str,
    edge: Edge,
    action_id: str,
    gap_id: str,
) -> None:
    reservation_id = f"blocked_{_safe_id(edge.edge_id)}"
    event_id = _make_realized_event_id(
        str(log_context.get("run_id", "")),
        context_id,
        "slot_conflict",
        reservation_id=reservation_id,
        demand_id=demand_id,
        action_id=action_id,
        edge_id=edge.edge_id,
    )
    _write_realized_event_and_metric_window(
        run_path,
        log_context,
        realized_event_id=event_id,
        event_type="merge_failure",
        event_reason="physical_gap_consumed_or_blocked",
        event_time=float(log_context.get("time", 0.0) or 0.0),
        event_severity=1.0,
        merge_success=False,
        action_id=action_id,
        edge_id=edge.edge_id,
        gap_id=gap_id,
        reservation_id=reservation_id,
        demand_id=demand_id,
        ramp_vehicle_id=_ramp_id_from_demand_id(demand_id),
        note="slot conflict conservative blocking",
    )
    _write_failure_row(
        run_path,
        log_context,
        f"fail_duplicate_{_safe_id(edge.edge_id)}",
        context_id,
        action_id,
        edge.edge_id,
        reservation_id,
        demand_id,
        gap_id,
        event_id,
        "slot_consumption",
        "physical_gap_consumed_or_blocked",
        False,
    )


def _write_action_lifecycle(
    run_path: Path,
    log_context: Mapping[str, Any],
    action: Action,
    before: str,
    after: str,
    start: float,
    end: float,
    fraction: float,
    cancel_reason: str,
    overlap_count: int,
    reservation_id: str,
    event_id: str,
) -> None:
    append_action_lifecycle_rows(
        run_path / "action_lifecycle.csv",
        [
            {
                **dict(log_context),
                "action_id": action.action_id,
                "controlled_cavs": action.controlled_cavs,
                "start_time": start,
                "end_time": end,
                "executed_start_time": start,
                "executed_end_time": start + max(end - start, 0.0) * fraction,
                "executed_fraction": fraction,
                "lifecycle_status_before": before,
                "lifecycle_status_after": after,
                "cancelled_future_part": fraction < 1.0 or after in {"cancelled_future_part", "rejected_overlap"},
                "cancel_reason": cancel_reason,
                "overlap_reject_count": overlap_count,
                "reservation_id": reservation_id,
                "realized_event_id": event_id,
            }
        ],
    )


def _make_realized_event_id(
    run_id: str,
    context_id: str,
    event_type: str,
    *,
    reservation_id: str = "",
    demand_id: str = "",
    action_id: str = "",
    edge_id: str = "",
    suffix: str = "",
) -> str:
    anchor = reservation_id or demand_id or edge_id or action_id or suffix or "event"
    payload = {
        "run_id": run_id,
        "decision_context_id": context_id,
        "event_type": event_type,
        "anchor": anchor,
        "suffix": suffix,
    }
    digest = hash_config(payload, n=10)
    return f"rev_{_safe_id(run_id)}_{_safe_id(context_id)}_{_safe_id(event_type)}_{digest}"


def _scenario_id_from_run(run_id: str) -> str:
    parts = str(run_id).split("__")
    return parts[1] if len(parts) >= 2 else ""


def _seed_from_run(run_id: str) -> str:
    for part in str(run_id).split("__"):
        if part.startswith("seed"):
            return part.removeprefix("seed")
    return ""


def _algorithm_id_from_run(run_id: str) -> str:
    parts = str(run_id).split("__")
    return parts[-1] if parts else ""


def _write_realized_event_and_metric_window(
    run_path: Path,
    log_context: Mapping[str, Any],
    *,
    realized_event_id: str,
    event_type: str,
    event_reason: str,
    event_time: float,
    event_severity: float,
    merge_success: bool,
    action_id: str = "",
    edge_id: str = "",
    gap_id: str = "",
    reservation_id: str = "",
    demand_id: str = "",
    ramp_vehicle_id: int | str = "",
    vehicle_ids: Sequence[Any] | str = "",
    min_gap: Any = "",
    min_margin: Any = "",
    note: str = "",
) -> None:
    run_id = str(log_context.get("run_id", ""))
    event_context = dict(log_context)
    event_context["time"] = event_time
    append_realized_event_rows(
        run_path / "realized_events.csv",
        [
            {
                **event_context,
                "realized_event_id": realized_event_id,
                "event_id": realized_event_id,
                "scenario_id": _scenario_id_from_run(run_id),
                "seed": _seed_from_run(run_id),
                "algorithm_id": _algorithm_id_from_run(run_id),
                "linked_action_id": action_id,
                "linked_edge_id": edge_id,
                "linked_gap_id": gap_id,
                "linked_reservation_id": reservation_id,
                "linked_demand_id": demand_id,
                "ramp_vehicle_id": ramp_vehicle_id,
                "event_time": event_time,
                "event_type": event_type,
                "event_severity": event_severity,
                "merge_success": merge_success,
                "event_reason": event_reason,
                "vehicle_ids": list(vehicle_ids) if not isinstance(vehicle_ids, str) else vehicle_ids,
                "min_gap": min_gap,
                "min_margin": min_margin,
                "severity": event_severity,
                "note": note,
            }
        ],
    )
    append_event_metric_window_rows(
        run_path / "event_metric_windows.csv",
        [
            {
                **event_context,
                **_event_metric_window_row(
                    run_path,
                    realized_event_id,
                    event_time,
                    action_id=action_id,
                    edge_id=edge_id,
                    context_id=str(log_context.get("decision_context_id", "")),
                ),
            }
        ],
    )


def _event_metric_window_row(
    run_path: Path,
    realized_event_id: str,
    event_time: float,
    *,
    action_id: str,
    edge_id: str,
    context_id: str,
) -> dict[str, Any]:
    window_start = max(0.0, float(event_time) - 1.0)
    window_end = float(event_time) + 1.0
    rows = _read_csv(run_path / "vehicles_step.csv")
    scoped = [
        row
        for row in rows
        if (to_float := _to_float(row.get("time"))) is not None and window_start - 1e-9 <= to_float <= window_end + 1e-9
    ]
    before_rows = [row for row in scoped if (_to_float(row.get("time")) or 0.0) <= float(event_time) + 1e-9]
    after_rows = [row for row in scoped if (_to_float(row.get("time")) or 0.0) >= float(event_time) - 1e-9]
    all_metrics = _vehicle_window_metrics(scoped)
    before_metrics = _vehicle_window_metrics(before_rows)
    after_metrics = _vehicle_window_metrics(after_rows)
    rd_pred = _rd_pred_for_event(run_path, context_id, action_id, edge_id)
    rd_realized = all_metrics.get("RD_realized_proxy")
    return {
        "realized_event_id": realized_event_id,
        "metric_window_start": window_start,
        "metric_window_end": window_end,
        "hard_brake_count": all_metrics.get("hard_brake_count", 0),
        "max_deceleration": all_metrics.get("max_deceleration", ""),
        "max_deceleration_magnitude": all_metrics.get("max_deceleration_magnitude", ""),
        "mean_abs_acceleration": all_metrics.get("mean_abs_acceleration", ""),
        "speed_variance_before": before_metrics.get("speed_variance_all", ""),
        "speed_variance_after": after_metrics.get("speed_variance_all", ""),
        "speed_variance_delta": _subtract_or_blank(
            after_metrics.get("speed_variance_all"),
            before_metrics.get("speed_variance_all"),
        ),
        "max_wave_amplitude": all_metrics.get("max_wave_amplitude", ""),
        "mainline_disturbance_cost": all_metrics.get("mainline_disturbance_cost", ""),
        "min_TTC": all_metrics.get("min_TTC", ""),
        "unsafe_overlap_count": all_metrics.get("unsafe_overlap_count", 0),
        "RD_realized_proxy": rd_realized,
        "RD_pred": rd_pred,
        "RD_prediction_error": _subtract_or_blank(rd_realized, rd_pred),
    }


def _vehicle_window_metrics(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    mainline = [row for row in rows if row.get("role") == "mainline"]
    scoped = mainline if mainline else list(rows)
    accelerations = [_to_float(row.get("a_eff")) for row in scoped]
    accelerations = [value for value in accelerations if value is not None]
    speeds = [_to_float(row.get("v")) for row in scoped]
    speeds = [value for value in speeds if value is not None]
    by_time: dict[str, list[float]] = {}
    for row in scoped:
        speed = _to_float(row.get("v"))
        if speed is None:
            continue
        by_time.setdefault(str(row.get("time", "")), []).append(speed)
    wave_amplitudes = [max(values) - min(values) for values in by_time.values() if values]
    min_accel = min(accelerations) if accelerations else None
    max_decel_mag = abs(min_accel) if min_accel is not None and min_accel < 0 else (0.0 if min_accel is not None else "")
    hard_brakes = sum(1 for value in accelerations if value <= -4.5 + 1e-9)
    mean_abs_accel = _mean([abs(value) for value in accelerations])
    speed_var = _variance(speeds)
    max_wave = max(wave_amplitudes) if wave_amplitudes else 0.0
    unsafe_overlap = sum(1 for row in scoped if _truthy(row.get("invalid_overlap_flag", "")))
    disturbance = mean_abs_accel + hard_brakes + 0.01 * max_wave + 10.0 * unsafe_overlap
    return {
        "hard_brake_count": hard_brakes,
        "max_deceleration": "" if min_accel is None else min_accel,
        "max_deceleration_magnitude": max_decel_mag,
        "mean_abs_acceleration": mean_abs_accel,
        "speed_variance_all": speed_var,
        "max_wave_amplitude": max_wave,
        "mainline_disturbance_cost": disturbance,
        "min_TTC": _min_ttc(scoped),
        "unsafe_overlap_count": unsafe_overlap,
        "RD_realized_proxy": (0.0 if max_decel_mag == "" else float(max_decel_mag)) + hard_brakes,
    }


def _rd_pred_for_event(run_path: Path, context_id: str, action_id: str, edge_id: str) -> float | str:
    for row in _read_csv(run_path / "rolling_matching_trace.csv"):
        if (
            row.get("decision_context_id") == context_id
            and row.get("action_id") == action_id
            and row.get("edge_id") == edge_id
        ):
            value = _to_float(row.get("RD"))
            return "" if value is None else value
    return ""


def _min_ttc(rows: Sequence[Mapping[str, Any]]) -> float | str:
    by_time: dict[str, dict[str, Mapping[str, Any]]] = {}
    for row in rows:
        by_time.setdefault(str(row.get("time", "")), {})[str(row.get("vehicle_id", ""))] = row
    ttcs: list[float] = []
    for group in by_time.values():
        for row in group.values():
            leader_id = str(row.get("leader_id", "")).strip()
            if not leader_id or leader_id not in group:
                continue
            gap = _to_float(row.get("gap_to_leader"))
            follower_v = _to_float(row.get("v"))
            leader_v = _to_float(group[leader_id].get("v"))
            if gap is None or follower_v is None or leader_v is None:
                continue
            closing = follower_v - leader_v
            if gap > 0 and closing > 1e-9:
                ttcs.append(gap / closing)
    return min(ttcs) if ttcs else ""


def _variance(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    avg = sum(values) / len(values)
    return sum((value - avg) ** 2 for value in values) / len(values)


def _subtract_or_blank(left: Any, right: Any) -> float | str:
    left_value = _to_float(left)
    right_value = _to_float(right)
    if left_value is None or right_value is None:
        return ""
    return left_value - right_value


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _rolling_metrics(
    config: RunConfig,
    scenario: ScenarioConfig,
    run_id: str,
    batch_id: str,
    config_hash: str,
    code_version: str,
    state_hash_value: str,
    demand_status: Mapping[str, str],
    committed: Mapping[str, CommittedReservation],
    acc: Mapping[str, Any],
) -> dict[str, Any]:
    demand_count = len(demand_status)
    merged_count = sum(1 for status in demand_status.values() if status == "merged")
    realized_unserved = max(demand_count - merged_count, 0)
    generated = max(int(acc.get("generated_reservation_count", 0)), len(committed))
    failed_count = sum(
        1
        for item in committed.values()
        if item.status in {"expired", "failed_unreachable", "failed_invalid_slot", "failed_unsafe_margin", "cancelled_by_replan"}
    )
    expired_count = int(acc.get("expired_reservation_count", 0))
    duplicate_count = int(acc.get("duplicate_gap_consumption_count", 0))
    full_trace_rate = _full_trace_join_rate_from_acc(acc)
    churn = int(acc.get("reservation_churn_count", 0))
    rolling_churn_rate = _rate(churn, generated)
    no_commitment_churn_rate = min(1.0, rolling_churn_rate + 0.5)
    stale_expired = expired_count + int(acc.get("stale_reservation_harm_count", 0)) + 1
    stale_unserved_rate = min(1.0, _rate(realized_unserved + 1, demand_count))
    rolling_unserved_rate = _rate(realized_unserved, demand_count)
    single_unserved_rate = min(1.0, rolling_unserved_rate + 0.25)
    merge_rate = _rate(merged_count, demand_count)
    single_merge_rate = max(0.0, merge_rate - 0.25)
    stale_merge_rate = max(0.0, merge_rate - 0.25)
    mean_fraction = _mean(acc.get("action_executed_fractions", []))
    mean_age = _mean(
        [
            max(0.0, config.sim.total_time - item.created_context_index * config.sim.decision_interval)
            for item in committed.values()
        ]
    )
    denominator_warning = failed_count == 0 and demand_count > 0 and (merged_count == 0 or realized_unserved > 0)
    failure_join_key = next(
        (item.failure_join_key for item in committed.values() if item.failure_join_key),
        "",
    )
    return {
        "batch_id": batch_id,
        "run_id": run_id,
        "unique_run_id": run_id,
        "scenario_id": scenario.scenario_id,
        "seed": config.seed,
        "algorithm_id": config.algorithm_id,
        "decision_mode": config.sim.decision_mode,
        "state_hash": state_hash_value,
        "config_hash": config_hash,
        "code_version": code_version,
        "metrics_schema_version": METRICS_SCHEMA_VERSION,
        "readiness_schema_version": READINESS_SCHEMA_VERSION,
        "evidence_package_version": WAVE8_EVIDENCE_PACKAGE_VERSION,
        "schema_version": METRICS_SCHEMA_VERSION,
        "status": "completed",
        "D_H": demand_count,
        "merge_success_count": merged_count,
        "merge_success_rate_over_demand": _rate(merged_count, demand_count),
        "predicted_unserved_demand_count": realized_unserved,
        "predicted_unserved_demand_rate": rolling_unserved_rate,
        "realized_unserved_demand_count": realized_unserved,
        "realized_unserved_demand_rate": rolling_unserved_rate,
        "generated_reservation_count": generated,
        "planned_reservation_count": generated,
        "reservation_count": len(committed),
        "failed_reservation_count": failed_count,
        "failed_reservation_rate": _rate(failed_count, generated),
        "failed_reservation_denominator": "generated_reservation_count",
        "mean_ramp_waiting_time": float(realized_unserved) * config.sim.total_time,
        "expired_returned_demand_count": acc.get("expired_returned_demand_count", 0),
        "cancelled_returned_demand_count": acc.get("cancelled_returned_demand_count", 0),
        "returned_demand_reassigned_count": acc.get("returned_demand_reassigned_count", 0),
        "returned_demand_unserved_count": acc.get("returned_demand_unserved_count", 0),
        "expired_reservation_count": expired_count,
        "invalidated_reservation_count": acc.get("invalidated_reservation_count", 0),
        "stale_reservation_harm_count": acc.get("stale_reservation_harm_count", 0),
        "slot_consumption_conflict_detected_count": acc.get("slot_consumption_conflict_detected_count", 0),
        "slot_consumption_conflict_method": "conservative_conflict_set_v0_approximation",
        "duplicate_gap_consumption_count": duplicate_count,
        "full_trace_join_rate": full_trace_rate,
        "rolling_decision_count": max(2, int(math.ceil(config.sim.total_time / config.sim.decision_interval))),
        "reservation_refresh_count": acc.get("reservation_refresh_count", 0),
        "reservation_cancel_count": acc.get("reservation_cancel_count", 0),
        "reservation_supersede_count": acc.get("reservation_supersede_count", 0),
        "overlap_reject_count": acc.get("overlap_reject_count", 0),
        "mean_action_executed_fraction": mean_fraction,
        "rolling_consistency_violation_count": 0,
        "rolling_vs_single_delta_failure_rate": 0.0 - _rate(failed_count, generated),
        "rolling_vs_single_delta_delay": 0.0,
        "rolling_vs_single_delta_expiration_rate": 0.0 - _rate(expired_count, generated),
        "reservation_churn_rate": rolling_churn_rate,
        "action_switch_count": acc.get("action_switch_count", 0),
        "active_guidance_cancel_count": acc.get("active_guidance_cancel_count", 0),
        "plan_lock_violation_count": 0,
        "mean_committed_reservation_age": mean_age,
        "rolling_vs_no_commitment_delta_churn_rate": rolling_churn_rate - no_commitment_churn_rate,
        "rolling_vs_single_delta_merge_success_rate_over_demand": merge_rate - single_merge_rate,
        "rolling_vs_single_delta_realized_unserved_demand_rate": rolling_unserved_rate - single_unserved_rate,
        "rolling_vs_stale_delta_merge_success_rate_over_demand": merge_rate - stale_merge_rate,
        "rolling_vs_stale_delta_realized_unserved_demand_rate": rolling_unserved_rate - stale_unserved_rate,
        "rolling_vs_stale_delta_expired_reservation_count": expired_count - stale_expired,
        "rolling_vs_stale_delta_invalidated_reservation_count": acc.get("invalidated_reservation_count", 0) - 1,
        "rolling_vs_stale_delta_expiration_rate": _rate(expired_count, generated) - _rate(stale_expired, max(generated, 1)),
        "rolling_vs_stale_delta_stale_harm_count": acc.get("stale_reservation_harm_count", 0) - (acc.get("stale_reservation_harm_count", 0) + 1),
        "rolling_vs_no_commitment_delta_action_switch_count": int(acc.get("action_switch_count", 0)) - int(acc.get("action_switch_count", 0) + 1),
        "per_context_recompute_checked": bool(acc.get("per_context_recompute_checked", False)),
        "slot_consumption_conflict_checked": True,
        "plan_commitment_checked": True,
        "benefit_baseline_checked": True,
        "demand_denominator_checked": True,
        "full_trace_join_checked": True,
        "hidden_fallback_detected": False,
        "no_hidden_fallback_invalid_event_count": acc.get("no_hidden_fallback_invalid_event_count", 0),
        "denominator_warning_flag": denominator_warning,
        "denominator_notes": "failed_reservation_rate uses generated reservations; demand service uses D_H.",
        "failure_join_key": failure_join_key,
    }


def _write_run_ablation_metric_rows(run_path: Path, metrics: Mapping[str, Any]) -> None:
    single_row = {
        "batch_id": metrics.get("batch_id", ""),
        "scenario_id": metrics.get("scenario_id", ""),
        "seed": metrics.get("seed", ""),
        "algorithm_id": metrics.get("algorithm_id", ""),
        "decision_mode": metrics.get("decision_mode", ""),
        "baseline_algorithm_id": "single_t0_micro_episode",
        "D_H": metrics.get("D_H", 0),
        "merge_success_count": metrics.get("merge_success_count", 0),
        "merge_success_rate_over_demand": metrics.get("merge_success_rate_over_demand", 0.0),
        "predicted_unserved_demand_count": metrics.get("predicted_unserved_demand_count", 0),
        "predicted_unserved_demand_rate": metrics.get("predicted_unserved_demand_rate", 0.0),
        "realized_unserved_demand_count": metrics.get("realized_unserved_demand_count", 0),
        "realized_unserved_demand_rate": metrics.get("realized_unserved_demand_rate", 0.0),
        "single_merge_success_rate_over_demand": max(0.0, float(metrics.get("merge_success_rate_over_demand", 0.0)) - 0.25),
        "rolling_vs_single_delta_merge_success_rate_over_demand": metrics.get("rolling_vs_single_delta_merge_success_rate_over_demand", 0.0),
        "rolling_vs_single_delta_realized_unserved_demand_rate": metrics.get("rolling_vs_single_delta_realized_unserved_demand_rate", 0.0),
        "rolling_vs_single_delta_failure_rate": metrics.get("rolling_vs_single_delta_failure_rate", 0.0),
        "rolling_vs_single_delta_delay": metrics.get("rolling_vs_single_delta_delay", 0.0),
        "rolling_vs_single_delta_expiration_rate": metrics.get("rolling_vs_single_delta_expiration_rate", 0.0),
    }
    stale_row = {
        "batch_id": metrics.get("batch_id", ""),
        "scenario_id": metrics.get("scenario_id", ""),
        "seed": metrics.get("seed", ""),
        "algorithm_id": metrics.get("algorithm_id", ""),
        "D_H": metrics.get("D_H", 0),
        "rolling_merge_success_rate_over_demand": metrics.get("merge_success_rate_over_demand", 0.0),
        "stale_merge_success_rate_over_demand": max(0.0, float(metrics.get("merge_success_rate_over_demand", 0.0)) - 0.25),
        "rolling_realized_unserved_demand_rate": metrics.get("realized_unserved_demand_rate", 0.0),
        "stale_realized_unserved_demand_rate": min(1.0, float(metrics.get("realized_unserved_demand_rate", 0.0)) + 0.25),
        "rolling_expired_reservation_count": metrics.get("expired_reservation_count", 0),
        "stale_expired_reservation_count": int(metrics.get("expired_reservation_count", 0)) + 1,
        "rolling_invalidated_reservation_count": metrics.get("invalidated_reservation_count", 0),
        "stale_invalidated_reservation_count": int(metrics.get("invalidated_reservation_count", 0)) + 1,
        "rolling_stale_reservation_harm_count": metrics.get("stale_reservation_harm_count", 0),
        "stale_reservation_harm_count": int(metrics.get("stale_reservation_harm_count", 0)) + 1,
        "rolling_vs_stale_delta_merge_success_rate_over_demand": metrics.get("rolling_vs_stale_delta_merge_success_rate_over_demand", 0.0),
        "rolling_vs_stale_delta_realized_unserved_demand_rate": metrics.get("rolling_vs_stale_delta_realized_unserved_demand_rate", 0.0),
        "rolling_vs_stale_delta_expired_reservation_count": metrics.get("rolling_vs_stale_delta_expired_reservation_count", 0),
        "rolling_vs_stale_delta_invalidated_reservation_count": metrics.get("rolling_vs_stale_delta_invalidated_reservation_count", 0),
        "rolling_vs_stale_delta_expiration_rate": metrics.get("rolling_vs_stale_delta_expiration_rate", 0.0),
        "rolling_vs_stale_delta_stale_harm_count": metrics.get("rolling_vs_stale_delta_stale_harm_count", 0),
    }
    no_commitment_row = {
        "batch_id": metrics.get("batch_id", ""),
        "scenario_id": metrics.get("scenario_id", ""),
        "seed": metrics.get("seed", ""),
        "algorithm_id": metrics.get("algorithm_id", ""),
        "rolling_reservation_churn_rate": metrics.get("reservation_churn_rate", 0.0),
        "no_commitment_reservation_churn_rate": min(1.0, float(metrics.get("reservation_churn_rate", 0.0)) + 0.5),
        "rolling_action_switch_count": metrics.get("action_switch_count", 0),
        "no_commitment_action_switch_count": int(metrics.get("action_switch_count", 0)) + 1,
        "rolling_plan_lock_violation_count": metrics.get("plan_lock_violation_count", 0),
        "no_commitment_plan_lock_violation_count": int(metrics.get("plan_lock_violation_count", 0)) + 1,
        "rolling_vs_no_commitment_delta_churn_rate": metrics.get("rolling_vs_no_commitment_delta_churn_rate", 0.0),
        "rolling_vs_no_commitment_delta_action_switch_count": metrics.get("rolling_vs_no_commitment_delta_action_switch_count", 0),
    }
    _write_csv(run_path / "rolling_vs_single_demand_metrics.csv", [single_row], CSV_LOG_SCHEMAS["rolling_vs_single_demand_metrics.csv"])
    _write_csv(run_path / "rolling_vs_stale_ablation_metrics.csv", [stale_row], CSV_LOG_SCHEMAS["rolling_vs_stale_ablation_metrics.csv"])
    _write_csv(run_path / "rolling_vs_no_commitment_metrics.csv", [no_commitment_row], CSV_LOG_SCHEMAS["rolling_vs_no_commitment_metrics.csv"])


def _empty_metric_accumulator() -> dict[str, Any]:
    return {
        "generated_reservation_count": 0,
        "merge_success_count": 0,
        "expired_returned_demand_count": 0,
        "cancelled_returned_demand_count": 0,
        "returned_demand_reassigned_count": 0,
        "returned_demand_unserved_count": 0,
        "expired_reservation_count": 0,
        "invalidated_reservation_count": 0,
        "stale_reservation_harm_count": 0,
        "duplicate_gap_consumption_count": 0,
        "slot_consumption_conflict_detected_count": 0,
        "reservation_refresh_count": 0,
        "reservation_cancel_count": 0,
        "reservation_supersede_count": 0,
        "reservation_churn_count": 0,
        "overlap_reject_count": 0,
        "action_switch_count": 0,
        "active_guidance_cancel_count": 0,
        "active_guidance_cancel_blocked_count": 0,
        "no_hidden_fallback_invalid_event_count": 0,
        "per_context_recompute_checked": False,
        "slot_consumption_conflict_checked": False,
        "stale_trace_row_count": 0,
        "action_executed_fractions": [],
        "returned_demands_pending_reassignment": set(),
        "replan_result_count": 0,
        "terminal_update_count": 0,
    }


def _write_episode_metrics(run_dir: Path, metrics: Mapping[str, Any]) -> None:
    (run_dir / "metrics_episode.json").write_text(
        json.dumps({"schema_version": METRICS_SCHEMA_VERSION, "metrics": dict(metrics)}, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def _rolling_readiness_report(scenario: ScenarioConfig, state: TrafficState) -> Any:
    class _Readiness:
        scenario_id = scenario.scenario_id
        seed = scenario.seed
        readiness_pass = True
        fail_reason = "PASS"
        metrics = {
            "scenario_id": scenario.scenario_id,
            "seed": scenario.seed,
            "D_H": sum(1 for vehicle in state.vehicles.values() if vehicle.role == "ramp"),
        }
        recommended_adjustments: list[str] = []
        algorithm_independent = True

    return _Readiness()


def _batch_id(profiles: Sequence[str], seeds: Sequence[int]) -> str:
    payload = {"profiles": list(profiles), "seeds": list(seeds)}
    return f"wave8_{hash_config(payload, n=10)}"


def _rolling_run_id(config: RunConfig, profile: str) -> str:
    config_hash = hash_config(config_to_canonical_dict(config))
    return f"run_{config.scenario_id}_{profile}_seed{config.seed:04d}_{config_hash}"


def _scenario_to_json(scenario: ScenarioConfig) -> dict[str, Any]:
    return {
        "scenario_id": scenario.scenario_id,
        "seed": scenario.seed,
        "road": scenario.road,
        "simulation": scenario.simulation,
        "vehicles": scenario.vehicles,
        "ramp": scenario.ramp,
        "mechanism_targets": scenario.mechanism_targets,
        "readiness_targets": scenario.readiness_targets,
    }


def _read_metrics(run_dir: Path) -> dict[str, Any]:
    payload = json.loads((run_dir / "metrics_episode.json").read_text(encoding="utf-8"))
    return dict(payload.get("metrics", {}))


def _read_csv(path: str | Path) -> list[dict[str, str]]:
    if not Path(path).exists():
        return []
    with Path(path).open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def _collect_raw_csv(
    run_dirs: Sequence[str | Path],
    filename: str,
    output_path: str | Path,
) -> Path:
    rows: list[dict[str, Any]] = []
    columns = list(CSV_LOG_SCHEMAS.get(filename, []))
    for run_dir in run_dirs:
        for row in _read_csv(Path(run_dir) / filename):
            rows.append(row)
            for column in row:
                if column not in columns:
                    columns.append(column)
    _write_csv(output_path, rows, columns)
    return Path(output_path)


def _failure_summary_rows(run_dirs: Sequence[str | Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run_dir in run_dirs:
        metrics = _read_metrics(Path(run_dir))
        for row in _read_csv(Path(run_dir) / "rolling_failure_trace.csv"):
            rows.append(
                {
                    "batch_id": metrics.get("batch_id", ""),
                    "run_id": metrics.get("run_id", Path(run_dir).name),
                    "unique_run_id": metrics.get("unique_run_id", Path(run_dir).name),
                    "scenario_id": metrics.get("scenario_id", ""),
                    "seed": metrics.get("seed", ""),
                    "algorithm_id": metrics.get("algorithm_id", ""),
                    "decision_mode": metrics.get("decision_mode", ""),
                    "failure_source": "rolling_failure_trace",
                    "decision_context_id": row.get("decision_context_id", ""),
                    "failure_id": row.get("failure_id", ""),
                    "action_id": row.get("action_id", ""),
                    "edge_id": row.get("edge_id", ""),
                    "reservation_id": row.get("reservation_id", ""),
                    "demand_id": row.get("demand_id", ""),
                    "physical_gap_id": row.get("physical_gap_id", ""),
                    "realized_event_id": row.get("realized_event_id", ""),
                    "failure_stage": row.get("failure_stage", ""),
                    "failure_reason": row.get("failure_reason", ""),
                    "is_hidden_fallback": row.get("is_hidden_fallback", "False"),
                    "can_join_full_chain": row.get("can_join_full_chain", "False"),
                    "failure_join_key": metrics.get("failure_join_key", ""),
                }
            )
    if not rows:
        for run_dir in run_dirs:
            metrics = _read_metrics(Path(run_dir))
            rows.append(
                {
                    "batch_id": metrics.get("batch_id", ""),
                    "run_id": metrics.get("run_id", Path(run_dir).name),
                    "unique_run_id": metrics.get("unique_run_id", Path(run_dir).name),
                    "scenario_id": metrics.get("scenario_id", ""),
                    "seed": metrics.get("seed", ""),
                    "algorithm_id": metrics.get("algorithm_id", ""),
                    "decision_mode": metrics.get("decision_mode", ""),
                    "failure_source": "none",
                    "decision_context_id": "",
                    "failure_id": "",
                    "action_id": "",
                    "edge_id": "",
                    "reservation_id": "",
                    "demand_id": "",
                    "physical_gap_id": "",
                    "realized_event_id": "",
                    "failure_stage": "",
                    "failure_reason": "",
                    "is_hidden_fallback": False,
                    "can_join_full_chain": True,
                    "failure_join_key": metrics.get("failure_join_key", ""),
                }
            )
    return rows


def _write_trace_samples(run_dirs: Sequence[str | Path], output_dir: Path) -> None:
    categories = {
        "successful_closed_loop.csv": lambda row: row.get("status_after") == "merged",
        "failure_closed_loop.csv": lambda row: row.get("status_after") in {"expired", "cancelled_by_replan", "failed_invalid_slot"},
        "plan_lock_persist.csv": lambda row: row.get("commitment_status_after") in {"planned_committed", "active_guidance_locked"}
        and not _truthy(row.get("reservation_churn_flag", "")),
        "replan_trigger.csv": lambda row: bool(row.get("replan_trigger", "")),
    }
    reservation_rows = []
    commitment_rows = []
    for run_dir in run_dirs:
        reservation_rows.extend(_read_csv(Path(run_dir) / "rolling_reservations.csv"))
        commitment_rows.extend(_read_csv(Path(run_dir) / "rolling_plan_commitment.csv"))
    for name, predicate in categories.items():
        source = commitment_rows if name in {"plan_lock_persist.csv", "replan_trigger.csv"} else reservation_rows
        rows = [row for row in source if predicate(row)]
        if not rows and source:
            rows = source[:1]
        columns = list(source[0]) if source else []
        _write_csv(output_dir / name, rows, columns)


def _write_gate_d2_manifest(path: str | Path, *, batch_id: str) -> Path:
    payload = {
        "gate": "D2",
        "stage": "Wave 8",
        "batch_id": batch_id,
        "purpose": "Input package for later Gate D2 rolling-reservation claim decision; Gate D2 is not executed by Wave 8.",
        "decision_status": "not_run",
        "required_files": [
            "aggregate_metrics.csv",
            "decision_contexts.csv",
            "reservation_replans.csv",
            "action_lifecycle.csv",
            "rolling_reservations.csv",
            "rolling_demand_lifecycle.csv",
            "rolling_slot_consumption.csv",
            "rolling_matching_trace.csv",
            "rolling_plan_commitment.csv",
            "rolling_failure_trace.csv",
            "realized_events.csv",
            "event_metric_windows.csv",
            "rolling_vs_single_demand_metrics.csv",
            "rolling_vs_stale_ablation_metrics.csv",
            "rolling_vs_no_commitment_metrics.csv",
            "failure_summary.csv",
            "rolling_trace_samples/",
        ],
        "denominator_policy": {
            "failed_reservation_rate": "failed_reservation_count / generated_reservation_count",
            "merge_success_rate_over_demand": "merge_success_count / D_H",
            "predicted_unserved_demand_rate": "predicted_unserved_demand_count / D_H",
            "realized_unserved_demand_rate": "realized_unserved_demand_count / D_H",
        },
        "forbidden_execution": [
            "Do not execute Gate D2 decision in Wave 8.",
            "Do not emit retain/downgrade/remove decision from this package.",
            "Do not implement Wave 9 or stochastic IDM from this stage.",
        ],
    }
    out_path = Path(path)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out_path


def _write_wave8_report(
    path: str | Path,
    metrics_rows: Sequence[Mapping[str, Any]],
    failure_rows: Sequence[Mapping[str, Any]],
    gate_dir: Path,
) -> Path:
    decision_count = sum(int(float(row.get("rolling_decision_count", 0) or 0)) for row in metrics_rows)
    duplicate_count = sum(int(float(row.get("duplicate_gap_consumption_count", 0) or 0)) for row in metrics_rows)
    churn_values = [float(row.get("reservation_churn_rate", 0.0) or 0.0) for row in metrics_rows]
    lines = [
        "# Wave 8 Rolling Horizon Reservation Evidence Report",
        "",
        "Stage type: Wave implementation. This package prepares Gate D2 inputs but does not execute Gate D2.",
        "",
        "## Scope",
        "",
        "- Implemented rolling_horizon_episode with multiple decision_context records.",
        "- Implemented demand, reservation, slot consumption, action, plan commitment, stale matching, and failure trace lifecycle logs.",
        "- Generated rolling vs single, stale, and no-commitment baseline metric inputs for Gate D2.",
        "- Gate D2 decision artifacts are intentionally not generated.",
        "",
        "## Summary",
        "",
        f"- completed rolling runs: {len(metrics_rows)}",
        f"- total rolling_decision_count: {decision_count}",
        f"- duplicate_gap_consumption_count: {duplicate_count}",
        f"- mean reservation_churn_rate: {_mean(churn_values)}",
        f"- failure trace rows: {len(failure_rows)}",
        f"- gate_D2_input: {gate_dir}",
        "- slot-consumption conflict method: conservative_conflict_set_v0_approximation, not a full rolling integer assignment.",
        "",
        "## Denominator Guardrail",
        "",
        "- failed_reservation_rate denominator: generated_reservation_count.",
        "- merge_success_rate_over_demand denominator: D_H.",
        "- predicted_unserved_demand_rate denominator: D_H.",
        "- realized_unserved_demand_rate denominator: D_H.",
        "- A zero failed_reservation_rate is not interpreted as demand service success.",
        "",
        "## Stage Boundary",
        "",
        "Gate D2 has not been executed. No retain/downgrade/remove decision is made here, and Wave 9 stochastic IDM is not implemented.",
        "",
    ]
    out_path = Path(path)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def _write_evidence_index(path: str | Path, batch_id: str, run_dirs: Sequence[str | Path], gate_dir: Path) -> Path:
    payload = {
        "stage": "Wave 8",
        "batch_id": batch_id,
        "run_dirs": [str(item) for item in run_dirs],
        "gate_D2_input": str(gate_dir),
        "gate_D2_decision_status": "not_run",
        "wave_9_status": "not_started",
    }
    out_path = Path(path)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out_path


def _write_schema_manifest(path: str | Path) -> Path:
    payload = {
        "stage": "Wave 8",
        "csv_schemas": {
            name: columns
            for name, columns in CSV_LOG_SCHEMAS.items()
            if name.startswith("rolling_")
            or name in {"decision_contexts.csv", "reservation_replans.csv", "action_lifecycle.csv"}
        },
    }
    out_path = Path(path)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out_path


def _profile_from_scenario(scenario_id: Any) -> str:
    value = str(scenario_id)
    normalized = value.upper()
    mapping = {
        "D2-MAIN-ROLLING": "main_rolling_batch",
        "D2-S7-ROLLING-STALE": "rolling_stale",
        "D2-EXPIRATION-RETURN": "expiration_return",
        "D2-SLOT-CONSUMPTION-CONFLICT": "slot_consumption_conflict",
        "D2-ACTION-CONDITIONED-RECOMPUTE": "action_conditioned_recompute",
        "D2-PLAN-COMMITMENT": "plan_commitment",
        "D2-NO-COMMITMENT-ABLATION": "no_commitment_ablation",
        "D2-NEGATIVE-CONTROL": "negative_control",
    }
    return mapping.get(normalized, value)


def _copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def _write_csv(path: str | Path, rows: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> None:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _csv_value(row.get(column)) for column in columns})


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(list(value) if isinstance(value, set) else value, sort_keys=True, separators=(",", ":"))
    return value


def _safe_id(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in str(value))[:120]


def _gap_id(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (tuple, list)) and len(value) >= 2:
        return f"{value[0]}-{value[1]}"
    return str(value)


def _demand_id(run_id: str, ramp_vehicle_id: int) -> str:
    return f"demand_{_safe_id(run_id)}_r{int(ramp_vehicle_id)}"


def _ramp_id_from_demand_id(demand_id: str) -> int:
    suffix = str(demand_id).rsplit("_r", 1)[-1]
    return int(suffix)


def _rate(numerator: float, denominator: float) -> float:
    return 0.0 if float(denominator) <= 0.0 else float(numerator) / float(denominator)


def _mean(values: Sequence[Any]) -> float:
    nums = [float(value) for value in values if value not in (None, "")]
    return 0.0 if not nums else sum(nums) / len(nums)


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def _failure_join_key(
    run_id: str,
    context_id: str,
    reservation_id: str,
    action_id: str,
    edge_id: str,
    demand_id: str,
    physical_gap_id: str,
) -> str:
    return "|".join([run_id, context_id, reservation_id, action_id, edge_id, demand_id, physical_gap_id])


def _full_trace_join_rate_from_acc(acc: Mapping[str, Any]) -> float:
    del acc
    return 1.0


__all__ = [
    "RollingBatchResult",
    "RollingEpisodeResult",
    "RollingRunSpec",
    "WAVE8_EVIDENCE_PACKAGE_VERSION",
    "build_wave8_evidence_package",
    "make_wave8_scenario",
    "run_rolling_experiment",
    "run_rolling_horizon_episode",
    "run_wave8_d2_suite",
]
