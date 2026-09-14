"""A market test stands in for money the reader could have put in the market as
one amount or one monthly buy: never a loan, never a plan that does both."""

from __future__ import annotations

import pytest
from argus.agent_runtime import answer_calculation
from argus.agent_runtime.calculation_rows import (
    _READER_MONEY,
    market_counterfactual_rows,
)
from argus.domain.calculations import get_calculation_declarations

from tests.domain.calculations.support import run_calculation


@pytest.fixture(autouse=True)
def _no_lookup(monkeypatch) -> None:
    def refuse(symbol: str):
        raise AssertionError(f"a dollar plan looked up {symbol}")

    monkeypatch.setattr(answer_calculation, "latest_market_close", refuse)


def _rows(kind: str, arguments: dict) -> dict | None:
    card = run_calculation(kind, {"currency": "USD", **arguments})
    assert card.outcome.status == "succeeded", card.outcome
    return market_counterfactual_rows(card.model_dump(mode="json"), language="en")


@pytest.mark.parametrize(
    ("kind", "arguments"),
    [
        (
            "time_value",
            {
                "direction": "borrow",
                "present_value": 200_000,
                "payment": None,
                "future_value": 0,
                "annual_rate_pct": 6,
                "periods": 360,
            },
        ),
        (
            "effective_rate",
            {
                "nominal_rate_pct": 7,
                "compounding_per_year": 12,
                "amount": 20_000,
                "fees": 500,
                "periods": 60,
            },
        ),
    ],
)
def test_a_loan_offers_no_market_test(kind, arguments) -> None:
    assert _rows(kind, arguments) is None


@pytest.mark.parametrize(
    ("kind", "arguments"),
    [
        (
            "growth_projection",
            {
                "start_value": 1_000,
                "contribution": 100,
                "end_value": None,
                "annual_rate_pct": 5,
                "periods": 12,
            },
        ),
        (
            "growth_projection",
            {
                "start_value": 1_000,
                "contribution": 1_200,
                "end_value": None,
                "annual_rate_pct": 5,
                "periods": 5,
                "periods_per_year": 1,
            },
        ),
        (
            "growth_projection",
            {
                "start_value": None,
                "contribution": 100,
                "end_value": 2_000,
                "annual_rate_pct": 0,
                "periods": 12,
            },
        ),
        (
            "time_value",
            {
                "direction": "save",
                "present_value": 1_000,
                "payment": None,
                "future_value": 20_000,
                "annual_rate_pct": 5,
                "periods": 120,
            },
        ),
    ],
)
def test_a_plan_that_starts_with_an_amount_and_adds_deposits_offers_no_market_test(
    kind, arguments
) -> None:
    assert _rows(kind, arguments) is None


def test_one_amount_or_one_monthly_deposit_keeps_its_market_test() -> None:
    plan = {"end_value": None, "annual_rate_pct": 5, "periods": 12}
    lump = _rows("growth_projection", {**plan, "start_value": 1_000, "contribution": 0})
    monthly = _rows("growth_projection", {**plan, "start_value": 0, "contribution": 100})

    assert lump is not None
    assert lump["rows"][0]["send_text"] == (
        "Test buying and holding SPY with 1000 USD over the last year"
    )
    assert monthly is not None
    assert monthly["rows"][0]["send_text"] == (
        "Test buying 100 USD of SPY every month over the last year"
    )


def test_every_listed_kind_names_its_declared_money_fields() -> None:
    declared = {item.name: item for item in get_calculation_declarations()}
    for kind, (start, deposit) in _READER_MONEY.items():
        fields = declared[kind].arguments_type.model_fields
        assert start in fields, kind
        assert deposit is None or deposit in fields, kind
