"""Merged retry admission keeps the owned frozen prefix and naming exclusion."""

from uuid import uuid4

import httpx
import pytest
from argus.api import state as api_state
from argus.api.message_store import (
    load_chat_request_history,
    load_runtime_thread_history,
    memory_message,
)
from argus.api.schemas import ChatStreamRequest
from argus.domain.supabase_gateway import SupabaseGateway

from supabase import ClientOptions, create_client
from tests.test_shared_fork_history import seed_imported


@pytest.mark.parametrize("persisted", [False, True])
@pytest.mark.parametrize("target", ["latest", "unmatched", "imported"])
def test_retry_uses_owned_snapshot_without_losing_imports_or_naming_boundary(
    monkeypatch, persisted, target
):
    api_state.store.reset()
    monkeypatch.setattr(api_state, "supabase_gateway", None)
    owner, chat, imported = seed_imported(count=12, ordinary=25)
    memory_message(conversation_id=chat.id, role="user", content="Current quote?")
    failed = memory_message(
        conversation_id=chat.id,
        role="assistant",
        content="The lookup failed.",
        metadata={"recovery": {"code": "research_lookup_failed", "retryable": True}},
    )
    stored = list(api_state.store.messages[chat.id])
    target_id = {
        "latest": failed.id,
        "unmatched": str(uuid4()),
        "imported": stored[1].id,
    }[target]
    reads = []

    def transport(request):
        assert request.method == "GET"
        assert request.url.path == "/rest/v1/messages"
        params = request.url.params
        assert params["user_id"] == f"eq.{owner}"
        assert params["conversation_id"] == f"eq.{chat.id}"
        reads.append(params)
        rows = [message.model_dump(mode="json") for message in stored]
        if "metadata" in params:
            assert params["metadata"] == 'cs.{"shared_conversation":{}}'
            rows = [row for row in rows if "shared_conversation" in row["metadata"]]
        for ordering in reversed(params["order"].split(",")):
            field, direction, *_ = ordering.split(".")
            rows.sort(key=lambda row: row[field], reverse=direction == "desc")
        start = int(params.get("offset", 0))
        return httpx.Response(200, json=rows[start : start + int(params["limit"])])

    with httpx.Client(transport=httpx.MockTransport(transport)) as http:
        if persisted:
            monkeypatch.setattr(
                api_state,
                "supabase_gateway",
                SupabaseGateway(
                    client=create_client(
                        "https://supabase.example.test",
                        "fixture-key",
                        options=ClientOptions(httpx_client=http),
                    )
                ),
            )
        payload, history = load_chat_request_history(
            user_id=owner,
            conversation_id=chat.id,
            payload=ChatStreamRequest(
                conversation_id=chat.id,
                message="Try again",
                failed_assistant_id=target_id,
            ),
        )
        assert payload.failed_assistant_id == (failed.id if target == "latest" else None)
        expected = [row["content"] for row in imported] + [
            message.content
            for message in stored[-20:]
            if not (target == "latest" and message.id == failed.id)
        ]
        assert [message.content for message in history] == expected
        assert sum(message.shared_context for message in history) == len(imported)
        if persisted:
            assert len(reads) == 2
        named = load_runtime_thread_history(
            user_id=owner, conversation_id=chat.id, drop_shared_turns=True
        )
        assert [message.content for message in named] == [
            message.content for message in stored[-20:]
        ]
        assert not any(message.shared_context for message in named)
        if persisted:
            assert len(reads) == 3
        else:
            other_payload, other_history = load_chat_request_history(
                user_id=str(uuid4()), conversation_id=chat.id, payload=payload
            )
            assert other_history == [] and other_payload.failed_assistant_id is None
