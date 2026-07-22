"""Chat-side durable admission flow.

A capacity rejection triggers one bounded blocker-reconciliation pass and
exactly one admission retry. Rejections are typed outcomes; they never fall
through to free in-process execution.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from loguru import logger

from argus.domain.backtest_admission import CHAT_RUN_SCOPE, validate_idempotency_key

BACKPRESSURE_RECONCILE_SCAN_LIMIT = 16


@dataclass(frozen=True)
class ChatAdmissionResult:
    decision: str
    job: dict[str, Any] | None = None


def admit_durable_chat_job(
    *,
    gateway: Any,
    context: Any,
    identity_hash: str,
    payload_digest: str,
    launch_payload: dict[str, Any],
    reconcile_blockers: Callable[..., bool],
) -> ChatAdmissionResult:
    # #229 grammar, never normalized: the reservation key is the accepted
    # header bytes exactly.
    key_state, idempotency_key = validate_idempotency_key(context.idempotency_key)
    if key_state != "ok" or idempotency_key is None:
        logger.warning(
            "Chat run action reached admission without a valid idempotency key",
            user_id=context.user_id,
            conversation_id=context.conversation_id,
            key_state=key_state,
        )
        return ChatAdmissionResult(decision="missing_key")

    execution_metadata = {
        "shadow_mode": True,
        "source": "api_chat",
        "request_id": context.request_id,
        "payload_hash": payload_digest,
    }

    for attempt in (1, 2):
        outcome = gateway.admit_backtest_job(
            user_id=context.user_id,
            operation_scope=CHAT_RUN_SCOPE,
            idempotency_key=idempotency_key,
            identity_hash=identity_hash,
            payload_hash=payload_digest,
            launch_payload=launch_payload,
            initial_status="queued",
            conversation_id=context.conversation_id,
            request_message_id=context.request_message_id,
            confirmation_message_id=context.confirmation_message_id,
            execution_metadata=execution_metadata,
        )
        decision = str(outcome.get("decision") or "")
        if decision in ("admitted", "replay"):
            job = outcome.get("job")
            return ChatAdmissionResult(
                decision=decision,
                job=dict(job) if isinstance(job, dict) else None,
            )
        if decision in ("per_user_capacity", "global_capacity"):
            if attempt == 1 and reconcile_blockers(
                gateway=gateway,
                fallback_user_id=context.user_id,
                status="queued" if decision == "global_capacity" else "running",
                user_id=(context.user_id if decision == "per_user_capacity" else None),
                limit=BACKPRESSURE_RECONCILE_SCAN_LIMIT,
            ):
                continue
            logger.warning(
                "Chat backtest admission rejected on capacity",
                reason=decision,
                user_id=context.user_id,
                conversation_id=context.conversation_id,
            )
            return ChatAdmissionResult(decision=decision)
        if decision in ("conflict", "allowance_exhausted"):
            logger.warning(
                "Chat backtest admission rejected",
                reason=decision,
                user_id=context.user_id,
                conversation_id=context.conversation_id,
            )
            return ChatAdmissionResult(decision=decision)
        raise RuntimeError(f"Backtest admission returned unknown decision {decision!r}.")
    return ChatAdmissionResult(decision="per_user_capacity")
