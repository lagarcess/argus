from __future__ import annotations

from typing import Any

from loguru import logger

from argus.agent_runtime.state.models import ConversationMessage
from argus.api import state as api_state
from argus.api.chat.previews import plain_text_preview
from argus.api.dependencies import dev_memory_fallback_enabled
from argus.api.schemas import Conversation, Message
from argus.domain.store import utcnow

_AUTHORITATIVE_ARTIFACT_KEYS = {
    "active_confirmation_reference",
    "backtest_job",
    "backtest_job_id",
    "confirmation_card",
    "confirmation_payload",
    "latest_run_id",
    "result_card",
    "result_run_id",
}
_RUNTIME_FAILURE_SUPERSEDED_KEY = "agent_runtime_failure_superseded"


def memory_conversation(
    *,
    title: str,
    title_source: str,
    language: str | None,
    user_id: str | None = None,
) -> Conversation:
    now = utcnow()
    conversation = Conversation(
        id=api_state.store.new_id(),
        title=title,
        title_source=title_source,
        language=language,
        created_at=now,
        updated_at=now,
    )
    api_state.store.conversations[conversation.id] = conversation
    if user_id is not None:
        api_state.store.conversation_owners[conversation.id] = user_id
    api_state.store.messages[conversation.id] = []
    return conversation


def message_preview(content: str, max_length: int = 180) -> str | None:
    return plain_text_preview(content, max_length=max_length)


