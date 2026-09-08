"""Owner-scoped persistence for decisions attached to computed answers.

A backtest decision keeps its RPC path in the gateway proper, because it moves
the artifact, idea, and version lifecycles together. A computed-answer
decision has no sidecars: it is one row keyed by the message it attaches to.
"""

from __future__ import annotations

from typing import Any

from argus.api.decision_contract import DecisionNote
from argus.api.schemas import Message
from argus.domain.decision_attachment import decision_message_metadata
from argus.domain.store import utcnow
from supabase import Client


def _row_one(result: Any) -> dict[str, Any] | None:
    data = getattr(result, "data", None)
    if not data:
        return None
    if isinstance(data, list):
        return data[0] if data else None
    return data


class DecisionAttachmentPersistenceMixin:
    client: Client

    def get_decision_note(self, *, user_id: str, decision_id: str) -> DecisionNote | None:
        rows = (
            self.client.table("decision_notes")
            .select("*")
            .eq("user_id", user_id)
            .eq("id", decision_id)
            .limit(1)
            .execute()
        )
        row = _row_one(rows)
        return DecisionNote.model_validate(row) if row else None

    def get_decision_note_by_message(
        self, *, user_id: str, message_id: str
    ) -> DecisionNote | None:
        rows = (
            self.client.table("decision_notes")
            .select("*")
            .eq("user_id", user_id)
            .eq("source_message_id", message_id)
            .limit(1)
            .execute()
        )
        row = _row_one(rows)
        return DecisionNote.model_validate(row) if row else None

    def upsert_message_decision_note(
        self, *, user_id: str, decision: DecisionNote
    ) -> DecisionNote:
        """One current decision per owned message; a repeat write updates it."""
        if decision.source_message_id is None or decision.computation is None:
            raise ValueError("A message decision needs its message and computation.")
        existing = self.get_decision_note_by_message(
            user_id=user_id,
            message_id=decision.source_message_id,
        )
        if existing is None:
            payload = decision.model_dump(mode="json")
            payload["user_id"] = user_id
            try:
                created = self.client.table("decision_notes").insert(payload).execute()
                return DecisionNote.model_validate(_row_one(created))
            except Exception:
                # A concurrent first write wins the unique key; converge on it.
                existing = self.get_decision_note_by_message(
                    user_id=user_id,
                    message_id=decision.source_message_id,
                )
                if existing is None:
                    raise
        updated = (
            self.client.table("decision_notes")
            .update(
                {
                    "decision_state": decision.decision_state,
                    "note": decision.note,
                    "updated_at": utcnow().isoformat(),
                }
            )
            .eq("user_id", user_id)
            .eq("id", existing.id)
            .execute()
        )
        return DecisionNote.model_validate(_row_one(updated))

    def stamp_message_decision(
        self,
        *,
        user_id: str,
        message: Message,
        decision: DecisionNote,
    ) -> None:
        metadata = decision_message_metadata(message.metadata, decision=decision)
        self.client.table("messages").update({"metadata": metadata}).eq(
            "user_id", user_id
        ).eq("id", message.id).execute()
