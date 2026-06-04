from __future__ import annotations

from datetime import date, datetime

from argus.domain.market_data.capabilities import (
    MarketClockSnapshot,
    latest_complete_data_adjustment,
)


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

