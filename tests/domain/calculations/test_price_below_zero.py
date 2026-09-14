"""A solved price below zero is refused, naming the input that makes it."""

from __future__ import annotations

import pytest

from tests.domain.calculations.support import run_calculation


@pytest.mark.parametrize(
    ("per_share", "multiple", "field"), [(-5, 20, "per_share"), (5, -20, "multiple")]
)
def test_a_solved_price_below_zero_names_its_input(per_share, multiple, field) -> None:
    card = run_calculation(
        "price_multiple",
        {
            "currency": "USD",
            "symbol": "AAPL",
            "price": None,
            "per_share": per_share,
            "multiple": multiple,
        },
    )
    assert card.outcome.status == "invalid"
    assert card.outcome.failure.code == "price_below_zero"
    assert card.outcome.failure.fields == [field]
