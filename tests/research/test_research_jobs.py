"""Thorough runs ride the existing job lifecycle; chat never hangs."""

from __future__ import annotations

import asyncio
from typing import Any

from argus.api import state as api_state
from argus.api.chat import research_jobs
from argus.domain.research.contracts import BackgroundPoll, ResearchPacket


def _job_request() -> dict[str, Any]:
    return {
        "capability_class": "thorough_research",
        "shape": "thorough",
        "language": "en",
        "question": "Compare Netflix and Disney over three years",
        "subjects": [
            {"symbol": "NFLX", "name": "Netflix", "asset_class": "equity"},
            {"symbol": "DIS", "name": "Walt Disney", "asset_class": "equity"},
        ],
        "period_of_interest": "last three years",
        "period_is_closed_window": False,
        "cache_key": "research-job-cache-key",
    }


class _JobGateway:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}
        self.completed: list[str] = []
        self.failed: list[tuple[str, str]] = []

    def create_backtest_job(self, **kwargs: Any) -> dict[str, Any]:
        job = {
            "id": "job-1",
            "status": "queued",
            "conversation_id": kwargs["conversation_id"],
            "request_message_id": kwargs.get("request_message_id"),
            "operation_scope": kwargs.get("operation_scope"),
            "launch_payload": kwargs.get("launch_payload"),
            "execution_metadata": kwargs.get("execution_metadata") or {},
            "retryable": False,
        }
        self.rows["job-1"] = job
        return job

    def get_backtest_job(self, *, user_id: str, job_id: str):
        return self.rows.get(job_id)

    def get_message(self, *, user_id: str, conversation_id: str, message_id: str):
        from datetime import datetime, timezone

        from argus.api.schemas import Message

        if message_id != "answer-1":
            return None
        return Message(
            id=message_id,
            conversation_id=conversation_id,
            role="assistant",
            content="HOOD vs. JPM vs. SCHW, quick comparison",
            created_at=datetime(2026, 8, 22, 1, 25, 58, tzinfo=timezone.utc),
            metadata={"conversation_mode": "guide", "research": {"sources": []}},
        )

    def mark_backtest_job_running(self, *, user_id: str, job_id: str, **_kw: Any):
        self.rows[job_id]["status"] = "running"
        return self.rows[job_id]

    def complete_research_job(
        self, *, user_id: str, job_id: str, execution_metadata=None
    ):
        self.rows[job_id]["status"] = "succeeded"
        self.rows[job_id]["execution_metadata"].update(execution_metadata or {})
        self.completed.append(job_id)
        return self.rows[job_id]

    def mark_backtest_job_failed(
        self, *, user_id: str, job_id: str, failure_code: str, **_kw: Any
    ):
        self.rows[job_id]["status"] = "failed"
        self.failed.append((job_id, failure_code))
        return self.rows[job_id]


class _FakeClient:
    def __init__(self, polls: list[BackgroundPoll]) -> None:
        self.polls = list(polls)
        self.submitted: list[str] = []

    def submit_background(self, prompt: str, spec: Any) -> str:
        self.submitted.append(prompt)
        return "resp_bg1"

    def poll_background(self, background_id: str, **_kw: Any) -> BackgroundPoll:
        return self.polls.pop(0)


def test_memory_mode_degrades_to_a_synchronous_thorough_run(monkeypatch) -> None:
    monkeypatch.setattr(api_state, "supabase_gateway", None)
    packet = ResearchPacket(answer_markdown="Deep synchronous answer")

    class SyncClient:
        def run_research(self, prompt: str, spec: Any) -> ResearchPacket:
            assert spec.model == "anthropic/claude-opus-4-7"
            return packet

    monkeypatch.setattr(research_jobs, "_client", lambda: SyncClient())
    job, sync_packet = research_jobs.start_research_job(
        job_request=_job_request(),
        user_id="u1",
        conversation_id="c1",
        request_message_id="m1",
        request_id="r1",
    )
    assert job is None
    assert sync_packet is packet


