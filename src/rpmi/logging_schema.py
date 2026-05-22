"""Empty log schemas for Phase 0 run initialization."""

from __future__ import annotations

from pathlib import Path
import csv
import json


SHARED_COLUMNS = [
    "run_id",
    "step",
    "time",
    "decision_context_id",
    "state_hash",
    "config_hash",
    "code_version",
    "units_version",
]


CSV_LOG_SCHEMAS: dict[str, list[str]] = {
    "readiness_summary.csv": SHARED_COLUMNS
    + [
        "batch_id",
        "unique_run_id",
        "config_hash",
        "code_version",
        "metrics_schema_version",
        "readiness_schema_version",
        "evidence_package_version",
        "scenario_id",
        "seed",
        "algorithm_id",
        "readiness_pass",
        "readiness_reason",
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
        "readiness_fail_reasons",
        "failed_attempts",
        "algorithm_independent",
    ],
    "vehicles_step.csv": SHARED_COLUMNS
    + [
        "vehicle_id",
        "role",
        "veh_type",
        "lane",
        "x",
        "v",
        "a",
        "length",
        "a_nominal",
        "a_action",
        "a_eff",
        "speed_floor_clip",
        "leader_id",
        "gap_to_leader",
        "controlled_by_action_id",
        "reservation_id",
        "invalid_overlap_flag",
    ],
    "slots.csv": SHARED_COLUMNS
    + [
        "slot_id",
        "front_id",
        "rear_id",
        "k",
        "tau",
        "physical_gap_id",
        "eval_context",
        "action_id",
        "gap_at_tau",
        "boundary_type",
    ],
    "edges.csv": SHARED_COLUMNS
    + [
        "edge_id",
        "ramp_id",
        "slot_id",
        "front_id",
        "rear_id",
        "k",
        "tau",
        "eval_context",
        "action_id",
        "physical_gap_id",
        "I_reach",
        "I_surv",
        "I_safe",
        "I_rec",
        "P_R",
        "V_phys_theory",
        "V_phys_buffer",
        "W",
        "delta_W_req",
        "RD",
        "rd_components_json",
        "is_reservable",
        "reason_not_reservable",
        "fail_reason_priority",
        "surv_mode",
        "validity_mode",
    ],
    "near_miss_edges.csv": SHARED_COLUMNS
    + [
        "edge_id",
        "near_miss_label",
        "near_miss_reason",
    ],
    "actions.csv": SHARED_COLUMNS
    + [
        "action_id",
        "action_type",
        "nominal_edge_id",
        "controlled_cavs",
        "target_gap_id",
        "boundary_type",
        "control_start",
        "control_end",
        "requested_delta_W",
        "delta_W_target",
        "T_prod",
        "u_front",
        "u_rear",
        "profile_clip_flag",
        "estimated_delta_W_after_clip",
        "action_profile_feasible",
        "estimated_cost",
        "rejected_before_rollout",
        "reject_reason",
        "lc_from_lane",
        "lc_to_lane",
        "lc_start_time",
        "lc_end_time",
        "lc_duration",
        "receiving_gap_id",
        "lc_feasibility_pass",
        "lc_reject_reason",
        "lc_cost_components_json",
        "lc_mode",
    ],
    "action_evaluations.csv": SHARED_COLUMNS
    + [
        "action_id",
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
        "lane_change_candidate_id",
        "lc_cost",
        "lc_feasibility_margin_front",
        "lc_feasibility_margin_rear",
        "lc_expected_gap_effect",
    ],
    "matching.csv": SHARED_COLUMNS
    + [
        "matching_id",
        "edge_id",
        "slot_id",
        "ramp_id",
        "matched",
        "conflict_mode",
        "match_reason",
        "tau",
        "physical_gap_id",
        "P_R",
        "RD",
        "weight",
    ],
    "reservations.csv": SHARED_COLUMNS
    + [
        "reservation_id",
        "ramp_id",
        "edge_id",
        "slot_id",
        "action_id",
        "planned_tau",
        "planned_merge_x",
        "planned_interval_lower",
        "planned_interval_upper",
        "actual_x_at_tau",
        "actual_margin_front",
        "actual_margin_rear",
        "status",
        "failure_reason",
        "stale_flag",
    ],
    "realized_events.csv": SHARED_COLUMNS
    + [
        "realized_event_id",
        "event_id",
        "scenario_id",
        "seed",
        "algorithm_id",
        "linked_action_id",
        "linked_edge_id",
        "linked_gap_id",
        "linked_reservation_id",
        "linked_demand_id",
        "ramp_vehicle_id",
        "event_time",
        "event_type",
        "event_severity",
        "merge_success",
        "event_reason",
        "vehicle_ids",
        "min_gap",
        "min_margin",
        "severity",
        "note",
    ],
    "event_metric_windows.csv": SHARED_COLUMNS
    + [
        "realized_event_id",
        "metric_window_start",
        "metric_window_end",
        "hard_brake_count",
        "max_deceleration",
        "max_deceleration_magnitude",
        "mean_abs_acceleration",
        "speed_variance_before",
        "speed_variance_after",
        "speed_variance_delta",
        "max_wave_amplitude",
        "mainline_disturbance_cost",
        "min_TTC",
        "unsafe_overlap_count",
        "RD_realized_proxy",
        "RD_pred",
        "RD_prediction_error",
    ],
    "metrics_step.csv": SHARED_COLUMNS
    + [
        "metric_name",
        "metric_value",
    ],
    "decision_contexts.csv": SHARED_COLUMNS
    + [
        "context_index",
        "context_time",
        "state_hash_at_context",
        "previous_context_id",
        "active_demand_count",
        "reserved_demand_count",
        "returned_demand_count",
        "active_reservation_count",
        "locked_reservation_count",
        "active_action_count",
        "consumed_gap_count",
        "blocked_slot_count",
        "readiness_pass",
        "candidate_action_count",
        "selected_action_id",
        "selected_RCMV",
        "baseline_matching_id",
        "action_conditioned_matching_id",
        "stale_matching_id",
    ],
    "reservation_replans.csv": SHARED_COLUMNS
    + [
        "reservation_id",
        "lineage_root_reservation_id",
        "lineage_parent_reservation_id",
        "ramp_vehicle_id",
        "old_edge_id",
        "new_edge_id",
        "old_action_id",
        "new_action_id",
        "replan_decision",
        "replan_trigger",
        "switching_cost",
        "improvement_margin",
        "hysteresis_threshold",
        "lock_break_reason",
        "status_before",
        "status_after",
        "demand_status_before",
        "demand_status_after",
    ],
    "action_lifecycle.csv": SHARED_COLUMNS
    + [
        "action_id",
        "controlled_cavs",
        "start_time",
        "end_time",
        "executed_start_time",
        "executed_end_time",
        "executed_fraction",
        "lifecycle_status_before",
        "lifecycle_status_after",
        "cancelled_future_part",
        "cancel_reason",
        "overlap_reject_count",
        "reservation_id",
        "realized_event_id",
    ],
    "rolling_reservations.csv": SHARED_COLUMNS
    + [
        "reservation_id",
        "lineage_root_reservation_id",
        "lineage_parent_reservation_id",
        "ramp_vehicle_id",
        "edge_id",
        "action_id",
        "physical_gap_id",
        "slot_group_id",
        "planned_tau",
        "commitment_status",
        "is_locked",
        "status_before",
        "status_after",
        "status_reason",
        "demand_status_before",
        "demand_status_after",
        "realized_event_id",
        "failure_join_key",
    ],
    "rolling_demand_lifecycle.csv": SHARED_COLUMNS
    + [
        "demand_id",
        "ramp_vehicle_id",
        "status_before",
        "status_after",
        "reservation_id",
        "event_reason",
        "returned_to_context_id",
        "merge_success",
        "predicted_unserved",
        "realized_unserved",
        "realized_event_id",
    ],
    "rolling_slot_consumption.csv": SHARED_COLUMNS
    + [
        "physical_gap_id",
        "slot_group_id",
        "edge_id",
        "reservation_id",
        "slot_status_before",
        "slot_status_after",
        "consumed_by_demand_id",
        "blocked_by_conflict_id",
        "duplicate_consumption_flag",
    ],
    "rolling_matching_trace.csv": SHARED_COLUMNS
    + [
        "matching_id",
        "matching_type",
        "action_id",
        "edge_id",
        "reservation_id",
        "ramp_vehicle_id",
        "physical_gap_id",
        "slot_group_id",
        "P_R",
        "RD",
        "selected",
        "rejected_reason",
    ],
    "rolling_plan_commitment.csv": SHARED_COLUMNS
    + [
        "reservation_id",
        "action_id",
        "commitment_status_before",
        "commitment_status_after",
        "is_locked",
        "replan_trigger",
        "lock_break_reason",
        "switching_cost",
        "improvement_margin",
        "reservation_churn_flag",
        "active_guidance_cancel_flag",
    ],
    "rolling_failure_trace.csv": SHARED_COLUMNS
    + [
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
    ],
    "rolling_vs_single_demand_metrics.csv": SHARED_COLUMNS
    + [
        "batch_id",
        "scenario_id",
        "seed",
        "algorithm_id",
        "decision_mode",
        "baseline_algorithm_id",
        "D_H",
        "merge_success_count",
        "merge_success_rate_over_demand",
        "predicted_unserved_demand_count",
        "predicted_unserved_demand_rate",
        "realized_unserved_demand_count",
        "realized_unserved_demand_rate",
        "single_merge_success_rate_over_demand",
        "rolling_vs_single_delta_merge_success_rate_over_demand",
        "rolling_vs_single_delta_realized_unserved_demand_rate",
        "rolling_vs_single_delta_failure_rate",
        "rolling_vs_single_delta_delay",
        "rolling_vs_single_delta_expiration_rate",
    ],
    "rolling_vs_stale_ablation_metrics.csv": SHARED_COLUMNS
    + [
        "batch_id",
        "scenario_id",
        "seed",
        "algorithm_id",
        "D_H",
        "rolling_merge_success_rate_over_demand",
        "stale_merge_success_rate_over_demand",
        "rolling_realized_unserved_demand_rate",
        "stale_realized_unserved_demand_rate",
        "rolling_expired_reservation_count",
        "stale_expired_reservation_count",
        "rolling_invalidated_reservation_count",
        "stale_invalidated_reservation_count",
        "rolling_stale_reservation_harm_count",
        "stale_reservation_harm_count",
        "rolling_vs_stale_delta_merge_success_rate_over_demand",
        "rolling_vs_stale_delta_realized_unserved_demand_rate",
        "rolling_vs_stale_delta_expired_reservation_count",
        "rolling_vs_stale_delta_invalidated_reservation_count",
        "rolling_vs_stale_delta_expiration_rate",
        "rolling_vs_stale_delta_stale_harm_count",
    ],
    "rolling_vs_no_commitment_metrics.csv": SHARED_COLUMNS
    + [
        "batch_id",
        "scenario_id",
        "seed",
        "algorithm_id",
        "rolling_reservation_churn_rate",
        "no_commitment_reservation_churn_rate",
        "rolling_action_switch_count",
        "no_commitment_action_switch_count",
        "rolling_plan_lock_violation_count",
        "no_commitment_plan_lock_violation_count",
        "rolling_vs_no_commitment_delta_churn_rate",
        "rolling_vs_no_commitment_delta_action_switch_count",
    ],
}


