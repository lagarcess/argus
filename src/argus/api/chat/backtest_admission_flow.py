"""Chat-side durable admission flow.

A capacity rejection triggers one bounded blocker-reconciliation pass and
exactly one admission retry. Rejections are typed outcomes; they never fall
through to free in-process execution.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from argus.api.guest_observability import (
    emit_verified_guest_funnel_event,
    guest_session_allowance_present,
)
from argus.domain.backtest_admission import CHAT_RUN_SCOPE, validate_idempotency_key
from argus.domain.usage_limits import (
    GUEST_SIMULATION_VISITOR_LIMITS,
    SIMULATION_USAGE_RESOURCE,
)
from argus.domain.visitor_usage import (
    settle_visitor_usage,
    visitor_within_limits,
)

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
        "openrouter_traffic_class": context.account_kind,
    }

    visitor_key = getattr(context, "visitor_key", None)
    should_check_first_guest_simulation = False
    if visitor_key:
        # Replay resolves before allowance: a retry of an admitted run must
        # return its existing job, never a conversion wall.
        existing_reservation = gateway.get_backtest_job_reservation(
            user_id=context.user_id,
            operation_scope=CHAT_RUN_SCOPE,
            idempotency_key=idempotency_key,
        )
        if existing_reservation is None:
            now = datetime.now(timezone.utc)
            should_check_first_guest_simulation = guest_session_allowance_present(
                context.allowance_limits
            )
            if not visitor_within_limits(
                gateway.client,
                visitor_key=visitor_key,
                resource=SIMULATION_USAGE_RESOURCE,
                limits=list(GUEST_SIMULATION_VISITOR_LIMITS),
                now=now,
            ):
                emit_verified_guest_funnel_event(
                    "guest_limit_reached",
                    user_id=context.user_id,
                    conversation_id=context.conversation_id,
                    surface="backtest",
                    capability_category="simulation",
                    conversion_reason="simulation_limit",
                    terminal_outcome="limit_reached",
                )
                return ChatAdmissionResult(decision="conversion_required")

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
            allowance_limits=context.allowance_limits,
        )
        decision = str(outcome.get("decision") or "")
        if decision in ("admitted", "replay"):
            job = outcome.get("job")
            if decision == "admitted" and visitor_key:
                # Best-effort: the check above is the enforcement point.
                try:
                    settle_visitor_usage(
                        gateway.client,
                        visitor_key=visitor_key,
                        resource=SIMULATION_USAGE_RESOURCE,
                        limits=list(GUEST_SIMULATION_VISITOR_LIMITS),
                    )
                except Exception as exc:
                    logger.warning(
                        "Visitor simulation settlement failed",
                        error=str(exc),
                        failure_classification="telemetry_only",
                    )
            if (
                decision == "admitted"
                and should_check_first_guest_simulation
                and _guest_session_simulation_used_count(
                    gateway=gateway,
                    context=context,
                )
                == 1
            ):
                emit_verified_guest_funnel_event(
                    "first_simulation_admitted",
                    user_id=context.user_id,
                    conversation_id=context.conversation_id,
                    job_id=(
                        str(job.get("id"))
                        if isinstance(job, dict) and job.get("id")
                        else None
                    ),
                    surface="backtest",
                    capability_category="simulation",
                    terminal_outcome="admitted",
                )
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
        if decision in ("conflict", "allowance_exhausted", "conversion_required"):
            if decision == "conversion_required" and guest_session_allowance_present(
                context.allowance_limits
            ):
                emit_verified_guest_funnel_event(
                    "guest_limit_reached",
                    user_id=context.user_id,
                    conversation_id=context.conversation_id,
                    surface="backtest",
                    capability_category="simulation",
                    conversion_reason="simulation_limit",
                    terminal_outcome="limit_reached",
                )
            logger.warning(
                "Chat backtest admission rejected",
                reason=decision,
                user_id=context.user_id,
                conversation_id=context.conversation_id,
            )
            return ChatAdmissionResult(decision=decision)
        raise RuntimeError(f"Backtest admission returned unknown decision {decision!r}.")
    return ChatAdmissionResult(decision="per_user_capacity")


def _guest_session_simulation_used_count(*, gateway: Any, context: Any) -> int | None:
    """Read the durable workspace counter after the atomic admission charge."""
    window = next(
        (
            item
            for item in context.allowance_limits or []
            if str(item.get("period") or "") == "guest_session"
        ),
        None,
    )
    if not isinstance(window, dict):
        return None
    raw_period_start = window.get("period_start")
    try:
        if isinstance(raw_period_start, str):
            period_start = datetime.fromisoformat(
                raw_period_start.replace("Z", "+00:00")
            )
        elif isinstance(raw_period_start, datetime):
            period_start = raw_period_start
        else:
            return None
    except ValueError:
        logger.warning("Guest first-simulation period start was invalid")
        return None
    try:
        rows = gateway.list_current_usage_counters(
            user_id=context.user_id,
            resources=(SIMULATION_USAGE_RESOURCE,),
            period="guest_session",
            at=datetime.now(timezone.utc),
            period_start=period_start,
        )
    except Exception:
        logger.opt(exception=True).warning("Guest first-simulation counter read failed")
        return None
    row = next(
        (item for item in rows if str(item.get("resource")) == SIMULATION_USAGE_RESOURCE),
        None,
    )
    return int(row.get("used_count", 0)) if isinstance(row, dict) else 0
