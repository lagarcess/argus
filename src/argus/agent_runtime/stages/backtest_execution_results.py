from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from argus.agent_runtime.recovery_messages import recovery_message, recovery_state
from argus.agent_runtime.stages.interpret import StageResult
from argus.agent_runtime.state.models import ArtifactReference
from argus.domain.engine_launch.results import user_safe_failure_message


def async_backtest_job_message(
    job: dict[str, Any],
    *,
    language: str = "en",
) -> str:
    status = _as_optional_str(job.get("status")) or "queued"
    if status == "succeeded":
        return "The backtest finished. I am loading the result card now."
    if status in {"failed", "canceled", "expired"}:
        failure_code = _as_optional_str(job.get("failure_code"))
        if failure_code == "backtest_capacity_exceeded":
            return recovery_message(
                "backtest_capacity_exceeded",
                language=language,
                retryable=True,
            )
        return user_safe_failure_message(failure_reason=failure_code)
    return (
        "I started the backtest. You can leave this chat and come back; "
        "I will show the result here as soon as it is ready."
    )


def failed_async_job_result(
    *,
    job: dict[str, Any],
    payload: dict[str, Any],
    records: list[dict[str, Any]],
    language: str,
) -> StageResult:
    failure_code = _as_optional_str(job.get("failure_code"))
    retryable = bool(job.get("retryable"))
    assistant_prompt = async_backtest_job_message(job, language=language)
    failure_classification = (
        "upstream_dependency_error"
        if failure_code == "backtest_capacity_exceeded"
        else "tool_execution_error"
    )
    failed_action_retryable = retryable or failure_code == "idempotency_conflict"
    failed_action_patch = failed_action_reference_patch(
        payload=payload,
        failure_classification=failure_classification,
        error=assistant_prompt,
        retryable=failed_action_retryable,
    )
    failed_action_reference = failed_action_patch["latest_failed_action_reference"]
    job_reference = ArtifactReference(
        artifact_kind="backtest_job",
        artifact_id=str(job["id"]),
        artifact_status=str(job.get("status") or "failed"),
        metadata=job,
    ).model_dump(mode="python")
    final_response_payload: dict[str, Any] = {
        "error": assistant_prompt,
        "backtest_job": job,
    }
    if failure_code == "account_conversion_required":
        final_response_payload["code"] = failure_code
    stage_patch: dict[str, Any] = {
        "tool_call_records": records,
        "failure_classification": failure_classification,
        "assistant_prompt": assistant_prompt,
        "backtest_job": job,
        "final_response_payload": final_response_payload,
        "latest_failed_action_reference": failed_action_reference,
        "artifact_references": [job_reference, failed_action_reference],
    }
    if failure_code == "backtest_capacity_exceeded":
        stage_patch["recovery"] = recovery_state(
            "backtest_capacity_exceeded",
            language=language,
            retryable=True,
        )
    return StageResult(
        outcome=(
            "execution_failed_recoverably" if retryable else "execution_failed_terminally"
        ),
        stage_patch=stage_patch,
    )


def failed_action_reference_patch(
    *,
    payload: dict[str, Any],
    failure_classification: str | None,
    error: str | None,
    retryable: bool,
) -> dict[str, Any]:
    reference = ArtifactReference(
        artifact_kind="failed_action",
        artifact_id=_failed_action_id(payload=payload, error=error),
        artifact_status="failed",
        metadata={
            "action_type": "run_backtest",
            "launch_payload": deepcopy(payload),
            "failure_classification": failure_classification,
            "error": error,
            "user_safe_message": error,
            "retryable": retryable,
            "recovery_mode": "reopen_confirmation",
        },
    )
    return {
        "latest_failed_action_reference": reference.model_dump(mode="python"),
        "artifact_references": [reference.model_dump(mode="python")],
    }


def _failed_action_id(*, payload: dict[str, Any], error: str | None) -> str:
    stable_payload = {"payload": payload, "error": error}
    digest = hashlib.sha256(
        json.dumps(stable_payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:16]
    return f"failed-action-{digest}"


def _as_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
