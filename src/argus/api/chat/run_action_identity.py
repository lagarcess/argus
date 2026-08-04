from __future__ import annotations

from fastapi import Request

from argus.api.chat.actions import confirmation_action_id
from argus.api.dependencies import problem
from argus.api.schemas import ChatStreamRequest
from argus.domain import backtest_admission


def validated_optional_idempotency_key(
    request: Request,
    raw: str | None,
) -> str | None:
    """Validate #229 grammar on the original, unnormalized header bytes."""

    state, key = backtest_admission.validate_idempotency_key(raw)
    if state == "invalid":
        raise problem(
            request,
            status_code=422,
            code="validation_error",
            title="Validation Error",
            detail=(
                "Idempotency-Key must be 1-128 visible ASCII characters "
                "with no whitespace."
            ),
        )
    return key


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
