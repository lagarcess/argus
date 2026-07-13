from __future__ import annotations

import time
import traceback
from collections.abc import Callable, Mapping
from contextlib import ExitStack, contextmanager
from datetime import date, datetime
from math import isfinite
from typing import TYPE_CHECKING, Any, Protocol
from uuid import UUID

from argus.api.schemas import BacktestRun, EvidenceArtifact, Idea, IdeaVersion
from argus.domain.backtest_finalization import (
    FinalizedBacktest,
    PreparedBacktestFinalization,
)
from argus.domain.evidence import CapturedEvidence
from argus.observability.cost_ledger import (
    normalize_cost_ledger_entry,
    persist_openrouter_cost_ledger_entries,
)
from loguru import logger

if TYPE_CHECKING:
    from argus.agent_runtime.result_readout import ResultReadout
    from argus.llm.openrouter import OpenRouterRouteReceipt

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

    def merge_backtest_job_execution_metadata(
        self,
        *,
        user_id: str,
        job_id: str,
        execution_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """Merge non-lifecycle execution metadata onto an existing job."""

    def create_route_receipt(
        self,
        *,
        user_id: str | None,
        receipt: dict[str, Any],
        conversation_id: str | None = None,
        run_id: str | None = None,
        message_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Persist LLM route telemetry produced during workflow execution."""

    def create_cost_ledger_entry(self, *, entry: dict[str, Any]) -> dict[str, Any]:
        """Append provider/runtime spend produced during workflow execution."""


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
    timings = _WorkflowTimingRecorder()
    phase_started = time.perf_counter()
    row = gateway.fetch_job(job_id)
    timings.record_elapsed("job_fetch", phase_started)
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
    phase_started = time.perf_counter()
    running = gateway.mark_backtest_job_running(
        user_id=user_id,
        job_id=job_id,
        execution_metadata=running_metadata,
        started_at=started_at,
    )
    timings.record_elapsed("mark_running", phase_started)

    if backtest_tool is None:
        phase_started = time.perf_counter()
        tool = _default_backtest_tool()
        timings.record_elapsed("dependency_or_tool_load", phase_started)
    else:
        tool = backtest_tool
    try:
        phase_started = time.perf_counter()
        result = tool.run(request)
        timings.record_elapsed("backtest_tool_run_total", phase_started)
        timings.merge(_tool_timings_ms(result))
        if not bool(result.get("success")):
            return _mark_failed_from_tool_result(
                gateway,
                row=running,
                job_id=job_id,
                user_id=user_id,
                result=result,
                workflow_run_id=workflow_run_id,
                timings=timings,
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
                timings=timings,
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
                timings=timings,
            )
        explanation_context = payload.get("explanation_context")
        explanation_context_dict = (
            dict(explanation_context) if isinstance(explanation_context, dict) else {}
        )
        phase_started = time.perf_counter()
        result_readout, result_readout_receipts = _safe_result_readout_with_receipts(
            request=request,
            envelope=envelope,
            result_card=result_card,
            explanation_context=explanation_context_dict,
        )
        timings.record_elapsed("result_readout_total", phase_started)

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
                timings=timings,
            )

        phase_started = time.perf_counter()
        created = gateway.create_backtest_run(user_id=user_id, run=run)
        timings.record_elapsed("backtest_run_persist", phase_started)
        result_run_id = _created_run_id(created, fallback=run.id)
        phase_started = time.perf_counter()
        _persist_result_readout_route_receipts(
            gateway,
            receipts=result_readout_receipts,
            user_id=user_id,
            conversation_id=conversation_id,
            result_run_id=result_run_id,
            job_id=job_id,
            workflow_run_id=workflow_run_id,
        )
        timings.record_elapsed("result_readout_receipts_persist", phase_started)
        finished_at = utcnow_iso()
        succeeded_metadata = _merge_workflow_metadata(
            running,
            {
                "kind": REAL_BACKTEST_JOB_KIND,
                "workflow_run_id": workflow_run_id,
                "started_at": started_at,
                "finished_at": finished_at,
                "result_run_id": result_run_id,
                "timings_ms": timings.snapshot(),
                **_result_readout_metadata(result_readout),
            },
        )
        phase_started = time.perf_counter()
        succeeded = gateway.link_backtest_job_result(
            user_id=user_id,
            job_id=job_id,
            result_run_id=result_run_id,
            execution_metadata=succeeded_metadata,
            mark_succeeded=True,
        )
        timings.record_elapsed("link_result", phase_started)
        succeeded = _persist_final_workflow_timings(
            gateway,
            user_id=user_id,
            job_id=job_id,
            row=succeeded,
            timings=timings,
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
            timings=timings,
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


def _safe_result_readout_with_receipts(
    *,
    request: dict[str, Any],
    envelope: dict[str, Any],
    result_card: dict[str, Any],
    explanation_context: dict[str, Any],
) -> tuple["ResultReadout", list["OpenRouterRouteReceipt"]]:
    from argus.llm.openrouter import (
        begin_openrouter_route_receipt_capture,
        end_openrouter_route_receipt_capture,
    )

    token = begin_openrouter_route_receipt_capture()
    try:
        result_readout = _safe_result_readout(
            request=request,
            envelope=envelope,
            result_card=result_card,
            explanation_context=explanation_context,
        )
    finally:
        receipts = end_openrouter_route_receipt_capture(token)
    return result_readout, receipts


def _persist_result_readout_route_receipts(
    gateway: BacktestJobGateway,
    *,
    receipts: list["OpenRouterRouteReceipt"],
    user_id: str,
    conversation_id: str,
    result_run_id: str,
    job_id: str,
    workflow_run_id: str | None,
) -> None:
    if not receipts:
        return
    metadata = {
        "job_id": job_id,
        "workflow_run_id": workflow_run_id,
        "source": "render_workflow",
    }
    for receipt in receipts:
        try:
            created = gateway.create_route_receipt(
                user_id=user_id,
                conversation_id=conversation_id,
                run_id=result_run_id,
                metadata=metadata,
                receipt=receipt.as_dict(),
            )
            persist_openrouter_cost_ledger_entries(
                gateway=gateway,
                receipts=[receipt],
                source="render_workflow",
                feature_area="result_readout",
                user_id=user_id,
                conversation_id=conversation_id,
                backtest_run_id=result_run_id,
                backtest_job_id=job_id,
                route_receipt_rows=[created],
                correlation_id=":".join(
                    part
                    for part in (
                        "workflow",
                        workflow_run_id,
                        job_id,
                        result_run_id,
                    )
                    if part
                ),
                metadata=metadata,
            )
        except Exception as exc:
            logger.warning(
                "Backtest workflow route receipt persistence failed",
                error=str(exc),
                job_id=job_id,
                workflow_run_id=workflow_run_id,
                llm_task=receipt.task,
            )


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


class _WorkflowTimingRecorder:
    def __init__(self) -> None:
        self._task_started = time.perf_counter()
        self._timings_ms: dict[str, float] = {}

    def record_elapsed(self, name: str, started: float) -> None:
        self.add(name, (time.perf_counter() - started) * 1000.0)

    def add(self, name: str, elapsed_ms: Any) -> None:
        if isinstance(elapsed_ms, bool):
            return
        try:
            numeric = float(elapsed_ms)
        except (TypeError, ValueError):
            return
        if not isfinite(numeric) or numeric < 0.0:
            return
        self._timings_ms[name] = self._timings_ms.get(name, 0.0) + numeric

    def merge(self, timings_ms: Mapping[str, Any]) -> None:
        for name, elapsed_ms in timings_ms.items():
            self.add(str(name), elapsed_ms)

    def record_workflow_total(self) -> None:
        self._timings_ms["workflow_task_total"] = (
            time.perf_counter() - self._task_started
        ) * 1000.0

    def snapshot(self) -> dict[str, float]:
        return {
            name: round(elapsed_ms, 3)
            for name, elapsed_ms in sorted(self._timings_ms.items())
        }


def _tool_timings_ms(result: Mapping[str, Any]) -> dict[str, float]:
    metadata = result.get("execution_metadata")
    if not isinstance(metadata, dict):
        return {}
    raw_timings = metadata.get("timings_ms")
    if not isinstance(raw_timings, dict):
        return {}
    timings: dict[str, float] = {}
    for name, elapsed_ms in raw_timings.items():
        if not isinstance(name, str) or isinstance(elapsed_ms, bool):
            continue
        try:
            numeric = float(elapsed_ms)
        except (TypeError, ValueError):
            continue
        if isfinite(numeric) and numeric >= 0.0:
            timings[name] = numeric
    return timings


def _persist_final_workflow_timings(
    gateway: BacktestJobGateway,
    *,
    user_id: str,
    job_id: str,
    row: Mapping[str, Any],
    timings: _WorkflowTimingRecorder,
) -> dict[str, Any]:
    timings.record_workflow_total()
    metadata = _merge_workflow_metadata(row, {"timings_ms": timings.snapshot()})
    try:
        updated = gateway.merge_backtest_job_execution_metadata(
            user_id=user_id,
            job_id=job_id,
            execution_metadata=metadata,
        )
    except Exception as exc:
        logger.warning(
            "Backtest workflow timing metadata merge failed",
            error=str(exc),
            job_id=job_id,
        )
        updated = dict(row)
        updated["execution_metadata"] = metadata
    return updated


def _mark_failed_from_tool_result(
    gateway: BacktestJobGateway,
    *,
    row: Mapping[str, Any],
    job_id: str,
    user_id: str,
    result: dict[str, Any],
    workflow_run_id: str | None,
    timings: _WorkflowTimingRecorder,
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
        timings=timings,
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
    timings: _WorkflowTimingRecorder | None = None,
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
    if timings is not None:
        failure_patch["timings_ms"] = timings.snapshot()
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
    if timings is not None:
        failed = _persist_final_workflow_timings(
            gateway,
            user_id=user_id,
            job_id=job_id,
            row=failed,
            timings=timings,
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
        self._conn: Any | None = None
        self._exit_stack: ExitStack | None = None

    @classmethod
    def from_env(cls) -> PostgresBacktestJobGateway:
        return cls(require_database_url())

    def __enter__(self) -> PostgresBacktestJobGateway:
        if self._exit_stack is not None:
            return self
        exit_stack = ExitStack()
        self._conn = exit_stack.enter_context(self._connect())
        self._exit_stack = exit_stack
        return self

    def __exit__(self, *exc_info: object) -> None:
        if self._exit_stack is not None:
            self._exit_stack.__exit__(*exc_info)
        self._conn = None
        self._exit_stack = None

    def _connect(self) -> Any:
        import psycopg
        from psycopg.rows import dict_row

        return psycopg.connect(self.database_url, autocommit=True, row_factory=dict_row)

    @contextmanager
    def _connection(self) -> Any:
        if self._conn is not None:
            yield self._conn
            return
        with self._connect() as conn:
            yield conn

    def fetch_job(self, job_id: str) -> dict[str, Any] | None:
        with self._connection() as conn:
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

        with self._connection() as conn:
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

    def merge_backtest_job_execution_metadata(
        self,
        *,
        user_id: str,
        job_id: str,
        execution_metadata: dict[str, Any],
    ) -> dict[str, Any]:
        from psycopg.types.json import Jsonb

        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update public.backtest_jobs
                    set execution_metadata = %(execution_metadata)s,
                        updated_at = %(updated_at)s
                    where id = %(job_id)s
                      and user_id = %(user_id)s
                    returning *
                    """,
                    {
                        "job_id": job_id,
                        "user_id": user_id,
                        "execution_metadata": Jsonb(execution_metadata),
                        "updated_at": utcnow_iso(),
                    },
                )
                row = cur.fetchone()
                if row is None:
                    raise WorkflowBacktestJobError(f"Backtest job {job_id} not found.")
        return _json_safe(row)

    def create_backtest_run(self, *, user_id: str, run: BacktestRun) -> dict[str, Any]:
        from psycopg.types.json import Jsonb

        payload = run.model_dump(mode="json")
        with self._connection() as conn:
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

    def finalize_backtest_completion(
        self,
        *,
        finalization: PreparedBacktestFinalization,
    ) -> FinalizedBacktest:
        from psycopg.types.json import Jsonb

        captured = finalization.captured
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select *
                    from public.finalize_backtest_completion(
                      %(user_id)s::uuid,
                      %(execution_identity)s::text,
                      %(run)s::jsonb,
                      %(idea)s::jsonb,
                      %(idea_version)s::jsonb,
                      %(evidence_artifact)s::jsonb
                    )
                    """,
                    {
                        "user_id": finalization.user_id,
                        "execution_identity": finalization.execution_identity,
                        "run": Jsonb(finalization.run.model_dump(mode="json")),
                        "idea": Jsonb(captured.idea.model_dump(mode="json")),
                        "idea_version": Jsonb(
                            captured.idea_version.model_dump(mode="json")
                        ),
                        "evidence_artifact": Jsonb(
                            captured.evidence_artifact.model_dump(mode="json")
                        ),
                    },
                )
                row = cur.fetchone()
        if row is None:
            raise WorkflowBacktestJobError(
                "Backtest finalization did not return durable artifact state."
            )
        return FinalizedBacktest(
            run=BacktestRun.model_validate(row["run"]),
            captured=CapturedEvidence(
                idea=Idea.model_validate(row["idea"]),
                idea_version=IdeaVersion.model_validate(row["idea_version"]),
                evidence_artifact=EvidenceArtifact.model_validate(
                    row["evidence_artifact"]
                ),
            ),
        )

    def create_route_receipt(
        self,
        *,
        user_id: str | None,
        receipt: dict[str, Any],
        conversation_id: str | None = None,
        run_id: str | None = None,
        message_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        from psycopg.types.json import Jsonb

        context_packet_ids = [
            str(packet_id)
            for packet_id in receipt.get("context_packet_ids") or []
            if str(packet_id or "").strip()
        ]
        token_usage = receipt.get("token_usage")
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into public.route_receipts (
                      user_id,
                      conversation_id,
                      run_id,
                      message_id,
                      task,
                      tier,
                      model,
                      fallback_model,
                      mode,
                      schema_name,
                      latency_ms,
                      outcome,
                      failure_mode,
                      fallback_used,
                      token_usage,
                      context_packet_ids,
                      metadata,
                      created_at
                    )
                    values (
                      %(user_id)s,
                      %(conversation_id)s,
                      %(run_id)s,
                      %(message_id)s,
                      %(task)s,
                      %(tier)s,
                      %(model)s,
                      %(fallback_model)s,
                      %(mode)s,
                      %(schema_name)s,
                      %(latency_ms)s,
                      %(outcome)s,
                      %(failure_mode)s,
                      %(fallback_used)s,
                      %(token_usage)s,
                      %(context_packet_ids)s,
                      %(metadata)s,
                      %(created_at)s
                    )
                    returning *
                    """,
                    {
                        "user_id": user_id,
                        "conversation_id": conversation_id,
                        "run_id": run_id,
                        "message_id": message_id,
                        "task": receipt["task"],
                        "tier": receipt["tier"],
                        "model": receipt.get("model"),
                        "fallback_model": receipt.get("fallback_model"),
                        "mode": receipt["mode"],
                        "schema_name": receipt.get("schema_name"),
                        "latency_ms": int(receipt.get("latency_ms") or 0),
                        "outcome": receipt["outcome"],
                        "failure_mode": receipt.get("failure_mode"),
                        "fallback_used": bool(receipt.get("fallback_used")),
                        "token_usage": Jsonb(token_usage)
                        if token_usage is not None
                        else None,
                        "context_packet_ids": context_packet_ids,
                        "metadata": Jsonb(metadata or {}),
                        "created_at": receipt.get("created_at") or utcnow_iso(),
                    },
                )
                row = cur.fetchone()
        return _json_safe(row)

    def create_cost_ledger_entry(self, *, entry: dict[str, Any]) -> dict[str, Any]:
        from psycopg.types.json import Jsonb

        params = normalize_cost_ledger_entry(entry)
        params["usage_metadata"] = Jsonb(params["usage_metadata"])
        params["metadata"] = Jsonb(params["metadata"])
        params["occurred_at"] = params["occurred_at"] or utcnow_iso()
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into public.cost_ledger_entries (
                      source,
                      service,
                      provider,
                      model,
                      feature_area,
                      task,
                      user_id,
                      conversation_id,
                      message_id,
                      backtest_run_id,
                      backtest_job_id,
                      route_receipt_id,
                      request_id,
                      correlation_id,
                      provider_request_id,
                      upstream_id,
                      usage_metadata,
                      input_tokens,
                      output_tokens,
                      total_tokens,
                      billable_unit,
                      billable_quantity,
                      cost_amount,
                      cost_currency,
                      cost_source,
                      latency_ms,
                      status,
                      metadata,
                      occurred_at
                    )
                    values (
                      %(source)s,
                      %(service)s,
                      %(provider)s,
                      %(model)s,
                      %(feature_area)s,
                      %(task)s,
                      %(user_id)s,
                      %(conversation_id)s,
                      %(message_id)s,
                      %(backtest_run_id)s,
                      %(backtest_job_id)s,
                      %(route_receipt_id)s,
                      %(request_id)s,
                      %(correlation_id)s,
                      %(provider_request_id)s,
                      %(upstream_id)s,
                      %(usage_metadata)s,
                      %(input_tokens)s,
                      %(output_tokens)s,
                      %(total_tokens)s,
                      %(billable_unit)s,
                      %(billable_quantity)s,
                      %(cost_amount)s,
                      %(cost_currency)s,
                      %(cost_source)s,
                      %(latency_ms)s,
                      %(status)s,
                      %(metadata)s,
                      %(occurred_at)s
                    )
                    returning *
                    """,
                    params,
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
        with self._connection() as conn:
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

        with self._connection() as conn:
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
