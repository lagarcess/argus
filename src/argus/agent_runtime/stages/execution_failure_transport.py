from __future__ import annotations

from typing import Any


def public_failure_code(capability_context: dict[str, Any]) -> str | None:
    """Expose only the client-negotiated guest conversion signal."""
    code = capability_context.get("failure_code")
    return (
        "account_conversion_required" if code == "account_conversion_required" else None
    )


def failed_final_response_payload(
    assistant_prompt: str, public_code: str | None
) -> dict[str, str]:
    payload = {"error": assistant_prompt}
    if public_code is not None:
        payload["code"] = public_code
    return payload


def runtime_failure_classification(error_type: str | None) -> str:
    known_taxonomy = {
        "parameter_validation_error",
        "missing_required_input",
        "unsupported_capability",
        "tool_execution_error",
        "upstream_dependency_error",
        "ambiguous_user_intent",
        "internal_system_error",
    }
    if error_type in known_taxonomy:
        return str(error_type)
    if error_type in {"service_overloaded", "rate_limited", "timeout"}:
        return "upstream_dependency_error"
    return "tool_execution_error"
