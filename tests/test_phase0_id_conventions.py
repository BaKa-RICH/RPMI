from rpmi.ids import (
    make_action_id,
    make_decision_context_id,
    make_edge_id,
    make_reservation_id,
    make_slot_id,
)


def test_decision_context_id_includes_run_and_step():
    value = make_decision_context_id("run_abc", step=7)

    assert value == "dc_run_abc_7"


def test_slot_id_includes_required_components():
    value = make_slot_id("frontA", "rearB", 3, "baseline")

    assert "frontA" in value
    assert "rearB" in value
    assert "k3" in value
    assert "baseline" in value


def test_edge_id_includes_required_components():
    value = make_edge_id("ramp9", "frontA", "rearB", 4, "act_none")

    assert "ramp9" in value
    assert "frontA" in value
    assert "rearB" in value
    assert "k4" in value
    assert "act_none" in value


def test_action_and_reservation_ids_include_bindings():
    action_id = make_action_id("front_acc", 2)
    edge_id = make_edge_id("r1", "f1", "r2", 1, "ctx")
    reservation_id = make_reservation_id(action_id, edge_id)

    assert action_id == "act_front_acc_2"
    assert action_id in reservation_id
    assert edge_id in reservation_id

