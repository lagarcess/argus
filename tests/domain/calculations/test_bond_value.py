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



BOND = {
    "currency": "USD",
    "face_value": 1_000,
    "coupon_rate_pct": 5,
    "coupons_per_year": 2,
    "price": None,
    "yield_to_maturity_pct": 6,
}


@pytest.mark.parametrize("solve", ["price", "yield"])
def test_a_term_between_coupon_dates_has_no_price_rather_than_a_rounded_one(
    solve,
) -> None:
    arguments = {**BOND, "years": 1.2}
    if solve == "yield":
        arguments = {**arguments, "price": 980, "yield_to_maturity_pct": None}
    card = run_calculation("bond_value", arguments)
    assert card.outcome.status != "succeeded"
    assert card.outcome.failure is not None
    assert card.outcome.failure.code == "periods_not_whole"
    assert card.outcome.failure.fields == ["years"]


def test_a_term_of_whole_coupon_periods_prices_with_coupons_over_the_same_schedule() -> (
    None
):
    card = run_calculation("bond_value", {**BOND, "years": 1.5})
    assert card.outcome.status == "succeeded"
    assert row_value(card, "total_coupons") == pytest.approx(75.0)
    assert answer_value(card) == pytest.approx(985.86, abs=0.01)
