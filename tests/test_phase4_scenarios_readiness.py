import csv
import json

import pytest

from rpmi.logging_schema import CSV_LOG_SCHEMAS, append_readiness_summary_rows, write_empty_csv
from rpmi.scenarios import (
    NearMissLabel,
    ReadinessReport,
    apply_template_perturbation,
    classify_near_miss,
    compute_readiness_metrics,
    diagnostic_rows_for_readiness,
    generate_initial_vehicles,
    generate_s0_samples,
    generate_s2_near_critical,
    generate_s5_boundary_templates,
    generate_s6_raw_gap_illusion,
    generate_state,
    make_scenario_config,
    parameter_sweep_for_readiness,
    readiness_allows_comparison,
    readiness_check,
    readiness_report_to_row,
    write_scenario_manifest,
)
from rpmi.slots import EdgeQuality


def run_report(scenario_id: str, seed: int = 1) -> ReadinessReport:
    config = make_scenario_config(scenario_id, seed=seed)
    state = generate_state(config)
    metrics = compute_readiness_metrics(state, config)
    return readiness_check(metrics, config)


def test_s0_s2_s5_s6_each_have_one_seed_readiness_pass():
    reports = {scenario_id: run_report(scenario_id, seed=7) for scenario_id in ["S0", "S2", "S5", "S6"]}

    assert all(report.readiness_pass for report in reports.values())
    assert reports["S2"].metrics["near_miss_edge_count"] > 0
    assert reports["S6"].metrics["G_H"] >= 2
    assert reports["S6"].metrics["S_R_0"] == pytest.approx(0.0)
    assert reports["S6"].metrics["Z_R_0"] >= 1.0


def test_readiness_fail_blocks_comparison():
    config = make_scenario_config("S2", readiness_targets={"near_miss_count_min": 99})
    report = readiness_check(compute_readiness_metrics(generate_state(config), config), config)

    assert not report.readiness_pass
    assert "near_miss_too_low" in report.fail_reason
    assert not readiness_allows_comparison(report)


