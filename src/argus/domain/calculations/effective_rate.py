"""The rate a borrower or saver really gets once compounding and fees count."""

from __future__ import annotations

from pydantic import Field

from argus.domain.calculations._shared import (
    CalculationArguments,
    CalculationResult,
    free_policy,
    input_fact,
    money_fact,
    money_input,
    no_solution,
    pct,
    percent_fact,
    percent_input,
    period_unit,
    text,
)
from argus.domain.finance import ratios, tvm
from argus.domain.finance.outcomes import NoSolution
from argus.domain.tool_contracts import ToolCardPresentation, ToolOutcome
from argus.domain.tool_declaration import (
    ToolCardBinding,
    ToolDeclaration,
    ToolProgressTemplate,
)
from argus.domain.tool_fact_projection import ResultFact, ResultProjection


class EffectiveRateArguments(CalculationArguments):
    nominal_rate_pct: float = Field(gt=-100)
    compounding_per_year: int = Field(default=12, ge=1, le=365)
    amount: float = Field(default=0.0, ge=0)
    fees: float = Field(default=0.0, ge=0)
    periods: int = Field(default=0, ge=0, le=1200)


class EffectiveRateResult(CalculationResult):
    effective_rate_pct: float
    includes_fees: bool
    payment: float
    total_paid: float
    total_cost: float


def compute_effective_rate(arguments: EffectiveRateArguments) -> EffectiveRateResult:
    nominal = pct(arguments.nominal_rate_pct)
    effective = ratios.effective_annual_rate(nominal, arguments.compounding_per_year)
    if isinstance(effective, NoSolution):
        raise no_solution(effective)
    payment = 0.0
    total_paid = 0.0
    total_cost = 0.0
    includes_fees = False
    if arguments.fees > 0 and (arguments.amount <= 0 or arguments.periods <= 0):
        # A fee changes the rate only over a loan's amount and term; without them
        # it cannot be counted, and leaving it out would understate the rate.
        raise no_solution(
            NoSolution(
                field="amount" if arguments.amount <= 0 else "periods",
                code="fees_need_loan_terms",
            )
        )
    if arguments.amount > 0 and arguments.periods > 0:
        per_period = nominal / arguments.compounding_per_year
        level = tvm.payment(arguments.amount, 0.0, per_period, arguments.periods)
        if isinstance(level, NoSolution):
            raise no_solution(level)
        payment = -level
        total_paid = payment * arguments.periods + arguments.fees
        total_cost = total_paid - arguments.amount
        if arguments.fees > 0:
            with_fees = ratios.effective_apr(
                arguments.amount,
                arguments.fees,
                payment,
                arguments.periods,
                arguments.compounding_per_year,
            )
            if isinstance(with_fees, NoSolution):
                raise no_solution(with_fees)
            nominal_with_fees = with_fees
            effective_with_fees = ratios.effective_annual_rate(
                nominal_with_fees, arguments.compounding_per_year
            )
            if isinstance(effective_with_fees, NoSolution):
                raise no_solution(effective_with_fees)
            effective = effective_with_fees
            includes_fees = True
    return EffectiveRateResult(
        effective_rate_pct=effective * 100.0,
        includes_fees=includes_fees,
        payment=payment,
        total_paid=total_paid,
        total_cost=total_cost,
    )


RESULT_PROJECTION = ResultProjection(
    (
        ResultFact(
            "effective_rate_pct",
            lambda name, a, r: percent_fact(name, pct(r.effective_rate_pct)),
            placement="answer",
        ),
        *(
            ResultFact(
                field,
                lambda name, a, r: money_fact(name, getattr(r, name), a.currency),
                when=lambda a, r: r.payment > 0,
            )
            for field in ("payment", "total_paid", "total_cost")
        ),
    )
)


def present_effective_rate(
    arguments: EffectiveRateArguments, outcome: ToolOutcome
) -> ToolCardPresentation:
    currency = arguments.currency
    inputs = [
        percent_input("nominal_rate_pct", arguments.nominal_rate_pct),
        input_fact("compounding_per_year", arguments.compounding_per_year),
        money_input("amount", arguments.amount, currency),
        money_input("fees", arguments.fees, currency),
        input_fact(
            "periods", arguments.periods, period_unit(arguments.compounding_per_year)
        ),
    ]
    title = text("tools.calc.effective_rate.title")
    if outcome.status != "succeeded":
        return ToolCardPresentation(title=title, inputs=inputs)
    result = EffectiveRateResult.model_validate(outcome.result)
    notes = [text("tools.calc.notes.includes_fees")] if result.includes_fees else []
    return ToolCardPresentation(title=title, inputs=inputs, notes=notes)


def get_effective_rate_declaration() -> ToolDeclaration:
    return ToolDeclaration(
        name="effective_rate",
        description=(
            "Turn a nominal yearly rate into the effective yearly rate under its "
            "compounding, and when a loan amount, fees and a number of payments are "
            "given, the effective APR the fees raise it to, with the payment and total cost."
        ),
        handler=compute_effective_rate,
        policy=free_policy(
            "nominal_rate_pct",
            "compounding_per_year",
            "amount",
            "fees",
            "periods",
            driving=("nominal_rate_pct", "amount", "fees", "periods"),
        ),
        progress=ToolProgressTemplate(locale_key="tools.calc.effective_rate.progress"),
        card=ToolCardBinding(
            result_projection=RESULT_PROJECTION,
            card_type="effective_rate",
            version=1,
            presenter=present_effective_rate,
        ),
        domain=("Fees are counted as money kept by the lender on day one.",),
    )
