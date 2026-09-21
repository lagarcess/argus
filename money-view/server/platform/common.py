"""Small shared boundary: ownership, dated evidence and exact money."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import Request
from pydantic import BaseModel, ConfigDict, Field

from ..store import Store


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


Amount = Annotated[Decimal, Field(allow_inf_nan=False, ge=-1e12, le=1e12)]
PositiveAmount = Annotated[Decimal, Field(allow_inf_nan=False, gt=0, le=1e12)]
NonNegativeAmount = Annotated[Decimal, Field(allow_inf_nan=False, ge=0, le=1e12)]


class PlatformError(Exception):
    def __init__(self, code: str, status: int = 422):
        self.code = code
        self.status = status
        super().__init__(code)


@dataclass(frozen=True)
class Context:
    user_id: str
    household_id: str
    role: Literal["owner", "editor", "viewer"]
    session_id: str


class Evidence(Model):
    id: str
    kind: Literal["synthetic", "user", "calculated", "published"]
    title: str
    as_of: date
    recorded_at: datetime
    published_on: date | None = None
    method: str | None = None
    inputs: list[str] = Field(default_factory=list)
    url: str | None = None


def now() -> datetime:
    return datetime.now(timezone.utc)


def identifier(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def require_editor(context: Context) -> None:
    if context.role == "viewer":
        raise PlatformError("read_only_household", 403)


def require_owner(context: Context) -> None:
    if context.role != "owner":
        raise PlatformError("owner_required", 403)


def get_store(request: Request) -> Store:
    return request.app.state.store


def get_context(request: Request) -> Context:
    return request.app.state.identity.context(request)


# One currency precision owner. Unknown codes fail instead of silently rounding.
CURRENCY_DIGITS = {
    "DOP": 2,
    "USD": 2,
    "NZD": 2,
    "EUR": 2,
    "GBP": 2,
    "CAD": 2,
    "JPY": 0,
    "KWD": 3,
}


def minor_units(amount: Decimal, currency: str) -> int:
    if currency not in CURRENCY_DIGITS:
        raise PlatformError("unsupported_currency")
    scaled = amount * (10 ** CURRENCY_DIGITS[currency])
    if (
        not amount.is_finite()
        or abs(amount) > Decimal("1e12")
        or scaled != scaled.to_integral_value()
    ):
        raise PlatformError("invalid_money_precision")
    return int(scaled)


def decimal_amount(minor: int, currency: str) -> str:
    if currency not in CURRENCY_DIGITS:
        raise PlatformError("unsupported_currency")
    return format(Decimal(minor).scaleb(-CURRENCY_DIGITS[currency]), "f")
