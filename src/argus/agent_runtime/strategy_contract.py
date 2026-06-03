from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from argus.agent_runtime.state.models import StrategySummary
from argus.domain.backtesting.rules import (
    rule_spec_from_moving_average_crossover_rules,
    rule_spec_from_signal_rule,
    validate_rule_spec,
)
from argus.domain.indicators import executable_indicator_spec
from argus.domain.slot_normalizer import normalize_template_name

SUPPORTED_STRATEGY_TYPES = {
    "buy_and_hold",
    "dca_accumulation",
    "indicator_threshold",
    "signal_strategy",
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
    used_default: bool = False

    @property
    def payload(self) -> dict[str, str]:
        return {"start": self.start.isoformat(), "end": self.end.isoformat()}

    @property
    def display(self) -> str:
        range_text = (
            f"{format_display_date(self.start)} - {format_display_date(self.end)}"
        )
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
    del entry_logic, exit_logic
    normalized = _normalize_token(raw_type)
    template = normalize_template_name(normalized)
    template_strategy_types = {
        "buy_and_hold": "buy_and_hold",
        "dca_accumulation": "dca_accumulation",
        "buy_the_dip": "indicator_threshold",
        "rsi_mean_reversion": "indicator_threshold",
        "moving_average_crossover": "signal_strategy",
    }
    if template in template_strategy_types:
        return template_strategy_types[template]
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
        "signal": "signal_strategy",
        "signal_strategy": "signal_strategy",
        "moving_average_crossover": "signal_strategy",
        "ma_crossover": "signal_strategy",
        "golden_cross": "signal_strategy",
        "death_cross": "signal_strategy",
    }
    if normalized in aliases:
        return aliases[normalized]
    if _has_value(cadence):
        return "dca_accumulation"
    return normalized


def executable_strategy_type(strategy: StrategySummary | dict[str, Any]) -> str:
    payload = _strategy_payload(strategy)
    explicit = _explicit_strategy_type(payload)
    if explicit in {"buy_and_hold", "dca_accumulation"}:
        return explicit
    if _has_structured_moving_average_rule(payload):
        return "signal_strategy"
    if explicit == "indicator_threshold":
        return explicit
    if explicit == "signal_strategy":
        return "signal_strategy"
    return canonical_strategy_type(
        payload.get("strategy_type"),
        entry_logic=payload.get("entry_logic"),
        exit_logic=payload.get("exit_logic"),
        cadence=payload.get("cadence"),
    )


def executable_strategy_type_from_extracted_fields(
    fields: Mapping[str, Any],
) -> str | None:
    """Resolve only the executable strategy contract from extracted LLM fields."""
    payload = dict(fields)
    if _has_executable_signal_rule(payload):
        return "signal_strategy"

    strategy_type = canonical_strategy_type(fields.get("strategy_type"), cadence=None)
    if strategy_type == "signal_strategy":
        return None
    if strategy_type in SUPPORTED_STRATEGY_TYPES:
        return strategy_type

    indicator = fields.get("indicator")
    if not isinstance(indicator, str) or not indicator.strip():
        return None
    if executable_indicator_spec(indicator.strip().lower()) is None:
        return None
    if not _has_value(fields.get("entry_threshold")) or not _has_value(
        fields.get("exit_threshold")
    ):
        return None
    return "indicator_threshold"


def strategy_can_be_approved(strategy: StrategySummary | dict[str, Any]) -> bool:
    payload = _strategy_payload(strategy)
    strategy_type = executable_strategy_type(payload)
    if strategy_type not in SUPPORTED_STRATEGY_TYPES:
        return False
    if has_partial_explicit_date_range(payload.get("date_range")):
        return False
    if not _has_value(payload.get("asset_universe")) or not _has_value(
        payload.get("date_range")
    ):
        return False
    if strategy_type == "dca_accumulation" and not _has_value(
        payload.get("capital_amount")
    ):
        return False
    if strategy_type == "indicator_threshold":
        return _has_value(payload.get("entry_logic")) and _has_value(
            payload.get("exit_logic")
        )
    if strategy_type == "signal_strategy":
        return _has_executable_signal_rule(payload)
    return True


def display_strategy_type(strategy: StrategySummary | dict[str, Any]) -> str:
    payload = _strategy_payload(strategy)
    extra_parameters = payload.get("extra_parameters")
    raw_type = (
        extra_parameters.get("raw_strategy_type")
        if isinstance(extra_parameters, dict)
        and extra_parameters.get("raw_strategy_type")
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
        "signal_strategy": "Signal Strategy",
    }
    return labels.get(canonical, str(raw_type or "Strategy").replace("_", " ").title())

