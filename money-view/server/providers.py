"""Provider seams and fail-closed real-source adapters for Clara."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal, Protocol, TypeAlias, runtime_checkable

import httpx
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictInt,
    field_validator,
)

from .fixtures import FixtureProvider
from .models import RateDataset

SB_DEPOSIT_DETAIL_URL = (
    "https://apis.sb.gob.do/estadisticas/v2/captaciones/detalle"
)


class ProviderError(RuntimeError):
    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        self.detail = detail
        super().__init__(detail or code)


class ProviderUnavailableError(ProviderError):
    pass


class ProviderPayloadError(ProviderError):
    pass


class ProviderDataIncompleteError(ProviderError):
    pass


@runtime_checkable
class RateProvider(Protocol):
    def fetch(self, country: str) -> RateDataset: ...


class _ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


_MAX_IEEE_754_DOUBLE = Decimal("1.7976931348623157e308")


def _json_number_to_decimal(value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("value must be a JSON number")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("value must be finite")
    parsed = Decimal(str(value))
    if abs(parsed) > _MAX_IEEE_754_DOUBLE:
        raise ValueError("value exceeds the documented double range")
    return parsed


SBJsonNumber: TypeAlias = Annotated[
    Decimal,
    BeforeValidator(_json_number_to_decimal),
]
SBInt32Quantity: TypeAlias = Annotated[
    StrictInt,
    Field(ge=0, le=2_147_483_647),
]


class SBDepositRecord(_ClosedModel):
    """Exact optional fields documented for SB's deposit-detail response."""

    periodo: str | None = None
    tipoEntidad: str | None = None
    entidad: str | None = None
    region: str | None = None
    provincia: str | None = None
    persona: str | None = None
    genero: str | None = None
    tipoCliente: str | None = None
    instrumentoCaptacion: str | None = None
    moneda: str | None = None
    divisa: str | None = None
    partidaNivel1: str | None = None
    partidaNivel2: str | None = None
    publicoPrivadoNivel1: str | None = None
    publicoPrivadoNivel2: str | None = None
    financieroNoFinanciero: str | None = None
    residenteNoResidente: str | None = None
    componente: str | None = None
    instrumentoMedio: str | None = None
    contraParte: str | None = None
    situacionNivel1: str | None = None
    situacionNivel2: str | None = None
    cantidadInstrumento: SBInt32Quantity | None = None
    balance: SBJsonNumber | None = None
    tasaPrimedioPonderadoPorBalance: SBJsonNumber | None = None
    tasaPrimedioPonderado: SBJsonNumber | None = None


SBValidationIssue = Literal[
    "missing_maturity",
    "unknown_rate_unit",
    "unknown_annualization",
    "missing_publication_date",
]


class SBNormalizedDeposit(_ClosedModel):
    institution: str | None
    instrument_category: str | None
    currency: str | None
    currency_description: str | None
    effective_period: str | None
    observed_balance: Decimal | None
    average_rate_paid_on_balances: Decimal | None
    source_url: str
    retrieved_at: datetime
    validation_issues: list[SBValidationIssue]

    @field_validator("retrieved_at")
    @classmethod
    def validate_retrieved_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("retrieved_at must include a timezone")
        return value


class _Response(Protocol):
    headers: object

    def json(self) -> object: ...

    def raise_for_status(self) -> None: ...


class _HTTPClient(Protocol):
    def get(
        self,
        url: str,
        *,
        params: dict[str, object],
        headers: dict[str, str],
        timeout: float,
    ) -> _Response: ...


def parse_sb_records(payload: object) -> list[SBDepositRecord]:
    if not isinstance(payload, list):
        raise ProviderPayloadError(
            "invalid_sb_payload",
            "SB deposit detail response must be a JSON array",
        )
    records: list[SBDepositRecord] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ProviderPayloadError(
                "invalid_sb_record",
                f"SB record {index} is not an object",
            )
        try:
            records.append(SBDepositRecord.model_validate(item))
        except ValueError as exc:
            raise ProviderPayloadError(
                "invalid_sb_record",
                f"SB record {index} does not match the documented schema",
            ) from exc
    return records