REQUIRED_JSON_LOGS = ["scenario_manifest.json", "metrics_episode.json"]


def write_empty_csv(path: str | Path, columns: list[str]) -> None:
    with Path(path).open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(columns)


def append_csv_rows(
    path: str | Path,
    columns: list[str],
    rows: list[dict[str, object]],
) -> None:
    """Append dictionaries to a CSV file using the declared schema order."""

    if not rows:
        return
    with Path(path).open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns, extrasaction="ignore")
        for row in rows:
            writer.writerow({column: _csv_value(row.get(column)) for column in columns})


def append_vehicle_step_rows(
    path: str | Path,
    rows: list[dict[str, object]],
) -> None:
    """Append realized vehicle-step rows to ``vehicles_step.csv``."""

    append_csv_rows(path, CSV_LOG_SCHEMAS["vehicles_step.csv"], rows)


def append_realized_event_rows(
    path: str | Path,
    rows: list[dict[str, object]],
) -> None:
    """Append no-fallback event rows to ``realized_events.csv``."""

    append_csv_rows(path, CSV_LOG_SCHEMAS["realized_events.csv"], rows)


def append_event_metric_window_rows(
    path: str | Path,
    rows: list[dict[str, object]],
) -> None:
    """Append event-level before/after metric windows."""

    append_csv_rows(path, CSV_LOG_SCHEMAS["event_metric_windows.csv"], rows)


