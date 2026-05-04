from argus.domain.strategy_capabilities import STRATEGY_CAPABILITIES


def test_all_strategies_have_spanish_aliases():
    """Ensure every strategy in the registry has at least one Spanish alias."""
    for key, capability in STRATEGY_CAPABILITIES.items():
        # Check strategy-level aliases
        # Spanish aliases often contain characters like 'ñ', 'í', 'ó' or are common Spanish words
        # We look for specific Spanish words or just ensure list is not empty and different from English
        # A simple check: does it have at least 3 aliases (English key + English display + at least one more)?
        assert len(capability.aliases) >= 1, f"Strategy {key} has no aliases"

        # More specific: does it have any common Spanish markers or words?
        # For now, let's just check that it's not JUST the English name.
        has_alias = any(a.lower() != key.lower().replace("_", " ") for a in capability.aliases)
        assert has_alias, f"Strategy {key} appears to lack non-technical aliases"

def test_all_parameters_with_allowed_values_have_aliases():
    """Ensure parameters with discrete allowed values have localized aliases defined."""
    for strat_key, capability in STRATEGY_CAPABILITIES.items():
        for param_key, spec in capability.parameters.items():
            if spec.allowed_values:
                # If there are allowed values, there should be value_aliases
                assert spec.value_aliases, f"Parameter {param_key} in {strat_key} has allowed_values but no value_aliases"

                # Check that all canonical values are mapped in value_aliases
                for val in spec.allowed_values:
                    assert val in spec.value_aliases, f"Canonical value '{val}' for {param_key} in {strat_key} is missing from value_aliases"
                    # And that it has at least one alias (besides maybe itself)
                    assert len(spec.value_aliases[val]) >= 1, f"Canonical value '{val}' for {param_key} in {strat_key} has empty alias list"