def normalize_sb_record(
    record: SBDepositRecord,
    *,
    retrieved_at: datetime,
) -> SBNormalizedDeposit:
    """Map only verified semantics and retain every calculation blocker."""

    return SBNormalizedDeposit(
        institution=record.entidad,
        instrument_category=record.instrumentoCaptacion,
        currency=record.divisa,
        currency_description=record.moneda,
        effective_period=record.periodo,
        observed_balance=record.balance,
        average_rate_paid_on_balances=record.tasaPrimedioPonderadoPorBalance,
        source_url=SB_DEPOSIT_DETAIL_URL,
        retrieved_at=retrieved_at,
        validation_issues=[
            "missing_maturity",
            "unknown_rate_unit",
            "unknown_annualization",
            "missing_publication_date",
        ],
    )


def _has_next(headers: object) -> bool:
    try:
        raw = headers["x-pagination"]  # type: ignore[index]
    except (KeyError, TypeError) as exc:
        raise ProviderPayloadError(
            "missing_sb_pagination",
            "SB response omitted the documented x-pagination header",
        ) from exc
    try:
        metadata = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ProviderPayloadError(
            "invalid_sb_pagination",
            "SB x-pagination header is not valid JSON",
        ) from exc
    if not isinstance(metadata, dict) or not isinstance(metadata.get("HasNext"), bool):
        raise ProviderPayloadError(
            "invalid_sb_pagination",
            "SB x-pagination header omitted boolean HasNext",
        )
    return metadata["HasNext"]


class SBProvider:
    """Raw SB reader that intentionally cannot yield a calculable dataset yet."""

    def __init__(
        self,
        *,
        subscription_key: str | None,
        period_start: str | None,
        period_end: str | None = None,
        client: _HTTPClient | None = None,
        max_pages: int = 10,
        records_per_page: int = 1000,
        timeout_seconds: float = 15.0,
    ) -> None:
        if max_pages < 1:
            raise ValueError("max_pages must be at least one")
        if records_per_page < 1:
            raise ValueError("records_per_page must be at least one")
        self._subscription_key = subscription_key
        self._period_start = period_start
        self._period_end = period_end
        self._client = client
        self._max_pages = max_pages
        self._records_per_page = records_per_page
        self._timeout_seconds = timeout_seconds

    def _validate_config(self, country: str) -> None:
        if country.upper() != "DO":
            raise ProviderUnavailableError(
                "unsupported_country",
                "The SB adapter only covers Dominican Republic source rows",
            )
        if not self._subscription_key or not self._subscription_key.strip():
            raise ProviderUnavailableError(
                "missing_sb_subscription_key",
                "SB subscription access is required before making a request",
            )
        if not self._period_start:
            raise ProviderUnavailableError(
                "missing_sb_period",
                "An explicit SB reporting period is required",
            )

    def fetch_raw(self, country: str) -> list[SBNormalizedDeposit]:
        self._validate_config(country)
        client: _HTTPClient = self._client or httpx.Client()
        records: list[SBDepositRecord] = []
        retrieved_at = datetime.now(timezone.utc)

        for page in range(1, self._max_pages + 1):
            params: dict[str, object] = {
                "periodoInicial": self._period_start,
                "paginas": page,
                "registros": self._records_per_page,
            }
            if self._period_end:
                params["periodoFinal"] = self._period_end
            response = client.get(
                SB_DEPOSIT_DETAIL_URL,
                params=params,
                headers={
                    "Ocp-Apim-Subscription-Key": self._subscription_key or "",
                },
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            records.extend(parse_sb_records(response.json()))
            has_next = _has_next(response.headers)
            if not has_next:
                return [
                    normalize_sb_record(record, retrieved_at=retrieved_at)
                    for record in records
                ]

        raise ProviderPayloadError(
            "sb_pagination_limit_reached",
            f"SB indicated more than the configured {self._max_pages} pages",
        )

    def fetch(self, country: str) -> RateDataset:
        rows = self.fetch_raw(country)
        raise ProviderDataIncompleteError(
            "sb_not_calculation_ready",
            (
                f"Read {len(rows)} raw SB rows, but SB does not provide verified "
                "maturity, publication date, rate unit, or annualization"
            ),
        )


class BCRDProvider:
    """Explicit placeholder until an authorized BCRD machine schema is verified."""

    def fetch(self, country: str) -> RateDataset:
        del country
        raise ProviderUnavailableError(
            "bcrd_schema_unverified",
            "BCRD endpoint, authentication, schema, and publication metadata are unverified",
        )


__all__ = [
    "BCRDProvider",
    "FixtureProvider",
    "ProviderDataIncompleteError",
    "ProviderError",
    "ProviderPayloadError",
    "ProviderUnavailableError",
    "RateProvider",
    "SBDepositRecord",
    "SBNormalizedDeposit",
    "SBProvider",
    "normalize_sb_record",
    "parse_sb_records",
]
