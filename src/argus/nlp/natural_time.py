from __future__ import annotations

import calendar
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Literal, cast

from dateparser.date import DateDataParser
from dateparser.search import search_dates

DatePeriod = Literal["day", "week", "month", "year"]
DateIntentUnit = Literal["day", "week", "month", "quarter", "year"]


@dataclass(frozen=True)
class NaturalDateRange:
    label: str
    start: date
    end: date
    evidence_spans: tuple[str, ...] = ()

    @property
    def payload(self) -> dict[str, str]:
        return {"start": self.start.isoformat(), "end": self.end.isoformat()}


@dataclass(frozen=True)
class DateRangeIntentResolution:
    label: str
    payload: dict[str, str]
    evidence_spans: tuple[str, ...] = ()


def date_range_evidence_has_explicit_endpoints(
    evidence_spans: tuple[str, ...],
) -> bool:
    """Return true when natural-time evidence came from two user-visible endpoints."""

    spans = tuple(str(span or "").strip() for span in evidence_spans if str(span or "").strip())
    if len(spans) < 2:
        return False
    return not any(_is_generated_time_span_endpoint(span) for span in spans)


@dataclass(frozen=True)
class _ParsedDate:
    value: date
    period: DatePeriod
    span: str


def resolve_date_range_text(
    text: str,
    *,
    today: date | None = None,
    languages: tuple[str, ...] | None = None,
) -> NaturalDateRange | None:
    """Resolve bounded natural-language date/window text into canonical dates.

    Dateparser is intentionally wrapped here rather than called directly from runtime
    contracts: Argus can bound inputs, normalize endpoint semantics, and reject weak
    single-date false positives in one place.
    """

    raw = str(text or "").strip()
    if not raw:
        return None
    current_date = today or date.today()
    matches = _search_date_spans(raw, today=current_date, languages=languages)
    if not matches:
        return None

    time_span = _range_from_returned_time_span(matches, today=current_date)
    if time_span is not None:
        return time_span

    parsed = [
        parsed
        for span, _ in matches
        if (parsed := _parse_date_span(span, today=current_date, languages=languages))
        is not None
    ]
    if len(parsed) < 2:
        return None

    first = parsed[0]
    last = parsed[-1]
    if (
        first.period == "month"
        and last.period == "month"
        and not _span_has_explicit_year(first.span)
        and _span_has_explicit_year(last.span)
    ):
        first = _ParsedDate(
            value=first.value.replace(year=last.value.year),
            period=first.period,
            span=first.span,
        )

    start = _endpoint_date(first, endpoint="start", today=current_date)
    end = _endpoint_date(last, endpoint="end", today=current_date)
    if end < start:
        return None
    label = _relative_window_label(start=start, end=end, today=current_date) or (
        f"{start} to {end}"
    )
    return NaturalDateRange(
        label=label,
        start=start,
        end=end,
        evidence_spans=(first.span, last.span),
    )


def resolve_rolling_window_intent_text(
    text: str,
    *,
    today: date | None = None,
    languages: tuple[str, ...] | None = None,
    confidence: float = 0.65,
) -> dict[str, Any] | None:
    """Recover a canonical rolling-window intent from bounded date evidence.

    This is intentionally a repair path for short LLM-provided evidence spans, not
    a chat-message parser. The language-specific work stays inside dateparser;
    Argus only converts a resolved relative range into language-neutral intent.
    """

    raw = str(text or "").strip()
    if not raw:
        return None
    current_date = today or date.today()
    resolved = resolve_date_range_text(
        raw,
        today=current_date,
        languages=languages,
    )
    window = (
        _rolling_window_fields_from_range(
            start=resolved.start,
            end=resolved.end,
            today=current_date,
        )
        if resolved is not None
        else _rolling_window_fields_from_single_date_evidence(
            raw,
            today=current_date,
            languages=languages,
        )
    )
    if window is None:
        return None
    return {
        "kind": "rolling_window",
        **window,
        "anchor": "today",
        "confidence": confidence,
        "evidence": raw,
    }


