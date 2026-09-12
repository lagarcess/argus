"""Owner-scoped reads of computed answers for Search, over PostgREST.

Bounded by the page of conversations Search already selected; no model,
retrieval or market-data call. The marker on the message is the only fact
these reads filter on.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from supabase import Client

_COMPUTED_ANSWER_LIMIT = 500
_MESSAGE_SELECT = "id,conversation_id,role,content,metadata,created_at"


class SupabaseComputedAnswerReadMixin:
    client: Client

    def latest_computed_answers(
        self, *, user_id: str, conversation_ids: Iterable[str]
    ) -> dict[str, dict[str, Any]]:
        """The newest computed assistant message per conversation, keyed by id."""
        ids = list(dict.fromkeys(str(value) for value in conversation_ids))
        if not ids:
            return {}
        rows = (
            self.client.table("messages")
            .select(_MESSAGE_SELECT)
            .eq("user_id", user_id)
            .eq("role", "assistant")
            .in_("conversation_id", ids)
            .not_.is_("metadata->computation", "null")
            .order("created_at", desc=True)
            .order("id", desc=True)
            .limit(_COMPUTED_ANSWER_LIMIT)
            .execute()
        )
        latest: dict[str, dict[str, Any]] = {}
        for row in getattr(rows, "data", None) or []:
            conversation_id = str(row.get("conversation_id") or "")
            if conversation_id and conversation_id not in latest:
                latest[conversation_id] = dict(row)
        return latest

    def question_before_message(
        self, *, user_id: str, conversation_id: str, created_at: str
    ) -> dict[str, Any] | None:
        rows = (
            self.client.table("messages")
            .select(_MESSAGE_SELECT)
            .eq("user_id", user_id)
            .eq("conversation_id", conversation_id)
            .eq("role", "user")
            .lte("created_at", created_at)
            .order("created_at", desc=True)
            .order("id", desc=True)
            .limit(1)
            .execute()
        )
        data = getattr(rows, "data", None) or []
        return dict(data[0]) if data else None

    def computed_answer_rows_for_symbols(
        self, *, user_id: str, conversation_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Computed answers that name at least one asset, newest first, bounded."""
        query = (
            self.client.table("messages")
            .select(_MESSAGE_SELECT)
            .eq("user_id", user_id)
            .eq("role", "assistant")
            .not_.is_("metadata->computation->symbols", "null")
        )
        if conversation_id is not None:
            query = query.eq("conversation_id", conversation_id)
        rows = (
            query.order("created_at", desc=True)
            .order("id", desc=True)
            .limit(_COMPUTED_ANSWER_LIMIT)
            .execute()
        )
        return [dict(row) for row in getattr(rows, "data", None) or []]
