from argus.domain.cadences import SUPPORTED_DCA_CADENCE_VALUES
from argus.domain.slot_normalizer import normalize_template_name
from argus.domain.strategy_capabilities import STRATEGY_CAPABILITIES


def test_registry_contains_all_alpha_templates():
    expected = {
        "buy_and_hold",
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
    assert spec.allowed_values == list(SUPPORTED_DCA_CADENCE_VALUES)


def test_strategy_aliases_are_present():
    for cap in STRATEGY_CAPABILITIES.values():
        assert len(cap.aliases) > 0
        assert cap.display_name != ""


def test_buy_and_hold_aliases():
    """Verify buy_and_hold can be found via Spanish aliases."""
    bah = STRATEGY_CAPABILITIES["buy_and_hold"]
    assert bah.display_name == "Buy and Hold"
    assert "comprar y mantener" in bah.aliases
    assert "buy and hold" in bah.aliases
    assert "hold" in bah.aliases


def test_buy_and_hold_aliases_are_registry_data_not_orchestrator_nlu():
    """The registry can expose aliases without restoring legacy extraction."""
    import importlib.util

    assert importlib.util.find_spec("argus.domain.orchestrator") is None
    assert "comprar y mantener" in STRATEGY_CAPABILITIES["buy_and_hold"].aliases


def test_buy_and_hold_canonical_template():
    """normalize_template_name() should resolve aliases to buy_and_hold."""
    assert normalize_template_name("buy and hold") == "buy_and_hold"
    assert normalize_template_name("comprar y mantener") == "buy_and_hold"
    assert normalize_template_name("mantener") == "buy_and_hold"
    assert normalize_template_name("hold") == "buy_and_hold"
    assert normalize_template_name("buy and hold") != "buy_the_dip"
