"""An expense ratio above the whole balance is refused before it compounds."""

from __future__ import annotations

import pytest

from tests.domain.calculations.support import run_calculation

BASE = {
    "currency": "USD",
    "symbol": "VOO",
    "assets": 1_000,
    "years": 2,
    "growth_rate_pct": 0,
}


def test_a_fee_above_the_whole_balance_names_what_to_change() -> None:
    stated = run_calculation(
        "expense_ratio", {**BASE, "ratio_pct": 200, "annual_fee": None}
    )
    derived = run_calculation(
        "expense_ratio", {**BASE, "annual_fee": 3_000, "ratio_pct": None}
    )
    whole = run_calculation(
        "expense_ratio", {**BASE, "ratio_pct": 100, "annual_fee": None}
    )
    for card, field in ((stated, "ratio_pct"), (derived, "annual_fee")):
        assert card.outcome.status == "invalid"
        assert card.outcome.failure.code == "fee_above_balance"
        assert card.outcome.failure.fields == [field]
    assert whole.outcome.status == "succeeded"
    assert whole.outcome.result["ending_with_fee"] == pytest.approx(0.0)
