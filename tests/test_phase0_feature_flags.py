import pytest

from rpmi.config import FeatureFlagError, FeatureFlags, RunConfig, SimConfig, validate_v0_flags


@pytest.mark.parametrize("flag_name", ["sumo", "mobil", "learning", "action_bundle"])
def test_v0_feature_lock_blocks_forbidden_flags(flag_name):
    flags = FeatureFlags(**{flag_name: True})
    config = RunConfig(flags=flags)

    with pytest.raises(FeatureFlagError, match=flag_name):
        validate_v0_flags(config)


def test_v0_feature_lock_accepts_phase0_defaults():
    validate_v0_flags(RunConfig())


def test_v0_feature_lock_blocks_rolling_decision_mode():
    config = RunConfig(sim=SimConfig(decision_mode="rolling"))

    with pytest.raises(FeatureFlagError, match="single_t0_micro_episode"):
        validate_v0_flags(config)

