from __future__ import annotations

from typing import Any

from argus.agent_runtime.presentation_i18n import runtime_locale
from argus.agent_runtime.recovery_messages import recovery_message
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
