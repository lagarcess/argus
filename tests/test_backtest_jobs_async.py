from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from argus.agent_runtime.stages.execute import execute_stage
from argus.agent_runtime.state.models import RunState
from argus.api.chat.backtest_jobs import (
    BacktestJobShadowContext,
    ShadowBacktestJobTool,
    backtest_job_shadow_context,
)
from argus.api.main import app
from argus.api.schemas import BacktestRun, OnboardingState, User
from fastapi.testclient import TestClient


class _DelegateTool:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.calls: list[dict[str, object]] = []

    def run(self, payload: dict[str, object]) -> dict[str, object]:
        self.events.append("delegate")
        self.calls.append(payload)
        return {"success": True, "payload": {"result": "in-process"}}


class _Gateway:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.jobs: list[dict[str, object]] = []
        self.metadata_updates: list[dict[str, object]] = []

    def create_backtest_job(self, **payload: object) -> dict[str, object]:
        self.events.append("job")
        job = {
            "id": "job-async-1",
            "status": "queued",
            "result_run_id": None,
            "failure_code": None,
            "failure_detail": None,
            "retryable": False,
            "queued_at": "2026-06-06T12:00:00+00:00",
            "created_at": "2026-06-06T12:00:00+00:00",
            "updated_at": "2026-06-06T12:00:00+00:00",
            **payload,
        }
        self.jobs.append(job)
        return job

    def admit_backtest_job(self, **payload: object) -> dict[str, object]:
        self.events.append("job")
        job = {
            "id": "job-async-1",
            "status": str(payload.get("initial_status") or "queued"),
            "result_run_id": None,
            "failure_code": None,
            "failure_detail": None,
            "retryable": False,
            "queued_at": "2026-06-06T12:00:00+00:00",
            "created_at": "2026-06-06T12:00:00+00:00",
            "updated_at": "2026-06-06T12:00:00+00:00",
            **{
                key: value
                for key, value in payload.items()
                if key not in ("initial_status", "simulation_day_limit")
            },
        }
        self.jobs.append(job)
        return {"decision": "admitted", "job": job}

    def merge_backtest_job_execution_metadata(
        self, **payload: object
    ) -> dict[str, object]:
        self.events.append("metadata")
        self.metadata_updates.append(payload)
        return {"id": payload["job_id"], **payload}

    def count_backtest_jobs(
        self,
        *,
        status: str,
        user_id: str | None = None,
        limit: int = 100,
    ) -> int:
        del status, user_id, limit
        return 0


class _Dispatcher:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.calls: list[dict[str, object]] = []

    def dispatch(self, **payload: object) -> dict[str, object]:
        self.events.append("dispatch")
        self.calls.append(payload)
        return {"id": "task-run-real-1", "status": "pending"}


class _AsyncJobTool:
    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        del payload
        return {
            "success": True,
            "payload": {
                "backtest_job": {
                    "id": "job-async-1",
                    "conversation_id": "conversation-1",
                    "request_message_id": "message-1",
                    "confirmation_message_id": "confirmation-message-1",
                    "status": "queued",
                    "result_run_id": None,
                    "failure_code": None,
                    "failure_detail": None,
                    "retryable": False,
                }
            },
            "error_type": None,
            "error_message": None,
            "retryable": False,
            "capability_context": {"execution_status": "queued"},
        }


