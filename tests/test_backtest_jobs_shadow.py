from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from argus.api.chat.backtest_jobs import (
    BacktestJobShadowContext,
    RenderTaskRunClient,
    RenderWorkflowDispatcher,
    ShadowBacktestJobTool,
    backtest_job_shadow_context,
    link_shadow_backtest_job_result,
    payload_hash,
)


class _DelegateTool:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.calls: list[dict[str, object]] = []

    def run(self, payload: dict[str, object]) -> dict[str, object]:
        self.events.append("delegate")
        self.calls.append(payload)
        return {"success": True, "payload": {"result": "ok"}}


class _Gateway:
    def __init__(
        self,
        events: list[str],
        *,
        should_raise: bool = False,
        create_result: dict[str, object] | None = None,
        backpressure_counts: dict[tuple[str, str | None], int] | None = None,
    ) -> None:
        self.events = events
        self.should_raise = should_raise
        self.create_result = create_result
        self.backpressure_counts = backpressure_counts or {}
        self.jobs: list[dict[str, object]] = []
        self.metadata_updates: list[dict[str, object]] = []
        self.result_links: list[dict[str, object]] = []

    def create_backtest_job(self, **payload: object) -> dict[str, object]:
        self.events.append("job")
        if self.should_raise:
            raise RuntimeError("write failed")
        if self.create_result is not None:
            return self.create_result
        self.jobs.append(payload)
        return {"id": "job-1", **payload}

    def merge_backtest_job_execution_metadata(
        self, **payload: object
    ) -> dict[str, object]:
        self.events.append("metadata")
        self.metadata_updates.append(payload)
        return {"id": payload["job_id"], **payload}

    def link_backtest_job_result(self, **payload: object) -> dict[str, object]:
        self.events.append("link")
        self.result_links.append(payload)
        return {"id": payload["job_id"], **payload}

    def count_backtest_jobs(
        self,
        *,
        status: str,
        user_id: str | None = None,
        limit: int = 100,
    ) -> int:
        return min(self.backpressure_counts.get((status, user_id), 0), limit)


class _Dispatcher:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.calls: list[dict[str, object]] = []

    def dispatch(self, **payload: object) -> dict[str, object]:
        self.events.append("dispatch")
        self.calls.append(payload)
        return {"id": "task-run-1", "status": "pending"}


class _FakeTerminalTaskRunClient:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls: list[str] = []

    def get_task_run(self, task_run_id: str) -> dict[str, object]:
        self.calls.append(task_run_id)
        return dict(self.payload)


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return dict(self.payload)


class _BackpressureReconciliationGateway(_Gateway):
    def __init__(self, events: list[str]) -> None:
        super().__init__(events)
        self.blocking_failed = False
        self.failed_updates: list[dict[str, object]] = []

    def count_backtest_jobs(
        self,
        *,
        status: str,
        user_id: str | None = None,
        limit: int = 100,
    ) -> int:
        if status == "running" and user_id == "user-1" and not self.blocking_failed:
            return min(1, limit)
        return 0

    def list_backtest_jobs(
        self,
        *,
        status: str,
        user_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, object]]:
        if status != "running" or user_id != "user-1" or self.blocking_failed:
            return []
        return [
            {
                "id": "blocking-job-1",
                "user_id": "user-1",
                "status": "running",
                "execution_metadata": {
                    "workflow_dispatch": {
                        "task_run_id": "trn-blocking-timeout",
                    }
                },
            }
        ][:limit]

    def mark_backtest_job_failed(self, **payload: object) -> dict[str, object]:
        self.events.append("reconcile")
        self.blocking_failed = True
        self.failed_updates.append(payload)
        return {
            "id": payload["job_id"],
            "user_id": payload["user_id"],
            "status": "failed",
            "failure_code": payload["failure_code"],
            "failure_detail": payload["failure_detail"],
            "retryable": payload["retryable"],
            "execution_metadata": payload.get("execution_metadata") or {},
        }


