"""Recorder correctness only: these fixtures are not latency evidence."""

import json

import httpx
import pytest
from faker import Faker

from scripts.benchmarks import run_turn_latency as runner
from scripts.benchmarks.summarize_turn_latency import summarize
from scripts.benchmarks.turn_latency import StreamObservation, distribution, poll_job

fake = Faker()


def frame(value, newline="\n"):
    return "data: " + json.dumps(value) + newline + newline


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_only_complete_nonempty_token_frames_start_token_clock(newline):
    observation = StreamObservation()
    observation.feed(frame({"type": "stage_start", "stage": "interpret"}, newline), 10)
    observation.feed(frame({"type": "token", "content": "  "}, newline), 20)
    token = frame({"type": "token", "content": fake.sentence()}, newline)
    observation.feed(token[:-1], 30)
    assert observation.timings.get("first_token_ms") is None
    observation.feed(token[-1:], 40)
    observation.feed(frame({"type": "token", "content": fake.word()}, newline), 50)
    assert observation.timings["first_token_ms"] == 40
    assert observation.timings["first_stage_ms"] == 10


@pytest.mark.parametrize("key", ["confirmation", "confirmation_card"])
@pytest.mark.parametrize("nested", [False, True])
def test_card_is_visible_but_is_not_a_token(key, nested):
    observation = StreamObservation()
    payload = {key: {"title": fake.sentence()}, "assistant_response": fake.sentence()}
    if nested:
        payload = {"final_response_payload": payload}
    observation.feed(
        frame(
            {
                "type": "final",
                "payload": payload,
            }
        ),
        100,
    )
    observation.feed("data: [DONE]\n\n", 105)
    assert observation.timings.get("first_token_ms") is None
    assert observation.timings["first_visible_ms"] == 100
    assert observation.timings["done_ms"] == 105
    assert observation.visible_kind == "confirmation_card"


def test_recorded_events_never_retain_payload_text_or_identifiers():
    private_text, private_id = fake.sentence(), fake.uuid4()
    observation = StreamObservation()
    observation.feed(frame({"type": "token", "content": private_text}), 15)
    observation.feed(
        frame(
            {
                "type": "final",
                "payload": {
                    "message_id": private_id,
                    "assistant_response": private_text,
                },
            }
        ),
        20,
    )
    serialized = json.dumps(observation.events)
    assert private_text not in serialized
    assert private_id not in serialized


def test_no_done_frame_does_not_become_a_completed_turn():
    observation = StreamObservation()
    observation.feed(frame({"type": "final", "payload": {}}), 100)
    assert observation.timings.get("done_ms") is None


def test_distribution_preserves_missing_and_observed_nearest_rank_tails():
    assert distribution([None, None]) == {"n": 0, "missing": 2}
    result = distribution([None, *range(1, 21)])
    assert result == {"n": 20, "missing": 1, "min": 1, "p50": 10, "p95": 19, "max": 20}


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1])
def test_distribution_rejects_invalid_measurements(value):
    with pytest.raises(ValueError):
        distribution([value])


@pytest.mark.parametrize(
    "scope,artifact", [("chat.research", "result_message"), ("chat.run_backtest", "run")]
)
def test_succeeded_job_waits_for_its_terminal_artifact(scope, artifact):
    responses = iter(
        [
            {"job": {"status": "succeeded", "operation_scope": scope}, artifact: None},
            {
                "job": {"status": "succeeded", "operation_scope": scope},
                artifact: {"id": fake.uuid4(), "content": fake.sentence()},
            },
        ]
    )
    with httpx.Client(
        base_url="https://example.test",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=next(responses))
        ),
    ) as client:
        result = poll_job(client, fake.uuid4(), 0, interval=0)
    assert len(result["polls"]) == 2
    assert result["status"] == "succeeded"


