"""Complete and save a Breakdown independently of its requesting browser."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from loguru import logger

from argus.api import state as api_state
from argus.api.artifact_presentation import result_breakdown_metadata
from argus.api.chat import breakdown, research_jobs
from argus.api.chat.backtest_job_envelopes import public_backtest_job_payload
from argus.api.chat.backtest_jobs import payload_hash
from argus.api.chat.turn_lifecycle_hooks import ChatTurnLifecycleHooks
from argus.api.schemas import BacktestRun, Message
from argus.domain.backtest_message_projection import result_fact_bank


@dataclass(frozen=True)
class BreakdownDispatch:
    job: dict[str, Any] | None = None
    message: Message | None = None

    @property
    def text(self) -> str:
        return self.message.content if self.message else ""

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            **(self.message.metadata if self.message else {}),
            "artifact_presentation_kind": "breakdown",
        }


async def dispatch_result_breakdown(
    run: BacktestRun | None,
    *,
    language: str,
    lifecycle: ChatTurnLifecycleHooks,
    settle_usage: dict[str, Any] | None,
) -> BreakdownDispatch:
    gateway = api_state.supabase_gateway
    job = None
    acknowledgement = None
    if gateway is not None:
        identity = lifecycle.request_message.id
        replay = gateway.find_backtest_job_by_idempotency_key(
            user_id=lifecycle.user_id,
            operation_scope=research_jobs.RESEARCH_OPERATION_SCOPE,
            idempotency_key=identity,
        )
        if replay is not None:
            return BreakdownDispatch(job=public_backtest_job_payload(replay))
        launch = {
            "schema_version": "result_breakdown_job/v1",
            "run_id": run.id if run else None,
            "language": language,
        }
        # The durable reservation precedes paid work. A failed write cannot
        # leave a provider answer with no job to attach to.
        job = gateway.create_backtest_job(
            user_id=lifecycle.user_id,
            conversation_id=lifecycle.conversation_id,
            request_message_id=identity,
            operation_scope=research_jobs.RESEARCH_OPERATION_SCOPE,
            idempotency_key=identity,
            payload_hash=payload_hash(launch),
            launch_payload=launch,
            execution_metadata={"capability_class": "result_breakdown"},
        )
        try:
            acknowledgement = lifecycle.complete(
                content="",
                metadata={
                    "conversation_mode": "result_review",
                    "artifact_presentation_kind": "breakdown",
                    "chat_action": lifecycle.request_message.metadata.get("chat_action"),
                    "backtest_job": public_backtest_job_payload(job),
                    "backtest_job_id": job["id"],
                },
                settle_usage=settle_usage,
            )
        except Exception:
            research_jobs._fail_job(
                job_id=str(job["id"]),
                user_id=lifecycle.user_id,
                detail="job acknowledgement persistence failed",
            )
            raise
    task = research_jobs.retain_research_work(
        _complete_breakdown(
            run,
            language=language,
            lifecycle=lifecycle,
            settle_usage=settle_usage,
            job_id=str(job["id"]) if job else None,
        ),
        name=f"result-breakdown-{lifecycle.request_message.id}",
    )
    if job is not None:
        return BreakdownDispatch(
            job=public_backtest_job_payload(job), message=acknowledgement
        )
    # Memory development has no job endpoint. Its existing turn readback owns
    # reload; shield only the wait, while the retained task owns persistence.
    return BreakdownDispatch(message=await asyncio.shield(task))


async def _complete_breakdown(
    run: BacktestRun | None,
    *,
    language: str,
    lifecycle: ChatTurnLifecycleHooks,
    settle_usage: dict[str, Any] | None,
    job_id: str | None,
) -> Message | None:
    if job_id is not None:
        try:
            api_state.supabase_gateway.mark_backtest_job_running(
                job_id=job_id, user_id=lifecycle.user_id
            )
        except Exception:
            # The existing compare-and-set admits one worker. A replay or a
            # failed claim must never dispatch another paid request.
            logger.warning(
                "Breakdown job was not claimed; skipping provider", job_id=job_id
            )
            return None
    result = await asyncio.to_thread(
        breakdown.result_breakdown_action,
        run,
        language=language,
        user_id=lifecycle.user_id,
        conversation_id=lifecycle.conversation_id,
        request_id=lifecycle.request_id,
    )
    metadata = {
        "conversation_mode": "result_review",
        "agent_runtime_stage_outcome": "completed",
        "chat_action": lifecycle.request_message.metadata.get("chat_action"),
        **result_breakdown_metadata(result, run, language=language),
    }
    if run is not None:
        metadata.update(
            latest_run_id=run.id,
            result_run_id=run.id,
            result_strategy_id=run.strategy_id,
            result_fact_bank=result_fact_bank(run),
        )
    if job_id is not None:
        metadata["backtest_job_id"] = job_id
        return await research_jobs.persist_research_job_answer(
            job_id=job_id,
            user_id=lifecycle.user_id,
            conversation_id=lifecycle.conversation_id,
            content=result.text,
            metadata=metadata,
        )
    return lifecycle.complete(
        content=result.text, metadata=metadata, settle_usage=settle_usage
    )
