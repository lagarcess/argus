from __future__ import annotations

from typing import Any

from argus.api.schemas import ChatStreamRequest


def retry_last_turn_metadata(
    *,
    payload: ChatStreamRequest,
    request_message: str,
) -> dict[str, Any] | None:
    if payload.action is not None:
        return None
    message = request_message.strip()
    if not message:
        return None
    return {
        "retry_last_turn": {
            "message": message,
        },
    }
