from datetime import date

from argus.agent_runtime.state.models import StrategySummary
from argus.agent_runtime.strategy_contract import (
    executable_strategy_type_from_extracted_fields,
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


def test_resolve_date_range_accepts_month_year_to_today() -> None:
    resolved = resolve_date_range(
        "January 2022 to today",
        today=date(2026, 5, 20),
    )

    assert resolved.payload == {"start": "2022-01-01", "end": "2026-05-20"}
    assert resolved.display == "January 1, 2022 - May 20, 2026"
    assert resolved.used_default is False


def test_resolve_date_range_accepts_calendar_year() -> None:
    resolved = resolve_date_range("in 2024", today=date(2026, 5, 3))

    assert resolved.label == "2024"
    assert resolved.payload == {"start": "2024-01-01", "end": "2024-12-31"}
    assert resolved.display == "2024 (January 1, 2024 - December 31, 2024)"
    assert resolved.used_default is False


def test_normalize_date_range_preserves_structured_month_name_ranges() -> None:
    normalized = normalize_date_range_candidate(
        {"start": "2020-02-07", "end": "2024-02-07"},
        today=date(2026, 5, 3),
    )

    assert normalized == {"start": "2020-02-07", "end": "2024-02-07"}


def test_raw_phrase_no_longer_overrides_structured_date_range() -> None:
    normalized = normalize_date_range_candidate(
        "past year",
        raw_user_phrasing="Invest $500 in Bitcoin every month since 2021.",
        today=date(2026, 5, 3),
    )

    assert normalized == "past year"


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
            phrase,
            today=date(2026, 5, 3),
        )
        resolved = resolve_date_range(normalized, today=date(2026, 5, 3))

        assert normalized == phrase
        assert resolved.label == label
        assert resolved.payload == {"start": start, "end": end}
        assert resolved.used_default is False


def test_embedded_singular_relative_periods_are_not_default_fallback() -> None:
    resolved = resolve_date_range(
        "use the past year instead",
        today=date(2026, 5, 3),
    )

    assert resolved.label == "past year"
    assert resolved.payload == {"start": "2025-05-03", "end": "2026-05-03"}
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


def test_extracted_fields_resolve_indicator_threshold_from_registry() -> None:
    resolved = executable_strategy_type_from_extracted_fields(
        {
            "indicator": "sma",
            "entry_threshold": 450,
            "exit_threshold": 500,
        }
    )

    assert resolved == "indicator_threshold"


def test_extracted_fields_do_not_force_unknown_strategy_contract() -> None:
    resolved = executable_strategy_type_from_extracted_fields(
        {
            "strategy_type": "sentiment_strategy",
            "entry_logic": "news sentiment turns positive",
            "asset_universe": ["AAPL"],
            "date_range": "past year",
        }
    )

    assert resolved is None


def test_extracted_fields_do_not_accept_unknown_rule_spec_as_signal_strategy() -> None:
    resolved = executable_strategy_type_from_extracted_fields(
        {
            "strategy_type": "signal_strategy",
            "rule_spec": {"type": "news_sentiment", "sentiment_direction": "positive"},
            "asset_universe": ["AAPL"],
            "date_range": "past year",
        }
    )

    assert resolved is None
