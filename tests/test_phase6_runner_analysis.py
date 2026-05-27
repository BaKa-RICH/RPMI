import csv
import json
from dataclasses import asdict

from rpmi.analysis import (
    aggregate_failures,
    aggregate_metrics,
    collect_rcmv_trace,
    write_gate_d0_decision,
)
from rpmi.analysis import EVIDENCE_PACKAGE_VERSION, METRICS_SCHEMA_VERSION
from rpmi.runner import (
    ExperimentRunSpec,
    build_decision_context,
    resolve_baseline_config,
    run_baseline_suite,
    run_experiment,
    verify_state_hash_fairness,
)
from rpmi.scenarios import generate_state, make_scenario_config


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def test_one_scenario_multiple_baselines_runs_and_generates_batch_outputs(tmp_path):
    scenario = make_scenario_config("S5", seed=3)

    result = run_baseline_suite(
        [scenario],
        [3],
        ["fifo_no_production", "raw_gap_reservation", "rpmi_cmv"],
        tmp_path,
        batch_id="wave6a_gate",
    )

    aggregate_rows = read_csv(result.aggregate_metrics_path)
    failure_rows = read_csv(result.failure_summary_path)
    rcmv_rows = read_csv(result.rcmv_trace_path)
    fairness = json.loads(open(result.fairness_report_path, encoding="utf-8").read())

    assert len(result.run_dirs) == 3
    assert len(aggregate_rows) == 3
    assert fairness["fairness_pass"] is True
    assert len({row["state_hash"] for row in aggregate_rows}) == 1
    assert {row["algorithm_id"] for row in aggregate_rows} == {
        "fifo_no_production",
        "raw_gap_reservation",
        "rpmi_cmv",
    }
    assert failure_rows
    assert rcmv_rows
    assert any(row["algorithm_id"] == "rpmi_cmv" for row in rcmv_rows)
    assert open(result.baseline_comparison_summary_path, encoding="utf-8").readline()


def test_readiness_failed_run_is_marked_and_aggregates(tmp_path):
    scenario = make_scenario_config("S2", readiness_targets={"near_miss_count_min": 99})
    scenario_path = tmp_path / "bad_s2.json"
    scenario_path.write_text(json.dumps(asdict(scenario)), encoding="utf-8")

    run_dir = run_experiment(
        ExperimentRunSpec(str(scenario_path), "rpmi_cmv", scenario.seed, tmp_path / "runs")
    )
    metrics = json.loads((run_dir / "metrics_episode.json").read_text(encoding="utf-8"))["metrics"]
    aggregate_path = aggregate_metrics([run_dir], tmp_path / "aggregate_metrics.csv")
    failure_path = aggregate_failures([run_dir], tmp_path / "failure_summary.csv")

    assert metrics["status"] == "readiness_failed"
    assert metrics["readiness_pass"] is False
    assert "near_miss_too_low" in metrics["readiness_reason"]
    assert read_csv(aggregate_path)[0]["status"] == "readiness_failed"
    assert read_csv(failure_path)[0]["failure_source"] == "readiness"


def test_baselines_do_not_use_proposed_information_for_decision_context():
    scenario = make_scenario_config("S5", seed=4)
    state = generate_state(scenario)

    raw_gap_context = build_decision_context(
        state,
        scenario,
        resolve_baseline_config("raw_gap_reservation"),
    )
    rpmi_context = build_decision_context(
        state,
        scenario,
        resolve_baseline_config("rpmi_cmv"),
    )

    assert resolve_baseline_config("raw_gap_reservation").uses_near_miss is False
    assert resolve_baseline_config("raw_gap_reservation").uses_rd is False
    assert raw_gap_context["baseline_evaluation"].matched_edge_ids == rpmi_context["baseline_evaluation"].matched_edge_ids
    assert not any(edge.action_id for edge in raw_gap_context["edges"])


