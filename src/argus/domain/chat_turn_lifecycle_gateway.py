"""Focused Supabase gateway mixin for ordinary-turn recovery state."""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from argus.api.chat.previews import plain_text_preview
from argus.api.schemas import Message
from argus.domain.chat_turn_lifecycle import TransitionResult, TurnStatus
from supabase import Client


def _data_rows(result: Any) -> list[dict[str, Any]]:
    data = getattr(result, "data", None)
    if not data:
        return []
    if isinstance(data, list):
        return [dict(row) for row in data]
    if isinstance(data, dict):
        return [dict(data)]
    raise RuntimeError("Lifecycle RPC returned an invalid response.")


class ChatTurnLifecycleGatewayMixin:
    """Service-role persistence methods for the approved lifecycle RPCs."""

    client: Client

    def accept_chat_turn(
        self,
        *,
        user_id: str,
        conversation_id: str,
        request_id: str,
        message: Message,
    ) -> Message:
        if message.conversation_id != conversation_id:
            raise ValueError("Message conversation does not match acceptance.")
        if message.role != "user":
            raise ValueError("Accepted chat-turn message must be a user message.")
        result = self.client.rpc(
            "accept_chat_turn",
            {
                "p_user_id": user_id,
                "p_conversation_id": conversation_id,
                "p_message_id": message.id,
                "p_role": message.role,
                "p_content": message.content,
                "p_metadata": message.metadata or {},
                "p_created_at": message.created_at.isoformat(),
                "p_preview": plain_text_preview(
                    message.content,
                    max_length=180,
                ),
                "p_request_id": request_id,
            },
        ).execute()
        rows = _data_rows(result)
        if not rows or not isinstance(rows[0].get("message"), dict):
            raise RuntimeError("Chat-turn acceptance did not return a message.")
        return Message.model_validate(rows[0]["message"])

    def transition_chat_turn(
        self,
        *,
        turn_id: str,
        to_status: TurnStatus,
        assistant_message_id: str | None,
        reconciled_outcome: str | None,
        failure_code: str | None,
        retryable: bool | None,
    ) -> TransitionResult:
        result = self.client.rpc(
            "transition_chat_turn",
            {
                "p_turn_id": turn_id,
                "p_to_status": to_status,
                "p_assistant_message_id": assistant_message_id,
                "p_reconciled_outcome": reconciled_outcome,
                "p_failure_code": failure_code,
                "p_retryable": retryable,
            },
        ).execute()
        rows = _data_rows(result)
        if not rows or rows[0].get("outcome") not in {
            "applied",
            "noop",
            "conflict",
            "missing",
            "invalid",
        }:
            raise RuntimeError("Chat-turn transition returned an invalid outcome.")
        row = rows[0].get("row")
        return TransitionResult(
            outcome=cast(Any, rows[0]["outcome"]),
            row=dict(row) if isinstance(row, dict) else None,
        )

    def reconcile_stale_chat_turns(
        self,
        *,
        conversation_id: str,
        user_id: str,
    ) -> list[dict[str, Any]]:
        result = self.client.rpc(
            "reconcile_stale_chat_turns",
            {
                "p_conversation_id": conversation_id,
                "p_user_id": user_id,
            },
        ).execute()
        return _data_rows(result)

    def list_projectable_chat_turns(
        self,
        *,
        conversation_id: str,
        user_id: str,
        message_ids: list[str],
    ) -> list[dict[str, Any]]:
        if not message_ids:
            return []
        canonical_message_ids = list(
            dict.fromkeys(str(UUID(message_id)) for message_id in message_ids)
        )
        message_ids_filter = ",".join(canonical_message_ids)
        rows = (
            self.client.table("chat_turn_lifecycles")
            .select("*")
            .eq("user_id", user_id)
            .eq("conversation_id", conversation_id)
            .or_(
                f"assistant_message_id.in.({message_ids_filter}),"
                "and(assistant_message_id.is.null,"
                f"turn_id.in.({message_ids_filter}))"
            )
            .execute()
            .data
            or []
        )
        message_id_set = set(canonical_message_ids)
        by_turn_id = {
            str(row["turn_id"]): dict(row)
            for row in rows
            if row.get("turn_id") is not None
            and (
                str(row.get("assistant_message_id")) in message_id_set
                or (
                    row.get("assistant_message_id") is None
                    and str(row["turn_id"]) in message_id_set
                )
            )
        }
        return sorted(
            by_turn_id.values(),
            key=lambda row: str(row["turn_id"]),
        )