class _ProofBackpressureGateway(_Gateway):
    def __init__(self, events: list[str]) -> None:
        super().__init__(events)
        self.blocking_failed = False
        self.failed_updates: list[dict[str, object]] = []

    def count_backtest_jobs(
        self,
        *,
        status: str,
        user_id: str | None = None,
        limit: int = 100,
    ) -> int:
        if status == "running" and user_id == "user-1" and not self.blocking_failed:
            return min(1, limit)
        return 0

    def list_backtest_jobs(
        self,
        *,
        status: str,
        user_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, object]]:
        if status != "running" or user_id != "user-1" or self.blocking_failed:
            return []
        old_timestamp = (
            datetime.now(timezone.utc) - timedelta(seconds=60 * 60)
        ).isoformat()
        return [
            {
                "id": "proof-blocking-job-1",
                "user_id": "user-1",
                "status": "running",
                "created_at": old_timestamp,
                "started_at": old_timestamp,
                "launch_payload": {"kind": "render_workflow_proof"},
                "execution_metadata": {},
            }
        ][:limit]

    def mark_backtest_job_failed(self, **payload: object) -> dict[str, object]:
        self.events.append("reconcile")
        self.blocking_failed = True
        self.failed_updates.append(payload)
        return {
            "id": payload["job_id"],
            "user_id": payload["user_id"],
            "status": "failed",
            "failure_code": payload["failure_code"],
            "failure_detail": payload["failure_detail"],
            "retryable": payload["retryable"],
            "execution_metadata": payload.get("execution_metadata") or {},
        }


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
        idempotency_key="idem-1",
        request_id="request-1",
        chat_action={
            "type": "run_backtest",
            "payload": {"confirmation_id": "confirmation-1"},
        },
    )


def test_render_workflow_dispatcher_uses_local_task_server_without_render_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api.chat import backtest_jobs

    monkeypatch.setenv("RENDER_USE_LOCAL_DEV", "true")
    monkeypatch.setenv("RENDER_LOCAL_DEV_URL", "http://127.0.0.1:8121")
    monkeypatch.delenv("RENDER_API_KEY", raising=False)
    calls: list[dict[str, object]] = []

    def fake_post(
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, object],
        timeout: int,
    ) -> _FakeResponse:
        calls.append(
            {
                "url": url,
                "headers": headers,
                "json": json,
                "timeout": timeout,
            }
        )
        return _FakeResponse({"id": "trn-local", "status": "pending"})

    monkeypatch.setattr(backtest_jobs.httpx, "post", fake_post)

    result = RenderWorkflowDispatcher(
        task_id="argus-backtests/workflow_proof"
    ).dispatch(job_id="job-1", nonce="nonce-1")

    assert result == {"id": "trn-local", "status": "pending"}
    assert calls == [
        {
            "url": "http://127.0.0.1:8121/v1/task-runs",
            "headers": {"Content-Type": "application/json"},
            "json": {
                "task": "argus-backtests/workflow_proof",
                "input": ["job-1", "nonce-1"],
            },
            "timeout": 15,
        }
    ]


def test_render_task_run_client_uses_local_task_server_without_render_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api.chat import backtest_jobs

    monkeypatch.setenv("RENDER_USE_LOCAL_DEV", "true")
    monkeypatch.delenv("RENDER_LOCAL_DEV_URL", raising=False)
    monkeypatch.delenv("RENDER_API_KEY", raising=False)
    calls: list[dict[str, object]] = []

    def fake_get(
        url: str,
        *,
        headers: dict[str, str],
        timeout: int,
    ) -> _FakeResponse:
        calls.append({"url": url, "headers": headers, "timeout": timeout})
        return _FakeResponse({"id": "trn-local", "status": "completed"})

    monkeypatch.setattr(backtest_jobs.httpx, "get", fake_get)

    result = RenderTaskRunClient().get_task_run("trn-local")

    assert result == {"id": "trn-local", "status": "completed"}
    assert calls == [
        {
            "url": "http://localhost:8120/v1/task-runs/trn-local",
            "headers": {"Accept": "application/json"},
            "timeout": 10,
        }
    ]


