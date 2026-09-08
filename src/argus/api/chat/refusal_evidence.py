"""Observe emitted chat outcomes without deciding whether they were justified."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import Request
from loguru import logger

from argus.api import state as api_state
from argus.api.schemas import ChatStreamRequest, Message
from argus.observability.refusal_log import (
    RefusalObservation,
    persist_refusal_observation,
)


def bind_refusal_request(
    request: Request, *, payload: ChatStreamRequest, user_id: str
) -> None:
    # This runs only after FastAPI has authenticated and validated the request.
    # It precedes admission, so stale/missing/unowned actions are still observable.
    request.state.refusal_request = (user_id, payload.model_copy(deep=True))


def record_terminal_pair(
    *,
    user_id: str,
    conversation_id: str,
    request_id: str,
    request_message: Message,
    response_message: Message,
) -> None:
    try:
        persist_refusal_observation(
            gateway=api_state.supabase_gateway,
            observation=RefusalObservation(
                user_id=user_id,
                conversation_id=conversation_id,
                request_id=request_id,
                request_message_id=request_message.id,
                response_message_id=response_message.id,
            ),
        )
    except Exception:
        # The evidence store cannot replace a successful terminal with recovery.
        logger.warning("Refusal observation failed for a terminal message pair")


async def record_http_rejection(
    request: Request, *, body: dict[str, Any], status_code: int
) -> None:
    bound = getattr(request.state, "refusal_request", None)
    if bound is None:
        return
    user_id, payload = bound
    if payload.action is None:
        return
    try:
        observation = RefusalObservation(
            user_id=user_id,
            conversation_id=payload.conversation_id,
            request_id=request.state.request_id,
            asked=payload.message if payload.message is not None else "",
            action=payload.action.model_dump(mode="json", by_alias=True),
            outcome=body,
            status_code=status_code,
        )
        # Await the write attempt. An untracked after-response task could lose
        # the only record of a rejection, since no transcript row exists.
        await asyncio.to_thread(
            persist_refusal_observation,
            gateway=api_state.supabase_gateway,
            observation=observation,
        )
    except Exception:
        logger.warning("Refusal observation failed for an HTTP rejection")
