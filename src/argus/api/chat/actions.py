from __future__ import annotations

from typing import Any

from argus.api.chat.recovery import (
    _metadata_invalidates_confirmation,
    _recent_messages_for_conversation,
    _run_by_id_for_user,
    latest_completed_run_for_conversation,
)
from argus.api.schemas import BacktestRun, ChatStreamRequest, Message, User

CONFIRMATION_ACTION_TYPES = {
    "run_backtest",
    "change_dates",
    "change_asset",
    "adjust_assumptions",
    "cancel_confirmation",
}

RESULT_ACTION_TYPES = {
    "show_breakdown",
    "refine_strategy",
    "save_strategy",
}

STALE_CONFIRMATION_ACTION_MESSAGE = (
    "That confirmation was updated. Use the latest card action before continuing."
)

_ACTION_LABELS = {
    "en": {
        "chat.confirmation.actions.run_backtest": "Run backtest",
        "chat.confirmation.actions.change_dates": "Change dates",
        "chat.confirmation.actions.change_asset": "Change asset",
        "chat.confirmation.actions.adjust_assumptions": "Adjust assumptions",
        "chat.confirmation.actions.cancel": "Cancel",
        "chat.result_card.explain_result": "Explain result",
        "chat.result_card.refine_idea": "Refine idea",
        "chat.result_card.save": "Save",
        "common.retry": "Retry",
    },
    "es-419": {
        "chat.confirmation.actions.run_backtest": "Ejecutar backtest",
        "chat.confirmation.actions.change_dates": "Cambiar fechas",
        "chat.confirmation.actions.change_asset": "Cambiar activo",
        "chat.confirmation.actions.adjust_assumptions": "Ajustar supuestos",
        "chat.confirmation.actions.cancel": "Cancelar",
        "chat.result_card.explain_result": "Explicar resultado",
        "chat.result_card.refine_idea": "Ajustar idea",
        "chat.result_card.save": "Guardar",
        "common.retry": "Reintentar",
    },
}

_ACTION_TYPE_LABEL_KEYS = {
    "run_backtest": "chat.confirmation.actions.run_backtest",
    "change_dates": "chat.confirmation.actions.change_dates",
    "change_asset": "chat.confirmation.actions.change_asset",
    "adjust_assumptions": "chat.confirmation.actions.adjust_assumptions",
    "cancel_confirmation": "chat.confirmation.actions.cancel",
    "show_breakdown": "chat.result_card.explain_result",
    "refine_strategy": "chat.result_card.refine_idea",
    "save_strategy": "chat.result_card.save",
    "retry_failed_action": "common.retry",
}


def chat_request_message(payload: ChatStreamRequest, *, language: str = "en") -> str:
    if payload.action is None:
        return payload.message or ""
    action_type = payload.action.type
    action_messages = {
        "run_backtest": "run backtest",
        "change_dates": "change dates",
        "change_asset": "change asset",
        "adjust_assumptions": "adjust assumptions",
        "cancel_confirmation": "cancel backtest",
        "show_breakdown": "show a detailed breakdown of this result",
        "refine_strategy": "refine this strategy",
        "save_strategy": "save this strategy",
        "retry_failed_action": "retry failed action",
    }
    if _resolve_language(language) != "en":
        label_key = payload.action.label_key or _ACTION_TYPE_LABEL_KEYS.get(action_type)
        if label_key:
            localized = _localized_action_label(label_key, language=language)
            if localized:
                return localized
        if payload.action.label:
            return payload.action.label
    return action_messages[action_type]


def chat_display_message(payload: ChatStreamRequest, *, language: str = "en") -> str:
    if payload.action is None:
        return payload.message or ""
    label_key = payload.action.label_key or _ACTION_TYPE_LABEL_KEYS.get(
        payload.action.type
    )
    if label_key:
        localized = _localized_action_label(label_key, language=language)
        if localized:
            return localized
    return payload.action.label or chat_request_message(payload, language=language)


def _localized_action_label(label_key: str, *, language: str) -> str | None:
    labels = _ACTION_LABELS[_resolve_language(language)]
    return labels.get(label_key)


def _resolve_language(language: str | None) -> str:
    return "es-419" if (language or "en").lower().startswith("es") else "en"


