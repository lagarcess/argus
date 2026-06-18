import pytest
from argus.domain.strategy_capabilities import STRATEGY_CAPABILITIES


def test_registry_keeps_locale_phrases_out_of_execution_capabilities():
    """Execution capabilities are not the multilingual NLU layer."""
    if "dca_accumulation" not in STRATEGY_CAPABILITIES:
        pytest.skip("dca_accumulation not in registry")

    forbidden_fragments = {
        "compra",
        "comprar",
        "mantener",
        "semanal",
        "mensual",
        "diario",
        "quincenal",
        "trimestral",
        "tendencia",
        "ruptura",
    }
    all_aliases: list[str] = []
    for capability in STRATEGY_CAPABILITIES.values():
        all_aliases.extend(capability.aliases)
        assert capability.display_name not in capability.aliases
        for spec in capability.parameters.values():
            for aliases in spec.value_aliases.values():
                all_aliases.extend(aliases)

    leaked = [
        alias
        for alias in all_aliases
        if any(fragment in alias.casefold() for fragment in forbidden_fragments)
    ]
    assert leaked == []

    cap = STRATEGY_CAPABILITIES["dca_accumulation"]
    assert "dca_cadence" in cap.parameters
    spec = cap.parameters["dca_cadence"]
    assert set(spec.allowed_values) == {
        "daily",
        "weekly",
        "biweekly",
        "monthly",
        "quarterly",
    }


def test_normalizer_exists():
    """Task 2: Normalizer module should exist and expose key functions."""
    try:
        from argus.domain import slot_normalizer
    except ImportError:
        pytest.fail("slot_normalizer module not found")

    assert hasattr(slot_normalizer, "normalize_template_name")
    assert hasattr(slot_normalizer, "normalize_parameter_value")


def test_normalizes_canonical_cadence_values():
    """The LLM should return canonical cadence values, not localized prose."""
    from argus.domain.slot_normalizer import normalize_parameter_value

    assert (
        normalize_parameter_value("dca_accumulation", "dca_cadence", "weekly")
        == "weekly"
    )
    assert (
        normalize_parameter_value("dca_accumulation", "dca_cadence", "biweekly")
        == "biweekly"
    )
    assert (
        normalize_parameter_value("dca_accumulation", "dca_cadence", "daily")
        == "daily"
    )

    assert (
        normalize_parameter_value("dca_accumulation", "dca_cadence", "  WEEKLY  ")
        == "weekly"
    )
    assert (
        normalize_parameter_value("dca_accumulation", "dca_cadence", "unknown")
        == "unknown"
    )


def test_normalizes_template_names():
    """Normalizer should canonicalize machine identifiers only."""
    from argus.domain.slot_normalizer import normalize_template_name

    assert normalize_template_name("buy_and_hold") == "buy_and_hold"
    assert normalize_template_name("lump_sum_investment") == "buy_and_hold"
    assert normalize_template_name("buy and hold") is None
    assert normalize_template_name("dca") == "dca_accumulation"
    assert normalize_template_name("DCA Accumulation") is None
    assert normalize_template_name("recurring_buy") == "dca_accumulation"
    assert normalize_template_name("compra y mantén") is None
