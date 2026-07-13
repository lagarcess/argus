from __future__ import annotations

import importlib
import sys
from datetime import date, datetime, timezone
from types import ModuleType
from uuid import UUID, uuid4

import pytest
from argus.domain.backtest_finalization import (
    BacktestFinalizationInput,
    MemoryBacktestFinalizationGateway,
    PreparedBacktestFinalization,
    finalize_backtest_completion,
    stable_backtest_run_id,
)
from argus.domain.store import AlphaStore, utcnow


class FakeBacktestJobGateway:
    def __init__(self, row: dict[str, object]) -> None:
        self.row = dict(row)
        self.transitions: list[str] = []
        self.failed_updates: list[dict[str, object]] = []
        self.route_receipts: list[dict[str, object]] = []
        self.cost_ledger_entries: list[dict[str, object]] = []
        self.finalization_store = AlphaStore()
        self.finalization_calls: list[PreparedBacktestFinalization] = []
        self.fail_finalization_after_commit_once = False
        self.fail_result_link_once = False
        self.fail_result_link_after_commit_once = False

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
        self.row["result_run_id"] = None
        self.row["finished_at"] = None
        self.row["failure_code"] = None
        self.row["failure_detail"] = None
        self.row["retryable"] = False
        self.row["execution_metadata"] = execution_metadata
        return dict(self.row)

    def finalize_backtest_completion(
        self,
        *,
        finalization: PreparedBacktestFinalization,
    ):
        self.transitions.append("finalize")
        self.finalization_calls.append(finalization)
        finalized = MemoryBacktestFinalizationGateway(
            self.finalization_store
        ).finalize_backtest_completion(finalization=finalization)
        if self.fail_finalization_after_commit_once:
            self.fail_finalization_after_commit_once = False
            raise RuntimeError("finalization response lost")
        return finalized

    def merge_backtest_job_execution_metadata(
        self,
        *,
        user_id: str,
        job_id: str,
        execution_metadata: dict[str, object],
    ) -> dict[str, object]:
        assert self.row["user_id"] == user_id
        assert self.row["id"] == job_id
        self.row["execution_metadata"] = execution_metadata
        return dict(self.row)

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
        if self.fail_result_link_once:
            self.fail_result_link_once = False
            raise RuntimeError("job result link unavailable")
        self.transitions.append("succeeded")
        metadata = dict(self.row.get("execution_metadata") or {})
        metadata.update(execution_metadata or {})
        self.row["status"] = "succeeded"
        self.row["result_run_id"] = result_run_id
        self.row["failure_code"] = None
        self.row["failure_detail"] = None
        self.row["retryable"] = False
        self.row["finished_at"] = datetime.now(timezone.utc).isoformat()
        self.row["execution_metadata"] = metadata
        if self.fail_result_link_after_commit_once:
            self.fail_result_link_after_commit_once = False
            raise RuntimeError("job result link response lost")
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
        self.row["result_run_id"] = None
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

    def create_route_receipt(
        self,
        *,
        user_id: str | None,
        receipt: dict[str, object],
        conversation_id: str | None = None,
        run_id: str | None = None,
        message_id: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> dict[str, object]:
        row = {
            "id": f"receipt-{len(self.route_receipts) + 1}",
            "user_id": user_id,
            "conversation_id": conversation_id,
            "run_id": run_id,
            "message_id": message_id,
            "metadata": metadata or {},
            **receipt,
        }
        self.route_receipts.append(row)
        return row

    def create_cost_ledger_entry(self, *, entry: dict[str, object]) -> dict[str, object]:
        row = {"id": f"ledger-{len(self.cost_ledger_entries) + 1}", **entry}
        self.cost_ledger_entries.append(row)
        return row


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


def _successful_tool_result_with_timings() -> dict[str, object]:
    result = _successful_tool_result()
    result["execution_metadata"] = {
        "timings_ms": {
            "provider_fetch_total": 12.3456,
            "engine_compute_total": 45.6789,
            "chart_result_build_total": 7.8912,
        }
    }
    return result


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


def test_postgres_backtest_job_gateway_reuses_connection_in_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from workflows.backtest_job import PostgresBacktestJobGateway

    connect_calls = 0

    class FakeCursor:
        def __init__(self) -> None:
            self.query = ""

        def __enter__(self) -> FakeCursor:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def execute(self, query: str, params: object = None) -> None:
            del params
            self.query = query

        def fetchone(self) -> dict[str, object]:
            if "select *" in self.query.lower():
                return {"id": "job-1", "execution_metadata": {}}
            return {"id": "job-1", "execution_metadata": {"kept": True}}

    class FakeConnection:
        def __enter__(self) -> FakeConnection:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def cursor(self) -> FakeCursor:
            return FakeCursor()

    def fake_connect(self: PostgresBacktestJobGateway) -> FakeConnection:
        del self
        nonlocal connect_calls
        connect_calls += 1
        return FakeConnection()

    monkeypatch.setattr(PostgresBacktestJobGateway, "_connect", fake_connect)
    gateway = PostgresBacktestJobGateway("postgres://example")

    with gateway:
        assert gateway.fetch_job("job-1") == {"id": "job-1", "execution_metadata": {}}
        assert gateway.merge_backtest_job_execution_metadata(
            user_id="user-1",
            job_id="job-1",
            execution_metadata={"kept": True},
        ) == {"id": "job-1", "execution_metadata": {"kept": True}}

    assert connect_calls == 1


def test_postgres_backtest_job_gateway_rejects_running_job_claim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from workflows.backtest_job import (
        PostgresBacktestJobGateway,
        WorkflowBacktestJobError,
    )

    captured: dict[str, str] = {}

    class FakeCursor:
        def __enter__(self) -> FakeCursor:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def execute(self, query: str, params: object = None) -> None:
            del params
            captured["query"] = " ".join(query.split())

        def fetchone(self) -> dict[str, object] | None:
            if "status in ('queued', 'running')" in captured["query"]:
                return {"id": "job-1", "status": "running"}
            return None

    class FakeConnection:
        def __enter__(self) -> FakeConnection:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def cursor(self) -> FakeCursor:
            return FakeCursor()

    monkeypatch.setattr(
        PostgresBacktestJobGateway,
        "_connect",
        lambda _self: FakeConnection(),
    )
    gateway = PostgresBacktestJobGateway("postgres://example")

    with pytest.raises(WorkflowBacktestJobError, match="cannot be started or retried"):
        gateway.mark_backtest_job_running(
            user_id="user-1",
            job_id="job-1",
            execution_metadata={"workflow_run_id": "overlap"},
        )

    assert "status = 'queued'" in captured["query"]
    assert "status in ('queued', 'running')" not in captured["query"]
    assert "status = 'failed'" in captured["query"]
    assert "failure_code = 'finalization_failed'" in captured["query"]


def test_postgres_backtest_job_gateway_appends_cost_ledger_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from workflows.backtest_job import PostgresBacktestJobGateway

    captured: dict[str, object] = {}

    class FakeCursor:
        def __enter__(self) -> FakeCursor:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def execute(self, query: str, params: object = None) -> None:
            captured["query"] = query
            captured["params"] = params

        def fetchone(self) -> dict[str, object]:
            return {
                "id": "ledger-1",
                "source": "render_workflow",
                "correlation_id": "workflow:render-run:job-1:run-1",
            }

    class FakeConnection:
        def __enter__(self) -> FakeConnection:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def cursor(self) -> FakeCursor:
            return FakeCursor()

    def fake_connect(self: PostgresBacktestJobGateway) -> FakeConnection:
        del self
        return FakeConnection()

    monkeypatch.setattr(PostgresBacktestJobGateway, "_connect", fake_connect)
    gateway = PostgresBacktestJobGateway("postgres://example")

    row = gateway.create_cost_ledger_entry(
        entry={
            "source": "render_workflow",
            "service": "openrouter",
            "provider": "openrouter",
            "model": "openai/gpt-4.1-mini",
            "feature_area": "result_readout",
            "task": "result_summary",
            "user_id": "user-1",
            "conversation_id": "conversation-1",
            "backtest_run_id": "run-1",
            "backtest_job_id": "job-1",
            "route_receipt_id": "receipt-1",
            "correlation_id": "workflow:render-run:job-1:run-1",
            "usage_metadata": {"prompt_tokens": 21, "completion_tokens": 9},
            "input_tokens": 21,
            "output_tokens": 9,
            "total_tokens": 30,
            "billable_unit": "token",
            "billable_quantity": 30,
            "cost_amount": 0.0009,
            "cost_currency": "USD",
            "cost_source": "provider_reported",
            "latency_ms": 42,
            "status": "succeeded",
            "metadata": {"source": "render_workflow"},
            "occurred_at": "2026-07-02T18:00:00+00:00",
        }
    )

    assert row["id"] == "ledger-1"
    assert "insert into public.cost_ledger_entries" in str(captured["query"]).lower()
    params = captured["params"]
    assert isinstance(params, dict)
    assert params["source"] == "render_workflow"
    assert params["service"] == "openrouter"
    assert params["feature_area"] == "result_readout"
    assert params["backtest_job_id"] == "job-1"
    assert params["route_receipt_id"] == "receipt-1"
    assert params["correlation_id"] == "workflow:render-run:job-1:run-1"
    assert params["usage_metadata"].obj == {
        "prompt_tokens": 21,
        "completion_tokens": 9,
    }
    assert params["metadata"].obj == {"source": "render_workflow"}
    assert params["billable_quantity"] == 30
    assert params["cost_amount"] == 0.0009
    assert params["occurred_at"] == "2026-07-02T18:00:00+00:00"


def test_postgres_backtest_job_gateway_calls_shared_finalization_rpc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api.schemas import BacktestRun

    from workflows.backtest_job import PostgresBacktestJobGateway

    captured: dict[str, object] = {}
    run = BacktestRun(
        id="run-1",
        conversation_id="conversation-1",
        strategy_id=None,
        status="completed",
        asset_class="equity",
        symbols=["AAPL"],
        allocation_method="equal_weight",
        benchmark_symbol="SPY",
        metrics={"aggregate": {"performance": {"total_return_pct": 12.4}}},
        config_snapshot={"template": "buy_and_hold", "symbols": ["AAPL"]},
        conversation_result_card={"title": "AAPL buy and hold", "actions": []},
        created_at=utcnow(),
        chart=None,
        trades=[],
    )

    class FakeCursor:
        def __enter__(self) -> FakeCursor:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def execute(self, query: str, params: object = None) -> None:
            captured["query"] = query
            captured["params"] = params

        def fetchone(self) -> dict[str, object]:
            params = captured["params"]
            assert isinstance(params, dict)
            return {
                "run": params["run"].obj,
                "idea": params["idea"].obj,
                "idea_version": params["idea_version"].obj,
                "evidence_artifact": params["evidence_artifact"].obj,
            }

    class FakeConnection:
        def __enter__(self) -> FakeConnection:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def cursor(self) -> FakeCursor:
            return FakeCursor()

    monkeypatch.setattr(
        PostgresBacktestJobGateway,
        "_connect",
        lambda _self: FakeConnection(),
    )
    gateway = PostgresBacktestJobGateway("postgres://example")
    finalization = BacktestFinalizationInput(
        user_id="user-1",
        execution_identity="backtest_job:job-1",
        run=run,
        result_card=dict(run.conversation_result_card),
        idea_id="idea-1",
        idea_version_id="version-1",
        evidence_artifact_id="artifact-1",
        finalized_at=utcnow(),
    )

    finalized = finalize_backtest_completion(gateway, finalization)

    assert "public.finalize_backtest_completion" in str(captured["query"])
    assert finalized.identity.run_id == "run-1"
    assert finalized.identity.evidence_artifact_id == "artifact-1"


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
    assert gateway.transitions == ["running", "finalize", "succeeded"]
    assert tool.calls == [request]
    created_run = gateway.finalization_store.backtest_runs["run-workflow"]
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
    assert len(gateway.finalization_store.ideas) == 1
    assert len(gateway.finalization_store.idea_versions) == 1
    assert len(gateway.finalization_store.evidence_artifacts) == 1
    assert created_run.conversation_result_card["evidence_artifact_id"]
    assert gateway.row["execution_metadata"]["existing"] == "kept"
    assert (
        gateway.row["execution_metadata"]["workflow_backtest"]["workflow_run_id"]
        == "local-run"
    )


def test_run_backtest_job_persists_workflow_internal_timings_on_success() -> None:
    from workflows.backtest_job import REAL_BACKTEST_JOB_KIND, run_backtest_job

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
        backtest_tool=FakeBacktestTool(_successful_tool_result_with_timings()),
        workflow_run_id="local-run",
        run_id_factory=lambda: "run-workflow",
    )

    assert result["status"] == "succeeded"
    metadata = gateway.row["execution_metadata"]["workflow_backtest"]
    timings = metadata["timings_ms"]
    assert timings["provider_fetch_total"] == pytest.approx(12.346)
    assert timings["engine_compute_total"] == pytest.approx(45.679)
    assert timings["chart_result_build_total"] == pytest.approx(7.891)
    for key in (
        "workflow_task_total",
        "job_fetch",
        "mark_running",
        "backtest_tool_run_total",
        "backtest_finalization",
        "result_readout_total",
        "link_result",
    ):
        assert timings[key] >= 0.0


