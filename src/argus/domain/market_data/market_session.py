"""Which session US equities are in right now, in Eastern time.

Two rules this module exists to hold.

Session is Eastern, never the caller's clock. Someone in London at 2pm is in US
pre-market, and a local-time calculation gets that backwards.

Closure comes from the trading calendar, never from a weekday check. The
calendar is what knows a Thursday in November is shut. The weekday is consulted
only after the calendar has already said the market is closed, and only to
choose which kind of closure to name.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Literal
from zoneinfo import ZoneInfo

from argus.domain.market_data.capabilities import (
    EquityMarketSession,
    fetch_alpaca_market_calendar,
)

EASTERN = ZoneInfo("America/New_York")

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

    Cached by date rather than by elapsed time: a past or present calendar day's
    session never changes, so there is no TTL to guess at and one provider call
    covers the whole day.
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

    None is a real answer rather than a guess. Callers that speak about the
    market say nothing about it instead of inventing an open or a holiday.
    """
    if (
        os.getenv("ARGUS_MARKET_DATA_PROVIDER_MODE") or "live_provider"
    ).strip().lower() == "synthetic_unit_fixture":
        return None
    at = now or _now_eastern()
    if at.tzinfo is None:
        # astimezone would read a naive value as system local time, which is the
        # local-clock mistake this module exists to prevent, one layer down.
        raise ValueError("market_session_requires_aware_datetime")
    at = at.astimezone(EASTERN)
    try:
        session = _session_for(at.date())
    except Exception:
        return None

    if session is None:
        # The calendar has already ruled today closed. Saturday and Sunday only
        # decide whether to call it a weekend or a holiday.
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
