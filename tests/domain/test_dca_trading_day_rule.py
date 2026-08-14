"""The non-trading-day contribution rule, proven on a real exchange calendar.

The rule Argus states to users: each contribution buys at the first available
price in its period, so one that falls on a non-trading day buys on the next
trading day. Measured here against the actual 2024 NYSE sessions, including
the months whose first day was a holiday or a weekend and the months that have
no 31st at all, because a synthetic fixture that puts bars on weekends would
let a broken rule pass.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest
from argus.domain.backtesting.coverage import prepare_market_data
from argus.domain.backtesting.signals import _build_signals
from argus.domain.dca_capital import build_dca_capital_plan, dca_capital_config_fields

from tests.domain.nyse_calendar import (
    NYSE_2024_HOLIDAYS,
    is_nyse_session,
    next_nyse_session,
    nyse_market_calendar,
    nyse_session_index,
)

_YEAR_START = date(2024, 1, 1)
_YEAR_END = date(2024, 12, 31)


@pytest.fixture(autouse=True)
def _pin_provider_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Coverage skips the calendar entirely in synthetic mode, so pin the mode.

    These assertions are about a real exchange calendar; inheriting the
    runner's mode would let them pass by never consulting one.
    """
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "live_provider")


def _dca_config(*, period: str, start: date, end: date) -> dict[str, object]:
    plan = build_dca_capital_plan(
        starting_capital=0.0,
        contribution=200.0,
        period=period,
    )
    return {
        "template": "dca_accumulation",
        "asset_class": "equity",
        "symbols": ["AAPL"],
        "timeframe": "1D",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "side": "long",
        "allocation_method": "equal_weight",
        "benchmark_symbol": "SPY",
        "parameters": {"dca_cadence": period},
        **dca_capital_config_fields(plan),
    }


def _session_bars(index: pd.DatetimeIndex) -> pd.DataFrame:
    close = pd.Series(range(100, 100 + len(index)), index=index, dtype=float)
    return pd.DataFrame(
        {
            "open": close,
            "high": close,
            "low": close,
            "close": close,
            "volume": 1_000_000.0,
        },
        index=index,
    )


def _contribution_dates(period: str) -> list[date]:
    index = nyse_session_index(_YEAR_START, _YEAR_END)
    entries, _ = _build_signals(
        _dca_config(period=period, start=_YEAR_START, end=_YEAR_END),
        _session_bars(index),
    )
    return [pd.Timestamp(value).date() for value in index[entries.to_numpy()]]


@pytest.mark.parametrize("period", ["daily", "weekly", "biweekly", "monthly", "quarterly"])
def test_no_contribution_ever_lands_on_a_day_the_exchange_was_closed(
    period: str,
) -> None:
    contributions = _contribution_dates(period)

    assert contributions
    assert [day for day in contributions if not is_nyse_session(day)] == []


def test_a_month_that_opens_on_a_holiday_buys_on_the_next_trading_day() -> None:
    """January 2024 opened on New Year's Day; July 4 closed the 4th."""
    contributions = _contribution_dates("monthly")
    by_month = {day.month: day for day in contributions}

    assert date(2024, 1, 1) in NYSE_2024_HOLIDAYS
    assert by_month[1] == next_nyse_session(date(2024, 1, 1)) == date(2024, 1, 2)
    # September 2024 opened on a Sunday with Labor Day on the Monday.
    assert by_month[9] == next_nyse_session(date(2024, 9, 1)) == date(2024, 9, 3)


def test_every_monthly_contribution_is_that_month_s_first_open_session() -> None:
    """The rule is not "the 1st" and not "a weekday": it is the next session."""
    contributions = _contribution_dates("monthly")

    assert len(contributions) == 12
    for month, day in enumerate(contributions, start=1):
        assert day == next_nyse_session(date(2024, month, 1))


def test_a_contribution_dated_the_31st_falls_on_the_next_session() -> None:
    """Months without a 31st, and 31sts on closed days, both resolve forward.

    Stated as the general rule rather than as one date: for every month, the
    day a "31st" request resolves to is the next session on or after the last
    day that month actually has.
    """
    for month in range(1, 13):
        first_of_next = (
            date(2024, month + 1, 1) if month < 12 else date(2025, 1, 1)
        )
        last_day_of_month = first_of_next - timedelta(days=1)
        requested = min(31, last_day_of_month.day)
        resolved = next_nyse_session(date(2024, month, requested))

        assert is_nyse_session(resolved)
        assert resolved >= date(2024, month, requested)

    # December 31, 2024 was itself a session; November 30 was a Saturday.
    assert next_nyse_session(date(2024, 12, 31)) == date(2024, 12, 31)
    assert next_nyse_session(date(2024, 11, 30)) == date(2024, 12, 2)


def test_weekly_contributions_skip_the_holiday_that_opens_their_week() -> None:
    """Memorial Day and Labor Day both closed a Monday in 2024."""
    contributions = set(_contribution_dates("weekly"))

    assert date(2024, 5, 27) in NYSE_2024_HOLIDAYS
    assert date(2024, 5, 27) not in contributions
    assert date(2024, 5, 28) in contributions
    assert date(2024, 9, 2) in NYSE_2024_HOLIDAYS
    assert date(2024, 9, 2) not in contributions
    assert date(2024, 9, 3) in contributions


def test_coverage_reads_the_same_calendar_the_contributions_land_on() -> None:
    """The engine and the calendar are one source, not two that agree today."""
    index = nyse_session_index(_YEAR_START, _YEAR_END)
    bars = _session_bars(index)
    config = _dca_config(period="monthly", start=_YEAR_START, end=_YEAR_END)

    prepared = prepare_market_data(
        config,
        fetch_ohlcv_func=lambda *, symbol, **_: bars.copy(),
        fetch_market_calendar_func=nyse_market_calendar,
    )

    session_dates = {
        session.session_date for session in prepared.equity_market_sessions or ()
    }
    assert session_dates
    assert not session_dates & NYSE_2024_HOLIDAYS
    assert set(_contribution_dates("monthly")) <= session_dates
