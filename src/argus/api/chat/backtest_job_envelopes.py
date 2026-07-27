from __future__ import annotations

from typing import Any


def admission_rejection_envelope(decision: str) -> dict[str, Any]:
    """Return typed rejection truth for a run that was never admitted."""

    if decision == "conversion_required":
        error_type = "account_required"
        failure_code = "account_conversion_required"
    elif decision == "allowance_exhausted":
        error_type = "rate_limited"
        failure_code = "simulation_allowance_exhausted"
    elif decision in ("per_user_capacity", "global_capacity"):
        error_type = "service_overloaded"
        failure_code = "backtest_capacity_exceeded"
    elif decision == "conflict":
        error_type = "tool_execution_error"
        failure_code = "idempotency_conflict"
    else:
        error_type = "tool_execution_error"
        failure_code = "backtest_admission_unavailable"
    return {
        "success": False,
        "payload": None,
        "error_type": error_type,
        "error_message": None,
        "retryable": False,
        "capability_context": {
            "execution_status": "rejected",
            "failure_code": failure_code,
        },
    }


def public_backtest_job_payload(job: dict[str, Any]) -> dict[str, Any]:
    public_keys = (
        "id",
        "conversation_id",
        "request_message_id",
        "confirmation_message_id",
        "status",
        "result_run_id",
        "failure_code",
        "failure_detail",
        "retryable",
        "queued_at",
        "started_at",
        "finished_at",
        "created_at",
        "updated_at",
    )
    return {key: job.get(key) for key in public_keys if key in job}


def async_backtest_job_envelope(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "success": True,
        "payload": {"backtest_job": public_backtest_job_payload(job)},
        "error_type": None,
        "error_message": None,
        "retryable": False,
        "capability_context": {
            "execution_status": str(job.get("status") or "queued"),
        },
    }
