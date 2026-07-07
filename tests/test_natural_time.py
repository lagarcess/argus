from datetime import date

from argus.nlp.natural_time import (
    contains_named_date_evidence,
    dateparser_languages_for_user_language,
    parse_date_text,
    parse_explicit_date_text,
    parse_relative_endpoint_text,
    resolve_date_range_endpoint_patch,
    resolve_date_range_intent,
    resolve_date_range_text,
    resolve_rolling_window_intent_text,
)


def test_resolves_spanish_month_year_range() -> None:
    resolved = resolve_date_range_text(
        "desde enero de 2021 hasta diciembre de 2024",
        today=date(2026, 6, 1),
        languages=("es", "en"),
    )

    assert resolved is not None
    assert resolved.payload == {"start": "2021-01-01", "end": "2024-12-31"}
    assert resolved.evidence_spans == ("enero de 2021", "diciembre de 2024")


def test_resolves_english_shared_year_month_span() -> None:
    resolved = resolve_date_range_text(
        "march through october 2024",
        today=date(2026, 6, 1),
        languages=("en", "es"),
    )

    assert resolved is not None
    assert resolved.payload == {"start": "2024-03-01", "end": "2024-10-31"}


def test_resolves_compact_month_year_range() -> None:
    resolved = resolve_date_range_text(
        "Jan 2021-Jan 2024",
        today=date(2026, 6, 1),
        languages=("en", "es"),
    )

    assert resolved is not None
    assert resolved.payload == {"start": "2021-01-01", "end": "2024-01-31"}


def test_resolves_spanish_relative_window_to_today() -> None:
    resolved = resolve_date_range_text(
        "los ultimos 8 meses hasta hoy",
        today=date(2026, 6, 1),
        languages=("es", "en"),
    )

    assert resolved is not None
    assert resolved.label == "past 8 months"
    assert resolved.payload == {"start": "2025-10-01", "end": "2026-06-01"}


def test_resolves_english_relative_time_span() -> None:
    resolved = resolve_date_range_text(
        "past 6 months",
        today=date(2026, 6, 1),
        languages=("en", "es"),
    )

    assert resolved is not None
    assert resolved.label == "past 6 months"
    assert resolved.payload == {"start": "2025-12-01", "end": "2026-06-01"}


def test_resolves_language_agnostic_year_windows_to_rolling_intent() -> None:
    today = date(2026, 6, 16)

    cases = [
        ("last 2 years", ("en",), 2),
        ("last year", ("en",), 1),
        ("últimos 2 años", ("es", "en"), 2),
    ]

    for text, languages, count in cases:
        assert resolve_rolling_window_intent_text(
            text,
            today=today,
            languages=languages,
        ) == {
            "kind": "rolling_window",
            "count": count,
            "unit": "year",
            "anchor": "today",
            "confidence": 0.65,
            "evidence": text,
        }


def test_unparsed_spanish_singular_year_does_not_become_day_window() -> None:
    today = date(2026, 6, 16)

    assert (
        resolve_rolling_window_intent_text(
            "último año",
            today=today,
            languages=("es", "en"),
        )
        is None
    )


def test_leap_day_trailing_year_stays_month_aligned_not_366_days() -> None:
    # "last year" on Feb 29 clamps its start to Feb 28 of the prior non-leap
    # year; the window must keep its year/month label, not become "366 days".
    today = date(2028, 2, 29)

    assert resolve_rolling_window_intent_text(
        "last year",
        today=today,
        languages=("en",),
    ) == {
        "kind": "rolling_window",
        "count": 1,
        "unit": "year",
        "anchor": "today",
        "confidence": 0.65,
        "evidence": "last year",
    }
    assert resolve_rolling_window_intent_text(
        "últimos 12 meses",
        today=today,
        languages=("es", "en"),
    ) == {
        "kind": "rolling_window",
        "count": 12,
        "unit": "month",
        "anchor": "today",
        "confidence": 0.65,
        "evidence": "últimos 12 meses",
    }


