from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Literal, cast

from dateparser.date import DateDataParser
from dateparser.search import search_dates

DatePeriod = Literal["day", "week", "month", "year"]

_TIME_SPAN_SUFFIX_RE = re.compile(r"\s+\((?:start|end)\)$", flags=re.IGNORECASE)
_COMPACT_RANGE_SEPARATOR_RE = re.compile(r"(?<=\d)\s*[-–—]\s*(?=[^\W\d_])")


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


def resolve_date_window_text(
    text: str,
    *,
    today: date | None = None,
    languages: tuple[str, ...] | None = None,
) -> NaturalDateRange | None:
    """Resolve Argus-supported date-window language behind the NLP boundary.

    This function is the stable runtime-facing wrapper. It keeps dateparser as
    the multilingual engine while preserving Argus' rolling-window semantics for
    compact user phrases such as "past month", "last 3 months", and "2mo".
    """

    raw = str(text or "").strip()
    if not raw:
        return None
    current_date = today or date.today()
    normalized = _normalize_period_text(raw)

    relative = _relative_period(normalized, today=current_date)
    if relative is not None:
        return relative

    parsed_natural = resolve_date_range_text(
        raw,
        today=current_date,
        languages=languages,
    )
    if parsed_natural is not None:
        return parsed_natural

    multi_year = _multi_year_period(normalized, today=current_date)
    if multi_year is not None:
        return multi_year
    ytd = _year_to_date(normalized, today=current_date)
    if ytd is not None:
        return ytd
    since = _since_year(normalized, today=current_date)
    if since is not None:
        return since
    calendar_year = _calendar_year(normalized, today=current_date)
    if calendar_year is not None:
        return calendar_year
    beginning_last_year = _beginning_last_year(normalized, today=current_date)
    if beginning_last_year is not None:
        return beginning_last_year
    return None


def canonical_date_range_label_from_text(
    text: str,
    *,
    today: date | None = None,
    languages: tuple[str, ...] | None = None,
) -> str | None:
    resolved = resolve_date_window_text(text, today=today, languages=languages)
    if resolved is None:
        return None
    if resolved.label == f"{resolved.start} to {resolved.end}":
        return None
    return resolved.label


def resolve_current_message_date_patch(
    text: str,
    *,
    today: date | None = None,
    languages: tuple[str, ...] | None = None,
) -> dict[str, str] | None:
    """Resolve date edits/ranges stated in the current user message.

    The return shape intentionally matches the runtime patch contract because a
    turn can update only one endpoint, e.g. "change the end date to yesterday".
    """

    raw = str(text or "")
    current_date = today or date.today()
    tokens = _tokens(raw.casefold())

    year_so_far = _year_so_far_date_range_from_tokens(tokens, today=current_date)
    if year_so_far is not None:
        return year_so_far.payload

    start_endpoint = _date_endpoint_from_marker_tokens(
        tokens,
        markers={"start", "starting", "beginning"},
        endpoint="start",
    )
    end_endpoint = _date_endpoint_from_marker_tokens(
        tokens,
        markers={"end", "ending"},
        endpoint="end",
    )
    if start_endpoint is not None and end_endpoint is not None:
        return {"start": start_endpoint.isoformat(), "end": end_endpoint.isoformat()}
    if start_endpoint is not None and not _tokens_after_year_include_date_endpoint(
        tokens,
        endpoint=start_endpoint,
    ):
        return {"start": start_endpoint.isoformat()}
    if end_endpoint is not None:
        return {"end": end_endpoint.isoformat()}

    relative_endpoint = _relative_date_endpoint_from_marker_tokens(
        tokens,
        today=current_date,
        languages=languages,
    )
    if relative_endpoint is not None:
        return relative_endpoint

    parsed_natural = resolve_date_range_text(
        raw,
        today=current_date,
        languages=languages,
    )
    if parsed_natural is not None:
        return parsed_natural.payload

    has_named_date = contains_named_date_evidence(
        raw,
        today=current_date,
        languages=languages,
    )
    if not has_named_date:
        multi_year = _multi_year_period(raw, today=current_date)
        if multi_year is not None:
            return multi_year.payload
        calendar_year = _calendar_year(raw, today=current_date)
        if calendar_year is not None:
            return calendar_year.payload
    return None


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


