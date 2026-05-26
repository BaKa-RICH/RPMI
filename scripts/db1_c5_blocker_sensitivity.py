"""DB1 C5 blocker sensitivity probe.

This script keeps the DB1 CAV-HDV/front-acceleration audit narrow and only
varies raw gap, H, and T_prod. It does not tune lambda, change the objective,
create locked evidence, or expand to other boundary/lane-change mechanisms.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
import copy
import csv
import json
import shutil
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
for path in (REPO_ROOT, SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import scripts.db1_c5_mechanism_audit as audit

from rpmi.actions import action_evaluation_to_row, action_to_row, find_near_miss_edges, generate_candidate_actions, run_action_selection, slot_inventory_params
from rpmi.ids import make_decision_context_id
from rpmi.reservations import reservation_to_row
from rpmi.scenarios import ScenarioConfig, generate_state, no_action_rollout, scenario_config_hash
from rpmi.state import TrafficState, hash_state
from rpmi.reproducibility import get_code_version


OUTPUT_ROOT = REPO_ROOT / "outputs" / "d2_5_theory_alignment" / "DB1_audit"
VARIANT_SCHEMA_VERSION = "DB1_blocker_sensitivity_v1"


@dataclass(frozen=True)
class ProbeVariant:
    variant_id: str
    group: str
    raw_gap: float
    H: float
    T_prod: float
    target_tau: float = 3.5


def main() -> None:
    run_dir = _prepare_run_dir()
    code_version = get_code_version(REPO_ROOT)
    variants = _build_required_variants()
    rows: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []

    for variant in variants:
        result = run_variant(variant, run_dir, code_version)
        rows.append(result["row"])
        summaries.append(result["summary"])
    time_variants_crossed = any(
        row["group"] == "time_window"
        and row["best_front_acc_W"] is not None
        and float(row["best_front_acc_W"]) >= 0.0
        for row in rows
    )
    if not time_variants_crossed:
        optional = ProbeVariant("gap55_H8_Tprod50", "time_window_optional", 55.0, 8.0, 5.0)
        result = run_variant(optional, run_dir, code_version)
        rows.append(result["row"])
        summaries.append(result["summary"])

    overall = _overall_summary(run_dir, code_version, rows, summaries)
    _write_json(run_dir / "DB1_blocker_sensitivity_summary.json", overall)
    _write_csv(run_dir / "DB1_blocker_sensitivity_summary.csv", rows, _summary_columns())

    locked_files = list(run_dir.rglob("LOCKED_*")) + list(OUTPUT_ROOT.rglob("LOCKED_*"))
    if locked_files:
        raise RuntimeError(f"forbidden LOCKED_* outputs found: {[str(path) for path in locked_files]}")

    print(f"db1_sensitivity_run_dir={run_dir}")
    print(f"db1_sensitivity_summary_json={run_dir / 'DB1_blocker_sensitivity_summary.json'}")
    print(f"db1_sensitivity_summary_csv={run_dir / 'DB1_blocker_sensitivity_summary.csv'}")
    for row in rows:
        print(
            "variant="
            f"{row['variant_id']} "
            f"gap={row['raw_gap']} H={row['H']} T_prod={row['T_prod']} "
            f"best_W={row['best_front_acc_W']} selected={row['selected_action_id']} "
            f"classification={row['classification']}"
        )


def run_variant(variant: ProbeVariant, run_dir: Path, code_version: str) -> dict[str, Any]:
    config = _variant_config(variant)
    state = generate_state(config)
    params = audit.db1_action_config(config)
    slot_params = slot_inventory_params(params)
    variant_dir = run_dir / variant.variant_id
    variant_dir.mkdir(parents=True, exist_ok=True)
    decision_context_id = make_decision_context_id(variant.variant_id, 0)
    log_context = _log_context(variant, decision_context_id, state, config, code_version)

    no_action = audit._inventory_for_rollout(
        no_action_rollout(state, config),
        state,
        slot_params,
        eval_context="baseline",
        action_id=None,
        params=params,
    )
    near_misses = find_near_miss_edges(no_action["qualities"], no_action["edge_map"], state, params)
    candidate_actions = generate_candidate_actions(near_misses, no_action["edge_map"], state, params)
    result = run_action_selection(state, no_action["qualities"], no_action["edge_map"], params)
    selected = result.selected_evaluation
    selected_action = result.selected_action
    action_inventory = audit._inventory_from_evaluation(selected)
    reservations = audit._create_reservations(selected, decision_context_id, slot_params)
    execution = audit._execute_guided_episode(
        state,
        selected_action,
        reservations,
        action_inventory["edge_map"],
        params,
        slot_params,
    )

    summary = audit._summary(
        config,
        state,
        params,
        slot_params,
        no_action,
        result,
        reservations,
        execution,
        code_version,
    )
    records = audit._trace_records(
        config,
        state,
        params,
        slot_params,
        no_action,
        action_inventory,
        result,
        candidate_actions,
        reservations,
        execution,
        log_context,
    )
    best = _best_front_acc_probe(result, candidate_actions)
    matched = _matched_front_acc_probe(result, candidate_actions)
    row = _variant_row(
        variant,
        config,
        state,
        no_action,
        result,
        summary,
        best,
        matched,
        execution,
    )
    _assert_variant_invariants(row, result)

    _write_json(variant_dir / "DB1_blocker_variant_summary.json", {"row": row, "audit_summary": summary})
    _write_jsonl(variant_dir / "DB1_blocker_variant_trace.jsonl", records)
    _write_csv(variant_dir / "DB1_blocker_no_action_edges.csv", audit._edge_rows(no_action, log_context), audit._edge_columns())
    _write_csv(variant_dir / "DB1_blocker_selected_action_edges.csv", audit._edge_rows(action_inventory, log_context), audit._edge_columns())
    _write_csv(
        variant_dir / "DB1_blocker_counterfactual_action_edges.csv",
        audit._counterfactual_action_edge_rows(result, log_context),
        audit._counterfactual_edge_columns(),
    )
    _write_csv(
        variant_dir / "DB1_blocker_actions.csv",
        [action_to_row(action, log_context) for action in audit._actions_for_log(result, candidate_actions)],
        audit._action_columns(),
    )
    _write_csv(
        variant_dir / "DB1_blocker_action_evaluations.csv",
        [action_evaluation_to_row(evaluation, log_context) for evaluation in result.evaluations],
        audit._action_evaluation_columns(),
    )
    _write_csv(
        variant_dir / "DB1_blocker_reservations.csv",
        [reservation_to_row(item, log_context) for item in execution["reservations"]],
        audit._reservation_columns(),
    )

    return {"row": row, "summary": summary}


def _build_required_variants() -> list[ProbeVariant]:
    variants = [
        ProbeVariant("gap55_H4_Tprod35", "raw_gap", 55.0, 4.0, 3.5),
        ProbeVariant("gap56_H4_Tprod35", "raw_gap", 56.0, 4.0, 3.5),
        ProbeVariant("gap57_H4_Tprod35", "raw_gap", 57.0, 4.0, 3.5),
        ProbeVariant("gap58_H4_Tprod35", "raw_gap", 58.0, 4.0, 3.5),
        ProbeVariant("gap55_H8_Tprod35", "time_window", 55.0, 8.0, 3.5),
        ProbeVariant("gap55_H8_Tprod40", "time_window", 55.0, 8.0, 4.0),
        ProbeVariant("gap55_H8_Tprod45", "time_window", 55.0, 8.0, 4.5),
    ]
    return variants


def _variant_config(variant: ProbeVariant) -> ScenarioConfig:
    base = audit.build_db1_scenario_config()
    simulation = copy.deepcopy(base.simulation)
    vehicles = copy.deepcopy(base.vehicles)
    mechanism_targets = copy.deepcopy(base.mechanism_targets)
    simulation["H"] = variant.H
    simulation["T_prod"] = variant.T_prod
    vehicles["gap_widths"] = [variant.raw_gap]
    vehicles["ramp_start_x"] = _ramp_start_for_gap(variant.raw_gap, variant.target_tau)
    mechanism_targets["target_designed_tau"] = variant.target_tau
    mechanism_targets["sensitivity_variant_id"] = variant.variant_id
    mechanism_targets["sensitivity_group"] = variant.group
    scenario_id = f"DB1-C5-CAV-HDV-FRONTACC-V20-GAP{int(variant.raw_gap)}-H{_tag_float(variant.H)}-TPROD{_tag_float(variant.T_prod)}"
    return ScenarioConfig(
        scenario_id=scenario_id,
        seed=base.seed,
        road=copy.deepcopy(base.road),
        simulation=simulation,
        vehicles=vehicles,
        ramp=copy.deepcopy(base.ramp),
        mechanism_targets=mechanism_targets,
        readiness_targets=copy.deepcopy(base.readiness_targets),
    )


def _ramp_start_for_gap(raw_gap: float, target_tau: float) -> float:
    front_x0 = 100.0
    front_length = 5.0
    rear_x0 = front_x0 - front_length - raw_gap
    speed = 20.0
    ramp_length = 5.0
    d_front = 2.0 + 1.2 * speed
    d_rear = 2.0 + 1.6 * speed
    front_x_tau = front_x0 + speed * target_tau
    rear_x_tau = rear_x0 + speed * target_tau
    lower = rear_x_tau + ramp_length + d_rear
    upper = front_x_tau - front_length - d_front
    planned_mid_x_tau = (lower + upper) / 2.0
    return planned_mid_x_tau - speed * target_tau


def _best_front_acc_probe(result: Any, candidate_actions: Sequence[Any]) -> dict[str, Any]:
    best: dict[str, Any] = {
        "action_id": "",
        "tau": None,
        "W": None,
        "is_reservable": False,
        "reason": "",
        "matched": False,
        "matched_edge_ids": [],
        "J": None,
        "RCMV": None,
        "Z_bar": None,
        "D_bar": None,
        "C_bar": None,
        "u_front": None,
        "T_prod": None,
        "controlled_cavs": [],
    }
    actions_by_id = {action.action_id: action for action in candidate_actions}
    actions_by_id[result.selected_action.action_id] = result.selected_action
    for evaluation in result.evaluations:
        action = actions_by_id.get(evaluation.action_id)
        if action is None or action.action_type != "front_acc":
            continue
        target_qualities = []
        for edge, quality in zip(evaluation.edges, evaluation.edge_qualities):
            if edge.ramp_id == 100 and edge.front_id == 1 and edge.rear_id == 2:
                target_qualities.append((edge, quality))
        if not target_qualities:
            continue
        edge, quality = max(target_qualities, key=lambda item: (item[1].W, item[0].tau))
        if best["W"] is None or quality.W > float(best["W"]):
            best = {
                "action_id": evaluation.action_id,
                "tau": edge.tau,
                "W": quality.W,
                "is_reservable": bool(quality.is_reservable),
                "reason": quality.reason_not_reservable or quality.fail_reason_priority,
                "matched": edge.edge_id in set(evaluation.matched_edge_ids),
                "matched_edge_ids": list(evaluation.matched_edge_ids),
                "J": evaluation.J,
                "RCMV": evaluation.RCMV,
                "Z_bar": evaluation.Z_bar,
                "D_bar": evaluation.D_bar,
                "C_bar": evaluation.C_bar,
                "u_front": action.control_profile.get("u_front"),
                "T_prod": action.control_profile.get("T_prod"),
                "controlled_cavs": list(action.controlled_cavs),
            }
    return best


def _matched_front_acc_probe(result: Any, candidate_actions: Sequence[Any]) -> dict[str, Any]:
    actions_by_id = {action.action_id: action for action in candidate_actions}
    actions_by_id[result.selected_action.action_id] = result.selected_action
    best: dict[str, Any] = {
        "action_id": "",
        "edge_id": "",
        "tau": None,
        "W": None,
        "is_reservable": False,
        "reason": "",
        "J": None,
        "RCMV": None,
        "Z_bar": None,
        "D_bar": None,
        "C_bar": None,
        "u_front": None,
        "T_prod": None,
        "controlled_cavs": [],
    }
    for evaluation in result.evaluations:
        action = actions_by_id.get(evaluation.action_id)
        if action is None or action.action_type != "front_acc":
            continue
        matched_ids = set(evaluation.matched_edge_ids)
        if not matched_ids:
            continue
        quality_by_id = {quality.edge_id: quality for quality in evaluation.edge_qualities}
        for edge in evaluation.edges:
            if edge.edge_id not in matched_ids:
                continue
            if edge.ramp_id != 100 or edge.front_id != 1 or edge.rear_id != 2:
                continue
            quality = quality_by_id.get(edge.edge_id)
            if quality is None:
                continue
            if best["W"] is None or quality.W > float(best["W"]):
                best = {
                    "action_id": evaluation.action_id,
                    "edge_id": edge.edge_id,
                    "tau": edge.tau,
                    "W": quality.W,
                    "is_reservable": bool(quality.is_reservable),
                    "reason": quality.reason_not_reservable or quality.fail_reason_priority,
                    "J": evaluation.J,
                    "RCMV": evaluation.RCMV,
                    "Z_bar": evaluation.Z_bar,
                    "D_bar": evaluation.D_bar,
                    "C_bar": evaluation.C_bar,
                    "u_front": action.control_profile.get("u_front"),
                    "T_prod": action.control_profile.get("T_prod"),
                    "controlled_cavs": list(action.controlled_cavs),
                }
    return best


def _variant_row(
    variant: ProbeVariant,
    config: ScenarioConfig,
    state: TrafficState,
    no_action: Mapping[str, Any],
    result: Any,
    summary: Mapping[str, Any],
    best: Mapping[str, Any],
    matched: Mapping[str, Any],
    execution: Mapping[str, Any],
) -> dict[str, Any]:
    target_qualities = _target_qualities(no_action)
    target_tau_quality = _quality_at_tau(target_qualities, variant.target_tau)
    no_action_reservable_taus = [edge.tau for edge, quality in target_qualities if quality.is_reservable]
    selected_eval = result.selected_evaluation
    selected_reservation = summary["selected_reservation"]
    classification = _classification(summary, best, matched)
    return {
        "schema_version": VARIANT_SCHEMA_VERSION,
        "variant_id": variant.variant_id,
        "group": variant.group,
        "scenario_id": config.scenario_id,
        "scenario_hash": scenario_config_hash(config),
        "state_hash": hash_state(state),
        "raw_gap": variant.raw_gap,
        "H": variant.H,
        "T_prod": variant.T_prod,
        "target_tau": variant.target_tau,
        "ramp_start_x": config.vehicles.get("ramp_start_x"),
        "no_action_all_target_edges_invalid": all(not quality.is_reservable for _, quality in target_qualities),
        "no_action_reservable_taus": no_action_reservable_taus,
        "no_action_target_tau_W": None if target_tau_quality is None else target_tau_quality.W,
        "no_action_target_tau_reason": None if target_tau_quality is None else target_tau_quality.fail_reason_priority,
        "no_action_front_accel_abs_max": summary["no_action"]["front_accel_abs_max"],
        "no_action_rear_min_accel": summary["no_action"]["rear_min_accel"],
        "no_action_ramp_accel_abs_max": summary["no_action"]["ramp_accel_abs_max"],
        "best_front_acc_action_id": best.get("action_id", ""),
        "best_front_acc_controlled_cavs": best.get("controlled_cavs", []),
        "best_front_acc_tau": best.get("tau"),
        "best_front_acc_u_front": best.get("u_front"),
        "best_front_acc_effective_T_prod": best.get("T_prod"),
        "best_front_acc_W": best.get("W"),
        "best_front_acc_W_ge_0": bool(best.get("W") is not None and float(best["W"]) >= 0.0),
        "best_front_acc_is_reservable": bool(best.get("is_reservable")),
        "best_front_acc_reason": best.get("reason", ""),
        "best_front_acc_matched": bool(best.get("matched")),
        "best_front_acc_matched_edge_ids": best.get("matched_edge_ids", []),
        "best_front_acc_J": best.get("J"),
        "best_front_acc_RCMV": best.get("RCMV"),
        "best_front_acc_Z_bar": best.get("Z_bar"),
        "best_front_acc_D_bar": best.get("D_bar"),
        "best_front_acc_C_bar": best.get("C_bar"),
        "matched_front_acc_action_id": matched.get("action_id", ""),
        "matched_front_acc_edge_id": matched.get("edge_id", ""),
        "matched_front_acc_tau": matched.get("tau"),
        "matched_front_acc_W": matched.get("W"),
        "matched_front_acc_is_reservable": bool(matched.get("is_reservable")),
        "matched_front_acc_reason": matched.get("reason", ""),
        "matched_front_acc_J": matched.get("J"),
        "matched_front_acc_RCMV": matched.get("RCMV"),
        "matched_front_acc_Z_bar": matched.get("Z_bar"),
        "matched_front_acc_D_bar": matched.get("D_bar"),
        "matched_front_acc_C_bar": matched.get("C_bar"),
        "selected_action_id": result.selected_action.action_id,
        "selected_action_type": result.selected_action.action_type,
        "selected_controlled_cavs": list(result.selected_action.controlled_cavs),
        "selected_J": selected_eval.J,
        "selected_RCMV": selected_eval.RCMV,
        "selected_Z_bar": selected_eval.Z_bar,
        "selected_D_bar": selected_eval.D_bar,
        "selected_C_bar": selected_eval.C_bar,
        "selected_matched_edge_ids": list(selected_eval.matched_edge_ids),
        "selected_reservation_source": selected_reservation.get("source"),
        "selected_reservation_status": selected_reservation.get("status"),
        "selected_reservation_W": selected_reservation.get("W"),
        "selected_reservation_tau": selected_reservation.get("planned_tau"),
        "reservation_count": len(execution["reservations"]),
        "blocker_is_blocker": summary["blocker"]["is_blocker"],
        "blocker_kind": summary["blocker"]["kind"],
        "blocker_reasons": summary["blocker"]["reasons"],
        "classification": classification,
    }


def _classification(summary: Mapping[str, Any], best: Mapping[str, Any], matched: Mapping[str, Any]) -> str:
    selected = summary["selected_action"]
    selected_reservation = summary["selected_reservation"]
    best_crossed = best.get("W") is not None and float(best["W"]) >= 0.0
    matched_crossed = matched.get("W") is not None and float(matched["W"]) >= 0.0
    matched_reservable = bool(matched.get("is_reservable"))
    selected_front_acc = selected.get("action_type") == "front_acc"
    selected_action_conditioned = selected_reservation.get("source") == "action_conditioned"
    if matched_crossed and matched_reservable and selected_front_acc and selected_action_conditioned:
        return "front_acc_selected_after_W_crossed"
    if matched_crossed and matched_reservable and not selected_front_acc:
        return "objective_alignment_blocker_after_W_crossed"
    if best_crossed and not matched_reservable:
        return "matching_or_reservation_blocker_after_W_crossed"
    if selected_reservation.get("source") == "baseline_or_none" and not best_crossed:
        return "action_rollout_still_below_W0"
    return "implementation_objective_blocker"


def _target_qualities(inventory: Mapping[str, Any]) -> list[tuple[Any, Any]]:
    return [
        (edge, quality)
        for edge, quality in zip(inventory["edges"], inventory["qualities"])
        if edge.ramp_id == 100 and edge.front_id == 1 and edge.rear_id == 2
    ]


def _quality_at_tau(items: Sequence[tuple[Any, Any]], tau: float) -> Any | None:
    for edge, quality in items:
        if abs(edge.tau - tau) <= 1e-9:
            return quality
    return None


def _assert_variant_invariants(row: Mapping[str, Any], result: Any) -> None:
    if row["selected_reservation_source"] == "action_conditioned":
        edge_ids = row["selected_matched_edge_ids"]
        if not edge_ids or not all("_act_" in str(edge_id) for edge_id in edge_ids):
            raise AssertionError(f"{row['variant_id']}: selected reservation source is action_conditioned but edge ids are stale")
    if result.selected_action.action_type != "none" and row["selected_reservation_source"] == "baseline_or_none":
        # This is allowed only when there is no selected reservation.
        if row["selected_matched_edge_ids"]:
            raise AssertionError(f"{row['variant_id']}: selected non-none action matched baseline edges")


def _overall_summary(
    run_dir: Path,
    code_version: str,
    rows: Sequence[Mapping[str, Any]],
    summaries: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    successful = [
        row
        for row in rows
        if row["classification"] == "front_acc_selected_after_W_crossed"
    ]
    objective_blockers = [
        row
        for row in rows
        if row["classification"] == "objective_alignment_blocker_after_W_crossed"
    ]
    time_h8_tprod35_success = any(
        row["variant_id"] == "gap55_H8_Tprod35" and row["classification"] == "front_acc_selected_after_W_crossed"
        for row in rows
    )
    h4_success = any(
        row["group"] == "raw_gap" and row["classification"] == "front_acc_selected_after_W_crossed"
        for row in rows
    )
    tprod_gt_35_success = any(
        row["group"] == "time_window"
        and float(row["T_prod"]) > 3.5
        and row["classification"] == "front_acc_selected_after_W_crossed"
        for row in rows
    )
    if successful:
        if objective_blockers:
            interpretation = "mixed: some variants succeed while at least one W-crossed matched variant still selects a0"
        elif h4_success:
            interpretation = "objective_not_primary; original DB1-C5 is likely too close to the hard W boundary"
        elif time_h8_tprod35_success:
            interpretation = "same 3.5s production may need a later candidate time within a longer horizon"
        elif tprod_gt_35_success:
            interpretation = "production window longer than 3.5s is needed under current rollout and dynamic safety distances"
        else:
            interpretation = "front_acc can succeed in sensitivity variants"
    elif objective_blockers:
        interpretation = "objective_alignment_blocker_after_W_crossed"
    else:
        interpretation = "all_light_relaxations_still_fail; inspect action profile estimate versus rollout"
    return {
        "schema_version": VARIANT_SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_dir": str(run_dir),
        "code_version": code_version,
        "forbidden_outputs": {"locked_files_created": False, "performance_claim": False},
        "variant_count": len(rows),
        "successful_variant_ids": [row["variant_id"] for row in successful],
        "objective_blocker_variant_ids": [row["variant_id"] for row in objective_blockers],
        "interpretation": interpretation,
        "rows": list(rows),
        "audit_summaries": list(summaries),
    }


def _log_context(
    variant: ProbeVariant,
    decision_context_id: str,
    state: TrafficState,
    config: ScenarioConfig,
    code_version: str,
) -> dict[str, Any]:
    return {
        "run_id": variant.variant_id,
        "step": 0,
        "time": 0.0,
        "decision_context_id": decision_context_id,
        "state_hash": hash_state(state),
        "config_hash": scenario_config_hash(config),
        "code_version": code_version,
        "units_version": "rpmi_units_v1",
        "scenario_id": config.scenario_id,
        "seed": config.seed,
        "algorithm_id": audit.VARIANT,
    }


def _prepare_run_dir() -> Path:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = OUTPUT_ROOT / f"DB1_blocker_sensitivity_{stamp}"
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)
    return run_dir


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(_json_safe(row), ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _csv_value(row.get(column, "")) for column in columns})


def _csv_value(value: Any) -> Any:
    if isinstance(value, (list, tuple, dict)):
        return json.dumps(_json_safe(value), ensure_ascii=False, sort_keys=True)
    return value


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "item"):
        return value.item()
    return value


def _tag_float(value: float) -> str:
    return str(value).replace(".", "p")


def _summary_columns() -> list[str]:
    return [
        "schema_version",
        "variant_id",
        "group",
        "scenario_id",
        "raw_gap",
        "H",
        "T_prod",
        "target_tau",
        "ramp_start_x",
        "no_action_all_target_edges_invalid",
        "no_action_reservable_taus",
        "no_action_target_tau_W",
        "no_action_target_tau_reason",
        "best_front_acc_action_id",
        "best_front_acc_controlled_cavs",
        "best_front_acc_tau",
        "best_front_acc_u_front",
        "best_front_acc_effective_T_prod",
        "best_front_acc_W",
        "best_front_acc_W_ge_0",
        "best_front_acc_is_reservable",
        "best_front_acc_reason",
        "best_front_acc_matched",
        "best_front_acc_matched_edge_ids",
        "best_front_acc_J",
        "best_front_acc_RCMV",
        "best_front_acc_Z_bar",
        "best_front_acc_D_bar",
        "best_front_acc_C_bar",
        "matched_front_acc_action_id",
        "matched_front_acc_edge_id",
        "matched_front_acc_tau",
        "matched_front_acc_W",
        "matched_front_acc_is_reservable",
        "matched_front_acc_reason",
        "matched_front_acc_J",
        "matched_front_acc_RCMV",
        "matched_front_acc_Z_bar",
        "matched_front_acc_D_bar",
        "matched_front_acc_C_bar",
        "selected_action_id",
        "selected_action_type",
        "selected_controlled_cavs",
        "selected_J",
        "selected_RCMV",
        "selected_Z_bar",
        "selected_D_bar",
        "selected_C_bar",
        "selected_matched_edge_ids",
        "selected_reservation_source",
        "selected_reservation_status",
        "selected_reservation_W",
        "selected_reservation_tau",
        "reservation_count",
        "blocker_is_blocker",
        "blocker_kind",
        "blocker_reasons",
        "classification",
        "scenario_hash",
        "state_hash",
        "no_action_front_accel_abs_max",
        "no_action_rear_min_accel",
        "no_action_ramp_accel_abs_max",
    ]


if __name__ == "__main__":
    main()
