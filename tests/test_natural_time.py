from datetime import date

from argus.nlp.natural_time import (
    canonical_date_range_label_from_text,
    contains_named_date_evidence,
    parse_relative_endpoint_text,
    resolve_current_message_date_patch,
    resolve_date_range_text,
    resolve_date_window_text,
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


def test_resolves_current_year_to_date_in_spanish() -> None:
    resolved = resolve_date_range_text(
        "este año hasta hoy",
        today=date(2026, 6, 1),
        languages=("es", "en"),
    )

    assert resolved is not None
    assert resolved.payload == {"start": "2026-01-01", "end": "2026-06-01"}


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


def test_resolves_runtime_relative_windows_in_natural_time_layer() -> None:
    today = date(2026, 5, 3)

    resolved = resolve_date_window_text(
        "use the past year instead",
        today=today,
        languages=("en", "es"),
    )

    assert resolved is not None
    assert resolved.label == "past year"
    assert resolved.payload == {"start": "2025-05-03", "end": "2026-05-03"}


def test_resolves_runtime_calendar_year_shapes_in_natural_time_layer() -> None:
    today = date(2026, 6, 1)

    multi_year = resolve_date_window_text("over 2024 and 2025", today=today)
    year_so_far = resolve_date_window_text("in 2026 so far", today=today)
    since_year = resolve_date_window_text("since 2021", today=today)

    assert multi_year is not None
    assert multi_year.payload == {"start": "2024-01-01", "end": "2025-12-31"}
    assert year_so_far is not None
    assert year_so_far.label == "2026 so far"
    assert year_so_far.payload == {"start": "2026-01-01", "end": "2026-06-01"}
    assert since_year is not None
    assert since_year.payload == {"start": "2021-01-01", "end": "2026-06-01"}


def test_natural_time_owns_current_message_date_patches() -> None:
    today = date(2026, 6, 3)

    assert resolve_current_message_date_patch(
        "adjust the end date to yesterday",
        today=today,
        languages=("en", "es"),
    ) == {"end": "2026-06-02"}
    assert resolve_current_message_date_patch(
        "how did apple perform over 2024 and 2025?",
        today=today,
        languages=("en", "es"),
    ) == {"start": "2024-01-01", "end": "2025-12-31"}


def test_canonical_date_range_label_preserves_user_relative_phrase() -> None:
    assert (
        canonical_date_range_label_from_text(
            "los ultimos 8 meses hasta hoy",
            today=date(2026, 6, 1),
            languages=("es", "en"),
        )
        == "past 8 months"
    )


def test_canonical_date_range_label_does_not_stringify_concrete_spans() -> None:
    assert (
        canonical_date_range_label_from_text(
            "enero de 2024 hasta marzo de 2024",
            today=date(2026, 6, 1),
            languages=("es", "en"),
        )
        is None
    )
