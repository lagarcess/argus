from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, cast

from loguru import logger

from argus.agent_runtime.state.models import ConversationMessage
from argus.api import state as api_state
from argus.api.chat.previews import (
    is_degraded_clarification_compatibility_text,
    plain_text_preview,
)
from argus.api.dependencies import dev_memory_fallback_enabled
from argus.api.schemas import Conversation, Message, MessageRole
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


@dataclass(frozen=True)
class ResponseOptionActionClaim:
    source_message: Message
    request_message: Message


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


def message_preview(
    content: str,
    max_length: int = 180,
    *,
    role: str = "assistant",
    metadata: dict[str, Any] | None = None,
) -> str | None:
    if is_degraded_clarification_compatibility_text(
        role=role,
        metadata=metadata,
    ):
        return None
    # Onboarding control tokens are localized at render time and must never
    # surface raw in the conversation preview.
    if role == "user" and content.startswith("__ONBOARDING_"):
        return None
    return plain_text_preview(content, max_length=max_length)


def memory_message(
    *,
    conversation_id: str,
    role: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> Message:
    return _append_memory_message(
        prepare_message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            metadata=metadata,
        )
    )


def prepare_message(
    *,
    conversation_id: str,
    role: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> Message:
    return Message(
        id=api_state.store.new_id(),
        conversation_id=conversation_id,
        role=cast(MessageRole, role),
        content=content,
        created_at=utcnow(),
        metadata=metadata if metadata is not None else {},
    )


def _append_memory_message(message: Message) -> Message:
    with api_state.store.conversation_message_lock:
        messages = api_state.store.messages.setdefault(message.conversation_id, [])
        if messages:
            latest_created_at = max(item.created_at for item in messages)
            if message.created_at <= latest_created_at:
                message = message.model_copy(
                    update={"created_at": latest_created_at + timedelta(microseconds=1)}
                )
        messages.append(message)
        preview = message_preview(
            message.content,
            role=message.role,
            metadata=message.metadata,
        )
        conversation = api_state.store.conversations.get(message.conversation_id)
        if conversation and preview:
            api_state.store.conversations[message.conversation_id] = (
                conversation.model_copy(
                    update={"last_message_preview": preview, "updated_at": utcnow()}
                )
            )
        return message


def claim_response_option_action(
    *,
    user_id: str,
    conversation_id: str,
    source_assistant_id: str,
    option_id: str,
    replacement_values: dict[str, Any],
    request_message: Message,
    expected_source_metadata: dict[str, Any] | None = None,
) -> ResponseOptionActionClaim | None:
    gateway = api_state.supabase_gateway
    if gateway is not None:
        claimed = gateway.claim_response_option_action(
            user_id=user_id,
            conversation_id=conversation_id,
            source_assistant_id=source_assistant_id,
            option_id=option_id,
            replacement_values=replacement_values,
            request_message=request_message,
            expected_source_metadata=expected_source_metadata,
        )
        if claimed is None:
            return None
        source_message, accepted_request = claimed
        return ResponseOptionActionClaim(
            source_message=source_message,
            request_message=accepted_request,
        )

    with api_state.store.conversation_message_lock:
        if api_state.store.conversation_owners.get(conversation_id) != user_id:
            return None
        if request_message.conversation_id != conversation_id:
            raise ValueError("Request message conversation does not match claim.")

        existing = next(
            (
                message
                for messages in api_state.store.messages.values()
                for message in messages
                if message.id == request_message.id
            ),
            None,
        )
        conversation_messages = api_state.store.messages.get(conversation_id, [])
        if existing is not None:
            if not _same_immutable_message(existing, request_message):
                raise ValueError(
                    "Message identity collided with different immutable payload."
                )
            preceding = [
                message
                for message in conversation_messages
                if (message.created_at, message.id) < (existing.created_at, existing.id)
            ]
            replay_source = (
                max(preceding, key=lambda item: (item.created_at, item.id))
                if preceding
                else None
            )
            if not _is_exact_response_option_source(
                replay_source,
                source_assistant_id=source_assistant_id,
                option_id=option_id,
                replacement_values=replacement_values,
                expected_source_metadata=expected_source_metadata,
            ):
                return None
            assert replay_source is not None
            return ResponseOptionActionClaim(
                source_message=replay_source,
                request_message=existing,
            )

        latest = (
            max(conversation_messages, key=lambda item: (item.created_at, item.id))
            if conversation_messages
            else None
        )
        if not _is_exact_response_option_source(
            latest,
            source_assistant_id=source_assistant_id,
            option_id=option_id,
            replacement_values=replacement_values,
            expected_source_metadata=expected_source_metadata,
        ):
            return None
        assert latest is not None
        previous_conversation = api_state.store.conversations.get(conversation_id)
        accepted_request = _append_memory_message(request_message)
        # #240 acceptance rides the claim transaction: the accepted request
        # and its lifecycle row persist together or not at all.
        acceptance_request_id = _turn_acceptance_request_id(
            role="user", metadata=request_message.metadata
        )
        if acceptance_request_id is not None:
            from argus.domain.chat_turn_lifecycle import create_accepted_memory

            try:
                create_accepted_memory(
                    api_state.store,
                    turn_id=accepted_request.id,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    request_id=acceptance_request_id,
                )
            except Exception:
                messages = api_state.store.messages.get(conversation_id, [])
                api_state.store.messages[conversation_id] = [
                    item for item in messages if item.id != accepted_request.id
                ]
                if previous_conversation is not None:
                    api_state.store.conversations[conversation_id] = (
                        previous_conversation
                    )
                raise
        return ResponseOptionActionClaim(
            source_message=latest,
            request_message=accepted_request,
        )


def _same_immutable_message(existing: Message, requested: Message) -> bool:
    return (
        existing.conversation_id == requested.conversation_id
        and existing.role == requested.role
        and existing.content == requested.content
        and (existing.metadata or {}) == (requested.metadata or {})
    )


def _is_exact_response_option_source(
    source_message: Message | None,
    *,
    source_assistant_id: str,
    option_id: str,
    replacement_values: dict[str, Any],
    expected_source_metadata: dict[str, Any] | None = None,
) -> bool:
    if (
        source_message is None
        or source_message.id != source_assistant_id
        or source_message.role != "assistant"
        or not isinstance(source_message.metadata, dict)
    ):
        return False
    if (
        expected_source_metadata is not None
        and source_message.metadata != expected_source_metadata
    ):
        return False
    clarification = source_message.metadata.get("clarification")
    if not isinstance(clarification, dict):
        return False
    options = clarification.get("options")
    if not isinstance(options, list):
        return False
    return any(
        isinstance(option, dict)
        and option.get("id") == option_id
        and option.get("replacement_values") == replacement_values
        for option in options
    )


def owned_conversation_message(
    *,
    user_id: str,
    conversation_id: str,
    message_id: str,
) -> Message | None:
    gateway = api_state.supabase_gateway
    if gateway is not None:
        return gateway.get_message(
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
        )
    with api_state.store.conversation_message_lock:
        if api_state.store.conversation_owners.get(conversation_id) != user_id:
            return None
        return next(
            (
                message
                for message in api_state.store.messages.get(conversation_id, [])
                if message.id == message_id
            ),
            None,
        )


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
    metadata = _attach_turn_lifecycle_identity(
        user_id=user_id,
        conversation_id=conversation_id,
        role=role,
        metadata=metadata,
    )
    acceptance_request_id = _turn_acceptance_request_id(role=role, metadata=metadata)
    if acceptance_request_id is not None:
        return _accept_user_turn(
            user_id=user_id,
            conversation_id=conversation_id,
            role=role,
            content=content,
            metadata=metadata,
            request_id=acceptance_request_id,
        )
    if api_state.supabase_gateway is not None:
        try:
            persisted = api_state.supabase_gateway.create_message(
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
        else:
            _apply_turn_lifecycle_effects(user_id=user_id, message=persisted)
            return persisted
    persisted = memory_message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        metadata=metadata,
    )
    _apply_turn_lifecycle_effects(user_id=user_id, message=persisted)
    return persisted


def _turn_acceptance_request_id(
    *, role: str, metadata: dict[str, Any] | None
) -> str | None:
    """The acceptance case: a started user turn that is not a run_backtest
    action (backtest_jobs owns that action's durable state)."""

    if role != "user" or not isinstance(metadata, dict):
        return None
    turn = metadata.get("agent_runtime_turn")
    if not isinstance(turn, dict) or turn.get("status") != "started":
        return None
    chat_action = metadata.get("chat_action")
    if isinstance(chat_action, dict) and chat_action.get("type") == "run_backtest":
        return None
    request_id = turn.get("request_id")
    if isinstance(request_id, str) and request_id:
        return request_id
    return None


# Public name: the route uses the same predicate to decide whether a persisted
# request message owns an ordinary lifecycle (run_backtest turns never do).
ordinary_turn_request_id = _turn_acceptance_request_id


def _accept_user_turn(
    *,
    user_id: str,
    conversation_id: str,
    role: str,
    content: str,
    metadata: dict[str, Any] | None,
    request_id: str,
) -> Message:
    """#240 acceptance boundary: the user message and its lifecycle row
    persist together. A lifecycle failure never leaves an accepted message
    without its lifecycle (fail closed; the user retries the turn)."""

    from argus.domain.chat_turn_lifecycle import create_accepted_memory

    if api_state.supabase_gateway is not None:
        try:
            row = api_state.supabase_gateway.accept_chat_turn(
                user_id=user_id,
                conversation_id=conversation_id,
                role=role,
                content=content,
                metadata=metadata,
                request_id=request_id,
            )
            return Message.model_validate(row)
        except Exception as exc:
            if not dev_memory_fallback_enabled():
                raise
            logger.warning(
                "Supabase turn acceptance failed; using dev memory fallback",
                error_type=type(exc).__name__,
                conversation_id=conversation_id,
            )

    with api_state.store.conversation_message_lock:
        previous_conversation = api_state.store.conversations.get(conversation_id)
        message = memory_message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            metadata=metadata,
        )
        try:
            create_accepted_memory(
                api_state.store,
                turn_id=message.id,
                user_id=user_id,
                conversation_id=conversation_id,
                request_id=request_id,
            )
        except Exception:
            messages = api_state.store.messages.get(conversation_id, [])
            api_state.store.messages[conversation_id] = [
                item for item in messages if item.id != message.id
            ]
            if previous_conversation is not None:
                api_state.store.conversations[conversation_id] = previous_conversation
            raise
        return message


