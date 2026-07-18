"""#240 — project abandoned lifecycle truth into message reads.

Abandoned turns have no durable assistant message; reads project an ephemeral
typed-recovery item directly after the owning user message so the user sees
honest, retryable state. Immutable messages are never mutated and nothing is
persisted — the projection is derived from the lifecycle row on every read.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from argus.agent_runtime.recovery_messages import recovery_message
from argus.api.schemas import Message

PROJECTION_ID_PREFIX = "turn-recovery-"


def _finished_at(row: dict[str, Any]) -> datetime | None:
    raw = row.get("finished_at")
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    if isinstance(raw, str) and raw:
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def _projection_message(
    row: dict[str, Any],
    *,
    owning_message: Message | None,
    language: str | None,
) -> Message:
    turn_id = str(row.get("turn_id") or "")
    metadata: dict[str, Any] = {
        "conversation_mode": "recovery",
        "agent_runtime_stage_outcome": "agent_runtime_failure",
        "agent_runtime_turn": {
            "turn_id": turn_id,
            "request_id": row.get("request_id"),
            "terminal": True,
            "status": "abandoned",
        },
        "failure_code": "turn_abandoned",
        "retryable": True,
        "turn_lifecycle_projection": True,
    }
    if owning_message is not None and owning_message.content.strip():
        metadata["retry_last_turn"] = {"message": owning_message.content.strip()}

    created_at = _finished_at(row)
    if created_at is None and owning_message is not None:
        created_at = owning_message.created_at + timedelta(microseconds=1)
    if created_at is None:
        created_at = datetime.now(timezone.utc)

    return Message(
        id=f"{PROJECTION_ID_PREFIX}{turn_id}",
        conversation_id=str(row.get("conversation_id") or ""),
        role="assistant",
        content=str(
            recovery_message("runtime_failure", language=language, retryable=True)
        ),
        created_at=created_at,
        metadata=metadata,
    )


def project_abandoned_turn_recovery(
    messages: list[Message],
    abandoned_rows: list[dict[str, Any]],
    *,
    language: str | None = None,
) -> list[Message]:
    if not abandoned_rows:
        return messages

    by_turn = {str(row.get("turn_id") or ""): row for row in abandoned_rows}
    projected: list[Message] = []
    for message in messages:
        projected.append(message)
        row = by_turn.pop(message.id, None)
        if row is not None and message.role == "user":
            projected.append(
                _projection_message(row, owning_message=message, language=language)
            )
    # Rows whose owning user message is outside this page still surface,
    # ordered by their own finished_at timestamp.
    for row in by_turn.values():
        projected.append(_projection_message(row, owning_message=None, language=language))
    projected.sort(key=lambda item: (item.created_at, item.id))
    return projected
