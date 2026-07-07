from __future__ import annotations

from typing import Any

from argus.agent_runtime.recovery_messages import recovery_message
from argus.agent_runtime.simplification_option_contract import simplification_option_kind
from argus.agent_runtime.state.models import StrategySummary

OFFLINE_CLARIFICATION_FALLBACK = recovery_message(
    "clarification_generation_unavailable",
    language="en",
)


def offline_clarification_fallback(
    *,
    language: str | None = None,
    response_intent: dict[str, Any] | None = None,
    strategy: StrategySummary | dict[str, Any] | None = None,
) -> str:
    intent_question = intent_clarification_fallback(
        language=language,
        response_intent=response_intent,
        strategy=strategy,
    )
    if intent_question:
        return intent_question
    return recovery_message(
        "clarification_generation_unavailable",
        language=language,
    )


def intent_clarification_fallback(
    *,
    language: str | None,
    response_intent: dict[str, Any] | None,
    strategy: StrategySummary | dict[str, Any] | None,
) -> str | None:
    if not isinstance(response_intent, dict):
        return None
    if response_intent.get("kind") == "unsupported_recovery":
        return _unsupported_recovery_fallback(
            language=language,
            response_intent=response_intent,
            strategy=strategy,
        )
    if response_intent.get("kind") != "clarification":
        return None
    needs = response_intent.get("semantic_needs")
    if not isinstance(needs, list) or not needs:
        return None
    symbol = _primary_symbol(strategy)
    _ = language
    if "period" in needs:
        return f"What date window should I use{_en_asset_suffix(symbol)}?"
    if "asset_target" in needs:
        return "Which asset should I test?"
    if "assumption" in needs:
        return f"What assumption should I adjust{_en_asset_suffix(symbol)}?"
    if "sizing_amount" in needs and "schedule" in needs:
        return "How much should each purchase be, and how often should it happen?"
    if "sizing_amount" in needs:
        return "How much should I use?"
    if "schedule" in needs:
        return "How often should the purchases happen?"
    if "rule_definition" in needs:
        return "What entry or exit rule should I test?"
    if "refinement" in needs:
        return "What would you like to change?"
    return None


def _unsupported_recovery_fallback(
    *,
    language: str | None,
    response_intent: dict[str, Any],
    strategy: StrategySummary | dict[str, Any] | None,
) -> str | None:
    _ = language
    options = _option_labels(response_intent)
    if not options:
        return None
    raw_value = _unsupported_raw_value(response_intent)
    symbol = _primary_symbol(strategy)
    joined_options = _join_options(options)
    subject = raw_value or "That rule"
    symbol_suffix = f" for {symbol}" if symbol else ""
    return (
        f"{subject} does not define when to buy or sell{symbol_suffix} on its own. "
        f"Which supported direction should I use: {joined_options}?"
    )


def _option_labels(response_intent: dict[str, Any]) -> list[str]:
    raw_options = response_intent.get("options")
    if not isinstance(raw_options, list):
        return []
    labels: list[str] = []
    for option in raw_options:
        if not isinstance(option, dict):
            continue
        label = _fallback_option_label(option)
        if label is None:
            continue
        if label not in labels:
            labels.append(label)
    return labels[:3]


def _unsupported_raw_value(response_intent: dict[str, Any]) -> str | None:
    facts = response_intent.get("facts")
    if not isinstance(facts, dict):
        return None
    constraints = facts.get("unsupported_constraints")
    if not isinstance(constraints, list):
        return None
    for constraint in constraints:
        if not isinstance(constraint, dict):
            continue
        raw_value = constraint.get("raw_value")
        if not isinstance(raw_value, str):
            continue
        value = raw_value.strip()
        if value and not _looks_like_internal_code(value):
            return value
    return None


def _looks_like_internal_code(value: str) -> bool:
    # raw_value should carry the user's own words; a whitespace-free
    # lowercase snake_case token is an internal reason code and must never
    # render in prose. Uppercase underscore tokens (BTC_USDT, BRK_B) are
    # user-typed symbols and stay quotable.
    return (
        "_" in value
        and value == value.lower()
        and not any(character.isspace() for character in value)
    )


def _fallback_option_label(option: dict[str, Any]) -> str | None:
    kind = simplification_option_kind(option.get("replacement_values"))
    if kind == "rsi_threshold":
        return "Use a supported RSI threshold rule"
    if kind == "buy_and_hold":
        return "Compare with buy and hold"
    if kind == "moving_average_crossover":
        return "Use a supported moving-average crossover"
    label = option.get("label")
    if isinstance(label, str) and label.strip():
        return label.strip()
    return None


def _join_options(options: list[str]) -> str:
    if len(options) <= 1:
        return options[0] if options else ""
    if len(options) == 2:
        return " or ".join(options)
    return f"{', '.join(options[:-1])}, or {options[-1]}"


def _primary_symbol(strategy: StrategySummary | dict[str, Any] | None) -> str | None:
    assets: Any = None
    if isinstance(strategy, StrategySummary):
        assets = strategy.asset_universe
    elif isinstance(strategy, dict):
        assets = strategy.get("asset_universe")
    if not isinstance(assets, list):
        return None
    for item in assets:
        symbol = str(item or "").strip().upper()
        if symbol:
            return symbol
    return None


def _en_asset_suffix(symbol: str | None) -> str:
    return f" for {symbol}" if symbol else ""
