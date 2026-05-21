import csv
import json

import pytest

from rpmi.config import FeatureFlagError, FeatureFlags, RunConfig, SimConfig, validate_v0_flags
from rpmi.logging_schema import CSV_LOG_SCHEMAS
from rpmi.rolling import run_wave8_d2_suite


@pytest.fixture(scope="module")
def wave8_suite(tmp_path_factory):
    root = tmp_path_factory.mktemp("wave8_suite")
    result = run_wave8_d2_suite([0], output_root=root, batch_id="wave8_test_batch")
    gate = root / "wave8_test_batch" / "gate_D2_input"
    return {
        "result": result,
        "gate": gate,
        "aggregate": read_csv(gate / "aggregate_metrics.csv"),
        "contexts": read_csv(gate / "decision_contexts.csv"),
        "reservations": read_csv(gate / "rolling_reservations.csv"),
        "demand": read_csv(gate / "rolling_demand_lifecycle.csv"),
        "slots": read_csv(gate / "rolling_slot_consumption.csv"),
        "matching": read_csv(gate / "rolling_matching_trace.csv"),
        "commitment": read_csv(gate / "rolling_plan_commitment.csv"),
        "replans": read_csv(gate / "reservation_replans.csv"),
        "actions": read_csv(gate / "action_lifecycle.csv"),
        "failures": read_csv(gate / "rolling_failure_trace.csv"),
        "single": read_csv(gate / "rolling_vs_single_demand_metrics.csv"),
        "stale": read_csv(gate / "rolling_vs_stale_ablation_metrics.csv"),
        "no_commitment": read_csv(gate / "rolling_vs_no_commitment_metrics.csv"),
    }


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def by_scenario(rows, scenario_id):
    return [row for row in rows if row.get("scenario_id") == scenario_id]


def test_w8_feature_lock_accepts_only_spec_named_entrypoint():
    validate_v0_flags(
        RunConfig(
            sim=SimConfig(decision_mode="rolling_horizon_episode"),
            flags=FeatureFlags(rolling_reservation=True),
        )
    )
    with pytest.raises(FeatureFlagError, match="single_t0_micro_episode"):
        validate_v0_flags(RunConfig(sim=SimConfig(decision_mode="rolling")))
    with pytest.raises(FeatureFlagError, match="rolling_horizon_episode"):
        validate_v0_flags(RunConfig(flags=FeatureFlags(rolling_reservation=True)))


def test_w8_log_schemas_do_not_duplicate_shared_headers():
    for name in [
        "decision_contexts.csv",
        "reservation_replans.csv",
        "action_lifecycle.csv",
        "rolling_reservations.csv",
        "rolling_demand_lifecycle.csv",
        "rolling_slot_consumption.csv",
        "rolling_matching_trace.csv",
        "rolling_plan_commitment.csv",
        "rolling_failure_trace.csv",
    ]:
        columns = CSV_LOG_SCHEMAS[name]
        assert len(columns) == len(set(columns)), name


def test_w8_1_two_contexts(wave8_suite):
    assert max(int(row["rolling_decision_count"]) for row in wave8_suite["aggregate"]) > 1
    assert len({row["decision_context_id"] for row in wave8_suite["contexts"]}) > 1


def test_w8_2_persist_planned(wave8_suite):
    persists = [row for row in wave8_suite["replans"] if row["replan_decision"] == "persist"]
    assert persists
    assert all(row["replan_trigger"] == "" for row in persists)


def test_w8_3_refresh_or_supersede_reservation(wave8_suite):
    supersedes = [row for row in wave8_suite["reservations"] if row["status_after"] == "superseded"]
    assert supersedes
    assert all(row["lineage_root_reservation_id"] for row in supersedes)


def test_w8_4_cancel_unsafe_or_invalid_stale(wave8_suite):
    failures = [
        row
        for row in wave8_suite["failures"]
        if row["failure_reason"] in {"predicted_physical_validity_failed", "reservation_tau_expired"}
    ]
    assert failures
    assert all(row["can_join_full_chain"] == "True" for row in failures)