def test_background_path_creates_a_research_scope_job(monkeypatch) -> None:
    gateway = _JobGateway()
    monkeypatch.setattr(api_state, "supabase_gateway", gateway)
    client = _FakeClient([])
    monkeypatch.setattr(research_jobs, "_client", lambda: client)
    monkeypatch.setattr(research_jobs, "_spawn_poller", lambda **_kw: None)

    job, sync_packet = research_jobs.start_research_job(
        job_request=_job_request(),
        user_id="u1",
        conversation_id="c1",
        request_message_id="m1",
        request_id="r1",
    )

    assert sync_packet is None
    assert job is not None and job["status"] == "queued"
    row = gateway.rows["job-1"]
    assert row["operation_scope"] == "chat.research"
    assert row["launch_payload"]["perplexity_background_id"] == "resp_bg1"
    # The prompt follows the documented guidance: question, tickers, window.
    prompt = client.submitted[0]
    assert prompt.startswith("Compare Netflix and Disney")
    assert "Netflix (NFLX)" in prompt and "last three years" in prompt


def test_poller_finalizes_success_as_an_assistant_message(monkeypatch) -> None:
    gateway = _JobGateway()
    gateway.create_backtest_job(
        conversation_id="c1",
        request_message_id="m1",
        operation_scope="chat.research",
        launch_payload={},
        execution_metadata={},
    )
    monkeypatch.setattr(api_state, "supabase_gateway", gateway)
    packet = ResearchPacket(answer_markdown="Final research answer")
    client = _FakeClient(
        [
            BackgroundPoll(status="in_progress"),
            BackgroundPoll(status="completed", packet=packet),
        ]
    )
    monkeypatch.setattr(research_jobs, "_client", lambda: client)

    created: list[dict[str, Any]] = []

    def fake_create_message(**kwargs: Any):
        created.append(kwargs)

        class _Message:
            id = "answer-msg-1"

        return _Message()

    monkeypatch.setattr("argus.api.message_store.create_message", fake_create_message)
    recorded: list[dict[str, Any]] = []
    monkeypatch.setattr(
        research_jobs,
        "record_research_turn_evidence",
        lambda **kwargs: recorded.append(kwargs),
    )
    monkeypatch.setattr(research_jobs, "BACKGROUND_POLL_INTERVAL_SECONDS", 0.0)

    asyncio.run(
        research_jobs._poll_and_finalize(
            job_id="job-1",
            background_id="resp_bg1",
            job_request=_job_request(),
            user_id="u1",
            conversation_id="c1",
            request_id="r1",
        )
    )

    assert gateway.rows["job-1"]["status"] == "succeeded"
    assert (
        gateway.rows["job-1"]["execution_metadata"]["research_result_message_id"]
        == "answer-msg-1"
    )
    message = created[0]
    assert message["role"] == "assistant"
    assert message["content"].startswith("Final research answer")
    sidecar = message["metadata"]["research"]
    assert sidecar["capability_class"] == "thorough_research"
    # The sidecar names its subjects so later confirmation cards can find
    # this research in the transcript and offer its remaining peers.
    assert sidecar["anchor_symbols"] == ["NFLX", "DIS"]
    assert recorded and recorded[0]["message_id"] == "answer-msg-1"
    # The finalized packet enters the shared cache under the key the
    # requesting turn computed, so the same question now answers inline.
    from argus.domain.research.cache import cache_get

    assert cache_get("research-job-cache-key") is packet


def test_sync_fallback_composes_and_caches(monkeypatch) -> None:
    monkeypatch.setattr(api_state, "supabase_gateway", None)
    packet = ResearchPacket(answer_markdown="Deep synchronous answer")

    class SyncClient:
        def run_research(self, prompt: str, spec: Any) -> ResearchPacket:
            return packet

    monkeypatch.setattr(research_jobs, "_client", lambda: SyncClient())
    runtime_result: dict[str, Any] = {"research_job_request": _job_request()}
    job = research_jobs.apply_research_job_request(
        runtime_result,
        user_id="u1",
        conversation_id="c1",
        request_message_id="m1",
        request_id="r1",
    )
    assert job is None
    assert runtime_result["assistant_response"].startswith("Deep synchronous answer")
    assert runtime_result["research"]["anchor_symbols"] == ["NFLX", "DIS"]
    from argus.domain.research.cache import cache_get

    assert cache_get("research-job-cache-key") is packet


