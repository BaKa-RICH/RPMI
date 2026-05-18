from datetime import datetime, timezone

from rpmi.config import RunConfig, config_to_canonical_dict, hash_config
from rpmi.reproducibility import deterministic_fake_state, make_run_id, set_global_seed
from rpmi.state import hash_state


def test_same_config_and_seed_reproduce_state_hash():
    config = RunConfig(scenario_id="toy", algorithm_id="phase0", seed=123)
    config_hash = hash_config(config_to_canonical_dict(config))

    set_global_seed(config.seed)
    state_a = deterministic_fake_state(config.seed)
    set_global_seed(config.seed)
    state_b = deterministic_fake_state(config.seed)

    assert hash_state(state_a) == hash_state(state_b)
    assert config_hash == hash_config(config_to_canonical_dict(config))


def test_different_seed_keeps_config_hash_stable_but_state_hash_changes():
    config_a = RunConfig(seed=1)
    config_b = RunConfig(seed=2)
    state_a = deterministic_fake_state(config_a.seed)
    state_b = deterministic_fake_state(config_b.seed)

    assert hash_config(config_to_canonical_dict(config_a)) == hash_config(
        config_to_canonical_dict(config_b)
    )
    assert hash_state(state_a) != hash_state(state_b)


def test_run_id_is_traceable_with_fixed_timestamp():
    config = RunConfig(scenario_id="s0", algorithm_id="alg", seed=9)
    run_id = make_run_id(
        config,
        "abcdef123456",
        timestamp=datetime(2026, 5, 18, 0, 0, 0, tzinfo=timezone.utc),
    )

    assert run_id == "run_20260518T000000Z_s0_alg_seed0009_abcdef123456"
