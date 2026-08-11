"""Fractional durations: the LLM interprets, deterministic code computes (#332).

Probes the parser directly, as the spec's nondeterminism note requires:
interpretation normalizes some phrasings, so a passing journey proves nothing
about the parser. Reference date 2026-08-01 matches the spec's defect table.

The contract has three layers:
- the typed intent carries a possibly-fractional count and deterministic math
  resolves it exactly;
- the bounded trailing-window idiom reads the whole decimal token, including
  the es-419 decimal comma;
- every dateparser-backed read refuses text carrying a fractional duration
  instead of resolving the digits after the separator as the whole quantity.
"""

from __future__ import annotations

from datetime import date

import pytest
from argus.agent_runtime.llm_interpreter_types import LLMDateRangeIntent
from argus.nlp.natural_time import (
    parse_date_text,
    resolve_date_range_endpoint_patch,
    resolve_date_range_intent,
    resolve_date_range_text,
    resolve_rolling_window_intent_text,
    text_has_fractional_duration,
)

TODAY = date(2026, 8, 1)


def _rolling(count: float, unit: str = "month") -> dict[str, object]:
    return {
        "kind": "rolling_window",
        "count": count,
        "unit": unit,
        "anchor": "today",
        "confidence": 0.9,
        "evidence": f"last {count} {unit}s",
    }


class TestTypedIntentFractionalMath:
    """The spec's table, resolved through the typed path."""

    @pytest.mark.parametrize(
        ("count", "unit", "expected_start"),
        [
            # 8 whole months before 2026-08-01 is 2025-12-01; the half month
            # crosses November (30 days), so 15 more days: 2025-11-16.
            (8.5, "month", "2025-11-16"),
            # 3 whole months back is 2026-05-01; half of April is 15 days.
            (3.5, "month", "2026-04-16"),
            # 2 whole months back is 2026-06-01; half of May (31) rounds to 16.
            (2.5, "month", "2026-05-16"),
            # The integer rows of the spec table stay byte-identical.
            (5, "month", "2026-03-01"),
            (2, "month", "2026-06-01"),
            (8, "month", "2025-12-01"),
            # 1.5 years is exactly 18 months.
            (1.5, "year", "2025-02-01"),
            # 2.5 weeks is 17.5 days, rounded half-up to 18.
            (2.5, "week", "2026-07-14"),
            (1.5, "quarter", "2026-03-16"),
            (10.5, "day", "2026-07-21"),
        ],
    )
    def test_rolling_window_resolution(
        self, count: float, unit: str, expected_start: str
    ) -> None:
        resolution = resolve_date_range_intent(_rolling(count, unit), today=TODAY)
        assert resolution is not None
        assert resolution.payload == {
            "start": expected_start,
            "end": TODAY.isoformat(),
        }

    def test_fractional_label_shows_the_stated_quantity(self) -> None:
        resolution = resolve_date_range_intent(_rolling(8.5), today=TODAY)
        assert resolution is not None
        assert resolution.label == "past 8.5 months"
        integer = resolve_date_range_intent(_rolling(8), today=TODAY)
        assert integer is not None
        assert integer.label == "past 8 months"

    def test_the_llm_schema_accepts_fractional_counts(self) -> None:
        intent = LLMDateRangeIntent(kind="rolling_window", count=8.5, unit="month")
        assert intent.count == 8.5
        resolution = resolve_date_range_intent(
            intent.model_dump(mode="python"), today=TODAY
        )
        assert resolution is not None
        assert resolution.payload["start"] == "2025-11-16"

    def test_endpoint_patch_recomputes_from_a_fractional_base(self) -> None:
        resolution = resolve_date_range_endpoint_patch(
            _rolling(8.5),
            {
                "kind": "endpoint_patch",
                "endpoint": "end",
                "end": "2026-06-01",
                "confidence": 0.9,
            },
            today=TODAY,
        )
        assert resolution is not None
        # 8 whole months before 2026-06-01 is 2025-10-01; half of September
        # (30 days) is 15 more: 2025-09-16.
        assert resolution.payload == {"start": "2025-09-16", "end": "2026-06-01"}


class TestBoundedIdiomReadsWholeDecimals:
    @pytest.mark.parametrize(
        ("text", "count"),
        [
            ("last 8.5 months", 8.5),
            ("the last 8.5 months", 8.5),
            ("últimos 8.5 meses", 8.5),
            ("últimos 8,5 meses", 8.5),
            ("last 12 months", 12),
            ("último año", 1),
        ],
    )
    def test_trailing_window_counts(self, text: str, count: float) -> None:
        languages = ("es", "en") if "ú" in text or "meses" in text else ("en",)
        intent = resolve_rolling_window_intent_text(
            text, today=TODAY, languages=languages
        )
        assert intent is not None, text
        assert intent["count"] == count
        assert intent["unit"] in {"month", "year"}

    def test_whole_counts_stay_integers_in_the_payload(self) -> None:
        intent = resolve_rolling_window_intent_text("last 12 months", today=TODAY)
        assert intent is not None
        assert isinstance(intent["count"], int)

    def test_list_commas_still_separate_tokens(self) -> None:
        assert not text_has_fractional_duration("enero, febrero y marzo")


class TestDateparserBackedReadsRefuseFractions:
    """The defect table's inputs must never resolve to the wrong window."""

    SPEC_TABLE_FRACTIONAL = [
        "8.5 months ago",
        "3.5 months ago",
        "2.5 months ago",
        "hace 8.5 meses",
        "hace 8,5 meses",
        "1.5 years ago",
        "2.5 weeks ago",
        "8.0 months ago",
    ]

    @pytest.mark.parametrize("text", SPEC_TABLE_FRACTIONAL)
    def test_parse_date_text_refuses(self, text: str) -> None:
        languages = ("es", "en") if "hace" in text or "meses" in text else ("en",)
        assert (
            parse_date_text(
                text,
                today=TODAY,
                endpoint="start",
                languages=languages,
                prefer_dates_from="past",
            )
            is None
        ), f"{text!r} must refuse, not resolve the digits after the separator"

    @pytest.mark.parametrize("text", SPEC_TABLE_FRACTIONAL)
    def test_range_and_evidence_reads_refuse(self, text: str) -> None:
        languages = ("es", "en") if "hace" in text or "meses" in text else ("en",)
        assert resolve_date_range_text(text, today=TODAY, languages=languages) is None

    def test_ago_phrasings_do_not_misresolve_through_the_rolling_fallback(
        self,
    ) -> None:
        # "hace 8,5 meses" is not the trailing-window idiom, so with the
        # dateparser fallback refusing, the whole read declines and the turn
        # stays with the interpreter instead of running a wrong window.
        intent = resolve_rolling_window_intent_text(
            "hace 8,5 meses", today=TODAY, languages=("es", "en")
        )
        assert intent is None

    @pytest.mark.parametrize(
        ("text", "expected_start"),
        [
            ("5 months ago", "2026-03-01"),
            ("2 months ago", "2026-06-01"),
        ],
    )
    def test_integer_reads_are_unchanged(self, text: str, expected_start: str) -> None:
        parsed = parse_date_text(
            text,
            today=TODAY,
            endpoint="start",
            languages=("en",),
            prefer_dates_from="past",
        )
        assert parsed is not None
        assert parsed.isoformat() == expected_start

    def test_plain_dates_with_decimals_elsewhere_still_parse(self) -> None:
        parsed = parse_date_text(
            "March 2024",
            today=TODAY,
            endpoint="start",
            languages=("en",),
        )
        assert parsed is not None
        assert parsed.isoformat() == "2024-03-01"
