"""Wave 6A CSV-first aggregation and summary-table helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence
import csv
import json


AGGREGATE_METRIC_COLUMNS = [
    "run_id",
    "scenario_id",
    "seed",
    "algorithm_id",
    "status",
    "decision_mode",
    "state_hash",
    "readiness_pass",
    "readiness_reason",
    "selected_action_id",
    "selected_action_type",
    "baseline_J",
    "selected_J",
    "selected_RCMV",
    "baseline_S_R",
    "baseline_Z_R",
    "selected_S_R",
    "selected_Z_R",
    "mean_ramp_delay",
    "merge_success_count",
    "failed_reservation_count",
    "failed_reservation_rate",
    "slot_expiration_count",
    "slot_expiration_rate",
    "mean_RD_matched",
    "hard_brake_count",
    "max_wave_amplitude",
    "no_fallback_invalid_event_count",
    "throughput_outflow",
    "mean_Z_R",
    "production_cost_sum",
    "stale_reservation_count",
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
    "run_id",
    "scenario_id",
    "seed",
    "algorithm_id",
    "failure_source",
    "reservation_id",
    "event_id",
    "event_type",
    "status",
    "failure_reason",
    "linked_action_id",
    "linked_edge_id",
    "ramp_id",
    "edge_id",
    "slot_id",
    "severity",
]


RCMV_TRACE_COLUMNS = [
    "run_id",
    "scenario_id",
    "seed",
    "algorithm_id",
    "decision_context_id",
    "state_hash",
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
) -> Path:
    """Collect reservation failures and no-fallback events into one CSV."""

    out_path = Path(output_path) if output_path is not None else Path("failure_summary.csv")
    rows: list[dict[str, Any]] = []
    for run_dir in run_dirs:
        run_path = Path(run_dir)
        metrics = _read_metrics(run_path)
        rows.extend(_reservation_failure_rows(run_path, metrics))
        rows.extend(_event_failure_rows(run_path, metrics))
        if metrics.get("status") == "readiness_failed":
            rows.append(
                {
                    **_metric_context(metrics),
                    "failure_source": "readiness",
                    "status": "readiness_failed",
                    "failure_reason": metrics.get("readiness_reason", ""),
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
        for row in _read_csv(run_path / "action_evaluations.csv"):
            rows.append(
                {
                    **_metric_context(metrics),
                    "decision_context_id": row.get("decision_context_id", ""),
                    "state_hash": row.get("state_hash", metrics.get("state_hash", "")),
                    "action_id": row.get("action_id", ""),
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


def _metrics_row(run_dir: str | Path) -> dict[str, Any]:
    run_path = Path(run_dir)
    metrics = _read_metrics(run_path)
    row = {column: metrics.get(column, "") for column in AGGREGATE_METRIC_COLUMNS}
    row["run_id"] = metrics.get("run_id") or run_path.name
    return row


def _read_metrics(run_path: Path) -> dict[str, Any]:
    metrics_path = run_path / "metrics_episode.json"
    if not metrics_path.exists():
        return {"run_id": run_path.name}
    payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics = payload.get("metrics", payload)
    metrics.setdefault("run_id", run_path.name)
    return metrics


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
                "failure_source": "reservation",
                "reservation_id": row.get("reservation_id", ""),
                "status": status,
                "failure_reason": row.get("failure_reason", ""),
                "linked_action_id": row.get("action_id", ""),
                "linked_edge_id": row.get("edge_id", ""),
                "ramp_id": row.get("ramp_id", ""),
                "edge_id": row.get("edge_id", ""),
                "slot_id": row.get("slot_id", ""),
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
                "failure_source": "realized_event",
                "event_id": row.get("event_id", ""),
                "event_type": event_type,
                "status": event_type,
                "failure_reason": row.get("note", ""),
                "linked_action_id": row.get("linked_action_id", ""),
                "linked_edge_id": row.get("linked_edge_id", ""),
                "reservation_id": row.get("linked_reservation_id", ""),
                "severity": row.get("severity", ""),
            }
        )
    return rows


def _metric_context(metrics: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "run_id": metrics.get("run_id", ""),
        "scenario_id": metrics.get("scenario_id", ""),
        "seed": metrics.get("seed", ""),
        "algorithm_id": metrics.get("algorithm_id", ""),
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
    "FAILURE_SUMMARY_COLUMNS",
    "RCMV_TRACE_COLUMNS",
    "SUMMARY_COLUMNS",
    "aggregate_failures",
    "aggregate_metrics",
    "collect_rcmv_trace",
    "generate_summary_tables",
]
