from __future__ import annotations

from typing import Any

from argus.api.schemas import ChatStreamRequest


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
