"""Valuation scenarios from typed inputs, as low, base and high ranges.

The base growth rate and the per-share figure are the inputs a page states;
a missing bound falls back to the base and a missing multiple to the one the
price already implies, each fallback named on the card as an assumption the
reader can replace. An invested amount, when stated, is carried to the
horizon at each scenario's price.
"""

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
    note,
    pct,
    percent_input,
    required,
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
from argus.domain.tool_fact_projection import ResultFact, ResultProjection

SINGLE_GROWTH_FORECAST = "single_growth_forecast"
CURRENT_MULTIPLE_HELD = "current_multiple_held"
SINGLE_MULTIPLE = "single_multiple"


class ValuationArguments(CalculationArguments):
    symbol: Symbol
    price: float | None = Field(default=None, gt=0)
    per_share: float | None = Field(default=None, gt=0)
    growth_low_pct: float | None = Field(default=None, gt=-100)
    growth_base_pct: float | None = Field(default=None, gt=-100)
    growth_high_pct: float | None = Field(default=None, gt=-100)
    multiple_low: float | None = Field(default=None, gt=0)
    multiple_base: float | None = Field(default=None, gt=0)
    multiple_high: float | None = Field(default=None, gt=0)
    horizon_years: int = Field(default=5, ge=1, le=30)
    amount: float | None = Field(default=None, gt=0)


class ScenarioRow(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    label: str
    growth_pct: float
    multiple: float
    price_at_horizon: float
    annual_return_pct: float
    value_at_horizon: float | None = None


class ValuationResult(CalculationResult):
    current_multiple: float
    scenarios: list[ScenarioRow]
    # Fallbacks the inputs left to the math, by their note code.
    assumptions: list[str] = Field(default_factory=list)


def compute_valuation_scenarios(arguments: ValuationArguments) -> ValuationResult:
    price = required(arguments.price, "price")
    per_share = required(arguments.per_share, "per_share")
    base_growth = required(arguments.growth_base_pct, "growth_base_pct")
    current_multiple = price / per_share
    assumptions: list[str] = []
    if arguments.growth_low_pct is None or arguments.growth_high_pct is None:
        assumptions.append(SINGLE_GROWTH_FORECAST)
    base_multiple = arguments.multiple_base
    if base_multiple is None:
        base_multiple = current_multiple
        assumptions.append(CURRENT_MULTIPLE_HELD)
    if arguments.multiple_low is None or arguments.multiple_high is None:
        assumptions.append(SINGLE_MULTIPLE)
    low_growth = arguments.growth_low_pct
    high_growth = arguments.growth_high_pct
    scenarios = valuation.valuation_scenarios(
        price=price,
        per_share=per_share,
        growth=(
            pct(base_growth if low_growth is None else low_growth),
            pct(base_growth),
            pct(base_growth if high_growth is None else high_growth),
        ),
        multiples=(
            base_multiple if arguments.multiple_low is None else arguments.multiple_low,
            base_multiple,
            base_multiple if arguments.multiple_high is None else arguments.multiple_high,
        ),
        horizon=arguments.horizon_years,
    )
    if isinstance(scenarios, NoSolution):
        raise no_solution(scenarios)
    return ValuationResult(
        current_multiple=current_multiple,
        scenarios=[
            ScenarioRow(
                label=scenario.label,
                growth_pct=scenario.growth * 100.0,
                multiple=scenario.multiple,
                price_at_horizon=scenario.price_at_horizon,
                annual_return_pct=scenario.annual_return * 100.0,
                value_at_horizon=(
                    None
                    if arguments.amount is None
                    else arguments.amount * scenario.price_at_horizon / price
                ),
            )
            for scenario in scenarios
        ],
        assumptions=assumptions,
    )


def _scenario(result: ValuationResult, label: str) -> ScenarioRow:
    return next(row for row in result.scenarios if row.label == label)


def _scenario_projection() -> ResultProjection:
    facts = [
        ResultFact(
            "base_annual_return_pct",
            lambda name, a, r: percent_fact_named(
                name,
                text("tools.calc.valuation_scenarios.annual_return_base"),
                _scenario(r, "base").annual_return_pct,
            ),
            placement="answer",
            when=lambda a, r: _scenario(r, "base").value_at_horizon is None,
        ),
        ResultFact(
            "current_multiple",
            lambda name, a, r: ToolFact(
                name=name,
                label=text("tools.calc.fields.multiple"),
                value=round(r.current_multiple, 2),
                unit=text(UNIT_MULTIPLE_KEY),
            ),
        ),
    ]
    for label in valuation.SCENARIO_LABELS:
        facts.extend(
            (
                ResultFact(
                    f"value_at_horizon_{label}",
                    lambda name, a, r, key=label: ToolFact(
                        name=name,
                        label=text(f"tools.calc.valuation_scenarios.{name}"),
                        value=round(_scenario(r, key).value_at_horizon, 2),
                        unit=text("tools.calc.units.currency", code=a.currency),
                    ),
                    placement="answer_and_row" if label == "base" else "row",
                    when=lambda a, r, key=label: _scenario(r, key).value_at_horizon
                    is not None,
                ),
                ResultFact(
                    f"price_at_horizon_{label}",
                    lambda name, a, r, key=label: ToolFact(
                        name=name,
                        label=text(f"tools.calc.valuation_scenarios.{name}"),
                        value=round(_scenario(r, key).price_at_horizon, 2),
                        unit=text("tools.calc.units.currency", code=a.currency),
                    ),
                ),
                ResultFact(
                    f"annual_return_pct_{label}",
                    lambda name, a, r, key=label: percent_fact_named(
                        name,
                        text(f"tools.calc.valuation_scenarios.annual_return_{key}"),
                        _scenario(r, key).annual_return_pct,
                    ),
                ),
            )
        )
    return ResultProjection(tuple(facts))


RESULT_PROJECTION = _scenario_projection()


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
        money_input("amount", arguments.amount, currency),
    ]
    title = text("tools.calc.valuation_scenarios.title")
    if outcome.status != "succeeded":
        return ToolCardPresentation(title=title, inputs=inputs)
    result = ValuationResult.model_validate(outcome.result)
    return ToolCardPresentation(
        title=title,
        inputs=inputs,
        notes=[
            text("tools.calc.notes.scenarios_not_forecasts"),
            *(note(code) for code in result.assumptions),
        ],
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
            "price, a per-share figure such as earnings or cash flow, a base growth "
            "rate with optional low and high bounds, optional multiples and a "
            "horizon in years, showing the price each scenario implies, the annual "
            "return that would mean from today's price, and what a stated amount "
            "invested today would be worth. A missing bound uses the base and a "
            "missing multiple holds today's."
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
            "amount",
            driving=(
                "price",
                "per_share",
                "growth_base_pct",
                "horizon_years",
                "amount",
                "multiple_base",
                "growth_low_pct",
                "growth_high_pct",
                "multiple_low",
                "multiple_high",
            ),
        ),
        progress=ToolProgressTemplate(
            locale_key="tools.calc.valuation_scenarios.progress"
        ),
        card=ToolCardBinding(
            result_projection=RESULT_PROJECTION,
            card_type="valuation_scenarios",
            version=1,
            presenter=present_valuation_scenarios,
        ),
        domain=(
            "Scenarios are arithmetic on stated inputs, labeled low to high, never forecasts.",
            "Growth rates and multiples are cited or given by the user.",
            "A fallback the inputs left to the math is named on the card as an assumption.",
        ),
    )
