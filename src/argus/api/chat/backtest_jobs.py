from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx
from loguru import logger

TRUE_VALUES = {"1", "true", "yes", "on"}
SHADOW_JOB_SCHEMA_VERSION = "backtest_job_launch/v1"
DEFAULT_WORKFLOW_TASK = "argus-backtests/workflow_proof"
RENDER_TASK_RUNS_URL = "https://api.render.com/v1/task-runs"
DEFAULT_USER_RUNNING_LIMIT = 1
DEFAULT_USER_QUEUED_LIMIT = 2
DEFAULT_GLOBAL_RUNNING_LIMIT = 5
DEFAULT_GLOBAL_QUEUED_LIMIT = 10


@dataclass
class BacktestJobShadowContext:
    user_id: str
    conversation_id: str
    request_message_id: str | None = None
    confirmation_message_id: str | None = None
    idempotency_key: str | None = None
    request_id: str | None = None
    chat_action: dict[str, Any] | None = None
    created_job_id: str | None = None
    workflow_dispatch_started: bool = False
    workflow_task_run_id: str | None = None
    workflow_dispatch_error: str | None = None


@dataclass(frozen=True)
class BacktestJobBackpressureLimits:
    user_running: int
    user_queued: int
    global_running: int
    global_queued: int


_shadow_context: ContextVar[BacktestJobShadowContext | None] = ContextVar(
    "argus_backtest_job_shadow_context",
    default=None,
)


def backtest_jobs_shadow_enabled() -> bool:
    return (
        os.getenv("ARGUS_BACKTEST_JOBS_SHADOW_ENABLED", "").strip().lower() in TRUE_VALUES
    )


def backtest_jobs_dispatch_enabled() -> bool:
    return (
        os.getenv("ARGUS_BACKTEST_JOBS_DISPATCH_ENABLED", "").strip().lower()
        in TRUE_VALUES
    )


@contextmanager
def backtest_job_shadow_context(
    context: BacktestJobShadowContext | None,
) -> Iterator[None]:
    token = _shadow_context.set(context)
    try:
        yield
    finally:
        _shadow_context.reset(token)


def current_backtest_job_shadow_context() -> BacktestJobShadowContext | None:
    return _shadow_context.get()


def set_backtest_job_shadow_context(
    context: BacktestJobShadowContext | None,
) -> Token[BacktestJobShadowContext | None]:
    return _shadow_context.set(context)


def reset_backtest_job_shadow_context(
    token: Token[BacktestJobShadowContext | None],
) -> None:
    _shadow_context.reset(token)


def payload_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def shadow_launch_payload(
    *,
    payload: dict[str, Any],
    context: BacktestJobShadowContext,
) -> dict[str, Any]:
    launch_payload: dict[str, Any] = {
        "kind": "render_workflow_proof",
        "schema_version": SHADOW_JOB_SCHEMA_VERSION,
        "source": "chat_runtime",
        "request": _json_safe_payload(payload),
    }
    if context.chat_action is not None:
        launch_payload["chat_action"] = _json_safe_payload(context.chat_action)
    return launch_payload


def _json_safe_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(deepcopy(payload), sort_keys=True, default=str))


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _workflow_task_id() -> str:
    return (
        os.getenv("ARGUS_BACKTEST_WORKFLOW_TASK")
        or os.getenv("ARGUS_RENDER_WORKFLOW_PROOF_TASK")
        or DEFAULT_WORKFLOW_TASK
    ).strip()


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        logger.warning("Invalid integer environment value; using default", key=name)
        return default


def backtest_job_backpressure_limits() -> BacktestJobBackpressureLimits:
    return BacktestJobBackpressureLimits(
        user_running=_int_env(
            "ARGUS_BACKTEST_JOBS_USER_RUNNING_LIMIT",
            DEFAULT_USER_RUNNING_LIMIT,
        ),
        user_queued=_int_env(
            "ARGUS_BACKTEST_JOBS_USER_QUEUED_LIMIT",
            DEFAULT_USER_QUEUED_LIMIT,
        ),
        global_running=_int_env(
            "ARGUS_BACKTEST_JOBS_GLOBAL_RUNNING_LIMIT",
            DEFAULT_GLOBAL_RUNNING_LIMIT,
        ),
        global_queued=_int_env(
            "ARGUS_BACKTEST_JOBS_GLOBAL_QUEUED_LIMIT",
            DEFAULT_GLOBAL_QUEUED_LIMIT,
        ),
    )