def resolve_calendar_year_intent_text(
    text: str,
    *,
    today: date | None = None,
    languages: tuple[str, ...] | None = None,
    confidence: float = 0.8,
) -> dict[str, Any] | None:
    """Recover a canonical calendar-year intent from bounded date-answer text.

    This helper is for typed pending-date contracts, not general chat routing.
    It uses dateparser to identify a single explicit year, then returns the same
    machine intent shape produced by the structured interpreter.
    """

    raw = str(text or "").strip()
    if not raw:
        return None
    current_date = today or date.today()
    years: list[int] = []
    for span, _ in _search_date_spans(
        raw,
        today=current_date,
        languages=languages,
        return_time_span=False,
    ):
        parsed = _parse_date_span(span, today=current_date, languages=languages)
        if parsed is None or parsed.period != "year":
            continue
        if not _span_has_explicit_year(parsed.span):
            continue
        if parsed.value.year > current_date.year:
            continue
        years.append(parsed.value.year)
    unique_years = list(dict.fromkeys(years))
    if len(unique_years) != 1:
        return None
    return {
        "kind": "calendar_year",
        "year": unique_years[0],
        "confidence": confidence,
        "evidence": raw,
    }


def resolve_date_range_intent(
    intent: Mapping[str, Any] | object | None,
    *,
    today: date | None = None,
) -> DateRangeIntentResolution | None:
    """Resolve canonical interpreter time intent into an Argus date-range patch.

    This is intentionally not a natural-language parser. The LLM owns phrases such
    as "los últimos 12 meses" or "year to date" and returns language-neutral
    fields; this function only performs deterministic date math and validation.
    """

    payload = _intent_payload(intent)
    if not payload:
        return None
    current_date = today or date.today()
    if not _intent_confidence_is_usable(payload):
        return None

    kind = str(payload.get("kind") or "").strip()
    evidence = _intent_evidence_spans(payload)

    if kind == "rolling_window":
        count = _positive_int(payload.get("count"))
        unit = _intent_unit(payload.get("unit"))
        if count is None or unit is None:
            return None
        end = _intent_date(payload.get("end"), today=current_date) or current_date
        start = _subtract_period(end, count=count, unit=unit)
        if end < start:
            return None
        return DateRangeIntentResolution(
            label=_relative_label(count=count, unit=unit),
            payload={"start": start.isoformat(), "end": end.isoformat()},
            evidence_spans=evidence,
        )

    if kind == "year_to_date":
        year = _positive_int(payload.get("year")) or current_date.year
        if year > current_date.year:
            return None
        end = _intent_date(payload.get("end"), today=current_date)
        if end is None:
            end = current_date if year == current_date.year else date(year, 12, 31)
        if end < date(year, 1, 1):
            return None
        return DateRangeIntentResolution(
            label="year to date" if year == current_date.year else f"{year} so far",
            payload={"start": date(year, 1, 1).isoformat(), "end": end.isoformat()},
            evidence_spans=evidence,
        )

    if kind == "calendar_year":
        year = _positive_int(payload.get("year"))
        if year is None or year > current_date.year:
            return None
        end = current_date if year == current_date.year else date(year, 12, 31)
        return DateRangeIntentResolution(
            label=str(year),
            payload={"start": date(year, 1, 1).isoformat(), "end": end.isoformat()},
            evidence_spans=evidence,
        )

    if kind == "since":
        start = _intent_date(payload.get("start"), today=current_date)
        year = _positive_int(payload.get("year"))
        if start is None and year is not None:
            start = date(year, 1, 1)
        if start is None or start > current_date:
            return None
        end = _intent_date(payload.get("end"), today=current_date) or current_date
        if end < start:
            return None
        return DateRangeIntentResolution(
            label=f"since {start.isoformat()}",
            payload={"start": start.isoformat(), "end": end.isoformat()},
            evidence_spans=evidence,
        )

    if kind in {"explicit_range", "endpoint_patch"}:
        patch: dict[str, str] = {}
        start = _intent_date(payload.get("start"), today=current_date)
        end = _intent_date(payload.get("end"), today=current_date)
        offset_date = _intent_day_offset_date(payload, today=current_date)
        endpoint = str(payload.get("endpoint") or "").strip()
        if start is not None:
            patch["start"] = start.isoformat()
        if end is not None:
            patch["end"] = end.isoformat()
        if kind == "endpoint_patch" and endpoint in {"start", "end"}:
            endpoint_value = (start if endpoint == "start" else end) or offset_date
            if endpoint_value is None:
                return None
            patch = {endpoint: endpoint_value.isoformat()}
        if not patch or (
            patch.get("start") and patch.get("end") and patch["end"] < patch["start"]
        ):
            return None
        label = (
            f"{patch['start']} to {patch['end']}"
            if set(patch) == {"start", "end"}
            else "date endpoint"
        )
        return DateRangeIntentResolution(
            label=label,
            payload=patch,
            evidence_spans=evidence,
        )
    return None


