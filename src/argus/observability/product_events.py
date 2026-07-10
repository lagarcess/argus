from __future__ import annotations

import hashlib
from typing import Any, Literal, cast

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
    "eval_readiness",
]

_PRODUCT_EVENT_MAP: dict[ProductEventKind, tuple[EventType, EventAction, FeatureArea]] = {
    "evidence_capture": ("storage", "completed", "evidence_capture"),
    "decision_capture": ("decision_saved", "completed", "decision_capture"),
    "recall_usage": ("tool_result", "completed", "recall"),
    "continuity_mismatch": ("recovery", "failed", "continuity"),
    "compare_started": ("compare_started", "started", "result_explanation"),
    "eval_readiness": ("eval_suite_run", "completed", "chat_interpretation"),
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
    return capture_event(
        build_product_event(
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
    )


def actor_hash_for_user(user_id: str | None) -> str | None:
    if user_id is None or not str(user_id).strip():
        return None
    digest = hashlib.sha256(f"argus:actor:{user_id.strip()}".encode("utf-8")).hexdigest()
    return f"argus_actor_{digest[:32]}"
