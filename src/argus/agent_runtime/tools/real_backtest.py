from __future__ import annotations

from typing import Any

from argus.domain.engine_launch.adapter import run_launch_backtest
from argus.domain.engine_launch.models import LaunchBacktestRequest
from argus.domain.engine_launch.results import (
    user_safe_failure_detail,
    user_safe_failure_message,
)
from pydantic import ValidationError


class RealBacktestTool:
    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            request = LaunchBacktestRequest.model_validate(payload)
        except ValidationError as exc:
            failure_reason = _first_validation_code(exc)
            return _validation_failure(failure_reason)

        if request.coverage_preflight is None:
            return _validation_failure("approved_data_window_unavailable")

        result = run_launch_backtest(request, language=request.language)
        envelope = result.envelope.model_dump(mode="python")

        if result.envelope.execution_status == "succeeded":
            return {
                "success": True,
                "payload": {
                    "envelope": envelope,
                    "result_card": result.result_card,
                    "explanation_context": result.explanation_context,
                },
                "execution_metadata": {"timings_ms": result.timings_ms},
                "error_type": None,
                "error_message": None,
                "retryable": False,
                "capability_context": {
                    "execution_status": result.envelope.execution_status,
                },
            }

        error_type = result.envelope.failure_category or "tool_execution_error"
        failure_reason = result.envelope.failure_reason
        return {
            "success": False,
            "payload": None,
            "execution_metadata": {"timings_ms": result.timings_ms},
            "error_type": error_type,
            "error_message": user_safe_failure_message(
                failure_reason=failure_reason,
                failure_category=error_type,
            ),
            "retryable": error_type == "upstream_dependency_error",
            "capability_context": {
                "execution_status": result.envelope.execution_status,
                "failure_detail": user_safe_failure_detail(
                    failure_reason=failure_reason,
                    failure_category=error_type,
                ),
                "resolved_strategy": envelope["resolved_strategy"],
                "resolved_parameters": envelope["resolved_parameters"],
            },
        }


def _first_validation_code(exc: ValidationError) -> str:
    errors = exc.errors()
    if not errors:
        return "invalid_launch_request"
    message = str(errors[0].get("msg") or "invalid_launch_request")
    prefix = "Value error, "
    if message.startswith(prefix):
        return message[len(prefix) :]
    return message


def _validation_failure(failure_reason: str) -> dict[str, Any]:
    return {
        "success": False,
        "payload": None,
        "error_type": "parameter_validation_error",
        "error_message": user_safe_failure_message(
            failure_reason=failure_reason,
            failure_category="parameter_validation_error",
        ),
        "retryable": False,
        "capability_context": {
            "failure_detail": user_safe_failure_detail(
                failure_reason=failure_reason,
                failure_category="parameter_validation_error",
            )
        },
    }