def memory_message(
    *,
    conversation_id: str,
    role: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> Message:
    message = Message(
        id=api_state.store.new_id(),
        conversation_id=conversation_id,
        role=role,
        content=content,
        created_at=utcnow(),
        metadata=metadata,
    )
    api_state.store.messages.setdefault(conversation_id, []).append(message)
    preview = message_preview(content)
    conversation = api_state.store.conversations.get(conversation_id)
    if conversation and preview:
        api_state.store.conversations[conversation_id] = conversation.model_copy(
            update={"last_message_preview": preview, "updated_at": utcnow()}
        )
    return message


def _ephemeral_suppressed_message(
    *,
    conversation_id: str,
    role: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> Message:
    return Message(
        id=api_state.store.new_id(),
        conversation_id=conversation_id,
        role=role,
        content=content,
        created_at=utcnow(),
        metadata=metadata,
    )


def create_message(
    *,
    user_id: str,
    conversation_id: str,
    role: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> Message:
    if _should_suppress_late_success_artifact(
        user_id=user_id,
        conversation_id=conversation_id,
        role=role,
        metadata=metadata,
    ):
        logger.warning(
            "Suppressing late assistant artifact after terminal runtime failure",
            conversation_id=conversation_id,
            artifact_keys=sorted(
                key
                for key in _AUTHORITATIVE_ARTIFACT_KEYS
                if isinstance(metadata, dict) and metadata.get(key)
            ),
        )
        return _ephemeral_suppressed_message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            metadata=metadata,
        )
    if api_state.supabase_gateway is not None:
        try:
            return api_state.supabase_gateway.create_message(
                user_id=user_id,
                conversation_id=conversation_id,
                role=role,
                content=content,
                metadata=metadata,
            )
        except Exception as exc:
            if not dev_memory_fallback_enabled():
                raise
            logger.warning(
                "Supabase message write failed; using dev memory fallback",
                error=str(exc),
                conversation_id=conversation_id,
            )
    return memory_message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        metadata=metadata,
    )


def reconcile_reload_message_metadata(messages: list[Message]) -> list[Message]:
    artifact_request_ids_after: set[str] = set()
    same_segment_artifact_after = False
    reconciled_reversed: list[Message] = []
    for message in reversed(messages):
        metadata = message.metadata
        next_message = message
        if message.role == "user":
            same_segment_artifact_after = False
            reconciled_reversed.append(next_message)
            continue
        if message.role == "assistant" and isinstance(metadata, dict):
            request_id = _runtime_turn_request_id(metadata)
            should_supersede = (
                request_id in artifact_request_ids_after
                if request_id is not None
                else same_segment_artifact_after
            )
            if should_supersede and _is_visible_runtime_failure(metadata):
                updated_metadata = _supersede_retry_last_turn(metadata)
                updated_metadata = {
                    **updated_metadata,
                    _RUNTIME_FAILURE_SUPERSEDED_KEY: True,
                }
                if updated_metadata is not metadata:
                    next_message = message.model_copy(
                        update={"metadata": updated_metadata}
                    )
            if _metadata_has_authoritative_artifact(metadata):
                same_segment_artifact_after = True
                if request_id is not None:
                    artifact_request_ids_after.add(request_id)
        reconciled_reversed.append(next_message)
    return list(reversed(reconciled_reversed))


def load_runtime_thread_history(
    *,
    user_id: str,
    conversation_id: str,
    limit: int = 20,
) -> list[ConversationMessage]:
    messages: list[Message] = []
    if api_state.supabase_gateway is not None:
        try:
            messages = api_state.supabase_gateway.list_messages(
                user_id=user_id,
                conversation_id=conversation_id,
                limit=limit,
            )
        except Exception as exc:
            if not dev_memory_fallback_enabled():
                raise
            logger.warning(
                "Supabase message history read failed; using dev memory fallback",
                error=str(exc),
                conversation_id=conversation_id,
            )
    if not messages:
        messages = list(api_state.store.messages.get(conversation_id, []))[-limit:]
    history: list[ConversationMessage] = []
    for message in messages:
        if message.role not in {"user", "assistant", "system", "tool"}:
            continue
        history.append(ConversationMessage(role=message.role, content=message.content))
    return history


def _should_suppress_late_success_artifact(
    *,
    user_id: str,
    conversation_id: str,
    role: str,
    metadata: dict[str, Any] | None,
) -> bool:
    if role != "assistant" or not _metadata_has_authoritative_artifact(metadata):
        return False
    messages = _recent_persisted_messages_for_guard(
        user_id=user_id,
        conversation_id=conversation_id,
    )
    return _has_unresolved_visible_runtime_failure(
        messages,
        candidate_request_id=_runtime_turn_request_id(metadata),
    )


def _recent_persisted_messages_for_guard(
    *,
    user_id: str,
    conversation_id: str,
    limit: int = 25,
) -> list[Message]:
    messages: list[Message] = []
    if api_state.supabase_gateway is not None:
        try:
            messages = api_state.supabase_gateway.list_messages(
                user_id=user_id,
                conversation_id=conversation_id,
                limit=limit,
            )
        except Exception as exc:
            if not dev_memory_fallback_enabled():
                raise
            logger.warning(
                "Terminal runtime failure guard could not read Supabase messages",
                error=str(exc),
                conversation_id=conversation_id,
            )
    if (
        not messages
        or (
            dev_memory_fallback_enabled()
            and conversation_id in api_state.store.conversations
            and api_state.store.messages.get(conversation_id)
        )
    ):
        messages = list(api_state.store.messages.get(conversation_id, []))[-limit:]
    return sorted(messages, key=lambda item: (item.created_at, item.id))


def latest_unresolved_terminal_runtime_failure_metadata(
    *,
    user_id: str,
    conversation_id: str,
    limit: int = 25,
) -> dict[str, Any] | None:
    messages = _recent_persisted_messages_for_guard(
        user_id=user_id,
        conversation_id=conversation_id,
        limit=limit,
    )
    for message in reversed(messages):
        if message.role == "user":
            return None
        if message.role != "assistant" or not isinstance(message.metadata, dict):
            continue
        if _metadata_has_authoritative_artifact(message.metadata):
            return None
        if _is_terminal_owner_runtime_failure(message.metadata):
            return message.metadata
    return None


def _has_unresolved_visible_runtime_failure(
    messages: list[Message],
    *,
    candidate_request_id: str | None,
) -> bool:
    if candidate_request_id:
        resolved_request_ids: set[str] = set()
        for message in reversed(messages):
            if message.role != "assistant" or not isinstance(message.metadata, dict):
                continue
            message_request_id = _runtime_turn_request_id(message.metadata)
            if (
                message_request_id == candidate_request_id
                and _metadata_has_authoritative_artifact(message.metadata)
            ):
                resolved_request_ids.add(message_request_id)
                continue
            if (
                message_request_id == candidate_request_id
                and message_request_id not in resolved_request_ids
                and _is_terminal_owner_runtime_failure(message.metadata)
            ):
                return True
        return False

    for message in reversed(messages):
        if message.role == "user":
            return False
        if message.role != "assistant" or not isinstance(message.metadata, dict):
            continue
        if _metadata_has_authoritative_artifact(message.metadata):
            return False
        if _is_terminal_owner_runtime_failure(message.metadata):
            return True
    return False


def _metadata_has_authoritative_artifact(
    metadata: dict[str, Any] | None,
) -> bool:
    if not isinstance(metadata, dict):
        return False
    if any(metadata.get(key) for key in _AUTHORITATIVE_ARTIFACT_KEYS):
        return True
    artifact_references = metadata.get("artifact_references")
    if isinstance(artifact_references, list):
        return any(
            isinstance(reference, dict)
            and str(reference.get("artifact_kind") or "")
            in {"confirmation", "result", "backtest_job"}
            for reference in artifact_references
        )
    return False


def _is_visible_runtime_failure(metadata: dict[str, Any]) -> bool:
    if metadata.get("agent_runtime_stage_outcome") != "agent_runtime_failure":
        return False
    recovery = metadata.get("recovery")
    if not isinstance(recovery, dict):
        return metadata.get("conversation_mode") == "recovery"
    return (
        recovery.get("code") in {"runtime_failure", "agent_runtime_failure"}
        or metadata.get("conversation_mode") == "recovery"
    )


def _is_terminal_owner_runtime_failure(metadata: dict[str, Any]) -> bool:
    turn = metadata.get("agent_runtime_turn")
    return (
        isinstance(turn, dict)
        and turn.get("status") == "failed"
        and turn.get("terminal") is True
        and _is_visible_runtime_failure(metadata)
    )


def _runtime_turn_request_id(metadata: dict[str, Any] | None) -> str | None:
    if not isinstance(metadata, dict):
        return None
    turn = metadata.get("agent_runtime_turn")
    if not isinstance(turn, dict):
        return None
    request_id = turn.get("request_id")
    if not isinstance(request_id, str):
        return None
    return request_id.strip() or None


def _supersede_retry_last_turn(metadata: dict[str, Any]) -> dict[str, Any]:
    recovery = metadata.get("recovery")
    retryable_recovery = isinstance(recovery, dict) and recovery.get("retryable") is True
    if "retry_last_turn" not in metadata and not retryable_recovery:
        return metadata
    updated = dict(metadata)
    updated.pop("retry_last_turn", None)
    if retryable_recovery:
        updated_recovery = dict(recovery)
        updated_recovery["retryable"] = False
        updated["recovery"] = updated_recovery
    return updated