def _is_leap_day_clamp_pair(start: date, end: date) -> bool:
    """True when a Feb-29 anchor clamped to Feb-28 marks the same month/year day.

    A trailing 1-year window ending on Feb 29 subtracts to Feb 28 of the prior
    (non-leap) year, so the endpoints share a month-aligned anchor even though
    their day-of-month differs.
    """

    return {(start.month, start.day), (end.month, end.day)} == {(2, 28), (2, 29)}


def _rolling_window_fields_from_range(
    *,
    start: date,
    end: date,
    today: date,
) -> dict[str, Any] | None:
    if end < start or end != today:
        return None
    month_delta = (end.year - start.year) * 12 + (end.month - start.month)
    if month_delta > 0 and (start.day == end.day or _is_leap_day_clamp_pair(start, end)):
        return {"count": month_delta, "unit": "month"}
    day_delta = end.toordinal() - start.toordinal()
    if day_delta <= 0:
        return None
    if day_delta % 365 == 0:
        return {"count": day_delta // 365, "unit": "year"}
    if day_delta % 7 == 0:
        return {"count": day_delta // 7, "unit": "week"}
    return {"count": day_delta, "unit": "day"}


def _rolling_window_fields_from_single_date_evidence(
    text: str,
    *,
    today: date,
    languages: tuple[str, ...] | None,
) -> dict[str, Any] | None:
    parsed = _single_searched_date_span(text, today=today, languages=languages)
    if parsed is not None and parsed.period != "day" and parsed.value < today:
        if _span_has_explicit_year(parsed.span):
            return None
        window = _rolling_window_fields_from_range(
            start=parsed.value,
            end=today,
            today=today,
        )
        if (
            parsed.period == "year"
            and window is not None
            and window.get("unit") == "month"
            and int(window.get("count") or 0) % 12 == 0
        ):
            return {"count": int(window["count"]) // 12, "unit": "year"}
        return window
    return None


def resolve_date_range_endpoint_patch(
    base_intent: Mapping[str, Any] | object | None,
    endpoint_patch: Mapping[str, Any] | object | None,
    *,
    today: date | None = None,
) -> DateRangeIntentResolution | None:
    """Resolve an endpoint edit against a prior canonical date-range intent."""

    base = _intent_payload(base_intent)
    patch = _intent_payload(endpoint_patch)
    if not base or not patch:
        return None
    if str(base.get("kind") or "").strip() != "rolling_window":
        return None
    if str(patch.get("kind") or "").strip() != "endpoint_patch":
        return None
    if not _intent_confidence_is_usable(base) or not _intent_confidence_is_usable(patch):
        return None

    count = _positive_int(base.get("count"))
    unit = _intent_unit(base.get("unit"))
    endpoint = str(patch.get("endpoint") or "").strip()
    if count is None or unit is None or endpoint not in {"start", "end"}:
        return None

    current_date = today or date.today()
    start = _intent_date(patch.get("start"), today=current_date)
    end = _intent_date(patch.get("end"), today=current_date)
    offset_date = _intent_day_offset_date(patch, today=current_date)
    endpoint_value = (start if endpoint == "start" else end) or offset_date
    if endpoint_value is None:
        return None

    if endpoint == "start":
        start_date = endpoint_value
        end_date = _add_period(endpoint_value, count=count, unit=unit)
    else:
        end_date = endpoint_value
        start_date = _subtract_period(endpoint_value, count=count, unit=unit)
    if end_date < start_date:
        return None

    evidence = tuple(
        dict.fromkeys([*_intent_evidence_spans(base), *_intent_evidence_spans(patch)])
    )
    return DateRangeIntentResolution(
        label=_relative_label(count=count, unit=unit),
        payload={"start": start_date.isoformat(), "end": end_date.isoformat()},
        evidence_spans=evidence,
    )


def _intent_payload(intent: Mapping[str, Any] | object | None) -> dict[str, Any]:
    if intent is None:
        return {}
    if isinstance(intent, Mapping):
        return dict(intent)
    model_dump = getattr(intent, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="python")
        return dict(dumped) if isinstance(dumped, Mapping) else {}
    return {}


def _intent_confidence_is_usable(payload: Mapping[str, Any]) -> bool:
    confidence = payload.get("confidence")
    if confidence in (None, ""):
        return True
    try:
        return float(confidence) >= 0.5
    except (TypeError, ValueError):
        return False


def _intent_evidence_spans(payload: Mapping[str, Any]) -> tuple[str, ...]:
    evidence = str(payload.get("evidence") or "").strip()
    return (evidence,) if evidence else ()


def _positive_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _intent_unit(value: Any) -> DateIntentUnit | None:
    normalized = str(value or "").strip()
    if normalized in {"day", "week", "month", "quarter", "year"}:
        return cast(DateIntentUnit, normalized)
    return None


def _intent_date(value: Any, *, today: date) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    if text in {"today", "current_date"}:
        return today
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _intent_day_offset_date(payload: Mapping[str, Any], *, today: date) -> date | None:
    offset = payload.get("day_offset")
    if offset in (None, ""):
        return None
    anchor = str(payload.get("anchor") or "today").strip()
    if anchor not in {"today", "current_date"}:
        return None
    try:
        days = int(offset)
    except (TypeError, ValueError):
        return None
    return today + timedelta(days=days)


def parse_date_text(
    text: str,
    *,
    today: date | None = None,
    endpoint: Literal["start", "end"] = "start",
    languages: tuple[str, ...] | None = None,
    prefer_dates_from: Literal["past", "future"] | None = None,
) -> date | None:
    current_date = today or date.today()
    parsed = _parse_date_span(
        str(text or ""),
        today=current_date,
        languages=languages,
        prefer_dates_from=prefer_dates_from,
    )
    if parsed is None:
        parsed = _single_searched_date_span(
            str(text or ""),
            today=current_date,
            languages=languages,
            prefer_dates_from=prefer_dates_from,
        )
    if parsed is None:
        return None
    return _endpoint_date(parsed, endpoint=endpoint, today=current_date)


def dateparser_languages_for_user_language(language: str | None) -> tuple[str, ...]:
    primary = str(language or "en").strip().replace("_", "-").split("-", 1)[0]
    primary = primary.casefold()
    if not primary or not primary.isalpha():
        return ("en",)
    if primary == "en":
        return ("en",)
    return (primary, "en")


def shift_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def contains_named_date_evidence(
    text: str,
    *,
    today: date | None = None,
    languages: tuple[str, ...] | None = None,
) -> bool:
    """Return whether dateparser found month/day-like natural date evidence.

    Runtime contracts use this as a guardrail to avoid broadening text such as
    "January 2024" into the entire calendar year without carrying dateparser's
    language data directly in the runtime layer.
    """

    current_date = today or date.today()
    for span, _ in _search_date_spans(
        str(text or ""),
        today=current_date,
        languages=languages,
        return_time_span=False,
    ):
        parsed = _parse_date_span(span, today=current_date, languages=languages)
        if parsed is None:
            continue
        if not any(char.isdigit() for char in parsed.span) and parsed.period != "month":
            continue
        if parsed.period in {"day", "month", "week"} and any(
            char.isalpha() for char in parsed.span
        ):
            return True
    return False


def _search_date_spans(
    text: str,
    *,
    today: date,
    languages: tuple[str, ...] | None,
    return_time_span: bool = True,
    prefer_dates_from: Literal["past", "future"] | None = None,
) -> list[tuple[str, datetime]]:
    settings = {
        "RELATIVE_BASE": _relative_base(today),
        "RETURN_AS_TIMEZONE_AWARE": False,
        "PREFER_DAY_OF_MONTH": "first",
        "PREFER_MONTH_OF_YEAR": "first",
    }
    if prefer_dates_from is not None:
        settings["PREFER_DATES_FROM"] = prefer_dates_from
    if return_time_span:
        settings["RETURN_TIME_SPAN"] = True
    results = search_dates(
        _normalize_compact_range_separators(text),
        languages=list(languages) if languages else None,
        settings=settings,
    )
    return list(results or [])


def _parse_date_span(
    span: str,
    *,
    today: date,
    languages: tuple[str, ...] | None,
    prefer_dates_from: Literal["past", "future"] | None = None,
) -> _ParsedDate | None:
    settings = {
        "RELATIVE_BASE": _relative_base(today),
        "RETURN_AS_TIMEZONE_AWARE": False,
        "PREFER_DAY_OF_MONTH": "first",
        "PREFER_MONTH_OF_YEAR": "first",
    }
    if prefer_dates_from is not None:
        settings["PREFER_DATES_FROM"] = prefer_dates_from
    parser = DateDataParser(
        languages=list(languages) if languages else None,
        settings=settings,
    )
    data = parser.get_date_data(_strip_time_span_suffix(span))
    if data.date_obj is None:
        return None
    period = str(data.period or "day")
    if period not in {"day", "week", "month", "year"}:
        period = "day"
    return _ParsedDate(
        value=data.date_obj.date(),
        period=cast(DatePeriod, period),
        span=_strip_time_span_suffix(span),
    )


def _single_searched_date_span(
    text: str,
    *,
    today: date,
    languages: tuple[str, ...] | None,
    prefer_dates_from: Literal["past", "future"] | None = None,
) -> _ParsedDate | None:
    matches = _search_date_spans(
        text,
        today=today,
        languages=languages,
        return_time_span=False,
        prefer_dates_from=prefer_dates_from,
    )
    if len(matches) != 1:
        return None
    span, value = matches[0]
    parsed = _parse_date_span(
        span,
        today=today,
        languages=languages,
        prefer_dates_from=prefer_dates_from,
    )
    if parsed is not None:
        return parsed
    return _ParsedDate(
        value=value.date(),
        period="day",
        span=span,
    )


def _endpoint_date(
    parsed: _ParsedDate,
    *,
    endpoint: Literal["start", "end"],
    today: date,
) -> date:
    if parsed.period == "day":
        return parsed.value
    if parsed.period == "week":
        start = parsed.value
        end = min(date.fromordinal(start.toordinal() + 6), today)
        return start if endpoint == "start" else end
    if parsed.period == "month":
        if endpoint == "start":
            return parsed.value.replace(day=1)
        day = calendar.monthrange(parsed.value.year, parsed.value.month)[1]
        return parsed.value.replace(day=day)
    if endpoint == "start":
        return date(parsed.value.year, 1, 1)
    return date(parsed.value.year, 12, 31)


def _range_from_returned_time_span(
    matches: list[tuple[str, datetime]],
    *,
    today: date,
) -> NaturalDateRange | None:
    start: tuple[str, date] | None = None
    end: tuple[str, date] | None = None
    for span, value in matches:
        normalized = span.casefold()
        if normalized.endswith("(start)"):
            start = (span, value.date())
        elif normalized.endswith("(end)"):
            end = (span, value.date())
    if start is None or end is None or end[1] < start[1]:
        return None
    label = _relative_window_label(start=start[1], end=end[1], today=today) or (
        f"{start[1]} to {end[1]}"
    )
    return NaturalDateRange(
        label=label,
        start=start[1],
        end=end[1],
        evidence_spans=(start[0], end[0]),
    )


def _relative_window_label(*, start: date, end: date, today: date) -> str | None:
    if end < start or end != today:
        return None
    month_delta = (end.year - start.year) * 12 + (end.month - start.month)
    if month_delta > 0 and start.day == end.day:
        unit = "month" if month_delta == 1 else "months"
        return f"past {month_delta} {unit}"
    day_delta = end.toordinal() - start.toordinal()
    if day_delta > 0:
        if day_delta % 365 == 0:
            years = day_delta // 365
            unit = "year" if years == 1 else "years"
            return f"past {years} {unit}"
        if day_delta % 7 == 0:
            weeks = day_delta // 7
            unit = "week" if weeks == 1 else "weeks"
            return f"past {weeks} {unit}"
    return None


def _relative_base(value: date) -> datetime:
    return datetime.combine(value, time(hour=12))


def _normalize_compact_range_separators(value: str) -> str:
    text = str(value or "")
    output: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char not in {"-", "–", "—"}:
            output.append(char)
            index += 1
            continue
        prev_index = _previous_non_space_index(text, index - 1)
        next_index = _next_non_space_index(text, index + 1)
        if (
            prev_index is not None
            and next_index is not None
            and text[prev_index].isdigit()
            and text[next_index].isalpha()
        ):
            while output and output[-1].isspace():
                output.pop()
            output.append(" to ")
            index = next_index
            continue
        output.append(char)
        index += 1
    return "".join(output)


def _strip_time_span_suffix(value: str) -> str:
    stripped = str(value or "").strip()
    lowered = stripped.casefold()
    for suffix in ("(start)", "(end)"):
        if lowered.endswith(suffix):
            return stripped[: -len(suffix)].rstrip()
    return stripped


def _is_generated_time_span_endpoint(value: str) -> bool:
    lowered = str(value or "").strip().casefold()
    return lowered.endswith("(start)") or lowered.endswith("(end)")


def _span_has_explicit_year(value: str) -> bool:
    text = str(value or "")
    for index in range(max(len(text) - 3, 0)):
        candidate = text[index : index + 4]
        if not candidate.isdigit():
            continue
        previous_ok = index == 0 or not text[index - 1].isdigit()
        next_index = index + 4
        next_ok = next_index >= len(text) or not text[next_index].isdigit()
        if previous_ok and next_ok:
            return True
    return False


def _previous_non_space_index(value: str, index: int) -> int | None:
    while index >= 0:
        if not value[index].isspace():
            return index
        index -= 1
    return None


def _next_non_space_index(value: str, index: int) -> int | None:
    while index < len(value):
        if not value[index].isspace():
            return index
        index += 1
    return None


def _relative_label(*, count: int, unit: str) -> str:
    unit_name = {
        "d": "day",
        "w": "week",
        "m": "month",
        "mo": "month",
        "q": "quarter",
        "y": "year",
    }.get(unit, unit.removesuffix("s"))
    return f"past {unit_name}" if count == 1 else f"past {count} {unit_name}s"


def _subtract_period(today: date, *, count: int, unit: str) -> date:
    if unit in {"d", "day", "days"}:
        return today - timedelta(days=count)
    if unit in {"w", "week", "weeks"}:
        return today - timedelta(days=count * 7)
    if unit in {"m", "mo", "month", "months"}:
        return shift_months(today, -count)
    if unit in {"q", "quarter", "quarters"}:
        return shift_months(today, -(count * 3))
    return shift_months(today, -(count * 12))


def _add_period(value: date, *, count: int, unit: str) -> date:
    if unit in {"d", "day", "days"}:
        return value + timedelta(days=count)
    if unit in {"w", "week", "weeks"}:
        return value + timedelta(days=count * 7)
    if unit in {"m", "mo", "month", "months"}:
        return shift_months(value, count)
    if unit in {"q", "quarter", "quarters"}:
        return shift_months(value, count * 3)
    return shift_months(value, count * 12)
