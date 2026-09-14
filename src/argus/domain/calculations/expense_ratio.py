"""A fund's expense ratio and what it costs over the years."""

from __future__ import annotations

from pydantic import Field

from argus.domain.calculations._shared import (
    UNIT_YEARS_KEY,
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

UNKNOWN_FIELDS = ("annual_fee", "ratio_pct")


class ExpenseRatioArguments(CalculationArguments):
    symbol: Symbol
    assets: float = Field(gt=0)
    annual_fee: float | None = Field(default=None, ge=0)
    ratio_pct: float | None = Field(default=None, ge=0)
    years: int = Field(default=10, ge=1, le=60)
    growth_rate_pct: float = Field(default=0.0, gt=-100)


class ExpenseRatioResult(CalculationResult):
    solved_field: str
    solved_value: float
    annual_fee: float
    ratio_pct: float
    ending_with_fee: float
    ending_without_fee: float
    cost_over_years: float


def compute_expense_ratio(arguments: ExpenseRatioArguments) -> ExpenseRatioResult:
    unknown = next(name for name in UNKNOWN_FIELDS if getattr(arguments, name) is None)
    if unknown == "ratio_pct":
        assert arguments.annual_fee is not None
        ratio = ratios.expense_ratio(arguments.annual_fee, arguments.assets)
        if isinstance(ratio, NoSolution):
            raise no_solution(ratio)
        fee, solved_value = arguments.annual_fee, ratio * 100.0
    else:
        assert arguments.ratio_pct is not None
        ratio = pct(arguments.ratio_pct)
        fee = arguments.assets * ratio
        solved_value = fee
    if ratio > 1:
        # A fee above the whole balance each year empties it; compounding the
        # negative remainder would make the balance rebound.
        raise no_solution(
            NoSolution(
                field="annual_fee" if unknown == "ratio_pct" else "ratio_pct",
                code="fee_above_balance",
            )
        )
    cost = ratios.expense_cost(
        arguments.assets, ratio, pct(arguments.growth_rate_pct), arguments.years
    )
    return ExpenseRatioResult(
        solved_field=unknown,
        solved_value=solved_value,
        annual_fee=fee,
        ratio_pct=ratio * 100.0,
        ending_with_fee=cost.ending_with_fee,
        ending_without_fee=cost.ending_without_fee,
        cost_over_years=cost.cost,
    )


def present_expense_ratio(
    arguments: ExpenseRatioArguments, outcome: ToolOutcome
) -> ToolCardPresentation:
    currency = arguments.currency
    inputs = [
        input_fact("symbol", arguments.symbol),
        money_input("assets", arguments.assets, currency),
        money_input("annual_fee", arguments.annual_fee, currency),
        percent_input("ratio_pct", arguments.ratio_pct),
        input_fact("years", arguments.years, text(UNIT_YEARS_KEY)),
        percent_input("growth_rate_pct", arguments.growth_rate_pct),
    ]
    title = text("tools.calc.expense_ratio.title")
    if outcome.status != "succeeded":
        return ToolCardPresentation(title=title, inputs=inputs)
    result = ExpenseRatioResult.model_validate(outcome.result)
    answer: ToolFact = (
        percent_fact("ratio_pct", pct(result.ratio_pct))
        if result.solved_field == "ratio_pct"
        else money_fact("annual_fee", result.annual_fee, currency)
    )
    rows = [
        money_fact("cost_over_years", result.cost_over_years, currency),
        money_fact("ending_with_fee", result.ending_with_fee, currency),
        money_fact("ending_without_fee", result.ending_without_fee, currency),
    ]
    return ToolCardPresentation(title=title, answer=answer, rows=rows, inputs=inputs)


def get_expense_ratio_declaration() -> ToolDeclaration:
    return ToolDeclaration(
        name="expense_ratio",
        description=(
            "A yearly fee as a share of assets, or the fee a ratio charges, and what "
            "that fee costs over a number of years at a stated growth rate. Exactly "
            "one of the yearly fee and the ratio is blank."
        ),
        handler=compute_expense_ratio,
        policy=free_policy(
            *UNKNOWN_FIELDS,
            "assets",
            "years",
            "growth_rate_pct",
            driving=("assets", *UNKNOWN_FIELDS, "years", "growth_rate_pct"),
        ),
        progress=ToolProgressTemplate(locale_key="tools.calc.expense_ratio.progress"),
        card=ToolCardBinding(
            card_type="expense_ratio", version=1, presenter=present_expense_ratio
        ),
        rules=(ExactlyOneUnknown(fields=UNKNOWN_FIELDS),),
        domain=("The growth rate is an input, never a forecast Argus makes.",),
    )
