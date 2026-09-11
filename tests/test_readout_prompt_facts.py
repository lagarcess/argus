from copy import deepcopy

import pytest


@pytest.mark.parametrize("language", ["en", "es-419"])
def test_model_facts_use_card_precision_without_changing_stored_values(language):
    from argus.domain.result_readout_prompt_facts import readout_prompt_facts

    facts = {
        "symbols": ["DOCN"],
        "facts": {
            "portfolio.max_drawdown": {
                "value": -42.12,
                "unit": "percent",
                "meaning": "Investment decline",
                "presentation": ["absolute_magnitude"],
                "basis": "flow_adjusted_drawdown",
            },
            "portfolio.ending_equity": {
                "value": 6644.07,
                "unit": "currency",
                "currency": "USD",
                "meaning": "Ending account balance",
                "provenance": {"path": "chart.series"},
            },
            "portfolio.drawdown_illustration": {
                "value": 421.2,
                "unit": "currency",
                "basis": "starting_capital_illustration",
            },
        },
        "series": {
            "portfolio_equity": {
                "unit": "currency",
                "currency": "USD",
                "basis": "nominal_equity_close",
                "points": [{"time": "2026-09-09", "value": 6644.07}],
            }
        },
    }
    before = deepcopy(facts)
    prompt = readout_prompt_facts(facts, language=language)
    assert prompt["facts"]["portfolio.max_drawdown"]["value"] == 42.1
    assert prompt["facts"]["portfolio.max_drawdown"]["display"] == "42.1%"
    assert prompt["facts"]["portfolio.ending_equity"]["value"] == 6644
    assert prompt["facts"]["portfolio.ending_equity"]["display"] == "$6,644"
    assert "portfolio.drawdown_illustration" not in prompt["facts"]
    assert "basis" not in prompt["facts"]["portfolio.max_drawdown"]
    assert "provenance" not in prompt["facts"]["portfolio.ending_equity"]
    assert prompt["series"]["portfolio_equity"]["points"][0]["value"] == 6644
    assert facts == before


@pytest.mark.parametrize("language", ["en", "es-419"])
def test_percent_projection_keeps_value_and_unit_consistent(language):
    from argus.domain.result_readout_grounding import accepted_readout_text
    from argus.domain.result_readout_prompt_facts import readout_prompt_facts

    row = {"value": 1.0, "unit": "ratio", "presentation": ["fraction_as_percent"]}
    stored = {"facts": {"portfolio.win_rate": row}}
    projected = readout_prompt_facts(stored, language=language)["facts"][
        "portfolio.win_rate"
    ]
    assert projected["value"] == 100.0
    assert projected["unit"] == "percent"
    assert projected["display"] == "100.0%"
    assert row["value"] == 1.0 and row["unit"] == "ratio"
    draft = {
        "language": language,
        "text": "100.0%.",
        "figures": [{"fact_key": "portfolio.win_rate", "value": projected["value"]}],
    }
    assert accepted_readout_text(draft, facts=stored, language=language) == (
        draft["text"],
        None,
    )
