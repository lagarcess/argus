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
from argus.domain.cadences import SUPPORTED_DCA_CADENCE_VALUES

# Single source of truth: the runtime contract's supported execution types are derived
# from the canonical capability registry. Re-exported here so existing importers keep
# `from argus.agent_runtime.strategy_contract import SUPPORTED_STRATEGY_TYPES`.
from argus.domain.capability_registry import SUPPORTED_STRATEGY_TYPES
from argus.domain.indicators import executable_indicator_spec
from argus.domain.slot_normalizer import normalize_template_name
from argus.domain.strategy_capabilities import STRATEGY_CAPABILITIES
from argus.nlp.natural_time import resolve_date_range_intent, shift_months


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
    if normalized in SUPPORTED_STRATEGY_TYPES:
        return normalized
    template = normalize_template_name(normalized)
    if template is not None:
        capability = STRATEGY_CAPABILITIES.get(template)
        if capability is not None and capability.execution_strategy_type:
            return capability.execution_strategy_type
        return template
    if _has_canonical_dca_cadence(cadence):
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
            value.get("start") or value.get("from"),
            today=current_date,
            endpoint="start",
        )
        end = _parse_date_token(
            value.get("end") or value.get("to"),
            today=current_date,
            endpoint="end",
        )
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
        special_window = _normalize_token(value)
        if special_window in {"since_ipo", "max_available", "maximum_available"}:
            return DateRangeResolution(
                label=(
                    "since IPO"
                    if "ipo" in special_window
                    else "maximum available history"
                ),
                start=date(1900, 1, 1),
                end=current_date,
            )
        machine_resolution = _date_range_resolution_from_intent(
            resolve_date_range_intent(
                _canonical_machine_date_range_intent(value),
                today=current_date,
            ),
            today=current_date,
        )
        if machine_resolution is not None:
            return machine_resolution
    start = shift_months(current_date, -12)
    return DateRangeResolution(
        label="past year",
        start=start,
        end=current_date,
        used_default=True,
    )


def resolve_executable_date_range(
    value: Any,
    *,
    extra_parameters: Mapping[str, Any] | None = None,
    today: date | None = None,
) -> DateRangeResolution:
    current_date = today or date.today()
    explicit_resolution = resolve_date_range(value, today=current_date)
    if not explicit_resolution.used_default:
        return explicit_resolution

    date_range_intent = (
        extra_parameters.get("date_range_intent")
        if isinstance(extra_parameters, Mapping)
        else None
    )
    intent_resolution = resolve_date_range_intent(
        date_range_intent,
        today=current_date,
    )
    resolved_intent = _date_range_resolution_from_intent(
        intent_resolution,
        today=current_date,
    )
    if resolved_intent is not None:
        return resolved_intent

    return explicit_resolution


def requested_date_range_from_strategy(
    strategy: Mapping[str, Any],
) -> dict[str, str] | None:
    extra_parameters = strategy.get("extra_parameters")
    if not isinstance(extra_parameters, Mapping):
        return None
    requested = extra_parameters.get("requested_date_range")
    if not (
        isinstance(requested, Mapping)
        and isinstance(requested.get("start"), str)
        and isinstance(requested.get("end"), str)
    ):
        return None
    return resolve_executable_date_range(requested).payload


def normalize_date_range_candidate(
    value: Any,
    *,
    raw_user_phrasing: str | None = None,
    today: date | None = None,
) -> Any:
    del raw_user_phrasing, today
    if isinstance(value, dict):
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


def _canonical_machine_date_range_intent(value: str) -> dict[str, Any] | None:
    raw = value.strip().lower()
    if raw == "year_to_date":
        return {"kind": "year_to_date", "anchor": "today", "confidence": 1.0}
    if " " in raw:
        return None
    parts = raw.split("_")
    if len(parts) != 3 or parts[0] not in {"last", "past"}:
        return None
    count = _int_or_none(parts[1])
    if count is None or count <= 0:
        return None
    unit = parts[2][:-1] if parts[2].endswith("s") else parts[2]
    if unit not in {"day", "week", "month", "quarter", "year"}:
        return None
    return {
        "kind": "rolling_window",
        "count": count,
        "unit": unit,
        "anchor": "today",
        "confidence": 1.0,
    }


def _date_range_resolution_from_intent(
    intent_resolution: Any,
    *,
    today: date,
) -> DateRangeResolution | None:
    if intent_resolution is None:
        return None
    start = _parse_date_token(
        intent_resolution.payload.get("start"),
        today=today,
        endpoint="start",
    )
    end = _parse_date_token(
        intent_resolution.payload.get("end"),
        today=today,
        endpoint="end",
    )
    if start is None or end is None:
        return None
    return DateRangeResolution(
        label=intent_resolution.label,
        start=start,
        end=end,
    )


def _first_present_endpoint(value: dict[Any, Any], *keys: str) -> Any | None:
    for key in keys:
        endpoint = value.get(key)
        if endpoint not in (None, "", [], {}):
            return endpoint
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


def _has_value(value: Any) -> bool:
    if value is None or value == "":
        return False
    if isinstance(value, list):
        return bool(value)
    return True


def _has_canonical_dca_cadence(value: Any) -> bool:
    if isinstance(value, str):
        return _normalize_token(value) in SUPPORTED_DCA_CADENCE_VALUES
    if isinstance(value, list):
        return any(_has_canonical_dca_cadence(item) for item in value)
    return False


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


def _parse_iso_month(value: Any, *, endpoint: str) -> date | None:
    if not isinstance(value, str):
        return None
    parts = value.strip().split("-")
    if len(parts) != 2:
        return None
    year = _int_or_none(parts[0])
    month = _int_or_none(parts[1])
    if year is None or month is None or not 1 <= month <= 12:
        return None
    day = 1 if endpoint == "start" else _last_day_of_month(year, month)
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _parse_date_token(
    value: Any,
    *,
    today: date,
    endpoint: str | None = None,
) -> date | None:
    if isinstance(value, str) and value.strip().casefold() in {
        "today",
        "current_date",
    }:
        return today
    parsed = _parse_iso_date(value)
    if parsed is not None:
        return parsed
    if endpoint is not None:
        parsed_month = _parse_iso_month(value, endpoint=endpoint)
        if parsed_month is not None:
            return parsed_month
    return None


def _explicit_iso_range(value: str) -> DateRangeResolution | None:
    collapsed = _collapse_spaces(value.lower())
    if " to " not in collapsed:
        return None
    start_text, end_text = collapsed.split(" to ", 1)
    start = _parse_iso_date(start_text.strip()) or _parse_iso_month(
        start_text.strip(),
        endpoint="start",
    )
    end = _parse_iso_date(end_text.strip()) or _parse_iso_month(
        end_text.strip(),
        endpoint="end",
    )
    if start is None or end is None:
        return None
    return DateRangeResolution(
        label=f"{format_display_date(start)} to {format_display_date(end)}",
        start=start,
        end=end,
    )


def _last_day_of_month(year: int, month: int) -> int:
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    return (next_month - timedelta(days=1)).day


def _int_or_none(value: Any) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _collapse_spaces(value: str) -> str:
    return " ".join(value.split())
