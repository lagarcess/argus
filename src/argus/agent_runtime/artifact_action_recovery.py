from __future__ import annotations

from pydantic import ValidationError

from argus.agent_runtime.recovery_messages import Language, resolve_recovery_language
from argus.agent_runtime.state.models import (
    ArtifactActionRecoveryFacts,
    ResponseIntent,
)


def artifact_action_recovery_message(intent: ResponseIntent) -> str | None:
    if intent.kind != "artifact_action_recovery":
        return None
    facts = _artifact_action_recovery_facts(intent)
    language = _intent_language(intent)
    if facts is None:
        if language == "es-419":
            return (
                "Esa acción ya no está conectada al estado actual de la "
                "conversación. Usa la acción visible más reciente o dime qué "
                "quieres hacer ahora."
            )
        return (
            "That action is no longer attached to the current conversation state. "
            "Use the latest visible action or tell me what you want to do next."
        )
    if facts.status == "stale":
        if language == "es-419":
            return (
                "Ese reintento pertenece a una ejecución fallida anterior. Usa "
                "la acción de reintento más reciente o confirma la configuración "
                "que quieres ejecutar."
            )
        return (
            "That retry belongs to an older failed run. Use the latest retry action "
            "or confirm the setup you want to run."
        )
    if facts.status == "missing_artifact_id":
        if language == "es-419":
            return (
                "A ese reintento le falta la referencia de la ejecución fallida. "
                "Usa la acción de reintento más reciente o confirma la "
                "configuración que quieres ejecutar."
            )
        return (
            "That retry is missing its failed-run reference. Use the latest retry "
            "action or confirm the strategy you want me to run."
        )
    if facts.status == "missing_payload":
        if language == "es-419":
            return (
                "No tengo una carga de ejecución fallida para reintentar. Usa de "
                "nuevo la acción visible de ejecutar backtest, o confirma la "
                "estrategia que quieres ejecutar."
            )
        return (
            "I do not have a failed run payload to retry. Use the visible Run "
            "backtest action again, or confirm the strategy you want me to run."
        )
    if facts.status == "non_retryable":
        message = facts.user_safe_message
        if isinstance(message, str) and message.strip():
            if language == "es-419":
                return (
                    "Todavía tengo la configuración fallida, pero volver a "
                    "ejecutar la misma carga encontrará el mismo bloqueo: "
                    f"{message.strip()} Ajusta la regla, el activo o el rango "
                    "de fechas y mantendré la idea intacta."
                )
            return (
                "I still have the failed setup, but rerunning the same payload will "
                f"hit the same blocker: {message.strip()} Adjust the rule, asset, "
                "or date range and I will keep the idea intact."
            )
        if language == "es-419":
            return (
                "Todavía tengo la configuración fallida, pero volver a ejecutar "
                "la misma carga encontrará el mismo bloqueo. Ajusta la regla, el "
                "activo o el rango de fechas y mantendré la idea intacta."
            )
        return (
            "I still have the failed setup, but rerunning the same payload will hit "
            "the same blocker. Adjust the rule, asset, or date range and I will "
            "keep the idea intact."
        )
    if facts.status == "rebuilt_confirmation":
        if language == "es-419":
            return (
                "Todavía tengo esa configuración fallida. Reconstruí el borrador "
                "para que puedas revisar la tarjeta y reintentar cuando estés listo."
            )
        return (
            "I still have that failed setup. I rebuilt the draft so you can review "
            "the card and retry when you are ready."
        )
    if language == "es-419":
        return (
            "Ese reintento ya no está conectado a una ejecución fallida activa. "
            "Usa la acción de reintento más reciente o confirma la configuración "
            "que quieres ejecutar."
        )
    return (
        "That retry is no longer attached to an active failed run. Use the latest "
        "retry action or confirm the setup you want to run."
    )


def _artifact_action_recovery_facts(
    intent: ResponseIntent,
) -> ArtifactActionRecoveryFacts | None:
    try:
        return ArtifactActionRecoveryFacts.model_validate(intent.facts)
    except ValidationError:
        return None


def _intent_language(intent: ResponseIntent) -> Language:
    raw_language = intent.facts.get("language")
    return resolve_recovery_language(raw_language if isinstance(raw_language, str) else None)
