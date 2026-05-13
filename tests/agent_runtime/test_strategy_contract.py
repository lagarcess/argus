from datetime import date

from argus.agent_runtime.state.models import StrategySummary
from argus.agent_runtime.strategy_contract import (
    normalize_date_range_candidate,
    resolve_date_range,
    strategy_can_be_approved,
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


def test_raw_since_ipo_period_overrides_model_default() -> None:
    normalized = normalize_date_range_candidate(
        "past year",
        raw_user_phrasing="take META since IPO",
        today=date(2026, 5, 3),
    )

    assert normalized == "since_ipo"


def test_singular_relative_periods_do_not_fall_back_to_past_year() -> None:
    cases = {
        "last month": ("past month", "2026-04-03", "2026-05-03"),
        "past month": ("past month", "2026-04-03", "2026-05-03"),
        "last week": ("past week", "2026-04-26", "2026-05-03"),
        "past week": ("past week", "2026-04-26", "2026-05-03"),
        "last quarter": ("past quarter", "2026-02-03", "2026-05-03"),
    }

    for phrase, (label, start, end) in cases.items():
        normalized = normalize_date_range_candidate(
            "past year",
            raw_user_phrasing=f"try buy and hold BABA for the {phrase}",
            today=date(2026, 5, 3),
        )
        resolved = resolve_date_range(normalized, today=date(2026, 5, 3))

        assert normalized == phrase
        assert resolved.label == label
        assert resolved.payload == {"start": start, "end": end}
        assert resolved.used_default is False


def test_resolve_date_range_exposes_default_fallback() -> None:
    resolved = resolve_date_range("the previous market mood", today=date(2026, 5, 3))

    assert resolved.label == "past year"
    assert resolved.payload == {"start": "2025-05-03", "end": "2026-05-03"}
    assert resolved.used_default is True


def test_dca_strategy_requires_explicit_recurring_amount_for_approval() -> None:
    strategy = StrategySummary(
        strategy_type="dca_accumulation",
        strategy_thesis="Buy Tesla every month.",
        asset_universe=["TSLA"],
        date_range="past year",
        cadence="monthly",
    )

    assert strategy_can_be_approved(strategy) is False

    strategy.capital_amount = 500

    assert strategy_can_be_approved(strategy) is True