def test_run_backtest_job_finalization_failure_is_retryable_and_replay_safe() -> None:
    from workflows.backtest_job import REAL_BACKTEST_JOB_KIND, run_backtest_job

    job = _job_row(
        launch_payload={
            "kind": REAL_BACKTEST_JOB_KIND,
            "schema_version": "backtest_job_launch/v1",
            "request": _request_payload(),
        }
    )
    gateway = FakeBacktestJobGateway(job)
    gateway.fail_finalization_after_commit_once = True
    tool = FakeBacktestTool(_successful_tool_result())
    expected_run_id = stable_backtest_run_id("user-1", f"backtest_job:{job['id']}")

    first = run_backtest_job(
        gateway,
        job_id=str(job["id"]),
        backtest_tool=tool,
        workflow_run_id="first-attempt",
    )

    assert first == {
        "job_id": job["id"],
        "status": "failed",
        "failure_code": "finalization_failed",
        "failure_detail": "execution_failed",
        "retryable": True,
        "workflow_run_id": "first-attempt",
        "execution_metadata": gateway.row["execution_metadata"],
    }
    assert gateway.row["result_run_id"] is None
    assert len(gateway.finalization_store.backtest_runs) == 1
    assert len(gateway.finalization_store.evidence_artifacts) == 1

    second = run_backtest_job(
        gateway,
        job_id=str(job["id"]),
        backtest_tool=tool,
        workflow_run_id="retry-attempt",
    )

    assert second["status"] == "succeeded"
    assert second["result_run_id"] == expected_run_id
    assert len(gateway.finalization_store.backtest_runs) == 1
    assert len(gateway.finalization_store.ideas) == 1
    assert len(gateway.finalization_store.idea_versions) == 1
    assert len(gateway.finalization_store.evidence_artifacts) == 1
    assert len(gateway.finalization_calls) == 2


