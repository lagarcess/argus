from datetime import date

from argus.nlp.natural_time import resolve_date_range_text


def test_resolves_spanish_month_year_range() -> None:
    resolved = resolve_date_range_text(
        "desde enero de 2021 hasta diciembre de 2024",
        today=date(2026, 6, 1),
        languages=("es", "en"),
    )

    assert resolved is not None
    assert resolved.payload == {"start": "2021-01-01", "end": "2024-12-31"}
    assert resolved.evidence_spans == ("enero de 2021", "diciembre de 2024")


def test_resolves_spanish_relative_window_to_today() -> None:
    resolved = resolve_date_range_text(
        "los ultimos 8 meses hasta hoy",
        today=date(2026, 6, 1),
        languages=("es", "en"),
    )

    assert resolved is not None
    assert resolved.label == "past 8 months"
    assert resolved.payload == {"start": "2025-10-01", "end": "2026-06-01"}


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
