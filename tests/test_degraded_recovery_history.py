from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from argus.agent_runtime.capabilities.contract import (
    build_default_capability_contract,
)
from argus.agent_runtime.llm_clarifier import (
    ClarificationRequest,
    OpenRouterClarificationGenerator,
)
from argus.agent_runtime.llm_interpreter import OpenRouterStructuredInterpreter
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.agent_runtime.state.models import UserState
from argus.api import state as api_state
from argus.api.message_store import (
    create_message,
    load_runtime_thread_history,
    memory_conversation,
)
from argus.api.routers.history import history as list_history
from argus.api.search_assembly import scored_memory_search_items
from argus.domain.supabase_gateway import SupabaseGateway
from langchain_core.messages import AIMessage

RAW_ENGLISH_FALLBACK = "Compatibility fallback must not reach the next model."
EXACT_LLM_VOICE = "Exact model voice stays available to the next turn."


@pytest.fixture(autouse=True)
def _memory_message_store(monkeypatch: pytest.MonkeyPatch):
    api_state.store.reset()
    monkeypatch.setattr(api_state, "supabase_gateway", None)
    yield
    api_state.store.reset()


def _degraded_clarification() -> dict[str, Any]:
    return {
        "clarification": {
            "kind": "unsupported_recovery",
            "reason_code": "unsupported_time_granularity",
            "prompt_source": "degraded_fallback",
            "requested_field": "timeframe",
            "requested_fields": ["timeframe"],
            "semantic_needs": ["simplification_choice"],
            "payload": {
                "raw_value": "5m",
                "strategy": {"asset_universe": ["AAPL"], "timeframe": "5m"},
            },
            "options": [
                {
                    "id": "option_0",
                    "replacement_values": {"timeframe": "1D"},
                }
            ],
        }
    }


def _llm_clarification() -> dict[str, Any]:
    return {
        "clarification": {
            "kind": "clarification",
            "reason_code": "missing_period",
            "prompt_source": "llm_generated",
            "requested_field": "date_range",
            "requested_fields": ["date_range"],
            "semantic_needs": ["period"],
            "payload": {"strategy": {"asset_universe": ["AAPL"]}},
            "options": [],
        }
    }


def test_degraded_compatibility_text_stays_durable_but_not_in_history_or_preview() -> (
    None
):
    user = api_state.store.get_or_create_dev_user()
    user_id = user.id
    conversation = memory_conversation(
        title="AAPL idea",
        title_source="system_default",
        language="es-419",
        user_id=user_id,
    )
    create_message(
        user_id=user_id,
        conversation_id=conversation.id,
        role="user",
        content="Prueba AAPL con velas de cinco minutos.",
    )
    degraded = create_message(
        user_id=user_id,
        conversation_id=conversation.id,
        role="assistant",
        content=RAW_ENGLISH_FALLBACK,
        metadata=_degraded_clarification(),
    )

    persisted = api_state.store.messages[conversation.id]
    assert persisted[-1].id == degraded.id
    assert persisted[-1].content == RAW_ENGLISH_FALLBACK
    assert persisted[-1].metadata == _degraded_clarification()
    assert (
        api_state.store.conversations[conversation.id].last_message_preview
        == "Prueba AAPL con velas de cinco minutos."
    )
    assert RAW_ENGLISH_FALLBACK not in {
        item.content
        for item in load_runtime_thread_history(
            user_id=user_id,
            conversation_id=conversation.id,
        )
    }

    history_items = list_history(
        request=MagicMock(),
        limit=20,
        cursor=None,
        archived=False,
        deleted=False,
        user=user,
    )
    assert history_items.items[0].subtitle == "Prueba AAPL con velas de cinco minutos."
    assert scored_memory_search_items(user=user, query="compatibility") == []
    search_items = scored_memory_search_items(user=user, query="prueba")
    assert search_items[0][1].matched_text == (
        "Prueba AAPL con velas de cinco minutos."
    )


def test_llm_generated_recovery_voice_remains_in_history_preview_and_model_messages() -> (
    None
):
    user_id = "user-1"
    conversation = memory_conversation(
        title="AAPL idea",
        title_source="system_default",
        language="en",
        user_id=user_id,
    )
    create_message(
        user_id=user_id,
        conversation_id=conversation.id,
        role="user",
        content="Test AAPL.",
    )
    create_message(
        user_id=user_id,
        conversation_id=conversation.id,
        role="assistant",
        content=RAW_ENGLISH_FALLBACK,
        metadata=_degraded_clarification(),
    )
    create_message(
        user_id=user_id,
        conversation_id=conversation.id,
        role="assistant",
        content=EXACT_LLM_VOICE,
        metadata=_llm_clarification(),
    )

    history = load_runtime_thread_history(
        user_id=user_id,
        conversation_id=conversation.id,
    )
    assert [item.content for item in history] == ["Test AAPL.", EXACT_LLM_VOICE]
    assert (
        api_state.store.conversations[conversation.id].last_message_preview
        == EXACT_LLM_VOICE
    )

    user = UserState(user_id=user_id, language_preference="en")
    interpreter_messages = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )._messages(
        InterpretationRequest(
            current_user_message="Use the same idea.",
            recent_thread_history=history,
            user=user,
        )
    )
    clarifier_messages = OpenRouterClarificationGenerator()._messages(
        ClarificationRequest(
            current_user_message="Use the same idea.",
            recent_thread_history=history,
            language="en",
        )
    )

    for model_messages in (interpreter_messages, clarifier_messages):
        assistant_contents = [
            str(message.content)
            for message in model_messages
            if isinstance(message, AIMessage)
        ]
        assert assistant_contents == [EXACT_LLM_VOICE]
        assert RAW_ENGLISH_FALLBACK not in assistant_contents


def test_supabase_append_omits_degraded_compatibility_text_from_preview() -> None:
    gateway = SupabaseGateway(client=MagicMock())

    def append(**kwargs: Any):
        return kwargs["message"], None, False

    gateway._append_conversation_message = MagicMock(side_effect=append)  # type: ignore[method-assign]

    gateway.create_message(
        user_id="user-1",
        conversation_id="conversation-1",
        role="assistant",
        content=RAW_ENGLISH_FALLBACK,
        metadata=_degraded_clarification(),
    )
    degraded_call = gateway._append_conversation_message.call_args

    gateway.create_message(
        user_id="user-1",
        conversation_id="conversation-1",
        role="assistant",
        content=EXACT_LLM_VOICE,
        metadata=_llm_clarification(),
    )
    llm_call = gateway._append_conversation_message.call_args

    assert degraded_call.kwargs["preview"] is None
    assert llm_call.kwargs["preview"] == EXACT_LLM_VOICE
