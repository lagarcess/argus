"""Discounted cash flow value, or the growth a value implies (reverse DCF)."""

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
from argus.domain.finance import dcf
from argus.domain.finance.outcomes import NoSolution
from argus.domain.tool_contracts import ToolCardPresentation, ToolOutcome
from argus.domain.tool_declaration import (
    ExactlyOneUnknown,
    ToolCardBinding,
    ToolDeclaration,
    ToolProgressTemplate,
)

UNKNOWN_FIELDS = ("value", "growth_rate_pct")


class CashFlowArguments(CalculationArguments):
    symbol: Symbol
    cash_flow: float = Field(gt=0)
    growth_rate_pct: float | None = Field(default=None, gt=-100)
    discount_rate_pct: float = Field(gt=-100)
    years: int = Field(ge=1, le=50)
    terminal_growth_rate_pct: float = Field(default=2.0, gt=-100)
    value: float | None = Field(default=None, ge=0)


class CashFlowResult(CalculationResult):
    solved_field: str
    solved_value: float
    value: float
    growth_rate_pct: float
    cash_flow_at_horizon: float


def compute_discounted_cash_flow(arguments: CashFlowArguments) -> CashFlowResult:
    unknown = next(name for name in UNKNOWN_FIELDS if getattr(arguments, name) is None)
    discount = pct(arguments.discount_rate_pct)
    terminal = pct(arguments.terminal_growth_rate_pct)
    if unknown == "value":
        assert arguments.growth_rate_pct is not None
        growth = pct(arguments.growth_rate_pct)
        value = dcf.dcf_value(
            arguments.cash_flow, growth, discount, arguments.years, terminal
        )
        if isinstance(value, NoSolution):
            raise no_solution(_named(value))
        solved_value = value
    else:
        assert arguments.value is not None
        value = arguments.value
        solved_growth = dcf.implied_growth(
            value, arguments.cash_flow, discount, arguments.years, terminal
        )
        if isinstance(solved_growth, NoSolution):
            raise no_solution(_named(solved_growth))
        growth = solved_growth
        solved_value = growth * 100.0
    return CashFlowResult(
        solved_field=unknown,
        solved_value=solved_value,
        value=value,
        growth_rate_pct=growth * 100.0,
        cash_flow_at_horizon=arguments.cash_flow * (1.0 + growth) ** arguments.years,
    )


def _named(outcome: NoSolution) -> NoSolution:
    fields = {"discount_rate": "discount_rate_pct", "cash_flow": "cash_flow"}
    return NoSolution(field=fields.get(outcome.field, outcome.field), code=outcome.code)


def present_discounted_cash_flow(
    arguments: CashFlowArguments, outcome: ToolOutcome
) -> ToolCardPresentation:
    currency = arguments.currency
    inputs = [
        input_fact("symbol", arguments.symbol),
        money_input("cash_flow", arguments.cash_flow, currency),
        percent_input("growth_rate_pct", arguments.growth_rate_pct),
        percent_input("discount_rate_pct", arguments.discount_rate_pct),
        input_fact("years", arguments.years, text(UNIT_YEARS_KEY)),
        percent_input("terminal_growth_rate_pct", arguments.terminal_growth_rate_pct),
        money_input("value", arguments.value, currency),
    ]
    title = text("tools.calc.discounted_cash_flow.title")
    if outcome.status != "succeeded":
        return ToolCardPresentation(title=title, inputs=inputs)
    result = CashFlowResult.model_validate(outcome.result)
    answer = (
        money_fact("value", result.value, currency)
        if result.solved_field == "value"
        else percent_fact("growth_rate_pct", pct(result.growth_rate_pct))
    )
    rows = [money_fact("cash_flow_at_horizon", result.cash_flow_at_horizon, currency)]
    return ToolCardPresentation(title=title, answer=answer, rows=rows, inputs=inputs)


def get_discounted_cash_flow_declaration() -> ToolDeclaration:
    return ToolDeclaration(
        name="discounted_cash_flow",
        description=(
            "Value a stream of cash flows that grow for a number of years and then "
            "at a terminal rate, discounted at a required rate; or, given a value or "
            "price, find the growth it implies. Exactly one of value and growth is blank."
        ),
        handler=compute_discounted_cash_flow,
        policy=free_policy(
            *UNKNOWN_FIELDS,
            "cash_flow",
            "discount_rate_pct",
            "years",
            "terminal_growth_rate_pct",
            driving=(
                "cash_flow",
                "discount_rate_pct",
                "years",
                *UNKNOWN_FIELDS,
                "terminal_growth_rate_pct",
            ),
        ),
        progress=ToolProgressTemplate(
            locale_key="tools.calc.discounted_cash_flow.progress"
        ),
        card=ToolCardBinding(
            card_type="discounted_cash_flow",
            version=1,
            presenter=present_discounted_cash_flow,
        ),
        rules=(ExactlyOneUnknown(fields=UNKNOWN_FIELDS),),
        domain=(
            "The discount rate must exceed the terminal growth rate.",
            "Growth and discount rates are inputs, never forecasts Argus makes.",
        ),
    )
