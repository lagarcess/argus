from __future__ import annotations

import traceback
from collections.abc import Callable, Mapping
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Protocol
from uuid import UUID

from argus.api.schemas import BacktestRun

if TYPE_CHECKING:
    from argus.agent_runtime.result_readout import ResultReadout

try:
    from workflows.proof import require_database_url, utcnow_iso
except ModuleNotFoundError:  # pragma: no cover - supports `python workflows/main.py`
    from proof import require_database_url, utcnow_iso

REAL_BACKTEST_JOB_KIND = "run_backtest_job"
WORKFLOW_METADATA_KEY = "workflow_backtest"


class WorkflowBacktestJobError(RuntimeError):
    """Raised when a real backtest job cannot be executed safely."""


class BacktestJobGateway(Protocol):
    def fetch_job(self, job_id: str) -> dict[str, Any] | None:
        """Return one backtest job row by id."""

    def mark_backtest_job_running(
        self,
        *,
        user_id: str,
        job_id: str,
        execution_metadata: dict[str, Any],
        started_at: str | None = None,
    ) -> dict[str, Any]:
        """Transition a queued job to running."""

    def create_backtest_run(self, *, user_id: str, run: BacktestRun) -> Any:
        """Persist the canonical completed run."""

    def link_backtest_job_result(
        self,
        *,
        user_id: str,
        job_id: str,
        result_run_id: str,
        execution_metadata: dict[str, Any] | None = None,
        mark_succeeded: bool = False,
    ) -> dict[str, Any]:
        """Link a successful job to its canonical run."""

    def mark_backtest_job_failed(
        self,
        *,
        user_id: str,
        job_id: str,
        failure_code: str,
        failure_detail: str,
        retryable: bool,
        execution_metadata: dict[str, Any] | None = None,
        finished_at: str | None = None,
    ) -> dict[str, Any]:
        """Persist a structured workflow failure."""


