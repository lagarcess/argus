from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal

AssetClass = Literal["equity", "crypto", "currency_pair"]

ALPACA_EQUITY_HISTORY_START = date(2016, 1, 1)
KRAKEN_MAX_OHLC_CANDLES = 720

PROVIDER_TIMEFRAME_MINUTES: dict[str, int] = {
    "1h": 60,
    "2h": 120,
    "4h": 240,
    "6h": 360,
    "12h": 720,
    "1D": 1440,
}

KRAKEN_OHLC_TIMEFRAME_MINUTES: dict[str, int] = {
    "1h": 60,
    "4h": 240,
    "1D": 1440,
}


@dataclass(frozen=True)
class MarketDataWindowViolation:
    code: str
    provider: str
    detail: str


@dataclass(frozen=True)
class MarketDataDateAdjustment:
    kind: str
    original_end: date
    through: date
    provider: str
    timeframe: str

    @property
    def metadata(self) -> dict[str, str]:
        return {
            "kind": self.kind,
            "original_end": self.original_end.isoformat(),
            "provider": self.provider,
            "through": self.through.isoformat(),
            "timeframe": self.timeframe,
        }


@dataclass(frozen=True)
class MarketClockSnapshot:
    provider: str
    timestamp: datetime
    is_open: bool
    next_open: datetime | None = None
    next_close: datetime | None = None
    is_market_day: bool | None = None
    phase: str | None = None


def fetch_alpaca_market_clock() -> MarketClockSnapshot:
    from alpaca.trading.client import TradingClient

    key = (os.getenv("ALPACA_API_KEY") or "").strip()
    secret = (os.getenv("ALPACA_SECRET_KEY") or "").strip()
    if not key or not secret:
        raise ValueError("market_clock_unavailable")
    paper = (os.getenv("ALPACA_PAPER_TRADING") or "true").strip().lower() != "false"
    clock = TradingClient(api_key=key, secret_key=secret, paper=paper).get_clock()
    return MarketClockSnapshot(
        provider="alpaca",
        timestamp=clock.timestamp,
        is_open=bool(clock.is_open),
        next_open=getattr(clock, "next_open", None),
        next_close=getattr(clock, "next_close", None),
    )


def expected_candle_count(
    *, start_date: date, end_date: date, interval_minutes: int
) -> int:
    span_minutes = max(0, int((end_date - start_date).total_seconds() // 60))
    full_day_minutes = 24 * 60
    return (span_minutes + full_day_minutes) // interval_minutes


def latest_complete_data_adjustment(
    *,
    asset_class: AssetClass,
    timeframe: str,
    end_date: date,
    today: date,
    clock: MarketClockSnapshot | None = None,
) -> MarketDataDateAdjustment | None:
    normalized_timeframe = _normalize_timeframe(timeframe)
    if normalized_timeframe not in PROVIDER_TIMEFRAME_MINUTES:
        return None
    latest_complete = _latest_complete_data_date(
        asset_class=asset_class,
        timeframe=normalized_timeframe,
        today=today,
        clock=clock,
    )
    if end_date <= latest_complete or end_date > today:
        return None
    return MarketDataDateAdjustment(
        kind=(
            "latest_complete_daily_data"
            if normalized_timeframe == "1D"
            else "latest_complete_market_data"
        ),
        original_end=end_date,
        through=latest_complete,
        provider=_availability_provider(asset_class=asset_class, clock=clock),
        timeframe=normalized_timeframe,
    )


def _latest_complete_data_date(
    *,
    asset_class: AssetClass,
    timeframe: str,
    today: date,
    clock: MarketClockSnapshot | None,
) -> date:
    if asset_class == "equity":
        return _latest_complete_equity_date(
            timeframe=timeframe,
            today=today,
            clock=clock,
        )
    if timeframe == "1D":
        return today - timedelta(days=1)
    return today


def _latest_complete_equity_date(
    *,
    timeframe: str,
    today: date,
    clock: MarketClockSnapshot | None,
) -> date:
    if clock is None:
        return _previous_equity_session_date(today)
    if clock.is_market_day is False:
        return _previous_equity_session_date(today)
    if clock.is_open and timeframe != "1D":
        return today
    if clock.next_open is not None and clock.next_open.date() == today:
        return _previous_equity_session_date(today)
    if today.weekday() >= 5:
        return _previous_equity_session_date(today)
    return today


def _previous_equity_session_date(today: date) -> date:
    candidate = today - timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    return candidate


def _normalize_timeframe(timeframe: str) -> str:
    normalized = str(timeframe or "").strip().lower()
    aliases = {
        "1d": "1D",
        "1day": "1D",
        "daily": "1D",
        "day": "1D",
        "60m": "1h",
        "120m": "2h",
        "240m": "4h",
        "360m": "6h",
        "720m": "12h",
    }
    return aliases.get(normalized, normalized)


def _availability_provider(
    *,
    asset_class: AssetClass,
    clock: MarketClockSnapshot | None,
) -> str:
    if asset_class == "equity":
        return clock.provider if clock is not None else "alpaca"
    if asset_class == "currency_pair":
        return "kraken"
    return "continuous"


def market_data_window_violation(
    *,
    asset_class: AssetClass,
    timeframe: str,
    start_date: date,
    end_date: date,
) -> MarketDataWindowViolation | None:
    if asset_class == "equity":
        if start_date < ALPACA_EQUITY_HISTORY_START:
            return MarketDataWindowViolation(
                code="provider_history_start_unavailable",
                provider="alpaca",
                detail="Alpaca equity history starts in 2016 for this launch path.",
            )
        return None

    if asset_class == "currency_pair":
        interval = KRAKEN_OHLC_TIMEFRAME_MINUTES.get(timeframe)
        if interval is None:
            return MarketDataWindowViolation(
                code="provider_timeframe_unavailable",
                provider="kraken",
                detail="Kraken OHLC supports 1h, 4h, and 1D in this launch path.",
            )
        if (
            expected_candle_count(
                start_date=start_date,
                end_date=end_date,
                interval_minutes=interval,
            )
            > KRAKEN_MAX_OHLC_CANDLES
        ):
            return MarketDataWindowViolation(
                code="kraken_ohlc_window_exceeded",
                provider="kraken",
                detail="Kraken OHLC returns only the latest 720 candles.",
            )
    return None


def validate_market_data_window(
    *,
    asset_class: AssetClass,
    timeframe: str,
    start_date: date,
    end_date: date,
) -> None:
    violation = market_data_window_violation(
        asset_class=asset_class,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date,
    )
    if violation is not None:
        raise ValueError(violation.code)
