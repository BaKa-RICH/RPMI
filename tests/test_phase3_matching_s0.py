import csv

import pytest

from rpmi.logging_schema import CSV_LOG_SCHEMAS, append_matching_rows, write_empty_csv
from rpmi.matching import (
    DemandRecord,
    MatchingConfig,
    MatchingEdge,
    analyze_predictor_outcome,
    build_matching_cost_matrix,
    build_matching_edges,
    build_minimal_s0_samples,
    compute_demand_weights,
    compute_future_outcome_row,
    compute_inventory_from_matching,
    compute_predictor_row,
    edges_conflict,
    join_predictor_outcome_rows,
    matching_result_to_rows,
    solve_matching_slot_only_debug,
    solve_matching_v0_greedy_conflict,
)


def edge(
    edge_id: str,
    ramp_id: int,
    slot_id: str,
    gap: tuple[int, int] = (1, 2),
    tau: float = 1.0,
    weight: float = 1.0,
    P_R: float = 1.0,
    RD: float = 0.0,
) -> MatchingEdge:
    return MatchingEdge(
        edge_id=edge_id,
        ramp_id=ramp_id,
        slot_id=slot_id,
        physical_gap_id=gap,
        tau=tau,
        P_R=P_R,
        RD=RD,
        weight=weight,
    )


def test_one_ramp_one_edge_selects_and_z_zero():
    demand = {1: DemandRecord(1)}
    result = solve_matching_v0_greedy_conflict([edge("e1", 1, "s1")], demand)

    assert result.selected_edge_ids == ["e1"]
    assert result.S_R == pytest.approx(1.0)
    assert result.Z_R == pytest.approx(0.0)
    assert result.solver_name == "greedy_conflict"


def test_two_ramps_one_slot_conflict_selects_only_one():
    demand = {1: DemandRecord(1), 2: DemandRecord(2)}
    edges = [
        edge("e1", 1, "same_slot", weight=1.0),
        edge("e2", 2, "same_slot", weight=0.9),
    ]

    result = solve_matching_v0_greedy_conflict(edges, demand)

    assert result.selected_edge_ids == ["e1"]
    assert result.S_R == pytest.approx(1.0)
    assert result.Z_R == pytest.approx(1.0)
    assert result.unmatched_ramps == [2]


def test_one_ramp_two_edges_conflict_selects_one():
    demand = {1: DemandRecord(1)}
    edges = [
        edge("e1", 1, "s1", weight=0.8),
        edge("e2", 1, "s2", weight=1.2),
    ]

    result = solve_matching_v0_greedy_conflict(edges, demand)

    assert result.selected_edge_ids == ["e2"]
    assert result.S_R == pytest.approx(1.0)


def test_time_window_conflict_blocks_close_same_gap():
    e1 = edge("e1", 1, "s1", gap=(10, 20), tau=1.0)
    e2 = edge("e2", 2, "s2", gap=(10, 20), tau=1.5)
    demand = {1: DemandRecord(1), 2: DemandRecord(2)}

    assert edges_conflict(e1, e2, "time_window_default", T_merge=1.0, T_buffer=0.0)
    result = solve_matching_v0_greedy_conflict(
        [e1, e2],
        demand,
        MatchingConfig(T_merge=1.0, T_buffer=0.0),
    )

    assert result.selected_edge_ids == ["e2"]
    assert result.S_R == pytest.approx(1.0)
    assert result.Z_R == pytest.approx(1.0)


def test_same_gap_far_apart_may_both_select_under_time_window_default():
    e1 = edge("e1", 1, "s1", gap=(10, 20), tau=1.0)
    e2 = edge("e2", 2, "s2", gap=(10, 20), tau=3.0)
    demand = {1: DemandRecord(1), 2: DemandRecord(2)}

    assert not edges_conflict(e1, e2, "time_window_default", T_merge=1.0, T_buffer=0.0)
    assert edges_conflict(e1, e2, "whole_horizon_debug", T_merge=1.0, T_buffer=0.0)
    result = solve_matching_v0_greedy_conflict(
        [e1, e2],
        demand,
        MatchingConfig(T_merge=1.0, T_buffer=0.0),
    )

    assert set(result.selected_edge_ids) == {"e1", "e2"}
    assert result.S_R == pytest.approx(2.0)
    assert result.Z_R == pytest.approx(0.0)


