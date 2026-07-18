"""#240 — Supabase-backed turn-lifecycle operations.

The compare-and-set itself lives in the database
(``transition_chat_turn_lifecycle``); this module owns the bounded selects and
orchestration around it, mirroring the memory twin's predicate, ordering, and
batch limits exactly. Real-database proof remains an external gate.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from argus.domain.chat_turn_lifecycle import (
    STALE_TURN_BATCH,
    STALE_TURN_MINUTES,
    terminal_turn_evidence,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


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
) -> dict[str, Any] | None:
    result = (
        client.table("chat_turn_lifecycles")
        .select("*")
        .eq("conversation_id", conversation_id)
        .eq("request_id", request_id)
        .in_("status", ["accepted", "running"])
        .limit(1)
        .execute()
    )
    rows = _rows(result)
    return rows[0] if rows else None


class _MessageRow:
    """Adapter so the shared evidence predicate reads PostgREST rows."""

    def __init__(self, row: dict[str, Any]) -> None:
        self.id = str(row.get("id") or "")
        self.conversation_id = row.get("conversation_id")
        self.role = row.get("role")
        self.created_at = str(row.get("created_at") or "")
        self.metadata = row.get("metadata")


def reconcile_stale_chat_turns(
    client: Any,
    *,
    conversation_id: str,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Bounded reconciliation through the database CAS: at most 20 stale rows
    in deterministic order; durable terminal evidence wins with failure
    precedence on equal timestamps; no proof transitions to abandoned."""

    moment = now or _utcnow()
    cutoff = (moment - timedelta(minutes=STALE_TURN_MINUTES)).isoformat()

    candidates = _rows(
        client.table("chat_turn_lifecycles")
        .select("*")
        .eq("conversation_id", conversation_id)
        .in_("status", ["accepted", "running"])
        .execute()
    )
    stale = []
    for row in candidates:
        stale_since = str(row.get("running_at") or row.get("accepted_at") or "")
        if stale_since and stale_since <= cutoff:
            stale.append((stale_since, str(row.get("turn_id") or ""), row))
    stale.sort(key=lambda item: (item[0], item[1]))
    stale = stale[:STALE_TURN_BATCH]

    reconciled: list[dict[str, Any]] = []
    for _, turn_id, row in stale:
        evidence_rows = _rows(
            client.table("messages")
            .select("id,conversation_id,role,created_at,metadata")
            .eq("conversation_id", conversation_id)
            .eq("role", "assistant")
            .eq("metadata->agent_runtime_turn->>turn_id", turn_id)
            .execute()
        )
        ranked = []
        for message_row in evidence_rows:
            message = _MessageRow(message_row)
            outcome = terminal_turn_evidence(message, row=row)
            if outcome is None:
                continue
            precedence = 0 if outcome == "recoverable_failed" else 1
            ranked.append((message.created_at, precedence, message.id, outcome))
        ranked.sort(key=lambda item: (item[0], item[1], item[2]))

        if ranked:
            _, _, winner_id, outcome = ranked[0]
            result = transition_chat_turn_lifecycle(
                client,
                turn_id=turn_id,
                to_status="reconciled",
                assistant_message_id=winner_id,
                reconciled_outcome=outcome,
            )
        else:
            result = transition_chat_turn_lifecycle(
                client,
                turn_id=turn_id,
                to_status="abandoned",
                failure_code="turn_abandoned",
                retryable=True,
            )
        row_result = result.get("row")
        if isinstance(row_result, dict):
            reconciled.append(row_result)
    return reconciled