def test_run_backtest_job_result_link_failure_retries_finalized_tuple() -> None:
    from workflows.backtest_job import REAL_BACKTEST_JOB_KIND, run_backtest_job

    job = _job_row(
        launch_payload={
            "kind": REAL_BACKTEST_JOB_KIND,
            "schema_version": "backtest_job_launch/v1",
            "request": _request_payload(),
        }
    )
    gateway = FakeBacktestJobGateway(job)
    gateway.fail_result_link_once = True
    tool = FakeBacktestTool(_successful_tool_result())
    expected_run_id = stable_backtest_run_id("user-1", f"backtest_job:{job['id']}")

    first = run_backtest_job(
        gateway,
        job_id=str(job["id"]),
        backtest_tool=tool,
        workflow_run_id="first-attempt",
    )

    assert first["status"] == "failed"
    assert first["failure_code"] == "finalization_failed"
    assert first["failure_detail"] == "execution_failed"
    assert first["retryable"] is True
    assert gateway.row["result_run_id"] is None
    assert len(gateway.finalization_store.backtest_runs) == 1
    assert len(gateway.finalization_store.evidence_artifacts) == 1

    second = run_backtest_job(
        gateway,
        job_id=str(job["id"]),
        backtest_tool=tool,
        workflow_run_id="retry-attempt",
    )

    assert second["status"] == "succeeded"
    assert second["result_run_id"] == expected_run_id
    assert len(gateway.finalization_store.backtest_runs) == 1
    assert len(gateway.finalization_store.ideas) == 1
    assert len(gateway.finalization_store.idea_versions) == 1
    assert len(gateway.finalization_store.evidence_artifacts) == 1
    assert len(gateway.finalization_calls) == 2


