"""Growth and compounding, with what inflation leaves of the ending value."""

from __future__ import annotations

from pydantic import Field

from argus.domain.calculations._shared import (
    MAX_PERIODS,
    MIN_ANNUAL_RATE_PCT,
    CalculationArguments,
    CalculationResult,
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
from argus.domain.finance import growth, tvm
from argus.domain.finance.outcomes import NoSolution
from argus.domain.tool_contracts import ToolCardPresentation, ToolFact, ToolOutcome
from argus.domain.tool_declaration import (
    ExactlyOneUnknown,
    ToolCardBinding,
    ToolDeclaration,
    ToolProgressTemplate,
)

UNKNOWN_FIELDS = ("start_value", "end_value", "annual_rate_pct", "periods")


class GrowthArguments(CalculationArguments):
    start_value: float | None = Field(default=None, ge=0)
    contribution: float = Field(default=0.0, ge=0)
    end_value: float | None = Field(default=None, ge=0)
    annual_rate_pct: float | None = Field(default=None, gt=-100)
    periods: int | None = Field(default=None, ge=1, le=1200)
    periods_per_year: int = Field(default=12, ge=1, le=365)
    inflation_rate_pct: float = Field(default=0.0, gt=-100)


class GrowthResult(CalculationResult):
    solved_field: str
    solved_value: float
    start_value: float
    end_value: float
    annual_rate_pct: float
    periods: float
    total_contributed: float
    growth: float
    real_end_value: float
    real_annual_rate_pct: float
    notes: list[str] = Field(default_factory=list)


def compute_growth(arguments: GrowthArguments) -> GrowthResult:
    unknown = next(name for name in UNKNOWN_FIELDS if getattr(arguments, name) is None)
    notes: list[str] = []
    start = arguments.start_value or 0.0
    end = arguments.end_value or 0.0
    periods = float(arguments.periods) if arguments.periods is not None else None
    per_period = (
        pct(arguments.annual_rate_pct) / arguments.periods_per_year
        if arguments.annual_rate_pct is not None
        else None
    )
    contribution = arguments.contribution
    if unknown == "end_value":
        assert per_period is not None and periods is not None
        end = tvm.future_value(-start, -contribution, per_period, periods)
        solved_value = end
    elif unknown == "start_value":
        assert per_period is not None and periods is not None
        # The signed present value is the deposit's cash flow, negative when the
        # saver pays in; the starting balance is its magnitude.
        start = -tvm.present_value(end, -contribution, per_period, periods)
        if start < 0:
            # Contributions alone reach past the target: no starting amount is
            # needed, and the balance ends where they take it.
            start = 0.0
            end = tvm.future_value(0.0, -contribution, per_period, periods)
            notes.append("already_covered")
        solved_value = start
    elif unknown == "annual_rate_pct":
        assert periods is not None
        solved_rate = tvm.rate(-start, -contribution, end, periods)
        if isinstance(solved_rate, NoSolution):
            raise no_solution(NoSolution(field="annual_rate_pct", code=solved_rate.code))
        per_period = solved_rate
        solved_value = per_period * arguments.periods_per_year * 100.0
        if solved_value <= MIN_ANNUAL_RATE_PCT:
            # A periodic loss this steep annualizes past the rate the input accepts.
            raise no_solution(
                NoSolution(field="annual_rate_pct", code="rate_out_of_range")
            )
    else:
        assert per_period is not None
        if tvm.target_already_met(start, contribution, end, per_period):
            # The balance already meets the target: no period is needed, and the
            # plan ends at the balance itself.
            count = 0.0
            end = start
            notes.append("already_covered")
        else:
            count = tvm.periods(-start, -contribution, end, per_period)
            if isinstance(count, NoSolution):
                raise no_solution(
                    NoSolution(field="annual_rate_pct", code="rate_never_reaches_target")
                )
            if count > MAX_PERIODS:
                raise no_solution(
                    NoSolution(
                        field="contribution" if contribution else "annual_rate_pct",
                        code="periods_beyond_limit",
                    )
                )
        periods = count
        solved_value = count
    assert per_period is not None and periods is not None
    annual_rate = per_period * arguments.periods_per_year
    # Inflation is yearly, so the periodic rate compounds to a year before the
    # Fisher relation compares the two.
    effective_annual = (1.0 + per_period) ** arguments.periods_per_year - 1.0
    years = periods / arguments.periods_per_year
    inflation = pct(arguments.inflation_rate_pct)
    real_end = growth.real_value(end, inflation, years)
    real_annual = growth.real_rate(effective_annual, inflation)
    if isinstance(real_end, NoSolution) or isinstance(real_annual, NoSolution):
        raise no_solution(
            NoSolution(field="inflation_rate_pct", code="rate_out_of_range")
        )
    total_contributed = start + contribution * periods
    return GrowthResult(
        solved_field=unknown,
        solved_value=solved_value,
        start_value=start,
        end_value=end,
        annual_rate_pct=annual_rate * 100.0,
        periods=periods,
        total_contributed=total_contributed,
        growth=end - total_contributed,
        real_end_value=real_end,
        real_annual_rate_pct=real_annual * 100.0,
        notes=notes,
    )


def present_growth(
    arguments: GrowthArguments, outcome: ToolOutcome
) -> ToolCardPresentation:
    currency = arguments.currency
    inputs = [
        money_input("start_value", arguments.start_value, currency),
        money_input("contribution", arguments.contribution, currency),
        money_input("end_value", arguments.end_value, currency),
        percent_input("annual_rate_pct", arguments.annual_rate_pct),
        input_fact("periods", arguments.periods, period_unit(arguments.periods_per_year)),
        input_fact("periods_per_year", arguments.periods_per_year),
        percent_input("inflation_rate_pct", arguments.inflation_rate_pct),
    ]
    title = text("tools.calc.growth_projection.title")
    if outcome.status != "succeeded":
        return ToolCardPresentation(title=title, inputs=inputs)
    result = GrowthResult.model_validate(outcome.result)
    if result.solved_field == "annual_rate_pct":
        answer: ToolFact = percent_fact("annual_rate_pct", pct(result.solved_value))
    elif result.solved_field == "periods":
        answer = number_fact(
            "periods",
            rounded(result.solved_value, 1),
            period_unit(arguments.periods_per_year),
        )
    else:
        answer = money_fact(result.solved_field, result.solved_value, currency)
    rows = [
        money_fact("total_contributed", result.total_contributed, currency),
        money_fact("growth", result.growth, currency),
        money_fact("real_end_value", result.real_end_value, currency),
        percent_fact("real_annual_rate_pct", pct(result.real_annual_rate_pct)),
    ]
    return ToolCardPresentation(
        title=title,
        answer=answer,
        rows=rows,
        inputs=inputs,
        notes=[note(code) for code in result.notes],
    )


def get_growth_projection_declaration() -> ToolDeclaration:
    return ToolDeclaration(
        name="growth_projection",
        description=(
            "Project a balance that compounds at an annual rate with optional "
            "periodic contributions, solving for the one blank among starting "
            "value, ending value, annual rate and number of periods, and show "
            "the ending value and rate after inflation."
        ),
        handler=compute_growth,
        policy=free_policy(
            *UNKNOWN_FIELDS,
            "contribution",
            "periods_per_year",
            "inflation_rate_pct",
            driving=(*UNKNOWN_FIELDS, "contribution", "inflation_rate_pct"),
        ),
        progress=ToolProgressTemplate(locale_key="tools.calc.growth_projection.progress"),
        card=ToolCardBinding(
            card_type="growth_projection", version=1, presenter=present_growth
        ),
        rules=(ExactlyOneUnknown(fields=UNKNOWN_FIELDS),),
        domain=(
            "Real values follow the Fisher relation, never a subtraction of rates.",
            "The rate is an input the user gives or a page cites, never a forecast.",
        ),
    )