def test_shadow_backtest_job_tool_is_noop_when_flag_disabled(monkeypatch) -> None:
    monkeypatch.delenv("ARGUS_BACKTEST_JOBS_SHADOW_ENABLED", raising=False)
    events: list[str] = []
    gateway = _Gateway(events)
    delegate = _DelegateTool(events)
    tool = ShadowBacktestJobTool(
        delegate=delegate,
        gateway_getter=lambda: gateway,
        dev_memory_fallback_getter=lambda: True,
    )
    payload = _payload()

    with backtest_job_shadow_context(_context()):
        result = tool.run(payload)

    assert result == {"success": True, "payload": {"result": "ok"}}
    assert events == ["delegate"]
    assert gateway.jobs == []
    assert delegate.calls == [payload]


def test_shadow_backtest_job_tool_creates_job_before_in_process_execution(
    monkeypatch,
) -> None:
    monkeypatch.setenv("ARGUS_BACKTEST_JOBS_SHADOW_ENABLED", "true")
    events: list[str] = []
    gateway = _Gateway(events)
    delegate = _DelegateTool(events)
    tool = ShadowBacktestJobTool(
        delegate=delegate,
        gateway_getter=lambda: gateway,
        dev_memory_fallback_getter=lambda: True,
    )
    payload = _payload()

    with backtest_job_shadow_context(_context()):
        result = tool.run(payload)

    assert result == {"success": True, "payload": {"result": "ok"}}
    assert events == ["job", "delegate"]
    assert len(gateway.jobs) == 1
    job = gateway.jobs[0]
    assert job["user_id"] == "user-1"
    assert job["conversation_id"] == "conversation-1"
    assert job["request_message_id"] == "message-1"
    assert job["idempotency_key"] == "idem-1"
    assert job["payload_hash"] == payload_hash(payload)
    assert job["launch_payload"] == {
        "kind": "render_workflow_proof",
        "schema_version": "backtest_job_launch/v1",
        "source": "chat_runtime",
        "request": payload,
        "chat_action": {
            "type": "run_backtest",
            "payload": {"confirmation_id": "confirmation-1"},
        },
    }
    assert job["execution_metadata"] == {
        "shadow_mode": True,
        "source": "api_chat",
        "request_id": "request-1",
        "payload_hash": payload_hash(payload),
    }
    assert delegate.calls == [payload]


def test_shadow_backtest_job_tool_dispatches_job_when_dispatch_flag_enabled(
    monkeypatch,
) -> None:
    monkeypatch.setenv("ARGUS_BACKTEST_JOBS_SHADOW_ENABLED", "true")
    monkeypatch.setenv("ARGUS_BACKTEST_JOBS_DISPATCH_ENABLED", "true")
    monkeypatch.setenv("ARGUS_BACKTEST_WORKFLOW_TASK", "argus-backtests/workflow_proof")
    events: list[str] = []
    gateway = _Gateway(events)
    dispatcher = _Dispatcher(events)
    delegate = _DelegateTool(events)
    tool = ShadowBacktestJobTool(
        delegate=delegate,
        gateway_getter=lambda: gateway,
        dev_memory_fallback_getter=lambda: True,
        dispatcher_getter=lambda: dispatcher,
    )
    payload = _payload()
    context = _context()

    with backtest_job_shadow_context(context):
        result = tool.run(payload)

    digest = payload_hash(payload)
    assert result == {"success": True, "payload": {"result": "ok"}}
    assert events == ["job", "dispatch", "metadata", "delegate"]
    assert context.created_job_id == "job-1"
    assert context.workflow_dispatch_started is True
    assert context.workflow_task_run_id == "task-run-1"
    assert dispatcher.calls == [
        {"job_id": "job-1", "nonce": digest.removeprefix("sha256:")}
    ]
    assert gateway.metadata_updates == [
        {
            "user_id": "user-1",
            "job_id": "job-1",
            "execution_metadata": {
                "workflow_dispatch": {
                    "task": "argus-backtests/workflow_proof",
                    "task_run_id": "task-run-1",
                    "status": "pending",
                    "dispatched_at": gateway.metadata_updates[0]["execution_metadata"][
                        "workflow_dispatch"
                    ]["dispatched_at"],
                }
            },
        }
    ]
    assert delegate.calls == [payload]