@pytest.mark.parametrize("failure", ["http", "sse", "receipts"])
def test_attempt_survives_transport_sse_or_telemetry_failure(monkeypatch, failure):
    def receipts(*args):
        if failure == "receipts":
            raise runner.psycopg.OperationalError("private connection detail")
        return []

    monkeypatch.setattr(runner, "receipts_for", receipts)
    content = (
        frame({"type": "error", "code": "runtime_failure"})
        if failure == "sse"
        else frame({"type": "final", "payload": {}})
    )
    content += "data: [DONE]\n\n"
    with httpx.Client(
        base_url="https://example.test",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                503 if failure == "http" else 200,
                text=content,
                headers={"x-request-id": fake.uuid4()},
            )
        ),
    ) as client:
        row, _, _ = runner.observe(
            client,
            None,
            {"language": "en", "conversation_id": fake.uuid4()},
            category="ordinary_chat",
            sample_id="test",
            case_id="test",
        )
    assert "private connection detail" not in json.dumps(row)
    if failure == "receipts":
        assert row["receipt_status"] == "unavailable"
    else:
        assert row["status"] == "stream_error"
        assert row["completion_ms"] is None


def test_poll_failure_retains_the_observed_prefix():
    responses = iter([200, 503])

    def handle(request):
        return httpx.Response(
            next(responses),
            json={"job": {"status": "running", "operation_scope": "chat.research"}},
        )

    with httpx.Client(
        base_url="https://example.test", transport=httpx.MockTransport(handle)
    ) as client:
        result = poll_job(client, fake.uuid4(), 0, interval=0)
    assert result["status"] == "measurement_error"
    assert result["completion_ms"] is None
    assert result["polls"][0]["status"] == "running"


@pytest.mark.parametrize(
    "failure,expected_status,failure_group",
    [
        (None, "succeeded", None),
        ("transport", "stream_error", "stream_error"),
        ("sse", "stream_error", "stream_error"),
        ("truncated", "incomplete_stream", "incomplete"),
    ],
)
@pytest.mark.parametrize(
    "scope,artifact,category",
    [
        ("chat.research", "result_message", "research_thorough"),
        ("chat.run_backtest", "run", "backtest_run"),
    ],
)
def test_successful_job_cannot_hide_a_broken_stream(
    monkeypatch, failure, expected_status, failure_group, scope, artifact, category
):
    job = {"id": fake.uuid4(), "operation_scope": scope, "status": "succeeded"}
    monkeypatch.setattr(runner, "receipts_for", lambda *args: [])

    class JobEnvelopeStream(httpx.SyncByteStream):
        def __iter__(self):
            yield frame({"type": "final", "payload": {"backtest_job": job}}).encode()
            if failure == "transport":
                raise httpx.ReadError("private stream detail")
            if failure == "sse":
                yield frame({"type": "error", "code": "runtime_failure"}).encode()
            if failure != "truncated":
                yield b"data: [DONE]\n\n"

    def handle(request):
        if request.method == "POST":
            return httpx.Response(
                200,
                stream=JobEnvelopeStream(),
                headers={"x-request-id": fake.uuid4()},
            )
        return httpx.Response(
            200,
            json={
                "job": job,
                artifact: {"id": fake.uuid4(), "content": fake.sentence()},
            },
        )

    with httpx.Client(
        base_url="https://example.test", transport=httpx.MockTransport(handle)
    ) as client:
        row, _, _ = runner.observe(
            client,
            None,
            {"language": "en", "conversation_id": fake.uuid4()},
            category=category,
            sample_id="test",
            case_id="test",
        )

    assert row["status"] == expected_status
    assert row["job"]["status"] == "succeeded"
    assert row["job"]["completion_ms"] is not None
    assert "private stream detail" not in json.dumps(row)
    expected_group = category if failure_group is None else failure_group
    group = summarize([row])["groups"][expected_group]
    assert group["statuses"] == {expected_status: 1}
    if failure:
        assert row["completion_ms"] is None
        assert group["metrics"]["first_grounded_answer_ms"]["missing"] == 1
    else:
        assert row["completion_ms"] == row["job"]["completion_ms"]