def test_resolves_relative_year_windows_before_strategy_semantics() -> None:
    today = date(2026, 6, 16)

    cases = [
        ("buy_and_hold", "last 2 years", ("en",), "2024-06-16"),
        ("dca_accumulation", "last year", ("en",), "2025-06-16"),
        ("buy_and_hold", "últimos 2 años", ("es", "en"), "2024-06-16"),
    ]

    for strategy_type, text, languages, expected_start in cases:
        intent = resolve_rolling_window_intent_text(
            text,
            today=today,
            languages=languages,
        )
        resolved = resolve_date_range_intent(intent, today=today)

        assert resolved is not None, strategy_type
        assert resolved.payload == {
            "start": expected_start,
            "end": "2026-06-16",
        }


def test_calendar_year_evidence_is_not_a_rolling_window() -> None:
    assert (
        resolve_rolling_window_intent_text(
            "durante 2024",
            today=date(2026, 6, 16),
            languages=("es", "en"),
        )
        is None
    )


def test_resolves_language_agnostic_year_window_endpoint_patch() -> None:
    today = date(2026, 6, 16)
    base_intent = resolve_rolling_window_intent_text(
        "últimos 2 años",
        today=today,
        languages=("es", "en"),
    )

    resolved = resolve_date_range_endpoint_patch(
        base_intent,
        {
            "kind": "endpoint_patch",
            "endpoint": "end",
            "end": "today",
            "confidence": 0.9,
            "evidence": "que termine hoy",
        },
        today=today,
    )

    assert resolved is not None
    assert resolved.payload == {"start": "2024-06-16", "end": "2026-06-16"}
    assert resolved.evidence_spans == ("últimos 2 años", "que termine hoy")


def test_resolves_current_year_to_date_in_spanish() -> None:
    resolved = resolve_date_range_text(
        "este año hasta hoy",
        today=date(2026, 6, 1),
        languages=("es", "en"),
    )

    assert resolved is not None
    assert resolved.payload == {"start": "2026-01-01", "end": "2026-06-01"}


def test_resolves_canonical_rolling_window_intent_without_language_tokens() -> None:
    resolved = resolve_date_range_intent(
        {
            "kind": "rolling_window",
            "count": 12,
            "unit": "month",
            "anchor": "today",
            "evidence": "durante los últimos 12 meses",
        },
        today=date(2026, 6, 12),
    )

    assert resolved is not None
    assert resolved.payload == {"start": "2025-06-12", "end": "2026-06-12"}
    assert resolved.evidence_spans == ("durante los últimos 12 meses",)


def test_resolves_endpoint_patch_against_prior_rolling_intent() -> None:
    resolved = resolve_date_range_endpoint_patch(
        {
            "kind": "rolling_window",
            "count": 12,
            "unit": "month",
            "anchor": "today",
            "evidence": "last 12 months",
        },
        {
            "kind": "endpoint_patch",
            "endpoint": "end",
            "end": "2026-06-12",
            "confidence": 0.9,
            "evidence": "last friday",
        },
        today=date(2026, 6, 15),
    )

    assert resolved is not None
    assert resolved.payload == {"start": "2025-06-12", "end": "2026-06-12"}
    assert resolved.evidence_spans == ("last 12 months", "last friday")


def test_resolves_canonical_year_to_date_intent_without_language_tokens() -> None:
    resolved = resolve_date_range_intent(
        {
            "kind": "year_to_date",
            "anchor": "today",
            "evidence": "en lo que va del año",
        },
        today=date(2026, 6, 12),
    )

    assert resolved is not None
    assert resolved.payload == {"start": "2026-01-01", "end": "2026-06-12"}
    assert resolved.evidence_spans == ("en lo que va del año",)


def test_past_year_to_date_intent_preserves_explicit_today_endpoint() -> None:
    resolved = resolve_date_range_intent(
        {
            "kind": "year_to_date",
            "year": 2023,
            "end": "today",
            "anchor": "today",
            "evidence": "canonical range ending today",
        },
        today=date(2026, 6, 1),
    )

    assert resolved is not None
    assert resolved.payload == {"start": "2023-01-01", "end": "2026-06-01"}


def test_natural_time_does_not_grow_locale_phrase_alias_tables() -> None:
    from pathlib import Path

    source = Path("src/argus/nlp/natural_time.py").read_text()

    forbidden = [
        "import re",
        "re.",
        "_TIME_TOKEN_ALIASES",
        "_NUMBER_TOKEN_ALIASES",
        "_YTD_PROGRESS_TOKENS",
    ]
    assert [token for token in forbidden if token in source] == []