def test_state_hash_fairness_helper_detects_batch_consistency(tmp_path):
    result = run_baseline_suite(
        [make_scenario_config("S5", seed=5)],
        [5],
        ["fifo_no_production", "density_triggered", "speed_benefit"],
        tmp_path,
        batch_id="fairness",
    )

    report = verify_state_hash_fairness(result.run_dirs)

    assert report["fairness_pass"] is True
    assert report["group_count"] == 1
    assert len({row["state_hash"] for row in report["rows"]}) == 1


def test_collect_rcmv_trace_can_be_generated_for_single_run(tmp_path):
    result = run_baseline_suite(
        [make_scenario_config("S5", seed=6)],
        [6],
        ["rpmi_cmv"],
        tmp_path,
        batch_id="trace",
    )

    trace_path = collect_rcmv_trace(result.run_dirs, tmp_path / "trace.csv")
    rows = read_csv(trace_path)

    assert rows
    assert {"action_id", "J", "RCMV", "selected"}.issubset(rows[0])


def test_no_near_miss_ablation_is_runnable_and_expands_candidates(tmp_path):
    result = run_baseline_suite(
        [make_scenario_config("S5", seed=3)],
        [3],
        ["rpmi_cmv", "rpmi_cmv_without_near_miss"],
        tmp_path,
        batch_id="no_near_miss_ablation",
    )

    metrics_by_algorithm = {}
    for run_dir in result.run_dirs:
        metrics = json.loads(
            open(f"{run_dir}/metrics_episode.json", encoding="utf-8").read()
        )["metrics"]
        metrics_by_algorithm[metrics["algorithm_id"]] = metrics

    proposed = metrics_by_algorithm["rpmi_cmv"]
    ablation = metrics_by_algorithm["rpmi_cmv_without_near_miss"]

    assert ablation["uses_near_miss"] is False
    assert ablation["ablation_no_near_miss_screening"] is True
    assert ablation["candidate_action_count"] > proposed["candidate_action_count"]


def test_wave6a0_unique_run_ids_and_evidence_package_layout(tmp_path):
    result = run_baseline_suite(
        [make_scenario_config("S5", seed=3)],
        [3],
        ["fifo_no_production", "raw_gap_reservation", "rpmi_cmv"],
        tmp_path,
        batch_id="wave6a0_layout",
    )

    package = tmp_path / "wave6a0_layout" / "evidence_package"
    manifest_rows = read_csv(package / "main_batch" / "batch_manifest.csv")
    run_ids = [row["run_id"] for row in manifest_rows]

    assert result.evidence_package_path == str(package)
    assert len(run_ids) == len(set(run_ids))
    assert all("__" in row["run_id"] for row in manifest_rows)
    for path in [
        package / "main_batch" / "aggregate_metrics_completed.csv",
        package / "main_batch" / "failure_summary_main_batch.csv",
        package / "readiness_fail" / "failure_summary_readiness_fail.csv",
        package / "positive_rcmv_micro" / "positive_rcmv_manifest.json",
        package / "gate_D0_input" / "paper_claim_support_table.csv",
        package / "evidence_index.json",
        package / "schema_manifest.json",
    ]:
        assert path.exists()
    assert not (package / "failure_summary.csv").exists()


def test_wave6a0_aggregate_metrics_have_dual_denominators(tmp_path):
    result = run_baseline_suite(
        [make_scenario_config("S5", seed=3)],
        [3],
        ["rpmi_cmv"],
        tmp_path,
        batch_id="wave6a0_denominator",
    )

    rows = read_csv(result.aggregate_metrics_path)
    row = rows[0]

    assert row["metrics_schema_version"] == METRICS_SCHEMA_VERSION
    assert row["evidence_package_version"] == EVIDENCE_PACKAGE_VERSION
    assert row["failed_reservation_denominator"] == "generated_reservation_count"
    assert "failed_reservation_rate" in row
    assert "merge_success_rate_over_demand" in row
    assert "predicted_unserved_demand_rate" in row
    assert "realized_unserved_demand_rate" in row
    if float(row["D_H"]) > 0:
        assert float(row["merge_success_rate_over_demand"]) == float(row["merge_success_count"]) / float(row["D_H"])