def display_strategy_slug(strategy: StrategySummary | dict[str, Any]) -> str:
    return display_strategy_type(strategy).lower()


def resolve_date_range(value: Any, *, today: date | None = None) -> DateRangeResolution:
    current_date = today or date.today()
    if isinstance(value, dict):
        start = _parse_date_token(
            value.get("start") or value.get("from"), today=current_date
        )
        end = _parse_date_token(value.get("end") or value.get("to"), today=current_date)
        if start is not None and end is not None:
            return DateRangeResolution(
                label=f"{format_display_date(start)} to {format_display_date(end)}",
                start=start,
                end=end,
            )

    if isinstance(value, str):
        explicit = _explicit_iso_range(value)
        if explicit is not None:
            return explicit
        normalized = _normalize_period_text(value)
        if normalized in {"since_ipo", "since ipo", "max_available", "maximum available"}:
            return DateRangeResolution(
                label="since IPO" if "ipo" in normalized else "maximum available history",
                start=date(1900, 1, 1),
                end=current_date,
            )
        natural_explicit = _explicit_natural_range(normalized, today=current_date)
        if natural_explicit is not None:
            return natural_explicit
        multi_year = _multi_year_period(normalized, today=current_date)
        if multi_year is not None:
            return multi_year
        ytd = _year_to_date(normalized, today=current_date)
        if ytd is not None:
            return ytd
        since = _since_year(normalized, today=current_date)
        if since is not None:
            return since
        calendar_year = _calendar_year(normalized)
        if calendar_year is not None:
            return calendar_year
        beginning_last_year = _beginning_last_year(normalized, today=current_date)
        if beginning_last_year is not None:
            return beginning_last_year
        relative = _relative_period(normalized, today=current_date)
        if relative is not None:
            return relative
    start = _add_months(current_date, -12)
    return DateRangeResolution(
        label="past year",
        start=start,
        end=current_date,
        used_default=True,
    )


def normalize_date_range_candidate(
    value: Any,
    *,
    raw_user_phrasing: str | None = None,
    today: date | None = None,
) -> Any:
    if isinstance(value, dict):
        if not _date_range_dict_uses_natural_endpoint(value):
            relative_label = _relative_date_label_from_user_phrasing(
                raw_user_phrasing,
                today=today,
            )
            if relative_label is not None:
                return relative_label
        return {
            key: nested_value
            for key, nested_value in value.items()
            if key in {"start", "end", "from", "to"}
        }
    return value


def has_partial_explicit_date_range(value: Any) -> bool:
    """Return true when a structured date range has only one endpoint."""

    if not isinstance(value, dict):
        return False
    start = _first_present_endpoint(value, "start", "from")
    end = _first_present_endpoint(value, "end", "to")
    return (start is not None) != (end is not None)


def _first_present_endpoint(value: dict[Any, Any], *keys: str) -> Any | None:
    for key in keys:
        endpoint = value.get(key)
        if endpoint not in (None, "", [], {}):
            return endpoint
    return None


def _date_range_dict_uses_natural_endpoint(value: dict[Any, Any]) -> bool:
    endpoints = [value.get(key) for key in ("start", "end", "from", "to")]
    endpoint_values = [endpoint for endpoint in endpoints if endpoint not in (None, "")]
    return any(
        isinstance(endpoint, str) and _parse_iso_date(endpoint) is None
        for endpoint in endpoint_values
    )


def _relative_date_label_from_user_phrasing(
    raw_user_phrasing: str | None,
    *,
    today: date | None,
) -> str | None:
    if not isinstance(raw_user_phrasing, str) or not raw_user_phrasing.strip():
        return None
    current_date = today or date.today()
    normalized = _normalize_period_text(raw_user_phrasing)
    year_to_date = _year_to_date(normalized, today=current_date)
    if year_to_date is not None:
        return year_to_date.label
    since_year = _find_since_year(_tokens(normalized))
    if since_year is not None:
        return f"since {since_year}"
    beginning_last_year = _beginning_last_year(normalized, today=current_date)
    if beginning_last_year is not None:
        return beginning_last_year.label
    relative = _relative_period(normalized, today=current_date)
    if relative is not None:
        return relative.label
    return None


def format_display_date(value: date) -> str:
    return f"{value.strftime('%B')} {value.day}, {value.year}"


