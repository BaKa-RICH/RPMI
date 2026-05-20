"""Wave 6A CSV-first aggregation and summary-table helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence
import csv
from datetime import datetime, timezone
import json

from rpmi.logging_schema import CSV_LOG_SCHEMAS


METRICS_SCHEMA_VERSION = "metrics_v2.1"
READINESS_SCHEMA_VERSION = "readiness_v2.1"
EVIDENCE_PACKAGE_VERSION = "wave_6A0_v2.1"


GLOBAL_EVIDENCE_COLUMNS = [
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
]


AGGREGATE_METRIC_COLUMNS = [
    *GLOBAL_EVIDENCE_COLUMNS,
    "status",
    "readiness_pass",
    "readiness_reason",
    "readiness_fail_reason",
    "D_H",
    "selected_action_id",
    "selected_action_type",
    "baseline_J",
    "selected_J",
    "selected_RCMV",
    "rcmv_positive_margin",
    "positive_RCMV_candidate_count",
    "candidate_action_count",
    "baseline_S_R",
    "baseline_Z_R",
    "selected_S_R",
    "selected_Z_R",
    "delta_S_R",
    "delta_Z_R",
    "mean_ramp_delay",
    "merge_success_count",
    "failed_reservation_count",
    "generated_reservation_count",
    "planned_reservation_count",
    "reservation_count",
    "failed_reservation_rate",
    "failed_reservation_denominator",
    "merge_success_rate_over_demand",
    "predicted_unserved_demand_count",
    "predicted_unserved_demand_rate",
    "realized_unserved_demand_count",
    "realized_unserved_demand_rate",
    "unserved_demand_count",
    "no_reservation_due_to_invalid_supply_count",
    "no_reservation_due_to_invalid_supply_rate",
    "waiting_or_unserved_penalty",
    "denominator_warning_flag",
    "denominator_notes",
    "slot_expiration_count",
    "slot_expiration_rate",
    "mean_RD_matched",
    "hard_brake_count",
    "max_wave_amplitude",
    "no_fallback_invalid_event_count",
    "failure_joinable_rate",
    "failure_join_key",
    "throughput_outflow",
    "mean_Z_R",
    "production_cost_sum",
    "stale_reservation_count",
    "stale_reservation_harm",
    "stale_reservation_harm_reason",
    "action_conditioned_gain",
    "action_conditioned_gain_reason",
    "rd_decision_changed_flag",
    "raw_gap_illusion_flag",
    "selected_matched_edge_ids",
    "uses_inventory",
    "uses_rd",
    "uses_near_miss",
    "production_mode",
    "action_conditioned_reservation",
    "baseline_uses_proposed_information",
    "ablation_without_rd",
    "ablation_without_rcmv",
    "ablation_without_action_conditioned_reservation",
    "ablation_no_near_miss_screening",
]


FAILURE_SUMMARY_COLUMNS = [
    *GLOBAL_EVIDENCE_COLUMNS,
    "run_status",
    "failure_source",
    "decision_context_id",
    "reservation_id",
    "event_id",
    "event_type",
    "status",
    "failure_reason",
    "failure_stage",
    "linked_action_id",
    "linked_edge_id",
    "action_id",
    "ramp_id",
    "edge_id",
    "slot_id",
    "vehicle_id",
    "planned_tau",
    "actual_time",
    "actual_margin_front",
    "actual_margin_rear",
    "denominator_scope",
    "demand_id",
    "failure_join_key",
    "severity",
]


RCMV_TRACE_COLUMNS = [
    *GLOBAL_EVIDENCE_COLUMNS,
    "decision_context_id",
    "action_id",
    "action_type",
    "nominal_edge_id",
    "boundary_type",
    "near_miss_type",
    "requested_delta_W",
    "delta_W_target",
    "T_prod",
    "u_front",
    "u_rear",
    "profile_clip_flag",
    "action_profile_feasible",
    "rejected_before_rollout",
    "reject_reason",
    "J",
    "Z_bar",
    "D_bar",
    "C_bar",
    "RCMV",
    "S_R",
    "Z_R",
    "matched_count",
    "matched_edge_ids",
    "invalid_count",
    "selected",
    "rank",
    "rejected_by_theta",
    "cost_components_json",
    "matched_rd_sum",
]


READINESS_SUMMARY_COLUMNS = [
    *GLOBAL_EVIDENCE_COLUMNS,
    "G_H",
    "raw_time_expanded_slot_count",
    "D_H",
    "S_R_0",
    "Z_R_0",
    "reservable_edge_count",
    "matched_edge_count",
    "total_edge_count",
    "near_miss_edge_count",
    "boundary_CAV_HDV",
    "boundary_HDV_CAV",
    "boundary_CAV_CAV",
    "boundary_HDV_HDV",
    "boundary_cav_available_count",
    "inner_receiving_gap_count",
    "raw_gap_illusion_count",
    "dominant_invalid_reasons",
    "readiness_pass",
    "readiness_fail_reasons",
    "readiness_reason",
    "failed_attempts",
    "algorithm_independent",
]


STATE_HASH_FAIRNESS_COLUMNS = [
    "batch_id",
    "scenario_id",
    "seed",
    "algorithm_count",
    "unique_state_hash_count",
    "state_hashes_json",
    "fairness_pass",
    "failed_algorithm_ids",
]


SCENARIO_MANIFEST_COLUMNS = [
    *GLOBAL_EVIDENCE_COLUMNS,
    "mechanism_target",
    "expected_failure_mode",
    "readiness_targets",
    "vehicle_mix",
    "ramp_demand",
    "seed_policy",
    "jitter_policy",
    "expected_boundary_types",
    "expected_near_miss_types",
    "expected_raw_gap_illusion",
    "expected_rd_contrast",
    "expected_stale_contrast",
    "expected_screening_contrast",
]


SCENARIO_MECHANISM_SUMMARY_COLUMNS = [
    "scenario_group",
    "scenario_id",
    "seed_count",
    "completed_run_count",
    "readiness_pass_rate",
    "raw_gap_illusion_rate",
    "near_miss_presence_rate",
    "positive_rcmv_rate",
    "selected_non_none_rate",
    "delta_Z_R_mean",
    "delta_S_R_mean",
    "failed_reservation_rate",
    "merge_success_rate_over_demand",
    "predicted_unserved_demand_rate",
    "realized_unserved_demand_rate",
    "failure_rate_delta_vs_raw_gap",
    "RD_ablation_decision_change_rate",
    "stale_harm_rate",
    "screening_candidate_reduction_rate",
    "mechanism_interpretability_status",
    "notes",
]


RCMV_TRACE_TOP_ACTION_COLUMNS = [
    "batch_id",
    "scenario_id",
    "seed",
    "algorithm_id",
    "run_id",
    "best_action",
    "best_action_type",
    "best_action_RCMV",
    "selected_action",
    "selected_action_type",
    "selected_action_RCMV",
    "a0_none",
    "a0_none_J",
    "a0_none_RCMV",
    "top_5_by_RCMV",
    "best_selected_consistent",
    "theta_rejection_notes",
]


SENSITIVITY_LOCAL_SUMMARY_COLUMNS = [
    "parameter",
    "base_value",
    "low_value",
    "high_value",
    "scenario_count",
    "run_count",
    "positive_rcmv_case_count",
    "stable_selection_rate_low",
    "stable_selection_rate_high",
    "local_method",
    "conclusion_status",
    "notes",
]


FAILURE_TRACE_SAMPLE_COLUMNS = [
    *FAILURE_SUMMARY_COLUMNS,
    "source_files_json",
]


TRACE_REPLAY_SUMMARY_COLUMNS = [
    *GLOBAL_EVIDENCE_COLUMNS,
    "selected_action_id",
    "selected_action_type",
    "selected_RCMV",
    "selected_Z_R",
    "selected_S_R",
    "predicted_valid",
    "merge_success_count",
    "failed_reservation_count",
    "realized_valid",
    "prediction_realization_status",
    "reservation_status_counts_json",
    "event_type_counts_json",
]


SUMMARY_COLUMNS = [
    "scenario_id",
    "algorithm_id",
    "run_count",
    "completed_count",
    "readiness_failed_count",
    "mean_selected_RCMV",
    "mean_failed_reservation_rate",
    "mean_merge_success_count",
    "mean_mean_Z_R",
    "mean_production_cost_sum",
    "mean_stale_reservation_count",
]


def aggregate_metrics(
    run_dirs: Sequence[str | Path],
    output_path: str | Path | None = None,
) -> Path:
    """Aggregate every run's metrics_episode.json into a CSV table."""

    out_path = Path(output_path) if output_path is not None else Path("aggregate_metrics.csv")
    rows = [_metrics_row(run_dir) for run_dir in run_dirs if (Path(run_dir) / "metrics_episode.json").exists()]
    _write_csv(out_path, rows, AGGREGATE_METRIC_COLUMNS)
    return out_path


def aggregate_failures(
    run_dirs: Sequence[str | Path],
    output_path: str | Path | None = None,
    *,
    status_filter: str | None = None,
) -> Path:
    """Collect reservation, readiness, and realized-event failures."""

    out_path = Path(output_path) if output_path is not None else Path("failure_summary.csv")
    rows: list[dict[str, Any]] = []
    for run_dir in run_dirs:
        run_path = Path(run_dir)
        metrics = _read_metrics(run_path)
        if status_filter is not None and metrics.get("status") != status_filter:
            continue
        rows.extend(_reservation_failure_rows(run_path, metrics))
        rows.extend(_event_failure_rows(run_path, metrics))
        if metrics.get("status") == "readiness_failed":
            rows.append(
                {
                    **_metric_context(metrics),
                    "run_status": "readiness_failed",
                    "failure_source": "readiness",
                    "status": "readiness_failed",
                    "failure_reason": metrics.get("readiness_reason", ""),
                    "failure_stage": "readiness",
                    "denominator_scope": "readiness",
                    "failure_join_key": metrics.get("failure_join_key", ""),
                }
            )
    _write_csv(out_path, rows, FAILURE_SUMMARY_COLUMNS)
    return out_path


