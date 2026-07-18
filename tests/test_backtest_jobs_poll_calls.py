"""#231 — fresh and stale job polls are database-only; the scanner owns Render."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from argus.api import state as api_state
from argus.api.chat import backtest_jobs as jobs_module
from argus.api.main import app
from fastapi.testclient import TestClient


class _CountingRenderClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get_task_run(self, task_run_id: str) -> dict[str, object]:
        self.calls.append(task_run_id)
        return {"id": task_run_id, "status": "failed", "completedAt": None}


class _PollGateway:
    def __init__(self, status: str, *, stale: bool = False) -> None:
        queued_at = datetime.now(timezone.utc) - (
            timedelta(hours=2) if stale else timedelta(seconds=5)
        )
        self.job = {
            "id": "job-poll-1",
            "user_id": "00000000-0000-0000-0000-000000000001",
            "conversation_id": "conv-1",
            "status": status,
            "result_run_id": None,
            "retryable": False,
            "queued_at": queued_at.isoformat(),
            "started_at": queued_at.isoformat() if status == "running" else None,
            "execution_metadata": {
                "workflow_dispatch": {"task_run_id": "trn-poll-1"},
            },
        }

    def get_backtest_job(self, *, user_id: str, job_id: str):
        if job_id != self.job["id"]:
            return None
        return dict(self.job)


@pytest.fixture()
def render_client(monkeypatch: pytest.MonkeyPatch) -> _CountingRenderClient:
    client = _CountingRenderClient()
    monkeypatch.setattr(
        jobs_module, "RenderTaskRunClient", lambda *args, **kwargs: client
    )
    return client


@pytest.mark.parametrize("status", ["queued", "running", "succeeded", "failed"])
def test_fresh_job_polls_make_zero_render_calls(
    monkeypatch: pytest.MonkeyPatch,
    render_client: _CountingRenderClient,
    status: str,
) -> None:
    monkeypatch.setattr(api_state, "supabase_gateway", _PollGateway(status))
    response = TestClient(app).get("/api/v1/backtest-jobs/job-poll-1")

    assert response.status_code == 200
    assert response.json()["job"]["status"] == status
    assert render_client.calls == []


def test_stale_job_poll_returns_supabase_state_without_render_call(
    monkeypatch: pytest.MonkeyPatch,
    render_client: _CountingRenderClient,
) -> None:
    monkeypatch.setattr(
        api_state, "supabase_gateway", _PollGateway("running", stale=True)
    )
    response = TestClient(app).get("/api/v1/backtest-jobs/job-poll-1")

    assert response.status_code == 200
    assert response.json()["job"]["status"] == "running"
    assert render_client.calls == []


def test_stale_scanner_still_reconciles_with_bounded_render_calls(
    render_client: _CountingRenderClient,
) -> None:
    class _ScannerGateway(_PollGateway):
        def __init__(self) -> None:
            super().__init__("running", stale=True)
            self.failed: list[dict[str, object]] = []

        def list_backtest_jobs(self, *, status, user_id=None, limit=100, **_kw):
            if status == "running":
                return [dict(self.job)]
            return []

        def mark_backtest_job_failed(self, **payload):
            self.failed.append(payload)
            return {**self.job, "status": "failed", **payload}

    gateway = _ScannerGateway()
    summary = jobs_module.scan_stale_backtest_jobs(gateway=gateway)

    assert render_client.calls == ["trn-poll-1"]
    assert gateway.failed, summary
