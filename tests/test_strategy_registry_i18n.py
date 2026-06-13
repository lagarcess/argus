from argus.domain.strategy_capabilities import STRATEGY_CAPABILITIES


def test_strategy_registry_is_not_a_locale_phrasebook():
    """The LLM owns multilingual semantics; capabilities stay canonical."""
    forbidden_fragments = {
        "buy and hold",
        "buy the dip",
        "compra",
        "comprar",
        "dollar cost averaging",
        "moving average",
        "mantener",
        "one time investment",
        "semanal",
        "mensual",
        "diario",
        "quincenal",
        "trimestral",
        "tendencia",
        "ruptura",
    }

    for key, capability in STRATEGY_CAPABILITIES.items():
        assert capability.aliases, f"Strategy {key} has no aliases"
        for alias in capability.aliases:
            assert " " not in alias, (
                f"Strategy {key} exposes phrase alias {alias!r}; "
                "aliases must be machine identifiers"
            )
            assert not any(
                fragment in alias.casefold() for fragment in forbidden_fragments
            ), f"Strategy {key} leaks locale phrase alias {alias!r}"

        for param_key, spec in capability.parameters.items():
            for aliases in spec.value_aliases.values():
                for alias in aliases:
                    assert not any(
                        fragment in alias.casefold()
                        for fragment in forbidden_fragments
                    ), f"Parameter {param_key} in {key} leaks locale alias {alias!r}"
