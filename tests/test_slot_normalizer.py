import pytest
from argus.domain.strategy_capabilities import STRATEGY_CAPABILITIES


def test_registry_has_value_aliases():
    """Task 1: Every strategy parameter spec should support localized aliases for its allowed values."""
    if "dca_accumulation" not in STRATEGY_CAPABILITIES:
        pytest.skip("dca_accumulation not in registry")

    cap = STRATEGY_CAPABILITIES["dca_accumulation"]
    assert "dca_cadence" in cap.parameters
    spec = cap.parameters["dca_cadence"]

    # This will fail initially because 'value_aliases' is not yet on ParameterSpec
    assert hasattr(spec, "value_aliases"), "ParameterSpec should have value_aliases attribute"
    assert "weekly" in spec.value_aliases
    assert "semanal" in spec.value_aliases["weekly"]

def test_normalizer_exists():
    """Task 2: Normalizer module should exist and expose key functions."""
    try:
        from argus.domain import slot_normalizer
    except ImportError:
        pytest.fail("slot_normalizer module not found")

    assert hasattr(slot_normalizer, "normalize_template_name")
    assert hasattr(slot_normalizer, "normalize_parameter_value")

def test_normalizes_locale_cadence_values():
    """Task 2: Normalizer should map Spanish terms to English canonical keys."""
    from argus.domain.slot_normalizer import normalize_parameter_value

    # Test DCA cadence
    assert normalize_parameter_value("dca_accumulation", "dca_cadence", "semanal") == "weekly"
    assert normalize_parameter_value("dca_accumulation", "dca_cadence", "diario") == "daily"
    assert normalize_parameter_value("dca_accumulation", "dca_cadence", "mensual") == "monthly"

    # Test case insensitivity and whitespace
    assert normalize_parameter_value("dca_accumulation", "dca_cadence", "  SEMANAL  ") == "weekly"

    # Test unknown values (should return original or raise? Let's assume return original for now)
    assert normalize_parameter_value("dca_accumulation", "dca_cadence", "unknown") == "unknown"

def test_normalizes_template_names():
    """Task 2: Normalizer should canonicalize strategy template names."""
    from argus.domain.slot_normalizer import normalize_template_name

    assert normalize_template_name("dca") == "dca_accumulation"
    assert normalize_template_name("DCA Accumulation") == "dca_accumulation"
    assert normalize_template_name("promedio de costo") == "dca_accumulation"
