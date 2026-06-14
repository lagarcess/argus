from __future__ import annotations

from typing import Literal

Language = Literal["en", "es-419"]
RecoveryMessageCode = Literal[
    "interpreter_unavailable",
    "assumption_edit_unapplied",
    "setup_change_unapplied",
    "confirmation_change_unapplied",
    "latest_result_followup_unavailable",
    "confirmation_action_guidance",
    "clarification_generation_unavailable",
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