def test_readiness_metrics_do_not_call_proposed_action_rollout(monkeypatch):
    import rpmi.scenarios as scenarios

    called = False

    def forbidden(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("proposed action rollout must not be used for readiness")

    monkeypatch.setattr(scenarios, "proposed_action_rollout", forbidden, raising=False)
    config = make_scenario_config("S2")
    metrics = scenarios.compute_readiness_metrics(scenarios.generate_state(config), config)

    assert not called
    assert metrics["used_proposed_action_rollout"] is False
    assert metrics["algorithm_independent"] is True


def test_parameter_sweep_records_failed_attempts_and_accepts_later_candidate():
    config = make_scenario_config("S2")
    sweep = parameter_sweep_for_readiness(
        config,
        [
            {"vehicles.boundary_pairs": ["HDV-HDV"], "vehicles.gap_widths": [7.0]},
            {"vehicles.boundary_pairs": ["CAV-HDV"], "vehicles.gap_widths": [7.0]},
        ],
    )

    assert sweep["attempt_count"] == 2
    assert sweep["accepted_count"] == 1
    assert sweep["rejected_count"] == 1
    assert sweep["rejected"][0]["readiness_pass"] is False
    assert "boundary_cav_unavailable" in sweep["rejected"][0]["fail_reason"]


def test_s0_generator_produces_stratified_readiness_inputs():
    config = make_scenario_config("S0", seed=10)
    states = generate_s0_samples(config, N=16)
    reports = [readiness_check(compute_readiness_metrics(state, config), config) for state in states]

    assert len(states) == 16
    assert any(report.metrics["G_H"] >= 2 and report.metrics["Z_R_0"] > 0 for report in reports)
    assert len({report.metrics["G_H"] for report in reports}) >= 2
    assert any(report.metrics["Z_R_0"] == 0 for report in reports)


def test_s2_s5_s6_template_helpers_return_expected_shapes():
    s2_config = make_scenario_config("S2")
    s5_config = make_scenario_config("S5")
    s6_config = make_scenario_config("S6")

    assert generate_s2_near_critical(s2_config).vehicles
    assert len(generate_s5_boundary_templates(s5_config)) == 4
    s6_report = readiness_check(
        compute_readiness_metrics(generate_s6_raw_gap_illusion(s6_config), s6_config),
        s6_config,
    )
    assert s6_report.metrics["raw_gap_illusion_count"] >= 1


def test_seed_perturbation_is_deterministic_and_seed_sensitive():
    config = make_scenario_config("S0", vehicles={"x_jitter": 0.25, "v_jitter": 0.1})

    first = generate_initial_vehicles(config)
    second = generate_initial_vehicles(config)
    third = generate_initial_vehicles(make_scenario_config("S0", seed=config.seed + 1, vehicles=config.vehicles))

    assert [(v.x, v.v) for v in first] == [(v.x, v.v) for v in second]
    assert [(v.x, v.v) for v in first] != [(v.x, v.v) for v in third]
    assert apply_template_perturbation(first, __import__("random").Random(1), make_scenario_config("S0")) == first


def test_near_miss_classifier_is_read_only_and_boundary_aware():
    quality = EdgeQuality(
        edge_id="e",
        ramp_id=1,
        slot_id="s",
        I_reach=1,
        I_surv=1,
        I_safe=0,
        I_rec=1,
        P_R=0.0,
        RD=0.2,
        W=2.0,
        V_phys_theory=1,
        V_phys_buffer=0,
        delta_W_req=3.0,
        is_reservable=False,
        reason_not_reservable="BUFFER_WIDTH_INSUFFICIENT",
        fail_reason_priority="BUFFER_WIDTH_INSUFFICIENT",
        surv_mode="deterministic_tau_generated",
        validity_mode="deterministic_v0_cascade_rd_proxy_v0_minimal",
        rd_components={"proxy_mode": "RD_proxy_v0_minimal"},
        min_safety_margin=2.0,
        reachability={"I_reach": 1},
    )

    label = classify_near_miss(quality, "CAV-HDV")
    no_cav = classify_near_miss(quality, "HDV-HDV")

    assert isinstance(label, NearMissLabel)
    assert label.is_near_miss
    assert label.available_modes == ("front_acc",)
    assert not no_cav.is_near_miss
    assert no_cav.reason == "no_boundary_cav_mode"


def test_manifest_and_readiness_summary_are_writable(tmp_path):
    config = make_scenario_config("S2", seed=22)
    state = generate_state(config)
    report = readiness_check(compute_readiness_metrics(state, config), config)
    manifest_path = tmp_path / "scenario_manifest.json"
    readiness_path = tmp_path / "readiness_summary.csv"
    write_empty_csv(readiness_path, CSV_LOG_SCHEMAS["readiness_summary.csv"])

    write_scenario_manifest(manifest_path, config, state, report)
    append_readiness_summary_rows(
        readiness_path,
        [
            readiness_report_to_row(
                report,
                {
                    "run_id": "run_test",
                    "step": 0,
                    "time": 0.0,
                    "decision_context_id": "dc_test",
                    "state_hash": report.metrics["state_hash"],
                    "config_hash": "config",
                    "code_version": "test",
                    "units_version": "rpmi_units_v1",
                },
            )
        ],
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "phase4_v1"
    assert manifest["scenario"]["readiness"]["algorithm_independent"] is True
    with readiness_path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    assert rows[0]["scenario_id"] == "S2"
    assert rows[0]["algorithm_independent"] == "True"


def test_diagnostic_rows_can_feed_existing_log_schemas():
    config = make_scenario_config("S2")
    metrics = compute_readiness_metrics(generate_state(config), config)
    rows = diagnostic_rows_for_readiness(metrics, {"run_id": "run_test"})

    assert rows["slots"]
    assert rows["edges"]
    assert "matching" in rows
    assert rows["near_miss_edges"]
    assert set(rows) == {"slots", "edges", "matching", "near_miss_edges"}