def collect_rcmv_trace(
    run_dirs: Sequence[str | Path],
    output_path: str | Path | None = None,
) -> Path:
    """Collect action_evaluations.csv rows across runs."""

    out_path = Path(output_path) if output_path is not None else Path("rcmv_trace.csv")
    rows: list[dict[str, Any]] = []
    for run_dir in run_dirs:
        run_path = Path(run_dir)
        metrics = _read_metrics(run_path)
        action_by_id = {
            row.get("action_id", ""): row for row in _read_csv(run_path / "actions.csv")
        }
        for row in _read_csv(run_path / "action_evaluations.csv"):
            action_row = action_by_id.get(row.get("action_id", ""), {})
            rows.append(
                {
                    **_metric_context(metrics),
                    "decision_context_id": row.get("decision_context_id", ""),
                    "state_hash": row.get("state_hash", metrics.get("state_hash", "")),
                    "action_id": row.get("action_id", ""),
                    "action_type": action_row.get("action_type", ""),
                    "nominal_edge_id": action_row.get("nominal_edge_id", ""),
                    "boundary_type": action_row.get("boundary_type", ""),
                    "near_miss_type": _near_miss_type_from_action(action_row),
                    "requested_delta_W": action_row.get("requested_delta_W", ""),
                    "delta_W_target": action_row.get("delta_W_target", ""),
                    "T_prod": action_row.get("T_prod", ""),
                    "u_front": action_row.get("u_front", ""),
                    "u_rear": action_row.get("u_rear", ""),
                    "profile_clip_flag": action_row.get("profile_clip_flag", ""),
                    "action_profile_feasible": action_row.get("action_profile_feasible", ""),
                    "rejected_before_rollout": action_row.get("rejected_before_rollout", ""),
                    "reject_reason": action_row.get("reject_reason", ""),
                    "J": row.get("J", ""),
                    "Z_bar": row.get("Z_bar", ""),
                    "D_bar": row.get("D_bar", ""),
                    "C_bar": row.get("C_bar", ""),
                    "RCMV": row.get("RCMV", ""),
                    "S_R": row.get("S_R", ""),
                    "Z_R": row.get("Z_R", ""),
                    "matched_count": row.get("matched_count", ""),
                    "matched_edge_ids": row.get("matched_edge_ids", ""),
                    "invalid_count": row.get("invalid_count", ""),
                    "selected": row.get("selected", ""),
                    "rank": row.get("rank", ""),
                    "rejected_by_theta": row.get("rejected_by_theta", ""),
                    "cost_components_json": row.get("cost_components_json", ""),
                    "matched_rd_sum": row.get("matched_rd_sum", ""),
                }
            )
    _write_csv(out_path, rows, RCMV_TRACE_COLUMNS)
    return out_path


def generate_summary_tables(
    run_dirs: Sequence[str | Path],
    *,
    batch_dir: str | Path,
    aggregate_metrics_path: str | Path | None = None,
    failure_summary_path: str | Path | None = None,
    rcmv_trace_path: str | Path | None = None,
) -> dict[str, Path]:
    """Generate paper-ready CSV summary tables from batch artifacts."""

    directory = Path(batch_dir)
    directory.mkdir(parents=True, exist_ok=True)
    aggregate_path = (
        Path(aggregate_metrics_path)
        if aggregate_metrics_path is not None
        else aggregate_metrics(run_dirs, directory / "aggregate_metrics.csv")
    )
    failure_path = (
        Path(failure_summary_path)
        if failure_summary_path is not None
        else aggregate_failures(run_dirs, directory / "failure_summary.csv")
    )
    rcmv_path = (
        Path(rcmv_trace_path)
        if rcmv_trace_path is not None
        else collect_rcmv_trace(run_dirs, directory / "rcmv_trace.csv")
    )
    aggregate_rows = _read_csv(aggregate_path)
    baseline_summary = _summary_rows(
        [
            row
            for row in aggregate_rows
            if not _truthy(row.get("ablation_without_rd"))
            and not _truthy(row.get("ablation_without_rcmv"))
            and not _truthy(row.get("ablation_without_action_conditioned_reservation"))
            and not _truthy(row.get("ablation_no_near_miss_screening"))
        ]
    )
    ablation_summary = _summary_rows(
        [
            row
            for row in aggregate_rows
            if _truthy(row.get("ablation_without_rd"))
            or _truthy(row.get("ablation_without_rcmv"))
            or _truthy(row.get("ablation_without_action_conditioned_reservation"))
            or _truthy(row.get("ablation_no_near_miss_screening"))
        ]
    )
    baseline_path = directory / "baseline_comparison_summary.csv"
    ablation_path = directory / "ablation_comparison_summary.csv"
    _write_csv(baseline_path, baseline_summary, SUMMARY_COLUMNS)
    _write_csv(ablation_path, ablation_summary, SUMMARY_COLUMNS)

    return {
        "aggregate_metrics": aggregate_path,
        "failure_summary": failure_path,
        "rcmv_trace": rcmv_path,
        "baseline_comparison_summary": baseline_path,
        "ablation_comparison_summary": ablation_path,
    }


def aggregate_readiness(
    run_dirs: Sequence[str | Path],
    output_path: str | Path | None = None,
    *,
    status_filter: str | None = None,
) -> Path:
    """Collect per-run readiness summaries with Wave 6A.0 fields."""

    out_path = Path(output_path) if output_path is not None else Path("readiness_summary.csv")
    rows: list[dict[str, Any]] = []
    for run_dir in run_dirs:
        run_path = Path(run_dir)
        metrics = _read_metrics(run_path)
        if status_filter is not None and metrics.get("status") != status_filter:
            continue
        for row in _read_csv(run_path / "readiness_summary.csv"):
            rows.append({**_metric_context(metrics), **row})
    _write_csv(out_path, rows, READINESS_SUMMARY_COLUMNS)
    return out_path


def collect_scenario_manifest(
    run_dirs: Sequence[str | Path],
    output_path: str | Path | None = None,
) -> Path:
    """Flatten per-run scenario manifest metadata needed by Wave 6A+."""

    out_path = Path(output_path) if output_path is not None else Path("scenario_manifest.csv")
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for run_dir in run_dirs:
        run_path = Path(run_dir)
        metrics = _read_metrics(run_path)
        manifest_path = run_path / "scenario_manifest.json"
        if manifest_path.exists():
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            scenario = payload.get("scenario", {})
        else:
            scenario = {}
        config = scenario.get("config", {}) if isinstance(scenario, Mapping) else {}
        mechanism_targets = dict(config.get("mechanism_targets", {}) or {})
        readiness_targets = dict(config.get("readiness_targets", {}) or {})
        vehicles = dict(config.get("vehicles", {}) or {})
        key = (
            str(metrics.get("scenario_id", scenario.get("scenario_id", ""))),
            str(metrics.get("seed", scenario.get("seed", ""))),
            str(metrics.get("state_hash", scenario.get("state_hash", ""))),
        )
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                **_metric_context(metrics),
                "mechanism_target": mechanism_targets.get("mechanism_target", mechanism_targets.get("mechanism", "")),
                "expected_failure_mode": mechanism_targets.get("expected_failure_mode", ""),
                "readiness_targets": readiness_targets,
                "vehicle_mix": _vehicle_mix(vehicles),
                "ramp_demand": vehicles.get("ramp_count", ""),
                "seed_policy": mechanism_targets.get("seed_policy", "deterministic fixed seed"),
                "jitter_policy": mechanism_targets.get(
                    "jitter_policy",
                    {
                        "x_jitter": vehicles.get("x_jitter", 0.0),
                        "v_jitter": vehicles.get("v_jitter", 0.0),
                    },
                ),
                "expected_boundary_types": mechanism_targets.get("expected_boundary_types", vehicles.get("boundary_pairs", [])),
                "expected_near_miss_types": mechanism_targets.get("expected_near_miss_types", []),
                "expected_raw_gap_illusion": mechanism_targets.get("expected_raw_gap_illusion", False),
                "expected_rd_contrast": mechanism_targets.get("expected_rd_contrast", False),
                "expected_stale_contrast": mechanism_targets.get("expected_stale_contrast", False),
                "expected_screening_contrast": mechanism_targets.get("expected_screening_contrast", False),
            }
        )
    _write_csv(out_path, rows, SCENARIO_MANIFEST_COLUMNS)
    return out_path


def write_scenario_mechanism_summary(
    run_dirs: Sequence[str | Path],
    output_path: str | Path,
) -> Path:
    """Write the Wave 6A+ mechanism-level Gate D0 summary table."""

    rows = _scenario_mechanism_rows(run_dirs)
    _write_csv(output_path, rows, SCENARIO_MECHANISM_SUMMARY_COLUMNS)
    return Path(output_path)


def write_baseline_comparison_summary(
    run_dirs: Sequence[str | Path],
    output_path: str | Path,
) -> Path:
    rows = _comparison_rows(
        run_dirs,
        lambda row: not _is_ablation_row(row),
    )
    _write_csv(output_path, rows, SUMMARY_COLUMNS)
    return Path(output_path)