def test_wave6a0_readiness_failed_is_split_from_completed_comparison(tmp_path):
    failed = make_scenario_config("S2", readiness_targets={"near_miss_count_min": 99})
    completed = make_scenario_config("S5", seed=3)

    result = run_baseline_suite(
        [failed, completed],
        [3],
        ["rpmi_cmv"],
        tmp_path,
        batch_id="wave6a0_readiness_split",
    )

    package = tmp_path / "wave6a0_readiness_split" / "evidence_package"
    completed_rows = read_csv(package / "main_batch" / "aggregate_metrics_completed.csv")
    readiness_rows = read_csv(package / "readiness_fail" / "aggregate_metrics_readiness_fail.csv")
    readiness_failures = read_csv(package / "readiness_fail" / "failure_summary_readiness_fail.csv")

    assert completed_rows
    assert readiness_rows
    assert all(row["status"] == "completed" for row in completed_rows)
    assert all(row["status"] == "readiness_failed" for row in readiness_rows)
    assert all(row["failure_stage"] == "readiness" for row in readiness_failures)


def test_wave6a0_rcmv_trace_contains_action_profile_fields(tmp_path):
    result = run_baseline_suite(
        [make_scenario_config("S5", seed=3)],
        [3],
        ["rpmi_cmv"],
        tmp_path,
        batch_id="wave6a0_rcmv_trace",
    )

    rows = read_csv(result.rcmv_trace_path)

    assert len(rows) >= 3
    assert {
        "action_type",
        "nominal_edge_id",
        "boundary_type",
        "requested_delta_W",
        "delta_W_target",
        "T_prod",
        "u_front",
        "u_rear",
        "action_profile_feasible",
        "matched_rd_sum",
    }.issubset(rows[0])
    assert any(row["selected"].lower() == "true" for row in rows)


def test_wave6a0_failure_summary_rows_have_join_keys(tmp_path):
    result = run_baseline_suite(
        [make_scenario_config("S5", seed=3)],
        [3],
        ["fifo_no_production", "raw_gap_reservation", "rpmi_cmv"],
        tmp_path,
        batch_id="wave6a0_failure_join",
    )

    rows = read_csv(result.failure_summary_path)

    assert rows
    assert all("failure_join_key" in row for row in rows)
    assert any(row["action_id"] or row["linked_action_id"] for row in rows)
    assert any(row["edge_id"] or row["linked_edge_id"] for row in rows)


def test_wave6a0_stale_rd_and_raw_gap_metrics_are_visible(tmp_path):
    result = run_baseline_suite(
        [make_scenario_config("S5", seed=3)],
        [3],
        [
            "raw_gap_reservation",
            "rpmi_cmv",
            "rpmi_cmv_without_rd",
            "rpmi_cmv_without_action_conditioned_reservation",
        ],
        tmp_path,
        batch_id="wave6a0_ablation_metrics",
    )

    rows = {row["algorithm_id"]: row for row in read_csv(result.aggregate_metrics_path)}

    assert "stale_reservation_harm" in rows["rpmi_cmv_without_action_conditioned_reservation"]
    assert rows["rpmi_cmv_without_action_conditioned_reservation"]["stale_reservation_harm_reason"]
    assert rows["rpmi_cmv_without_rd"]["rd_decision_changed_flag"] in {"True", "False"}
    assert rows["raw_gap_reservation"]["raw_gap_illusion_flag"] in {"True", "False"}
    assert "action_conditioned_gain" in rows["rpmi_cmv"]


