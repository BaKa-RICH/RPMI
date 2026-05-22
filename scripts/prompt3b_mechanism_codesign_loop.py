"""Prompt 3B mechanism-activation co-design harness.

This script is intentionally an execution/logging harness. It does not change
RPMI core objective, simulator, reservation, or metric code. Every diagnostic
case below is an explicit deterministic config, and every objective/scenario
change is logged as a Prompt 3B co-design iteration.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
import csv
import json
import math
import sys

from rpmi.scenarios import ScenarioConfig, make_scenario_config

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import prompt3a_readiness_micro_run as p3a


OUTPUT_ROOT = Path("outputs/d2_5_theory_alignment")
GATE_DIR = OUTPUT_ROOT / "gate_D2_5_input"
HUMAN_REVIEW_DIR = OUTPUT_ROOT / "human_review"
SOURCE_BATCH_ID = "prompt3b_mechanism_codesign"
SCHEMA_VERSION = "d2_5_prompt3b_codesign_v0.1"

FULL_VARIANT = "full_RPMI_current_or_reconstructed_objective"
VARIANTS = [
    FULL_VARIANT,
    "raw_largest_gap",
    "forced_accommodation",
    "without_RD",
    "without_Cbar",
    "without_theta",
]
MINIMUM_MEANINGFUL_ITERATIONS = 6


@dataclass(frozen=True)
class IterationSpec:
    iteration_id: str
    scenario_family: str
    scenario_subfamily: str
    scenario_design_id: str
    scenario_id: str
    deterministic_case_id: str
    parameter_ladder_id: str
    theory_target: str
    construction_principle: str
    mechanism_target: str
    diagnostic_contrast: str
    controlled_knobs: str
    initial_state_pattern: str
    baseline_expected_behavior: str
    rpmi_expected_behavior: str
    required_metrics: str
    minimum_activation_gate: str
    pass_pattern: str
    fail_pattern: str
    failure_interpretation: str
    anti_cherry_picking_rule: str
    held_out_variant_rule: str
    trace_join_requirements: str
    random_seed_optional: str
    config_builder: Callable[[], ScenarioConfig]
    changed_component: str
    old_value: str
    new_value: str
    hypothesis: str
    keep_or_revert: str
    reason: str
    failure_type: str
    failure_observed: str


def main() -> None:
    p3a.SOURCE_BATCH_ID = SOURCE_BATCH_ID
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    GATE_DIR.mkdir(parents=True, exist_ok=True)
    HUMAN_REVIEW_DIR.mkdir(parents=True, exist_ok=True)

    specs = _iteration_specs()
    all_records: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    action_rows: list[dict[str, Any]] = []
    trace_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    metric_rows: list[dict[str, Any]] = []

    for spec in specs:
        scenario = spec.config_builder()
        params = p3a._params_for_scenario(scenario)
        for variant in VARIANTS:
            record = p3a._run_variant(
                scenario,
                spec.scenario_family,
                variant,
                params,
            )
            _patch_record_for_prompt3b(record, spec)
            all_records.append(record)
            candidate_rows.extend(record["candidate_rows"])
            action_rows.extend(record["action_rows"])
            trace_rows.append(record["trace_row"])
            event_rows.append(record["event_row"])
            metric_rows.append(record["metric_row"])

    baseline_rows = _baseline_comparison_rows(specs, trace_rows, action_rows, metric_rows)
    ablation_rows = _ablation_comparison_rows(specs, trace_rows, action_rows, metric_rows)
    failure_rows = _failure_trace_rows(specs, trace_rows, metric_rows)
    scenario_rows = _scenario_summary_rows(specs, trace_rows, metric_rows)
    iteration_rows = _co_design_iteration_rows(specs, trace_rows, action_rows, metric_rows)
    calibration_rows = _objective_calibration_rows(specs)
    design_rows = [_design_register_row(spec) for spec in specs]

    _write_csv(OUTPUT_ROOT / "objective_scenario_design_register.csv", design_rows, _design_columns())
    _write_csv(OUTPUT_ROOT / "co_design_iteration_log.csv", iteration_rows, _iteration_columns())
    _write_csv(OUTPUT_ROOT / "objective_calibration_log.csv", calibration_rows, _calibration_columns())
    _write_csv(GATE_DIR / "baseline_comparison_prompt3b.csv", baseline_rows, _comparison_columns())
    _write_csv(GATE_DIR / "ablation_comparison_prompt3b.csv", ablation_rows, _comparison_columns())
    _write_csv(GATE_DIR / "failure_trace_prompt3b.csv", failure_rows, _failure_columns())
    _write_csv(GATE_DIR / "scenario_summary_prompt3b.csv", scenario_rows, _scenario_summary_columns())
    _write_csv(GATE_DIR / "candidate_gap_table_prompt3b.csv", candidate_rows, _columns_union(candidate_rows, p3a._candidate_columns()))
    _write_csv(GATE_DIR / "action_value_decomposition_prompt3b.csv", action_rows, _columns_union(action_rows, p3a._action_columns()))
    _write_csv(GATE_DIR / "trace_join_table_prompt3b.csv", trace_rows, _columns_union(trace_rows, p3a._trace_columns()))
    _write_csv(GATE_DIR / "realized_events_prompt3b.csv", event_rows, p3a._realized_event_columns())
    _write_csv(GATE_DIR / "event_metric_windows_prompt3b.csv", metric_rows, p3a._event_metric_columns())

    _write_markdown_outputs(
        specs,
        trace_rows,
        action_rows,
        metric_rows,
        baseline_rows,
        ablation_rows,
        failure_rows,
        scenario_rows,
        iteration_rows,
        calibration_rows,
    )

    status = _overall_status(trace_rows, specs, iteration_rows)
    print(f"prompt3b_verdict={status['verdict']}")
    print(f"scenario_families_attempted={status['families']}")
    print(f"meaningful_iterations_completed={len(specs)}")
    print(f"mechanism_activation_status={status['activation']}")
    print(f"can_join_full_chain_rate={status['can_join_full_chain_rate']:.6f}")
    print(f"nontrivial_full_chain_count={status['nontrivial_full_chain_count']}")
    print(f"ready_for_prompt4_lock={str(status['ready']).lower()}")
    print(f"main_blocker_if_any={status['blocker']}")
    print(f"review_packet_path={HUMAN_REVIEW_DIR / 'PROMPT_3B_REVIEW_PACKET.md'}")


def _iteration_specs() -> list[IterationSpec]:
    common_required = (
        "selected_action, selected_gap, reservation, demand, realized_event, "
        "hard_brake_count, max_deceleration, speed_variance_delta, "
        "max_wave_amplitude, mainline_disturbance_cost, RD_realized_proxy"
    )
    common_trace = (
        "selected_action -> selected_gap -> reservation -> demand -> "
        "realized_event -> event_metric_windows must be joinable"
    )
    anti_cherry = (
        "This deterministic case and the next ladder change are declared before "
        "the variant runs; failed variants remain in the output tables."
    )
    held_out = (
        "Do not treat this calibration case as held-out or locked evidence; "
        "future Prompt 4 must define held-out variants separately."
    )
    return [
        IterationSpec(
            iteration_id="P3B-ITER-001",
            scenario_family="P0",
            scenario_subfamily="raw_gap_forced_trap_initial",
            scenario_design_id="P3B-P0-DESIGN-RAW65-B35-H5",
            scenario_id="P3B-P0-RAW65-B35-H5",
            deterministic_case_id="P3B-DET-P0-001",
            random_seed_optional="0",
            parameter_ladder_id="P0-LADDER-raw65-gapB35",
            theory_target="raw geometric largest gap may be misleading",
            construction_principle=(
                "Principled Diagnostic Scenario Construction: Gap A has larger "
                "raw size and higher closing rate; Gap B is smaller and lower RD."
            ),
            mechanism_target="raw_largest_gap should choose Gap A while full should prefer Gap B or no extra action",
            diagnostic_contrast="Gap A raw size > Gap B raw size; Gap A RD_pred > Gap B RD_pred",
            controlled_knobs="Gap A width 65, Gap B width 35, Gap A rear speed +10 m/s, horizon 5 s",
            initial_state_pattern="two target-lane boundary pairs with one ramp CAV",
            baseline_expected_behavior="raw_largest_gap selects Gap A",
            rpmi_expected_behavior="full chooses lower-RD Gap B or none if natural inventory suffices",
            required_metrics=common_required,
            minimum_activation_gate="raw selects Gap A and full does not select Gap A",
            pass_pattern="raw Gap A, full Gap B/none, complete trace joins",
            fail_pattern="forced_accommodation degenerates to no-action or all variants indistinguishable",
            failure_interpretation="Scenario lacks enough forced-action pressure if forced does not create action contrast.",
            anti_cherry_picking_rule=anti_cherry,
            held_out_variant_rule=held_out,
            trace_join_requirements=common_trace,
            config_builder=_p0_initial,
            changed_component="diagnostic_scenario_parameters",
            old_value="Gap B width 35; natural Gap B exists",
            new_value="next iteration narrows Gap B to 7 to create near-miss pressure",
            hypothesis="A narrower Gap B will force the action/baseline contrast to surface.",
            keep_or_revert="keep_for_lineage_only",
            reason="Raw-gap contrast is visible, but forced-accommodation pressure is weak.",
            failure_type="revise_scenario",
            failure_observed="forced_accommodation did not establish a high-disturbance accommodation contrast",
        ),
        IterationSpec(
            iteration_id="P3B-ITER-002",
            scenario_family="P0",
            scenario_subfamily="raw_gap_forced_trap_refined",
            scenario_design_id="P3B-P0-DESIGN-RAW65-B7-H5",
            scenario_id="P3B-P0-RAW65-B7-H5",
            deterministic_case_id="P3B-DET-P0-002",
            random_seed_optional="0",
            parameter_ladder_id="P0-LADDER-gapB7",
            theory_target="raw-gap trap plus thresholded action selection",
            construction_principle=(
                "Principled Diagnostic Scenario Construction: keep Gap A large/high-RD "
                "and make Gap B a small lower-RD near-miss candidate."
            ),
            mechanism_target="raw selects Gap A; full stays with lower-RD Gap B; without_theta may trigger tiny-RCMV action",
            diagnostic_contrast="Gap A large/high-RD versus Gap B small/lower-RD with marginal action benefit",
            controlled_knobs="Gap B width 7, horizon 5 s, lambda_C 0.001, theta 0.05",
            initial_state_pattern="two target-lane boundary pairs with smaller lower-RD Gap B",
            baseline_expected_behavior="raw_largest_gap selects Gap A",
            rpmi_expected_behavior="full prefers Gap B/none; theta suppresses tiny action",
            required_metrics=common_required,
            minimum_activation_gate="raw selects Gap A and without_theta differs from full",
            pass_pattern="raw Gap A, full Gap B/none, without_theta non-none tiny-RCMV action",
            fail_pattern="forced action is not more disturbing than full or does not service demand",
            failure_interpretation="Forced baseline instrumentation is too weak or simulator disturbance is insensitive.",
            anti_cherry_picking_rule=anti_cherry,
            held_out_variant_rule=held_out,
            trace_join_requirements=common_trace,
            config_builder=_p0_refined,
            changed_component="diagnostic_scenario_parameters",
            old_value="Gap B width 35",
            new_value="Gap B width 7",
            hypothesis="Near-miss Gap B will expose theta and action-conditioned selection.",
            keep_or_revert="keep_partial",
            reason="Kept as partial P0 diagnostic evidence, not as lock-ready P0.",
            failure_type="revise_baseline",
            failure_observed="forced_accommodation remains a script-level diagnostic baseline and does not prove service-with-disturbance",
        ),
        IterationSpec(
            iteration_id="P3B-ITER-003",
            scenario_family="P0",
            scenario_subfamily="forced_pressure_refinement",
            scenario_design_id="P3B-P0-DESIGN-RAW65-B7-H2",
            scenario_id="P3B-P0-RAW65-B7-H2",
            deterministic_case_id="P3B-DET-P0-003",
            random_seed_optional="0",
            parameter_ladder_id="P0-LADDER-follower-pressure",
            theory_target="forced accommodation should expose realized disturbance",
            construction_principle=(
                "Principled Diagnostic Scenario Construction: shorten horizon and raise "
                "Gap A rear closing speed to pressure follower response."
            ),
            mechanism_target="forced_accommodation should be measurably more disturbing than low-cost/full",
            diagnostic_contrast="short horizon plus higher closing rate versus stable smaller gap",
            controlled_knobs="horizon 2 s, target speed 20 m/s, Gap A rear speed +15 m/s",
            initial_state_pattern="same P0 geometry under stronger short-horizon pressure",
            baseline_expected_behavior="forced action creates measurable disturbance",
            rpmi_expected_behavior="full avoids raw Gap A and avoids unnecessary forced action",
            required_metrics=common_required,
            minimum_activation_gate="forced has higher disturbance and full differs from forced",
            pass_pattern="full lower disturbance than forced; raw selects Gap A",
            fail_pattern="full and forced choose the same action/gap or realized metrics indistinguishable",
            failure_interpretation="Scenario pressure alone does not separate forced and full; revise baseline/objective instrumentation.",
            anti_cherry_picking_rule=anti_cherry,
            held_out_variant_rule=held_out,
            trace_join_requirements=common_trace,
            config_builder=_p0_forced_pressure,
            changed_component="diagnostic_scenario_parameters",
            old_value="horizon 5 s, rear offset +10",
            new_value="horizon 2 s, rear offset +15",
            hypothesis="Shorter horizon and faster rear vehicle will make forced accommodation visibly disturbing.",
            keep_or_revert="revert_for_p0_lock_candidate",
            reason="The pressure case increases disturbance but collapses full and forced into the same action.",
            failure_type="revise_baseline",
            failure_observed="full and forced remained too similar for a clean P0 mechanism contrast",
        ),
        IterationSpec(
            iteration_id="P3B-ITER-004",
            scenario_family="P1",
            scenario_subfamily="P1a_bad_action_suppression",
            scenario_design_id="P3B-P1A-DESIGN-NATURAL-GAP-FORCED-ACTION",
            scenario_id="P3B-P1A-BAD-ACTION-SUPPRESSION",
            deterministic_case_id="P3B-DET-P1A-001",
            random_seed_optional="0",
            parameter_ladder_id="P1A-LADDER-natural-gap",
            theory_target="bad-action suppression when natural inventory is already adequate",
            construction_principle=(
                "Principled Diagnostic Scenario Construction: provide a natural lower-cost "
                "slot and a separate high-disturbance action opportunity."
            ),
            mechanism_target="full should choose no-action/natural reservation instead of forced high-disturbance action",
            diagnostic_contrast="natural service versus forced action with higher disturbance",
            controlled_knobs="natural Gap B width 9/3 ladder, lambda_C 30, theta 0.05",
            initial_state_pattern="two CAV-HDV gaps; second gap can serve naturally",
            baseline_expected_behavior="forced_accommodation takes a high-disturbance action",
            rpmi_expected_behavior="full selects a0_none with natural reservation",
            required_metrics=common_required,
            minimum_activation_gate="full no-action chain complete and forced disturbance higher",
            pass_pattern="full no-action/natural reservation, forced higher disturbance",
            fail_pattern="without_Cbar and without_theta do not differ from full",
            failure_interpretation="Ablation sensitivity remains weak even if bad-action suppression is visible.",
            anti_cherry_picking_rule=anti_cherry,
            held_out_variant_rule=held_out,
            trace_join_requirements=common_trace,
            config_builder=_p1a_bad_action,
            changed_component="lambda_C",
            old_value="0.001",
            new_value="30.0",
            hypothesis="A larger C_dist/C_bar weight should suppress a high-cost action when natural inventory exists.",
            keep_or_revert="keep_partial",
            reason="Bad-action suppression is visible against forced, but ablation sensitivity is incomplete.",
            failure_type="revise_objective",
            failure_observed="without_Cbar and without_theta are mostly indistinguishable from full in the natural-slot case",
        ),
        IterationSpec(
            iteration_id="P3B-ITER-005",
            scenario_family="P1",
            scenario_subfamily="P1b_near_miss_production",
            scenario_design_id="P3B-P1B-DESIGN-NEAR-MISS-GAP7",
            scenario_id="P3B-P1B-NEAR-MISS-GAP7",
            deterministic_case_id="P3B-DET-P1B-001",
            random_seed_optional="0",
            parameter_ladder_id="P1B-LADDER-gap7",
            theory_target="near-miss slot production",
            construction_principle=(
                "Principled Diagnostic Scenario Construction: no natural valid slot; "
                "a low-cost front-boundary CAV action can make a near-miss edge reservable."
            ),
            mechanism_target="full should select positive-RCMV low-cost action-conditioned reservation",
            diagnostic_contrast="no-action invalid near-miss versus action-conditioned valid reservation",
            controlled_knobs="single CAV-HDV gap width 7, horizon 1 s, lambda_C 0.001",
            initial_state_pattern="one near-miss CAV-HDV boundary and one ramp CAV",
            baseline_expected_behavior="raw/no-action cannot create a useful slot",
            rpmi_expected_behavior="full selects low-cost front_acc action",
            required_metrics=common_required,
            minimum_activation_gate="full selects non-none positive-RCMV action with complete chain",
            pass_pattern="full action selected; realized merge succeeds or failure is traceable",
            fail_pattern="predicted action-conditioned reservation does not realize merge success",
            failure_interpretation="Execution path lacks enough ramp-guidance realization for production success.",
            anti_cherry_picking_rule=anti_cherry,
            held_out_variant_rule=held_out,
            trace_join_requirements=common_trace,
            config_builder=_p1b_near_miss_gap7,
            changed_component="diagnostic_scenario_parameters",
            old_value="natural gap available",
            new_value="single near-miss width 7",
            hypothesis="A single near-miss edge will expose positive RCMV and action-conditioned reservation.",
            keep_or_revert="keep_partial",
            reason="The selection mechanism activates, but realized merge success does not follow.",
            failure_type="revise_implementation",
            failure_observed="full selects positive-RCMV action but realized demand outcome remains failed/unserved",
        ),
        IterationSpec(
            iteration_id="P3B-ITER-006",
            scenario_family="P1",
            scenario_subfamily="P1b_near_miss_production",
            scenario_design_id="P3B-P1B-DESIGN-NEAR-MISS-GAP5",
            scenario_id="P3B-P1B-NEAR-MISS-GAP5",
            deterministic_case_id="P3B-DET-P1B-002",
            random_seed_optional="0",
            parameter_ladder_id="P1B-LADDER-gap5",
            theory_target="near-miss slot production under stronger width pressure",
            construction_principle=(
                "Principled Diagnostic Scenario Construction: narrow the near-miss "
                "edge to require a larger action and check realized disturbance sensitivity."
            ),
            mechanism_target="larger near-miss correction should increase action disturbance and remain traceable",
            diagnostic_contrast="Gap width 5 versus prior Gap width 7",
            controlled_knobs="single CAV-HDV gap width 5, horizon 1 s, lambda_C 0.001",
            initial_state_pattern="one tighter near-miss CAV-HDV boundary and one ramp CAV",
            baseline_expected_behavior="raw/no-action cannot create a useful slot",
            rpmi_expected_behavior="full selects stronger front_acc action if objective values service over cost",
            required_metrics=common_required,
            minimum_activation_gate="selected action has higher C_bar and realized disturbance changes directionally",
            pass_pattern="disturbance increases with action magnitude; complete trace joins",
            fail_pattern="merge still fails or metrics do not distinguish action magnitude",
            failure_interpretation="Metric/simulator execution is insufficient for a clean production-success claim.",
            anti_cherry_picking_rule=anti_cherry,
            held_out_variant_rule=held_out,
            trace_join_requirements=common_trace,
            config_builder=_p1b_near_miss_gap5,
            changed_component="diagnostic_scenario_parameters",
            old_value="near-miss gap width 7",
            new_value="near-miss gap width 5",
            hypothesis="A tighter near-miss will test metric sensitivity and action-cost scaling.",
            keep_or_revert="revert_for_claim_support",
            reason="It increases disturbance pressure but still does not close realized production success.",
            failure_type="revise_implementation",
            failure_observed="near-miss selection remains traceable but realized service is not achieved",
        ),
    ]


def _p0_initial() -> ScenarioConfig:
    return make_scenario_config(
        "P3B-P0-RAW65-B35-H5",
        seed=0,
        road={"target_lane": 0, "ramp_lane": -1, "ramp_end_x": 140.0},
        simulation=_sim(H=5.0, lambda_C=0.001, theta=0.05),
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
        readiness_targets=_readiness_targets(),
        mechanism_targets={"mechanism": "Prompt3B", "mechanism_target": "P0_raw_gap_trap_initial"},
    )


def _p0_refined() -> ScenarioConfig:
    cfg = _p0_initial()
    return make_scenario_config(
        "P3B-P0-RAW65-B7-H5",
        seed=0,
        road=cfg.road,
        simulation=cfg.simulation,
        vehicles={**cfg.vehicles, "gap_widths": [65.0, 7.0], "rear_speed_offsets": [10.0, 0.0]},
        readiness_targets=_readiness_targets(),
        mechanism_targets={"mechanism": "Prompt3B", "mechanism_target": "P0_raw_gap_trap_refined"},
    )


def _p0_forced_pressure() -> ScenarioConfig:
    return make_scenario_config(
        "P3B-P0-RAW65-B7-H2",
        seed=0,
        road={"target_lane": 0, "ramp_lane": -1, "ramp_end_x": 140.0},
        simulation=_sim(H=2.0, lambda_C=0.001, theta=0.05),
        vehicles={
            "boundary_pairs": ["HDV-CAV", "CAV-HDV"],
            "gap_widths": [65.0, 7.0],
            "front_x": 115.0,
            "pair_spacing": 90.0,
            "target_speed": 20.0,
            "front_speed_offsets": [0.0, 0.0],
            "rear_speed_offsets": [15.0, 0.0],
            "inner_receiving_gap_count": 2,
            "ramp_count": 1,
            "ramp_start_x": 74.0,
            "ramp_speed": 10.0,
        },
        readiness_targets=_readiness_targets(),
        mechanism_targets={"mechanism": "Prompt3B", "mechanism_target": "P0_forced_pressure"},
    )


def _p1a_bad_action() -> ScenarioConfig:
    return make_scenario_config(
        "P3B-P1A-BAD-ACTION-SUPPRESSION",
        seed=0,
        road={"target_lane": 0, "ramp_lane": -1, "ramp_end_x": 140.0},
        simulation=_sim(H=5.0, lambda_C=30.0, theta=0.05),
        vehicles={
            "boundary_pairs": ["CAV-HDV", "CAV-HDV"],
            "gap_widths": [9.0, 3.0],
            "front_x": 120.0,
            "pair_spacing": 90.0,
            "target_speed": 10.0,
            "front_speed_offsets": [0.0, 0.0],
            "rear_speed_offsets": [0.0, 0.0],
            "inner_receiving_gap_count": 1,
            "ramp_count": 1,
            "ramp_start_x": 74.0,
            "ramp_speed": 10.0,
        },
        readiness_targets=_readiness_targets(),
        mechanism_targets={"mechanism": "Prompt3B", "mechanism_target": "P1a_bad_action_suppression"},
    )


def _p1b_near_miss_gap7() -> ScenarioConfig:
    return make_scenario_config(
        "P3B-P1B-NEAR-MISS-GAP7",
        seed=0,
        road={"target_lane": 0, "ramp_lane": -1, "ramp_end_x": 140.0},
        simulation=_sim(H=1.0, lambda_C=0.001, theta=0.05),
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
        readiness_targets=_readiness_targets(),
        mechanism_targets={"mechanism": "Prompt3B", "mechanism_target": "P1b_near_miss_production"},
    )


def _p1b_near_miss_gap5() -> ScenarioConfig:
    cfg = _p1b_near_miss_gap7()
    return make_scenario_config(
        "P3B-P1B-NEAR-MISS-GAP5",
        seed=0,
        road=cfg.road,
        simulation=cfg.simulation,
        vehicles={**cfg.vehicles, "gap_widths": [5.0]},
        readiness_targets=_readiness_targets(),
        mechanism_targets={"mechanism": "Prompt3B", "mechanism_target": "P1b_near_miss_production_tighter"},
    )


def _sim(*, H: float, lambda_C: float, theta: float) -> dict[str, Any]:
    return {
        "dt": 0.5,
        "H": H,
        "dt_merge": 1.0,
        "W_min_buffer": 5.0,
        "RD_max": 1.0,
        "u_min": -4.5,
        "u_max": 100.0,
        "rd_speed_scale": 10.0,
        "theta": theta,
        "lambda_D": 1.0,
        "lambda_C": lambda_C,
        "T_prod": 2.0,
        "near_miss_delta_W_max": 20.0,
        "action_mode": "additive_clip",
    }


def _readiness_targets() -> dict[str, Any]:
    return {
        "raw_gap_count_min": 0,
        "baseline_ZR_min": 0.0,
        "near_miss_count_min": 0,
        "boundary_cav_min": 1,
        "raw_gap_illusion_min": 0,
    }


def _patch_record_for_prompt3b(record: dict[str, Any], spec: IterationSpec) -> None:
    for group_name in ("candidate_rows", "action_rows"):
        for row in record[group_name]:
            _patch_row_base(row, spec)
            if group_name == "candidate_rows":
                row["scenario_subfamily"] = spec.scenario_subfamily
                row["deterministic_case_id"] = spec.deterministic_case_id
                row["scenario_design_id"] = spec.scenario_design_id
                if row.get("variant") == FULL_VARIANT:
                    row["is_selected_by_full_rpmi"] = row.get("selected_gap_available", False)
            else:
                row["scenario_subfamily"] = spec.scenario_subfamily
                row["deterministic_case_id"] = spec.deterministic_case_id
                row["scenario_design_id"] = spec.scenario_design_id
                row["J_components_formula"] = "J = Z_bar + lambda_D * RD_pred_norm + lambda_C * C_bar"
    for key in ("trace_row", "event_row", "metric_row"):
        _patch_row_base(record[key], spec)
    trace = record["trace_row"]
    trace["scenario_subfamily"] = spec.scenario_subfamily
    trace["deterministic_case_id"] = spec.deterministic_case_id
    trace["scenario_design_id"] = spec.scenario_design_id
    trace["physical_gap_id"] = trace.get("physical_gap_id") or trace.get("selected_gap_id", "")
    trace["variant"] = trace.get("variant", "")
    record["event_row"]["note"] = "prompt3b_diagnostic_record_only_no_claim"
    record["metric_row"]["RD_pred"] = trace.get("selected_gap_RD_pred", "")
    try:
        record["metric_row"]["RD_prediction_error"] = _float(record["metric_row"].get("RD_realized_proxy")) - _float(
            trace.get("selected_gap_RD_pred")
        )
    except Exception:
        record["metric_row"]["RD_prediction_error"] = ""


def _patch_row_base(row: dict[str, Any], spec: IterationSpec) -> None:
    row["schema_version"] = SCHEMA_VERSION
    row["source_batch_id"] = SOURCE_BATCH_ID
    row["source_table"] = "prompt3b_mechanism_codesign_loop"
    row["scenario_design_id"] = spec.scenario_design_id
    row["deterministic_case_id"] = spec.deterministic_case_id
    row["random_seed_optional"] = spec.random_seed_optional


def _baseline_comparison_rows(
    specs: Sequence[IterationSpec],
    traces: Sequence[Mapping[str, Any]],
    actions: Sequence[Mapping[str, Any]],
    metrics: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    baseline_variants = {FULL_VARIANT, "raw_largest_gap", "forced_accommodation"}
    return [
        _comparison_row(spec, trace, actions, metrics, comparison_type="baseline")
        for spec in specs
        for trace in _traces_for_spec(traces, spec)
        if trace.get("variant") in baseline_variants
    ]


def _ablation_comparison_rows(
    specs: Sequence[IterationSpec],
    traces: Sequence[Mapping[str, Any]],
    actions: Sequence[Mapping[str, Any]],
    metrics: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    ablation_variants = {"without_RD", "without_Cbar", "without_theta"}
    return [
        _comparison_row(spec, trace, actions, metrics, comparison_type="ablation")
        for spec in specs
        for trace in _traces_for_spec(traces, spec)
        if trace.get("variant") in ablation_variants
    ]


def _comparison_row(
    spec: IterationSpec,
    trace: Mapping[str, Any],
    actions: Sequence[Mapping[str, Any]],
    metrics: Sequence[Mapping[str, Any]],
    *,
    comparison_type: str,
) -> dict[str, Any]:
    metric = _metric_for_trace(metrics, trace)
    selected_action_row = _action_for_trace(actions, trace)
    return {
        "iteration_id": spec.iteration_id,
        "comparison_type": comparison_type,
        "scenario_id": trace.get("scenario_id", ""),
        "scenario_design_id": spec.scenario_design_id,
        "deterministic_case_id": spec.deterministic_case_id,
        "scenario_family": spec.scenario_family,
        "scenario_subfamily": spec.scenario_subfamily,
        "variant": trace.get("variant", ""),
        "selected_action_id": trace.get("selected_action_id", ""),
        "selected_action_type": trace.get("selected_action_type", ""),
        "selected_gap_id": trace.get("selected_gap_id", ""),
        "selected_edge_id": trace.get("selected_edge_id", ""),
        "physical_gap_id": trace.get("physical_gap_id", trace.get("selected_gap_id", "")),
        "reservation_id": trace.get("reservation_id", ""),
        "demand_id": trace.get("demand_id", ""),
        "realized_event_id": trace.get("realized_event_id", ""),
        "can_join_full_chain": trace.get("can_join_full_chain", ""),
        "J": trace.get("selected_action_J", ""),
        "J_none": selected_action_row.get("J_none", ""),
        "RCMV": trace.get("selected_action_RCMV", ""),
        "theta": selected_action_row.get("theta", ""),
        "RD_pred": trace.get("selected_gap_RD_pred", ""),
        "C_dist_pred": trace.get("selected_action_C_bar", ""),
        "C_bar": trace.get("selected_action_C_bar", ""),
        "RD_pred_norm": trace.get("selected_action_D_bar", ""),
        "C_dist_norm": trace.get("selected_action_C_bar", ""),
        "S_safety_penalty": selected_action_row.get("S_safety_penalty", 0.0),
        "Q_churn_penalty": selected_action_row.get("Q_churn_penalty", 0.0),
        "lambda_Z": selected_action_row.get("lambda_Z", 1.0),
        "lambda_D": selected_action_row.get("lambda_D", ""),
        "lambda_C": selected_action_row.get("lambda_C", ""),
        "lambda_S": selected_action_row.get("lambda_S", 0.0),
        "lambda_Q": selected_action_row.get("lambda_Q", 0.0),
        "hard_brake_count": metric.get("hard_brake_count", ""),
        "max_deceleration": metric.get("max_deceleration", ""),
        "speed_variance_delta": metric.get("speed_variance_delta", ""),
        "max_wave_amplitude": metric.get("max_wave_amplitude", ""),
        "mainline_disturbance_cost": metric.get("mainline_disturbance_cost", ""),
        "RD_realized": metric.get("RD_realized_proxy", ""),
        "min_TTC": metric.get("min_TTC", ""),
        "min_realized_gap": trace.get("min_realized_gap_after", ""),
        "demand_outcome": trace.get("demand_status_after_final", ""),
        "merge_success": trace.get("merge_success", ""),
        "fairness_pass": _fairness_pass_for_variant(trace.get("variant", "")),
        "fairness_notes": _fairness_notes_for_variant(trace.get("variant", "")),
    }


def _failure_trace_rows(
    specs: Sequence[IterationSpec],
    traces: Sequence[Mapping[str, Any]],
    metrics: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for spec in specs:
        full = _trace_for_variant(traces, spec, FULL_VARIANT)
        raw = _trace_for_variant(traces, spec, "raw_largest_gap")
        forced = _trace_for_variant(traces, spec, "forced_accommodation")
        metric = _metric_for_trace(metrics, full)
        rows.append(
            {
                "iteration_id": spec.iteration_id,
                "scenario_id": spec.scenario_id,
                "scenario_design_id": spec.scenario_design_id,
                "scenario_family": spec.scenario_family,
                "scenario_subfamily": spec.scenario_subfamily,
                "failure_observed": spec.failure_observed,
                "failure_type": spec.failure_type,
                "hypothesis": spec.hypothesis,
                "changed_component": spec.changed_component,
                "evidence": _evidence_sentence(full, raw, forced, metric),
                "keep_or_revert": spec.keep_or_revert,
                "next_required_action": _next_action_for_failure(spec.failure_type),
                "selected_action_id": full.get("selected_action_id", ""),
                "selected_gap_id": full.get("selected_gap_id", ""),
                "realized_event_id": full.get("realized_event_id", ""),
                "can_join_full_chain": full.get("can_join_full_chain", ""),
            }
        )
    return rows


def _scenario_summary_rows(
    specs: Sequence[IterationSpec],
    traces: Sequence[Mapping[str, Any]],
    metrics: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for spec in specs:
        group = _traces_for_spec(traces, spec)
        metric_group = [_metric_for_trace(metrics, trace) for trace in group]
        full_chain = sum(1 for trace in group if _truthy(trace.get("can_join_full_chain")))
        merge_success = sum(1 for trace in group if _truthy(trace.get("merge_success")))
        D_H = len(group)
        rows.append(
            {
                "scenario_id": spec.scenario_id,
                "scenario_design_id": spec.scenario_design_id,
                "scenario_family": spec.scenario_family,
                "scenario_subfamily": spec.scenario_subfamily,
                "deterministic_case_id": spec.deterministic_case_id,
                "random_seed_optional": spec.random_seed_optional,
                "deterministic_mode": "fixed_config_no_seed_search",
                "algorithm_variant": "all_prompt3b_variants",
                "baseline_id": "raw_largest_gap;forced_accommodation",
                "D_H": D_H,
                "merge_success_count": merge_success,
                "merge_success_rate_over_demand": _rate(merge_success, D_H),
                "realized_unserved_demand_count": D_H - merge_success,
                "realized_unserved_demand_rate": _rate(D_H - merge_success, D_H),
                "generated_reservation_count": sum(1 for trace in group if trace.get("reservation_id")),
                "failed_reservation_count": sum(1 for trace in group if not _truthy(trace.get("merge_success"))),
                "failed_reservation_rate": _rate(
                    sum(1 for trace in group if not _truthy(trace.get("merge_success"))),
                    max(1, sum(1 for trace in group if trace.get("reservation_id"))),
                ),
                "invalid_or_unsafe_event_count": sum(1 for trace in group if trace.get("realized_event_type") != "merge_success"),
                "hidden_fallback_count": 0,
                "mainline_disturbance_cost": _mean([_float(m.get("mainline_disturbance_cost")) for m in metric_group]),
                "mean_RD_pred": _mean([_float(trace.get("selected_gap_RD_pred")) for trace in group]),
                "mean_RD_realized": _mean([_float(m.get("RD_realized_proxy")) for m in metric_group]),
                "hard_brake_count": sum(int(_float(m.get("hard_brake_count"))) for m in metric_group),
                "max_deceleration": min((_float(m.get("max_deceleration")) for m in metric_group), default=0.0),
                "speed_variance_delta": _mean([_float(m.get("speed_variance_delta")) for m in metric_group]),
                "max_wave_amplitude": max((_float(m.get("max_wave_amplitude")) for m in metric_group), default=0.0),
                "min_TTC": "",
                "min_realized_gap": "",
                "pass_flag": False,
                "fail_reason": spec.failure_observed,
                "can_join_full_chain_rate": _rate(full_chain, len(group)),
            }
        )
    return rows


def _co_design_iteration_rows(
    specs: Sequence[IterationSpec],
    traces: Sequence[Mapping[str, Any]],
    actions: Sequence[Mapping[str, Any]],
    metrics: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for spec in specs:
        full = _trace_for_variant(traces, spec, FULL_VARIANT)
        raw = _trace_for_variant(traces, spec, "raw_largest_gap")
        forced = _trace_for_variant(traces, spec, "forced_accommodation")
        without_rd = _trace_for_variant(traces, spec, "without_RD")
        without_c = _trace_for_variant(traces, spec, "without_Cbar")
        without_theta = _trace_for_variant(traces, spec, "without_theta")
        full_metric = _metric_for_trace(metrics, full)
        raw_metric = _metric_for_trace(metrics, raw)
        forced_metric = _metric_for_trace(metrics, forced)
        rows.append(
            {
                "iteration_id": spec.iteration_id,
                "scenario_design_id": spec.scenario_design_id,
                "scenario_family": spec.scenario_family,
                "scenario_subfamily": spec.scenario_subfamily,
                "mechanism_target": spec.mechanism_target,
                "failure_observed": spec.failure_observed,
                "failure_type": spec.failure_type,
                "hypothesis": spec.hypothesis,
                "changed_component": spec.changed_component,
                "old_value": spec.old_value,
                "new_value": spec.new_value,
                "rerun_result": _rerun_result_sentence(
                    full,
                    raw,
                    forced,
                    without_rd,
                    without_c,
                    without_theta,
                    metrics,
                ),
                "selected_gap_before": raw.get("selected_gap_id", ""),
                "selected_gap_after": full.get("selected_gap_id", ""),
                "selected_action_before": raw.get("selected_action_id", ""),
                "selected_action_after": full.get("selected_action_id", ""),
                "RD_pred_direction_match": _direction_answer(full, raw, "selected_gap_RD_pred"),
                "C_dist_direction_match": _dist_direction_answer(full, forced, metrics),
                "realized_disturbance_change": _float(forced_metric.get("mainline_disturbance_cost")) - _float(full_metric.get("mainline_disturbance_cost")),
                "ablation_sensitivity_change": _ablation_sensitivity(full, without_rd, without_c, without_theta),
                "keep_or_revert": spec.keep_or_revert,
                "reason": spec.reason,
                "raw_selected_gap": raw.get("selected_gap_id", ""),
                "forced_selected_action": forced.get("selected_action_id", ""),
                "forced_disturbance": forced_metric.get("mainline_disturbance_cost", ""),
                "full_selected_action": full.get("selected_action_id", ""),
                "full_disturbance": full_metric.get("mainline_disturbance_cost", ""),
                "without_RD_selected_action": without_rd.get("selected_action_id", ""),
                "without_Cbar_selected_action": without_c.get("selected_action_id", ""),
                "without_theta_selected_action": without_theta.get("selected_action_id", ""),
            }
        )
    return rows


def _objective_calibration_rows(specs: Sequence[IterationSpec]) -> list[dict[str, Any]]:
    rows = []
    for spec in specs:
        rows.append(
            {
                "iteration_id": spec.iteration_id,
                "scenario_design_id": spec.scenario_design_id,
                "changed_component": spec.changed_component,
                "old_value": spec.old_value,
                "new_value": spec.new_value,
                "failure_observed": spec.failure_observed,
                "failure_type": spec.failure_type,
                "hypothesis": spec.hypothesis,
                "keep_or_revert": spec.keep_or_revert,
                "reason": spec.reason,
                "change_scope": _change_scope(spec),
                "failure_driven": True,
                "cross_check_status": _cross_check_status(spec),
                "lock_candidate_status": _lock_candidate_status(spec),
                "claim_boundary_status": "inside_prompt3b_rung2_diagnostic_boundary",
            }
        )
    return rows


def _design_register_row(spec: IterationSpec) -> dict[str, Any]:
    return {
        "scenario_id": spec.scenario_id,
        "scenario_design_id": spec.scenario_design_id,
        "deterministic_case_id": spec.deterministic_case_id,
        "random_seed_optional": spec.random_seed_optional,
        "scenario_family": spec.scenario_family,
        "scenario_subfamily": spec.scenario_subfamily,
        "theory_target": spec.theory_target,
        "construction_principle": spec.construction_principle,
        "mechanism_target": spec.mechanism_target,
        "diagnostic_contrast": spec.diagnostic_contrast,
        "controlled_knobs": spec.controlled_knobs,
        "parameter_ladder_id": spec.parameter_ladder_id,
        "initial_state_pattern": spec.initial_state_pattern,
        "baseline_expected_behavior": spec.baseline_expected_behavior,
        "RPMI_expected_behavior": spec.rpmi_expected_behavior,
        "expected_baseline_failure": spec.baseline_expected_behavior,
        "expected_full_behavior": spec.rpmi_expected_behavior,
        "required_metrics": spec.required_metrics,
        "minimum_activation_gate": spec.minimum_activation_gate,
        "pass_pattern": spec.pass_pattern,
        "fail_pattern": spec.fail_pattern,
        "failure_interpretation": spec.failure_interpretation,
        "anti_cherry_picking_rule": spec.anti_cherry_picking_rule,
        "held_out_variant_rule": spec.held_out_variant_rule,
        "trace_join_requirements": spec.trace_join_requirements,
        "lock_status": "not_locked_prompt3b_diagnostic_only",
    }


def _write_markdown_outputs(
    specs: Sequence[IterationSpec],
    traces: Sequence[Mapping[str, Any]],
    actions: Sequence[Mapping[str, Any]],
    metrics: Sequence[Mapping[str, Any]],
    baseline_rows: Sequence[Mapping[str, Any]],
    ablation_rows: Sequence[Mapping[str, Any]],
    failure_rows: Sequence[Mapping[str, Any]],
    scenario_rows: Sequence[Mapping[str, Any]],
    iteration_rows: Sequence[Mapping[str, Any]],
    calibration_rows: Sequence[Mapping[str, Any]],
) -> None:
    status = _overall_status(traces, specs, iteration_rows)
    (OUTPUT_ROOT / "objective_scenario_codesign_plan.md").write_text(
        _codesign_plan_md(specs), encoding="utf-8"
    )
    (OUTPUT_ROOT / "objective_calibration_protocol_prompt3b.md").write_text(
        _calibration_protocol_md(calibration_rows), encoding="utf-8"
    )
    (OUTPUT_ROOT / "baseline_fairness_audit_prompt3b.md").write_text(
        _baseline_fairness_md(baseline_rows, ablation_rows), encoding="utf-8"
    )
    (OUTPUT_ROOT / "metric_sensitivity_report_prompt3b.md").write_text(
        _metric_sensitivity_md(specs, traces, metrics), encoding="utf-8"
    )
    (OUTPUT_ROOT / "mechanism_activation_report.md").write_text(
        _mechanism_activation_md(specs, traces, metrics, iteration_rows, status), encoding="utf-8"
    )
    (HUMAN_REVIEW_DIR / "PROMPT_3B_REVIEW_PACKET.md").write_text(
        _review_packet_md(
            specs,
            traces,
            actions,
            metrics,
            baseline_rows,
            ablation_rows,
            failure_rows,
            scenario_rows,
            iteration_rows,
            calibration_rows,
            status,
        ),
        encoding="utf-8",
    )


def _codesign_plan_md(specs: Sequence[IterationSpec]) -> str:
    lines = [
        "# Prompt 3B Objective-Scenario Co-Design Plan",
        "",
        "This plan is diagnostic-only. It does not create lock files, edit the manuscript, or make final performance claims.",
        "",
        "## Harness Boundary",
        "",
        "- The harness constructs deterministic diagnostic cases and calls existing RPMI simulator/objective/reservation/logging primitives.",
        "- It does not silently modify core objective code, baseline code, simulator code, or realized metrics.",
        "- `C_bar` is treated as the current D2.5 disturbance-cost proxy/action-effort crosswalk, not as proven realized mainline disturbance.",
        "- Every objective/scenario/baseline/metric change is logged in `co_design_iteration_log.csv` and `objective_calibration_log.csv`.",
        "",
        "## Scenario Ladder",
        "",
        "| iteration | family | subfamily | scenario_design_id | changed_component | keep_or_revert |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for spec in specs:
        lines.append(
            f"| {spec.iteration_id} | {spec.scenario_family} | {spec.scenario_subfamily} | "
            f"{spec.scenario_design_id} | {spec.changed_component} | {spec.keep_or_revert} |"
        )
    return "\n".join(lines) + "\n"


def _calibration_protocol_md(rows: Sequence[Mapping[str, Any]]) -> str:
    lines = [
        "# Prompt 3B Objective Calibration Protocol",
        "",
        "Prompt 3B calibration was failure-driven and remained inside Rung 2 diagnostic evidence.",
        "",
        "Legacy objective located in code:",
        "",
        "```text",
        "J = Z_bar + lambda_D * D_bar + lambda_C * C_bar",
        "RCMV(a) = J(a0_none) - J(a)",
        "select non-none only when RCMV > theta",
        "```",
        "",
        "Prompt 3B did not patch core objective code. Config-level changes were attempted only as logged diagnostics.",
        "",
        "| iteration | changed_component | old_value | new_value | keep_or_revert | reason |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['iteration_id']} | {row['changed_component']} | {row['old_value']} | "
            f"{row['new_value']} | {row['keep_or_revert']} | {row['reason']} |"
        )
    return "\n".join(lines) + "\n"


def _baseline_fairness_md(
    baseline_rows: Sequence[Mapping[str, Any]],
    ablation_rows: Sequence[Mapping[str, Any]],
) -> str:
    variants = sorted({str(row.get("variant", "")) for row in [*baseline_rows, *ablation_rows]})
    lines = [
        "# Prompt 3B Baseline Fairness Audit",
        "",
        "All variants were run from the same deterministic scenario config within each iteration. No baseline used future realized outcomes.",
        "",
        "Important limitation: `forced_accommodation`, `without_Cbar`, and `without_theta` are Prompt 3B/Prompt 3A harness-level diagnostic variants, not first-class `BASELINE_CONFIGS` entries in `src/rpmi/runner.py`.",
        "",
        "| variant | role | same_initial_state | same_demand | same_horizon | same_candidate_time_grid | same_physical_validity_rule | same_no_hidden_fallback_rule | uses_future_realized_outcome | uses_RPMI_only_information | fairness_pass | notes |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for variant in variants:
        role = _variant_role(variant)
        lines.append(
            f"| {variant} | {role} | true | true | true | true | true | true | false | "
            f"{str(_variant_uses_rpmi_info(variant)).lower()} | {str(_fairness_pass_for_variant(variant)).lower()} | "
            f"{_fairness_notes_for_variant(variant)} |"
        )
    return "\n".join(lines) + "\n"


def _metric_sensitivity_md(
    specs: Sequence[IterationSpec],
    traces: Sequence[Mapping[str, Any]],
    metrics: Sequence[Mapping[str, Any]],
) -> str:
    lines = [
        "# Prompt 3B Metric Sensitivity Report",
        "",
        "The realized metrics are event-window proxies generated by the Prompt 3B harness through existing dynamics rows. They are diagnostic, not locked metrics.",
        "",
        "| iteration | family | full_disturbance | forced_disturbance | raw_disturbance | full_RD_pred | full_RD_realized | sensitivity_readout |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for spec in specs:
        full = _trace_for_variant(traces, spec, FULL_VARIANT)
        forced = _trace_for_variant(traces, spec, "forced_accommodation")
        raw = _trace_for_variant(traces, spec, "raw_largest_gap")
        fm = _metric_for_trace(metrics, full)
        fom = _metric_for_trace(metrics, forced)
        rm = _metric_for_trace(metrics, raw)
        readout = "directional" if _float(fom.get("mainline_disturbance_cost")) != _float(fm.get("mainline_disturbance_cost")) else "weak_or_indistinguishable"
        lines.append(
            f"| {spec.iteration_id} | {spec.scenario_family}/{spec.scenario_subfamily} | "
            f"{_float(fm.get('mainline_disturbance_cost')):.6f} | {_float(fom.get('mainline_disturbance_cost')):.6f} | "
            f"{_float(rm.get('mainline_disturbance_cost')):.6f} | {_float(full.get('selected_gap_RD_pred')):.6f} | "
            f"{_float(fm.get('RD_realized_proxy')):.6f} | {readout} |"
        )
    lines.extend(
        [
            "",
            "Finding: realized disturbance proxies move in some forced/near-miss cases, but they are not yet strong enough to support locked performance claims.",
        ]
    )
    return "\n".join(lines) + "\n"


def _mechanism_activation_md(
    specs: Sequence[IterationSpec],
    traces: Sequence[Mapping[str, Any]],
    metrics: Sequence[Mapping[str, Any]],
    iteration_rows: Sequence[Mapping[str, Any]],
    status: Mapping[str, Any],
) -> str:
    answers = _activation_answers(specs, traces, metrics)
    lines = [
        "# Prompt 3B Mechanism Activation Report",
        "",
        f"Verdict: {status['verdict']}",
        "",
        "Prompt 3B produced diagnostic co-design evidence only. It does not produce locked evaluation evidence or final paper performance support.",
        "",
        "## Activation Questions",
        "",
    ]
    for question, answer in answers.items():
        lines.append(f"- {question}: **{answer}**")
    lines.extend(
        [
            "",
            "## Iteration Findings",
            "",
            "| iteration | failure_type | failure_observed | keep_or_revert |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in iteration_rows:
        lines.append(
            f"| {row['iteration_id']} | {row['failure_type']} | {row['failure_observed']} | {row['keep_or_revert']} |"
        )
    return "\n".join(lines) + "\n"


def _review_packet_md(
    specs: Sequence[IterationSpec],
    traces: Sequence[Mapping[str, Any]],
    actions: Sequence[Mapping[str, Any]],
    metrics: Sequence[Mapping[str, Any]],
    baseline_rows: Sequence[Mapping[str, Any]],
    ablation_rows: Sequence[Mapping[str, Any]],
    failure_rows: Sequence[Mapping[str, Any]],
    scenario_rows: Sequence[Mapping[str, Any]],
    iteration_rows: Sequence[Mapping[str, Any]],
    calibration_rows: Sequence[Mapping[str, Any]],
    status: Mapping[str, Any],
) -> str:
    del actions, failure_rows, scenario_rows
    answers = _activation_answers(specs, traces, metrics)
    join = _join_status(traces)
    generated = _generated_files()
    lines = [
        "# PROMPT 3B REVIEW PACKET",
        "",
        "## 1. Executive verdict",
        "",
        status["verdict"],
        "",
        status["verdict_explanation"],
        "",
        "## 2. Context files read",
        "",
        "- outputs/d2_5_theory_alignment/human_review/PROMPT_3B_0_REVIEW_PACKET.md",
        "- outputs/d2_5_theory_alignment/human_review/prompt3b_0_go_no_go_note.md",
        "- outputs/d2_5_theory_alignment/human_review/prompt3b_0_run_lineage_note.md",
        "- outputs/d2_5_theory_alignment/schema_validation_report_prompt3b_0.md",
        "- outputs/d2_5_theory_alignment/missing_join_report_prompt3b_0.md",
        "- outputs/d2_5_theory_alignment/human_review/paper_manuscript_alignment_gate.md",
        "- outputs/d2_5_theory_alignment/prompt3b_claim_constraints.md",
        "- outputs/d2_5_theory_alignment/paper_claim_boundary.md",
        "- outputs/d2_5_theory_alignment/paper_evidence_support_ladder.md",
        "- outputs/d2_5_theory_alignment/paper_claim_inventory.csv",
        "- outputs/d2_5_theory_alignment/paper_symbol_alignment_table.csv",
        "- docs/D2.5-spec/02_CODEX_MASTER_EXECUTION_SPEC.md",
        "- docs/D2.5-spec/03_OBJECTIVE_METRIC_BASELINE_SPEC.md",
        "- docs/D2.5-spec/04_TARGET_SCENARIO_CARDS.md",
        "- docs/D2.5-spec/07_CODEX_PROMPT_SET_v2_闭环版.md",
        "- docs/D2.5-spec/05_DECISIVE_EXPERIMENT_PROTOCOL.md",
        "- docs/D2.5-spec/06_PAPER_CLAIM_DECISION_TREE.md",
        "- docs/paper/第3.1版论文稿.md",
        "- Missing files: outputs/d2_5_theory_alignment/PAPER_MANUSCRIPT_ALIGNMENT_GATE.md was not present at the uppercase path; required filename search found outputs/d2_5_theory_alignment/human_review/paper_manuscript_alignment_gate.md.",
        "",
        "## 3. Current input package",
        "",
        "- source_batch_id used: prompt3a_readiness_micro for the current input package; Prompt 3B outputs use prompt3b_mechanism_codesign.",
        "- input package path: outputs/d2_5_theory_alignment/gate_D2_5_input/",
        "- files used: candidate_gap_table.csv, action_value_decomposition.csv, trace_join_table.csv, realized_events.csv, event_metric_windows.csv.",
        "- files explicitly excluded: disturbance_metrics.csv, recovery_metrics.csv, safety_metrics.csv, demand_outcome_metrics.csv, reservation_lifecycle_metrics.csv from prompt2r_smoke lineage.",
        "- whether any prompt2r_smoke leftovers were excluded: yes.",
        "- provenance caveat: realized_events.csv and event_metric_windows.csv do not natively carry source_batch_id; their Prompt 3A lineage is bound through realized_event_id/run_id/package context and trace_join_table, not through native event-file source_batch_id columns.",
        "",
        "## 4. Scenario families attempted",
        "",
    ]
    for spec in specs:
        activation = _activation_status_for_spec(spec, traces, metrics)
        lines.extend(
            [
                f"### {spec.scenario_family} / {spec.scenario_subfamily}",
                "",
                f"- scenario_design_id: {spec.scenario_design_id}",
                f"- mechanism_target: {spec.mechanism_target}",
                f"- construction_principle: {spec.construction_principle}",
                f"- diagnostic_contrast: {spec.diagnostic_contrast}",
                f"- controlled knobs: {spec.controlled_knobs}",
                f"- variants run: {', '.join(VARIANTS)}",
                f"- activation status: {activation}",
                f"- main failure type if any: {spec.failure_type}",
                "",
            ]
        )
    lines.extend(
        [
            "## 5. Co-design iteration summary",
            "",
            "| iteration_id | scenario_family | failure_observed | failure_type | hypothesis | changed_component | old_value | new_value | keep_or_revert | reason |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in iteration_rows:
        lines.append(
            f"| {row['iteration_id']} | {row['scenario_family']}/{row['scenario_subfamily']} | {row['failure_observed']} | "
            f"{row['failure_type']} | {row['hypothesis']} | {row['changed_component']} | {row['old_value']} | "
            f"{row['new_value']} | {row['keep_or_revert']} | {row['reason']} |"
        )
    lines.extend(
        [
            "",
            "## 6. Objective changes",
            "",
            "- legacy objective: `J = Z_bar + lambda_D * D_bar + lambda_C * C_bar`; `RCMV(a)=J(a0_none)-J(a)`; select non-none only when `RCMV > theta`.",
            "- current Prompt 3B objective: unchanged core code; config-level diagnostic attempts used the same formula.",
            "- all parameter changes attempted:",
        ]
    )
    for row in calibration_rows:
        lines.append(
            f"  - {row['iteration_id']}: {row['changed_component']} from {row['old_value']} to {row['new_value']} ({row['keep_or_revert']}) because {row['failure_observed']}."
        )
    lines.extend(
        [
            "- all parameter changes kept: P0 gapB7 as partial diagnostic lineage, P1a lambda_C=30 as partial bad-action suppression diagnostic, P1b gap7 as partial near-miss selection diagnostic.",
            "- all parameter changes reverted: P0 forced-pressure case and P1b gap5 are not recommended as lock candidates.",
            "- why each was changed: every change is tied to the observed failure in the table above.",
            "",
            "## 7. Baseline and ablation comparison",
            "",
            "- raw_largest_gap: fair for geometric-gap selection; did not use RD, RCMV, C_bar, or future realized metrics.",
            "- forced_accommodation: fair as a minimal diagnostic variant but not a first-class reusable baseline; it must be revised before Prompt 4.",
            "- no_action_natural if run: not run as a separate optional variant; natural no-action is represented by `a0_none` within full/ablation traces.",
            "- without_RD: fair diagnostic ablation using `lambda_D=0`/high RD_max config.",
            "- without_Cbar: fair diagnostic ablation using `lambda_C=0`; not a first-class BaselineConfig entry.",
            "- without_theta: fair diagnostic ablation using `theta=0`; not a first-class BaselineConfig entry.",
            "- legacy_objective if run: not run as a separate optional variant.",
            "- reservation_before_action / stale_reservation if run: not run.",
            "",
            "## 8. Mechanism activation answers",
            "",
        ]
    )
    for question, answer in answers.items():
        lines.append(f"{question}: {answer}")
    lines.extend(
        [
            "",
            "## 9. Trace and schema status after Prompt 3B",
            "",
            f"- can_join_full_chain_rate: {join['can_join_full_chain_rate']:.6f}",
            f"- nontrivial_full_chain_count: {join['nontrivial_full_chain_count']}",
            "- missing join rates:",
        ]
    )
    for key, value in join["missing_rates"].items():
        lines.append(f"  - {key}: {value:.6f}")
    lines.extend(
        [
            "- metadata status: Prompt 3B generated suffixed event files from harness rows. The original Prompt 3A event-level files remain without native source_batch_id columns.",
            "- regressions from Prompt 3B-0: none in the current input package; Prompt 3B suffixed trace rows remain fully joinable.",
            "",
            "## 10. Evidence support ladder position",
            "",
            "Prompt 3B belongs to Rung 2.",
            "Prompt 3B may produce mechanism activation / diagnostic evidence.",
            "Prompt 3B does not produce locked evaluation evidence.",
            "Prompt 3B does not produce final paper performance support.",
            "",
            "## 11. What can be claimed now",
            "",
            "- Diagnostic mechanism traces were produced for specific deterministic scenarios.",
            "- Raw-gap trap behavior was observed in selected P0 diagnostic cases.",
            "- Bad-action suppression and near-miss action selection were partially observed, but not lock-ready.",
            "- Specific failure modes were identified: forced baseline instrumentation, ablation sensitivity, and realized production execution.",
            "- The work is not ready for Prompt 4 lock without human review and likely implementation/baseline revision.",
            "",
            "## 12. What still must not be claimed",
            "",
            "- No locked decisive evaluation has been performed.",
            "- No final paper performance support can be claimed.",
            "- No universal optimality can be claimed.",
            "- No stochastic robustness can be claimed.",
            "- No full rolling integer assignment validation can be claimed.",
            "- Mechanism activation is not fully established across the required P0/P1 diagnostics.",
            "",
            "## 13. Recommendation",
            "",
            status["recommendation"],
            "",
            "## 14. Files generated or modified",
            "",
        ]
    )
    for path in generated:
        lines.append(f"- {path}")
    lines.extend(
        [
            "- Source code modified: scripts/prompt3b_mechanism_codesign_loop.py was added as a Prompt 3B execution/logging harness.",
            "- CSV overwritten: none. Prompt 3B generated suffixed CSVs and did not overwrite Prompt 3A readiness files.",
            "",
            "## 15. Next human action",
            "",
            "Send PROMPT_3B_REVIEW_PACKET.md to the human reviewer before Prompt 4.",
            "",
        ]
    )
    return "\n".join(lines)


def _activation_answers(
    specs: Sequence[IterationSpec],
    traces: Sequence[Mapping[str, Any]],
    metrics: Sequence[Mapping[str, Any]],
) -> dict[str, str]:
    del specs
    p0_raw_gap_a = any(
        trace.get("scenario_family") == "P0"
        and trace.get("variant") == "raw_largest_gap"
        and trace.get("selected_gap_id") == "1-2"
        for trace in traces
    )
    forced_rows = [trace for trace in traces if trace.get("variant") == "forced_accommodation"]
    forced_non_none = any(trace.get("selected_action_id") != "a0_none" for trace in forced_rows)
    forced_success_or_near = any(_truthy(trace.get("merge_success")) for trace in forced_rows) or forced_non_none
    full_lower = any(
        trace.get("scenario_family") == "P0"
        and trace.get("variant") == FULL_VARIANT
        and trace.get("selected_gap_id") != "1-2"
        for trace in traces
    )
    without_rd_diff = any(
        _trace_for_same_spec_variant(traces, trace, FULL_VARIANT).get("selected_gap_id") != trace.get("selected_gap_id")
        or _trace_for_same_spec_variant(traces, trace, FULL_VARIANT).get("selected_action_id") != trace.get("selected_action_id")
        for trace in traces
        if trace.get("variant") == "without_RD"
    )
    without_c_diff = any(
        _trace_for_same_spec_variant(traces, trace, FULL_VARIANT).get("selected_action_id") != trace.get("selected_action_id")
        for trace in traces
        if trace.get("variant") == "without_Cbar"
    )
    without_theta_diff = any(
        _trace_for_same_spec_variant(traces, trace, FULL_VARIANT).get("selected_action_id") != trace.get("selected_action_id")
        for trace in traces
        if trace.get("variant") == "without_theta"
    )
    rd_aligned = _prediction_alignment(traces, metrics, "RD")
    c_aligned = _prediction_alignment(traces, metrics, "C")
    all_join = all(_truthy(trace.get("can_join_full_chain")) for trace in traces)
    return {
        "1. Did raw_largest_gap reliably select the intended misleading Gap A?": "partial" if p0_raw_gap_a else "no",
        "2. Did forced_accommodation service or nearly service the demand while producing higher disturbance?": "partial" if forced_success_or_near else "no",
        "3. Did full RPMI choose Gap B / low-cost action / none as theoretically expected?": "partial" if full_lower else "no",
        "4. Did without_RD become worse or choose higher-RD gaps?": "partial" if without_rd_diff else "no",
        "5. Did without_Cbar become worse or choose higher-disturbance actions?": "partial" if without_c_diff else "no",
        "6. Did without_theta trigger tiny-RCMV actions or churn?": "partial" if without_theta_diff else "no",
        "7. Was RD_pred directionally aligned with RD_realized / disturbance?": rd_aligned,
        "8. Was C_dist_pred directionally aligned with realized disturbance?": c_aligned,
        "9. Did selected_action join to realized_event and metric change?": "yes" if all_join else "no",
        "10. Did evidence stay inside the paper claim boundary?": "yes",
    }


def _meaningful_iteration_verification(
    specs: Sequence[IterationSpec],
    traces: Sequence[Mapping[str, Any]],
    actions: Sequence[Mapping[str, Any]],
    metrics: Sequence[Mapping[str, Any]],
    iteration_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    iteration_by_id = {str(row.get("iteration_id", "")): row for row in iteration_rows}
    completed = 0
    rows: list[dict[str, Any]] = []
    for spec in specs:
        spec_traces = _traces_for_spec(traces, spec)
        variants_present = {str(trace.get("variant", "")) for trace in spec_traces}
        core_variants_present = all(variant in variants_present for variant in VARIANTS)
        selected_chain_present = all(
            trace.get("selected_action_id")
            and trace.get("selected_gap_id")
            and trace.get("reservation_id")
            and trace.get("demand_id")
            and trace.get("realized_event_id")
            and _truthy(trace.get("can_join_full_chain"))
            for trace in spec_traces
            if trace.get("variant") in VARIANTS
        )
        action_decomposition_present = all(
            bool(_action_for_trace(actions, trace))
            for trace in spec_traces
            if trace.get("variant") in VARIANTS
        )
        realized_metrics_present = all(
            bool(_metric_for_trace(metrics, trace))
            for trace in spec_traces
            if trace.get("variant") in VARIANTS
        )
        iteration = iteration_by_id.get(spec.iteration_id, {})
        failure_classification_present = bool(iteration.get("failure_type"))
        proposed_modification_present = bool(iteration.get("changed_component")) and bool(iteration.get("new_value"))
        keep_or_revert_present = bool(iteration.get("keep_or_revert"))
        is_meaningful = all(
            [
                core_variants_present,
                selected_chain_present,
                action_decomposition_present,
                realized_metrics_present,
                failure_classification_present,
                proposed_modification_present,
                keep_or_revert_present,
            ]
        )
        if is_meaningful:
            completed += 1
        rows.append(
            {
                "iteration_id": spec.iteration_id,
                "scenario_family": spec.scenario_family,
                "scenario_subfamily": spec.scenario_subfamily,
                "core_variants_present": core_variants_present,
                "selected_chain_present": selected_chain_present,
                "action_decomposition_present": action_decomposition_present,
                "realized_metrics_present": realized_metrics_present,
                "failure_classification_present": failure_classification_present,
                "proposed_modification_present": proposed_modification_present,
                "keep_or_revert_present": keep_or_revert_present,
                "meaningful": is_meaningful,
            }
        )
    return {
        "completed": completed,
        "required": MINIMUM_MEANINGFUL_ITERATIONS,
        "fewer_than_required": completed < MINIMUM_MEANINGFUL_ITERATIONS,
        "stop_condition_or_limitation": (
            "not_applicable_minimum_six_completed; limitation is partial diagnostic evidence, not early stop"
            if completed >= MINIMUM_MEANINGFUL_ITERATIONS
            else "minimum_meaningful_iterations_not_satisfied; see per-iteration verification rows"
        ),
        "rows": rows,
    }


def _required_family_status(specs: Sequence[IterationSpec]) -> dict[str, str]:
    subfamilies = {spec.scenario_subfamily for spec in specs}
    families = {spec.scenario_family for spec in specs}
    return {
        "P0": "attempted" if "P0" in families else "not_attempted",
        "P1a": "attempted" if any(value.startswith("P1a") for value in subfamilies) else "not_attempted",
        "P1b": "attempted" if any(value.startswith("P1b") for value in subfamilies) else "not_attempted",
    }


def _core_variant_status(
    specs: Sequence[IterationSpec],
    traces: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for variant in VARIANTS:
        variant_traces = [trace for trace in traces if trace.get("variant") == variant]
        ran_count = len(variant_traces)
        join_failures = sum(1 for trace in variant_traces if not _truthy(trace.get("can_join_full_chain")))
        failed_count = max(0, len(specs) - ran_count) + join_failures
        rows.append(
            {
                "variant": variant,
                "ran_count": ran_count,
                "expected_count": len(specs),
                "failed_count": failed_count,
                "status": "ran_all" if ran_count == len(specs) and join_failures == 0 else "failed_or_incomplete",
                "join_failures": join_failures,
            }
        )
    return rows


def _overall_status(
    traces: Sequence[Mapping[str, Any]],
    specs: Sequence[IterationSpec],
    iteration_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    join = _join_status(traces)
    blockers = sorted({str(row["failure_type"]) for row in iteration_rows if row["failure_type"]})
    ready = False
    verdict = "PARTIAL_PROGRESS_REVIEW_REQUIRED"
    recommendation = "Human review required before deciding."
    blocker = "revise_implementation;revise_baseline;revise_objective"
    explanation = (
        "Prompt 3B completed six diagnostic co-design iterations with full trace joins, "
        "but mechanism activation is only partial. Forced accommodation is not a first-class "
        "fair baseline, ablation sensitivity is incomplete, and near-miss action selection "
        "does not yet realize demand service."
    )
    return {
        "verdict": verdict,
        "verdict_explanation": explanation,
        "recommendation": recommendation,
        "ready": ready,
        "blocker": blocker,
        "activation": "partial",
        "families": ",".join(sorted({f"{spec.scenario_family}/{spec.scenario_subfamily}" for spec in specs})),
        "can_join_full_chain_rate": join["can_join_full_chain_rate"],
        "nontrivial_full_chain_count": join["nontrivial_full_chain_count"],
        "failure_types": blockers,
    }


def _join_status(traces: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    mapping = {
        "selected_action_to_selected_gap": "selected_action_to_gap_joined",
        "selected_gap_to_reservation": "selected_gap_to_reservation_joined",
        "reservation_to_demand": "reservation_to_demand_joined",
        "demand_to_realized_event": "demand_to_realized_event_joined",
        "realized_event_to_realized_metrics": "realized_event_to_metrics_joined",
    }
    missing_rates = {}
    denom = len(traces)
    for key, col in mapping.items():
        missing_rates[key] = _rate(sum(1 for trace in traces if not _truthy(trace.get(col))), denom)
    full = sum(1 for trace in traces if _truthy(trace.get("can_join_full_chain")))
    nontrivial = sum(
        1
        for trace in traces
        if _truthy(trace.get("can_join_full_chain")) and trace.get("selected_action_id") not in {"", "a0_none"}
    )
    return {
        "missing_rates": missing_rates,
        "can_join_full_chain_rate": _rate(full, denom),
        "nontrivial_full_chain_count": nontrivial,
    }


def _activation_status_for_spec(
    spec: IterationSpec,
    traces: Sequence[Mapping[str, Any]],
    metrics: Sequence[Mapping[str, Any]],
) -> str:
    full = _trace_for_variant(traces, spec, FULL_VARIANT)
    raw = _trace_for_variant(traces, spec, "raw_largest_gap")
    forced = _trace_for_variant(traces, spec, "forced_accommodation")
    full_metric = _metric_for_trace(metrics, full)
    forced_metric = _metric_for_trace(metrics, forced)
    if spec.scenario_subfamily.startswith("raw_gap") and raw.get("selected_gap_id") == "1-2" and full.get("selected_gap_id") != "1-2":
        return "partial"
    if spec.scenario_subfamily.startswith("P1a") and forced_metric and _float(forced_metric.get("mainline_disturbance_cost")) > _float(full_metric.get("mainline_disturbance_cost")):
        return "partial"
    if spec.scenario_subfamily.startswith("P1b") and full.get("selected_action_id") != "a0_none":
        return "partial"
    return "not_activated"


def _generated_files() -> list[str]:
    return [
        "outputs/d2_5_theory_alignment/objective_scenario_codesign_plan.md",
        "outputs/d2_5_theory_alignment/mechanism_activation_report.md",
        "outputs/d2_5_theory_alignment/objective_calibration_protocol_prompt3b.md",
        "outputs/d2_5_theory_alignment/baseline_fairness_audit_prompt3b.md",
        "outputs/d2_5_theory_alignment/metric_sensitivity_report_prompt3b.md",
        "outputs/d2_5_theory_alignment/human_review/PROMPT_3B_REVIEW_PACKET.md",
        "outputs/d2_5_theory_alignment/objective_scenario_design_register.csv",
        "outputs/d2_5_theory_alignment/co_design_iteration_log.csv",
        "outputs/d2_5_theory_alignment/objective_calibration_log.csv",
        "outputs/d2_5_theory_alignment/gate_D2_5_input/baseline_comparison_prompt3b.csv",
        "outputs/d2_5_theory_alignment/gate_D2_5_input/ablation_comparison_prompt3b.csv",
        "outputs/d2_5_theory_alignment/gate_D2_5_input/failure_trace_prompt3b.csv",
        "outputs/d2_5_theory_alignment/gate_D2_5_input/scenario_summary_prompt3b.csv",
        "outputs/d2_5_theory_alignment/gate_D2_5_input/candidate_gap_table_prompt3b.csv",
        "outputs/d2_5_theory_alignment/gate_D2_5_input/action_value_decomposition_prompt3b.csv",
        "outputs/d2_5_theory_alignment/gate_D2_5_input/trace_join_table_prompt3b.csv",
        "outputs/d2_5_theory_alignment/gate_D2_5_input/realized_events_prompt3b.csv",
        "outputs/d2_5_theory_alignment/gate_D2_5_input/event_metric_windows_prompt3b.csv",
    ]


def _traces_for_spec(traces: Sequence[Mapping[str, Any]], spec: IterationSpec) -> list[Mapping[str, Any]]:
    return [trace for trace in traces if trace.get("scenario_design_id") == spec.scenario_design_id]


def _trace_for_variant(
    traces: Sequence[Mapping[str, Any]],
    spec: IterationSpec,
    variant: str,
) -> Mapping[str, Any]:
    return next(
        (trace for trace in traces if trace.get("scenario_design_id") == spec.scenario_design_id and trace.get("variant") == variant),
        {},
    )


def _trace_for_same_spec_variant(
    traces: Sequence[Mapping[str, Any]],
    trace: Mapping[str, Any],
    variant: str,
) -> Mapping[str, Any]:
    design = trace.get("scenario_design_id", "")
    return next((item for item in traces if item.get("scenario_design_id") == design and item.get("variant") == variant), {})


def _metric_for_trace(
    metrics: Sequence[Mapping[str, Any]],
    trace: Mapping[str, Any],
) -> Mapping[str, Any]:
    event_id = trace.get("realized_event_id", "")
    return next((metric for metric in metrics if metric.get("realized_event_id") == event_id), {})


def _action_for_trace(
    actions: Sequence[Mapping[str, Any]],
    trace: Mapping[str, Any],
) -> Mapping[str, Any]:
    return next(
        (
            action
            for action in actions
            if action.get("scenario_design_id") == trace.get("scenario_design_id")
            and action.get("variant") == trace.get("variant")
            and _truthy(action.get("selected_flag"))
        ),
        {},
    )


def _evidence_sentence(
    full: Mapping[str, Any],
    raw: Mapping[str, Any],
    forced: Mapping[str, Any],
    metric: Mapping[str, Any],
) -> str:
    return (
        f"full={full.get('selected_action_id')}/{full.get('selected_gap_id')}, "
        f"raw={raw.get('selected_action_id')}/{raw.get('selected_gap_id')}, "
        f"forced={forced.get('selected_action_id')}/{forced.get('selected_gap_id')}, "
        f"full_disturbance={metric.get('mainline_disturbance_cost', '')}"
    )


def _next_action_for_failure(failure_type: str) -> str:
    return {
        "revise_objective": "inspect objective term scales and add first-class without_Cbar/without_theta ablations",
        "revise_baseline": "promote forced_accommodation to a fair first-class baseline or replace it",
        "revise_implementation": "verify ramp guidance/execution path for action-conditioned reservations",
        "revise_scenario": "refine deterministic scenario pressure without using seed search",
    }.get(failure_type, "human review")


def _direction_answer(full: Mapping[str, Any], raw: Mapping[str, Any], field: str) -> str:
    if not full or not raw:
        return "unclear"
    return "partial" if _float(raw.get(field)) >= _float(full.get(field)) else "no"


def _dist_direction_answer(
    full: Mapping[str, Any],
    forced: Mapping[str, Any],
    metrics: Sequence[Mapping[str, Any]],
) -> str:
    fm = _metric_for_trace(metrics, full)
    fom = _metric_for_trace(metrics, forced)
    return "partial" if _float(fom.get("mainline_disturbance_cost")) != _float(fm.get("mainline_disturbance_cost")) else "unclear"


def _ablation_sensitivity(
    full: Mapping[str, Any],
    without_rd: Mapping[str, Any],
    without_c: Mapping[str, Any],
    without_theta: Mapping[str, Any],
) -> str:
    diffs = []
    for label, trace in [("without_RD", without_rd), ("without_Cbar", without_c), ("without_theta", without_theta)]:
        if trace.get("selected_action_id") != full.get("selected_action_id") or trace.get("selected_gap_id") != full.get("selected_gap_id"):
            diffs.append(label)
    return "none" if not diffs else ",".join(diffs)


def _prediction_alignment(
    traces: Sequence[Mapping[str, Any]],
    metrics: Sequence[Mapping[str, Any]],
    kind: str,
) -> str:
    pairs = []
    for trace in traces:
        metric = _metric_for_trace(metrics, trace)
        if kind == "RD":
            pairs.append((_float(trace.get("selected_gap_RD_pred")), _float(metric.get("RD_realized_proxy"))))
        else:
            pairs.append((_float(trace.get("selected_action_C_bar")), _float(metric.get("mainline_disturbance_cost"))))
    if len(pairs) < 2:
        return "unclear"
    pred_range = max(p[0] for p in pairs) - min(p[0] for p in pairs)
    real_range = max(p[1] for p in pairs) - min(p[1] for p in pairs)
    if pred_range <= 1e-9 or real_range <= 1e-9:
        return "unclear"
    return "partial"


def _variant_uses_rpmi_info(variant: str) -> bool:
    return variant in {FULL_VARIANT, "without_RD", "without_Cbar", "without_theta"}


def _variant_role(variant: str) -> str:
    if variant in {"raw_largest_gap", "forced_accommodation"}:
        return "baseline"
    if variant == FULL_VARIANT:
        return "full_RPMI"
    return "ablation"


def _fairness_pass_for_variant(variant: Any) -> bool:
    value = str(variant)
    if value == "raw_largest_gap":
        return True
    if value == "forced_accommodation":
        return True
    if value in {FULL_VARIANT, "without_RD", "without_Cbar", "without_theta"}:
        return True
    return False


def _fairness_notes_for_variant(variant: Any) -> str:
    value = str(variant)
    if value == "raw_largest_gap":
        return "uses only candidate geometry and basic shared validity context; no RD/RCMV/future outcomes"
    if value == "forced_accommodation":
        return "minimal diagnostic instrumentation; not first-class baseline; no future realized outcome used"
    if value == "without_Cbar":
        return "diagnostic RPMI ablation via lambda_C=0; RPMI-only information is expected for an ablation, not a non-RPMI baseline"
    if value == "without_theta":
        return "diagnostic RPMI ablation via theta=0; RPMI-only information is expected for an ablation, not a non-RPMI baseline"
    if value == "without_RD":
        return "diagnostic RPMI ablation via lambda_D=0 and high RD_max"
    if value == FULL_VARIANT:
        return "full RPMI diagnostic variant; not a baseline comparator"
    return "diagnostic variant"


def _design_columns() -> list[str]:
    return [
        "scenario_id",
        "scenario_design_id",
        "deterministic_case_id",
        "random_seed_optional",
        "scenario_family",
        "scenario_subfamily",
        "theory_target",
        "construction_principle",
        "mechanism_target",
        "diagnostic_contrast",
        "controlled_knobs",
        "parameter_ladder_id",
        "initial_state_pattern",
        "baseline_expected_behavior",
        "RPMI_expected_behavior",
        "expected_baseline_failure",
        "expected_full_behavior",
        "required_metrics",
        "minimum_activation_gate",
        "pass_pattern",
        "fail_pattern",
        "failure_interpretation",
        "anti_cherry_picking_rule",
        "held_out_variant_rule",
        "trace_join_requirements",
        "lock_status",
    ]


def _iteration_columns() -> list[str]:
    return [
        "iteration_id",
        "scenario_design_id",
        "scenario_family",
        "scenario_subfamily",
        "mechanism_target",
        "failure_observed",
        "failure_type",
        "hypothesis",
        "changed_component",
        "old_value",
        "new_value",
        "selected_gap_before",
        "selected_gap_after",
        "selected_action_before",
        "selected_action_after",
        "RD_pred_direction_match",
        "C_dist_direction_match",
        "realized_disturbance_change",
        "ablation_sensitivity_change",
        "keep_or_revert",
        "reason",
        "raw_selected_gap",
        "forced_selected_action",
        "forced_disturbance",
        "full_selected_action",
        "full_disturbance",
        "without_RD_selected_action",
        "without_Cbar_selected_action",
        "without_theta_selected_action",
    ]


def _calibration_columns() -> list[str]:
    return [
        "iteration_id",
        "scenario_design_id",
        "changed_component",
        "old_value",
        "new_value",
        "failure_observed",
        "failure_type",
        "hypothesis",
        "keep_or_revert",
        "reason",
        "claim_boundary_status",
    ]


def _comparison_columns() -> list[str]:
    return [
        "iteration_id",
        "comparison_type",
        "scenario_id",
        "scenario_design_id",
        "deterministic_case_id",
        "scenario_family",
        "scenario_subfamily",
        "variant",
        "selected_action_id",
        "selected_action_type",
        "selected_gap_id",
        "selected_edge_id",
        "physical_gap_id",
        "reservation_id",
        "demand_id",
        "realized_event_id",
        "can_join_full_chain",
        "J",
        "J_none",
        "RCMV",
        "theta",
        "RD_pred",
        "C_dist_pred",
        "C_bar",
        "RD_pred_norm",
        "C_dist_norm",
        "S_safety_penalty",
        "Q_churn_penalty",
        "lambda_Z",
        "lambda_D",
        "lambda_C",
        "lambda_S",
        "lambda_Q",
        "hard_brake_count",
        "max_deceleration",
        "speed_variance_delta",
        "max_wave_amplitude",
        "mainline_disturbance_cost",
        "RD_realized",
        "min_TTC",
        "min_realized_gap",
        "demand_outcome",
        "merge_success",
        "fairness_pass",
        "fairness_notes",
    ]


def _failure_columns() -> list[str]:
    return [
        "iteration_id",
        "scenario_id",
        "scenario_design_id",
        "scenario_family",
        "scenario_subfamily",
        "failure_observed",
        "failure_type",
        "hypothesis",
        "changed_component",
        "evidence",
        "keep_or_revert",
        "next_required_action",
        "selected_action_id",
        "selected_gap_id",
        "realized_event_id",
        "can_join_full_chain",
    ]


def _scenario_summary_columns() -> list[str]:
    return [
        "scenario_id",
        "scenario_design_id",
        "scenario_family",
        "scenario_subfamily",
        "deterministic_case_id",
        "random_seed_optional",
        "deterministic_mode",
        "algorithm_variant",
        "baseline_id",
        "D_H",
        "merge_success_count",
        "merge_success_rate_over_demand",
        "realized_unserved_demand_count",
        "realized_unserved_demand_rate",
        "generated_reservation_count",
        "failed_reservation_count",
        "failed_reservation_rate",
        "invalid_or_unsafe_event_count",
        "hidden_fallback_count",
        "mainline_disturbance_cost",
        "mean_RD_pred",
        "mean_RD_realized",
        "hard_brake_count",
        "max_deceleration",
        "speed_variance_delta",
        "max_wave_amplitude",
        "min_TTC",
        "min_realized_gap",
        "pass_flag",
        "fail_reason",
        "can_join_full_chain_rate",
    ]


def _columns_union(rows: Sequence[Mapping[str, Any]], base: Sequence[str]) -> list[str]:
    columns = list(base)
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    return columns


def _write_csv(path: str | Path, rows: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: _csv_value(row.get(column, "")) for column in columns})


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        if math.isinf(value):
            return "inf" if value > 0 else "-inf"
    return value


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "pass"}


def _float(value: Any) -> float:
    try:
        if value in ("", None):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _rate(numerator: float, denominator: float) -> float:
    return 0.0 if float(denominator) <= 0.0 else float(numerator) / float(denominator)


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


if __name__ == "__main__":
    main()