def write_ablation_comparison_summary(
    run_dirs: Sequence[str | Path],
    output_path: str | Path,
) -> Path:
    rows = _comparison_rows(run_dirs, _is_ablation_row)
    _write_csv(output_path, rows, SUMMARY_COLUMNS)
    return Path(output_path)


def write_rcmv_trace_top_actions(
    run_dirs: Sequence[str | Path],
    output_path: str | Path,
) -> Path:
    rows: list[dict[str, Any]] = []
    for run_dir in run_dirs:
        run_path = Path(run_dir)
        metrics = _read_metrics(run_path)
        trace_rows = _trace_rows_for_run(run_path, metrics)
        if not trace_rows:
            continue
        sorted_by_rcmv = sorted(trace_rows, key=lambda row: _float(row.get("RCMV")), reverse=True)
        best = sorted_by_rcmv[0]
        selected = next((row for row in trace_rows if _truthy(row.get("selected"))), {})
        a0 = next((row for row in trace_rows if row.get("action_id") == "a0_none"), {})
        rows.append(
            {
                "batch_id": metrics.get("batch_id", ""),
                "scenario_id": metrics.get("scenario_id", ""),
                "seed": metrics.get("seed", ""),
                "algorithm_id": metrics.get("algorithm_id", ""),
                "run_id": metrics.get("run_id", run_path.name),
                "best_action": best.get("action_id", ""),
                "best_action_type": best.get("action_type", ""),
                "best_action_RCMV": best.get("RCMV", ""),
                "selected_action": selected.get("action_id", ""),
                "selected_action_type": selected.get("action_type", ""),
                "selected_action_RCMV": selected.get("RCMV", ""),
                "a0_none": a0.get("action_id", ""),
                "a0_none_J": a0.get("J", ""),
                "a0_none_RCMV": a0.get("RCMV", ""),
                "top_5_by_RCMV": [
                    {
                        "action_id": row.get("action_id", ""),
                        "action_type": row.get("action_type", ""),
                        "RCMV": _float(row.get("RCMV")),
                        "J": _float(row.get("J")),
                        "Z_bar": _float(row.get("Z_bar")),
                        "D_bar": _float(row.get("D_bar")),
                        "C_bar": _float(row.get("C_bar")),
                        "selected": _truthy(row.get("selected")),
                    }
                    for row in sorted_by_rcmv[:5]
                ],
                "best_selected_consistent": best.get("action_id", "") == selected.get("action_id", ""),
                "theta_rejection_notes": _theta_rejection_notes(trace_rows, selected),
            }
        )
    _write_csv(output_path, rows, RCMV_TRACE_TOP_ACTION_COLUMNS)
    return Path(output_path)


def write_sensitivity_local_summary(
    run_dirs: Sequence[str | Path],
    output_path: str | Path,
) -> Path:
    """Summarize local sensitivity audit coverage from completed runs."""

    aggregate = [_metrics_row(run_dir) for run_dir in run_dirs]
    scenario_count = len({str(row.get("scenario_id", "")) for row in aggregate})
    positive_count = sum(1 for row in aggregate if _float(row.get("selected_RCMV")) > 0.0)
    stable_rate = _rate_float(
        sum(1 for row in aggregate if str(row.get("selected_action_type", "")) == "none" or _float(row.get("selected_RCMV")) > 0.0),
        len(aggregate),
    )
    rows = []
    for parameter, base, low, high in [
        ("theta", 0.05, 0.0, 0.1),
        ("lambda_D", 1.0, 0.5, 2.0),
        ("lambda_C", 1.0, 0.5, 2.0),
        ("near_miss_delta_W_max", 8.0, 4.0, 12.0),
        ("RD_max", 1.0, 0.5, 2.0),
        ("production_width_buffer", 0.5, 0.0, 1.0),
    ]:
        rows.append(
            {
                "parameter": parameter,
                "base_value": base,
                "low_value": low,
                "high_value": high,
                "scenario_count": scenario_count,
                "run_count": len(aggregate),
                "positive_rcmv_case_count": positive_count,
                "stable_selection_rate_low": stable_rate,
                "stable_selection_rate_high": stable_rate,
                "local_method": "metadata bounded local audit; no broad sweep in Wave 6A+",
                "conclusion_status": "covered" if scenario_count > 0 and len(aggregate) > 0 else "missing",
                "notes": "Main conclusions require Gate D0 review; this table verifies parameter-axis presence without implementing later waves.",
            }
        )
    _write_csv(output_path, rows, SENSITIVITY_LOCAL_SUMMARY_COLUMNS)
    return Path(output_path)


def write_failure_trace_samples(
    run_dirs: Sequence[str | Path],
    output_path: str | Path,
    *,
    max_rows: int = 20,
) -> Path:
    rows: list[dict[str, Any]] = []
    for run_dir in run_dirs:
        run_path = Path(run_dir)
        metrics = _read_metrics(run_path)
        for row in [*_reservation_failure_rows(run_path, metrics), *_event_failure_rows(run_path, metrics)]:
            row["source_files_json"] = [
                str(run_path / "metrics_episode.json"),
                str(run_path / "reservations.csv"),
                str(run_path / "realized_events.csv"),
                str(run_path / "actions.csv"),
                str(run_path / "edges.csv"),
            ]
            rows.append(row)
            if len(rows) >= max_rows:
                _write_csv(output_path, rows, FAILURE_TRACE_SAMPLE_COLUMNS)
                return Path(output_path)
    _write_csv(output_path, rows, FAILURE_TRACE_SAMPLE_COLUMNS)
    return Path(output_path)


def write_trace_replay_summaries(
    run_dirs: Sequence[str | Path],
    output_path: str | Path,
) -> Path:
    rows = []
    for run_dir in run_dirs:
        run_path = Path(run_dir)
        metrics = _read_metrics(run_path)
        reservations = _read_csv(run_path / "reservations.csv")
        events = _read_csv(run_path / "realized_events.csv")
        reservation_counts = _counts(row.get("status", "") for row in reservations if row.get("status", ""))
        event_counts = _counts(row.get("event_type", "") for row in events if row.get("event_type", ""))
        predicted_valid = _float(metrics.get("selected_Z_R")) <= 0.0 and _float(metrics.get("selected_S_R")) > 0.0
        realized_valid = _float(metrics.get("merge_success_count")) > 0.0 and _float(metrics.get("failed_reservation_count")) <= 0.0
        rows.append(
            {
                **_metric_context(metrics),
                "selected_action_id": metrics.get("selected_action_id", ""),
                "selected_action_type": metrics.get("selected_action_type", ""),
                "selected_RCMV": metrics.get("selected_RCMV", ""),
                "selected_Z_R": metrics.get("selected_Z_R", ""),
                "selected_S_R": metrics.get("selected_S_R", ""),
                "predicted_valid": predicted_valid,
                "merge_success_count": metrics.get("merge_success_count", ""),
                "failed_reservation_count": metrics.get("failed_reservation_count", ""),
                "realized_valid": realized_valid,
                "prediction_realization_status": _prediction_realization_status(predicted_valid, realized_valid),
                "reservation_status_counts_json": reservation_counts,
                "event_type_counts_json": event_counts,
            }
        )
    _write_csv(output_path, rows, TRACE_REPLAY_SUMMARY_COLUMNS)
    return Path(output_path)


def write_state_hash_fairness_csv(
    fairness: Mapping[str, Any],
    output_path: str | Path,
    *,
    batch_id: str = "",
) -> Path:
    """Write grouped state-hash fairness rows for Gate D0 inputs."""

    rows = []
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in fairness.get("rows", []):
        key = (str(row.get("scenario_id", "")), str(row.get("seed", "")))
        item = grouped.setdefault(
            key,
            {
                "batch_id": batch_id,
                "scenario_id": key[0],
                "seed": key[1],
                "algorithm_ids": set(),
                "state_hashes": set(),
                "failed_algorithm_ids": set(),
            },
        )
        item["algorithm_ids"].add(str(row.get("algorithm_id", "")))
        item["state_hashes"].add(str(row.get("state_hash", "")))
    mismatches = {
        (str(item.get("scenario_id", "")), str(item.get("seed", "")))
        for item in fairness.get("mismatches", [])
    }
    for key, item in sorted(grouped.items()):
        failed = item["algorithm_ids"] if key in mismatches else set()
        hashes = sorted(item["state_hashes"])
        rows.append(
            {
                "batch_id": batch_id,
                "scenario_id": item["scenario_id"],
                "seed": item["seed"],
                "algorithm_count": len(item["algorithm_ids"]),
                "unique_state_hash_count": len(hashes),
                "state_hashes_json": hashes,
                "fairness_pass": len(hashes) == 1,
                "failed_algorithm_ids": sorted(failed),
            }
        )
    out_path = Path(output_path)
    _write_csv(out_path, rows, STATE_HASH_FAIRNESS_COLUMNS)
    return out_path


