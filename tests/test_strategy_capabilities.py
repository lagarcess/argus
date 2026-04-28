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
    assert spec.allowed_values == ["daily", "weekly", "monthly"]


def test_strategy_aliases_are_present():
    for cap in STRATEGY_CAPABILITIES.values():
        assert len(cap.aliases) > 0
        assert cap.display_name != ""


def test_buy_and_hold_aliases():
    """Verify buy_and_hold can be found via Spanish aliases — the exact bug scenario."""
    bah = STRATEGY_CAPABILITIES["buy_and_hold"]
    assert bah.display_name == "Buy and Hold"
    assert "comprar y mantener" in bah.aliases
    assert "buy and hold" in bah.aliases
    assert "hold" in bah.aliases


def test_buy_and_hold_deterministic_extraction():
    """Deterministic extraction should map 'comprar y mantener' to buy_and_hold."""
    from argus.domain.orchestrator import _extract_deterministic_intent

    extraction = _extract_deterministic_intent("comprar y mantener AAPL")
    assert extraction.template.value == "buy_and_hold"
    assert extraction.template.confidence >= 0.9
    assert extraction.symbols.value is not None
    assert "AAPL" in extraction.symbols.value


def test_buy_and_hold_canonical_template():
    """canonical_template() should resolve aliases to buy_and_hold."""
    from argus.domain.orchestrator import canonical_template

    assert canonical_template("buy and hold") == "buy_and_hold"
    assert canonical_template("comprar y mantener") == "buy_and_hold"
    assert canonical_template("mantener") == "buy_and_hold"
    assert canonical_template("hold") == "buy_and_hold"
    # Ensure buy_the_dip is NOT returned for these
    assert canonical_template("buy and hold") != "buy_the_dip"
