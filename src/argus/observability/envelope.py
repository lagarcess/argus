from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

PrivacyMode = Literal["raw_alpha", "redacted_default", "metadata_only", "disabled"]
EventAction = Literal[
    "started",
    "completed",
    "failed",
    "suppressed",
    "redacted",
    "sampled",
    "reconciled",
]
EventType = Literal[
    "user_message",
    "ai_interpretation",
    "ai_response",
    "tool_call",
    "tool_result",
    "research",
    "stt",
    "storage",
    "system",
    "recovery",
    "decision_saved",
    "revisit_opened",
    "compare_started",
    "memory_candidate_proposed",
    "memory_candidate_suppressed",
    "cost_ledger_entry",
    "eval_case_run",
    "eval_suite_run",
    "broker_handoff_prep",
]
FeatureArea = Literal[
    "chat_interpretation",
    "continuity",
    "evidence_capture",
    "decision_capture",
    "recall",
    "result_explanation",
    "memory_candidate_proposal",
    "research_light",
    "research_deep",
    "freshness_check",
    "stt",
    "storage",
    "broker_handoff_prep",
]

EVENT_ACTIONS: tuple[str, ...] = (
    "started",
    "completed",
    "failed",
    "suppressed",
    "redacted",
    "sampled",
    "reconciled",
)
EVENT_TYPES: tuple[str, ...] = (
    "user_message",
    "ai_interpretation",
    "ai_response",
    "tool_call",
    "tool_result",
    "research",
    "stt",
    "storage",
    "system",
    "recovery",
    "decision_saved",
    "revisit_opened",
    "compare_started",
    "memory_candidate_proposed",
    "memory_candidate_suppressed",
    "cost_ledger_entry",
    "eval_case_run",
    "eval_suite_run",
    "broker_handoff_prep",
)
FEATURE_AREAS: tuple[str, ...] = (
    "chat_interpretation",
    "continuity",
    "evidence_capture",
    "decision_capture",
    "recall",
    "result_explanation",
    "memory_candidate_proposal",
    "research_light",
    "research_deep",
    "freshness_check",
    "stt",
    "storage",
    "broker_handoff_prep",
)

_BLOCKED_KEY_PARTS = (
    "account_balance",
    "api_key",
    "auth_token",
    "broker_credentials",
    "context_packets",
    "full_audio",
    "holdings",
    "message_history",
    "model_metadata",
    "password",
    "payment_identifier",
    "prompt",
    "provider_metadata",
    "raw_payload",
    "route_receipt",
    "secret",
    "token",
    "transcript",
)


class ArgusEventEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "argus_observability_event/v1"
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    environment: str = "local"
    privacy_mode: PrivacyMode = "metadata_only"
    event_type: EventType
    event_action: EventAction
    feature_area: FeatureArea
    actor_hash: str | None = None
    session_id: str | None = None
    conversation_id: str | None = None
    turn_id: str | None = None
    message_id: str | None = None
    job_id: str | None = None
    backtest_run_id: str | None = None
    route_receipt_id: str | None = None
    provider: str | None = None
    model: str | None = None
    provider_request_id: str | None = None
    upstream_id: str | None = None
    status: str | None = None
    latency_ms: int | None = None
    usage: dict[str, Any] | None = None
    cost: dict[str, Any] | None = None
    error_category: str | None = None
    sampling_rate: float | None = None
    retention_class: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class EventCaptureResult(BaseModel):
    status: Literal["suppressed"]
    reason: Literal["p1_measurement_only"]
    event_id: str


def build_event_envelope(
    *,
    event_type: EventType,
    event_action: EventAction,
    feature_area: FeatureArea,
    attributes: dict[str, Any] | None = None,
    **kwargs: Any,
) -> ArgusEventEnvelope:
    return ArgusEventEnvelope(
        event_type=event_type,
        event_action=event_action,
        feature_area=feature_area,
        attributes=sanitize_observability_attributes(attributes or {}),
        **kwargs,
    )


def live_analytics_sink_enabled() -> bool:
    return False


def capture_event(envelope: ArgusEventEnvelope) -> EventCaptureResult:
    return EventCaptureResult(
        status="suppressed",
        reason="p1_measurement_only",
        event_id=envelope.event_id,
    )


def sanitize_observability_attributes(value: dict[str, Any]) -> dict[str, Any]:
    sanitized = _sanitize_value(value)
    return sanitized if isinstance(sanitized, dict) else {}


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        safe: dict[str, Any] = {}
        for key, raw in value.items():
            if not isinstance(key, str) or _blocked_key(key):
                continue
            sanitized = _sanitize_value(raw)
            if sanitized is not None:
                safe[key] = sanitized
        return safe
    if isinstance(value, list):
        return [
            sanitized
            for item in value
            if (sanitized := _sanitize_value(item)) is not None
        ]
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        return stripped[:500]
    if isinstance(value, int | float | bool) or value is None:
        return value
    return str(value)[:500]


def _blocked_key(key: str) -> bool:
    normalized = key.strip().lower()
    return any(part in normalized for part in _BLOCKED_KEY_PARTS)
