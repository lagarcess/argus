from __future__ import annotations

from typing import Literal

Language = Literal["en", "es-419"]
RecoveryMessageCode = Literal[
    "interpreter_unavailable",
    "assumption_edit_unapplied",
    "setup_change_unapplied",
    "confirmation_change_unapplied",
    "latest_result_followup_unavailable",
    "private_alpha_save_unavailable",
    "confirmation_action_guidance",
    "confirmation_action_missing_context",
    "confirmation_action_missing_identity",
    "confirmation_action_stale_card",
    "confirmation_action_stale_payload",
    "confirmation_state_lost",
    "confirmation_cancelled",
    "clarification_generation_unavailable",
    "result_refine_missing",
    "context_macro_recovery",
    "context_corporate_events_recovery",
    "context_market_movers_recovery",
    "context_market_movers_seed_recovery",
    "capability_answer_unavailable",
    "runtime_failure",
]


RECOVERY_MESSAGES: dict[RecoveryMessageCode, dict[Language, str]] = {
    "interpreter_unavailable": {
        "en": (
            "I saved your message, but I could not turn it into a reliable "
            "test setup. Please retry in a moment."
        ),
        "es-419": (
            "Guardé tu mensaje, pero no pude convertirlo en una configuración "
            "de prueba confiable. Intenta de nuevo en un momento."
        ),
    },
    "assumption_edit_unapplied": {
        "en": (
            "I saved your reply, but I could not safely apply that assumption "
            "change, so I left the current idea unchanged. Please retry the "
            "change in a moment."
        ),
        "es-419": (
            "Guardé tu respuesta, pero no pude aplicar ese cambio de supuesto "
            "con confianza, así que dejé la idea actual sin cambios. Intenta el "
            "cambio de nuevo en un momento."
        ),
    },
    "setup_change_unapplied": {
        "en": (
            "I still have the {setup_phrase} in this chat, but I could not "
            "safely apply that change. Please retry in a moment."
        ),
        "es-419": (
            "Todavía tengo {setup_phrase} en este chat, pero no pude aplicar "
            "ese cambio con confianza. Intenta de nuevo en un momento."
        ),
    },
    "confirmation_change_unapplied": {
        "en": (
            "I still have the {setup_phrase} confirmation in this chat, but I "
            "could not safely apply that change. {action_guidance}"
        ),
        "es-419": (
            "Todavía tengo la confirmación de {setup_phrase} en este chat, pero "
            "no pude aplicar ese cambio con confianza. {action_guidance}"
        ),
    },
    "latest_result_followup_unavailable": {
        "en": (
            "I still have the latest result in this chat, but I could not "
            "safely answer that follow-up. Please retry in a moment."
        ),
        "es-419": (
            "Todavía tengo el resultado más reciente en este chat, pero no "
            "pude responder ese seguimiento con confianza. Intenta de nuevo en "
            "un momento."
        ),
    },
    "private_alpha_save_unavailable": {
        "en": (
            "I cannot move this into Strategies while that surface is off for "
            "private alpha, but the completed run is still part of this chat "
            "and can be reopened from the conversation or Recents."
        ),
        "es-419": (
            "No puedo mover esto a Estrategias mientras esa superficie está "
            "desactivada para la alfa privada, pero la ejecución completa "
            "sigue en este chat y puedes volver a abrirla desde la conversación "
            "o Recientes."
        ),
    },
    "confirmation_action_guidance": {
        "en": (
            "The visible confirmation is still ready. Use the card to start "
            "the simulation, or use the card controls to change it."
        ),
        "es-419": (
            "La confirmación visible sigue lista. Usa la tarjeta para iniciar "
            "la simulación, o usa sus controles para cambiarla."
        ),
    },
    "confirmation_action_missing_context": {
        "en": (
            "I do not have an active confirmation to change. Describe the "
            "investing idea again and I will prepare a fresh draft."
        ),
        "es-419": (
            "No tengo una confirmación activa para cambiar. Describe la idea "
            "de inversión otra vez y prepararé un borrador nuevo."
        ),
    },
    "confirmation_action_missing_identity": {
        "en": (
            "That confirmation action is missing its card identity. Use the "
            "latest card action before continuing."
        ),
        "es-419": (
            "A esa acción de confirmación le falta la identidad de la tarjeta. "
            "Usa la acción de la tarjeta más reciente antes de continuar."
        ),
    },
    "confirmation_action_stale_card": {
        "en": (
            "That confirmation was updated. Use the latest visible card and I "
            "will keep the current confirmation intact."
        ),
        "es-419": (
            "Esa confirmación ya se actualizó. Usa la tarjeta visible más "
            "reciente y mantendré intacta la confirmación actual."
        ),
    },
    "confirmation_state_lost": {
        "en": (
            "I lost the active confirmation state, but your conversation is "
            "saved. I can restate the strategy so you can confirm it again."
        ),
        "es-419": (
            "Perdí el estado activo de confirmación, pero tu conversación está "
            "guardada. Puedo volver a plantear la estrategia para que la "
            "confirmes otra vez."
        ),
    },
    "confirmation_action_stale_payload": {
        "en": (
            "That confirmation payload is stale. Use the latest visible card "
            "and I will keep the current confirmation intact."
        ),
        "es-419": (
            "Ese contenido de confirmación ya quedó desactualizado. Usa la "
            "tarjeta visible más reciente y mantendré intacta la confirmación "
            "actual."
        ),
    },
    "confirmation_cancelled": {
        "en": "No problem. I will leave that draft unrun.",
        "es-419": "Sin problema. Dejaré ese borrador sin ejecutar.",
    },
    "clarification_generation_unavailable": {
        "en": (
            "I could not phrase the follow-up clearly just now. Your draft is "
            "still here; tell me the detail you want to change, or try again "
            "in a moment."
        ),
        "es-419": (
            "No pude formular bien el seguimiento en este momento. Tu borrador "
            "sigue aquí; dime el detalle que quieres cambiar, o intenta de "
            "nuevo en un momento."
        ),
    },
    "result_refine_missing": {
        "en": (
            "I do not have a completed result to refine. Run a strategy first, "
            "then use Refine idea from the result card."
        ),
        "es-419": (
            "No tengo un resultado completo para ajustar. Ejecuta una "
            "estrategia primero y luego usa Ajustar idea desde la tarjeta de "
            "resultado."
        ),
    },
    "context_macro_recovery": {
        "en": (
            "Macro conditions can be useful context for a historical test. "
            "Choose a symbol, strategy, or comparison window and I can help "
            "frame a supported experiment."
        ),
        "es-419": (
            "Las condiciones macro pueden ser contexto útil para una prueba "
            "histórica. Elige un símbolo, una estrategia o una ventana de "
            "comparación y puedo ayudarte a plantear un experimento compatible."
        ),
    },
    "context_corporate_events_recovery": {
        "en": (
            "Corporate events are most useful when tied to a symbol and period. "
            "Choose an equity ticker and I can use events like splits or "
            "dividends as context around a supported historical test."
        ),
        "es-419": (
            "Los eventos corporativos son más útiles cuando están ligados a un "
            "símbolo y un periodo. Elige un ticker de acciones y puedo usar "
            "eventos como splits o dividendos como contexto de una prueba "
            "histórica compatible."
        ),
    },
    "context_market_movers_recovery": {
        "en": (
            "A market move can be a useful starting point for an experiment. "
            "Choose a symbol or idea and I can turn it into a supported "
            "historical test instead of a live feed."
        ),
        "es-419": (
            "Un movimiento del mercado puede ser un buen punto de partida para "
            "un experimento. Elige un símbolo o una idea y puedo convertirlo en "
            "una prueba histórica compatible, no en un feed en vivo."
        ),
    },
    "context_market_movers_seed_recovery": {
        "en": (
            "A short-lived movers snapshot can help pick experiment seeds: "
            "{seeds}. Treat those as symbols to validate, not recommendations "
            "or a live ranking. Choose one and I can shape a supported "
            "historical test."
        ),
        "es-419": (
            "Una foto momentánea de movimientos puede ayudar a elegir semillas "
            "para un experimento: {seeds}. Trátalas como símbolos por validar, "
            "no como recomendaciones ni como un ranking en vivo. Elige uno y "
            "puedo plantear una prueba histórica compatible."
        ),
    },
    "capability_answer_unavailable": {
        "en": (
            "I could not phrase that capability answer clearly just now. Tell me "
            "the asset, period, or supported rule you want to test, or try again "
            "in a moment."
        ),
        "es-419": (
            "No pude formular esa respuesta de capacidades con claridad en este "
            "momento. Dime el activo, periodo o regla compatible que quieres "
            "probar, o intenta de nuevo en un momento."
        ),
    },
    "runtime_failure": {
        "en": "Something went wrong. Your conversation is saved. Please try again.",
        "es-419": "Algo salió mal. Tu conversación está guardada. Intenta de nuevo.",
    },
}


def resolve_recovery_language(language: str | None) -> Language:
    return "es-419" if (language or "en").lower().startswith("es") else "en"


def recovery_message(
    code: RecoveryMessageCode,
    *,
    language: str | None = None,
    **params: str,
) -> str:
    resolved = resolve_recovery_language(language)
    return RECOVERY_MESSAGES[code][resolved].format(**params)


def recovery_state(
    code: RecoveryMessageCode,
    *,
    language: str | None = None,
    retryable: bool,
) -> dict[str, str | bool]:
    return {
        "code": code,
        "retryable": retryable,
        "language": resolve_recovery_language(language),
    }


def recovery_state_stage_patch(
    code: RecoveryMessageCode,
    *,
    language: str | None = None,
    retryable: bool,
) -> dict[str, dict[str, str | bool]]:
    return {
        "recovery": recovery_state(
            code,
            language=language,
            retryable=retryable,
        )
    }


def retry_last_turn_stage_patch(message: str) -> dict[str, dict[str, str]] | None:
    cleaned = message.strip()
    if not cleaned:
        return None
    return {"retry_last_turn": {"message": cleaned}}
