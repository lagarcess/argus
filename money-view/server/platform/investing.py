"""Household-scoped alternative holdings and fictional investing simulation."""

from __future__ import annotations

import base64
import binascii
import calendar
import json
import sqlite3
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_CEILING, ROUND_DOWN, ROUND_FLOOR, ROUND_HALF_UP, Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Request, Response
from pydantic import Field, field_validator, model_validator

from ..store import Store
from .common import (
    CURRENCY_DIGITS,
    Context,
    Evidence,
    Model,
    PlatformError,
    PositiveAmount,
    active_context,
    assert_active_context,
    decimal_amount,
    get_context,
    get_store,
    identifier,
    minor_units,
    now,
    require_editor,
)
from .market_data import (
    FIXTURE_AS_OF,
    FixtureMarketDataAdapter,
    latest_prices,
    load_market_prices,
)
from .market_data import (
    initialize as initialize_market_data,
)
from .statement_parser import DEFAULT_LIMITS, parse_delimited

router = APIRouter(prefix="/api/platform")

Quantity = Annotated[
    Decimal,
    Field(gt=0, le=Decimal("1000000000000"), max_digits=20, decimal_places=8),
]
Symbol = Annotated[str, Field(pattern=r"^[A-Z0-9.-]{1,24}$")]

FIXTURE_RECORDED_AT = datetime(2026, 9, 20, 12, tzinfo=timezone.utc)
QUOTE_LIFETIME = timedelta(minutes=5)
MAX_RECURRING_BATCH = 100
RECURRING_RUN_LEASE = timedelta(seconds=30)
RECURRING_ANCHOR_MIGRATION_BATCH = 100


def _upper_symbol(value: str) -> str:
    return value.strip().upper()


class HoldingCreate(Model):
    symbol: Symbol
    name: str = Field(min_length=1, max_length=120)
    quantity: Quantity
    total_cost: PositiveAmount
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    as_of: date

    @field_validator("symbol", mode="before")
    @classmethod
    def normalize_symbol(cls, value: object) -> object:
        return _upper_symbol(value) if isinstance(value, str) else value


class HoldingUpdate(Model):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    quantity: Quantity | None = None
    total_cost: PositiveAmount | None = None
    as_of: date | None = None

    @model_validator(mode="after")
    def require_change(self) -> "HoldingUpdate":
        if not self.model_fields_set or all(
            getattr(self, field) is None for field in self.model_fields_set
        ):
            raise ValueError("at least one change is required")
        return self


class HoldingCsvRequest(Model):
    csv: str = Field(min_length=1, max_length=DEFAULT_LIMITS.max_bytes)


class IdempotencyRequest(Model):
    idempotency_key: str = Field(min_length=1, max_length=120)


class PriceLoadRequest(Model):
    outcome: Literal["success", "failure"]


class OrderPreviewRequest(Model):
    book_id: str = Field(min_length=1, max_length=120)
    side: Literal["buy", "sell"]
    symbol: Symbol | None = None
    quantity: Quantity | None = None
    bundle_id: str | None = Field(default=None, min_length=1, max_length=120)
    amount: PositiveAmount | None = None

    @field_validator("symbol", mode="before")
    @classmethod
    def normalize_symbol(cls, value: object) -> object:
        return _upper_symbol(value) if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_shape(self) -> "OrderPreviewRequest":
        is_symbol = self.symbol is not None and self.quantity is not None
        is_bundle = self.bundle_id is not None and self.amount is not None
        if is_symbol == is_bundle:
            raise ValueError("supply one symbol/quantity or bundle/amount")
        if is_symbol and (self.bundle_id is not None or self.amount is not None):
            raise ValueError("symbol orders cannot include bundle fields")
        if is_bundle and (self.symbol is not None or self.quantity is not None):
            raise ValueError("bundle orders cannot include symbol fields")
        if is_bundle and self.side != "buy":
            raise ValueError("bundles are buy-only")
        return self


class RecurringPlanCreate(Model):
    book_id: str = Field(min_length=1, max_length=120)
    cadence: Literal["weekly", "monthly"]
    next_run_on: date
    symbol: Symbol | None = None
    bundle_id: str | None = Field(default=None, min_length=1, max_length=120)
    amount: PositiveAmount

    @field_validator("symbol", mode="before")
    @classmethod
    def normalize_symbol(cls, value: object) -> object:
        return _upper_symbol(value) if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_target(self) -> "RecurringPlanCreate":
        if (self.symbol is None) == (self.bundle_id is None):
            raise ValueError("supply one symbol or bundle")
        return self


class RecurringPlanUpdate(Model):
    amount: PositiveAmount | None = None
    next_run_on: date | None = None
    active: bool | None = None

    @model_validator(mode="after")
    def require_change(self) -> "RecurringPlanUpdate":
        if not self.model_fields_set or all(
            getattr(self, field) is None for field in self.model_fields_set
        ):
            raise ValueError("at least one change is required")
        return self


class RecurringRunRequest(Model):
    run_on: date


INVESTING_SCHEMA = """
CREATE TABLE IF NOT EXISTS p_investment_fixture_manifest (
    module TEXT PRIMARY KEY,
    seeded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS p_investment_holdings (
    id TEXT PRIMARY KEY,
    household_id TEXT NOT NULL,
    created_by TEXT NOT NULL,
    symbol TEXT NOT NULL,
    name TEXT NOT NULL,
    quantity TEXT NOT NULL,
    total_cost_minor INTEGER NOT NULL CHECK(total_cost_minor > 0),
    currency TEXT NOT NULL,
    as_of TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT,
    source_json TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS p_investment_holdings_active_symbol
ON p_investment_holdings(household_id,symbol,currency)
WHERE deleted_at IS NULL;
CREATE TABLE IF NOT EXISTS p_investment_import_previews (
    id TEXT PRIMARY KEY,
    household_id TEXT NOT NULL,
    created_by TEXT NOT NULL,
    rows_json TEXT NOT NULL,
    errors_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    source_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS p_investment_import_receipts (
    id TEXT PRIMARY KEY,
    preview_id TEXT NOT NULL UNIQUE REFERENCES p_investment_import_previews(id),
    household_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    document_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(household_id,idempotency_key)
);
CREATE TABLE IF NOT EXISTS p_investment_books (
    id TEXT PRIMARY KEY,
    household_id TEXT NOT NULL,
    name TEXT NOT NULL,
    currency TEXT NOT NULL,
    initial_cash_minor INTEGER NOT NULL CHECK(initial_cash_minor >= 0),
    cash_minor INTEGER NOT NULL CHECK(cash_minor >= 0),
    created_at TEXT NOT NULL,
    source_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS p_investment_positions (
    book_id TEXT NOT NULL REFERENCES p_investment_books(id),
    symbol TEXT NOT NULL,
    currency TEXT NOT NULL,
    quantity TEXT NOT NULL,
    total_cost_minor INTEGER NOT NULL CHECK(total_cost_minor >= 0),
    updated_at TEXT NOT NULL,
    PRIMARY KEY(book_id,symbol)
);
CREATE TABLE IF NOT EXISTS p_investment_order_previews (
    id TEXT PRIMARY KEY,
    household_id TEXT NOT NULL,
    book_id TEXT NOT NULL REFERENCES p_investment_books(id),
    document_json TEXT NOT NULL,
    quote_keys_json TEXT NOT NULL,
    quoted_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS p_investment_order_receipts (
    id TEXT PRIMARY KEY,
    preview_id TEXT NOT NULL UNIQUE REFERENCES p_investment_order_previews(id),
    household_id TEXT NOT NULL,
    book_id TEXT NOT NULL REFERENCES p_investment_books(id),
    idempotency_key TEXT NOT NULL,
    document_json TEXT NOT NULL,
    confirmed_at TEXT NOT NULL,
    UNIQUE(household_id,idempotency_key)
);
CREATE TABLE IF NOT EXISTS p_investment_recurring_plans (
    id TEXT PRIMARY KEY,
    household_id TEXT NOT NULL,
    created_by TEXT NOT NULL,
    book_id TEXT NOT NULL REFERENCES p_investment_books(id),
    cadence TEXT NOT NULL CHECK(cadence IN ('weekly','monthly')),
    next_run_on TEXT NOT NULL,
    monthly_anchor_day INTEGER CHECK(monthly_anchor_day BETWEEN 1 AND 31),
    symbol TEXT,
    bundle_id TEXT,
    amount_minor INTEGER NOT NULL CHECK(amount_minor > 0),
    currency TEXT NOT NULL,
    active INTEGER NOT NULL CHECK(active IN (0,1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    source_json TEXT NOT NULL,
    CHECK((symbol IS NULL) <> (bundle_id IS NULL))
);
CREATE INDEX IF NOT EXISTS p_investment_recurring_due
ON p_investment_recurring_plans(active,next_run_on,id);
CREATE TABLE IF NOT EXISTS p_investment_recurring_runs (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL REFERENCES p_investment_recurring_plans(id),
    household_id TEXT NOT NULL,
    period_key TEXT NOT NULL,
    run_on TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('running','succeeded','failed')),
    receipt_id TEXT REFERENCES p_investment_order_receipts(id),
    error_code TEXT,
    source_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    completed_at TEXT,
    UNIQUE(plan_id,period_key)
);
CREATE INDEX IF NOT EXISTS p_investment_recurring_run_recovery
ON p_investment_recurring_runs(plan_id,status,created_at,id);
"""


