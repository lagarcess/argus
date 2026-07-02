from __future__ import annotations

from typing import Any

from argus.agent_runtime.presentation_i18n import runtime_locale
from argus.agent_runtime.recovery_messages import recovery_message
from argus.agent_runtime.simplification_option_contract import (
    localized_simplification_option_label,
)
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
    locale = runtime_locale(language)
    if "period" in needs:
        if locale == "es-419":
            return f"¿Qué periodo quieres usar{_es_asset_suffix(symbol)}?"
        return f"What date window should I use{_en_asset_suffix(symbol)}?"
    if "asset_target" in needs:
        if locale == "es-419":
            return "¿Qué activo quieres probar?"
        return "Which asset should I test?"
    if "assumption" in needs:
        if locale == "es-419":
            return f"¿Qué supuesto quieres ajustar{_es_asset_suffix(symbol)}?"
        return f"What assumption should I adjust{_en_asset_suffix(symbol)}?"
    if "sizing_amount" in needs and "schedule" in needs:
        if locale == "es-419":
            return "¿Cuánto quieres invertir en cada compra y con qué frecuencia?"
        return "How much should each purchase be, and how often should it happen?"
    if "sizing_amount" in needs:
        if locale == "es-419":
            return "¿Cuánto quieres invertir?"
        return "How much should I use?"
    if "schedule" in needs:
        if locale == "es-419":
            return "¿Con qué frecuencia quieres hacer las compras?"
        return "How often should the purchases happen?"
    if "rule_definition" in needs:
        if locale == "es-419":
            return "¿Qué regla de entrada o salida quieres probar?"
        return "What entry or exit rule should I test?"
    if "refinement" in needs:
        if locale == "es-419":
            return "¿Qué quieres ajustar de esta idea?"
        return "What would you like to change?"
    return None


def _unsupported_recovery_fallback(
    *,
    language: str | None,
    response_intent: dict[str, Any],
    strategy: StrategySummary | dict[str, Any] | None,
) -> str | None:
    locale = runtime_locale(language)
    options = _option_labels(response_intent, locale=locale)
    if not options:
        return None
    raw_value = _unsupported_raw_value(response_intent)
    symbol = _primary_symbol(strategy)
    joined_options = _join_options(options, locale=locale)
    if locale == "es-419":
        subject = raw_value or "Esa regla"
        symbol_suffix = f" para {symbol}" if symbol else ""
        return (
            f"{subject} no define por sí solo cuándo comprar o vender"
            f"{symbol_suffix}. ¿Qué camino quieres usar: {joined_options}?"
        )
    subject = raw_value or "That rule"
    symbol_suffix = f" for {symbol}" if symbol else ""
    return (
        f"{subject} does not define when to buy or sell{symbol_suffix} on its own. "
        f"Which supported direction should I use: {joined_options}?"
    )


def _option_labels(response_intent: dict[str, Any], *, locale: str) -> list[str]:
    raw_options = response_intent.get("options")
    if not isinstance(raw_options, list):
        return []
    labels: list[str] = []
    for option in raw_options:
        if not isinstance(option, dict):
            continue
        label = localized_simplification_option_label(
            label=option.get("label"),
            replacement_values=option.get("replacement_values"),
            locale=locale,
        )
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
        if isinstance(raw_value, str) and raw_value.strip():
            return raw_value.strip()
    return None


def _join_options(options: list[str], *, locale: str) -> str:
    if len(options) <= 1:
        return options[0] if options else ""
    if len(options) == 2:
        conjunction = " o " if locale == "es-419" else " or "
        return conjunction.join(options)
    conjunction = "o" if locale == "es-419" else "or"
    return f"{', '.join(options[:-1])}, {conjunction} {options[-1]}"


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


def _es_asset_suffix(symbol: str | None) -> str:
    return f" para {symbol}" if symbol else ""