def chat_action_run_id(payload: ChatStreamRequest) -> str | None:
    if payload.action is None:
        return None
    raw_run_id = payload.action.payload.get("run_id")
    if raw_run_id is None:
        raw_run_id = payload.action.payload.get("runId")
    if raw_run_id is None:
        return None
    run_id = str(raw_run_id).strip()
    return run_id or None


def chat_action_conversation_id(payload: ChatStreamRequest) -> str | None:
    if payload.action is None:
        return None
    raw_conversation_id = payload.action.payload.get("conversation_id")
    if raw_conversation_id is None:
        raw_conversation_id = payload.action.payload.get("conversationId")
    if raw_conversation_id is None:
        return None
    conversation_id = str(raw_conversation_id).strip()
    return conversation_id or None


def is_confirmation_action(payload: ChatStreamRequest) -> bool:
    return payload.action is not None and payload.action.type in CONFIRMATION_ACTION_TYPES


def is_cancel_confirmation_action(payload: ChatStreamRequest) -> bool:
    return payload.action is not None and payload.action.type == "cancel_confirmation"


def is_result_action(payload: ChatStreamRequest) -> bool:
    return payload.action is not None and payload.action.type in RESULT_ACTION_TYPES


def pending_confirmation_exists(*, user_id: str, conversation_id: str) -> bool:
    messages = _recent_messages_for_conversation(
        user_id=user_id,
        conversation_id=conversation_id,
        limit=20,
    )

    for message in reversed(messages):
        if message.role != "assistant" or not isinstance(message.metadata, dict):
            continue
        metadata = message.metadata
        if _metadata_invalidates_confirmation(metadata):
            return False
        if metadata.get("confirmation_card"):
            return True
    return False


def stale_confirmation_action_message(
    *,
    payload: ChatStreamRequest,
    user_id: str,
    conversation_id: str,
    recent_messages: list[Message] | None = None,
) -> str | None:
    if payload.action is None or payload.action.presentation != "confirmation":
        return None
    if payload.action.type not in CONFIRMATION_ACTION_TYPES:
        return None
    action_confirmation_id = _confirmation_id_from_action_payload(payload.action.payload)
    if action_confirmation_id is None:
        return None
    latest_confirmation_id = latest_active_confirmation_id(
        user_id=user_id,
        conversation_id=conversation_id,
        recent_messages=recent_messages,
    )
    if latest_confirmation_id is None or latest_confirmation_id == action_confirmation_id:
        return None
    return STALE_CONFIRMATION_ACTION_MESSAGE


def latest_active_confirmation_id(
    *,
    user_id: str,
    conversation_id: str,
    recent_messages: list[Message] | None = None,
) -> str | None:
    messages = (
        recent_messages
        if recent_messages is not None
        else _recent_messages_for_conversation(
            user_id=user_id,
            conversation_id=conversation_id,
            limit=20,
        )
    )
    for message in reversed(messages):
        if message.role != "assistant" or not isinstance(message.metadata, dict):
            continue
        metadata = message.metadata
        if _metadata_invalidates_confirmation(metadata):
            return None
        card = metadata.get("confirmation_card")
        if not isinstance(card, dict):
            continue
        return _confirmation_id_from_card(card)
    return None


def _confirmation_id_from_action_payload(payload: dict[str, Any]) -> str | None:
    raw_value = payload.get("confirmation_id") or payload.get("confirmationId")
    if raw_value is None:
        return None
    value = str(raw_value).strip()
    return value or None


def _confirmation_id_from_card(card: dict[str, Any]) -> str | None:
    raw_value = card.get("confirmation_id") or card.get("confirmationId")
    if raw_value is None:
        return None
    value = str(raw_value).strip()
    return value or None


def run_for_result_action(
    *,
    payload: ChatStreamRequest,
    user: User,
    conversation_id: str,
    require_run_id: bool = False,
) -> BacktestRun | None:
    run_id = chat_action_run_id(payload)
    action_conversation_id = chat_action_conversation_id(payload)
    if action_conversation_id and action_conversation_id != conversation_id:
        return None
    if require_run_id and not run_id:
        return None
    if run_id:
        run = _run_by_id_for_user(user_id=user.id, run_id=run_id)
        if run is None:
            return None
        if run.conversation_id != conversation_id or run.status != "completed":
            return None
        return run
    return latest_completed_run_for_conversation(
        user_id=user.id,
        conversation_id=conversation_id,
    )