def test_wave6a0_denominator_warning_when_reservation_success_hides_unserved_demand(tmp_path):
    run_dir = run_experiment(
        ExperimentRunSpec(
            None,
            "density_triggered",
            3,
            tmp_path / "runs",
            scenario_id="S5",
        )
    )

    aggregate_path = aggregate_metrics([run_dir], tmp_path / "aggregate_metrics.csv")
    row = read_csv(aggregate_path)[0]

    assert row["failed_reservation_denominator"] == "generated_reservation_count"
    if float(row["failed_reservation_rate"]) == 0.0 and float(row["realized_unserved_demand_count"]) > 0.0:
        assert row["denominator_warning_flag"] == "True"


def test_wave6a0_state_hash_fairness_csv_groups_by_scenario_seed(tmp_path):
    result = run_baseline_suite(
        [make_scenario_config("S5", seed=5)],
        [5],
        ["fifo_no_production", "density_triggered", "speed_benefit"],
        tmp_path,
        batch_id="wave6a0_fairness_csv",
    )

    package = tmp_path / "wave6a0_fairness_csv" / "evidence_package"
    rows = read_csv(package / "main_batch" / "state_hash_fairness.csv")

    assert rows
    assert rows[0]["algorithm_count"] == "3"
    assert rows[0]["unique_state_hash_count"] == "1"
    assert rows[0]["fairness_pass"] == "True"


def test_wave6a0_evidence_index_answers_audit_questions(tmp_path):
    result = run_baseline_suite(
        [make_scenario_config("S2", seed=3)],
        [3],
        ["rpmi_cmv"],
        tmp_path,
        batch_id="wave6a0_index",
    )

    index = json.loads(open(result.evidence_index_path, encoding="utf-8").read())

    assert index["denominator_policy"]["failed_reservation_rate"] == "failed_reservation_count / generated_reservation_count"
    assert index["files"]["reservation_denominator"] == "main_batch/aggregate_metrics_completed.csv"
    assert index["files"]["demand_denominator"] == "main_batch/aggregate_metrics_completed.csv"
    assert index["answers"]["positive_rcmv_micro_package_present"] is True
    assert index["answers"]["positive_rcmv_case_formally_included"] is False
    assert index["answers"]["readiness_failure_saved_separately"] is True


def test_wave6a0_positive_rcmv_package_is_formally_included(tmp_path):
    result = run_baseline_suite(
        [make_scenario_config("S2", seed=3)],
        [3],
        ["rpmi_cmv"],
        tmp_path,
        batch_id="wave6a0_positive",
    )

    package = tmp_path / "wave6a0_positive" / "evidence_package"
    manifest = json.loads(open(package / "positive_rcmv_micro" / "positive_rcmv_manifest.json", encoding="utf-8").read())
    aggregate_rows = read_csv(package / "positive_rcmv_micro" / "positive_rcmv_aggregate_metrics.csv")
    trace_rows = read_csv(package / "positive_rcmv_micro" / "positive_rcmv_rcmv_trace.csv")

    assert manifest["positive_rcmv_case_count"] == 0
    assert aggregate_rows == []
    assert trace_rows == []


def test_wave6a0_run_artifacts_include_state_hash_json(tmp_path):
    run_dir = run_experiment(
        ExperimentRunSpec(None, "rpmi_cmv", 3, tmp_path / "runs", scenario_id="S5")
    )

    state_hash = json.loads((run_dir / "state_hash.json").read_text(encoding="utf-8"))
    metrics = json.loads((run_dir / "metrics_episode.json").read_text(encoding="utf-8"))["metrics"]

    assert state_hash["state_hash"] == metrics["state_hash"]
    assert metrics["metrics_schema_version"] == METRICS_SCHEMA_VERSION


