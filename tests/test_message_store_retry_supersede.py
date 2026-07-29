"""A completed retry retires the composition failure it replaced (issue
#249): the failed assistant message is marked superseded and its recovery
stops offering a retry, while the metadata stays for telemetry."""

from __future__ import annotations

from argus.api.message_store import reconcile_reload_message_metadata
from argus.api.schemas import Message


def _message(role: str, message_id: str, metadata: dict | None = None) -> Message:
    return Message(
        id=message_id,
        conversation_id="conv-1",
        role=role,
        content="body",
        created_at="2026-07-29T00:00:00Z",
        metadata=metadata or {},
    )


def test_retried_composition_failure_is_superseded() -> None:
    messages = [
        _message("user", "u1"),
        _message(
            "assistant",
            "a1",
            {
                "recovery": {
                    "code": "latest_result_followup_unavailable",
                    "retryable": True,
                }
            },
        ),
        _message(
            "user",
            "u2",
            {
                "chat_action": {
                    "type": "retry_last_turn",
                    "payload": {"message": "try again", "failed_assistant_id": "a1"},
                }
            },
        ),
        _message("assistant", "a2", {"agent_runtime_stage_outcome": "ready_to_respond"}),
    ]

    reconciled = reconcile_reload_message_metadata(messages)

    failed = next(item for item in reconciled if item.id == "a1")
    assert failed.metadata["agent_runtime_failure_superseded"] is True
    assert failed.metadata["recovery"]["retryable"] is False


def test_unretried_failure_keeps_its_retry() -> None:
    messages = [
        _message("user", "u1"),
        _message(
            "assistant",
            "a1",
            {
                "recovery": {
                    "code": "latest_result_followup_unavailable",
                    "retryable": True,
                }
            },
        ),
    ]

    reconciled = reconcile_reload_message_metadata(messages)

    failed = next(item for item in reconciled if item.id == "a1")
    assert "agent_runtime_failure_superseded" not in failed.metadata
    assert failed.metadata["recovery"]["retryable"] is True
