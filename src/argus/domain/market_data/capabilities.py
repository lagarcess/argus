from __future__ import annotations

from dataclasses import dataclass
from datetime import date
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


def expected_candle_count(
    *, start_date: date, end_date: date, interval_minutes: int
) -> int:
    span_minutes = max(0, int((end_date - start_date).total_seconds() // 60))
    full_day_minutes = 24 * 60
    return (span_minutes + full_day_minutes) // interval_minutes


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
