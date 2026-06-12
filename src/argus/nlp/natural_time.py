from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Literal, cast

from dateparser.date import DateDataParser
from dateparser.search import search_dates

DatePeriod = Literal["day", "week", "month", "year"]


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

    start = _endpoint_date(parsed[0], endpoint="start", today=current_date)
    end = _endpoint_date(parsed[-1], endpoint="end", today=current_date)
    if end < start:
        return None
    label = _relative_window_label(start=start, end=end, today=current_date) or (
        f"{start} to {end}"
    )
    return NaturalDateRange(
        label=label,
        start=start,
        end=end,
        evidence_spans=(parsed[0].span, parsed[-1].span),
    )


def parse_date_text(
    text: str,
    *,
    today: date | None = None,
    endpoint: Literal["start", "end"] = "start",
    languages: tuple[str, ...] | None = None,
) -> date | None:
    parsed = _parse_date_span(
        str(text or ""),
        today=today or date.today(),
        languages=languages,
    )
    if parsed is None:
        return None
    return _endpoint_date(parsed, endpoint=endpoint, today=today or date.today())


def relative_range_label_from_text(
    text: str,
    *,
    today: date | None = None,
    languages: tuple[str, ...] | None = None,
) -> str | None:
    resolved = resolve_date_range_text(text, today=today, languages=languages)
    if resolved is None:
        return None
    return _relative_window_label(
        start=resolved.start,
        end=resolved.end,
        today=today or date.today(),
    )


def _search_date_spans(
    text: str,
    *,
    today: date,
    languages: tuple[str, ...] | None,
) -> list[tuple[str, datetime]]:
    settings = {
        "RELATIVE_BASE": _relative_base(today),
        "RETURN_AS_TIMEZONE_AWARE": False,
        "PREFER_DAY_OF_MONTH": "first",
        "PREFER_MONTH_OF_YEAR": "first",
    }
    results = search_dates(
        text,
        languages=list(languages) if languages else None,
        settings=settings,
    )
    return list(results or [])


def _parse_date_span(
    span: str,
    *,
    today: date,
    languages: tuple[str, ...] | None,
) -> _ParsedDate | None:
    parser = DateDataParser(
        languages=list(languages) if languages else None,
        settings={
            "RELATIVE_BASE": _relative_base(today),
            "RETURN_AS_TIMEZONE_AWARE": False,
            "PREFER_DAY_OF_MONTH": "first",
            "PREFER_MONTH_OF_YEAR": "first",
        },
    )
    data = parser.get_date_data(span)
    if data.date_obj is None:
        return None
    period = str(data.period or "day")
    if period not in {"day", "week", "month", "year"}:
        period = "day"
    return _ParsedDate(
        value=data.date_obj.date(),
        period=cast(DatePeriod, period),
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