def test_wave6aplus_gate_d0_input_contains_deterministic_hardening_tables(tmp_path):
    result = run_baseline_suite(
        [
            make_scenario_config("S2", seed=0),
            make_scenario_config("S5", seed=0),
            make_scenario_config("S6", seed=0),
            make_scenario_config("S6_productive", seed=0),
            make_scenario_config("S7", seed=0),
            make_scenario_config("S8", seed=0),
        ],
        [0],
        [
            "raw_gap_reservation",
            "rpmi_cmv",
            "rpmi_cmv_without_rd",
            "rpmi_cmv_without_action_conditioned_reservation",
            "rpmi_cmv_without_near_miss",
        ],
        tmp_path,
        batch_id="wave6aplus_gate_d0",
    )

    gate = tmp_path / "wave6aplus_gate_d0" / "evidence_package" / "gate_D0_input"
    required = [
        gate / "aggregate_metrics_completed.csv",
        gate / "aggregate_metrics_readiness_fail.csv",
        gate / "scenario_manifest.csv",
        gate / "scenario_mechanism_summary.csv",
        gate / "baseline_comparison_summary.csv",
        gate / "ablation_comparison_summary.csv",
        gate / "rcmv_trace_top_actions.csv",
        gate / "sensitivity_local_summary.csv",
        gate / "failure_trace_samples" / "failure_trace_samples.csv",
        gate / "trace_replay_summaries" / "trace_replay_summaries.csv",
        gate / "paper_claim_support_table.csv",
        gate / "positive_rcmv_micro" / "positive_rcmv_manifest.json",
        gate / "positive_rcmv_micro" / "positive_rcmv_rcmv_trace.csv",
        gate / "S6_productive_manifest.json",
        gate / "S6_productive_aggregate_metrics.csv",
        gate / "S6_productive_rcmv_trace.csv",
        gate / "S6_productive_failure_summary.csv",
    ]

    assert result.gate_D0_input_path == str(gate)
    assert all(path.exists() for path in required)


def test_wave6aplus_scenario_manifest_and_mechanism_summary_are_auditable(tmp_path):
    run_baseline_suite(
        [make_scenario_config("S2", seed=0), make_scenario_config("S5", seed=0)],
        [0],
        ["raw_gap_reservation", "rpmi_cmv", "rpmi_cmv_without_near_miss"],
        tmp_path,
        batch_id="wave6aplus_manifest",
    )
    gate = tmp_path / "wave6aplus_manifest" / "evidence_package" / "gate_D0_input"
    manifest_rows = read_csv(gate / "scenario_manifest.csv")
    summary_rows = read_csv(gate / "scenario_mechanism_summary.csv")

    assert {"mechanism_target", "expected_failure_mode", "expected_boundary_types"}.issubset(manifest_rows[0])
    assert {row["scenario_id"] for row in manifest_rows} == {"S2", "S5"}
    assert {row["scenario_id"] for row in summary_rows} == {"S2", "S5"}
    assert all(row["mechanism_interpretability_status"] in {"clear_support", "partial_support", "inconclusive", "contradicts_claim"} for row in summary_rows)
    assert any("Inventory-only support" in row["notes"] for row in summary_rows if row["scenario_id"] == "S5")


def test_wave6aplus_rcmv_top_actions_sensitivity_and_replay_tables(tmp_path):
    run_baseline_suite(
        [make_scenario_config("S2", seed=0)],
        [0],
        ["rpmi_cmv", "rpmi_cmv_without_rd"],
        tmp_path,
        batch_id="wave6aplus_trace",
    )
    gate = tmp_path / "wave6aplus_trace" / "evidence_package" / "gate_D0_input"

    top_rows = read_csv(gate / "rcmv_trace_top_actions.csv")
    sensitivity_rows = read_csv(gate / "sensitivity_local_summary.csv")
    replay_rows = read_csv(gate / "trace_replay_summaries" / "trace_replay_summaries.csv")

    assert top_rows
    assert {"best_action", "selected_action", "a0_none", "top_5_by_RCMV"}.issubset(top_rows[0])
    assert any(row["best_selected_consistent"] == "True" for row in top_rows)
    assert {row["parameter"] for row in sensitivity_rows} == {
        "theta",
        "lambda_D",
        "lambda_C",
        "near_miss_delta_W_max",
        "RD_max",
        "production_width_buffer",
    }
    assert replay_rows
    assert {"predicted_valid", "realized_valid", "prediction_realization_status"}.issubset(replay_rows[0])


