from __future__ import annotations

import importlib
import sys
from datetime import date, datetime, timezone
from types import ModuleType
from uuid import UUID, uuid4

import pytest


class FakeBacktestJobGateway:
    def __init__(self, row: dict[str, object]) -> None:
        self.row = dict(row)
        self.transitions: list[str] = []
        self.created_runs: list[dict[str, object]] = []
        self.failed_updates: list[dict[str, object]] = []

    def fetch_job(self, job_id: str) -> dict[str, object] | None:
        if self.row["id"] != job_id:
            return None
        return dict(self.row)

    def mark_backtest_job_running(
        self,
        *,
        user_id: str,
        job_id: str,
        execution_metadata: dict[str, object],
        started_at: str | None = None,
    ) -> dict[str, object]:
        assert self.row["user_id"] == user_id
        assert self.row["id"] == job_id
        self.transitions.append("running")
        self.row["status"] = "running"
        self.row["started_at"] = started_at
        self.row["attempts"] = int(self.row.get("attempts") or 0) + 1
        self.row["execution_metadata"] = execution_metadata
        return dict(self.row)

    def create_backtest_run(self, *, user_id: str, run: object) -> object:
        assert self.row["user_id"] == user_id
        self.transitions.append("create_run")
        self.created_runs.append({"user_id": user_id, "run": run})
        return run

    def link_backtest_job_result(
        self,
        *,
        user_id: str,
        job_id: str,
        result_run_id: str,
        execution_metadata: dict[str, object] | None = None,
        mark_succeeded: bool = False,
    ) -> dict[str, object]:
        assert self.row["user_id"] == user_id
        assert self.row["id"] == job_id
        assert mark_succeeded is True
        self.transitions.append("succeeded")
        metadata = dict(self.row.get("execution_metadata") or {})
        metadata.update(execution_metadata or {})
        self.row["status"] = "succeeded"
        self.row["result_run_id"] = result_run_id
        self.row["finished_at"] = datetime.now(timezone.utc).isoformat()
        self.row["execution_metadata"] = metadata
        return dict(self.row)

    def mark_backtest_job_failed(
        self,
        *,
        user_id: str,
        job_id: str,
        failure_code: str,
        failure_detail: str,
        retryable: bool,
        execution_metadata: dict[str, object] | None = None,
        finished_at: str | None = None,
    ) -> dict[str, object]:
        assert self.row["user_id"] == user_id
        assert self.row["id"] == job_id
        self.transitions.append("failed")
        metadata = dict(self.row.get("execution_metadata") or {})
        metadata.update(execution_metadata or {})
        self.row["status"] = "failed"
        self.row["failure_code"] = failure_code
        self.row["failure_detail"] = failure_detail
        self.row["retryable"] = retryable
        self.row["finished_at"] = finished_at
        self.row["execution_metadata"] = metadata
        self.failed_updates.append(
            {
                "failure_code": failure_code,
                "failure_detail": failure_detail,
                "retryable": retryable,
                "execution_metadata": execution_metadata,
            }
        )
        return dict(self.row)


class FakeBacktestTool:
    def __init__(self, result: dict[str, object]) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    def run(self, payload: dict[str, object]) -> dict[str, object]:
        self.calls.append(payload)
        return self.result


def _job_row(*, launch_payload: dict[str, object]) -> dict[str, object]:
    return {
        "id": str(uuid4()),
        "user_id": "user-1",
        "conversation_id": "conversation-1",
        "status": "queued",
        "attempts": 0,
        "launch_payload": launch_payload,
        "execution_metadata": {"existing": "kept"},
        "result_run_id": None,
    }


def _request_payload() -> dict[str, object]:
    return {
        "strategy_type": "buy_and_hold",
        "symbol": "AAPL",
        "symbols": ["AAPL"],
        "asset_class": "equity",
        "timeframe": "1D",
        "date_range": "past year",
        "language": "en",
    }


def _successful_tool_result() -> dict[str, object]:
    return {
        "success": True,
        "payload": {
            "envelope": {
                "resolved_strategy": {
                    "strategy_type": "buy_and_hold",
                    "asset_universe": ["AAPL"],
                    "symbol": "AAPL",
                },
                "resolved_parameters": {
                    "timeframe": "1D",
                    "date_range": "past year",
                    "benchmark_symbol": "SPY",
                },
                "metrics": {
                    "aggregate": {
                        "total_return": 0.123,
                        "total_return_pct": 12.3,
                        "performance": {"total_return_pct": 12.3},
                    }
                },
                "benchmark_metrics": {
                    "symbol": "SPY",
                    "benchmark_return_pct": 8.1,
                    "total_return": 0.081,
                    "total_return_pct": 8.1,
                },
                "provider_metadata": {"provider": "synthetic_unit_fixture"},
            },
            "result_card": {
                "title": "Apple buy and hold",
                "actions": [{"type": "save_strategy", "payload": {}}],
                "chart": {
                    "kind": "portfolio_equity",
                    "markers": [
                        {
                            "time": "2025-01-02",
                            "type": "entry",
                            "symbols": ["AAPL"],
                        }
                    ],
                },
            },
            "explanation_context": {},
        },
        "error_type": None,
        "error_message": None,
        "retryable": False,
        "capability_context": {"execution_status": "succeeded"},
    }


