"""Provider-neutral domain contracts for the standalone Clara application."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal, TypeAlias
from urllib.parse import urlparse

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    field_validator,
    model_validator,
)


class DomainModel(BaseModel):
    """Immutable, closed boundary model shared by Clara components."""

    model_config = ConfigDict(extra="forbid", frozen=True)


def _require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must include a timezone")
    return value


def _require_code(value: str, *, length: int, label: str) -> str:
    normalized = value.upper()
    if len(normalized) != length or not normalized.isascii() or not normalized.isalpha():
        raise ValueError(f"{label} must be {length} ASCII letters")
    return normalized


FiniteDecimal: TypeAlias = Annotated[Decimal, Field(allow_inf_nan=False)]
NonNegativeDecimal: TypeAlias = Annotated[
    Decimal, Field(ge=Decimal("0"), allow_inf_nan=False)
]

# External calculation inputs stay inside a deliberate envelope. Three money
# decimals cover ISO minor units used by Clara; six percentage decimals retain
# more precision than the published fixture sources while bounding exponents.
MIN_MONEY = Decimal("0.001")
MAX_MONEY = Decimal("1000000000000")
MIN_RATE_PCT = Decimal("-100")
MAX_RATE_PCT = Decimal("1000")
MoneyInput: TypeAlias = Annotated[
    Decimal,
    Field(
        ge=MIN_MONEY,
        le=MAX_MONEY,
        max_digits=16,
        decimal_places=3,
        allow_inf_nan=False,
    ),
]
FeeInput: TypeAlias = Annotated[
    Decimal,
    Field(
        ge=Decimal("0"),
        le=MAX_MONEY,
        max_digits=16,
        decimal_places=3,
        allow_inf_nan=False,
    ),
]
RatePercentInput: TypeAlias = Annotated[
    Decimal,
    Field(
        gt=MIN_RATE_PCT,
        le=MAX_RATE_PCT,
        max_digits=10,
        decimal_places=6,
        allow_inf_nan=False,
    ),
]


class Source(DomainModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    url: str = Field(min_length=1)
    published_on: date
    retrieved_at: datetime
    kind: Literal["synthetic", "published"]

    @field_validator("retrieved_at")
    @classmethod
    def validate_retrieved_at(cls, value: datetime) -> datetime:
        return _require_aware(value)

    @model_validator(mode="after")
    def validate_url(self) -> Source:
        if self.kind == "synthetic":
            if not self.url.startswith("/api/sources/") or self.url.endswith("/"):
                raise ValueError("synthetic source url must use the local source endpoint")
            return self
        parsed = urlparse(self.url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("published source url must be an absolute HTTP(S) URL")
        return self


class InputSource(DomainModel):
    kind: Literal["user", "assumption"]
    recorded_on: datetime

    @field_validator("recorded_on")
    @classmethod
    def validate_recorded_on(cls, value: datetime) -> datetime:
        return _require_aware(value)


ReceiptSource: TypeAlias = Annotated[
    Source | InputSource,
    Field(discriminator="kind"),
]


class DepositRate(DomainModel):
    id: str = Field(min_length=1)
    country: str
    institution: str = Field(min_length=1)
    product_type: Literal["savings", "certificate"]
    currency: str
    annual_rate_pct: RatePercentInput
    rate_basis: Literal["simple_annual"] = "simple_annual"
    term_days: StrictInt | None = Field(default=None, gt=0, le=3650)
    source: Source
    annual_fee: FeeInput | None = None
    fee_source: Source | None = None

    @field_validator("country")
    @classmethod
    def validate_country(cls, value: str) -> str:
        return _require_code(value, length=2, label="country")

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        return _require_code(value, length=3, label="currency")

    @model_validator(mode="after")
    def validate_term_and_fee(self) -> DepositRate:
        if self.product_type == "savings" and self.term_days is not None:
            raise ValueError("savings rates cannot declare a fixed term")
        if self.product_type == "certificate" and self.term_days is None:
            raise ValueError("certificate rates require a term")
        if (self.annual_fee is None) != (self.fee_source is None):
            raise ValueError("annual_fee and fee_source must be present together")
        return self


class InflationRate(DomainModel):
    country: str
    currency: str
    annual_rate_pct: RatePercentInput
    source: Source

    @field_validator("country")
    @classmethod
    def validate_country(cls, value: str) -> str:
        return _require_code(value, length=2, label="country")

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        return _require_code(value, length=3, label="currency")


class RateDataset(DomainModel):
    id: str = Field(min_length=1)
    country: str
    label: str = Field(min_length=1)
    rates: list[DepositRate] = Field(min_length=1)
    inflation: list[InflationRate] = Field(min_length=1)
    published_on: date
    synthetic: bool

    @field_validator("country")
    @classmethod
    def validate_country(cls, value: str) -> str:
        return _require_code(value, length=2, label="country")

    @model_validator(mode="after")
    def validate_contents(self) -> RateDataset:
        if len({rate.id for rate in self.rates}) != len(self.rates):
            raise ValueError("dataset rate ids must be unique")
        if any(rate.country != self.country for rate in self.rates):
            raise ValueError("every rate must match the dataset country")
        if any(item.country != self.country for item in self.inflation):
            raise ValueError("every inflation basket must match the dataset country")

        basket_currencies = [item.currency for item in self.inflation]
        if len(set(basket_currencies)) != len(basket_currencies):
            raise ValueError("dataset cannot contain duplicate inflation baskets")
        rate_currencies = {rate.currency for rate in self.rates}
        if not rate_currencies.issubset(set(basket_currencies)):
            raise ValueError("every rate currency needs an inflation basket")

        sources = [rate.source for rate in self.rates]
        sources.extend(
            rate.fee_source for rate in self.rates if rate.fee_source is not None
        )
        sources.extend(item.source for item in self.inflation)
        if any(source.published_on > self.published_on for source in sources):
            raise ValueError("dataset publication cannot precede a source publication")
        expected_kind = "synthetic" if self.synthetic else "published"
        if any(source.kind != expected_kind for source in sources):
            raise ValueError("dataset source kinds must match the dataset origin")
        return self


def _without_retrieval_timestamps(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: _without_retrieval_timestamps(item)
            for key, item in value.items()
            if key != "retrieved_at"
        }
    if isinstance(value, list):
        return [_without_retrieval_timestamps(item) for item in value]
    return value


def dataset_content_id(dataset: RateDataset) -> str:
    """Derive the dataset identity from its facts, excluding observation time."""

    raw = dataset.model_dump(mode="json")
    raw.pop("id")
    raw["rates"] = sorted(raw["rates"], key=lambda item: item["id"])
    raw["inflation"] = sorted(
        raw["inflation"],
        key=lambda item: (item["country"], item["currency"], item["source"]["id"]),
    )
    payload = _without_retrieval_timestamps(raw)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class PlacementInputs(DomainModel):
    amount: MoneyInput
    currency: str
    horizon_days: StrictInt = Field(ge=1, le=3650)
    country: str
    current_annual_rate_pct: RatePercentInput | None = None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        return _require_code(value, length=3, label="currency")

    @field_validator("country")
    @classmethod
    def validate_country(cls, value: str) -> str:
        return _require_code(value, length=2, label="country")


class CalculationFormula(DomainModel):
    amount: FiniteDecimal
    horizon_days: StrictInt = Field(ge=1, le=3650)
    year_fraction: FiniteDecimal
    annual_rate_pct: FiniteDecimal
    annual_fee: NonNegativeDecimal
    interest: FiniteDecimal
    fee_amount: NonNegativeDecimal
    nominal_end_value: FiniteDecimal
    inflation_annual_rate_pct: FiniteDecimal
    inflation_factor: Annotated[
        Decimal,
        Field(gt=Decimal("0"), allow_inf_nan=False),
    ]
    real_value: FiniteDecimal


class ComparisonRow(DomainModel):
    id: str = Field(min_length=1)
    institution: str = Field(min_length=1)
    product_type: Literal["cash", "savings", "certificate"]
    is_baseline: bool
    annual_rate_pct: FiniteDecimal
    end_value: FiniteDecimal
    effective_annual_rate_pct: FiniteDecimal
    real_value: FiniteDecimal
    interest: FiniteDecimal
    fees: NonNegativeDecimal
    source: ReceiptSource
    fee_source: Source | None = None
    formula: CalculationFormula

    @model_validator(mode="after")
    def validate_baseline_type(self) -> ComparisonRow:
        if self.is_baseline != (self.product_type == "cash"):
            raise ValueError("only the cash row may be the baseline")
        if self.fees > 0 and self.fee_source is None:
            raise ValueError("a nonzero fee requires its source receipt")
        return self


class ComparisonResult(DomainModel):
    id: str = Field(min_length=1)
    inputs: PlacementInputs
    dataset_id: str = Field(min_length=1)
    created_at: datetime
    input_source: InputSource
    rows: list[ComparisonRow] = Field(min_length=2)
    winner_ids: list[str] = Field(min_length=1)
    inflation: InflationRate
    assumptions: list[str] = Field(min_length=1)
    synthetic: bool

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        return _require_aware(value)

    @model_validator(mode="after")
    def validate_result(self) -> ComparisonResult:
        if sum(row.is_baseline for row in self.rows) != 1:
            raise ValueError("comparison must contain exactly one baseline row")
        if len({row.id for row in self.rows}) != len(self.rows):
            raise ValueError("comparison row ids must be unique")
        maximum = max(row.end_value for row in self.rows)
        expected_winners = {row.id for row in self.rows if row.end_value == maximum}
        if set(self.winner_ids) != expected_winners or len(self.winner_ids) != len(
            expected_winners
        ):
            raise ValueError("winner_ids must contain the complete tied winning set")
        if self.inflation.currency != self.inputs.currency:
            raise ValueError("inflation basket must match the calculation currency")
        return self


class Confirmation(DomainModel):
    id: str = Field(min_length=1)
    inputs: PlacementInputs
    dataset_id: str = Field(min_length=1)
    created_at: datetime
    expires_at: datetime
    assumptions: list[str] = Field(min_length=1)
    synthetic: bool

    @field_validator("created_at", "expires_at")
    @classmethod
    def validate_datetimes(cls, value: datetime) -> datetime:
        return _require_aware(value)

    @model_validator(mode="after")
    def validate_expiry(self) -> Confirmation:
        if self.expires_at <= self.created_at:
            raise ValueError("confirmation expiry must follow creation")
        return self


class DecisionCheck(DomainModel):
    id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    load_id: str = Field(min_length=1)
    created_at: datetime
    status: Literal["unchanged", "changed", "failed"]
    before_comparison_id: str = Field(min_length=1)
    after_comparison_id: str | None = None
    reasons: list[str] = Field(default_factory=list)
    reference_annual_rate_pct: FiniteDecimal | None = None
    error_code: str | None = None
    read_at: datetime | None = None

    @field_validator("created_at", "read_at")
    @classmethod
    def validate_datetimes(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _require_aware(value)

    @model_validator(mode="after")
    def validate_status_fields(self) -> DecisionCheck:
        if self.status == "failed":
            if self.after_comparison_id is not None or not self.error_code:
                raise ValueError("failed checks require an error and no after result")
        elif self.after_comparison_id is None or self.error_code is not None:
            raise ValueError("successful checks require an after result and no error")
        if self.status == "changed" and not self.reasons:
            raise ValueError("changed checks require at least one reason")
        if self.status != "changed" and self.reasons:
            raise ValueError("only changed checks may contain notice reasons")
        return self


class SavedDecision(DomainModel):
    id: str = Field(min_length=1)
    comparison_id: str = Field(min_length=1)
    created_at: datetime
    baseline: ComparisonResult
    latest: ComparisonResult
    checks: list[DecisionCheck] = Field(default_factory=list)

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        return _require_aware(value)


class Notice(DomainModel):
    id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    created_at: datetime
    reasons: list[str] = Field(min_length=1)
    before: ComparisonResult
    after: ComparisonResult
    reference_annual_rate_pct: FiniteDecimal | None = None
    read_at: datetime | None = None

    @field_validator("created_at", "read_at")
    @classmethod
    def validate_datetimes(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _require_aware(value)


class SourceStatus(DomainModel):
    state: Literal["ready", "loading", "stale", "unavailable"]
    last_success_at: datetime | None = None
    last_attempt_at: datetime | None = None
    error_code: str | None = None
    dataset_id: str | None = None
    load_id: str | None = None

    @field_validator("last_success_at", "last_attempt_at")
    @classmethod
    def validate_datetimes(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _require_aware(value)
