from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

from argus.api.schemas import BacktestRun, Message

_PUBLIC_BACKTEST_JOB_KEYS = (
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


def result_fact_bank(run: BacktestRun) -> dict[str, Any]:
    context_packets = (
        run.conversation_result_card.get("context_packets")
        if isinstance(run.conversation_result_card, dict)
        else None
    )
    return {
        "run_id": run.id,
        "conversation_id": run.conversation_id,
        "strategy_id": run.strategy_id,
        "asset_class": run.asset_class,
        "symbols": list(run.symbols),
        "benchmark_symbol": run.benchmark_symbol,
        "metrics": deepcopy(run.metrics),
        "config_snapshot": deepcopy(run.config_snapshot),
        "result_card": deepcopy(run.conversation_result_card),
        "context_packets": deepcopy(context_packets)
        if isinstance(context_packets, list)
        else [],
        "chart": deepcopy(run.chart),
        "trades": deepcopy(run.trades),
    }


def hydrate_completed_backtest_job_messages(
    messages: list[Message],
    *,
    load_job: Callable[[str], dict[str, Any] | None],
    load_run: Callable[[str], BacktestRun | None],
) -> list[Message]:
    """Project canonical completed runs over stale queued-job messages."""

    jobs: dict[str, dict[str, Any] | None] = {}
    runs: dict[str, BacktestRun | None] = {}
    projected: list[Message] = []
    for message in messages:
        metadata = message.metadata
        if message.role != "assistant" or not isinstance(metadata, dict):
            projected.append(message)
            continue
        job_id = _backtest_job_id(metadata)
        if job_id is None:
            projected.append(message)
            continue

        if job_id not in jobs:
            jobs[job_id] = load_job(job_id)
        job = jobs[job_id]
        if not _is_completed_job_for_message(job, message):
            projected.append(message)
            continue
        assert job is not None

        run_id = str(job.get("result_run_id") or "").strip()
        if run_id not in runs:
            runs[run_id] = load_run(run_id)
        run = runs[run_id]
        if not _is_completed_run_for_message(run, message, run_id=run_id):
            projected.append(message)
            continue
        assert run is not None

        next_metadata = dict(metadata)
        next_metadata.update(
            {
                "conversation_mode": "result_review",
                "agent_runtime_stage_outcome": "ready_to_respond",
                "backtest_job": _public_backtest_job(job),
                "backtest_job_id": job_id,
                "result_card": deepcopy(run.conversation_result_card),
                "latest_run_id": run.id,
                "result_run_id": run.id,
                "result_strategy_id": run.strategy_id,
                "result_conversation_id": run.conversation_id,
                "result_fact_bank": result_fact_bank(run),
            }
        )
        readout = _result_readout(job)
        projected.append(
            message.model_copy(
                update={
                    "content": readout or "",
                    "metadata": next_metadata,
                }
            )
        )
    return projected


def _backtest_job_id(metadata: dict[str, Any]) -> str | None:
    candidate = metadata.get("backtest_job_id")
    if not isinstance(candidate, str) or not candidate.strip():
        job = metadata.get("backtest_job")
        candidate = job.get("id") if isinstance(job, dict) else None
    if not isinstance(candidate, str):
        return None
    normalized = candidate.strip()
    return normalized or None


def _is_completed_job_for_message(
    job: dict[str, Any] | None,
    message: Message,
) -> bool:
    if not isinstance(job, dict) or job.get("status") != "succeeded":
        return False
    run_id = job.get("result_run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        return False
    conversation_id = job.get("conversation_id")
    return conversation_id in {None, message.conversation_id}


def _is_completed_run_for_message(
    run: BacktestRun | None,
    message: Message,
    *,
    run_id: str,
) -> bool:
    return bool(
        run is not None
        and run.id == run_id
        and run.status == "completed"
        and run.conversation_id == message.conversation_id
    )


def _public_backtest_job(job: dict[str, Any]) -> dict[str, Any]:
    return {key: job.get(key) for key in _PUBLIC_BACKTEST_JOB_KEYS if key in job}


def _result_readout(job: dict[str, Any]) -> str | None:
    execution_metadata = job.get("execution_metadata")
    if not isinstance(execution_metadata, dict):
        return None
    workflow_metadata = execution_metadata.get("workflow_backtest")
    if not isinstance(workflow_metadata, dict):
        return None
    readout = workflow_metadata.get("result_readout")
    if not isinstance(readout, str):
        return None
    normalized = readout.strip()
    return normalized or None
