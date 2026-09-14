"""A confirmation card turn carries no prose; every reader gets its typed facts.

The card used to persist "Ready to test ..." as English scaffolding around a
language-formatted period. Nothing painted it, but model thread history,
artifact naming, the search index and the message transport all read it.
These tests drive the real card builder and chat route for every shape that
sentence covered, in English and Spanish.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest
from argus.api import state as api_state
from argus.api.chat.confirmation import runtime_confirmation_card
from argus.api.chat.title_finalization import artifact_naming_assistant_message
from argus.api.main import app
from argus.api.message_store import create_message, load_runtime_thread_history
from argus.api.schemas import Message
from argus.domain.chat_turn_lifecycle_gateway import ChatTurnLifecycleGatewayMixin
from argus.domain.store import utcnow
from fastapi.testclient import TestClient

LANGUAGES = ("en", "es-419")
DATE_RANGE = {"start": "2024-01-02", "end": "2024-12-31"}
CONFIRMATION_ID = "33333333-3333-4333-8333-333333333333"

# One entry per branch of the deleted sentence: buy-and-hold, recurring buys,
# and each rule label it phrased separately.
SHAPES: dict[str, dict[str, Any]] = {
    "buy_and_hold": {
        "symbol": "AAPL",
        "strategy_type": "buy_and_hold",
        "strategy": {"strategy_type": "buy_and_hold"},
    },
    "recurring_buys": {
        "symbol": "AAPL",
        "strategy_type": "dca_accumulation",
        "strategy": {"strategy_type": "dca_accumulation", "cadence": "monthly"},
    },
    "rsi_threshold": {
        "symbol": "TSLA",
        "strategy_type": "indicator_threshold",
        "strategy": {
            "strategy_type": "indicator_threshold",
            "strategy_thesis": "Buy TSLA when RSI falls below 30 and sell above 70.",
        },
    },
    "dip_buying": {
        "symbol": "NVDA",
        "strategy_type": "indicator_threshold",
        "strategy": {
            "strategy_type": "indicator_threshold",
            "extra_parameters": {"raw_strategy_type": "dip_buying"},
        },
    },
    "indicator_threshold": {
        "symbol": "MSFT",
        "strategy_type": "indicator_threshold",
        "strategy": {"strategy_type": "indicator_threshold"},
    },
    "signal_strategy": {
        "symbol": "SPY",
        "strategy_type": "signal_strategy",
        "strategy": {"strategy_type": "signal_strategy"},
    },
    "moving_average_crossover": {
        "symbol": "QQQ",
        "strategy_type": "signal_strategy",
        "strategy": {
            "strategy_type": "signal_strategy",
            "requested_strategy_template": "moving_average_crossover",
        },
    },
}
SHAPE_NAMES = sorted(SHAPES)

# What a card turn persisted before the sentence was deleted, per language.
LEGACY_SENTENCES = {
    "en": "Ready to test buy-and-hold for AAPL over January 2, 2024 - December 31, 2024.",
    "es-419": (
        "Ready to test buy-and-hold for AAPL over "
        "2 de enero de 2024 al 31 de diciembre de 2024."
    ),
}


def _payload(shape: str, *, confirmation_id: str | None = None) -> dict[str, Any]:
    spec = SHAPES[shape]
    symbol = spec["symbol"]
    strategy: dict[str, Any] = {
        "asset_universe": [symbol],
        "asset_class": "equity",
        "timeframe": "1D",
        "date_range": dict(DATE_RANGE),
        "sizing_mode": "capital_amount",
        "capital_amount": 1000,
        **spec["strategy"],
    }
    launch: dict[str, Any] = {
        "strategy_type": spec["strategy_type"],
        "symbol": symbol,
        "symbols": [symbol],
        "asset_class": "equity",
        "timeframe": "1D",
        "date_range": dict(DATE_RANGE),
        "sizing_mode": "capital_amount",
        "capital_amount": 1000,
        "benchmark_symbol": "SPY",
    }
    if "cadence" in strategy:
        launch["cadence"] = strategy["cadence"]
    payload: dict[str, Any] = {
        "strategy": strategy,
        "optional_parameters": {},
        "launch_payload": launch,
        "validation": {"status": "ready_to_run", "executable": True},
    }
    if confirmation_id is not None:
        payload["confirmation_id"] = confirmation_id
        payload["artifact_id"] = confirmation_id
    return payload


def _facts(shape: str) -> dict[str, Any]:
    spec = SHAPES[shape]
    return {
        "confirmation_card": {
            "strategy_type": spec["strategy_type"],
            "symbols": [spec["symbol"]],
            "date_range": dict(DATE_RANGE),
        }
    }


def _search_text(shape: str) -> str:
    spec = SHAPES[shape]
    return " ".join(
        [spec["symbol"], spec["strategy_type"], DATE_RANGE["start"], DATE_RANGE["end"]]
    )


def _card(
    shape: str, language: str, *, conversation_id: str | None = None
) -> dict[str, Any]:
    card = runtime_confirmation_card(
        {
            "stage_outcome": "await_approval",
            "confirmation_payload": _payload(shape, confirmation_id=CONFIRMATION_ID),
        },
        confirmation_id=CONFIRMATION_ID,
        conversation_id=conversation_id,
        language=language,
    )
    assert card is not None
    return card


def _parsed(content: str | None) -> Any:
    try:
        return json.loads(content or "")
    except ValueError:
        return content


def _client(language: str) -> tuple[TestClient, str]:
    client = TestClient(app)
    client.post("/api/v1/dev/reset")
    patched = client.patch("/api/v1/me", json={"language": language})
    assert patched.status_code == 200, patched.text
    return client, client.get("/api/v1/me").json()["user"]["id"]


def _conversation_id(client: TestClient) -> str:
    return client.post("/api/v1/conversations", json={}).json()["conversation"]["id"]


def _final_payload(stream: str) -> dict[str, Any]:
    for line in stream.splitlines():
        if not line.startswith("data: ") or line == "data: [DONE]":
            continue
        event = json.loads(line.removeprefix("data: "))
        if event.get("type") == "final":
            return event["payload"]
    raise AssertionError("the stream carried no final payload")


def _card_turn(client: TestClient, conversation_id: str) -> dict[str, Any]:
    items = client.get(f"/api/v1/conversations/{conversation_id}/messages").json()[
        "items"
    ]
    return next(item for item in items if item["role"] == "assistant")


def _history_card_turn(user_id: str, conversation_id: str) -> Any:
    history = load_runtime_thread_history(
        user_id=user_id, conversation_id=conversation_id
    )
    assistant = [item for item in history if item.role == "assistant"]
    assert len(assistant) == 1
    return _parsed(assistant[0].content)


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("shape", SHAPE_NAMES)
def test_the_card_builder_composes_no_summary_prose(shape: str, language: str) -> None:
    card = _card(shape, language)

    assert "summary" not in card
    assert card["strategy_type"] == SHAPES[shape]["strategy_type"]
    assert {key: card["date_range"][key] for key in DATE_RANGE} == DATE_RANGE


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("shape", SHAPE_NAMES)
def test_a_card_turn_persists_no_prose_and_every_reader_gets_typed_facts(
    monkeypatch: pytest.MonkeyPatch, shape: str, language: str
) -> None:
    from argus.api.routers import agent as agent_router

    payload = _payload(shape)

    async def _card_turn_events(**_: Any):
        yield {"type": "stage_start", "stage": "interpret"}
        # Prose the runtime streamed or returned must not become the card turn.
        yield {"type": "token", "content": "Ready to test this idea."}
        yield {
            "type": "final",
            "payload": {
                "stage_outcome": "await_approval",
                "assistant_response": "Ready to test this idea.",
                "confirmation_payload": payload,
            },
        }

    monkeypatch.setattr(agent_router, "stream_agent_turn_events", _card_turn_events)
    client, user_id = _client(language)
    conversation_id = _conversation_id(client)

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation_id,
            "message": "Test this idea",
            "language": language,
        },
    )

    assert response.status_code == 200, response.text
    assert "summary" not in _final_payload(response.text)["confirmation"]
    card_turn = _card_turn(client, conversation_id)
    assert card_turn["content"] == ""
    assert "summary" not in card_turn["metadata"]["confirmation_card"]
    stored = next(
        message
        for message in api_state.store.messages[conversation_id]
        if message.role == "assistant"
    )
    assert stored.content == ""
    assert _history_card_turn(user_id, conversation_id) == _facts(shape)
    assert _parsed(
        artifact_naming_assistant_message(stored.content, metadata=stored.metadata)
    ) == _facts(shape)
    conversation = api_state.store.conversations[conversation_id]
    assert conversation.last_message_preview == _search_text(shape)


@pytest.mark.parametrize("language", LANGUAGES)
def test_an_in_place_card_edit_rebuilds_the_card_without_prose(
    monkeypatch: pytest.MonkeyPatch, language: str
) -> None:
    monkeypatch.setenv("ARGUS_IN_PLACE_CARD_EDITS_ENABLED", "true")
    client, user_id = _client(language)
    conversation_id = _conversation_id(client)
    create_message(
        user_id=user_id,
        conversation_id=conversation_id,
        role="assistant",
        content="",
        metadata={
            "conversation_mode": "confirm",
            "confirmation_card": _card(
                "buy_and_hold", language, conversation_id=conversation_id
            ),
            "confirmation_payload": _payload(
                "buy_and_hold", confirmation_id=CONFIRMATION_ID
            ),
        },
    )

    response = client.post(
        f"/api/v1/conversations/{conversation_id}/confirmations/"
        f"{CONFIRMATION_ID}/direct-edit",
        json={"capital": 25000},
    )

    assert response.status_code == 200, response.text
    message = response.json()["message"]
    assert message["content"] == ""
    assert "summary" not in message["metadata"]["confirmation_card"]
    assert _history_card_turn(user_id, conversation_id) == _facts("buy_and_hold")
    conversation = api_state.store.conversations[conversation_id]
    assert conversation.last_message_preview == _search_text("buy_and_hold")


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_legacy_card_turn_sentence_reaches_no_reader(language: str) -> None:
    client, user_id = _client(language)
    conversation_id = _conversation_id(client)
    sentence = LEGACY_SENTENCES[language]
    legacy_card = {
        **_card("buy_and_hold", language, conversation_id=conversation_id),
        "summary": sentence,
    }
    create_message(
        user_id=user_id,
        conversation_id=conversation_id,
        role="assistant",
        content=sentence,
        metadata={
            "conversation_mode": "confirm",
            "confirmation_card": legacy_card,
            "confirmation_payload": _payload(
                "buy_and_hold", confirmation_id=CONFIRMATION_ID
            ),
        },
    )

    card_turn = _card_turn(client, conversation_id)

    assert card_turn["content"] == ""
    assert "summary" not in card_turn["metadata"]["confirmation_card"]
    assert _history_card_turn(user_id, conversation_id) == _facts("buy_and_hold")
    assert _parsed(
        artifact_naming_assistant_message(sentence, metadata=card_turn["metadata"])
    ) == _facts("buy_and_hold")


@pytest.mark.parametrize("language", LANGUAGES)
def test_supabase_turn_finalization_indexes_the_card_facts(language: str) -> None:
    message = Message(
        id="44444444-4444-4444-8444-444444444444",
        conversation_id="55555555-5555-4555-8555-555555555555",
        role="assistant",
        content="",
        created_at=utcnow(),
        metadata={
            "confirmation_card": _card("rsi_threshold", language),
            "confirmation_payload": _payload("rsi_threshold"),
        },
    )
    captured: dict[str, dict[str, Any]] = {}

    def _rpc(name: str, params: dict[str, Any]) -> SimpleNamespace:
        captured[name] = params
        row = {"message": message.model_dump(mode="json")}
        return SimpleNamespace(execute=lambda: SimpleNamespace(data=[row]))

    gateway = ChatTurnLifecycleGatewayMixin()
    gateway.client = SimpleNamespace(rpc=_rpc)  # type: ignore[assignment]

    gateway.finalize_chat_turn(
        user_id="66666666-6666-4666-8666-666666666666",
        conversation_id=message.conversation_id,
        turn_id="77777777-7777-4777-8777-777777777777",
        request_id="request-card-turn",
        message=message,
        to_status="completed",
        failure_code=None,
        retryable=False,
        settle_usage=None,
    )

    assert captured["finalize_chat_turn"]["p_preview"] == _search_text("rsi_threshold")


@pytest.mark.parametrize("language", LANGUAGES)
def test_supabase_message_creation_indexes_the_card_facts(language: str) -> None:
    from argus.domain.supabase_conversation_messages import (
        ConversationMessagePersistenceMixin,
    )

    captured: dict[str, Any] = {}

    class _Persistence(ConversationMessagePersistenceMixin):
        def _append_conversation_message(  # type: ignore[override]
            self, *, message: Message, preview: str | None, **_: Any
        ) -> tuple[Message, None, bool]:
            captured["preview"] = preview
            return message, None, False

    _Persistence().create_message(  # type: ignore[abstract]
        user_id="66666666-6666-4666-8666-666666666666",
        conversation_id="55555555-5555-4555-8555-555555555555",
        role="assistant",
        content="",
        metadata={
            "confirmation_card": _card("dip_buying", language),
            "confirmation_payload": _payload("dip_buying"),
        },
    )

    assert captured["preview"] == _search_text("dip_buying")


def _card_without_facts(card: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in card.items()
        if key not in {"strategy_type", "date_range"}
    }


def _card_disagreeing_with_payload(card: dict[str, Any]) -> dict[str, Any]:
    return {
        **card,
        "strategy_type": "buy_and_hold",
        "date_range": {
            "start": "2023-01-03",
            "end": "2023-12-29",
            "display": "3 de enero de 2023 al 29 de diciembre de 2023",
        },
    }


@pytest.mark.parametrize(
    ("reshape_card", "expected_facts", "expected_search_text"),
    [
        (
            _card_without_facts,
            {"strategy_type": None, "symbols": ["AAPL"], "date_range": None},
            "AAPL",
        ),
        (
            _card_disagreeing_with_payload,
            {
                "strategy_type": "buy_and_hold",
                "symbols": ["AAPL"],
                "date_range": {"start": "2023-01-03", "end": "2023-12-29"},
            },
            "AAPL buy_and_hold 2023-01-03 2023-12-29",
        ),
    ],
    ids=["legacy_card_missing_facts", "card_disagrees_with_payload"],
)
def test_card_turn_readers_only_see_facts_the_card_carries(
    reshape_card: Any,
    expected_facts: dict[str, Any],
    expected_search_text: str,
) -> None:
    # The payload is a recurring plan over 2024, so any fallback to it shows.
    client, user_id = _client("es-419")
    conversation_id = _conversation_id(client)
    metadata = {
        "conversation_mode": "confirm",
        "confirmation_card": reshape_card(
            _card("recurring_buys", "es-419", conversation_id=conversation_id)
        ),
        "confirmation_payload": _payload(
            "recurring_buys", confirmation_id=CONFIRMATION_ID
        ),
    }
    create_message(
        user_id=user_id,
        conversation_id=conversation_id,
        role="assistant",
        content="",
        metadata=metadata,
    )

    facts = {"confirmation_card": expected_facts}
    assert _history_card_turn(user_id, conversation_id) == facts
    assert _parsed(artifact_naming_assistant_message("", metadata=metadata)) == facts
    conversation = api_state.store.conversations[conversation_id]
    assert conversation.last_message_preview == expected_search_text
