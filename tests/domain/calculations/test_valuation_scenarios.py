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


@pytest.mark.parametrize(
    "field", ["growth_low_pct", "growth_base_pct", "growth_high_pct"]
)
@pytest.mark.parametrize("growth", [-100, -100.01])
def test_total_loss_boundary_on_every_scenario(field: str, growth: float) -> None:
    arguments = {
        **_APPLE,
        "growth_low_pct": -100,
        "growth_base_pct": -100,
        "growth_high_pct": -100,
        field: growth,
        "amount": 10000,
    }
    card = run_calculation("valuation_scenarios", arguments)
    if growth < -100:
        assert card.outcome.status == "invalid"
    else:
        assert card.outcome.status == "succeeded"
        for label in ("low", "base", "high"):
            assert row_value(card, f"value_at_horizon_{label}") == 0
            assert row_value(card, f"annual_return_pct_{label}") == -100


def test_an_invested_amount_is_carried_to_the_horizon_and_leads_the_card() -> None:
    card = run_calculation("valuation_scenarios", {**_APPLE, "amount": 10_000})
    base_price = row_value(card, "price_at_horizon_base")
    # The card rounds each row once, so the check allows a cent of rounding.
    assert row_value(card, "value_at_horizon_base") == pytest.approx(
        10_000 * base_price / 150, abs=0.5
    )
    assert card.presentation.answer is not None
    assert card.presentation.answer.name == "value_at_horizon_base"
    assert row_value(card, "value_at_horizon_low") < row_value(
        card, "value_at_horizon_high"
    )
    amount = next(fact for fact in card.presentation.inputs if fact.name == "amount")
    assert amount.editable and amount.value == 10_000


def test_missing_bounds_fall_back_to_the_base_and_are_named_as_assumptions() -> None:
    card = run_calculation(
        "valuation_scenarios",
        {
            "currency": "USD",
            "symbol": "NVDA",
            "price": 218.36,
            "per_share": 4.5,
            "growth_base_pct": 25,
            "horizon_years": 10,
            "amount": 10_000,
        },
    )
    assert card.outcome.status == "succeeded"
    assert row_value(card, "current_multiple") == pytest.approx(218.36 / 4.5, abs=0.01)
    assert row_value(card, "price_at_horizon_low") == row_value(
        card, "price_at_horizon_base"
    )
    assert row_value(card, "price_at_horizon_high") == row_value(
        card, "price_at_horizon_base"
    )
    assert [note.locale_key for note in card.presentation.notes] == [
        "tools.calc.notes.scenarios_not_forecasts",
        "tools.calc.notes.single_growth_forecast",
        "tools.calc.notes.current_multiple_held",
        "tools.calc.notes.single_multiple",
    ]
    blank = next(
        fact for fact in card.presentation.inputs if fact.name == "growth_low_pct"
    )
    assert blank.value is None and not blank.unknown


def test_cases_out_of_low_to_high_order_name_the_input_that_breaks_it() -> None:
    base = {
        "currency": "USD",
        "symbol": "AAPL",
        "price": 200,
        "per_share": 8,
        "growth_low_pct": 3,
        "growth_base_pct": 6,
        "growth_high_pct": 9,
        "multiple_low": 20,
        "multiple_base": 25,
        "multiple_high": 30,
        "horizon_years": 5,
    }
    assert run_calculation("valuation_scenarios", base).outcome.status == "succeeded"
    for changes, field in (
        ({"growth_low_pct": 12}, "growth_low_pct"),
        ({"multiple_low": 40}, "multiple_low"),
        ({"growth_high_pct": 1}, "growth_high_pct"),
        ({"multiple_high": 10}, "multiple_high"),
    ):
        card = run_calculation("valuation_scenarios", {**base, **changes})
        assert card.outcome.status == "invalid"
        assert card.outcome.failure.code == "scenarios_out_of_order"
        assert card.outcome.failure.fields == [field]
