"""Dated read-only market prices for Clara's local investing simulator."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Literal, Protocol

import httpx
from pydantic import Field

from ..store import Store
from .common import (
    Evidence,
    Model,
    PlatformError,
    PositiveAmount,
    identifier,
    minor_units,
)

FIXTURE_AS_OF = date(2026, 9, 20)
FIXTURE_RECORDED_AT = datetime(2026, 9, 20, 12, tzinfo=timezone.utc)

ALPACA_READ_ONLY_ENV_NAMES = (
    "CLARA_ALPACA_API_KEY",
    "CLARA_ALPACA_API_SECRET",
)
ALPACA_LATEST_BARS_URL = "https://data.alpaca.markets/v2/stocks/bars/latest"
ALPACA_DATA_HOST = "data.alpaca.markets"
ALPACA_RESPONSE_LIMIT = 1_000_000
AlpacaFeed = Literal["iex", "sip", "delayed_sip", "boats", "overnight", "otc"]


class DatedPrice(Model):
    symbol: str = Field(pattern=r"^[A-Z0-9.-]{1,24}$")
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    price: PositiveAmount
    as_of: date
    source: Evidence


class PriceBatch(Model):
    as_of: date
    prices: list[DatedPrice] = Field(min_length=1, max_length=500)
    source: Evidence


class MarketDataAdapter(Protocol):
    """Read-only adapter seam. Adapters return observations and cannot trade."""

    def fetch_prices(self) -> PriceBatch: ...


class MarketDataLoadError(Exception):
    def __init__(self, code: str = "market_data_unavailable") -> None:
        self.code = code
        super().__init__(code)


def _fixture_evidence(title: str, *, as_of: date = FIXTURE_AS_OF) -> Evidence:
    return Evidence(
        id=f"fixture-market-{title.lower().replace(' ', '-')}",
        kind="synthetic",
        title=title,
        as_of=as_of,
        recorded_at=FIXTURE_RECORDED_AT,
        method="Local deterministic fixture. Not a live quote.",
        inputs=[],
    )


class FixtureMarketDataAdapter:
    """Deterministic local observations used by tests and the demo load job."""

    def __init__(
        self,
        outcome: str = "success",
        *,
        as_of: date = FIXTURE_AS_OF,
        overrides: dict[tuple[str, str], Decimal] | None = None,
        symbols: list[str] | None = None,
    ) -> None:
        self.outcome = outcome
        self.as_of = as_of
        self.overrides = overrides or {}
        self.symbols = (
            tuple(dict.fromkeys(_stock_symbol(symbol) for symbol in symbols))
            if symbols is not None
            else None
        )
        if self.symbols == ():
            raise MarketDataLoadError("invalid_market_symbols")

    def fetch_prices(self) -> PriceBatch:
        if self.outcome != "success":
            raise MarketDataLoadError("fixture_market_load_failed")
        defaults = {
            ("AAPL", "USD"): Decimal("230.00"),
            ("BND", "USD"): Decimal("75.00"),
            ("SPY", "USD"): Decimal("650.00"),
            ("VXUS", "USD"): Decimal("72.00"),
            ("ALT-GOLD", "USD"): Decimal("1950.00"),
            ("VWCE", "EUR"): Decimal("135.00"),
        }
        defaults.update(self.overrides)
        if self.symbols is not None:
            requested = set(self.symbols)
            unknown = requested - {symbol for symbol, _currency in defaults}
            if unknown:
                raise MarketDataLoadError("fixture_symbol_unavailable")
            defaults = {
                key: value for key, value in defaults.items() if key[0] in requested
            }
        source = _fixture_evidence("Synthetic market observations", as_of=self.as_of)
        return PriceBatch(
            as_of=self.as_of,
            source=source,
            prices=[
                DatedPrice(
                    symbol=symbol,
                    currency=currency,
                    price=price,
                    as_of=self.as_of,
                    source=source,
                )
                for (symbol, currency), price in sorted(defaults.items())
            ],
        )


def _stock_symbol(value: str) -> str:
    normalized = value.strip().upper()
    if (
        not normalized
        or len(normalized) > 24
        or any(
            character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-"
            for character in normalized
        )
    ):
        raise MarketDataLoadError("invalid_market_symbol")
    return normalized


def _alpaca_url() -> httpx.URL:
    url = httpx.URL(ALPACA_LATEST_BARS_URL)
    if (
        url.scheme != "https"
        or url.host != ALPACA_DATA_HOST
        or url.path != "/v2/stocks/bars/latest"
    ):
        raise MarketDataLoadError("invalid_alpaca_destination")
    return url


class AlpacaMarketDataAdapter:
    """One-shot, read-only latest-minute-bar adapter for US stocks and ETFs."""

    def __init__(
        self,
        *,
        api_key: str,
        api_secret: str,
        symbols: list[str],
        feed: AlpacaFeed = "iex",
        timeout_seconds: float = 5.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not api_key.strip() or not api_secret.strip():
            raise MarketDataLoadError("alpaca_configuration_missing")
        normalized = tuple(dict.fromkeys(_stock_symbol(symbol) for symbol in symbols))
        if not normalized or len(normalized) > 200:
            raise MarketDataLoadError("invalid_market_symbols")
        if feed not in {"iex", "sip", "delayed_sip", "boats", "overnight", "otc"}:
            raise MarketDataLoadError("invalid_alpaca_feed")
        if not 0 < timeout_seconds <= 30:
            raise MarketDataLoadError("invalid_market_timeout")
        self._api_key = api_key.strip()
        self._api_secret = api_secret.strip()
        self.symbols = normalized
        self.feed = feed
        self.timeout = httpx.Timeout(timeout_seconds)
        self.transport = transport

    def fetch_prices(self) -> PriceBatch:
        recorded_at = datetime.now(timezone.utc)
        try:
            with httpx.Client(
                transport=self.transport,
                timeout=self.timeout,
                follow_redirects=False,
                trust_env=False,
            ) as client:
                response = client.get(
                    _alpaca_url(),
                    params={
                        "symbols": ",".join(self.symbols),
                        "feed": self.feed,
                        "currency": "USD",
                    },
                    headers={
                        "Accept": "application/json",
                        "APCA-API-KEY-ID": self._api_key,
                        "APCA-API-SECRET-KEY": self._api_secret,
                    },
                )
        except httpx.RequestError as exc:
            raise MarketDataLoadError("alpaca_request_failed") from exc
        if response.is_redirect:
            raise MarketDataLoadError("alpaca_redirect_rejected")
        if response.status_code in {401, 403}:
            raise MarketDataLoadError("alpaca_authentication_failed")
        if response.status_code == 429:
            raise MarketDataLoadError("alpaca_rate_limited")
        if response.status_code != 200:
            raise MarketDataLoadError("alpaca_http_error")
        if len(response.content) > ALPACA_RESPONSE_LIMIT:
            raise MarketDataLoadError("alpaca_response_too_large")
        try:
            document = response.json()
        except ValueError as exc:
            raise MarketDataLoadError("invalid_alpaca_response") from exc
        return self._parse(document, recorded_at)

    def _parse(self, document: object, recorded_at: datetime) -> PriceBatch:
        if not isinstance(document, dict) or set(document) != {"bars"}:
            raise MarketDataLoadError("invalid_alpaca_response")
        bars = document["bars"]
        if not isinstance(bars, dict) or set(bars) != set(self.symbols):
            raise MarketDataLoadError("alpaca_incomplete_price_set")
        observations: list[tuple[str, Decimal, datetime]] = []
        for symbol in self.symbols:
            bar = bars[symbol]
            if not isinstance(bar, dict) or "c" not in bar or "t" not in bar:
                raise MarketDataLoadError("invalid_alpaca_bar")
            close = bar["c"]
            if isinstance(close, bool):
                raise MarketDataLoadError("invalid_alpaca_price")
            try:
                price = Decimal(str(close))
            except (InvalidOperation, ValueError) as exc:
                raise MarketDataLoadError("invalid_alpaca_price") from exc
            if not price.is_finite() or price <= 0:
                raise MarketDataLoadError("invalid_alpaca_price")
            timestamp = bar["t"]
            if not isinstance(timestamp, str):
                raise MarketDataLoadError("invalid_alpaca_timestamp")
            try:
                observed_at = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except ValueError as exc:
                raise MarketDataLoadError("invalid_alpaca_timestamp") from exc
            if observed_at.tzinfo is None:
                raise MarketDataLoadError("invalid_alpaca_timestamp")
            observations.append((symbol, price, observed_at.astimezone(timezone.utc)))
        observed_dates = {observed_at.date() for _, _, observed_at in observations}
        if len(observed_dates) != 1:
            raise MarketDataLoadError("inconsistent_alpaca_price_date")
        as_of = observed_dates.pop()
        source = Evidence(
            id=identifier("alpaca-market-observation"),
            kind="published",
            title=f"Alpaca {self.feed.upper()} latest minute bars",
            as_of=as_of,
            recorded_at=recorded_at,
            published_on=as_of,
            method=(
                "Latest minute-bar close from Alpaca Market Data. Read-only market "
                "observation, not a broker quote or execution price."
            ),
            inputs=[
                f"feed={self.feed}",
                "currency=USD",
                *[
                    f"{symbol}:bar_timestamp={observed_at.isoformat()}"
                    for symbol, _price, observed_at in observations
                ],
            ],
            url=ALPACA_LATEST_BARS_URL,
        )
        return PriceBatch(
            as_of=as_of,
            source=source,
            prices=[
                DatedPrice(
                    symbol=symbol,
                    currency="USD",
                    price=price,
                    as_of=as_of,
                    source=source,
                )
                for symbol, price, _observed_at in observations
            ],
        )


MARKET_SCHEMA = """
CREATE TABLE IF NOT EXISTS p_market_price_loads (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK(status IN ('loading','succeeded','failed')),
    as_of TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    error_code TEXT,
    source_json TEXT
);
CREATE TABLE IF NOT EXISTS p_market_price_sets (
    id TEXT PRIMARY KEY,
    load_id TEXT NOT NULL UNIQUE REFERENCES p_market_price_loads(id),
    as_of TEXT NOT NULL,
    loaded_at TEXT NOT NULL,
    source_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS p_market_prices (
    set_id TEXT NOT NULL REFERENCES p_market_price_sets(id),
    symbol TEXT NOT NULL,
    currency TEXT NOT NULL,
    price_minor INTEGER NOT NULL CHECK(price_minor > 0),
    as_of TEXT NOT NULL,
    source_json TEXT NOT NULL,
    PRIMARY KEY(set_id, symbol, currency)
);
CREATE INDEX IF NOT EXISTS p_market_prices_lookup
ON p_market_prices(symbol, currency, as_of DESC, set_id DESC);
"""


def initialize(store: Store) -> None:
    with store.connection(write=True) as connection:
        connection.executescript(MARKET_SCHEMA)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def load_market_prices(store: Store, adapter: MarketDataAdapter) -> dict[str, object]:
    """Run one manual/scheduled read-only load and retain the last good set."""

    load_id = identifier("price-load")
    started_at = datetime.now(timezone.utc)
    with store.connection(write=True) as connection:
        connection.execute(
            "INSERT INTO p_market_price_loads(id,status,started_at) VALUES(?,?,?)",
            (load_id, "loading", _iso(started_at)),
        )
    try:
        batch = adapter.fetch_prices()
        pairs = {(price.symbol, price.currency) for price in batch.prices}
        if len(pairs) != len(batch.prices):
            raise MarketDataLoadError("duplicate_market_price")
        if any(price.as_of != batch.as_of for price in batch.prices):
            raise MarketDataLoadError("inconsistent_market_price_date")
        completed_at = datetime.now(timezone.utc)
        set_id = identifier("price-set")
        with store.connection(write=True) as connection:
            connection.execute(
                """
                INSERT INTO p_market_price_sets(id,load_id,as_of,loaded_at,source_json)
                VALUES(?,?,?,?,?)
                """,
                (
                    set_id,
                    load_id,
                    batch.as_of.isoformat(),
                    _iso(completed_at),
                    batch.source.model_dump_json(),
                ),
            )
            for price in batch.prices:
                connection.execute(
                    """
                    INSERT INTO p_market_prices(
                        set_id,symbol,currency,price_minor,as_of,source_json
                    ) VALUES(?,?,?,?,?,?)
                    """,
                    (
                        set_id,
                        price.symbol,
                        price.currency,
                        minor_units(price.price, price.currency),
                        price.as_of.isoformat(),
                        price.source.model_dump_json(),
                    ),
                )
            connection.execute(
                """
                UPDATE p_market_price_loads
                SET status='succeeded',as_of=?,completed_at=?,source_json=?
                WHERE id=?
                """,
                (
                    batch.as_of.isoformat(),
                    _iso(completed_at),
                    batch.source.model_dump_json(),
                    load_id,
                ),
            )
        return price_load(store, load_id)
    except Exception as exc:
        completed_at = datetime.now(timezone.utc)
        code = (
            exc.code
            if isinstance(exc, (MarketDataLoadError, PlatformError))
            else "market_data_unavailable"
        )
        with store.connection(write=True) as connection:
            connection.execute(
                """
                UPDATE p_market_price_loads
                SET status='failed',completed_at=?,error_code=? WHERE id=?
                """,
                (_iso(completed_at), code, load_id),
            )
        return price_load(store, load_id)


def price_load(store: Store, load_id: str) -> dict[str, object]:
    with store.connection() as connection:
        row = connection.execute(
            "SELECT * FROM p_market_price_loads WHERE id=?", (load_id,)
        ).fetchone()
    if row is None:
        raise PlatformError("price_load_not_found", 404)
    return {
        "id": row["id"],
        "status": row["status"],
        "as_of": row["as_of"],
        "completed_at": row["completed_at"],
        "error_code": row["error_code"],
        "source": (
            Evidence.model_validate_json(row["source_json"]).model_dump(mode="json")
            if row["source_json"]
            else None
        ),
    }


def latest_prices(
    store: Store, *, currency: str | None = None
) -> dict[tuple[str, str], dict[str, object]]:
    params: list[object] = []
    currency_clause = ""
    if currency is not None:
        currency_clause = "AND prices.currency=?"
        params.append(currency)
    with store.connection() as connection:
        rows = connection.execute(
            f"""
            SELECT prices.symbol,prices.currency,prices.price_minor,prices.as_of,
                   prices.source_json,sets.loaded_at,prices.set_id
            FROM p_market_prices prices
            JOIN p_market_price_sets sets ON sets.id=prices.set_id
            WHERE NOT EXISTS (
                SELECT 1 FROM p_market_prices newer
                JOIN p_market_price_sets newer_sets ON newer_sets.id=newer.set_id
                WHERE newer.symbol=prices.symbol
                  AND newer.currency=prices.currency
                  AND (newer.as_of > prices.as_of OR
                       (newer.as_of=prices.as_of AND newer_sets.loaded_at > sets.loaded_at))
            ) {currency_clause}
            ORDER BY prices.symbol,prices.currency
            """,
            params,
        ).fetchall()
    result: dict[tuple[str, str], dict[str, object]] = {}
    for row in rows:
        result[(row["symbol"], row["currency"])] = {
            "set_id": row["set_id"],
            "symbol": row["symbol"],
            "currency": row["currency"],
            "price_minor": row["price_minor"],
            "as_of": row["as_of"],
            "loaded_at": row["loaded_at"],
            "source": Evidence.model_validate_json(row["source_json"]).model_dump(
                mode="json"
            ),
        }
    return result
