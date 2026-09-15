"""Time value of money: a saving or borrowing plan solved for any one unknown."""

from __future__ import annotations

import math
from datetime import date
from typing import Literal

from pydantic import Field

from argus.domain.calculations._shared import (
    MAX_PERIODS,
    MIN_ANNUAL_RATE_PCT,
    CalculationArguments,
    CalculationResult,
    dated_path,
    free_policy,
    input_fact,
    money_fact,
    money_input,
    no_solution,
    note,
    number_fact,
    pct,
    percent_fact,
    percent_input,
    period_unit,
    rounded,
    text,
)
from argus.domain.finance import tvm
from argus.domain.finance.outcomes import NoSolution
from argus.domain.tool_contracts import (
    ToolCardPresentation,
    ToolFact,
    ToolOutcome,
)
from argus.domain.tool_declaration import (
    ExactlyOneUnknown,
    ToolCardBinding,
    ToolDeclaration,
    ToolProgressTemplate,
)
from argus.domain.tool_fact_projection import ResultFact, ResultProjection, solved_facts

UNKNOWN_FIELDS = (
    "present_value",
    "payment",
    "future_value",
    "annual_rate_pct",
    "periods",
)
Direction = Literal["save", "borrow"]
Timing = Literal["end", "start"]


class TimeValueArguments(CalculationArguments):
    direction: Direction
    present_value: float | None = Field(default=None, ge=0)
    payment: float | None = Field(default=None, ge=0)
    future_value: float | None = Field(default=None, ge=0)
    annual_rate_pct: float | None = Field(default=None, gt=-100)
    periods: int | None = Field(default=None, ge=1, le=1200)
    periods_per_year: int = Field(default=12, ge=1, le=365)
    payment_timing: Timing = "end"
    start_date: date | None = None


class TimeValueResult(CalculationResult):
    solved_field: str
    solved_value: float
    present_value: float
    payment: float
    future_value: float
    annual_rate_pct: float
    periods: float
    total_payments: float
    total_interest: float
    balances: list[float]
    notes: list[str]


def _signed(direction: Direction, present: float, payment: float, future: float):
    if direction == "save":
        return -present, -payment, future
    return present, -payment, -future


def _magnitude(direction: Direction, field: str, signed: float) -> float:
    if direction == "save":
        return -signed if field in {"present_value", "payment"} else signed
    return signed if field == "present_value" else -signed