def test_shadow_backtest_job_tool_dispatches_real_task_only_when_execution_enabled(
    monkeypatch,
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
        dev_memory_fallback_getter=lambda: True,
        dispatcher_getter=lambda: dispatcher,
    )
    payload = _payload()

    with backtest_job_shadow_context(_context()):
        result = tool.run(payload)

    assert result["success"] is True
    assert result["payload"]["backtest_job"]["id"] == "job-1"
    assert events == ["job", "dispatch", "metadata"]
    assert gateway.jobs[0]["launch_payload"] == {
        "kind": "run_backtest_job",
        "schema_version": "backtest_job_launch/v1",
        "source": "chat_runtime",
        "request": payload,
        "chat_action": {
            "type": "run_backtest",
            "payload": {"confirmation_id": "confirmation-1"},
        },
    }
    assert (
        gateway.metadata_updates[0]["execution_metadata"]["workflow_dispatch"]["task"]
        == "argus-backtests/run_backtest_job"
    )
    assert delegate.calls == []


def test_shadow_backtest_job_tool_does_not_redispatch_existing_job(
    monkeypatch,
) -> None:
    monkeypatch.setenv("ARGUS_BACKTEST_JOBS_SHADOW_ENABLED", "true")
    monkeypatch.setenv("ARGUS_BACKTEST_JOBS_DISPATCH_ENABLED", "true")
    events: list[str] = []
    gateway = _Gateway(
        events,
        create_result={
            "id": "job-1",
            "status": "queued",
            "execution_metadata": {
                "workflow_dispatch": {
                    "task_run_id": "task-run-existing",
                    "status": "pending",
                }
            },
        },
    )
    dispatcher = _Dispatcher(events)
    delegate = _DelegateTool(events)
    tool = ShadowBacktestJobTool(
        delegate=delegate,
        gateway_getter=lambda: gateway,
        dev_memory_fallback_getter=lambda: True,
        dispatcher_getter=lambda: dispatcher,
    )
    context = _context()

    with backtest_job_shadow_context(context):
        result = tool.run(_payload())

    assert result == {"success": True, "payload": {"result": "ok"}}
    assert events == ["job", "delegate"]
    assert dispatcher.calls == []
    assert context.created_job_id == "job-1"
    assert context.workflow_dispatch_started is True
    assert context.workflow_task_run_id == "task-run-existing"
    assert gateway.metadata_updates == []


def test_shadow_backtest_job_tool_skips_job_when_backpressure_limit_hit(
    monkeypatch,
) -> None:
    monkeypatch.setenv("ARGUS_BACKTEST_JOBS_SHADOW_ENABLED", "true")
    monkeypatch.setenv("ARGUS_BACKTEST_JOBS_DISPATCH_ENABLED", "true")
    events: list[str] = []
    gateway = _Gateway(events, backpressure_counts={("running", "user-1"): 1})
    dispatcher = _Dispatcher(events)
    delegate = _DelegateTool(events)
    tool = ShadowBacktestJobTool(
        delegate=delegate,
        gateway_getter=lambda: gateway,
        dev_memory_fallback_getter=lambda: True,
        dispatcher_getter=lambda: dispatcher,
    )
    payload = _payload()
    context = _context()

    with backtest_job_shadow_context(context):
        result = tool.run(payload)

    assert result == {"success": True, "payload": {"result": "ok"}}
    assert events == ["delegate"]
    assert gateway.jobs == []
    assert dispatcher.calls == []
    assert context.created_job_id is None
    assert delegate.calls == [payload]


