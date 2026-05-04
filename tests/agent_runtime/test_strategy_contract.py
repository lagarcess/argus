from datetime import date

from argus.agent_runtime.strategy_contract import (
    normalize_date_range_candidate,
    resolve_date_range,
)


def test_resolve_date_range_accepts_month_name_ranges() -> None:
    resolved = resolve_date_range(
        "Jan 1 2010 to Dec 31 2020",
        today=date(2026, 5, 3),
    )

    assert resolved.payload == {"start": "2010-01-01", "end": "2020-12-31"}
    assert resolved.display == "January 1, 2010 - December 31, 2020"


def test_normalize_date_range_reads_month_name_ranges_from_raw_phrase() -> None:
    normalized = normalize_date_range_candidate(
        None,
        raw_user_phrasing="Can we see Feb 7 2020 till Feb 7 2024?",
        today=date(2026, 5, 3),
    )

    assert normalized == {"start": "2020-02-07", "end": "2024-02-07"}


def test_raw_since_year_period_overrides_model_default() -> None:
    normalized = normalize_date_range_candidate(
        "past year",
        raw_user_phrasing="Invest $500 in Bitcoin every month since 2021.",
        today=date(2026, 5, 3),
    )

    assert normalized == "since 2021"
