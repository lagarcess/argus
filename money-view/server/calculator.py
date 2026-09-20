"""Pure placement comparison math for Clara."""

from __future__ import annotations

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, DecimalException, localcontext
from typing import Literal

from .models import (
    CalculationFormula,
    ComparisonResult,
    ComparisonRow,
    DepositRate,
    InflationRate,
    InputSource,
    PlacementInputs,
    RateDataset,
    ReceiptSource,
    Source,
    dataset_content_id,
)

_DAYS_PER_YEAR = Decimal("365")
_HUNDRED = Decimal("100")

_ZERO_DIGIT_CURRENCIES = {
    "BIF",
    "CLP",
    "DJF",
    "GNF",
    "ISK",
    "JPY",
    "KMF",
    "KRW",
    "PYG",
    "RWF",
    "UGX",
    "VND",
    "VUV",
    "XAF",
    "XOF",
    "XPF",
}
_THREE_DIGIT_CURRENCIES = {
    "BHD",
    "IQD",
    "JOD",
    "KWD",
    "LYD",
    "OMR",
    "TND",
}

ASSUMPTIONS = [
    "simple_annual_act_365",
    "inflation_constant_illustration",
    "no_fx_or_reinvestment",
    "taxes_excluded",
    "unknown_fees_excluded",
]


