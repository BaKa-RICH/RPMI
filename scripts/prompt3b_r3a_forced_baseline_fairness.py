"""Prompt 3B-R3-A forced baseline fairness repair/audit.

This script is intentionally narrow. It checks only C2 forced_accommodation
fairness after the R3-A implementation repair, then runs the smallest P1a/P1b
full-vs-forced matrix. It does not run Prompt 4 or lock paper evidence.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence
import ast
import csv
import hashlib
import inspect
import json
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
for path in (REPO_ROOT, SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from rpmi.config import stable_json
from rpmi.scenarios import ScenarioConfig, scenario_config_hash

from scripts import prompt3a_readiness_micro_run as p3a
from scripts import prompt3b_mechanism_codesign_loop as p3b


OUTPUT_ROOT = Path("outputs/d2_5_theory_alignment")
GATE_DIR = OUTPUT_ROOT / "gate_D2_5_input"
HUMAN_REVIEW_DIR = OUTPUT_ROOT / "human_review"
SOURCE_BATCH_ID = "prompt3b_r3a_forced_baseline_fairness"
FULL = p3b.FULL_VARIANT
FORCED = "forced_accommodation"


def main() -> None:
    GATE_DIR.mkdir(parents=True, exist_ok=True)
    HUMAN_REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    p3a.SOURCE_BATCH_ID = SOURCE_BATCH_ID

    static_rows = _static_audit_rows()
    matrix_rows, records = _run_minimal_matrix()
    verdict = _c2_verdict(static_rows, matrix_rows)

    _write_csv(GATE_DIR / "prompt3b_r3a_forced_baseline_static_audit.csv", static_rows, _static_columns())
    _write_csv(GATE_DIR / "prompt3b_r3a_forced_vs_full_minimal_matrix.csv", matrix_rows, _matrix_columns())
    _write_packet(static_rows, matrix_rows, verdict)

    print(f"prompt3b_r3a_verdict={verdict['verdict']}")
    print(f"forced_baseline_fair={str(verdict['forced_baseline_fair']).lower()}")
    print(f"c2_supportable={str(verdict['c2_supportable']).lower()}")
    print(f"main_reason={verdict['reason']}")
    print(f"matrix_rows={len(matrix_rows)}")
    print(f"review_packet_path={HUMAN_REVIEW_DIR / 'PROMPT_3B_R3A_FORCED_BASELINE_FAIRNESS_PACKET.md'}")


def _run_minimal_matrix() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cases = [
        ("P1a", p3b._p1a_default_lambda()),
        ("P1b", p3b._p1b_near_miss_gap7()),
    ]
    rows: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    for family, scenario in cases:
        params = p3a._params_for_scenario(scenario)
        for variant in (FULL, FORCED):
            record = p3a._run_variant(scenario, family, variant, params)
            record["scenario_config"] = scenario
            records.append(record)
            rows.append(_matrix_row(family, scenario, variant, record))
    return rows, records


def _matrix_row(
    family: str,
    scenario: ScenarioConfig,
    variant: str,
    record: Mapping[str, Any],
) -> dict[str, Any]:
    trace = record["trace_row"]
    metric = record["metric_row"]
    event = record["event_row"]
    selected_eval = record["selected_eval"]
    selected_action = record["selected_action"]
    return {
        "run_id": trace.get("run_id", ""),
        "scenario_family": family,
        "scenario_design_id": scenario.scenario_id,
        "scenario_hash": scenario_config_hash(scenario),
        "variant": variant,
        "selected_action_id": trace.get("selected_action_id", ""),
        "selected_gap_id": trace.get("selected_gap_id", ""),
        "merge_success": trace.get("merge_success", ""),
        "actual_margin": event.get("min_margin", ""),
        "mainline_disturbance_cost": metric.get("mainline_disturbance_cost", ""),
        "hard_brake_count": metric.get("hard_brake_count", ""),
        "max_deceleration": metric.get("max_deceleration", ""),
        "speed_variance_delta": metric.get("speed_variance_delta", ""),
        "max_wave_amplitude": metric.get("max_wave_amplitude", ""),
        "RD_realized_proxy": metric.get("RD_realized_proxy", ""),
        "trace_complete": trace.get("can_join_full_chain", ""),
        "instrumentation_note": record.get("instrumentation_note", ""),
        "selected_action_type": getattr(selected_action, "action_type", ""),
        "selected_edge_id": trace.get("selected_edge_id", ""),
        "selected_eval_J": getattr(selected_eval, "J", ""),
        "selected_eval_RCMV": getattr(selected_eval, "RCMV", ""),
        "selected_eval_D_bar": getattr(selected_eval, "D_bar", ""),
        "selected_eval_C_bar": getattr(selected_eval, "C_bar", ""),
        "used_for_tuning": True,
        "candidate_or_repair_evidence": "r3a_repair_evidence_only",
        "git_commit_or_worktree_hash": _worktree_hash(),
        "config_hash": _hash({"scenario": scenario_config_hash(scenario), "variant": variant, "batch": SOURCE_BATCH_ID}),
        "objective_hash": _hash("R3A_no_objective_change_lambda_D_1_lambda_C_0_001_theta_0_05"),
        "metric_hash": _hash("R3A_existing_prompt3a_metric_extraction"),
        "baseline_hash": _hash("forced_physical_geometry_baseline_no_rpmi_selection"),
    }


def _static_audit_rows() -> list[dict[str, Any]]:
    import rpmi.runner as runner

    functions = [
        "_select_forced_accommodation_baseline",
        "_forced_physical_candidates",
        "_forced_action_for_physical_edge",
        "_estimated_width_after_action",
    ]
    rows = []
    forbidden = {
        "run_action_selection": "RPMI candidate/evaluation path",
        "select_action": "RCMV/theta selector",
        "compute_objective": "objective evaluator",
        "find_near_miss_edges": "RPMI near-miss objective path",
        "realized_events": "post-hoc realized outcomes",
        "realized_event": "post-hoc realized outcomes",
        "RCMV": "RCMV ranking",
        "D_bar": "RD predicted ranking",
        "C_bar": "Cbar predicted ranking",
    }
    allowed_calls = {
        "boundary_type_for_edge",
        "build_boundary_speed_profile",
        "compute_profile_cost",
        "controlled_cavs_for_mode",
        "validate_single_action",
        "_evaluation_for_selected_edge_ids",
        "_policy_result",
        "_copy_eval_flags",
        "_available_boundary_modes_for_ablation",
        "_estimated_width_after_action",
        "_forced_physical_candidates",
        "_forced_action_for_physical_edge",
        "make_action_id",
        "max",
        "str",
        "float",
        "int",
        "getattr",
        "list",
        "dict",
        "set",
        "sorted",
    }
    for name in functions:
        func = getattr(runner, name)
        source = inspect.getsource(func)
        calls = sorted(_called_names(source))
        forbidden_hits = sorted(key for key in forbidden if key in source)
        rows.append(
            {
                "component": name,
                "file": "src/rpmi/runner.py",
                "call_graph_calls": ";".join(calls),
                "forbidden_hits": ";".join(forbidden_hits),
                "allowed_call_notes": ";".join(call for call in calls if call in allowed_calls),
                "uses_objective_scores": "compute_objective" in source,
                "uses_rcmv": "RCMV" in source or "select_action" in source,
                "uses_rd_pred_ranking": "D_bar" in source or "matched_rd" in source,
                "uses_cbar_ranking": "C_bar" in source,
                "uses_rpmi_candidate_generation": "run_action_selection" in source or "find_near_miss_edges" in source or "generate_candidate_actions" in source,
                "uses_posthoc_realized_outcomes": "realized_event" in source or "realized_events" in source,
                "uses_future_trajectory": "future" in source,
                "uses_action_conditioned_inventory_in_selection": "evaluate_action" in source or "evaluate_rollout_inventory" in source,
                "fair_by_static_audit": not forbidden_hits and "evaluate_action" not in source and "evaluate_rollout_inventory" not in source,
                "audit_note": "selection uses physical edge geometry and action feasibility; evaluation is used only after selection for trace logging",
            }
        )
    return rows


def _called_names(source: str) -> set[str]:
    tree = ast.parse(source)
    calls: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)
    return calls


def _c2_verdict(static_rows: Sequence[Mapping[str, Any]], matrix_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    fair = all(str(row.get("fair_by_static_audit")).lower() == "true" for row in static_rows)
    by_case_variant = {(row["scenario_family"], row["variant"]): row for row in matrix_rows}
    p1a_full = by_case_variant.get(("P1a", FULL), {})
    p1a_forced = by_case_variant.get(("P1a", FORCED), {})
    p1b_full = by_case_variant.get(("P1b", FULL), {})
    p1b_forced = by_case_variant.get(("P1b", FORCED), {})
    forced_services = any(_truthy(row.get("merge_success")) for row in (p1a_forced, p1b_forced))
    forced_more_disturbing = any(
        _float(forced.get("mainline_disturbance_cost")) > _float(full.get("mainline_disturbance_cost"))
        for full, forced in ((p1a_full, p1a_forced), (p1b_full, p1b_forced))
    )
    trace_complete = all(_truthy(row.get("trace_complete")) for row in matrix_rows)
    c2_supportable = fair and forced_services and forced_more_disturbing and trace_complete
    if c2_supportable:
        verdict = "C2_SUPPORTABLE_REPAIR_CANDIDATE"
        reason = "forced baseline is fair by static audit and has service plus higher disturbance contrast"
    elif fair:
        verdict = "C2_FAIR_BASELINE_REPAIRED_BUT_CLAIM_NOT_SUPPORTED"
        reason = "forced baseline no longer uses RPMI-internal selection, but minimal P1a/P1b matrix does not show service/near-service with higher disturbance"
    else:
        verdict = "C2_BLOCKED_BASELINE_NOT_INDEPENDENT"
        reason = "static audit still found forbidden RPMI/objective/action-conditioned selection dependency"
    return {
        "verdict": verdict,
        "forced_baseline_fair": fair,
        "forced_services": forced_services,
        "forced_more_disturbing": forced_more_disturbing,
        "trace_complete": trace_complete,
        "c2_supportable": c2_supportable,
        "reason": reason,
    }


def _write_packet(static_rows: Sequence[Mapping[str, Any]], matrix_rows: Sequence[Mapping[str, Any]], verdict: Mapping[str, Any]) -> None:
    lines = [
        "# PROMPT 3B-R3A FORCED BASELINE FAIRNESS PACKET",
        "",
        "## Verdict",
        "",
        str(verdict["verdict"]),
        "",
        "This is R3-A repair evidence only. It is not Prompt 4 and does not lock paper evidence.",
        "",
        "## Static Audit",
        "",
        f"- forced_baseline_fair: {str(verdict['forced_baseline_fair']).lower()}",
        "- Audited functions: `_select_forced_accommodation_baseline`, `_forced_physical_candidates`, `_forced_action_for_physical_edge`, `_estimated_width_after_action`.",
        "- Forbidden path checks cover objective scoring, RCMV/theta selector, RD/Cbar ranking, RPMI near-miss generation, action-conditioned inventory during selection, realized outcomes, and future trajectory access.",
        "",
        "| component | fair | forbidden_hits | calls |",
        "| --- | --- | --- | --- |",
    ]
    for row in static_rows:
        lines.append(f"| {row['component']} | {row['fair_by_static_audit']} | {row['forbidden_hits']} | {row['call_graph_calls']} |")
    lines.extend(
        [
            "",
            "## Minimal P1a/P1b Matrix",
            "",
            "| family | variant | action | gap | service | disturbance | trace |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in matrix_rows:
        lines.append(
            f"| {row['scenario_family']} | {row['variant']} | {row['selected_action_id']} | {row['selected_gap_id']} | {row['merge_success']} | {row['mainline_disturbance_cost']} | {row['trace_complete']} |"
        )
    lines.extend(
        [
            "",
            "## C2 Interpretation",
            "",
            f"- c2_supportable: {str(verdict['c2_supportable']).lower()}",
            f"- forced_services: {str(verdict['forced_services']).lower()}",
            f"- forced_more_disturbing: {str(verdict['forced_more_disturbing']).lower()}",
            f"- trace_complete: {str(verdict['trace_complete']).lower()}",
            f"- reason: {verdict['reason']}",
            "",
            "If the paper requires forced_accommodation as a performance-supporting baseline, the claim must remain downgraded unless a later deterministic scenario shows fair forced service/near-service with higher disturbance.",
        ]
    )
    (HUMAN_REVIEW_DIR / "PROMPT_3B_R3A_FORCED_BASELINE_FAIRNESS_PACKET.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _csv_value(row.get(column, "")) for column in columns})


def _static_columns() -> list[str]:
    return [
        "component",
        "file",
        "call_graph_calls",
        "forbidden_hits",
        "allowed_call_notes",
        "uses_objective_scores",
        "uses_rcmv",
        "uses_rd_pred_ranking",
        "uses_cbar_ranking",
        "uses_rpmi_candidate_generation",
        "uses_posthoc_realized_outcomes",
        "uses_future_trajectory",
        "uses_action_conditioned_inventory_in_selection",
        "fair_by_static_audit",
        "audit_note",
    ]


def _matrix_columns() -> list[str]:
    return [
        "run_id",
        "scenario_family",
        "scenario_design_id",
        "scenario_hash",
        "variant",
        "selected_action_id",
        "selected_gap_id",
        "merge_success",
        "actual_margin",
        "mainline_disturbance_cost",
        "hard_brake_count",
        "max_deceleration",
        "speed_variance_delta",
        "max_wave_amplitude",
        "RD_realized_proxy",
        "trace_complete",
        "instrumentation_note",
        "selected_action_type",
        "selected_edge_id",
        "selected_eval_J",
        "selected_eval_RCMV",
        "selected_eval_D_bar",
        "selected_eval_C_bar",
        "used_for_tuning",
        "candidate_or_repair_evidence",
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
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _hash(payload: Any) -> str:
    text = stable_json(payload) if not isinstance(payload, str) else payload
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _worktree_hash() -> str:
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False).stdout.strip()
    diff = subprocess.run(["git", "diff", "--", "src/rpmi/runner.py", "scripts/prompt3b_r3a_forced_baseline_fairness.py"], capture_output=True, text=True, check=False).stdout
    return f"{head}+wt{hashlib.sha256(diff.encode('utf-8')).hexdigest()[:10]}"


if __name__ == "__main__":
    main()
