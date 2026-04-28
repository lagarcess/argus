from argus.domain.strategy_capabilities import STRATEGY_CAPABILITIES


def test_registry_contains_all_alpha_templates():
    expected = {
        "buy_the_dip",
        "rsi_mean_reversion",
        "moving_average_crossover",
        "dca_accumulation",
        "momentum_breakout",
        "trend_follow",
    }
    assert set(STRATEGY_CAPABILITIES.keys()) == expected


def test_dca_accumulation_has_cadence_parameter():
    dca = STRATEGY_CAPABILITIES["dca_accumulation"]
    assert "dca_cadence" in dca.parameters
    spec = dca.parameters["dca_cadence"]
    assert spec.policy == "clarify_if_missing"
    assert spec.default == "monthly"
    assert spec.allowed_values == ["daily", "weekly", "monthly"]


def test_strategy_aliases_are_present():
    for cap in STRATEGY_CAPABILITIES.values():
        assert len(cap.aliases) > 0
        assert cap.display_name != ""
