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
                    )
                }
            },
        }

    def get_backtest_run(self, *, user_id: str, run_id: str) -> BacktestRun | None:
        if user_id != self.user.id or run_id != self.run.id:
            return None
        return self.run


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