def append_slot_rows(
    path: str | Path,
    rows: list[dict[str, object]],
) -> None:
    """Append time-expanded slot rows to ``slots.csv``."""

    append_csv_rows(path, CSV_LOG_SCHEMAS["slots.csv"], rows)


def append_edge_rows(
    path: str | Path,
    rows: list[dict[str, object]],
) -> None:
    """Append edge validity rows to ``edges.csv``."""

    append_csv_rows(path, CSV_LOG_SCHEMAS["edges.csv"], rows)


def append_matching_rows(
    path: str | Path,
    rows: list[dict[str, object]],
) -> None:
    """Append diagnostic matching rows to ``matching.csv``."""

    append_csv_rows(path, CSV_LOG_SCHEMAS["matching.csv"], rows)


def append_readiness_summary_rows(
    path: str | Path,
    rows: list[dict[str, object]],
) -> None:
    """Append Wave 4 readiness rows to ``readiness_summary.csv``."""

    append_csv_rows(path, CSV_LOG_SCHEMAS["readiness_summary.csv"], rows)


def append_action_rows(
    path: str | Path,
    rows: list[dict[str, object]],
) -> None:
    """Append Phase 5 action rows to ``actions.csv``."""

    append_csv_rows(path, CSV_LOG_SCHEMAS["actions.csv"], rows)


