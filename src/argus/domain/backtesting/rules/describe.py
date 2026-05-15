from __future__ import annotations

from typing import Any

from argus.domain.indicators import executable_indicator_spec

from .models import Condition, RuleSpec, SeriesRef


def describe_rule_spec(rule_spec: RuleSpec | None, side: str) -> str | None:
    if not isinstance(rule_spec, dict):
        return None
    group = rule_spec.get(side)
    if not isinstance(group, dict):
        return None
    raw_conditions = group.get("conditions")
    if not isinstance(raw_conditions, list) or not raw_conditions:
        return None

    condition_texts = [
        text
        for condition in raw_conditions
        if isinstance(condition, dict)
        for text in [describe_condition(condition)]
        if text
    ]
    if not condition_texts:
        return None
    combinator = str(group.get("combinator") or "all").lower()
    joiner = " or " if combinator == "any" else " and "
    return joiner.join(condition_texts)


def describe_condition(condition: Condition) -> str | None:
    left = _series_ref_text(condition.get("left"))
    right = _series_ref_text(condition.get("right"))
    operator = str(condition.get("operator") or "").lower()
    if left is None or right is None:
        return None

    threshold_text = _threshold_condition_text(
        left=left,
        right=right,
        operator=operator,
        right_value=condition.get("right"),
    )
    if threshold_text is not None:
        return threshold_text

    operator_text = {
        "lt": "is below",
        "lte": "is at or below",
        "gt": "is above",
        "gte": "is at or above",
        "cross_above": "crosses above",
        "cross_below": "crosses below",
    }.get(operator)
    if operator_text is None:
        return None
    return f"{left} {operator_text} {right}"


def _threshold_condition_text(
    *,
    left: str,
    right: str,
    operator: str,
    right_value: Any,
) -> str | None:
    if not isinstance(right_value, int | float):
        return None
    if operator == "lte":
        return f"{left} is {_format_number(right_value)} or lower"
    if operator == "lt":
        return f"{left} is below {_format_number(right_value)}"
    if operator == "gte":
        return f"{left} is {_format_number(right_value)} or higher"
    if operator == "gt":
        return f"{left} is above {_format_number(right_value)}"
    return None


def _series_ref_text(value: Any) -> str | None:
    if isinstance(value, int | float):
        return _format_number(value)
    if not isinstance(value, dict):
        return None

    kind = str(value.get("kind") or "").lower()
    if kind == "price":
        field = str(value.get("field") or "close").strip()
        return field.replace("_", " ").title() if field else "Price"
    if kind == "volume":
        return "Volume"
    if kind != "indicator":
        return None
    return _indicator_ref_text(value)


def _indicator_ref_text(ref: SeriesRef) -> str | None:
    key = str(ref.get("key") or "").strip().lower()
    spec = executable_indicator_spec(key)
    if spec is None:
        return None
    label = spec.label
    if key in {"sma", "ema"}:
        return f"{_indicator_period(ref, spec.default_period)}-day {label}"
    if key == "rsi":
        return f"{label}({_indicator_period(ref, spec.default_period)})"
    if key == "macd":
        params = ref.get("parameters") if isinstance(ref.get("parameters"), dict) else {}
        fast = int(params.get("fast") or spec.default_parameters.get("fast") or 12)
        slow = int(params.get("slow") or spec.default_parameters.get("slow") or 26)
        signal = int(params.get("signal") or spec.default_parameters.get("signal") or 9)
        output = str(ref.get("output") or "macd").lower()
        if output == "signal":
            return f"{label} signal line ({fast}, {slow}, {signal})"
        if output == "histogram":
            return f"{label} histogram ({fast}, {slow}, {signal})"
        return f"{label} line ({fast}, {slow}, {signal})"
    period = _indicator_period(ref, spec.default_period)
    return f"{label}({period})"


def _indicator_period(ref: SeriesRef, default_period: int) -> int:
    try:
        return int(float(ref.get("period", default_period)))
    except (TypeError, ValueError):
        return default_period


def _format_number(value: int | float) -> str:
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:g}"
