from __future__ import annotations

from copy import deepcopy
from typing import Any

from .models import Condition, RuleSpec


def canonicalize_rule_spec(rule_spec: RuleSpec) -> RuleSpec:
    normalized = deepcopy(rule_spec)
    for group_name in ("entry", "exit"):
        group = normalized.get(group_name)
        if not isinstance(group, dict):
            continue
        conditions = group.get("conditions")
        if not isinstance(conditions, list):
            continue
        group["conditions"] = [
            _canonicalize_condition(condition)
            if isinstance(condition, dict)
            else condition
            for condition in conditions
        ]
    return normalized


def _canonicalize_condition(condition: Condition) -> Condition:
    operator = str(condition.get("operator") or "").lower()
    if operator not in {"cross_above", "cross_below"}:
        return condition
    left = condition.get("left")
    right = condition.get("right")
    if not (_is_same_indicator_family(left, right) and _period(left) > _period(right)):
        return condition
    swapped = dict(condition)
    swapped["left"] = right
    swapped["right"] = left
    swapped["operator"] = (
        "cross_below" if operator == "cross_above" else "cross_above"
    )
    return swapped


def _is_same_indicator_family(left: Any, right: Any) -> bool:
    if not isinstance(left, dict) or not isinstance(right, dict):
        return False
    if str(left.get("kind") or "").lower() != "indicator":
        return False
    if str(right.get("kind") or "").lower() != "indicator":
        return False
    return str(left.get("key") or "").lower() == str(right.get("key") or "").lower()


def _period(ref: Any) -> int:
    if not isinstance(ref, dict):
        return 0
    try:
        return int(float(ref.get("period") or 0))
    except (TypeError, ValueError):
        return 0
