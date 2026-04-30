from __future__ import annotations

from copy import deepcopy
from typing import Any

from argus.agent_runtime.recovery.policy import should_retry
from argus.agent_runtime.stages.interpret import StageResult
from argus.agent_runtime.state.models import ConfirmationPayload, RunState


def execute_stage(*, state: RunState, tool: Any, max_retries: int = 2) -> StageResult:
    payload = _confirmation_payload(state)
    records: list[dict[str, Any]] = []
    last_error_type: str | None = None

    for attempt in range(1, max(max_retries, 1) + 1):
        envelope = tool.run(payload)
        record = _build_tool_call_record(attempt=attempt, envelope=envelope)
        records.append(record)

        if envelope.get("success"):
            return StageResult(
                outcome="execution_succeeded",
                stage_patch={
                    "tool_call_records": records,
                    "failure_classification": None,
                    "final_response_payload": {"result": envelope.get("payload")},
                },
            )

        error_type = _as_optional_str(envelope.get("error_type"))
        failure_classification = _runtime_failure_classification(error_type)
        last_error_type = failure_classification
        retryable = bool(envelope.get("retryable"))
        capability_context = dict(envelope.get("capability_context") or {})
        if not should_retry(
            error_type=error_type,
            retryable=retryable,
            attempt=attempt,
            max_retries=max_retries,
            capability_context=capability_context,
        ):
            if failure_classification in {
                "missing_required_input",
                "unsupported_capability",
                "ambiguous_user_intent",
            }:
                return StageResult(
                    outcome="needs_clarification",
                    stage_patch={
                        "tool_call_records": records,
                        "failure_classification": failure_classification,
                        "assistant_prompt": _fallback_prompt(
                            error_type=failure_classification,
                            error_message=_as_optional_str(
                                envelope.get("error_message")
                            ),
                        ),
                        "missing_required_fields": _missing_required_fields(
                            capability_context
                        ),
                        "final_response_payload": {
                            "error": _as_optional_str(envelope.get("error_message")),
                        },
                    },
                )
            return StageResult(
                outcome="execution_failed_terminally",
                stage_patch={
                    "tool_call_records": records,
                    "failure_classification": failure_classification,
                    "assistant_prompt": _fallback_prompt(
                        error_type=failure_classification,
                        error_message=_as_optional_str(envelope.get("error_message")),
                    ),
                    "final_response_payload": {
                        "error": _as_optional_str(envelope.get("error_message")),
                    },
                },
            )
        if error_type == "parameter_validation_error":
            corrected_payload = _corrected_payload(capability_context)
            if corrected_payload is None or not _correction_preserves_user_intent(
                original_payload=payload,
                corrected_payload=corrected_payload,
            ):
                return StageResult(
                    outcome="execution_failed_terminally",
                    stage_patch={
                        "tool_call_records": records,
                        "failure_classification": failure_classification,
                    "assistant_prompt": _fallback_prompt(
                        error_type=failure_classification,
                        error_message=_as_optional_str(
                            envelope.get("error_message")
                        ),
                    ),
                        "final_response_payload": {
                            "error": _as_optional_str(envelope.get("error_message")),
                        },
                    },
                )
            payload = corrected_payload

    return StageResult(
        outcome="execution_failed_terminally",
        stage_patch={
            "tool_call_records": records,
            "failure_classification": last_error_type,
            "assistant_prompt": _fallback_prompt(
                error_type=last_error_type,
                error_message=_retry_exhausted_message(records),
            ),
            "final_response_payload": {"error": _retry_exhausted_message(records)},
        },
    )


def _confirmation_payload(state: RunState) -> dict[str, Any]:
    payload = state.confirmation_payload
    if payload is None:
        return {}
    if isinstance(payload, ConfirmationPayload):
        return payload.model_dump(mode="python")
    return dict(payload)


def _build_tool_call_record(
    *,
    attempt: int,
    envelope: dict[str, Any],
) -> dict[str, Any]:
    return {
        "tool_name": "backtest_stub",
        "attempt": attempt,
        "success": bool(envelope.get("success")),
        "error_type": _as_optional_str(envelope.get("error_type")),
        "error_message": _as_optional_str(envelope.get("error_message")),
        "retryable": bool(envelope.get("retryable")),
        "capability_context": dict(envelope.get("capability_context") or {}),
        "payload": envelope.get("payload"),
    }


def _as_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _missing_required_fields(capability_context: dict[str, Any]) -> list[str]:
    missing_fields = capability_context.get("missing_required_fields", [])
    if not isinstance(missing_fields, list):
        return []
    return [str(field_name) for field_name in missing_fields]


def _fallback_prompt(*, error_type: str | None, error_message: str | None) -> str | None:
    if error_type == "unsupported_capability":
        if error_message:
            return (
                f"{error_message} I can help you reframe this into a supported backtest "
                "or simplify it to a same-asset strategy Argus can run now."
            )
        return (
            "That request is outside the current backtest capability. "
            "I can help you reframe it into a supported same-asset strategy."
        )
    if error_type == "ambiguous_user_intent":
        if error_message:
            return (
                f"{error_message} Should I keep working on the current idea, "
                "or are you starting a new backtest?"
            )
        return (
            "I need one clarification before I run anything. "
            "Should I keep working on the current idea, or are you starting a new backtest?"
        )
    return error_message


def _corrected_payload(capability_context: dict[str, Any]) -> dict[str, Any] | None:
    corrected_payload = capability_context.get("corrected_payload")
    if not isinstance(corrected_payload, dict) or not corrected_payload:
        return None
    return deepcopy(corrected_payload)


def _correction_preserves_user_intent(
    *,
    original_payload: dict[str, Any],
    corrected_payload: dict[str, Any] | None,
) -> bool:
    if corrected_payload is None:
        return False
    original_strategy = _strategy_fields(original_payload)
    corrected_strategy = _strategy_fields(corrected_payload)
    protected_fields = (
        "strategy_thesis",
        "asset_universe",
        "entry_logic",
        "exit_logic",
        "date_range",
    )
    return all(
        _protected_field_matches(
            field_name=field_name,
            original_value=original_strategy.get(field_name),
            corrected_value=corrected_strategy.get(field_name),
        )
        for field_name in protected_fields
    )


def _strategy_fields(payload: dict[str, Any]) -> dict[str, Any]:
    strategy = payload.get("strategy", {})
    if not isinstance(strategy, dict):
        return {}
    return dict(strategy)


def _protected_field_matches(
    *,
    field_name: str,
    original_value: Any,
    corrected_value: Any,
) -> bool:
    if original_value is None:
        return True
    if field_name == "asset_universe":
        return _normalize_asset_universe(original_value) == _normalize_asset_universe(
            corrected_value
        )
    return _normalize_scalar_field(original_value) == _normalize_scalar_field(
        corrected_value
    )


def _normalize_asset_universe(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item).strip().upper() for item in value)


def _normalize_scalar_field(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    return value


def _runtime_failure_classification(error_type: str | None) -> str:
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


def _retry_exhausted_message(records: list[dict[str, Any]]) -> str:
    if not records:
        return "Retry limit reached"
    last_record = records[-1]
    error_message = _as_optional_str(last_record.get("error_message"))
    if error_message:
        return f"Retry limit reached after the last upstream failure: {error_message}"
    error_type = _as_optional_str(last_record.get("error_type"))
    if error_type:
        return f"Retry limit reached after the last upstream failure: {error_type}"
    return "Retry limit reached"
