from __future__ import annotations

import hashlib
from typing import Any, Literal, cast
from uuid import uuid4

from loguru import logger

from argus.observability.envelope import (
    ArgusEventEnvelope,
    EventAction,
    EventCaptureResult,
    EventType,
    FeatureArea,
    build_event_envelope,
    capture_event,
)

ProductEventKind = Literal[
    "evidence_capture",
    "decision_capture",
    "recall_usage",
    "continuity_mismatch",
    "compare_started",
    "next_experiments_offered",
    "eval_readiness",
    "receipt_created",
    "receipt_revoked",
    "receipt_viewed",
    "receipt_try_argus",
    "receipt_followed_up",
    "receipt_signed_up",
    "account_registration_completed",
]

_PRODUCT_EVENT_MAP: dict[ProductEventKind, tuple[EventType, EventAction, FeatureArea]] = {
    "evidence_capture": ("storage", "completed", "evidence_capture"),
    "decision_capture": ("decision_saved", "completed", "decision_capture"),
    "recall_usage": ("tool_result", "completed", "recall"),
    "continuity_mismatch": ("recovery", "failed", "continuity"),
    "compare_started": ("compare_started", "started", "result_explanation"),
    "next_experiments_offered": ("system", "completed", "result_explanation"),
    "eval_readiness": ("eval_suite_run", "completed", "chat_interpretation"),
    # The receipt funnel. Viewer-side stages carry no actor and no source id, so
    # a public view can never be attributed back to the owner who shared it.
    "receipt_created": ("storage", "completed", "evidence_capture"),
    "receipt_revoked": ("storage", "redacted", "evidence_capture"),
    "receipt_viewed": ("system", "completed", "guest_acquisition"),
    "receipt_try_argus": ("system", "started", "guest_acquisition"),
    "receipt_followed_up": ("system", "completed", "guest_acquisition"),
    "receipt_signed_up": ("system", "completed", "guest_acquisition"),
    "account_registration_completed": ("storage", "completed", "guest_acquisition"),
}


def build_product_event(
    kind: ProductEventKind | str,
    *,
    user_id: str | None,
    conversation_id: str | None = None,
    turn_id: str | None = None,
    message_id: str | None = None,
    job_id: str | None = None,
    backtest_run_id: str | None = None,
    status: str | None = None,
    latency_ms: int | None = None,
    error_category: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> ArgusEventEnvelope:
    product_event_kind = cast(ProductEventKind, kind)
    event_type, event_action, feature_area = _PRODUCT_EVENT_MAP[product_event_kind]
    event_attributes = {**(attributes or {}), "product_event": product_event_kind}
    return build_event_envelope(
        event_type=event_type,
        event_action=event_action,
        feature_area=feature_area,
        actor_hash=actor_hash_for_user(user_id),
        conversation_id=conversation_id,
        turn_id=turn_id,
        message_id=message_id,
        job_id=job_id,
        backtest_run_id=backtest_run_id,
        status=status,
        latency_ms=latency_ms,
        error_category=error_category,
        attributes=event_attributes,
    )


def capture_product_event(
    kind: ProductEventKind | str,
    *,
    user_id: str | None,
    conversation_id: str | None = None,
    turn_id: str | None = None,
    message_id: str | None = None,
    job_id: str | None = None,
    backtest_run_id: str | None = None,
    status: str | None = None,
    latency_ms: int | None = None,
    error_category: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> EventCaptureResult:
    try:
        envelope = build_product_event(
            kind,
            user_id=user_id,
            conversation_id=conversation_id,
            turn_id=turn_id,
            message_id=message_id,
            job_id=job_id,
            backtest_run_id=backtest_run_id,
            status=status,
            latency_ms=latency_ms,
            error_category=error_category,
            attributes=attributes,
        )
    except KeyError:
        logger.warning(
            "Unknown product event kind",
            product_event=kind,
        )
        return EventCaptureResult(
            status="failed",
            reason="unknown_product_event_kind",
            event_id=str(uuid4()),
            destination=None,
        )
    return capture_event(envelope)


def actor_hash_for_user(user_id: str | None) -> str | None:
    if user_id is None or not str(user_id).strip():
        return None
    digest = hashlib.sha256(f"argus:actor:{user_id.strip()}".encode("utf-8")).hexdigest()
    return f"argus_actor_{digest[:32]}"
