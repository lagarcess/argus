"""Valuation scenarios from typed inputs, as low, base and high ranges."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from argus.domain.calculations._shared import (
    UNIT_MULTIPLE_KEY,
    UNIT_YEARS_KEY,
    CalculationArguments,
    CalculationResult,
    Symbol,
    free_policy,
    input_fact,
    money_input,
    no_solution,
    pct,
    percent_input,
    text,
)
from argus.domain.finance import valuation
from argus.domain.finance.outcomes import NoSolution
from argus.domain.tool_contracts import ToolCardPresentation, ToolFact, ToolOutcome
from argus.domain.tool_declaration import (
    ToolCardBinding,
    ToolDeclaration,
    ToolProgressTemplate,
)


class ValuationArguments(CalculationArguments):
    symbol: Symbol
    price: float = Field(gt=0)
    per_share: float = Field(gt=0)
    growth_low_pct: float = Field(gt=-100)
    growth_base_pct: float = Field(gt=-100)
    growth_high_pct: float = Field(gt=-100)
    multiple_low: float = Field(gt=0)
    multiple_base: float = Field(gt=0)
    multiple_high: float = Field(gt=0)
    horizon_years: int = Field(default=5, ge=1, le=30)


class ScenarioRow(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    label: str
    growth_pct: float
    multiple: float
    price_at_horizon: float
    annual_return_pct: float


class ValuationResult(CalculationResult):
    current_multiple: float
    scenarios: list[ScenarioRow]


def compute_valuation_scenarios(arguments: ValuationArguments) -> ValuationResult:
    scenarios = valuation.valuation_scenarios(
        price=arguments.price,
        per_share=arguments.per_share,
        growth=(
            pct(arguments.growth_low_pct),
            pct(arguments.growth_base_pct),
            pct(arguments.growth_high_pct),
        ),
        multiples=(
            arguments.multiple_low,
            arguments.multiple_base,
            arguments.multiple_high,
        ),
        horizon=arguments.horizon_years,
    )
    if isinstance(scenarios, NoSolution):
        raise no_solution(scenarios)
    return ValuationResult(
        current_multiple=arguments.price / arguments.per_share,
        scenarios=[
            ScenarioRow(
                label=scenario.label,
                growth_pct=scenario.growth * 100.0,
                multiple=scenario.multiple,
                price_at_horizon=scenario.price_at_horizon,
                annual_return_pct=scenario.annual_return * 100.0,
            )
            for scenario in scenarios
        ],
    )


def present_valuation_scenarios(
    arguments: ValuationArguments, outcome: ToolOutcome
) -> ToolCardPresentation:
    currency = arguments.currency
    inputs = [
        input_fact("symbol", arguments.symbol),
        money_input("price", arguments.price, currency),
        money_input("per_share", arguments.per_share, currency),
        percent_input("growth_low_pct", arguments.growth_low_pct),
        percent_input("growth_base_pct", arguments.growth_base_pct),
        percent_input("growth_high_pct", arguments.growth_high_pct),
        input_fact("multiple_low", arguments.multiple_low, text(UNIT_MULTIPLE_KEY)),
        input_fact("multiple_base", arguments.multiple_base, text(UNIT_MULTIPLE_KEY)),
        input_fact("multiple_high", arguments.multiple_high, text(UNIT_MULTIPLE_KEY)),
        input_fact("horizon_years", arguments.horizon_years, text(UNIT_YEARS_KEY)),
    ]
    title = text("tools.calc.valuation_scenarios.title")
    if outcome.status != "succeeded":
        return ToolCardPresentation(title=title, inputs=inputs)
    result = ValuationResult.model_validate(outcome.result)
    base = next(row for row in result.scenarios if row.label == "base")
    answer = ToolFact(
        name="base_annual_return_pct",
        label=text("tools.calc.valuation_scenarios.annual_return", scenario="base"),
        value=round(base.annual_return_pct, 2),
        unit=text("chat.tools.units.percent"),
    )
    rows: list[ToolFact] = [
        ToolFact(
            name="current_multiple",
            label=text("tools.calc.fields.multiple"),
            value=round(result.current_multiple, 2),
            unit=text(UNIT_MULTIPLE_KEY),
        )
    ]
    for row in result.scenarios:
        rows.append(
            ToolFact(
                name=f"price_at_horizon_{row.label}",
                label=text(
                    "tools.calc.valuation_scenarios.price_at_horizon", scenario=row.label
                ),
                value=round(row.price_at_horizon, 2),
                unit=text("tools.calc.units.currency", code=currency),
            )
        )
        rows.append(
            percent_fact_named(
                f"annual_return_pct_{row.label}",
                text("tools.calc.valuation_scenarios.annual_return", scenario=row.label),
                row.annual_return_pct,
            )
        )
    return ToolCardPresentation(
        title=title,
        answer=answer,
        rows=rows,
        inputs=inputs,
        notes=[text("tools.calc.notes.scenarios_not_forecasts")],
    )


def percent_fact_named(name: str, label, value_pct: float) -> ToolFact:
    return ToolFact(
        name=name,
        label=label,
        value=round(value_pct, 2),
        unit=text("chat.tools.units.percent"),
    )


def get_valuation_scenarios_declaration() -> ToolDeclaration:
    return ToolDeclaration(
        name="valuation_scenarios",
        description=(
            "Build low, base and high valuation scenarios for an asset from its "
            "price, a per-share figure such as earnings or cash flow, three growth "
            "rates, three multiples and a horizon in years, showing the price each "
            "scenario implies and the annual return that would mean from today's price."
        ),
        handler=compute_valuation_scenarios,
        policy=free_policy(
            "price",
            "per_share",
            "growth_low_pct",
            "growth_base_pct",
            "growth_high_pct",
            "multiple_low",
            "multiple_base",
            "multiple_high",
            "horizon_years",
        ),
        progress=ToolProgressTemplate(
            locale_key="tools.calc.valuation_scenarios.progress"
        ),
        card=ToolCardBinding(
            card_type="valuation_scenarios",
            version=1,
            presenter=present_valuation_scenarios,
        ),
        domain=(
            "Scenarios are arithmetic on stated inputs, labeled low to high, never forecasts.",
            "Growth rates and multiples are cited or given by the user.",
        ),
    )
