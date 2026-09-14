"""Research provider failures (#609): typed, asked again inside the call's
deadline only when no paid work can have started, then ended on the recovery
discovery already uses.

Every provider here is scripted, and so is time: a retry's wait is asserted,
never slept. The failures are the five the issue names (a 500, a 429 with
Retry-After, a timeout, a 400 and a missing key), plus a connection refused
before the request was sent and one dropped mid-request, which the founder's
paid-work rule tells apart.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx
import pytest
from argus.agent_runtime import research_answer as ra
from argus.agent_runtime import research_grounded as grounded
from argus.agent_runtime.recovery_messages import (
    DURABLE_RETRY_RECOVERY_CODES,
    RECOVERY_FALLBACK_MESSAGES,
)
from argus.api import state as api_state
from argus.api.chat.research_evidence import record_research_turn_evidence
from argus.domain.research import perplexity_agent
from argus.domain.research.config import RESEARCH_CONFIG_SPECS
from argus.domain.research.contracts import ResearchUnavailableError
from argus.domain.research.perplexity_agent import PerplexityAgentClient
from argus.domain.supabase_gateway import SupabaseGateway

from tests.research.conftest import (
    agent_response,
    educational_interpretation,
    request_body,
    run_research_turn,
    set_research_query,
)
from tests.test_supabase_gateway import _RecordingSupabaseClient

FAST = RESEARCH_CONFIG_SPECS["fast"]
QUESTION = "What is Apple trading at right now?"
BACKOFF = perplexity_agent._FIRST_BACKOFF_SECONDS
ATTEMPTS = perplexity_agent._MAX_ATTEMPTS

Step = Callable[[httpx.Request], httpx.Response]


class ScriptedClock:
    """Monotonic time that moves only when a wait or a timed-out request moves it."""

    def __init__(self) -> None:
        self.now = 0.0
        self.waits: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.waits.append(seconds)
        self.now += seconds


class ScriptedProvider(httpx.BaseTransport):
    """Plays one scripted step per request and records every request."""

    def __init__(self, steps: list[Step]) -> None:
        self.steps = list(steps)
        self.requests: list[httpx.Request] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.steps.pop(0)(request)


def status(code: int, headers: dict[str, str] | None = None) -> Step:
    return lambda _request: httpx.Response(
        code, headers=headers, json={"error": {"message": "scripted"}}
    )


def answer() -> Step:
    document = agent_response()
    return lambda _request: httpx.Response(200, json=document)


def timeout(clock: ScriptedClock) -> Step:
    def step(request: httpx.Request) -> httpx.Response:
        # A read timeout fires only once the attempt's whole budget has passed.
        clock.now += budget(request)
        raise httpx.ReadTimeout("scripted", request=request)

    return step


def budget(request: httpx.Request) -> float:
    return request.extensions["timeout"]["read"]


def transport_error(error: type[httpx.TransportError]) -> Step:
    def step(request: httpx.Request) -> httpx.Response:
        raise error("scripted", request=request)

    return step


def scripted_client(
    clock: ScriptedClock, steps: list[Step], *, api_key: str = "k"
) -> tuple[PerplexityAgentClient, ScriptedProvider]:
    provider = ScriptedProvider(steps)
    client = PerplexityAgentClient(
        api_key, transport=provider, clock=clock.monotonic, sleep=clock.sleep
    )
    return client, provider


@dataclass(frozen=True)
class Failure:
    name: str
    steps: Callable[[ScriptedClock], list[Step]]
    reason: str
    status: int | None
    transient: bool
    attempts: int
    waits: tuple[float, ...]
    # Attempts the provider may have billed without answering.
    unanswered: int = 0
    api_key: str = "k"

    @property
    def recovery_code(self) -> str:
        return "research_lookup_failed" if self.transient else "research_lookup_unavailable"

    @property
    def degraded(self) -> dict[str, Any]:
        return {
            "code": f"research_unavailable_{self.reason}",
            **({"status": self.status} if self.status is not None else {}),
        }


RETRY_AFTER_SECONDS = 7

FAILURES = [
    Failure(
        "http_500",
        lambda _clock: [status(500)] * ATTEMPTS,
        reason="http_error",
        status=500,
        transient=True,
        attempts=ATTEMPTS,
        waits=(BACKOFF, 2 * BACKOFF),
    ),
    Failure(
        "http_429_retry_after",
        lambda _clock: [status(429, {"Retry-After": str(RETRY_AFTER_SECONDS)})]
        * ATTEMPTS,
        reason="http_error",
        status=429,
        transient=True,
        attempts=ATTEMPTS,
        waits=(RETRY_AFTER_SECONDS, RETRY_AFTER_SECONDS),
    ),
    Failure(
        "timeout",
        lambda clock: [timeout(clock)],
        reason="timeout",
        status=None,
        transient=True,
        attempts=1,
        waits=(),
        unanswered=1,
    ),
    Failure(
        "connection_refused",
        lambda _clock: [transport_error(httpx.ConnectError)] * ATTEMPTS,
        reason="transport",
        status=None,
        transient=True,
        attempts=ATTEMPTS,
        waits=(BACKOFF, 2 * BACKOFF),
    ),
    Failure(
        "connection_dropped",
        lambda _clock: [transport_error(httpx.RemoteProtocolError)],
        reason="transport",
        status=None,
        transient=True,
        attempts=1,
        waits=(),
        unanswered=1,
    ),
    Failure(
        "http_400",
        lambda _clock: [status(400)],
        reason="http_error",
        status=400,
        transient=False,
        attempts=1,
        waits=(),
    ),
    Failure(
        "not_configured",
        lambda _clock: [],
        reason="not_configured",
        status=None,
        transient=False,
        attempts=0,
        waits=(),
        api_key="",
    ),
]


# --- The client: asked again only when no paid work can have started -------


@pytest.mark.parametrize("failure", FAILURES, ids=lambda failure: failure.name)
def test_each_failure_is_retried_only_when_no_paid_work_can_have_started(
    monkeypatch: pytest.MonkeyPatch, failure: Failure
) -> None:
    unpriced: list[Any] = []
    monkeypatch.setattr(perplexity_agent, "record_unpriced_spend", unpriced.append)
    clock = ScriptedClock()
    client, provider = scripted_client(
        clock, failure.steps(clock), api_key=failure.api_key
    )

    with pytest.raises(ResearchUnavailableError) as raised:
        client.run_research(QUESTION, FAST)

    error = raised.value
    assert (error.reason, error.status, error.transient) == (
        failure.reason,
        failure.status,
        failure.transient,
    )
    assert len(provider.requests) == failure.attempts
    assert clock.waits == list(failure.waits)
    assert clock.now <= FAST.timeout_seconds, "every attempt ends inside one deadline"
    assert len({request.content for request in provider.requests}) <= 1
    # An attempt the provider may have billed without answering is on record.
    assert [(spend.reason, spend.provider_response_id) for spend in unpriced] == [
        ("unanswered_attempt", None)
    ] * failure.unanswered


def test_a_transient_failure_that_clears_answers_inside_the_same_deadline() -> None:
    clock = ScriptedClock()
    client, provider = scripted_client(clock, [status(500), status(503), answer()])

    packet = client.run_research(QUESTION, FAST)

    assert packet.answer_markdown.startswith("Apple closed")
    assert clock.waits == [BACKOFF, 2 * BACKOFF]
    # A retry gets what is left of the one deadline, never a fresh ceiling.
    assert [budget(request) for request in provider.requests] == [
        FAST.timeout_seconds,
        FAST.timeout_seconds - BACKOFF,
        FAST.timeout_seconds - 3 * BACKOFF,
    ]


def test_a_rate_limit_waits_exactly_what_retry_after_asks() -> None:
    clock = ScriptedClock()
    client, provider = scripted_client(
        clock, [status(429, {"Retry-After": str(RETRY_AFTER_SECONDS)}), answer()]
    )

    packet = client.run_research(QUESTION, FAST)

    assert packet.answer_markdown.startswith("Apple closed")
    assert clock.waits == [RETRY_AFTER_SECONDS]
    assert budget(provider.requests[1]) == FAST.timeout_seconds - RETRY_AFTER_SECONDS


def test_a_wait_that_would_leave_under_half_the_deadline_is_not_taken() -> None:
    clock = ScriptedClock()
    too_long = str(int(FAST.timeout_seconds / 2) + 1)
    client, provider = scripted_client(clock, [status(429, {"Retry-After": too_long})])

    with pytest.raises(ResearchUnavailableError) as raised:
        client.run_research(QUESTION, FAST)

    assert raised.value.status == 429 and raised.value.transient
    assert len(provider.requests) == 1
    assert clock.waits == []


def test_retry_after_as_a_past_http_date_asks_again_at_once() -> None:
    clock = ScriptedClock()
    client, provider = scripted_client(
        clock,
        [status(503, {"Retry-After": "Wed, 21 Oct 2015 07:28:00 GMT"}), answer()],
    )

    client.run_research(QUESTION, FAST)

    assert clock.waits == [0.0]
    assert len(provider.requests) == 2


def test_a_poll_is_left_to_the_poller_and_not_retried_by_the_client() -> None:
    clock = ScriptedClock()
    client, provider = scripted_client(clock, [status(500)])

    with pytest.raises(ResearchUnavailableError):
        client.poll_background("resp_bg1", timeout_seconds=FAST.timeout_seconds)

    assert len(provider.requests) == 1
    assert clock.waits == []


@pytest.mark.parametrize(
    ("error", "retried"),
    [
        (httpx.ConnectError, True),
        (httpx.ConnectTimeout, True),
        (httpx.PoolTimeout, True),
        (httpx.ReadTimeout, False),
        (httpx.ReadError, False),
        (httpx.WriteTimeout, False),
        (httpx.WriteError, False),
        (httpx.RemoteProtocolError, False),
    ],
    ids=lambda value: value.__name__ if isinstance(value, type) else str(value),
)
def test_a_transport_error_is_asked_again_only_when_the_request_never_left_argus(
    monkeypatch: pytest.MonkeyPatch, error: type[httpx.TransportError], retried: bool
) -> None:
    unpriced: list[Any] = []
    monkeypatch.setattr(perplexity_agent, "record_unpriced_spend", unpriced.append)
    clock = ScriptedClock()
    client, provider = scripted_client(clock, [transport_error(error), answer()])

    if retried:
        assert client.run_research(QUESTION, FAST).answer_markdown.startswith("Apple")
    else:
        with pytest.raises(ResearchUnavailableError) as raised:
            client.run_research(QUESTION, FAST)
        assert raised.value.transient and raised.value.sent

    assert len(provider.requests) == (2 if retried else 1)
    assert len(unpriced) == (0 if retried else 1)


def test_an_unmapped_os_error_fails_closed_as_a_sent_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unpriced: list[Any] = []
    monkeypatch.setattr(perplexity_agent, "record_unpriced_spend", unpriced.append)

    def step(_request: httpx.Request) -> httpx.Response:
        raise OSError("scripted socket failure")

    clock = ScriptedClock()
    client, provider = scripted_client(clock, [step, answer()])

    with pytest.raises(ResearchUnavailableError) as raised:
        client.run_research(QUESTION, FAST)

    error = raised.value
    assert (error.reason, error.transient, error.sent) == ("transport", True, True)
    assert len(provider.requests) == 1
    assert [spend.reason for spend in unpriced] == ["unanswered_attempt"]


def submitted() -> Step:
    return lambda _request: httpx.Response(200, json={"id": "resp_bg1", "status": "queued"})


@pytest.mark.parametrize(
    ("first", "sent"),
    [
        (status(500), 2),
        (status(429, {"Retry-After": "1"}), 2),
        (transport_error(httpx.ConnectError), 2),
        (transport_error(httpx.ReadTimeout), 1),
        (transport_error(httpx.RemoteProtocolError), 1),
    ],
    ids=["http_500", "http_429", "connection_refused", "read_timeout", "connection_dropped"],
)
def test_a_background_submission_is_sent_again_only_when_no_run_can_have_started(
    monkeypatch: pytest.MonkeyPatch, first: Step, sent: int
) -> None:
    unpriced: list[Any] = []
    monkeypatch.setattr(perplexity_agent, "record_unpriced_spend", unpriced.append)
    clock = ScriptedClock()
    client, provider = scripted_client(clock, [first, submitted()])

    if sent == 2:
        assert client.submit_background(QUESTION, FAST) == "resp_bg1"
        assert unpriced == []
    else:
        with pytest.raises(ResearchUnavailableError) as raised:
            client.submit_background(QUESTION, FAST)
        # A run may already be billing: no Retry for the reader, and it is on record.
        assert raised.value.run_may_be_billing and not raised.value.transient
        assert [spend.reason for spend in unpriced] == ["unanswered_attempt"]

    assert len(provider.requests) == sent


@pytest.mark.parametrize(
    ("steps", "code"),
    [
        ([transport_error(httpx.ReadTimeout)], "research_lookup_unavailable"),
        ([transport_error(httpx.RemoteProtocolError)], "research_lookup_unavailable"),
        ([status(503)] * ATTEMPTS, "research_lookup_failed"),
    ],
    ids=["read_timeout", "connection_dropped", "server_error"],
)
def test_a_background_submission_offers_retry_only_when_no_run_can_be_billing(
    monkeypatch: pytest.MonkeyPatch, steps: list[Step], code: str
) -> None:
    from argus.api.chat import research_jobs

    from tests.research.test_research_jobs import _job_request, _JobGateway

    unpriced: list[Any] = []
    monkeypatch.setattr(perplexity_agent, "record_unpriced_spend", unpriced.append)
    gateway = _JobGateway()
    monkeypatch.setattr(api_state, "supabase_gateway", gateway)
    client, provider = scripted_client(ScriptedClock(), list(steps))
    monkeypatch.setattr(research_jobs, "_client", lambda: client)
    runtime_result: dict[str, Any] = {"research_job_request": _job_request()}

    job = research_jobs.apply_research_job_request(
        runtime_result,
        user_id="u1",
        conversation_id="c1",
        request_message_id="m1",
        request_id="r1",
    )

    retryable = code in DURABLE_RETRY_RECOVERY_CODES
    assert job is None and gateway.rows == {}
    assert runtime_result["recovery"] == {"code": code, "retryable": retryable}
    assert len(provider.requests) == len(steps)
    assert len(unpriced) == (0 if retryable else 1)


@pytest.mark.parametrize(
    ("error", "transient"),
    [
        (ResearchUnavailableError("http_error", status=500), True),
        (ResearchUnavailableError("http_error", status=503), True),
        (ResearchUnavailableError("http_error", status=429), True),
        (ResearchUnavailableError("timeout"), True),
        (ResearchUnavailableError("transport"), True),
        (ResearchUnavailableError("http_error", status=400), False),
        (ResearchUnavailableError("http_error", status=404), False),
        (ResearchUnavailableError("not_configured", status=401), False),
        (ResearchUnavailableError("not_configured"), False),
        (ResearchUnavailableError("malformed_response"), False),
        (ResearchUnavailableError("empty_answer"), False),
        (ResearchUnavailableError("timeout", run_may_be_billing=True), False),
    ],
)
def test_transient_is_derived_from_the_status_or_the_reason(
    error: ResearchUnavailableError, transient: bool
) -> None:
    assert error.transient is transient


@pytest.mark.parametrize(
    ("error", "ruled_out"),
    [
        (ResearchUnavailableError("http_error", status=500), True),
        (ResearchUnavailableError("http_error", status=503), True),
        (ResearchUnavailableError("http_error", status=429), True),
        (ResearchUnavailableError("transport", sent=False), True),
        (ResearchUnavailableError("timeout", sent=False), True),
        (ResearchUnavailableError("timeout"), False),
        (ResearchUnavailableError("transport"), False),
        (ResearchUnavailableError("http_error", status=400), False),
        (ResearchUnavailableError("not_configured", sent=False), False),
        (ResearchUnavailableError("malformed_response"), False),
    ],
)
def test_paid_work_is_ruled_out_only_by_a_429_a_5xx_or_a_request_never_sent(
    error: ResearchUnavailableError, ruled_out: bool
) -> None:
    assert error.paid_work_ruled_out is ruled_out


# --- The turn: a recovery, never an answer, and the outage is recorded -------


def _wire(monkeypatch: pytest.MonkeyPatch, failure: Failure) -> None:
    set_research_query(
        monkeypatch, globals(), question_kind="live_quote", symbols=["AAPL"]
    )
    if not failure.api_key:
        monkeypatch.setattr(grounded, "_client", lambda: None)
        return
    clock = ScriptedClock()
    client, _provider = scripted_client(clock, failure.steps(clock))
    monkeypatch.setattr(grounded, "_client", lambda: client)


@pytest.mark.parametrize("failure", FAILURES, ids=lambda failure: failure.name)
def test_a_failed_lookup_ends_the_turn_on_its_recovery(
    monkeypatch: pytest.MonkeyPatch, failure: Failure
) -> None:
    _wire(monkeypatch, failure)

    result = run_research_turn(QUESTION)

    assert result is not None
    patch = result.stage_patch
    code = failure.recovery_code
    assert patch["recovery"] == {"code": code, "retryable": failure.transient}
    # Only the transient code settles with a durable retry, as discovery's does.
    assert (code in DURABLE_RETRY_RECOVERY_CODES) is failure.transient
    assert patch["assistant_response"] == RECOVERY_FALLBACK_MESSAGES[code]
    assert "next_experiments" not in patch
    sidecar = patch["research"]
    assert sidecar["degraded"] == failure.degraded
    assert sidecar["rows"] == []
    assert sidecar["sources"] == []
    assert sidecar["anchor_symbols"] == ["AAPL"]


def test_a_turn_whose_retry_clears_publishes_the_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_research_query(
        monkeypatch, globals(), question_kind="live_quote", symbols=["AAPL"]
    )
    clock = ScriptedClock()
    client, provider = scripted_client(clock, [status(500), answer()])
    monkeypatch.setattr(grounded, "_client", lambda: client)

    result = run_research_turn(QUESTION)

    assert result is not None
    assert "recovery" not in result.stage_patch
    assert result.stage_patch["assistant_response"].startswith("Apple closed")
    assert clock.waits == [BACKOFF]
    assert request_body(provider.requests[0]) == request_body(provider.requests[1])


class _LedgerGateway(SupabaseGateway):
    def __init__(self) -> None:
        super().__init__(client=_RecordingSupabaseClient())
        self.entries: list[dict[str, Any]] = []

    def create_cost_ledger_entry(self, *, entry: dict[str, Any]) -> dict[str, Any]:
        row = super().create_cost_ledger_entry(entry=entry)
        self.entries.append(row)
        return row


@pytest.mark.parametrize("failure", FAILURES, ids=lambda failure: failure.name)
def test_the_ledger_counts_an_outage_by_its_code_and_status(
    monkeypatch: pytest.MonkeyPatch, failure: Failure
) -> None:
    ledger = _LedgerGateway()
    monkeypatch.setattr(api_state, "supabase_gateway", ledger)
    _wire(monkeypatch, failure)

    result = run_research_turn(QUESTION)
    assert result is not None
    record_research_turn_evidence(
        research=result.stage_patch["research"],
        user_id="u1",
        conversation_id="c1",
        message_id="m1",
        request_id="r1",
    )

    metadata = ledger.entries[-1]["usage_metadata"]
    assert metadata["degraded_code"] == failure.degraded["code"]
    assert metadata.get("degraded_status") == failure.status


# --- The chat route: the same settlement and retry discovery uses -----------


def _final_payload(stream: str) -> dict[str, Any]:
    events = [
        json.loads(line.removeprefix("data: "))
        for line in stream.splitlines()
        if line.startswith("data: {")
    ]
    finals = [event for event in events if event.get("type") == "final"]
    assert len(finals) == 1
    return finals[0]["payload"]


def _chat_over_the_rail(monkeypatch: pytest.MonkeyPatch, steps: list[Step]):
    """The chat route, with each turn composed by the real research rail over
    a scripted provider. Returns the API client, the provider and the message
    every turn was asked."""
    from argus.agent_runtime.research_query import ResearchQueryExtraction
    from argus.agent_runtime.runtime import _public_result
    from argus.agent_runtime.state.models import RunState, UserState
    from argus.api.main import app
    from argus.api.routers import agent as agent_router
    from fastapi.testclient import TestClient

    clock = ScriptedClock()
    client, provider = scripted_client(clock, steps)
    monkeypatch.setattr(grounded, "_client", lambda: client)
    interpretation = educational_interpretation().model_copy(
        update={
            "research_query": ResearchQueryExtraction(
                question_kind="live_quote", symbols=["AAPL"]
            )
        }
    )
    asked: list[str] = []

    async def _research_turn(*, message: str, user: UserState, **_: Any):
        asked.append(message)
        result = await ra.research_answer_stage_result(
            interpretation=interpretation,
            state=RunState.new(current_user_message=message, recent_thread_history=[]),
            user=UserState(user_id=user.user_id, language_preference="en"),
        )
        assert result is not None
        yield {
            "type": "final",
            "payload": _public_result(
                {"stage_outcome": result.outcome, **result.stage_patch}
            ),
        }

    monkeypatch.setattr(agent_router, "stream_agent_turn_events", _research_turn)
    api = TestClient(app)
    api.post("/api/v1/dev/reset")
    return api, provider, asked


def _ask(api, conversation_id: str) -> dict[str, Any]:
    response = api.post(
        "/api/v1/chat/stream",
        json={"conversation_id": conversation_id, "message": QUESTION, "language": "en"},
    )
    assert response.status_code == 200
    return _final_payload(response.text)


def _messages(api, conversation_id: str) -> list[dict[str, Any]]:
    return api.get(f"/api/v1/conversations/{conversation_id}/messages").json()["items"]


def test_an_outage_settles_with_a_durable_retry_that_asks_the_same_question(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api, provider, asked = _chat_over_the_rail(
        monkeypatch, [*[status(500)] * ATTEMPTS, answer()]
    )
    conversation_id = api.post("/api/v1/conversations", json={}).json()["conversation"][
        "id"
    ]

    live = _ask(api, conversation_id)

    assert live["recovery"] == {"code": "research_lookup_failed", "retryable": True}
    assert live["retry_last_turn"] == {"message": QUESTION}
    assert live["research"]["degraded"] == {
        "code": "research_unavailable_http_error",
        "status": 500,
    }
    assert "next_experiments" not in live

    request, failure = _messages(api, conversation_id)[-2:]
    assert request["role"] == "user" and request["content"] == QUESTION
    assert failure["content"] == RECOVERY_FALLBACK_MESSAGES["research_lookup_failed"]
    assert failure["metadata"]["agent_runtime_turn"] == {
        "turn_id": request["id"],
        "request_id": failure["metadata"]["agent_runtime_turn"]["request_id"],
        "status": "recoverable_failed",
        "terminal": True,
        "reconciled_outcome": None,
        "failure_code": "research_lookup_failed",
        "retryable": True,
    }
    assert failure["metadata"]["retry_last_turn"] == {
        "request_message_id": request["id"],
        "message": QUESTION,
    }
    assert failure["metadata"]["recovery"] == live["recovery"]
    assert failure["metadata"]["research"]["degraded"] == live["research"]["degraded"]
    assert "next_experiments" not in failure["metadata"]

    # Retry re-sends the persisted question, and the rail asks the provider again.
    retried = _ask(api, conversation_id)

    assert "recovery" not in retried
    assert retried["assistant_response"].startswith("Apple closed")
    assert asked == [QUESTION, QUESTION]
    assert len(provider.requests) == ATTEMPTS + 1
    assert all(QUESTION in request_body(sent)["input"] for sent in provider.requests)
    assert _messages(api, conversation_id)[-1]["content"].startswith("Apple closed")


def test_a_refused_request_ends_on_the_quiet_recovery_with_nothing_to_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api, provider, asked = _chat_over_the_rail(monkeypatch, [status(400)])
    conversation_id = api.post("/api/v1/conversations", json={}).json()["conversation"][
        "id"
    ]

    live = _ask(api, conversation_id)

    assert live["recovery"] == {"code": "research_lookup_unavailable", "retryable": False}
    assert "retry_last_turn" not in live
    assert live["research"]["degraded"] == {
        "code": "research_unavailable_http_error",
        "status": 400,
    }
    assert len(provider.requests) == 1

    failure = _messages(api, conversation_id)[-1]
    assert failure["content"] == RECOVERY_FALLBACK_MESSAGES["research_lookup_unavailable"]
    assert failure["metadata"]["agent_runtime_turn"]["status"] == "completed"
    assert "retry_last_turn" not in failure["metadata"]
    assert failure["metadata"]["recovery"] == live["recovery"]
    assert asked == [QUESTION]


# --- A registered call: its recovery speaks for its turn only when it is alone -


TRANSIENT_RECOVERY = {"code": "research_lookup_failed", "retryable": True}


@pytest.mark.asyncio()
@pytest.mark.parametrize("tool_name", ["thorough_research", "balanced_lookup"])
@pytest.mark.parametrize(
    ("calls", "turn_recovery"),
    [(1, TRANSIENT_RECOVERY), (2, None)],
    ids=["one_call", "two_calls"],
)
async def test_a_registered_lookup_failure_settles_a_turn_only_when_alone(
    monkeypatch: pytest.MonkeyPatch,
    tool_name: str,
    calls: int,
    turn_recovery: dict[str, Any] | None,
) -> None:
    """A registered research call whose lookup fails ends on the lookup recovery,
    published through the same projection its answer would take: a thorough
    call when its background submission fails at publication, a balanced call
    when its inline lookup fails at execution. One call's recovery settles its
    turn; a turn with several calls keeps each failure on its own card instead
    of settling as one failure."""
    from argus.api.chat import research_jobs
    from argus.api.chat.tool_results import prepare_runtime_tool_publication
    from argus.domain.tool_contracts import ToolResultCard

    from tests.research.test_registry_discarded_spend import _call, _execute
    from tests.research.test_research_jobs import _JobGateway

    class _SubmissionDown:
        def submit_background(self, prompt: str, spec: Any) -> str:
            raise ResearchUnavailableError("http_error", "http 503", status=503)

    gateway = _JobGateway()
    monkeypatch.setattr(api_state, "supabase_gateway", gateway)
    monkeypatch.setattr(research_jobs, "_client", lambda: _SubmissionDown())
    clock = ScriptedClock()
    inline, _provider = scripted_client(clock, [status(503)] * ATTEMPTS * calls)
    monkeypatch.setattr(grounded, "_client", lambda: inline)
    result = await _execute(*[_call(tool_name) for _ in range(calls)])
    runtime_result = result.stage_patch

    publication = prepare_runtime_tool_publication(
        runtime_result,
        runtime_result["tool_effects"],
        assistant_text=None,
        user_id="u1",
        conversation_id="c1",
        request_message_id="m1",
        request_id="r1",
    )

    assert gateway.rows == {}
    cards = [ToolResultCard.model_validate(card) for card in publication.cards]
    assert [card.outcome.status for card in cards] == ["unavailable"] * calls
    assert all(
        effect.stage_patch["recovery"] == TRANSIENT_RECOVERY
        for effect in publication.effects
    )
    assert runtime_result.get("recovery") == turn_recovery
    if turn_recovery is not None:
        assert runtime_result["research"]["degraded"] == {
            "code": "research_unavailable_http_error",
            "status": 503,
        }
        assert (
            publication.assistant_text
            == RECOVERY_FALLBACK_MESSAGES["research_lookup_failed"]
        )