def compute_time_value(arguments: TimeValueArguments) -> TimeValueResult:
    unknown = next(name for name in UNKNOWN_FIELDS if getattr(arguments, name) is None)
    timing = 1 if arguments.payment_timing == "start" else 0
    per_period = (
        pct(arguments.annual_rate_pct) / arguments.periods_per_year
        if arguments.annual_rate_pct is not None
        else None
    )
    present = arguments.present_value or 0.0
    payment = arguments.payment or 0.0
    future = arguments.future_value or 0.0
    periods = float(arguments.periods) if arguments.periods is not None else None
    pv_s, pmt_s, fv_s = _signed(arguments.direction, present, payment, future)
    notes: list[str] = []

    if unknown == "annual_rate_pct":
        assert periods is not None
        solved_rate = tvm.rate(pv_s, pmt_s, fv_s, periods, timing)
        if isinstance(solved_rate, NoSolution):
            raise no_solution(NoSolution(field="annual_rate_pct", code=solved_rate.code))
        per_period = solved_rate
        solved_value = per_period * arguments.periods_per_year * 100.0
        if solved_value <= MIN_ANNUAL_RATE_PCT:
            # A periodic loss this steep annualizes past the rate the input accepts.
            raise no_solution(
                NoSolution(field="annual_rate_pct", code="rate_out_of_range")
            )
    elif unknown == "periods":
        assert per_period is not None
        if arguments.direction == "save" and tvm.target_already_met(
            present, payment, future, per_period, timing
        ):
            # A savings balance already at or past its target needs no period, and
            # the plan ends at the balance itself.
            count = 0.0
            future = present
        else:
            count = tvm.periods(pv_s, pmt_s, fv_s, per_period, timing)
            if isinstance(count, NoSolution):
                raise no_solution(_periods_repair(count, pv_s, per_period, arguments))
            if count > MAX_PERIODS:
                raise no_solution(
                    NoSolution(
                        field="payment" if payment else "annual_rate_pct",
                        code="periods_beyond_limit",
                    )
                )
        if count == 0:
            # The balance already meets the target: no period is needed.
            notes.append("already_covered")
        periods = count
        solved_value = count
    else:
        assert per_period is not None and periods is not None
        if unknown == "future_value":
            signed = tvm.future_value(pv_s, pmt_s, per_period, periods, timing)
        elif unknown == "present_value":
            signed = tvm.present_value(fv_s, pmt_s, per_period, periods, timing)
        else:
            solved_payment = tvm.payment(pv_s, fv_s, per_period, periods, timing)
            if isinstance(solved_payment, NoSolution):
                raise no_solution(solved_payment)
            signed = solved_payment
        solved_value = _magnitude(arguments.direction, unknown, signed)
        if solved_value < 0:
            # The other inputs already cross the line: nothing more is needed.
            notes.append("already_covered")
            solved_value = 0.0
    present, payment, future = (
        solved_value if unknown == "present_value" else present,
        solved_value if unknown == "payment" else payment,
        solved_value if unknown == "future_value" else future,
    )
    assert per_period is not None and periods is not None
    covered = "already_covered" in notes and unknown != "periods"
    if covered and unknown != "future_value":
        # The other inputs reach past the target on their own, so the plan ends
        # where they take it rather than at the target.
        start_s, payment_s, _ = _signed(arguments.direction, present, payment, 0.0)
        future = _magnitude(
            arguments.direction,
            "future_value",
            tvm.future_value(start_s, payment_s, per_period, periods, timing),
        )
    # A target already met needs no period, so its schedule is empty.
    whole_periods = 0 if periods == 0 else max(int(math.ceil(periods - 1e-9)), 1)
    if arguments.direction == "borrow":
        balances = [
            max(row.balance, 0.0)
            for row in tvm.amortization_schedule(
                present, per_period, payment, whole_periods, timing
            )
        ]
        # Payments that clear the loan before its last period stop there.
        total_payments = (
            tvm.total_paid(present, per_period, payment, whole_periods, timing)
            if covered and unknown == "future_value"
            else payment * periods + future
        )
        total_interest = total_payments - present
    else:
        balances = tvm.savings_path(present, per_period, payment, whole_periods, timing)
        total_payments = present + payment * periods
        total_interest = future - total_payments
    if unknown == "periods" and whole_periods > periods:
        # The target is reached partway through the last period, so the path
        # ends at the reported balance rather than a whole period past it.
        balances[-1] = future
    return TimeValueResult(
        solved_field=unknown,
        solved_value=solved_value,
        present_value=present,
        payment=payment,
        future_value=future,
        annual_rate_pct=per_period * arguments.periods_per_year * 100.0,
        periods=periods,
        total_payments=total_payments,
        total_interest=total_interest,
        balances=balances,
        notes=notes,
    )


def _periods_repair(
    outcome: NoSolution, pv_s: float, per_period: float, arguments: TimeValueArguments
) -> NoSolution:
    """Name the payment, and offer the one that would clear the balance in time."""
    if arguments.direction == "borrow" and per_period > 0:
        interest_only = abs(pv_s) * per_period
        return NoSolution(
            field="payment",
            code="payment_below_interest",
            repair={"payment": interest_only * 1.05},
        )
    return outcome


