"""A price multiple such as P/E: price, the per-share figure, or the multiple."""

from __future__ import annotations

from pydantic import Field

from argus.domain.calculations._shared import (
    UNIT_MULTIPLE_KEY,
    CalculationArguments,
    CalculationResult,
    Symbol,
    free_policy,
    input_fact,
    money_fact,
    money_input,
    no_solution,
    number_fact,
    percent_fact,
    rounded,
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

UNKNOWN_FIELDS = ("price", "per_share", "multiple")


class PriceMultipleArguments(CalculationArguments):
    symbol: Symbol
    price: float | None = Field(default=None, ge=0)
    per_share: float | None = None
    multiple: float | None = None


class PriceMultipleResult(CalculationResult):
    solved_field: str
    solved_value: float
    price: float
    per_share: float
    multiple: float
    earnings_yield_pct: float


def compute_price_multiple(arguments: PriceMultipleArguments) -> PriceMultipleResult:
    unknown = next(name for name in UNKNOWN_FIELDS if getattr(arguments, name) is None)
    if unknown == "multiple":
        assert arguments.price is not None and arguments.per_share is not None
        multiple = ratios.price_to_earnings(arguments.price, arguments.per_share)
        if isinstance(multiple, NoSolution):
            raise no_solution(NoSolution(field="per_share", code=multiple.code))
        price, per_share, solved_value = arguments.price, arguments.per_share, multiple
    elif unknown == "price":
        assert arguments.per_share is not None and arguments.multiple is not None
        price = arguments.per_share * arguments.multiple
        if price < 0:
            # A price below zero is outside the price the input itself accepts.
            raise no_solution(
                NoSolution(
                    field="per_share" if arguments.per_share < 0 else "multiple",
                    code="price_below_zero",
                )
            )
        per_share, multiple, solved_value = arguments.per_share, arguments.multiple, price
    else:
        assert arguments.price is not None and arguments.multiple is not None
        per_share = ratios.ratio(arguments.price, arguments.multiple, field="multiple")
        if isinstance(per_share, NoSolution):
            raise no_solution(per_share)
        price, multiple, solved_value = arguments.price, arguments.multiple, per_share
    earnings_yield = ratios.ratio(per_share, price, field="price")
    if isinstance(earnings_yield, NoSolution):
        raise no_solution(earnings_yield)
    return PriceMultipleResult(
        solved_field=unknown,
        solved_value=solved_value,
        price=price,
        per_share=per_share,
        multiple=multiple,
        earnings_yield_pct=earnings_yield * 100.0,
    )


RESULT_PROJECTION = ResultProjection(
    (
        *solved_facts(
            UNKNOWN_FIELDS,
            lambda name, a, r: number_fact(
                name, rounded(r.multiple), text(UNIT_MULTIPLE_KEY)
            )
            if name == "multiple"
            else money_fact(name, r.solved_value, a.currency),
        ),
        ResultFact(
            "earnings_yield_pct",
            lambda name, a, r: percent_fact(name, r.earnings_yield_pct / 100.0),
        ),
    )
)


def present_price_multiple(
    arguments: PriceMultipleArguments, outcome: ToolOutcome
) -> ToolCardPresentation:
    currency = arguments.currency
    inputs = [
        input_fact("symbol", arguments.symbol),
        money_input("price", arguments.price, currency),
        money_input("per_share", arguments.per_share, currency),
        input_fact("multiple", arguments.multiple, text(UNIT_MULTIPLE_KEY)),
    ]
    title = text("tools.calc.price_multiple.title")
    if outcome.status != "succeeded":
        return ToolCardPresentation(title=title, inputs=inputs)
    return ToolCardPresentation(title=title, inputs=inputs)


def get_price_multiple_declaration() -> ToolDeclaration:
    return ToolDeclaration(
        name="price_multiple",
        description=(
            "Relate a price to a per-share figure through a multiple such as "
            "price to earnings, price to cash flow or price to book: give any two "
            "of price, per-share figure and multiple and the third is solved."
        ),
        handler=compute_price_multiple,
        policy=free_policy(*UNKNOWN_FIELDS, driving=UNKNOWN_FIELDS),
        progress=ToolProgressTemplate(locale_key="tools.calc.price_multiple.progress"),
        card=ToolCardBinding(
            result_projection=RESULT_PROJECTION,
            card_type="price_multiple",
            version=1,
            presenter=present_price_multiple,
        ),
        rules=(ExactlyOneUnknown(fields=UNKNOWN_FIELDS),),
        domain=("A multiple is a ratio of cited figures, never a verdict on value.",),
    )
