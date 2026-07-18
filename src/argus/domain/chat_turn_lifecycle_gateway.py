"""#240 — Supabase-backed turn-lifecycle operations.

The compare-and-set itself lives in the database
(``transition_chat_turn_lifecycle``); this module owns the bounded selects and
orchestration around it, mirroring the memory twin's predicate, ordering, and
batch limits exactly. Real-database proof remains an external gate.
"""

from __future__ import annotations

from typing import Any

from argus.domain.chat_turn_lifecycle import PROJECTABLE_STATUSES


class ChatTurnLifecycleGatewayMixin:
    """Gateway surface for the durable turn lifecycle; composed into
    ``SupabaseGateway`` so the mega-file stays within its budget."""

    client: Any

    def create_chat_turn_lifecycle(self, **kwargs: Any) -> dict[str, Any]:
        return create_chat_turn_lifecycle(self.client, **kwargs)

    def transition_chat_turn_lifecycle(self, **kwargs: Any) -> dict[str, Any]:
        return transition_chat_turn_lifecycle(self.client, **kwargs)

    def find_active_chat_turn(self, **kwargs: Any) -> dict[str, Any] | None:
        return find_active_chat_turn(self.client, **kwargs)

    def reconcile_stale_chat_turns(self, **kwargs: Any) -> list[dict[str, Any]]:
        return reconcile_stale_chat_turns(self.client, **kwargs)

    def accept_chat_turn(self, **kwargs: Any) -> dict[str, Any]:
        return accept_chat_turn(self.client, **kwargs)

    def list_projectable_chat_turns(self, **kwargs: Any) -> list[dict[str, Any]]:
        return list_projectable_chat_turns(self.client, **kwargs)


def _rows(result: Any) -> list[dict[str, Any]]:
    data = getattr(result, "data", None)
    return [dict(row) for row in data] if isinstance(data, list) else []


def create_chat_turn_lifecycle(
    client: Any,
    *,
    turn_id: str,
    user_id: str,
    conversation_id: str,
    request_id: str,
) -> dict[str, Any]:
    """Acceptance row; idempotent per turn_id (re-acceptance is a no-op)."""

    payload = {
        "turn_id": turn_id,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "request_id": request_id,
        "status": "accepted",
    }
    result = (
        client.table("chat_turn_lifecycles")
        .upsert(payload, on_conflict="turn_id", ignore_duplicates=True)
        .execute()
    )
    rows = _rows(result)
    return rows[0] if rows else dict(payload)


def transition_chat_turn_lifecycle(
    client: Any,
    *,
    turn_id: str,
    to_status: str,
    assistant_message_id: str | None = None,
    reconciled_outcome: str | None = None,
    failure_code: str | None = None,
    retryable: bool | None = None,
) -> dict[str, Any]:
    result = client.rpc(
        "transition_chat_turn_lifecycle",
        {
            "p_turn_id": turn_id,
            "p_to_status": to_status,
            "p_assistant_message_id": assistant_message_id,
            "p_reconciled_outcome": reconciled_outcome,
            "p_failure_code": failure_code,
            "p_retryable": retryable,
        },
    ).execute()
    data = result.data if isinstance(result.data, dict) else None
    if data is None:
        rows = _rows(result)
        data = rows[0] if rows else {"outcome": "missing"}
    return data


def find_active_chat_turn(
    client: Any,
    *,
    conversation_id: str,
    request_id: str,
    user_id: str,
) -> dict[str, Any] | None:
    result = (
        client.table("chat_turn_lifecycles")
        .select("*")
        .eq("conversation_id", conversation_id)
        .eq("user_id", user_id)
        .eq("request_id", request_id)
        .in_("status", ["accepted", "running"])
        .limit(1)
        .execute()
    )
    rows = _rows(result)
    return rows[0] if rows else None


def reconcile_stale_chat_turns(
    client: Any,
    *,
    conversation_id: str,
    user_id: str,
) -> list[dict[str, Any]]:
    """One database-owned, owner-scoped reconciliation boundary: unowned
    conversations are rejected, and stale selection on the database clock,
    at-most-20 deterministic ordering, row locking, post-lock stale recheck,
    the complete owner/conversation/request/turn evidence predicate, and the
    terminal transition all live in ``reconcile_stale_chat_turns`` (see
    migration 20260718000003)."""

    result = client.rpc(
        "reconcile_stale_chat_turns",
        {"p_conversation_id": conversation_id, "p_user_id": user_id},
    ).execute()
    data = result.data
    if isinstance(data, dict):
        rows = data.get("reconciled")
        return [dict(row) for row in rows] if isinstance(rows, list) else []
    if isinstance(data, list):
        return [dict(row) for row in data]
    return []


def list_projectable_chat_turns(
    client: Any,
    *,
    conversation_id: str,
    user_id: str,
    message_ids: list[str],
) -> list[dict[str, Any]]:
    """Owner-scoped terminal lifecycle truth for the messages actually on the
    read: an abandoned row matches its owning user message (turn_id) and a
    reconciled row its linked assistant message. Scoping by message id keeps
    projection complete for any history depth instead of capping at the
    oldest rows."""

    if not message_ids:
        return []
    ids_csv = ",".join(message_ids)
    result = (
        client.table("chat_turn_lifecycles")
        .select("*")
        .eq("conversation_id", conversation_id)
        .eq("user_id", user_id)
        .in_("status", list(PROJECTABLE_STATUSES))
        .or_(f"turn_id.in.({ids_csv}),assistant_message_id.in.({ids_csv})")
        .order("turn_id", desc=False)
        .execute()
    )
    return _rows(result)


def accept_chat_turn(
    client: Any,
    *,
    user_id: str,
    conversation_id: str,
    role: str,
    content: str,
    metadata: dict[str, Any] | None,
    request_id: str,
) -> dict[str, Any]:
    """Acceptance boundary: the user message persists through the canonical
    serialized append (message identity, user_id, monotonic created_at,
    preview, conversation updated_at, replay) and its lifecycle row lands in
    the same database-owned transaction (see migration 20260718000003)."""

    from uuid import uuid4

    from argus.domain.store import utcnow
    from argus.domain.supabase_conversation_messages import message_preview

    result = client.rpc(
        "accept_chat_turn",
        {
            "p_user_id": user_id,
            "p_conversation_id": conversation_id,
            "p_message_id": str(uuid4()),
            "p_role": role,
            "p_content": content,
            "p_metadata": metadata or {},
            "p_created_at": utcnow().isoformat(),
            "p_preview": message_preview(content, role=role, metadata=metadata),
            "p_request_id": request_id,
        },
    ).execute()
    row = result.data if isinstance(result.data, dict) else None
    if row is None:
        rows = _rows(result)
        row = rows[0] if rows else None
    if not isinstance(row, dict):
        raise RuntimeError("Chat turn acceptance did not return the message row.")
    return row
