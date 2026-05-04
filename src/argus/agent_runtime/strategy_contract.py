from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from argus.agent_runtime.state.models import StrategySummary

SUPPORTED_STRATEGY_TYPES = {
    "buy_and_hold",
    "dca_accumulation",
    "indicator_threshold",
}

MONTH_ALIASES = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


@dataclass(frozen=True)
class DateRangeResolution:
    label: str
    start: date
    end: date

    @property
    def payload(self) -> dict[str, str]:
        return {"start": self.start.isoformat(), "end": self.end.isoformat()}

    @property
    def display(self) -> str:
        range_text = f"{format_display_date(self.start)} - {format_display_date(self.end)}"
        if self.label in {
            range_text,
            f"{format_display_date(self.start)} to {format_display_date(self.end)}",
        }:
            return range_text
        return f"{self.label} ({range_text})"


def canonical_strategy_type(
    raw_type: Any,
    *,
    entry_logic: Any = None,
    exit_logic: Any = None,
    cadence: Any = None,
) -> str:
    normalized = _normalize_token(raw_type)
    aliases = {
        "buy_hold": "buy_and_hold",
        "buy_and_hold": "buy_and_hold",
        "buyandhold": "buy_and_hold",
        "hold": "buy_and_hold",
        "dca": "dca_accumulation",
        "dollar_cost_averaging": "dca_accumulation",
        "recurring_accumulation": "dca_accumulation",
        "recurring_buys": "dca_accumulation",
        "dca_accumulation": "dca_accumulation",
        "rsi": "indicator_threshold",
        "rsi_threshold": "indicator_threshold",
        "rsi_mean_reversion": "indicator_threshold",
        "dip_buying": "indicator_threshold",
        "buy_the_dip": "indicator_threshold",
        "buying_dips": "indicator_threshold",
        "threshold": "indicator_threshold",
        "indicator": "indicator_threshold",
        "indicator_threshold": "indicator_threshold",
        "rule_based": "indicator_threshold",
    }
    if normalized in aliases:
        return aliases[normalized]
    if _has_value(cadence):
        return "dca_accumulation"
    if _has_value(entry_logic) or _has_value(exit_logic):
        return "indicator_threshold"
    return normalized


def explicit_buy_and_hold_requested(*values: Any) -> bool:
    text = " ".join(str(value) for value in values if isinstance(value, str)).lower()
    if not text:
        return False
    return bool(re.search(r"\bbuy\s*(?:-|and\s+)hold\b|\bbuy-and-hold\b", text))


def executable_strategy_type(strategy: StrategySummary | dict[str, Any]) -> str:
    payload = _strategy_payload(strategy)
    return canonical_strategy_type(
        payload.get("strategy_type"),
        entry_logic=payload.get("entry_logic"),
        exit_logic=payload.get("exit_logic"),
        cadence=payload.get("cadence"),
    )


def strategy_can_be_approved(strategy: StrategySummary | dict[str, Any]) -> bool:
    payload = _strategy_payload(strategy)
    strategy_type = executable_strategy_type(payload)
    if strategy_type not in SUPPORTED_STRATEGY_TYPES:
        return False
    if not _has_value(payload.get("asset_universe")) or not _has_value(payload.get("date_range")):
        return False
    if strategy_type == "indicator_threshold":
        return _has_value(payload.get("entry_logic")) and _has_value(payload.get("exit_logic"))
    return True


def display_strategy_type(strategy: StrategySummary | dict[str, Any]) -> str:
    payload = _strategy_payload(strategy)
    extra_parameters = payload.get("extra_parameters")
    raw_type = (
        extra_parameters.get("raw_strategy_type")
        if isinstance(extra_parameters, dict) and extra_parameters.get("raw_strategy_type")
        else payload.get("strategy_type")
    )
    normalized = _normalize_token(raw_type)
    if normalized in {"dip_buying", "buy_the_dip", "buying_dips"}:
        return "Dip Buying"
    if normalized in {"rsi_threshold", "rsi_mean_reversion"}:
        return "RSI Threshold"
    canonical = executable_strategy_type(payload)
    thesis_text = " ".join(
        str(value)
        for value in [
            payload.get("strategy_thesis"),
            payload.get("raw_user_phrasing"),
            payload.get("entry_logic"),
            payload.get("exit_logic"),
        ]
        if value
    ).lower()
    if canonical == "indicator_threshold" and "rsi" in thesis_text:
        if "dip" in thesis_text:
            return "Dip Buying"
        return "RSI Threshold"
    labels = {
        "buy_and_hold": "Buy and Hold",
        "dca_accumulation": "Recurring Buys",
        "indicator_threshold": "Indicator Threshold",
    }
    return labels.get(canonical, str(raw_type or "Strategy").replace("_", " ").title())


def display_strategy_slug(strategy: StrategySummary | dict[str, Any]) -> str:
    return display_strategy_type(strategy).lower()


