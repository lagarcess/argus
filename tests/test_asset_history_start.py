"""An asset's history starts on its own first daily bar, never on the provider's
floor; when market data cannot say, nothing states a start."""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import pytest
from argus.domain.market_data import (
    asset_history_start,
    clear_tradable_history_cache,
    shared_history_start,
)
from argus.domain.market_data import provider as provider_module
from argus.domain.market_data.capabilities import ALPACA_EQUITY_HISTORY_START


@pytest.fixture(autouse=True)
def _fresh_cache() -> None:
    clear_tradable_history_cache()


def _series(first: str) -> pd.Series:
    index = pd.date_range(first, periods=3, freq="D", tz="UTC")
    return pd.Series([1.0, 2.0, 3.0], index=index)


def _install(monkeypatch: pytest.MonkeyPatch, handler: Any) -> list[tuple[Any, ...]]:
    calls: list[tuple[Any, ...]] = []

    def fetch(symbol: str, asset_class: str, start: date, end: date, timeframe: str) -> pd.Series:
        calls.append((symbol, asset_class, start, end, timeframe))
        return handler(symbol)

    monkeypatch.setattr(provider_module, "fetch_price_series", fetch)
    return calls


def test_a_later_listing_starts_on_its_first_bar_and_is_cached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _install(monkeypatch, lambda symbol: _series("2021-03-24"))

    assert asset_history_start("docn", "equity") == date(2021, 3, 24)
    assert asset_history_start("DOCN", "equity") == date(2021, 3, 24)

    assert len(calls) == 1
    # The probe asks from the provider's floor, so the first bar is the asset's own.
    assert calls[0][2] == ALPACA_EQUITY_HISTORY_START


@pytest.mark.parametrize("asset_class", ["crypto", "currency_pair"])
def test_rolling_window_feeds_state_no_start(
    monkeypatch: pytest.MonkeyPatch, asset_class: str
) -> None:
    calls = _install(monkeypatch, lambda symbol: _series("2024-01-01"))

    assert asset_history_start("BTC", asset_class) is None
    assert calls == []


def test_an_outage_states_no_start_and_is_asked_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(symbol: str) -> pd.Series:
        raise ValueError("market_data_unavailable")

    calls = _install(monkeypatch, unavailable)

    assert asset_history_start("DOCN", "equity") is None
    assert asset_history_start("DOCN", "equity") is None
    assert len(calls) == 2


def test_a_run_shares_the_latest_start_and_none_when_any_is_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    firsts = {"SPY": "2016-01-04", "DOCN": "2021-03-24"}

    def series(symbol: str) -> pd.Series:
        if symbol not in firsts:
            raise ValueError("market_data_unavailable")
        return _series(firsts[symbol])

    _install(monkeypatch, series)

    assert shared_history_start(["SPY", "DOCN"], "equity") == date(2021, 3, 24)
    assert shared_history_start(["SPY", "NOPE"], "equity") is None
    assert shared_history_start([], "equity") is None
