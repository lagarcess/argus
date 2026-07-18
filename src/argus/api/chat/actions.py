from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from argus.agent_runtime.recovery_messages import recovery_message
from argus.api.chat.recovery import (
    RuntimeFallbackContext,
    _metadata_invalidates_confirmation,
    _recent_messages_for_conversation,
    _run_by_id_for_user,
    latest_completed_run_for_conversation,
    pending_strategy_metadata_fallback_context_from_message,
)
from argus.api.message_store import (
    claim_response_option_action,
    owned_conversation_message,
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
        "chat.coverage_recovery.actions.change_dates": "Change dates",
        "chat.coverage_recovery.actions.change_asset": "Change asset",
        "chat.coverage_recovery.actions.change_benchmark": "Change benchmark",
        "chat.clarification.timeframe_actions.daily": "Retry with daily bars",
        "chat.clarification.timeframe_actions.hour_1": "Retry with 1-hour bars",
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
        "chat.coverage_recovery.actions.change_dates": "Cambiar fechas",
        "chat.coverage_recovery.actions.change_asset": "Cambiar activo",
        "chat.coverage_recovery.actions.change_benchmark": "Cambiar referencia",
        "chat.clarification.timeframe_actions.daily": "Usar barras diarias",
        "chat.clarification.timeframe_actions.hour_1": "Usar barras de 1 hora",
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


@dataclass(frozen=True)
class ValidatedResponseOptionSource:
    assistant_id: str
    runtime_fallback: RuntimeFallbackContext
    request_message: Message


def chat_request_message(payload: ChatStreamRequest, *, language: str = "en") -> str:
    if payload.action is None:
        return payload.message or ""
    action_type = payload.action.type
    if action_type == "select_response_option":
        if payload.action.label_key:
            localized = _localized_action_label(
                payload.action.label_key,
                language=language,
            )
            if localized:
                return localized
        return payload.action.label or payload.message or ""
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


def is_response_option_action(payload: ChatStreamRequest) -> bool:
    return payload.action is not None and payload.action.type == "select_response_option"


def persisted_chat_action(payload: ChatStreamRequest) -> dict[str, Any] | None:
    if payload.action is None:
        return None
    action = payload.action.model_dump(mode="python")
    if payload.action.type != "select_response_option":
        return action
    action["payload"] = {
        key: payload.action.payload[key]
        for key in ("option_id", "replacement_values")
        if key in payload.action.payload
    }
    return action


def validated_response_option_source(
    *,
    payload: ChatStreamRequest,
    user_id: str,
    conversation_id: str,
    request_message: Message,
) -> ValidatedResponseOptionSource | None:
    if not is_response_option_action(payload) or payload.action is None:
        return None
    source_assistant_id = _clean_action_payload_id(
        payload.action.payload.get("source_assistant_id")
    )
    if source_assistant_id is None:
        return None
    option_id = payload.action.payload.get("option_id")
    replacement_values = payload.action.payload.get("replacement_values")
    if not isinstance(option_id, str) or not isinstance(replacement_values, dict):
        return None
    source_message = owned_conversation_message(
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=source_assistant_id,
    )
    if source_message is None or not isinstance(source_message.metadata, dict):
        return None
    if (
        _response_option_source_context(
            source_message,
            user_id=user_id,
            conversation_id=conversation_id,
            request_message=request_message,
        )
        is None
    ):
        return None
    claim = claim_response_option_action(
        user_id=user_id,
        conversation_id=conversation_id,
        source_assistant_id=source_assistant_id,
        option_id=option_id,
        replacement_values=replacement_values,
        request_message=request_message,
        expected_source_metadata=source_message.metadata,
    )
    if claim is None:
        return None
    source_context = _response_option_source_context(
        claim.source_message,
        user_id=user_id,
        conversation_id=conversation_id,
        request_message=claim.request_message,
    )
    return source_context


def _response_option_source_context(
    source_message: Message,
    *,
    user_id: str,
    conversation_id: str,
    request_message: Message,
) -> ValidatedResponseOptionSource | None:
    fallback = pending_strategy_metadata_fallback_context_from_message(
        user_id=user_id,
        conversation_id=conversation_id,
        source_message=source_message,
    )
    if (
        fallback is None
        or fallback.latest_task_snapshot is None
        or fallback.selected_thread_metadata is None
    ):
        return None
    selected_thread_metadata = {
        **fallback.selected_thread_metadata,
        "fallback_source": "validated_response_option_source",
        "validated_source_assistant_id": source_message.id,
    }
    return ValidatedResponseOptionSource(
        assistant_id=source_message.id,
        runtime_fallback=RuntimeFallbackContext(
            latest_task_snapshot=fallback.latest_task_snapshot,
            selected_thread_metadata=selected_thread_metadata,
            artifact_references=fallback.artifact_references,
            confirmation_payload=fallback.confirmation_payload,
        ),
        request_message=request_message,
    )


def _clean_action_payload_id(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


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


def recent_metadata_invalidates_confirmation(
    recent_messages: list[Message] | None,
) -> bool:
    if not recent_messages:
        return False
    for message in reversed(recent_messages):
        if message.role != "assistant" or not isinstance(message.metadata, dict):
            continue
        if _metadata_invalidates_confirmation(message.metadata):
            return True
        if message.metadata.get("confirmation_card"):
            return False
    return False


def stale_confirmation_action_message(
    *,
    payload: ChatStreamRequest,
    user_id: str,
    conversation_id: str,
    recent_messages: list[Message] | None = None,
    language: str | None = None,
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
    return recovery_message("confirmation_action_stale_card", language=language)


def missing_result_action_run_message(
    *,
    action_type: str,
    language: str | None,
) -> str:
    is_es = str(language or "").lower().startswith("es")
    if action_type == "save_strategy":
        if is_es:
            return (
                "No pude encontrar el backtest completado para guardarlo. "
                "Ejecuta la estrategia de nuevo y luego guárdala desde la "
                "tarjeta de resultado."
            )
        return (
            "I could not find the completed backtest to save. Run the strategy "
            "again, then save it from the result card."
        )
    if is_es:
        return (
            "No pude encontrar el backtest completado para explicarlo. Ejecuta "
            "la estrategia de nuevo y luego usa Explicar resultado desde la "
            "tarjeta de resultado."
        )
    return (
        "I could not find the completed backtest to explain. Run the strategy "
        "again, then explain it from the result card."
    )


def missing_run_confirmation_action_id_message(language: str | None = None) -> str:
    return recovery_message("confirmation_action_missing_identity", language=language)


def confirmation_action_id(payload: ChatStreamRequest) -> str | None:
    if payload.action is None:
        return None
    return _confirmation_id_from_action_payload(payload.action.payload)


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