def test_run_backtest_job_reconciles_result_link_response_loss() -> None:
    from workflows.backtest_job import REAL_BACKTEST_JOB_KIND, run_backtest_job

    job = _job_row(
        launch_payload={
            "kind": REAL_BACKTEST_JOB_KIND,
            "schema_version": "backtest_job_launch/v1",
            "request": _request_payload(),
        }
    )
    gateway = FakeBacktestJobGateway(job)
    gateway.fail_result_link_after_commit_once = True
    tool = FakeBacktestTool(_successful_tool_result())
    expected_run_id = stable_backtest_run_id("user-1", f"backtest_job:{job['id']}")

    result = run_backtest_job(
        gateway,
        job_id=str(job["id"]),
        backtest_tool=tool,
        workflow_run_id="ambiguous-link-attempt",
    )

    assert result["status"] == "succeeded"
    assert result["result_run_id"] == expected_run_id
    assert gateway.row["status"] == "succeeded"
    assert gateway.row["result_run_id"] == expected_run_id
    assert gateway.failed_updates == []
    assert len(gateway.finalization_store.backtest_runs) == 1
    assert len(gateway.finalization_store.evidence_artifacts) == 1
    assert tool.calls == [_request_payload()]


def test_run_backtest_job_replay_after_success_does_not_recompute() -> None:
    from workflows.backtest_job import REAL_BACKTEST_JOB_KIND, run_backtest_job

    job = _job_row(
        launch_payload={
            "kind": REAL_BACKTEST_JOB_KIND,
            "schema_version": "backtest_job_launch/v1",
            "request": _request_payload(),
        }
    )
    gateway = FakeBacktestJobGateway(job)
    tool = FakeBacktestTool(_successful_tool_result())

    first = run_backtest_job(
        gateway,
        job_id=str(job["id"]),
        backtest_tool=tool,
        workflow_run_id="first-attempt",
    )
    transitions_after_success = list(gateway.transitions)
    second = run_backtest_job(
        gateway,
        job_id=str(job["id"]),
        backtest_tool=tool,
        workflow_run_id="replayed-task",
    )

    assert second["status"] == "succeeded"
    assert second["result_run_id"] == first["result_run_id"]
    assert tool.calls == [_request_payload()]
    assert gateway.transitions == transitions_after_success
    assert len(gateway.finalization_calls) == 1


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