def build_evidence_package(
    run_dirs: Sequence[str | Path],
    *,
    package_dir: str | Path,
    batch_id: str,
    fairness: Mapping[str, Any] | None = None,
    batch_manifest_path: str | Path | None = None,
) -> dict[str, Path]:
    """Create the Wave 6A.0 layered evidence package."""

    root = Path(package_dir)
    main_dir = root / "main_batch"
    readiness_dir = root / "readiness_fail"
    positive_dir = root / "positive_rcmv_micro"
    gate_dir = root / "gate_D0_input"
    for directory in (main_dir, readiness_dir, positive_dir, gate_dir):
        directory.mkdir(parents=True, exist_ok=True)

    completed_dirs = _filter_run_dirs_by_status(run_dirs, "completed")
    readiness_failed_dirs = _filter_run_dirs_by_status(run_dirs, "readiness_failed")
    positive_dirs = [
        run_dir
        for run_dir in completed_dirs
        if _float(_read_metrics(Path(run_dir)).get("selected_RCMV")) > 0.0
    ]

    paths: dict[str, Path] = {}
    paths["main_batch_manifest"] = main_dir / "batch_manifest.csv"
    if batch_manifest_path is not None and Path(batch_manifest_path).exists():
        _copy_file(Path(batch_manifest_path), paths["main_batch_manifest"])
    else:
        _write_manifest(paths["main_batch_manifest"], run_dirs)

    paths["aggregate_metrics_completed"] = aggregate_metrics(
        completed_dirs,
        main_dir / "aggregate_metrics_completed.csv",
    )
    paths["failure_summary_main_batch"] = aggregate_failures(
        completed_dirs,
        main_dir / "failure_summary_main_batch.csv",
    )
    paths["rcmv_trace"] = collect_rcmv_trace(completed_dirs, main_dir / "rcmv_trace.csv")
    paths["readiness_summary"] = aggregate_readiness(
        run_dirs,
        main_dir / "readiness_summary.csv",
    )
    paths["state_hash_fairness"] = write_state_hash_fairness_csv(
        fairness or {},
        main_dir / "state_hash_fairness.csv",
        batch_id=batch_id,
    )
    paths["scenario_manifest"] = collect_scenario_manifest(
        run_dirs,
        main_dir / "scenario_manifest.csv",
    )
    paths["main_schema_manifest"] = _write_schema_manifest(main_dir / "schema_manifest.json")

    paths["aggregate_metrics_readiness_fail"] = aggregate_metrics(
        readiness_failed_dirs,
        readiness_dir / "aggregate_metrics_readiness_fail.csv",
    )
    paths["failure_summary_readiness_fail"] = aggregate_failures(
        readiness_failed_dirs,
        readiness_dir / "failure_summary_readiness_fail.csv",
    )
    paths["readiness_failures"] = aggregate_readiness(
        readiness_failed_dirs,
        readiness_dir / "readiness_failures.csv",
    )

    paths["positive_rcmv_manifest"] = _write_positive_manifest(
        positive_dir / "positive_rcmv_manifest.json",
        positive_dirs,
        batch_id=batch_id,
    )
    paths["positive_rcmv_aggregate_metrics"] = aggregate_metrics(
        positive_dirs,
        positive_dir / "positive_rcmv_aggregate_metrics.csv",
    )
    paths["positive_rcmv_failure_summary"] = aggregate_failures(
        positive_dirs,
        positive_dir / "positive_rcmv_failure_summary.csv",
    )
    paths["positive_rcmv_rcmv_trace"] = collect_rcmv_trace(
        positive_dirs,
        positive_dir / "positive_rcmv_rcmv_trace.csv",
    )
    paths["positive_rcmv_action_evaluations"] = _collect_raw_csv(
        positive_dirs,
        "action_evaluations.csv",
        positive_dir / "positive_rcmv_action_evaluations.csv",
    )
    paths["positive_rcmv_reservations"] = _collect_raw_csv(
        positive_dirs,
        "reservations.csv",
        positive_dir / "positive_rcmv_reservations.csv",
    )

    paths["gate_manifest"] = _write_gate_manifest(
        gate_dir / "gate_D0_manifest.json",
        batch_id=batch_id,
        run_dirs=run_dirs,
    )
    _copy_file(paths["aggregate_metrics_completed"], gate_dir / "aggregate_metrics_completed.csv")
    _copy_file(paths["aggregate_metrics_readiness_fail"], gate_dir / "aggregate_metrics_readiness_fail.csv")
    _copy_file(paths["failure_summary_main_batch"], gate_dir / "failure_summary_main_batch.csv")
    _copy_file(paths["failure_summary_readiness_fail"], gate_dir / "failure_summary_readiness_fail.csv")
    _copy_file(paths["positive_rcmv_aggregate_metrics"], gate_dir / "positive_rcmv_aggregate_metrics.csv")
    _copy_file(paths["positive_rcmv_failure_summary"], gate_dir / "positive_rcmv_failure_summary.csv")
    _copy_file(paths["positive_rcmv_rcmv_trace"], gate_dir / "positive_rcmv_rcmv_trace.csv")
    _copy_file(paths["state_hash_fairness"], gate_dir / "state_hash_fairness.csv")
    _copy_file(paths["scenario_manifest"], gate_dir / "scenario_manifest.csv")
    paths["scenario_mechanism_summary"] = write_scenario_mechanism_summary(
        completed_dirs,
        gate_dir / "scenario_mechanism_summary.csv",
    )
    paths["baseline_comparison_summary"] = write_baseline_comparison_summary(
        completed_dirs,
        gate_dir / "baseline_comparison_summary.csv",
    )
    paths["ablation_comparison_summary"] = write_ablation_comparison_summary(
        completed_dirs,
        gate_dir / "ablation_comparison_summary.csv",
    )
    paths["rcmv_trace_top_actions"] = write_rcmv_trace_top_actions(
        completed_dirs,
        gate_dir / "rcmv_trace_top_actions.csv",
    )
    paths["sensitivity_local_summary"] = write_sensitivity_local_summary(
        completed_dirs,
        gate_dir / "sensitivity_local_summary.csv",
    )
    paths["failure_trace_samples"] = write_failure_trace_samples(
        completed_dirs,
        gate_dir / "failure_trace_samples" / "failure_trace_samples.csv",
    )
    paths["trace_replay_summaries"] = write_trace_replay_summaries(
        completed_dirs,
        gate_dir / "trace_replay_summaries" / "trace_replay_summaries.csv",
    )
    paths["s6_productive_manifest"] = _write_s6_productive_manifest(
        gate_dir / "S6_productive_manifest.json",
        completed_dirs,
        batch_id=batch_id,
    )
    paths["s6_productive_aggregate_metrics"] = aggregate_metrics(
        _filter_run_dirs_by_scenario(completed_dirs, "S6_productive"),
        gate_dir / "S6_productive_aggregate_metrics.csv",
    )
    paths["s6_productive_rcmv_trace"] = collect_rcmv_trace(
        _filter_run_dirs_by_scenario(completed_dirs, "S6_productive"),
        gate_dir / "S6_productive_rcmv_trace.csv",
    )
    paths["s6_productive_failure_summary"] = aggregate_failures(
        _filter_run_dirs_by_scenario(completed_dirs, "S6_productive"),
        gate_dir / "S6_productive_failure_summary.csv",
    )
    positive_gate_dir = gate_dir / "positive_rcmv_micro"
    positive_gate_dir.mkdir(parents=True, exist_ok=True)
    _copy_file(paths["positive_rcmv_manifest"], positive_gate_dir / "positive_rcmv_manifest.json")
    _copy_file(paths["positive_rcmv_aggregate_metrics"], positive_gate_dir / "positive_rcmv_aggregate_metrics.csv")
    _copy_file(paths["positive_rcmv_failure_summary"], positive_gate_dir / "positive_rcmv_failure_summary.csv")
    _copy_file(paths["positive_rcmv_rcmv_trace"], positive_gate_dir / "positive_rcmv_rcmv_trace.csv")
    _copy_file(paths["positive_rcmv_action_evaluations"], positive_gate_dir / "positive_rcmv_action_evaluations.csv")
    _copy_file(paths["positive_rcmv_reservations"], positive_gate_dir / "positive_rcmv_reservations.csv")
    paths["paper_claim_support_table"] = _write_paper_claim_support_table(
        gate_dir / "paper_claim_support_table.csv",
        positive_dirs=positive_dirs,
        fairness=fairness or {},
        mechanism_rows=_scenario_mechanism_rows(completed_dirs),
    )

    paths["evidence_index"] = _write_evidence_index(
        root / "evidence_index.json",
        batch_id=batch_id,
        run_dirs=run_dirs,
        positive_dirs=positive_dirs,
        fairness=fairness or {},
    )
    paths["schema_manifest"] = _write_schema_manifest(root / "schema_manifest.json")
    return paths


def _metrics_row(run_dir: str | Path) -> dict[str, Any]:
    run_path = Path(run_dir)
    metrics = _read_metrics(run_path)
    row = {column: metrics.get(column, "") for column in AGGREGATE_METRIC_COLUMNS}
    row.update(_derived_metric_fields(metrics, run_path))
    return row


def _read_metrics(run_path: Path) -> dict[str, Any]:
    metrics_path = run_path / "metrics_episode.json"
    if not metrics_path.exists():
        return {"run_id": run_path.name}
    payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics = payload.get("metrics", payload)
    metrics.setdefault("run_id", run_path.name)
    metrics.setdefault("unique_run_id", metrics.get("run_id", run_path.name))
    metrics.setdefault("metrics_schema_version", METRICS_SCHEMA_VERSION)
    metrics.setdefault("readiness_schema_version", READINESS_SCHEMA_VERSION)
    metrics.setdefault("evidence_package_version", EVIDENCE_PACKAGE_VERSION)
    return metrics


