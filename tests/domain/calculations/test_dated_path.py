"""A dated path steps by the period's own length and dates no other frequency."""

from __future__ import annotations

from datetime import date

from argus.domain.calculations._shared import dated_path


def _dates(start: date, per_year: int, count: int) -> list[str] | None:
    visual = dated_path(start, per_year, [1.0] * count, currency="USD")
    return None if visual is None else [point.time for point in visual.series]


def test_monthly_dates_keep_the_start_day_within_each_month() -> None:
    assert _dates(date(2026, 1, 31), 12, 3) == ["2026-02-28", "2026-03-31", "2026-04-30"]


def test_quarterly_and_yearly_dates_step_by_whole_months() -> None:
    assert _dates(date(2026, 9, 11), 4, 2) == ["2026-12-11", "2027-03-11"]
    assert _dates(date(2026, 9, 11), 1, 2) == ["2027-09-11", "2028-09-11"]


def test_weekly_and_daily_dates_step_by_days() -> None:
    assert _dates(date(2026, 9, 11), 52, 3) == ["2026-09-18", "2026-09-25", "2026-10-02"]
    assert _dates(date(2026, 9, 11), 365, 2) == ["2026-09-12", "2026-09-13"]


def test_a_frequency_of_neither_whole_months_nor_whole_days_has_no_dated_path() -> None:
    assert _dates(date(2026, 9, 11), 24, 3) is None