def _backpressure_reason(
    *,
    gateway: Any,
    user_id: str,
    limits: BacktestJobBackpressureLimits,
) -> str | None:
    count_jobs = getattr(gateway, "count_backtest_jobs", None)
    if count_jobs is None:
        return None

    checks = (
        ("user_running", "running", user_id, limits.user_running),
        ("user_queued", "queued", user_id, limits.user_queued),
        ("global_running", "running", None, limits.global_running),
        ("global_queued", "queued", None, limits.global_queued),
    )
    for reason, status, scoped_user_id, limit in checks:
        if limit <= 0:
            return reason
        count = count_jobs(status=status, user_id=scoped_user_id, limit=limit + 1)
        if count >= limit:
            return reason
    return None


class RenderWorkflowDispatcher:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        task_id: str | None = None,
        endpoint: str = RENDER_TASK_RUNS_URL,
    ) -> None:
        self.api_key = (api_key or os.getenv("RENDER_API_KEY") or "").strip()
        self.task_id = (task_id or _workflow_task_id()).strip()
        self.endpoint = endpoint

    def dispatch(self, *, job_id: str, nonce: str) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("RENDER_API_KEY is required to dispatch backtest jobs.")
        if "/" not in self.task_id:
            raise RuntimeError(
                "ARGUS_BACKTEST_WORKFLOW_TASK must use {workflow-slug}/{task-name}."
            )

        response = httpx.post(
            self.endpoint,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={"task": self.task_id, "input": [job_id, nonce]},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        return dict(data) if isinstance(data, dict) else {"response": data}


class ShadowBacktestJobTool:
    def __init__(
        self,
        *,
        delegate: Any,
        gateway_getter: Callable[[], Any | None],
        dev_memory_fallback_getter: Callable[[], bool],
        dispatcher_getter: Callable[[], Any | None] | None = None,
    ) -> None:
        self._delegate = delegate
        self._gateway_getter = gateway_getter
        self._dev_memory_fallback_getter = dev_memory_fallback_getter
        self._dispatcher_getter = dispatcher_getter or (
            lambda: RenderWorkflowDispatcher()
        )

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._maybe_create_shadow_job(payload)
        return self._delegate.run(payload)

    def _maybe_create_shadow_job(self, payload: dict[str, Any]) -> None:
        if not backtest_jobs_shadow_enabled():
            return

        context = current_backtest_job_shadow_context()
        if context is None:
            logger.warning(
                "Backtest job shadow flag enabled without request context; skipping",
            )
            return

        try:
            gateway = self._gateway_getter()
            if gateway is None:
                raise RuntimeError(
                    "Supabase persistence is required for shadow backtest jobs."
                )
            backpressure_reason = _backpressure_reason(
                gateway=gateway,
                user_id=context.user_id,
                limits=backtest_job_backpressure_limits(),
            )
            if backpressure_reason is not None:
                logger.warning(
                    "Shadow backtest job backpressure hit; skipping durable job",
                    reason=backpressure_reason,
                    user_id=context.user_id,
                    conversation_id=context.conversation_id,
                )
                return
            payload_digest = payload_hash(payload)
            job = gateway.create_backtest_job(
                user_id=context.user_id,
                conversation_id=context.conversation_id,
                request_message_id=context.request_message_id,
                confirmation_message_id=context.confirmation_message_id,
                idempotency_key=context.idempotency_key,
                payload_hash=payload_digest,
                launch_payload=shadow_launch_payload(
                    payload=payload,
                    context=context,
                ),
                execution_metadata={
                    "shadow_mode": True,
                    "source": "api_chat",
                    "request_id": context.request_id,
                    "payload_hash": payload_digest,
                },
            )
            job_id = str(job.get("id") or "").strip()
            if job_id:
                context.created_job_id = job_id
                self._maybe_dispatch_shadow_job(
                    gateway=gateway,
                    context=context,
                    job_id=job_id,
                    job=job,
                    payload_digest=payload_digest,
                )
        except Exception as exc:
            if not self._dev_memory_fallback_getter():
                raise
            logger.warning(
                "Shadow backtest job creation failed; continuing in-process execution",
                error=str(exc),
                user_id=context.user_id,
                conversation_id=context.conversation_id,
            )

    def _maybe_dispatch_shadow_job(
        self,
        *,
        gateway: Any,
        context: BacktestJobShadowContext,
        job_id: str,
        job: dict[str, Any],
        payload_digest: str,
    ) -> None:
        if not backtest_jobs_dispatch_enabled():
            return
        if self._restore_existing_dispatch_context(context=context, job=job):
            return
        if job.get("result_run_id"):
            return
        job_status = str(job.get("status") or "").strip().lower()
        if job_status and job_status != "queued":
            return

        try:
            dispatcher = self._dispatcher_getter()
            if dispatcher is None:
                raise RuntimeError("Backtest job dispatch is not configured.")
            result = dispatcher.dispatch(
                job_id=job_id,
                nonce=payload_digest.removeprefix("sha256:"),
            )
            task_run_id = str(result.get("id") or "").strip() or None
            context.workflow_dispatch_started = True
            context.workflow_task_run_id = task_run_id
            gateway.merge_backtest_job_execution_metadata(
                user_id=context.user_id,
                job_id=job_id,
                execution_metadata={
                    "workflow_dispatch": {
                        "task": _workflow_task_id(),
                        "task_run_id": task_run_id,
                        "status": result.get("status"),
                        "dispatched_at": _utcnow_iso(),
                    }
                },
            )
        except Exception as exc:
            context.workflow_dispatch_error = str(exc)
            if not self._dev_memory_fallback_getter():
                raise
            logger.warning(
                "Shadow backtest job dispatch failed; continuing in-process execution",
                error=str(exc),
                user_id=context.user_id,
                conversation_id=context.conversation_id,
                job_id=job_id,
            )

    @staticmethod
    def _restore_existing_dispatch_context(
        *,
        context: BacktestJobShadowContext,
        job: dict[str, Any],
    ) -> bool:
        metadata = job.get("execution_metadata")
        if not isinstance(metadata, dict):
            return False
        workflow_dispatch = metadata.get("workflow_dispatch")
        if not isinstance(workflow_dispatch, dict):
            return False

        context.workflow_dispatch_started = True
        task_run_id = str(workflow_dispatch.get("task_run_id") or "").strip()
        context.workflow_task_run_id = task_run_id or None
        return True


def link_shadow_backtest_job_result(
    *,
    user_id: str,
    run_id: str,
    gateway: Any | None,
    dev_memory_fallback_enabled: bool,
) -> None:
    context = current_backtest_job_shadow_context()
    if context is None or context.created_job_id is None:
        return
    if gateway is None:
        if dev_memory_fallback_enabled:
            return
        raise RuntimeError("Supabase persistence is required to link backtest jobs.")

    mark_succeeded = not context.workflow_dispatch_started
    metadata: dict[str, Any] = {
        "api_in_process_result": {
            "result_run_id": run_id,
            "linked_at": _utcnow_iso(),
            "marked_succeeded": mark_succeeded,
        }
    }
    if context.workflow_task_run_id:
        metadata["workflow_dispatch"] = {
            "task_run_id": context.workflow_task_run_id,
            "result_linked_at": _utcnow_iso(),
        }
    if context.workflow_dispatch_error:
        metadata["workflow_dispatch_error"] = context.workflow_dispatch_error

    try:
        gateway.link_backtest_job_result(
            user_id=user_id,
            job_id=context.created_job_id,
            result_run_id=run_id,
            execution_metadata=metadata,
            mark_succeeded=mark_succeeded,
        )
    except Exception as exc:
        if not dev_memory_fallback_enabled:
            raise
        logger.warning(
            "Shadow backtest job result link failed; result run remains persisted",
            error=str(exc),
            user_id=user_id,
            job_id=context.created_job_id,
            run_id=run_id,
        )
