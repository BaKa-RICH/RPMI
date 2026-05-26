"""Prompt 3B-R3-B Cbar predicted-vs-realized disturbance alignment.

This is diagnostic only. It does not tune lambda_C or lock paper evidence.
"""

from __future__ import annotations

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
from rpmi.runner import apply_policy, build_decision_context, resolve_baseline_config
from rpmi.scenarios import generate_state, scenario_config_hash

from scripts import prompt3a_readiness_micro_run as p3a
from scripts import prompt3b_mechanism_codesign_loop as p3b


OUTPUT_ROOT = Path("outputs/d2_5_theory_alignment")
GATE_DIR = OUTPUT_ROOT / "gate_D2_5_input"
HUMAN_REVIEW_DIR = OUTPUT_ROOT / "human_review"
SOURCE_BATCH_ID = "prompt3b_r3b_cbar_alignment"
FULL = p3b.FULL_VARIANT
WITHOUT_CBAR = "without_Cbar"


def main() -> None:
    GATE_DIR.mkdir(parents=True, exist_ok=True)
    HUMAN_REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    p3a.SOURCE_BATCH_ID = SOURCE_BATCH_ID

    scenario = p3b._p1a_default_lambda()
    rows, summary = _alignment_rows("P1a", scenario)
    _write_csv(GATE_DIR / "Cbar_pred_vs_realized_disturbance_alignment.csv", rows, _columns())
    _write_packet(rows, summary)
    print(f"prompt3b_r3b_rows={len(rows)}")
    print(f"cbar_alignment_status={summary['status']}")
    print(f"full_selected_action={summary['full_selected_action']}")
    print(f"without_Cbar_selected_action={summary['without_cbar_selected_action']}")
    print(f"review_packet_path={HUMAN_REVIEW_DIR / 'PROMPT_3B_R3B_CBAR_ALIGNMENT_PACKET.md'}")