def parse_relative_endpoint_text(
    text: str,
    *,
    today: date | None = None,
    languages: tuple[str, ...] | None = None,
) -> date | None:
    """Parse a short relative endpoint token without accepting calendar names.

    This is intentionally narrower than parse_date_text because current-turn edit
    markers like "end date to yesterday" scan nearby tokens. Dateparser can treat
    ordinary words or month names as dates, so endpoint repair only accepts dates
    adjacent to the current day.
    """

    current_date = today or date.today()
    parsed = parse_date_text(text, today=current_date, languages=languages)
    if parsed is None:
        return None
    if abs(parsed.toordinal() - current_date.toordinal()) <= 1:
        return parsed
    return None


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
) -> list[tuple[str, datetime]]:
    settings = {
        "RELATIVE_BASE": _relative_base(today),
        "RETURN_AS_TIMEZONE_AWARE": False,
        "PREFER_DAY_OF_MONTH": "first",
        "PREFER_MONTH_OF_YEAR": "first",
    }
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
    return _COMPACT_RANGE_SEPARATOR_RE.sub(" to ", str(value or ""))


def _strip_time_span_suffix(value: str) -> str:
    return _TIME_SPAN_SUFFIX_RE.sub("", str(value or "")).strip()


def _span_has_explicit_year(value: str) -> bool:
    return any(
        len(part) == 4 and part.isdigit()
        for part in re.findall(r"\b\d{4}\b", str(value or ""))
    )


def _normalize_period_text(value: str) -> str:
    normalized = _tokens_to_text(value)
    return _normalize_period_number_words(normalized)


def _normalize_period_number_words(value: str) -> str:
    number_words = {
        "one": "1",
        "two": "2",
        "three": "3",
        "four": "4",
        "five": "5",
        "six": "6",
        "seven": "7",
        "eight": "8",
        "nine": "9",
        "ten": "10",
    }
    period_units = {
        "day",
        "days",
        "week",
        "weeks",
        "month",
        "months",
        "quarter",
        "quarters",
        "year",
        "years",
    }
    tokens = _tokens(value)
    normalized: list[str] = []
    for index, token in enumerate(tokens):
        next_token = tokens[index + 1] if index + 1 < len(tokens) else None
        normalized.append(number_words[token] if token in number_words and next_token in period_units else token)
    return " ".join(normalized)


def _year_to_date(value: str, *, today: date) -> NaturalDateRange | None:
    tokens = _tokens(value)
    if value in {"ytd", "year_to_date", "year to date"}:
        return NaturalDateRange(
            label="year to date",
            start=date(today.year, 1, 1),
            end=today,
        )
    if {"so", "far"} <= set(tokens):
        if {"this", "year"} <= set(tokens):
            return NaturalDateRange(
                label="this year so far",
                start=date(today.year, 1, 1),
                end=today,
            )
        for token in tokens:
            if _is_four_digit_year(token) and int(token) == today.year:
                year = int(token)
                return NaturalDateRange(
                    label=f"{year} so far",
                    start=date(year, 1, 1),
                    end=today,
                )
    return None


def _year_so_far_date_range_from_tokens(
    tokens: list[str],
    *,
    today: date,
) -> NaturalDateRange | None:
    return _year_to_date(" ".join(tokens), today=today)


