"""Exercise the hosted history window through its real Supabase read method."""

import httpx
from argus.api import state as api_state
from argus.api.message_store import memory_message
from argus.domain.chat_turn_lifecycle import MemoryChatTurnLifecycleGateway
from argus.domain.supabase_gateway import SupabaseGateway

from supabase import ClientOptions, create_client
from tests.test_alpha_api_supabase import mock_gateway  # noqa: F401
from tests.test_chat_retry_history import chat, failure_reply, history  # noqa: F401


def test_latest_failure_retry_uses_newest_supabase_window(
    chat, mock_gateway, faker  # noqa: F811 - shared pytest fixtures
):
    ask, calls = chat
    conversation = next(iter(api_state.store.conversations.values()))
    user_id = mock_gateway.get_or_create_mock_user.return_value.id
    mock_gateway.get_conversation.return_value = conversation
    lifecycle = MemoryChatTurnLifecycleGateway(api_state.store)
    mock_gateway.accept_chat_turn.side_effect = lifecycle.accept_chat_turn
    mock_gateway.finalize_chat_turn.side_effect = lifecycle.finalize_chat_turn

    # Seed more than one bounded window before the latest failed lookup.
    for _ in range(11):
        for role in ("user", "assistant"):
            memory_message(
                conversation_id=conversation.id, role=role, content=faker.sentence()
            )

    def transport(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/rest/v1/messages"
        params = request.url.params
        assert params["user_id"] == f"eq.{user_id}"
        assert params["conversation_id"] == f"eq.{conversation.id}"
        rows = [
            item.model_dump(mode="json")
            for item in api_state.store.messages[conversation.id]
        ]
        # Emulate PostgREST order-before-limit, not the memory tail shortcut.
        for ordering in reversed(params["order"].split(",")):
            field, direction, *_ = ordering.split(".")
            rows.sort(key=lambda row: row[field], reverse=direction == "desc")
        return httpx.Response(200, json=rows[: int(params["limit"])])

    with httpx.Client(transport=httpx.MockTransport(transport)) as http:
        gateway = SupabaseGateway(
            client=create_client(
                "https://supabase.example.test",
                "fixture-key",
                options=ClientOptions(httpx_client=http),
            )
        )
        mock_gateway.list_messages.side_effect = gateway.list_messages
        question, failure = faker.sentence(), faker.sentence()
        valid = faker.sentence()
        ask(
            faker.sentence(),
            {
                "assistant_response": valid,
                "research": {"degraded": {"code": "result_followup_research_unused"}},
            },
        )
        messages = ask(question, failure_reply(failure))
        failed = messages[-1]
        assert failed.role == "assistant"
        assert len(messages) > 20
        expected = [(item.role, item.content) for item in messages[-20:-1]]

        retried = ask(
            question,
            {"assistant_response": faker.sentence()},
            failed_assistant_id=failed.id,
        )
        assert calls[-1]["message"] == question
        assert history(calls[-1]) == expected
        assert ("assistant", failure) not in history(calls[-1])
        assert ("user", question) in history(calls[-1])
        assert retried[-2].metadata["failed_assistant_id"] == failed.id
        ask(faker.sentence(), {"assistant_response": faker.sentence()})
        assert ("assistant", failure) not in history(calls[-1])
        assert ("assistant", valid) in history(calls[-1])