def test_run_backtest_job_rejects_proof_payloads() -> None:
    from workflows.backtest_job import WorkflowBacktestJobError, run_backtest_job

    job = _job_row(launch_payload={"kind": "render_workflow_proof"})
    gateway = FakeBacktestJobGateway(job)

    with pytest.raises(WorkflowBacktestJobError, match="run_backtest_job"):
        run_backtest_job(
            gateway,
            job_id=str(job["id"]),
            backtest_tool=FakeBacktestTool(_successful_tool_result()),
        )

    assert gateway.transitions == []


def test_run_backtest_job_marks_queued_job_running_then_succeeded_with_result_run() -> (
    None
):
    from workflows.backtest_job import REAL_BACKTEST_JOB_KIND, run_backtest_job

    request = _request_payload()
    job = _job_row(
        launch_payload={
            "kind": REAL_BACKTEST_JOB_KIND,
            "schema_version": "backtest_job_launch/v1",
            "request": request,
        }
    )
    gateway = FakeBacktestJobGateway(job)
    tool = FakeBacktestTool(_successful_tool_result())

    result = run_backtest_job(
        gateway,
        job_id=str(job["id"]),
        backtest_tool=tool,
        workflow_run_id="local-run",
        run_id_factory=lambda: "run-workflow",
    )

    assert result["job_id"] == job["id"]
    assert result["status"] == "succeeded"
    assert result["result_run_id"] == "run-workflow"
    assert gateway.transitions == ["running", "create_run", "succeeded"]
    assert tool.calls == [request]
    created_run = gateway.created_runs[0]["run"]
    assert created_run.id == "run-workflow"
    assert created_run.conversation_id == "conversation-1"
    assert created_run.status == "completed"
    assert created_run.symbols == ["AAPL"]
    assert created_run.benchmark_symbol == "SPY"
    assert (
        created_run.conversation_result_card["actions"][0]["payload"]["run_id"]
        == "run-workflow"
    )
    assert gateway.row["result_run_id"] == "run-workflow"
    assert gateway.row["execution_metadata"]["existing"] == "kept"
    assert (
        gateway.row["execution_metadata"]["workflow_backtest"]["workflow_run_id"]
        == "local-run"
    )


def test_run_backtest_job_persists_backend_result_readout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime.result_readout import ResultReadout

    from workflows import backtest_job as workflow_module
    from workflows.backtest_job import REAL_BACKTEST_JOB_KIND, run_backtest_job

    readout = (
        "**Quick take**\n\n"
        "Backend generated readout.\n\n"
        "- Tested: AAPL buy and hold."
    )
    monkeypatch.setattr(
        workflow_module,
        "result_readout_with_metadata_from_backtest_payload",
        lambda **kwargs: ResultReadout(
            text=readout,
            source="llm_explain_stage",
            fallback_used=False,
        ),
    )
    job = _job_row(
        launch_payload={
            "kind": REAL_BACKTEST_JOB_KIND,
            "schema_version": "backtest_job_launch/v1",
            "request": _request_payload(),
        }
    )
    gateway = FakeBacktestJobGateway(job)

    result = run_backtest_job(
        gateway,
        job_id=str(job["id"]),
        backtest_tool=FakeBacktestTool(_successful_tool_result()),
        workflow_run_id="local-run",
        run_id_factory=lambda: "run-workflow",
    )

    assert result["result_readout"] == readout
    metadata = gateway.row["execution_metadata"]["workflow_backtest"]
    assert metadata["result_readout"] == readout
    assert metadata["result_readout_source"] == "llm_explain_stage"
    assert metadata["result_readout_fallback_used"] is False


def test_run_backtest_job_uses_mainline_llm_quick_take_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime.stages import explain as explain_module

    from workflows.backtest_job import REAL_BACKTEST_JOB_KIND, run_backtest_job

    async def fake_quick_take_plan(**_: object) -> dict[str, object]:
        return {
            "relative_performance_claim": "beat_benchmark",
            "takeaway": (
                "AAPL beat SPY by 4.2 percentage points in this historical test."
            ),
            "tested_bullet": "Tested AAPL buy and hold over the requested window.",
            "meaning_bullet": "The result is grounded in the completed backtest run.",
            "next_check_bullet": None,
            "assumption_bullet": None,
            "caveat_bullet": "Historical simulation only.",
            "next_experiment_option_kinds": [],
            "fact_ids": [
                "tested_summary",
                "total_return",
                "benchmark_return",
                "benchmark_comparison",
                "benchmark_symbol",
                "caveat",
            ],
        }

    monkeypatch.setattr(
        explain_module,
        "invoke_openrouter_json_schema",
        fake_quick_take_plan,
    )
    job = _job_row(
        launch_payload={
            "kind": REAL_BACKTEST_JOB_KIND,
            "schema_version": "backtest_job_launch/v1",
            "request": _request_payload(),
        }
    )
    gateway = FakeBacktestJobGateway(job)

    result = run_backtest_job(
        gateway,
        job_id=str(job["id"]),
        backtest_tool=FakeBacktestTool(_successful_tool_result()),
        workflow_run_id="local-run",
        run_id_factory=lambda: "run-workflow",
    )

    assert "AAPL beat SPY by 4.2 percentage points" in result["result_readout"]
    metadata = gateway.row["execution_metadata"]["workflow_backtest"]
    assert metadata["result_readout_source"] == "llm_explain_stage"
    assert metadata["result_readout_fallback_used"] is False


