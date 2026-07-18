"""#240 — project terminal lifecycle truth into message reads.

Message reads project the current lifecycle row into
``metadata.agent_runtime_turn`` on a response copy; immutable messages are
never rewritten and no synthetic message is ever inserted. For ``abandoned``
no assistant message exists, so the accepted user message whose id equals
``turn_id`` owns the projection and additionally carries the ``recovery`` and
typed ``retry_last_turn`` overlays exactly as specified in
``docs/API_CONTRACT.md``. For ``reconciled`` the linked assistant message owns
the projection through the same canonical ``agent_runtime_turn`` object.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from argus.api.schemas import Message


def _with_abandoned_overlay(message: Message, row: dict[str, Any]) -> Message:
    turn_id = str(row.get("turn_id") or "")
    metadata = dict(message.metadata or {})
    metadata["agent_runtime_turn"] = {
        "turn_id": turn_id,
        "request_id": row.get("request_id"),
        "status": "abandoned",
        "terminal": True,
        "reconciled_outcome": None,
        "failure_code": row.get("failure_code"),
        "retryable": row.get("retryable"),
    }
    metadata["recovery"] = {
        "code": row.get("failure_code"),
        "retryable": row.get("retryable"),
    }
    retry_last_turn: dict[str, Any] = {
        "request_message_id": turn_id,
        "message": message.content,
    }
    chat_action = metadata.get("chat_action")
    if isinstance(chat_action, dict):
        retry_last_turn["action"] = deepcopy(chat_action)
    metadata["retry_last_turn"] = retry_last_turn
    return message.model_copy(update={"metadata": metadata})


def _with_reconciled_overlay(message: Message, row: dict[str, Any]) -> Message:
    metadata = dict(message.metadata or {})
    existing = metadata.get("agent_runtime_turn")
    turn: dict[str, Any] = dict(existing) if isinstance(existing, dict) else {}
    turn.update(
        {
            "turn_id": str(row.get("turn_id") or ""),
            "status": "reconciled",
            "terminal": True,
            "reconciled_outcome": row.get("reconciled_outcome"),
        }
    )
    if row.get("failure_code") is not None:
        turn["failure_code"] = row.get("failure_code")
    if row.get("retryable") is not None:
        turn["retryable"] = row.get("retryable")
    metadata["agent_runtime_turn"] = turn
    return message.model_copy(update={"metadata": metadata})


def project_turn_lifecycle(
    messages: list[Message],
    lifecycle_rows: list[dict[str, Any]],
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
        abandoned_row = abandoned.get(message.id)
        reconciled_row = reconciled_by_assistant.get(message.id)
        if abandoned_row is not None and message.role == "user":
            message = _with_abandoned_overlay(message, abandoned_row)
        elif reconciled_row is not None and message.role == "assistant":
            message = _with_reconciled_overlay(message, reconciled_row)
        projected.append(message)
    return projected
