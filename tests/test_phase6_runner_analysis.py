import csv
import json
from dataclasses import asdict

from rpmi.analysis import aggregate_failures, aggregate_metrics, collect_rcmv_trace
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
