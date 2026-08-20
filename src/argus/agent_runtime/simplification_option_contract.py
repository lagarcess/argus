"""Typed contract helpers for recovery simplification options."""

from __future__ import annotations

from typing import Any, Literal

from argus.agent_runtime.strategy_contract import canonical_strategy_type

SimplificationOptionKind = Literal[
    "rsi_threshold",
    "buy_and_hold",
    "buy_and_hold_with_starting_capital",
    "moving_average_crossover",
    "recurring_only",
    "use_as_starting_capital",
]


def simplification_option_kind(
    replacement_values: Any,
) -> SimplificationOptionKind | None:
    if not isinstance(replacement_values, dict):
        return None
    if replacement_values.get("simplify_logic") == "rsi_only":
        return "rsi_threshold"
    if _contains_rule_type(replacement_values, "rsi_threshold"):
        return "rsi_threshold"
    if _contains_rule_type(replacement_values, "moving_average_crossover"):
        return "moving_average_crossover"
    if replacement_values.get("rule_family") == "moving_average_crossover":
        return "moving_average_crossover"
    strategy_type = canonical_strategy_type(replacement_values.get("strategy_type"))
    if (
        strategy_type == "buy_and_hold"
        and replacement_values.get("initial_capital") is not None
    ):
        # The DCA ceiling recovery's strategy-switch option: the money funds
        # the switched plan, which is a different offer than comparing.
        return "buy_and_hold_with_starting_capital"
    if strategy_type == "buy_and_hold":
        return "buy_and_hold"
    if strategy_type == "moving_average_crossover":
        return "moving_average_crossover"
    # The DCA ceiling recovery's money-role options: both must localize, so
    # each carries a typed kind rather than only its compatibility label.
    if replacement_values.get("ignore_initial_capital") is True:
        return "recurring_only"
    if replacement_values.get("initial_capital") is not None:
        return "use_as_starting_capital"
    return None


def simplification_option_matches_selection(
    *,
    option_replacement_values: Any,
    selected_replacement_values: Any,
) -> bool:
    if not isinstance(option_replacement_values, dict) or not isinstance(
        selected_replacement_values,
        dict,
    ):
        return False
    selected_kind = simplification_option_kind(selected_replacement_values)
    option_kind = simplification_option_kind(option_replacement_values)
    if selected_kind is not None or option_kind is not None:
        return selected_kind == option_kind
    if not selected_replacement_values:
        return False
    return all(
        option_replacement_values.get(key) == value
        for key, value in selected_replacement_values.items()
    )


def _contains_rule_type(payload: dict[str, Any], rule_type: str) -> bool:
    for key in ("entry_rule", "exit_rule"):
        rule = payload.get(key)
        if isinstance(rule, dict) and rule.get("type") == rule_type:
            return True
    return False
