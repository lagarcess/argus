"""Chat-side #230 admission flow, kept out of the backtest_jobs mega-file.

Routes durable chat job creation through the one database-owned admission
decision (replay/collision, allowance, per-user then global capacity, insert
plus charge). On a capacity rejection it runs one bounded blocker
reconciliation pass, then retries admission exactly once.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from loguru import logger

from argus.domain.backtest_admission import CHAT_RUN_SCOPE

BACKPRESSURE_RECONCILE_SCAN_LIMIT = 16


class BacktestAdmissionConflictError(RuntimeError):
    """Idempotency-Key reuse with a different canonical identity (#229/#230)."""


def admit_durable_chat_job(
    *,
    gateway: Any,
    context: Any,
    identity_hash: str,
    payload_digest: str,
    launch_payload: dict[str, Any],
    reconcile_blockers: Callable[..., bool],
    artifact_launch_hash: str | None = None,
) -> dict[str, Any] | None:
    from argus.domain.backtest_admission import is_full_sha256_hash

    idempotency_key = (context.idempotency_key or "").strip()
    if not idempotency_key:
        logger.warning(
            "Chat run action reached admission without an idempotency key",
            user_id=context.user_id,
            conversation_id=context.conversation_id,
        )
        return None
    if not is_full_sha256_hash(artifact_launch_hash):
        # A reservation without the artifact's full-width launch hash could
        # never be reproduced by the by-action lookup; skip durable admission
        # rather than create an unreconcilable reservation.
        logger.warning(
            "Chat run action lacks a reproducible artifact launch hash",
            user_id=context.user_id,
            conversation_id=context.conversation_id,
        )
        return None

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
            return dict(job) if isinstance(job, dict) else None
        if decision == "conflict":
            raise BacktestAdmissionConflictError(
                "Idempotency-Key is reserved for a different run identity."
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
            return None
        if decision == "allowance_exhausted":
            logger.warning(
                "Chat backtest admission rejected on allowance",
                user_id=context.user_id,
                conversation_id=context.conversation_id,
            )
            return None
        raise RuntimeError(f"Backtest admission returned unknown decision {decision!r}.")
    return None
