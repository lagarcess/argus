"""Session resolution in Eastern time, against a real trading calendar.

Both traps this covers have already cost the repo once. Synthetic fixtures put
bars on weekends and holidays, so date logic passed every test and broke on a
real exchange calendar; and a local-clock session calculation is backwards for
every user outside Eastern time.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest
from argus.domain.market_data import market_session as module
from argus.domain.market_data.capabilities import EquityMarketSession
from argus.domain.market_data.market_session import (
    EASTERN,
    reset_market_session_cache,
    resolve_market_session,
)

LONDON = ZoneInfo("Europe/London")


def _session(day: date, open_hour: int = 9, open_minute: int = 30, close_hour: int = 16):
    return EquityMarketSession(
        provider="alpaca",
        session_date=day,
        opens_at=datetime(
            day.year, day.month, day.day, open_hour, open_minute, tzinfo=EASTERN
        ),
        closes_at=datetime(day.year, day.month, day.day, close_hour, 0, tzinfo=EASTERN),
    )


@pytest.fixture(autouse=True)
def _clean_cache_and_live_mode(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")
    reset_market_session_cache()
    yield
    reset_market_session_cache()


def _calendar(sessions: dict[date, EquityMarketSession | None], calls: list[date]):
    def fetch(*, start_date: date, end_date: date):
        calls.append(start_date)
        session = sessions.get(start_date)
        return (session,) if session is not None else ()

    return fetch


def test_a_weekday_the_calendar_omits_is_a_holiday_not_a_weekday(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Thanksgiving 2026 is a Thursday. Nothing about the weekday says it is shut;
    # only the calendar does.
    thanksgiving = date(2026, 11, 26)
    assert thanksgiving.weekday() == 3
    monkeypatch.setattr(
        module, "fetch_alpaca_market_calendar", _calendar({thanksgiving: None}, [])
    )

    snapshot = resolve_market_session(now=datetime(2026, 11, 26, 11, 0, tzinfo=EASTERN))

    assert snapshot is not None
    assert snapshot.phase == "closed_holiday"
    assert snapshot.is_market_day is False


def test_a_weekend_the_calendar_omits_is_named_a_weekend() -> None:
    saturday = date(2026, 8, 8)
    assert saturday.weekday() == 5
    snapshot = None
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            module, "fetch_alpaca_market_calendar", _calendar({saturday: None}, [])
        )
        snapshot = resolve_market_session(now=datetime(2026, 8, 8, 11, 0, tzinfo=EASTERN))

    assert snapshot is not None
    assert snapshot.phase == "closed_weekend"
    assert snapshot.is_market_day is False


def test_session_is_eastern_even_when_the_caller_is_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 2pm in London is 9am in New York, which is pre-market, not open. A
    # local-clock calculation calls this the middle of the trading day.
    trading_day = date(2026, 8, 10)
    monkeypatch.setattr(
        module,
        "fetch_alpaca_market_calendar",
        _calendar({trading_day: _session(trading_day)}, []),
    )

    snapshot = resolve_market_session(now=datetime(2026, 8, 10, 14, 0, tzinfo=LONDON))

    assert snapshot is not None
    assert snapshot.phase == "pre_market"
    assert snapshot.as_of.tzinfo is EASTERN
    assert snapshot.as_of.hour == 9


@pytest.mark.parametrize(
    ("hour", "minute", "expected"),
    [
        (3, 30, "closed"),
        (4, 0, "pre_market"),
        (9, 29, "pre_market"),
        (9, 30, "open"),
        (15, 59, "open"),
        (16, 0, "after_hours"),
        (19, 59, "after_hours"),
        (20, 0, "closed"),
    ],
)
def test_extended_hours_bound_the_phases(
    monkeypatch: pytest.MonkeyPatch, hour: int, minute: int, expected: str
) -> None:
    trading_day = date(2026, 8, 10)
    monkeypatch.setattr(
        module,
        "fetch_alpaca_market_calendar",
        _calendar({trading_day: _session(trading_day)}, []),
    )

    snapshot = resolve_market_session(
        now=datetime(2026, 8, 10, hour, minute, tzinfo=EASTERN)
    )

    assert snapshot is not None
    assert snapshot.phase == expected
    assert snapshot.is_market_day is True


def test_a_half_day_closes_when_the_calendar_says_so(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The early close is why the regular bounds come from the calendar per
    # session rather than from a constant 16:00.
    half_day = date(2026, 11, 27)
    monkeypatch.setattr(
        module,
        "fetch_alpaca_market_calendar",
        _calendar({half_day: _session(half_day, close_hour=13)}, []),
    )

    snapshot = resolve_market_session(now=datetime(2026, 11, 27, 14, 0, tzinfo=EASTERN))

    assert snapshot is not None
    assert snapshot.phase == "after_hours"


def test_one_calendar_call_covers_the_whole_day(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trading_day = date(2026, 8, 10)
    calls: list[date] = []
    monkeypatch.setattr(
        module,
        "fetch_alpaca_market_calendar",
        _calendar({trading_day: _session(trading_day)}, calls),
    )

    for hour in (5, 10, 17):
        resolve_market_session(now=datetime(2026, 8, 10, hour, tzinfo=EASTERN))

    assert calls == [trading_day]


def test_an_unreachable_calendar_resolves_to_nothing_rather_than_a_guess(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(*, start_date: date, end_date: date):
        raise ValueError("market_calendar_unavailable")

    monkeypatch.setattr(module, "fetch_alpaca_market_calendar", unavailable)

    assert resolve_market_session(now=datetime(2026, 8, 10, 11, tzinfo=EASTERN)) is None


def test_synthetic_fixture_mode_never_reports_a_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Fixture calendars are the exact source of the weekend-bars trap, so the
    # hermetic mode says nothing rather than something false.
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "synthetic_unit_fixture")

    assert resolve_market_session(now=datetime(2026, 8, 10, 11, tzinfo=EASTERN)) is None


def test_a_utc_caller_is_converted_rather_than_assumed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 18:00 UTC in August is 14:00 in New York, inside the session.
    trading_day = date(2026, 8, 10)
    monkeypatch.setattr(
        module,
        "fetch_alpaca_market_calendar",
        _calendar({trading_day: _session(trading_day)}, []),
    )

    snapshot = resolve_market_session(
        now=datetime(2026, 8, 10, 18, 0, tzinfo=timezone.utc)
    )

    assert snapshot is not None
    assert snapshot.phase == "open"
    assert snapshot.as_of.hour == 14


def test_a_naive_datetime_is_refused_rather_than_read_as_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trading_day = date(2026, 8, 10)
    monkeypatch.setattr(
        module,
        "fetch_alpaca_market_calendar",
        _calendar({trading_day: _session(trading_day)}, []),
    )

    with pytest.raises(ValueError, match="market_session_requires_aware_datetime"):
        resolve_market_session(now=datetime(2026, 8, 10, 11, 0))


def test_a_utc_evening_belongs_to_the_eastern_day_it_falls_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 01:00 UTC on the 11th is 21:00 Eastern on the 10th, so the calendar day
    # looked up is the 10th. Reading the UTC date instead asks for a session on
    # a day the user has not reached.
    trading_day = date(2026, 8, 10)
    calls: list[date] = []
    monkeypatch.setattr(
        module,
        "fetch_alpaca_market_calendar",
        _calendar({trading_day: _session(trading_day)}, calls),
    )

    snapshot = resolve_market_session(
        now=datetime(2026, 8, 11, 1, 0, tzinfo=timezone.utc)
    )

    assert calls == [trading_day]
    assert snapshot is not None
    assert snapshot.phase == "closed"