class CalculationError(ValueError):
    """A stable, transport-independent calculation rejection."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        self.detail = detail
        super().__init__(detail or code)


def currency_minor_digits(currency: str) -> int:
    """Return the common ISO 4217 display precision used by the presenter."""

    if currency in _ZERO_DIGIT_CURRENCIES:
        return 0
    if currency in _THREE_DIGIT_CURRENCIES:
        return 3
    return 2


def _eligible_rates(inputs: PlacementInputs, dataset: RateDataset) -> list[DepositRate]:
    return [
        rate
        for rate in dataset.rates
        if rate.country == inputs.country
        and rate.currency == inputs.currency
        and (
            rate.product_type == "savings"
            or rate.term_days == inputs.horizon_days
        )
    ]


def _inflation_for(inputs: PlacementInputs, dataset: RateDataset) -> InflationRate:
    matches = [
        item
        for item in dataset.inflation
        if item.country == inputs.country and item.currency == inputs.currency
    ]
    if not matches:
        raise CalculationError(
            "missing_inflation_basket",
            f"No inflation basket matches {inputs.country}/{inputs.currency}",
        )
    if len(matches) > 1:
        raise CalculationError(
            "ambiguous_inflation_basket",
            f"More than one inflation basket matches {inputs.country}/{inputs.currency}",
        )
    return matches[0]


def _make_row(
    *,
    row_id: str,
    institution: str,
    product_type: Literal["cash", "savings", "certificate"],
    is_baseline: bool,
    annual_rate_pct: Decimal,
    annual_fee: Decimal,
    source: ReceiptSource,
    fee_source: Source | None,
    inputs: PlacementInputs,
    inflation: InflationRate,
) -> ComparisonRow:
    try:
        with localcontext() as context:
            context.prec = 50
            year_fraction = Decimal(inputs.horizon_days) / _DAYS_PER_YEAR
            interest = inputs.amount * annual_rate_pct / _HUNDRED * year_fraction
            fee_amount = annual_fee * year_fraction
            end_value = inputs.amount + interest - fee_amount
            if end_value <= 0:
                raise CalculationError(
                    "nonpositive_end_value",
                    f"{institution} produces a nonpositive modeled end value",
                )
            effective_annual_rate_pct = (
                (end_value / inputs.amount) ** (Decimal("1") / year_fraction)
                - Decimal("1")
            ) * _HUNDRED
            inflation_factor = (
                Decimal("1") + inflation.annual_rate_pct / _HUNDRED
            ) ** year_fraction
            real_value = end_value / inflation_factor
    except DecimalException as exc:
        raise CalculationError(
            "invalid_numeric_result",
            f"The modeled values for {institution} are outside supported bounds",
        ) from exc

    formula = CalculationFormula(
        amount=inputs.amount,
        horizon_days=inputs.horizon_days,
        year_fraction=year_fraction,
        annual_rate_pct=annual_rate_pct,
        annual_fee=annual_fee,
        interest=interest,
        fee_amount=fee_amount,
        nominal_end_value=end_value,
        inflation_annual_rate_pct=inflation.annual_rate_pct,
        inflation_factor=inflation_factor,
        real_value=real_value,
    )
    return ComparisonRow(
        id=row_id,
        institution=institution,
        product_type=product_type,
        is_baseline=is_baseline,
        annual_rate_pct=annual_rate_pct,
        end_value=end_value,
        effective_annual_rate_pct=effective_annual_rate_pct,
        real_value=real_value,
        interest=interest,
        fees=fee_amount,
        source=source,
        fee_source=fee_source,
        formula=formula,
    )


def confirmation_assumptions(inputs: PlacementInputs) -> list[str]:
    """Return the one canonical assumption set used before and after compute."""

    assumptions = list(ASSUMPTIONS)
    if inputs.current_annual_rate_pct is None:
        assumptions.append("zero_interest_cash_baseline_confirmed")
    return assumptions


def validate_comparison_inputs(
    inputs: PlacementInputs,
    dataset: RateDataset,
) -> None:
    """Validate dataset eligibility without calculating or exposing result figures."""

    if dataset.id != dataset_content_id(dataset):
        raise CalculationError(
            "invalid_dataset_identity",
            "Dataset id does not match its calculation facts",
        )
    if dataset.country != inputs.country:
        raise CalculationError(
            "country_mismatch",
            f"Dataset {dataset.id} does not cover {inputs.country}",
        )
    _inflation_for(inputs, dataset)
    if not _eligible_rates(inputs, dataset):
        raise CalculationError(
            "no_comparable_rates",
            "No savings rate or exact-horizon certificate matches the inputs",
        )


def calculate(
    inputs: PlacementInputs,
    dataset: RateDataset,
    *,
    comparison_id: str,
    created_at: datetime,
) -> ComparisonResult:
    """Compare cash and eligible deposits without rounding intermediate values."""

    if not comparison_id:
        raise CalculationError("invalid_comparison_id", "comparison_id is required")
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise CalculationError("invalid_created_at", "created_at must include a timezone")
    validate_comparison_inputs(inputs, dataset)
    inflation = _inflation_for(inputs, dataset)
    rates = _eligible_rates(inputs, dataset)

    input_source = InputSource(
        kind="user" if inputs.current_annual_rate_pct is not None else "assumption",
        recorded_on=created_at,
    )
    baseline_rate = inputs.current_annual_rate_pct or Decimal("0")
    rows = [
        _make_row(
            row_id="cash",
            institution="Current cash baseline",
            product_type="cash",
            is_baseline=True,
            annual_rate_pct=baseline_rate,
            annual_fee=Decimal("0"),
            source=input_source,
            fee_source=None,
            inputs=inputs,
            inflation=inflation,
        )
    ]
    for rate in rates:
        rows.append(
            _make_row(
                row_id=f"deposit:{rate.id}",
                institution=rate.institution,
                product_type=rate.product_type,
                is_baseline=False,
                annual_rate_pct=rate.annual_rate_pct,
                annual_fee=rate.annual_fee or Decimal("0"),
                source=rate.source,
                fee_source=rate.fee_source,
                inputs=inputs,
                inflation=inflation,
            )
        )

    maximum = max(row.end_value for row in rows)
    winner_ids = [row.id for row in rows if row.end_value == maximum]
    return ComparisonResult(
        id=comparison_id,
        inputs=inputs,
        dataset_id=dataset.id,
        created_at=created_at,
        input_source=input_source,
        rows=rows,
        winner_ids=winner_ids,
        inflation=inflation,
        assumptions=confirmation_assumptions(inputs),
        synthetic=dataset.synthetic,
    )


def _money(value: Decimal, digits: int) -> str:
    try:
        with localcontext() as context:
            integer_digits = max(value.adjusted() + 1, 1)
            context.prec = max(50, integer_digits + digits + 2)
            quantum = Decimal("1").scaleb(-digits)
            rounded = value.quantize(quantum, rounding=ROUND_HALF_UP)
            return f"{rounded:.{digits}f}"
    except DecimalException as exc:
        raise CalculationError(
            "invalid_numeric_result",
            "A monetary value is outside the supported presentation bounds",
        ) from exc


def present_result(result: ComparisonResult) -> dict[str, object]:
    """Serialize a comparison, applying currency rounding exactly once at the edge."""

    data = result.model_dump(mode="json")
    digits = currency_minor_digits(result.inputs.currency)
    inputs = data["inputs"]
    assert isinstance(inputs, dict)
    inputs["amount"] = _money(result.inputs.amount, digits)

    rows = data["rows"]
    assert isinstance(rows, list)
    for presented, row in zip(rows, result.rows, strict=True):
        assert isinstance(presented, dict)
        for field in ("end_value", "real_value", "interest", "fees"):
            presented[field] = _money(getattr(row, field), digits)

        formula = presented["formula"]
        assert isinstance(formula, dict)
        for field in (
            "amount",
            "annual_fee",
            "interest",
            "fee_amount",
            "nominal_end_value",
            "real_value",
        ):
            formula[field] = _money(getattr(row.formula, field), digits)
    return data
