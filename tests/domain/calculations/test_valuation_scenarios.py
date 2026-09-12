from __future__ import annotations

import pytest

from tests.domain.calculations.support import answer_value, row_value, run_calculation

_APPLE = {
    "currency": "USD",
    "symbol": "AAPL",
    "price": 150,
    "per_share": 6,
    "growth_low_pct": 3,
    "growth_base_pct": 8,
    "growth_high_pct": 12,
    "multiple_low": 18,
    "multiple_base": 22,
    "multiple_high": 28,
    "horizon_years": 5,
}


def test_scenarios_are_labeled_low_to_high_with_the_current_multiple() -> None:
    card = run_calculation("valuation_scenarios", _APPLE)
    assert answer_value(card) == pytest.approx(5.27, abs=0.01)
    assert row_value(card, "current_multiple") == pytest.approx(25.0)
    assert row_value(card, "price_at_horizon_low") < row_value(
        card, "price_at_horizon_base"
    )
    assert row_value(card, "price_at_horizon_base") < row_value(
        card, "price_at_horizon_high"
    )
    assert row_value(card, "price_at_horizon_base") == pytest.approx(193.95, abs=0.01)
    assert [note.locale_key for note in card.presentation.notes] == [
        "tools.calc.notes.scenarios_not_forecasts"
    ]


def test_the_symbol_rides_along_as_a_stated_input() -> None:
    card = run_calculation("valuation_scenarios", _APPLE)
    symbol = next(fact for fact in card.presentation.inputs if fact.name == "symbol")
    assert symbol.value == "AAPL"
    assert card.arguments["symbol"] == "AAPL"
