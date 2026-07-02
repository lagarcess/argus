"""Typed contract helpers for recovery simplification options."""

from __future__ import annotations

import re
import unicodedata
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


def simplification_option_kind_from_selection_text(
    text: Any,
) -> SimplificationOptionKind | None:
    normalized = _normalized_selection_text(text)
    if not normalized:
        return None
    tokens = set(normalized.split())
    matches: set[SimplificationOptionKind] = set()
    if "rsi" in tokens:
        matches.add("rsi_threshold")
    if (
        "crossover" in tokens
        or "cruce" in tokens
        and _has_any_token(tokens, {"media", "medias", "movil", "moviles"})
        or _has_phrase(normalized, "moving average")
        or _has_phrase(normalized, "moving averages")
    ):
        matches.add("moving_average_crossover")
    if (
        _has_phrase(normalized, "buy and hold")
        or _has_phrase(normalized, "buy hold")
        or _has_phrase(normalized, "comprar y mantener")
        or _has_phrase(normalized, "compra y mantener")
        or _has_phrase(normalized, "compra y manten")
    ):
        matches.add("buy_and_hold")
    if len(matches) == 1:
        return next(iter(matches))
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


def _normalized_selection_text(text: Any) -> str:
    if not isinstance(text, str):
        return ""
    normalized = unicodedata.normalize("NFKD", text.casefold())
    without_marks = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9]+", " ", without_marks).strip()


def _has_phrase(text: str, phrase: str) -> bool:
    return f" {phrase} " in f" {text} "


def _has_any_token(tokens: set[str], candidates: set[str]) -> bool:
    return bool(tokens.intersection(candidates))