BUNDLES: tuple[dict[str, object], ...] = (
    {
        "id": "bundle-steady-three",
        "name": "Synthetic steady three",
        "description": "A fictional learning mix of US shares, bonds, and international shares.",
        "currency": "USD",
        "legs": [
            {"symbol": "AAPL", "weight_pct": "40.0000"},
            {"symbol": "BND", "weight_pct": "40.0000"},
            {"symbol": "VXUS", "weight_pct": "20.0000"},
        ],
    },
    {
        "id": "bundle-global-two",
        "name": "Synthetic global two",
        "description": "A fictional learning mix of broad US and international shares.",
        "currency": "USD",
        "legs": [
            {"symbol": "SPY", "weight_pct": "50.0000"},
            {"symbol": "VXUS", "weight_pct": "50.0000"},
        ],
    },
)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _decimal_string(value: Decimal) -> str:
    normalized = format(value, "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return normalized or "0"


def _money_minor(value: Decimal, currency: str) -> int:
    digits = CURRENCY_DIGITS.get(currency)
    if digits is None:
        raise PlatformError("unsupported_currency")
    rounded = value.quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)
    return minor_units(rounded, currency)


def _settlement_minor(
    value: Decimal, currency: str, side: Literal["buy", "sell"]
) -> tuple[int, Decimal]:
    """Round against the simulator so splitting an order cannot create cash."""

    digits = CURRENCY_DIGITS.get(currency)
    if digits is None:
        raise PlatformError("unsupported_currency")
    if not value.is_finite() or value <= 0 or value > Decimal("1e12"):
        raise PlatformError("invalid_money_precision")
    if value < Decimal(1).scaleb(-digits):
        raise PlatformError("order_amount_too_small")
    rounding = ROUND_CEILING if side == "buy" else ROUND_FLOOR
    settled_minor = int(
        (value * (10**digits)).to_integral_value(rounding=rounding)
    )
    if settled_minor <= 0:
        raise PlatformError("order_amount_too_small")
    settled = Decimal(settled_minor).scaleb(-digits)
    rounding_cost = settled - value if side == "buy" else value - settled
    return settled_minor, rounding_cost


def _percent(numerator: Decimal, denominator: Decimal) -> str | None:
    if denominator == 0:
        return None
    return format(
        (numerator * Decimal(100) / denominator).quantize(Decimal("0.0001")),
        "f",
    )


def _fixture_evidence(title: str, *, inputs: list[str] | None = None) -> Evidence:
    return Evidence(
        id=f"investing-fixture-{title.lower().replace(' ', '-')}",
        kind="synthetic",
        title=title,
        as_of=FIXTURE_AS_OF,
        recorded_at=FIXTURE_RECORDED_AT,
        method="Local deterministic Clara fixture. Not live market data or advice.",
        inputs=inputs or [],
    )


def _user_evidence(title: str, as_of: date, inputs: list[str]) -> Evidence:
    return Evidence(
        id=identifier("investment-evidence"),
        kind="user",
        title=title,
        as_of=as_of,
        recorded_at=now(),
        method="Recorded from a household editor's explicit input.",
        inputs=inputs,
    )


def _calculated_evidence(
    title: str, as_of: date, inputs: list[str], *, method: str
) -> Evidence:
    return Evidence(
        id=identifier("investment-calculation"),
        kind="calculated",
        title=title,
        as_of=as_of,
        recorded_at=now(),
        method=method,
        inputs=inputs,
    )


def _migrate_recurring_anchor(connection: sqlite3.Connection) -> None:
    columns = {
        row["name"]
        for row in connection.execute(
            "PRAGMA table_info('p_investment_recurring_plans')"
        )
    }
    if "monthly_anchor_day" not in columns:
        connection.execute(
            """
            ALTER TABLE p_investment_recurring_plans
            ADD COLUMN monthly_anchor_day INTEGER
            CHECK(monthly_anchor_day BETWEEN 1 AND 31)
            """
        )
    rows = connection.execute(
        """
        SELECT id,next_run_on
        FROM p_investment_recurring_plans
        WHERE cadence='monthly' AND monthly_anchor_day IS NULL
        ORDER BY id LIMIT ?
        """,
        (RECURRING_ANCHOR_MIGRATION_BATCH,),
    ).fetchall()
    for row in rows:
        anchor_day = date.fromisoformat(row["next_run_on"]).day
        connection.execute(
            """
            UPDATE p_investment_recurring_plans SET monthly_anchor_day=?
            WHERE id=? AND monthly_anchor_day IS NULL
            """,
            (anchor_day, row["id"]),
        )


def initialize(store: Store) -> None:
    """Create tables and seed once. A cleared household is never reseeded."""

    initialize_market_data(store)
    with store.connection(write=True) as connection:
        connection.executescript(INVESTING_SCHEMA)
    with store.connection(write=True) as connection:
        _migrate_recurring_anchor(connection)
        seeded = connection.execute(
            "SELECT 1 FROM p_investment_fixture_manifest WHERE module='investing'"
        ).fetchone()
        if seeded is not None:
            needs_prices = False
        else:
            timestamp = _iso(FIXTURE_RECORDED_AT)
            holding_source = _fixture_evidence("Synthetic alternative holding")
            book_source = _fixture_evidence("Fictional simulation cash")
            connection.execute(
                """
                INSERT INTO p_investment_holdings(
                    id,household_id,created_by,symbol,name,quantity,total_cost_minor,
                    currency,as_of,created_at,updated_at,source_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    "holding-demo-gold",
                    "household-demo",
                    "user-demo",
                    "ALT-GOLD",
                    "Gold certificate",
                    "2",
                    360000,
                    "USD",
                    FIXTURE_AS_OF.isoformat(),
                    timestamp,
                    timestamp,
                    holding_source.model_dump_json(),
                ),
            )
            connection.execute(
                """
                INSERT INTO p_investment_holdings(
                    id,household_id,created_by,symbol,name,quantity,total_cost_minor,
                    currency,as_of,created_at,updated_at,source_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    "holding-other-vwce",
                    "household-other",
                    "user-other",
                    "VWCE",
                    "Manual fund certificate",
                    "3",
                    36000,
                    "EUR",
                    FIXTURE_AS_OF.isoformat(),
                    timestamp,
                    timestamp,
                    holding_source.model_dump_json(),
                ),
            )
            for values in (
                (
                    "book-demo-usd",
                    "household-demo",
                    "USD learning book",
                    "USD",
                    1_000_000,
                ),
                (
                    "book-other-usd",
                    "household-other",
                    "Other household learning book",
                    "USD",
                    500_000,
                ),
            ):
                connection.execute(
                    """
                    INSERT INTO p_investment_books(
                        id,household_id,name,currency,initial_cash_minor,cash_minor,
                        created_at,source_json
                    ) VALUES(?,?,?,?,?,?,?,?)
                    """,
                    (*values, values[4], timestamp, book_source.model_dump_json()),
                )
            connection.execute(
                "INSERT INTO p_investment_fixture_manifest(module,seeded_at) VALUES('investing',?)",
                (timestamp,),
            )
            needs_prices = (
                connection.execute("SELECT 1 FROM p_market_price_sets LIMIT 1").fetchone()
                is None
            )
    if needs_prices:
        load_market_prices(store, FixtureMarketDataAdapter())


def _holding_record(row: sqlite3.Row) -> dict[str, object]:
    return {
        "id": row["id"],
        "symbol": row["symbol"],
        "name": row["name"],
        "quantity": row["quantity"],
        "currency": row["currency"],
        "total_cost": decimal_amount(row["total_cost_minor"], row["currency"]),
        "as_of": row["as_of"],
        "source": Evidence.model_validate_json(row["source_json"]).model_dump(
            mode="json"
        ),
    }


def list_holdings(store: Store, context: Context) -> dict[str, object]:
    with store.connection() as connection:
        rows = connection.execute(
            """
            SELECT * FROM p_investment_holdings
            WHERE household_id=? AND deleted_at IS NULL ORDER BY name,id
            """,
            (context.household_id,),
        ).fetchall()
    return {"items": [_holding_record(row) for row in rows]}


