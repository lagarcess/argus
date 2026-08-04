from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace

import pytest
from argus.domain.market_data.capabilities import (
    MarketClockSnapshot,
    fetch_alpaca_market_calendar,
    latest_complete_data_adjustment,
)


def test_fetch_alpaca_market_calendar_uses_one_bounded_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    monkeypatch.setenv("ALPACA_API_KEY", "test-key")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "test-secret")
    requests: list[object] = []

    class FakeTradingClient:
        def __init__(self, **_: object) -> None:
            pass

        def get_calendar(self, filters: object) -> list[SimpleNamespace]:
            requests.append(filters)
            return [
                SimpleNamespace(
                    date=date(2024, 11, 27),
                    open=datetime.fromisoformat("2024-11-27T09:30:00-05:00"),
                    close=datetime.fromisoformat("2024-11-27T16:00:00-05:00"),
                ),
                SimpleNamespace(
                    date=date(2024, 11, 29),
                    open=datetime.fromisoformat("2024-11-29T09:30:00-05:00"),
                    close=datetime.fromisoformat("2024-11-29T13:00:00-05:00"),
                ),
            ]

    monkeypatch.setattr("alpaca.trading.client.TradingClient", FakeTradingClient)

    sessions = fetch_alpaca_market_calendar(
        start_date=date(2024, 11, 27),
        end_date=date(2024, 11, 29),
    )

    assert len(requests) == 1
    assert requests[0].start == date(2024, 11, 27)
    assert requests[0].end == date(2024, 11, 29)
    assert [(session.session_date, session.closes_at.hour) for session in sessions] == [
        (date(2024, 11, 27), 16),
        (date(2024, 11, 29), 13),
    ]


def test_synthetic_mode_never_constructs_an_alpaca_calendar_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "synthetic_unit_fixture")
    monkeypatch.setenv("ALPACA_API_KEY", "test-key")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "test-secret")
    client_constructions = 0

    class UnexpectedTradingClient:
        def __init__(self, **_: object) -> None:
            nonlocal client_constructions
            client_constructions += 1

    monkeypatch.setattr("alpaca.trading.client.TradingClient", UnexpectedTradingClient)

    with pytest.raises(ValueError, match="market_calendar_unavailable"):
        fetch_alpaca_market_calendar(
            start_date=date(2024, 11, 27),
            end_date=date(2024, 11, 29),
        )

    assert client_constructions == 0


def test_latest_complete_daily_equity_uses_prior_session_before_market_open() -> None:
    adjustment = latest_complete_data_adjustment(
        asset_class="equity",
        timeframe="1D",
        end_date=date(2026, 6, 3),
        today=date(2026, 6, 3),
        clock=MarketClockSnapshot(
            provider="alpaca",
            timestamp=datetime.fromisoformat("2026-06-03T02:00:00-04:00"),
            is_open=False,
            next_open=datetime.fromisoformat("2026-06-03T09:30:00-04:00"),
            next_close=datetime.fromisoformat("2026-06-03T16:00:00-04:00"),
            is_market_day=True,
        ),
    )

    assert adjustment is not None
    assert adjustment.metadata == {
        "kind": "latest_complete_daily_data",
        "original_end": "2026-06-03",
        "provider": "alpaca",
        "through": "2026-06-02",
        "timeframe": "1D",
    }


def test_latest_complete_intraday_equity_uses_clock_before_market_open() -> None:
    adjustment = latest_complete_data_adjustment(
        asset_class="equity",
        timeframe="1h",
        end_date=date(2026, 6, 3),
        today=date(2026, 6, 3),
        clock=MarketClockSnapshot(
            provider="alpaca",
            timestamp=datetime.fromisoformat("2026-06-03T02:00:00-04:00"),
            is_open=False,
            next_open=datetime.fromisoformat("2026-06-03T09:30:00-04:00"),
            next_close=datetime.fromisoformat("2026-06-03T16:00:00-04:00"),
            is_market_day=True,
        ),
    )

    assert adjustment is not None
    assert adjustment.metadata == {
        "kind": "latest_complete_market_data",
        "original_end": "2026-06-03",
        "provider": "alpaca",
        "through": "2026-06-02",
        "timeframe": "1h",
    }


def test_latest_complete_intraday_equity_allows_today_after_market_close() -> None:
    adjustment = latest_complete_data_adjustment(
        asset_class="equity",
        timeframe="1h",
        end_date=date(2026, 6, 3),
        today=date(2026, 6, 3),
        clock=MarketClockSnapshot(
            provider="alpaca",
            timestamp=datetime.fromisoformat("2026-06-03T17:00:00-04:00"),
            is_open=False,
            next_open=datetime.fromisoformat("2026-06-04T09:30:00-04:00"),
            next_close=datetime.fromisoformat("2026-06-04T16:00:00-04:00"),
            is_market_day=True,
        ),
    )

    assert adjustment is None


def test_latest_complete_intraday_crypto_allows_today() -> None:
    adjustment = latest_complete_data_adjustment(
        asset_class="crypto",
        timeframe="1h",
        end_date=date(2026, 6, 3),
        today=date(2026, 6, 3),
    )

    assert adjustment is None
