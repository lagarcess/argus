"""Peer rows on the Try-next surface and the no-turn add/undo endpoint."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from argus.api.chat.confirmation import (
    research_peer_add_rows_for_confirmation,
    runtime_confirmation_card,
)
from argus.api.main import app
from argus.api.message_store import create_message
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _in_place_surface_enabled(monkeypatch):
    """These tests exercise the in-place surface, which ships default-off
    behind ARGUS_IN_PLACE_CARD_EDITS_ENABLED until the consumption guard
    lane closes."""
    monkeypatch.setenv("ARGUS_IN_PLACE_CARD_EDITS_ENABLED", "true")


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


PEERS = [
    {"symbol": "AAPL", "name": "Apple", "asset_class": "equity"},
    {"symbol": "MSFT", "name": "Microsoft", "asset_class": "equity"},
]


def _mock_user_id(client: TestClient) -> str:
    return client.get("/api/v1/me").json()["user"]["id"]


def _plant_confirmation(
    client: TestClient,
    conversation_id: str,
    *,
    symbols: list[str],
    peers: list[dict[str, str]],
) -> dict[str, Any]:
    payload = _confirmation_payload(symbols)
    card = runtime_confirmation_card(
        {"stage_outcome": "await_approval", "confirmation_payload": payload},
        confirmation_id=CONFIRMATION_ID,
        conversation_id=conversation_id,
        language="en",
    )
    assert card is not None
    metadata: dict[str, Any] = {
        "conversation_mode": "confirm",
        "confirmation_card": card,
        "confirmation_payload": payload,
    }
    rows = research_peer_add_rows_for_confirmation(
        peers,
        confirmation_payload=payload,
        language="en",
    )
    if rows is not None:
        metadata["next_experiments"] = rows
    create_message(
        user_id=_mock_user_id(client),
        conversation_id=conversation_id,
        role="assistant",
        content=str(card.get("summary") or ""),
        metadata=metadata,
        settle_usage=None,
    )
    return metadata


def _add(client: TestClient, conversation_id: str, confirmation_id: str, body):
    return client.post(
        f"/api/v1/conversations/{conversation_id}/confirmations/"
        f"{confirmation_id}/peer-assets",
        json=body,
    )


def test_peer_rows_ride_the_try_next_surface_not_the_card() -> None:
    payload = _confirmation_payload(["NFLX"])
    card = runtime_confirmation_card(
        {"stage_outcome": "await_approval", "confirmation_payload": payload},
        confirmation_id=CONFIRMATION_ID,
        conversation_id="c1",
        language="en",
    )
    assert card is not None
    assert "research_peers" not in card

    rows = research_peer_add_rows_for_confirmation(
        [*PEERS, {"symbol": "BTC", "name": "Bitcoin", "asset_class": "crypto"}],
        confirmation_payload=payload,
        language="en",
    )
    assert rows is not None
    labels = [row["label"] for row in rows["rows"]]
    assert labels[0] == "Add Apple (AAPL) to this test"
    assert labels[1] == "Add Microsoft (MSFT) to this test"
    # Cross-class candidates never become rows; the set row carries both.
    assert labels[2] == "Add Apple (AAPL) and Microsoft (MSFT)"
    assert rows["rows"][2]["why"]["params"]["symbols"] == ["AAPL", "MSFT"]
    for row in rows["rows"]:
        assert row["kind"].startswith("research_add_peer")
        assert row["label_key"]

    spanish = research_peer_add_rows_for_confirmation(
        PEERS[:1],
        confirmation_payload=payload,
        language="es-419",
    )
    assert spanish is not None
    assert spanish["rows"][0]["label"] == "Agregar Apple (AAPL) a esta prueba"


def test_rows_respect_the_five_asset_maximum() -> None:
    payload = _confirmation_payload(["NFLX", "AAPL", "MSFT", "GOOG", "AMZN"])
    rows = research_peer_add_rows_for_confirmation(
        PEERS,
        confirmation_payload=payload,
        language="en",
    )
    assert rows is None, "a full basket offers nothing"


def test_flag_off_emits_no_rows(monkeypatch) -> None:
    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "false")
    rows = research_peer_add_rows_for_confirmation(
        PEERS,
        confirmation_payload=_confirmation_payload(["NFLX"]),
        language="en",
    )
    assert rows is None


def test_background_research_peers_reach_the_next_confirmation_card() -> None:
    """A thorough job completes out of band; when the user taps the resulting
    test row, the confirmation still offers the remaining researched peers.
    The persisted sidecar is the one peer contract every completion path
    honors, so the finalizer needs no runtime-state write."""
    from argus.api.chat.confirmation import attach_research_peer_rows
    from argus.api.chat.research_jobs import _finalize_success
    from argus.domain.research.perplexity_agent import _packet_from_response

    from tests.research.conftest import agent_response

    client = _client()
    conversation = _conversation(client)
    user_id = _mock_user_id(client)

    packet = _packet_from_response(
        agent_response(
            text="Netflix, thoroughly.",
            tickers=["NFLX"],
            lookup_rows=[
                ("Apple", "AAPL", "Apple Inc."),
                ("Microsoft", "MSFT", "Microsoft Corporation"),
            ],
        ),
        latency_ms=900,
    )
    asyncio.run(
        _finalize_success(
            job_id="job-research-1",
            job_request={
                "capability_class": "thorough_research",
                "shape": "thorough",
                "language": "en",
                "question": "Break down Netflix against its rivals",
                "subjects": [
                    {"symbol": "NFLX", "name": "Netflix", "asset_class": "equity"}
                ],
            },
            packet=packet,
            user_id=user_id,
            conversation_id=conversation["id"],
            request_id=None,
        )
    )

    runtime_result: dict[str, Any] = {
        "confirmation_payload": _confirmation_payload(["NFLX"])
    }
    metadata: dict[str, Any] = {}
    attach_research_peer_rows(
        runtime_result,
        metadata,
        user_id=user_id,
        conversation_id=conversation["id"],
        language="en",
    )
    rows = metadata["next_experiments"]["rows"]
    offered = sorted(
        symbol
        for row in rows
        if not row["kind"].endswith("_set")
        for symbol in row["why"]["params"]["symbols"]
    )
    assert offered == ["AAPL", "MSFT"]

    # Tapping a peer row instead of the anchor still finds the research:
    # the basket overlaps the sidecar's peers rather than its anchors.
    peer_tap: dict[str, Any] = {"confirmation_payload": _confirmation_payload(["MSFT"])}
    peer_metadata: dict[str, Any] = {}
    attach_research_peer_rows(
        peer_tap,
        peer_metadata,
        user_id=user_id,
        conversation_id=conversation["id"],
        language="en",
    )
    peer_rows = peer_metadata["next_experiments"]["rows"]
    assert [
        row["why"]["params"]["symbols"]
        for row in peer_rows
        if not row["kind"].endswith("_set")
    ] == [["AAPL"]], "the tapped peer leaves the basket's offers"


def test_the_relevant_research_wins_over_the_latest() -> None:
    """Newest-first with a relevance gate: research about other assets in
    between neither hides the right peers nor leaks its own."""
    from argus.api.chat.confirmation import research_peers_from_transcript

    client = _client()
    conversation = _conversation(client)
    user_id = _mock_user_id(client)

    def _plant_research(anchors: list[str], peers: list[dict[str, str]]) -> None:
        create_message(
            user_id=user_id,
            conversation_id=conversation["id"],
            role="assistant",
            content="research answer",
            metadata={
                "conversation_mode": "guide",
                "research": {
                    "schema_version": "argus_research/v1",
                    "capability_class": "balanced_lookup",
                    "shape": "balanced",
                    "anchor_symbols": anchors,
                    "peers": peers,
                    "usage": {"cache_status": "miss"},
                },
            },
            settle_usage=None,
        )

    _plant_research(["NFLX"], PEERS)
    _plant_research(
        ["GOOG"], [{"symbol": "META", "name": "Meta", "asset_class": "equity"}]
    )

    nflx_peers = research_peers_from_transcript(
        user_id=user_id,
        conversation_id=conversation["id"],
        basket_symbols=["NFLX"],
    )
    assert [p["symbol"] for p in nflx_peers] == ["AAPL", "MSFT"]

    goog_peers = research_peers_from_transcript(
        user_id=user_id,
        conversation_id=conversation["id"],
        basket_symbols=["GOOG"],
    )
    assert [p["symbol"] for p in goog_peers] == ["META"]

    assert (
        research_peers_from_transcript(
            user_id=user_id,
            conversation_id=conversation["id"],
            basket_symbols=["AMZN"],
        )
        == []
    ), "unrelated baskets get no researched peers"


def test_add_peer_updates_in_place_without_narration_and_without_turn_spend() -> None:
    client = _client()
    conversation = _conversation(client)
    _plant_confirmation(client, conversation["id"], symbols=["NFLX"], peers=PEERS)

    usage_before = client.get("/api/v1/me/usage").json()
    response = _add(client, conversation["id"], CONFIRMATION_ID, {"symbols": ["AAPL"]})
    assert response.status_code == 200, response.text
    message = response.json()["message"]
    assert message["role"] == "assistant"
    card = message["metadata"]["confirmation_card"]
    # No turn was spent, so nothing new appears: the same card is the record.
    assert card["confirmation_id"] == CONFIRMATION_ID
    adjustment = card["assets_adjustment"]
    # The resolver owns display names; the row label is never trusted.
    assert adjustment["added"] == [{"symbol": "AAPL", "name": "Apple Inc."}]
    assert adjustment["previous_symbols"] == ["NFLX"]
    assert adjustment["symbols"] == ["NFLX", "AAPL"]
    payload = message["metadata"]["confirmation_payload"]
    assert payload["strategy"]["asset_universe"] == ["NFLX", "AAPL"]
    # The remaining researched peer rides the Try-next surface of the new turn.
    rows = message["metadata"]["next_experiments"]["rows"]
    assert [row["why"]["params"]["symbols"] for row in rows] == [["MSFT"]]
    assert "research_peers" not in card

    # No turn was spent: the message allowance is untouched.
    usage_after = client.get("/api/v1/me/usage").json()
    assert usage_after == usage_before


def test_restore_previous_undoes_the_latest_add() -> None:
    client = _client()
    conversation = _conversation(client)
    _plant_confirmation(client, conversation["id"], symbols=["NFLX"], peers=PEERS)

    added = _add(client, conversation["id"], CONFIRMATION_ID, {"symbols": ["AAPL"]})
    assert added.status_code == 200, added.text
    same_id = added.json()["message"]["metadata"]["confirmation_card"]["confirmation_id"]
    assert same_id == CONFIRMATION_ID

    restored = _add(client, conversation["id"], same_id, {"restore_previous": True})
    assert restored.status_code == 200, restored.text
    message = restored.json()["message"]
    card = message["metadata"]["confirmation_card"]
    payload = message["metadata"]["confirmation_payload"]
    assert payload["strategy"]["asset_universe"] == ["NFLX"]
    assert card["assets_adjustment"]["code"] == "assets_restored"
    # The undone peer becomes offerable again alongside the untouched one.
    rows = message["metadata"]["next_experiments"]["rows"]
    offered = sorted(
        symbol
        for row in rows
        if row["kind"].startswith("research_add_peer")
        and not row["kind"].endswith("_set")
        for symbol in row["why"]["params"]["symbols"]
    )
    assert offered == ["AAPL", "MSFT"]


def test_restore_without_a_prior_add_conflicts() -> None:
    client = _client()
    conversation = _conversation(client)
    _plant_confirmation(client, conversation["id"], symbols=["NFLX"], peers=PEERS)

    response = _add(
        client, conversation["id"], CONFIRMATION_ID, {"restore_previous": True}
    )
    assert response.status_code == 409


def test_add_peer_rejects_symbols_that_were_never_offered() -> None:
    client = _client()
    conversation = _conversation(client)
    _plant_confirmation(client, conversation["id"], symbols=["NFLX"], peers=PEERS)

    response = _add(client, conversation["id"], CONFIRMATION_ID, {"symbols": ["TSLA"]})
    assert response.status_code == 409
    assert response.json()["code"] == "artifact_action_invalid_state"


def test_add_peer_rejects_stale_confirmations() -> None:
    client = _client()
    conversation = _conversation(client)
    _plant_confirmation(client, conversation["id"], symbols=["NFLX"], peers=PEERS)

    response = _add(
        client,
        conversation["id"],
        "22222222-2222-4222-8222-222222222222",
        {"symbols": ["AAPL"]},
    )
    assert response.status_code == 409


def test_add_peer_enforces_the_asset_maximum_as_defense_in_depth() -> None:
    # The row builder already caps offers to free slots, so an honest client
    # cannot exceed the run maximum. This plants adversarial row metadata
    # claiming more offers than slots and proves the materializer still
    # refuses: every layer holds the five-asset invariant independently.
    client = _client()
    conversation = _conversation(client)
    symbols = ["NFLX", "GOOG", "AMZN", "META"]
    payload = _confirmation_payload(symbols)
    card = runtime_confirmation_card(
        {"stage_outcome": "await_approval", "confirmation_payload": payload},
        confirmation_id=CONFIRMATION_ID,
        conversation_id=conversation["id"],
        language="en",
    )
    assert card is not None
    create_message(
        user_id=_mock_user_id(client),
        conversation_id=conversation["id"],
        role="assistant",
        content=str(card.get("summary") or ""),
        metadata={
            "conversation_mode": "confirm",
            "confirmation_card": card,
            "confirmation_payload": payload,
            "next_experiments": {
                "version": "argus_next_experiments/v1",
                "rows": [
                    {
                        "kind": "research_add_peer_set",
                        "label": "Add Apple (AAPL) and Microsoft (MSFT)",
                        "label_key": "chat.next_experiments.labels.research_dynamic",
                        "why": {
                            "code": "research_add_peer",
                            "params": {"symbols": ["AAPL", "MSFT"]},
                        },
                    }
                ],
            },
        },
        settle_usage=None,
    )

    response = _add(
        client,
        conversation["id"],
        CONFIRMATION_ID,
        {"symbols": ["AAPL", "MSFT"]},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "asset_maximum_reached"


def test_add_peer_is_absent_with_the_flag_off(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    conversation = _conversation(client)
    _plant_confirmation(client, conversation["id"], symbols=["NFLX"], peers=PEERS)
    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "false")

    response = _add(client, conversation["id"], CONFIRMATION_ID, {"symbols": ["AAPL"]})
    assert response.status_code == 404


def test_peer_rows_survive_a_direct_edit_of_the_same_card() -> None:
    """A capital edit does not change the basket, so the offered peer rows
    ride the updated card unchanged; both writes share the same metadata
    path, and neither may drop the other's sidecar."""
    client = _client()
    conversation = _conversation(client)
    _plant_confirmation(client, conversation["id"], symbols=["NFLX"], peers=PEERS)

    response = client.post(
        f"/api/v1/conversations/{conversation['id']}/confirmations/"
        f"{CONFIRMATION_ID}/direct-edit",
        json={"capital": 25000},
    )
    assert response.status_code == 200, response.text
    message = response.json()["message"]
    payload = message["metadata"]["confirmation_payload"]
    assert payload["strategy"]["capital_amount"] == 25000
    rows = message["metadata"]["next_experiments"]["rows"]
    offered = sorted(
        symbol
        for row in rows
        if row["kind"].startswith("research_add_peer")
        and not row["kind"].endswith("_set")
        for symbol in row["why"]["params"]["symbols"]
    )
    assert offered == [
        "AAPL",
        "MSFT",
    ], "the peer offers must survive an in-place edit of the same card"
