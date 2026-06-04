from __future__ import annotations

from typing import Any

from loguru import logger

from argus.agent_runtime.state.models import ConversationMessage
from argus.api import state as api_state
from argus.api.chat.previews import plain_text_preview
from argus.api.dependencies import dev_memory_fallback_enabled
from argus.api.schemas import Conversation, Message
from argus.domain.store import utcnow


def memory_conversation(
    *,
    title: str,
    title_source: str,
    language: str | None,
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


def create_message(
    *,
    user_id: str,
    conversation_id: str,
    role: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> Message:
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