def create_holding(
    store: Store, context: Context, payload: HoldingCreate
) -> dict[str, object]:
    require_editor(context)
    holding_id = identifier("holding")
    timestamp = now()
    source = _user_evidence(
        "Manual alternative holding",
        payload.as_of,
        [holding_id, context.user_id],
    )
    try:
        with store.connection(write=True) as connection:
            assert_active_context(connection, context)
            connection.execute(
                """
                INSERT INTO p_investment_holdings(
                    id,household_id,created_by,symbol,name,quantity,total_cost_minor,
                    currency,as_of,created_at,updated_at,source_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    holding_id,
                    context.household_id,
                    context.user_id,
                    payload.symbol,
                    payload.name.strip(),
                    _decimal_string(payload.quantity),
                    minor_units(payload.total_cost, payload.currency),
                    payload.currency,
                    payload.as_of.isoformat(),
                    _iso(timestamp),
                    _iso(timestamp),
                    source.model_dump_json(),
                ),
            )
    except sqlite3.IntegrityError as exc:
        raise PlatformError("holding_already_exists", 409) from exc
    return get_holding(store, context, holding_id)


def get_holding(store: Store, context: Context, holding_id: str) -> dict[str, object]:
    with store.connection() as connection:
        row = connection.execute(
            """
            SELECT * FROM p_investment_holdings
            WHERE id=? AND household_id=? AND deleted_at IS NULL
            """,
            (holding_id, context.household_id),
        ).fetchone()
    if row is None:
        raise PlatformError("holding_not_found", 404)
    return _holding_record(row)


def update_holding(
    store: Store, context: Context, holding_id: str, payload: HoldingUpdate
) -> dict[str, object]:
    require_editor(context)
    with store.connection(write=True) as connection:
        assert_active_context(connection, context)
        row = connection.execute(
            """
            SELECT * FROM p_investment_holdings
            WHERE id=? AND household_id=? AND deleted_at IS NULL
            """,
            (holding_id, context.household_id),
        ).fetchone()
        if row is None:
            raise PlatformError("holding_not_found", 404)
        name = payload.name.strip() if payload.name is not None else row["name"]
        quantity = (
            _decimal_string(payload.quantity)
            if payload.quantity is not None
            else row["quantity"]
        )
        total_cost_minor = (
            minor_units(payload.total_cost, row["currency"])
            if payload.total_cost is not None
            else row["total_cost_minor"]
        )
        as_of = payload.as_of.isoformat() if payload.as_of else row["as_of"]
        source = _user_evidence(
            "Updated manual alternative holding",
            date.fromisoformat(as_of),
            [holding_id, context.user_id],
        )
        connection.execute(
            """
            UPDATE p_investment_holdings
            SET name=?,quantity=?,total_cost_minor=?,as_of=?,updated_at=?,source_json=?
            WHERE id=? AND household_id=?
            """,
            (
                name,
                quantity,
                total_cost_minor,
                as_of,
                _iso(now()),
                source.model_dump_json(),
                holding_id,
                context.household_id,
            ),
        )
    return get_holding(store, context, holding_id)


def delete_holding(store: Store, context: Context, holding_id: str) -> dict[str, object]:
    require_editor(context)
    with store.connection(write=True) as connection:
        assert_active_context(connection, context)
        changed = connection.execute(
            """
            UPDATE p_investment_holdings SET deleted_at=?,updated_at=?
            WHERE id=? AND household_id=? AND deleted_at IS NULL
            """,
            (_iso(now()), _iso(now()), holding_id, context.household_id),
        ).rowcount
    if changed != 1:
        raise PlatformError("holding_not_found", 404)
    return {"id": holding_id, "deleted": True}


def _latest_price_rows(
    connection: sqlite3.Connection,
) -> dict[tuple[str, str], sqlite3.Row]:
    rows = connection.execute(
        """
        SELECT prices.symbol,prices.currency,prices.price_minor,prices.as_of,
               prices.source_json,prices.set_id,sets.loaded_at
        FROM p_market_prices prices
        JOIN p_market_price_sets sets ON sets.id=prices.set_id
        WHERE NOT EXISTS (
            SELECT 1 FROM p_market_prices newer
            JOIN p_market_price_sets newer_sets ON newer_sets.id=newer.set_id
            WHERE newer.symbol=prices.symbol AND newer.currency=prices.currency
              AND (newer.as_of > prices.as_of OR
                   (newer.as_of=prices.as_of AND newer_sets.loaded_at > sets.loaded_at))
        )
        """
    ).fetchall()
    return {(row["symbol"], row["currency"]): row for row in rows}


def _price_record(row: sqlite3.Row) -> dict[str, object]:
    return {
        "symbol": row["symbol"],
        "currency": row["currency"],
        "price": decimal_amount(row["price_minor"], row["currency"]),
        "as_of": row["as_of"],
        "source": Evidence.model_validate_json(row["source_json"]).model_dump(
            mode="json"
        ),
    }


def net_worth_additions(
    connection: sqlite3.Connection, context: Context
) -> list[dict[str, object]]:
    """Return priced alternative assets only, for ledger overview composition."""

    try:
        price_rows = _latest_price_rows(connection)
        holdings = connection.execute(
            """
            SELECT * FROM p_investment_holdings
            WHERE household_id=? AND deleted_at IS NULL ORDER BY id
            """,
            (context.household_id,),
        ).fetchall()
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc).lower():
            return []
        raise
    totals: dict[str, int] = {}
    inputs: dict[str, list[str]] = {}
    as_of_by_currency: dict[str, date] = {}
    for holding in holdings:
        key = (holding["symbol"], holding["currency"])
        price = price_rows.get(key)
        if price is None:
            continue
        quantity = Decimal(holding["quantity"])
        value_minor = _money_minor(
            quantity * Decimal(decimal_amount(price["price_minor"], price["currency"])),
            holding["currency"],
        )
        totals[holding["currency"]] = totals.get(holding["currency"], 0) + value_minor
        inputs.setdefault(holding["currency"], []).extend(
            [holding["id"], price["set_id"]]
        )
        observed = date.fromisoformat(price["as_of"])
        as_of_by_currency[holding["currency"]] = max(
            as_of_by_currency.get(holding["currency"], observed), observed
        )
    return [
        {
            "currency": currency,
            "amount": decimal_amount(amount, currency),
            "source": _calculated_evidence(
                "Priced alternative holdings added to net worth",
                as_of_by_currency[currency],
                inputs[currency],
                method=(
                    "Sum of active manual alternative holding quantity times the "
                    "latest dated price. Linked accounts and simulated books excluded."
                ),
            ).model_dump(mode="json"),
        }
        for currency, amount in sorted(totals.items())
    ]


def _linked_investment_accounts(
    store: Store, context: Context
) -> list[dict[str, object]]:
    from .ledger import account_balances

    return [
        account
        for account in account_balances(store, context)
        if account.get("kind") == "investment"
    ]


def _alternative_valuations(
    connection: sqlite3.Connection, context: Context
) -> tuple[list[dict[str, object]], dict[str, dict[str, object]]]:
    price_rows = _latest_price_rows(connection)
    holdings = connection.execute(
        """
        SELECT * FROM p_investment_holdings
        WHERE household_id=? AND deleted_at IS NULL ORDER BY name,id
        """,
        (context.household_id,),
    ).fetchall()
    raw: list[tuple[sqlite3.Row, sqlite3.Row | None, int | None]] = []
    priced_totals: dict[str, int] = {}
    for holding in holdings:
        price = price_rows.get((holding["symbol"], holding["currency"]))
        value_minor = None
        if price is not None:
            value_minor = _money_minor(
                Decimal(holding["quantity"])
                * Decimal(decimal_amount(price["price_minor"], price["currency"])),
                holding["currency"],
            )
            priced_totals[holding["currency"]] = (
                priced_totals.get(holding["currency"], 0) + value_minor
            )
        raw.append((holding, price, value_minor))
    valued: list[dict[str, object]] = []
    stats: dict[str, dict[str, object]] = {}
    for holding, price, value_minor in raw:
        currency = holding["currency"]
        currency_stats = stats.setdefault(
            currency,
            {"priced": 0, "cost": 0, "unpriced": [], "inputs": [], "as_of": None},
        )
        record = _holding_record(holding)
        if price is None or value_minor is None:
            record.update(
                {
                    "price": None,
                    "market_value": None,
                    "gain_loss": None,
                    "gain_loss_pct": None,
                    "allocation_pct": None,
                }
            )
            currency_stats["unpriced"].append(holding["id"])
        else:
            gain_minor = value_minor - holding["total_cost_minor"]
            record.update(
                {
                    "price": _price_record(price),
                    "market_value": decimal_amount(value_minor, currency),
                    "gain_loss": decimal_amount(gain_minor, currency),
                    "gain_loss_pct": _percent(
                        Decimal(gain_minor), Decimal(holding["total_cost_minor"])
                    ),
                    "allocation_pct": _percent(
                        Decimal(value_minor), Decimal(priced_totals[currency])
                    ),
                }
            )
            currency_stats["priced"] = int(currency_stats["priced"]) + value_minor
            currency_stats["cost"] = (
                int(currency_stats["cost"]) + holding["total_cost_minor"]
            )
            currency_stats["inputs"].extend([holding["id"], price["set_id"]])
            observed = date.fromisoformat(price["as_of"])
            prior = currency_stats["as_of"]
            currency_stats["as_of"] = max(prior, observed) if prior else observed
        valued.append(record)
    return valued, stats


def _benchmarks() -> list[dict[str, object]]:
    source = _fixture_evidence(
        "Synthetic benchmark history",
        inputs=["benchmark-spy", "590.00", "650.00"],
    ).model_dump(mode="json")
    return [
        {
            "id": "benchmark-spy",
            "symbol": "SPY",
            "name": "Synthetic broad US market example",
            "currency": "USD",
            "start_on": "2025-09-20",
            "end_on": "2026-09-20",
            "start_price": "590.00",
            "end_price": "650.00",
            "return_pct": _percent(Decimal("60"), Decimal("590")),
            "source": source,
        }
    ]


def portfolio_summary(store: Store, context: Context) -> dict[str, object]:
    with store.read_snapshot():
        return _portfolio_summary(store, context)


def _portfolio_summary(store: Store, context: Context) -> dict[str, object]:
    linked_accounts = _linked_investment_accounts(store, context)
    with store.connection() as connection:
        alternative_holdings, stats = _alternative_valuations(connection, context)
        additions = net_worth_additions(connection, context)
    linked_totals: dict[str, Decimal] = {}
    linked_dates: dict[str, list[date]] = {}
    for account in linked_accounts:
        currency = str(account["currency"])
        linked_totals[currency] = linked_totals.get(currency, Decimal(0)) + Decimal(
            str(account["balance"])
        )
        source = account.get("source")
        if source and source.get("as_of"):
            linked_dates.setdefault(currency, []).append(
                date.fromisoformat(str(source["as_of"]))
            )
    totals: list[dict[str, object]] = []
    observed_dates = [
        observed
        for currency_dates in linked_dates.values()
        for observed in currency_dates
    ]
    currencies = sorted(set(linked_totals) | set(stats))
    for currency in currencies:
        currency_stats = stats.get(
            currency,
            {"priced": 0, "cost": 0, "unpriced": [], "inputs": [], "as_of": None},
        )
        linked_minor = _money_minor(linked_totals.get(currency, Decimal(0)), currency)
        priced = int(currency_stats["priced"])
        cost = int(currency_stats["cost"])
        gain = priced - cost
        currency_dates = list(linked_dates.get(currency, []))
        if currency_stats["as_of"]:
            currency_dates.append(currency_stats["as_of"])
        currency_as_of = max(currency_dates, default=FIXTURE_AS_OF)
        evidence = _calculated_evidence(
            "Portfolio summary",
            currency_as_of,
            [str(value) for value in currency_stats["inputs"]]
            + [
                str(account["id"])
                for account in linked_accounts
                if account["currency"] == currency
            ],
            method=(
                "Linked ledger investment balances plus separately owned priced "
                "alternative holdings. Simulation values excluded."
            ),
        )
        totals.append(
            {
                "currency": currency,
                "linked_accounts": decimal_amount(linked_minor, currency),
                "priced_alternatives": decimal_amount(priced, currency),
                "portfolio_value": decimal_amount(linked_minor + priced, currency),
                "alternative_cost_basis": decimal_amount(cost, currency),
                "alternative_gain_loss": decimal_amount(gain, currency),
                "alternative_gain_loss_pct": _percent(Decimal(gain), Decimal(cost)),
                "is_partial": bool(currency_stats["unpriced"]),
                "unpriced_holding_ids": list(currency_stats["unpriced"]),
                "source": evidence.model_dump(mode="json"),
            }
        )
        if currency_stats["as_of"]:
            observed_dates.append(currency_stats["as_of"])
    portfolio_as_of = max(observed_dates, default=FIXTURE_AS_OF)
    source = _calculated_evidence(
        "Investing portfolio read model",
        portfolio_as_of,
        [str(item["id"]) for item in linked_accounts]
        + [str(item["id"]) for item in alternative_holdings],
        method="Household-scoped composition of ledger accounts and investing records.",
    )
    return {
        "as_of": portfolio_as_of.isoformat(),
        "linked_accounts": linked_accounts,
        "alternative_holdings": alternative_holdings,
        "totals": totals,
        "net_worth_additions": additions,
        "benchmarks": _benchmarks(),
        "simulation": {
            "books": list_books(store, context)["items"],
            "positions": list_positions(store, context),
            "recent_orders": list_orders(store, context, limit=10)["items"],
        },
        "source": source.model_dump(mode="json"),
    }


def preview_holding_csv(
    store: Store, context: Context, content: str
) -> dict[str, object]:
    require_editor(context)
    table = parse_delimited(content)
    if set(table.headers) != set(HoldingCreate.model_fields):
        raise PlatformError("invalid_csv_header")
    with store.connection() as connection:
        existing = {
            (row["symbol"], row["currency"])
            for row in connection.execute(
                """
                SELECT symbol,currency FROM p_investment_holdings
                WHERE household_id=? AND deleted_at IS NULL
                """,
                (context.household_id,),
            ).fetchall()
        }
    rows: list[dict[str, object]] = []
    errors: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for row in table.rows:
        if not row.cells:
            continue
        try:
            raw = dict(zip(table.headers, row.cells, strict=True))
            parsed = HoldingCreate.model_validate(raw)
            key = (parsed.symbol, parsed.currency)
            duplicate = key in existing or key in seen
            seen.add(key)
            rows.append(
                {
                    "line": row.line,
                    **parsed.model_dump(mode="json"),
                    "duplicate": duplicate,
                }
            )
        except (ValueError, TypeError):
            errors.append({"line": row.line, "code": "invalid_holding_row"})
    preview_id = identifier("holding-import")
    preview_as_of = max(
        (date.fromisoformat(str(row["as_of"])) for row in rows),
        default=FIXTURE_AS_OF,
    )
    source = _user_evidence(
        "Alternative holding CSV preview",
        preview_as_of,
        [preview_id, context.user_id],
    )
    with store.connection(write=True) as connection:
        assert_active_context(connection, context)
        connection.execute(
            """
            INSERT INTO p_investment_import_previews(
                id,household_id,created_by,rows_json,errors_json,created_at,source_json
            ) VALUES(?,?,?,?,?,?,?)
            """,
            (
                preview_id,
                context.household_id,
                context.user_id,
                json.dumps(rows),
                json.dumps(errors),
                _iso(now()),
                source.model_dump_json(),
            ),
        )
    duplicate_count = sum(bool(row["duplicate"]) for row in rows)
    valid_count = len(rows) - duplicate_count
    return {
        "id": preview_id,
        "rows": rows,
        "errors": errors,
        "valid_count": valid_count,
        "duplicate_count": duplicate_count,
        "can_commit": not errors and valid_count > 0,
        "source": source.model_dump(mode="json"),
    }


def commit_holding_import(
    store: Store, context: Context, preview_id: str, idempotency_key: str
) -> dict[str, object]:
    require_editor(context)
    with store.connection(write=True) as connection:
        assert_active_context(connection, context)
        replay = connection.execute(
            """
            SELECT preview_id,document_json FROM p_investment_import_receipts
            WHERE household_id=? AND idempotency_key=?
            """,
            (context.household_id, idempotency_key),
        ).fetchone()
        if replay is not None:
            if replay["preview_id"] != preview_id:
                raise PlatformError("idempotency_conflict", 409)
            return json.loads(replay["document_json"])
        preview = connection.execute(
            """
            SELECT * FROM p_investment_import_previews
            WHERE id=? AND household_id=?
            """,
            (preview_id, context.household_id),
        ).fetchone()
        if preview is None:
            raise PlatformError("holding_import_not_found", 404)
        errors = json.loads(preview["errors_json"])
        if errors:
            raise PlatformError("holding_import_has_errors")
        rows = json.loads(preview["rows_json"])
        holding_ids: list[str] = []
        duplicates = 0
        timestamp = now()
        for row in rows:
            existing = connection.execute(
                """
                SELECT 1 FROM p_investment_holdings
                WHERE household_id=? AND symbol=? AND currency=? AND deleted_at IS NULL
                """,
                (context.household_id, row["symbol"], row["currency"]),
            ).fetchone()
            if row["duplicate"] or existing is not None:
                duplicates += 1
                continue
            holding_id = identifier("holding")
            source = _user_evidence(
                "Imported alternative holding",
                date.fromisoformat(row["as_of"]),
                [preview_id, holding_id],
            )
            connection.execute(
                """
                INSERT INTO p_investment_holdings(
                    id,household_id,created_by,symbol,name,quantity,total_cost_minor,
                    currency,as_of,created_at,updated_at,source_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    holding_id,
                    context.household_id,
                    context.user_id,
                    row["symbol"],
                    row["name"],
                    row["quantity"],
                    minor_units(Decimal(row["total_cost"]), row["currency"]),
                    row["currency"],
                    row["as_of"],
                    _iso(timestamp),
                    _iso(timestamp),
                    source.model_dump_json(),
                ),
            )
            holding_ids.append(holding_id)
        if not holding_ids:
            raise PlatformError("holding_import_has_no_new_rows")
        receipt_id = identifier("holding-import-receipt")
        source = _calculated_evidence(
            "Alternative holding import receipt",
            max(
                date.fromisoformat(str(row["as_of"]))
                for row in rows
                if not row["duplicate"]
            ),
            [preview_id, *holding_ids],
            method="Atomic import after duplicate recheck.",
        )
        document = {
            "id": receipt_id,
            "imported": len(holding_ids),
            "duplicates": duplicates,
            "holding_ids": holding_ids,
            "source": source.model_dump(mode="json"),
        }
        connection.execute(
            """
            INSERT INTO p_investment_import_receipts(
                id,preview_id,household_id,idempotency_key,document_json,created_at
            ) VALUES(?,?,?,?,?,?)
            """,
            (
                receipt_id,
                preview_id,
                context.household_id,
                idempotency_key,
                json.dumps(document),
                _iso(timestamp),
            ),
        )
        return document