def test_shadow_backtest_job_tool_reconciles_terminal_blocker_before_backpressure(
    monkeypatch,
) -> None:
    from argus.api.chat import backtest_jobs as backtest_job_helpers

    monkeypatch.setenv("ARGUS_BACKTEST_JOBS_SHADOW_ENABLED", "true")
    monkeypatch.setenv("ARGUS_BACKTEST_JOBS_DISPATCH_ENABLED", "true")
    monkeypatch.setenv("ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED", "true")
    task_client = _FakeTerminalTaskRunClient(
        {
            "id": "trn-blocking-timeout",
            "status": "failed",
            "error": "task timed out",
            "completedAt": "2026-06-07T07:21:51Z",
        }
    )
    monkeypatch.setattr(
        backtest_job_helpers,
        "RenderTaskRunClient",
        lambda: task_client,
    )
    events: list[str] = []
    gateway = _BackpressureReconciliationGateway(events)
    dispatcher = _Dispatcher(events)
    tool = ShadowBacktestJobTool(
        delegate=None,
        gateway_getter=lambda: gateway,
        dev_memory_fallback_getter=lambda: False,
        dispatcher_getter=lambda: dispatcher,
    )
    context = _context()

    with backtest_job_shadow_context(context):
        result = tool.run(_payload())

    assert result["success"] is True
    assert result["payload"]["backtest_job"]["id"] == "job-1"
    assert events == ["reconcile", "job", "dispatch", "metadata"]
    assert task_client.calls == ["trn-blocking-timeout"]
    assert gateway.failed_updates[0]["failure_code"] == "workflow_task_timeout"
    assert context.created_job_id == "job-1"


def test_shadow_backtest_job_tool_reconciles_stale_proof_without_task_metadata(
    monkeypatch,
) -> None:
    monkeypatch.setenv("ARGUS_BACKTEST_JOBS_SHADOW_ENABLED", "true")
    monkeypatch.setenv("ARGUS_BACKTEST_JOBS_DISPATCH_ENABLED", "true")
    monkeypatch.setenv("ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED", "true")
    events: list[str] = []
    gateway = _ProofBackpressureGateway(events)
    dispatcher = _Dispatcher(events)
    tool = ShadowBacktestJobTool(
        delegate=None,
        gateway_getter=lambda: gateway,
        dev_memory_fallback_getter=lambda: False,
        dispatcher_getter=lambda: dispatcher,
    )
    context = _context()

    with backtest_job_shadow_context(context):
        result = tool.run(_payload())

    assert result["success"] is True
    assert result["payload"]["backtest_job"]["id"] == "job-1"
    assert events == ["reconcile", "job", "dispatch", "metadata"]
    assert gateway.failed_updates[0]["job_id"] == "proof-blocking-job-1"
    assert gateway.failed_updates[0]["failure_code"] == "workflow_dispatch_missing"
    assert context.created_job_id == "job-1"


def test_shadow_backtest_job_write_failure_falls_back_to_in_process_execution(
    monkeypatch,
) -> None:
    monkeypatch.setenv("ARGUS_BACKTEST_JOBS_SHADOW_ENABLED", "true")
    events: list[str] = []
    gateway = _Gateway(events, should_raise=True)
    delegate = _DelegateTool(events)
    tool = ShadowBacktestJobTool(
        delegate=delegate,
        gateway_getter=lambda: gateway,
        dev_memory_fallback_getter=lambda: True,
    )
    payload = _payload()

    with backtest_job_shadow_context(_context()):
        result = tool.run(payload)

    assert result == {"success": True, "payload": {"result": "ok"}}
    assert events == ["job", "delegate"]
    assert delegate.calls == [payload]


def test_shadow_backtest_job_write_failure_surfaces_in_strict_mode(
    monkeypatch,
) -> None:
    monkeypatch.setenv("ARGUS_BACKTEST_JOBS_SHADOW_ENABLED", "true")
    events: list[str] = []
    gateway = _Gateway(events, should_raise=True)
    delegate = _DelegateTool(events)
    tool = ShadowBacktestJobTool(
        delegate=delegate,
        gateway_getter=lambda: gateway,
        dev_memory_fallback_getter=lambda: False,
    )

    with backtest_job_shadow_context(_context()):
        with pytest.raises(RuntimeError, match="write failed"):
            tool.run(_payload())

    assert events == ["job"]
    assert delegate.calls == []


