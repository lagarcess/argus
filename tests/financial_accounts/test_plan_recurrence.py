from datetime import date

import pytest
from argus.domain.planning.recurrence import dates
from argus.domain.planning.schemas import Schedule


@pytest.mark.parametrize("year, february", [(2024, 29), (2025, 28)])
def test_month_end_stays_anchored_after_february(year, february):
    schedule = Schedule(cadence="monthly", start_date=date(year, 1, 31))
    assert dates(schedule, date(year, 3, 31)) == [
        date(year, 1, 31),
        date(year, 2, february),
        date(year, 3, 31),
    ]


def test_quincena_clamps_and_deduplicates():
    schedule = Schedule(
        cadence="twice_monthly", start_date=date(2025, 2, 1), month_days=[30, 31]
    )
    assert dates(schedule, date(2025, 3, 31)) == [
        date(2025, 2, 28),
        date(2025, 3, 30),
        date(2025, 3, 31),
    ]


def test_monthly_recurrence_crosses_year_and_respects_end():
    schedule = Schedule(
        cadence="monthly", start_date=date(2026, 12, 31), end_date=date(2027, 2, 28)
    )
    assert dates(schedule, date(2027, 4, 30)) == [
        date(2026, 12, 31),
        date(2027, 1, 31),
        date(2027, 2, 28),
    ]
