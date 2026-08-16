"""Real NYSE sessions for 2024, as the coverage-owned calendar type.

Synthetic market-data fixtures in this repo put bars on weekends and holidays,
so date logic passes green against them and breaks on a real exchange. These
are the actual 2024 NYSE closures and early closes, enumerated rather than
derived, so a test that says "the next trading day" is measured against days
the exchange really was shut.

Sessions are built as ``EquityMarketSession`` because that is the calendar
truth market-data coverage already owns; nothing here is a second calendar.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pandas as pd
from argus.domain.market_data.capabilities import EquityMarketSession

# The 2024 NYSE full-day closures.
NYSE_2024_HOLIDAYS: frozenset[date] = frozenset(
    {
        date(2024, 1, 1),  # New Year's Day
        date(2024, 1, 15),  # Martin Luther King Jr. Day
        date(2024, 2, 19),  # Washington's Birthday
        date(2024, 3, 29),  # Good Friday
        date(2024, 5, 27),  # Memorial Day
        date(2024, 6, 19),  # Juneteenth
        date(2024, 7, 4),  # Independence Day
        date(2024, 9, 2),  # Labor Day
        date(2024, 11, 28),  # Thanksgiving
        date(2024, 12, 25),  # Christmas
    }
)

# The 2024 NYSE 1:00 p.m. early closes.
NYSE_2024_EARLY_CLOSES: frozenset[date] = frozenset(
    {
        date(2024, 7, 3),
        date(2024, 11, 29),
        date(2024, 12, 24),
    }
)

_REGULAR_OPEN = time(9, 30)
_REGULAR_CLOSE = time(16, 0)
_EARLY_CLOSE = time(13, 0)


def is_nyse_session(day: date) -> bool:
    return day.weekday() < 5 and day not in NYSE_2024_HOLIDAYS


def nyse_session_dates(start: date, end: date) -> tuple[date, ...]:
    days: list[date] = []
    current = start
    while current <= end:
        if is_nyse_session(current):
            days.append(current)
        current += timedelta(days=1)
    return tuple(days)


def next_nyse_session(day: date) -> date:
    current = day
    while not is_nyse_session(current):
        current += timedelta(days=1)
    return current


def nyse_market_calendar(
    *,
    start_date: date,
    end_date: date,
) -> tuple[EquityMarketSession, ...]:
    """A ``fetch_market_calendar_func`` backed by the real 2024 session list."""
    return tuple(
        EquityMarketSession(
            provider="nyse-2024",
            session_date=session_date,
            opens_at=datetime.combine(session_date, _REGULAR_OPEN),
            closes_at=datetime.combine(
                session_date,
                _EARLY_CLOSE if session_date in NYSE_2024_EARLY_CLOSES else _REGULAR_CLOSE,
            ),
        )
        for session_date in nyse_session_dates(start_date, end_date)
    )


def nyse_session_index(start: date, end: date) -> pd.DatetimeIndex:
    """Daily bars that exist only on days the exchange was open."""
    return pd.DatetimeIndex(
        [pd.Timestamp(session_date) for session_date in nyse_session_dates(start, end)]
    )
