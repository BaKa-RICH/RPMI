"""Prompt 3B-R3-C C5 near-miss robustness ladder.

Runs deterministic ramp_start_x ladder points and classifies actual service,
near-service, or fail. This is repair/candidate screening only, not Prompt 4.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping, Sequence
import csv
import hashlib
import json
import math
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
for path in (REPO_ROOT, SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from rpmi.config import stable_json
from rpmi.scenarios import make_scenario_config, scenario_config_hash

from scripts import prompt3a_readiness_micro_run as p3a
from scripts import prompt3b_mechanism_codesign_loop as p3b


OUTPUT_ROOT = Path("outputs/d2_5_theory_alignment")
GATE_DIR = OUTPUT_ROOT / "gate_D2_5_input"
HUMAN_REVIEW_DIR = OUTPUT_ROOT / "human_review"
SOURCE_BATCH_ID = "prompt3b_r3c_c5_robustness_ladder"
FULL = p3b.FULL_VARIANT
FORCED = "forced_accommodation"
RAW = "raw_largest_gap"
EPSILON_MARGIN = 0.05


def main() -> None:
    GATE_DIR.mkdir(parents=True, exist_ok=True)
    HUMAN_REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    p3a.SOURCE_BATCH_ID = SOURCE_BATCH_ID
    rows = []
    for x in (74.05, 74.10, 74.15, 74.20, 74.25):
        scenario = _p1b_gap7_ramp(x)
        params = p3a._params_for_scenario(scenario)
        for variant in (FULL, RAW, FORCED):
            record = p3a._run_variant(scenario, "P1b", variant, params)
            rows.append(_row(x, scenario, variant, record))
    summary = _summary(rows)
    _write_csv(GATE_DIR / "prompt3b_r3c_c5_robustness_ladder.csv", rows, _columns())
    _write_packet(rows, summary)
    print(f"prompt3b_r3c_points=5")
    print(f"prompt3b_r3c_rows={len(rows)}")
    print(f"c5_contiguous_success_or_near_service={str(summary['contiguous_success_or_near_service']).lower()}")
    print(f"c5_lock_candidate={str(summary['c5_lock_candidate']).lower()}")
    print(f"main_reason={summary['reason']}")
    print(f"review_packet_path={HUMAN_REVIEW_DIR / 'PROMPT_3B_R3C_C5_ROBUSTNESS_PACKET.md'}")


def _p1b_gap7_ramp(x: float) -> Any:
    cfg = p3b._p1b_near_miss_gap7()
    return make_scenario_config(
        f"P3BR3C-P1B-GAP7-RAMP{str(x).replace('.', '')}",
        seed=0,
        road=cfg.road,
        simulation={**cfg.simulation, "H": 1.0, "theta": 0.05, "lambda_C": 0.001},
        vehicles={**cfg.vehicles, "ramp_start_x": float(x), "gap_widths": [7.0]},
        readiness_targets=p3b._readiness_targets(),
        mechanism_targets={"mechanism": "Prompt3B-R3C", "mechanism_target": "C5_ramp_timing_robustness"},
    )


def _row(x: float, scenario: Any, variant: str, record: Mapping[str, Any]) -> dict[str, Any]:
    trace = record["trace_row"]
    event = record["event_row"]
    metric = record["metric_row"]
    actual_margin = _float(event.get("min_margin"))
    service = _truthy(trace.get("merge_success"))
    finite_margin = math.isfinite(actual_margin)
    near = (not service) and finite_margin and actual_margin >= -EPSILON_MARGIN
    status = "actual_service" if service else ("near_service" if near else "fail")
    selected_action = record["selected_action"]
    selected_eval = record["selected_eval"]
    return {
        "ramp_start_x": x,
        "scenario_family": "P1b",
        "scenario_design_id": scenario.scenario_id,
        "scenario_hash": scenario_config_hash(scenario),
        "variant": variant,
        "service_classification": status,
        "merge_success": trace.get("merge_success", ""),
        "near_service_epsilon_margin": EPSILON_MARGIN,
        "actual_margin": event.get("min_margin", ""),
        "event_reason": event.get("event_reason", ""),
        "selected_action_id": trace.get("selected_action_id", ""),
        "selected_gap_id": trace.get("selected_gap_id", ""),
        "selected_edge_id": trace.get("selected_edge_id", ""),
        "planned_selected_action_applied": trace.get("selected_action_id") != "a0_none",
        "action_duration_actual": getattr(selected_action, "control_profile", {}).get("T_prod", ""),
        "post_action_edge_recomputed": "act_" in str(trace.get("selected_edge_id", "")) or trace.get("selected_action_id") == "a0_none",
        "forced_contrast_variant": FORCED,
        "mainline_disturbance_cost": metric.get("mainline_disturbance_cost", ""),
        "hard_brake_count": metric.get("hard_brake_count", ""),
        "max_deceleration": metric.get("max_deceleration", ""),
        "speed_variance_delta": metric.get("speed_variance_delta", ""),
        "max_wave_amplitude": metric.get("max_wave_amplitude", ""),
        "RD_realized_proxy": metric.get("RD_realized_proxy", ""),
        "trace_complete": trace.get("can_join_full_chain", ""),
        "positive_RCMV_action": _float(getattr(selected_eval, "RCMV", 0.0)) > 0.0,
        "selected_action_RCMV": getattr(selected_eval, "RCMV", ""),
        "selected_action_C_bar": getattr(selected_eval, "C_bar", ""),
        "candidate_or_repair_evidence": "r3c_ladder_repair_evidence_only",
        "used_for_tuning": True,
        "git_commit_or_worktree_hash": _worktree_hash(),
        "config_hash": _hash(asdict(scenario)),
        "objective_hash": _hash("R3C_existing_objective_lambda_D_1_lambda_C_0_001_theta_0_05"),
        "metric_hash": _hash("R3C_near_service_actual_margin_epsilon_0_05"),
        "baseline_hash": _hash("R3C_full_raw_forced_current"),
    }


def _summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    full_rows = [row for row in rows if row["variant"] == FULL]
    good = [row for row in full_rows if row["service_classification"] in {"actual_service", "near_service"}]
    x_good = sorted(float(row["ramp_start_x"]) for row in good)
    contiguous = len(x_good) >= 2 and any(abs(b - a - 0.05) < 1e-9 for a, b in zip(x_good, x_good[1:]))
    forced_rows = {float(row["ramp_start_x"]): row for row in rows if row["variant"] == FORCED}
    full_forced_contrast = any(
        _float(forced_rows.get(float(row["ramp_start_x"]), {}).get("mainline_disturbance_cost"))
        > _float(row.get("mainline_disturbance_cost"))
        for row in full_rows
    )
    c5_lock_candidate = contiguous and full_forced_contrast
    if c5_lock_candidate:
        reason = "full has a contiguous service/near-service interval and forced is more disturbing at least once"
    elif contiguous:
        reason = "full has a contiguous service/near-service interval, but forced contrast is not more disturbing"
    elif good:
        reason = "only isolated full service/near-service points were observed"
    else:
        reason = "full did not realize service or near-service on the ladder"
    return {
        "contiguous_success_or_near_service": contiguous,
        "full_forced_contrast": full_forced_contrast,
        "c5_lock_candidate": c5_lock_candidate,
        "reason": reason,
    }


def _write_packet(rows: Sequence[Mapping[str, Any]], summary: Mapping[str, Any]) -> None:
    lines = [
        "# PROMPT 3B-R3C C5 ROBUSTNESS PACKET",
        "",
        "## Verdict",
        "",
        f"c5_lock_candidate={str(summary['c5_lock_candidate']).lower()}",
        "",
        "This is a deterministic R3-C robustness ladder, not Prompt 4 lock evidence.",
        "",
        "## Summary",
        "",
        f"- contiguous_success_or_near_service: {str(summary['contiguous_success_or_near_service']).lower()}",
        f"- full_forced_contrast: {str(summary['full_forced_contrast']).lower()}",
        f"- reason: {summary['reason']}",
        "",
        "## Ladder Rows",
        "",
        "| ramp_start_x | variant | class | action | gap | margin | disturbance | trace |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['ramp_start_x']} | {row['variant']} | {row['service_classification']} | {row['selected_action_id']} | {row['selected_gap_id']} | {row['actual_margin']} | {row['mainline_disturbance_cost']} | {row['trace_complete']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- If only one point succeeds, C5 cannot be claimed.",
            "- If a contiguous interval succeeds but forced is not more disturbing, C5 may be a service candidate but not a forced-contrast candidate.",
        ]
    )
    (HUMAN_REVIEW_DIR / "PROMPT_3B_R3C_C5_ROBUSTNESS_PACKET.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _csv_value(row.get(column, "")) for column in columns})


def _columns() -> list[str]:
    return [
        "ramp_start_x",
        "scenario_family",
        "scenario_design_id",
        "scenario_hash",
        "variant",
        "service_classification",
        "merge_success",
        "near_service_epsilon_margin",
        "actual_margin",
        "event_reason",
        "selected_action_id",
        "selected_gap_id",
        "selected_edge_id",
        "planned_selected_action_applied",
        "action_duration_actual",
        "post_action_edge_recomputed",
        "forced_contrast_variant",
        "mainline_disturbance_cost",
        "hard_brake_count",
        "max_deceleration",
        "speed_variance_delta",
        "max_wave_amplitude",
        "RD_realized_proxy",
        "trace_complete",
        "positive_RCMV_action",
        "selected_action_RCMV",
        "selected_action_C_bar",
        "candidate_or_repair_evidence",
        "used_for_tuning",
        "git_commit_or_worktree_hash",
        "config_hash",
        "objective_hash",
        "metric_hash",
        "baseline_hash",
    ]


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return value


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "pass"}


def _float(value: Any) -> float:
    try:
        if value in {"", None}:
            return -math.inf
        return float(value)
    except (TypeError, ValueError):
        return -math.inf


def _hash(payload: Any) -> str:
    text = stable_json(payload) if not isinstance(payload, str) else payload
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _worktree_hash() -> str:
    return _hash("r3c_worktree")


if __name__ == "__main__":
    main()
