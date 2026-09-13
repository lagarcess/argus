"""Throwaway ordinary-annuity arithmetic. Never register in the runtime.

Signed cash flows: PV*(1+r)**n + PMT*annuity_factor(r,n) + FV = 0.
Payments occur at period end. Rate is effective per payment period, not APR.
Money shares one unit. None is an unknown; zero is a known value.
"""

from math import exp, expm1, isfinite, log1p


def solve_for_unknown(
    present_value: float | None,
    payment: float | None,
    rate: float | None,
    periods: float | None,
    future_value: float | None,
) -> float:
    """Solve exactly one blank, without rounding money or the period count.

    Rate inversion accepts integer periods and cash flows with exactly one
    sign change (a unique positive discount-factor root). Its numerical search
    is bounded to -30 <= log(1+rate) <= 30. Other inversions allow positive
    fractional periods as an algebraic equivalent, not a partial payment plan.
    Undefined, nonunique, unsupported and nonfinite results raise ValueError.
    """
    values = (present_value, payment, rate, periods, future_value)
    if sum(value is None for value in values) != 1:
        raise ValueError("exactly_one_unknown_required")
    for value in values:
        if value is not None and (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not isfinite(value)
        ):
            raise ValueError("finite_numbers_required")
    if rate is not None and rate <= -1:
        raise ValueError("rate_must_exceed_minus_one")
    if periods is not None and periods <= 0:
        raise ValueError("periods_must_be_positive")

    try:
        if rate is None:
            answer = _rate(present_value, payment, periods, future_value)
        elif periods is None:
            if rate == 0:
                answer = -(future_value + present_value) / payment
            else:
                delta = (
                    -(present_value + future_value)
                    * rate
                    / (present_value * rate + payment)
                )
                answer = log1p(delta) / log1p(rate)
            if answer <= 0:
                raise ValueError("no_positive_period_solution")
        else:
            log_growth = periods * log1p(rate)
            growth_delta = expm1(log_growth)
            growth = exp(log_growth)
            annuity = periods if rate == 0 else growth_delta / rate
            if present_value is None:
                answer = -(payment * annuity + future_value) / growth
            elif payment is None:
                answer = -(present_value * growth + future_value) / annuity
            else:
                answer = -(present_value * growth + payment * annuity)
    except (OverflowError, ZeroDivisionError) as exc:
        raise ValueError("undefined_or_outside_numeric_range") from exc
    if not isfinite(answer):
        raise ValueError("nonfinite_solution")
    return float(answer)


def _rate(
    present_value: float, payment: float, periods: float, future_value: float
) -> float:
    if not float(periods).is_integer():
        raise ValueError("rate_inversion_requires_integer_periods")
    scale = max(abs(present_value), abs(payment), abs(future_value))
    if scale == 0:
        raise ValueError("indeterminate_rate")
    pv, pmt, fv = (value / scale for value in (present_value, payment, future_value))
    cash_flows = [pv, *([pmt] if periods > 1 else []), pmt + fv]
    signs = [value > 0 for value in cash_flows if value != 0]
    if sum(left != right for left, right in zip(signs, signs[1:], strict=False)) != 1:
        raise ValueError("rate_requires_exactly_one_cash_flow_sign_change")

    def residual(log_growth: float) -> float:
        # Scale by growth when positive, avoiding exponential overflow.
        if log_growth == 0:
            return pv + pmt * periods + fv
        rate = expm1(log_growth)
        if log_growth > 0:
            discount = exp(-periods * log_growth)
            annuity = -expm1(-periods * log_growth) / rate
            return pv + pmt * annuity + fv * discount
        growth = exp(periods * log_growth)
        annuity = expm1(periods * log_growth) / rate
        return pv * growth + pmt * annuity + fv

    low, high = -30.0, 30.0
    left, right = residual(low), residual(high)
    if left == 0:
        return expm1(low)
    if right == 0:
        return expm1(high)
    if (left > 0) == (right > 0):
        raise ValueError("rate_outside_search_interval")
    for _ in range(160):
        middle = (low + high) / 2
        value = residual(middle)
        if value == 0:
            return expm1(middle)
        if (value > 0) == (left > 0):
            low, left = middle, value
        else:
            high = middle
    return expm1((low + high) / 2)
