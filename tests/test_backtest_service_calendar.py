from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from typing import Any

import pandas as pd
import pytest
from argus.api import backtest_service
from argus.domain.market_data.capabilities import EquityMarketSession
from fastapi import HTTPException
from starlette.requests import Request


def test_direct_preflight_uses_one_calendar_for_a_complete_holiday_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    dates = [
        "2024-12-24",
        "2024-12-26",
        "2024-12-27",
        "2024-12-30",
        "2024-12-31",
        "2025-01-02",
    ]
    index = pd.to_datetime(dates, utc=True)
    close = pd.Series(range(100, 106), index=index, dtype=float)
    bars = pd.DataFrame(
        {
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1_000.0,
        },
        index=index,
    )
    calendar_calls: list[tuple[date, date]] = []

    def fake_calendar(*, start_date: date, end_date: date):
        calendar_calls.append((start_date, end_date))
        return tuple(
            EquityMarketSession(
                provider="alpaca",
                session_date=date.fromisoformat(day),
                opens_at=datetime.fromisoformat(f"{day}T09:30:00-05:00"),
                closes_at=datetime.fromisoformat(
                    f"{day}T{'13:00' if day == '2024-12-24' else '16:00'}:00-05:00"
                ),
            )
            for day in dates
        )

    def classify(symbol: str):
        return type(
            "ResolvedAsset",
            (),
            {"canonical_symbol": symbol, "asset_class": "equity", "symbol": symbol},
        )()

    monkeypatch.setattr(backtest_service, "classify_symbol", classify)
    monkeypatch.setattr(backtest_service.domain_engine, "classify_symbol", classify)
    monkeypatch.setattr(
        backtest_service.domain_engine,
        "fetch_ohlcv",
        lambda **_: bars.copy(deep=True),
    )
    monkeypatch.setattr(
        backtest_service,
        "_market_calendar_for_preflight",
        lambda: fake_calendar,
    )
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/backtests/run",
            "headers": [],
        }
    )
    request.state.request_id = "calendar-success"
    payload: dict[str, Any] = {
        "template": "buy_and_hold",
        "asset_class": "equity",
        "symbols": ["AAPL"],
        "timeframe": "1D",
        "start_date": dates[0],
        "end_date": dates[-1],
        "side": "long",
        "starting_capital": 10_000.0,
        "allocation_method": "equal_weight",
        "benchmark_symbol": "SPY",
        "parameters": {},
    }

    prepared = backtest_service.prepare_run_from_payload(payload, request)

    assert prepared.market_data.outcome == "full_coverage"
    assert calendar_calls == [(date(2024, 12, 24), date(2025, 1, 2))]


def test_direct_live_preflight_fails_closed_when_calendar_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dates = [
        "2024-12-24",
        "2024-12-26",
        "2024-12-27",
        "2024-12-30",
        "2024-12-31",
        "2025-01-02",
    ]
    index = pd.to_datetime(dates, utc=True)
    close = pd.Series(range(100, 106), index=index, dtype=float)
    bars = pd.DataFrame(
        {
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1_000.0,
        },
        index=index,
    )
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    calendar_calls = 0
    artifact_calls: Counter[str] = Counter()

    def classify(symbol: str):
        return type(
            "ResolvedAsset",
            (),
            {"canonical_symbol": symbol, "asset_class": "equity", "symbol": symbol},
        )()

    monkeypatch.setattr(
        backtest_service,
        "classify_symbol",
        classify,
    )
    monkeypatch.setattr(backtest_service.domain_engine, "classify_symbol", classify)
    monkeypatch.setattr(
        backtest_service.domain_engine,
        "fetch_ohlcv",
        lambda **_: bars.copy(deep=True),
    )

    def unavailable_calendar(**_: object) -> tuple[EquityMarketSession, ...]:
        nonlocal calendar_calls
        calendar_calls += 1
        raise ValueError("provider-specific calendar failure")

    monkeypatch.setattr(
        backtest_service,
        "_market_calendar_for_preflight",
        lambda: unavailable_calendar,
        raising=False,
    )

    def unexpected_artifact_call(kind: str):
        def fail(*_: object, **__: object):
            artifact_calls[kind] += 1
            raise AssertionError(f"{kind} must not run after calendar failure")

        return fail

    monkeypatch.setattr(
        backtest_service,
        "compute_alpha_metrics",
        unexpected_artifact_call("metrics"),
    )
    monkeypatch.setattr(
        backtest_service,
        "build_result_chart",
        unexpected_artifact_call("chart"),
    )
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/backtests/run",
            "headers": [],
        }
    )
    request.state.request_id = "calendar-unavailable"
    payload: dict[str, Any] = {
        "template": "buy_and_hold",
        "asset_class": "equity",
        "symbols": ["AAPL"],
        "timeframe": "1D",
        "start_date": dates[0],
        "end_date": dates[-1],
        "side": "long",
        "starting_capital": 10_000.0,
        "allocation_method": "equal_weight",
        "benchmark_symbol": "SPY",
        "parameters": {},
    }

    with pytest.raises(HTTPException) as exc_info:
        backtest_service.create_run_from_payload(payload, request)

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["code"] == "market_data_unavailable"
    assert calendar_calls == 1
    assert artifact_calls == Counter()