def test_wave6aplus_s6_productive_and_positive_rcmv_are_formal_gate_inputs(tmp_path):
    run_baseline_suite(
        [make_scenario_config("S6_productive", seed=0)],
        [0],
        ["raw_gap_reservation", "rpmi_cmv"],
        tmp_path,
        batch_id="wave6aplus_s6_productive",
    )
    gate = tmp_path / "wave6aplus_s6_productive" / "evidence_package" / "gate_D0_input"
    manifest = json.loads((gate / "S6_productive_manifest.json").read_text(encoding="utf-8"))
    aggregate_rows = read_csv(gate / "S6_productive_aggregate_metrics.csv")
    positive_manifest = json.loads((gate / "positive_rcmv_micro" / "positive_rcmv_manifest.json").read_text(encoding="utf-8"))

    assert manifest["case_count"] == 2
    rpmi_rows = [row for row in aggregate_rows if row["algorithm_id"] == "rpmi_cmv"]
    assert rpmi_rows
    assert all(row["selected_action_type"] == "none" and float(row["selected_RCMV"]) == 0.0 for row in rpmi_rows)
    assert positive_manifest["positive_rcmv_case_count"] == 0


def test_gate_d0_decision_downgrades_boundary_speed_to_micro_evidence(tmp_path):
    result = run_baseline_suite(
        [
            make_scenario_config("S2", seed=0),
            make_scenario_config("S5", seed=0),
            make_scenario_config("S6", seed=0),
            make_scenario_config("S6_productive", seed=0),
            make_scenario_config("S7", seed=0),
            make_scenario_config("S8", seed=0),
        ],
        [0],
        [
            "raw_gap_reservation",
            "rpmi_cmv",
            "rpmi_cmv_without_rd",
            "rpmi_cmv_without_action_conditioned_reservation",
            "rpmi_cmv_without_near_miss",
        ],
        tmp_path,
        batch_id="gate_d0_decision",
    )

    paths = write_gate_d0_decision(result.gate_D0_input_path)
    decision = json.loads(paths["gate_D0_decision"].read_text(encoding="utf-8"))
    report = paths["gate_D0_report"].read_text(encoding="utf-8")

    assert paths["gate_D0_report"].exists()
    assert paths["gate_D0_claim_revision_plan"].exists()
    assert paths["gate_D0_fixlist"].exists()
    assert decision["decision"] == "conditional_pass"
    assert decision["allowed_next_stage"] == "Wave 7"
    assert decision["completeness"]["pass"] is True
    assert decision["completeness"]["positive_rcmv_micro_package_present"] is True
    assert decision["scenario_support"]["S2"]["support_level"] == "clear_support"
    assert decision["scenario_support"]["S5"]["support_level"] == "partial_support"
    assert "production action effectiveness" in " ".join(decision["downgraded_claims"])
    assert decision["claim_boundaries"]["production_action_effectiveness_supported"] is False
    assert decision["audit_answers"]["failed_reservation_rate_denominator"] == "generated_reservation_count"
    assert decision["audit_answers"]["positive_rcmv_case_formally_included"] is False
    assert decision["audit_answers"]["positive_rcmv_micro_package_present"] is True
    assert decision["audit_answers"]["failure_summary_split_main_readiness_positive"] is True
    assert decision["audit_answers"]["failed_reservation_zero_but_unserved_or_no_merge_exists"] is True
    assert "Boundary-speed V0 is not strong enough" in report
