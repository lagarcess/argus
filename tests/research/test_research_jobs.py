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
    assert message["metadata"]["research"]["capability_class"] == "thorough_research"
    assert recorded and recorded[0]["message_id"] == "answer-msg-1"


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
