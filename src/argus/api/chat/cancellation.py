from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request
from fastapi.responses import StreamingResponse

from argus.api.chat.actions import (
    ConfirmationCancellationAdmission,
    confirmation_cancellation_admission,
)
from argus.api.chat.streaming import sse_data, sse_done
from argus.api.dependencies import problem
from argus.api.schemas import ChatStreamRequest, Message


def prepare_confirmation_cancellation(
    *,
    payload: ChatStreamRequest,
    request: Request,
    recent_messages: list[Message],
    headers: dict[str, str],
) -> tuple[ConfirmationCancellationAdmission, StreamingResponse | None]:
    admission = confirmation_cancellation_admission(
        payload=payload,
        recent_messages=recent_messages,
    )
    if admission is None:
        raise problem(
            request,
            status_code=409,
            code="confirmation_required",
            title="Confirmation Required",
            detail=(
                "That confirmation is no longer active. Describe the idea again "
                "and I will prepare a fresh confirmation."
            ),
        )
    if admission.replay_message is None:
        return admission, None

    replay_message_id = admission.replay_message.id
    confirmation_id = admission.confirmation_id

    async def replay_events() -> AsyncIterator[str]:
        yield sse_data(
            {
                "type": "final",
                "payload": {
                    "stage_outcome": "ready_to_respond",
                    "assistant_response": "",
                    "message_id": replay_message_id,
                    "confirmation_cancelled": {
                        "confirmation_id": confirmation_id,
                    },
                },
            }
        )
        yield sse_done()

    return admission, StreamingResponse(
        replay_events(),
        media_type="text/event-stream",
        headers=headers,
    )