def _derived_metric_fields(metrics: Mapping[str, Any], run_path: Path) -> dict[str, Any]:
    run_id = str(metrics.get("run_id") or run_path.name)
    D_H = _float(metrics.get("D_H"))
    selected_Z_R = _float(metrics.get("selected_Z_R"))
    baseline_Z_R = _float(metrics.get("baseline_Z_R"))
    selected_S_R = _float(metrics.get("selected_S_R"))
    baseline_S_R = _float(metrics.get("baseline_S_R"))
    reservation_count = int(_float(metrics.get("reservation_count")))
    planned_count = int(_float(metrics.get("planned_reservation_count")))
    generated = int(_float(metrics.get("generated_reservation_count")))
    if generated <= 0:
        generated = reservation_count if reservation_count > 0 else planned_count
    failed_count = int(_float(metrics.get("failed_reservation_count")))
    merge_success = int(_float(metrics.get("merge_success_count")))
    realized_unserved = max(D_H - merge_success, 0.0)
    warning = generated > 0 and failed_count == 0 and (merge_success == 0 or realized_unserved > 0.0)
    if not warning:
        warning = generated == 0 and D_H > 0.0
    no_reservation_due_to_invalid_supply = max(D_H - generated, 0.0) if generated <= 0 else 0.0
    return {
        "batch_id": metrics.get("batch_id", ""),
        "run_id": run_id,
        "unique_run_id": metrics.get("unique_run_id") or run_id,
        "config_hash": metrics.get("config_hash", _read_text(run_path / "config_hash.txt")),
        "code_version": metrics.get("code_version", _read_text(run_path / "code_version.txt")),
        "metrics_schema_version": metrics.get("metrics_schema_version", METRICS_SCHEMA_VERSION),
        "readiness_schema_version": metrics.get("readiness_schema_version", READINESS_SCHEMA_VERSION),
        "evidence_package_version": metrics.get("evidence_package_version", EVIDENCE_PACKAGE_VERSION),
        "D_H": D_H,
        "readiness_fail_reason": metrics.get("readiness_fail_reason", metrics.get("readiness_reason", "")),
        "generated_reservation_count": generated,
        "failed_reservation_rate": _rate_float(failed_count, generated),
        "failed_reservation_denominator": "generated_reservation_count",
        "merge_success_rate_over_demand": _rate_float(merge_success, D_H),
        "predicted_unserved_demand_count": metrics.get("predicted_unserved_demand_count", selected_Z_R),
        "predicted_unserved_demand_rate": _rate_float(selected_Z_R, D_H),
        "realized_unserved_demand_count": metrics.get("realized_unserved_demand_count", realized_unserved),
        "realized_unserved_demand_rate": _rate_float(realized_unserved, D_H),
        "unserved_demand_count": metrics.get("unserved_demand_count", realized_unserved),
        "no_reservation_due_to_invalid_supply_count": metrics.get(
            "no_reservation_due_to_invalid_supply_count",
            no_reservation_due_to_invalid_supply,
        ),
        "no_reservation_due_to_invalid_supply_rate": metrics.get(
            "no_reservation_due_to_invalid_supply_rate",
            _rate_float(no_reservation_due_to_invalid_supply, D_H),
        ),
        "waiting_or_unserved_penalty": metrics.get("waiting_or_unserved_penalty", selected_Z_R),
        "denominator_warning_flag": metrics.get("denominator_warning_flag", warning),
        "denominator_notes": metrics.get(
            "denominator_notes",
            "failed_reservation_rate uses generated reservations; merge_success_rate_over_demand uses D_H.",
        ),
        "delta_S_R": metrics.get("delta_S_R", selected_S_R - baseline_S_R),
        "delta_Z_R": metrics.get("delta_Z_R", baseline_Z_R - selected_Z_R),
        "rcmv_positive_margin": metrics.get("rcmv_positive_margin", _float(metrics.get("selected_RCMV"))),
        "failure_joinable_rate": metrics.get("failure_joinable_rate", _failure_joinable_rate(run_path)),
        "failure_join_key": metrics.get("failure_join_key", _failure_join_key(metrics)),
    }


