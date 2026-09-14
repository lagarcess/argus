"""A computed answer that landed after later turns reads the question it answers."""

from __future__ import annotations

from types import SimpleNamespace

from argus.api.main import app
from argus.api.message_store import create_message
from argus.api.search_computed import question_for_answer
from fastapi.testclient import TestClient


def test_an_answer_reads_the_question_it_records_not_the_latest_before_it() -> None:
    client = TestClient(app)
    client.post("/api/v1/dev/reset")
    owner = client.get("/api/v1/me").json()["user"]["id"]
    conversation = client.post(
        "/api/v1/conversations", json={"title": "Two questions"}
    ).json()["conversation"]["id"]
    asked = create_message(
        user_id=owner,
        conversation_id=conversation,
        role="user",
        content="What does 10,000 at 5% become in ten years?",
    )
    create_message(
        user_id=owner,
        conversation_id=conversation,
        role="user",
        content="And what about my car loan?",
    )
    recorded = create_message(
        user_id=owner,
        conversation_id=conversation,
        role="assistant",
        content="The research answer.",
        metadata={"request_message_id": asked.id},
    )
    inline = create_message(
        user_id=owner,
        conversation_id=conversation,
        role="assistant",
        content="An inline answer.",
        metadata={},
    )
    user = SimpleNamespace(id=owner)

    assert (
        question_for_answer(user, recorded.model_dump(mode="python"))
        == "What does 10,000 at 5% become in ten years?"
    )
    assert (
        question_for_answer(user, inline.model_dump(mode="python"))
        == "And what about my car loan?"
    )