RESULT_PROJECTION = ResultProjection(
    (
        *solved_facts(
            UNKNOWN_FIELDS,
            lambda name, a, r: _fact(
                name, r.solved_value, a.currency, a.periods_per_year
            ),
        ),
        ResultFact(
            "total_payments",
            lambda name, a, r: money_fact(name, r.total_payments, a.currency),
        ),
        ResultFact(
            "total_interest",
            lambda name, a, r: money_fact(name, r.total_interest, a.currency),
            when=lambda a, r: a.direction == "borrow",
        ),
        ResultFact(
            "total_growth",
            lambda name, a, r: money_fact(name, r.total_interest, a.currency),
            when=lambda a, r: a.direction != "borrow",
        ),
        ResultFact(
            "future_value",
            lambda name, a, r: money_fact(name, r.future_value, a.currency),
            when=lambda a, r: r.solved_field != "future_value",
        ),
        ResultFact(
            "annual_rate_pct",
            lambda name, a, r: percent_fact(name, pct(r.annual_rate_pct)),
            when=lambda a, r: r.solved_field == "future_value",
        ),
    )
)


def present_time_value(
    arguments: TimeValueArguments, outcome: ToolOutcome
) -> ToolCardPresentation:
    currency = arguments.currency
    inputs = [
        input_fact("direction", arguments.direction, None),
        money_input("present_value", arguments.present_value, currency),
        money_input("payment", arguments.payment, currency),
        money_input("future_value", arguments.future_value, currency),
        percent_input("annual_rate_pct", arguments.annual_rate_pct),
        input_fact("periods", arguments.periods, period_unit(arguments.periods_per_year)),
        input_fact("periods_per_year", arguments.periods_per_year),
        input_fact("payment_timing", arguments.payment_timing),
    ]
    title = text(f"tools.calc.time_value.title_{arguments.direction}")
    if outcome.status != "succeeded":
        return ToolCardPresentation(title=title, inputs=inputs)
    result = TimeValueResult.model_validate(outcome.result)
    visual = (
        dated_path(
            arguments.start_date,
            arguments.periods_per_year,
            result.balances,
            currency=currency,
            base_value=result.present_value,
        )
        if arguments.start_date is not None
        else None
    )
    return ToolCardPresentation(
        title=title,
        inputs=inputs,
        visual=visual,
        notes=[note(code) for code in result.notes],
    )


def _fact(field: str, value: float, currency: str, per_year: int) -> ToolFact:
    if field == "annual_rate_pct":
        return percent_fact(field, pct(value))
    if field == "periods":
        return number_fact(field, rounded(value, 1), period_unit(per_year))
    return money_fact(field, value, currency)


def get_time_value_declaration() -> ToolDeclaration:
    return ToolDeclaration(
        name="time_value",
        description=(
            "Solve a saving or borrowing plan for the one blank among starting "
            "amount, payment per period, ending amount, annual rate and number "
            "of periods. Covers savings goals, affordability, loans, amortization "
            "and certificates. Money is in the stated currency; zero is a known value."
        ),
        handler=compute_time_value,
        policy=free_policy(
            *UNKNOWN_FIELDS,
            "periods_per_year",
            "payment_timing",
            "direction",
            driving=UNKNOWN_FIELDS,
        ),
        progress=ToolProgressTemplate(
            locale_key="tools.calc.time_value.progress", argument_fields=("direction",)
        ),
        card=ToolCardBinding(
            result_projection=RESULT_PROJECTION,
            card_type="time_value",
            version=1,
            presenter=present_time_value,
        ),
        rules=(ExactlyOneUnknown(fields=UNKNOWN_FIELDS),),
        domain=(
            "Saving: the starting amount and payments go in, the ending amount comes out.",
            "Borrowing: the starting amount is received, payments and any ending balance are paid.",
            "Rates are annual percentages; periods are counted in the stated periods per year.",
            "No forecast: the rate is an input the user gives or a page cites.",
        ),
    )


__all__ = [
    "TimeValueArguments",
    "TimeValueResult",
    "compute_time_value",
    "get_time_value_declaration",
    "present_time_value",
]
