"""Supabase result transport keeps authored prose private and typed facts public."""

from typing import Any

import pytest
from argus.api.schemas import Conversation, Message
from argus.domain.store import utcnow

from tests.test_alpha_api_supabase import (
    _final_payload,
    _mock_profile,
    _patch_engine_io,  # noqa: F401
    _runtime_success_events,
    _stream_events,
    client,
    mock_gateway,  # noqa: F401
)


def test_chat_stream_supabase_sends_legacy_stage_profile_to_runtime(
    mock_gateway,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
):
    from argus.api.routers import agent as agent_router

    async def _result_events_with_explain_stage(**kwargs: Any):
        async for event in _runtime_success_events(**kwargs):
            if event["type"] == "token":
                yield {"type": "stage_start", "stage": "explain"}
            yield event

    monkeypatch.setattr(
        agent_router, "stream_agent_turn_events", _result_events_with_explain_stage
    )
    now = utcnow()
    conversation = Conversation(
        id="conv-2",
        title="New conversation",
        title_source="system_default",
        language="en",
        pinned=False,
        archived=False,
        last_message_preview=None,
        deleted_at=None,
        created_at=now,
        updated_at=now,
    )
    mock_gateway.get_conversation.return_value = conversation
    mock_gateway.get_user.return_value = _mock_profile(stage="language_selection")
    mock_gateway.count_completed_runs.return_value = 0
    mock_gateway.create_message.side_effect = lambda **kwargs: Message(
        id="msg-2",
        conversation_id=kwargs["conversation_id"],
        role=kwargs["role"],  # type: ignore[arg-type]
        content=kwargs["content"],
        created_at=utcnow(),
    )

    response = client.post(
        "/api/v1/chat/stream",
        json={"conversation_id": "conv-2", "message": "Test TSLA dip idea"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert "event:" not in response.text
    assert response.text.count("data: [DONE]") == 1
    events = _stream_events(response.text)
    token_events = [event for event in events if event.get("type") == "token"]
    assert token_events == []
    accepted = mock_gateway.accept_chat_turn.call_args.kwargs["message"]
    assert accepted.role == "user"
    assert accepted.content == "Test TSLA dip idea"
    final_payload = _final_payload(response.text)
    terminal = mock_gateway.finalize_chat_turn.call_args.kwargs
    assert terminal["to_status"] == "completed"
    assert final_payload["stage_outcome"] == "ready_to_respond"
    assert final_payload["assistant_response"] == ""
    assert terminal["message"].content == "I tested that idea with TSLA."
    finalized_run = mock_gateway.finalize_backtest_completion.call_args.kwargs[
        "finalization"
    ].run
    assert final_payload["run"]["metrics"] == finalized_run.metrics
    assert final_payload["run"]["config_snapshot"] == finalized_run.config_snapshot
    assert final_payload["run"]["symbols"] == ["TSLA"]
    assert final_payload["message_id"] == terminal["message"].id
    mock_gateway.finalize_backtest_completion.assert_called_once()
