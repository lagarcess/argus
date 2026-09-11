from __future__ import annotations

from typing import Any

from argus.api.schemas import ChatStreamRequest, Message


def discovery_recovery_code(recovery: Any) -> str | None:
    """Only retryable discovery refusals use recoverable turn settlement."""
    if not isinstance(recovery, dict) or recovery.get("retryable") is not True:
        return None
    code = recovery.get("code")
    return (
        code
        if code in {"discovery_search_failed", "discovery_suggestions_unavailable"}
        else None
    )


def durable_retry_last_turn_metadata(
    request_message: Message,
    *,
    include_structured_action: bool = True,
) -> dict[str, Any]:
    retry_payload: dict[str, Any] = {
        "request_message_id": request_message.id,
        "message": request_message.content,
    }
    action = (
        request_message.metadata.get("chat_action")
        if isinstance(request_message.metadata, dict)
        else None
    )
    if include_structured_action and isinstance(action, dict):
        retry_payload["action"] = action
    return {"retry_last_turn": retry_payload}


def retryable_finalization_execution_identity(
    metadata: dict[str, Any] | None,
    *,
    request_message: str,
) -> str | None:
    if not isinstance(metadata, dict) or metadata.get("failure_code") != (
        "finalization_failed"
    ):
        return None
    retry_last_turn = metadata.get("retry_last_turn")
    if not isinstance(retry_last_turn, dict):
        return None
    failed_message = str(retry_last_turn.get("message") or "").strip()
    if not failed_message or failed_message != request_message.strip():
        return None
    finalization = metadata.get("backtest_finalization")
    if not isinstance(finalization, dict):
        return None
    execution_identity = str(finalization.get("execution_identity") or "").strip()
    return execution_identity or None


def backtest_finalization_execution_identity(
    *,
    backtest_job: dict[str, Any] | None,
    retry_execution_identity: str | None,
    idempotency_key: str | None,
    request_id: str,
) -> str:
    durable_job_id = (
        str(backtest_job.get("id") or "").strip()
        if isinstance(backtest_job, dict)
        else ""
    )
    if durable_job_id:
        return f"backtest_job:{durable_job_id}"
    return retry_execution_identity or (
        f"/api/v1/chat/stream:{idempotency_key or request_id}"
    )


def retry_last_turn_metadata(
    *,
    payload: ChatStreamRequest,
    request_message: str,
    include_structured_action: bool = False,
) -> dict[str, Any] | None:
    if payload.action is not None and not include_structured_action:
        return None
    message = request_message.strip()
    if not message:
        return None
    retry_payload: dict[str, Any] = {"message": message}
    if payload.action is not None:
        retry_payload["action"] = payload.action.model_dump(mode="python")
    return {
        "retry_last_turn": retry_payload,
    }


def live_retry_payload(message: Message) -> dict[str, Any] | None:
    """Stream the message-shaped retry; history keeps the durable anchor."""
    retry = (
        message.metadata.get("retry_last_turn")
        if isinstance(message.metadata, dict)
        else None
    )
    if not isinstance(retry, dict):
        return None
    return {key: retry[key] for key in ("message", "action") if key in retry}