def _book_record(row: sqlite3.Row) -> dict[str, object]:
    return {
        "id": row["id"],
        "name": row["name"],
        "currency": row["currency"],
        "cash": decimal_amount(row["cash_minor"], row["currency"]),
        "initial_cash": decimal_amount(row["initial_cash_minor"], row["currency"]),
        "source": Evidence.model_validate_json(row["source_json"]).model_dump(
            mode="json"
        ),
    }


def list_books(store: Store, context: Context) -> dict[str, object]:
    with store.connection() as connection:
        rows = connection.execute(
            "SELECT * FROM p_investment_books WHERE household_id=? ORDER BY id",
            (context.household_id,),
        ).fetchall()
    return {"items": [_book_record(row) for row in rows]}


def _bundle(bundle_id: str) -> dict[str, object]:
    bundle = next((item for item in BUNDLES if item["id"] == bundle_id), None)
    if bundle is None:
        raise PlatformError("bundle_not_found", 404)
    return bundle


def list_bundles() -> dict[str, object]:
    source = _fixture_evidence("Synthetic learning bundles").model_dump(mode="json")
    return {"items": [{**bundle, "source": source} for bundle in BUNDLES]}


def _build_order_legs(
    request: OrderPreviewRequest,
    currency: str,
    prices: dict[tuple[str, str], dict[str, object]],
) -> tuple[str, list[dict[str, object]], int, Decimal]:
    if request.symbol is not None and request.quantity is not None:
        price = prices.get((request.symbol, currency))
        if price is None:
            raise PlatformError("price_unavailable")
        price_amount = Decimal(decimal_amount(int(price["price_minor"]), currency))
        gross_minor, rounding_cost = _settlement_minor(
            request.quantity * price_amount, currency, request.side
        )
        leg = {
            "symbol": request.symbol,
            "quantity": _decimal_string(request.quantity),
            "price": decimal_amount(int(price["price_minor"]), currency),
            "gross": decimal_amount(gross_minor, currency),
            "price_as_of": price["as_of"],
            "price_source": price["source"],
        }
        return "symbol", [leg], gross_minor, rounding_cost
    assert request.bundle_id is not None and request.amount is not None
    bundle = _bundle(request.bundle_id)
    if bundle["currency"] != currency:
        raise PlatformError("currency_mismatch")
    target_minor = minor_units(request.amount, currency)
    legs: list[dict[str, object]] = []
    gross_minor = 0
    rounding_cost = Decimal(0)
    bundle_legs = list(bundle["legs"])
    for index, bundle_leg in enumerate(bundle_legs):
        price = prices.get((str(bundle_leg["symbol"]), currency))
        if price is None:
            raise PlatformError("price_unavailable")
        if index == len(bundle_legs) - 1:
            allocation_minor = target_minor - gross_minor
        else:
            allocation_minor = int(
                Decimal(target_minor)
                * Decimal(str(bundle_leg["weight_pct"]))
                / Decimal(100)
            )
        price_amount = Decimal(decimal_amount(int(price["price_minor"]), currency))
        allocation_amount = Decimal(decimal_amount(allocation_minor, currency))
        quantity = (allocation_amount / price_amount).quantize(
            Decimal("0.00000001"), rounding=ROUND_DOWN
        )
        if quantity <= 0:
            raise PlatformError("order_amount_too_small")
        leg_gross, leg_rounding_cost = _settlement_minor(
            quantity * price_amount, currency, request.side
        )
        gross_minor += leg_gross
        rounding_cost += leg_rounding_cost
        legs.append(
            {
                "symbol": bundle_leg["symbol"],
                "quantity": _decimal_string(quantity),
                "price": decimal_amount(int(price["price_minor"]), currency),
                "gross": decimal_amount(leg_gross, currency),
                "price_as_of": price["as_of"],
                "price_source": price["source"],
            }
        )
    return "bundle", legs, gross_minor, rounding_cost


