"""Retry excludes one identified reply from runtime history, without paid calls."""

from __future__ import annotations

import json
from typing import Any

import pytest
from argus.api import state as api_state
from argus.api.main import app
from argus.api.routers import agent as agent_router
from faker import Faker
from fastapi.testclient import TestClient

fake = Faker()


@pytest.fixture
def chat(monkeypatch: pytest.MonkeyPatch):
    calls: list[dict[str, Any]] = []
    replies: list[dict[str, Any]] = []

    async def stream(**kwargs: Any):
        calls.append(kwargs)
        yield {
            "type": "final",
            "payload": {"stage_outcome": "ready_to_respond", **replies.pop(0)},
        }

    monkeypatch.setattr(agent_router, "stream_agent_turn_events", stream)
    with TestClient(app) as api:
        api.post("/api/v1/dev/reset")
        conversation_id = api.post("/api/v1/conversations", json={}).json()[
            "conversation"
        ]["id"]

        def ask(question: str, reply: dict[str, Any], **fields: Any):
            replies.append(reply)
            response = api.post(
                "/api/v1/chat/stream",
                json={
                    "conversation_id": conversation_id,
                    "message": question,
                    "language": "en",
                    **fields,
                },
            )
            assert response.status_code == 200
            assert any(
                json.loads(line[6:]).get("type") == "final"
                for line in response.text.splitlines()
                if line.startswith("data: {")
            )
            return list(api_state.store.messages[conversation_id])

        yield ask, calls


def failure_reply(content: str) -> dict[str, Any]:
    return {
        "assistant_response": content,
        "recovery": {"code": "research_lookup_failed", "retryable": True},
    }


def history(call: dict[str, Any]) -> list[tuple[str, str]]:
    return [(item.role, item.content) for item in call["recent_thread_history"]]


@pytest.mark.parametrize("under_answer", [False, True])
def test_retry_history_keeps_question_and_omits_only_target_reply(chat, under_answer):
    ask, calls = chat
    question = "What is Apple trading at right now?"
    unrelated, failed, answer = (fake.sentence() for _ in range(3))
    # Same question and another retryable reply: text equality must not retire it.
    ask(question, failure_reply(unrelated))
    reply = failure_reply(failed)
    if under_answer:
        reply["recovery"]["under_answer"] = True
    messages = ask(question, reply)
    failed_id = messages[-1].id
    messages = ask(
        question, {"assistant_response": answer}, failed_assistant_id=failed_id
    )

    assert calls[-1]["message"] == question
    assert history(calls[-1]) == [
        ("user", question),
        ("assistant", unrelated),
        ("user", question),
    ]
    assert messages[-2].metadata["failed_assistant_id"] == failed_id
    ask(fake.sentence(), {"assistant_response": fake.sentence()})
    assert ("assistant", unrelated) in history(calls[-1])
    assert ("assistant", failed) not in history(calls[-1])


@pytest.mark.parametrize("legacy_link", [False, True])
def test_later_followup_preserves_other_degraded_replies(chat, legacy_link):
    ask, calls = chat
    question = "What is Apple trading at right now?"
    valid, failed, answer = (fake.sentence() for _ in range(3))
    ask(
        question,
        {
            "assistant_response": valid,
            "research": {"degraded": {"code": "result_followup_research_unused"}},
        },
    )
    messages = ask(question, failure_reply(failed))
    # Different replay wording proves the durable link, not the text fallback.
    replay = "Please look up Apple's current quote."
    messages = ask(
        replay, {"assistant_response": answer}, failed_assistant_id=messages[-1].id
    )
    if legacy_link:
        metadata = messages[-2].metadata
        metadata["chat_action"] = {
            "type": "retry_last_turn",
            "payload": {"failed_assistant_id": metadata.pop("failed_assistant_id")},
        }
    ask("When was that?", {"assistant_response": fake.sentence()})

    assert history(calls[-1]) == [
        ("user", question),
        ("assistant", valid),
        ("user", question),
        ("user", replay),
        ("assistant", answer),
    ]


@pytest.mark.parametrize("target", ["absent", "unmatched", "user"])
def test_retry_identity_never_removes_other_roles_or_unidentified_replies(chat, target):
    ask, calls = chat
    question, failed = fake.sentence(), fake.sentence()
    messages = ask(question, failure_reply(failed))
    fields = (
        {}
        if target == "absent"
        else {
            "failed_assistant_id": messages[-2].id if target == "user" else fake.uuid4()
        }
    )
    ask(question, {"assistant_response": fake.sentence()}, **fields)
    ask(fake.sentence(), {"assistant_response": fake.sentence()})
    assert ("assistant", failed) in history(calls[-1])
    assert ("user", question) in history(calls[-1])