class BacktestTool(Protocol):
    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute the Argus launch backtest payload."""


def result_readout_with_metadata_from_backtest_payload(
    *args: Any,
    **kwargs: Any,
) -> "ResultReadout":
    from argus.agent_runtime.result_readout import (
        result_readout_with_metadata_from_backtest_payload as _result_readout,
    )

    return _result_readout(*args, **kwargs)


def run_backtest_job(
    gateway: BacktestJobGateway,
    *,
    job_id: str,
    backtest_tool: BacktestTool | None = None,
    workflow_run_id: str | None = None,
    run_id_factory: Callable[[], str] | None = None,
) -> dict[str, Any]:
    row = gateway.fetch_job(job_id)
    if row is None:
        raise WorkflowBacktestJobError(f"Backtest job {job_id} was not found.")
    _assert_real_job(row)

    user_id = _required_str(row, "user_id")
    conversation_id = _required_str(row, "conversation_id")
    request = _request_payload(row)
    started_at = utcnow_iso()
    running_metadata = _merge_workflow_metadata(
        row,
        {
            "kind": REAL_BACKTEST_JOB_KIND,
            "workflow_run_id": workflow_run_id,
            "started_at": started_at,
        },
    )
    running = gateway.mark_backtest_job_running(
        user_id=user_id,
        job_id=job_id,
        execution_metadata=running_metadata,
        started_at=started_at,
    )

    tool = backtest_tool or _default_backtest_tool()
    try:
        result = tool.run(request)
        if not bool(result.get("success")):
            return _mark_failed_from_tool_result(
                gateway,
                row=running,
                job_id=job_id,
                user_id=user_id,
                result=result,
                workflow_run_id=workflow_run_id,
            )

        payload = result.get("payload")
        if not isinstance(payload, dict):
            return _mark_failed(
                gateway,
                row=running,
                job_id=job_id,
                user_id=user_id,
                failure_code="invalid_tool_result",
                failure_detail="execution_failed",
                retryable=False,
                workflow_run_id=workflow_run_id,
            )
        envelope = payload.get("envelope")
        result_card = payload.get("result_card")
        if not isinstance(envelope, dict) or not isinstance(result_card, dict):
            return _mark_failed(
                gateway,
                row=running,
                job_id=job_id,
                user_id=user_id,
                failure_code="invalid_tool_result",
                failure_detail="execution_failed",
                retryable=False,
                workflow_run_id=workflow_run_id,
            )
        explanation_context = payload.get("explanation_context")
        explanation_context_dict = (
            dict(explanation_context) if isinstance(explanation_context, dict) else {}
        )
        result_readout = _safe_result_readout(
            request=request,
            envelope=envelope,
            result_card=result_card,
            explanation_context=explanation_context_dict,
        )

        from argus.domain.backtest_run_builder import build_backtest_run_from_result

        run = build_backtest_run_from_result(
            conversation_id=conversation_id,
            result_card=result_card,
            envelope=envelope,
            run_id_factory=run_id_factory,
        )
        if run is None:
            return _mark_failed(
                gateway,
                row=running,
                job_id=job_id,
                user_id=user_id,
                failure_code="invalid_run_snapshot",
                failure_detail="execution_failed",
                retryable=False,
                workflow_run_id=workflow_run_id,
            )

        created = gateway.create_backtest_run(user_id=user_id, run=run)
        result_run_id = _created_run_id(created, fallback=run.id)
        finished_at = utcnow_iso()
        succeeded_metadata = _merge_workflow_metadata(
            running,
            {
                "kind": REAL_BACKTEST_JOB_KIND,
                "workflow_run_id": workflow_run_id,
                "started_at": started_at,
                "finished_at": finished_at,
                "result_run_id": result_run_id,
                **_result_readout_metadata(result_readout),
            },
        )
        succeeded = gateway.link_backtest_job_result(
            user_id=user_id,
            job_id=job_id,
            result_run_id=result_run_id,
            execution_metadata=succeeded_metadata,
            mark_succeeded=True,
        )
        return {
            "job_id": str(succeeded.get("id") or job_id),
            "status": succeeded.get("status") or "succeeded",
            "result_run_id": result_run_id,
            "workflow_run_id": workflow_run_id,
            **({"result_readout": result_readout.text} if result_readout.text else {}),
            "result_readout_source": result_readout.source,
            "result_readout_fallback_used": result_readout.fallback_used,
            **(
                {"result_readout_failure_mode": result_readout.failure_mode}
                if result_readout.failure_mode
                else {}
            ),
            "execution_metadata": _json_safe(
                succeeded.get("execution_metadata") or succeeded_metadata
            ),
        }
    except Exception as exc:
        return _mark_failed(
            gateway,
            row=gateway.fetch_job(job_id) or running,
            job_id=job_id,
            user_id=user_id,
            failure_code="failed_internal",
            failure_detail="execution_failed",
            retryable=False,
            workflow_run_id=workflow_run_id,
            source_error=exc,
        )


def _default_backtest_tool() -> BacktestTool:
    from argus.agent_runtime.tools.real_backtest import RealBacktestTool

    return RealBacktestTool()


def _safe_result_readout(
    *,
    request: dict[str, Any],
    envelope: dict[str, Any],
    result_card: dict[str, Any],
    explanation_context: dict[str, Any],
) -> "ResultReadout":
    from argus.agent_runtime.result_readout import unavailable_result_readout

    try:
        return result_readout_with_metadata_from_backtest_payload(
            request=request,
            envelope=envelope,
            result_card=result_card,
            explanation_context=explanation_context,
            language=_optional_str(request.get("language")),
        )
    except Exception:
        return unavailable_result_readout()


def _result_readout_metadata(result_readout: "ResultReadout") -> dict[str, Any]:
    metadata = {
        "result_readout_source": result_readout.source,
        "result_readout_fallback_used": result_readout.fallback_used,
    }
    if result_readout.text:
        metadata["result_readout"] = result_readout.text
    if result_readout.failure_mode:
        metadata["result_readout_failure_mode"] = result_readout.failure_mode
    return metadata


def _assert_real_job(row: Mapping[str, Any]) -> None:
    if row.get("status") != "queued":
        raise WorkflowBacktestJobError(
            f"run_backtest_job expected queued job, found {row.get('status')!r}."
        )
    payload = _launch_payload(row)
    if payload.get("kind") != REAL_BACKTEST_JOB_KIND:
        raise WorkflowBacktestJobError(
            "run_backtest_job can only execute launch_payload.kind="
            f"{REAL_BACKTEST_JOB_KIND!r} jobs."
        )
    if not isinstance(payload.get("request"), dict):
        raise WorkflowBacktestJobError(
            "run_backtest_job requires a JSON object launch_payload.request."
        )


def _request_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    request = _launch_payload(row).get("request")
    return dict(request) if isinstance(request, dict) else {}


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _launch_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    raw = row.get("launch_payload") or {}
    if not isinstance(raw, dict):
        return {}
    return dict(raw)


def _job_metadata(row: Mapping[str, Any]) -> dict[str, Any]:
    raw = row.get("execution_metadata") or {}
    if not isinstance(raw, dict):
        return {}
    return dict(raw)


def _merge_workflow_metadata(
    row: Mapping[str, Any],
    patch: dict[str, Any],
) -> dict[str, Any]:
    metadata = _job_metadata(row)
    workflow_metadata = dict(metadata.get(WORKFLOW_METADATA_KEY) or {})
    workflow_metadata.update(patch)
    metadata[WORKFLOW_METADATA_KEY] = workflow_metadata
    return metadata


def _mark_failed_from_tool_result(
    gateway: BacktestJobGateway,
    *,
    row: Mapping[str, Any],
    job_id: str,
    user_id: str,
    result: dict[str, Any],
    workflow_run_id: str | None,
) -> dict[str, Any]:
    failure_code = str(result.get("error_type") or "failed_internal")
    capability_context = result.get("capability_context")
    failure_detail = None
    if isinstance(capability_context, dict):
        raw_failure_detail = capability_context.get("failure_detail")
        if isinstance(raw_failure_detail, str) and raw_failure_detail.strip():
            failure_detail = raw_failure_detail.strip()
    from argus.domain.engine_launch.results import user_safe_failure_detail

    failure_detail = failure_detail or user_safe_failure_detail(
        failure_reason=failure_code,
        failure_category=failure_code,
    )
    return _mark_failed(
        gateway,
        row=row,
        job_id=job_id,
        user_id=user_id,
        failure_code=failure_code,
        failure_detail=failure_detail,
        retryable=bool(result.get("retryable")),
        workflow_run_id=workflow_run_id,
    )


def _mark_failed(
    gateway: BacktestJobGateway,
    *,
    row: Mapping[str, Any],
    job_id: str,
    user_id: str,
    failure_code: str,
    failure_detail: str,
    retryable: bool,
    workflow_run_id: str | None,
    source_error: Exception | None = None,
) -> dict[str, Any]:
    finished_at = utcnow_iso()
    failure_patch: dict[str, Any] = {
        "kind": REAL_BACKTEST_JOB_KIND,
        "workflow_run_id": workflow_run_id,
        "finished_at": finished_at,
        "failure_category": failure_code,
        "failure_detail": failure_detail,
        "retryable": retryable,
    }
    if source_error is not None:
        failure_patch["source_error_type"] = type(source_error).__name__
        failure_patch["source_traceback"] = traceback.format_exception_only(
            type(source_error),
            source_error,
        )[-1].strip()
    metadata = _merge_workflow_metadata(row, failure_patch)
    failed = gateway.mark_backtest_job_failed(
        user_id=user_id,
        job_id=job_id,
        failure_code=failure_code,
        failure_detail=failure_detail,
        retryable=retryable,
        execution_metadata=metadata,
        finished_at=finished_at,
    )
    return {
        "job_id": str(failed.get("id") or job_id),
        "status": failed.get("status") or "failed",
        "failure_code": failure_code,
        "failure_detail": failure_detail,
        "retryable": retryable,
        "workflow_run_id": workflow_run_id,
        "execution_metadata": _json_safe(failed.get("execution_metadata") or metadata),
    }


def _created_run_id(created: Any, *, fallback: str) -> str:
    created_id = getattr(created, "id", None)
    if isinstance(created_id, str) and created_id.strip():
        return created_id
    if isinstance(created, dict):
        raw_id = created.get("id")
        if isinstance(raw_id, str) and raw_id.strip():
            return raw_id
    return fallback


def _required_str(row: Mapping[str, Any], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise WorkflowBacktestJobError(f"Backtest job is missing required {key}.")
    return value


def _json_safe(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return value


class PostgresBacktestJobGateway:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    @classmethod
    def from_env(cls) -> PostgresBacktestJobGateway:
        return cls(require_database_url())

    def _connect(self) -> Any:
        import psycopg
        from psycopg.rows import dict_row

        return psycopg.connect(self.database_url, row_factory=dict_row)

    def fetch_job(self, job_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select *
                    from public.backtest_jobs
                    where id = %s
                    limit 1
                    """,
                    (job_id,),
                )
                row = cur.fetchone()
        return _json_safe(row) if row else None

    def mark_backtest_job_running(
        self,
        *,
        user_id: str,
        job_id: str,
        execution_metadata: dict[str, Any],
        started_at: str | None = None,
    ) -> dict[str, Any]:
        from psycopg.types.json import Jsonb

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update public.backtest_jobs
                    set status = 'running',
                        started_at = coalesce(started_at, %(started_at)s),
                        attempts = attempts + 1,
                        execution_metadata = %(execution_metadata)s,
                        updated_at = %(updated_at)s
                    where id = %(job_id)s
                      and user_id = %(user_id)s
                      and status = 'queued'
                    returning *
                    """,
                    {
                        "job_id": job_id,
                        "user_id": user_id,
                        "started_at": started_at or utcnow_iso(),
                        "execution_metadata": Jsonb(execution_metadata),
                        "updated_at": utcnow_iso(),
                    },
                )
                row = cur.fetchone()
                if row is None:
                    raise WorkflowBacktestJobError(
                        f"Backtest job {job_id} was not queued or not found."
                    )
        return _json_safe(row)

    def create_backtest_run(self, *, user_id: str, run: BacktestRun) -> dict[str, Any]:
        from psycopg.types.json import Jsonb

        payload = run.model_dump(mode="json")
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into public.backtest_runs (
                      id,
                      user_id,
                      conversation_id,
                      strategy_id,
                      status,
                      asset_class,
                      symbols,
                      allocation_method,
                      benchmark_symbol,
                      metrics,
                      config_snapshot,
                      conversation_result_card,
                      chart,
                      trades,
                      created_at
                    )
                    values (
                      %(id)s,
                      %(user_id)s,
                      %(conversation_id)s,
                      %(strategy_id)s,
                      %(status)s,
                      %(asset_class)s,
                      %(symbols)s,
                      %(allocation_method)s,
                      %(benchmark_symbol)s,
                      %(metrics)s,
                      %(config_snapshot)s,
                      %(conversation_result_card)s,
                      %(chart)s,
                      %(trades)s,
                      %(created_at)s
                    )
                    returning *
                    """,
                    {
                        **payload,
                        "user_id": user_id,
                        "metrics": Jsonb(payload["metrics"]),
                        "config_snapshot": Jsonb(payload["config_snapshot"]),
                        "conversation_result_card": Jsonb(
                            payload["conversation_result_card"]
                        ),
                        "chart": Jsonb(payload.get("chart")),
                        "trades": Jsonb(payload.get("trades") or []),
                    },
                )
                row = cur.fetchone()
        return _json_safe(row)

    def link_backtest_job_result(
        self,
        *,
        user_id: str,
        job_id: str,
        result_run_id: str,
        execution_metadata: dict[str, Any] | None = None,
        mark_succeeded: bool = False,
    ) -> dict[str, Any]:
        from psycopg.types.json import Jsonb

        status = "succeeded" if mark_succeeded else None
        finished_at = utcnow_iso() if mark_succeeded else None
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update public.backtest_jobs
                    set result_run_id = coalesce(result_run_id, %(result_run_id)s),
                        status = coalesce(%(status)s, status),
                        finished_at = coalesce(%(finished_at)s, finished_at),
                        execution_metadata = %(execution_metadata)s,
                        updated_at = %(updated_at)s
                    where id = %(job_id)s
                      and user_id = %(user_id)s
                    returning *
                    """,
                    {
                        "job_id": job_id,
                        "user_id": user_id,
                        "result_run_id": result_run_id,
                        "status": status,
                        "finished_at": finished_at,
                        "execution_metadata": Jsonb(execution_metadata or {}),
                        "updated_at": utcnow_iso(),
                    },
                )
                row = cur.fetchone()
                if row is None:
                    raise WorkflowBacktestJobError(f"Backtest job {job_id} not found.")
        return _json_safe(row)

    def mark_backtest_job_failed(
        self,
        *,
        user_id: str,
        job_id: str,
        failure_code: str,
        failure_detail: str,
        retryable: bool,
        execution_metadata: dict[str, Any] | None = None,
        finished_at: str | None = None,
    ) -> dict[str, Any]:
        from psycopg.types.json import Jsonb

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update public.backtest_jobs
                    set status = 'failed',
                        finished_at = coalesce(%(finished_at)s, finished_at),
                        failure_code = %(failure_code)s,
                        failure_detail = %(failure_detail)s,
                        retryable = %(retryable)s,
                        execution_metadata = %(execution_metadata)s,
                        updated_at = %(updated_at)s
                    where id = %(job_id)s
                      and user_id = %(user_id)s
                    returning *
                    """,
                    {
                        "job_id": job_id,
                        "user_id": user_id,
                        "failure_code": failure_code,
                        "failure_detail": failure_detail,
                        "retryable": retryable,
                        "finished_at": finished_at or utcnow_iso(),
                        "execution_metadata": Jsonb(execution_metadata or {}),
                        "updated_at": utcnow_iso(),
                    },
                )
                row = cur.fetchone()
                if row is None:
                    raise WorkflowBacktestJobError(f"Backtest job {job_id} not found.")
        return _json_safe(row)
