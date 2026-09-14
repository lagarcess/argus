"""The four ratio declarations: multiples, yields, effective rates, debt to income, fees."""

from __future__ import annotations

import pytest

from tests.domain.calculations.support import answer_value, row_value, run_calculation


def test_price_multiple_solves_each_of_its_three_fields() -> None:
    multiple = run_calculation(
        "price_multiple",
        {
            "currency": "USD",
            "symbol": "AAPL",
            "price": 150,
            "per_share": 6,
            "multiple": None,
        },
    )
    assert answer_value(multiple) == pytest.approx(25.0)
    assert row_value(multiple, "earnings_yield_pct") == pytest.approx(4.0)
    price = run_calculation(
        "price_multiple",
        {"currency": "USD", "price": None, "per_share": 6, "multiple": 25},
    )
    assert answer_value(price) == pytest.approx(150.0)
    per_share = run_calculation(
        "price_multiple",
        {"currency": "USD", "price": 150, "per_share": None, "multiple": 25},
    )
    assert answer_value(per_share) == pytest.approx(6.0)
    zero = run_calculation(
        "price_multiple",
        {"currency": "USD", "price": 150, "per_share": 0, "multiple": None},
    )
    assert zero.outcome.status == "invalid" and zero.outcome.failure.fields == [
        "per_share"
    ]


def test_income_yield_and_its_monthly_income_row() -> None:
    card = run_calculation(
        "income_yield",
        {"currency": "USD", "annual_income": 4, "price": 100, "yield_pct": None},
    )
    assert answer_value(card) == pytest.approx(4.0)
    assert row_value(card, "monthly_income") == pytest.approx(4 / 12, abs=0.01)
    price = run_calculation(
        "income_yield",
        {"currency": "USD", "annual_income": 4, "price": None, "yield_pct": 4},
    )
    assert answer_value(price) == pytest.approx(100.0)


def test_effective_rate_without_and_with_fees() -> None:
    plain = run_calculation(
        "effective_rate",
        {"currency": "USD", "nominal_rate_pct": 12, "compounding_per_year": 12},
    )
    assert answer_value(plain) == pytest.approx(12.68)
    assert plain.presentation.rows == []
    loan = run_calculation(
        "effective_rate",
        {
            "currency": "USD",
            "nominal_rate_pct": 10,
            "compounding_per_year": 12,
            "amount": 10_000,
            "fees": 300,
            "periods": 36,
        },
    )
    assert answer_value(loan) > 12.0
    assert row_value(loan, "payment") == pytest.approx(322.67)
    assert row_value(loan, "total_cost") == pytest.approx(
        322.67 * 36 + 300 - 10_000, abs=0.5
    )
    assert [note.locale_key for note in loan.presentation.notes] == [
        "tools.calc.notes.includes_fees"
    ]


def test_debt_to_income_from_any_two_fields() -> None:
    ratio = run_calculation(
        "debt_to_income",
        {
            "currency": "MXN",
            "monthly_debt_payments": 1_500,
            "monthly_income": 5_000,
            "ratio_pct": None,
        },
    )
    assert answer_value(ratio) == pytest.approx(30.0)
    assert row_value(ratio, "income_after_debt") == pytest.approx(3_500.0)
    income = run_calculation(
        "debt_to_income",
        {
            "currency": "MXN",
            "monthly_debt_payments": 1_500,
            "monthly_income": None,
            "ratio_pct": 30,
        },
    )
    assert answer_value(income) == pytest.approx(5_000.0)
    zero = run_calculation(
        "debt_to_income",
        {
            "currency": "MXN",
            "monthly_debt_payments": 1_500,
            "monthly_income": 0,
            "ratio_pct": None,
        },
    )
    assert zero.outcome.failure.fields == ["monthly_income"]


def test_expense_ratio_and_its_cost_over_thirty_years() -> None:
    card = run_calculation(
        "expense_ratio",
        {
            "currency": "USD",
            "assets": 10_000,
            "annual_fee": None,
            "ratio_pct": 0.5,
            "years": 30,
            "growth_rate_pct": 7,
        },
    )
    assert answer_value(card) == pytest.approx(50.0)
    assert row_value(card, "ending_without_fee") == pytest.approx(76_122.55, abs=0.01)
    assert row_value(card, "cost_over_years") == pytest.approx(
        row_value(card, "ending_without_fee") - row_value(card, "ending_with_fee"),
        abs=0.01,
    )
    ratio = run_calculation(
        "expense_ratio",
        {"currency": "USD", "assets": 10_000, "annual_fee": 50, "ratio_pct": None},
    )
    assert answer_value(ratio) == pytest.approx(0.5)
