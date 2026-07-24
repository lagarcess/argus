from __future__ import annotations

from argus.api import state as api_state
from argus.api.chat.request_admission import prepare_chat_request_admission
from argus.api.message_store import memory_conversation
from argus.api.schemas import ChatActionPayload, ChatStreamRequest
from fastapi import Request


def _request(request_id: str = "request-1") -> Request:
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/chat/stream",
            "headers": [],
        }
    )
    request.state.request_id = request_id
    return request


def test_prepared_response_option_request_sanitizes_persisted_action() -> None:
    payload = ChatStreamRequest(
        conversation_id="conversation-1",
        action=ChatActionPayload(
            type="select_response_option",
            label="Retry with daily bars",
            labelKey="chat.clarification.timeframe_actions.daily",
            payload={
                "source_assistant_id": "assistant-recovery",
                "option_id": "option_0",
                "replacement_values": {"timeframe": "1D"},
            },
        ),
        language="en",
    )

    admission = prepare_chat_request_admission(
        payload=payload,
        request=_request(),
        user_id="user-1",
        conversation_id="conversation-1",
        display_message="Retry with daily bars",
        mention_provenance=[],
        enabled=True,
        language="en",
    )

    assert admission.request_message_candidate is not None
    assert admission.request_message_candidate.metadata["chat_action"] == {
        "type": "select_response_option",
        "label": "Retry with daily bars",
        "labelKey": "chat.clarification.timeframe_actions.daily",
        "payload": {
            "option_id": "option_0",
            "replacement_values": {"timeframe": "1D"},
        },
        "presentation": None,
    }


def test_prepared_request_persists_exactly_once() -> None:
    api_state.store.reset()
    conversation = memory_conversation(
        title="New conversation",
        title_source="system_default",
        language="en",
        user_id="user-1",
    )
    payload = ChatStreamRequest(
        conversation_id=conversation.id,
        message="Test AAPL",
        language="en",
    )
    admission = prepare_chat_request_admission(
        payload=payload,
        request=_request(),
        user_id="user-1",
        conversation_id=conversation.id,
        display_message="Test AAPL",
        mention_provenance=[],
        enabled=True,
        language="en",
    )

    first = admission.persist()
    second = admission.persist()

    assert first is not None
    assert second == first
    assert api_state.store.messages[conversation.id] == [first]


def test_ordinary_turn_accepts_message_and_lifecycle_atomically() -> None:
    api_state.store.reset()
    conversation = memory_conversation(
        title="New conversation",
        title_source="system_default",
        language="en",
        user_id="user-1",
    )
    admission = prepare_chat_request_admission(
        payload=ChatStreamRequest(
            conversation_id=conversation.id,
            message="Test AAPL",
            language="en",
        ),
        request=_request("request-ordinary"),
        user_id="user-1",
        conversation_id=conversation.id,
        display_message="Test AAPL",
        mention_provenance=[],
        enabled=True,
        language="en",
        owner="ordinary_turn",
    )

    accepted = admission.persist()

    assert accepted is not None
    assert api_state.store.messages[conversation.id] == [accepted]
    assert api_state.store.chat_turn_lifecycles[accepted.id] == {
        **api_state.store.chat_turn_lifecycles[accepted.id],
        "turn_id": accepted.id,
        "user_id": "user-1",
        "conversation_id": conversation.id,
        "request_id": "request-ordinary",
        "status": "accepted",
    }


def test_message_only_admission_appends_without_chat_turn_lifecycle() -> None:
    api_state.store.reset()
    conversation = memory_conversation(
        title="New conversation",
        title_source="system_default",
        language="en",
        user_id="user-1",
    )
    admission = prepare_chat_request_admission(
        payload=ChatStreamRequest(
            conversation_id=conversation.id,
            action=ChatActionPayload(
                type="run_backtest",
                label="Run backtest",
                payload={"confirmation_id": "confirmation-1"},
                presentation="confirmation",
            ),
        ),
        request=_request("request-run"),
        user_id="user-1",
        conversation_id=conversation.id,
        display_message="Run backtest",
        mention_provenance=[],
        enabled=True,
        language="en",
        owner="message_only",
    )

    appended = admission.persist()

    assert appended is not None
    assert api_state.store.messages[conversation.id] == [appended]
    assert api_state.store.chat_turn_lifecycles == {}
