"""#240 — project terminal lifecycle truth into message reads.

Abandoned turns have no durable assistant message; reads insert an ephemeral
typed-recovery item directly after the owning user message. Reconciled turns
project their status and outcome onto the linked assistant message's response
copy. Immutable messages are never mutated and nothing is persisted — every
projection is derived from the lifecycle rows on read, and insertion order
(not a timestamp re-sort) keeps recovery adjacent to its owning turn.
"""

from __future__ import annotations

from typing import Any

from argus.agent_runtime.recovery_messages import recovery_message
from argus.api.schemas import Message

PROJECTION_ID_PREFIX = "turn-recovery-"


def _projection_message(
    row: dict[str, Any],
    *,
    owning_message: Message,
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
    if owning_message.content.strip():
        metadata["retry_last_turn"] = {"message": owning_message.content.strip()}

    return Message(
        id=f"{PROJECTION_ID_PREFIX}{turn_id}",
        conversation_id=str(row.get("conversation_id") or ""),
        role="assistant",
        content=str(
            recovery_message("runtime_failure", language=language, retryable=True)
        ),
        # The owning message's timestamp (with the projection id as the
        # (created_at, id) tiebreak) keeps cursor ordering monotonic while the
        # recovery item stays directly after its turn.
        created_at=owning_message.created_at,
        metadata=metadata,
    )


def _with_reconciled_outcome(message: Message, row: dict[str, Any]) -> Message:
    metadata = dict(message.metadata or {})
    metadata["turn_lifecycle_reconciled"] = {
        "turn_id": str(row.get("turn_id") or ""),
        "status": "reconciled",
        "outcome": row.get("reconciled_outcome"),
    }
    return message.model_copy(update={"metadata": metadata})


def project_turn_lifecycle(
    messages: list[Message],
    lifecycle_rows: list[dict[str, Any]],
    *,
    language: str | None = None,
) -> list[Message]:
    if not lifecycle_rows:
        return messages

    abandoned: dict[str, dict[str, Any]] = {}
    reconciled_by_assistant: dict[str, dict[str, Any]] = {}
    for row in lifecycle_rows:
        status = str(row.get("status") or "")
        if status == "abandoned":
            abandoned[str(row.get("turn_id") or "")] = row
        elif status == "reconciled":
            assistant_id = str(row.get("assistant_message_id") or "")
            if assistant_id:
                reconciled_by_assistant[assistant_id] = row

    projected: list[Message] = []
    for message in messages:
        reconciled_row = reconciled_by_assistant.get(message.id)
        if reconciled_row is not None and message.role == "assistant":
            message = _with_reconciled_outcome(message, reconciled_row)
        projected.append(message)
        row = abandoned.get(message.id)
        if row is not None and message.role == "user":
            projected.append(
                _projection_message(row, owning_message=message, language=language)
            )
    return projected
