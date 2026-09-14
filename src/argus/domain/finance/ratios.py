"""Ratios: multiples, yields, effective rates, debt to income, expense ratios."""

from __future__ import annotations

from dataclasses import dataclass

from argus.domain.finance import tvm
from argus.domain.finance.outcomes import NoSolution


def ratio(numerator: float, denominator: float, *, field: str) -> float | NoSolution:
    if denominator == 0:
        return NoSolution(field=field, code="division_by_zero")
    return numerator / denominator


def price_to_earnings(price: float, earnings_per_share: float) -> float | NoSolution:
    return ratio(price, earnings_per_share, field="earnings_per_share")


def income_yield(income: float, price: float) -> float | NoSolution:
    return ratio(income, price, field="price")


def effective_annual_rate(
    nominal: float, compounding_per_year: int
) -> float | NoSolution:
    if compounding_per_year <= 0:
        return NoSolution(field="compounding_per_year", code="no_periods")
    return (1.0 + nominal / compounding_per_year) ** compounding_per_year - 1.0


def nominal_from_effective(
    effective: float, compounding_per_year: int
) -> float | NoSolution:
    if compounding_per_year <= 0:
        return NoSolution(field="compounding_per_year", code="no_periods")
    if effective <= -1:
        return NoSolution(field="effective_rate", code="rate_out_of_range")
    return compounding_per_year * (
        (1.0 + effective) ** (1.0 / compounding_per_year) - 1.0
    )


def effective_apr(
    amount_received: float,
    fees: float,
    payment: float,
    periods: int,
    periods_per_year: int,
) -> float | NoSolution:
    """The annual rate a borrower really pays once fees leave the money received."""
    if periods_per_year <= 0 or periods <= 0:
        return NoSolution(field="periods", code="no_periods")
    net = amount_received - fees
    if net <= 0:
        return NoSolution(field="fees", code="fees_exceed_amount")
    per_period = tvm.rate(net, -payment, 0.0, periods)
    if isinstance(per_period, NoSolution):
        return NoSolution(field="payment", code=per_period.code)
    return per_period * periods_per_year


def debt_to_income(monthly_debt: float, monthly_income: float) -> float | NoSolution:
    return ratio(monthly_debt, monthly_income, field="monthly_income")


def expense_ratio(annual_fee: float, assets: float) -> float | NoSolution:
    return ratio(annual_fee, assets, field="assets")


@dataclass(frozen=True)
class ExpenseCost:
    ending_with_fee: float
    ending_without_fee: float
    cost: float


def expense_cost(
    assets: float, ratio_per_year: float, growth: float, years: float
) -> ExpenseCost:
    """What a yearly fee takes from a growing balance over ``years``."""
    with_fee = assets * ((1.0 + growth) * (1.0 - ratio_per_year)) ** years
    without_fee = assets * (1.0 + growth) ** years
    return ExpenseCost(
        ending_with_fee=with_fee,
        ending_without_fee=without_fee,
        cost=without_fee - with_fee,
    )