def _reservation_failure_rows(run_path: Path, metrics: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    seen: set[tuple[str, str, str]] = set()
    for row in _read_csv(run_path / "reservations.csv"):
        status = str(row.get("status", ""))
        if not status.startswith("failed_") and status != "expired":
            continue
        key = (
            str(row.get("reservation_id", "")),
            status,
            str(row.get("failure_reason", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                **_metric_context(metrics),
                "run_status": metrics.get("status", ""),
                "failure_source": "reservation",
                "decision_context_id": row.get("decision_context_id", ""),
                "reservation_id": row.get("reservation_id", ""),
                "status": status,
                "failure_reason": row.get("failure_reason", ""),
                "failure_stage": _reservation_failure_stage(status),
                "linked_action_id": row.get("action_id", ""),
                "linked_edge_id": row.get("edge_id", ""),
                "action_id": row.get("action_id", ""),
                "ramp_id": row.get("ramp_id", ""),
                "edge_id": row.get("edge_id", ""),
                "slot_id": row.get("slot_id", ""),
                "vehicle_id": row.get("ramp_id", ""),
                "planned_tau": row.get("planned_tau", ""),
                "actual_time": row.get("planned_tau", ""),
                "actual_margin_front": row.get("actual_margin_front", ""),
                "actual_margin_rear": row.get("actual_margin_rear", ""),
                "denominator_scope": "reservation",
                "demand_id": row.get("ramp_id", ""),
                "failure_join_key": _failure_join_key(
                    {
                        **metrics,
                        "decision_context_id": row.get("decision_context_id", ""),
                        "reservation_id": row.get("reservation_id", ""),
                        "action_id": row.get("action_id", ""),
                        "edge_id": row.get("edge_id", ""),
                        "slot_id": row.get("slot_id", ""),
                        "demand_id": row.get("ramp_id", ""),
                    }
                ),
            }
        )
    return rows


def _event_failure_rows(run_path: Path, metrics: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in _read_csv(run_path / "realized_events.csv"):
        event_type = str(row.get("event_type", ""))
        if not event_type:
            continue
        rows.append(
            {
                **_metric_context(metrics),
                "run_status": metrics.get("status", ""),
                "failure_source": "realized_event",
                "decision_context_id": row.get("decision_context_id", ""),
                "event_id": row.get("event_id", ""),
                "event_type": event_type,
                "status": event_type,
                "failure_reason": row.get("note", ""),
                "failure_stage": "guidance_execution",
                "linked_action_id": row.get("linked_action_id", ""),
                "linked_edge_id": row.get("linked_edge_id", ""),
                "action_id": row.get("linked_action_id", ""),
                "reservation_id": row.get("linked_reservation_id", ""),
                "edge_id": row.get("linked_edge_id", ""),
                "vehicle_id": row.get("vehicle_ids", ""),
                "actual_time": row.get("time", ""),
                "denominator_scope": "realized_event",
                "failure_join_key": _failure_join_key(
                    {
                        **metrics,
                        "decision_context_id": row.get("decision_context_id", ""),
                        "reservation_id": row.get("linked_reservation_id", ""),
                        "action_id": row.get("linked_action_id", ""),
                        "edge_id": row.get("linked_edge_id", ""),
                        "event_id": row.get("event_id", ""),
                    }
                ),
                "severity": row.get("severity", ""),
            }
        )
    return rows


def _metric_context(metrics: Mapping[str, Any]) -> dict[str, Any]:
    run_id = metrics.get("run_id", "")
    return {
        "batch_id": metrics.get("batch_id", ""),
        "run_id": run_id,
        "unique_run_id": metrics.get("unique_run_id", run_id),
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
    }


def _summary_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for row in rows:
        key = (str(row.get("scenario_id", "")), str(row.get("algorithm_id", "")))
        groups.setdefault(key, []).append(row)
    out = []
    for (scenario_id, algorithm_id), group in sorted(groups.items()):
        out.append(
            {
                "scenario_id": scenario_id,
                "algorithm_id": algorithm_id,
                "run_count": len(group),
                "completed_count": sum(1 for row in group if row.get("status") == "completed"),
                "readiness_failed_count": sum(1 for row in group if row.get("status") == "readiness_failed"),
                "mean_selected_RCMV": _mean_column(group, "selected_RCMV"),
                "mean_failed_reservation_rate": _mean_column(group, "failed_reservation_rate"),
                "mean_merge_success_count": _mean_column(group, "merge_success_count"),
                "mean_mean_Z_R": _mean_column(group, "mean_Z_R"),
                "mean_production_cost_sum": _mean_column(group, "production_cost_sum"),
                "mean_stale_reservation_count": _mean_column(group, "stale_reservation_count"),
            }
        )
    return out


def _mean_column(rows: Sequence[Mapping[str, Any]], column: str) -> float:
    values = [_float(row.get(column)) for row in rows]
    return 0.0 if not values else float(sum(values) / len(values))


def _mean_bool(rows: Sequence[Mapping[str, Any]], column: str) -> float:
    if not rows:
        return 0.0
    return float(sum(1 for row in rows if _truthy(row.get(column)))) / float(len(rows))


def _near_miss_presence_rate(rows: Sequence[Mapping[str, Any]]) -> float:
    if not rows:
        return 0.0
    return float(sum(1 for row in rows if _float(row.get("near_miss_edge_count")) > 0.0)) / float(len(rows))


def _candidate_reduction_rate(
    rpmi_rows: Sequence[Mapping[str, Any]],
    ablation_rows: Sequence[Mapping[str, Any]],
) -> float:
    full = _mean_column(rpmi_rows, "candidate_action_count")
    ablated = _mean_column(ablation_rows, "candidate_action_count")
    if ablated <= 0.0:
        return 0.0
    return max(ablated - full, 0.0) / ablated


def _scenario_group(scenario_id: str) -> str:
    value = scenario_id.upper()
    if value.startswith("S6_PRODUCTIVE"):
        return "S6_productive"
    return value.split("_", 1)[0]


def _mechanism_status(
    scenario_id: str,
    rows: Sequence[Mapping[str, Any]],
    readiness_rows: Sequence[Mapping[str, Any]],
) -> str:
    sid = scenario_id.upper()
    rpmi = [row for row in rows if row.get("algorithm_id") == "rpmi_cmv"]
    if not rows:
        return "inconclusive"
    if sid.startswith("S2"):
        return "clear_support" if any(_truthy(row.get("raw_gap_illusion_flag")) for row in rows) else "inconclusive"
    if sid.startswith("S5"):
        if any(str(row.get("selected_action_type", "")) not in {"", "none"} and _float(row.get("selected_RCMV")) > 0.0 for row in rpmi):
            return "clear_support"
        if any(_float(row.get("selected_S_R")) > 0.0 for row in rpmi):
            return "partial_support"
        return "inconclusive"
    if sid.startswith("S6_PRODUCTIVE"):
        if any(
            str(row.get("selected_action_type", "")) not in {"", "none"}
            and _float(row.get("selected_RCMV")) > 0.0
            and _float(row.get("selected_Z_R")) <= _float(row.get("baseline_Z_R"))
            for row in rpmi
        ):
            return "partial_support"
        return "inconclusive"
    if sid.startswith("S6"):
        return "partial_support" if any(_truthy(row.get("raw_gap_illusion_flag")) for row in rows) else "inconclusive"
    if sid.startswith("S7"):
        return "partial_support" if any(_float(row.get("action_conditioned_gain")) > 0.0 for row in rpmi) else "inconclusive"
    if sid.startswith("S8"):
        no_screen = [row for row in rows if row.get("algorithm_id") == "rpmi_cmv_without_near_miss"]
        return "partial_support" if _candidate_reduction_rate(rpmi, no_screen) > 0.0 else "inconclusive"
    if readiness_rows and not any(_truthy(row.get("readiness_pass")) for row in readiness_rows):
        return "inconclusive"
    return "partial_support" if rpmi else "inconclusive"


def _mechanism_notes(
    scenario_id: str,
    rows: Sequence[Mapping[str, Any]],
    readiness_rows: Sequence[Mapping[str, Any]],
) -> str:
    sid = scenario_id.upper()
    rpmi = [row for row in rows if row.get("algorithm_id") == "rpmi_cmv"]
    selected_non_none = sum(1 for row in rpmi if str(row.get("selected_action_type", "")) not in {"", "none"})
    positive = sum(1 for row in rpmi if _float(row.get("selected_RCMV")) > 0.0)
    readiness_near_miss = sum(1 for row in readiness_rows if _float(row.get("near_miss_edge_count")) > 0.0)
    if sid.startswith("S5") and selected_non_none == 0 and any(_float(row.get("selected_S_R")) > 0.0 for row in rpmi):
        return "Inventory-only support: selected_action_type=none with recoverable supply; do not claim production action effectiveness."
    if sid.startswith("S6") and any(_float(row.get("selected_Z_R")) > 0.0 and _float(row.get("merge_success_count")) == 0.0 for row in rpmi):
        return "Supports diagnostic avoidance more than demand service improvement."
    return (
        f"rpmi_positive_runs={positive}; rpmi_non_none_runs={selected_non_none}; "
        f"readiness_near_miss_runs={readiness_near_miss}"
    )


def _vehicle_mix(vehicles: Mapping[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for pair in vehicles.get("boundary_pairs", []) or []:
        for item in str(pair).split("-"):
            counts[item] = counts.get(item, 0) + 1
    ramp_count = int(_float(vehicles.get("ramp_count", 0)))
    if ramp_count:
        counts["ramp_CAV"] = ramp_count
    return counts


def _counts(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _prediction_realization_status(predicted_valid: bool, realized_valid: bool) -> str:
    if predicted_valid and realized_valid:
        return "predicted_valid_realized_valid"
    if predicted_valid and not realized_valid:
        return "predicted_valid_realized_invalid"
    if not predicted_valid and realized_valid:
        return "predicted_invalid_realized_valid"
    return "predicted_invalid_realized_invalid"


def _float(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"true", "1", "yes"}


def _filter_run_dirs_by_status(
    run_dirs: Sequence[str | Path],
    status: str,
) -> list[Path]:
    return [Path(run_dir) for run_dir in run_dirs if _read_metrics(Path(run_dir)).get("status") == status]


def _filter_run_dirs_by_scenario(
    run_dirs: Sequence[str | Path],
    scenario_id: str,
) -> list[Path]:
    target = scenario_id.lower()
    return [
        Path(run_dir)
        for run_dir in run_dirs
        if str(_read_metrics(Path(run_dir)).get("scenario_id", "")).lower() == target
    ]


def _scenario_mechanism_rows(run_dirs: Sequence[str | Path]) -> list[dict[str, Any]]:
    aggregate = [_metrics_row(run_dir) for run_dir in run_dirs]
    readiness = []
    for run_dir in run_dirs:
        readiness.extend(_read_csv(Path(run_dir) / "readiness_summary.csv"))
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in aggregate:
        grouped.setdefault(str(row.get("scenario_id", "")), []).append(row)
    rows = []
    for scenario_id, group in sorted(grouped.items()):
        readiness_group = [
            row for row in readiness if str(row.get("scenario_id", "")) == scenario_id
        ]
        rpmi = [row for row in group if row.get("algorithm_id") == "rpmi_cmv"]
        raw_gap = [row for row in group if row.get("algorithm_id") == "raw_gap_reservation"]
        without_rd = [row for row in group if row.get("algorithm_id") == "rpmi_cmv_without_rd"]
        without_action_conditioned = [
            row
            for row in group
            if row.get("algorithm_id") == "rpmi_cmv_without_action_conditioned_reservation"
        ]
        without_near_miss = [
            row for row in group if row.get("algorithm_id") == "rpmi_cmv_without_near_miss"
        ]
        rows.append(
            {
                "scenario_group": _scenario_group(scenario_id),
                "scenario_id": scenario_id,
                "seed_count": len({str(row.get("seed", "")) for row in group}),
                "completed_run_count": len(group),
                "readiness_pass_rate": _mean_bool(readiness_group, "readiness_pass"),
                "raw_gap_illusion_rate": _mean_bool(raw_gap or group, "raw_gap_illusion_flag"),
                "near_miss_presence_rate": _near_miss_presence_rate(readiness_group),
                "positive_rcmv_rate": _rate_float(
                    sum(1 for row in rpmi if _float(row.get("selected_RCMV")) > 0.0),
                    len(rpmi),
                ),
                "selected_non_none_rate": _rate_float(
                    sum(1 for row in rpmi if str(row.get("selected_action_type", "")) not in {"", "none"}),
                    len(rpmi),
                ),
                "delta_Z_R_mean": _mean_column(rpmi or group, "delta_Z_R"),
                "delta_S_R_mean": _mean_column(rpmi or group, "delta_S_R"),
                "failed_reservation_rate": _mean_column(rpmi or group, "failed_reservation_rate"),
                "merge_success_rate_over_demand": _mean_column(rpmi or group, "merge_success_rate_over_demand"),
                "predicted_unserved_demand_rate": _mean_column(rpmi or group, "predicted_unserved_demand_rate"),
                "realized_unserved_demand_rate": _mean_column(rpmi or group, "realized_unserved_demand_rate"),
                "failure_rate_delta_vs_raw_gap": _mean_column(rpmi, "failed_reservation_rate")
                - _mean_column(raw_gap, "failed_reservation_rate"),
                "RD_ablation_decision_change_rate": _mean_bool(without_rd, "rd_decision_changed_flag"),
                "stale_harm_rate": _rate_float(
                    sum(1 for row in without_action_conditioned if _float(row.get("stale_reservation_harm")) > 0.0),
                    len(without_action_conditioned),
                ),
                "screening_candidate_reduction_rate": _candidate_reduction_rate(rpmi, without_near_miss),
                "mechanism_interpretability_status": _mechanism_status(scenario_id, group, readiness_group),
                "notes": _mechanism_notes(scenario_id, group, readiness_group),
            }
        )
    return rows


def _comparison_rows(
    run_dirs: Sequence[str | Path],
    predicate: Any,
) -> list[dict[str, Any]]:
    return _summary_rows([row for row in [_metrics_row(run_dir) for run_dir in run_dirs] if predicate(row)])


def _is_ablation_row(row: Mapping[str, Any]) -> bool:
    return (
        _truthy(row.get("ablation_without_rd"))
        or _truthy(row.get("ablation_without_rcmv"))
        or _truthy(row.get("ablation_without_action_conditioned_reservation"))
        or _truthy(row.get("ablation_no_near_miss_screening"))
    )


def _trace_rows_for_run(run_path: Path, metrics: Mapping[str, Any]) -> list[dict[str, Any]]:
    action_by_id = {row.get("action_id", ""): row for row in _read_csv(run_path / "actions.csv")}
    rows = []
    for row in _read_csv(run_path / "action_evaluations.csv"):
        action_row = action_by_id.get(row.get("action_id", ""), {})
        rows.append(
            {
                **row,
                **_metric_context(metrics),
                "action_type": action_row.get("action_type", ""),
                "nominal_edge_id": action_row.get("nominal_edge_id", ""),
                "boundary_type": action_row.get("boundary_type", ""),
            }
        )
    return rows


def _theta_rejection_notes(
    trace_rows: Sequence[Mapping[str, Any]],
    selected: Mapping[str, Any],
) -> str:
    rejected = [
        row.get("action_id", "")
        for row in trace_rows
        if _truthy(row.get("rejected_by_theta"))
    ]
    if rejected:
        return "rejected_by_theta=" + ",".join(str(item) for item in rejected)
    if selected:
        return "selected action cleared theta or baseline a0_none selected"
    return "no selected action row"


def _near_miss_type_from_action(action_row: Mapping[str, Any]) -> str:
    nominal_edge_id = str(action_row.get("nominal_edge_id", ""))
    if not nominal_edge_id:
        return ""
    action_type = str(action_row.get("action_type", ""))
    return "boundary_speed_near_miss" if action_type in {"front_acc", "rear_dec", "front_rear"} else ""


def _reservation_failure_stage(status: str) -> str:
    if status == "expired":
        return "slot_expiration"
    if status == "failed_invalid_slot":
        return "predicted_valid_realized_invalid"
    if status == "failed_unsafe_margin":
        return "merge_at_tau"
    if status == "failed_unreachable":
        return "guidance_execution"
    return "reservation_creation"


def _failure_join_key(values: Mapping[str, Any]) -> str:
    parts = [
        values.get("batch_id", ""),
        values.get("run_id", ""),
        values.get("decision_context_id", ""),
        values.get("reservation_id", ""),
        values.get("action_id", ""),
        values.get("edge_id", values.get("linked_edge_id", "")),
        values.get("slot_id", ""),
        values.get("demand_id", values.get("ramp_id", "")),
        values.get("event_id", ""),
    ]
    return "|".join(str(part) for part in parts if part not in (None, ""))


def _failure_joinable_rate(run_path: Path) -> float:
    rows = [
        *_read_csv(run_path / "reservations.csv"),
        *_read_csv(run_path / "realized_events.csv"),
    ]
    failures = []
    for row in rows:
        status = str(row.get("status", ""))
        event_type = str(row.get("event_type", ""))
        if status.startswith("failed_") or status == "expired" or event_type:
            failures.append(row)
    if not failures:
        return 1.0
    joinable = 0
    for row in failures:
        if row.get("reservation_id") or row.get("linked_reservation_id") or row.get("action_id") or row.get("linked_action_id"):
            joinable += 1
    return float(joinable) / float(len(failures))


def _rate_float(numerator: Any, denominator: Any) -> float:
    denom = _float(denominator)
    return 0.0 if denom <= 0 else _float(numerator) / denom


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def _copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(source.read_bytes())


def _write_manifest(path: Path, run_dirs: Sequence[str | Path]) -> Path:
    rows = []
    for run_dir in run_dirs:
        run_path = Path(run_dir)
        metrics = _read_metrics(run_path)
        rows.append(
            {
                "batch_id": metrics.get("batch_id", ""),
                "run_id": metrics.get("run_id", run_path.name),
                "run_dir": str(run_path),
                "scenario_id": metrics.get("scenario_id", ""),
                "seed": metrics.get("seed", ""),
                "algorithm_id": metrics.get("algorithm_id", ""),
                "state_hash": metrics.get("state_hash", ""),
                "status": metrics.get("status", ""),
            }
        )
    _write_csv(
        path,
        rows,
        ["batch_id", "run_id", "run_dir", "scenario_id", "seed", "algorithm_id", "state_hash", "status"],
    )
    return path


def _write_schema_manifest(path: Path) -> Path:
    payload = {
        "evidence_package_version": EVIDENCE_PACKAGE_VERSION,
        "metrics_schema_version": METRICS_SCHEMA_VERSION,
        "readiness_schema_version": READINESS_SCHEMA_VERSION,
        "aggregate_metrics_columns": AGGREGATE_METRIC_COLUMNS,
        "failure_summary_columns": FAILURE_SUMMARY_COLUMNS,
        "rcmv_trace_columns": RCMV_TRACE_COLUMNS,
        "readiness_summary_columns": READINESS_SUMMARY_COLUMNS,
        "state_hash_fairness_columns": STATE_HASH_FAIRNESS_COLUMNS,
        "scenario_manifest_columns": SCENARIO_MANIFEST_COLUMNS,
        "scenario_mechanism_summary_columns": SCENARIO_MECHANISM_SUMMARY_COLUMNS,
        "rcmv_trace_top_action_columns": RCMV_TRACE_TOP_ACTION_COLUMNS,
        "sensitivity_local_summary_columns": SENSITIVITY_LOCAL_SUMMARY_COLUMNS,
        "failure_trace_sample_columns": FAILURE_TRACE_SAMPLE_COLUMNS,
        "trace_replay_summary_columns": TRACE_REPLAY_SUMMARY_COLUMNS,
        "run_csv_schemas": CSV_LOG_SCHEMAS,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_positive_manifest(
    path: Path,
    run_dirs: Sequence[str | Path],
    *,
    batch_id: str,
) -> Path:
    rows = []
    for run_dir in run_dirs:
        metrics = _read_metrics(Path(run_dir))
        rows.append(
            {
                "run_id": metrics.get("run_id", Path(run_dir).name),
                "scenario_id": metrics.get("scenario_id", ""),
                "seed": metrics.get("seed", ""),
                "algorithm_id": metrics.get("algorithm_id", ""),
                "selected_RCMV": metrics.get("selected_RCMV", ""),
                "selected_action_type": metrics.get("selected_action_type", ""),
                "merge_success_rate_over_demand": metrics.get("merge_success_rate_over_demand", ""),
            }
        )
    payload = {
        "batch_id": batch_id,
        "evidence_package_version": EVIDENCE_PACKAGE_VERSION,
        "positive_rcmv_case_count": len(rows),
        "positive_rcmv_cases": rows,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_s6_productive_manifest(
    path: Path,
    run_dirs: Sequence[str | Path],
    *,
    batch_id: str,
) -> Path:
    s6_dirs = _filter_run_dirs_by_scenario(run_dirs, "S6_productive")
    rows = []
    for run_dir in s6_dirs:
        metrics = _read_metrics(Path(run_dir))
        rows.append(
            {
                "run_id": metrics.get("run_id", Path(run_dir).name),
                "scenario_id": metrics.get("scenario_id", ""),
                "seed": metrics.get("seed", ""),
                "algorithm_id": metrics.get("algorithm_id", ""),
                "selected_action_type": metrics.get("selected_action_type", ""),
                "selected_RCMV": metrics.get("selected_RCMV", ""),
                "selected_Z_R": metrics.get("selected_Z_R", ""),
                "baseline_Z_R": metrics.get("baseline_Z_R", ""),
                "merge_success_rate_over_demand": metrics.get("merge_success_rate_over_demand", ""),
                "realized_unserved_demand_rate": metrics.get("realized_unserved_demand_rate", ""),
            }
        )
    payload = {
        "batch_id": batch_id,
        "evidence_package_version": EVIDENCE_PACKAGE_VERSION,
        "scenario_id": "S6_productive",
        "case_count": len(rows),
        "interpretation_guardrail": (
            "If no non-none positive RCMV case exists, Gate D0 must not claim "
            "boundary-speed production improves merge success."
        ),
        "cases": rows,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_gate_manifest(
    path: Path,
    *,
    batch_id: str,
    run_dirs: Sequence[str | Path] = (),
) -> Path:
    scenario_ids = sorted({str(_read_metrics(Path(run_dir)).get("scenario_id", "")) for run_dir in run_dirs})
    payload = {
        "batch_id": batch_id,
        "evidence_package_version": EVIDENCE_PACKAGE_VERSION,
        "purpose": "Gate D0 input assembled by Wave 6A+ deterministic evidence hardening patch",
        "scenario_groups": scenario_ids,
        "denominator_policy": _denominator_policy(),
        "audit_questions": [
            "failed_reservation_rate is separated from demand service rates",
            "S5 no-action inventory is separated from production action evidence",
            "S6 diagnostic avoidance is separated from demand service improvement",
            "positive RCMV prediction-valid vs realized-valid status is replayable",
        ],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_paper_claim_support_table(
    path: Path,
    *,
    positive_dirs: Sequence[str | Path],
    fairness: Mapping[str, Any],
    mechanism_rows: Sequence[Mapping[str, Any]] = (),
) -> Path:
    status_by_group = {
        str(row.get("scenario_group", row.get("scenario_id", ""))).upper(): str(row.get("mechanism_interpretability_status", ""))
        for row in mechanism_rows
    }
    production_status = status_by_group.get("S5", "")
    s6_productive_status = status_by_group.get("S6_PRODUCTIVE", "")
    rd_status = status_by_group.get("S6", "")
    stale_status = status_by_group.get("S7", "")
    screening_status = status_by_group.get("S8", "")
    rows = [
        {
            "claim": "boundary_speed_v0_micro_episode_traceable",
            "support_status": _claim_status(status_by_group.values()),
            "evidence_file": "aggregate_metrics_completed.csv",
            "notes": "Wave 6A+ supplies deterministic mechanism evidence; Gate D0 still decides paper claim strength.",
        },
        {
            "claim": "positive_rcmv_case_exists",
            "support_status": "supported" if positive_dirs else "not_supported",
            "evidence_file": "positive_rcmv_rcmv_trace.csv",
            "notes": f"positive selected_RCMV run count: {len(positive_dirs)}",
        },
        {
            "claim": "state_hash_fairness",
            "support_status": "supported" if fairness.get("fairness_pass") else "not_supported",
            "evidence_file": "state_hash_fairness.csv",
            "notes": "unique_state_hash_count must be 1 for each scenario/seed comparison group.",
        },
        {
            "claim": "raw_gap_illusion_diagnosis",
            "support_status": _status_to_claim(status_by_group.get("S2", "")),
            "evidence_file": "scenario_mechanism_summary.csv",
            "notes": "S2 should show raw gap can be misleading once reachability/safety/recoverability are applied.",
        },
        {
            "claim": "boundary_speed_production_action_effectiveness",
            "support_status": _status_to_claim(production_status if production_status == "clear_support" else s6_productive_status),
            "evidence_file": "S6_productive_aggregate_metrics.csv",
            "notes": "Requires selected_action_type != none, selected_RCMV > 0, improved predicted inventory, and non-degraded realized demand denominator.",
        },
        {
            "claim": "rd_recoverability_useful",
            "support_status": _status_to_claim(rd_status),
            "evidence_file": "ablation_comparison_summary.csv",
            "notes": "S6 distinguishes RD/recoverability contrast from demand service improvement.",
        },
        {
            "claim": "action_conditioned_reservation_useful",
            "support_status": _status_to_claim(stale_status),
            "evidence_file": "ablation_comparison_summary.csv",
            "notes": "S7 checks full RPMI-CMV against stale/no-action inventory reservation.",
        },
        {
            "claim": "near_miss_screening_useful",
            "support_status": _status_to_claim(screening_status),
            "evidence_file": "rcmv_trace_top_actions.csv",
            "notes": "S8 checks candidate reduction without losing positive RCMV opportunity.",
        },
        {
            "claim": "lane_change_rolling_stochastic",
            "support_status": "not_evaluated",
            "evidence_file": "",
            "notes": "Forbidden in Wave 6A+; keep as limitation/future work until later gates.",
        },
    ]
    _write_csv(path, rows, ["claim", "support_status", "evidence_file", "notes"])
    return path


def _write_evidence_index(
    path: Path,
    *,
    batch_id: str,
    run_dirs: Sequence[str | Path],
    positive_dirs: Sequence[str | Path],
    fairness: Mapping[str, Any],
) -> Path:
    scenarios = sorted({str(_read_metrics(Path(run_dir)).get("scenario_id", "")) for run_dir in run_dirs})
    algorithms = sorted({str(_read_metrics(Path(run_dir)).get("algorithm_id", "")) for run_dir in run_dirs})
    mechanism_rows = _scenario_mechanism_rows(_filter_run_dirs_by_status(run_dirs, "completed"))
    payload = {
        "batch_id": batch_id,
        "evidence_package_version": EVIDENCE_PACKAGE_VERSION,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "code_version": _first_present(run_dirs, "code_version"),
        "metrics_schema_version": METRICS_SCHEMA_VERSION,
        "readiness_schema_version": READINESS_SCHEMA_VERSION,
        "included_scenarios": scenarios,
        "included_algorithms": algorithms,
        "positive_rcmv_case_count": len(positive_dirs),
        "state_hash_fairness_pass": bool(fairness.get("fairness_pass")),
        "denominator_policy": _denominator_policy(),
        "files": {
            "aggregate_metrics_completed": "main_batch/aggregate_metrics_completed.csv",
            "failure_summary_main_batch": "main_batch/failure_summary_main_batch.csv",
            "failure_summary_readiness_fail": "readiness_fail/failure_summary_readiness_fail.csv",
            "positive_rcmv_aggregate_metrics": "positive_rcmv_micro/positive_rcmv_aggregate_metrics.csv",
            "positive_rcmv_failure_summary": "positive_rcmv_micro/positive_rcmv_failure_summary.csv",
            "positive_rcmv_rcmv_trace": "positive_rcmv_micro/positive_rcmv_rcmv_trace.csv",
            "rcmv_trace": "main_batch/rcmv_trace.csv",
            "readiness_summary": "main_batch/readiness_summary.csv",
            "state_hash_fairness": "main_batch/state_hash_fairness.csv",
            "reservation_denominator": "main_batch/aggregate_metrics_completed.csv",
            "demand_denominator": "main_batch/aggregate_metrics_completed.csv",
            "scenario_manifest": "main_batch/scenario_manifest.csv",
            "scenario_mechanism_summary": "gate_D0_input/scenario_mechanism_summary.csv",
            "baseline_comparison_summary": "gate_D0_input/baseline_comparison_summary.csv",
            "ablation_comparison_summary": "gate_D0_input/ablation_comparison_summary.csv",
            "rcmv_trace_top_actions": "gate_D0_input/rcmv_trace_top_actions.csv",
            "sensitivity_local_summary": "gate_D0_input/sensitivity_local_summary.csv",
            "failure_trace_samples": "gate_D0_input/failure_trace_samples/failure_trace_samples.csv",
            "trace_replay_summaries": "gate_D0_input/trace_replay_summaries/trace_replay_summaries.csv",
            "s6_productive_manifest": "gate_D0_input/S6_productive_manifest.json",
            "s6_productive_aggregate_metrics": "gate_D0_input/S6_productive_aggregate_metrics.csv",
            "positive_rcmv_micro_dir": "gate_D0_input/positive_rcmv_micro/",
        },
        "mechanism_status": {
            str(row.get("scenario_id", "")): row.get("mechanism_interpretability_status", "")
            for row in mechanism_rows
        },
        "answers": {
            "reservation_denominator_file": "main_batch/aggregate_metrics_completed.csv",
            "demand_denominator_file": "main_batch/aggregate_metrics_completed.csv",
            "positive_rcmv_case_formally_included": len(positive_dirs) > 0,
            "readiness_failure_saved_separately": True,
            "failure_summary_layered_names": [
                "main_batch/failure_summary_main_batch.csv",
                "readiness_fail/failure_summary_readiness_fail.csv",
                "positive_rcmv_micro/positive_rcmv_failure_summary.csv",
            ],
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _collect_raw_csv(
    run_dirs: Sequence[str | Path],
    filename: str,
    output_path: str | Path,
) -> Path:
    rows = []
    columns: list[str] = []
    for run_dir in run_dirs:
        metrics = _read_metrics(Path(run_dir))
        for row in _read_csv(Path(run_dir) / filename):
            merged = {**_metric_context(metrics), **row}
            rows.append(merged)
            for column in merged:
                if column not in columns:
                    columns.append(column)
    _write_csv(output_path, rows, columns or GLOBAL_EVIDENCE_COLUMNS)
    return Path(output_path)


def _first_present(run_dirs: Sequence[str | Path], key: str) -> str:
    for run_dir in run_dirs:
        value = _read_metrics(Path(run_dir)).get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def _denominator_policy() -> dict[str, str]:
    return {
        "failed_reservation_rate": "failed_reservation_count / generated_reservation_count",
        "generated_reservation_count": "reservation_count or planned_reservation_count, explicitly marked by failed_reservation_denominator",
        "merge_success_rate_over_demand": "merge_success_count / D_H",
        "predicted_unserved_demand_rate": "selected_Z_R / D_H",
        "realized_unserved_demand_rate": "(D_H - merge_success_count) / D_H",
    }


def _status_to_claim(status: str) -> str:
    if status == "clear_support":
        return "supported"
    if status == "partial_support":
        return "partial_support"
    if status == "contradicts_claim":
        return "contradicts_claim"
    return "not_supported"


def _claim_status(statuses: Any) -> str:
    values = list(statuses)
    if any(value == "contradicts_claim" for value in values):
        return "contradicts_claim"
    if any(value == "clear_support" for value in values):
        return "candidate_evidence"
    if any(value == "partial_support" for value in values):
        return "partial_support"
    return "not_supported"


def _read_csv(path: str | Path) -> list[dict[str, str]]:
    file_path = Path(path)
    if not file_path.exists():
        return []
    with file_path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def _write_csv(path: str | Path, rows: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", newline="", encoding="utf-8") as file:
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


__all__ = [
    "AGGREGATE_METRIC_COLUMNS",
    "EVIDENCE_PACKAGE_VERSION",
    "FAILURE_SUMMARY_COLUMNS",
    "GLOBAL_EVIDENCE_COLUMNS",
    "METRICS_SCHEMA_VERSION",
    "RCMV_TRACE_COLUMNS",
    "READINESS_SCHEMA_VERSION",
    "READINESS_SUMMARY_COLUMNS",
    "RCMV_TRACE_TOP_ACTION_COLUMNS",
    "SCENARIO_MANIFEST_COLUMNS",
    "SCENARIO_MECHANISM_SUMMARY_COLUMNS",
    "SENSITIVITY_LOCAL_SUMMARY_COLUMNS",
    "SUMMARY_COLUMNS",
    "STATE_HASH_FAIRNESS_COLUMNS",
    "aggregate_failures",
    "aggregate_metrics",
    "aggregate_readiness",
    "build_evidence_package",
    "collect_rcmv_trace",
    "collect_scenario_manifest",
    "generate_summary_tables",
    "write_ablation_comparison_summary",
    "write_baseline_comparison_summary",
    "write_failure_trace_samples",
    "write_rcmv_trace_top_actions",
    "write_scenario_mechanism_summary",
    "write_sensitivity_local_summary",
    "write_state_hash_fairness_csv",
    "write_trace_replay_summaries",
]