def _strategy_payload(strategy: StrategySummary | dict[str, Any]) -> dict[str, Any]:
    if isinstance(strategy, StrategySummary):
        return strategy.model_dump(mode="python")
    return dict(strategy)


def _normalize_token(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    parts: list[str] = []
    previous_was_separator = True
    for char in value.strip().lower():
        if char.isalnum():
            parts.append(char)
            previous_was_separator = False
            continue
        if not previous_was_separator:
            parts.append("_")
            previous_was_separator = True
    return "".join(parts).strip("_")


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
        if token in number_words and next_token in period_units:
            normalized.append(number_words[token])
        else:
            normalized.append(token)
    return " ".join(normalized)


def _has_value(value: Any) -> bool:
    if value is None or value == "":
        return False
    if isinstance(value, list):
        return bool(value)
    return True


def _explicit_strategy_type(payload: dict[str, Any]) -> str | None:
    candidates: list[Any] = [payload.get("strategy_type")]
    extra_parameters = payload.get("extra_parameters")
    if isinstance(extra_parameters, dict):
        candidates.extend(
            [
                extra_parameters.get("raw_strategy_type"),
                extra_parameters.get("strategy_type"),
                extra_parameters.get("template"),
            ]
        )
    for candidate in candidates:
        if not isinstance(candidate, str) or not candidate:
            continue
        normalized = canonical_strategy_type(
            candidate,
            entry_logic=payload.get("entry_logic"),
            exit_logic=payload.get("exit_logic"),
            cadence=payload.get("cadence"),
        )
        if normalized in SUPPORTED_STRATEGY_TYPES:
            return normalized
    return None


def _has_structured_moving_average_rule(payload: dict[str, Any]) -> bool:
    for field_name in ("entry_rule", "exit_rule"):
        rule = payload.get(field_name)
        if isinstance(rule, dict) and rule.get("type") == "moving_average_crossover":
            return True
    extra_parameters = payload.get("extra_parameters")
    if not isinstance(extra_parameters, dict):
        return False
    for field_name in ("entry_rule", "exit_rule"):
        rule = extra_parameters.get(field_name)
        if isinstance(rule, dict) and rule.get("type") == "moving_average_crossover":
            return True
    return False


def _has_executable_signal_rule(payload: dict[str, Any]) -> bool:
    rule_spec = payload.get("rule_spec")
    if _valid_rule_spec_payload(rule_spec):
        return True
    if _valid_typed_signal_rule(
        entry_rule=payload.get("entry_rule"),
        exit_rule=payload.get("exit_rule"),
    ):
        return True
    extra_parameters = payload.get("extra_parameters")
    if not isinstance(extra_parameters, dict):
        return False
    return _valid_rule_spec_payload(
        extra_parameters.get("rule_spec")
    ) or _valid_typed_signal_rule(
        entry_rule=extra_parameters.get("entry_rule"),
        exit_rule=extra_parameters.get("exit_rule"),
    )


def _valid_rule_spec_payload(value: Any) -> bool:
    if not isinstance(value, dict) or not value:
        return False
    try:
        validate_rule_spec(value)
        return True
    except (TypeError, ValueError):
        try:
            converted = rule_spec_from_signal_rule(value)
        except (TypeError, ValueError):
            return False
        return converted is not None


def _valid_typed_signal_rule(*, entry_rule: Any, exit_rule: Any) -> bool:
    if not isinstance(entry_rule, dict) or not entry_rule:
        return False
    try:
        return (
            rule_spec_from_moving_average_crossover_rules(
                entry_rule=entry_rule,
                exit_rule=exit_rule if isinstance(exit_rule, dict) else None,
            )
            is not None
        )
    except (TypeError, ValueError):
        try:
            return rule_spec_from_signal_rule(entry_rule) is not None
        except (TypeError, ValueError):
            return False


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
    relative = parse_relative_date_token(normalized, today=today)
    if relative is not None:
        return relative
    natural = _parse_natural_date(normalized)
    if natural is not None:
        return natural
    return None


def parse_relative_date_token(value: Any, *, today: date | None = None) -> date | None:
    current_date = today or date.today()
    normalized = _normalize_token(value)
    if normalized == "yesterday":
        return current_date - timedelta(days=1)
    if normalized in {"today", "now", "present", "current", "to_date", "current_date"}:
        return current_date
    return None


def _explicit_iso_range(value: str) -> DateRangeResolution | None:
    collapsed = _collapse_spaces(value.lower())
    start: date | None = None
    end: date | None = None
    for connector in (" to ", " through ", " until ", " till "):
        if connector not in collapsed:
            continue
        start_text, end_text = collapsed.split(connector, 1)
        start = _parse_iso_date(start_text.strip())
        end = _parse_iso_date(end_text.strip())
        if start is not None and end is not None:
            break
    if start is None or end is None:
        return None
    return DateRangeResolution(
        label=f"{format_display_date(start)} to {format_display_date(end)}",
        start=start,
        end=end,
    )


def _explicit_natural_range(
    value: str,
    *,
    today: date,
) -> DateRangeResolution | None:
    tokens = _tokens(value)
    shared_year_span = _month_span_with_shared_year(tokens)
    if shared_year_span is not None:
        return shared_year_span
    start: date | None = None
    end: date | None = None
    connectors = {"to", "through", "until", "till"}
    for index in range(0, len(tokens)):
        start_candidate = _natural_endpoint_candidate(
            tokens,
            index,
            today=today,
            endpoint="start",
        )
        if start_candidate is None:
            continue
        candidate_start, next_index = start_candidate
        if next_index >= len(tokens) or tokens[next_index] not in connectors:
            continue
        end_candidate = _natural_endpoint_candidate(
            tokens,
            next_index + 1,
            today=today,
            endpoint="end",
        )
        if end_candidate is None:
            continue
        candidate_end, _ = end_candidate
        start = candidate_start
        end = candidate_end
        break
    if start is None or end is None:
        return None
    return DateRangeResolution(
        label=f"{format_display_date(start)} to {format_display_date(end)}",
        start=start,
        end=end,
    )


def _month_span_with_shared_year(tokens: list[str]) -> DateRangeResolution | None:
    connectors = {"to", "through", "until", "till"}
    for index, token in enumerate(tokens):
        start_month = MONTH_ALIASES.get(token)
        if start_month is None:
            continue
        connector_index = index + 1
        end_month_index = index + 2
        year_index = index + 3
        if year_index >= len(tokens):
            continue
        if tokens[connector_index] not in connectors:
            continue
        end_month = MONTH_ALIASES.get(tokens[end_month_index])
        if end_month is None:
            continue
        year = _int_or_none(tokens[year_index])
        if year is None:
            continue
        if end_month < start_month:
            continue
        start = date(year, start_month, 1)
        end = date(year, end_month, _last_day_of_month(year, end_month))
        return DateRangeResolution(
            label=f"{format_display_date(start)} to {format_display_date(end)}",
            start=start,
            end=end,
        )
    return None


def _natural_endpoint_candidate(
    tokens: list[str],
    index: int,
    *,
    today: date,
    endpoint: str,
) -> tuple[date, int] | None:
    if index >= len(tokens):
        return None
    token = tokens[index]
    if token in {"today", "now", "present"}:
        return today, index + 1
    if index + 2 < len(tokens):
        natural = _build_natural_date(tokens[index], tokens[index + 1], tokens[index + 2])
        if natural is not None:
            return natural, index + 3
    if index + 1 < len(tokens):
        month_year = _build_month_year_date(
            tokens[index],
            tokens[index + 1],
            endpoint=endpoint,
        )
        if month_year is not None:
            return month_year, index + 2
    return None


def _build_month_year_date(
    month_value: Any,
    year_value: Any,
    *,
    endpoint: str,
) -> date | None:
    month = MONTH_ALIASES.get(str(month_value or "").lower())
    year = _int_or_none(year_value)
    if month is None or year is None:
        return None
    day = 1 if endpoint == "start" else _last_day_of_month(year, month)
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _last_day_of_month(year: int, month: int) -> int:
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    return (next_month - timedelta(days=1)).day


def _parse_natural_date(value: str) -> date | None:
    tokens = _tokens(value)
    if len(tokens) != 3:
        return None
    return _build_natural_date(tokens[0], tokens[1], tokens[2])


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
    tokens = _tokens(value)
    if value in {"ytd", "year_to_date", "year to date"}:
        return DateRangeResolution(
            label="year to date",
            start=date(today.year, 1, 1),
            end=today,
        )
    if {"so", "far"} <= set(tokens):
        if {"this", "year"} <= set(tokens):
            return DateRangeResolution(
                label="this year so far",
                start=date(today.year, 1, 1),
                end=today,
            )
        for token in tokens:
            if _is_four_digit_year(token) and int(token) == today.year:
                year = int(token)
                return DateRangeResolution(
                    label=f"{year} so far",
                    start=date(year, 1, 1),
                    end=today,
                )
    return None


def _multi_year_period(value: str, *, today: date) -> DateRangeResolution | None:
    tokens = _tokens(value)
    years: list[int] = []
    for token in tokens:
        if _is_four_digit_year(token):
            year = int(token)
            if year <= today.year and year not in years:
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
    return DateRangeResolution(
        label=f"{start_year} to {end_year}",
        start=date(start_year, 1, 1),
        end=end,
    )


def _since_year(value: str, *, today: date) -> DateRangeResolution | None:
    tokens = _tokens(value)
    if len(tokens) != 2 or tokens[0] != "since" or not _is_four_digit_year(tokens[1]):
        return None
    year = int(tokens[1])
    return DateRangeResolution(
        label=f"since {year}",
        start=date(year, 1, 1),
        end=today,
    )


def _calendar_year(value: str) -> DateRangeResolution | None:
    tokens = _tokens(value)
    year_tokens = [token for token in tokens if _is_four_digit_year(token)]
    if len(set(year_tokens)) != 1:
        return None
    for index, token in enumerate(tokens):
        if not _is_four_digit_year(token):
            continue
        year = int(token)
        previous = tokens[index - 1] if index > 0 else ""
        if len(tokens) == 1 or previous in {
            "in",
            "during",
            "throughout",
            "for",
            "over",
        }:
            return DateRangeResolution(
                label=str(year),
                start=date(year, 1, 1),
                end=date(year, 12, 31),
            )
    return None


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
    tokens = _tokens(value)
    if tokens in (["past", "year"], ["last", "year"]):
        return DateRangeResolution(
            label="past year",
            start=_add_months(today, -12),
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
        return DateRangeResolution(
            label=f"past {unit}",
            start=_subtract_period(today, count=count, unit=unit),
            end=today,
        )

    relative_label = _extract_relative_period_label(tokens)
    if relative_label is not None:
        parts = relative_label.split()
        if len(parts) == 2:
            _, unit = parts
            return DateRangeResolution(
                label=_relative_label(count=1, unit=unit),
                start=_subtract_period(today, count=1, unit=unit),
                end=today,
            )
        if len(parts) != 3 or not parts[1].isdigit():
            return None
        count = int(parts[1])
        unit = parts[2]
        return DateRangeResolution(
            label=_relative_label(count=count, unit=unit),
            start=_subtract_period(today, count=count, unit=unit),
            end=today,
        )

    compact = _split_compact_period_token(value)
    if compact is not None:
        count, unit = compact
        return DateRangeResolution(
            label=_relative_label(count=count, unit=unit),
            start=_subtract_period(today, count=count, unit=unit),
            end=today,
        )
    return None


def _tokens(value: Any) -> list[str]:
    if not isinstance(value, str):
        return []
    tokens: list[str] = []
    current: list[str] = []
    for char in value.lower():
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


def _collapse_spaces(value: str) -> str:
    return " ".join(value.split())


def _contains_any_phrase(value: str, phrases: set[str]) -> bool:
    return any(_contains_phrase(value, phrase) for phrase in phrases)


def _contains_phrase(value: str, phrase: str) -> bool:
    tokens = _tokens(value)
    phrase_tokens = _tokens(phrase)
    if not phrase_tokens:
        return False
    if len(phrase_tokens) > len(tokens):
        return False
    for index in range(0, len(tokens) - len(phrase_tokens) + 1):
        if tokens[index : index + len(phrase_tokens)] == phrase_tokens:
            return True
    return False


def _find_since_year(tokens: list[str]) -> str | None:
    for index, token in enumerate(tokens[:-1]):
        if token == "since" and _is_four_digit_year(tokens[index + 1]):
            return tokens[index + 1]
    return None


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


def _extract_ago_to_now_label(tokens: list[str]) -> tuple[str, str] | None:
    units = {"day", "days", "week", "weeks", "month", "months", "year", "years"}
    connectors = {"to", "through", "until", "till"}
    endpoints = {"now", "today", "present"}
    for index in range(0, max(len(tokens) - 4, 0)):
        count = tokens[index]
        unit = tokens[index + 1]
        if not count.isdigit() or unit not in units or tokens[index + 2] != "ago":
            continue
        if tokens[index + 3] in connectors and tokens[index + 4] in endpoints:
            return count, unit
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
        return _add_months(today, -count)
    if unit in {"q", "quarter", "quarters"}:
        return _add_months(today, -(count * 3))
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
