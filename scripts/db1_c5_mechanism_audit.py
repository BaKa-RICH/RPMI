"""DB1 C5 mechanism audit for no-action CAV/HDV credibility.

This script is intentionally narrow. It runs one full RPMI-CMV decision on the
DB1 C5 CAV-HDV/front-acceleration audit scenario and writes trace artifacts for
human implementation review. It does not create locked evidence, tune lambda, or
run raw/forced/ablation variants.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
import csv
import json
import math
import shutil
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
for path in (REPO_ROOT, SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from rpmi.actions import (
    ActionConfig,
    action_evaluation_to_row,
    action_to_row,
    find_near_miss_edges,
    generate_candidate_actions,
    run_action_selection,
    slot_inventory_params,
)
from rpmi.dynamics import compute_gap_margin, step_traffic
from rpmi.ids import make_decision_context_id
from rpmi.matching import MatchingConfig, build_matching_edges, matching_result_to_rows, solve_matching_v0_greedy_conflict
from rpmi.reservations import Reservation, execute_reservation_guidance, reservation_to_row, update_reservation_at_tau
from rpmi.runner import resolve_baseline_config
from rpmi.scenarios import (
    ScenarioConfig,
    compute_readiness_metrics,
    generate_state,
    make_scenario_config,
    no_action_rollout,
    readiness_check,
    scenario_config_hash,
)
from rpmi.slots import (
    Edge,
    EdgeQuality,
    SlotInventoryParams,
    build_edges,
    compute_edge_qualities,
    compute_feasible_interval,
    edge_quality_to_row,
    generate_slots,
)
from rpmi.state import TrafficState, VehicleState, hash_state
from rpmi.reproducibility import get_code_version


SCENARIO_ID = "DB1-C5-CAV-HDV-FRONTACC-V20-GAP55-TAU35"
SCENARIO_FAMILY = "DB1-C5"
VARIANT = "full_RPMI"
OUTPUT_ROOT = REPO_ROOT / "outputs" / "d2_5_theory_alignment" / "DB1_audit"


def main() -> None:
    run_dir = _prepare_run_dir()
    config = build_db1_scenario_config()
    state = generate_state(config)
    params = db1_action_config(config)
    slot_params = slot_inventory_params(params)
    code_version = get_code_version(REPO_ROOT)
    run_id = run_dir.name
    decision_context_id = make_decision_context_id(run_id, 0)
    log_context = _log_context(run_id, decision_context_id, state, config, code_version)

    no_action = _inventory_for_rollout(
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
    action_inventory = {
        "rollout": dict(selected.rollout or {}),
        "slots": list(selected.slots),
        "edges": list(selected.edges),
        "qualities": list(selected.edge_qualities),
        "matching_edges": list(selected.matching_edges),
        "matching": selected.matching_result,
        "edge_map": {edge.edge_id: edge for edge in selected.edges},
    }
    reservations = _create_reservations(selected, decision_context_id, slot_params)
    execution = _execute_guided_episode(
        state,
        selected_action,
        reservations,
        action_inventory["edge_map"],
        params,
        slot_params,
    )
    summary = _summary(
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
    records = _trace_records(
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

    _write_json(run_dir / "DB1_audit_summary.json", summary)
    _write_jsonl(run_dir / "DB1_audit_trace.jsonl", records)
    _write_summary_csv(run_dir / "DB1_audit_trace_summary.csv", records)
    _write_csv(run_dir / "DB1_audit_no_action_edges.csv", _edge_rows(no_action, log_context), _edge_columns())
    _write_csv(run_dir / "DB1_audit_action_edges.csv", _edge_rows(action_inventory, log_context), _edge_columns())
    _write_csv(
        run_dir / "DB1_audit_actions.csv",
        [action_to_row(action, log_context) for action in _actions_for_log(result, candidate_actions)],
        _action_columns(),
    )
    _write_csv(
        run_dir / "DB1_audit_action_evaluations.csv",
        [action_evaluation_to_row(evaluation, log_context) for evaluation in result.evaluations],
        _action_evaluation_columns(),
    )
    _write_csv(
        run_dir / "DB1_audit_counterfactual_action_edges.csv",
        _counterfactual_action_edge_rows(result, log_context),
        _counterfactual_edge_columns(),
    )
    _write_csv(
        run_dir / "DB1_audit_matching.csv",
        _matching_rows(no_action, log_context, "baseline")
        + _matching_rows(action_inventory, log_context, "selected_action"),
        _matching_columns(),
    )
    _write_csv(
        run_dir / "DB1_audit_reservations.csv",
        [reservation_to_row(item, log_context) for item in execution["reservations"]],
        _reservation_columns(),
    )
    _write_csv(run_dir / "DB1_audit_vehicle_steps.csv", execution["vehicle_rows"], _vehicle_columns())
    _write_csv(run_dir / "DB1_audit_events.csv", execution["event_rows"], _event_columns())

    print(f"db1_audit_run_dir={run_dir}")
    print(f"db1_audit_trace_jsonl={run_dir / 'DB1_audit_trace.jsonl'}")
    print(f"db1_audit_trace_summary_csv={run_dir / 'DB1_audit_trace_summary.csv'}")
    print(f"db1_selected_action={summary['selected_action']['action_id']}")
    print(f"db1_selected_action_type={summary['selected_action']['action_type']}")
    print(f"db1_selected_edge={summary['selected_reservation']['edge_id']}")
    print(f"db1_blocker={str(summary['blocker']['is_blocker']).lower()}")
    print(f"db1_blocker_kind={summary['blocker']['kind']}")
    print(f"db1_no_action_all_target_edges_invalid={str(summary['no_action']['all_target_edges_invalid']).lower()}")


def build_db1_scenario_config() -> ScenarioConfig:
    return make_scenario_config(
        SCENARIO_ID,
        seed=0,
        road={
            "target_lane": 0,
            "ramp_lane": -1,
            "ramp_end_x": 150.0,
            "merge_zone": (0.0, 150.0),
            "lanes": 2,
        },
        simulation={
            "dt": 0.5,
            "H": 4.0,
            "dt_merge": 0.5,
            "W_min_buffer": 0.0,
            "RD_max": 1.0,
            "d0": 2.0,
            "T_front_CAV_following": 1.2,
            "T_rear_HDV_following": 1.6,
            "b_safe": 2.5,
            "u_min": -4.5,
            "u_max": 2.0,
            "v_max": 40.0,
            "rd_speed_scale": 10.0,
            "T_prod": 3.5,
            "production_width_buffer": 0.0,
            "near_miss_delta_W_max": 12.0,
            "near_miss_RD_max": 1.0,
            "theta": 0.05,
            "lambda_D": 1.0,
            "lambda_C": 1.0,
            "T_merge": 0.5,
            "T_buffer": 0.0,
            "conflict_mode": "time_window_default",
            "action_mode": "override",
            "event_min_gap": 0.0,
            "enable_boundary_speed": True,
            "enable_lane_change": False,
        },
        vehicles={
            "boundary_pairs": ["CAV-HDV"],
            "gap_widths": [55.0],
            "front_x": 100.0,
            "pair_spacing": 90.0,
            "target_speed": 20.0,
            "front_speed_offsets": [0.0],
            "rear_speed_offsets": [0.0],
            "inner_receiving_gap_count": 1,
            "ramp_count": 1,
            "ramp_start_x": 74.0,
            "ramp_spacing": 14.0,
            "ramp_speed": 20.0,
            "ramp_speed_step": 0.0,
            "front_nominal_v0": 20.0,
            "rear_nominal_v0": 22.0,
            "ramp_nominal_v0": 20.0,
            "cav_idm_params": {"a_max": 1.2, "b": 2.5, "T": 1.0, "s0": 2.0, "delta": 4.0},
            "hdv_idm_params": {"a_max": 1.5, "b": 2.0, "T": 1.2, "s0": 2.0, "delta": 4.0},
        },
        readiness_targets={
            "raw_gap_count_min": 0,
            "baseline_ZR_min": 1.0,
            "near_miss_count_min": 1,
            "boundary_cav_min": 1,
            "raw_gap_illusion_min": 0,
        },
        mechanism_targets={
            "mechanism": "DB1-C5",
            "scenario_family": SCENARIO_FAMILY,
            "mechanism_target": "action_conditioned_reservation_front_acc",
            "boundary_pairs": ["CAV-HDV"],
            "target_designed_tau": 3.5,
            "variant": VARIANT,
        },
    )


def db1_action_config(config: ScenarioConfig) -> ActionConfig:
    values = {**config.road, **config.simulation, **config.vehicles, **config.ramp}
    return ActionConfig(
        H=float(values["H"]),
        dt=float(values["dt"]),
        dt_merge=float(values["dt_merge"]),
        target_lane=int(values["target_lane"]),
        W_min_buffer=float(values["W_min_buffer"]),
        RD_max=float(values["RD_max"]),
        d0=float(values["d0"]),
        T_front_CAV_following=float(values["T_front_CAV_following"]),
        T_rear_HDV_following=float(values["T_rear_HDV_following"]),
        b_safe=float(values["b_safe"]),
        u_min=float(values["u_min"]),
        u_max=float(values["u_max"]),
        v_max=float(values["v_max"]),
        T_prod=float(values["T_prod"]),
        production_width_buffer=float(values["production_width_buffer"]),
        lambda_D=float(values["lambda_D"]),
        lambda_C=float(values["lambda_C"]),
        theta=float(values["theta"]),
        u_max_comfort=float(values["u_max"]),
        u_min_comfort=float(values["u_min"]),
        rd_speed_scale=float(values["rd_speed_scale"]),
        ramp_end_x=float(values["ramp_end_x"]),
        T_merge=float(values["T_merge"]),
        T_buffer=float(values["T_buffer"]),
        conflict_mode=str(values["conflict_mode"]),
        near_miss_delta_W_max=float(values["near_miss_delta_W_max"]),
        near_miss_RD_max=float(values["near_miss_RD_max"]),
        action_mode=str(values["action_mode"]),
        event_min_gap=float(values["event_min_gap"]),
        lanes=int(values["lanes"]),
        enable_boundary_speed=True,
        enable_lane_change=False,
    )


def _inventory_for_rollout(
    rollout: Mapping[float, TrafficState],
    state: TrafficState,
    slot_params: SlotInventoryParams,
    *,
    eval_context: str,
    action_id: str | None,
    params: ActionConfig,
) -> dict[str, Any]:
    slots = generate_slots(
        rollout,
        t=state.time,
        H=slot_params.H,
        dt_merge=slot_params.dt_merge,
        target_lane=slot_params.target_lane,
        eval_context=eval_context,
        action_id=action_id,
    )
    ramps = [vehicle for vehicle in state.vehicles.values() if vehicle.active and vehicle.role == "ramp"]
    edges = build_edges(ramps, slots)
    qualities = compute_edge_qualities(edges, rollout, state, slot_params)
    demand = {ramp.id: 1.0 for ramp in ramps}
    matching_edges = build_matching_edges(
        qualities,
        demand,
        edge_metadata={edge.edge_id: {"physical_gap_id": edge.physical_gap_id, "tau": edge.tau} for edge in edges},
    )
    matching = solve_matching_v0_greedy_conflict(
        matching_edges,
        demand,
        MatchingConfig(T_merge=params.T_merge, T_buffer=params.T_buffer, conflict_mode=params.conflict_mode),
    )
    return {
        "rollout": dict(rollout),
        "slots": slots,
        "edges": edges,
        "qualities": qualities,
        "matching_edges": matching_edges,
        "matching": matching,
        "edge_map": {edge.edge_id: edge for edge in edges},
    }


def _create_reservations(
    selected: Any,
    decision_context_id: str,
    slot_params: SlotInventoryParams,
) -> list[Reservation]:
    edge_by_id = {edge.edge_id: edge for edge in selected.edges}
    quality_by_id = {quality.edge_id: quality for quality in selected.edge_qualities}
    state_by_tau = dict(selected.rollout or {})
    reservations = []
    for edge_id in selected.matched_edge_ids:
        edge = edge_by_id.get(edge_id)
        quality = quality_by_id.get(edge_id)
        state_tau = state_by_tau.get(round(edge.tau, 10)) if edge is not None else None
        if edge is None or quality is None or state_tau is None:
            continue
        interval = compute_feasible_interval(edge, state_tau, slot_params)
        status = "planned" if quality.is_reservable else "failed_invalid_slot"
        reason = "" if quality.is_reservable else quality.fail_reason_priority
        reservations.append(
            Reservation(
                reservation_id=f"res_{selected.action_id}_{edge.edge_id}",
                decision_context_id=decision_context_id,
                ramp_id=edge.ramp_id,
                edge_id=edge.edge_id,
                slot_id=edge.slot_id,
                action_id=selected.action_id,
                planned_tau=edge.tau,
                planned_merge_x=(interval.lower + interval.upper) / 2.0,
                planned_interval_lower=interval.lower,
                planned_interval_upper=interval.upper,
                status=status,
                failure_reason=reason,
                stale_flag=False,
            )
        )
    return reservations


def _execute_guided_episode(
    state: TrafficState,
    action: Any,
    reservations: Sequence[Reservation],
    edge_map: Mapping[str, Edge],
    params: ActionConfig,
    slot_params: SlotInventoryParams,
) -> dict[str, Any]:
    current = state
    active_reservations = list(reservations)
    vehicle_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    guidance_rows: list[dict[str, Any]] = []
    dyn_config = {
        "dt": params.dt,
        "action_mode": params.action_mode,
        "limits": {"u_min": params.u_min, "u_max": params.u_max, "v_max": params.v_max},
        "cav_nominal_cf": {"v0": 20.0},
        "hdv_idm": {"v0": 22.0},
        "min_gap": params.event_min_gap,
    }
    for _ in range(max(1, int(round(params.H / params.dt)))):
        action_commands = _commands_for_action(action, current.time)
        guidance_commands, active_reservations = execute_reservation_guidance(
            current,
            active_reservations,
            current.time,
            u_min=params.u_min,
            u_max=params.u_max,
        )
        guidance_rows.extend(
            {
                "time": current.time,
                "ramp_id": ramp_id,
                "reservation_id": command.get("reservation_id", ""),
                "a_action": command.get("a_action", ""),
            }
            for ramp_id, command in guidance_commands.items()
        )
        current, step_rows, step_events = step_traffic(
            current,
            {**action_commands, **guidance_commands},
            dyn_config,
        )
        for event in step_events:
            event.setdefault("linked_action_id", action.action_id)
            for reservation in active_reservations:
                if reservation.ramp_id in event.get("vehicle_ids", []):
                    event["linked_reservation_id"] = reservation.reservation_id
                    event["linked_edge_id"] = reservation.edge_id
                    break
        vehicle_rows.extend(step_rows)
        event_rows.extend(step_events)
        active_reservations = [
            update_reservation_at_tau(
                current,
                reservation,
                edge_map[reservation.edge_id],
                slot_params=slot_params,
                tolerance=max(params.dt, 1e-9) / 2.0,
            )
            for reservation in active_reservations
            if reservation.edge_id in edge_map
        ]
    return {
        "final_state": current,
        "reservations": active_reservations,
        "vehicle_rows": vehicle_rows,
        "event_rows": event_rows,
        "guidance_rows": guidance_rows,
    }


def _commands_for_action(action: Any, current_time: float) -> dict[int, dict[str, Any]]:
    if action.action_type != "front_acc":
        return {}
    profile = action.control_profile
    if current_time >= float(profile.get("T_prod", 0.0)) - 1e-9:
        return {}
    return {
        int(action.controlled_cavs[0]): {
            "a_action": float(profile.get("u_front", 0.0)),
            "action_id": action.action_id,
        }
    }


def _trace_records(
    config: ScenarioConfig,
    state: TrafficState,
    params: ActionConfig,
    slot_params: SlotInventoryParams,
    no_action: Mapping[str, Any],
    action_inventory: Mapping[str, Any],
    result: Any,
    candidate_actions: Sequence[Any],
    reservations: Sequence[Reservation],
    execution: Mapping[str, Any],
    log_context: Mapping[str, Any],
) -> list[dict[str, Any]]:
    records = [
        {
            "record_type": "run_metadata",
            **log_context,
            "scenario_family": SCENARIO_FAMILY,
            "mechanism_target": config.mechanism_targets.get("mechanism_target"),
            "variant": VARIANT,
            "scenario_config": asdict(config),
            "action_config": asdict(params),
            "slot_params": asdict(slot_params),
        },
        {
            "record_type": "candidate_time_grid",
            "variant": VARIANT,
            "candidate_taus": [tau for _, tau in _candidate_grid(params)],
        },
    ]
    records.extend(_rollout_records("no_action_rollout", no_action, no_action["rollout"], None))
    records.extend(_edge_records("slot_edge_validity", no_action, no_action["rollout"]))
    records.extend(_action_records(result, candidate_actions, log_context))
    diagnostic_eval = _best_non_none_evaluation(result)
    if diagnostic_eval is not None and diagnostic_eval.action_id != result.selected_action.action_id:
        diagnostic_inventory = _inventory_from_evaluation(diagnostic_eval)
        records.extend(
            _rollout_records(
                "diagnostic_action_conditioned_rollout",
                diagnostic_inventory,
                diagnostic_inventory["rollout"],
                diagnostic_eval.action_id,
            )
        )
        records.extend(
            _edge_records(
                "diagnostic_action_conditioned_edge_validity",
                diagnostic_inventory,
                diagnostic_inventory["rollout"],
            )
        )
    selected_action = result.selected_action
    records.extend(_rollout_records("action_conditioned_rollout", action_inventory, action_inventory["rollout"], selected_action.action_id))
    records.extend(_edge_records("action_conditioned_edge_validity", action_inventory, action_inventory["rollout"]))
    records.append(_action_effect_record(no_action, action_inventory, result))
    records.append(_matching_record("baseline_matching", no_action))
    records.append(_matching_record("selected_action_matching", action_inventory))
    for reservation in reservations:
        records.append({"record_type": "reservation", **reservation_to_row(reservation, log_context)})
    records.extend({"record_type": "ramp_guidance", **row} for row in execution["guidance_rows"])
    records.extend({"record_type": "result_event", **row} for row in _result_event_records(execution, reservations))
    return records


def _rollout_records(
    record_type: str,
    inventory: Mapping[str, Any],
    rollout: Mapping[float, TrafficState],
    action_id: str | None,
) -> list[dict[str, Any]]:
    out = []
    for _, tau in _candidate_grid_from_inventory(inventory):
        state_tau = rollout.get(round(tau, 10))
        if state_tau is None:
            continue
        for vehicle_id in (1, 2, 100):
            vehicle = state_tau.vehicles[vehicle_id]
            out.append(
                {
                    "record_type": record_type,
                    "eval_context": "baseline" if action_id is None else "action",
                    "action_id": action_id,
                    "tau": tau,
                    "vehicle_id": vehicle.id,
                    "role": vehicle.role,
                    "veh_type": vehicle.veh_type,
                    "lane": vehicle.lane,
                    "x": vehicle.x,
                    "v": vehicle.v,
                    "a": vehicle.a,
                    "length": vehicle.length,
                }
            )
    return out


def _edge_records(
    record_type: str,
    inventory: Mapping[str, Any],
    rollout: Mapping[float, TrafficState],
) -> list[dict[str, Any]]:
    out = []
    quality_by_id = {quality.edge_id: quality for quality in inventory["qualities"]}
    for edge in inventory["edges"]:
        if edge.front_id != 1 or edge.rear_id != 2 or edge.ramp_id != 100:
            continue
        state_tau = rollout.get(round(edge.tau, 10))
        quality = quality_by_id[edge.edge_id]
        interval = compute_feasible_interval(edge, state_tau, _params_from_quality(quality)) if state_tau else None
        front = state_tau.vehicles[edge.front_id] if state_tau else None
        rear = state_tau.vehicles[edge.rear_id] if state_tau else None
        raw_gap = compute_gap_margin(front, rear) if front is not None and rear is not None else None
        out.append(
            {
                "record_type": record_type,
                "edge_id": edge.edge_id,
                "slot_id": edge.slot_id,
                "eval_context": edge.eval_context,
                "action_id": edge.action_id,
                "tau": edge.tau,
                "ramp_id": edge.ramp_id,
                "front_id": edge.front_id,
                "rear_id": edge.rear_id,
                "raw_gap": raw_gap,
                "ramp_length": state_tau.vehicles[edge.ramp_id].length if state_tau else None,
                "d_front": None if interval is None else interval.d_front,
                "d_rear": None if interval is None else interval.d_rear,
                "lower": None if interval is None else interval.lower,
                "upper": None if interval is None else interval.upper,
                "W": quality.W,
                "V_phys_pred": quality.V_phys_theory,
                "V_phys_buffer": quality.V_phys_buffer,
                "I_reach": quality.I_reach,
                "reachability": quality.reachability,
                "validity_reason": quality.fail_reason_priority,
                "is_reservable": quality.is_reservable,
                "RD": quality.RD,
            }
        )
    return out


def _action_records(
    result: Any,
    candidate_actions: Sequence[Any],
    log_context: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows = []
    eval_by_id = {evaluation.action_id: evaluation for evaluation in result.evaluations}
    for action in _actions_for_log(result, candidate_actions):
        evaluation = eval_by_id.get(action.action_id)
        rows.append(
            {
                "record_type": "candidate_action",
                **action_to_row(action, log_context),
                "target_vehicle_id": action.controlled_cavs[0] if action.controlled_cavs else "",
                "effective_duration": action.control_profile.get("T_prod", 0.0),
                "u_front_profile": action.control_profile.get("u_front", 0.0),
                "action_limits": {"u_min": -4.5, "u_max": 2.0},
                "J": None if evaluation is None else evaluation.J,
                "RCMV": None if evaluation is None else evaluation.RCMV,
                "selected": action.action_id == result.selected_action.action_id,
            }
        )
    return rows


def _action_effect_record(no_action: Mapping[str, Any], action_inventory: Mapping[str, Any], result: Any) -> dict[str, Any]:
    selected_eval = result.selected_evaluation
    edge_id = selected_eval.matched_edge_ids[0] if selected_eval.matched_edge_ids else ""
    action_edge = next((edge for edge in action_inventory["edges"] if edge.edge_id == edge_id), None)
    selected_tau = action_edge.tau if action_edge is not None else 3.5
    no_state = no_action["rollout"].get(round(selected_tau, 10))
    action_state = action_inventory["rollout"].get(round(selected_tau, 10))
    baseline_quality = _quality_for_tau(no_action, selected_tau)
    selected_quality = next((quality for quality in action_inventory["qualities"] if quality.edge_id == edge_id), None)
    return {
        "record_type": "action_effect",
        "action_id": result.selected_action.action_id,
        "selected_edge_id": edge_id,
        "selected_tau": selected_tau,
        "front_extra_displacement": None
        if no_state is None or action_state is None
        else action_state.vehicles[1].x - no_state.vehicles[1].x,
        "W_before": None if baseline_quality is None else baseline_quality.W,
        "W_after": None if selected_quality is None else selected_quality.W,
        "reservation_edge_source": "action_conditioned" if "_act_" in edge_id else "baseline_or_none",
    }


def _matching_record(record_type: str, inventory: Mapping[str, Any]) -> dict[str, Any]:
    matching = inventory.get("matching")
    return {
        "record_type": record_type,
        "matching_id": "" if matching is None else matching.matching_id,
        "selected_edge_ids": [] if matching is None else list(matching.selected_edge_ids),
        "S_R": None if matching is None else matching.S_R,
        "Z_R": None if matching is None else matching.Z_R,
        "D_H": None if matching is None else matching.D_H,
        "solver_name": None if matching is None else matching.solver_name,
    }


def _result_event_records(execution: Mapping[str, Any], reservations: Sequence[Reservation]) -> list[dict[str, Any]]:
    rows = []
    if execution["event_rows"]:
        rows.extend(dict(row) for row in execution["event_rows"])
    if not rows:
        final_reservations = execution.get("reservations", reservations)
        for reservation in final_reservations:
            rows.append(
                {
                    "event_type": "merge_success" if reservation.status == "merged" else reservation.status,
                    "linked_action_id": reservation.action_id,
                    "linked_edge_id": reservation.edge_id,
                    "linked_reservation_id": reservation.reservation_id,
                    "event_time": reservation.planned_tau,
                    "service": reservation.status == "merged",
                    "near_service": _near_service(reservation),
                    "hard_brake": False,
                    "overlap": False,
                    "failure_reason": reservation.failure_reason,
                    "actual_x_at_tau": reservation.actual_x_at_tau,
                    "actual_margin_front": reservation.actual_margin_front,
                    "actual_margin_rear": reservation.actual_margin_rear,
                }
            )
    return rows


def _summary(
    config: ScenarioConfig,
    state: TrafficState,
    params: ActionConfig,
    slot_params: SlotInventoryParams,
    no_action: Mapping[str, Any],
    result: Any,
    reservations: Sequence[Reservation],
    execution: Mapping[str, Any],
    code_version: str,
) -> dict[str, Any]:
    readiness_metrics = compute_readiness_metrics(state, config)
    readiness = readiness_check(readiness_metrics, config)
    target_no_action = [
        quality
        for edge, quality in zip(no_action["edges"], no_action["qualities"])
        if edge.ramp_id == 100 and edge.front_id == 1 and edge.rear_id == 2
    ]
    selected_eval = result.selected_evaluation
    selected_edge_id = selected_eval.matched_edge_ids[0] if selected_eval.matched_edge_ids else ""
    selected_quality = next(
        (quality for quality in selected_eval.edge_qualities if quality.edge_id == selected_edge_id),
        None,
    )
    baseline_quality = _quality_for_tau(no_action, 3.5)
    final_reservation = execution["reservations"][0] if execution["reservations"] else (reservations[0] if reservations else None)
    blocker_reasons = []
    if result.selected_action.action_type != "front_acc":
        blocker_reasons.append("selected_action_not_front_acc")
    if result.selected_action.controlled_cavs != (1,):
        blocker_reasons.append("selected_action_target_not_vehicle_1")
    if selected_quality is None or selected_quality.W < 0.0:
        blocker_reasons.append("action_conditioned_selected_W_negative")
    if "_act_" not in selected_edge_id:
        blocker_reasons.append("selected_reservation_not_action_conditioned")
    if not final_reservation or final_reservation.status != "merged":
        blocker_reasons.append("reservation_did_not_merge")
    return {
        "schema_version": "DB1_audit_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scenario_id": config.scenario_id,
        "scenario_family": SCENARIO_FAMILY,
        "variant": VARIANT,
        "mechanism_target": config.mechanism_targets.get("mechanism_target"),
        "code_version": code_version,
        "state_hash": hash_state(state),
        "scenario_hash": scenario_config_hash(config),
        "readiness": {"pass": readiness.readiness_pass, "reason": readiness.fail_reason},
        "params": {"action": asdict(params), "slot": asdict(slot_params)},
        "no_action": {
            "all_target_edges_invalid": all(not quality.is_reservable for quality in target_no_action),
            "target_tau_3_5_W": None if baseline_quality is None else baseline_quality.W,
            "target_tau_3_5_reason": None if baseline_quality is None else baseline_quality.fail_reason_priority,
            "reservable_taus": [
                quality.edge_id
                for quality in target_no_action
                if quality.is_reservable
            ],
            "front_accel_abs_max": _max_abs_accel(no_action["rollout"], 1),
            "rear_min_accel": _min_accel(no_action["rollout"], 2),
            "ramp_accel_abs_max": _max_abs_accel(no_action["rollout"], 100),
        },
        "selected_action": {
            "action_id": result.selected_action.action_id,
            "action_type": result.selected_action.action_type,
            "controlled_cavs": result.selected_action.controlled_cavs,
            "profile": result.selected_action.control_profile,
            "RCMV": selected_eval.RCMV,
            "J": selected_eval.J,
        },
        "selected_reservation": {
            "edge_id": selected_edge_id,
            "source": "action_conditioned" if "_act_" in selected_edge_id else "baseline_or_none",
            "W": None if selected_quality is None else selected_quality.W,
            "status": None if final_reservation is None else final_reservation.status,
            "planned_tau": None if final_reservation is None else final_reservation.planned_tau,
            "planned_merge_x": None if final_reservation is None else final_reservation.planned_merge_x,
        },
        "blocker": {
            "is_blocker": bool(blocker_reasons),
            "kind": "implementation_objective_blocker" if blocker_reasons else "",
            "reasons": blocker_reasons,
        },
        "forbidden_outputs": {"locked_files_created": False, "performance_claim": False},
    }


def _prepare_run_dir() -> Path:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = OUTPUT_ROOT / f"DB1_audit_{stamp}"
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)
    return run_dir


def _log_context(
    run_id: str,
    decision_context_id: str,
    state: TrafficState,
    config: ScenarioConfig,
    code_version: str,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "step": 0,
        "time": 0.0,
        "decision_context_id": decision_context_id,
        "state_hash": hash_state(state),
        "config_hash": scenario_config_hash(config),
        "code_version": code_version,
        "units_version": "rpmi_units_v1",
        "scenario_id": config.scenario_id,
        "seed": config.seed,
        "algorithm_id": VARIANT,
    }


def _candidate_grid(params: ActionConfig) -> list[tuple[int, float]]:
    out = []
    k = 1
    while k * params.dt_merge <= params.H + 1e-9:
        out.append((k, round(k * params.dt_merge, 10)))
        k += 1
    return out


def _candidate_grid_from_inventory(inventory: Mapping[str, Any]) -> list[tuple[int, float]]:
    return sorted({(edge.k, edge.tau) for edge in inventory["edges"]})


def _quality_for_tau(inventory: Mapping[str, Any], tau: float) -> EdgeQuality | None:
    for edge, quality in zip(inventory["edges"], inventory["qualities"]):
        if edge.ramp_id == 100 and edge.front_id == 1 and edge.rear_id == 2 and abs(edge.tau - tau) <= 1e-9:
            return quality
    return None


def _params_from_quality(quality: EdgeQuality) -> dict[str, Any]:
    return {
        "W_min_buffer": quality.rd_components.get("W_min_buffer", 0.0),
        "d0": quality.rd_components.get("d0", 0.0),
        "T_safe": quality.rd_components.get("T_safe", 0.0),
        "T_front_CAV_following": quality.rd_components.get("T_front_CAV_following"),
        "T_rear_HDV_following": quality.rd_components.get("T_rear_HDV_following"),
        "b_safe": quality.rd_components.get("b_safe", 2.5),
    }


def _actions_for_log(result: Any, candidate_actions: Sequence[Any]) -> list[Any]:
    by_id = {action.action_id: action for action in candidate_actions}
    by_id[result.selected_action.action_id] = result.selected_action
    ordered_ids = [evaluation.action_id for evaluation in result.evaluations]
    return [by_id[action_id] for action_id in ordered_ids if action_id in by_id]


def _best_non_none_evaluation(result: Any) -> Any | None:
    candidates = [
        evaluation
        for evaluation in result.evaluations
        if evaluation.action_id != "a0_none" and math.isfinite(evaluation.RCMV)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda item: (item.RCMV, -item.J, item.action_id))


def _inventory_from_evaluation(evaluation: Any) -> dict[str, Any]:
    return {
        "rollout": dict(evaluation.rollout or {}),
        "slots": list(evaluation.slots),
        "edges": list(evaluation.edges),
        "qualities": list(evaluation.edge_qualities),
        "matching_edges": list(evaluation.matching_edges),
        "matching": evaluation.matching_result,
        "edge_map": {edge.edge_id: edge for edge in evaluation.edges},
    }


def _counterfactual_action_edge_rows(result: Any, log_context: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for evaluation in result.evaluations:
        if evaluation.action_id == "a0_none":
            continue
        inventory = _inventory_from_evaluation(evaluation)
        for row in _edge_rows(inventory, log_context):
            rows.append(
                {
                    **row,
                    "counterfactual_action_id": evaluation.action_id,
                    "counterfactual_J": evaluation.J,
                    "counterfactual_RCMV": evaluation.RCMV,
                    "counterfactual_selected": evaluation.selected,
                }
            )
    return rows


def _near_service(reservation: Reservation) -> bool:
    margins = [
        value
        for value in (reservation.actual_margin_front, reservation.actual_margin_rear)
        if value is not None
    ]
    return bool(margins) and reservation.status != "merged" and min(margins) >= -0.05


def _max_abs_accel(rollout: Mapping[float, TrafficState], vehicle_id: int) -> float:
    return max((abs(state.vehicles[vehicle_id].a) for state in rollout.values()), default=0.0)


def _min_accel(rollout: Mapping[float, TrafficState], vehicle_id: int) -> float:
    return min((state.vehicles[vehicle_id].a for state in rollout.values()), default=0.0)


def _edge_rows(inventory: Mapping[str, Any], log_context: Mapping[str, Any]) -> list[dict[str, Any]]:
    edge_by_id = {edge.edge_id: edge for edge in inventory["edges"]}
    return [
        edge_quality_to_row(edge_by_id[quality.edge_id], quality, log_context)
        for quality in inventory["qualities"]
        if quality.edge_id in edge_by_id
    ]


def _matching_rows(inventory: Mapping[str, Any], log_context: Mapping[str, Any], source: str) -> list[dict[str, Any]]:
    if inventory.get("matching") is None:
        return []
    return [
        {**row, "source_table": source}
        for row in matching_result_to_rows(inventory["matching"], inventory["matching_edges"], log_context)
    ]


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(_json_safe(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(_json_safe(dict(row)), sort_keys=True, ensure_ascii=False) + "\n")


def _write_summary_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    columns = [
        "record_type",
        "eval_context",
        "action_id",
        "tau",
        "edge_id",
        "W",
        "is_reservable",
        "validity_reason",
        "selected",
        "reservation_id",
        "event_type",
        "service",
        "near_service",
    ]
    _write_csv(path, rows, columns)


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _csv_value(row.get(column, "")) for column in columns})


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, float) and not math.isfinite(value):
        return "inf" if value > 0 else "-inf"
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(_json_safe(value), sort_keys=True, separators=(",", ":"))
    return value


def _json_safe(value: Any) -> Any:
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, VehicleState):
        return _json_safe(value.__dict__)
    return value


def _edge_columns() -> list[str]:
    return [
        "run_id",
        "scenario_id",
        "algorithm_id",
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
    ]


def _action_columns() -> list[str]:
    return [
        "run_id",
        "scenario_id",
        "algorithm_id",
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
    ]


def _action_evaluation_columns() -> list[str]:
    return [
        "run_id",
        "scenario_id",
        "algorithm_id",
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


def _counterfactual_edge_columns() -> list[str]:
    return [
        "run_id",
        "scenario_id",
        "algorithm_id",
        "counterfactual_action_id",
        "counterfactual_J",
        "counterfactual_RCMV",
        "counterfactual_selected",
        *_edge_columns()[3:],
    ]


def _matching_columns() -> list[str]:
    return [
        "run_id",
        "scenario_id",
        "algorithm_id",
        "source_table",
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
    ]


def _reservation_columns() -> list[str]:
    return [
        "run_id",
        "scenario_id",
        "algorithm_id",
        "reservation_id",
        "decision_context_id",
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
    ]


def _vehicle_columns() -> list[str]:
    return [
        "step",
        "time",
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
    ]


def _event_columns() -> list[str]:
    return [
        "event_id",
        "event_type",
        "step",
        "time",
        "vehicle_ids",
        "min_gap",
        "min_margin",
        "severity",
        "linked_reservation_id",
        "linked_action_id",
        "linked_edge_id",
        "note",
    ]


if __name__ == "__main__":
    main()