def preview_order(
    store: Store, context: Context, payload: OrderPreviewRequest
) -> dict[str, object]:
    require_editor(context)
    with store.connection() as connection:
        book = connection.execute(
            "SELECT * FROM p_investment_books WHERE id=? AND household_id=?",
            (payload.book_id, context.household_id),
        ).fetchone()
    if book is None:
        raise PlatformError("simulation_book_not_found", 404)
    prices = latest_prices(store, currency=book["currency"])
    kind, legs, gross_minor, rounding_cost = _build_order_legs(
        payload, book["currency"], prices
    )
    quoted_at = now()
    expires_at = quoted_at + QUOTE_LIFETIME
    preview_id = identifier("order-preview")
    source = _calculated_evidence(
        "Fictional order preview",
        max(date.fromisoformat(str(leg["price_as_of"])) for leg in legs),
        [str(prices[(str(leg["symbol"]), book["currency"])]["set_id"]) for leg in legs],
        method=(
            "Price snapshot multiplied by requested fictional quantity; buys "
            "settle up and sells settle down to the currency minor unit."
        ),
    )
    document = {
        "id": preview_id,
        "book_id": book["id"],
        "side": payload.side,
        "kind": kind,
        "symbol": payload.symbol,
        "bundle_id": payload.bundle_id,
        "currency": book["currency"],
        "legs": legs,
        "gross": decimal_amount(gross_minor, book["currency"]),
        "fee": decimal_amount(0, book["currency"]),
        "rounding_rule": "buy_ceiling_sell_floor",
        "rounding_cost": _decimal_string(rounding_cost),
        "cash_effect": decimal_amount(
            -gross_minor if payload.side == "buy" else gross_minor,
            book["currency"],
        ),
        "quoted_at": _iso(quoted_at),
        "expires_at": _iso(expires_at),
        "source": source.model_dump(mode="json"),
    }
    quote_keys = [
        {
            "symbol": leg["symbol"],
            "currency": book["currency"],
            "set_id": prices[(str(leg["symbol"]), book["currency"])]["set_id"],
        }
        for leg in legs
    ]
    with store.connection(write=True) as connection:
        assert_active_context(connection, context)
        connection.execute(
            """
            INSERT INTO p_investment_order_previews(
                id,household_id,book_id,document_json,quote_keys_json,quoted_at,expires_at
            ) VALUES(?,?,?,?,?,?,?)
            """,
            (
                preview_id,
                context.household_id,
                book["id"],
                json.dumps(document),
                json.dumps(quote_keys),
                _iso(quoted_at),
                _iso(expires_at),
            ),
        )
    return document


def _latest_price_keys(connection: sqlite3.Connection) -> dict[tuple[str, str], str]:
    return {key: row["set_id"] for key, row in _latest_price_rows(connection).items()}


