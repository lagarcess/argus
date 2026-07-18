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

from argus.api.chat.backtest_admission_flow import BacktestArtifactIdentityError
from argus.domain.backtest_admission import chat_run_identity_hash, is_full_sha256_hash

TRUE_VALUES = {"1", "true", "yes", "on"}
SHADOW_JOB_SCHEMA_VERSION = "backtest_job_launch/v1"
DEFAULT_WORKFLOW_TASK = "argus-backtests/workflow_proof"
DEFAULT_REAL_WORKFLOW_TASK = "argus-backtests/run_backtest_job"
PROOF_JOB_KIND = "render_workflow_proof"
REAL_BACKTEST_JOB_KIND = "run_backtest_job"
RENDER_TASK_RUNS_URL = "https://api.render.com/v1/task-runs"
WORKFLOW_METADATA_KEY = "workflow_backtest"
DEFAULT_USER_RUNNING_LIMIT = 1
DEFAULT_USER_QUEUED_LIMIT = 2
DEFAULT_GLOBAL_RUNNING_LIMIT = 5
DEFAULT_GLOBAL_QUEUED_LIMIT = 10
DEFAULT_STALE_QUEUED_SECONDS = 15 * 60
DEFAULT_STALE_RUNNING_SECONDS = 15 * 60


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


def backtest_workflow_execution_enabled() -> bool:
    return (
        os.getenv("ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED", "").strip().lower()
        in TRUE_VALUES
    )


def render_local_dev_enabled() -> bool:
    return os.getenv("RENDER_USE_LOCAL_DEV", "").strip().lower() in TRUE_VALUES


def _render_task_runs_endpoint(endpoint: str | None = None) -> str:
    if endpoint:
        return endpoint.rstrip("/")
    if render_local_dev_enabled():
        local_base = os.getenv("RENDER_LOCAL_DEV_URL", "http://localhost:8120").strip()
        return f"{local_base.rstrip('/')}/v1/task-runs"
    return RENDER_TASK_RUNS_URL


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
        "kind": REAL_BACKTEST_JOB_KIND
        if backtest_workflow_execution_enabled()
        else PROOF_JOB_KIND,
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
    if backtest_workflow_execution_enabled():
        return (
            os.getenv("ARGUS_BACKTEST_REAL_WORKFLOW_TASK") or DEFAULT_REAL_WORKFLOW_TASK
        ).strip()
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
        if count >= limit and _reconcile_backpressure_blockers(
            gateway=gateway,
            fallback_user_id=user_id,
            status=status,
            user_id=scoped_user_id,
            limit=limit + 1,
        ):
            count = count_jobs(status=status, user_id=scoped_user_id, limit=limit + 1)
        if count >= limit:
            return reason
    return None


def _reconcile_backpressure_blockers(
    *,
    gateway: Any,
    fallback_user_id: str,
    status: str,
    user_id: str | None,
    limit: int,
) -> bool:
    list_jobs = getattr(gateway, "list_backtest_jobs", None)
    if list_jobs is None:
        return False

    try:
        jobs = list_jobs(status=status, user_id=user_id, limit=limit)
    except Exception as exc:
        logger.warning(
            "Backtest job backpressure reconciliation listing failed",
            error=str(exc),
            status=status,
            user_id=user_id,
        )
        return False

    changed = False
    for job in jobs:
        if not isinstance(job, dict):
            continue
        owner_user_id = str(job.get("user_id") or user_id or fallback_user_id)
        before = str(job.get("status") or "").strip().lower()
        if _should_fail_stale_proof_job_without_task_run(job):
            reconciled = _fail_stale_proof_job_without_task_run(
                gateway=gateway,
                user_id=owner_user_id,
                job=job,
            )
        else:
            reconciled = reconcile_terminal_render_task_run(
                gateway=gateway,
                user_id=owner_user_id,
                job=job,
            )
        after = str((reconciled or {}).get("status") or "").strip().lower()
        if before and after and after != before:
            changed = True
    return changed


