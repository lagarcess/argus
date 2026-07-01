"""Typed contract helpers for recovery simplification options."""

from __future__ import annotations

from typing import Any, Literal

from argus.agent_runtime.strategy_contract import canonical_strategy_type

SimplificationOptionKind = Literal[
    "rsi_threshold",
    "buy_and_hold",
    "moving_average_crossover",
]

_LOCALIZED_OPTION_LABELS: dict[SimplificationOptionKind, dict[str, str]] = {
    "rsi_threshold": {
        "en": "Use a supported RSI threshold rule",
        "es-419": "Usar una regla RSI compatible",
    },
    "buy_and_hold": {
        "en": "Compare with buy and hold",
        "es-419": "Comparar con comprar y mantener",
    },
    "moving_average_crossover": {
        "en": "Use a supported moving-average crossover",
        "es-419": "Usar un cruce de medias móviles compatible",
    },
}


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
    if strategy_type == "buy_and_hold":
        return "buy_and_hold"
    if strategy_type == "moving_average_crossover":
        return "moving_average_crossover"
    return None


def localized_simplification_option_label(
    *,
    label: Any,
    replacement_values: Any,
    locale: str,
) -> str | None:
    kind = simplification_option_kind(replacement_values)
    if kind is not None:
        return _LOCALIZED_OPTION_LABELS[kind].get(locale) or _LOCALIZED_OPTION_LABELS[
            kind
        ]["en"]
    if isinstance(label, str) and label.strip():
        return label.strip()
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
