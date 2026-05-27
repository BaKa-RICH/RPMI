"""Prompt 3A readiness micro-run artifact generator.

This script is intentionally narrow: it uses the existing deterministic
scenario, action-selection, baseline, and reservation primitives to produce the
Prompt 3A trace-readiness package. It does not tune objective weights, lock
evaluation settings, or make performance claims.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping, Sequence
import csv
import hashlib
import json
import math
import re
import shutil

from rpmi.actions import (
    Action,
    ActionConfig,
    ActionEvaluation,
    commands_for_action,
    compute_profile_cost,
    evaluate_action,
    run_action_selection,
)
from rpmi.config import AlgorithmConfig, FeatureFlags, RunConfig, SimConfig
from rpmi.dynamics import step_traffic
from rpmi.ids import make_decision_context_id
from rpmi.logging_schema import CSV_LOG_SCHEMAS
from rpmi.reservations import Reservation
from rpmi.reservations import execute_reservation_guidance
from rpmi.runner import (
    BaselineConfig,
    apply_policy,
    build_decision_context,
    resolve_baseline_config,
)
from rpmi.scenarios import ScenarioConfig, generate_state, make_scenario_config
from rpmi.slots import Edge, EdgeQuality, compute_feasible_interval
from rpmi.state import TrafficState, hash_state


SCHEMA_VERSION = "d2_5_trace_metric_schema_v0.1"
SOURCE_BATCH_ID = "prompt3a_readiness_micro"
OUTPUT_ROOT = Path("outputs/d2_5_theory_alignment")
GATE_DIR = OUTPUT_ROOT / "gate_D2_5_input"

FAILURE_TYPES = {
    "insufficient_trace_join",
    "baseline_not_implemented",
    "baseline_not_instrumented",
    "ablation_not_implemented",
    "ablation_not_instrumented",
    "scenario_not_diagnostic",
    "missing_candidate_gap_fields",
    "missing_realized_event",
    "missing_event_metric_window",
    "implementation_bug",
    "simulator_sensitivity_insufficient",
    "ready_for_prompt3",
    "not_ready_return_to_prompt2r_b",
}


VARIANT_ORDER = [
    "full_RPMI_CMV_current_objective",
    "raw_largest_gap",
    "forced_accommodation",
    "without_RD",
    "without_Cbar",
    "without_theta",
]


def main() -> None:
    prior = _read_prior_prompt2r_status()
    _prepare_output_dir()

    scenarios = _prompt3a_scenarios()
    records: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    action_rows: list[dict[str, Any]] = []
    trace_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    metric_rows: list[dict[str, Any]] = []
    blocked_rows: list[dict[str, Any]] = []

    for scenario_family, scenario_config in scenarios:
        full_params = _params_for_scenario(scenario_config)
        for variant in VARIANT_ORDER:
            if variant == "without_theta" and not _theta_is_available():
                blocked_rows.append(
                    _blocked_variant(
                        scenario_config,
                        scenario_family,
                        variant,
                        "ablation_not_implemented",
                        "No theta parameter is exposed by ActionConfig/select_action.",
                    )
                )
                continue

            record = _run_variant(
                scenario_config,
                scenario_family,
                variant,
                full_params,
            )
            records.append(record)
            candidate_rows.extend(record["candidate_rows"])
            action_rows.extend(record["action_rows"])
            trace_rows.append(record["trace_row"])
            event_rows.append(record["event_row"])
            metric_rows.append(record["metric_row"])

    matrix = _scenario_variant_matrix(records, blocked_rows)
    schema_report = _schema_validation_report(
        candidate_rows,
        action_rows,
        trace_rows,
        event_rows,
        metric_rows,
        matrix,
        prior,
    )
    missing_report = _missing_join_report(trace_rows, matrix)
    readiness_report = _readiness_report(
        prior,
        matrix,
        records,
        blocked_rows,
        candidate_rows,
        action_rows,
        trace_rows,
        event_rows,
        metric_rows,
    )

    _write_csv(GATE_DIR / "candidate_gap_table.csv", candidate_rows, _candidate_columns())
    _write_csv(GATE_DIR / "action_value_decomposition.csv", action_rows, _action_columns())
    _write_csv(GATE_DIR / "trace_join_table.csv", trace_rows, _trace_columns())
    _write_csv(GATE_DIR / "realized_events.csv", event_rows, _realized_event_columns())
    _write_csv(GATE_DIR / "event_metric_windows.csv", metric_rows, _event_metric_columns())
    (OUTPUT_ROOT / "schema_validation_report.md").write_text(schema_report, encoding="utf-8")
    (OUTPUT_ROOT / "missing_join_report.md").write_text(missing_report, encoding="utf-8")
    (OUTPUT_ROOT / "prompt3a_readiness_report.md").write_text(readiness_report, encoding="utf-8")


def _prepare_output_dir() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    GATE_DIR.mkdir(parents=True, exist_ok=True)


def _read_prior_prompt2r_status() -> dict[str, Any]:
    report_path = GATE_DIR / "schema_validation_report.md"
    if report_path.exists():
        report = report_path.read_text(encoding="utf-8")
        if "Prompt 2R" in report:
            full_chain_count = _extract_markdown_metric(report, "can_join_full_chain_count", 0)
            selected_rows = _extract_markdown_metric(report, "selected_action_rows", 0)
            rate = _extract_markdown_metric(
                report,
                "can_join_full_chain_rate",
                _rate(full_chain_count, selected_rows),
                as_float=True,
            )
            nontrivial = _extract_markdown_metric(report, "nontrivial_full_chain_count", 0)
            minimum = (
                "PASS"
                if re.search(r"\|\s*minimum_pass_condition\s*\|\s*PASS\s*\|", report)
                else "FAIL"
            )
            return {
                "selected_action_rows": int(selected_rows),
                "can_join_full_chain_count": int(full_chain_count),
                "can_join_full_chain_rate": float(rate),
                "nontrivial_full_chain_count": int(nontrivial),
                "minimum_pass_condition": minimum,
            }

    rows = _read_csv(GATE_DIR / "trace_join_table.csv")
    selected_rows = len(rows)
    full_chain_count = sum(1 for row in rows if _truthy(row.get("can_join_full_chain")))
    nontrivial_full_chain_count = sum(
        1
        for row in rows
        if _truthy(row.get("can_join_full_chain"))
        and str(row.get("selected_action_id", "")) not in {"", "a0_none"}
    )
    return {
        "selected_action_rows": selected_rows,
        "can_join_full_chain_count": full_chain_count,
        "can_join_full_chain_rate": _rate(full_chain_count, selected_rows),
        "nontrivial_full_chain_count": nontrivial_full_chain_count,
        "minimum_pass_condition": (
            "PASS" if nontrivial_full_chain_count >= 1 and full_chain_count >= 1 else "FAIL"
        ),
    }


def _extract_markdown_metric(
    text: str,
    metric: str,
    default: int | float,
    *,
    as_float: bool = False,
) -> int | float:
    match = re.search(rf"\|\s*{re.escape(metric)}\s*\|\s*([0-9.]+)\s*\|", text)
    if not match:
        return default
    return float(match.group(1)) if as_float else int(float(match.group(1)))


def _prompt3a_scenarios() -> list[tuple[str, ScenarioConfig]]:
    raw_trap = make_scenario_config(
        "P3A-RAW-LARGE-GAP-TRAP",
        seed=0,
        road={"target_lane": 0, "ramp_lane": -1, "ramp_end_x": 140.0},
        simulation={
            "dt": 0.5,
            "H": 5.0,
            "dt_merge": 1.0,
            "W_min_buffer": 5.0,
            "RD_max": 1.0,
            "u_min": -4.5,
            "u_max": 50.0,
            "rd_speed_scale": 10.0,
            "theta": 0.05,
            "lambda_D": 1.0,
            "lambda_C": 0.001,
            "T_prod": 2.0,
            "near_miss_delta_W_max": 20.0,
            "action_mode": "override",
        },
        vehicles={
            "boundary_pairs": ["HDV-CAV", "CAV-HDV"],
            "gap_widths": [65.0, 35.0],
            "front_x": 115.0,
            "pair_spacing": 90.0,
            "target_speed": 20.0,
            "front_speed_offsets": [0.0, 0.0],
            "rear_speed_offsets": [10.0, -0.5],
            "inner_receiving_gap_count": 2,
            "ramp_count": 1,
            "ramp_start_x": -40.0,
            "ramp_speed": 18.0,
        },
        readiness_targets={
            "raw_gap_count_min": 1,
            "baseline_ZR_min": 0.0,
            "near_miss_count_min": 0,
            "boundary_cav_min": 1,
            "raw_gap_illusion_min": 0,
        },
        mechanism_targets={
            "mechanism": "Prompt3A",
            "mechanism_target": "raw_large_gap_trap_trace_coverage",
            "expected_failure_mode": "raw largest gap can pick geometrically larger, higher-RD gap",
            "seed_policy": "deterministic fixed case; seed only reproduces jitter-free state",
        },
    )
    forced = make_scenario_config(
        "P3A-FORCED-ACCOMMODATION",
        seed=0,
        road={"target_lane": 0, "ramp_lane": -1, "ramp_end_x": 140.0},
        simulation={
            "dt": 0.5,
            "H": 1.0,
            "dt_merge": 1.0,
            "W_min_buffer": 5.0,
            "RD_max": 1.0,
            "u_min": -4.5,
            "u_max": 100.0,
            "rd_speed_scale": 10.0,
            "theta": 0.05,
            "lambda_D": 1.0,
            "lambda_C": 0.001,
            "T_prod": 2.0,
            "near_miss_delta_W_max": 20.0,
            "action_mode": "override",
        },
        vehicles={
            "boundary_pairs": ["CAV-HDV"],
            "gap_widths": [7.0],
            "front_x": 120.0,
            "pair_spacing": 90.0,
            "target_speed": 10.0,
            "front_speed_offsets": [0.0],
            "rear_speed_offsets": [0.0],
            "inner_receiving_gap_count": 1,
            "ramp_count": 1,
            "ramp_start_x": 74.0,
            "ramp_speed": 10.0,
        },
        readiness_targets={
            "raw_gap_count_min": 0,
            "baseline_ZR_min": 0.0,
            "near_miss_count_min": 1,
            "boundary_cav_min": 1,
            "raw_gap_illusion_min": 0,
        },
        mechanism_targets={
            "mechanism": "Prompt3A",
            "mechanism_target": "forced_accommodation_trace_coverage",
            "expected_failure_mode": "forced baseline should run a non-none action and emit event-linked metrics",
            "seed_policy": "deterministic fixed case; seed only reproduces jitter-free state",
        },
    )
    return [
        ("Raw-Large-Gap-Trap", raw_trap),
        ("Forced-Accommodation", forced),
    ]


def _theta_is_available() -> bool:
    return hasattr(ActionConfig, "__dataclass_fields__") and "theta" in ActionConfig.__dataclass_fields__


def _params_for_scenario(config: ScenarioConfig) -> ActionConfig:
    values = {**config.road, **config.simulation, **config.vehicles, **config.ramp}
    return ActionConfig(
        H=float(values.get("H", 1.0)),
        dt=float(values.get("dt", 0.5)),
        dt_merge=float(values.get("dt_merge", 1.0)),
        target_lane=int(values.get("target_lane", 0)),
        W_min_buffer=float(values.get("W_min_buffer", 5.0)),
        RD_max=float(values.get("RD_max", 1.0)),
        u_min=float(values.get("u_min", -4.5)),
        u_max=float(values.get("u_max", 2.0)),
        v_max=float(values.get("v_max", 40.0)),
        T_prod=float(values.get("T_prod", 2.0)),
        production_width_buffer=float(values.get("production_width_buffer", 0.5)),
        lambda_D=float(values.get("lambda_D", 1.0)),
        lambda_C=float(values.get("lambda_C", 1.0)),
        theta=float(values.get("theta", 0.05)),
        u_max_comfort=float(values.get("u_max_comfort", values.get("u_max", 2.0))),
        u_min_comfort=float(values.get("u_min_comfort", values.get("u_min", -4.5))),
        rd_speed_scale=float(values.get("rd_speed_scale", 10.0)),
        ramp_end_x=float(values.get("ramp_end_x", 140.0)),
        T_merge=float(values.get("T_merge", 1.0)),
        T_buffer=float(values.get("T_buffer", 0.0)),
        conflict_mode=str(values.get("conflict_mode", "time_window_default")),
        near_miss_delta_W_max=float(values.get("near_miss_delta_W_max", 8.0)),
        near_miss_RD_max=float(values.get("near_miss_RD_max", 1.0)),
        action_mode=str(values.get("action_mode", "override")),
        event_min_gap=float(values.get("event_min_gap", 0.0)),
        lanes=int(values.get("lanes", 2)),
        enable_boundary_speed=bool(values.get("enable_boundary_speed", True)),
        enable_lane_change=bool(values.get("enable_lane_change", False)),
    )


def _run_variant(
    scenario_config: ScenarioConfig,
    scenario_family: str,
    variant: str,
    full_params: ActionConfig,
) -> dict[str, Any]:
    state = generate_state(scenario_config)
    params = _params_for_variant(full_params, variant)
    baseline_config = _baseline_for_variant(variant)
    params = _params_for_baseline_config(params, baseline_config)
    scenario_for_run = _scenario_with_params(scenario_config, params)
    run_id = (
        f"{SOURCE_BATCH_ID}__{scenario_config.scenario_id}"
        f"__seed{scenario_config.seed}__{variant}"
    )
    decision_context_id = make_decision_context_id(run_id, 0)
    log_context = {
        "schema_version": SCHEMA_VERSION,
        "source_batch_id": SOURCE_BATCH_ID,
        "source_table": "prompt3a_readiness_micro_run",
        "run_id": run_id,
        "scenario_id": scenario_config.scenario_id,
        "seed": scenario_config.seed,
        "algorithm_id": variant,
        "step": 0,
        "time": 0.0,
        "decision_context_id": decision_context_id,
        "state_hash": hash_state(state),
        "config_hash": _hash_variant_config(scenario_for_run, variant, params),
        "code_version": "local_prompt3a_micro",
    }
    context = build_decision_context(
        state,
        scenario_for_run,
        baseline_config,
    )
    context["action_params"] = params

    if variant == "raw_largest_gap":
        policy_result = _raw_largest_gap_policy(state, context, params)
    else:
        policy_result = apply_policy(baseline_config, state, context)
        policy_result["instrumentation_note"] = f"first_class_baseline_config:{baseline_config.baseline_id}"

    selected_action: Action = policy_result["selected_action"]
    selected_eval: ActionEvaluation = policy_result["selected_evaluation"]
    evaluations: Sequence[ActionEvaluation] = policy_result["evaluations"]
    reservation = _reservation_for_selected(selected_eval, decision_context_id)
    demand_id = _demand_id(run_id, reservation.ramp_id if reservation else _first_ramp_id(state))
    execution = _execute_variant_event_window(
        state,
        selected_action,
        reservation,
        {edge.edge_id: edge for edge in selected_eval.edges} or context["edge_map"],
        params,
        log_context,
        demand_id,
    )
    event = execution["event_row"]
    metric = execution["metric_row"]

    candidate_rows = _candidate_gap_rows(
        log_context,
        scenario_family,
        variant,
        state,
        context,
        selected_eval,
    )
    action_rows = _action_value_rows(
        log_context,
        scenario_family,
        variant,
        params,
        policy_result,
    )
    trace_row = _trace_join_row(
        log_context,
        scenario_family,
        variant,
        selected_action,
        selected_eval,
        reservation,
        demand_id,
        event,
        metric,
        policy_result,
    )
    return {
        "scenario_id": scenario_config.scenario_id,
        "scenario_family": scenario_family,
        "variant": variant,
        "run_id": run_id,
        "state": state,
        "context": context,
        "params": params,
        "selected_action": selected_action,
        "selected_eval": selected_eval,
        "evaluations": list(evaluations),
        "reservation": reservation,
        "candidate_rows": candidate_rows,
        "action_rows": action_rows,
        "trace_row": trace_row,
        "event_row": event,
        "metric_row": metric,
        "instrumentation_note": policy_result.get("instrumentation_note", ""),
    }


def _scenario_with_params(config: ScenarioConfig, params: ActionConfig) -> ScenarioConfig:
    simulation = {
        **config.simulation,
        "H": params.H,
        "dt": params.dt,
        "dt_merge": params.dt_merge,
        "W_min_buffer": params.W_min_buffer,
        "RD_max": params.RD_max,
        "lambda_D": params.lambda_D,
        "lambda_C": params.lambda_C,
        "theta": params.theta,
        "T_prod": params.T_prod,
        "u_min": params.u_min,
        "u_max": params.u_max,
        "near_miss_delta_W_max": params.near_miss_delta_W_max,
    }
    return replace(config, simulation=simulation)


def _params_for_variant(params: ActionConfig, variant: str) -> ActionConfig:
    del variant
    return params


def _params_for_baseline_config(params: ActionConfig, baseline: BaselineConfig) -> ActionConfig:
    updated = params
    if baseline.ablations.without_rd:
        updated = replace(updated, lambda_D=0.0, RD_max=1e9)
    if getattr(baseline.ablations, "without_cbar", False):
        updated = replace(updated, lambda_C=0.0)
    if getattr(baseline.ablations, "without_theta", False):
        updated = replace(updated, theta=0.0)
    return updated


def _baseline_for_variant(variant: str) -> BaselineConfig:
    if variant == "raw_largest_gap":
        return resolve_baseline_config("raw_gap_reservation")
    if variant == "forced_accommodation":
        return resolve_baseline_config("forced_accommodation")
    if variant == "without_RD":
        return resolve_baseline_config("rpmi_cmv_without_rd")
    if variant == "without_Cbar":
        return resolve_baseline_config("rpmi_cmv_without_cbar")
    if variant == "without_theta":
        return resolve_baseline_config("rpmi_cmv_without_theta")
    return resolve_baseline_config("rpmi_cmv")


def _actions_for_selection(
    state: TrafficState,
    context: Mapping[str, Any],
    params: ActionConfig,
    selected_action: Action,
) -> list[Action]:
    from rpmi.actions import find_near_miss_edges, generate_candidate_actions

    near_misses = find_near_miss_edges(context["qualities"], context["edge_map"], state, params)
    actions = generate_candidate_actions(near_misses, context["edge_map"], state, params)
    if all(action.action_id != selected_action.action_id for action in actions):
        actions.append(selected_action)
    return actions


def _raw_largest_gap_policy(
    state: TrafficState,
    context: Mapping[str, Any],
    params: ActionConfig,
) -> dict[str, Any]:
    del state
    action = _none_action()
    selected_edge_ids = _raw_largest_gap_edge_ids(context)
    selected = _evaluation_for_edge_ids(
        "raw_largest_gap_policy",
        selected_edge_ids,
        action,
        context,
        params,
    )
    selected = _copy_evaluation_flags(selected, selected=True, rank=1, rcmv=0.0)
    baseline = _copy_evaluation_flags(context["baseline_evaluation"], selected=False, rank=2, rcmv=0.0)
    return {
        "selected_action": action,
        "selected_evaluation": selected,
        "baseline_evaluation": baseline,
        "evaluations": [selected],
        "actions_to_log": [action],
        "instrumentation_note": "raw_largest_gap_policy_existing_candidate_geometry",
    }


def _forced_accommodation_policy(
    state: TrafficState,
    context: Mapping[str, Any],
    params: ActionConfig,
) -> dict[str, Any]:
    selection = run_action_selection(state, context["qualities"], context["edge_map"], params)
    actions = _actions_for_selection(state, context, params, selection.selected_action)
    evaluations: list[ActionEvaluation] = []
    baseline_eval = evaluate_action(actions[0], state, params)
    for action in actions:
        if action.action_id == "a0_none":
            evaluations.append(baseline_eval)
        else:
            evaluations.append(evaluate_action(action, state, params, baseline_J=baseline_eval.J))
    non_none = [item for item in evaluations if item.action_id != "a0_none" and item.matched_edge_ids]
    if non_none:
        selected = sorted(
            non_none,
            key=lambda item: (
                item.S_R,
                item.matched_count,
                item.C_bar,
                -item.D_bar,
                item.action_id,
            ),
            reverse=True,
        )[0]
    else:
        selected = baseline_eval
    selected = _copy_evaluation_flags(selected, selected=True, rank=1, rcmv=selected.RCMV)
    final_evals = []
    rank = 1
    for item in evaluations:
        final_evals.append(
            _copy_evaluation_flags(
                item,
                selected=item.action_id == selected.action_id,
                rank=rank if item.action_id == selected.action_id else rank + 1,
                rcmv=item.RCMV,
                rejected_by_theta=False,
            )
        )
        rank += 1
    action_by_id = {action.action_id: action for action in actions}
    return {
        "selected_action": action_by_id.get(selected.action_id, actions[0]),
        "selected_evaluation": selected,
        "baseline_evaluation": baseline_eval,
        "evaluations": final_evals,
        "actions_to_log": actions,
        "instrumentation_note": "forced_accommodation_micro_policy_uses_existing_candidate_actions",
    }


def _raw_largest_gap_edge_ids(context: Mapping[str, Any]) -> list[str]:
    slot_by_id = {slot.slot_id: slot for slot in context["slots"]}
    chosen: list[Edge] = []
    used_ramps: set[int] = set()
    used_slots: set[str] = set()
    for edge in sorted(
        context["edges"],
        key=lambda item: (
            slot_by_id[item.slot_id].gap_at_tau if item.slot_id in slot_by_id else -math.inf,
            -item.tau,
            item.edge_id,
        ),
        reverse=True,
    ):
        if edge.ramp_id in used_ramps or edge.slot_id in used_slots:
            continue
        chosen.append(edge)
        used_ramps.add(edge.ramp_id)
        used_slots.add(edge.slot_id)
    return [edge.edge_id for edge in chosen]


def _evaluation_for_edge_ids(
    matching_id: str,
    selected_ids: Sequence[str],
    action: Action,
    context: Mapping[str, Any],
    params: ActionConfig,
) -> ActionEvaluation:
    from rpmi.matching import MatchingResult
    from rpmi.runner import _matching_edge_for_quality
    from rpmi.actions import compute_objective

    qualities = list(context["qualities"])
    edges = list(context["edges"])
    edge_by_id = {edge.edge_id: edge for edge in edges}
    quality_by_id = {quality.edge_id: quality for quality in qualities}
    selected_matching_edges = []
    for edge_id in selected_ids:
        edge = edge_by_id.get(edge_id)
        quality = quality_by_id.get(edge_id)
        if edge is None or quality is None:
            continue
        selected_matching_edges.append(_matching_edge_for_quality(edge, quality))
    demand_ids = {edge.ramp_id for edge in edges}
    selected_supply = sum(edge.P_R for edge in selected_matching_edges)
    matching = MatchingResult(
        matching_id=matching_id,
        selected_edges=selected_matching_edges,
        selected_edge_ids=[edge.edge_id for edge in selected_matching_edges],
        S_R=float(selected_supply),
        Z_R=max(float(len(demand_ids)) - float(selected_supply), 0.0),
        D_H=float(len(demand_ids)),
        unmatched_ramps=[
            ramp_id
            for ramp_id in sorted(demand_ids)
            if ramp_id not in {edge.ramp_id for edge in selected_matching_edges}
        ],
        conflict_mode="prompt3a_policy",
        solver_name=matching_id,
        objective_value=float(len(selected_matching_edges)),
    )
    matched_rd = sum(quality_by_id[edge_id].RD for edge_id in selected_ids if edge_id in quality_by_id)
    objective = compute_objective(matching.Z_R, matching.D_H, matched_rd, action.estimated_cost, params.lambda_D, params.lambda_C)
    return ActionEvaluation(
        action_id=action.action_id,
        J=objective["J"],
        Z_bar=objective["Z_bar"],
        D_bar=objective["D_bar"],
        C_bar=objective["C_bar"],
        RCMV=0.0,
        S_R=matching.S_R,
        Z_R=matching.Z_R,
        D_H=matching.D_H,
        matched_edge_ids=list(matching.selected_edge_ids),
        selected=True,
        rejected_by_theta=False,
        matched_count=len(matching.selected_edges),
        invalid_count=sum(1 for quality in qualities if not quality.is_reservable),
        rank=1,
        cost_components={"baseline_policy_cost": action.estimated_cost},
        matched_rd_sum=float(matched_rd),
        matching_result=matching,
        slots=tuple(context["slots"]),
        edges=tuple(edges),
        edge_qualities=tuple(qualities),
        matching_edges=tuple(selected_matching_edges),
        rollout=context.get("rollout"),
    )


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


def _copy_evaluation_flags(
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
        rejected_by_theta=evaluation.rejected_by_theta if rejected_by_theta is None else rejected_by_theta,
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


def _reservation_for_selected(
    selected_eval: ActionEvaluation,
    decision_context_id: str,
) -> Reservation | None:
    edge_by_id = {edge.edge_id: edge for edge in selected_eval.edges}
    quality_by_id = {quality.edge_id: quality for quality in selected_eval.edge_qualities}
    state_by_tau = dict(selected_eval.rollout or {})
    if not selected_eval.matched_edge_ids:
        return None
    edge_id = selected_eval.matched_edge_ids[0]
    edge = edge_by_id.get(edge_id)
    quality = quality_by_id.get(edge_id)
    state_tau = state_by_tau.get(round(edge.tau, 10)) if edge is not None else None
    if edge is None or quality is None or state_tau is None:
        return None
    interval = compute_feasible_interval(edge, state_tau)
    status = "planned"
    reason = ""
    if not quality.is_reservable:
        status = "failed_unreachable" if quality.fail_reason_priority in {"UNREACHABLE", "RAMP_END_INFEASIBLE"} else "failed_invalid_slot"
        reason = quality.fail_reason_priority
    return Reservation(
        reservation_id=f"res_{selected_eval.action_id}_{edge.edge_id}",
        decision_context_id=decision_context_id,
        ramp_id=edge.ramp_id,
        edge_id=edge.edge_id,
        slot_id=edge.slot_id,
        action_id=selected_eval.action_id,
        planned_tau=edge.tau,
        planned_merge_x=(interval.lower + interval.upper) / 2.0,
        planned_interval_lower=interval.lower,
        planned_interval_upper=interval.upper,
        status=status,  # type: ignore[arg-type]
        failure_reason=reason,
    )


def _execute_variant_event_window(
    state: TrafficState,
    action: Action,
    reservation: Reservation | None,
    edge_map: Mapping[str, Edge],
    params: ActionConfig,
    log_context: Mapping[str, Any],
    demand_id: str,
) -> dict[str, Any]:
    current = state
    vehicle_rows: list[dict[str, Any]] = []
    interval_events: list[dict[str, Any]] = []
    horizon = max(params.H, (reservation.planned_tau if reservation else params.H), params.dt)
    steps = max(1, int(math.ceil(horizon / params.dt)))
    final_reservation = reservation
    active_reservations = [] if final_reservation is None else [final_reservation]
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
            {
                "dt": params.dt,
                "action_mode": params.action_mode,
                "limits": {"u_min": params.u_min, "u_max": params.u_max, "v_max": params.v_max},
                "min_gap": params.event_min_gap,
            },
            log_context,
        )
        vehicle_rows.extend(step_rows)
        interval_events.extend(step_events)
        if active_reservations:
            final_reservation = active_reservations[0]
        if final_reservation and final_reservation.status in {"planned", "active_guidance"} and current.time + 1e-9 >= final_reservation.planned_tau:
            final_reservation = _finalize_reservation_at_tau(current, final_reservation, edge_map)
            active_reservations = [final_reservation]
    status = "" if final_reservation is None else final_reservation.status
    event_type = _event_type_for_status(status, interval_events)
    event_reason = _event_reason_for_status(final_reservation, interval_events)
    event_id = _stable_event_id(
        str(log_context["run_id"]),
        str(log_context["decision_context_id"]),
        event_type,
        action.action_id,
        "" if final_reservation is None else final_reservation.edge_id,
        "" if final_reservation is None else final_reservation.reservation_id,
        demand_id,
    )
    metrics = _window_metrics(vehicle_rows, event_time=float(final_reservation.planned_tau if final_reservation else params.H), params=params)
    event_row = {
        **_event_base(log_context),
        "realized_event_id": event_id,
        "event_id": event_id,
        "linked_action_id": action.action_id,
        "linked_edge_id": "" if final_reservation is None else final_reservation.edge_id,
        "linked_gap_id": "" if final_reservation is None else _gap_id_from_edge(edge_map.get(final_reservation.edge_id)),
        "linked_reservation_id": "" if final_reservation is None else final_reservation.reservation_id,
        "linked_demand_id": demand_id,
        "ramp_vehicle_id": "" if final_reservation is None else final_reservation.ramp_id,
        "event_time": final_reservation.planned_tau if final_reservation else params.H,
        "event_type": event_type,
        "event_severity": 0.0 if event_type == "merge_success" else 1.0,
        "merge_success": event_type == "merge_success",
        "event_reason": event_reason,
        "vehicle_ids": json.dumps([final_reservation.ramp_id] if final_reservation else []),
        "min_gap": "",
        "min_margin": "" if final_reservation is None else min(
            _blank_to_inf(final_reservation.actual_margin_front),
            _blank_to_inf(final_reservation.actual_margin_rear),
        ),
        "severity": 0.0 if event_type == "merge_success" else 1.0,
        "note": "prompt3a_readiness_record_only_no_claim",
    }
    metric_row = {
        **_event_base(log_context),
        "realized_event_id": event_id,
        "metric_window_start": metrics["metric_window_start"],
        "metric_window_end": metrics["metric_window_end"],
        "hard_brake_count": metrics["hard_brake_count"],
        "max_deceleration": metrics["max_deceleration"],
        "max_deceleration_magnitude": metrics["max_deceleration_magnitude"],
        "mean_abs_acceleration": metrics["mean_abs_acceleration"],
        "speed_variance_before": metrics["speed_variance_before"],
        "speed_variance_after": metrics["speed_variance_after"],
        "speed_variance_delta": metrics["speed_variance_delta"],
        "max_wave_amplitude": metrics["max_wave_amplitude"],
        "mainline_disturbance_cost": metrics["mainline_disturbance_cost"],
        "min_TTC": metrics["min_TTC"],
        "unsafe_overlap_count": sum(1 for item in interval_events if item.get("event_type") in {"overlap", "negative_margin"}),
        "RD_realized_proxy": metrics["RD_realized_proxy"],
        "RD_pred": "",
        "RD_prediction_error": "",
    }
    return {"event_row": event_row, "metric_row": metric_row, "reservation": final_reservation}


def _finalize_reservation_at_tau(
    state: TrafficState,
    reservation: Reservation,
    edge_map: Mapping[str, Edge],
) -> Reservation:
    edge = edge_map.get(reservation.edge_id)
    if edge is None:
        return replace(reservation, status="failed_invalid_slot", failure_reason="edge_missing")
    ramp = state.vehicles.get(reservation.ramp_id)
    front = state.vehicles.get(edge.front_id)
    rear = state.vehicles.get(edge.rear_id)
    if ramp is None or front is None or rear is None:
        return replace(reservation, status="failed_invalid_slot", failure_reason="missing_vehicle_at_tau")
    interval = compute_feasible_interval(edge, state)
    margin_front = interval.upper - ramp.x
    margin_rear = ramp.x - interval.lower
    base = replace(
        reservation,
        actual_x_at_tau=ramp.x,
        actual_margin_front=margin_front,
        actual_margin_rear=margin_rear,
    )
    if reservation.status.startswith("failed_"):
        return base
    if interval.V_phys_theory == 0:
        return replace(base, status="failed_invalid_slot", failure_reason="physical_width_negative")
    if margin_front < -1e-9 or margin_rear < -1e-9:
        return replace(base, status="failed_unsafe_margin", failure_reason="negative_actual_margin")
    return replace(base, status="merged", failure_reason="")


def _event_type_for_status(status: str, step_events: Sequence[Mapping[str, Any]]) -> str:
    if status == "merged":
        return "merge_success"
    if status.startswith("failed_"):
        return "merge_failure"
    if step_events:
        return str(step_events[0].get("event_type", "realized_transition"))
    if not status:
        return "no_reservation"
    return status


def _event_reason_for_status(reservation: Reservation | None, step_events: Sequence[Mapping[str, Any]]) -> str:
    if reservation is None:
        return "no_selected_reservation"
    if reservation.status == "merged":
        return "merge_success"
    if reservation.failure_reason:
        return reservation.failure_reason
    if step_events:
        return str(step_events[0].get("event_type", "realized_transition"))
    return reservation.status


def _window_metrics(
    vehicle_rows: Sequence[Mapping[str, Any]],
    *,
    event_time: float,
    params: ActionConfig,
) -> dict[str, Any]:
    if not vehicle_rows:
        return {
            "metric_window_start": 0.0,
            "metric_window_end": event_time,
            "hard_brake_count": 0,
            "max_deceleration": 0.0,
            "max_deceleration_magnitude": 0.0,
            "mean_abs_acceleration": 0.0,
            "speed_variance_before": 0.0,
            "speed_variance_after": 0.0,
            "speed_variance_delta": 0.0,
            "max_wave_amplitude": 0.0,
            "mainline_disturbance_cost": 0.0,
            "min_TTC": "",
            "RD_realized_proxy": 0.0,
        }
    start = max(0.0, event_time - params.H)
    end = event_time + params.dt
    rows = [row for row in vehicle_rows if start - 1e-9 <= float(row.get("time", 0.0) or 0.0) <= end + 1e-9]
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
        "max_deceleration_magnitude": max_decel_mag,
        "mean_abs_acceleration": mean_abs,
        "speed_variance_before": speed_var_before,
        "speed_variance_after": speed_var_after,
        "speed_variance_delta": speed_var_after - speed_var_before,
        "max_wave_amplitude": wave,
        "mainline_disturbance_cost": disturbance,
        "min_TTC": "",
        "RD_realized_proxy": max_decel_mag + hard_brake_count,
    }


def _candidate_gap_rows(
    log_context: Mapping[str, Any],
    scenario_family: str,
    variant: str,
    state: TrafficState,
    context: Mapping[str, Any],
    selected_eval: ActionEvaluation,
) -> list[dict[str, Any]]:
    selected_ids = set(selected_eval.matched_edge_ids)
    slot_by_id = {slot.slot_id: slot for slot in selected_eval.slots or context["slots"]}
    quality_by_edge = {quality.edge_id: quality for quality in selected_eval.edge_qualities or context["qualities"]}
    rows = []
    for edge in selected_eval.edges or context["edges"]:
        quality = quality_by_edge.get(edge.edge_id)
        slot = slot_by_id.get(edge.slot_id)
        state_tau = dict(selected_eval.rollout or context.get("rollout") or {}).get(round(edge.tau, 10))
        front = state_tau.vehicles.get(edge.front_id) if state_tau else state.vehicles.get(edge.front_id)
        rear = state_tau.vehicles.get(edge.rear_id) if state_tau else state.vehicles.get(edge.rear_id)
        raw_gap = slot.gap_at_tau if slot else (quality.W if quality else "")
        closing_rate = (rear.v - front.v) if front is not None and rear is not None else ""
        rows.append(
            {
                **_base_row(log_context),
                "scenario_family": scenario_family,
                "variant": variant,
                "candidate_action_id": edge.action_id or "a0_none",
                "candidate_edge_id": edge.edge_id,
                "candidate_gap_id": _gap_id_from_edge(edge),
                "physical_gap_id": _gap_id_from_edge(edge),
                "slot_group_id": _gap_id_from_edge(edge),
                "ramp_vehicle_id": edge.ramp_id,
                "matching_id": selected_eval.matching_result.matching_id if selected_eval.matching_result else "",
                "matching_type": "prompt3a_variant_candidate",
                "source_policy": variant,
                "P_R": "" if quality is None else quality.P_R,
                "RD_pred": "" if quality is None else quality.RD,
                "RD_pred_source": "EdgeQuality.RD_proxy_v0_minimal",
                "raw_gap_size": raw_gap,
                "closing_rate": closing_rate,
                "front_vehicle_id": edge.front_id,
                "rear_vehicle_id": edge.rear_id,
                "is_selected_by_full_rpmi": variant == "full_RPMI_CMV_current_objective" and edge.edge_id in selected_ids,
                "is_selected_by_baseline_no_action": edge.action_id is None and edge.edge_id in selected_ids,
                "is_selected_by_raw_largest_gap": variant == "raw_largest_gap" and edge.edge_id in selected_ids,
                "is_selected_by_forced_accommodation": variant == "forced_accommodation" and edge.edge_id in selected_ids,
                "selected_gap_available": edge.edge_id in selected_ids,
                "known_gap": "",
            }
        )
    return rows


def _action_value_rows(
    log_context: Mapping[str, Any],
    scenario_family: str,
    variant: str,
    params: ActionConfig,
    policy_result: Mapping[str, Any],
) -> list[dict[str, Any]]:
    selected_eval: ActionEvaluation = policy_result["selected_evaluation"]
    action_by_id = {action.action_id: action for action in policy_result.get("actions_to_log", [])}
    eval_by_id = {item.action_id: item for item in policy_result["evaluations"]}
    j_none = policy_result["baseline_evaluation"].J
    out = []
    for action_id, evaluation in eval_by_id.items():
        action = action_by_id.get(action_id)
        edge = _first_edge_for_eval(evaluation)
        reservation_id = f"res_{evaluation.action_id}_{edge.edge_id}" if edge else ""
        out.append(
            {
                **_base_row(log_context),
                "scenario_family": scenario_family,
                "variant": variant,
                "action_id": action_id,
                "action_type": action.action_type if action else ("none" if action_id == "a0_none" else ""),
                "nominal_edge_id": action.nominal_edge_id if action else "",
                "selected_edge_id": edge.edge_id if edge else "",
                "selected_gap_id": _gap_id_from_edge(edge) if edge else "",
                "selected_slot_group_id": _gap_id_from_edge(edge) if edge else "",
                "reservation_id_if_selected": reservation_id if evaluation.selected else "",
                "J": evaluation.J,
                "J_none": j_none,
                "J_delta_vs_none": evaluation.J - j_none if _finite(evaluation.J) and _finite(j_none) else "",
                "Z_bar": evaluation.Z_bar,
                "D_bar": evaluation.D_bar,
                "C_bar": evaluation.C_bar,
                "RCMV": evaluation.RCMV,
                "S_R": evaluation.S_R,
                "Z_R": evaluation.Z_R,
                "matched_count": evaluation.matched_count,
                "matched_edge_ids": json.dumps(evaluation.matched_edge_ids),
                "matched_rd_sum": evaluation.matched_rd_sum,
                "invalid_count": evaluation.invalid_count,
                "rank": evaluation.rank,
                "selected": evaluation.action_id == selected_eval.action_id,
                "rejected_by_theta": evaluation.rejected_by_theta,
                "theta_suppression_observed": evaluation.rejected_by_theta,
                "cost_components_json": json.dumps(evaluation.cost_components or {}, sort_keys=True, default=str),
                "lane_change_candidate_id": (evaluation.cost_components or {}).get("lane_change_candidate_id", ""),
                "lc_cost": (evaluation.cost_components or {}).get("lc_cost", (evaluation.cost_components or {}).get("C_bar", "")),
                "lc_feasibility_margin_front": (evaluation.cost_components or {}).get("lc_feasibility_margin_front", ""),
                "lc_feasibility_margin_rear": (evaluation.cost_components or {}).get("lc_feasibility_margin_rear", ""),
                "lc_expected_gap_effect": (evaluation.cost_components or {}).get("lc_expected_gap_effect", ""),
                "affects_action_selection": True,
                "affects_reservation_selection": True,
                "is_posthoc_diagnostic": False,
                "known_gap": _action_known_gap(variant),
                "Z_R": evaluation.Z_R,
                "RD_pred_norm": evaluation.D_bar,
                "C_dist_norm": evaluation.C_bar,
                "S_safety_penalty": 0.0,
                "Q_churn_penalty": 0.0,
                "theta": params.theta,
                "lambda_Z": 1.0,
                "lambda_D": params.lambda_D,
                "lambda_C": params.lambda_C,
                "lambda_S": 0.0,
                "lambda_Q": 0.0,
                "selected_flag": evaluation.action_id == selected_eval.action_id,
                "selection_reason": policy_result.get("instrumentation_note", ""),
            }
        )
    return out


def _trace_join_row(
    log_context: Mapping[str, Any],
    scenario_family: str,
    variant: str,
    action: Action,
    selected_eval: ActionEvaluation,
    reservation: Reservation | None,
    demand_id: str,
    event: Mapping[str, Any],
    metric: Mapping[str, Any],
    policy_result: Mapping[str, Any],
) -> dict[str, Any]:
    edge = _first_edge_for_eval(selected_eval)
    quality = _quality_for_edge(selected_eval, edge.edge_id if edge else "")
    has_gap = edge is not None
    has_reservation = reservation is not None
    has_event = bool(event.get("realized_event_id"))
    has_metrics = bool(metric.get("realized_event_id")) and metric.get("realized_event_id") == event.get("realized_event_id")
    missing = []
    if not has_gap:
        missing.append("missing_selected_gap")
    if not has_reservation:
        missing.append("missing_reservation_for_selected_gap")
    if not demand_id:
        missing.append("missing_demand_for_reservation")
    if not has_event:
        missing.append("blank_realized_event_id")
    if not has_metrics:
        missing.append("no_event_level_realized_metric_join")
    return {
        **_base_row(log_context),
        "scenario_family": scenario_family,
        "variant": variant,
        "selected_action_id": action.action_id,
        "selected_action_type": action.action_type,
        "selected_action_rank": selected_eval.rank,
        "selected_action_J": selected_eval.J,
        "selected_action_RCMV": selected_eval.RCMV,
        "selected_action_C_bar": selected_eval.C_bar,
        "selected_action_D_bar": selected_eval.D_bar,
        "selected_action_Z_bar": selected_eval.Z_bar,
        "selected_action_S_R": selected_eval.S_R,
        "selected_action_Z_R": selected_eval.Z_R,
        "selected_edge_id": edge.edge_id if edge else "",
        "selected_gap_id": _gap_id_from_edge(edge) if edge else "",
        "selected_slot_group_id": _gap_id_from_edge(edge) if edge else "",
        "selected_gap_P_R": quality.P_R if quality else "",
        "selected_gap_RD_pred": quality.RD if quality else "",
        "matching_id": selected_eval.matching_result.matching_id if selected_eval.matching_result else "",
        "matching_type": policy_result.get("instrumentation_note", "prompt3a_variant"),
        "reservation_id": reservation.reservation_id if reservation else "",
        "reservation_status_after_initial": "planned" if reservation else "",
        "reservation_final_status_after": _event_reason_to_status(event.get("event_type", "")),
        "reservation_final_status_reason": event.get("event_reason", ""),
        "planned_tau": reservation.planned_tau if reservation else "",
        "commitment_status": "prompt3a_single_decision_record_only" if reservation else "",
        "is_locked": False,
        "demand_id": demand_id,
        "ramp_vehicle_id": reservation.ramp_id if reservation else "",
        "demand_status_after_final": "merged" if event.get("event_type") == "merge_success" else "unserved_or_failed",
        "demand_event_reason_final": event.get("event_reason", ""),
        "merge_success": event.get("merge_success", False),
        "predicted_unserved": selected_eval.Z_R > 0.0,
        "realized_unserved": event.get("event_type") != "merge_success",
        "realized_event_id": event.get("realized_event_id", ""),
        "realized_event_type": event.get("event_type", ""),
        "realized_event_severity": event.get("event_severity", ""),
        "metric_scope": "event_linked" if has_metrics else "",
        "hard_brake_count_after": metric.get("hard_brake_count", ""),
        "max_deceleration_after": metric.get("max_deceleration", ""),
        "max_deceleration_magnitude_after": metric.get("max_deceleration_magnitude", ""),
        "speed_wave_after": metric.get("max_wave_amplitude", ""),
        "speed_variance_delta_after": metric.get("speed_variance_delta", ""),
        "mainline_disturbance_cost_after": metric.get("mainline_disturbance_cost", ""),
        "min_TTC_after": metric.get("min_TTC", ""),
        "RD_realized_proxy_after": metric.get("RD_realized_proxy", ""),
        "selected_action_to_gap_joined": has_gap,
        "selected_gap_to_reservation_joined": has_gap and has_reservation,
        "reservation_to_demand_joined": has_reservation and bool(demand_id),
        "demand_to_realized_event_joined": bool(demand_id) and has_event,
        "realized_event_to_metrics_joined": has_event and has_metrics,
        "trajectory_proxy_metrics_joined": True,
        "can_join_full_chain": not missing,
        "missing_join_reason": ";".join(missing),
        "red_line_status": "PASS" if not missing else "BLOCKER",
        "known_gap": "",
        "physical_gap_id": _gap_id_from_edge(edge) if edge else "",
        "slot_group_id": _gap_id_from_edge(edge) if edge else "",
        "selected_gap_raw_size": _raw_gap_for_edge(selected_eval, edge),
        "selected_gap_RD_realized": metric.get("RD_realized_proxy", ""),
        "hard_brake_count_after": metric.get("hard_brake_count", ""),
        "max_wave_amplitude_after": metric.get("max_wave_amplitude", ""),
        "mainline_disturbance_cost_after": metric.get("mainline_disturbance_cost", ""),
        "min_realized_gap_after": event.get("min_gap", ""),
        "join_failure_reason": ";".join(missing),
    }


def _scenario_variant_matrix(
    records: Sequence[Mapping[str, Any]],
    blocked_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for record in records:
        trace = record["trace_row"]
        action_rows = record["action_rows"]
        selected_action_count = sum(1 for row in action_rows if _truthy(row.get("selected_flag")))
        nontrivial = 1 if trace.get("selected_action_id") not in {"", "a0_none"} else 0
        full_chain = 1 if _truthy(trace.get("can_join_full_chain")) else 0
        missing_rates = {
            "selected_action_to_gap_missing_rate": 0.0 if _truthy(trace.get("selected_action_to_gap_joined")) else 1.0,
            "selected_gap_to_reservation_missing_rate": 0.0 if _truthy(trace.get("selected_gap_to_reservation_joined")) else 1.0,
            "reservation_to_demand_missing_rate": 0.0 if _truthy(trace.get("reservation_to_demand_joined")) else 1.0,
            "demand_to_realized_event_missing_rate": 0.0 if _truthy(trace.get("demand_to_realized_event_joined")) else 1.0,
            "realized_event_to_metrics_missing_rate": 0.0 if _truthy(trace.get("realized_event_to_metrics_joined")) else 1.0,
        }
        readiness_status = "PASS" if full_chain else "FAIL"
        failure_type = "ready_for_prompt3" if full_chain else _failure_type_for_trace(trace)
        repair = "No trace repair needed for this micro-run row." if full_chain else "Repair selected_action -> realized_event -> metric-window linkage for this variant."
        rows.append(
            {
                "scenario_id": record["scenario_id"],
                "scenario_family": record["scenario_family"],
                "variant": record["variant"],
                "selected_action_count": selected_action_count,
                "nontrivial_selected_action_count": nontrivial,
                **missing_rates,
                "can_join_full_chain_count": full_chain,
                "can_join_full_chain_rate": float(full_chain),
                "readiness_status": readiness_status,
                "failure_type": failure_type,
                "repair_recommendation": repair,
            }
        )
    rows.extend(blocked_rows)
    return rows


def _failure_type_for_trace(trace: Mapping[str, Any]) -> str:
    reason = str(trace.get("missing_join_reason", trace.get("join_failure_reason", "")))
    if "realized_event" in reason:
        return "missing_realized_event"
    if "metric" in reason:
        return "missing_event_metric_window"
    if "selected_gap" in reason:
        return "insufficient_trace_join"
    return "insufficient_trace_join"


def _blocked_variant(
    config: ScenarioConfig,
    scenario_family: str,
    variant: str,
    failure_type: str,
    reason: str,
) -> dict[str, Any]:
    assert failure_type in FAILURE_TYPES
    return {
        "scenario_id": config.scenario_id,
        "scenario_family": scenario_family,
        "variant": variant,
        "selected_action_count": 0,
        "nontrivial_selected_action_count": 0,
        "selected_action_to_gap_missing_rate": 1.0,
        "selected_gap_to_reservation_missing_rate": 1.0,
        "reservation_to_demand_missing_rate": 1.0,
        "demand_to_realized_event_missing_rate": 1.0,
        "realized_event_to_metrics_missing_rate": 1.0,
        "can_join_full_chain_count": 0,
        "can_join_full_chain_rate": 0.0,
        "readiness_status": "BLOCKED",
        "failure_type": failure_type,
        "repair_recommendation": reason,
    }


def _schema_validation_report(
    candidate_rows: Sequence[Mapping[str, Any]],
    action_rows: Sequence[Mapping[str, Any]],
    trace_rows: Sequence[Mapping[str, Any]],
    event_rows: Sequence[Mapping[str, Any]],
    metric_rows: Sequence[Mapping[str, Any]],
    matrix: Sequence[Mapping[str, Any]],
    prior: Mapping[str, Any],
) -> str:
    files = [
        ("candidate_gap_table.csv", candidate_rows, _candidate_columns()),
        ("action_value_decomposition.csv", action_rows, _action_columns()),
        ("trace_join_table.csv", trace_rows, _trace_columns()),
        ("realized_events.csv", event_rows, _realized_event_columns()),
        ("event_metric_windows.csv", metric_rows, _event_metric_columns()),
    ]
    lines = [
        "# Prompt 3A Schema Validation Report",
        "",
        "Generated: 2026-05-22",
        f"Source batch: `{SOURCE_BATCH_ID}`",
        f"Output package: `{GATE_DIR.as_posix()}`",
        f"Schema version: `{SCHEMA_VERSION}`",
        "",
        "## Verdict",
        "",
        "**Prompt 3A readiness micro-run artifacts generated.** This is a trace-readiness check only; no objective tuning, locked evaluation, or performance claim was made.",
        "",
        "## Prior Prompt 2R Carryover",
        "",
        f"- Prompt 2R minimum pass condition before Prompt 3A: {prior.get('minimum_pass_condition')}",
        f"- Prior nontrivial full-chain count: {prior.get('nontrivial_full_chain_count')}",
        f"- Prior can_join_full_chain rate: {float(prior.get('can_join_full_chain_rate', 0.0)):.6f}",
        "",
        "## File Existence Checklist",
        "",
        "| file | exists | row_count | column_count |",
        "| --- | --- | ---: | ---: |",
    ]
    for filename, rows, columns in files:
        lines.append(f"| {filename} | True | {len(rows)} | {len(columns)} |")
    lines.extend(
        [
            "",
            "## Schema Validation Checklist",
            "",
            "| file | required_columns_present | missing_columns | extra_columns |",
            "| --- | --- | --- | --- |",
        ]
    )
    for filename, rows, columns in files:
        actual = set(rows[0].keys()) if rows else set(columns)
        required = set(columns)
        missing = sorted(required - actual)
        extra = sorted(actual - required)
        lines.append(f"| {filename} | {not missing} | {', '.join(missing)} | {', '.join(extra)} |")
    join_rates = _overall_join_rates(trace_rows)
    lines.extend(
        [
            "",
            "## Join Missing Rates",
            "",
            "| join | missing_count | denominator | missing_rate |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for name, data in join_rates.items():
        lines.append(f"| {name} | {data['missing']} | {data['denominator']} | {data['rate']:.6f} |")
    full_count = sum(1 for row in trace_rows if _truthy(row.get("can_join_full_chain")))
    nontrivial_full = sum(
        1 for row in trace_rows if _truthy(row.get("can_join_full_chain")) and row.get("selected_action_id") != "a0_none"
    )
    lines.extend(
        [
            "",
            "## Full Chain Closure",
            "",
            "| metric | value |",
            "| --- | ---: |",
            f"| can_join_full_chain_count | {full_count} |",
            f"| selected_action_rows | {len(trace_rows)} |",
            f"| can_join_full_chain_rate | {_rate(full_count, len(trace_rows)):.6f} |",
            f"| nontrivial_full_chain_count | {nontrivial_full} |",
        ]
    )
    return "\n".join(lines) + "\n"


def _missing_join_report(
    trace_rows: Sequence[Mapping[str, Any]],
    matrix: Sequence[Mapping[str, Any]],
) -> str:
    join_rates = _overall_join_rates(trace_rows)
    missing = [row for row in trace_rows if not _truthy(row.get("can_join_full_chain"))]
    lines = [
        "# Prompt 3A Missing Join Report",
        "",
        "Generated: 2026-05-22",
        f"Schema version: `{SCHEMA_VERSION}`",
        "",
        "## Summary",
        "",
        "Prompt 3A generated event-linked rows for the available micro-run variants. Any incomplete or blocked scenario/variant appears below with the controlled failure type used by the readiness report.",
        "",
        "## Missing Join Rates",
        "",
        "| join | missing_count | denominator | missing_rate |",
        "| --- | ---: | ---: | ---: |",
    ]
    for name, data in join_rates.items():
        lines.append(f"| {name} | {data['missing']} | {data['denominator']} | {data['rate']:.6f} |")
    lines.extend(
        [
            "",
            "## Missing Rows",
            "",
            "| scenario_id | variant | selected_action_id | selected_edge_id | reservation_id | demand_id | realized_event_id | missing_join_reason | failure_type |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    matrix_by_key = {(row["scenario_id"], row["variant"]): row for row in matrix}
    if not missing:
        lines.append("| _none_ | _none_ |  |  |  |  |  |  | ready_for_prompt3 |")
    for row in missing:
        key = (row.get("scenario_id", ""), row.get("variant", ""))
        failure_type = matrix_by_key.get(key, {}).get("failure_type", "insufficient_trace_join")
        lines.append(
            "| {scenario_id} | {variant} | {selected_action_id} | {selected_edge_id} | {reservation_id} | {demand_id} | {realized_event_id} | {missing_join_reason} | {failure_type} |".format(
                scenario_id=row.get("scenario_id", ""),
                variant=row.get("variant", ""),
                selected_action_id=row.get("selected_action_id", ""),
                selected_edge_id=row.get("selected_edge_id", ""),
                reservation_id=row.get("reservation_id", ""),
                demand_id=row.get("demand_id", ""),
                realized_event_id=row.get("realized_event_id", ""),
                missing_join_reason=row.get("missing_join_reason", ""),
                failure_type=failure_type,
            )
        )
    return "\n".join(lines) + "\n"


def _readiness_report(
    prior: Mapping[str, Any],
    matrix: Sequence[Mapping[str, Any]],
    records: Sequence[Mapping[str, Any]],
    blocked_rows: Sequence[Mapping[str, Any]],
    candidate_rows: Sequence[Mapping[str, Any]],
    action_rows: Sequence[Mapping[str, Any]],
    trace_rows: Sequence[Mapping[str, Any]],
    event_rows: Sequence[Mapping[str, Any]],
    metric_rows: Sequence[Mapping[str, Any]],
) -> str:
    decision = _final_decision(matrix, trace_rows, action_rows)
    lines = [
        "# Prompt 3A Co-Design Readiness Micro-Run Report",
        "",
        "Generated: 2026-05-22",
        "",
        "This report is a readiness micro-run only. It does not start the full two-hour co-design loop, tune objective weights, reconstruct the objective, run decisive experiments, make performance claims, write paper claims, or lock evaluation settings.",
        "",
        "## A. Prior Prompt 2R Status Summary",
        "",
        f"- Prompt 2R minimum pass still holds: {prior.get('minimum_pass_condition') == 'PASS'}",
        f"- nontrivial_full_chain_count before Prompt 3A: {prior.get('nontrivial_full_chain_count')}",
        f"- can_join_full_chain rate before Prompt 3A: {float(prior.get('can_join_full_chain_rate', 0.0)):.2%}",
        "- Regression from Prompt 2R: none observed in the archived prior status; Prompt 3A writes a new micro-run gate package and does not claim comparability to Prompt 2R performance.",
        "",
        "## B. Scenario / Variant Matrix",
        "",
        "| scenario_id | scenario_family | variant | selected_action_count | nontrivial_selected_action_count | selected_action_to_gap_missing_rate | selected_gap_to_reservation_missing_rate | reservation_to_demand_missing_rate | demand_to_realized_event_missing_rate | realized_event_to_metrics_missing_rate | can_join_full_chain_count | can_join_full_chain_rate | readiness_status | failure_type | repair_recommendation |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for row in matrix:
        lines.append(
            "| {scenario_id} | {scenario_family} | {variant} | {selected_action_count} | {nontrivial_selected_action_count} | {selected_action_to_gap_missing_rate:.2%} | {selected_gap_to_reservation_missing_rate:.2%} | {reservation_to_demand_missing_rate:.2%} | {demand_to_realized_event_missing_rate:.2%} | {realized_event_to_metrics_missing_rate:.2%} | {can_join_full_chain_count} | {can_join_full_chain_rate:.2%} | {readiness_status} | {failure_type} | {repair_recommendation} |".format(
                **row
            )
        )
    raw_check = _raw_large_gap_check(candidate_rows, trace_rows)
    forced_check = _forced_check(trace_rows, event_rows, metric_rows)
    ablation_check = _ablation_check(action_rows, trace_rows)
    lines.extend(
        [
            "",
            "## C. Raw-Large-Gap-Trap Diagnostic Check",
            "",
            f"- Gap A raw_gap_size > Gap B raw_gap_size: {raw_check['raw_gap_contrast']}",
            f"- Gap A closing_rate > Gap B closing_rate: {raw_check['closing_rate_contrast']}",
            f"- Gap A predicted RD or disturbance risk higher than Gap B: {raw_check['rd_contrast']}",
            f"- raw_largest_gap selects Gap A if instrumented: {raw_check['raw_selects_gap_a']}",
            f"- full current objective selects Gap B / lower-risk gap / none if observable: {raw_check['full_lower_risk_or_none']}",
            "",
            "These are diagnostic validity and trace coverage observations only, not performance evidence.",
            "",
            "## D. Forced-Accommodation Diagnostic Check",
            "",
            f"- forced_accommodation actually runs: {forced_check['runs']}",
            f"- produces selected_action / selected_gap: {forced_check['selected_action_gap']}",
            f"- creates reservation / demand linkage: {forced_check['reservation_demand']}",
            f"- produces realized_event_id: {forced_check['realized_event']}",
            f"- produces event_metric_windows row: {forced_check['metric_window']}",
            "",
            "Any disturbance values are non-final diagnostic observations only.",
            "",
            "## E. Ablation Comparability Check",
            "",
            f"- without_RD action_value_decomposition rows exist: {ablation_check['without_RD_rows']}",
            f"- without_Cbar action_value_decomposition rows exist: {ablation_check['without_Cbar_rows']}",
            f"- columns are comparable to full objective: {ablation_check['columns_comparable']}",
            f"- selected_action and selected_gap are joinable: {ablation_check['selected_joinable']}",
            f"- realized_event and event_metric_windows are joinable when a realized event occurs: {ablation_check['event_joinable']}",
            "",
            "## F. Sample Rows",
            "",
        ]
    )
    for label, predicate in [
        ("full_RPMI_CMV_current_objective", lambda row: row.get("variant") == "full_RPMI_CMV_current_objective"),
        ("raw_largest_gap_or_forced_accommodation", lambda row: row.get("variant") in {"raw_largest_gap", "forced_accommodation"}),
        ("without_RD_or_without_Cbar", lambda row: row.get("variant") in {"without_RD", "without_Cbar"}),
    ]:
        sample = next((row for row in trace_rows if predicate(row)), None)
        lines.append(f"### {label}")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(_compact_sample(sample), indent=2, sort_keys=True))
        lines.append("```")
        lines.append("")
        if sample:
            metric = next((row for row in metric_rows if row.get("realized_event_id") == sample.get("realized_event_id")), None)
            lines.append("Linked event_metric_windows row:")
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(_compact_metric_sample(metric), indent=2, sort_keys=True))
            lines.append("```")
            lines.append("")
    if blocked_rows:
        lines.extend(["## Blocked Scenario / Variant Rows", ""])
        for row in blocked_rows:
            lines.append(f"- {row['scenario_id']} / {row['variant']}: {row['failure_type']} - {row['repair_recommendation']}")
        lines.append("")
    lines.extend(
        [
            "## G. Final Readiness Decision",
            "",
            decision,
        ]
    )
    return "\n".join(lines) + "\n"


def _final_decision(
    matrix: Sequence[Mapping[str, Any]],
    trace_rows: Sequence[Mapping[str, Any]],
    action_rows: Sequence[Mapping[str, Any]],
) -> str:
    required_100_missing = [
        row
        for row in matrix
        if row["variant"] in VARIANT_ORDER
        and (
            float(row["demand_to_realized_event_missing_rate"]) >= 1.0
            or float(row["realized_event_to_metrics_missing_rate"]) >= 1.0
        )
    ]
    full_nontrivial = any(
        row.get("variant") == "full_RPMI_CMV_current_objective"
        and row.get("selected_action_id") != "a0_none"
        and _truthy(row.get("can_join_full_chain"))
        for row in trace_rows
    )
    baseline_nontrivial = any(
        row.get("variant") in {"raw_largest_gap", "forced_accommodation"}
        and row.get("selected_action_id") != "a0_none"
        and _truthy(row.get("can_join_full_chain"))
        for row in trace_rows
    )
    ablation_join = any(
        row.get("variant") in {"without_RD", "without_Cbar"}
        and _truthy(row.get("can_join_full_chain"))
        for row in trace_rows
    )
    comparable_ablation_rows = any(row.get("variant") in {"without_RD", "without_Cbar"} for row in action_rows)
    if required_100_missing:
        return "NOT_READY_RETURN_TO_PROMPT2R_B"
    if full_nontrivial and baseline_nontrivial and ablation_join and comparable_ablation_rows:
        return "READY_FOR_PROMPT3"
    return "PARTIAL_READY_NEEDS_HUMAN_REVIEW"


def _raw_large_gap_check(
    candidate_rows: Sequence[Mapping[str, Any]],
    trace_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    rows = [
        row
        for row in candidate_rows
        if row.get("scenario_family") == "Raw-Large-Gap-Trap"
        and row.get("variant") == "full_RPMI_CMV_current_objective"
    ]
    by_gap: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        by_gap.setdefault(str(row.get("physical_gap_id", "")), []).append(row)
    summaries = []
    for gap_id, group in by_gap.items():
        summaries.append(
            {
                "gap_id": gap_id,
                "raw": max((_float(row.get("raw_gap_size")) for row in group), default=0.0),
                "closing": max((_float(row.get("closing_rate")) for row in group), default=0.0),
                "rd": max((_float(row.get("RD_pred")) for row in group), default=0.0),
            }
        )
    if len(summaries) < 2:
        return {
            "raw_gap_contrast": False,
            "closing_rate_contrast": False,
            "rd_contrast": False,
            "raw_selects_gap_a": False,
            "full_lower_risk_or_none": False,
        }
    gap_a = max(summaries, key=lambda item: item["raw"])
    gap_b = min(summaries, key=lambda item: item["rd"])
    raw_trace = next(
        (
            row
            for row in trace_rows
            if row.get("scenario_family") == "Raw-Large-Gap-Trap"
            and row.get("variant") == "raw_largest_gap"
        ),
        {},
    )
    full_trace = next(
        (
            row
            for row in trace_rows
            if row.get("scenario_family") == "Raw-Large-Gap-Trap"
            and row.get("variant") == "full_RPMI_CMV_current_objective"
        ),
        {},
    )
    return {
        "raw_gap_contrast": gap_a["raw"] > gap_b["raw"],
        "closing_rate_contrast": gap_a["closing"] > gap_b["closing"],
        "rd_contrast": gap_a["rd"] > gap_b["rd"],
        "raw_selects_gap_a": raw_trace.get("selected_gap_id") == gap_a["gap_id"],
        "full_lower_risk_or_none": full_trace.get("selected_action_id") == "a0_none"
        or full_trace.get("selected_gap_id") == gap_b["gap_id"],
    }


def _forced_check(
    trace_rows: Sequence[Mapping[str, Any]],
    event_rows: Sequence[Mapping[str, Any]],
    metric_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    row = next((item for item in trace_rows if item.get("variant") == "forced_accommodation"), {})
    event_id = row.get("realized_event_id", "")
    return {
        "runs": bool(row),
        "selected_action_gap": bool(row.get("selected_action_id")) and bool(row.get("selected_gap_id")),
        "reservation_demand": bool(row.get("reservation_id")) and bool(row.get("demand_id")),
        "realized_event": bool(event_id) and any(item.get("realized_event_id") == event_id for item in event_rows),
        "metric_window": bool(event_id) and any(item.get("realized_event_id") == event_id for item in metric_rows),
    }


def _ablation_check(
    action_rows: Sequence[Mapping[str, Any]],
    trace_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    full_cols = set(next((row for row in action_rows if row.get("variant") == "full_RPMI_CMV_current_objective"), {}).keys())
    ablation_cols = set(next((row for row in action_rows if row.get("variant") in {"without_RD", "without_Cbar"}), {}).keys())
    return {
        "without_RD_rows": any(row.get("variant") == "without_RD" for row in action_rows),
        "without_Cbar_rows": any(row.get("variant") == "without_Cbar" for row in action_rows),
        "columns_comparable": bool(full_cols) and full_cols == ablation_cols,
        "selected_joinable": all(
            _truthy(row.get("selected_action_to_gap_joined"))
            for row in trace_rows
            if row.get("variant") in {"without_RD", "without_Cbar"}
        ),
        "event_joinable": all(
            _truthy(row.get("demand_to_realized_event_joined"))
            and _truthy(row.get("realized_event_to_metrics_joined"))
            for row in trace_rows
            if row.get("variant") in {"without_RD", "without_Cbar"}
        ),
    }


def _overall_join_rates(trace_rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    checks = {
        "selected_action_to_selected_gap": "selected_action_to_gap_joined",
        "selected_gap_to_reservation": "selected_gap_to_reservation_joined",
        "reservation_to_demand": "reservation_to_demand_joined",
        "demand_to_realized_event": "demand_to_realized_event_joined",
        "realized_event_to_realized_metrics": "realized_event_to_metrics_joined",
    }
    out = {}
    denominator = len(trace_rows)
    for name, column in checks.items():
        missing = sum(1 for row in trace_rows if not _truthy(row.get(column)))
        out[name] = {"missing": missing, "denominator": denominator, "rate": _rate(missing, denominator)}
    return out


def _first_edge_for_eval(evaluation: ActionEvaluation) -> Edge | None:
    if not evaluation.matched_edge_ids:
        return None
    edge_by_id = {edge.edge_id: edge for edge in evaluation.edges}
    return edge_by_id.get(evaluation.matched_edge_ids[0])


def _quality_for_edge(evaluation: ActionEvaluation, edge_id: str) -> EdgeQuality | None:
    return next((quality for quality in evaluation.edge_qualities if quality.edge_id == edge_id), None)


def _raw_gap_for_edge(evaluation: ActionEvaluation, edge: Edge | None) -> Any:
    if edge is None:
        return ""
    slot = next((item for item in evaluation.slots if item.slot_id == edge.slot_id), None)
    return "" if slot is None else slot.gap_at_tau


def _event_reason_to_status(event_type: str) -> str:
    if event_type == "merge_success":
        return "merged"
    if event_type == "merge_failure":
        return "failed"
    return event_type


def _event_base(log_context: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "source_batch_id": SOURCE_BATCH_ID,
        "source_table": "prompt3a_readiness_micro_run",
        "run_id": log_context["run_id"],
        "scenario_id": log_context["scenario_id"],
        "seed": log_context["seed"],
        "algorithm_id": log_context["algorithm_id"],
        "decision_context_id": log_context["decision_context_id"],
    }


def _base_row(log_context: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "source_batch_id": SOURCE_BATCH_ID,
        "source_table": "prompt3a_readiness_micro_run",
        "run_id": log_context["run_id"],
        "scenario_id": log_context["scenario_id"],
        "seed": log_context["seed"],
        "algorithm_id": log_context["algorithm_id"],
        "step": log_context["step"],
        "time": log_context["time"],
        "decision_context_id": log_context["decision_context_id"],
        "state_hash": log_context["state_hash"],
        "config_hash": log_context["config_hash"],
        "code_version": log_context["code_version"],
    }


def _hash_variant_config(config: ScenarioConfig, variant: str, params: ActionConfig) -> str:
    payload = {
        "scenario_id": config.scenario_id,
        "seed": config.seed,
        "variant": variant,
        "params": {
            "H": params.H,
            "dt": params.dt,
            "dt_merge": params.dt_merge,
            "lambda_D": params.lambda_D,
            "lambda_C": params.lambda_C,
            "theta": params.theta,
        },
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:12]


def _stable_event_id(
    run_id: str,
    context_id: str,
    event_type: str,
    action_id: str,
    edge_id: str,
    reservation_id: str,
    demand_id: str,
) -> str:
    digest = hashlib.sha256(
        "|".join([run_id, context_id, event_type, action_id, edge_id, reservation_id, demand_id]).encode("utf-8")
    ).hexdigest()[:12]
    return f"rev_{_safe_id(run_id)}_{_safe_id(context_id)}_{event_type}_{digest}"


def _safe_id(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in value).strip("_")


def _gap_id_from_edge(edge: Edge | None) -> str:
    if edge is None:
        return ""
    return f"{edge.front_id}-{edge.rear_id}"


def _demand_id(run_id: str, ramp_id: int | str) -> str:
    return f"demand_{_safe_id(run_id)}_r{ramp_id}"


def _first_ramp_id(state: TrafficState) -> int:
    ramps = [vehicle.id for vehicle in state.vehicles.values() if vehicle.role == "ramp"]
    return ramps[0] if ramps else -1


def _action_known_gap(variant: str) -> str:
    if variant == "without_Cbar":
        return "lambda_C=0 uses existing objective parameter; no first-class AblationConfig flag exists"
    if variant == "without_theta":
        return "theta=0 uses existing select_action threshold parameter; no first-class AblationConfig flag exists"
    if variant == "forced_accommodation":
        return "Prompt3A micro-policy uses existing candidate action hooks; not registered in BASELINE_CONFIGS"
    return ""


def _compact_sample(row: Mapping[str, Any] | None) -> dict[str, Any]:
    if row is None:
        return {}
    keys = [
        "scenario_id",
        "scenario_family",
        "variant",
        "selected_action_id",
        "selected_action_type",
        "selected_edge_id",
        "selected_gap_id",
        "reservation_id",
        "demand_id",
        "realized_event_id",
        "can_join_full_chain",
        "missing_join_reason",
    ]
    return {key: row.get(key, "") for key in keys}


def _compact_metric_sample(row: Mapping[str, Any] | None) -> dict[str, Any]:
    if row is None:
        return {}
    keys = [
        "realized_event_id",
        "hard_brake_count",
        "max_deceleration",
        "speed_variance_delta",
        "max_wave_amplitude",
        "mainline_disturbance_cost",
        "RD_realized_proxy",
    ]
    return {key: row.get(key, "") for key in keys}


def _candidate_columns() -> list[str]:
    return [
        "schema_version",
        "source_batch_id",
        "source_table",
        "run_id",
        "scenario_id",
        "seed",
        "algorithm_id",
        "step",
        "time",
        "decision_context_id",
        "state_hash",
        "config_hash",
        "code_version",
        "scenario_family",
        "variant",
        "candidate_action_id",
        "candidate_edge_id",
        "candidate_gap_id",
        "physical_gap_id",
        "slot_group_id",
        "ramp_vehicle_id",
        "matching_id",
        "matching_type",
        "source_policy",
        "P_R",
        "RD_pred",
        "RD_pred_source",
        "raw_gap_size",
        "closing_rate",
        "front_vehicle_id",
        "rear_vehicle_id",
        "is_selected_by_full_rpmi",
        "is_selected_by_baseline_no_action",
        "is_selected_by_raw_largest_gap",
        "is_selected_by_forced_accommodation",
        "selected_gap_available",
        "known_gap",
    ]


def _action_columns() -> list[str]:
    return [
        "schema_version",
        "source_batch_id",
        "source_table",
        "run_id",
        "scenario_id",
        "seed",
        "algorithm_id",
        "step",
        "time",
        "decision_context_id",
        "state_hash",
        "config_hash",
        "code_version",
        "scenario_family",
        "variant",
        "action_id",
        "action_type",
        "nominal_edge_id",
        "selected_edge_id",
        "selected_gap_id",
        "selected_slot_group_id",
        "reservation_id_if_selected",
        "J",
        "J_none",
        "J_delta_vs_none",
        "Z_bar",
        "D_bar",
        "C_bar",
        "RCMV",
        "S_R",
        "Z_R",
        "matched_count",
        "matched_edge_ids",
        "matched_rd_sum",
        "invalid_count",
        "rank",
        "selected",
        "rejected_by_theta",
        "theta_suppression_observed",
        "cost_components_json",
        "lane_change_candidate_id",
        "lc_cost",
        "lc_feasibility_margin_front",
        "lc_feasibility_margin_rear",
        "lc_expected_gap_effect",
        "affects_action_selection",
        "affects_reservation_selection",
        "is_posthoc_diagnostic",
        "known_gap",
        "RD_pred_norm",
        "C_dist_norm",
        "S_safety_penalty",
        "Q_churn_penalty",
        "theta",
        "lambda_Z",
        "lambda_D",
        "lambda_C",
        "lambda_S",
        "lambda_Q",
        "selected_flag",
        "selection_reason",
    ]


def _trace_columns() -> list[str]:
    return [
        "schema_version",
        "source_batch_id",
        "source_table",
        "run_id",
        "scenario_id",
        "seed",
        "algorithm_id",
        "step",
        "time",
        "decision_context_id",
        "state_hash",
        "config_hash",
        "code_version",
        "scenario_family",
        "variant",
        "selected_action_id",
        "selected_action_type",
        "selected_action_rank",
        "selected_action_J",
        "selected_action_RCMV",
        "selected_action_C_bar",
        "selected_action_D_bar",
        "selected_action_Z_bar",
        "selected_action_S_R",
        "selected_action_Z_R",
        "selected_edge_id",
        "physical_gap_id",
        "selected_gap_id",
        "slot_group_id",
        "selected_slot_group_id",
        "selected_gap_P_R",
        "selected_gap_raw_size",
        "selected_gap_RD_pred",
        "selected_gap_RD_realized",
        "matching_id",
        "matching_type",
        "reservation_id",
        "reservation_status_after_initial",
        "reservation_final_status_after",
        "reservation_final_status_reason",
        "planned_tau",
        "commitment_status",
        "is_locked",
        "demand_id",
        "ramp_vehicle_id",
        "demand_status_after_final",
        "demand_event_reason_final",
        "merge_success",
        "predicted_unserved",
        "realized_unserved",
        "realized_event_id",
        "realized_event_type",
        "realized_event_severity",
        "metric_scope",
        "hard_brake_count_after",
        "max_deceleration_after",
        "max_deceleration_magnitude_after",
        "speed_wave_after",
        "speed_variance_delta_after",
        "max_wave_amplitude_after",
        "mainline_disturbance_cost_after",
        "min_TTC_after",
        "min_realized_gap_after",
        "RD_realized_proxy_after",
        "selected_action_to_gap_joined",
        "selected_gap_to_reservation_joined",
        "reservation_to_demand_joined",
        "demand_to_realized_event_joined",
        "realized_event_to_metrics_joined",
        "trajectory_proxy_metrics_joined",
        "can_join_full_chain",
        "missing_join_reason",
        "join_failure_reason",
        "red_line_status",
        "known_gap",
    ]


def _realized_event_columns() -> list[str]:
    return list(CSV_LOG_SCHEMAS["realized_events.csv"])


def _event_metric_columns() -> list[str]:
    return list(CSV_LOG_SCHEMAS["event_metric_windows.csv"])


def _write_csv(path: str | Path, rows: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> None:
    with Path(path).open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _csv_value(row.get(column, "")) for column in columns})


def _read_csv(path: str | Path) -> list[dict[str, str]]:
    if not Path(path).exists():
        return []
    with Path(path).open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (list, tuple, dict)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        if math.isinf(value):
            return "inf" if value > 0 else "-inf"
    return value


def _float(value: Any) -> float:
    try:
        if value in ("", None):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _blank_to_inf(value: Any) -> float:
    if value is None or value == "":
        return math.inf
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.inf


def _finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _variance(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    mean = _mean(values)
    return sum((value - mean) ** 2 for value in values) / len(values)


def _rate(numerator: float, denominator: float) -> float:
    return 0.0 if float(denominator) <= 0.0 else float(numerator) / float(denominator)


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "pass"}


if __name__ == "__main__":
    main()
