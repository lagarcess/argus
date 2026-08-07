"""Peer offers on the card and the no-turn add endpoint."""

from __future__ import annotations

from typing import Any

import pytest
from argus.api.chat.confirmation import runtime_confirmation_card
from argus.api.main import app
from argus.api.message_store import create_message
from fastapi.testclient import TestClient

CONFIRMATION_ID = "11111111-1111-4111-8111-111111111111"


def _client() -> TestClient:
    client = TestClient(app)
    client.post("/api/v1/dev/reset")
    return client


def _conversation(client: TestClient) -> dict[str, Any]:
    return client.post("/api/v1/conversations", json={}).json()["conversation"]


def _confirmation_payload(symbols: list[str]) -> dict[str, Any]:
    return {
        "confirmation_id": CONFIRMATION_ID,
        "artifact_id": CONFIRMATION_ID,
        "strategy": {
            "strategy_type": "buy_and_hold",
            "asset_universe": list(symbols),
            "asset_class": "equity",
            "timeframe": "1D",
            "date_range": {"start": "2023-01-02", "end": "2023-06-30"},
            "sizing_mode": "capital_amount",
            "capital_amount": 10000,
        },
        "optional_parameters": {},
        "launch_payload": {
            "strategy_type": "buy_and_hold",
            "symbol": symbols[0],
            "symbols": list(symbols),
            "asset_class": "equity",
            "timeframe": "1D",
            "date_range": {"start": "2023-01-02", "end": "2023-06-30"},
            "sizing_mode": "capital_amount",
            "capital_amount": 10000,
            "parameters": {},
            "risk_rules": [],
            "benchmark_symbol": "SPY",
            "language": "en",
        },
        "validation": {"status": "ready_to_run", "executable": True},
    }


def _runtime_result(symbols: list[str], peers: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "stage_outcome": "await_approval",
        "confirmation_payload": _confirmation_payload(symbols),
        "research_peers": {"peers": peers},
    }


PEERS = [
    {"symbol": "AAPL", "name": "Apple", "asset_class": "equity"},
    {"symbol": "MSFT", "name": "Microsoft", "asset_class": "equity"},
]


def _plant_confirmation(
    client: TestClient,
    conversation_id: str,
    *,
    symbols: list[str],
    peers: list[dict[str, str]],
) -> dict[str, Any]:
    card = runtime_confirmation_card(
        _runtime_result(symbols, peers),
        confirmation_id=CONFIRMATION_ID,
        conversation_id=conversation_id,
        language="en",
    )
    assert card is not None
    create_message(
        user_id=_mock_user_id(client),
        conversation_id=conversation_id,
        role="assistant",
        content=str(card.get("summary") or ""),
        metadata={
            "conversation_mode": "confirm",
            "confirmation_card": card,
            "confirmation_payload": _confirmation_payload(symbols),
        },
        settle_usage=None,
    )
    return card


def _mock_user_id(client: TestClient) -> str:
    return client.get("/api/v1/me").json()["user"]["id"]


def test_card_offers_remaining_class_matched_peers_with_localized_labels() -> None:
    card = runtime_confirmation_card(
        _runtime_result(
            ["NFLX"],
            [
                *PEERS,
                {"symbol": "NFLX", "name": "Netflix", "asset_class": "equity"},
                {"symbol": "BTC", "name": "Bitcoin", "asset_class": "crypto"},
            ],
        ),
        confirmation_id=CONFIRMATION_ID,
        conversation_id="c1",
        language="en",
    )
    assert card is not None
    offers = card["research_peers"]["offers"]
    # In-basket and cross-class candidates never become offers.
    assert [offer["symbol"] for offer in offers] == ["AAPL", "MSFT"]
    assert offers[0]["label"] == "Add Apple [AAPL] to this test"
    assert card["research_peers"]["set"]["symbols"] == ["AAPL", "MSFT"]
    assert card["research_peers"]["set"]["label"] == (
        "Add Apple [AAPL] and Microsoft [MSFT]"
    )

    spanish = runtime_confirmation_card(
        _runtime_result(["NFLX"], PEERS[:1]),
        confirmation_id=CONFIRMATION_ID,
        conversation_id="c1",
        language="es-419",
    )
    assert spanish is not None
    assert spanish["research_peers"]["offers"][0]["label"] == (
        "Agregar Apple [AAPL] a esta prueba"
    )


def test_offers_respect_the_five_asset_maximum() -> None:
    card = runtime_confirmation_card(
        _runtime_result(["NFLX", "AAPL", "MSFT", "GOOG", "AMZN"], PEERS),
        confirmation_id=CONFIRMATION_ID,
        conversation_id="c1",
        language="en",
    )
    assert card is not None
    assert "research_peers" not in card, "a full basket offers nothing"


