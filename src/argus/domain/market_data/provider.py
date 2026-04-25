from __future__ import annotations

import os
import time as time_module
from datetime import date, datetime, time, timezone
from functools import lru_cache
from typing import Literal

import joblib
import pandas as pd
from alpaca.common.enums import Sort
from alpaca.data.enums import Adjustment, DataFeed
from alpaca.data.historical import CryptoHistoricalDataClient, StockHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest, StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

AssetClass = Literal["equity", "crypto"]


def _cache_location() -> str | None:
    enabled = (os.getenv("ENABLE_MARKET_DATA_CACHE") or "true").strip().lower()
    if enabled in {"0", "false", "no", "off"}:
        return None
    return ".gemini/cache/market_data"


_memory = joblib.Memory(location=_cache_location(), verbose=0)


def _cache_ttl_seconds() -> int:
    raw = (os.getenv("MARKET_DATA_CACHE_TTL") or "900").strip()
    try:
        value = int(raw)
    except ValueError:
        value = 900
    return max(60, value)


def _to_utc_datetime(value: date, *, end_of_day: bool = False) -> datetime:
    edge = time(23, 59, 59) if end_of_day else time(0, 0, 0)
    return datetime.combine(value, edge, tzinfo=timezone.utc)


def _normalize_asset_class(asset_class: AssetClass) -> AssetClass:
    if asset_class == "equity":
        return "equity"
    return "crypto"


def _to_alpaca_symbol(symbol: str, asset_class: AssetClass) -> str:
    candidate = symbol.strip().upper().replace("-", "/")
    if asset_class == "crypto":
        if "/" in candidate:
            return candidate
        if candidate.endswith("USD") and len(candidate) > 3:
            return f"{candidate[:-3]}/USD"
        return f"{candidate}/USD"
    return candidate.replace("/", "")


def _parse_timeframe(timeframe: str) -> TimeFrame:
    normalized = timeframe.strip().lower()
    mapping: dict[str, TimeFrame] = {
        "1h": TimeFrame(1, TimeFrameUnit.Hour),
        "2h": TimeFrame(2, TimeFrameUnit.Hour),
        "4h": TimeFrame(4, TimeFrameUnit.Hour),
        "6h": TimeFrame(6, TimeFrameUnit.Hour),
        "12h": TimeFrame(12, TimeFrameUnit.Hour),
        "1d": TimeFrame(1, TimeFrameUnit.Day),
    }
    if normalized not in mapping:
        raise ValueError("unsupported_timeframe")
    return mapping[normalized]


@lru_cache()
def _stock_client() -> StockHistoricalDataClient:
    key = (os.getenv("ALPACA_API_KEY") or "").strip()
    secret = (os.getenv("ALPACA_SECRET_KEY") or "").strip()
    if not key or not secret:
        raise ValueError("market_data_unavailable")
    return StockHistoricalDataClient(api_key=key, secret_key=secret)


@lru_cache()
def _crypto_client() -> CryptoHistoricalDataClient:
    key = (os.getenv("ALPACA_API_KEY") or "").strip()
    secret = (os.getenv("ALPACA_SECRET_KEY") or "").strip()
    if not key or not secret:
        raise ValueError("market_data_unavailable")
    return CryptoHistoricalDataClient(api_key=key, secret_key=secret)


def _normalize_df(df: pd.DataFrame, *, symbol: str) -> pd.DataFrame:
    if df is None or df.empty:
        raise ValueError("market_data_unavailable")

    if isinstance(df.index, pd.MultiIndex):
        df = df.reset_index(level=0, drop=True)
    df.index = pd.to_datetime(df.index, utc=True)
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]
    df.columns = [str(col).lower() for col in df.columns]

    required = {"open", "high", "low", "close", "volume"}
    if not required.issubset(df.columns):
        raise ValueError("market_data_unavailable")

    normalized = df.loc[:, ["open", "high", "low", "close", "volume"]].dropna()
    if normalized.empty:
        raise ValueError("market_data_unavailable")
    return normalized.astype(float)


def _fetch_bars_core(
    *,
    symbol: str,
    asset_class: AssetClass,
    timeframe: str,
    start_date: date,
    end_date: date,
    cache_bin: int | None = None,  # part of cached signature
) -> pd.DataFrame:
    timeframe_enum = _parse_timeframe(timeframe)
    start_dt = _to_utc_datetime(start_date, end_of_day=False)
    end_dt = _to_utc_datetime(end_date, end_of_day=True)
    alpaca_symbol = _to_alpaca_symbol(symbol, asset_class)

    try:
        if _normalize_asset_class(asset_class) == "equity":
            request = StockBarsRequest(
                symbol_or_symbols=alpaca_symbol,
                timeframe=timeframe_enum,
                start=start_dt,
                end=end_dt,
                adjustment=Adjustment.SPLIT,
                feed=DataFeed.IEX,
                sort=Sort.ASC,
            )
            bars = _stock_client().get_stock_bars(request).df
        else:
            request = CryptoBarsRequest(
                symbol_or_symbols=alpaca_symbol,
                timeframe=timeframe_enum,
                start=start_dt,
                end=end_dt,
                sort=Sort.ASC,
            )
            bars = _crypto_client().get_crypto_bars(request).df
    except Exception as exc:  # pragma: no cover - network/API failure path
        raise ValueError("market_data_unavailable") from exc

    return _normalize_df(bars, symbol=alpaca_symbol)


_fetch_bars_cached = _memory.cache(_fetch_bars_core)


def _fetch_bars_with_ttl(
    *,
    symbol: str,
    asset_class: AssetClass,
    timeframe: str,
    start_date: date,
    end_date: date,
) -> pd.DataFrame:
    ttl = _cache_ttl_seconds()
    cache_bin = int(time_module.time()) // ttl
    return _fetch_bars_cached(
        symbol=symbol,
        asset_class=asset_class,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date,
        cache_bin=cache_bin,
    )


def fetch_ohlcv(
    symbol: str,
    asset_class: AssetClass,
    start_date: date,
    end_date: date,
    timeframe: str,
) -> pd.DataFrame:
    return _fetch_bars_with_ttl(
        symbol=symbol,
        asset_class=asset_class,
        start_date=start_date,
        end_date=end_date,
        timeframe=timeframe,
    )


def fetch_price_series(
    symbol: str,
    asset_class: AssetClass,
    start_date: date,
    end_date: date,
    timeframe: str,
) -> pd.Series:
    data = fetch_ohlcv(
        symbol=symbol,
        asset_class=asset_class,
        start_date=start_date,
        end_date=end_date,
        timeframe=timeframe,
    )
    return data["close"].copy()


def clear_market_data_cache() -> None:
    try:
        _fetch_bars_cached.clear()
    except Exception:
        pass
