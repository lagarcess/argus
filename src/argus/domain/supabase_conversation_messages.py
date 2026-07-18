"""Focused Supabase persistence boundary for durable conversation messages."""

from __future__ import annotations

from typing import Any, cast
from uuid import uuid4

from argus.api.chat.previews import (
    is_degraded_clarification_compatibility_text,
    plain_text_preview,
)
from argus.api.schemas import Message, MessageRole
from argus.domain.store import utcnow
from supabase import Client


def _row_one(result: Any) -> dict[str, Any] | None:
    data = getattr(result, "data", None)
    if not data:
        return None
    if isinstance(data, list):
        return data[0] if data else None
    return cast(dict[str, Any], data)


def message_preview(
    content: str,
    max_length: int = 180,
    *,
    role: str = "assistant",
    metadata: dict[str, Any] | None = None,
) -> str | None:
    """Canonical conversation-preview computation for every durable append."""

    if is_degraded_clarification_compatibility_text(
        role=role,
        metadata=metadata,
    ):
        return None
    return plain_text_preview(content, max_length=max_length)


_message_preview = message_preview


class ConversationMessagePersistenceMixin:
    """Owner-scoped message queries and serialized RPC-backed appends."""

    client: Client

    def get_message(
        self,
        *,
        user_id: str,
        conversation_id: str,
        message_id: str,
    ) -> Message | None:
        result = (
            self.client.table("messages")
            .select("id,conversation_id,role,content,metadata,created_at")
            .eq("user_id", user_id)
            .eq("conversation_id", conversation_id)
            .eq("id", message_id)
            .limit(1)
            .execute()
        )
        row = _row_one(result)
        return Message.model_validate(row) if row else None

    def latest_message(
        self,
        *,
        user_id: str,
        conversation_id: str,
    ) -> Message | None:
        result = (
            self.client.table("messages")
            .select("id,conversation_id,role,content,metadata,created_at")
            .eq("user_id", user_id)
            .eq("conversation_id", conversation_id)
            .order("created_at", desc=True)
            .order("id", desc=True)
            .limit(1)
            .execute()
        )
        row = _row_one(result)
        return Message.model_validate(row) if row else None

    def create_message(
        self,
        *,
        user_id: str,
        conversation_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> Message:
        message = Message(
            id=str(uuid4()),
            conversation_id=conversation_id,
            role=cast(MessageRole, role),
            content=content,
            metadata=metadata if metadata is not None else {},
            created_at=utcnow(),
        )
        appended, _source, _replayed = self._append_conversation_message(
            user_id=user_id,
            message=message,
            preview=_message_preview(content, role=role, metadata=metadata),
        )
        return appended

    def claim_response_option_action(
        self,
        *,
        user_id: str,
        conversation_id: str,
        source_assistant_id: str,
        option_id: str,
        replacement_values: dict[str, Any],
        request_message: Message,
        expected_source_metadata: dict[str, Any] | None = None,
    ) -> tuple[Message, Message] | None:
        if request_message.conversation_id != conversation_id:
            raise ValueError("Request message conversation does not match claim.")
        # #240: the claim routes through the acceptance boundary so the exact
        # source validation, message append, and lifecycle row commit in one
        # database transaction — never a second post-transaction write.
        turn = (request_message.metadata or {}).get("agent_runtime_turn")
        request_id = turn.get("request_id") if isinstance(turn, dict) else None
        result = self.client.rpc(
            "accept_chat_turn",
            {
                "p_user_id": user_id,
                "p_conversation_id": conversation_id,
                "p_message_id": request_message.id,
                "p_role": request_message.role,
                "p_content": request_message.content,
                "p_metadata": (
                    request_message.metadata
                    if request_message.metadata is not None
                    else {}
                ),
                "p_created_at": request_message.created_at.isoformat(),
                "p_preview": message_preview(
                    request_message.content,
                    role=request_message.role,
                    metadata=request_message.metadata,
                ),
                "p_request_id": request_id,
                "p_expected_source_assistant_id": source_assistant_id,
                "p_expected_source_metadata": expected_source_metadata,
                "p_option_id": option_id,
                "p_replacement_values": replacement_values,
            },
        ).execute()
        row = _row_one(result)
        if row is None or not isinstance(row.get("message"), dict):
            return None
        source_row = row.get("source_message")
        if not source_row:
            return None
        return (
            Message.model_validate(source_row),
            Message.model_validate(row["message"]),
        )

    def _append_conversation_message(
        self,
        *,
        user_id: str,
        message: Message,
        preview: str | None,
        expected_source_assistant_id: str | None = None,
        option_id: str | None = None,
        replacement_values: dict[str, Any] | None = None,
        expected_source_metadata: dict[str, Any] | None = None,
    ) -> tuple[Message, Message | None, bool]:
        result = self.client.rpc(
            "append_conversation_message",
            {
                "p_user_id": user_id,
                "p_conversation_id": message.conversation_id,
                "p_message_id": message.id,
                "p_role": message.role,
                "p_content": message.content,
                "p_metadata": message.metadata if message.metadata is not None else {},
                "p_created_at": message.created_at.isoformat(),
                "p_preview": preview,
                "p_expected_source_assistant_id": expected_source_assistant_id,
                "p_expected_source_metadata": expected_source_metadata,
                "p_option_id": option_id,
                "p_replacement_values": replacement_values,
            },
        ).execute()
        row = _row_one(result)
        if row is None:
            return message, None, False
        appended = Message.model_validate(row["message"])
        source_row = row.get("source_message")
        source = Message.model_validate(source_row) if source_row else None
        return appended, source, bool(row.get("replayed", False))
