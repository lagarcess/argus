"""Worked arguments per declared calculation, shared by kernel and fixture tests."""

from __future__ import annotations

from typing import Any

WORKED_ARGUMENTS: dict[str, dict[str, Any]] = {
    "scaled_amount": {
        "currency": "USD",
        "amount": 1000,
        "rate": 2,
        "rate_unit": "percent",
        "operation": "multiply",
    },
    "time_value": {
        "direction": "borrow",
        "currency": "USD",
        "present_value": 200_000,
        "payment": None,
        "future_value": 0,
        "annual_rate_pct": 6,
        "periods": 360,
        "start_date": "2026-09-11",
        "sources": {
            "annual_rate_pct": {
                "kind": "page",
                "title": "Rate sheet",
                "url": "https://example.com/rates",
                "date": "2026-09-01",
            }
        },
    },
    "growth_projection": {
        "currency": "USD",
        "start_value": 10_000,
        "contribution": 0,
        "end_value": None,
        "annual_rate_pct": 1,
        "periods": 12,
        "inflation_rate_pct": 4,
    },
    "bond_value": {
        "currency": "DOP",
        "face_value": 1_000_000,
        "coupon_rate_pct": 9,
        "years": 3,
        "coupons_per_year": 2,
        "price": None,
        "yield_to_maturity_pct": 10,
    },
    "discounted_cash_flow": {
        "currency": "USD",
        "symbol": "AAPL",
        "cash_flow": 100,
        "growth_rate_pct": 5,
        "discount_rate_pct": 10,
        "years": 5,
        "terminal_growth_rate_pct": 2,
        "value": None,
    },
    "price_multiple": {
        "currency": "USD",
        "symbol": "AAPL",
        "price": 150,
        "per_share": 6,
        "multiple": None,
        "sources": {
            "price": {
                "kind": "page",
                "title": "Quote",
                "url": "https://example.com/aapl",
                "date": "2026-09-10",
            }
        },
    },
    "income_yield": {
        "currency": "USD",
        "annual_income": 4,
        "price": 100,
        "yield_pct": None,
    },
    "effective_rate": {
        "currency": "USD",
        "nominal_rate_pct": 10,
        "compounding_per_year": 12,
        "amount": 10_000,
        "fees": 300,
        "periods": 36,
    },
    "debt_to_income": {
        "currency": "MXN",
        "monthly_debt_payments": 1_500,
        "monthly_income": 5_000,
        "ratio_pct": None,
    },
    "expense_ratio": {
        "currency": "USD",
        "assets": 10_000,
        "annual_fee": None,
        "ratio_pct": 0.5,
        "years": 30,
        "growth_rate_pct": 7,
    },
    "ranked_comparison": {
        "currency": "DOP",
        "key_label": "Annual rate",
        "key_kind": "percent",
        "prefer": "lower",
        "items": [
            {"label": "Card A", "value": 24.9},
            {"label": "Card B", "value": 18.5},
            {"label": "Card C", "value": 18.5},
        ],
    },
    "valuation_scenarios": {
        "currency": "USD",
        "symbol": "AAPL",
        "price": 150,
        "per_share": 6,
        "growth_low_pct": 3,
        "growth_base_pct": 8,
        "growth_high_pct": 12,
        "multiple_low": 18,
        "multiple_base": 22,
        "multiple_high": 28,
        "horizon_years": 5,
    },
}

FAILING_ARGUMENTS: dict[str, dict[str, Any]] = {
    "time_value_payment_below_interest": {
        "direction": "borrow",
        "currency": "DOP",
        "present_value": 180_000,
        "payment": 2_000,
        "future_value": 0,
        "annual_rate_pct": 14,
        "periods": None,
    },
    "price_multiple_division_by_zero": {
        "currency": "USD",
        "symbol": "AAPL",
        "price": 150,
        "per_share": 0,
        "multiple": None,
    },
    "growth_projection_unreachable": {
        "currency": "USD",
        "start_value": 1_000,
        "end_value": 2_000,
        "annual_rate_pct": 0,
        "periods": None,
    },
}


def worked_arguments(name: str) -> dict[str, Any]:
    return dict(WORKED_ARGUMENTS[name])
