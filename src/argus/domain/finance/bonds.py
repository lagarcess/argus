"""Bond pricing and yield to maturity."""

from __future__ import annotations

from argus.domain.finance._roots import bracketed_root
from argus.domain.finance.outcomes import NoSolution


def bond_price(
    face: float,
    coupon_rate: float,
    yield_to_maturity: float,
    years: float,
    frequency: int,
) -> float | NoSolution:
    if frequency <= 0 or years <= 0:
        return NoSolution(field="years", code="no_periods")
    per_period = yield_to_maturity / frequency
    if per_period <= -1:
        return NoSolution(field="yield_to_maturity", code="rate_out_of_range")
    coupon = face * coupon_rate / frequency
    count = _coupon_periods(years, frequency)
    if isinstance(count, NoSolution):
        return count
    discount = 1.0 + per_period
    if per_period == 0:
        return coupon * count + face
    annuity = coupon * (1.0 - discount ** (-count)) / per_period
    return annuity + face / discount**count


def bond_yield(
    face: float, coupon_rate: float, price: float, years: float, frequency: int
) -> float | NoSolution:
    if price <= 0:
        return NoSolution(field="price", code="growth_needs_positive_values")
    if frequency <= 0 or years <= 0:
        return NoSolution(field="years", code="no_periods")
    periods = _coupon_periods(years, frequency)
    if isinstance(periods, NoSolution):
        return periods

    def difference(candidate: float) -> float:
        priced = bond_price(face, coupon_rate, candidate, years, frequency)
        if isinstance(priced, NoSolution):
            raise ValueError(priced.code)
        return priced - price

    root = bracketed_root(difference)
    if root is None:
        return NoSolution(field="price", code="no_rate_fits")
    return root


def _coupon_periods(years: float, frequency: int) -> int | NoSolution:
    """The whole coupon periods a term spans; a stub period is not modeled, so a
    term that ends between coupon dates has no price rather than a rounded one."""
    periods = years * frequency
    count = round(periods)
    if count <= 0:
        return NoSolution(field="years", code="no_periods")
    if abs(periods - count) > 1e-9:
        return NoSolution(field="years", code="periods_not_whole")
    return count


def current_yield(face: float, coupon_rate: float, price: float) -> float | NoSolution:
    if price == 0:
        return NoSolution(field="price", code="division_by_zero")
    return face * coupon_rate / price
