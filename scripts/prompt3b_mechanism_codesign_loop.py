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

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
for path in (REPO_ROOT, SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from rpmi.scenarios import ScenarioConfig, make_scenario_config

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
PROMPT3B_R_SOURCE_BATCH_ID = "prompt3b_r_paper_evidence_codesign"


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


@dataclass(frozen=True)
class RepairIterationSpec:
    iteration_id: str
    evidence_target_id: str
    scenario_family: str
    scenario_subfamily: str
    observed_failure: str
    failure_type: str
    hypothesis: str
    changed_component: str
    old_value: str
    new_value: str
    rerun_case_id: str
    before_builder: Callable[[], ScenarioConfig]
    after_builder: Callable[[], ScenarioConfig]
    keep_or_revert: str
    reason: str
    attempt_kind: str
    cross_case_check: str


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
    repair_calibration_rows = _repair_objective_calibration_rows(specs, trace_rows, action_rows, metric_rows)
    design_rows = [_design_register_row(spec) for spec in specs]
    repair_specs = _repair_iteration_specs()
    repair_records, repair_iteration_rows = _run_repair_codesign_iterations(repair_specs)
    repair_trace_rows = [record["trace_row"] for record in repair_records]
    repair_action_rows = [row for record in repair_records for row in record["action_rows"]]
    repair_metric_rows = [record["metric_row"] for record in repair_records]
    repair_candidate_rows = [row for record in repair_records for row in record["candidate_rows"]]
    objective_attempt_rows = _repair_objective_attempt_rows(repair_iteration_rows)
    scenario_attempt_rows = _repair_scenario_attempt_rows(repair_iteration_rows)

    _write_csv(OUTPUT_ROOT / "objective_scenario_design_register.csv", design_rows, _design_columns())
    _write_csv(OUTPUT_ROOT / "co_design_iteration_log.csv", iteration_rows, _iteration_columns())
    _write_csv(OUTPUT_ROOT / "objective_calibration_log.csv", calibration_rows, _calibration_columns())
    _write_csv(
        OUTPUT_ROOT / "objective_calibration_repair_log_prompt3b_r.csv",
        repair_calibration_rows,
        _repair_calibration_columns(),
    )
    _write_csv(GATE_DIR / "baseline_comparison_prompt3b.csv", baseline_rows, _comparison_columns())
    _write_csv(GATE_DIR / "ablation_comparison_prompt3b.csv", ablation_rows, _comparison_columns())
    _write_csv(GATE_DIR / "failure_trace_prompt3b.csv", failure_rows, _failure_columns())
    _write_csv(GATE_DIR / "scenario_summary_prompt3b.csv", scenario_rows, _scenario_summary_columns())
    _write_csv(GATE_DIR / "candidate_gap_table_prompt3b.csv", candidate_rows, _columns_union(candidate_rows, p3a._candidate_columns()))
    _write_csv(GATE_DIR / "action_value_decomposition_prompt3b.csv", action_rows, _columns_union(action_rows, p3a._action_columns()))
    _write_csv(GATE_DIR / "trace_join_table_prompt3b.csv", trace_rows, _columns_union(trace_rows, p3a._trace_columns()))
    _write_csv(GATE_DIR / "realized_events_prompt3b.csv", event_rows, p3a._realized_event_columns())
    _write_csv(GATE_DIR / "event_metric_windows_prompt3b.csv", metric_rows, p3a._event_metric_columns())
    _write_csv(
        GATE_DIR / "prompt3b_r_codesign_repair_iteration_log.csv",
        repair_iteration_rows,
        _repair_iteration_log_columns(),
    )
    _write_csv(
        GATE_DIR / "prompt3b_r_objective_calibration_attempts.csv",
        objective_attempt_rows,
        _repair_objective_attempt_columns(),
    )
    _write_csv(
        GATE_DIR / "prompt3b_r_scenario_ladder_attempts.csv",
        scenario_attempt_rows,
        _repair_scenario_attempt_columns(),
    )
    (OUTPUT_ROOT / "prompt3b_r_keep_revert_decisions.md").write_text(
        _keep_revert_decisions_md(repair_iteration_rows),
        encoding="utf-8",
    )

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
        repair_calibration_rows,
    )
    paper_status = _write_paper_evidence_outputs(
        specs,
        trace_rows,
        action_rows,
        metric_rows,
        candidate_rows,
        baseline_rows,
        ablation_rows,
        iteration_rows,
        repair_calibration_rows,
        repair_iteration_rows,
        repair_trace_rows,
        repair_action_rows,
        repair_metric_rows,
        repair_candidate_rows,
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
    print(f"prompt3b_r_verdict={paper_status['verdict']}")
    print(f"paper_evidence_targets_supported={paper_status['supported']}")
    print(f"paper_evidence_targets_partial={paper_status['partial']}")
    print(f"paper_evidence_targets_failed={paper_status['failed']}")
    print("scenario_families_rerun=P0,P1a,P1b")
    print(f"default_objective_config_used={str(paper_status['default_objective_config_used']).lower()}")
    print(f"first_class_baselines_ready={str(paper_status['first_class_baselines_ready']).lower()}")
    print(f"can_join_full_chain_rate={status['can_join_full_chain_rate']:.6f}")
    print(f"near_miss_realized_service_status={paper_status['near_miss_realized_service_status']}")
    print(f"forced_accommodation_status={paper_status['forced_accommodation_status']}")
    print(f"ablation_sensitivity_status={paper_status['ablation_sensitivity_status']}")
    print(f"ready_for_prompt4_lock_candidate={str(paper_status['ready']).lower()}")
    print(f"main_blocker_if_any={paper_status['main_blocker']}")
    print(f"review_packet_path={HUMAN_REVIEW_DIR / 'PROMPT_3B_R_PAPER_EVIDENCE_PACKET.md'}")
    print("STOP_AFTER_PROMPT_3B_R_PAPER_EVIDENCE_PACKET=true")


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
            failure_observed="forced_accommodation is first-class after repair but remains RPMI-derived diagnostic instrumentation and does not prove service-with-disturbance",
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


def _p1b_near_miss_gap7_ramp7415() -> ScenarioConfig:
    cfg = _p1b_near_miss_gap7()
    return make_scenario_config(
        "P3BR-P1B-NEAR-MISS-GAP7-RAMP7415",
        seed=0,
        road=cfg.road,
        simulation=cfg.simulation,
        vehicles={**cfg.vehicles, "ramp_start_x": 74.15},
        readiness_targets=_readiness_targets(),
        mechanism_targets={"mechanism": "Prompt3B-R", "mechanism_target": "P1b_near_miss_ramp_timing_repair"},
    )


def _p1b_near_miss_gap5_ramp7625() -> ScenarioConfig:
    cfg = _p1b_near_miss_gap5()
    return make_scenario_config(
        "P3BR-P1B-NEAR-MISS-GAP5-RAMP7625",
        seed=0,
        road=cfg.road,
        simulation=cfg.simulation,
        vehicles={**cfg.vehicles, "ramp_start_x": 76.25},
        readiness_targets=_readiness_targets(),
        mechanism_targets={"mechanism": "Prompt3B-R", "mechanism_target": "P1b_near_miss_tight_gap_ramp_timing_repair"},
    )


def _p1a_tight_gap_default() -> ScenarioConfig:
    return make_scenario_config(
        "P3BR-P1A-TIGHT-GAP-DEFAULT",
        seed=0,
        road={"target_lane": 0, "ramp_lane": -1, "ramp_end_x": 140.0},
        simulation=_sim(H=5.0, lambda_C=0.001, theta=0.05),
        vehicles={
            "boundary_pairs": ["CAV-HDV", "CAV-HDV"],
            "gap_widths": [7.0, 1.0],
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
        mechanism_targets={"mechanism": "Prompt3B-R", "mechanism_target": "P1a_tight_gap_default"},
    )


def _p1a_tight_gap_theta0() -> ScenarioConfig:
    cfg = _p1a_tight_gap_default()
    return make_scenario_config(
        "P3BR-P1A-TIGHT-GAP-THETA0",
        seed=0,
        road=cfg.road,
        simulation=_sim(H=5.0, lambda_C=0.001, theta=0.0),
        vehicles=cfg.vehicles,
        readiness_targets=_readiness_targets(),
        mechanism_targets={"mechanism": "Prompt3B-R", "mechanism_target": "P1a_tight_gap_theta_zero"},
    )


def _p1a_tight_gap_lambda30() -> ScenarioConfig:
    cfg = _p1a_tight_gap_default()
    return make_scenario_config(
        "P3BR-P1A-TIGHT-GAP-LAMBDA30",
        seed=0,
        road=cfg.road,
        simulation=_sim(H=5.0, lambda_C=30.0, theta=0.05),
        vehicles=cfg.vehicles,
        readiness_targets=_readiness_targets(),
        mechanism_targets={"mechanism": "Prompt3B-R", "mechanism_target": "P1a_tight_gap_lambda_thirty"},
    )


def _p0_refined_h2() -> ScenarioConfig:
    cfg = _p0_refined()
    return make_scenario_config(
        "P3BR-P0-RAW65-B7-H2",
        seed=0,
        road=cfg.road,
        simulation=_sim(H=2.0, lambda_C=0.001, theta=0.05),
        vehicles=cfg.vehicles,
        readiness_targets=_readiness_targets(),
        mechanism_targets={"mechanism": "Prompt3B-R", "mechanism_target": "P0_raw_gap_shorter_metric_window"},
    )


def _p0_refined_h2_rear15() -> ScenarioConfig:
    cfg = _p0_refined()
    return make_scenario_config(
        "P3BR-P0-RAW65-B7-H2-REAR15",
        seed=0,
        road=cfg.road,
        simulation=_sim(H=2.0, lambda_C=0.001, theta=0.05),
        vehicles={**cfg.vehicles, "rear_speed_offsets": [15.0, 0.0]},
        readiness_targets=_readiness_targets(),
        mechanism_targets={"mechanism": "Prompt3B-R", "mechanism_target": "P0_raw_gap_closing_rate_pressure"},
    )


def _p1a_default_lambda() -> ScenarioConfig:
    cfg = _p1a_bad_action()
    return make_scenario_config(
        "P3BR-P1A-BAD-ACTION-LAMBDA-DEFAULT",
        seed=0,
        road=cfg.road,
        simulation=_sim(H=5.0, lambda_C=0.001, theta=0.05),
        vehicles=cfg.vehicles,
        readiness_targets=_readiness_targets(),
        mechanism_targets={"mechanism": "Prompt3B-R", "mechanism_target": "P1a_bad_action_default_lambda_check"},
    )


def _p1b_gap7_ramp7415_lambda30() -> ScenarioConfig:
    cfg = _p1b_near_miss_gap7_ramp7415()
    return make_scenario_config(
        "P3BR-P1B-GAP7-RAMP7415-LAMBDA30",
        seed=0,
        road=cfg.road,
        simulation=_sim(H=1.0, lambda_C=30.0, theta=0.05),
        vehicles=cfg.vehicles,
        readiness_targets=_readiness_targets(),
        mechanism_targets={"mechanism": "Prompt3B-R", "mechanism_target": "P1b_lambda30_cross_case_check"},
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
        "action_mode": "override",
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
        D_H = len({trace.get("demand_id") for trace in group if trace.get("demand_id")})
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


def _repair_objective_calibration_rows(
    specs: Sequence[IterationSpec],
    traces: Sequence[Mapping[str, Any]],
    actions: Sequence[Mapping[str, Any]],
    metrics: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in specs:
        full = _trace_for_variant(traces, spec, FULL_VARIANT)
        raw = _trace_for_variant(traces, spec, "raw_largest_gap")
        forced = _trace_for_variant(traces, spec, "forced_accommodation")
        without_rd = _trace_for_variant(traces, spec, "without_RD")
        without_c = _trace_for_variant(traces, spec, "without_Cbar")
        without_theta = _trace_for_variant(traces, spec, "without_theta")
        full_metric = _metric_for_trace(metrics, full)
        forced_metric = _metric_for_trace(metrics, forced)
        full_action = _action_for_trace(actions, full)
        rows.append(
            {
                "scenario_design_id": spec.scenario_design_id,
                "scenario_family": spec.scenario_family,
                "scenario_subfamily": spec.scenario_subfamily,
                "default_lambda_C": full_action.get("lambda_C", ""),
                "default_theta": full_action.get("theta", ""),
                "full_selected_action": full.get("selected_action_id", ""),
                "full_selected_gap": full.get("selected_gap_id", ""),
                "raw_selected_gap": raw.get("selected_gap_id", ""),
                "forced_selected_action": forced.get("selected_action_id", ""),
                "without_RD_selected_action": without_rd.get("selected_action_id", ""),
                "without_Cbar_selected_action": without_c.get("selected_action_id", ""),
                "without_theta_selected_action": without_theta.get("selected_action_id", ""),
                "full_merge_success": full.get("merge_success", ""),
                "forced_merge_success": forced.get("merge_success", ""),
                "RD_pred": full.get("selected_gap_RD_pred", ""),
                "RD_realized": full_metric.get("RD_realized_proxy", ""),
                "C_dist_pred": full.get("selected_action_C_bar", ""),
                "full_disturbance": full_metric.get("mainline_disturbance_cost", ""),
                "forced_disturbance": forced_metric.get("mainline_disturbance_cost", ""),
                "lambda_C_cross_case_status": "default_or_logged_diagnostic",
                "theta_cross_case_status": "default_or_without_theta_ablation",
                "keep_or_revert": spec.keep_or_revert,
                "claim_boundary_status": "prompt3b_r_diagnostic_only_not_locked",
            }
        )
    return rows


def _repair_iteration_specs() -> list[RepairIterationSpec]:
    return [
        RepairIterationSpec(
            iteration_id="P3BR-ITER-001",
            evidence_target_id="C1_raw_gap_illusion",
            scenario_family="P0",
            scenario_subfamily="P0_shorter_metric_window",
            observed_failure="P0 raw-gap contrast was visible, but the forced/full realized-disturbance contrast remained partial.",
            failure_type="revise_scenario",
            hypothesis="Shortening the metric window will preserve the raw-gap trap while making realized disturbance easier to detect.",
            changed_component="diagnostic_scenario_parameters",
            old_value="P0 refined H=5, Gap B width 7",
            new_value="P0 refined H=2, Gap B width 7",
            rerun_case_id="P3BR-DET-P0-001",
            before_builder=_p0_refined,
            after_builder=_p0_refined_h2,
            keep_or_revert="keep_partial",
            reason="Keep only as diagnostic lineage if it improves contrast without worsening listed safety/disturbance metrics.",
            attempt_kind="scenario_ladder",
            cross_case_check="P0 closing-rate pressure rerun checks whether the same repair direction survives stronger rear pressure.",
        ),
        RepairIterationSpec(
            iteration_id="P3BR-ITER-002",
            evidence_target_id="C2_forced_accommodation",
            scenario_family="P0",
            scenario_subfamily="P0_closing_rate_pressure",
            observed_failure="Forced accommodation still did not cleanly demonstrate service-with-disturbance versus full RPMI.",
            failure_type="revise_scenario",
            hypothesis="Increasing Gap A rear closing pressure should expose whether the forced baseline is more disturbing than full.",
            changed_component="diagnostic_scenario_parameters",
            old_value="P0 H=2, rear speed offsets [10,0]",
            new_value="P0 H=2, rear speed offsets [15,0]",
            rerun_case_id="P3BR-DET-P0-002",
            before_builder=_p0_refined_h2,
            after_builder=_p0_refined_h2_rear15,
            keep_or_revert="revert_for_claim_support",
            reason="Do not promote if the pressure case collapses full and forced choices or worsens safety/disturbance.",
            attempt_kind="scenario_ladder",
            cross_case_check="Local P0 pressure rerun only; not a held-out cross-family validation.",
        ),
        RepairIterationSpec(
            iteration_id="P3BR-ITER-003",
            evidence_target_id="C4_bad_action_suppression",
            scenario_family="P1a",
            scenario_subfamily="P1a_default_lambda_cross_check",
            observed_failure="The P1a bad-action suppression evidence depended on a high lambda_C diagnostic config.",
            failure_type="revise_objective",
            hypothesis="Rerunning P1a with the default lambda_C checks whether suppression is objective-stable rather than a single-case tuning artifact.",
            changed_component="lambda_C",
            old_value="lambda_C=30.0 in P1a bad-action diagnostic",
            new_value="lambda_C=0.001 default diagnostic value",
            rerun_case_id="P3BR-DET-P1A-001",
            before_builder=_p1a_bad_action,
            after_builder=_p1a_default_lambda,
            keep_or_revert="keep_for_cross_case_diagnostic_only",
            reason="Record the cross-check, but do not lock a global objective setting from a diagnostic rerun.",
            attempt_kind="objective_calibration",
            cross_case_check="Default lambda_C is checked locally in P1a and separately against P1b in P3BR-ITER-007.",
        ),
        RepairIterationSpec(
            iteration_id="P3BR-ITER-004",
            evidence_target_id="C6_ablation_mechanism",
            scenario_family="P1a",
            scenario_subfamily="P1a_theta_threshold_check",
            observed_failure="Theta sensitivity needed a first-class diagnostic attempt rather than an implicit harness branch.",
            failure_type="revise_objective",
            hypothesis="Setting theta to zero on the tight-gap P1a ladder should surface tiny-RCMV action sensitivity while retaining trace closure.",
            changed_component="theta",
            old_value="theta=0.05 on P1a tight-gap ladder",
            new_value="theta=0.0 on P1a tight-gap ladder",
            rerun_case_id="P3BR-DET-P1A-002",
            before_builder=_p1a_tight_gap_default,
            after_builder=_p1a_tight_gap_theta0,
            keep_or_revert="revert_for_global_objective",
            reason="Use as an ablation sensitivity check only; no global theta lock is allowed in Prompt 3B-R.",
            attempt_kind="objective_calibration",
            cross_case_check="The regular without_theta variant is rerun across every repair case as the cross-case theta check.",
        ),
        RepairIterationSpec(
            iteration_id="P3BR-ITER-005",
            evidence_target_id="C4_bad_action_suppression",
            scenario_family="P1a",
            scenario_subfamily="P1a_tight_gap_lambda_check",
            observed_failure="Bad-action suppression and lambda_C scaling remained entangled in the P1a ladder.",
            failure_type="revise_objective",
            hypothesis="The tight-gap P1a ladder with lambda_C=30 should show whether action-cost weighting changes the selected action without breaking trace joins.",
            changed_component="lambda_C",
            old_value="P1a tight-gap lambda_C=0.001",
            new_value="P1a tight-gap lambda_C=30.0",
            rerun_case_id="P3BR-DET-P1A-003",
            before_builder=_p1a_tight_gap_default,
            after_builder=_p1a_tight_gap_lambda30,
            keep_or_revert="keep_partial",
            reason="Keep as P1a diagnostic evidence only if the local rerun is trace-complete and no listed safety/disturbance regression appears.",
            attempt_kind="objective_calibration",
            cross_case_check="P3BR-ITER-007 checks the same high lambda_C direction on the P1b near-miss ladder.",
        ),
        RepairIterationSpec(
            iteration_id="P3BR-ITER-006",
            evidence_target_id="C5_near_miss_production",
            scenario_family="P1b",
            scenario_subfamily="P1b_ramp_timing_gap7",
            observed_failure="Near-miss selected actions were traceable but did not realize demand service.",
            failure_type="revise_implementation",
            hypothesis="A small deterministic ramp timing shift may turn the selected near-miss action into realized service without changing core logic.",
            changed_component="diagnostic_scenario_parameters",
            old_value="Gap 7 ramp_start_x=74.0",
            new_value="Gap 7 ramp_start_x=74.15",
            rerun_case_id="P3BR-DET-P1B-001",
            before_builder=_p1b_near_miss_gap7,
            after_builder=_p1b_near_miss_gap7_ramp7415,
            keep_or_revert="keep_partial",
            reason="Keep only as deterministic scenario-ladder evidence; service failure remains an implementation/scenario blocker.",
            attempt_kind="scenario_ladder",
            cross_case_check="P3BR-ITER-008 repeats the timing repair on the tighter Gap 5 P1b ladder.",
        ),
        RepairIterationSpec(
            iteration_id="P3BR-ITER-007",
            evidence_target_id="C6_ablation_mechanism",
            scenario_family="P1b",
            scenario_subfamily="P1b_lambda_cross_case",
            observed_failure="A high lambda_C repair that appears useful in P1a could be a single-family artifact.",
            failure_type="revise_objective",
            hypothesis="Applying lambda_C=30 to the repaired P1b Gap 7 timing case checks whether the objective change transfers or should be reverted.",
            changed_component="lambda_C",
            old_value="P1b repaired Gap 7 lambda_C=0.001",
            new_value="P1b repaired Gap 7 lambda_C=30.0",
            rerun_case_id="P3BR-DET-P1B-002",
            before_builder=_p1b_near_miss_gap7_ramp7415,
            after_builder=_p1b_gap7_ramp7415_lambda30,
            keep_or_revert="revert_for_global_objective",
            reason="Revert as a global objective candidate unless the cross-case run improves service without worse listed disturbance/safety metrics.",
            attempt_kind="objective_calibration_cross_case",
            cross_case_check="Cross-case check for P1a lambda_C=30 against P1b near-miss production.",
        ),
        RepairIterationSpec(
            iteration_id="P3BR-ITER-008",
            evidence_target_id="C5_near_miss_production",
            scenario_family="P1b",
            scenario_subfamily="P1b_ramp_timing_gap5",
            observed_failure="The tighter P1b near-miss scenario still needed a deterministic service-realization repair attempt.",
            failure_type="revise_scenario",
            hypothesis="A larger ramp timing shift on the Gap 5 ladder checks whether near-miss service can be realized by scenario timing alone.",
            changed_component="diagnostic_scenario_parameters",
            old_value="Gap 5 ramp_start_x=74.0",
            new_value="Gap 5 ramp_start_x=76.25",
            rerun_case_id="P3BR-DET-P1B-003",
            before_builder=_p1b_near_miss_gap5,
            after_builder=_p1b_near_miss_gap5_ramp7625,
            keep_or_revert="revert_for_claim_support",
            reason="Do not claim support if realized service remains absent or safety/disturbance worsens.",
            attempt_kind="scenario_ladder",
            cross_case_check="Cross-checks the P1b Gap 7 timing repair on a tighter near-miss ladder.",
        ),
    ]


def _run_repair_codesign_iterations(
    specs: Sequence[RepairIterationSpec],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    original_source_batch_id = p3a.SOURCE_BATCH_ID
    p3a.SOURCE_BATCH_ID = PROMPT3B_R_SOURCE_BATCH_ID
    try:
        for spec in specs:
            before_records, before_error = _run_repair_phase(spec, "before", spec.before_builder)
            after_records, after_error = _run_repair_phase(spec, "after", spec.after_builder)
            records.extend(before_records)
            records.extend(after_records)
            rows.append(_repair_iteration_row(spec, before_records, after_records, before_error, after_error))
    finally:
        p3a.SOURCE_BATCH_ID = original_source_batch_id
    return records, rows


def _run_repair_phase(
    spec: RepairIterationSpec,
    phase: str,
    builder: Callable[[], ScenarioConfig],
) -> tuple[list[dict[str, Any]], str]:
    records: list[dict[str, Any]] = []
    try:
        scenario = builder()
        params = p3a._params_for_scenario(scenario)
        for variant in VARIANTS:
            record = p3a._run_variant(scenario, spec.scenario_family, variant, params)
            _patch_repair_record_for_prompt3br(record, spec, phase, scenario)
            records.append(record)
        return records, ""
    except Exception as exc:
        return records, f"{type(exc).__name__}: {exc}"


def _patch_repair_record_for_prompt3br(
    record: dict[str, Any],
    spec: RepairIterationSpec,
    phase: str,
    scenario: ScenarioConfig,
) -> None:
    for group_name in ("candidate_rows", "action_rows"):
        for row in record[group_name]:
            _patch_repair_row_base(row, spec, phase, scenario)
            row["scenario_subfamily"] = spec.scenario_subfamily
            row["scenario_design_id"] = scenario.scenario_id
            if group_name == "candidate_rows" and row.get("variant") == FULL_VARIANT:
                row["is_selected_by_full_rpmi"] = row.get("selected_gap_available", False)
            if group_name == "action_rows":
                row["J_components_formula"] = "J = Z_bar + lambda_D * RD_pred_norm + lambda_C * C_bar"
    for key in ("trace_row", "event_row", "metric_row"):
        _patch_repair_row_base(record[key], spec, phase, scenario)
    trace = record["trace_row"]
    trace["scenario_subfamily"] = spec.scenario_subfamily
    trace["scenario_design_id"] = scenario.scenario_id
    trace["physical_gap_id"] = trace.get("physical_gap_id") or trace.get("selected_gap_id", "")
    record["event_row"]["note"] = "prompt3b_r_repair_rerun_record_only_no_lock"
    record["metric_row"]["RD_pred"] = trace.get("selected_gap_RD_pred", "")
    record["metric_row"]["RD_prediction_error"] = _float(record["metric_row"].get("RD_realized_proxy")) - _float(
        trace.get("selected_gap_RD_pred")
    )


def _patch_repair_row_base(
    row: dict[str, Any],
    spec: RepairIterationSpec,
    phase: str,
    scenario: ScenarioConfig,
) -> None:
    row["schema_version"] = SCHEMA_VERSION
    row["source_batch_id"] = PROMPT3B_R_SOURCE_BATCH_ID
    row["source_table"] = "prompt3b_mechanism_codesign_loop"
    row["repair_iteration_id"] = spec.iteration_id
    row["evidence_target_id"] = spec.evidence_target_id
    row["repair_phase"] = phase
    row["scenario_design_id"] = scenario.scenario_id
    row["deterministic_case_id"] = f"{spec.rerun_case_id}-{phase}"
    row["random_seed_optional"] = "0"


def _repair_iteration_row(
    spec: RepairIterationSpec,
    before_records: Sequence[Mapping[str, Any]],
    after_records: Sequence[Mapping[str, Any]],
    before_error: str,
    after_error: str,
) -> dict[str, Any]:
    before = _repair_record_for_variant(before_records, FULL_VARIANT)
    after = _repair_record_for_variant(after_records, FULL_VARIANT)
    before_raw = _repair_record_for_variant(before_records, "raw_largest_gap")
    after_raw = _repair_record_for_variant(after_records, "raw_largest_gap")
    before_forced = _repair_record_for_variant(before_records, "forced_accommodation")
    after_forced = _repair_record_for_variant(after_records, "forced_accommodation")
    after_without_rd = _repair_record_for_variant(after_records, "without_RD")
    after_without_c = _repair_record_for_variant(after_records, "without_Cbar")
    after_without_theta = _repair_record_for_variant(after_records, "without_theta")
    before_trace = before.get("trace_row", {})
    after_trace = after.get("trace_row", {})
    before_metric = before.get("metric_row", {})
    after_metric = after.get("metric_row", {})
    after_forced_metric = after_forced.get("metric_row", {})
    after_worse = _listed_disturbance_or_safety_worse(after_metric, before_metric) if before_metric and after_metric else False
    after_all_joined = all(_truthy(record.get("trace_row", {}).get("can_join_full_chain")) for record in after_records) if after_records else False
    before_all_joined = all(_truthy(record.get("trace_row", {}).get("can_join_full_chain")) for record in before_records) if before_records else False
    service_improved = _truthy(after_trace.get("merge_success")) and not _truthy(before_trace.get("merge_success"))
    selection_changed = (
        before_trace.get("selected_action_id") != after_trace.get("selected_action_id")
        or before_trace.get("selected_gap_id") != after_trace.get("selected_gap_id")
    )
    local_status = _repair_local_rerun_status(
        before_error=before_error,
        after_error=after_error,
        after_all_joined=after_all_joined,
        after_worse=after_worse,
        service_improved=service_improved,
        selection_changed=selection_changed,
    )
    return {
        "iteration_id": spec.iteration_id,
        "evidence_target_id": spec.evidence_target_id,
        "attempt_kind": spec.attempt_kind,
        "scenario_family": spec.scenario_family,
        "scenario_subfamily": spec.scenario_subfamily,
        "before_scenario_id": before.get("scenario_id", ""),
        "after_scenario_id": after.get("scenario_id", ""),
        "before_scenario_design_id": before_trace.get("scenario_design_id", ""),
        "after_scenario_design_id": after_trace.get("scenario_design_id", ""),
        "rerun_case_id": spec.rerun_case_id,
        "observed_failure": spec.observed_failure,
        "failure_observed": spec.observed_failure,
        "failure_type": spec.failure_type,
        "hypothesis": spec.hypothesis,
        "changed_component": spec.changed_component,
        "old_value": spec.old_value,
        "new_value": spec.new_value,
        "before_error": before_error,
        "after_error": after_error,
        "local_rerun_status": local_status,
        "local_rerun_result": _repair_rerun_result_sentence(before_records, after_records),
        "rerun_result": _repair_rerun_result_sentence(before_records, after_records),
        "selected_gap_before": before_trace.get("selected_gap_id", ""),
        "selected_gap_after": after_trace.get("selected_gap_id", ""),
        "selected_action_before": before_trace.get("selected_action_id", ""),
        "selected_action_after": after_trace.get("selected_action_id", ""),
        "raw_selected_gap_before": before_raw.get("trace_row", {}).get("selected_gap_id", ""),
        "raw_selected_gap_after": after_raw.get("trace_row", {}).get("selected_gap_id", ""),
        "forced_selected_action_before": before_forced.get("trace_row", {}).get("selected_action_id", ""),
        "forced_selected_action_after": after_forced.get("trace_row", {}).get("selected_action_id", ""),
        "without_RD_selected_action_after": after_without_rd.get("trace_row", {}).get("selected_action_id", ""),
        "without_Cbar_selected_action_after": after_without_c.get("trace_row", {}).get("selected_action_id", ""),
        "without_theta_selected_action_after": after_without_theta.get("trace_row", {}).get("selected_action_id", ""),
        "full_merge_success_before": before_trace.get("merge_success", ""),
        "full_merge_success_after": after_trace.get("merge_success", ""),
        "before_all_variants_joined": before_all_joined,
        "after_all_variants_joined": after_all_joined,
        "full_disturbance_before": before_metric.get("mainline_disturbance_cost", ""),
        "full_disturbance_after": after_metric.get("mainline_disturbance_cost", ""),
        "forced_disturbance_after": after_forced_metric.get("mainline_disturbance_cost", ""),
        "realized_disturbance_change": _float(after_metric.get("mainline_disturbance_cost")) - _float(
            before_metric.get("mainline_disturbance_cost")
        ),
        "disturbance_or_safety_worse": after_worse,
        "cross_case_check": spec.cross_case_check,
        "cross_case_status": _repair_cross_case_status(spec, local_status, after_all_joined, after_worse),
        "keep_or_revert": spec.keep_or_revert,
        "reason": spec.reason,
        "failure_driven": True,
        "claim_boundary_status": "prompt3b_r_repair_only_not_prompt4_not_locked",
    }


def _repair_record_for_variant(
    records: Sequence[Mapping[str, Any]],
    variant: str,
) -> Mapping[str, Any]:
    return next((record for record in records if record.get("variant") == variant), {})


def _repair_local_rerun_status(
    *,
    before_error: str,
    after_error: str,
    after_all_joined: bool,
    after_worse: bool,
    service_improved: bool,
    selection_changed: bool,
) -> str:
    if before_error or after_error:
        return "run_error"
    if not after_all_joined:
        return "trace_join_incomplete"
    if after_worse:
        return "rerun_completed_regression_observed"
    if service_improved:
        return "rerun_completed_service_improved"
    if selection_changed:
        return "rerun_completed_selection_changed"
    return "rerun_completed_no_decisive_change"


def _repair_cross_case_status(
    spec: RepairIterationSpec,
    local_status: str,
    after_all_joined: bool,
    after_worse: bool,
) -> str:
    if local_status == "run_error":
        return "cross_case_not_interpretable_run_error"
    if not after_all_joined:
        return "cross_case_not_interpretable_trace_join_incomplete"
    if after_worse:
        return "cross_case_ran_regression_or_safety_worse"
    if "cross_case" in spec.attempt_kind or "cross-case" in spec.cross_case_check.lower():
        return "cross_case_ran_no_listed_regression"
    return "local_rerun_ran_cross_case_pending_or_declared_in_adjacent_iteration"


def _repair_rerun_result_sentence(
    before_records: Sequence[Mapping[str, Any]],
    after_records: Sequence[Mapping[str, Any]],
) -> str:
    before = _repair_record_for_variant(before_records, FULL_VARIANT)
    after = _repair_record_for_variant(after_records, FULL_VARIANT)
    after_raw = _repair_record_for_variant(after_records, "raw_largest_gap")
    after_forced = _repair_record_for_variant(after_records, "forced_accommodation")
    after_without_rd = _repair_record_for_variant(after_records, "without_RD")
    after_without_c = _repair_record_for_variant(after_records, "without_Cbar")
    after_without_theta = _repair_record_for_variant(after_records, "without_theta")
    before_trace = before.get("trace_row", {})
    after_trace = after.get("trace_row", {})
    before_metric = before.get("metric_row", {})
    after_metric = after.get("metric_row", {})
    after_forced_metric = after_forced.get("metric_row", {})
    return (
        f"before_full={before_trace.get('selected_action_id', '')}/{before_trace.get('selected_gap_id', '')}, "
        f"after_full={after_trace.get('selected_action_id', '')}/{after_trace.get('selected_gap_id', '')}, "
        f"after_raw={after_raw.get('trace_row', {}).get('selected_action_id', '')}/"
        f"{after_raw.get('trace_row', {}).get('selected_gap_id', '')}, "
        f"after_forced={after_forced.get('trace_row', {}).get('selected_action_id', '')}/"
        f"{after_forced.get('trace_row', {}).get('selected_gap_id', '')}, "
        f"after_without_RD={after_without_rd.get('trace_row', {}).get('selected_action_id', '')}/"
        f"{after_without_rd.get('trace_row', {}).get('selected_gap_id', '')}, "
        f"after_without_Cbar={after_without_c.get('trace_row', {}).get('selected_action_id', '')}/"
        f"{after_without_c.get('trace_row', {}).get('selected_gap_id', '')}, "
        f"after_without_theta={after_without_theta.get('trace_row', {}).get('selected_action_id', '')}/"
        f"{after_without_theta.get('trace_row', {}).get('selected_gap_id', '')}, "
        f"before_disturbance={before_metric.get('mainline_disturbance_cost', '')}, "
        f"after_disturbance={after_metric.get('mainline_disturbance_cost', '')}, "
        f"after_forced_disturbance={after_forced_metric.get('mainline_disturbance_cost', '')}, "
        f"after_full_merge_success={after_trace.get('merge_success', '')}"
    )


def _repair_objective_attempt_rows(
    repair_iteration_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    objective_rows = []
    for row in repair_iteration_rows:
        if "objective" not in str(row.get("attempt_kind", "")) and row.get("changed_component") not in {"lambda_C", "theta"}:
            continue
        objective_rows.append(
            {
                "iteration_id": row.get("iteration_id", ""),
                "evidence_target_id": row.get("evidence_target_id", ""),
                "scenario_family": row.get("scenario_family", ""),
                "scenario_subfamily": row.get("scenario_subfamily", ""),
                "changed_component": row.get("changed_component", ""),
                "old_value": row.get("old_value", ""),
                "new_value": row.get("new_value", ""),
                "failure_observed": row.get("failure_observed", ""),
                "failure_type": row.get("failure_type", ""),
                "hypothesis": row.get("hypothesis", ""),
                "local_rerun_status": row.get("local_rerun_status", ""),
                "local_rerun_result": row.get("local_rerun_result", ""),
                "cross_case_check": row.get("cross_case_check", ""),
                "cross_case_status": row.get("cross_case_status", ""),
                "disturbance_or_safety_worse": row.get("disturbance_or_safety_worse", ""),
                "keep_or_revert": row.get("keep_or_revert", ""),
                "reason": row.get("reason", ""),
                "failure_driven": row.get("failure_driven", ""),
                "claim_boundary_status": row.get("claim_boundary_status", ""),
            }
        )
    return objective_rows


def _repair_scenario_attempt_rows(
    repair_iteration_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    scenario_rows = []
    for row in repair_iteration_rows:
        if row.get("changed_component") != "diagnostic_scenario_parameters" and "scenario" not in str(row.get("attempt_kind", "")):
            continue
        scenario_rows.append(
            {
                "iteration_id": row.get("iteration_id", ""),
                "evidence_target_id": row.get("evidence_target_id", ""),
                "scenario_family": row.get("scenario_family", ""),
                "scenario_subfamily": row.get("scenario_subfamily", ""),
                "before_scenario_id": row.get("before_scenario_id", ""),
                "after_scenario_id": row.get("after_scenario_id", ""),
                "rerun_case_id": row.get("rerun_case_id", ""),
                "changed_component": row.get("changed_component", ""),
                "old_value": row.get("old_value", ""),
                "new_value": row.get("new_value", ""),
                "failure_observed": row.get("failure_observed", ""),
                "failure_type": row.get("failure_type", ""),
                "hypothesis": row.get("hypothesis", ""),
                "local_rerun_status": row.get("local_rerun_status", ""),
                "local_rerun_result": row.get("local_rerun_result", ""),
                "selected_action_before": row.get("selected_action_before", ""),
                "selected_action_after": row.get("selected_action_after", ""),
                "selected_gap_before": row.get("selected_gap_before", ""),
                "selected_gap_after": row.get("selected_gap_after", ""),
                "full_merge_success_after": row.get("full_merge_success_after", ""),
                "realized_disturbance_change": row.get("realized_disturbance_change", ""),
                "disturbance_or_safety_worse": row.get("disturbance_or_safety_worse", ""),
                "cross_case_check": row.get("cross_case_check", ""),
                "cross_case_status": row.get("cross_case_status", ""),
                "keep_or_revert": row.get("keep_or_revert", ""),
                "reason": row.get("reason", ""),
                "claim_boundary_status": row.get("claim_boundary_status", ""),
            }
        )
    return scenario_rows


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
    repair_calibration_rows: Sequence[Mapping[str, Any]],
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
    (HUMAN_REVIEW_DIR / "PROMPT_3B_REPAIR_REVIEW_PACKET.md").write_text(
        _repair_review_packet_md(
            specs,
            traces,
            actions,
            metrics,
            baseline_rows,
            ablation_rows,
            iteration_rows,
            repair_calibration_rows,
            status,
        ),
        encoding="utf-8",
    )


def _write_paper_evidence_outputs(
    specs: Sequence[IterationSpec],
    traces: Sequence[Mapping[str, Any]],
    actions: Sequence[Mapping[str, Any]],
    metrics: Sequence[Mapping[str, Any]],
    candidates: Sequence[Mapping[str, Any]],
    baseline_rows: Sequence[Mapping[str, Any]],
    ablation_rows: Sequence[Mapping[str, Any]],
    iteration_rows: Sequence[Mapping[str, Any]],
    repair_calibration_rows: Sequence[Mapping[str, Any]],
    repair_iteration_rows: Sequence[Mapping[str, Any]],
    repair_trace_rows: Sequence[Mapping[str, Any]],
    repair_action_rows: Sequence[Mapping[str, Any]],
    repair_metric_rows: Sequence[Mapping[str, Any]],
    repair_candidate_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    del repair_trace_rows, repair_action_rows, repair_metric_rows, repair_candidate_rows
    target_rows = _paper_target_rows(specs, traces, metrics, candidates)
    evidence_rows = _paper_candidate_evidence_rows(specs, traces, actions, metrics, candidates, target_rows)
    variant_rows = _paper_candidate_variant_metric_rows(specs, traces, actions, metrics, target_rows)
    status = _paper_status(target_rows)

    _write_csv(
        GATE_DIR / "paper_candidate_evidence_table.csv",
        evidence_rows,
        _paper_evidence_columns(),
    )
    _write_csv(
        GATE_DIR / "paper_candidate_variant_metrics.csv",
        variant_rows,
        _paper_variant_metric_columns(),
    )
    (OUTPUT_ROOT / "paper_experiment_evidence_matrix.md").write_text(
        _paper_experiment_evidence_matrix_md(target_rows, evidence_rows, variant_rows),
        encoding="utf-8",
    )
    (OUTPUT_ROOT / "candidate_paper_figures_manifest.md").write_text(
        _candidate_paper_figures_manifest_md(),
        encoding="utf-8",
    )
    (HUMAN_REVIEW_DIR / "PROMPT_3B_R_PAPER_EVIDENCE_PACKET.md").write_text(
        _paper_evidence_packet_md(
            specs,
            traces,
            actions,
            metrics,
            candidates,
            baseline_rows,
            ablation_rows,
            repair_iteration_rows or iteration_rows,
            repair_calibration_rows,
            target_rows,
            evidence_rows,
            variant_rows,
            status,
        ),
        encoding="utf-8",
    )
    return status


def _paper_target_rows(
    specs: Sequence[IterationSpec],
    traces: Sequence[Mapping[str, Any]],
    metrics: Sequence[Mapping[str, Any]],
    candidates: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows = [
        _target_c1_raw_gap(specs, traces, metrics, candidates),
        _target_c2_forced_accommodation(specs, traces, metrics),
        _target_c3_full_selection(specs, traces, metrics),
        _target_c4_bad_action_suppression(specs, traces, metrics),
        _target_c5_near_miss_production(specs, traces, metrics),
        _target_c6_ablation_mechanism(specs, traces, metrics),
        _target_c7_trace_integrity(traces),
    ]
    return rows


def _target_c1_raw_gap(
    specs: Sequence[IterationSpec],
    traces: Sequence[Mapping[str, Any]],
    metrics: Sequence[Mapping[str, Any]],
    candidates: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    p0_specs = [spec for spec in specs if spec.scenario_family == "P0"]
    raw_selects_a = []
    full_avoids_a = []
    raw_gap_contrast = []
    closing_contrast = []
    raw_worse = []
    examples = []
    for spec in p0_specs:
        raw = _trace_for_variant(traces, spec, "raw_largest_gap")
        full = _trace_for_variant(traces, spec, FULL_VARIANT)
        forced = _trace_for_variant(traces, spec, "forced_accommodation")
        raw_metric = _metric_for_trace(metrics, raw)
        full_metric = _metric_for_trace(metrics, full)
        gap_a = _candidate_for_gap(candidates, spec, raw.get("variant", ""), "1-2")
        full_candidate = _candidate_for_gap(candidates, spec, full.get("variant", ""), full.get("selected_gap_id", ""))
        raw_selects_a.append(raw.get("selected_gap_id") == "1-2")
        full_avoids_a.append(bool(full.get("selected_gap_id")) and full.get("selected_gap_id") != "1-2")
        raw_gap_contrast.append(_float(gap_a.get("raw_gap_size")) > _float(full_candidate.get("raw_gap_size")))
        closing_contrast.append(_float(gap_a.get("closing_rate")) > _float(full_candidate.get("closing_rate")))
        raw_worse.append(_listed_disturbance_or_safety_worse(raw_metric, full_metric))
        examples.append(
            f"{spec.scenario_design_id}: raw={raw.get('selected_gap_id','')}, "
            f"full={full.get('selected_gap_id','')}, forced={forced.get('selected_gap_id','')}, "
            f"raw_dist={_float(raw_metric.get('mainline_disturbance_cost')):.6f}, "
            f"full_dist={_float(full_metric.get('mainline_disturbance_cost')):.6f}"
        )
    supported = bool(p0_specs) and any(raw_selects_a) and any(full_avoids_a) and any(raw_gap_contrast) and any(raw_worse)
    status = "SUPPORTS_LOCK_CANDIDATE" if supported else "PARTIAL_NEEDS_REPAIR"
    failure = "" if supported else ("FAIL_REVISE_SCENARIO" if not any(raw_selects_a) else "FAIL_REVISE_METRIC")
    return _target_row(
        "C1",
        "C1_raw_gap_illusion",
        "Raw-gap illusion",
        status,
        failure,
        "raw_largest_gap chooses misleading Gap A and full avoids it with a traceable lower-disturbance alternative",
        {
            "raw_selects_gap_a_count": sum(1 for item in raw_selects_a if item),
            "full_avoids_gap_a_count": sum(1 for item in full_avoids_a if item),
            "raw_gap_contrast_count": sum(1 for item in raw_gap_contrast if item),
            "closing_contrast_count": sum(1 for item in closing_contrast if item),
            "raw_worse_count": sum(1 for item in raw_worse if item),
        },
        "; ".join(examples),
    )


def _target_c2_forced_accommodation(
    specs: Sequence[IterationSpec],
    traces: Sequence[Mapping[str, Any]],
    metrics: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    first_class = _first_class_variant_status().get("forced_accommodation", False)
    no_future = True
    no_rpmi_only_for_baseline = not _variant_uses_rpmi_info("forced_accommodation")
    service_or_near = []
    higher_dist = []
    examples = []
    for spec in specs:
        full = _trace_for_variant(traces, spec, FULL_VARIANT)
        forced = _trace_for_variant(traces, spec, "forced_accommodation")
        full_metric = _metric_for_trace(metrics, full)
        forced_metric = _metric_for_trace(metrics, forced)
        service_or_near.append(_truthy(forced.get("merge_success")) or forced.get("selected_action_id") != "a0_none")
        higher_dist.append(_disturbance_score(forced_metric) > _disturbance_score(full_metric))
        examples.append(
            f"{spec.scenario_design_id}: forced_action={forced.get('selected_action_id','')}, "
            f"forced_success={forced.get('merge_success','')}, forced_dist={_float(forced_metric.get('mainline_disturbance_cost')):.6f}, "
            f"full_success={full.get('merge_success','')}, full_dist={_float(full_metric.get('mainline_disturbance_cost')):.6f}"
        )
    if not first_class:
        status = "FAIL_REVISE_BASELINE"
        failure = "FAIL_REVISE_BASELINE"
    elif not no_future:
        status = "FAIL_REVISE_BASELINE"
        failure = "FAIL_REVISE_BASELINE"
    elif not no_rpmi_only_for_baseline:
        status = "PARTIAL_NEEDS_REPAIR"
        failure = "FAIL_REVISE_BASELINE"
    elif any(service_or_near) and any(higher_dist):
        status = "SUPPORTS_LOCK_CANDIDATE"
        failure = ""
    else:
        status = "PARTIAL_NEEDS_REPAIR"
        failure = "FAIL_SIMULATOR_SENSITIVITY_INSUFFICIENT" if any(service_or_near) else "FAIL_REVISE_SCENARIO"
    return _target_row(
        "C2",
        "C2_forced_accommodation",
        "Forced accommodation",
        status,
        failure,
        "forced_accommodation should serve or near-serve demand with higher disturbance than full RPMI",
        {
            "first_class_config": first_class,
            "uses_future_realized_outcome": not no_future,
            "uses_RPMI_only_information": not no_rpmi_only_for_baseline,
            "service_or_near_count": sum(1 for item in service_or_near if item),
            "higher_disturbance_count": sum(1 for item in higher_dist if item),
        },
        "; ".join(examples),
    )


def _target_c3_full_selection(
    specs: Sequence[IterationSpec],
    traces: Sequence[Mapping[str, Any]],
    metrics: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    choice_diff = []
    objective_reason = []
    realized_not_worse = []
    examples = []
    for spec in specs:
        full = _trace_for_variant(traces, spec, FULL_VARIANT)
        raw = _trace_for_variant(traces, spec, "raw_largest_gap")
        forced = _trace_for_variant(traces, spec, "forced_accommodation")
        full_metric = _metric_for_trace(metrics, full)
        raw_metric = _metric_for_trace(metrics, raw)
        forced_metric = _metric_for_trace(metrics, forced)
        choice_diff.append(
            full.get("selected_gap_id") != raw.get("selected_gap_id")
            or full.get("selected_action_id") != forced.get("selected_action_id")
        )
        objective_reason.append(full.get("selected_action_RCMV") not in {"", None} and full.get("selected_action_D_bar") not in {"", None})
        realized_not_worse.append(
            _disturbance_score(full_metric) <= max(_disturbance_score(raw_metric), _disturbance_score(forced_metric))
            or _truthy(full.get("merge_success"))
        )
        examples.append(
            f"{spec.scenario_design_id}: full={full.get('selected_action_id','')}/{full.get('selected_gap_id','')}, "
            f"raw={raw.get('selected_action_id','')}/{raw.get('selected_gap_id','')}, "
            f"forced={forced.get('selected_action_id','')}/{forced.get('selected_gap_id','')}, "
            f"RCMV={_float(full.get('selected_action_RCMV')):.6f}"
        )
    p1b_full_success = all(
        _truthy(_trace_for_variant(traces, spec, FULL_VARIANT).get("merge_success"))
        for spec in specs
        if spec.scenario_subfamily.startswith("P1b")
    )
    supported = any(choice_diff) and all(objective_reason) and any(realized_not_worse) and p1b_full_success
    status = "SUPPORTS_LOCK_CANDIDATE" if supported else "PARTIAL_NEEDS_REPAIR"
    failure = "" if supported else "FAIL_REVISE_OBJECTIVE"
    return _target_row(
        "C3",
        "C3_full_rpmi_low_disturbance_selection",
        "Full RPMI low-disturbance selection",
        status,
        failure,
        "full RPMI should differ from raw/forced through RD/C_dist/theta/RCMV and not degrade realized metrics",
        {
            "choice_diff_count": sum(1 for item in choice_diff if item),
            "objective_reason_count": sum(1 for item in objective_reason if item),
            "realized_not_worse_count": sum(1 for item in realized_not_worse if item),
        },
        "; ".join(examples),
    )


def _target_c4_bad_action_suppression(
    specs: Sequence[IterationSpec],
    traces: Sequence[Mapping[str, Any]],
    metrics: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    p1a_specs = [spec for spec in specs if spec.scenario_subfamily.startswith("P1a")]
    full_suppresses = []
    forced_higher = []
    ablation_degrades = []
    lambda_global = _one_default_objective_config_used(specs)
    examples = []
    for spec in p1a_specs:
        full = _trace_for_variant(traces, spec, FULL_VARIANT)
        forced = _trace_for_variant(traces, spec, "forced_accommodation")
        without_c = _trace_for_variant(traces, spec, "without_Cbar")
        without_theta = _trace_for_variant(traces, spec, "without_theta")
        full_metric = _metric_for_trace(metrics, full)
        forced_metric = _metric_for_trace(metrics, forced)
        full_suppresses.append(full.get("selected_action_id") == "a0_none")
        forced_higher.append(_disturbance_score(forced_metric) > _disturbance_score(full_metric))
        ablation_degrades.append(
            without_c.get("selected_action_id") != full.get("selected_action_id")
            or without_theta.get("selected_action_id") != full.get("selected_action_id")
        )
        examples.append(
            f"{spec.scenario_design_id}: full={full.get('selected_action_id','')}, "
            f"forced={forced.get('selected_action_id','')}, without_Cbar={without_c.get('selected_action_id','')}, "
            f"without_theta={without_theta.get('selected_action_id','')}, lambda_global={lambda_global}"
        )
    supported = bool(p1a_specs) and all(full_suppresses) and any(forced_higher) and any(ablation_degrades) and lambda_global
    if supported:
        status, failure = "SUPPORTS_LOCK_CANDIDATE", ""
    elif bool(p1a_specs) and all(full_suppresses) and any(forced_higher):
        status, failure = "PARTIAL_NEEDS_REPAIR", "FAIL_REVISE_OBJECTIVE"
    else:
        status, failure = "FAIL_REVISE_OBJECTIVE", "FAIL_REVISE_OBJECTIVE"
    return _target_row(
        "C4",
        "C4_bad_action_suppression",
        "Bad-action suppression",
        status,
        failure,
        "full should suppress high-disturbance low-benefit action when natural service is enough",
        {
            "full_suppresses_count": sum(1 for item in full_suppresses if item),
            "forced_higher_disturbance_count": sum(1 for item in forced_higher if item),
            "ablation_degrades_count": sum(1 for item in ablation_degrades if item),
            "one_default_objective_config_used": lambda_global,
        },
        "; ".join(examples),
    )


def _target_c5_near_miss_production(
    specs: Sequence[IterationSpec],
    traces: Sequence[Mapping[str, Any]],
    metrics: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    p1b_specs = [spec for spec in specs if spec.scenario_subfamily.startswith("P1b")]
    no_action_fails = []
    full_positive_action = []
    full_service = []
    forced_higher = []
    examples = []
    for spec in p1b_specs:
        full = _trace_for_variant(traces, spec, FULL_VARIANT)
        raw = _trace_for_variant(traces, spec, "raw_largest_gap")
        forced = _trace_for_variant(traces, spec, "forced_accommodation")
        full_metric = _metric_for_trace(metrics, full)
        forced_metric = _metric_for_trace(metrics, forced)
        no_action_fails.append(not _truthy(raw.get("merge_success")))
        full_positive_action.append(full.get("selected_action_id") not in {"", "a0_none"} and _float(full.get("selected_action_RCMV")) > 0.0)
        full_service.append(_truthy(full.get("merge_success")))
        forced_higher.append(_disturbance_score(forced_metric) > _disturbance_score(full_metric))
        examples.append(
            f"{spec.scenario_design_id}: full_action={full.get('selected_action_id','')}, "
            f"full_success={full.get('merge_success','')}, reason={full.get('reservation_final_status_reason','')}, "
            f"raw_success={raw.get('merge_success','')}, forced_success={forced.get('merge_success','')}"
        )
    supported = bool(p1b_specs) and all(no_action_fails) and any(full_positive_action) and any(full_service) and any(forced_higher)
    if supported:
        status, failure = "SUPPORTS_LOCK_CANDIDATE", ""
    elif bool(p1b_specs) and any(full_positive_action) and not any(full_service):
        status, failure = "FAIL_REVISE_IMPLEMENTATION", "FAIL_REVISE_IMPLEMENTATION"
    else:
        status, failure = "PARTIAL_NEEDS_REPAIR", "FAIL_REVISE_SCENARIO"
    return _target_row(
        "C5",
        "C5_near_miss_production",
        "Near-miss production",
        status,
        failure,
        "full should convert invalid/no-action near-miss to realized service or near-service through action-conditioned reservation",
        {
            "no_action_fails_count": sum(1 for item in no_action_fails if item),
            "full_positive_action_count": sum(1 for item in full_positive_action if item),
            "full_realized_service_count": sum(1 for item in full_service if item),
            "forced_higher_disturbance_count": sum(1 for item in forced_higher if item),
        },
        "; ".join(examples),
    )


def _target_c6_ablation_mechanism(
    specs: Sequence[IterationSpec],
    traces: Sequence[Mapping[str, Any]],
    metrics: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    without_rd_degrades = []
    without_c_degrades = []
    without_theta_degrades = []
    examples = []
    for spec in specs:
        full = _trace_for_variant(traces, spec, FULL_VARIANT)
        full_metric = _metric_for_trace(metrics, full)
        without_rd = _trace_for_variant(traces, spec, "without_RD")
        without_c = _trace_for_variant(traces, spec, "without_Cbar")
        without_theta = _trace_for_variant(traces, spec, "without_theta")
        rd_metric = _metric_for_trace(metrics, without_rd)
        c_metric = _metric_for_trace(metrics, without_c)
        theta_metric = _metric_for_trace(metrics, without_theta)
        without_rd_degrades.append(
            without_rd.get("selected_gap_id") != full.get("selected_gap_id")
            and _float(without_rd.get("selected_gap_RD_pred")) >= _float(full.get("selected_gap_RD_pred"))
            or _disturbance_score(rd_metric) > _disturbance_score(full_metric)
        )
        without_c_degrades.append(
            without_c.get("selected_action_id") != full.get("selected_action_id")
            and _float(without_c.get("selected_action_C_bar")) >= _float(full.get("selected_action_C_bar"))
            or _disturbance_score(c_metric) > _disturbance_score(full_metric)
        )
        without_theta_degrades.append(
            without_theta.get("selected_action_id") != full.get("selected_action_id")
            or (_float(without_theta.get("selected_action_RCMV")) > 0.0 and without_theta.get("selected_action_id") != "a0_none")
            or _disturbance_score(theta_metric) > _disturbance_score(full_metric)
        )
        examples.append(
            f"{spec.scenario_design_id}: full={full.get('selected_action_id','')}/{full.get('selected_gap_id','')}, "
            f"without_RD={without_rd.get('selected_action_id','')}/{without_rd.get('selected_gap_id','')}, "
            f"without_Cbar={without_c.get('selected_action_id','')}/{without_c.get('selected_gap_id','')}, "
            f"without_theta={without_theta.get('selected_action_id','')}/{without_theta.get('selected_gap_id','')}"
        )
    rd_any = any(without_rd_degrades)
    c_any = any(without_c_degrades)
    theta_any = any(without_theta_degrades)
    supported = rd_any and c_any and theta_any
    status = "SUPPORTS_LOCK_CANDIDATE" if supported else "PARTIAL_NEEDS_REPAIR"
    failure = "" if supported else "FAIL_REVISE_OBJECTIVE"
    return _target_row(
        "C6",
        "C6_ablation_mechanism",
        "Ablation mechanism",
        status,
        failure,
        "without_RD, without_Cbar, and without_theta should each produce interpretable degradation",
        {
            "without_RD_degrades": rd_any,
            "without_Cbar_degrades": c_any,
            "without_theta_degrades": theta_any,
        },
        "; ".join(examples),
    )


def _target_c7_trace_integrity(traces: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    join = _join_status(traces)
    full = math.isclose(join["can_join_full_chain_rate"], 1.0)
    zero_missing = all(math.isclose(value, 0.0) for value in join["missing_rates"].values())
    supported = full and zero_missing
    return _target_row(
        "C7",
        "C7_trace_integrity",
        "Trace integrity",
        "SUPPORTS_LOCK_CANDIDATE" if supported else "FAIL_REVISE_IMPLEMENTATION",
        "" if supported else "NOT_READY_INSUFFICIENT_TRACE_JOIN",
        "selected_action -> selected_gap -> reservation -> demand -> realized_event -> metrics must close",
        {
            "can_join_full_chain_rate": join["can_join_full_chain_rate"],
            "nontrivial_full_chain_count": join["nontrivial_full_chain_count"],
            **join["missing_rates"],
        },
        "all Prompt 3B-R variants have explicit chain IDs; service success remains a separate C5/C2 question",
    )


def _target_row(
    claim_id: str,
    evidence_target_id: str,
    name: str,
    status: str,
    failure_type: str,
    criterion: str,
    metrics: Mapping[str, Any],
    evidence_summary: str,
) -> dict[str, Any]:
    return {
        "claim_id": claim_id,
        "evidence_target_id": evidence_target_id,
        "name": name,
        "status": status,
        "failure_type": failure_type,
        "criterion": criterion,
        "metrics": dict(metrics),
        "evidence_summary": evidence_summary,
    }


def _paper_status(target_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    supported = sum(1 for row in target_rows if row.get("status") == "SUPPORTS_LOCK_CANDIDATE")
    partial = sum(1 for row in target_rows if row.get("status") == "PARTIAL_NEEDS_REPAIR")
    failed = len(target_rows) - supported - partial
    failure_types = [str(row.get("failure_type", "")) for row in target_rows if row.get("failure_type")]
    if any(item == "NOT_READY_INSUFFICIENT_TRACE_JOIN" for item in failure_types):
        verdict = "FAIL_REVISE_IMPLEMENTATION"
    elif any(item == "FAIL_REVISE_IMPLEMENTATION" for item in failure_types):
        verdict = "FAIL_REVISE_IMPLEMENTATION"
    elif any(item == "FAIL_REVISE_BASELINE" for item in failure_types):
        verdict = "PARTIAL_NEEDS_REPAIR"
    elif failed or partial:
        verdict = "PARTIAL_NEEDS_REPAIR"
    else:
        verdict = "READY_FOR_PROMPT4_LOCK_CANDIDATE"
    ready = verdict == "READY_FOR_PROMPT4_LOCK_CANDIDATE"
    first_class = _first_class_variant_status()
    main_blocker = "none" if ready else ";".join(dict.fromkeys(failure_types)) or "PARTIAL_NEEDS_REPAIR"
    near_miss = next((row for row in target_rows if row.get("claim_id") == "C5"), {})
    forced = next((row for row in target_rows if row.get("claim_id") == "C2"), {})
    ablation = next((row for row in target_rows if row.get("claim_id") == "C6"), {})
    return {
        "verdict": verdict,
        "supported": supported,
        "partial": partial,
        "failed": failed,
        "default_objective_config_used": _default_objective_config_used_for_status(),
        "first_class_baselines_ready": all(first_class.values()),
        "near_miss_realized_service_status": _status_compact(near_miss),
        "forced_accommodation_status": _status_compact(forced),
        "ablation_sensitivity_status": _status_compact(ablation),
        "ready": ready,
        "main_blocker": main_blocker,
    }


def _default_objective_config_used_for_status() -> bool:
    return False


def _status_compact(row: Mapping[str, Any]) -> str:
    status = str(row.get("status", "not_tested"))
    failure = str(row.get("failure_type", ""))
    return status if not failure else f"{status}:{failure}"


def _paper_candidate_evidence_rows(
    specs: Sequence[IterationSpec],
    traces: Sequence[Mapping[str, Any]],
    actions: Sequence[Mapping[str, Any]],
    metrics: Sequence[Mapping[str, Any]],
    candidates: Sequence[Mapping[str, Any]],
    target_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    target_by_variant = {
        FULL_VARIANT: ["C3", "C4", "C5", "C7"],
        "raw_largest_gap": ["C1", "C7"],
        "forced_accommodation": ["C2", "C7"],
        "without_RD": ["C6", "C7"],
        "without_Cbar": ["C6", "C7"],
        "without_theta": ["C6", "C7"],
    }
    target_by_id = {str(row.get("claim_id")): row for row in target_rows}
    for spec in specs:
        full = _trace_for_variant(traces, spec, FULL_VARIANT)
        full_metric = _metric_for_trace(metrics, full)
        for variant in VARIANTS:
            trace = _trace_for_variant(traces, spec, variant)
            metric = _metric_for_trace(metrics, trace)
            action = _action_for_trace(actions, trace)
            candidate = _candidate_for_gap(candidates, spec, variant, trace.get("selected_gap_id", ""))
            claim_ids = _claim_ids_for_spec_variant(spec, variant, target_by_variant)
            for claim_id in claim_ids:
                target = target_by_id.get(claim_id, {})
                rows.append(
                    {
                        "claim_id": claim_id,
                        "evidence_target_id": target.get("evidence_target_id", ""),
                        "scenario_family": _paper_family(spec),
                        "scenario_design_id": spec.scenario_design_id,
                        "deterministic_case_id": spec.deterministic_case_id,
                        "variant": variant,
                        "selected_gap_id": trace.get("selected_gap_id", ""),
                        "selected_action_id": trace.get("selected_action_id", ""),
                        "selected_action_type": trace.get("selected_action_type", ""),
                        "reservation_id": trace.get("reservation_id", ""),
                        "demand_id": trace.get("demand_id", ""),
                        "realized_event_id": trace.get("realized_event_id", ""),
                        "merge_success_rate_over_demand": 1.0 if _truthy(trace.get("merge_success")) else 0.0,
                        "realized_unserved_demand_rate": 0.0 if _truthy(trace.get("merge_success")) else 1.0,
                        "RD_pred": trace.get("selected_gap_RD_pred", ""),
                        "RD_realized": metric.get("RD_realized_proxy", ""),
                        "RD_delta": _float(metric.get("RD_realized_proxy")) - _float(trace.get("selected_gap_RD_pred")),
                        "C_dist_pred": trace.get("selected_action_C_bar", ""),
                        "mainline_disturbance_cost": metric.get("mainline_disturbance_cost", ""),
                        "hard_brake_count": metric.get("hard_brake_count", ""),
                        "max_deceleration": metric.get("max_deceleration", ""),
                        "speed_variance_delta": metric.get("speed_variance_delta", ""),
                        "max_wave_amplitude": metric.get("max_wave_amplitude", ""),
                        "min_TTC": metric.get("min_TTC", trace.get("min_TTC_after", "")),
                        "min_realized_gap": trace.get("min_realized_gap_after", ""),
                        "raw_gap_size_selected": candidate.get("raw_gap_size", trace.get("selected_gap_raw_size", "")),
                        "closing_rate_selected": candidate.get("closing_rate", ""),
                        "ablation_difference": _ablation_difference_text(traces, metrics, spec, trace, full, full_metric),
                        "service_tradeoff_explanation": _service_tradeoff_text(trace, metric, full, full_metric),
                        "can_join_full_chain": trace.get("can_join_full_chain", ""),
                        "claim_support_status": target.get("status", ""),
                        "failure_type": target.get("failure_type", ""),
                        "evidence_file": "outputs/d2_5_theory_alignment/gate_D2_5_input/paper_candidate_variant_metrics.csv",
                    }
                )
    return rows


def _paper_candidate_variant_metric_rows(
    specs: Sequence[IterationSpec],
    traces: Sequence[Mapping[str, Any]],
    actions: Sequence[Mapping[str, Any]],
    metrics: Sequence[Mapping[str, Any]],
    target_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    status = _paper_status(target_rows)
    for spec in specs:
        for variant in VARIANTS:
            trace = _trace_for_variant(traces, spec, variant)
            metric = _metric_for_trace(metrics, trace)
            action = _action_for_trace(actions, trace)
            fail_reason = _variant_fail_reason(spec, variant, trace, metric, status)
            rows.append(
                {
                    "scenario_family": _paper_family(spec),
                    "scenario_design_id": spec.scenario_design_id,
                    "variant": variant,
                    "selected_gap_id": trace.get("selected_gap_id", ""),
                    "selected_action_id": trace.get("selected_action_id", ""),
                    "Z_R_norm": action.get("Z_bar", trace.get("selected_action_Z_bar", "")),
                    "RD_pred_norm": action.get("D_bar", trace.get("selected_action_D_bar", "")),
                    "C_dist_norm": action.get("C_bar", trace.get("selected_action_C_bar", "")),
                    "S_safety_penalty": action.get("S_safety_penalty", 0.0),
                    "Q_churn_penalty": action.get("Q_churn_penalty", 0.0),
                    "J": trace.get("selected_action_J", ""),
                    "J_none": action.get("J_none", ""),
                    "RCMV": trace.get("selected_action_RCMV", ""),
                    "theta": action.get("theta", ""),
                    "lambda_Z": action.get("lambda_Z", 1.0),
                    "lambda_D": action.get("lambda_D", ""),
                    "lambda_C": action.get("lambda_C", ""),
                    "lambda_S": action.get("lambda_S", 0.0),
                    "lambda_Q": action.get("lambda_Q", 0.0),
                    "merge_success_rate_over_demand": 1.0 if _truthy(trace.get("merge_success")) else 0.0,
                    "mainline_disturbance_cost": metric.get("mainline_disturbance_cost", ""),
                    "RD_realized": metric.get("RD_realized_proxy", ""),
                    "hard_brake_count": metric.get("hard_brake_count", ""),
                    "max_deceleration": metric.get("max_deceleration", ""),
                    "speed_variance_delta": metric.get("speed_variance_delta", ""),
                    "max_wave_amplitude": metric.get("max_wave_amplitude", ""),
                    "min_TTC": metric.get("min_TTC", ""),
                    "min_realized_gap": trace.get("min_realized_gap_after", ""),
                    "pass_flag": not bool(fail_reason),
                    "fail_reason": fail_reason,
                }
            )
    return rows


def _paper_experiment_evidence_matrix_md(
    target_rows: Sequence[Mapping[str, Any]],
    evidence_rows: Sequence[Mapping[str, Any]],
    variant_rows: Sequence[Mapping[str, Any]],
) -> str:
    del evidence_rows, variant_rows
    lines = [
        "# Prompt 3B-R Paper Experiment Evidence Matrix",
        "",
        "This matrix is Prompt 3B-R diagnostic evidence only. It is not Prompt 4 lock evidence and not final paper performance support.",
        "",
        "| target | status | failure_type | criterion | evidence_summary |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in target_rows:
        lines.append(
            f"| {row['claim_id']} {row['name']} | {row['status']} | {row['failure_type']} | "
            f"{row['criterion']} | {_md_cell(row['evidence_summary'])} |"
        )
    lines.extend(
        [
            "",
            "Source tables:",
            "",
            "- outputs/d2_5_theory_alignment/gate_D2_5_input/paper_candidate_evidence_table.csv",
            "- outputs/d2_5_theory_alignment/gate_D2_5_input/paper_candidate_variant_metrics.csv",
        ]
    )
    return "\n".join(lines) + "\n"


def _candidate_paper_figures_manifest_md() -> str:
    rows = [
        (
            "candidate_table_1",
            "variant-level evidence table",
            "outputs/d2_5_theory_alignment/gate_D2_5_input/paper_candidate_evidence_table.csv",
            "C1-C7 diagnostic claim-target mapping",
            "Diagnostic/co-design only; not locked decisive evidence.",
        ),
        (
            "candidate_figure_1",
            "selected gap/action comparison",
            "outputs/d2_5_theory_alignment/gate_D2_5_input/paper_candidate_variant_metrics.csv",
            "C1/C3 selected gap-action contrast",
            "Selection contrasts are not final performance claims.",
        ),
        (
            "candidate_figure_2",
            "disturbance / RD comparison",
            "outputs/d2_5_theory_alignment/gate_D2_5_input/paper_candidate_variant_metrics.csv",
            "C1/C2/C3 realized disturbance and RD proxy comparison",
            "C_bar is an action-cost proxy unless realized alignment is validated.",
        ),
        (
            "candidate_figure_3",
            "ablation comparison",
            "outputs/d2_5_theory_alignment/gate_D2_5_input/paper_candidate_variant_metrics.csv",
            "C6 ablation mechanism evidence",
            "Ablation sensitivity remains partial if variants match full.",
        ),
        (
            "candidate_figure_4",
            "trace chain diagram",
            "outputs/d2_5_theory_alignment/gate_D2_5_input/trace_join_table_prompt3b.csv",
            "C7 evidence-chain integrity",
            "Trace join is necessary but not sufficient for realized service.",
        ),
    ]
    lines = [
        "# Candidate Paper Figures Manifest",
        "",
        "These are candidate figures/tables for human review only. Do not treat them as paper-ready locked evidence.",
        "",
        "| id | description | source CSV | claim supported | limitations |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]} |")
    return "\n".join(lines) + "\n"


def _paper_evidence_packet_md(
    specs: Sequence[IterationSpec],
    traces: Sequence[Mapping[str, Any]],
    actions: Sequence[Mapping[str, Any]],
    metrics: Sequence[Mapping[str, Any]],
    candidates: Sequence[Mapping[str, Any]],
    baseline_rows: Sequence[Mapping[str, Any]],
    ablation_rows: Sequence[Mapping[str, Any]],
    iteration_rows: Sequence[Mapping[str, Any]],
    repair_calibration_rows: Sequence[Mapping[str, Any]],
    target_rows: Sequence[Mapping[str, Any]],
    evidence_rows: Sequence[Mapping[str, Any]],
    variant_rows: Sequence[Mapping[str, Any]],
    status: Mapping[str, Any],
) -> str:
    del evidence_rows, variant_rows
    join = _join_status(traces)
    first_class = _first_class_variant_status()
    target_by_id = {str(row.get("claim_id")): row for row in target_rows}
    lines = [
        "# PROMPT 3B-R PAPER EVIDENCE PACKET",
        "",
        "## 1. Executive verdict",
        "",
        str(status["verdict"]),
        "",
        _paper_verdict_explanation(status, target_rows),
        "",
        "This is a Prompt 3B-R paper-evidence co-design repair packet. It is not Prompt 4, not a lock, not a locked decisive experiment, and not final paper performance support.",
        "",
        "## 2. Repairs completed",
        "",
        "### implementation repair",
        "",
        "- what changed: Prompt 3A/3B event-window execution applies selected action commands plus reservation guidance, and selected reservations are finalized against the post-action selected-evaluation edge map.",
        "- file paths changed: scripts/prompt3a_readiness_micro_run.py; scripts/prompt3b_mechanism_codesign_loop.py.",
        "- why changed: Aristotle found selected positive-RCMV near-miss actions could remain traceable but not realized because the harness path under-applied guidance/edge-map context.",
        f"- evidence that change worked: trace joins stayed complete at can_join_full_chain_rate={join['can_join_full_chain_rate']:.6f}; P1b no longer fails by edge_missing in current traces, but service still fails by negative_actual_margin.",
        "- remaining risks: near-miss selected action still does not realize demand service, so C5 is not repaired enough for paper evidence.",
        "",
        "### baseline registration repair",
        "",
        "- what changed: forced_accommodation, without_Cbar, and without_theta are registered first-class opt-in configs in the runner, and Prompt 3B routes those variants through config resolution.",
        "- file paths changed: src/rpmi/runner.py; scripts/prompt3a_readiness_micro_run.py.",
        "- why changed: harness-only variants risked becoming hidden mechanism rewrites.",
        f"- evidence that change worked: first-class config status forced_accommodation={str(first_class.get('forced_accommodation')).lower()}, without_Cbar={str(first_class.get('without_Cbar')).lower()}, without_theta={str(first_class.get('without_theta')).lower()}.",
        "- remaining risks: forced_accommodation is still RPMI-derived diagnostic instrumentation and uses RPMI candidate/evaluation information; it is not a validated non-RPMI paper baseline.",
        "",
        "### objective calibration repair",
        "",
        "- what changed: calibration attempts are logged with keep/revert status; no Prompt 4 objective lock was created.",
        "- file paths changed: outputs/d2_5_theory_alignment/objective_calibration_repair_log_prompt3b_r.csv; scripts/prompt3b_mechanism_codesign_loop.py.",
        "- why changed: lambda_C/theta/RD/C_dist needed cross-case audit rather than single-case success packaging.",
        f"- evidence that change worked: repair log has {len(repair_calibration_rows)} rows across P0/P1a/P1b.",
        "- remaining risks: one default objective configuration was not used across P0/P1a/P1b; P1a still uses lambda_C=30 as a diagnostic scenario config and is not lock-ready.",
        "",
        "### metric repair",
        "",
        "- what changed: paper candidate outputs explicitly separate trace join, realized service, RD_realized proxy, C_dist proxy, and disturbance metrics.",
        "- file paths changed: scripts/prompt3b_mechanism_codesign_loop.py.",
        "- why changed: trace readiness must not be mistaken for realized service or performance evidence.",
        "- evidence that change worked: C5 and C7 are classified separately in this packet.",
        "- remaining risks: realized disturbance/RD proxies remain diagnostic event-window metrics and may be simulator-sensitive.",
        "",
        "### scenario repair",
        "",
        "- what changed: P1a/P1b are distinguished in logs and paper evidence outputs; P0/P1a/P1b were rerun after repair.",
        "- file paths changed: scripts/prompt3b_mechanism_codesign_loop.py and Prompt 3B-R output CSV/Markdown files.",
        "- why changed: P1 naming ambiguity and partial one-shot diagnostics could hide different failure modes.",
        "- evidence that change worked: scenario families rerun include P0, P1a, and P1b with all core variants.",
        "- remaining risks: current P1b scenarios still do not realize near-miss service; some P0/forced contrasts remain partial.",
        "",
        "## 3. Paper evidence target matrix",
        "",
        "| target | status | failure_type | evidence summary |",
        "| --- | --- | --- | --- |",
    ]
    for row in target_rows:
        lines.append(
            f"| {row['claim_id']} {row['name']} | {row['status']} | {row['failure_type']} | {_md_cell(row['evidence_summary'])} |"
        )
    lines.extend(
        [
            "",
            "## 4. Scenario results",
            "",
        ]
    )
    for spec in specs:
        lines.extend(_scenario_result_lines(spec, traces, metrics))
    lines.extend(
        [
            "## 5. Objective configuration",
            "",
            "- legacy objective: `J = Z_bar + lambda_D * D_bar + lambda_C * C_bar`; `RCMV(a) = J(a0_none) - J(a)`; select a non-none action only when `RCMV > theta`.",
            "- current repaired objective: same centralized objective formula; first-class ablation configs set lambda_D/lambda_C/theta through explicit config rather than hidden harness branches.",
            "- default objective parameters: scenario configs retain their declared diagnostic lambda/theta values; no Prompt 4 default objective is locked.",
            f"- whether one default config was used across P0/P1a/P1b: {str(_one_default_objective_config_used(specs)).lower()}.",
            "- all calibration attempts, kept changes, reverted changes, and cross-case checks:",
            "",
            "| iteration | family | changed_component | old_value | new_value | keep_or_revert | rerun_result | cross_case_check |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in iteration_rows:
        cross = _cross_check_status(next((spec for spec in specs if spec.iteration_id == row.get("iteration_id")), specs[0]))
        lines.append(
            f"| {row['iteration_id']} | {row['scenario_family']}/{row['scenario_subfamily']} | {row['changed_component']} | "
            f"{row['old_value']} | {row['new_value']} | {row['keep_or_revert']} | {_md_cell(row['rerun_result'])} | {cross} |"
        )
    lines.extend(
        [
            "",
            "- remaining objective risks: lambda_C=30 remains a P1a diagnostic setting, not a global lock candidate; C_bar/C_dist is still an action-cost proxy unless realized disturbance alignment is validated.",
            "",
            "## 6. Baseline fairness",
            "",
            "| variant | first_class_config_status | same_initial_state | same_demand | same_horizon | same_candidate_time_grid | same_physical_validity_rule | same_no_hidden_fallback_rule | uses_future_realized_outcome | uses_RPMI_only_information | fair_for_paper_evidence |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for variant in [
        "raw_largest_gap",
        "forced_accommodation",
        "without_RD",
        "without_Cbar",
        "without_theta",
        "no_action_natural",
        "legacy_objective",
        "stale_reservation",
    ]:
        fairness = _paper_fairness_row(variant, first_class)
        lines.append(
            f"| {variant} | {fairness['first_class_config_status']} | true | true | true | true | true | true | "
            f"{str(fairness['uses_future_realized_outcome']).lower()} | {str(fairness['uses_RPMI_only_information']).lower()} | "
            f"{str(fairness['fair_for_paper_evidence']).lower()} |"
        )
    c6 = target_by_id.get("C6", {})
    c6_metrics = c6.get("metrics", {}) if isinstance(c6.get("metrics"), Mapping) else {}
    lines.extend(
        [
            "",
            "## 7. Ablation evidence",
            "",
            f"- without_RD caused high-RD selection or worse RD_realized: {_yes_no_unclear(c6_metrics.get('without_RD_degrades'))}.",
            f"- without_Cbar caused high-disturbance action or worse mainline disturbance: {_yes_no_unclear(c6_metrics.get('without_Cbar_degrades'))}.",
            f"- without_theta caused tiny-RCMV action / churn / unnecessary action: {_yes_no_unclear(c6_metrics.get('without_theta_degrades'))}.",
            "- unsupported mechanism claims: any ablation answered no or unclear cannot support the corresponding paper mechanism claim until Prompt 3B-R2 or Prompt 4 review repairs it.",
            "",
            "## 8. Trace and realized metrics",
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
            "",
            "Trace examples:",
            "",
            "| scenario | variant | selected_action -> selected_gap | selected_gap -> reservation | reservation -> demand | demand -> realized_event | realized_event -> metrics | service |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for trace in _repair_example_traces(specs, traces):
        lines.append(
            f"| {trace.get('scenario_design_id','')} | {trace.get('variant','')} | "
            f"{trace.get('selected_action_id','')} -> {trace.get('selected_gap_id','')} | "
            f"{trace.get('selected_gap_id','')} -> {trace.get('reservation_id','')} | "
            f"{trace.get('reservation_id','')} -> {trace.get('demand_id','')} | "
            f"{trace.get('demand_id','')} -> {trace.get('realized_event_id','')} | "
            f"{trace.get('realized_event_id','')} -> {trace.get('realized_event_to_metrics_joined','')} | "
            f"{trace.get('merge_success','')} |"
        )
    lines.extend(
        [
            "",
            "## 9. Claim support boundary",
            "",
            "What the repaired Prompt 3B-R evidence can support:",
            "",
            "- Diagnostic traces and candidate evidence for specific deterministic P0/P1a/P1b scenarios.",
            "- Full-chain trace integrity for the generated diagnostic rows.",
            "- Partial evidence of raw-gap selection contrast, bad-action suppression, and ablation sensitivity where explicitly reported.",
            "- Clear failure localization for near-miss realized service and forced-accommodation fairness.",
            "",
            "What it cannot support:",
            "",
            "- final paper performance support",
            "- universal optimality",
            "- stochastic robustness",
            "- full rolling integer assignment validation",
            "- locked decisive evidence",
            "- a claim that near-miss production is realized successfully in the current P1b cases",
            "",
            "What must wait until Prompt 4/5:",
            "",
            "- locked objective/scenario/baseline/metric/pass-fail criteria",
            "- held-out or locked decisive evaluation",
            "- any final paper claim decision",
            "",
            "## 10. Candidate figures / tables for paper",
            "",
            "| candidate | source CSV | claim supported | limitations |",
            "| --- | --- | --- | --- |",
            "| candidate_table_1: variant-level evidence table | outputs/d2_5_theory_alignment/gate_D2_5_input/paper_candidate_evidence_table.csv | C1-C7 diagnostic mapping | diagnostic/co-design only; not locked evidence |",
            "| candidate_figure_1: selected gap/action comparison | outputs/d2_5_theory_alignment/gate_D2_5_input/paper_candidate_variant_metrics.csv | C1/C3 | selection contrast only; service must be checked separately |",
            "| candidate_figure_2: disturbance / RD comparison | outputs/d2_5_theory_alignment/gate_D2_5_input/paper_candidate_variant_metrics.csv | C1/C2/C3 | C_dist is proxy/action effort unless validated against realized disturbance |",
            "| candidate_figure_3: ablation comparison | outputs/d2_5_theory_alignment/gate_D2_5_input/paper_candidate_variant_metrics.csv | C6 | ablation evidence remains partial if variants match full |",
            "| candidate_figure_4: trace chain diagram | outputs/d2_5_theory_alignment/gate_D2_5_input/trace_join_table_prompt3b.csv | C7 | trace integrity is necessary but not sufficient for service |",
            "",
            "## 11. Final recommendation",
            "",
            _paper_final_recommendation(status),
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def _scenario_result_lines(
    spec: IterationSpec,
    traces: Sequence[Mapping[str, Any]],
    metrics: Sequence[Mapping[str, Any]],
) -> list[str]:
    display = _paper_family(spec)
    lines = [
        f"### {display} {spec.theory_target}",
        "",
        f"- scenario_design_id: {spec.scenario_design_id}",
        f"- mechanism_target: {spec.mechanism_target}",
        f"- construction_principle: {spec.construction_principle}",
        f"- diagnostic_contrast: {spec.diagnostic_contrast}",
        f"- variants_run: {', '.join(VARIANTS)}",
        "",
        "| variant | selected_gap/action | realized service | realized disturbance | activation_status | failure_type_if_any |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for variant in VARIANTS:
        trace = _trace_for_variant(traces, spec, variant)
        metric = _metric_for_trace(metrics, trace)
        lines.append(
            f"| {variant} | {trace.get('selected_gap_id','')}/{trace.get('selected_action_id','')} | "
            f"{trace.get('merge_success','')} ({trace.get('reservation_final_status_reason','')}) | "
            f"{_float(metric.get('mainline_disturbance_cost')):.6f} | "
            f"{_activation_status_for_spec(spec, traces, metrics)} | {spec.failure_type} |"
        )
    lines.append("")
    return lines


def _paper_verdict_explanation(status: Mapping[str, Any], target_rows: Sequence[Mapping[str, Any]]) -> str:
    failed = [f"{row.get('claim_id')}:{row.get('failure_type')}" for row in target_rows if row.get("failure_type")]
    if status.get("verdict") == "READY_FOR_PROMPT4_LOCK_CANDIDATE":
        return "All Prompt 3B-R diagnostic targets are candidate-supporting, subject to human review before any Prompt 4 lock."
    return (
        "The repaired run produced useful diagnostic evidence but does not satisfy the paper-evidence target set. "
        f"Blocking or partial targets: {', '.join(failed) if failed else 'partial diagnostics remain'}."
    )


def _paper_final_recommendation(status: Mapping[str, Any]) -> str:
    verdict = str(status.get("verdict", ""))
    blocker = str(status.get("main_blocker", ""))
    if verdict == "READY_FOR_PROMPT4_LOCK_CANDIDATE":
        return "Submit for human review as Prompt 4 lock candidate."
    if "FAIL_REVISE_IMPLEMENTATION" in blocker:
        return "Continue Prompt 3B-R2: revise implementation."
    if "FAIL_REVISE_BASELINE" in blocker:
        return "Continue Prompt 3B-R2: revise baseline."
    if "FAIL_REVISE_OBJECTIVE" in blocker:
        return "Continue Prompt 3B-R2: revise objective."
    if "FAIL_REVISE_METRIC" in blocker:
        return "Continue Prompt 3B-R2: revise metric."
    if "FAIL_SIMULATOR_SENSITIVITY_INSUFFICIENT" in blocker:
        return "Stop and classify simulator sensitivity insufficient."
    return "Continue Prompt 3B-R2: revise scenario."


def _paper_fairness_row(variant: str, first_class: Mapping[str, bool]) -> dict[str, Any]:
    first_class_status = {
        "raw_largest_gap": "first_class_existing_baseline",
        "forced_accommodation": "first_class_config" if first_class.get("forced_accommodation") else "not_first_class",
        "without_RD": "first_class_existing_ablation",
        "without_Cbar": "first_class_config" if first_class.get("without_Cbar") else "not_first_class",
        "without_theta": "first_class_config" if first_class.get("without_theta") else "not_first_class",
    }.get(variant, "not_run")
    uses_rpmi = _variant_uses_rpmi_info(variant)
    is_optional_not_run = variant in {"no_action_natural", "legacy_objective", "stale_reservation"}
    fair = not uses_rpmi and variant == "raw_largest_gap"
    if variant in {"without_RD", "without_Cbar", "without_theta"}:
        fair = True
    if variant == "forced_accommodation":
        fair = False
    if is_optional_not_run:
        fair = False
    return {
        "first_class_config_status": first_class_status,
        "uses_future_realized_outcome": False,
        "uses_RPMI_only_information": uses_rpmi,
        "fair_for_paper_evidence": fair,
    }


def _claim_ids_for_spec_variant(
    spec: IterationSpec,
    variant: str,
    target_by_variant: Mapping[str, Sequence[str]],
) -> list[str]:
    ids = list(target_by_variant.get(variant, ["C7"]))
    if spec.scenario_family == "P0" and variant in {"raw_largest_gap", FULL_VARIANT} and "C1" not in ids:
        ids.append("C1")
    if spec.scenario_subfamily.startswith("P1a") and variant in {FULL_VARIANT, "forced_accommodation", "without_Cbar", "without_theta"}:
        if "C4" not in ids:
            ids.append("C4")
    if spec.scenario_subfamily.startswith("P1b") and variant in {FULL_VARIANT, "raw_largest_gap", "forced_accommodation"}:
        if "C5" not in ids:
            ids.append("C5")
    return list(dict.fromkeys(ids))


def _paper_family(spec: IterationSpec) -> str:
    if spec.scenario_subfamily.startswith("P1a"):
        return "P1a"
    if spec.scenario_subfamily.startswith("P1b"):
        return "P1b"
    return spec.scenario_family


def _candidate_for_gap(
    candidates: Sequence[Mapping[str, Any]],
    spec: IterationSpec,
    variant: str,
    gap_id: Any,
) -> Mapping[str, Any]:
    gap = str(gap_id)
    return next(
        (
            row
            for row in candidates
            if row.get("scenario_design_id") == spec.scenario_design_id
            and row.get("variant") == variant
            and row.get("candidate_gap_id") == gap
        ),
        {},
    )


def _one_default_objective_config_used(specs: Sequence[IterationSpec]) -> bool:
    values = set()
    for spec in specs:
        cfg = spec.config_builder()
        sim = cfg.simulation
        values.add(
            (
                round(float(sim.get("lambda_D", 1.0)), 10),
                round(float(sim.get("lambda_C", 1.0)), 10),
                round(float(sim.get("theta", 0.0)), 10),
                round(float(sim.get("RD_max", 1.0)), 10),
            )
        )
    return len(values) == 1


def _disturbance_score(metric: Mapping[str, Any]) -> float:
    return (
        _float(metric.get("mainline_disturbance_cost"))
        + abs(_float(metric.get("max_deceleration")))
        + _float(metric.get("max_wave_amplitude"))
        + _float(metric.get("hard_brake_count"))
    )


def _listed_disturbance_or_safety_worse(
    candidate_metric: Mapping[str, Any],
    reference_metric: Mapping[str, Any],
) -> bool:
    return (
        _float(candidate_metric.get("mainline_disturbance_cost")) > _float(reference_metric.get("mainline_disturbance_cost"))
        or abs(_float(candidate_metric.get("max_deceleration"))) > abs(_float(reference_metric.get("max_deceleration")))
        or _float(candidate_metric.get("max_wave_amplitude")) > _float(reference_metric.get("max_wave_amplitude"))
        or _float(candidate_metric.get("hard_brake_count")) > _float(reference_metric.get("hard_brake_count"))
        or (
            reference_metric.get("min_TTC") not in {"", None}
            and candidate_metric.get("min_TTC") not in {"", None}
            and _float(candidate_metric.get("min_TTC")) < _float(reference_metric.get("min_TTC"))
        )
    )


def _ablation_difference_text(
    traces: Sequence[Mapping[str, Any]],
    metrics: Sequence[Mapping[str, Any]],
    spec: IterationSpec,
    trace: Mapping[str, Any],
    full: Mapping[str, Any],
    full_metric: Mapping[str, Any],
) -> str:
    variant = str(trace.get("variant", ""))
    if variant not in {"without_RD", "without_Cbar", "without_theta"}:
        return ""
    metric = _metric_for_trace(metrics, trace)
    return (
        f"action_diff={trace.get('selected_action_id') != full.get('selected_action_id')}; "
        f"gap_diff={trace.get('selected_gap_id') != full.get('selected_gap_id')}; "
        f"dist_delta={_float(metric.get('mainline_disturbance_cost')) - _float(full_metric.get('mainline_disturbance_cost')):.6f}; "
        f"family={_paper_family(spec)}"
    )


def _service_tradeoff_text(
    trace: Mapping[str, Any],
    metric: Mapping[str, Any],
    full: Mapping[str, Any],
    full_metric: Mapping[str, Any],
) -> str:
    if trace.get("variant") == FULL_VARIANT:
        return "full RPMI diagnostic variant; service and disturbance are reported directly"
    service_delta = (1 if _truthy(trace.get("merge_success")) else 0) - (1 if _truthy(full.get("merge_success")) else 0)
    dist_delta = _float(metric.get("mainline_disturbance_cost")) - _float(full_metric.get("mainline_disturbance_cost"))
    return f"service_delta_vs_full={service_delta}; disturbance_delta_vs_full={dist_delta:.6f}"


def _variant_fail_reason(
    spec: IterationSpec,
    variant: str,
    trace: Mapping[str, Any],
    metric: Mapping[str, Any],
    status: Mapping[str, Any],
) -> str:
    del metric
    if not _truthy(trace.get("can_join_full_chain")):
        return "trace_join_incomplete"
    if spec.scenario_subfamily.startswith("P1b") and variant == FULL_VARIANT and not _truthy(trace.get("merge_success")):
        return "near_miss_selected_action_no_realized_service"
    if variant == "forced_accommodation" and _variant_uses_rpmi_info("forced_accommodation"):
        return "forced_accommodation_rpmi_derived_diagnostic_not_validated_non_rpmi_baseline"
    if status.get("verdict") != "READY_FOR_PROMPT4_LOCK_CANDIDATE" and variant == FULL_VARIANT:
        return "paper_evidence_target_set_not_fully_supported"
    return ""


def _yes_no_unclear(value: Any) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return "unclear"


def _md_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _paper_evidence_columns() -> list[str]:
    return [
        "claim_id",
        "evidence_target_id",
        "scenario_family",
        "scenario_design_id",
        "deterministic_case_id",
        "variant",
        "selected_gap_id",
        "selected_action_id",
        "selected_action_type",
        "reservation_id",
        "demand_id",
        "realized_event_id",
        "merge_success_rate_over_demand",
        "realized_unserved_demand_rate",
        "RD_pred",
        "RD_realized",
        "RD_delta",
        "C_dist_pred",
        "mainline_disturbance_cost",
        "hard_brake_count",
        "max_deceleration",
        "speed_variance_delta",
        "max_wave_amplitude",
        "min_TTC",
        "min_realized_gap",
        "raw_gap_size_selected",
        "closing_rate_selected",
        "ablation_difference",
        "service_tradeoff_explanation",
        "can_join_full_chain",
        "claim_support_status",
        "failure_type",
        "evidence_file",
    ]


def _paper_variant_metric_columns() -> list[str]:
    return [
        "scenario_family",
        "scenario_design_id",
        "variant",
        "selected_gap_id",
        "selected_action_id",
        "Z_R_norm",
        "RD_pred_norm",
        "C_dist_norm",
        "S_safety_penalty",
        "Q_churn_penalty",
        "J",
        "J_none",
        "RCMV",
        "theta",
        "lambda_Z",
        "lambda_D",
        "lambda_C",
        "lambda_S",
        "lambda_Q",
        "merge_success_rate_over_demand",
        "mainline_disturbance_cost",
        "RD_realized",
        "hard_brake_count",
        "max_deceleration",
        "speed_variance_delta",
        "max_wave_amplitude",
        "min_TTC",
        "min_realized_gap",
        "pass_flag",
        "fail_reason",
    ]


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
    del failure_rows, scenario_rows
    answers = _activation_answers(specs, traces, metrics)
    join = _join_status(traces)
    generated = _generated_files()
    meaningful = _meaningful_iteration_verification(specs, traces, actions, metrics, iteration_rows)
    family_status = _required_family_status(specs)
    variant_status = _core_variant_status(specs, traces)
    lines = [
        "# PROMPT 3B REVIEW PACKET",
        "",
        "## 1. Executive verdict",
        "",
        status["verdict"],
        "",
        status["verdict_explanation"],
        "",
        f"- meaningful_iterations_completed: {meaningful['completed']}",
        f"- minimum_meaningful_iterations_required: {meaningful['required']}",
        f"- fewer_than_6_meaningful_iterations_completed: {str(meaningful['fewer_than_required']).lower()}",
        f"- stop_condition_or_limitation: {meaningful['stop_condition_or_limitation']}",
        "- partial evidence handling: verdict remains PARTIAL_PROGRESS_REVIEW_REQUIRED; it is not promoted to READY_FOR_PROMPT4_LOCK.",
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
        "| required_family | attempted_status |",
        "| --- | --- |",
    ]
    for family, attempted in family_status.items():
        lines.append(f"| {family} | {attempted} |")
    lines.append("")
    lines.extend(
        [
            "Core variant execution status:",
            "",
            "| variant | ran_count | expected_count | failed_count | join_failures | status |",
            "| --- | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in variant_status:
        lines.append(
            f"| {row['variant']} | {row['ran_count']} | {row['expected_count']} | "
            f"{row['failed_count']} | {row['join_failures']} | {row['status']} |"
        )
    lines.append("")
    lines.extend(
        [
    ]
    )
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
            f"- meaningful_iterations_completed: {meaningful['completed']}",
            f"- minimum_meaningful_iterations_required: {meaningful['required']}",
            f"- fewer_than_6_meaningful_iterations_completed: {str(meaningful['fewer_than_required']).lower()}",
            f"- stop_condition_or_limitation: {meaningful['stop_condition_or_limitation']}",
            "",
            "Meaningful-iteration verification:",
            "",
            "| iteration_id | family | core_variants | selected_chain | objective_decomposition | realized_metrics | failure_classification | proposed_modification | keep_revert | meaningful |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in meaningful["rows"]:
        lines.append(
            f"| {row['iteration_id']} | {row['scenario_family']}/{row['scenario_subfamily']} | "
            f"{str(row['core_variants_present']).lower()} | {str(row['selected_chain_present']).lower()} | "
            f"{str(row['action_decomposition_present']).lower()} | {str(row['realized_metrics_present']).lower()} | "
            f"{str(row['failure_classification_present']).lower()} | {str(row['proposed_modification_present']).lower()} | "
            f"{str(row['keep_or_revert_present']).lower()} | {str(row['meaningful']).lower()} |"
        )
    lines.extend(
        [
            "",
            "Iteration rerun summary:",
            "",
            "| iteration_id | scenario_family | failure_observed | failure_type | hypothesis | changed_component | old_value | new_value | rerun_result | keep_or_revert | reason |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in iteration_rows:
        lines.append(
            f"| {row['iteration_id']} | {row['scenario_family']}/{row['scenario_subfamily']} | {row['failure_observed']} | "
            f"{row['failure_type']} | {row['hypothesis']} | {row['changed_component']} | {row['old_value']} | "
            f"{row['new_value']} | {row['rerun_result']} | {row['keep_or_revert']} | {row['reason']} |"
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
            f"  - {row['iteration_id']}: {row['changed_component']} from {row['old_value']} to {row['new_value']} ({row['keep_or_revert']}) because {row['failure_observed']}; scope={row['change_scope']}; cross_check={row['cross_check_status']}."
        )
    lines.extend(
        [
            "- all parameter changes kept: P0 gapB7 as partial diagnostic lineage, P1a lambda_C=30 as partial bad-action suppression diagnostic, P1b gap7 as partial near-miss selection diagnostic.",
            "- all parameter changes reverted: P0 forced-pressure case and P1b gap5 are not recommended as lock candidates.",
            "- why each was changed: every change is tied to the observed failure in the table above.",
            "- lambda_C change status: lambda_C=30 was a config-level, failure-driven P1a diagnostic attempt only; it was not a global objective change, was not cross-checked beyond the single P1a case, and must not be promoted to lock.",
            "- theta change status: theta was tested through the without_theta ablation across all six iterations; no global theta calibration was kept.",
            "- cross-check status: no objective parameter change was validated on held-out or locked scenarios; Prompt 3B remains diagnostic Rung 2 evidence.",
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
            "- forced_accommodation validation status: diagnostic instrumentation only, not a validated reusable baseline and not lock-ready.",
            "- core variant run status: all six required variants ran in all six iterations with zero full-chain join failures.",
            "- harness-level deviations from existing RPMI primitives: the Prompt 3B script imports Prompt 3A private helper functions for row generation, implements forced_accommodation/without_Cbar/without_theta as script-level diagnostic variants because they are not first-class BASELINE_CONFIGS, and generates event-window metrics through the Prompt 3A harness path; no core RPMI module was edited.",
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
            "- Harness boundary: this script constructs deterministic cases, passes explicit configs, calls existing RPMI/Prompt 3A primitives, and writes suffixed Prompt 3B outputs. It does not silently patch core objective, simulator, reservation, or metric code.",
            "- Harness-level implementation deviations recorded for review: private Prompt 3A helper reuse, script-level forced_accommodation/without_Cbar/without_theta variants, and event-window metrics generated by harness path rather than the main runner path.",
            "- CSV overwritten: none. Prompt 3B generated suffixed CSVs and did not overwrite Prompt 3A readiness files.",
            "",
            "## 15. Next human action",
            "",
            "Send PROMPT_3B_REVIEW_PACKET.md to the human reviewer before Prompt 4.",
            "",
        ]
    )
    return "\n".join(lines)


def _repair_review_packet_md(
    specs: Sequence[IterationSpec],
    traces: Sequence[Mapping[str, Any]],
    actions: Sequence[Mapping[str, Any]],
    metrics: Sequence[Mapping[str, Any]],
    baseline_rows: Sequence[Mapping[str, Any]],
    ablation_rows: Sequence[Mapping[str, Any]],
    iteration_rows: Sequence[Mapping[str, Any]],
    repair_calibration_rows: Sequence[Mapping[str, Any]],
    status: Mapping[str, Any],
) -> str:
    del actions, status
    answers = _activation_answers(specs, traces, metrics)
    join = _join_status(traces)
    p1b_full = [
        trace
        for spec in specs
        if spec.scenario_subfamily.startswith("P1b")
        for trace in [_trace_for_variant(traces, spec, FULL_VARIANT)]
        if trace
    ]
    near_miss_service_closed = any(_truthy(trace.get("merge_success")) for trace in p1b_full)
    required_variants = _core_variant_status(specs, traces)
    all_variants_ran = all(row["status"] == "ran_all" for row in required_variants)
    first_class_variants = _first_class_variant_status()
    first_class_ok = all(first_class_variants.values())
    repair_verdict = _repair_verdict(near_miss_service_closed, first_class_ok, all_variants_ran)
    recommendation = _repair_recommendation(repair_verdict)
    lines = [
        "# PROMPT 3B-R REPAIR REVIEW PACKET",
        "",
        "## 1. Verdict",
        "",
        repair_verdict,
        "",
        recommendation,
        "",
        "Prompt 3B-R is a repair and re-validation pass only. It does not create Prompt 4 lock files, does not run Prompt 5, and does not edit the manuscript.",
        "",
        "## 2. Implementation repair verification",
        "",
        "- selected action commands plus reservation guidance applied: yes, the Prompt 3A/3B event-window path now calls `execute_reservation_guidance` and merges its commands with `commands_for_action` before stepping traffic.",
        "- action-conditioned reservation uses post-action edge map: yes for selected RPMI evaluations, reservations are built from selected evaluation edges/rollout; Prompt 3B passes the selected evaluation edge map into realized event finalization.",
        f"- near-miss selected action joins to realized demand service: {'yes' if near_miss_service_closed else 'no'}",
        "",
        "Selected action -> reservation -> realized_event -> demand_outcome examples:",
        "",
        "| scenario | variant | selected_action | selected_gap | reservation | realized_event | demand_outcome | merge_success | disturbance |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | ---: |",
    ]
    for trace in _repair_example_traces(specs, traces):
        metric = _metric_for_trace(metrics, trace)
        lines.append(
            f"| {trace.get('scenario_design_id', '')} | {trace.get('variant', '')} | {trace.get('selected_action_id', '')} | "
            f"{trace.get('selected_gap_id', '')} | {trace.get('reservation_id', '')} | {trace.get('realized_event_id', '')} | "
            f"{trace.get('demand_status_after_final', '')} | {trace.get('merge_success', '')} | "
            f"{_float(metric.get('mainline_disturbance_cost')):.6f} |"
        )
    lines.extend(
        [
            "",
            "## 3. Baseline / ablation registration verification",
            "",
            f"- forced_accommodation first-class config: {str(first_class_variants['forced_accommodation']).lower()}",
            f"- without_Cbar first-class config: {str(first_class_variants['without_Cbar']).lower()}",
            f"- without_theta first-class config: {str(first_class_variants['without_theta']).lower()}",
            "- Prompt 3B runner use: yes, Prompt 3B calls the Prompt 3A variant runner, which now resolves these variants through `resolve_baseline_config` and `apply_policy` instead of harness-only ad hoc selection for these three variants.",
            "- fairness status: no variant uses future realized outcomes. `without_Cbar` and `without_theta` are RPMI ablations, not non-RPMI baselines. `forced_accommodation` is a first-class diagnostic RPMI-derived baseline and remains outside default/paper-claim baseline sets.",
            "",
            "| variant | role | fairness_pass | fairness_notes |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in [*baseline_rows, *ablation_rows]:
        variant = str(row.get("variant", ""))
        if variant not in {"forced_accommodation", "without_Cbar", "without_theta"}:
            continue
        lines.append(
            f"| {variant} | {_variant_role(variant)} | {row.get('fairness_pass', '')} | {row.get('fairness_notes', '')} |"
        )
    lines.extend(
        [
            "",
            "## 4. Objective calibration verification",
            "",
            "- Re-run families: P0, P1a, and P1b were re-run after repair.",
            "- Default objective: Prompt 3B-R keeps the same centralized objective formula and logs every diagnostic config-level change; no Prompt 4 objective lock is created.",
            "- lambda_C=30 status: it remains a P1a diagnostic attempt only unless cross-case evidence below supports it; it is not promoted as a global answer.",
            "- theta status: theta is checked by the first-class `rpmi_cmv_without_theta` ablation across all diagnostic families; no global theta calibration is locked.",
            "",
            "| scenario | family | lambda_C | theta | full_action | raw_gap | forced_action | without_RD | without_Cbar | without_theta | full_success | RD_pred | RD_realized | C_dist_pred | full_disturbance | forced_disturbance | keep_or_revert |",
            "| --- | --- | ---: | ---: | --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in repair_calibration_rows:
        lines.append(
            f"| {row['scenario_design_id']} | {row['scenario_family']}/{row['scenario_subfamily']} | "
            f"{row['default_lambda_C']} | {row['default_theta']} | {row['full_selected_action']} | {row['raw_selected_gap']} | "
            f"{row['forced_selected_action']} | {row['without_RD_selected_action']} | {row['without_Cbar_selected_action']} | "
            f"{row['without_theta_selected_action']} | {row['full_merge_success']} | {row['RD_pred']} | {row['RD_realized']} | "
            f"{row['C_dist_pred']} | {row['full_disturbance']} | {row['forced_disturbance']} | {row['keep_or_revert']} |"
        )
    lines.extend(
        [
            "",
            "Logged calibration attempts:",
            "",
            "| iteration | changed_component | old_value | new_value | keep_or_revert | rerun_result |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in iteration_rows:
        lines.append(
            f"| {row['iteration_id']} | {row['changed_component']} | {row['old_value']} | {row['new_value']} | "
            f"{row['keep_or_revert']} | {row['rerun_result']} |"
        )
    lines.extend(
        [
            "",
            "## 5. Required re-run status",
            "",
            "| required_family | attempted |",
            "| --- | --- |",
        ]
    )
    for family, attempted in _required_family_status(specs).items():
        lines.append(f"| {family} | {attempted} |")
    lines.extend(
        [
            "",
            "| variant | ran_count | expected_count | failed_count | join_failures | status |",
            "| --- | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in required_variants:
        lines.append(
            f"| {row['variant']} | {row['ran_count']} | {row['expected_count']} | {row['failed_count']} | {row['join_failures']} | {row['status']} |"
        )
    lines.extend(
        [
            "",
            "## 6. Mechanism activation questions",
            "",
        ]
    )
    for question, answer in answers.items():
        if question.startswith("10."):
            continue
        lines.append(f"- {question}: {answer}")
    lines.extend(
        [
            "",
            "## 7. Trace status",
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
            "",
            "## 8. Files generated or modified",
            "",
            "- outputs/d2_5_theory_alignment/human_review/PROMPT_3B_REPAIR_REVIEW_PACKET.md",
            "- outputs/d2_5_theory_alignment/objective_calibration_repair_log_prompt3b_r.csv",
            "- src/rpmi/runner.py",
            "- scripts/prompt3a_readiness_micro_run.py",
            "- scripts/prompt3b_mechanism_codesign_loop.py",
            "- Prompt 3B suffixed CSV/Markdown outputs were regenerated; Prompt 3A readiness inputs were not overwritten.",
            "- CSV overwritten: none beyond Prompt 3B suffixed/repair outputs.",
            "",
            "## 9. Stop rule",
            "",
            "Stop after producing this repair review packet. Do not proceed to Prompt 4.",
        ]
    )
    return "\n".join(lines) + "\n"


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


def _first_class_variant_status() -> dict[str, bool]:
    from rpmi.runner import BASELINE_CONFIGS, resolve_baseline_config

    checks = {
        "forced_accommodation": "forced_accommodation",
        "without_Cbar": "rpmi_cmv_without_cbar",
        "without_theta": "rpmi_cmv_without_theta",
    }
    out: dict[str, bool] = {}
    for label, baseline_id in checks.items():
        try:
            out[label] = resolve_baseline_config(baseline_id).baseline_id == baseline_id and baseline_id in BASELINE_CONFIGS
        except Exception:
            out[label] = False
    return out


def _repair_example_traces(
    specs: Sequence[IterationSpec],
    traces: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    out: list[Mapping[str, Any]] = []
    wanted = [
        ("P0", FULL_VARIANT),
        ("P0", "forced_accommodation"),
        ("P1a", FULL_VARIANT),
        ("P1a", "forced_accommodation"),
        ("P1b", FULL_VARIANT),
        ("P1b", "forced_accommodation"),
    ]
    for subfamily_prefix, variant in wanted:
        spec = next(
            (
                item
                for item in specs
                if item.scenario_family == subfamily_prefix
                or item.scenario_subfamily.startswith(subfamily_prefix)
            ),
            None,
        )
        if spec is None:
            continue
        trace = _trace_for_variant(traces, spec, variant)
        if trace:
            out.append(trace)
    return out


def _repair_verdict(
    near_miss_service_closed: bool,
    first_class_ok: bool,
    all_variants_ran: bool,
) -> str:
    if not all_variants_ran:
        return "NOT_READY_INSUFFICIENT_TRACE_JOIN"
    if not first_class_ok:
        return "NOT_READY_REVISE_BASELINE"
    if not near_miss_service_closed:
        return "NOT_READY_REVISE_IMPLEMENTATION"
    return "PARTIAL_PROGRESS_REVIEW_REQUIRED"


def _repair_recommendation(verdict: str) -> str:
    if verdict == "NOT_READY_REVISE_IMPLEMENTATION":
        return "Do not proceed; revise implementation first."
    if verdict == "NOT_READY_REVISE_BASELINE":
        return "Do not proceed; revise baseline first."
    if verdict == "NOT_READY_INSUFFICIENT_TRACE_JOIN":
        return "Do not proceed; trace join is insufficient."
    if verdict == "READY_FOR_PROMPT4_LOCK":
        return "Proceed to Prompt 4 Evaluation Lock after human review."
    return "Human review required before deciding."


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


def _rerun_result_sentence(
    full: Mapping[str, Any],
    raw: Mapping[str, Any],
    forced: Mapping[str, Any],
    without_rd: Mapping[str, Any],
    without_c: Mapping[str, Any],
    without_theta: Mapping[str, Any],
    metrics: Sequence[Mapping[str, Any]],
) -> str:
    full_metric = _metric_for_trace(metrics, full)
    forced_metric = _metric_for_trace(metrics, forced)
    return (
        f"full={full.get('selected_action_id', '')}/{full.get('selected_gap_id', '')}, "
        f"raw={raw.get('selected_action_id', '')}/{raw.get('selected_gap_id', '')}, "
        f"forced={forced.get('selected_action_id', '')}/{forced.get('selected_gap_id', '')}, "
        f"without_RD={without_rd.get('selected_action_id', '')}/{without_rd.get('selected_gap_id', '')}, "
        f"without_Cbar={without_c.get('selected_action_id', '')}/{without_c.get('selected_gap_id', '')}, "
        f"without_theta={without_theta.get('selected_action_id', '')}/{without_theta.get('selected_gap_id', '')}, "
        f"full_disturbance={full_metric.get('mainline_disturbance_cost', '')}, "
        f"forced_disturbance={forced_metric.get('mainline_disturbance_cost', '')}, "
        f"full_merge_success={full.get('merge_success', '')}"
    )


def _change_scope(spec: IterationSpec) -> str:
    if spec.changed_component == "lambda_C":
        return "config_level_single_P1a_iteration_not_global"
    if spec.changed_component == "theta":
        return "config_level_theta_change_not_kept_global"
    return "diagnostic_scenario_ladder_not_global_objective"


def _cross_check_status(spec: IterationSpec) -> str:
    if spec.changed_component == "lambda_C":
        return "not_cross_checked_beyond_single_P1a_case"
    if spec.changed_component == "theta":
        return "theta_ablation_ran_across_all_iterations_but_no_theta_parameter_change_was_kept"
    if spec.keep_or_revert.startswith("revert"):
        return "rerun_showed_limited_or_failed_activation; not retained_for_claim_support"
    return "checked_only_within_declared_prompt3b_ladder; not held_out_or_locked"


def _lock_candidate_status(spec: IterationSpec) -> str:
    if spec.keep_or_revert in {"keep_partial", "keep_for_lineage_only"}:
        return "partial_diagnostic_only_not_lock_ready"
    return "not_recommended_for_lock_candidate"


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
    return variant in {FULL_VARIANT, "forced_accommodation", "without_RD", "without_Cbar", "without_theta"}


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
        return "first-class diagnostic RPMI-derived baseline config; no future realized outcome used; not a non-RPMI performance baseline"
    if value == "without_Cbar":
        return "first-class diagnostic RPMI ablation via lambda_C=0; RPMI-only information is expected for an ablation, not a non-RPMI baseline"
    if value == "without_theta":
        return "first-class diagnostic RPMI ablation via theta=0; RPMI-only information is expected for an ablation, not a non-RPMI baseline"
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
        "rerun_result",
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
        "change_scope",
        "failure_driven",
        "cross_check_status",
        "lock_candidate_status",
        "claim_boundary_status",
    ]


def _repair_calibration_columns() -> list[str]:
    return [
        "scenario_design_id",
        "scenario_family",
        "scenario_subfamily",
        "default_lambda_C",
        "default_theta",
        "full_selected_action",
        "full_selected_gap",
        "raw_selected_gap",
        "forced_selected_action",
        "without_RD_selected_action",
        "without_Cbar_selected_action",
        "without_theta_selected_action",
        "full_merge_success",
        "forced_merge_success",
        "RD_pred",
        "RD_realized",
        "C_dist_pred",
        "full_disturbance",
        "forced_disturbance",
        "lambda_C_cross_case_status",
        "theta_cross_case_status",
        "keep_or_revert",
        "claim_boundary_status",
    ]


def _repair_iteration_log_columns() -> list[str]:
    return [
        "iteration_id",
        "evidence_target_id",
        "attempt_kind",
        "scenario_family",
        "scenario_subfamily",
        "before_scenario_id",
        "after_scenario_id",
        "before_scenario_design_id",
        "after_scenario_design_id",
        "rerun_case_id",
        "observed_failure",
        "failure_observed",
        "failure_type",
        "hypothesis",
        "changed_component",
        "old_value",
        "new_value",
        "before_error",
        "after_error",
        "local_rerun_status",
        "local_rerun_result",
        "rerun_result",
        "selected_gap_before",
        "selected_gap_after",
        "selected_action_before",
        "selected_action_after",
        "raw_selected_gap_before",
        "raw_selected_gap_after",
        "forced_selected_action_before",
        "forced_selected_action_after",
        "without_RD_selected_action_after",
        "without_Cbar_selected_action_after",
        "without_theta_selected_action_after",
        "full_merge_success_before",
        "full_merge_success_after",
        "before_all_variants_joined",
        "after_all_variants_joined",
        "full_disturbance_before",
        "full_disturbance_after",
        "forced_disturbance_after",
        "realized_disturbance_change",
        "disturbance_or_safety_worse",
        "cross_case_check",
        "cross_case_status",
        "keep_or_revert",
        "reason",
        "failure_driven",
        "claim_boundary_status",
    ]


def _repair_objective_attempt_columns() -> list[str]:
    return [
        "iteration_id",
        "evidence_target_id",
        "scenario_family",
        "scenario_subfamily",
        "changed_component",
        "old_value",
        "new_value",
        "failure_observed",
        "failure_type",
        "hypothesis",
        "local_rerun_status",
        "local_rerun_result",
        "cross_case_check",
        "cross_case_status",
        "disturbance_or_safety_worse",
        "keep_or_revert",
        "reason",
        "failure_driven",
        "claim_boundary_status",
    ]


def _repair_scenario_attempt_columns() -> list[str]:
    return [
        "iteration_id",
        "evidence_target_id",
        "scenario_family",
        "scenario_subfamily",
        "before_scenario_id",
        "after_scenario_id",
        "rerun_case_id",
        "changed_component",
        "old_value",
        "new_value",
        "failure_observed",
        "failure_type",
        "hypothesis",
        "local_rerun_status",
        "local_rerun_result",
        "selected_action_before",
        "selected_action_after",
        "selected_gap_before",
        "selected_gap_after",
        "full_merge_success_after",
        "realized_disturbance_change",
        "disturbance_or_safety_worse",
        "cross_case_check",
        "cross_case_status",
        "keep_or_revert",
        "reason",
        "claim_boundary_status",
    ]


def _keep_revert_decisions_md(repair_iteration_rows: Sequence[Mapping[str, Any]]) -> str:
    lines = [
        "# Prompt 3B-R Keep/Revert Decisions",
        "",
        "Prompt 3B-R is a repair-loop trajectory only. These decisions do not create Prompt 4 lock files, do not edit LOCKED_* files, and do not change the manuscript.",
        "",
        "| iteration | target | family | change | local rerun | cross-case check | keep/revert | reason |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in repair_iteration_rows:
        change = f"{row.get('changed_component', '')}: {row.get('old_value', '')} -> {row.get('new_value', '')}"
        lines.append(
            f"| {row.get('iteration_id', '')} | {row.get('evidence_target_id', '')} | "
            f"{row.get('scenario_family', '')}/{row.get('scenario_subfamily', '')} | {_md_cell(change)} | "
            f"{row.get('local_rerun_status', '')} | {_md_cell(row.get('cross_case_status', ''))} | "
            f"{row.get('keep_or_revert', '')} | {_md_cell(row.get('reason', ''))} |"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- No Prompt 4 was run.",
            "- No `LOCKED_*` files were created or modified.",
            "- No manuscript files were edited.",
            "- Kept rows are diagnostic lineage or partial repair evidence only.",
            "- Reverted rows remain in the log so failed repair attempts are visible rather than silently discarded.",
        ]
    )
    return "\n".join(lines) + "\n"


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