def resolve_date_range(value: Any, *, today: date | None = None) -> DateRangeResolution:
    current_date = today or date.today()
    if isinstance(value, dict):
        start = _parse_date_token(value.get("start") or value.get("from"), today=current_date)
        end = _parse_date_token(value.get("end") or value.get("to"), today=current_date)
        if start is not None and end is not None:
            return DateRangeResolution(
                label=f"{format_display_date(start)} to {format_display_date(end)}",
                start=start,
                end=end,
            )

    if isinstance(value, str):
        normalized = _normalize_period_text(value)
        ytd = _year_to_date(normalized, today=current_date)
        if ytd is not None:
            return ytd
        since = _since_year(normalized, today=current_date)
        if since is not None:
            return since
        beginning_last_year = _beginning_last_year(normalized, today=current_date)
        if beginning_last_year is not None:
            return beginning_last_year
        relative = _relative_period(normalized, today=current_date)
        if relative is not None:
            return relative
        explicit = _explicit_iso_range(normalized)
        if explicit is not None:
            return explicit
        natural_explicit = _explicit_natural_range(normalized)
        if natural_explicit is not None:
            return natural_explicit

    start = _add_months(current_date, -12)
    return DateRangeResolution(label="past year", start=start, end=current_date)


def normalize_date_range_candidate(
    value: Any,
    *,
    raw_user_phrasing: str | None = None,
    today: date | None = None,
) -> Any:
    current_date = today or date.today()
    raw_period = _date_range_from_raw_phrase(raw_user_phrasing, today=current_date)
    if raw_period is not None:
        return raw_period
    if isinstance(raw_user_phrasing, str):
        raw_period_label = _extract_period_label_from_raw_phrase(
            raw_user_phrasing,
            today=current_date,
        )
        if raw_period_label is not None:
            return raw_period_label
    if isinstance(value, dict):
        return {
            key: nested_value
            for key, nested_value in value.items()
            if key in {"start", "end", "from", "to"}
        }
    return value


def format_display_date(value: date) -> str:
    return f"{value.strftime('%B')} {value.day}, {value.year}"


def _strategy_payload(strategy: StrategySummary | dict[str, Any]) -> dict[str, Any]:
    if isinstance(strategy, StrategySummary):
        return strategy.model_dump(mode="python")
    return dict(strategy)


