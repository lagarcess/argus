from __future__ import annotations

from typing import Any

import pandas as pd

from .models import Condition, ConditionGroup, RuleSpec
from .series import IndicatorResolver, resolve_series
from .validation import validate_rule_spec


def compile_rule_signals(
    rule_spec: RuleSpec,
    *,
    data: pd.DataFrame,
    indicator_resolver: IndicatorResolver | None = None,
) -> tuple[pd.Series, pd.Series]:
    validate_rule_spec(rule_spec, data)
    entries = _compile_group(
        rule_spec["entry"],
        data=data,
        indicator_resolver=indicator_resolver,
    )
    exits = _compile_group(
        rule_spec["exit"],
        data=data,
        indicator_resolver=indicator_resolver,
    )
    return entries.fillna(False).astype(bool), exits.fillna(False).astype(bool)


def _compile_group(
    group: ConditionGroup,
    *,
    data: pd.DataFrame,
    indicator_resolver: IndicatorResolver | None,
) -> pd.Series:
    conditions = [
        _compile_condition(condition, data=data, indicator_resolver=indicator_resolver)
        for condition in group["conditions"]
    ]
    if not conditions:
        raise ValueError("missing_rule_group")

    result = conditions[0]
    combinator = str(group.get("combinator") or "all").lower()
    for condition in conditions[1:]:
        if combinator == "all":
            result = result & condition
        elif combinator == "any":
            result = result | condition
        else:
            raise ValueError("unsupported_rule_operator")
    return result.reindex(data.index).fillna(False).astype(bool)


def _compile_condition(
    condition: Condition,
    *,
    data: pd.DataFrame,
    indicator_resolver: IndicatorResolver | None,
) -> pd.Series:
    left = _operand_series(
        condition["left"],
        data=data,
        indicator_resolver=indicator_resolver,
    )
    right = _operand_series(
        condition["right"],
        data=data,
        indicator_resolver=indicator_resolver,
    )
    operator = str(condition["operator"]).lower()

    if operator == "lt":
        return left < right
    if operator == "lte":
        return left <= right
    if operator == "gt":
        return left > right
    if operator == "gte":
        return left >= right
    if operator == "cross_above":
        return (left > right) & (left.shift(1) <= right.shift(1))
    if operator == "cross_below":
        return (left < right) & (left.shift(1) >= right.shift(1))
    raise ValueError("unsupported_rule_operator")


def _operand_series(
    value: Any,
    *,
    data: pd.DataFrame,
    indicator_resolver: IndicatorResolver | None,
) -> pd.Series:
    if isinstance(value, dict) and "kind" in value:
        return resolve_series(data, value, indicator_resolver=indicator_resolver)
    return pd.Series(float(value), index=data.index, dtype=float)