def test_run_backtest_job_marks_result_readout_fallback_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime.stages import explain as explain_module

    from workflows.backtest_job import REAL_BACKTEST_JOB_KIND, run_backtest_job

    async def failing_quick_take_plan(**_: object) -> dict[str, object]:
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(
        explain_module,
        "invoke_openrouter_json_schema",
        failing_quick_take_plan,
    )
    job = _job_row(
        launch_payload={
            "kind": REAL_BACKTEST_JOB_KIND,
            "schema_version": "backtest_job_launch/v1",
            "request": _request_payload(),
        }
    )
    gateway = FakeBacktestJobGateway(job)

    result = run_backtest_job(
        gateway,
        job_id=str(job["id"]),
        backtest_tool=FakeBacktestTool(_successful_tool_result()),
        workflow_run_id="local-run",
        run_id_factory=lambda: "run-workflow",
    )

    assert result["result_readout"].startswith("**Quick take**")
    metadata = gateway.row["execution_metadata"]["workflow_backtest"]
    assert metadata["result_readout_source"] == "deterministic_fallback"
    assert metadata["result_readout_fallback_used"] is True


def test_run_backtest_job_marks_tool_failure_with_structured_metadata() -> None:
    from workflows.backtest_job import REAL_BACKTEST_JOB_KIND, run_backtest_job

    job = _job_row(
        launch_payload={
            "kind": REAL_BACKTEST_JOB_KIND,
            "schema_version": "backtest_job_launch/v1",
            "request": _request_payload(),
        }
    )
    gateway = FakeBacktestJobGateway(job)
    tool = FakeBacktestTool(
        {
            "success": False,
            "payload": None,
            "error_type": "upstream_dependency_error",
            "error_message": "Market data is temporarily unavailable.",
            "retryable": True,
            "capability_context": {"failure_detail": "market_data_issue"},
        }
    )

    result = run_backtest_job(
        gateway,
        job_id=str(job["id"]),
        backtest_tool=tool,
        workflow_run_id="local-run",
    )

    assert result["job_id"] == job["id"]
    assert result["status"] == "failed"
    assert result["failure_code"] == "upstream_dependency_error"
    assert result["failure_detail"] == "market_data_issue"
    assert result["retryable"] is True
    assert gateway.transitions == ["running", "failed"]
    assert gateway.created_runs == []
    assert gateway.row["failure_code"] == "upstream_dependency_error"
    assert gateway.row["failure_detail"] == "market_data_issue"
    assert gateway.row["retryable"] is True
    assert (
        gateway.row["execution_metadata"]["workflow_backtest"]["failure_category"]
        == "upstream_dependency_error"
    )


def test_backtest_workflow_json_safe_normalizes_postgres_scalars() -> None:
    from workflows.backtest_job import _json_safe

    user_id = uuid4()
    created_at = datetime(2026, 6, 6, 12, 30, tzinfo=timezone.utc)
    payload = {
        "id": user_id,
        "created_at": created_at,
        "nested": {"date": date(2026, 6, 6), "uuids": [UUID(str(user_id))]},
    }

    assert _json_safe(payload) == {
        "id": str(user_id),
        "created_at": created_at.isoformat(),
        "nested": {"date": "2026-06-06", "uuids": [str(user_id)]},
    }


def test_workflow_task_registration_includes_proof_and_real_backtest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tasks: dict[str, dict[str, object]] = {}

    class FakeRetry:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    class FakeWorkflows:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

        def task(self, fn: object | None = None, **kwargs: object):
            def decorate(inner: object) -> object:
                name = str(kwargs.get("name") or getattr(inner, "__name__", "task"))
                tasks[name] = {"fn": inner, "kwargs": dict(kwargs)}
                return inner

            if fn is not None:
                return decorate(fn)
            return decorate

        def start(self) -> None:
            return None

    fake_render_sdk = ModuleType("render_sdk")
    fake_render_sdk.Retry = FakeRetry
    fake_render_sdk.Workflows = FakeWorkflows
    monkeypatch.setitem(sys.modules, "render_sdk", fake_render_sdk)
    sys.modules.pop("workflows.main", None)

    importlib.import_module("workflows.main")

    assert {"workflow_proof", "run_backtest_job"}.issubset(tasks)
    assert tasks["workflow_proof"]["kwargs"]["timeout_seconds"] == 60
    assert tasks["run_backtest_job"]["kwargs"]["timeout_seconds"] >= 300
