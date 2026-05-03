from __future__ import annotations

from typing import Any


TERMINAL_FAILURE_TYPES = frozenset(
    {
        "missing_required_input",
        "unsupported_capability",
        "ambiguous_user_intent",
        "internal_system_error",
    }
)


def should_retry(
    *,
    error_type: str | None,
    retryable: bool,
    attempt: int,
    max_retries: int,
    capability_context: dict[str, Any] | None = None,
) -> bool:
    if error_type in TERMINAL_FAILURE_TYPES:
        return False
    if error_type == "parameter_validation_error":
        return (
            retryable
            and attempt < max(max_retries, 1)
            and _is_mechanical_intent_preserving_correction(capability_context)
            and _has_corrected_payload(capability_context)
        )
    if not retryable:
        return False
    return attempt < max(max_retries, 1)


def _is_mechanical_intent_preserving_correction(
    capability_context: dict[str, Any] | None,
) -> bool:
    if not capability_context:
        return False
    return bool(capability_context.get("mechanical_correction_available")) and bool(
        capability_context.get("intent_preserving")
    )


def _has_corrected_payload(capability_context: dict[str, Any] | None) -> bool:
    if not capability_context:
        return False
    corrected_payload = capability_context.get("corrected_payload")
    return isinstance(corrected_payload, dict) and bool(corrected_payload)