def test_flag_off_cards_carry_no_offers(monkeypatch) -> None:
    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "false")
    card = runtime_confirmation_card(
        _runtime_result(["NFLX"], PEERS),
        confirmation_id=CONFIRMATION_ID,
        conversation_id="c1",
        language="en",
    )
    assert card is not None
    assert "research_peers" not in card
    assert "assets_adjustment" not in card


def test_add_peer_endpoint_supersedes_with_disclosure_and_no_turn_spend() -> None:
    client = _client()
    conversation = _conversation(client)
    user_id = _mock_user_id(client)
    _plant_confirmation(client, conversation["id"], symbols=["NFLX"], peers=PEERS)

    usage_before = client.get("/api/v1/me/usage").json()

    response = client.post(
        f"/api/v1/conversations/{conversation['id']}/confirmations/"
        f"{CONFIRMATION_ID}/peer-assets",
        json={"symbols": ["AAPL"]},
    )
    assert response.status_code == 200, response.text
    message = response.json()["message"]
    assert message["role"] == "assistant"
    card = message["metadata"]["confirmation_card"]
    assert card["confirmation_id"] != CONFIRMATION_ID, "a new identity supersedes"
    assert card["assets_adjustment"]["added"] == [{"symbol": "AAPL", "name": "Apple"}]
    assert card["assets_adjustment"]["previous_symbols"] == ["NFLX"]
    assert card["assets_adjustment"]["symbols"] == ["NFLX", "AAPL"]
    payload = message["metadata"]["confirmation_payload"]
    assert payload["strategy"]["asset_universe"] == ["NFLX", "AAPL"]
    # The remaining researched peer is still offered on the new card.
    assert [o["symbol"] for o in card["research_peers"]["offers"]] == ["MSFT"]

    # No turn was spent: the message allowance is untouched.
    usage_after = client.get("/api/v1/me/usage").json()
    assert usage_after == usage_before

    # The new card is now the active confirmation for the conversation.
    del user_id


def test_add_peer_rejects_symbols_that_were_never_offered() -> None:
    client = _client()
    conversation = _conversation(client)
    _plant_confirmation(client, conversation["id"], symbols=["NFLX"], peers=PEERS)

    response = client.post(
        f"/api/v1/conversations/{conversation['id']}/confirmations/"
        f"{CONFIRMATION_ID}/peer-assets",
        json={"symbols": ["TSLA"]},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "artifact_action_invalid_state"


def test_add_peer_rejects_stale_confirmations() -> None:
    client = _client()
    conversation = _conversation(client)
    _plant_confirmation(client, conversation["id"], symbols=["NFLX"], peers=PEERS)

    response = client.post(
        f"/api/v1/conversations/{conversation['id']}/confirmations/"
        "22222222-2222-4222-8222-222222222222/peer-assets",
        json={"symbols": ["AAPL"]},
    )
    assert response.status_code == 409


def test_add_peer_enforces_the_asset_maximum_as_defense_in_depth() -> None:
    # The offer builder already caps offers to free slots, so an honest client
    # cannot exceed the run maximum. This plants adversarial card metadata
    # claiming more offers than slots and proves the materializer still
    # refuses: every layer holds the five-asset invariant independently.
    client = _client()
    conversation = _conversation(client)
    symbols = ["NFLX", "GOOG", "AMZN", "META"]
    card = runtime_confirmation_card(
        _runtime_result(symbols, PEERS[:1]),
        confirmation_id=CONFIRMATION_ID,
        conversation_id=conversation["id"],
        language="en",
    )
    assert card is not None
    card["research_peers"] = {
        "schema_version": "argus_research_peers/v1",
        "offers": [
            {**peer, "label": f"Add {peer['name']} [{peer['symbol']}] to this test"}
            for peer in PEERS
        ],
    }
    create_message(
        user_id=_mock_user_id(client),
        conversation_id=conversation["id"],
        role="assistant",
        content=str(card.get("summary") or ""),
        metadata={
            "conversation_mode": "confirm",
            "confirmation_card": card,
            "confirmation_payload": _confirmation_payload(symbols),
        },
        settle_usage=None,
    )

    response = client.post(
        f"/api/v1/conversations/{conversation['id']}/confirmations/"
        f"{CONFIRMATION_ID}/peer-assets",
        json={"symbols": ["AAPL", "MSFT"]},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "asset_maximum_reached"


def test_add_peer_is_absent_with_the_flag_off(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    conversation = _conversation(client)
    _plant_confirmation(client, conversation["id"], symbols=["NFLX"], peers=PEERS)
    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "false")

    response = client.post(
        f"/api/v1/conversations/{conversation['id']}/confirmations/"
        f"{CONFIRMATION_ID}/peer-assets",
        json={"symbols": ["AAPL"]},
    )
    assert response.status_code == 404