def append_action_evaluation_rows(
    path: str | Path,
    rows: list[dict[str, object]],
) -> None:
    """Append Phase 5 action-evaluation rows to ``action_evaluations.csv``."""

    append_csv_rows(path, CSV_LOG_SCHEMAS["action_evaluations.csv"], rows)


def append_reservation_rows(
    path: str | Path,
    rows: list[dict[str, object]],
) -> None:
    """Append Phase 5 reservation rows to ``reservations.csv``."""

    append_csv_rows(path, CSV_LOG_SCHEMAS["reservations.csv"], rows)


def append_decision_context_rows(
    path: str | Path,
    rows: list[dict[str, object]],
) -> None:
    append_csv_rows(path, CSV_LOG_SCHEMAS["decision_contexts.csv"], rows)


def append_reservation_replan_rows(
    path: str | Path,
    rows: list[dict[str, object]],
) -> None:
    append_csv_rows(path, CSV_LOG_SCHEMAS["reservation_replans.csv"], rows)


def append_action_lifecycle_rows(
    path: str | Path,
    rows: list[dict[str, object]],
) -> None:
    append_csv_rows(path, CSV_LOG_SCHEMAS["action_lifecycle.csv"], rows)


def append_rolling_reservation_rows(
    path: str | Path,
    rows: list[dict[str, object]],
) -> None:
    append_csv_rows(path, CSV_LOG_SCHEMAS["rolling_reservations.csv"], rows)


def append_rolling_demand_lifecycle_rows(
    path: str | Path,
    rows: list[dict[str, object]],
) -> None:
    append_csv_rows(path, CSV_LOG_SCHEMAS["rolling_demand_lifecycle.csv"], rows)


def append_rolling_slot_consumption_rows(
    path: str | Path,
    rows: list[dict[str, object]],
) -> None:
    append_csv_rows(path, CSV_LOG_SCHEMAS["rolling_slot_consumption.csv"], rows)


def append_rolling_matching_trace_rows(
    path: str | Path,
    rows: list[dict[str, object]],
) -> None:
    append_csv_rows(path, CSV_LOG_SCHEMAS["rolling_matching_trace.csv"], rows)


def append_rolling_plan_commitment_rows(
    path: str | Path,
    rows: list[dict[str, object]],
) -> None:
    append_csv_rows(path, CSV_LOG_SCHEMAS["rolling_plan_commitment.csv"], rows)


def append_rolling_failure_trace_rows(
    path: str | Path,
    rows: list[dict[str, object]],
) -> None:
    append_csv_rows(path, CSV_LOG_SCHEMAS["rolling_failure_trace.csv"], rows)


def _csv_value(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return value


def init_empty_logs(run_dir: str | Path) -> None:
    """Create all Phase 0 log files with headers and empty JSON placeholders."""

    directory = Path(run_dir)
    for filename, columns in CSV_LOG_SCHEMAS.items():
        write_empty_csv(directory / filename, columns)
    (directory / "scenario_manifest.json").write_text(
        json.dumps({"schema_version": "phase0_v1", "scenarios": []}, indent=2) + "\n",
        encoding="utf-8",
    )
    (directory / "metrics_episode.json").write_text(
        json.dumps({"schema_version": "phase0_v1", "metrics": {}}, indent=2) + "\n",
        encoding="utf-8",
    )
