from __future__ import annotations

from datetime import date, datetime

import pytest
from argus.domain.market_data.capabilities import (
    MarketClockSnapshot,
    latest_complete_data_adjustment,
)


def _clock(timestamp: str, *, is_open: bool) -> MarketClockSnapshot:
    return MarketClockSnapshot(
        provider="alpaca",
        timestamp=datetime.fromisoformat(timestamp),
        is_open=is_open,
        is_market_day=True,
    )


@pytest.mark.parametrize(
    ("clock_timestamp", "is_open", "expected_through"),
    [
        # Mid-session Wednesday: today's daily bar is still forming.
        ("2026-08-12T15:56:00+00:00", True, "2026-08-11"),
        # After the close, same Eastern day: corrections can still land.
        ("2026-08-12T21:34:00+00:00", False, "2026-08-11"),
        # 21:00 ET Wednesday is Thursday in UTC; the Eastern date governs.
        ("2026-08-13T01:00:00+00:00", False, "2026-08-11"),
        # Eastern midnight passed: Wednesday's bar is final.
        ("2026-08-13T04:30:00+00:00", False, "2026-08-12"),
    ],
)
def test_equity_daily_completion_follows_the_eastern_date(
    clock_timestamp: str,
    is_open: bool,
    expected_through: str,
) -> None:
    adjustment = latest_complete_data_adjustment(
        asset_class="equity",
        timeframe="1D",
        end_date=date.fromisoformat("2026-08-12"),
        today=date.fromisoformat("2026-08-12"),
        clock=_clock(clock_timestamp, is_open=is_open),
    )

    if expected_through == "2026-08-12":
        assert adjustment is None
    else:
        assert adjustment is not None
        assert adjustment.through.isoformat() == expected_through
        assert adjustment.kind == "latest_complete_daily_data"


def test_equity_daily_completion_without_a_clock_uses_the_prior_session() -> None:
    adjustment = latest_complete_data_adjustment(
        asset_class="equity",
        timeframe="1D",
        end_date=date.fromisoformat("2026-08-10"),
        today=date.fromisoformat("2026-08-10"),
    )

    assert adjustment is not None
    assert adjustment.through.isoformat() == "2026-08-07"


def test_equity_intraday_keeps_the_open_session_available() -> None:
    adjustment = latest_complete_data_adjustment(
        asset_class="equity",
        timeframe="1h",
        end_date=date.fromisoformat("2026-08-12"),
        today=date.fromisoformat("2026-08-12"),
        clock=_clock("2026-08-12T15:56:00+00:00", is_open=True),
    )

    assert adjustment is None