def _normalize_token(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def _normalize_period_text(value: str) -> str:
    normalized = value.strip().lower()
    normalized = normalized.replace("-", "_")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def _has_value(value: Any) -> bool:
    if value is None or value == "":
        return False
    if isinstance(value, list):
        return bool(value)
    return True


def _parse_iso_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_date_token(value: Any, *, today: date) -> date | None:
    parsed = _parse_iso_date(value)
    if parsed is not None:
        return parsed
    if not isinstance(value, str):
        return None
    normalized = _normalize_token(value)
    if normalized in {"today", "now", "present", "to_date", "current_date"}:
        return today
    natural = _parse_natural_date(normalized)
    if natural is not None:
        return natural
    return None


def _date_range_from_raw_phrase(
    raw_user_phrasing: str | None,
    *,
    today: date,
) -> dict[str, str] | None:
    if not isinstance(raw_user_phrasing, str) or not raw_user_phrasing.strip():
        return None
    normalized = raw_user_phrasing.lower()
    normalized = re.sub(r"[^a-z0-9\s]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    starts_at_last_year_january = re.search(
        r"\b(?:jan(?:uary)?\s*(?:1|first)|beginning of)\s+last year\b",
        normalized,
    )
    ends_at_current_date = re.search(
        r"\b(?:to date|through today|until today|to today|to now|through now)\b",
        normalized,
    )
    if starts_at_last_year_january and ends_at_current_date:
        return {"start": date(today.year - 1, 1, 1).isoformat(), "end": "today"}
    natural_explicit = _explicit_natural_range(normalized)
    if natural_explicit is not None:
        return {
            "start": natural_explicit.start.isoformat(),
            "end": natural_explicit.end.isoformat(),
        }
    return None


def _extract_period_label_from_raw_phrase(
    raw_user_phrasing: str,
    *,
    today: date,
) -> str | None:
    del today
    normalized = raw_user_phrasing.lower()
    normalized = re.sub(r"[^a-z0-9\s]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    since_match = re.search(r"\bsince (?P<year>\d{4})\b", normalized)
    if since_match is not None:
        return f"since {since_match.group('year')}"
    ytd_match = re.search(r"\b(?:ytd|year to date)\b", normalized)
    if ytd_match is not None:
        return "year_to_date"
    relative_match = re.search(
        r"\b(?:past|last) (?P<count>\d+) "
        r"(?P<unit>day|days|week|weeks|month|months|year|years)\b",
        normalized,
    )
    if relative_match is not None:
        return relative_match.group(0)
    return None


def _explicit_iso_range(value: str) -> DateRangeResolution | None:
    match = re.fullmatch(
        r"(?P<start>\d{4}-\d{2}-\d{2})\s+(?:to|through|until)\s+(?P<end>\d{4}-\d{2}-\d{2})",
        value,
    )
    if match is None:
        return None
    start = _parse_iso_date(match.group("start"))
    end = _parse_iso_date(match.group("end"))
    if start is None or end is None:
        return None
    return DateRangeResolution(
        label=f"{format_display_date(start)} to {format_display_date(end)}",
        start=start,
        end=end,
    )


def _explicit_natural_range(value: str) -> DateRangeResolution | None:
    match = re.search(
        r"(?P<start_month>[a-z]{3,9})\s+"
        r"(?P<start_day>\d{1,2}|first)\s+"
        r"(?P<start_year>\d{4})\s+"
        r"(?:to|through|until|till|-)\s+"
        r"(?P<end_month>[a-z]{3,9})\s+"
        r"(?P<end_day>\d{1,2}|first)\s+"
        r"(?P<end_year>\d{4})",
        value,
    )
    if match is None:
        return None
    groups = match.groupdict()
    start = _build_natural_date(
        groups.get("start_month"),
        groups.get("start_day"),
        groups.get("start_year"),
    )
    end = _build_natural_date(
        groups.get("end_month"),
        groups.get("end_day"),
        groups.get("end_year"),
    )
    if start is None or end is None:
        return None
    return DateRangeResolution(
        label=f"{format_display_date(start)} to {format_display_date(end)}",
        start=start,
        end=end,
    )


def _parse_natural_date(value: str) -> date | None:
    match = re.fullmatch(
        r"(?P<month>[a-z]{3,9})\s+(?P<day>\d{1,2}|first)\s+(?P<year>\d{4})",
        value.strip().lower(),
    )
    if match is None:
        return None
    return _build_natural_date(
        match.group("month"),
        match.group("day"),
        match.group("year"),
    )


def _build_natural_date(
    month_value: Any,
    day_value: Any,
    year_value: Any,
) -> date | None:
    month = MONTH_ALIASES.get(str(month_value or "").lower())
    if month is None:
        return None
    day_text = str(day_value or "").lower()
    day = 1 if day_text == "first" else _int_or_none(day_text)
    year = _int_or_none(year_value)
    if day is None or year is None:
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _int_or_none(value: Any) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _year_to_date(value: str, *, today: date) -> DateRangeResolution | None:
    if value not in {"ytd", "year_to_date", "year to date"}:
        return None
    return DateRangeResolution(
        label="year to date",
        start=date(today.year, 1, 1),
        end=today,
    )


def _since_year(value: str, *, today: date) -> DateRangeResolution | None:
    match = re.fullmatch(r"since (?P<year>\d{4})", value)
    if match is None:
        return None
    year = int(match.group("year"))
    return DateRangeResolution(
        label=f"since {year}",
        start=date(year, 1, 1),
        end=today,
    )


def _beginning_last_year(value: str, *, today: date) -> DateRangeResolution | None:
    if value not in {
        "beginning of last year to now",
        "from the beginning of last year to now",
    }:
        return None
    return DateRangeResolution(
        label="beginning of last year to now",
        start=date(today.year - 1, 1, 1),
        end=today,
    )


def _relative_period(value: str, *, today: date) -> DateRangeResolution | None:
    if value in {"past_year", "last_year", "past year", "last year"}:
        return DateRangeResolution(
            label="past year",
            start=_add_months(today, -12),
            end=today,
        )

    patterns = [
        r"(?:over the )?(?:past|last) (?P<count>\d+) (?P<unit>day|days|week|weeks|month|months|year|years)",
        r"(?:past|last)_(?P<count>\d+)_(?P<unit>day|days|week|weeks|month|months|year|years)",
        r"(?P<count>\d+)\s*(?P<unit>d|w|m|mo|y)",
    ]
    for pattern in patterns:
        match = re.fullmatch(pattern, value)
        if match is None:
            continue
        count = int(match.group("count"))
        unit = match.group("unit")
        return DateRangeResolution(
            label=_relative_label(count=count, unit=unit),
            start=_subtract_period(today, count=count, unit=unit),
            end=today,
        )
    return None


def _relative_label(*, count: int, unit: str) -> str:
    unit_name = {
        "d": "day",
        "w": "week",
        "m": "month",
        "mo": "month",
        "y": "year",
    }.get(unit, unit.removesuffix("s"))
    return f"past {unit_name}" if count == 1 else f"past {count} {unit_name}s"


def _subtract_period(today: date, *, count: int, unit: str) -> date:
    if unit in {"d", "day", "days"}:
        return today - timedelta(days=count)
    if unit in {"w", "week", "weeks"}:
        return today - timedelta(days=count * 7)
    if unit in {"m", "mo", "month", "months"}:
        return _add_months(today, -count)
    return _add_months(today, -(count * 12))


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, _days_in_month(year, month))
    return date(year, month, day)


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        return 31
    next_month = date(year, month + 1, 1)
    return (next_month - timedelta(days=1)).day
