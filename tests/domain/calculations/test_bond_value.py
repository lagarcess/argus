from __future__ import annotations

import pytest

from tests.domain.calculations.support import answer_value, row_value, run_calculation


def test_price_from_yield_matches_the_bond_table_and_yield_inverts_it() -> None:
    priced = run_calculation(
        "bond_value",
        {
            "currency": "USD",
            "face_value": 1_000,
            "coupon_rate_pct": 5,
            "years": 10,
            "coupons_per_year": 2,
            "price": None,
            "yield_to_maturity_pct": 6,
        },
    )
    assert answer_value(priced) == pytest.approx(925.61)
    assert row_value(priced, "annual_coupon") == pytest.approx(50.0)
    yielded = run_calculation(
        "bond_value", {**priced.arguments, "price": 925.61, "yield_to_maturity_pct": None}
    )
    assert answer_value(yielded) == pytest.approx(6.0, abs=0.01)


def test_a_million_pesos_in_a_local_bond_keeps_its_currency() -> None:
    card = run_calculation(
        "bond_value",
        {
            "currency": "DOP",
            "face_value": 1_000_000,
            "coupon_rate_pct": 9,
            "years": 3,
            "coupons_per_year": 2,
            "price": None,
            "yield_to_maturity_pct": 10,
        },
    )
    assert card.presentation.answer.unit.interpolation_args == {"code": "DOP"}
    assert row_value(card, "total_coupons") == pytest.approx(270_000.0)
    assert card.presentation.inputs[0].name == "symbol"


def test_a_zero_price_cannot_yield() -> None:
    card = run_calculation(
        "bond_value",
        {
            "currency": "USD",
            "face_value": 1_000,
            "coupon_rate_pct": 5,
            "years": 10,
            "price": 0,
            "yield_to_maturity_pct": None,
        },
    )
    assert card.outcome.status == "invalid"
    assert card.outcome.failure.fields == ["price"]
