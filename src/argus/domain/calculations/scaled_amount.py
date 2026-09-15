"""Multiply or divide a stated amount by a percentage or quoted ratio."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from argus.domain.calculations._shared import (
    UNIT_MULTIPLE_KEY,
    UNIT_PERCENT_KEY,
    CalculationArguments,
    CalculationResult,
    Currency,
    free_policy,
    input_fact,
    money_fact,
    money_input,
    no_solution,
    note,
    pct,
    required,
    text,
)
from argus.domain.finance.outcomes import NoSolution
from argus.domain.finance.ratios import ratio
from argus.domain.tool_contracts import LocalizedText, ToolCardPresentation, ToolOutcome
from argus.domain.tool_declaration import (
    ToolCardBinding,
    ToolDeclaration,
    ToolProgressTemplate,
)
from argus.domain.tool_fact_projection import ResultFact, ResultProjection


class ScaledAmountArguments(CalculationArguments):
    amount: float | None = Field(default=None, ge=0)
    rate: float | None = Field(default=None, ge=0)
    rate_unit: Literal["percent", "multiple"]
    operation: Literal["multiply", "divide"]
    output_currency: Currency | None = None


class ScaledAmountResult(CalculationResult):
    scaled_amount: float
    output_currency: Currency


def compute_scaled_amount(arguments: ScaledAmountArguments) -> ScaledAmountResult:
    amount = required(arguments.amount, "amount")
    rate = required(arguments.rate, "rate")
    factor = pct(rate) if arguments.rate_unit == "percent" else rate
    value = (
        amount * factor
        if arguments.operation == "multiply"
        else ratio(amount, factor, field="rate")
    )
    if isinstance(value, NoSolution):
        raise no_solution(value)
    return ScaledAmountResult(
        scaled_amount=value,
        output_currency=(
            arguments.currency
            if arguments.output_currency is None
            else arguments.output_currency
        ),
    )


def _rate_unit(arguments: ScaledAmountArguments) -> LocalizedText:
    if arguments.rate_unit == "percent":
        return text(UNIT_PERCENT_KEY)
    if (
        arguments.output_currency is None
        or arguments.output_currency == arguments.currency
    ):
        return text(UNIT_MULTIPLE_KEY)
    numerator, denominator = arguments.output_currency, arguments.currency
    if arguments.operation == "divide":
        numerator, denominator = denominator, numerator
    return text(
        "tools.calc.units.currency_ratio", numerator=numerator, denominator=denominator
    )


RESULT_PROJECTION = ResultProjection(
    (
        ResultFact(
            "scaled_amount",
            lambda name, a, r: money_fact(name, r.scaled_amount, r.output_currency),
            placement="answer",
        ),
    )
)


def present_scaled_amount(
    arguments: ScaledAmountArguments, outcome: ToolOutcome
) -> ToolCardPresentation:
    inputs = [
        money_input("amount", arguments.amount, arguments.currency),
        input_fact("rate", arguments.rate, _rate_unit(arguments)),
        input_fact("output_currency", arguments.output_currency),
    ]
    title = text("tools.calc.scaled_amount.title")
    if outcome.status != "succeeded":
        return ToolCardPresentation(title=title, inputs=inputs)
    return ToolCardPresentation(
        title=title,
        inputs=inputs,
        notes=[note(f"scaled_{arguments.operation}")],
    )


def get_scaled_amount_declaration() -> ToolDeclaration:
    return ToolDeclaration(
        name="scaled_amount",
        description=(
            "Multiply or divide an amount by a stated percentage or multiple, "
            "without imposing a time period. Percent means rate / 100; multiple "
            "means the rate itself. For currency conversion, currency is the "
            "amount's currency and output_currency is the result's currency: "
            "multiply a quote in output currency per input currency, or divide "
            "a quote in input currency per output currency."
        ),
        handler=compute_scaled_amount,
        policy=free_policy(
            "amount",
            "rate",
            "rate_unit",
            "operation",
            "output_currency",
            driving=("amount", "rate", "output_currency"),
        ),
        progress=ToolProgressTemplate(locale_key="tools.calc.scaled_amount.progress"),
        card=ToolCardBinding(
            result_projection=RESULT_PROJECTION,
            card_type="scaled_amount",
            version=1,
            presenter=present_scaled_amount,
        ),
        domain=(
            "The rate must be stated or sourced; this calculation does not fetch it.",
        ),
    )