def test_w8_5_no_overlap_reject_logged(wave8_suite):
    assert any(row["lifecycle_status_after"] == "rejected_overlap" for row in wave8_suite["actions"])


def test_w8_6_partial_action_lifecycle_fields_exist(wave8_suite):
    fractions = [float(row["executed_fraction"]) for row in wave8_suite["actions"] if row["executed_fraction"]]
    assert fractions
    assert all(0.0 <= value <= 1.0 for value in fractions)
    assert {"cancelled_future_part", "cancel_reason", "overlap_reject_count"}.issubset(wave8_suite["actions"][0])


def test_w8_7_rolling_improves_stale(wave8_suite):
    rows = wave8_suite["stale"]
    assert rows
    assert any(float(row["rolling_vs_stale_delta_expired_reservation_count"]) < 0 for row in rows)
    assert any(float(row["rolling_vs_stale_delta_stale_harm_count"]) < 0 for row in rows)


def test_w8_8_expired_demand_returns(wave8_suite):
    assert any(row["status_after"] == "returned_after_expire" for row in wave8_suite["demand"])
    assert any(int(float(row["expired_returned_demand_count"])) > 0 for row in wave8_suite["aggregate"])


def test_w8_9_cancelled_demand_returns(wave8_suite):
    assert any(row["status_after"] == "returned_after_cancel" for row in wave8_suite["demand"])
    assert any(int(float(row["cancelled_returned_demand_count"])) > 0 for row in wave8_suite["aggregate"])


def test_w8_10_merged_demand_removed(wave8_suite):
    demand_rows = wave8_suite["demand"]
    merged = [row["demand_id"] for row in demand_rows if row["status_after"] == "merged"]
    assert merged
    for demand_id in merged:
        after_merge = False
        for row in demand_rows:
            if row["demand_id"] != demand_id:
                continue
            if after_merge:
                assert row["status_after"] != "active"
            if row["status_after"] == "merged":
                after_merge = True


def test_w8_11_consumed_gap_blocked(wave8_suite):
    assert any(row["slot_status_after"] == "consumed" for row in wave8_suite["slots"])
    assert all(row["duplicate_consumption_flag"] in {"False", "false", ""} for row in wave8_suite["slots"] if row["slot_status_after"] == "consumed")


def test_w8_12_duplicate_consumption_detected_but_not_consumed(wave8_suite):
    assert any(row["slot_status_after"] == "blocked_by_conflict" for row in wave8_suite["slots"])
    assert all(int(float(row["duplicate_gap_consumption_count"])) == 0 for row in wave8_suite["aggregate"])


def test_w8_13_lineage_join(wave8_suite):
    lineage_rows = [row for row in wave8_suite["reservations"] if row["lineage_parent_reservation_id"]]
    assert lineage_rows
    roots = {row["lineage_root_reservation_id"] for row in wave8_suite["reservations"]}
    assert all(row["lineage_root_reservation_id"] in roots for row in lineage_rows)


def test_w8_14_matching_trace_exists(wave8_suite):
    by_context = {}
    for row in wave8_suite["matching"]:
        by_context.setdefault(row["decision_context_id"], set()).add(row["matching_type"])
    assert by_context
    for types in by_context.values():
        assert {"baseline_no_action", "action_conditioned_selected", "stale_no_replan"}.issubset(types)


def test_w8_15_no_future_leak_and_no_hidden_fallback(wave8_suite):
    manifest = json.loads((wave8_suite["gate"] / "gate_D2_manifest.json").read_text(encoding="utf-8"))
    assert manifest["decision_status"] == "not_run"
    assert all(row["hidden_fallback_detected"] == "False" for row in wave8_suite["aggregate"])


