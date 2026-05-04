from __future__ import annotations

from typing import Any

from argus.domain.engine_launch.adapter import run_launch_backtest
from argus.domain.engine_launch.models import LaunchBacktestRequest
from pydantic import ValidationError


class RealBacktestTool:
    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            request = LaunchBacktestRequest.model_validate(payload)
        except ValidationError as exc:
            return {
                "success": False,
                "payload": None,
                "error_type": "parameter_validation_error",
                "error_message": _first_validation_code(exc),
                "retryable": False,
                "capability_context": {},
            }

        result = run_launch_backtest(request)
        envelope = result.envelope.model_dump(mode="python")

        if result.envelope.execution_status == "succeeded":
            return {
                "success": True,
                "payload": {
                    "envelope": envelope,
                    "result_card": result.result_card,
                    "explanation_context": result.explanation_context,
                },
                "error_type": None,
                "error_message": None,
                "retryable": False,
                "capability_context": {
                    "execution_status": result.envelope.execution_status,
                },
            }

        error_type = result.envelope.failure_category or "tool_execution_error"
        return {
            "success": False,
            "payload": None,
            "error_type": error_type,
            "error_message": result.envelope.failure_reason,
            "retryable": error_type == "upstream_dependency_error",
            "capability_context": {
                "execution_status": result.envelope.execution_status,
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
