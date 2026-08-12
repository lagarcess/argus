"""Which session US equities are in right now.

Two rules this module holds: the session is resolved in Eastern time, never the
caller's clock; and closure comes from the trading calendar, never a weekday
check. The weekday is read only after the calendar has ruled the day shut, to
choose between a weekend and a holiday.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Literal

from argus.domain.market_data.capabilities import (
    EASTERN,
    EquityMarketSession,
    fetch_alpaca_market_calendar,
)

# Extended-hours bounds for US equities, Eastern. The regular open and close
# come from the calendar per session, because half days move them.
PRE_MARKET_OPENS_AT = time(4, 0)
AFTER_HOURS_CLOSES_AT = time(20, 0)

MarketSessionPhase = Literal[
    "pre_market",
    "open",
    "after_hours",
    "closed_weekend",
    "closed_holiday",
    "closed",
]


@dataclass(frozen=True)
class MarketSessionSnapshot:
    phase: MarketSessionPhase
    is_market_day: bool
    as_of: datetime


_calendar_by_date: dict[date, EquityMarketSession | None] = {}


def _now_eastern() -> datetime:
    return datetime.now(EASTERN)


def _session_for(session_date: date) -> EquityMarketSession | None:
    """The trading session for one Eastern date, or None when the market is shut.

    Cached by date, not elapsed time: a calendar day's session never changes.
    """
    if session_date in _calendar_by_date:
        return _calendar_by_date[session_date]
    sessions = fetch_alpaca_market_calendar(
        start_date=session_date, end_date=session_date
    )
    session = next(
        (entry for entry in sessions if entry.session_date == session_date), None
    )
    _calendar_by_date[session_date] = session
    return session


def reset_market_session_cache() -> None:
    """Test seam, and the hook a process restart already gives production."""
    _calendar_by_date.clear()


def resolve_market_session(
    *, now: datetime | None = None
) -> MarketSessionSnapshot | None:
    """The current session, or None when the calendar cannot be reached.

    Callers say nothing about the market rather than invent an open or a holiday.
    """
    if (
        os.getenv("ARGUS_MARKET_DATA_PROVIDER_MODE") or "live_provider"
    ).strip().lower() == "synthetic_unit_fixture":
        return None
    at = now or _now_eastern()
    if at.tzinfo is None:
        # astimezone would read a naive value as system local time.
        raise ValueError("market_session_requires_aware_datetime")
    at = at.astimezone(EASTERN)
    try:
        session = _session_for(at.date())
    except Exception:
        return None

    if session is None:
        # The calendar already ruled today closed; the weekday only names it.
        weekend = at.weekday() >= 5
        return MarketSessionSnapshot(
            phase="closed_weekend" if weekend else "closed_holiday",
            is_market_day=False,
            as_of=at,
        )

    opens_at = session.opens_at.astimezone(EASTERN)
    closes_at = session.closes_at.astimezone(EASTERN)
    if at < opens_at:
        phase: MarketSessionPhase = (
            "pre_market" if at.time() >= PRE_MARKET_OPENS_AT else "closed"
        )
    elif at < closes_at:
        phase = "open"
    else:
        phase = "after_hours" if at.time() < AFTER_HOURS_CLOSES_AT else "closed"
    return MarketSessionSnapshot(phase=phase, is_market_day=True, as_of=at)
