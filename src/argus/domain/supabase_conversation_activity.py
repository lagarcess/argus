"""Bounded Supabase RPC gateway for conversation activity and read state."""

from __future__ import annotations

from typing import Any, Literal

_MAX_ACTIVITY_CONVERSATIONS = 100


def _rows(result: Any) -> list[dict[str, Any]]:
    data = getattr(result, "data", None)
    if not data:
        return []
    if isinstance(data, list):
        return [dict(row) for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        return [dict(data)]
    return []


def _distinct_conversation_ids(conversation_ids: list[str]) -> list[str]:
    distinct = list(dict.fromkeys(conversation_ids))
    if len(distinct) > _MAX_ACTIVITY_CONVERSATIONS:
        raise ValueError("At most 100 conversations may be projected at once.")
    return distinct


class SupabaseConversationActivityMixin:
    """Service-role-only activity reads, reconciliation, and read mutations."""

    client: Any

    def reconcile_conversation_activity_turns(
        self,
        *,
        user_id: str,
        conversation_ids: list[str],
    ) -> list[dict[str, Any]]:
        requested = _distinct_conversation_ids(conversation_ids)
        if not requested:
            return []
        result = self.client.rpc(
            "reconcile_stale_conversation_activity_turns",
            {
                "p_user_id": user_id,
                "p_conversation_ids": requested,
            },
        ).execute()
        return _rows(result)

    def read_conversation_activity_batch(
        self,
        *,
        user_id: str,
        conversation_ids: list[str],
    ) -> list[dict[str, Any]]:
        requested = _distinct_conversation_ids(conversation_ids)
        if not requested:
            return []
        result = self.client.rpc(
            "read_conversation_activity_sources",
            {
                "p_user_id": user_id,
                "p_conversation_ids": requested,
            },
        ).execute()
        return _rows(result)

    def mutate_conversation_activity_read_state(
        self,
        *,
        user_id: str,
        conversation_id: str,
        action: Literal["mark_unread", "mark_read"],
        source_kind: Literal["chat_turn", "backtest_job"] | None,
        source_id: str | None,
    ) -> dict[str, Any]:
        result = self.client.rpc(
            "mutate_conversation_activity_read_state",
            {
                "p_user_id": user_id,
                "p_conversation_id": conversation_id,
                "p_action": action,
                "p_source_kind": source_kind,
                "p_source_id": source_id,
            },
        ).execute()
        rows = _rows(result)
        return rows[0] if rows else {}