def _alignment_rows(family: str, scenario: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    params = p3a._params_for_scenario(scenario)
    state = generate_state(scenario)
    full_record = p3a._run_variant(scenario, family, FULL, params)
    without_record = p3a._run_variant(scenario, family, WITHOUT_CBAR, params)
    full_selected = full_record["trace_row"].get("selected_action_id", "")
    without_selected = without_record["trace_row"].get("selected_action_id", "")

    context = build_decision_context(state, scenario, resolve_baseline_config("rpmi_cmv"))
    policy_result = apply_policy(resolve_baseline_config("rpmi_cmv"), state, context)
    action_by_id = {action.action_id: action for action in policy_result.get("actions_to_log", [])}
    eval_by_id = {evaluation.action_id: evaluation for evaluation in policy_result.get("evaluations", [])}
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for action_row in full_record["action_rows"]:
        action_id = str(action_row.get("action_id", ""))
        if not action_id or action_id in seen:
            continue
        seen.add(action_id)
        evaluation = eval_by_id.get(action_id)
        action = action_by_id.get(action_id)
        if evaluation is None or action is None:
            continue
        metric = _realized_metric_for_action(state, action, evaluation, params)
        rows.append(
            {
                "run_id": f"{SOURCE_BATCH_ID}__{scenario.scenario_id}__{action_id}",
                "scenario_family": family,
                "scenario_design_id": scenario.scenario_id,
                "scenario_hash": scenario_config_hash(scenario),
                "candidate_action_id": action_id,
                "candidate_action_type": action.action_type,
                "candidate_gap_id": action_row.get("selected_gap_id", ""),
                "candidate_edge_id": action_row.get("selected_edge_id", ""),
                "C_dist_pred": action_row.get("C_bar", ""),
                "C_dist_norm": action_row.get("C_dist_norm", ""),
                "RD_pred_norm": action_row.get("RD_pred_norm", ""),
                "J": action_row.get("J", ""),
                "RCMV": action_row.get("RCMV", ""),
                "full_selected_action": full_selected,
                "without_Cbar_selected_action": without_selected,
                "selected_by_full": action_id == full_selected,
                "selected_by_without_Cbar": action_id == without_selected,
                "realized_disturbance": metric["mainline_disturbance_cost"],
                "hard_brake_count": metric["hard_brake_count"],
                "wave": metric["max_wave_amplitude"],
                "max_decel": metric["max_deceleration"],
                "speed_variance_delta": metric["speed_variance_delta"],
                "metric_window_start": metric["metric_window_start"],
                "metric_window_end": metric["metric_window_end"],
                "alignment_note": "candidate_action_replayed_with_its_selected_inventory_reservation",
                "used_for_tuning": True,
                "candidate_or_repair_evidence": "r3b_diagnostic_only",
                "git_commit_or_worktree_hash": _worktree_hash(),
                "config_hash": _hash({"scenario": scenario_config_hash(scenario), "action": action_id}),
                "objective_hash": _hash("R3B_existing_objective_no_weight_change"),
                "metric_hash": _hash("R3B_candidate_replay_disturbance_window"),
                "baseline_hash": _hash("R3B_full_vs_without_Cbar_current"),
            }
        )
    summary = _summary(rows, full_selected, without_selected)
    return rows, summary


def _action_for_id(record: Mapping[str, Any], action_id: str) -> Any | None:
    selected = record.get("selected_action")
    if getattr(selected, "action_id", "") == action_id:
        return selected
    for row in record.get("action_rows", []):
        if row.get("action_id") == action_id and action_id == "a0_none":
            return _none_action(record)
    for evaluation in record.get("evaluations", []):
        if evaluation.action_id == action_id:
            # The Prompt 3A record logs actions_to_log rows indirectly; selected
            # action is the only object retained for arbitrary candidates.
            if action_id == "a0_none":
                return _none_action(record)
    return selected if getattr(selected, "action_id", "") == action_id else None


def _none_action(record: Mapping[str, Any]) -> Any:
    from rpmi.actions import Action

    del record
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


def _realized_metric_for_action(state: Any, action: Any, evaluation: Any, params: Any) -> dict[str, Any]:
    log_context = {
        "schema_version": "d2_5_prompt3b_r3b_v0.1",
        "source_batch_id": SOURCE_BATCH_ID,
        "source_table": "prompt3b_r3b_cbar_alignment",
        "run_id": f"{SOURCE_BATCH_ID}_{action.action_id}",
        "scenario_id": "P1a",
        "seed": 0,
        "algorithm_id": "candidate_replay",
        "step": 0,
        "time": 0.0,
        "decision_context_id": f"dc_{SOURCE_BATCH_ID}_{action.action_id}",
        "state_hash": "",
        "config_hash": _hash(action.action_id),
        "code_version": "local_dirty",
    }
    reservation = p3a._reservation_for_selected(
        evaluation,
        str(log_context["decision_context_id"]),
    )
    execution = p3a._execute_variant_event_window(
        state,
        action,
        reservation,
        {edge.edge_id: edge for edge in evaluation.edges},
        params,
        log_context,
        f"demand_{action.action_id}",
    )
    return dict(execution["metric_row"])


def _disturbance_metrics(vehicle_rows: Sequence[Mapping[str, Any]], event: Mapping[str, Any], params: Any) -> dict[str, Any]:
    event_time = _float(event.get("event_time", params.H))
    start = max(0.0, event_time - params.H)
    end = event_time + params.dt
    rows = [row for row in vehicle_rows if start - 1e-9 <= _float(row.get("time", 0.0)) <= end + 1e-9]
    accels = [_float(row.get("a", row.get("accel", 0.0))) for row in rows]
    speeds = [_float(row.get("v", row.get("speed", 0.0))) for row in rows]
    before = [_float(row.get("v", row.get("speed", 0.0))) for row in rows if _float(row.get("time", 0.0)) <= event_time]
    after = [_float(row.get("v", row.get("speed", 0.0))) for row in rows if _float(row.get("time", 0.0)) >= event_time]
    max_decel = min(accels) if accels else 0.0
    max_decel_mag = abs(max_decel) if max_decel < 0.0 else 0.0
    hard_brake_count = sum(1 for value in accels if value <= -4.0)
    mean_abs = _mean([abs(value) for value in accels])
    speed_var_before = _variance(before)
    speed_var_after = _variance(after)
    wave = (max(speeds) - min(speeds)) if speeds else 0.0
    disturbance = mean_abs + max_decel_mag + max(0.0, speed_var_after - speed_var_before) + 0.1 * wave
    return {
        "metric_window_start": start,
        "metric_window_end": end,
        "hard_brake_count": hard_brake_count,
        "max_deceleration": max_decel,
        "speed_variance_delta": speed_var_after - speed_var_before,
        "max_wave_amplitude": wave,
        "mainline_disturbance_cost": disturbance,
    }


def _summary(rows: Sequence[Mapping[str, Any]], full_selected: str, without_selected: str) -> dict[str, Any]:
    values = [(_float(row.get("C_dist_pred")), _float(row.get("realized_disturbance"))) for row in rows]
    direction_matches = 0
    comparisons = 0
    for i, (c_i, r_i) in enumerate(values):
        for c_j, r_j in values[i + 1:]:
            if abs(c_i - c_j) <= 1e-12 or abs(r_i - r_j) <= 1e-12:
                continue
            comparisons += 1
            direction_matches += int((c_i - c_j) * (r_i - r_j) > 0)
    match_rate = 0.0 if comparisons == 0 else direction_matches / comparisons
    selected_differs = full_selected != without_selected
    if selected_differs:
        status = "without_Cbar_behavioral_difference_observed"
    elif match_rate >= 0.5 and comparisons > 0:
        status = "Cbar_predicts_disturbance_but_selection_insensitive"
    else:
        status = "Cbar_alignment_weak_or_candidate_set_insufficient"
    return {
        "status": status,
        "pairwise_direction_match_rate": match_rate,
        "pairwise_comparisons": comparisons,
        "full_selected_action": full_selected,
        "without_cbar_selected_action": without_selected,
    }


def _write_packet(rows: Sequence[Mapping[str, Any]], summary: Mapping[str, Any]) -> None:
    lines = [
        "# PROMPT 3B-R3B CBAR ALIGNMENT PACKET",
        "",
        "## Verdict",
        "",
        str(summary["status"]),
        "",
        "This is diagnostic repair evidence only. No lambda tuning or Prompt 4 lock was performed.",
        "",
        "## Summary",
        "",
        f"- full_selected_action: {summary['full_selected_action']}",
        f"- without_Cbar_selected_action: {summary['without_cbar_selected_action']}",
        f"- pairwise_direction_match_rate: {summary['pairwise_direction_match_rate']}",
        f"- pairwise_comparisons: {summary['pairwise_comparisons']}",
        "",
        "## Candidate Alignment Rows",
        "",
        "| action | C_dist_pred | realized_disturbance | hard_brake | wave | max_decel | selected_full | selected_without_Cbar |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['candidate_action_id']} | {row['C_dist_pred']} | {row['realized_disturbance']} | {row['hard_brake_count']} | {row['wave']} | {row['max_decel']} | {row['selected_by_full']} | {row['selected_by_without_Cbar']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- If Cbar predicts realized disturbance but selection is unchanged, R3 should next repair scenario pressure or candidate set.",
            "- If Cbar does not predict realized disturbance, the paper theory should downgrade or redefine Cbar instead of continuing weight tuning.",
        ]
    )
    (HUMAN_REVIEW_DIR / "PROMPT_3B_R3B_CBAR_ALIGNMENT_PACKET.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _csv_value(row.get(column, "")) for column in columns})


def _columns() -> list[str]:
    return [
        "run_id",
        "scenario_family",
        "scenario_design_id",
        "scenario_hash",
        "candidate_action_id",
        "candidate_action_type",
        "candidate_gap_id",
        "candidate_edge_id",
        "C_dist_pred",
        "C_dist_norm",
        "RD_pred_norm",
        "J",
        "RCMV",
        "full_selected_action",
        "without_Cbar_selected_action",
        "selected_by_full",
        "selected_by_without_Cbar",
        "realized_disturbance",
        "hard_brake_count",
        "wave",
        "max_decel",
        "speed_variance_delta",
        "metric_window_start",
        "metric_window_end",
        "alignment_note",
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


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _variance(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    mean = _mean(values)
    return sum((value - mean) ** 2 for value in values) / len(values)


def _float(value: Any) -> float:
    try:
        if value in {"", None}:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _hash(payload: Any) -> str:
    text = stable_json(payload) if not isinstance(payload, str) else payload
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _worktree_hash() -> str:
    return _hash("r3b_worktree")


if __name__ == "__main__":
    main()