def confirm_order(
    store: Store,
    context: Context,
    preview_id: str,
    idempotency_key: str,
    *,
    recurring_run_id: str | None = None,
) -> dict[str, object]:
    require_editor(context)
    with store.connection(write=True) as connection:
        assert_active_context(connection, context)
        replay = connection.execute(
            """
            SELECT preview_id,document_json FROM p_investment_order_receipts
            WHERE household_id=? AND idempotency_key=?
            """,
            (context.household_id, idempotency_key),
        ).fetchone()
        if replay is not None:
            if replay["preview_id"] != preview_id:
                raise PlatformError("idempotency_conflict", 409)
            return json.loads(replay["document_json"])
        prior = connection.execute(
            """
            SELECT document_json FROM p_investment_order_receipts
            WHERE preview_id=? AND household_id=?
            """,
            (preview_id, context.household_id),
        ).fetchone()
        if prior is not None:
            return json.loads(prior["document_json"])
        preview = connection.execute(
            """
            SELECT * FROM p_investment_order_previews
            WHERE id=? AND household_id=?
            """,
            (preview_id, context.household_id),
        ).fetchone()
        if preview is None:
            raise PlatformError("order_preview_not_found", 404)
        if recurring_run_id is not None:
            authority = connection.execute(
                """
                SELECT runs.status,runs.period_key,runs.plan_id,plans.book_id,
                       plans.active
                FROM p_investment_recurring_runs runs
                JOIN p_investment_recurring_plans plans ON plans.id=runs.plan_id
                WHERE runs.id=? AND runs.household_id=?
                """,
                (recurring_run_id, context.household_id),
            ).fetchone()
            if (
                authority is None
                or authority["status"] != "running"
                or not authority["active"]
                or authority["book_id"] != preview["book_id"]
                or idempotency_key
                != f"recurring:{authority['plan_id']}:{authority['period_key']}"
            ):
                raise PlatformError("recurring_settlement_not_authorized", 409)
        if datetime.fromisoformat(preview["expires_at"]) < now():
            raise PlatformError("stale_quote", 409)
        latest_keys = _latest_price_keys(connection)
        quote_keys = json.loads(preview["quote_keys_json"])
        if any(
            latest_keys.get((item["symbol"], item["currency"])) != item["set_id"]
            for item in quote_keys
        ):
            raise PlatformError("stale_quote", 409)
        document = json.loads(preview["document_json"])
        book = connection.execute(
            "SELECT * FROM p_investment_books WHERE id=? AND household_id=?",
            (preview["book_id"], context.household_id),
        ).fetchone()
        if book is None:
            raise PlatformError("simulation_book_not_found", 404)
        gross_minor = minor_units(Decimal(document["gross"]), book["currency"])
        cash_before = book["cash_minor"]
        if document["side"] == "buy" and cash_before < gross_minor:
            raise PlatformError("insufficient_simulated_cash")
        for leg in document["legs"]:
            position = connection.execute(
                "SELECT * FROM p_investment_positions WHERE book_id=? AND symbol=?",
                (book["id"], leg["symbol"]),
            ).fetchone()
            before_quantity = Decimal(position["quantity"]) if position else Decimal(0)
            quantity = Decimal(leg["quantity"])
            if document["side"] == "sell" and before_quantity < quantity:
                raise PlatformError("insufficient_simulated_quantity")
        timestamp = now()
        for leg in document["legs"]:
            position = connection.execute(
                "SELECT * FROM p_investment_positions WHERE book_id=? AND symbol=?",
                (book["id"], leg["symbol"]),
            ).fetchone()
            before_quantity = Decimal(position["quantity"]) if position else Decimal(0)
            before_cost = position["total_cost_minor"] if position else 0
            quantity = Decimal(leg["quantity"])
            leg_gross = minor_units(Decimal(leg["gross"]), book["currency"])
            if document["side"] == "buy":
                after_quantity = before_quantity + quantity
                after_cost = before_cost + leg_gross
            else:
                after_quantity = before_quantity - quantity
                removed_cost = (
                    int(
                        (Decimal(before_cost) * quantity / before_quantity).quantize(
                            Decimal("1"), rounding=ROUND_HALF_UP
                        )
                    )
                    if before_quantity
                    else 0
                )
                after_cost = max(0, before_cost - removed_cost)
            if after_quantity == 0:
                connection.execute(
                    "DELETE FROM p_investment_positions WHERE book_id=? AND symbol=?",
                    (book["id"], leg["symbol"]),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO p_investment_positions(
                        book_id,symbol,currency,quantity,total_cost_minor,updated_at
                    ) VALUES(?,?,?,?,?,?)
                    ON CONFLICT(book_id,symbol) DO UPDATE SET
                        quantity=excluded.quantity,
                        total_cost_minor=excluded.total_cost_minor,
                        updated_at=excluded.updated_at
                    """,
                    (
                        book["id"],
                        leg["symbol"],
                        book["currency"],
                        _decimal_string(after_quantity),
                        after_cost,
                        _iso(timestamp),
                    ),
                )
        cash_after = (
            cash_before - gross_minor
            if document["side"] == "buy"
            else cash_before + gross_minor
        )
        connection.execute(
            "UPDATE p_investment_books SET cash_minor=? WHERE id=? AND household_id=?",
            (cash_after, book["id"], context.household_id),
        )
        receipt_id = identifier("order-receipt")
        source = _calculated_evidence(
            "Confirmed fictional order",
            max(date.fromisoformat(leg["price_as_of"]) for leg in document["legs"]),
            [preview_id, book["id"]],
            method="Atomic update of a fictional cash book and simulated positions.",
        )
        receipt = {
            **{
                key: document[key]
                for key in (
                    "book_id",
                    "side",
                    "kind",
                    "symbol",
                    "bundle_id",
                    "currency",
                    "legs",
                    "gross",
                    "fee",
                    "rounding_rule",
                    "rounding_cost",
                    "cash_effect",
                )
            },
            "id": receipt_id,
            "preview_id": preview_id,
            "cash_before": decimal_amount(cash_before, book["currency"]),
            "cash_after": decimal_amount(cash_after, book["currency"]),
            "confirmed_at": _iso(timestamp),
            "source": source.model_dump(mode="json"),
        }
        connection.execute(
            """
            INSERT INTO p_investment_order_receipts(
                id,preview_id,household_id,book_id,idempotency_key,document_json,confirmed_at
            ) VALUES(?,?,?,?,?,?,?)
            """,
            (
                receipt_id,
                preview_id,
                context.household_id,
                book["id"],
                idempotency_key,
                json.dumps(receipt),
                _iso(timestamp),
            ),
        )
        return receipt


def list_orders(store: Store, context: Context, *, limit: int = 20) -> dict[str, object]:
    bounded_limit = min(max(limit, 1), 100)
    with store.connection() as connection:
        rows = connection.execute(
            """
            SELECT document_json FROM p_investment_order_receipts
            WHERE household_id=? ORDER BY confirmed_at DESC,id DESC LIMIT ?
            """,
            (context.household_id, bounded_limit),
        ).fetchall()
    return {"items": [json.loads(row["document_json"]) for row in rows]}


def list_positions(store: Store, context: Context) -> list[dict[str, object]]:
    prices = latest_prices(store)
    with store.connection() as connection:
        rows = connection.execute(
            """
            SELECT positions.*,books.source_json
            FROM p_investment_positions positions
            JOIN p_investment_books books ON books.id=positions.book_id
            WHERE books.household_id=? ORDER BY positions.book_id,positions.symbol
            """,
            (context.household_id,),
        ).fetchall()
    result: list[dict[str, object]] = []
    for row in rows:
        quantity = Decimal(row["quantity"])
        price = prices.get((row["symbol"], row["currency"]))
        record: dict[str, object] = {
            "book_id": row["book_id"],
            "symbol": row["symbol"],
            "currency": row["currency"],
            "quantity": row["quantity"],
            "total_cost": decimal_amount(row["total_cost_minor"], row["currency"]),
            "average_cost": format(
                (
                    Decimal(decimal_amount(row["total_cost_minor"], row["currency"]))
                    / quantity
                ).quantize(Decimal("0.01")),
                "f",
            ),
            "source": Evidence.model_validate_json(row["source_json"]).model_dump(
                mode="json"
            ),
        }
        if price is None:
            record.update(
                {
                    "price": None,
                    "market_value": None,
                    "gain_loss": None,
                    "gain_loss_pct": None,
                }
            )
        else:
            value_minor = _money_minor(
                quantity
                * Decimal(decimal_amount(int(price["price_minor"]), row["currency"])),
                row["currency"],
            )
            gain_minor = value_minor - row["total_cost_minor"]
            record.update(
                {
                    "price": {
                        key: value
                        for key, value in price.items()
                        if key not in {"set_id", "price_minor", "loaded_at"}
                    }
                    | {
                        "price": decimal_amount(
                            int(price["price_minor"]), row["currency"]
                        )
                    },
                    "market_value": decimal_amount(value_minor, row["currency"]),
                    "gain_loss": decimal_amount(gain_minor, row["currency"]),
                    "gain_loss_pct": _percent(
                        Decimal(gain_minor), Decimal(row["total_cost_minor"])
                    ),
                }
            )
        result.append(record)
    return result


def _plan_record(row: sqlite3.Row) -> dict[str, object]:
    return {
        "id": row["id"],
        "book_id": row["book_id"],
        "cadence": row["cadence"],
        "next_run_on": row["next_run_on"],
        "symbol": row["symbol"],
        "bundle_id": row["bundle_id"],
        "amount": decimal_amount(row["amount_minor"], row["currency"]),
        "currency": row["currency"],
        "active": bool(row["active"]),
        "source": Evidence.model_validate_json(row["source_json"]).model_dump(
            mode="json"
        ),
    }


def list_recurring_plans(store: Store, context: Context) -> dict[str, object]:
    with store.connection() as connection:
        rows = connection.execute(
            """
            SELECT * FROM p_investment_recurring_plans
            WHERE household_id=? ORDER BY created_at,id
            """,
            (context.household_id,),
        ).fetchall()
    return {"items": [_plan_record(row) for row in rows]}


def create_recurring_plan(
    store: Store, context: Context, payload: RecurringPlanCreate
) -> dict[str, object]:
    require_editor(context)
    with store.connection() as connection:
        book = connection.execute(
            "SELECT * FROM p_investment_books WHERE id=? AND household_id=?",
            (payload.book_id, context.household_id),
        ).fetchone()
    if book is None:
        raise PlatformError("simulation_book_not_found", 404)
    if payload.bundle_id is not None:
        bundle = _bundle(payload.bundle_id)
        if bundle["currency"] != book["currency"]:
            raise PlatformError("currency_mismatch")
    plan_id = identifier("recurring-plan")
    timestamp = now()
    source = _user_evidence(
        "Recurring fictional investment plan",
        payload.next_run_on,
        [plan_id, context.user_id],
    )
    with store.connection(write=True) as connection:
        assert_active_context(connection, context)
        connection.execute(
            """
            INSERT INTO p_investment_recurring_plans(
                id,household_id,created_by,book_id,cadence,next_run_on,
                monthly_anchor_day,symbol,
                bundle_id,amount_minor,currency,active,created_at,updated_at,source_json
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                plan_id,
                context.household_id,
                context.user_id,
                payload.book_id,
                payload.cadence,
                payload.next_run_on.isoformat(),
                payload.next_run_on.day if payload.cadence == "monthly" else None,
                payload.symbol,
                payload.bundle_id,
                minor_units(payload.amount, book["currency"]),
                book["currency"],
                1,
                _iso(timestamp),
                _iso(timestamp),
                source.model_dump_json(),
            ),
        )
    return get_recurring_plan(store, context, plan_id)


def get_recurring_plan(store: Store, context: Context, plan_id: str) -> dict[str, object]:
    with store.connection() as connection:
        row = connection.execute(
            """
            SELECT * FROM p_investment_recurring_plans
            WHERE id=? AND household_id=?
            """,
            (plan_id, context.household_id),
        ).fetchone()
    if row is None:
        raise PlatformError("recurring_plan_not_found", 404)
    return _plan_record(row)


def update_recurring_plan(
    store: Store, context: Context, plan_id: str, payload: RecurringPlanUpdate
) -> dict[str, object]:
    require_editor(context)
    with store.connection(write=True) as connection:
        assert_active_context(connection, context)
        row = connection.execute(
            """
            SELECT * FROM p_investment_recurring_plans
            WHERE id=? AND household_id=?
            """,
            (plan_id, context.household_id),
        ).fetchone()
        if row is None:
            raise PlatformError("recurring_plan_not_found", 404)
        connection.execute(
            """
            UPDATE p_investment_recurring_plans
            SET amount_minor=?,next_run_on=?,monthly_anchor_day=?,active=?,updated_at=?
            WHERE id=? AND household_id=?
            """,
            (
                (
                    minor_units(payload.amount, row["currency"])
                    if payload.amount is not None
                    else row["amount_minor"]
                ),
                (
                    payload.next_run_on.isoformat()
                    if payload.next_run_on is not None
                    else row["next_run_on"]
                ),
                (
                    payload.next_run_on.day
                    if payload.next_run_on is not None and row["cadence"] == "monthly"
                    else row["monthly_anchor_day"]
                ),
                int(payload.active) if payload.active is not None else row["active"],
                _iso(now()),
                plan_id,
                context.household_id,
            ),
        )
    return get_recurring_plan(store, context, plan_id)


def _period_key(cadence: str, run_on: date) -> str:
    if cadence == "weekly":
        iso_year, iso_week, _ = run_on.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"
    return run_on.strftime("%Y-%m")


def _monthly_anchor_day(plan: sqlite3.Row) -> int:
    anchor = plan["monthly_anchor_day"]
    if anchor is not None:
        return int(anchor)
    return date.fromisoformat(plan["next_run_on"]).day


