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

    def find_backtest_job_by_idempotency_key(
        self, *, user_id: str, operation_scope: str, idempotency_key: str
    ):
        return next(
            (
                row
                for row in self.rows.values()
                if row.get("operation_scope") == operation_scope
                and row.get("request_message_id") == idempotency_key
            ),
            None,
        )

    messages: dict[str, Any] = {}
    message_read_error: Exception | None = None

    def get_message(self, *, user_id: str, conversation_id: str, message_id: str):
        if self.message_read_error is not None:
            raise self.message_read_error
        return self.messages.get(message_id)

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
        self,
        *,
        user_id: str,
        job_id: str,
        failure_code: str,
        execution_metadata=None,
        **_kw: Any,
    ):
        self.rows[job_id]["status"] = "failed"
        self.rows[job_id]["execution_metadata"].update(execution_metadata or {})
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


def _stored_message(message_id: str, content: str, metadata: dict[str, Any]):
    from datetime import datetime, timezone

    from argus.api.schemas import Message

    return Message(
        id=message_id,
        conversation_id="c1",
        role="assistant",
        content=content,
        created_at=datetime(2026, 8, 22, 1, 25, 58, tzinfo=timezone.utc),
        metadata=metadata,
    )


def _research_gateway() -> _JobGateway:
    gateway = _JobGateway()
    gateway.create_backtest_job(
        conversation_id="c1",
        request_message_id="m1",
        operation_scope="chat.research",
        launch_payload={},
        execution_metadata={},
    )
    return gateway


