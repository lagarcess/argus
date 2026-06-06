from __future__ import annotations

import pytest
from argus.api.chat.backtest_jobs import (
    BacktestJobShadowContext,
    ShadowBacktestJobTool,
    backtest_job_shadow_context,
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
    ) -> None:
        self.events = events
        self.should_raise = should_raise
        self.jobs: list[dict[str, object]] = []

    def create_backtest_job(self, **payload: object) -> dict[str, object]:
        self.events.append("job")
        if self.should_raise:
            raise RuntimeError("write failed")
        self.jobs.append(payload)
        return {"id": "job-1", **payload}


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