def test_preserves_exact_day_range_without_broadening_to_whole_years() -> None:
    resolved = resolve_date_range_text(
        "from March 1 2020 to August 1 2021",
        today=date(2026, 6, 1),
        languages=("en",),
    )

    assert resolved is not None
    assert resolved.label == "2020-03-01 to 2021-08-01"
    assert resolved.payload == {"start": "2020-03-01", "end": "2021-08-01"}


def test_ignores_text_without_a_date_range() -> None:
    assert (
        resolve_date_range_text(
            "the previous market mood",
            today=date(2026, 6, 1),
            languages=("en", "es"),
        )
        is None
    )


def test_named_date_evidence_ignores_whole_message_false_positives() -> None:
    assert (
        contains_named_date_evidence(
            "how did apple perform over 2024 and 2025?",
            today=date(2026, 6, 1),
            languages=("en", "es"),
        )
        is False
    )


def test_relative_endpoint_parser_rejects_calendar_name_false_positive() -> None:
    today = date(2026, 6, 1)

    assert parse_relative_endpoint_text("yesterday", today=today) == date(2026, 5, 31)
    assert parse_relative_endpoint_text("march", today=today) is None


def test_date_parser_resolves_library_weekday_evidence_without_phrase_tables() -> None:
    today = date(2026, 6, 15)

    assert parse_date_text(
        "last friday",
        today=today,
        endpoint="end",
        languages=dateparser_languages_for_user_language("en"),
    ) == date(2026, 6, 12)


def test_date_parser_treats_previous_weekday_as_prior_week_when_today_matches() -> None:
    today = date(2026, 6, 19)

    assert parse_date_text(
        "next friday",
        today=today,
        endpoint="end",
        languages=dateparser_languages_for_user_language("en"),
    ) == date(2026, 6, 19)
    assert parse_date_text(
        "last friday",
        today=today,
        endpoint="end",
        languages=dateparser_languages_for_user_language("en"),
        prefer_dates_from="past",
    ) == date(2026, 6, 12)
    assert parse_date_text(
        "viernes pasado",
        today=today,
        endpoint="end",
        languages=dateparser_languages_for_user_language("es-419"),
        prefer_dates_from="past",
    ) == date(2026, 6, 12)
    assert parse_date_text(
        "el viernes pasado",
        today=today,
        endpoint="end",
        languages=dateparser_languages_for_user_language("es-419"),
        prefer_dates_from="past",
    ) == date(2026, 6, 12)


def test_explicit_date_parser_uses_language_hint_without_locale_phrase_tables() -> None:
    today = date(2026, 6, 1)

    assert dateparser_languages_for_user_language("es-419") == ("es", "en")
    assert dateparser_languages_for_user_language("pt-BR") == ("pt", "en")
    assert parse_explicit_date_text(
        "marzo de 2024",
        today=today,
        endpoint="end",
        languages=dateparser_languages_for_user_language("es-419"),
    ) == date(2024, 3, 31)
    assert parse_explicit_date_text(
        "março de 2024",
        today=today,
        endpoint="end",
        languages=dateparser_languages_for_user_language("pt-BR"),
    ) == date(2024, 3, 31)
    assert (
        parse_explicit_date_text(
            "last month",
            today=today,
            endpoint="end",
            languages=dateparser_languages_for_user_language("en"),
        )
        is None
    )


def test_resolves_canonical_endpoint_and_calendar_intents() -> None:
    today = date(2026, 6, 3)

    endpoint = resolve_date_range_intent(
        {
            "kind": "endpoint_patch",
            "endpoint": "end",
            "anchor": "today",
            "day_offset": -1,
            "evidence": "yesterday",
        },
        today=today,
    )
    year = resolve_date_range_intent(
        {
            "kind": "calendar_year",
            "year": 2024,
            "evidence": "2024",
        },
        today=today,
    )

    assert endpoint is not None
    assert endpoint.payload == {"end": "2026-06-02"}
    assert year is not None
    assert year.payload == {"start": "2024-01-01", "end": "2024-12-31"}
