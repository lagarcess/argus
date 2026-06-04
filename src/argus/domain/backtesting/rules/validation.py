from __future__ import annotations

from typing import Any

import pandas as pd

from argus.domain.indicator_execution import indicator_warmup_from_ref
from argus.domain.indicators import IndicatorExecutionSpec, executable_indicator_spec

from .models import SUPPORTED_COMBINATORS, SUPPORTED_OPERATORS, RuleSpec, SeriesRef


def validate_rule_spec(rule_spec: RuleSpec | None, data: pd.DataFrame | None = None) -> None:
    if not isinstance(rule_spec, dict):
        raise ValueError("missing_rule_group")

    max_warmup = required_warmup_bars(rule_spec)
    _validate_rule_shape(rule_spec, data)

    if data is not None and len(data) <= max_warmup:
        raise ValueError("indicator_data_insufficient")


def required_warmup_bars(rule_spec: RuleSpec | None) -> int:
    if not isinstance(rule_spec, dict):
        raise ValueError("missing_rule_group")

    max_warmup = 0
    for group_name in ("entry", "exit"):
        group = rule_spec.get(group_name)
        if not isinstance(group, dict) or not group.get("conditions"):
            raise ValueError("missing_rule_group")
        for condition in group["conditions"]:
            if not isinstance(condition, dict):
                raise ValueError("missing_rule_group")
            max_warmup = max(
                max_warmup,
                _series_ref_warmup(condition.get("left")),
                _series_ref_warmup(condition.get("right")),
            )
    return max_warmup


def _validate_rule_shape(rule_spec: RuleSpec, data: pd.DataFrame | None) -> None:
    for group_name in ("entry", "exit"):
        group = rule_spec.get(group_name)
        if not isinstance(group, dict) or not group.get("conditions"):
            raise ValueError("missing_rule_group")
        combinator = str(group.get("combinator") or "all").lower()
        if combinator not in SUPPORTED_COMBINATORS:
            raise ValueError("unsupported_rule_operator")
        for condition in group["conditions"]:
            if not isinstance(condition, dict):
                raise ValueError("missing_rule_group")
            operator = str(condition.get("operator") or "").lower()
            if operator not in SUPPORTED_OPERATORS:
                raise ValueError("unsupported_rule_operator")
            _validate_series_ref(condition.get("left"), data)
            _validate_series_ref(condition.get("right"), data)


def indicator_warmup_bars(ref: SeriesRef) -> int:
    spec = executable_indicator_spec(str(ref.get("key") or ""))
    if spec is None:
        raise ValueError("unsupported_indicator")
    return indicator_warmup_from_ref(spec, ref)


def _validate_series_ref(value: Any, data: pd.DataFrame | None) -> int:
    if isinstance(value, int | float):
        return 0
    if not isinstance(value, dict) or "kind" not in value:
        raise ValueError("missing_rule_group")

    kind = str(value.get("kind") or "").lower()
    if kind in {"price", "volume"}:
        field = str(value.get("field") or ("volume" if kind == "volume" else "close"))
        if data is not None and field not in data.columns:
            raise ValueError("market_data_unavailable")
        return 0

    if kind != "indicator":
        raise ValueError("unsupported_indicator")

    spec = executable_indicator_spec(str(value.get("key") or ""))
    if spec is None:
        raise ValueError("unsupported_indicator")
    warmup = indicator_warmup_from_ref(spec, value)
    if data is not None:
        source_column = str(value.get("field") or spec.required_columns[0])
        missing = [
            column
            for column in (source_column, *spec.required_columns[1:])
            if column not in data.columns
        ]
        if missing:
            raise ValueError("market_data_unavailable")
    return warmup


def _series_ref_warmup(value: Any) -> int:
    if isinstance(value, int | float):
        return 0
    if not isinstance(value, dict) or "kind" not in value:
        raise ValueError("missing_rule_group")
    kind = str(value.get("kind") or "").lower()
    if kind in {"price", "volume"}:
        return 0
    if kind != "indicator":
        raise ValueError("unsupported_indicator")
    spec = executable_indicator_spec(str(value.get("key") or ""))
    if spec is None:
        raise ValueError("unsupported_indicator")
    return indicator_warmup_from_ref(spec, value)


def _period_from_ref(ref: SeriesRef, spec: IndicatorExecutionSpec) -> int:
    raw_period = ref.get("period", spec.default_period)
    try:
        period = int(float(raw_period))
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid_indicator_parameter") from exc
    return period


def _validate_period(spec: IndicatorExecutionSpec, period: int) -> None:
    period_spec = next(
        (item for item in spec.parameter_schema if item.key == "indicator_period"),
        None,
    )
    if period_spec is None:
        return
    if period_spec.min_value is not None and period < period_spec.min_value:
        raise ValueError("invalid_indicator_parameter")
    if period_spec.max_value is not None and period > period_spec.max_value:
        raise ValueError("invalid_indicator_parameter")
