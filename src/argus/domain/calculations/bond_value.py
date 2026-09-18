"""A bond's price from its yield, or its yield to maturity from its price."""

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
from argus.domain.finance import bonds
from argus.domain.finance.outcomes import NoSolution
from argus.domain.tool_contracts import ToolCardPresentation, ToolOutcome
from argus.domain.tool_declaration import (
    ExactlyOneUnknown,
    ToolCardBinding,
    ToolDeclaration,
    ToolProgressTemplate,
)

UNKNOWN_FIELDS = ("price", "yield_to_maturity_pct")


class BondArguments(CalculationArguments):
    symbol: Symbol
    face_value: float = Field(gt=0)
    coupon_rate_pct: float = Field(ge=0)
    years: float = Field(gt=0, le=100)
    coupons_per_year: int = Field(default=2, ge=1, le=12)
    price: float | None = Field(default=None, ge=0)
    yield_to_maturity_pct: float | None = Field(default=None, gt=-100)


class BondResult(CalculationResult):
    solved_field: str
    solved_value: float
    price: float
    yield_to_maturity_pct: float
    current_yield_pct: float
    annual_coupon: float
    total_coupons: float
    total_return: float


def compute_bond_value(arguments: BondArguments) -> BondResult:
    unknown = next(name for name in UNKNOWN_FIELDS if getattr(arguments, name) is None)
    coupon_rate = pct(arguments.coupon_rate_pct)
    if unknown == "price":
        assert arguments.yield_to_maturity_pct is not None
        ytm = pct(arguments.yield_to_maturity_pct)
        price = bonds.bond_price(
            arguments.face_value,
            coupon_rate,
            ytm,
            arguments.years,
            arguments.coupons_per_year,
        )
        if isinstance(price, NoSolution):
            raise no_solution(price)
        solved_value = price
    else:
        assert arguments.price is not None
        price = arguments.price
        solved_ytm = bonds.bond_yield(
            arguments.face_value,
            coupon_rate,
            price,
            arguments.years,
            arguments.coupons_per_year,
        )
        if isinstance(solved_ytm, NoSolution):
            raise no_solution(solved_ytm)
        ytm = solved_ytm
        solved_value = ytm * 100.0
    current = bonds.current_yield(arguments.face_value, coupon_rate, price)
    if isinstance(current, NoSolution):
        raise no_solution(current)
    annual_coupon = arguments.face_value * coupon_rate
    total_coupons = annual_coupon * arguments.years
    return BondResult(
        solved_field=unknown,
        solved_value=solved_value,
        price=price,
        yield_to_maturity_pct=ytm * 100.0,
        current_yield_pct=current * 100.0,
        annual_coupon=annual_coupon,
        total_coupons=total_coupons,
        total_return=total_coupons + arguments.face_value - price,
    )


def present_bond_value(
    arguments: BondArguments, outcome: ToolOutcome
) -> ToolCardPresentation:
    currency = arguments.currency
    inputs = [
        input_fact("symbol", arguments.symbol),
        money_input("face_value", arguments.face_value, currency),
        percent_input("coupon_rate_pct", arguments.coupon_rate_pct),
        input_fact("years", arguments.years, text(UNIT_YEARS_KEY)),
        input_fact("coupons_per_year", arguments.coupons_per_year),
        money_input("price", arguments.price, currency),
        percent_input("yield_to_maturity_pct", arguments.yield_to_maturity_pct),
    ]
    title = text("tools.calc.bond_value.title")
    if outcome.status != "succeeded":
        return ToolCardPresentation(title=title, inputs=inputs)
    result = BondResult.model_validate(outcome.result)
    answer = (
        money_fact("price", result.price, currency)
        if result.solved_field == "price"
        else percent_fact("yield_to_maturity_pct", pct(result.yield_to_maturity_pct))
    )
    rows = [
        percent_fact("current_yield_pct", pct(result.current_yield_pct)),
        money_fact("annual_coupon", result.annual_coupon, currency),
        money_fact("total_coupons", result.total_coupons, currency),
        money_fact("total_return", result.total_return, currency),
    ]
    return ToolCardPresentation(title=title, answer=answer, rows=rows, inputs=inputs)


def get_bond_value_declaration() -> ToolDeclaration:
    return ToolDeclaration(
        name="bond_value",
        description=(
            "Price a bond or certificate from its face value, coupon rate, term "
            "and yield to maturity, or find the yield to maturity a price implies. "
            "Exactly one of price and yield is blank."
        ),
        handler=compute_bond_value,
        policy=free_policy(
            *UNKNOWN_FIELDS,
            "face_value",
            "coupon_rate_pct",
            "years",
            "coupons_per_year",
            driving=("face_value", "coupon_rate_pct", "years", *UNKNOWN_FIELDS),
        ),
        progress=ToolProgressTemplate(locale_key="tools.calc.bond_value.progress"),
        card=ToolCardBinding(
            card_type="bond_value", version=1, presenter=present_bond_value
        ),
        rules=(ExactlyOneUnknown(fields=UNKNOWN_FIELDS),),
        domain=("Coupons are paid evenly over the year and held to maturity.",),
    )
