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
    assert row_value(card, "real_annual_rate_pct") == pytest.approx(3.88, abs=0.01)


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
