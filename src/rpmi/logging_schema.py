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
        "action_index",
        "controlled_cav_ids",
        "requested_delta_W",
        "estimated_delta_W_after_clip",
        "action_profile_feasible",
        "profile_clip_flag",
    ],
    "action_evaluations.csv": SHARED_COLUMNS
    + [
        "action_id",
        "candidate_rank",
        "score",
        "D_bar",
        "C_bar",
        "selected",
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
    ],
    "realized_events.csv": SHARED_COLUMNS
    + [
        "event_id",
        "event_type",
        "vehicle_ids",
        "min_gap",
        "min_margin",
        "severity",
        "linked_reservation_id",
        "linked_action_id",
        "linked_edge_id",
        "note",
    ],
    "metrics_step.csv": SHARED_COLUMNS
    + [
        "metric_name",
        "metric_value",
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
