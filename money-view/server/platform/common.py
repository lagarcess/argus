"""Small shared boundary: ownership, dated evidence and exact money."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from sqlite3 import Connection
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
    data_generation: int = 0


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


def active_context(
    connection: Connection, *, user_id: str, household_id: str, session_id: str
) -> Context:
    """Read current membership and lifecycle truth in the caller's transaction."""
    row = connection.execute(
        """SELECT m.role,COALESCE(g.generation,0) AS generation
        FROM p_memberships m JOIN p_users u ON u.id=m.user_id
        LEFT JOIN p_household_generations g ON g.household_id=m.household_id
        LEFT JOIN p_guest_workspaces w ON w.user_id=u.id
        WHERE m.user_id=? AND m.household_id=? AND u.deleted_at IS NULL
        AND (w.user_id IS NULL OR w.claimed_at IS NOT NULL OR w.expires_at>?)""",
        (user_id, household_id, now().isoformat()),
    ).fetchone()
    if row is None:
        raise PlatformError("authentication_required", 401)
    return Context(user_id, household_id, row["role"], session_id, row["generation"])


def assert_active_context(
    connection: Connection,
    context: Context,
    *,
    minimum_role: Literal["viewer", "editor", "owner"] = "editor",
) -> None:
    """Fence private writes inside their existing BEGIN IMMEDIATE transaction.

    Captured authority must survive reset, deletion and membership changes. Session
    revocation is deliberately not checked: an accepted logout may finish work.
    """
    if not connection.in_transaction:
        raise RuntimeError("Private write guard requires an active write transaction")
    current = active_context(
        connection,
        user_id=context.user_id,
        household_id=context.household_id,
        session_id=context.session_id,
    )
    if current.role != context.role:
        raise PlatformError("household_access_changed", 409)
    if current.data_generation != context.data_generation:
        raise PlatformError("household_data_changed", 409)
    if minimum_role == "owner":
        require_owner(current)
    elif minimum_role == "editor":
        require_editor(current)


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
