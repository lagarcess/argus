from __future__ import annotations

from typing import Any

from argus.api.schemas import ChatStreamRequest


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