def test_w8_16_stale_fails_rolling_recovers(wave8_suite):
    stale_rows = by_scenario(wave8_suite["aggregate"], "D2-S7-ROLLING-STALE")
    assert stale_rows
    assert int(float(stale_rows[0]["returned_demand_reassigned_count"])) >= 1
    assert float(stale_rows[0]["merge_success_rate_over_demand"]) >= float(stale_rows[0]["realized_unserved_demand_rate"])


def test_w8_17_demand_denominator_checked(wave8_suite):
    negative = by_scenario(wave8_suite["aggregate"], "D2-NEGATIVE-CONTROL")[0]
    assert negative["failed_reservation_rate"] == "0.0"
    assert negative["merge_success_rate_over_demand"] == "0.0"
    assert negative["realized_unserved_demand_rate"] == "1.0"
    assert all(row["demand_denominator_checked"] == "True" for row in wave8_suite["aggregate"])


def test_w8_18_full_failure_trace_join(wave8_suite):
    assert wave8_suite["failures"]
    assert all(row["can_join_full_chain"] == "True" for row in wave8_suite["failures"])
    assert all(row["action_id"] and row["edge_id"] and row["reservation_id"] and row["demand_id"] for row in wave8_suite["failures"])


def test_w8_19_planned_persists(wave8_suite):
    assert any(row["replan_decision"] == "persist" and row["status_after"] == "planned" for row in wave8_suite["replans"])


def test_w8_20_active_guidance_locked(wave8_suite):
    locked = [row for row in wave8_suite["commitment"] if row["commitment_status_after"] == "active_guidance_locked"]
    assert locked
    assert all(row["active_guidance_cancel_flag"] in {"False", "false", ""} for row in locked)


def test_w8_21_supersede_threshold(wave8_suite):
    no_commit = by_scenario(wave8_suite["aggregate"], "D2-NO-COMMITMENT-ABLATION")[0]
    assert int(float(no_commit["reservation_supersede_count"])) == 0
    assert any(
        row["replan_decision"] in {"persist", "persist_locked"}
        and row["improvement_margin"]
        and float(row["improvement_margin"]) <= float(row["switching_cost"]) + float(row["hysteresis_threshold"])
        for row in wave8_suite["replans"]
    )


def test_w8_22_no_commitment_churn(wave8_suite):
    assert wave8_suite["no_commitment"]
    assert any(float(row["rolling_vs_no_commitment_delta_churn_rate"]) < 0 for row in wave8_suite["no_commitment"])


def test_gate_d2_input_files_generated_without_decision(wave8_suite):
    required = [
        "aggregate_metrics.csv",
        "decision_contexts.csv",
        "reservation_replans.csv",
        "action_lifecycle.csv",
        "rolling_reservations.csv",
        "rolling_demand_lifecycle.csv",
        "rolling_slot_consumption.csv",
        "rolling_matching_trace.csv",
        "rolling_plan_commitment.csv",
        "rolling_failure_trace.csv",
        "rolling_vs_single_demand_metrics.csv",
        "rolling_vs_stale_ablation_metrics.csv",
        "rolling_vs_no_commitment_metrics.csv",
        "failure_summary.csv",
        "rolling_trace_samples",
    ]
    for name in required:
        assert (wave8_suite["gate"] / name).exists(), name
    assert not (wave8_suite["gate"] / "gate_D2_decision.json").exists()
    assert not (wave8_suite["gate"] / "gate_D2_report.md").exists()
    assert not (wave8_suite["gate"] / "gate_D2_claim_revision_plan.md").exists()


def test_gate_d2_input_trace_samples_cover_required_cases(wave8_suite):
    sample_dir = wave8_suite["gate"] / "rolling_trace_samples"
    for name in [
        "successful_closed_loop.csv",
        "failure_closed_loop.csv",
        "plan_lock_persist.csv",
        "replan_trigger.csv",
    ]:
        rows = read_csv(sample_dir / name)
        assert rows, name

