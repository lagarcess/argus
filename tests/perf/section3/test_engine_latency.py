from __future__ import annotations

from datetime import date
from functools import lru_cache
from time import perf_counter, sleep

import pandas as pd
import pytest
from argus.domain import engine


def _bars_for_symbol(symbol: str) -> pd.DataFrame:
    index = pd.date_range("2023-01-01", "2025-12-30", freq="D", tz="UTC")
    bump = float(sum(ord(c) for c in symbol) % 20)
    close = pd.Series(100.0 + bump + (pd.RangeIndex(len(index)) * 0.05), index=index)
    return pd.DataFrame(
        {
            "open": close * 0.999,
            "high": close * 1.002,
            "low": close * 0.998,
            "close": close,
            "volume": 5000.0,
        },
        index=index,
    )


@pytest.fixture(autouse=True)
def _patch_provider_cache_behavior(monkeypatch: pytest.MonkeyPatch) -> None:
    @lru_cache(maxsize=32)
    def cached_loader(
        symbol: str,
        asset_class: str,  # noqa: ARG001
        start_date: date,
        end_date: date,
        timeframe: str,  # noqa: ARG001
    ) -> pd.DataFrame:
        sleep(0.01)
        frame = _bars_for_symbol(symbol)
        return frame.loc[
            (frame.index.date >= start_date) & (frame.index.date <= end_date)
        ].copy()

    def fake_fetch_ohlcv(
        symbol: str,
        asset_class: str,
        start_date: date,
        end_date: date,
        timeframe: str,
    ) -> pd.DataFrame:
        return cached_loader(symbol, asset_class, start_date, end_date, timeframe).copy()

    def fake_fetch_price_series(
        symbol: str,
        asset_class: str,
        start_date: date,
        end_date: date,
        timeframe: str,
    ) -> pd.Series:
        return fake_fetch_ohlcv(
            symbol=symbol,
            asset_class=asset_class,
            start_date=start_date,
            end_date=end_date,
            timeframe=timeframe,
        )["close"]

    monkeypatch.setattr(engine, "fetch_ohlcv", fake_fetch_ohlcv)
    monkeypatch.setattr(engine, "fetch_price_series", fake_fetch_price_series)


def _config() -> dict[str, object]:
    return {
        "template": "dca_accumulation",
        "asset_class": "equity",
        "symbols": ["AAPL", "MSFT", "NVDA", "TSLA", "SPY"],
        "timeframe": "1D",
        "start_date": "2023-01-01",
        "end_date": "2025-12-30",
        "side": "long",
        "starting_capital": 100000,
        "allocation_method": "equal_weight",
        "benchmark_symbol": "SPY",
        "parameters": {},
    }


@pytest.mark.slow
def test_five_symbol_three_year_run_under_latency_target() -> None:
    # Warm up vectorbt/pandas runtime artifacts before measuring steady-state latency.
    engine.compute_alpha_metrics(_config())

    started = perf_counter()
    metrics = engine.compute_alpha_metrics(_config())
    elapsed = perf_counter() - started

    assert elapsed < 3.0
    assert "aggregate" in metrics
    assert len(metrics["by_symbol"]) == 5


@pytest.mark.slow
def test_repeat_run_benefits_from_cached_data_path() -> None:
    started_one = perf_counter()
    engine.compute_alpha_metrics(_config())
    elapsed_one = perf_counter() - started_one

    started_two = perf_counter()
    engine.compute_alpha_metrics(_config())
    elapsed_two = perf_counter() - started_two

    assert elapsed_two < elapsed_one
