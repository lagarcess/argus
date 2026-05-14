from __future__ import annotations

from typing import Any

SeriesRef = dict[str, Any]
Condition = dict[str, Any]
ConditionGroup = dict[str, Any]
RuleSpec = dict[str, Any]

SUPPORTED_OPERATORS = {
    "lt",
    "lte",
    "gt",
    "gte",
    "cross_above",
    "cross_below",
}
SUPPORTED_COMBINATORS = {"all", "any"}
