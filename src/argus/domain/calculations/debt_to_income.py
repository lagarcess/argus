"""Debt to income: monthly debt payments as a share of monthly income."""

from __future__ import annotations

from pydantic import Field

from argus.domain.calculations._shared import (
    CalculationArguments,
    CalculationResult,
    free_policy,
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

UNKNOWN_FIELDS = ("monthly_debt_payments", "monthly_income", "ratio_pct")


class DebtToIncomeArguments(CalculationArguments):
    monthly_debt_payments: float | None = Field(default=None, ge=0)
    monthly_income: float | None = Field(default=None, ge=0)
    ratio_pct: float | None = Field(default=None, ge=0)


class DebtToIncomeResult(CalculationResult):
    solved_field: str
    solved_value: float
    monthly_debt_payments: float
    monthly_income: float
    ratio_pct: float
    income_after_debt: float


def compute_debt_to_income(arguments: DebtToIncomeArguments) -> DebtToIncomeResult:
    unknown = next(name for name in UNKNOWN_FIELDS if getattr(arguments, name) is None)
    if unknown == "ratio_pct":
        assert (
            arguments.monthly_debt_payments is not None
            and arguments.monthly_income is not None
        )
        ratio = ratios.debt_to_income(
            arguments.monthly_debt_payments, arguments.monthly_income
        )
        if isinstance(ratio, NoSolution):
            raise no_solution(ratio)
        debt, income, solved_value = (
            arguments.monthly_debt_payments,
            arguments.monthly_income,
            ratio * 100.0,
        )
    elif unknown == "monthly_debt_payments":
        assert arguments.monthly_income is not None and arguments.ratio_pct is not None
        debt = arguments.monthly_income * pct(arguments.ratio_pct)
        income, ratio, solved_value = (
            arguments.monthly_income,
            pct(arguments.ratio_pct),
            debt,
        )
    else:
        assert (
            arguments.monthly_debt_payments is not None
            and arguments.ratio_pct is not None
        )
        income = ratios.ratio(
            arguments.monthly_debt_payments, pct(arguments.ratio_pct), field="ratio_pct"
        )
        if isinstance(income, NoSolution):
            raise no_solution(income)
        debt, ratio, solved_value = (
            arguments.monthly_debt_payments,
            pct(arguments.ratio_pct),
            income,
        )
    return DebtToIncomeResult(
        solved_field=unknown,
        solved_value=solved_value,
        monthly_debt_payments=debt,
        monthly_income=income,
        ratio_pct=ratio * 100.0,
        income_after_debt=income - debt,
    )


RESULT_PROJECTION = ResultProjection(
    (
        *solved_facts(
            UNKNOWN_FIELDS,
            lambda name, a, r: percent_fact(name, pct(r.ratio_pct))
            if name == "ratio_pct"
            else money_fact(name, r.solved_value, a.currency),
        ),
        ResultFact(
            "income_after_debt",
            lambda name, a, r: money_fact(name, r.income_after_debt, a.currency),
        ),
    )
)


def present_debt_to_income(
    arguments: DebtToIncomeArguments, outcome: ToolOutcome
) -> ToolCardPresentation:
    currency = arguments.currency
    inputs = [
        money_input("monthly_debt_payments", arguments.monthly_debt_payments, currency),
        money_input("monthly_income", arguments.monthly_income, currency),
        percent_input("ratio_pct", arguments.ratio_pct),
    ]
    title = text("tools.calc.debt_to_income.title")
    if outcome.status != "succeeded":
        return ToolCardPresentation(title=title, inputs=inputs)
    return ToolCardPresentation(title=title, inputs=inputs)


def get_debt_to_income_declaration() -> ToolDeclaration:
    return ToolDeclaration(
        name="debt_to_income",
        description=(
            "Monthly debt payments as a share of monthly income: give any two of "
            "monthly debt payments, monthly income and the ratio."
        ),
        handler=compute_debt_to_income,
        policy=free_policy(*UNKNOWN_FIELDS, driving=UNKNOWN_FIELDS),
        progress=ToolProgressTemplate(locale_key="tools.calc.debt_to_income.progress"),
        card=ToolCardBinding(
            result_projection=RESULT_PROJECTION,
            card_type="debt_to_income",
            version=1,
            presenter=present_debt_to_income,
        ),
        rules=(ExactlyOneUnknown(fields=UNKNOWN_FIELDS),),
        domain=(
            "A ratio, not a lending decision; thresholds are the lender's to state.",
        ),
    )
