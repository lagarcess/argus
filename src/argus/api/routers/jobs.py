"""Owner-scoped shared job status; no simulation execution routes."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fastapi import APIRouter, Depends, Request
from loguru import logger

from argus.api import state as api_state
from argus.api.chat.backtest_jobs import (
    fail_job_without_task_run,
    should_fail_stale_job_without_task_run,
)
from argus.api.chat.confirmation import public_confirmation_projection
from argus.api.chat.research_jobs import RESEARCH_OPERATION_SCOPE
from argus.api.dependencies import current_user, problem
from argus.api.message_store import owned_conversation_message
from argus.api.schemas import BacktestJob, BacktestJobResponse, Message, User

router = APIRouter(prefix="/api/v1", tags=["jobs"])
_TERMINAL_RESEARCH_STATUSES = frozenset({"succeeded", "failed", "canceled", "expired"})


@router.get("/backtest-jobs/{job_id}", response_model=BacktestJobResponse)
def get_backtest_job(
    job_id: str,
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
) -> BacktestJobResponse:
    gateway = api_state.supabase_gateway
    if gateway is None:
        raise problem(
            request,
            status_code=500,
            code="internal_error",
            title="Internal Error",
            detail="Supabase persistence is required for job status.",
        )
    job = gateway.get_backtest_job(user_id=user.id, job_id=job_id)
    if not job:
        raise problem(
            request,
            status_code=404,
            code="not_found",
            title="Not Found",
            detail="Job not found.",
        )
    if should_fail_stale_job_without_task_run(job):
        job = fail_job_without_task_run(gateway=gateway, user_id=user.id, job=job)
    return _job_response(gateway=gateway, user_id=user.id, job=job)


def _job_response(
    *, gateway: Any, user_id: str, job: dict[str, object]
) -> BacktestJobResponse:
    # Stored run rows stay readable through their existing owner-scoped job.
    run = None
    result_run_id = job.get("result_run_id")
    if (
        job.get("status") == "succeeded"
        and isinstance(result_run_id, str)
        and result_run_id
    ):
        run = gateway.get_backtest_run(user_id=user_id, run_id=result_run_id)
    readout = None
    readout_metadata: dict[str, Any] = {}
    if run is not None:
        from argus.domain.result_readout_content import stored_readout_metadata

        readout = _result_readout_from_job(job)
        readout_metadata.update(_result_readout_metadata_from_job(job))
        readout_metadata.update(stored_readout_metadata(run.conversation_result_card))
    return BacktestJobResponse(
        job=BacktestJob.model_validate(job),
        run=run,
        result_message=_research_result_message(user_id=user_id, job=job),
        result_readout=readout,
        **readout_metadata,
    )


def _result_readout_from_job(job: dict[str, object]) -> str | None:
    execution_metadata = job.get("execution_metadata")
    if not isinstance(execution_metadata, dict):
        return None
    workflow_metadata = execution_metadata.get("workflow_backtest")
    if not isinstance(workflow_metadata, dict):
        return None
    result_readout = workflow_metadata.get("result_readout")
    if not isinstance(result_readout, str):
        return None
    normalized = result_readout.strip()
    return normalized or None


def _result_readout_metadata_from_job(job: dict[str, object]) -> dict[str, Any]:
    execution_metadata = job.get("execution_metadata")
    if not isinstance(execution_metadata, dict):
        return {}
    workflow_metadata = execution_metadata.get("workflow_backtest")
    if not isinstance(workflow_metadata, dict):
        return {}
    metadata: dict[str, Any] = {}
    source = workflow_metadata.get("result_readout_source")
    if isinstance(source, str) and source.strip():
        metadata["result_readout_source"] = source.strip()
    fallback_used = workflow_metadata.get("result_readout_fallback_used")
    if isinstance(fallback_used, bool):
        metadata["result_readout_fallback_used"] = fallback_used
    failure_mode = workflow_metadata.get("result_readout_failure_mode")
    if isinstance(failure_mode, str) and failure_mode.strip():
        metadata["result_readout_failure_mode"] = failure_mode.strip()
    next_experiments = workflow_metadata.get("next_experiments")
    if isinstance(next_experiments, dict):
        metadata["next_experiments"] = next_experiments
    return metadata


def _research_result_message(
    *, user_id: str, job: Mapping[str, object]
) -> Message | None:
    if (
        job.get("operation_scope") != RESEARCH_OPERATION_SCOPE
        or job.get("status") not in _TERMINAL_RESEARCH_STATUSES
    ):
        return None
    conversation_id = job.get("conversation_id")
    metadata = job.get("execution_metadata")
    message_id = (
        metadata.get("research_result_message_id")
        if isinstance(metadata, Mapping)
        else None
    )
    if not isinstance(conversation_id, str) or not isinstance(message_id, str):
        return None
    try:
        message = owned_conversation_message(
            user_id=user_id, conversation_id=conversation_id, message_id=message_id
        )
    except Exception as exc:
        logger.warning(
            "Research result message read failed; job status served without it",
            job_id=job.get("id"),
            error=str(exc),
        )
        return None
    if message is None:
        return None
    return message.model_copy(
        update={"metadata": public_confirmation_projection(message.metadata)}
    )
