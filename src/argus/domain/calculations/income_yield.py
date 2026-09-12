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
from argus.domain.tool_contracts import ToolCardPresentation, ToolFact, ToolOutcome
from argus.domain.tool_declaration import (
    ExactlyOneUnknown,
    ToolCardBinding,
    ToolDeclaration,
    ToolProgressTemplate,
)

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
    result = IncomeYieldResult.model_validate(outcome.result)
    answer: ToolFact = (
        percent_fact("yield_pct", pct(result.yield_pct))
        if result.solved_field == "yield_pct"
        else money_fact(result.solved_field, result.solved_value, currency)
    )
    rows = [money_fact("monthly_income", result.monthly_income, currency)]
    return ToolCardPresentation(title=title, answer=answer, rows=rows, inputs=inputs)


def get_income_yield_declaration() -> ToolDeclaration:
    return ToolDeclaration(
        name="income_yield",
        description=(
            "Relate yearly income to a price as a yield, for dividends, rent, "
            "interest or coupons: give any two of yearly income, price and yield."
        ),
        handler=compute_income_yield,
        policy=free_policy(*UNKNOWN_FIELDS),
        progress=ToolProgressTemplate(locale_key="tools.calc.income_yield.progress"),
        card=ToolCardBinding(
            card_type="income_yield", version=1, presenter=present_income_yield
        ),
        rules=(ExactlyOneUnknown(fields=UNKNOWN_FIELDS),),
        domain=("Income is the stated yearly amount; nothing here projects it forward.",),
    )