def _attach_turn_lifecycle_identity(
    *,
    user_id: str,
    conversation_id: str,
    role: str,
    metadata: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """#240: terminal assistant metadata carries the accepted turn's
    ``turn_id`` so reconciliation evidence is exact. Written with the message,
    before the lifecycle transition, so it stays discoverable if that
    transition is the interrupted operation."""

    if role != "assistant" or not isinstance(metadata, dict):
        return metadata
    turn = metadata.get("agent_runtime_turn")
    if not isinstance(turn, dict) or turn.get("terminal") is not True:
        return metadata
    if turn.get("turn_id"):
        return metadata
    request_id = turn.get("request_id")
    if not isinstance(request_id, str) or not request_id:
        return metadata

    from argus.domain.chat_turn_lifecycle import find_active_turn_memory

    if api_state.supabase_gateway is None:
        row = find_active_turn_memory(
            api_state.store,
            conversation_id=conversation_id,
            request_id=request_id,
            user_id=user_id,
        )
    else:
        try:
            row = api_state.supabase_gateway.find_active_chat_turn(
                conversation_id=conversation_id,
                request_id=request_id,
                user_id=user_id,
            )
        except Exception as exc:
            logger.warning(
                "Turn lifecycle lookup failed open during terminal enrichment",
                error_type=type(exc).__name__,
                conversation_id=conversation_id,
            )
            row = None
    if not row or row.get("user_id") != user_id:
        return metadata
    return {
        **metadata,
        "agent_runtime_turn": {**turn, "turn_id": row.get("turn_id")},
    }


def _apply_turn_lifecycle_effects(*, user_id: str, message: Message) -> None:
    """#240 choke point: user acceptance and terminal transitions ride the
    single durable message write path, never a second orchestrator."""

    from argus.api.chat import turn_lifecycle_hooks

    metadata = message.metadata if isinstance(message.metadata, dict) else None
    if metadata is None:
        return
    turn = metadata.get("agent_runtime_turn")
    if not isinstance(turn, dict):
        return

    # Acceptance is owned exclusively by the atomic _accept_user_turn
    # boundary; this choke point only applies terminal transitions.
    if message.role == "assistant" and turn.get("terminal") is True:
        turn_id = turn.get("turn_id")
        if not isinstance(turn_id, str) or not turn_id:
            return
        status = str(turn.get("status") or "")
        to_status = (
            "completed"
            if status in ("completed", "succeeded")
            else "recoverable_failed"
            if status in ("recoverable_failed", "failed")
            else None
        )
        if to_status is None:
            return
        # The canonical turn envelope owns failure evidence; legacy top-level
        # metadata fields remain a read-compatible fallback.
        failure_code = turn.get("failure_code") or metadata.get("failure_code")
        retryable = turn.get("retryable")
        if not isinstance(retryable, bool):
            retryable = metadata.get("retryable")
        turn_lifecycle_hooks.transition_turn(
            turn_id=turn_id,
            to_status=to_status,
            assistant_message_id=message.id,
            failure_code=str(failure_code) if failure_code else None,
            retryable=retryable if isinstance(retryable, bool) else None,
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
        if is_degraded_clarification_compatibility_text(
            role=message.role,
            metadata=message.metadata,
        ):
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
    if not messages or (
        dev_memory_fallback_enabled()
        and conversation_id in api_state.store.conversations
        and api_state.store.messages.get(conversation_id)
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


def metadata_has_authoritative_artifact(
    metadata: dict[str, Any] | None,
) -> bool:
    """Public name: read-time projections use the same authoritative-artifact
    predicate to supersede stale retry affordances."""

    return _metadata_has_authoritative_artifact(metadata)


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
            in {"confirmation", "result", "backtest_result", "backtest_job"}
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
    # Canonical status is recoverable_failed; historical rows persisted the
    # legacy "failed" status and must stay readable.
    return (
        isinstance(turn, dict)
        and turn.get("status") in ("recoverable_failed", "failed")
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
