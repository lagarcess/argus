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


def test_strategy_aliases_are_machine_identifiers():
    for cap in STRATEGY_CAPABILITIES.values():
        assert len(cap.aliases) > 0
        assert cap.display_name != ""
        for alias in cap.aliases:
            assert alias == alias.strip().casefold()
            assert " " not in alias
            assert "-" not in alias


def test_buy_and_hold_aliases_are_machine_compatibility_not_nlu():
    """Capability aliases are not the multilingual interpretation layer."""
    bah = STRATEGY_CAPABILITIES["buy_and_hold"]
    assert bah.display_name == "Buy and Hold"
    assert "lump_sum_investment" in bah.aliases
    assert "one_time_investment" in bah.aliases
    assert "buy and hold" not in bah.aliases
    assert "hold" not in bah.aliases
    assert "comprar y mantener" not in bah.aliases


def test_registry_aliases_are_not_orchestrator_nlu():
    """The registry exposes machine compatibility, not prose extraction."""
    import importlib.util

    assert importlib.util.find_spec("argus.domain.orchestrator") is None
    for capability in STRATEGY_CAPABILITIES.values():
        assert capability.display_name not in capability.aliases


def test_buy_and_hold_canonical_template():
    """normalize_template_name() resolves canonical/internal aliases only."""
    assert normalize_template_name("buy_and_hold") == "buy_and_hold"
    assert normalize_template_name("lump_sum_investment") == "buy_and_hold"
    assert normalize_template_name("buy and hold") is None
    assert normalize_template_name("hold") is None
    assert normalize_template_name("comprar y mantener") is None
