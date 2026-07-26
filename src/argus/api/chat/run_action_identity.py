from __future__ import annotations

from fastapi import Request

from argus.api.chat.actions import confirmation_action_id
from argus.api.dependencies import problem
from argus.api.schemas import ChatStreamRequest


def require_run_action_identity(
    *,
    payload: ChatStreamRequest,
    request: Request,
    idempotency_key: str | None,
) -> None:
    if idempotency_key is None:
        raise problem(
            request,
            status_code=400,
            code="idempotency_key_required",
            title="Idempotency Key Required",
            detail="Run backtest actions require an Idempotency-Key header.",
        )
    confirmation_id = confirmation_action_id(payload)
    if confirmation_id is None:
        raise problem(
            request,
            status_code=422,
            code="validation_error",
            title="Validation Error",
            detail="Run backtest actions require a confirmation_id.",
        )
    if idempotency_key != confirmation_id:
        raise problem(
            request,
            status_code=409,
            code="idempotency_conflict",
            title="Idempotency Conflict",
            detail="Idempotency-Key must match the Run action confirmation_id.",
        )