class _HydrationGateway:
    def __init__(self) -> None:
        self.user = User(
            id="user-1",
            email="mock@example.com",
            username=None,
            display_name="Mock Developer",
            language="en",
            locale="en-US",
            theme="dark",
            is_admin=True,
            onboarding=OnboardingState(completed=True, stage="completed"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.run = _run()

    def get_or_create_mock_user(self) -> User:
        return self.user

    def get_backtest_job(self, *, user_id: str, job_id: str) -> dict[str, object] | None:
        if user_id != self.user.id or job_id != "job-async-1":
            return None
        return {
            "id": "job-async-1",
            "conversation_id": "conversation-1",
            "request_message_id": "message-1",
            "confirmation_message_id": "confirmation-message-1",
            "status": "succeeded",
            "result_run_id": self.run.id,
            "failure_code": None,
            "failure_detail": None,
            "retryable": False,
            "queued_at": "2026-06-06T12:00:00+00:00",
            "started_at": "2026-06-06T12:00:01+00:00",
            "finished_at": "2026-06-06T12:00:04+00:00",
            "created_at": "2026-06-06T12:00:00+00:00",
            "updated_at": "2026-06-06T12:00:04+00:00",
            "execution_metadata": {
                "workflow_backtest": {
                    "result_readout": (
                        "**Quick take**\n\n"
                        "Backend generated readout.\n\n"
                        "- Tested: AAPL buy and hold."
                    ),
                    "result_readout_source": "llm_explain_stage",
                    "result_readout_fallback_used": False,
                }
            },
        }

    def get_backtest_run(self, *, user_id: str, run_id: str) -> BacktestRun | None:
        if user_id != self.user.id or run_id != self.run.id:
            return None
        return self.run


class _TimedOutJobGateway:
    def __init__(self) -> None:
        self.user = User(
            id="user-1",
            email="mock@example.com",
            username=None,
            display_name="Mock Developer",
            language="en",
            locale="en-US",
            theme="dark",
            is_admin=True,
            onboarding=OnboardingState(completed=True, stage="completed"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.job: dict[str, object] = {
            "id": "job-timeout-1",
            "conversation_id": "conversation-1",
            "request_message_id": "message-1",
            "confirmation_message_id": "confirmation-message-1",
            "status": "running",
            "result_run_id": None,
            "failure_code": None,
            "failure_detail": None,
            "retryable": False,
            "queued_at": "2026-06-06T12:00:00+00:00",
            "started_at": "2026-06-06T12:00:10+00:00",
            "finished_at": None,
            "created_at": "2026-06-06T12:00:00+00:00",
            "updated_at": "2026-06-06T12:00:10+00:00",
            "execution_metadata": {
                "workflow_dispatch": {
                    "task": "argus-backtests/run_backtest_job",
                    "task_run_id": "trn-timeout-1",
                    "status": "pending",
                    "dispatched_at": "2026-06-06T12:00:01+00:00",
                },
                "workflow_backtest": {
                    "kind": "run_backtest_job",
                    "workflow_run_id": "trn-timeout-1",
                    "started_at": "2026-06-06T12:00:10+00:00",
                },
            },
        }
        self.failed_updates: list[dict[str, object]] = []

    def get_or_create_mock_user(self) -> User:
        return self.user

    def get_backtest_job(self, *, user_id: str, job_id: str) -> dict[str, object] | None:
        if user_id != self.user.id or job_id != self.job["id"]:
            return None
        return dict(self.job)

    def get_backtest_run(self, *, user_id: str, run_id: str) -> BacktestRun | None:
        del user_id, run_id
        return None

    def mark_backtest_job_failed(self, **payload: object) -> dict[str, object]:
        self.failed_updates.append(payload)
        execution_metadata = dict(self.job.get("execution_metadata") or {})
        execution_metadata.update(dict(payload.get("execution_metadata") or {}))
        self.job.update(
            {
                "status": "failed",
                "failure_code": payload["failure_code"],
                "failure_detail": payload["failure_detail"],
                "retryable": payload["retryable"],
                "finished_at": payload.get("finished_at"),
                "execution_metadata": execution_metadata,
            }
        )
        return dict(self.job)


class _FakeTerminalTaskRunClient:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls: list[str] = []

    def get_task_run(self, task_run_id: str) -> dict[str, object]:
        self.calls.append(task_run_id)
        return dict(self.payload)


class _StaleJobScanGateway:
    def __init__(self) -> None:
        self.jobs: list[dict[str, object]] = [
            {
                "id": "job-stale-running",
                "user_id": "user-1",
                "status": "running",
                "queued_at": "2026-06-06T12:00:00+00:00",
                "started_at": "2026-06-06T12:01:00+00:00",
                "updated_at": "2026-06-06T12:01:00+00:00",
                "execution_metadata": {
                    "workflow_dispatch": {"task_run_id": "trn-stale-1"}
                },
            },
            {
                "id": "job-fresh-queued",
                "user_id": "user-1",
                "status": "queued",
                "queued_at": "2026-06-06T12:28:00+00:00",
                "created_at": "2026-06-06T12:28:00+00:00",
                "updated_at": "2026-06-06T12:28:00+00:00",
                "execution_metadata": {
                    "workflow_dispatch": {"task_run_id": "trn-fresh-1"}
                },
            },
        ]
        self.failed_updates: list[dict[str, object]] = []
        self.list_calls: list[dict[str, object]] = []

    def list_backtest_jobs(
        self,
        *,
        status: str,
        user_id: str | None = None,
        limit: int = 100,
        oldest_first: bool = False,
    ) -> list[dict[str, object]]:
        self.list_calls.append(
            {
                "status": status,
                "user_id": user_id,
                "limit": limit,
                "oldest_first": oldest_first,
            }
        )
        jobs = [
            dict(job)
            for job in self.jobs
            if job.get("status") == status
            and (user_id is None or job.get("user_id") == user_id)
        ]
        return jobs[:limit]

    def mark_backtest_job_failed(self, **payload: object) -> dict[str, object]:
        self.failed_updates.append(payload)
        for job in self.jobs:
            if job["id"] == payload["job_id"]:
                execution_metadata = dict(job.get("execution_metadata") or {})
                execution_metadata.update(dict(payload.get("execution_metadata") or {}))
                job.update(
                    {
                        "status": "failed",
                        "failure_code": payload["failure_code"],
                        "failure_detail": payload["failure_detail"],
                        "retryable": payload["retryable"],
                        "finished_at": payload.get("finished_at"),
                        "execution_metadata": execution_metadata,
                    }
                )
                return dict(job)
        raise AssertionError("unknown job")


def _payload() -> dict[str, object]:
    return {
        "strategy_type": "buy_and_hold",
        "symbol": "AAPL",
        "symbols": ["AAPL"],
        "asset_class": "equity",
        "timeframe": "1D",
        "date_range": "past year",
        "language": "en",
    }


def _context() -> BacktestJobShadowContext:
    return BacktestJobShadowContext(
        user_id="user-1",
        conversation_id="conversation-1",
        request_message_id="message-1",
        confirmation_message_id="confirmation-message-1",
        idempotency_key="idem-1",
        request_id="request-1",
        chat_action={
            "type": "run_backtest",
            "payload": {"confirmation_id": "confirmation-1"},
        },
    )


def _run() -> BacktestRun:
    return BacktestRun(
        id="run-workflow-1",
        conversation_id="conversation-1",
        strategy_id=None,
        status="completed",
        asset_class="equity",
        symbols=["AAPL"],
        allocation_method="equal_weight",
        benchmark_symbol="SPY",
        metrics={"aggregate": {"performance": {"total_return_pct": 12.4}}},
        config_snapshot={"template": "buy_and_hold", "benchmark_symbol": "SPY"},
        conversation_result_card={
            "title": "AAPL buy and hold",
            "date_range": {
                "start": "2025-06-06",
                "end": "2026-06-06",
                "display": "June 6, 2025 to June 6, 2026",
            },
            "status_label": "Simulation Complete",
            "rows": [
                {
                    "key": "total_return_pct",
                    "label": "Total return",
                    "value": "+12.4%",
                }
            ],
            "assumptions": ["Long-only", "Benchmark: SPY"],
            "actions": [],
        },
        created_at=datetime.now(timezone.utc),
        chart=None,
        trades=[],
    )


@pytest.fixture(autouse=True)
def _mock_auth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARGUS_MOCK_AUTH", "true")
    monkeypatch.setenv("ARGUS_DEV_MEMORY_FALLBACK", "false")


def test_real_workflow_mode_returns_async_job_without_delegate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_BACKTEST_JOBS_SHADOW_ENABLED", "true")
    monkeypatch.setenv("ARGUS_BACKTEST_JOBS_DISPATCH_ENABLED", "true")
    monkeypatch.setenv("ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED", "true")
    monkeypatch.delenv("ARGUS_BACKTEST_REAL_WORKFLOW_TASK", raising=False)
    events: list[str] = []
    gateway = _Gateway(events)
    dispatcher = _Dispatcher(events)
    delegate = _DelegateTool(events)
    tool = ShadowBacktestJobTool(
        delegate=delegate,
        gateway_getter=lambda: gateway,
        dev_memory_fallback_getter=lambda: False,
        dispatcher_getter=lambda: dispatcher,
    )

    with backtest_job_shadow_context(_context()):
        result = tool.run(_payload())

    assert result["success"] is True
    assert result["payload"]["backtest_job"]["id"] == "job-async-1"
    assert result["payload"]["backtest_job"]["status"] == "queued"
    assert events == ["job", "dispatch", "metadata"]
    assert delegate.calls == []
    assert gateway.jobs[0]["launch_payload"]["kind"] == "run_backtest_job"
    assert (
        gateway.metadata_updates[0]["execution_metadata"]["workflow_dispatch"]["task"]
        == "argus-backtests/run_backtest_job"
    )


def test_execute_stage_returns_job_artifact_without_result_explanation() -> None:
    state = RunState.new(current_user_message="Run it", recent_thread_history=[])
    state.confirmation_payload = {
        "strategy_type": "buy_and_hold",
        "symbol": "AAPL",
        "symbols": ["AAPL"],
        "asset_class": "equity",
        "date_range": "past year",
    }

    result = execute_stage(state=state, tool=_AsyncJobTool(), max_retries=1)

    assert result.outcome == "ready_to_respond"
    assert result.patch["backtest_job"]["id"] == "job-async-1"
    assert result.patch["final_response_payload"]["backtest_job"]["id"] == ("job-async-1")
    assert "started" in result.patch["assistant_response"].lower()
    assert result.patch["artifact_references"][0]["artifact_kind"] == "backtest_job"


def test_backtest_job_status_endpoint_returns_job_and_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api import state as api_state

    monkeypatch.setattr(api_state, "supabase_gateway", _HydrationGateway())
    client = TestClient(app)

    response = client.get("/api/v1/backtest-jobs/job-async-1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["job"]["status"] == "succeeded"
    assert payload["job"]["result_run_id"] == "run-workflow-1"
    assert payload["run"]["id"] == "run-workflow-1"
    assert payload["run"]["conversation_result_card"]["title"] == "AAPL buy and hold"
    assert payload["result_readout"].startswith("**Quick take**")
    assert "Backend generated readout" in payload["result_readout"]
    assert payload["result_readout_source"] == "llm_explain_stage"
    assert payload["result_readout_fallback_used"] is False


def test_backtest_job_status_does_not_return_run_for_failed_finalization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api import state as api_state

    class _FailedFinalizationHydrationGateway(_HydrationGateway):
        def get_backtest_job(
            self,
            *,
            user_id: str,
            job_id: str,
        ) -> dict[str, object] | None:
            job = super().get_backtest_job(user_id=user_id, job_id=job_id)
            assert job is not None
            return {
                **job,
                "status": "failed",
                "result_run_id": "run-workflow-1",
                "failure_code": "finalization_failed",
                "failure_detail": "execution_failed",
                "retryable": True,
            }

        def get_backtest_run(
            self,
            *,
            user_id: str,
            run_id: str,
        ) -> BacktestRun | None:
            raise AssertionError("failed finalization must not hydrate a run")

    gateway = _FailedFinalizationHydrationGateway()
    monkeypatch.setattr(api_state, "supabase_gateway", gateway)
    client = TestClient(app)

    response = client.get("/api/v1/backtest-jobs/job-async-1")

    assert response.status_code == 200
    assert response.json()["job"]["status"] == "failed"
    assert response.json()["run"] is None


def test_terminal_render_task_timeout_reconciles_running_job() -> None:
    from argus.api.chat.backtest_jobs import reconcile_terminal_render_task_run

    gateway = _TimedOutJobGateway()
    task_client = _FakeTerminalTaskRunClient(
        {
            "id": "trn-timeout-1",
            "status": "failed",
            "error": "task timed out",
            "completedAt": "2026-06-06T12:01:10Z",
        }
    )

    reconciled = reconcile_terminal_render_task_run(
        gateway=gateway,
        user_id="user-1",
        job=gateway.get_backtest_job(user_id="user-1", job_id="job-timeout-1"),
        task_run_client=task_client,
    )

    assert task_client.calls == ["trn-timeout-1"]
    assert reconciled["status"] == "failed"
    assert reconciled["failure_code"] == "workflow_task_timeout"
    assert reconciled["retryable"] is True
    assert gateway.failed_updates[0]["failure_detail"] == (
        "Backtest execution timed out before finishing."
    )
    metadata = reconciled["execution_metadata"]
    assert metadata["workflow_dispatch"]["status"] == "failed"
    assert metadata["workflow_dispatch"]["error"] == "task timed out"
    assert metadata["workflow_backtest"]["workflow_run_status"] == "failed"
    assert metadata["workflow_backtest"]["workflow_run_error"] == "task timed out"


def test_terminal_render_task_cancellation_reconciles_as_non_retryable() -> None:
    from argus.api.chat.backtest_jobs import reconcile_terminal_render_task_run

    gateway = _TimedOutJobGateway()
    task_client = _FakeTerminalTaskRunClient(
        {
            "id": "trn-timeout-1",
            "status": "canceled",
            "error": "canceled by operator",
            "completedAt": "2026-06-06T12:01:10Z",
        }
    )

    reconciled = reconcile_terminal_render_task_run(
        gateway=gateway,
        user_id="user-1",
        job=gateway.get_backtest_job(user_id="user-1", job_id="job-timeout-1"),
        task_run_client=task_client,
    )

    assert reconciled["status"] == "failed"
    assert reconciled["failure_code"] == "workflow_task_canceled"
    assert reconciled["retryable"] is False
    assert gateway.failed_updates[0]["failure_detail"] == (
        "Backtest execution was canceled before finishing."
    )


def test_terminal_render_task_expiration_reconciles_as_retryable() -> None:
    from argus.api.chat.backtest_jobs import reconcile_terminal_render_task_run

    gateway = _TimedOutJobGateway()
    task_client = _FakeTerminalTaskRunClient(
        {
            "id": "trn-timeout-1",
            "status": "expired",
            "error": "task expired",
            "completedAt": "2026-06-06T12:01:10Z",
        }
    )

    reconciled = reconcile_terminal_render_task_run(
        gateway=gateway,
        user_id="user-1",
        job=gateway.get_backtest_job(user_id="user-1", job_id="job-timeout-1"),
        task_run_client=task_client,
    )

    assert reconciled["status"] == "failed"
    assert reconciled["failure_code"] == "workflow_task_expired"
    assert reconciled["retryable"] is True
    assert gateway.failed_updates[0]["failure_detail"] == (
        "Backtest execution expired before finishing."
    )


def test_terminal_render_task_reconciliation_ignores_malformed_metadata() -> None:
    from argus.api.chat.backtest_jobs import reconcile_terminal_render_task_run

    gateway = _TimedOutJobGateway()
    job = gateway.get_backtest_job(user_id="user-1", job_id="job-timeout-1")
    assert job is not None
    job["execution_metadata"] = {"workflow_dispatch": "not-json-object"}
    task_client = _FakeTerminalTaskRunClient(
        {
            "id": "trn-timeout-1",
            "status": "failed",
            "error": "task timed out",
        }
    )

    reconciled = reconcile_terminal_render_task_run(
        gateway=gateway,
        user_id="user-1",
        job=job,
        task_run_client=task_client,
    )

    assert reconciled == job
    assert task_client.calls == []
    assert gateway.failed_updates == []


def test_backtest_job_status_endpoint_reconciles_terminal_workflow_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api import state as api_state
    from argus.api.chat import backtest_jobs as backtest_job_helpers

    gateway = _TimedOutJobGateway()
    monkeypatch.setattr(
        backtest_job_helpers,
        "RenderTaskRunClient",
        lambda: _FakeTerminalTaskRunClient(
            {
                "id": "trn-timeout-1",
                "status": "failed",
                "error": "task timed out",
                "completedAt": "2026-06-06T12:01:10Z",
            }
        ),
    )
    monkeypatch.setattr(api_state, "supabase_gateway", gateway)
    client = TestClient(app)

    response = client.get("/api/v1/backtest-jobs/job-timeout-1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["job"]["status"] == "failed"
    assert payload["job"]["failure_code"] == "workflow_task_timeout"
    assert payload["job"]["retryable"] is True


def test_stale_backtest_job_scan_reconciles_terminal_task_run() -> None:
    from argus.api.chat.backtest_jobs import scan_stale_backtest_jobs

    gateway = _StaleJobScanGateway()
    task_client = _FakeTerminalTaskRunClient(
        {
            "id": "trn-stale-1",
            "status": "failed",
            "error": "task timed out",
            "completedAt": "2026-06-06T12:03:00Z",
        }
    )

    report = scan_stale_backtest_jobs(
        gateway=gateway,
        now=datetime(2026, 6, 6, 12, 30, tzinfo=timezone.utc),
        queued_age_seconds=900,
        running_age_seconds=900,
        limit=20,
        task_run_client=task_client,
    )

    assert task_client.calls == ["trn-stale-1"]
    assert gateway.list_calls == [
        {
            "status": "queued",
            "user_id": None,
            "limit": 20,
            "oldest_first": True,
        },
        {
            "status": "running",
            "user_id": None,
            "limit": 20,
            "oldest_first": True,
        },
    ]
    assert gateway.failed_updates[0]["job_id"] == "job-stale-running"
    assert report["status"] == "ready"
    assert report["stale_count"] == 1
    assert report["reconciled_count"] == 1
    assert report["unresolved_count"] == 0


def test_stale_backtest_job_scan_reports_unresolved_jobs_without_task_metadata() -> None:
    from argus.api.chat.backtest_jobs import scan_stale_backtest_jobs

    gateway = _StaleJobScanGateway()
    gateway.jobs[0]["execution_metadata"] = {}
    task_client = _FakeTerminalTaskRunClient(
        {
            "id": "trn-stale-1",
            "status": "failed",
            "error": "task timed out",
        }
    )

    report = scan_stale_backtest_jobs(
        gateway=gateway,
        now=datetime(2026, 6, 6, 12, 30, tzinfo=timezone.utc),
        queued_age_seconds=900,
        running_age_seconds=900,
        limit=20,
        task_run_client=task_client,
    )

    assert task_client.calls == []
    assert report["status"] == "degraded"
    assert report["reconciled_count"] == 0
    assert report["unresolved_count"] == 1
    assert report["unresolved_jobs"] == [
        {
            "id": "job-stale-running",
            "status": "running",
            "user_id": "user-1",
            "age_seconds": 1740,
            "task_run_id": None,
        }
    ]


def test_stale_backtest_job_scan_fails_stale_proof_jobs_without_task_metadata() -> None:
    from argus.api.chat.backtest_jobs import scan_stale_backtest_jobs

    gateway = _StaleJobScanGateway()
    gateway.jobs = [
        {
            "id": "job-stale-proof",
            "user_id": "user-1",
            "status": "queued",
            "queued_at": "2026-06-06T12:00:00+00:00",
            "created_at": "2026-06-06T12:00:00+00:00",
            "updated_at": "2026-06-06T12:00:00+00:00",
            "launch_payload": {"kind": "render_workflow_proof"},
            "execution_metadata": {},
        }
    ]
    task_client = _FakeTerminalTaskRunClient(
        {
            "id": "trn-stale-1",
            "status": "failed",
            "error": "task timed out",
        }
    )

    report = scan_stale_backtest_jobs(
        gateway=gateway,
        now=datetime(2026, 6, 6, 12, 30, tzinfo=timezone.utc),
        queued_age_seconds=900,
        running_age_seconds=900,
        limit=20,
        task_run_client=task_client,
    )

    assert task_client.calls == []
    assert report["status"] == "ready"
    assert report["stale_count"] == 1
    assert report["reconciled_count"] == 1
    assert report["unresolved_count"] == 0
    assert gateway.failed_updates[0]["job_id"] == "job-stale-proof"
    assert gateway.failed_updates[0]["failure_code"] == "workflow_dispatch_missing"
    assert gateway.failed_updates[0]["retryable"] is True
