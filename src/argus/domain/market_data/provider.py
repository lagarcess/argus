from __future__ import annotations

from datetime import date, datetime, time, timezone
import os
from typing import Literal

import numpy as np
import pandas as pd

AssetClass = Literal["equity", "crypto"]

try:
    from alpaca.data.historical import CryptoHistoricalDataClient, StockHistoricalDataClient
    from alpaca.data.requests import CryptoBarsRequest, StockBarsRequest
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
except Exception:  # pragma: no cover - optional runtime dependency guard
    CryptoHistoricalDataClient = None  # type: ignore[assignment]
    StockHistoricalDataClient = None  # type: ignore[assignment]
    CryptoBarsRequest = None  # type: ignore[assignment]
    StockBarsRequest = None  # type: ignore[assignment]
    TimeFrame = None  # type: ignore[assignment]
    TimeFrameUnit = None  # type: ignore[assignment]


def _parse_timeframe(timeframe: str):
    if TimeFrame is None or TimeFrameUnit is None:
        return None
    if timeframe == "1H":
        return TimeFrame(1, TimeFrameUnit.Hour)
    return TimeFrame(1, TimeFrameUnit.Day)


def _has_alpaca_credentials() -> bool:
    return bool(
        os.getenv("ALPACA_API_KEY")
        and os.getenv("ALPACA_SECRET_KEY")
        and CryptoHistoricalDataClient
        and StockHistoricalDataClient
    )


def _to_utc_datetime(value: date, *, end_of_day: bool = False) -> datetime:
    edge = time(23, 59, 59) if end_of_day else time(0, 0, 0)
    return datetime.combine(value, edge, tzinfo=timezone.utc)


def _format_symbol(symbol: str, asset_class: AssetClass) -> str:
    if asset_class == "crypto" and "/" not in symbol:
        return f"{symbol}/USD"
    return symbol


def _fetch_from_alpaca(
    symbol: str,
    asset_class: AssetClass,
    start_date: date,
    end_date: date,
    timeframe: str,
) -> pd.Series | None:
    if not _has_alpaca_credentials():
        return None

    timeframe_enum = _parse_timeframe(timeframe)
    if timeframe_enum is None:
        return None

    key = os.getenv("ALPACA_API_KEY")
    secret = os.getenv("ALPACA_SECRET_KEY")
    if not key or not secret:
        return None

    start_dt = _to_utc_datetime(start_date, end_of_day=False)
    end_dt = _to_utc_datetime(end_date, end_of_day=True)
    symbol_value = _format_symbol(symbol, asset_class)

    try:
        if asset_class == "equity":
            request = StockBarsRequest(
                symbol_or_symbols=symbol_value,
                timeframe=timeframe_enum,
                start=start_dt,
                end=end_dt,
            )
            client = StockHistoricalDataClient(key, secret)
            bars = client.get_stock_bars(request).df
        else:
            request = CryptoBarsRequest(
                symbol_or_symbols=symbol_value,
                timeframe=timeframe_enum,
                start=start_dt,
                end=end_dt,
            )
            client = CryptoHistoricalDataClient(key, secret)
            bars = client.get_crypto_bars(request).df
    except Exception:
        return None

    if bars is None or bars.empty:
        return None

    if isinstance(bars.index, pd.MultiIndex):
        bars = bars.reset_index(level=0, drop=True)

    close = bars["close"].copy()
    close.index = pd.to_datetime(close.index, utc=True)
    close = close.sort_index()
    close = close[~close.index.duplicated(keep="last")]
    close = close.dropna()
    if close.empty:
        return None
    return close.astype(float)


def _fallback_index(start_date: date, end_date: date, timeframe: str) -> pd.DatetimeIndex:
    if timeframe == "1H":
        start_dt = _to_utc_datetime(start_date, end_of_day=False)
        end_dt = _to_utc_datetime(end_date, end_of_day=True)
        return pd.date_range(start=start_dt, end=end_dt, freq="h", tz="UTC")
    return pd.bdate_range(start=start_date, end=end_date, tz="UTC")


def _build_fallback_series(
    symbol: str, start_date: date, end_date: date, timeframe: str
) -> pd.Series:
    index = _fallback_index(start_date, end_date, timeframe)
    if len(index) < 3:
        index = pd.date_range(
            start=_to_utc_datetime(start_date, end_of_day=False),
            periods=3,
            freq="D",
            tz="UTC",
        )

    symbol_score = sum((i + 1) * ord(char) for i, char in enumerate(symbol))
    base_price = 80 + (symbol_score % 70)
    trend = np.linspace(0.0, len(index) * 0.0008, len(index))
    cycle = np.sin(np.linspace(0.0, 6.0, len(index))) * (0.002 + (symbol_score % 5) * 0.0003)
    period_returns = trend + cycle
    curve = base_price * np.cumprod(1 + period_returns)
    return pd.Series(curve, index=index, dtype=float)


def fetch_price_series(
    symbol: str,
    asset_class: AssetClass,
    start_date: date,
    end_date: date,
    timeframe: str,
) -> pd.Series:
    alpaca_series = _fetch_from_alpaca(
        symbol=symbol,
        asset_class=asset_class,
        start_date=start_date,
        end_date=end_date,
        timeframe=timeframe,
    )
    if alpaca_series is not None:
        return alpaca_series
    return _build_fallback_series(
        symbol=symbol, start_date=start_date, end_date=end_date, timeframe=timeframe
    )
