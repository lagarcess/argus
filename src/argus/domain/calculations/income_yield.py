"""Income as a share of price: a dividend, rent or coupon yield."""

from __future__ import annotations

from pydantic import Field

from argus.domain.calculations._shared import (
    CalculationArguments,
    CalculationResult,
    Symbol,
    free_policy,
    input_fact,
    money_fact,
    money_input,
    no_solution,
    pct,
    percent_fact,
    percent_input,
    text,
)
from argus.domain.finance import ratios
from argus.domain.finance.outcomes import NoSolution
from argus.domain.tool_contracts import ToolCardPresentation, ToolOutcome
from argus.domain.tool_declaration import (
    ExactlyOneUnknown,
    ToolCardBinding,
    ToolDeclaration,
    ToolProgressTemplate,
)
from argus.domain.tool_fact_projection import ResultFact, ResultProjection, solved_facts

UNKNOWN_FIELDS = ("annual_income", "price", "yield_pct")


class IncomeYieldArguments(CalculationArguments):
    symbol: Symbol
    annual_income: float | None = Field(default=None, ge=0)
    price: float | None = Field(default=None, ge=0)
    yield_pct: float | None = Field(default=None, ge=0)


class IncomeYieldResult(CalculationResult):
    solved_field: str
    solved_value: float
    annual_income: float
    price: float
    yield_pct: float
    monthly_income: float


def compute_income_yield(arguments: IncomeYieldArguments) -> IncomeYieldResult:
    unknown = next(name for name in UNKNOWN_FIELDS if getattr(arguments, name) is None)
    if unknown == "yield_pct":
        assert arguments.annual_income is not None and arguments.price is not None
        rate = ratios.income_yield(arguments.annual_income, arguments.price)
        if isinstance(rate, NoSolution):
            raise no_solution(rate)
        income, price, solved_value = (
            arguments.annual_income,
            arguments.price,
            rate * 100.0,
        )
    elif unknown == "annual_income":
        assert arguments.price is not None and arguments.yield_pct is not None
        income = arguments.price * pct(arguments.yield_pct)
        price, rate, solved_value = arguments.price, pct(arguments.yield_pct), income
    else:
        assert arguments.annual_income is not None and arguments.yield_pct is not None
        price = ratios.ratio(
            arguments.annual_income, pct(arguments.yield_pct), field="yield_pct"
        )
        if isinstance(price, NoSolution):
            raise no_solution(price)
        income, rate, solved_value = (
            arguments.annual_income,
            pct(arguments.yield_pct),
            price,
        )
    return IncomeYieldResult(
        solved_field=unknown,
        solved_value=solved_value,
        annual_income=income,
        price=price,
        yield_pct=rate * 100.0,
        monthly_income=income / 12.0,
    )


RESULT_PROJECTION = ResultProjection(
    (
        *solved_facts(
            UNKNOWN_FIELDS,
            lambda name, a, r: percent_fact(name, pct(r.yield_pct))
            if name == "yield_pct"
            else money_fact(name, r.solved_value, a.currency),
        ),
        ResultFact(
            "monthly_income",
            lambda name, a, r: money_fact(name, r.monthly_income, a.currency),
        ),
    )
)


def present_income_yield(
    arguments: IncomeYieldArguments, outcome: ToolOutcome
) -> ToolCardPresentation:
    currency = arguments.currency
    inputs = [
        input_fact("symbol", arguments.symbol),
        money_input("annual_income", arguments.annual_income, currency),
        money_input("price", arguments.price, currency),
        percent_input("yield_pct", arguments.yield_pct),
    ]
    title = text("tools.calc.income_yield.title")
    if outcome.status != "succeeded":
        return ToolCardPresentation(title=title, inputs=inputs)
    return ToolCardPresentation(title=title, inputs=inputs)


def get_income_yield_declaration() -> ToolDeclaration:
    return ToolDeclaration(
        name="income_yield",
        description=(
            "Relate yearly income to a price as a yield, for dividends, rent, "
            "interest or coupons: give any two of yearly income, price and yield."
        ),
        handler=compute_income_yield,
        policy=free_policy(*UNKNOWN_FIELDS, driving=UNKNOWN_FIELDS),
        progress=ToolProgressTemplate(locale_key="tools.calc.income_yield.progress"),
        card=ToolCardBinding(
            result_projection=RESULT_PROJECTION,
            card_type="income_yield",
            version=1,
            presenter=present_income_yield,
        ),
        rules=(ExactlyOneUnknown(fields=UNKNOWN_FIELDS),),
        domain=("Income is the stated yearly amount; nothing here projects it forward.",),
    )
