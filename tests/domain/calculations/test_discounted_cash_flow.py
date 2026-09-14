from __future__ import annotations

import pytest

from tests.domain.calculations.support import answer_value, run_calculation

_BASE = {
    "currency": "USD",
    "cash_flow": 100,
    "discount_rate_pct": 10,
    "years": 5,
    "terminal_growth_rate_pct": 2,
}


def test_value_and_reverse_dcf_agree() -> None:
    valued = run_calculation(
        "discounted_cash_flow", {**_BASE, "growth_rate_pct": 5, "value": None}
    )
    assert answer_value(valued) == pytest.approx(1_446.21, abs=0.01)
    implied = run_calculation(
        "discounted_cash_flow", {**_BASE, "growth_rate_pct": None, "value": 1_446.21}
    )
    assert answer_value(implied) == pytest.approx(5.0, abs=0.01)


def test_a_discount_rate_below_terminal_growth_names_the_discount_rate() -> None:
    card = run_calculation(
        "discounted_cash_flow",
        {**_BASE, "discount_rate_pct": 1, "growth_rate_pct": 5, "value": None},
    )
    assert card.outcome.status == "invalid"
    assert card.outcome.failure.code == "discount_below_terminal_growth"
    assert card.outcome.failure.fields == ["discount_rate_pct"]