def test_poller_failure_marks_the_job_and_posts_an_honest_note(monkeypatch) -> None:
    gateway = _JobGateway()
    gateway.create_backtest_job(
        conversation_id="c1",
        request_message_id="m1",
        operation_scope="chat.research",
        launch_payload={},
        execution_metadata={},
    )
    monkeypatch.setattr(api_state, "supabase_gateway", gateway)
    client = _FakeClient([BackgroundPoll(status="failed", failure_detail="boom")])
    monkeypatch.setattr(research_jobs, "_client", lambda: client)
    monkeypatch.setattr(research_jobs, "BACKGROUND_POLL_INTERVAL_SECONDS", 0.0)

    created: list[dict[str, Any]] = []

    def fake_create_message(**kwargs: Any):
        created.append(kwargs)

        class _Message:
            id = "note-1"

        return _Message()

    monkeypatch.setattr("argus.api.message_store.create_message", fake_create_message)

    asyncio.run(
        research_jobs._poll_and_finalize(
            job_id="job-1",
            background_id="resp_bg1",
            job_request=_job_request(),
            user_id="u1",
            conversation_id="c1",
            request_id="r1",
        )
    )

    assert gateway.failed == [("job-1", "research_failed")]
    assert created and "won't quote figures" in created[0]["content"]


def test_job_status_endpoint_serializes_the_research_scope(monkeypatch) -> None:
    """The polling REST surface must carry operation_scope: the client's
    reconciliation treats a succeeded research job as terminal (no run to
    wait for) only when the scope survives serialization."""
    from argus.api.main import app
    from fastapi.testclient import TestClient

    gateway = _JobGateway()
    gateway.create_backtest_job(
        conversation_id="c1",
        request_message_id="m1",
        operation_scope="chat.research",
        launch_payload={},
        execution_metadata={},
    )
    gateway.rows["job-1"]["status"] = "succeeded"
    gateway.rows["job-1"]["result_run_id"] = None
    monkeypatch.setattr(api_state, "supabase_gateway", gateway)
    client = TestClient(app)

    response = client.get("/api/v1/backtest-jobs/job-1")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["job"]["operation_scope"] == "chat.research"
    assert payload["job"]["status"] == "succeeded"
    assert payload["run"] is None


def test_job_status_endpoint_carries_the_research_answer_message(monkeypatch) -> None:
    """A succeeded research job's result is its persisted answer message, the
    way a backtest's result is ``run``; the poll response carries it so the
    open view renders it in place without refetching the transcript
    (production cb7b326d, 2026-08-21: card flipped, answer never painted)."""
    from argus.api.main import app
    from fastapi.testclient import TestClient

    gateway = _JobGateway()
    gateway.create_backtest_job(
        conversation_id="c1",
        request_message_id="m1",
        operation_scope="chat.research",
        launch_payload={},
        execution_metadata={},
    )
    monkeypatch.setattr(api_state, "supabase_gateway", gateway)
    client = TestClient(app)

    queued = client.get("/api/v1/backtest-jobs/job-1").json()
    assert queued["result_message"] is None

    gateway.complete_research_job(
        user_id="u1",
        job_id="job-1",
        execution_metadata={"research_result_message_id": "answer-1"},
    )

    succeeded = client.get("/api/v1/backtest-jobs/job-1").json()
    assert succeeded["job"]["status"] == "succeeded"
    assert succeeded["run"] is None
    assert succeeded["result_message"]["id"] == "answer-1"
    assert succeeded["result_message"]["role"] == "assistant"
    assert succeeded["result_message"]["content"].startswith("HOOD vs. JPM")
    assert succeeded["result_message"]["metadata"]["research"] == {"sources": []}

    gateway.rows["job-1"]["operation_scope"] = "chat.run_backtest"
    backtest = client.get("/api/v1/backtest-jobs/job-1").json()
    assert backtest["result_message"] is None


def test_missing_key_yields_no_job_and_no_sync_packet(monkeypatch) -> None:
    monkeypatch.setattr(api_state, "supabase_gateway", _JobGateway())
    monkeypatch.setattr(research_jobs, "_client", lambda: None)
    job, packet = research_jobs.start_research_job(
        job_request=_job_request(),
        user_id="u1",
        conversation_id="c1",
        request_message_id="m1",
        request_id="r1",
    )
    assert job is None and packet is None