def _multi_year_period(value: str, *, today: date) -> NaturalDateRange | None:
    tokens = _tokens(value)
    years: list[int] = []
    for token in tokens:
        if _is_four_digit_year(token):
            year = int(token)
            if 1900 <= year <= today.year and year not in years:
                years.append(year)
    if len(years) != 2:
        return None
    if not (
        set(tokens)
        & {
            "and",
            "to",
            "through",
            "thru",
            "until",
            "till",
            "from",
            "between",
            "over",
            "during",
        }
    ):
        return None
    start_year, end_year = years
    if end_year < start_year:
        return None
    if end_year == today.year and (
        {"so", "far"} <= set(tokens)
        or set(tokens) & {"today", "now", "present", "current"}
    ):
        end = today
    else:
        end = date(end_year, 12, 31)
    return NaturalDateRange(
        label=f"{start_year} to {end_year}",
        start=date(start_year, 1, 1),
        end=end,
    )


def _since_year(value: str, *, today: date) -> NaturalDateRange | None:
    tokens = _tokens(value)
    if len(tokens) != 2 or tokens[0] != "since" or not _is_four_digit_year(tokens[1]):
        return None
    year = int(tokens[1])
    if year > today.year:
        return None
    return NaturalDateRange(
        label=f"since {year}",
        start=date(year, 1, 1),
        end=today,
    )


def _calendar_year(value: str, *, today: date) -> NaturalDateRange | None:
    tokens = _tokens(value)
    year_tokens = [
        token
        for token in tokens
        if _is_four_digit_year(token) and 1900 <= int(token) <= today.year
    ]
    if len(set(year_tokens)) != 1:
        return None
    for index, token in enumerate(tokens):
        if not _is_four_digit_year(token):
            continue
        year = int(token)
        if year < 1900 or year > today.year:
            continue
        previous = tokens[index - 1] if index > 0 else ""
        if len(tokens) == 1 or previous in {
            "in",
            "during",
            "throughout",
            "for",
            "over",
        }:
            return NaturalDateRange(
                label=str(year),
                start=date(year, 1, 1),
                end=date(year, 12, 31),
            )
    return None


def _beginning_last_year(value: str, *, today: date) -> NaturalDateRange | None:
    if value not in {
        "beginning of last year to now",
        "from the beginning of last year to now",
    }:
        return None
    return NaturalDateRange(
        label="beginning of last year to now",
        start=date(today.year - 1, 1, 1),
        end=today,
    )


def _relative_period(value: str, *, today: date) -> NaturalDateRange | None:
    tokens = _tokens(value)
    if tokens in (["past", "year"], ["last", "year"]):
        return NaturalDateRange(
            label="past year",
            start=shift_months(today, -12),
            end=today,
        )
    singular_periods = {
        "past day": ("day", 1),
        "last day": ("day", 1),
        "past week": ("week", 1),
        "last week": ("week", 1),
        "past month": ("month", 1),
        "last month": ("month", 1),
        "past quarter": ("quarter", 1),
        "last quarter": ("quarter", 1),
    }
    singular_period = singular_periods.get(" ".join(tokens))
    if singular_period is not None:
        unit, count = singular_period
        return NaturalDateRange(
            label=f"past {unit}",
            start=_subtract_period(today, count=count, unit=unit),
            end=today,
        )

    relative_label = _extract_relative_period_label(tokens)
    if relative_label is not None:
        parts = relative_label.split()
        if len(parts) == 2:
            _, unit = parts
            return NaturalDateRange(
                label=_relative_label(count=1, unit=unit),
                start=_subtract_period(today, count=1, unit=unit),
                end=today,
            )
        if len(parts) != 3 or not parts[1].isdigit():
            return None
        count = int(parts[1])
        unit = parts[2]
        return NaturalDateRange(
            label=_relative_label(count=count, unit=unit),
            start=_subtract_period(today, count=count, unit=unit),
            end=today,
        )

    compact = _split_compact_period_token(value)
    if compact is not None:
        count, unit = compact
        return NaturalDateRange(
            label=_relative_label(count=count, unit=unit),
            start=_subtract_period(today, count=count, unit=unit),
            end=today,
        )
    return None


