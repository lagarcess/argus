from __future__ import annotations

from typing import Any

from argus.observability.product_events import capture_product_event


def emit_runtime_measurement_events(
    *,
    user_id: str,
    conversation_id: str,
    runtime_result: dict[str, Any],
    metadata: dict[str, Any],
) -> None:
    failure_code = _continuity_failure_code(metadata)
    if failure_code is not None:
        capture_product_event(
            "continuity_mismatch",
            user_id=user_id,
            conversation_id=conversation_id,
            status=failure_code,
            attributes={
                "failure_code": failure_code,
                "stage_outcome": str(metadata.get("agent_runtime_stage_outcome") or ""),
            },
        )

    comparison_started = runtime_result.get("comparison_started")
    if not isinstance(comparison_started, dict):
        return
    source = _clean_event_string(comparison_started.get("source")) or "workflow_boundary"
    attributes: dict[str, Any] = {
        "source": source,
        "baseline_present": bool(
            _clean_event_string(comparison_started.get("baseline"))
        ),
    }
    candidate_count = _positive_int(comparison_started.get("candidate_count"))
    if candidate_count is not None:
        attributes["candidate_count"] = candidate_count
    capture_product_event(
        "compare_started",
        user_id=user_id,
        conversation_id=conversation_id,
        status="started",
        attributes=attributes,
    )


def _continuity_failure_code(metadata: dict[str, Any]) -> str | None:
    reference = metadata.get("active_confirmation_reference")
    if not isinstance(reference, dict):
        return None
    reference_metadata = reference.get("metadata")
    if not isinstance(reference_metadata, dict):
        return None
    validation = reference_metadata.get("validation")
    if not isinstance(validation, dict):
        return None
    failure_code = _clean_event_string(validation.get("failure_code"))
    if failure_code is None or not failure_code.endswith("_mismatch"):
        return None
    return failure_code


def _clean_event_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _positive_int(value: Any) -> int | None:
    try:
        number = int(str(value))
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None