def test_run_backtest_job_persists_result_summary_route_receipts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime.result_readout import ResultReadout
    from argus.llm.openrouter import (
        clear_openrouter_route_receipts,
        record_openrouter_route_receipt,
    )

    from workflows import backtest_job as workflow_module
    from workflows.backtest_job import REAL_BACKTEST_JOB_KIND, run_backtest_job

    clear_openrouter_route_receipts()

    def fake_result_readout(**_: object) -> ResultReadout:
        record_openrouter_route_receipt(
            task="result_summary",
            model_name="unit-test-model",
            mode="json_schema",
            schema_name="QuickTakeDraft",
            latency_ms=42,
            outcome="succeeded",
            token_usage={
                "prompt_tokens": 21,
                "completion_tokens": 9,
                "total_tokens": 30,
            },
            usage_cost_usd=0.0009,
            context_packet_ids=["packet-1"],
        )
        return ResultReadout(
            text="**Quick take**\n\nAAPL beat SPY in this test.",
            source="llm_explain_stage",
            fallback_used=False,
        )

    monkeypatch.setattr(
        workflow_module,
        "result_readout_with_metadata_from_backtest_payload",
        fake_result_readout,
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

    assert result["status"] == "succeeded"
    assert len(gateway.route_receipts) == 1
    receipt = gateway.route_receipts[0]
    assert receipt["user_id"] == "user-1"
    assert receipt["conversation_id"] == "conversation-1"
    assert receipt["run_id"] == "run-workflow"
    assert receipt["metadata"] == {
        "job_id": job["id"],
        "workflow_run_id": "local-run",
        "source": "render_workflow",
    }
    assert receipt["task"] == "result_summary"
    assert receipt["tier"] == "chat"
    assert receipt["model"] == "unit-test-model"
    assert receipt["mode"] == "json_schema"
    assert receipt["schema_name"] == "QuickTakeDraft"
    assert receipt["latency_ms"] == 42
    assert receipt["outcome"] == "succeeded"
    assert receipt["failure_mode"] is None
    assert receipt["fallback_used"] is False
    assert receipt["context_packet_ids"] == ["packet-1"]
    assert len(gateway.cost_ledger_entries) == 1
    ledger_entry = gateway.cost_ledger_entries[0]
    assert ledger_entry["source"] == "render_workflow"
    assert ledger_entry["provider"] == "openrouter"
    assert ledger_entry["model"] == "unit-test-model"
    assert ledger_entry["backtest_run_id"] == "run-workflow"
    assert ledger_entry["backtest_job_id"] == job["id"]
    assert ledger_entry["route_receipt_id"] == "receipt-1"
    assert ledger_entry["correlation_id"] == f"workflow:local-run:{job['id']}:run-workflow"
    assert ledger_entry["total_tokens"] == 30
    assert ledger_entry["cost_amount"] == 0.0009


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

    assert "The strategy returned 12.3% while SPY returned 8.1%" in result["result_readout"]
    assert "outperformed by 4.2 percentage points" in result["result_readout"]
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
    assert gateway.finalization_calls == []
    assert gateway.row["failure_code"] == "upstream_dependency_error"
    assert gateway.row["failure_detail"] == "market_data_issue"
    assert gateway.row["retryable"] is True
    assert (
        gateway.row["execution_metadata"]["workflow_backtest"]["failure_category"]
        == "upstream_dependency_error"
    )
    timings = gateway.row["execution_metadata"]["workflow_backtest"]["timings_ms"]
    assert timings["workflow_task_total"] >= 0.0
    assert timings["job_fetch"] >= 0.0
    assert timings["mark_running"] >= 0.0
    assert timings["backtest_tool_run_total"] >= 0.0


def test_run_backtest_job_tool_failure_preserves_collected_timings() -> None:
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
            "error_type": "market_data_unavailable",
            "error_message": "Market data is temporarily unavailable.",
            "retryable": True,
            "capability_context": {"failure_detail": "market_data_issue"},
            "execution_metadata": {
                "timings_ms": {
                    "provider_fetch_total": 22.2222,
                    "engine_compute_total": 33.3333,
                }
            },
        }
    )

    result = run_backtest_job(
        gateway,
        job_id=str(job["id"]),
        backtest_tool=tool,
        workflow_run_id="local-run",
    )

    assert result["status"] == "failed"
    metadata = gateway.row["execution_metadata"]["workflow_backtest"]
    assert metadata["failure_category"] == "market_data_unavailable"
    assert metadata["failure_detail"] == "market_data_issue"
    timings = metadata["timings_ms"]
    assert timings["provider_fetch_total"] == pytest.approx(22.222)
    assert timings["engine_compute_total"] == pytest.approx(33.333)
    assert timings["workflow_task_total"] >= 0.0
    assert timings["backtest_tool_run_total"] >= 0.0


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