def _date_endpoint_from_marker_tokens(
    tokens: list[str],
    *,
    markers: set[str],
    endpoint: Literal["start", "end"],
) -> date | None:
    for index, token in enumerate(tokens):
        if token not in markers:
            continue
        year_index = _first_year_token_index(tokens, start=index + 1, limit=index + 5)
        if year_index is None:
            continue
        year = int(tokens[year_index])
        return date(year, 12, 31) if endpoint == "end" else date(year, 1, 1)
    return None


def _relative_date_endpoint_from_marker_tokens(
    tokens: list[str],
    *,
    today: date,
    languages: tuple[str, ...] | None,
) -> dict[str, str] | None:
    endpoint_markers: tuple[tuple[set[str], Literal["start", "end"]], ...] = (
        ({"start", "starting", "beginning", "from"}, "start"),
        ({"end", "ending", "through", "thru", "until", "till"}, "end"),
    )
    for markers, endpoint in endpoint_markers:
        for index, token in enumerate(tokens):
            if token not in markers:
                continue
            relative_date = _relative_date_token_after_marker(
                tokens,
                start=index + 1,
                limit=index + 5,
                today=today,
                languages=languages,
            )
            if relative_date is not None:
                return {endpoint: relative_date.isoformat()}
    return None


def _relative_date_token_after_marker(
    tokens: list[str],
    *,
    start: int,
    limit: int,
    today: date,
    languages: tuple[str, ...] | None,
) -> date | None:
    for index in range(max(start, 0), min(limit, len(tokens))):
        parsed = parse_relative_endpoint_text(
            tokens[index],
            today=today,
            languages=languages,
        )
        if parsed is not None:
            return parsed
    return None


def _first_year_token_index(
    tokens: list[str],
    *,
    start: int,
    limit: int,
) -> int | None:
    for index in range(max(start, 0), min(limit, len(tokens))):
        token = tokens[index]
        if len(token) != 4 or not token.isdigit():
            continue
        year = int(token)
        if 1900 <= year <= 2100:
            return index
    return None


def _tokens_after_year_include_date_endpoint(
    tokens: list[str],
    *,
    endpoint: date,
) -> bool:
    year = str(endpoint.year)
    try:
        index = tokens.index(year)
    except ValueError:
        return False
    endpoint_tokens = {
        "to",
        "through",
        "until",
        "till",
        "end",
        "ending",
        "today",
        "now",
        "present",
        "current",
    }
    return any(token in endpoint_tokens for token in tokens[index + 1 :])


def _tokens(value: object) -> list[str]:
    if not isinstance(value, str):
        return []
    tokens: list[str] = []
    current: list[str] = []
    for char in value.casefold():
        if char.isalnum():
            current.append(char)
            continue
        if current:
            tokens.append("".join(current))
            current = []
    if current:
        tokens.append("".join(current))
    return tokens


def _tokens_to_text(value: str) -> str:
    return " ".join(_tokens(value))


def _extract_relative_period_label(tokens: list[str]) -> str | None:
    period_units = {
        "day",
        "days",
        "week",
        "weeks",
        "month",
        "months",
        "quarter",
        "quarters",
        "year",
        "years",
    }
    singular_units = {"day", "week", "month", "quarter", "year"}
    for index, token in enumerate(tokens):
        if token not in {"past", "last"}:
            continue
        next_token = tokens[index + 1] if index + 1 < len(tokens) else None
        following_token = tokens[index + 2] if index + 2 < len(tokens) else None
        if next_token is not None and next_token.isdigit() and following_token in period_units:
            return f"{token} {next_token} {following_token}"
        if next_token in singular_units:
            return f"{token} {next_token}"
    return None


def _split_compact_period_token(value: str) -> tuple[int, str] | None:
    tokens = _tokens(value)
    if len(tokens) != 1:
        return None
    token = tokens[0]
    unit_aliases = ("mo", "d", "w", "m", "q", "y")
    for unit in unit_aliases:
        if not token.endswith(unit):
            continue
        count_text = token[: -len(unit)]
        if count_text.isdigit():
            return int(count_text), unit
    return None


def _is_four_digit_year(value: str) -> bool:
    return len(value) == 4 and value.isdigit()


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