class RenderWorkflowDispatcher:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        task_id: str | None = None,
        endpoint: str | None = None,
    ) -> None:
        self.api_key = (api_key or os.getenv("RENDER_API_KEY") or "").strip()
        self.task_id = (task_id or _workflow_task_id()).strip()
        self.endpoint = _render_task_runs_endpoint(endpoint)

    def dispatch(self, *, job_id: str, nonce: str) -> dict[str, Any]:
        if not self.api_key and not render_local_dev_enabled():
            raise RuntimeError("RENDER_API_KEY is required to dispatch backtest jobs.")
        if "/" not in self.task_id:
            raise RuntimeError(
                "ARGUS_BACKTEST_WORKFLOW_TASK must use {workflow-slug}/{task-name}."
            )

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        response = httpx.post(
            self.endpoint,
            headers=headers,
            json={"task": self.task_id, "input": [job_id, nonce]},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        return dict(data) if isinstance(data, dict) else {"response": data}


class RenderTaskRunClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        endpoint: str | None = None,
    ) -> None:
        self.api_key = (api_key or os.getenv("RENDER_API_KEY") or "").strip()
        self.endpoint = _render_task_runs_endpoint(endpoint)

    def get_task_run(self, task_run_id: str) -> dict[str, Any]:
        if not self.api_key and not render_local_dev_enabled():
            raise RuntimeError("RENDER_API_KEY is required to inspect task runs.")
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        response = httpx.get(
            f"{self.endpoint}/{task_run_id}",
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        return dict(data) if isinstance(data, dict) else {"response": data}


def reconcile_terminal_render_task_run(
    *,
    gateway: Any,
    user_id: str,
    job: dict[str, Any] | None,
    task_run_client: RenderTaskRunClient | None = None,
) -> dict[str, Any] | None:
    if job is None:
        return None
    status = str(job.get("status") or "").strip().lower()
    if status not in {"queued", "running"}:
        return job
    task_run_id = _task_run_id_from_job(job)
    if task_run_id is None:
        return job

    try:
        task_run = (task_run_client or RenderTaskRunClient()).get_task_run(task_run_id)
    except Exception as exc:
        logger.warning(
            "Render task run reconciliation skipped",
            error=str(exc),
            user_id=user_id,
            job_id=job.get("id"),
            task_run_id=task_run_id,
        )
        return job

    task_status = str(task_run.get("status") or "").strip().lower()
    if task_status not in {"failed", "canceled", "cancelled", "expired"}:
        return job

    failure_code, failure_detail, retryable = _workflow_task_failure(task_run)
    finished_at = _task_run_completed_at(task_run) or _utcnow_iso()
    reconciled = gateway.mark_backtest_job_failed(
        user_id=user_id,
        job_id=str(job.get("id") or ""),
        failure_code=failure_code,
        failure_detail=failure_detail,
        retryable=retryable,
        finished_at=finished_at,
        execution_metadata=_terminal_task_run_metadata(
            job=job,
            task_run=task_run,
            task_run_id=task_run_id,
            failure_code=failure_code,
            reconciled_at=_utcnow_iso(),
        ),
    )
    return dict(reconciled)


def scan_stale_backtest_jobs(
    *,
    gateway: Any,
    now: datetime | None = None,
    queued_age_seconds: int = DEFAULT_STALE_QUEUED_SECONDS,
    running_age_seconds: int = DEFAULT_STALE_RUNNING_SECONDS,
    limit: int = 100,
    task_run_client: RenderTaskRunClient | None = None,
) -> dict[str, Any]:
    list_jobs = getattr(gateway, "list_backtest_jobs", None)
    if list_jobs is None:
        raise RuntimeError("Gateway must support list_backtest_jobs for stale scan.")

    now_utc = now or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    now_utc = now_utc.astimezone(timezone.utc)

    report: dict[str, Any] = {
        "status": "ready",
        "scanned_count": 0,
        "stale_count": 0,
        "reconciled_count": 0,
        "unresolved_count": 0,
        "error_count": 0,
        "unresolved_jobs": [],
        "errors": [],
        "thresholds": {
            "queued_age_seconds": queued_age_seconds,
            "running_age_seconds": running_age_seconds,
        },
    }
    scan_plan = (
        ("queued", queued_age_seconds, ("queued_at", "created_at", "updated_at")),
        (
            "running",
            running_age_seconds,
            ("started_at", "updated_at", "queued_at", "created_at"),
        ),
    )
    max_jobs = max(1, limit)

    for status, stale_after_seconds, timestamp_keys in scan_plan:
        try:
            jobs = list_jobs(
                status=status,
                user_id=None,
                limit=max_jobs,
                oldest_first=True,
            )
        except TypeError:
            jobs = list_jobs(status=status, user_id=None, limit=max_jobs)
        except Exception as exc:
            report["errors"].append({"status": status, "error": str(exc)})
            report["error_count"] += 1
            continue

        for job in jobs:
            if not isinstance(job, dict):
                continue
            report["scanned_count"] += 1
            age_seconds = _job_age_seconds(
                job, now=now_utc, timestamp_keys=timestamp_keys
            )
            if age_seconds is not None and age_seconds < stale_after_seconds:
                continue

            report["stale_count"] += 1
            before = str(job.get("status") or status).strip().lower()
            user_id = str(job.get("user_id") or "").strip()
            task_run_id = _task_run_id_from_job(job)
            if not user_id:
                report["unresolved_jobs"].append(
                    _stale_job_report(job, before, age_seconds, task_run_id)
                )
                report["unresolved_count"] += 1
                continue

            try:
                if task_run_id is None and _is_workflow_proof_job(job):
                    reconciled = _fail_stale_proof_job_without_task_run(
                        gateway=gateway,
                        user_id=user_id,
                        job=job,
                    )
                    after = str(reconciled.get("status") or before).strip().lower()
                    if after not in {"queued", "running"}:
                        report["reconciled_count"] += 1
                        continue

                reconciled = reconcile_terminal_render_task_run(
                    gateway=gateway,
                    user_id=user_id,
                    job=job,
                    task_run_client=task_run_client,
                )
            except Exception as exc:
                report["errors"].append(
                    {
                        "id": job.get("id"),
                        "status": before,
                        "user_id": user_id,
                        "error": str(exc),
                    }
                )
                report["error_count"] += 1
                continue

            after = str((reconciled or {}).get("status") or before).strip().lower()
            if before in {"queued", "running"} and after not in {"queued", "running"}:
                report["reconciled_count"] += 1
                continue

            report["unresolved_jobs"].append(
                _stale_job_report(job, before, age_seconds, task_run_id)
            )
            report["unresolved_count"] += 1

    if report["unresolved_count"] or report["error_count"]:
        report["status"] = "degraded"
    return report


def _is_workflow_proof_job(job: dict[str, Any]) -> bool:
    launch_payload = _dict_or_empty(job.get("launch_payload"))
    return launch_payload.get("kind") == PROOF_JOB_KIND


def _fail_stale_proof_job_without_task_run(
    *,
    gateway: Any,
    user_id: str,
    job: dict[str, Any],
) -> dict[str, Any]:
    failure_code = "workflow_dispatch_missing"
    failure_detail = (
        "Render workflow proof did not record a task run before the stale threshold."
    )
    reconciled_at = _utcnow_iso()
    metadata = _dict_or_empty(job.get("execution_metadata"))

    workflow_dispatch = _dict_or_empty(metadata.get("workflow_dispatch"))
    workflow_dispatch.update(
        {
            "status": "failed",
            "failure_code": failure_code,
            "reconciled_at": reconciled_at,
        }
    )
    metadata["workflow_dispatch"] = workflow_dispatch

    workflow_metadata = _dict_or_empty(metadata.get("workflow_proof"))
    workflow_metadata.update(
        {
            "kind": PROOF_JOB_KIND,
            "failure_code": failure_code,
            "finished_at": reconciled_at,
        }
    )
    metadata["workflow_proof"] = workflow_metadata

    return dict(
        gateway.mark_backtest_job_failed(
            user_id=user_id,
            job_id=str(job.get("id") or ""),
            failure_code=failure_code,
            failure_detail=failure_detail,
            retryable=True,
            finished_at=reconciled_at,
            execution_metadata=metadata,
        )
    )


def _stale_seconds_for_status(status: str) -> int:
    if status == "queued":
        return DEFAULT_STALE_QUEUED_SECONDS
    return DEFAULT_STALE_RUNNING_SECONDS


def _should_fail_stale_proof_job_without_task_run(job: dict[str, Any]) -> bool:
    status = str(job.get("status") or "").strip().lower()
    if status not in {"queued", "running"}:
        return False
    if not _is_workflow_proof_job(job):
        return False
    if _task_run_id_from_job(job) is not None:
        return False
    age_seconds = _job_age_seconds(
        job,
        now=datetime.now(timezone.utc),
        timestamp_keys=("started_at", "created_at"),
    )
    if age_seconds is None:
        return False
    return age_seconds >= _stale_seconds_for_status(status)


def _stale_job_report(
    job: dict[str, Any],
    status: str,
    age_seconds: int | None,
    task_run_id: str | None,
) -> dict[str, Any]:
    return {
        "id": job.get("id"),
        "status": status,
        "user_id": job.get("user_id"),
        "age_seconds": age_seconds,
        "task_run_id": task_run_id,
    }


def _job_age_seconds(
    job: dict[str, Any],
    *,
    now: datetime,
    timestamp_keys: tuple[str, ...],
) -> int | None:
    timestamp = None
    for key in timestamp_keys:
        timestamp = _parse_timestamp(job.get(key))
        if timestamp is not None:
            break
    if timestamp is None:
        return None
    return max(0, int((now - timestamp).total_seconds()))


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _task_run_id_from_job(job: dict[str, Any]) -> str | None:
    metadata = _dict_or_empty(job.get("execution_metadata"))
    if not metadata:
        return None
    for key in ("workflow_dispatch", WORKFLOW_METADATA_KEY):
        section = _dict_or_empty(metadata.get(key))
        raw = section.get("task_run_id") or section.get("workflow_run_id")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return None


def _task_run_error(task_run: dict[str, Any]) -> str:
    raw = task_run.get("error")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    attempts = task_run.get("attempts")
    if isinstance(attempts, list):
        for attempt in reversed(attempts):
            if not isinstance(attempt, dict):
                continue
            error = attempt.get("error")
            if isinstance(error, str) and error.strip():
                return error.strip()
    return ""


def _task_run_completed_at(task_run: dict[str, Any]) -> str | None:
    for key in ("completedAt", "completed_at", "finishedAt", "finished_at"):
        raw = task_run.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    attempts = task_run.get("attempts")
    if isinstance(attempts, list):
        for attempt in reversed(attempts):
            if not isinstance(attempt, dict):
                continue
            for key in ("completedAt", "completed_at", "finishedAt", "finished_at"):
                raw = attempt.get(key)
                if isinstance(raw, str) and raw.strip():
                    return raw.strip()
    return None


def _workflow_task_failure(task_run: dict[str, Any]) -> tuple[str, str, bool]:
    status = str(task_run.get("status") or "").strip().lower()
    error = _task_run_error(task_run).lower()
    if "timed out" in error or "timeout" in error:
        return (
            "workflow_task_timeout",
            "Backtest execution timed out before finishing.",
            True,
        )
    if status in {"canceled", "cancelled"}:
        return (
            "workflow_task_canceled",
            "Backtest execution was canceled before finishing.",
            False,
        )
    if status == "expired":
        return (
            "workflow_task_expired",
            "Backtest execution expired before finishing.",
            True,
        )
    return (
        "workflow_task_failed",
        "Backtest execution failed before finishing.",
        True,
    )


def _terminal_task_run_metadata(
    *,
    job: dict[str, Any],
    task_run: dict[str, Any],
    task_run_id: str,
    failure_code: str,
    reconciled_at: str,
) -> dict[str, Any]:
    metadata = _dict_or_empty(job.get("execution_metadata"))
    task_status = str(task_run.get("status") or "").strip().lower()
    task_error = _task_run_error(task_run)
    completed_at = _task_run_completed_at(task_run)

    workflow_dispatch = _dict_or_empty(metadata.get("workflow_dispatch"))
    workflow_dispatch.update(
        {
            "task_run_id": task_run_id,
            "status": task_status,
            "failure_code": failure_code,
            "reconciled_at": reconciled_at,
        }
    )
    if task_error:
        workflow_dispatch["error"] = task_error
    if completed_at:
        workflow_dispatch["completed_at"] = completed_at
    metadata["workflow_dispatch"] = workflow_dispatch

    workflow_metadata = _dict_or_empty(metadata.get(WORKFLOW_METADATA_KEY))
    workflow_metadata.update(
        {
            "workflow_run_id": task_run_id,
            "workflow_run_status": task_status,
            "failure_code": failure_code,
            "reconciled_at": reconciled_at,
        }
    )
    if task_error:
        workflow_metadata["workflow_run_error"] = task_error
    if completed_at:
        workflow_metadata["finished_at"] = completed_at
    metadata[WORKFLOW_METADATA_KEY] = workflow_metadata
    return metadata


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


class ShadowBacktestJobTool:
    def __init__(
        self,
        *,
        delegate: Any | None,
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
        job = self._maybe_create_shadow_job(payload)
        if self._should_return_async_job(job):
            return async_backtest_job_envelope(job)
        if self._delegate is None:
            raise RuntimeError(
                "Backtest workflow execution is enabled, but no async job was "
                "created for this request."
            )
        return self._delegate.run(payload)

    def _maybe_create_shadow_job(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        if not backtest_jobs_shadow_enabled():
            return None

        context = current_backtest_job_shadow_context()
        if context is None:
            logger.warning(
                "Backtest job shadow flag enabled without request context; skipping",
            )
            return None

        confirmation_id = None
        artifact_launch_hash = None
        is_run_action = False
        if isinstance(context.chat_action, dict):
            is_run_action = context.chat_action.get("type") == "run_backtest"
            raw_confirmation = context.chat_action.get("confirmation_id")
            if isinstance(raw_confirmation, str) and raw_confirmation.strip():
                confirmation_id = raw_confirmation.strip()
            action_payload = context.chat_action.get("payload")
            if isinstance(action_payload, dict):
                if confirmation_id is None:
                    nested = action_payload.get("confirmation_id")
                    if isinstance(nested, str) and nested.strip():
                        confirmation_id = nested.strip()
                raw_full = action_payload.get("launch_payload_hash_full")
                if isinstance(raw_full, str):
                    artifact_launch_hash = raw_full
        # Identity binds to the immutable confirmation artifact's full-width
        # launch hash. A run action without it terminates here — before any
        # durable admission, delegate execution, provider access, or compute —
        # and this typed failure is never swallowed by the dev fallback.
        if is_run_action and not is_full_sha256_hash(artifact_launch_hash):
            raise BacktestArtifactIdentityError(
                "Run action confirmation artifact lacks a valid launch hash."
            )
        if not is_full_sha256_hash(artifact_launch_hash):
            return None

        try:
            gateway = self._gateway_getter()
            if gateway is None:
                raise RuntimeError(
                    "Supabase persistence is required for shadow backtest jobs."
                )
            payload_digest = payload_hash(payload)
            identity_hash = chat_run_identity_hash(
                conversation_id=context.conversation_id,
                confirmation_id=confirmation_id or context.idempotency_key,
                launch_payload_hash=artifact_launch_hash,
            )
            job = self._admit_durable_job(
                gateway=gateway,
                context=context,
                identity_hash=identity_hash,
                payload_digest=payload_digest,
                launch_payload=shadow_launch_payload(
                    payload=payload,
                    context=context,
                ),
                artifact_launch_hash=artifact_launch_hash,
            )
            if job is None:
                return None
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
                return dict(job)
        except BacktestArtifactIdentityError:
            # The identity failure is terminal by contract; the dev fallback
            # must not convert it into in-process execution.
            raise
        except Exception as exc:
            if not self._dev_memory_fallback_getter():
                raise
            logger.warning(
                "Shadow backtest job creation failed; continuing in-process execution",
                error=str(exc),
                user_id=context.user_id,
                conversation_id=context.conversation_id,
            )
        return None

    def _admit_durable_job(
        self,
        *,
        gateway: Any,
        context: BacktestJobShadowContext,
        identity_hash: str,
        payload_digest: str,
        launch_payload: dict[str, Any],
        artifact_launch_hash: str | None = None,
    ) -> dict[str, Any] | None:
        from argus.api.chat.backtest_admission_flow import admit_durable_chat_job

        return admit_durable_chat_job(
            gateway=gateway,
            context=context,
            identity_hash=identity_hash,
            payload_digest=payload_digest,
            launch_payload=launch_payload,
            reconcile_blockers=_reconcile_backpressure_blockers,
            artifact_launch_hash=artifact_launch_hash,
        )

    @staticmethod
    def _should_return_async_job(job: dict[str, Any] | None) -> bool:
        if job is None:
            return False
        if not (
            backtest_jobs_shadow_enabled()
            and backtest_jobs_dispatch_enabled()
            and backtest_workflow_execution_enabled()
        ):
            return False
        launch_payload = job.get("launch_payload")
        if not isinstance(launch_payload, dict):
            return False
        if launch_payload.get("kind") != REAL_BACKTEST_JOB_KIND:
            return False
        context = current_backtest_job_shadow_context()
        if context is None or context.created_job_id is None:
            return False
        status = str(job.get("status") or "").strip().lower()
        if status in {"succeeded", "failed", "canceled", "expired"}:
            return True
        return context.workflow_dispatch_started

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
    linked_at = _utcnow_iso()
    metadata: dict[str, Any] = {
        "api_in_process_result": {
            "result_run_id": run_id,
            "linked_at": linked_at,
            "marked_succeeded": mark_succeeded,
        }
    }
    if context.workflow_task_run_id:
        metadata["workflow_dispatch"] = {
            "task_run_id": context.workflow_task_run_id,
            "result_linked_at": linked_at,
        }
    if context.workflow_dispatch_error:
        metadata["workflow_dispatch_error"] = context.workflow_dispatch_error

    try:
        if context.workflow_dispatch_started and backtest_workflow_execution_enabled():
            metadata["api_in_process_result"]["job_result_column_owned_by"] = (
                REAL_BACKTEST_JOB_KIND
            )
            gateway.merge_backtest_job_execution_metadata(
                user_id=user_id,
                job_id=context.created_job_id,
                execution_metadata=metadata,
            )
            return
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
