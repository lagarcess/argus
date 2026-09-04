from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AdmissionFailureReason:
    failure_code: str
    failure_detail: str
    retryable: bool = False


def admission_failure_reason(decision: str) -> AdmissionFailureReason:
    """One owner for the durable and public meaning of an admission refusal."""

    if decision == "conversion_required":
        return AdmissionFailureReason(
            failure_code="account_conversion_required",
            failure_detail="guest_simulation_allowance_exhausted",
        )
    if decision == "allowance_exhausted":
        return AdmissionFailureReason(
            failure_code="simulation_allowance_exhausted",
            failure_detail="simulation_allowance_exhausted",
        )
    if decision in ("per_user_capacity", "global_capacity"):
        return AdmissionFailureReason(
            failure_code="backtest_capacity_exceeded",
            failure_detail=decision,
            retryable=True,
        )
    if decision == "conflict":
        return AdmissionFailureReason(
            failure_code="idempotency_conflict",
            failure_detail="confirmation_identity_already_spent",
        )
    if decision == "confirmation_changed":
        return AdmissionFailureReason(
            failure_code="confirmation_changed",
            failure_detail="confirmation_changed_before_start",
        )
    return AdmissionFailureReason(
        failure_code="backtest_admission_unavailable",
        failure_detail="admission_decision_unavailable",
    )


def admission_rejection_envelope(decision: str) -> dict[str, Any]:
    """Return typed rejection truth for a run that was never admitted."""

    reason = admission_failure_reason(decision)
    if reason.failure_code == "account_conversion_required":
        error_type = "account_required"
    elif reason.failure_code == "simulation_allowance_exhausted":
        error_type = "rate_limited"
    elif reason.failure_code == "backtest_capacity_exceeded":
        error_type = "service_overloaded"
    else:
        error_type = "tool_execution_error"
    return {
        "success": False,
        "payload": None,
        "error_type": error_type,
        "error_message": None,
        "retryable": reason.retryable,
        "capability_context": {
            "execution_status": "rejected",
            "failure_code": reason.failure_code,
            "failure_detail": reason.failure_detail,
        },
    }


def public_backtest_job_payload(job: dict[str, Any]) -> dict[str, Any]:
    public_keys = (
        "id",
        "conversation_id",
        "request_message_id",
        "confirmation_message_id",
        # Additive: lets clients tell research jobs from backtest jobs; absent
        # on legacy rows, which clients treat as chat.run_backtest.
        "operation_scope",
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