def test_job_status_endpoint_carries_the_research_answer_message(monkeypatch) -> None:
    """A succeeded research job's result is its persisted answer message, the
    way a backtest's result is ``run``; the poll response carries it so the
    open view renders it in place without refetching the transcript
    (production cb7b326d, 2026-08-21: card flipped, answer never painted)."""
    from argus.api.main import app
    from fastapi.testclient import TestClient

    gateway = _research_gateway()
    gateway.messages["answer-1"] = _stored_message(
        "answer-1",
        "HOOD vs. JPM vs. SCHW, quick comparison",
        {"conversation_mode": "guide", "research": {"sources": []}},
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


def test_job_status_endpoint_projects_the_message_like_the_transcript_does(
    monkeypatch,
) -> None:
    """The in-place paint and the reloaded transcript hydrate the same shape:
    private confirmation identity is stripped on both surfaces."""
    from argus.api.main import app
    from fastapi.testclient import TestClient

    gateway = _research_gateway()
    gateway.messages["answer-1"] = _stored_message(
        "answer-1",
        "Answer with a confirmation card",
        {
            "confirmation_card": {
                "rows": [],
                "canonical_launch_payload_hash": "sha256:private",
                "nested": {"canonical_launch_payload_hash": "sha256:private"},
            }
        },
    )
    gateway.complete_research_job(
        user_id="u1",
        job_id="job-1",
        execution_metadata={"research_result_message_id": "answer-1"},
    )
    monkeypatch.setattr(api_state, "supabase_gateway", gateway)

    payload = TestClient(app).get("/api/v1/backtest-jobs/job-1").json()

    card = payload["result_message"]["metadata"]["confirmation_card"]
    assert "canonical_launch_payload_hash" not in card
    assert "canonical_launch_payload_hash" not in card["nested"]
    assert card["rows"] == []


def test_job_status_survives_a_message_read_failure(monkeypatch) -> None:
    """The answer decorates the status report; it is not a precondition for
    it. A transient messages failure must not 500 the poll and strand the
    card on Researching."""
    from argus.api.main import app
    from fastapi.testclient import TestClient

    gateway = _research_gateway()
    gateway.complete_research_job(
        user_id="u1",
        job_id="job-1",
        execution_metadata={"research_result_message_id": "answer-1"},
    )
    gateway.message_read_error = RuntimeError("postgrest unavailable")
    monkeypatch.setattr(api_state, "supabase_gateway", gateway)

    response = TestClient(app).get("/api/v1/backtest-jobs/job-1")

    assert response.status_code == 200, response.text
    assert response.json()["job"]["status"] == "succeeded"
    assert response.json()["result_message"] is None


def test_failed_research_job_serves_its_failure_note(monkeypatch) -> None:
    """A failed run's persisted note is the job's message too, so the same
    in-place projection paints the explanation instead of leaving silence."""
    from argus.api.main import app
    from fastapi.testclient import TestClient

    gateway = _research_gateway()
    monkeypatch.setattr(api_state, "supabase_gateway", gateway)
    created: list[dict[str, Any]] = []

    def fake_create_message(**kwargs: Any):
        created.append(kwargs)
        note = _stored_message("note-1", kwargs["content"], kwargs["metadata"])
        gateway.messages["note-1"] = note
        return note

    monkeypatch.setattr("argus.api.message_store.create_message", fake_create_message)

    research_jobs._fail_job(
        job_id="job-1",
        user_id="u1",
        detail="background deadline exceeded",
        post_note=True,
        job_request=_job_request(),
        conversation_id="c1",
    )

    row = gateway.rows["job-1"]
    assert row["status"] == "failed"
    assert row["execution_metadata"]["research_result_message_id"] == "note-1"
    assert created[0]["content"]
    payload = TestClient(app).get("/api/v1/backtest-jobs/job-1").json()
    assert payload["job"]["status"] == "failed"
    assert payload["result_message"]["id"] == "note-1"
    assert payload["result_message"]["content"] == created[0]["content"]


def test_completion_mark_is_retried_then_fails_the_row_with_the_answer_linked(
    monkeypatch,
) -> None:
    """The completion mark is the row's only way out of running once the
    answer exists; no janitor revisits it. After the retries it fails the row
    with the answer still linked, so the conversation settles and the answer
    paints under the failed card instead of locking behind a running one."""
    gateway = _research_gateway()
    gateway.rows["job-1"]["status"] = "running"
    attempts: list[int] = []

    def failing_complete(**_kwargs: Any):
        attempts.append(1)
        raise RuntimeError("db unavailable")

    monkeypatch.setattr(gateway, "complete_research_job", failing_complete)
    monkeypatch.setattr(api_state, "supabase_gateway", gateway)
    monkeypatch.setattr(research_jobs, "COMPLETION_MARK_RETRY_SECONDS", 0.0)

    asyncio.run(
        research_jobs._mark_completed(job_id="job-1", user_id="u1", message_id="answer-1")
    )

    assert len(attempts) == research_jobs.COMPLETION_MARK_ATTEMPTS
    row = gateway.rows["job-1"]
    assert row["status"] == "failed"
    assert row["execution_metadata"]["research_result_message_id"] == "answer-1"
    assert gateway.failed == [("job-1", "research_failed")]


def test_a_replayed_request_message_reuses_the_existing_job_without_spend(
    monkeypatch,
) -> None:
    """A response-option retry re-adopts its request message, which is the
    research job's idempotency key. The existing row is returned whatever its
    status: no second provider run, no second poller, no unlinked answer that
    the settled row would otherwise serve stale."""
    gateway = _research_gateway()
    gateway.complete_research_job(
        user_id="u1",
        job_id="job-1",
        execution_metadata={"research_result_message_id": "answer-1"},
    )
    monkeypatch.setattr(api_state, "supabase_gateway", gateway)
    client = _FakeClient([])
    monkeypatch.setattr(research_jobs, "_client", lambda: client)
    spawned: list[dict[str, Any]] = []
    monkeypatch.setattr(research_jobs, "_spawn_poller", lambda **kw: spawned.append(kw))

    job, packet = research_jobs.start_research_job(
        job_request=_job_request(),
        user_id="u1",
        conversation_id="c1",
        request_message_id="m1",
        request_id="r2",
    )

    assert packet is None
    assert job is not None and job["id"] == "job-1" and job["status"] == "succeeded"
    assert client.submitted == []
    assert spawned == []
    assert len(gateway.rows) == 1


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
