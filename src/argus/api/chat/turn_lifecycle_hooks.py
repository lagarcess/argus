"""#240 — chat-route hooks onto the durable turn lifecycle.

Thin dispatch between the in-process twin (memory mode) and the
database-owned compare-and-set operation (Supabase mode). Lifecycle
bookkeeping is recovery truth and must never take the chat turn down with it:
hook failures log and fall open while the durable message path continues.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from argus.api import state as api_state
from argus.domain import chat_turn_lifecycle as lifecycle


def _gateway() -> Any | None:
    return api_state.supabase_gateway


def accept_turn(
    *,
    turn_id: str,
    user_id: str,
    conversation_id: str,
    request_id: str,
) -> None:
    try:
        gateway = _gateway()
        if gateway is not None:
            create = getattr(gateway, "create_chat_turn_lifecycle", None)
            if create is not None:
                create(
                    turn_id=turn_id,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    request_id=request_id,
                )
            return
        lifecycle.create_accepted_memory(
            api_state.store,
            turn_id=turn_id,
            user_id=user_id,
            conversation_id=conversation_id,
            request_id=request_id,
        )
    except Exception as exc:
        logger.warning(
            "Chat turn lifecycle acceptance failed open",
            error=str(exc),
            turn_id=turn_id,
        )


def transition_turn(
    *,
    turn_id: str,
    to_status: str,
    assistant_message_id: str | None = None,
    failure_code: str | None = None,
    retryable: bool | None = None,
) -> None:
    try:
        gateway = _gateway()
        if gateway is not None:
            transition = getattr(gateway, "transition_chat_turn_lifecycle", None)
            if transition is not None:
                transition(
                    turn_id=turn_id,
                    to_status=to_status,
                    assistant_message_id=assistant_message_id,
                    failure_code=failure_code,
                    retryable=retryable,
                )
            return
        lifecycle.transition_memory(
            api_state.store,
            turn_id=turn_id,
            to_status=to_status,  # type: ignore[arg-type]
            assistant_message_id=assistant_message_id,
            failure_code=failure_code,
            retryable=retryable,
        )
    except Exception as exc:
        logger.warning(
            "Chat turn lifecycle transition failed open",
            error=str(exc),
            turn_id=turn_id,
            to_status=to_status,
        )


def reconcile_conversation_turns(*, conversation_id: str) -> None:
    """Bounded pre-read reconciliation: before the next chat POST for a
    conversation and before returning its messages."""

    try:
        gateway = _gateway()
        if gateway is not None:
            reconcile = getattr(gateway, "reconcile_stale_chat_turns", None)
            if reconcile is not None:
                reconcile(conversation_id=conversation_id)
            return
        lifecycle.reconcile_stale_turns_memory(
            api_state.store,
            conversation_id=conversation_id,
        )
    except Exception as exc:
        logger.warning(
            "Chat turn lifecycle reconciliation failed open",
            error=str(exc),
            conversation_id=conversation_id,
        )
