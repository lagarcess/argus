"""A fee counts in the effective rate only over a loan's amount and term."""

from __future__ import annotations

import pytest

from tests.domain.calculations.support import run_calculation

LOAN = {
    "currency": "USD",
    "nominal_rate_pct": 10,
    "compounding_per_year": 12,
    "amount": 10_000,
    "fees": 300,
    "periods": 36,
}


@pytest.mark.parametrize(
    ("changes", "field"), [({"amount": 0}, "amount"), ({"periods": 0}, "periods")]
)
def test_a_fee_without_the_loan_terms_names_what_is_missing(changes, field) -> None:
    card = run_calculation("effective_rate", {**LOAN, **changes})
    assert card.outcome.status == "invalid"
    assert card.outcome.failure.code == "fees_need_loan_terms"
    assert card.outcome.failure.fields == [field]


def test_a_rate_with_no_fee_still_converts_on_its_own() -> None:
    card = run_calculation(
        "effective_rate",
        {"currency": "USD", "nominal_rate_pct": 10, "compounding_per_year": 12},
    )
    assert card.outcome.status == "succeeded"
    assert run_calculation("effective_rate", LOAN).outcome.status == "succeeded"
