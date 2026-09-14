"""Owner-scoped reads of computed answers for Search, over PostgREST.

Bounded by the page of conversations Search already selected; no model,
retrieval or market-data call. The marker on the message is the only fact
these reads filter on.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from supabase import Client

_COMPUTED_ANSWER_LIMIT = 500
_MESSAGE_SELECT = "id,conversation_id,role,content,metadata,created_at"
# Pages a list reads past answers in soft-deleted conversations before it
# stops short of its size.
_LIVE_REFILL_PAGES = 4


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
        """Computed answers that name an asset, in live conversations, newest first."""

        def newest() -> Any:
            query = (
                self.client.table("messages")
                .select(_MESSAGE_SELECT)
                .eq("user_id", user_id)
                .eq("role", "assistant")
                .not_.is_("metadata->computation->symbols", "null")
            )
            if conversation_id is not None:
                query = query.eq("conversation_id", conversation_id)
            return query.order("created_at", desc=True).order("id", desc=True)

        return self._live_newest(
            user_id=user_id, newest=newest, size=_COMPUTED_ANSWER_LIMIT
        )

    def computed_answers_of_kind(
        self, *, user_id: str, kind: str, limit: int
    ) -> list[dict[str, Any]]:
        """The owner's newest computed answers of one kind, in live conversations."""

        def newest() -> Any:
            return (
                self.client.table("messages")
                .select(_MESSAGE_SELECT)
                .eq("user_id", user_id)
                .eq("role", "assistant")
                .eq("metadata->computation->>kind", kind)
                .order("created_at", desc=True)
                .order("id", desc=True)
            )

        return self._live_newest(user_id=user_id, newest=newest, size=limit)

    def _live_newest(
        self, *, user_id: str, newest: Callable[[], Any], size: int
    ) -> list[dict[str, Any]]:
        """Up to ``size`` newest rows in live conversations: a page whose rows sit
        in soft-deleted conversations is refilled from the next, for a bounded
        number of pages."""
        kept: list[dict[str, Any]] = []
        for page in range(_LIVE_REFILL_PAGES if size > 0 else 0):
            start = page * size
            rows = newest().range(start, start + size - 1).execute()
            found = [dict(row) for row in getattr(rows, "data", None) or []]
            kept.extend(self._in_live_conversations(user_id=user_id, rows=found))
            if len(kept) >= size or len(found) < size:
                break
        return kept[:size]

    def _in_live_conversations(
        self, *, user_id: str, rows: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """The rows whose conversation the owner holds and has not soft-deleted."""
        conversation_ids = list(
            dict.fromkeys(
                str(row.get("conversation_id"))
                for row in rows
                if row.get("conversation_id")
            )
        )
        if not conversation_ids:
            return []
        live = (
            self.client.table("conversations")
            .select("id")
            .eq("user_id", user_id)
            .in_("id", conversation_ids)
            .is_("deleted_at", "null")
            .execute()
        )
        live_ids = {str(row.get("id")) for row in getattr(live, "data", None) or []}
        return [row for row in rows if str(row.get("conversation_id")) in live_ids]