def _next_run_date(
    cadence: str, run_on: date, *, monthly_anchor_day: int | None = None
) -> date:
    if cadence == "weekly":
        return run_on + timedelta(days=7)
    if monthly_anchor_day is None:
        raise ValueError("monthly recurrence requires an anchor day")
    year = run_on.year + (1 if run_on.month == 12 else 0)
    month = 1 if run_on.month == 12 else run_on.month + 1
    day = min(monthly_anchor_day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _encode_recurring_cursor(next_run_on: str, plan_id: str) -> str:
    document = json.dumps([next_run_on, plan_id], separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(document).decode().rstrip("=")


def _decode_recurring_cursor(cursor: str) -> tuple[str, str]:
    if not cursor or len(cursor) > 512:
        raise PlatformError("invalid_recurring_cursor")
    try:
        padding = "=" * (-len(cursor) % 4)
        document = json.loads(base64.urlsafe_b64decode(cursor + padding))
        if (
            not isinstance(document, list)
            or len(document) != 2
            or not all(isinstance(value, str) for value in document)
            or not document[1]
            or len(document[1]) > 200
        ):
            raise ValueError
        date.fromisoformat(document[0])
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        raise PlatformError("invalid_recurring_cursor") from None
    return document[0], document[1]


def _run_record(row: sqlite3.Row) -> dict[str, object]:
    receipt = None
    if row["receipt_json"]:
        receipt = json.loads(row["receipt_json"])
    return {
        "id": row["id"],
        "plan_id": row["plan_id"],
        "period_key": row["period_key"],
        "run_on": row["run_on"],
        "status": row["status"],
        "order_receipt": receipt,
        "error_code": row["error_code"],
        "source": Evidence.model_validate_json(row["source_json"]).model_dump(
            mode="json"
        ),
    }


def _read_run_for_household(
    store: Store, household_id: str, run_id: str
) -> dict[str, object]:
    with store.connection() as connection:
        row = connection.execute(
            """
            SELECT runs.*,receipts.document_json AS receipt_json
            FROM p_investment_recurring_runs runs
            LEFT JOIN p_investment_order_receipts receipts ON receipts.id=runs.receipt_id
            WHERE runs.id=? AND runs.household_id=?
            """,
            (run_id, household_id),
        ).fetchone()
    if row is None:
        raise PlatformError("recurring_run_not_found", 404)
    return _run_record(row)


def _read_run(store: Store, context: Context, run_id: str) -> dict[str, object]:
    return _read_run_for_household(store, context.household_id, run_id)


def _advance_recurring_plan(
    connection: sqlite3.Connection, plan: sqlite3.Row, run_on: date
) -> None:
    anchor_day = _monthly_anchor_day(plan) if plan["cadence"] == "monthly" else None
    next_run_on = _next_run_date(
        plan["cadence"], run_on, monthly_anchor_day=anchor_day
    ).isoformat()
    connection.execute(
        """
        UPDATE p_investment_recurring_plans
        SET next_run_on=CASE WHEN next_run_on<=? THEN ? ELSE next_run_on END,
            monthly_anchor_day=CASE
                WHEN cadence='monthly' THEN COALESCE(monthly_anchor_day,?)
                ELSE NULL
            END,
            updated_at=?
        WHERE id=? AND household_id=?
        """,
        (
            run_on.isoformat(),
            next_run_on,
            anchor_day,
            _iso(now()),
            plan["id"],
            plan["household_id"],
        ),
    )


def _reconcile_recurring_run(
    store: Store,
    plan: sqlite3.Row,
    run_id: str,
    *,
    advance_failed: bool = False,
) -> dict[str, object]:
    """Make the immutable paper-order receipt the recovery source of truth."""

    with store.connection(write=True) as connection:
        run = connection.execute(
            "SELECT * FROM p_investment_recurring_runs WHERE id=? AND household_id=?",
            (run_id, plan["household_id"]),
        ).fetchone()
        if run is None:
            raise PlatformError("recurring_run_not_found", 404)
        receipt = connection.execute(
            """
            SELECT id FROM p_investment_order_receipts
            WHERE household_id=? AND idempotency_key=?
            """,
            (
                plan["household_id"],
                f"recurring:{plan['id']}:{run['period_key']}",
            ),
        ).fetchone()
        timestamp = now()
        if receipt is not None:
            connection.execute(
                """
                UPDATE p_investment_recurring_runs
                SET status='succeeded',receipt_id=?,error_code=NULL,completed_at=?
                WHERE id=?
                """,
                (receipt["id"], _iso(timestamp), run_id),
            )
            _advance_recurring_plan(
                connection, plan, date.fromisoformat(run["run_on"])
            )
        elif run["status"] == "running" and datetime.fromisoformat(
            run["created_at"]
        ) <= timestamp - RECURRING_RUN_LEASE:
            connection.execute(
                """
                UPDATE p_investment_recurring_runs
                SET status='failed',error_code='recurring_run_interrupted',completed_at=?
                WHERE id=? AND status='running'
                """,
                (_iso(timestamp), run_id),
            )
            _advance_recurring_plan(
                connection, plan, date.fromisoformat(run["run_on"])
            )
        elif run["status"] == "succeeded" or (
            advance_failed and run["status"] == "failed"
        ):
            _advance_recurring_plan(
                connection, plan, date.fromisoformat(run["run_on"])
            )
    return _read_run_for_household(store, plan["household_id"], run_id)


def _record_recurring_authority_failure(
    connection: sqlite3.Connection, plan: sqlite3.Row, run_on: date
) -> str:
    period_key = _period_key(plan["cadence"], run_on)
    existing = connection.execute(
        """
        SELECT id,status FROM p_investment_recurring_runs
        WHERE plan_id=? AND period_key=?
        """,
        (plan["id"], period_key),
    ).fetchone()
    if existing is None:
        existing = connection.execute(
            """
            SELECT id,status FROM p_investment_recurring_runs
            WHERE plan_id=? AND status='running' ORDER BY created_at,id LIMIT 1
            """,
            (plan["id"],),
        ).fetchone()
    timestamp = now()
    if existing is None:
        run_id = identifier("recurring-run")
        source = _calculated_evidence(
            "Recurring fictional investment run",
            run_on,
            [plan["id"], period_key],
            method="Scheduled run stopped because its creator no longer has active edit permission.",
        )
        connection.execute(
            """
            INSERT INTO p_investment_recurring_runs(
                id,plan_id,household_id,period_key,run_on,status,error_code,
                source_json,created_at,completed_at
            ) VALUES(?,?,?,?,?,'failed','recurring_creator_unauthorized',?,?,?)
            """,
            (
                run_id,
                plan["id"],
                plan["household_id"],
                period_key,
                run_on.isoformat(),
                source.model_dump_json(),
                _iso(timestamp),
                _iso(timestamp),
            ),
        )
    else:
        run_id = existing["id"]
        connection.execute(
            """
            UPDATE p_investment_recurring_runs
            SET status='failed',error_code='recurring_creator_unauthorized',
                completed_at=?
            WHERE id=? AND status='running'
            """,
            (_iso(timestamp), run_id),
        )
    connection.execute(
        """
        UPDATE p_investment_recurring_plans
        SET active=0,updated_at=? WHERE id=? AND household_id=?
        """,
        (_iso(timestamp), plan["id"], plan["household_id"]),
    )
    return run_id


def _execute_recurring_plan(
    store: Store,
    context: Context | None,
    plan_id: str,
    run_on: date,
    *,
    scheduled: bool,
) -> dict[str, object]:
    if not scheduled:
        if context is None:
            raise ValueError("manual recurring runs require context")
        require_editor(context)
    with store.connection(write=True) as connection:
        if scheduled:
            plan = connection.execute(
                "SELECT * FROM p_investment_recurring_plans WHERE id=?",
                (plan_id,),
            ).fetchone()
        else:
            assert context is not None
            assert_active_context(connection, context)
            plan = connection.execute(
                """
                SELECT * FROM p_investment_recurring_plans
                WHERE id=? AND household_id=?
                """,
                (plan_id, context.household_id),
            ).fetchone()
        if plan is None:
            raise PlatformError("recurring_plan_not_found", 404)
        if not plan["active"]:
            raise PlatformError("recurring_plan_inactive")
        if scheduled:
            try:
                context = active_context(
                    connection,
                    user_id=plan["created_by"],
                    household_id=plan["household_id"],
                    session_id="scheduled-investing",
                )
                assert_active_context(connection, context)
            except PlatformError:
                run_id = _record_recurring_authority_failure(
                    connection, plan, run_on
                )
                blocked = True
            else:
                blocked = False
        else:
            blocked = False
        if not blocked:
            period_key = _period_key(plan["cadence"], run_on)
            existing = connection.execute(
                """
                SELECT id FROM p_investment_recurring_runs
                WHERE plan_id=? AND period_key=?
                """,
                (plan_id, period_key),
            ).fetchone()
            if existing is None:
                existing = connection.execute(
                    """
                    SELECT id FROM p_investment_recurring_runs
                    WHERE plan_id=? AND status='running'
                    ORDER BY created_at,id LIMIT 1
                    """,
                    (plan_id,),
                ).fetchone()
            if existing is not None:
                run_id = existing["id"]
                existing_run = True
            else:
                if run_on < date.fromisoformat(plan["next_run_on"]):
                    raise PlatformError("recurring_plan_not_due")
                existing_run = False
                run_id = identifier("recurring-run")
                source = _calculated_evidence(
                    "Recurring fictional investment run",
                    run_on,
                    [plan_id, period_key],
                    method="At most one paper-order attempt per cadence period.",
                )
                connection.execute(
                    """
                    INSERT INTO p_investment_recurring_runs(
                        id,plan_id,household_id,period_key,run_on,status,source_json,created_at
                    ) VALUES(?,?,?,?,?,'running',?,?)
                    """,
                    (
                        run_id,
                        plan_id,
                        plan["household_id"],
                        period_key,
                        run_on.isoformat(),
                        source.model_dump_json(),
                        _iso(now()),
                    ),
                )
        else:
            existing_run = True
    if existing_run:
        return _reconcile_recurring_run(
            store, plan, run_id, advance_failed=scheduled
        )
    assert context is not None
    prices = latest_prices(store, currency=plan["currency"])
    try:
        if plan["symbol"]:
            price = prices.get((plan["symbol"], plan["currency"]))
            if price is None:
                raise PlatformError("price_unavailable")
            amount = Decimal(decimal_amount(plan["amount_minor"], plan["currency"]))
            price_amount = Decimal(
                decimal_amount(int(price["price_minor"]), plan["currency"])
            )
            quantity = (amount / price_amount).quantize(
                Decimal("0.00000001"), rounding=ROUND_DOWN
            )
            preview_payload = OrderPreviewRequest(
                book_id=plan["book_id"],
                side="buy",
                symbol=plan["symbol"],
                quantity=quantity,
            )
        else:
            preview_payload = OrderPreviewRequest(
                book_id=plan["book_id"],
                side="buy",
                bundle_id=plan["bundle_id"],
                amount=Decimal(decimal_amount(plan["amount_minor"], plan["currency"])),
            )
        preview = preview_order(store, context, preview_payload)
        confirm_order(
            store,
            context,
            str(preview["id"]),
            f"recurring:{plan_id}:{period_key}",
            recurring_run_id=run_id,
        )
    except PlatformError as exc:
        with store.connection(write=True) as connection:
            connection.execute(
                """
                UPDATE p_investment_recurring_runs
                SET status='failed',error_code=?,completed_at=?
                WHERE id=? AND status='running'
                """,
                (exc.code, _iso(now()), run_id),
            )
            if scheduled:
                _advance_recurring_plan(connection, plan, run_on)
        return _reconcile_recurring_run(
            store, plan, run_id, advance_failed=scheduled
        )
    return _reconcile_recurring_run(store, plan, run_id)


def run_recurring_plan(
    store: Store, context: Context, plan_id: str, run_on: date
) -> dict[str, object]:
    return _execute_recurring_plan(
        store, context, plan_id, run_on, scheduled=False
    )


def run_due_recurring_plans(
    store: Store,
    run_on: date,
    *,
    cursor: str | None = None,
    limit: int = MAX_RECURRING_BATCH,
) -> dict[str, object]:
    if not 1 <= limit <= MAX_RECURRING_BATCH:
        raise PlatformError("invalid_recurring_limit")
    cursor_values = _decode_recurring_cursor(cursor) if cursor is not None else None
    with store.connection() as connection:
        if cursor_values is None:
            rows = connection.execute(
                """
                SELECT id,next_run_on FROM p_investment_recurring_plans
                WHERE active=1 AND next_run_on<=?
                ORDER BY next_run_on,id LIMIT ?
                """,
                (run_on.isoformat(), limit + 1),
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT id,next_run_on FROM p_investment_recurring_plans
                WHERE active=1 AND next_run_on<=?
                  AND (next_run_on>? OR (next_run_on=? AND id>?))
                ORDER BY next_run_on,id LIMIT ?
                """,
                (
                    run_on.isoformat(),
                    cursor_values[0],
                    cursor_values[0],
                    cursor_values[1],
                    limit + 1,
                ),
            ).fetchall()
    selected = rows[:limit]
    items: list[dict[str, object]] = []
    for row in selected:
        try:
            items.append(
                _execute_recurring_plan(
                    store, None, row["id"], run_on, scheduled=True
                )
            )
        except PlatformError as exc:
            if exc.code not in {"recurring_plan_inactive", "recurring_plan_not_due"}:
                raise
    next_cursor = (
        _encode_recurring_cursor(selected[-1]["next_run_on"], selected[-1]["id"])
        if len(rows) > limit and selected
        else None
    )
    with store.connection() as connection:
        next_poll_on = connection.execute(
            """
            SELECT MIN(next_run_on) FROM p_investment_recurring_plans
            WHERE active=1
            """
        ).fetchone()[0]
    return {
        "items": items,
        "next_cursor": next_cursor,
        "next_poll_on": next_poll_on,
    }


def export_data(connection: sqlite3.Connection, context: Context) -> dict[str, object]:
    """Identity lifecycle callback for this household's investing records."""

    household_tables = {
        "holdings": "p_investment_holdings",
        "books": "p_investment_books",
        "import_previews": "p_investment_import_previews",
        "import_receipts": "p_investment_import_receipts",
        "order_previews": "p_investment_order_previews",
        "order_receipts": "p_investment_order_receipts",
        "recurring_plans": "p_investment_recurring_plans",
        "recurring_runs": "p_investment_recurring_runs",
    }
    result: dict[str, object] = {}
    for name, table in household_tables.items():
        rows = connection.execute(
            f"SELECT * FROM {table} WHERE household_id=? ORDER BY id",
            (context.household_id,),
        ).fetchall()
        result[name] = [dict(row) for row in rows]
    positions = connection.execute(
        """
        SELECT positions.* FROM p_investment_positions positions
        JOIN p_investment_books books ON books.id=positions.book_id
        WHERE books.household_id=? ORDER BY positions.book_id,positions.symbol
        """,
        (context.household_id,),
    ).fetchall()
    result["positions"] = [dict(row) for row in positions]
    return result


def clear_data(connection: sqlite3.Connection, context: Context) -> None:
    """Delete one household's records while retaining the no-reseed manifest."""

    book_ids = [
        row["id"]
        for row in connection.execute(
            "SELECT id FROM p_investment_books WHERE household_id=?",
            (context.household_id,),
        ).fetchall()
    ]
    if book_ids:
        placeholders = ",".join("?" for _ in book_ids)
        connection.execute(
            f"DELETE FROM p_investment_positions WHERE book_id IN ({placeholders})",
            book_ids,
        )
    for table in (
        "p_investment_recurring_runs",
        "p_investment_recurring_plans",
        "p_investment_order_receipts",
        "p_investment_order_previews",
        "p_investment_import_receipts",
        "p_investment_import_previews",
        "p_investment_holdings",
        "p_investment_books",
    ):
        connection.execute(
            f"DELETE FROM {table} WHERE household_id=?", (context.household_id,)
        )


def usage_data(connection: sqlite3.Connection, context: Context) -> dict[str, object]:
    counts: dict[str, int] = {}
    for key, table in (
        ("holdings", "p_investment_holdings"),
        ("simulation_books", "p_investment_books"),
        ("confirmed_orders", "p_investment_order_receipts"),
        ("recurring_plans", "p_investment_recurring_plans"),
    ):
        counts[key] = int(
            connection.execute(
                f"SELECT COUNT(*) AS count FROM {table} WHERE household_id=?",
                (context.household_id,),
            ).fetchone()["count"]
        )
    return counts


@router.get("/investing/portfolio")
def portfolio_route(request: Request) -> dict[str, object]:
    return portfolio_summary(get_store(request), get_context(request))


@router.get("/investing/holdings/sample.csv")
def holding_sample_route() -> Response:
    content = (
        "symbol,name,quantity,total_cost,currency,as_of\n"
        "ALT-CARD,Card collection,1,1200.00,USD,2026-09-20\n"
    )
    return Response(content=content, media_type="text/csv")


@router.get("/investing/holdings")
def holdings_route(request: Request) -> dict[str, object]:
    return list_holdings(get_store(request), get_context(request))


@router.post("/investing/holdings")
def create_holding_route(payload: HoldingCreate, request: Request) -> dict[str, object]:
    return create_holding(get_store(request), get_context(request), payload)


@router.patch("/investing/holdings/{holding_id}")
def update_holding_route(
    holding_id: str, payload: HoldingUpdate, request: Request
) -> dict[str, object]:
    return update_holding(get_store(request), get_context(request), holding_id, payload)


@router.delete("/investing/holdings/{holding_id}")
def delete_holding_route(holding_id: str, request: Request) -> dict[str, object]:
    return delete_holding(get_store(request), get_context(request), holding_id)


@router.post("/investing/holding-imports/preview")
def holding_import_preview_route(
    payload: HoldingCsvRequest, request: Request
) -> dict[str, object]:
    return preview_holding_csv(get_store(request), get_context(request), payload.csv)


@router.post("/investing/holding-imports/{preview_id}/commit")
def holding_import_commit_route(
    preview_id: str, payload: IdempotencyRequest, request: Request
) -> dict[str, object]:
    return commit_holding_import(
        get_store(request), get_context(request), preview_id, payload.idempotency_key
    )


@router.post("/investing/prices/load")
def price_load_route(payload: PriceLoadRequest, request: Request) -> dict[str, object]:
    context = get_context(request)
    require_editor(context)
    return load_market_prices(
        get_store(request), FixtureMarketDataAdapter(outcome=payload.outcome)
    )


@router.get("/investing/books")
def books_route(request: Request) -> dict[str, object]:
    return list_books(get_store(request), get_context(request))


@router.get("/investing/orders")
def orders_route(request: Request, limit: int = 20) -> dict[str, object]:
    return list_orders(get_store(request), get_context(request), limit=limit)


@router.post("/investing/orders/preview")
def order_preview_route(
    payload: OrderPreviewRequest, request: Request
) -> dict[str, object]:
    return preview_order(get_store(request), get_context(request), payload)


@router.post("/investing/orders/{preview_id}/confirm")
def order_confirm_route(
    preview_id: str, payload: IdempotencyRequest, request: Request
) -> dict[str, object]:
    return confirm_order(
        get_store(request), get_context(request), preview_id, payload.idempotency_key
    )


@router.get("/investing/bundles")
def bundles_route() -> dict[str, object]:
    return list_bundles()


@router.get("/investing/recurring-plans")
def recurring_plans_route(request: Request) -> dict[str, object]:
    return list_recurring_plans(get_store(request), get_context(request))


@router.post("/investing/recurring-plans")
def recurring_plan_create_route(
    payload: RecurringPlanCreate, request: Request
) -> dict[str, object]:
    return create_recurring_plan(get_store(request), get_context(request), payload)


@router.patch("/investing/recurring-plans/{plan_id}")
def recurring_plan_update_route(
    plan_id: str, payload: RecurringPlanUpdate, request: Request
) -> dict[str, object]:
    return update_recurring_plan(
        get_store(request), get_context(request), plan_id, payload
    )


@router.post("/investing/recurring-plans/{plan_id}/run")
def recurring_plan_run_route(
    plan_id: str, payload: RecurringRunRequest, request: Request
) -> dict[str, object]:
    return run_recurring_plan(
        get_store(request), get_context(request), plan_id, payload.run_on
    )
