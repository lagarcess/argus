from __future__ import annotations

import argus.domain.engine as engine
import pandas as pd
import pytest
from argus.domain.engine import (
    _build_long_only_execution_ledger,
    _chart_markers_from_events,
    _collect_execution_fill_events,
    _execution_fill_count,
)


def test_long_only_ledger_ignores_exit_signals_while_flat() -> None:
    index = pd.date_range("2024-01-01", periods=5, freq="D")
    entries = pd.Series([False, False, True, False, False], index=index)
    exits = pd.Series([True, True, False, False, True], index=index)

    ledger = _build_long_only_execution_ledger(
        symbol="AAPL",
        entries=entries,
        exits=exits,
        allow_accumulation=False,
    )

    fills = [event for event in ledger if event.event_type == "fill"]
    ignored = [event for event in ledger if event.event_type == "ignored_signal"]

    assert [(event.side, event.timestamp) for event in fills] == [
        ("buy", index[2]),
        ("sell", index[4]),
    ]
    assert [(event.side, event.reason) for event in ignored] == [
        ("sell", "exit_signal_while_flat"),
        ("sell", "exit_signal_while_flat"),
    ]


def test_chart_markers_use_executed_fills_not_raw_signals() -> None:
    index = pd.date_range("2024-01-01", periods=4, freq="D")
    entries = pd.Series([False, True, False, False], index=index)
    exits = pd.Series([True, False, False, True], index=index)
    ledger = _build_long_only_execution_ledger(
        symbol="AAPL",
        entries=entries,
        exits=exits,
        allow_accumulation=False,
    )
    events: dict[str, dict[str, set[str]]] = {}

    _collect_execution_fill_events(events, symbol="AAPL", execution_events=ledger)
    markers = _chart_markers_from_events(events)

    assert [marker["type"] for marker in markers] == ["entry", "exit"]
    assert markers[0]["time"] == "2024-01-02"
    assert markers[0]["label"] == "Buy AAPL"


def test_long_only_ledger_blocks_duplicate_full_position_buys() -> None:
    index = pd.date_range("2024-01-01", periods=4, freq="D")
    entries = pd.Series([True, True, True, False], index=index)
    exits = pd.Series([False, False, False, True], index=index)

    ledger = _build_long_only_execution_ledger(
        symbol="AAPL",
        entries=entries,
        exits=exits,
        allow_accumulation=False,
    )

    assert _execution_fill_count(ledger) == 2
    assert _execution_fill_count(ledger, side="buy") == 1
    ignored_buys = [
        event
        for event in ledger
        if event.event_type == "ignored_signal" and event.side == "buy"
    ]
    assert [event.reason for event in ignored_buys] == [
        "entry_signal_while_already_long",
        "entry_signal_while_already_long",
    ]


def test_dca_ledger_allows_accumulating_buy_fills() -> None:
    index = pd.date_range("2024-01-01", periods=4, freq="D")
    entries = pd.Series([True, True, True, False], index=index)
    exits = pd.Series([False, False, False, False], index=index)

    ledger = _build_long_only_execution_ledger(
        symbol="BTC",
        entries=entries,
        exits=exits,
        allow_accumulation=True,
    )

    buy_fills = [
        event for event in ledger if event.event_type == "fill" and event.side == "buy"
    ]
    assert [event.action for event in buy_fills] == ["open", "add", "add"]
    assert _execution_fill_count(ledger, side="buy") == 3


def test_result_chart_markers_are_executed_fills(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index = pd.date_range("2024-01-01", periods=4, freq="D")
    bars = pd.DataFrame({"close": [100.0, 95.0, 105.0, 110.0]}, index=index)
    entries = pd.Series([False, True, False, False], index=index)
    exits = pd.Series([True, False, False, True], index=index)

    monkeypatch.setattr(engine, "fetch_ohlcv", lambda **_: bars)
    monkeypatch.setattr(engine, "_build_signals", lambda *_: (entries, exits))

    chart = engine.build_result_chart(
        {
            "template": "rsi_mean_reversion",
            "symbols": ["AAPL"],
            "asset_class": "equity",
            "start_date": "2024-01-01",
            "end_date": "2024-01-04",
            "timeframe": "1D",
            "starting_capital": 10000.0,
            "parameters": {},
            "benchmark": "SPY",
        }
    )

    assert [marker["type"] for marker in chart["markers"]] == ["entry", "exit"]
    assert chart["markers"][0]["time"] == "2024-01-02"


def test_result_chart_includes_strategy_portfolio_value_range(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index = pd.date_range("2024-01-01", periods=3, freq="D")
    bars = pd.DataFrame({"close": [100.0, 200.0, 50.0]}, index=index)
    entries = pd.Series([True, False, False], index=index)
    exits = pd.Series([False, False, False], index=index)

    monkeypatch.setattr(engine, "fetch_ohlcv", lambda **_: bars)
    monkeypatch.setattr(engine, "_build_signals", lambda *_: (entries, exits))

    chart = engine.build_result_chart(
        {
            "template": "rsi_mean_reversion",
            "symbols": ["AAPL"],
            "asset_class": "equity",
            "start_date": "2024-01-01",
            "end_date": "2024-01-03",
            "timeframe": "1D",
            "starting_capital": 10000.0,
            "parameters": {},
            "benchmark": "SPY",
        }
    )

    assert chart["value_summary"] == {
        "peak_value": 20000.0,
        "lowest_value": 5000.0,
        "currency": "USD",
        "source": "strategy_portfolio_equity_close",
    }


def test_metrics_trade_count_uses_executed_fills(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index = pd.date_range("2024-01-01", periods=5, freq="D")
    bars = pd.DataFrame({"close": [100.0, 95.0, 96.0, 110.0, 105.0]}, index=index)
    entries = pd.Series([True, True, True, False, False], index=index)
    exits = pd.Series([False, False, False, True, False], index=index)

    monkeypatch.setattr(engine, "fetch_ohlcv", lambda **_: bars)
    monkeypatch.setattr(engine, "_build_signals", lambda *_: (entries, exits))
    monkeypatch.setattr(
        engine,
        "build_benchmark_curve",
        lambda *_, **__: {"equity_curve": [1.0, 1.0, 1.0, 1.0, 1.0]},
    )

    metrics = engine.compute_alpha_metrics(
        {
            "template": "rsi_mean_reversion",
            "symbols": ["AAPL"],
            "asset_class": "equity",
            "start_date": "2024-01-01",
            "end_date": "2024-01-05",
            "timeframe": "1D",
            "starting_capital": 10000.0,
            "parameters": {},
            "benchmark": "SPY",
        }
    )

    assert metrics["by_symbol"]["AAPL"]["efficiency"]["total_trades"] == 2
    assert metrics["aggregate"]["efficiency"]["total_trades"] == 2
    assert metrics["aggregate"]["performance"]["portfolio_value_range"] == {
        "peak_value": 11000.0,
        "lowest_value": 9500.0,
        "currency": "USD",
        "source": "strategy_portfolio_equity_close",
    }
