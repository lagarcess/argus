"""Owner-scoped read-time projection of durable turn recovery state."""

from __future__ import annotations

from typing import Any

from argus.api.chat.onboarding import parse_onboarding_control_message
from argus.api.chat.retry import durable_retry_last_turn_metadata
from argus.api.message_store import (
    list_projectable_chat_turns,
    reconcile_stale_chat_turns,
)
from argus.api.schemas import Message

_AUTHORITATIVE_ARTIFACT_KEYS = {
    "backtest_job",
    "confirmation_card",
    "latest_run_id",
    "result_card",
}


def reconcile_and_project_chat_turns(
    *,
    user_id: str,
    conversation_id: str,
    messages: list[Message],
) -> list[Message]:
    reconcile_stale_chat_turns(
        user_id=user_id,
        conversation_id=conversation_id,
    )
    rows = list_projectable_chat_turns(
        user_id=user_id,
        conversation_id=conversation_id,
        message_ids=[message.id for message in messages],
    )
    return project_chat_turn_lifecycle_messages(
        messages=messages,
        lifecycle_rows=rows,
    )


def project_chat_turn_lifecycle_messages(
    *,
    messages: list[Message],
    lifecycle_rows: list[dict[str, Any]],
) -> list[Message]:
    hidden_protocol_turn_ids = {
        message.id
        for message in messages
        if message.role == "user"
        and parse_onboarding_control_message(message.content) is not None
    }
    by_assistant_message_id = {
        str(row["assistant_message_id"]): row
        for row in lifecycle_rows
        if row.get("assistant_message_id") is not None
    }
    assistantless_user_projection_by_turn_id = {
        str(row["turn_id"]): row
        for row in lifecycle_rows
        if row.get("turn_id") is not None
        and row.get("assistant_message_id") is None
        and row.get("status") in {"accepted", "running", "abandoned"}
    }
    projected: list[Message] = []
    for index, message in enumerate(messages):
        row = (
            assistantless_user_projection_by_turn_id.get(message.id)
            if message.role == "user"
            else by_assistant_message_id.get(message.id)
        )
        if row is None:
            projected.append(message)
            continue
        status = str(row.get("status") or "")
        reconciled_outcome = row.get("reconciled_outcome")
        terminal = status in {
            "completed",
            "recoverable_failed",
            "abandoned",
            "reconciled",
        }
        runtime_turn: dict[str, Any] = {
            "turn_id": str(row.get("turn_id") or ""),
            "request_id": str(row.get("request_id") or ""),
            "status": status,
            "terminal": terminal,
            "reconciled_outcome": reconciled_outcome,
            "failure_code": row.get("failure_code"),
            "retryable": bool(row.get("retryable", False)),
        }
        if status == "abandoned":
            runtime_turn.update(
                failure_code="turn_abandoned",
                retryable=True,
            )
        metadata = {
            **(message.metadata or {}),
            "agent_runtime_turn": runtime_turn,
        }
        if status == "abandoned":
            metadata["recovery"] = {
                "code": "turn_abandoned",
                "retryable": True,
            }
            if not _later_work_supersedes(messages, index=index):
                metadata.update(durable_retry_last_turn_metadata(message))
            else:
                metadata.pop("retry_last_turn", None)
        elif runtime_turn["retryable"] and "recovery" not in metadata:
            metadata["recovery"] = {
                "code": "runtime_failure",
                "retryable": True,
            }
        if (
            message.role != "user"
            and runtime_turn["turn_id"] in hidden_protocol_turn_ids
        ):
            metadata.pop("retry_last_turn", None)
        projected.append(message.model_copy(update={"metadata": metadata}))
    return projected


def _later_work_supersedes(messages: list[Message], *, index: int) -> bool:
    for later in messages[index + 1 :]:
        if later.role == "user":
            return True
        metadata = later.metadata
        if isinstance(metadata, dict) and any(
            metadata.get(key) for key in _AUTHORITATIVE_ARTIFACT_KEYS
        ):
            return True
    return False