def test_link_shadow_backtest_job_result_marks_succeeded_without_dispatch() -> None:
    events: list[str] = []
    gateway = _Gateway(events)
    context = _context()
    context.created_job_id = "job-1"

    with backtest_job_shadow_context(context):
        link_shadow_backtest_job_result(
            user_id="user-1",
            run_id="run-1",
            gateway=gateway,
            dev_memory_fallback_enabled=True,
        )

    assert events == ["link"]
    assert gateway.result_links == [
        {
            "user_id": "user-1",
            "job_id": "job-1",
            "result_run_id": "run-1",
            "execution_metadata": {
                "api_in_process_result": {
                    "result_run_id": "run-1",
                    "linked_at": gateway.result_links[0]["execution_metadata"][
                        "api_in_process_result"
                    ]["linked_at"],
                    "marked_succeeded": True,
                }
            },
            "mark_succeeded": True,
        }
    ]


def test_link_shadow_backtest_job_result_leaves_lifecycle_to_dispatch() -> None:
    events: list[str] = []
    gateway = _Gateway(events)
    context = _context()
    context.created_job_id = "job-1"
    context.workflow_dispatch_started = True
    context.workflow_task_run_id = "task-run-1"

    with backtest_job_shadow_context(context):
        link_shadow_backtest_job_result(
            user_id="user-1",
            run_id="run-1",
            gateway=gateway,
            dev_memory_fallback_enabled=True,
        )

    link = gateway.result_links[0]
    assert events == ["link"]
    assert link["result_run_id"] == "run-1"
    assert link["mark_succeeded"] is False
    assert link["execution_metadata"]["workflow_dispatch"]["task_run_id"] == "task-run-1"


def test_link_shadow_backtest_job_result_leaves_result_link_to_real_workflow(
    monkeypatch,
) -> None:
    monkeypatch.setenv("ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED", "true")
    events: list[str] = []
    gateway = _Gateway(events)
    context = _context()
    context.created_job_id = "job-1"
    context.workflow_dispatch_started = True
    context.workflow_task_run_id = "task-run-1"

    with backtest_job_shadow_context(context):
        link_shadow_backtest_job_result(
            user_id="user-1",
            run_id="run-1",
            gateway=gateway,
            dev_memory_fallback_enabled=True,
        )

    assert events == ["metadata"]
    assert gateway.result_links == []
    metadata = gateway.metadata_updates[0]["execution_metadata"]
    assert metadata["api_in_process_result"]["result_run_id"] == "run-1"
    assert metadata["api_in_process_result"]["marked_succeeded"] is False
    assert (
        metadata["api_in_process_result"]["job_result_column_owned_by"]
        == "run_backtest_job"
    )
    assert metadata["workflow_dispatch"]["task_run_id"] == "task-run-1"


def test_render_workflow_dispatcher_posts_to_render_task_api(
    monkeypatch,
) -> None:
    monkeypatch.setenv("RENDER_API_KEY", "rnd_test")
    calls: list[dict[str, object]] = []

    def fake_post(*args: object, **kwargs: object):
        calls.append({"args": args, "kwargs": kwargs})

        class Response:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict[str, object]:
                return {"id": "task-run-1", "status": "pending"}

        return Response()

    monkeypatch.setattr("argus.api.chat.backtest_jobs.httpx.post", fake_post)
    dispatcher = RenderWorkflowDispatcher(
        task_id="argus-backtests/workflow_proof",
        endpoint="https://api.render.test/v1/task-runs",
    )

    result = dispatcher.dispatch(job_id="job-1", nonce="nonce-1")

    assert result == {"id": "task-run-1", "status": "pending"}
    assert calls == [
        {
            "args": ("https://api.render.test/v1/task-runs",),
            "kwargs": {
                "headers": {
                    "Authorization": "Bearer rnd_test",
                    "Content-Type": "application/json",
                },
                "json": {
                    "task": "argus-backtests/workflow_proof",
                    "input": ["job-1", "nonce-1"],
                },
                "timeout": 15,
            },
        }
    ]