def test_no_edge_gives_z_equals_d():
    demand = {1: DemandRecord(1), 2: DemandRecord(2)}
    result = solve_matching_v0_greedy_conflict([], demand)
    metrics = compute_inventory_from_matching(result)

    assert result.S_R == pytest.approx(0.0)
    assert result.Z_R == pytest.approx(result.D_H)
    assert metrics["Z_H_R"] == pytest.approx(2.0)


def test_demand_weights_default_to_one_and_formula_optional():
    default_weights = compute_demand_weights([1, 2])
    weighted = compute_demand_weights(
        [{"id": 1, "wait_time": 2.0, "distance_to_ramp_end": 60.0}],
        {"chi_w": 0.5, "chi_d": 0.2, "d_crit": 120.0},
    )

    assert default_weights[1].omega == pytest.approx(1.0)
    assert default_weights[2].omega == pytest.approx(1.0)
    assert weighted[1].omega == pytest.approx(2.1)


def test_hungarian_like_debug_matrix_only_slot_mode():
    edges = [edge("e1", 1, "s1")]
    demand = {1: DemandRecord(1)}

    assert build_matching_cost_matrix(edges, demand, "slot_only_debug") == [[1.0]]
    with pytest.raises(ValueError, match="slot_only_debug"):
        build_matching_cost_matrix(edges, demand, "time_window_default")

    result = solve_matching_slot_only_debug(edges, demand)
    assert result.solver_name == "slot_only_debug"
    assert result.conflict_mode == "slot_only_debug"


def test_build_matching_edges_filters_reservable_and_uses_metadata():
    samples = build_minimal_s0_samples()
    quality = samples[1].edge_qualities[0]
    demand = {1: DemandRecord(1)}
    matching_edges = build_matching_edges(
        [quality],
        demand,
        edge_metadata={quality.edge_id: {"physical_gap_id": (30, 40), "tau": 1.0}},
    )

    assert matching_edges[0].edge_id == quality.edge_id
    assert matching_edges[0].physical_gap_id == (30, 40)
    assert matching_edges[0].tau == pytest.approx(1.0)


def test_raw_gap_illusion_row_can_be_generated():
    samples = build_minimal_s0_samples()
    predictors = []
    outcomes = []
    for sample in samples:
        demand = {record.ramp_id: record for record in sample.demand_records}
        matching_edges = build_matching_edges(sample.edge_qualities, demand)
        matching = solve_matching_v0_greedy_conflict(matching_edges, demand)
        predictors.append(compute_predictor_row(sample, matching))
        outcomes.append(compute_future_outcome_row(sample))

    joined = join_predictor_outcome_rows(predictors, outcomes)
    illusion = next(row for row in joined if row["sample_id"] == "s0_raw_gap_illusion")
    summary = analyze_predictor_outcome(joined)

    assert illusion["G_H"] == 4
    assert illusion["S_H_R"] == pytest.approx(0.0)
    assert illusion["Z_H_R"] == pytest.approx(2.0)
    assert illusion["label_policy"] == "FIFO_no_production"
    assert illusion["future_ramp_waiting"] > 0.0
    assert summary["raw_high_z_high_count"] >= 1


def test_matching_csv_rows_are_writable(tmp_path):
    path = tmp_path / "matching.csv"
    write_empty_csv(path, CSV_LOG_SCHEMAS["matching.csv"])
    edges = [edge("e1", 1, "s1")]
    demand = {1: DemandRecord(1)}
    result = solve_matching_v0_greedy_conflict(edges, demand)

    append_matching_rows = __import__("rpmi.logging_schema", fromlist=["append_matching_rows"]).append_matching_rows
    append_matching_rows(path, matching_result_to_rows(result, edges, {"run_id": "run_test"}))

    with path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))

    assert rows[0]["matching_id"] == "m_greedy_conflict"
    assert rows[0]["matched"] == "True"
    assert rows[0]["weight"] == "1.0"
