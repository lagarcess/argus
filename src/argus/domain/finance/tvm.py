"""Time value of money, solved for any unknown.

The signed convention is the calculator one: money received is positive and
money paid is negative, so ``pv (1+r)^n + pmt (1+r t) ((1+r)^n - 1)/r + fv = 0``
for a rate ``r`` per period, ``n`` periods and ``t`` of 1 when payments fall
at the start of each period. Callers that speak in magnitudes translate at
their boundary; this module never guesses a direction.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from argus.domain.finance._roots import bracketed_root
from argus.domain.finance.outcomes import NoSolution

Timing = int  # 0 for payments at the end of a period, 1 at the start


def _growth(rate: float, periods: float) -> float:
    return (1.0 + rate) ** periods


def _annuity_factor(rate: float, periods: float, timing: Timing) -> float:
    """What one unit paid every period is worth at the end, at ``rate``."""
    if rate == 0:
        return periods
    return (1.0 + rate * timing) * (_growth(rate, periods) - 1.0) / rate


def future_value(
    present_value: float,
    payment: float,
    rate: float,
    periods: float,
    timing: Timing = 0,
) -> float:
    """The signed ending value that balances the other three cash flows."""
    return -(
        present_value * _growth(rate, periods)
        + payment * _annuity_factor(rate, periods, timing)
    )


def present_value(
    future_value_amount: float,
    payment: float,
    rate: float,
    periods: float,
    timing: Timing = 0,
) -> float:
    growth = _growth(rate, periods)
    return -(future_value_amount + payment * _annuity_factor(rate, periods, timing)) / (
        growth
    )


def payment(
    present_value_amount: float,
    future_value_amount: float,
    rate: float,
    periods: float,
    timing: Timing = 0,
) -> float | NoSolution:
    factor = _annuity_factor(rate, periods, timing)
    if factor == 0:
        return NoSolution(field="periods", code="no_periods")
    return -(present_value_amount * _growth(rate, periods) + future_value_amount) / factor


# A count this close to zero is a target already met, not one left behind.
_AT_TARGET = 1e-9


def periods(
    present_value_amount: float,
    payment_amount: float,
    future_value_amount: float,
    rate: float,
    timing: Timing = 0,
) -> float | NoSolution:
    """How many periods the cash flows need: zero when they already balance,
    ``NoSolution`` when they never do."""
    if rate == 0:
        if payment_amount == 0:
            if abs(present_value_amount + future_value_amount) <= _AT_TARGET * max(
                1.0, abs(present_value_amount), abs(future_value_amount)
            ):
                return 0.0
            return NoSolution(field="payment", code="payment_never_balances")
        count = -(present_value_amount + future_value_amount) / payment_amount
        if count < -_AT_TARGET:
            return NoSolution(field="payment", code="payment_never_balances")
        return count if count > 0 else 0.0
    if rate <= -1:
        return NoSolution(field="rate", code="rate_out_of_range")
    adjusted = payment_amount * (1.0 + rate * timing)
    numerator = adjusted - future_value_amount * rate
    denominator = present_value_amount * rate + adjusted
    if denominator == 0 or numerator / denominator <= 0:
        return NoSolution(field="payment", code="payment_never_balances")
    count = math.log(numerator / denominator) / math.log(1.0 + rate)
    if count < -_AT_TARGET:
        return NoSolution(field="payment", code="payment_never_balances")
    return count if count > 0 else 0.0


def target_already_met(
    balance: float, deposit: float, target: float, rate: float, timing: Timing = 0
) -> bool:
    """Whether a balance already meets a target at or below it and does not fall
    from there; a declining balance still has periods left to reach it."""
    return balance >= target and balance * rate + deposit * (1.0 + rate * timing) >= 0


def rate(
    present_value_amount: float,
    payment_amount: float,
    future_value_amount: float,
    periods_count: float,
    timing: Timing = 0,
) -> float | NoSolution:
    """The rate per period that balances the cash flows, found numerically."""
    if periods_count <= 0:
        return NoSolution(field="periods", code="no_periods")

    def balance(candidate: float) -> float:
        return (
            present_value_amount * _growth(candidate, periods_count)
            + payment_amount * _annuity_factor(candidate, periods_count, timing)
            + future_value_amount
        )

    root = bracketed_root(balance)
    if root is None:
        return NoSolution(field="rate", code="no_rate_fits")
    return root


@dataclass(frozen=True)
class AmortizationRow:
    period: int
    payment: float
    interest: float
    principal: float
    balance: float


def amortization_schedule(
    principal: float,
    rate_per_period: float,
    payment_amount: float,
    periods_count: int,
    timing: Timing = 0,
) -> list[AmortizationRow]:
    """How a balance falls under level payments; magnitudes, one row per period."""
    rows: list[AmortizationRow] = []
    balance = principal
    for period in range(1, periods_count + 1):
        if timing == 1:
            balance -= payment_amount
            interest = balance * rate_per_period
            principal_part = payment_amount - interest
            balance += interest
        else:
            interest = balance * rate_per_period
            principal_part = payment_amount - interest
            balance = balance + interest - payment_amount
        rows.append(
            AmortizationRow(
                period=period,
                payment=payment_amount,
                interest=interest,
                principal=principal_part,
                balance=balance,
            )
        )
    return rows


def total_paid(
    principal: float,
    rate_per_period: float,
    payment_amount: float,
    periods_count: int,
    timing: Timing = 0,
) -> float:
    """What level payments pay over at most ``periods_count`` periods, stopping
    once the balance is cleared: the last payment is only what remains."""
    balance, paid = principal, 0.0
    for _ in range(periods_count):
        if timing == 1:
            due = min(payment_amount, balance)
            balance = (balance - due) * (1.0 + rate_per_period)
        else:
            balance *= 1.0 + rate_per_period
            due = min(payment_amount, balance)
            balance -= due
        paid += due
        if balance <= 1e-9:
            break
    return paid


def savings_path(
    start: float,
    rate_per_period: float,
    contribution: float,
    periods_count: int,
    timing: Timing = 0,
) -> list[float]:
    """The balance after each period of saving; magnitudes."""
    balances: list[float] = []
    balance = start
    for _ in range(periods_count):
        if timing == 1:
            balance = (balance + contribution) * (1.0 + rate_per_period)
        else:
            balance = balance * (1.0 + rate_per_period) + contribution
        balances.append(balance)
    return balances
