from __future__ import annotations

import pytest

from tests.domain.calculations.support import answer_value, row_value, run_calculation


def test_compounding_with_contributions_and_what_inflation_leaves() -> None:
    card = run_calculation(
        "growth_projection",
        {
            "currency": "USD",
            "start_value": 1_000,
            "contribution": 100,
            "end_value": None,
            "annual_rate_pct": 7,
            "periods": 120,
            "inflation_rate_pct": 3,
        },
    )
    assert answer_value(card) == pytest.approx(19_318.14, abs=0.01)
    assert row_value(card, "total_contributed") == pytest.approx(13_000.0)
    assert row_value(card, "real_end_value") < answer_value(card)
    # 7% compounds monthly to 7.23% a year, which 3% inflation leaves at 4.11%.
    assert row_value(card, "real_annual_rate_pct") == pytest.approx(4.11, abs=0.01)


@pytest.mark.parametrize(
    ("annual_rate_pct", "periods_per_year", "inflation_rate_pct", "real_rate_pct"),
    [(12, 12, 0, 12.68), (7, 1, 3, 3.88)],
)
def test_the_rate_after_inflation_compounds_the_stated_rate_to_a_year_first(
    annual_rate_pct, periods_per_year, inflation_rate_pct, real_rate_pct
) -> None:
    card = run_calculation(
        "growth_projection",
        {
            "currency": "USD",
            "start_value": 1_000,
            "end_value": None,
            "annual_rate_pct": annual_rate_pct,
            "periods": periods_per_year,
            "periods_per_year": periods_per_year,
            "inflation_rate_pct": inflation_rate_pct,
        },
    )
    assert row_value(card, "real_annual_rate_pct") == pytest.approx(
        real_rate_pct, abs=0.01
    )


def test_the_starting_balance_a_goal_needs_is_the_deposit_not_zero() -> None:
    card = run_calculation(
        "growth_projection",
        {
            "currency": "USD",
            "start_value": None,
            "contribution": 100,
            "end_value": 2_000,
            "annual_rate_pct": 0,
            "periods": 12,
        },
    )
    assert card.outcome.status == "succeeded"
    assert answer_value(card) == pytest.approx(800.0)
    assert row_value(card, "total_contributed") == pytest.approx(2_000.0)


def test_the_savings_account_losing_money_shows_a_negative_real_rate() -> None:
    card = run_calculation(
        "growth_projection",
        {
            "currency": "USD",
            "start_value": 10_000,
            "end_value": None,
            "annual_rate_pct": 1,
            "periods": 12,
            "inflation_rate_pct": 4,
        },
    )
    assert row_value(card, "real_annual_rate_pct") < 0
    assert row_value(card, "real_end_value") < 10_000


def test_solving_the_rate_and_the_periods_and_naming_an_unreachable_target() -> None:
    rate = run_calculation(
        "growth_projection",
        {
            "currency": "USD",
            "start_value": 1_000,
            "end_value": 2_000,
            "annual_rate_pct": None,
            "periods": 120,
        },
    )
    assert answer_value(rate) == pytest.approx(6.95, abs=0.01)
    periods = run_calculation(
        "growth_projection",
        {
            "currency": "USD",
            "start_value": 1_000,
            "end_value": 2_000,
            "annual_rate_pct": 7,
            "periods": None,
        },
    )
    assert answer_value(periods) == pytest.approx(119.2, abs=0.1)
    unreachable = run_calculation(
        "growth_projection",
        {
            "currency": "USD",
            "start_value": 1_000,
            "end_value": 2_000,
            "annual_rate_pct": 0,
            "periods": None,
        },
    )
    assert unreachable.outcome.status == "invalid"
    assert unreachable.outcome.failure.fields == ["annual_rate_pct"]


@pytest.mark.parametrize(
    ("per_year", "unit"),
    [(12, "tools.calc.units.months"), (1, "tools.calc.units.years"), (4, None)],
)
def test_periods_are_labeled_by_their_frequency(per_year, unit) -> None:
    card = run_calculation(
        "growth_projection",
        {
            "currency": "USD",
            "start_value": 1_000,
            "end_value": None,
            "annual_rate_pct": 5,
            "periods": 8,
            "periods_per_year": per_year,
        },
    )
    periods = next(fact for fact in card.presentation.inputs if fact.name == "periods")
    assert (periods.unit.locale_key if periods.unit else None) == unit


def test_a_goal_the_balance_already_meets_takes_no_periods() -> None:
    card = run_calculation(
        "growth_projection",
        {
            "currency": "USD",
            "start_value": 10_000,
            "contribution": 0,
            "end_value": 10_000,
            "annual_rate_pct": 5,
            "periods": None,
        },
    )
    assert card.outcome.status == "succeeded"
    assert answer_value(card) == pytest.approx(0.0)


def test_contributions_that_already_cover_the_goal_end_where_they_take_the_balance() -> (
    None
):
    card = run_calculation(
        "growth_projection",
        {
            "currency": "USD",
            "start_value": None,
            "contribution": 100,
            "end_value": 1_000,
            "annual_rate_pct": 0,
            "periods": 12,
        },
    )
    assert card.outcome.status == "succeeded"
    assert answer_value(card) == pytest.approx(0.0)
    assert card.outcome.result["end_value"] == pytest.approx(1_200.0)
    assert row_value(card, "growth") == pytest.approx(0.0)
    assert [note.locale_key for note in card.presentation.notes] == [
        "tools.calc.notes.already_covered"
    ]


def test_a_balance_already_past_the_goal_takes_no_periods() -> None:
    card = run_calculation(
        "growth_projection",
        {
            "currency": "USD",
            "start_value": 1_200,
            "contribution": 0,
            "end_value": 1_000,
            "annual_rate_pct": 12,
            "periods": None,
        },
    )
    assert card.outcome.status == "succeeded"
    assert answer_value(card) == pytest.approx(0.0)
    assert card.outcome.result["end_value"] == pytest.approx(1_200.0)
    assert row_value(card, "growth") == pytest.approx(0.0)
    assert [note.locale_key for note in card.presentation.notes] == [
        "tools.calc.notes.already_covered"
    ]


def test_a_declining_balance_solves_the_periods_to_its_lower_target() -> None:
    card = run_calculation(
        "growth_projection",
        {
            "currency": "USD",
            "start_value": 1_000,
            "contribution": 0,
            "end_value": 500,
            "annual_rate_pct": -10,
            "periods": None,
            "periods_per_year": 1,
        },
    )
    assert card.outcome.status == "succeeded"
    assert answer_value(card) == pytest.approx(6.6, abs=0.05)
