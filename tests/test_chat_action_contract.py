from __future__ import annotations

import json
from typing import Any

from argus.api.main import app
from argus.api.message_store import create_message
from fastapi.testclient import TestClient


def _client() -> TestClient:
    client = TestClient(app)
    client.post("/api/v1/dev/reset")
    client.patch(
        "/api/v1/me",
        json={
            "onboarding": {
                "stage": "ready",
                "language_confirmed": True,
                "primary_goal": "test_stock_idea",
                "completed": False,
            }
        },
    )
    return client


def _stream_payloads(stream: str, event_type: str) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for part in stream.split("\n\n"):
        data_line = next(
            (line for line in part.splitlines() if line.startswith("data: ")),
            None,
        )
        if data_line is None:
            continue
        raw = data_line.removeprefix("data: ").strip()
        if raw == "[DONE]":
            continue
        event = json.loads(raw)
        if event.get("type") == event_type:
            payloads.append(event.get("payload", event))
    return payloads


def _conversation(client: TestClient) -> dict[str, Any]:
    response = client.post("/api/v1/conversations", json={"language": "en"})
    assert response.status_code == 200
    return response.json()["conversation"]


def _user_id(client: TestClient) -> str:
    response = client.get("/api/v1/me")
    assert response.status_code == 200
    return str(response.json()["user"]["id"])


def test_artifact_metadata_fields_are_backward_compatible() -> None:
    from argus.agent_runtime.state.models import ArtifactReference, TaskSnapshot

    reference = ArtifactReference(
        artifact_kind="confirmation",
        artifact_id="confirm-1",
        artifact_status="active",
        metadata={"confirmation_id": "confirm-1"},
    )
    snapshot = TaskSnapshot(
        active_confirmation_reference=reference,
        artifact_references=[reference],
    )

    assert snapshot.active_confirmation_reference.artifact_id == "confirm-1"
    assert snapshot.artifact_references[0].artifact_status == "active"


def test_confirmation_card_is_not_ready_without_validated_launch_payload() -> None:
    from argus.api.chat.confirmation import runtime_confirmation_card

    card = runtime_confirmation_card(
        {
            "stage_outcome": "await_approval",
            "confirmation_payload": {
                "strategy": {
                    "strategy_type": "signal_strategy",
                    "asset_universe": ["SPY"],
                    "asset_class": "equity",
                    "date_range": "last month",
                    "entry_logic": "starts rising",
                },
                "optional_parameters": {},
            },
        },
        confirmation_id="confirm-1",
    )

    assert card is not None
    assert card["status"] == "needs_change"
    assert card["statusLabel"] == "Needs change"
    assert all("labelKey" in action for action in card["actions"])
    assert [action["type"] for action in card["actions"]] == [
        "change_dates",
        "change_asset",
        "adjust_assumptions",
        "cancel_confirmation",
    ]


def test_change_asset_action_uses_structured_runtime_context() -> None:
    client = _client()
    conversation = _conversation(client)
    user_id = _user_id(client)
    create_message(
        user_id=user_id,
        conversation_id=conversation["id"],
        role="assistant",
        content="I read this as AAPL using a buy and hold approach.",
        metadata={
            "conversation_mode": "confirm",
            "agent_runtime_stage_outcome": "await_approval",
            "confirmation_payload": {
                "strategy": {
                    "strategy_type": "buy_and_hold",
                    "strategy_thesis": "Buy and hold Apple.",
                    "asset_universe": ["AAPL"],
                    "asset_class": "equity",
                    "date_range": "past year",
                    "capital_amount": 10000,
                },
                "optional_parameters": {},
            },
            "confirmation_card": {
                "title": "AAPL buy and hold",
                "statusLabel": "Ready to run",
                "summary": "I read this as AAPL using a buy and hold approach.",
                "rows": [],
                "assumptions": ["Benchmark: SPY"],
                "actions": [
                    {
                        "id": "change-asset",
                        "type": "change_asset",
                        "label": "Change asset",
                        "labelKey": "chat.confirmation.actions.change_asset",
                        "presentation": "confirmation",
                        "payload": {},
                    }
                ],
            },
        },
    )

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "action": {
                "type": "change_asset",
                "label": "Change asset",
                "labelKey": "chat.confirmation.actions.change_asset",
                "presentation": "confirmation",
                "payload": {},
            },
            "language": "en",
        },
    )

    assert response.status_code == 200
    final = _stream_payloads(response.text, "final")[0]
    text = final["assistant_response"] or final.get("assistant_prompt") or ""
    lowered = text.lower()
    assert "which" in lowered
    assert any(term in lowered for term in ("asset", "stock", "etf", "ticker", "symbol"))
    assert final["stage_outcome"] == "await_user_reply"
    assert final["pending_strategy"]["requested_field"] == "asset_universe"
    messages = client.get(f"/api/v1/conversations/{conversation['id']}/messages").json()[
        "items"
    ]
    user_message = messages[-2]
    assistant_message = messages[-1]
    assert user_message["metadata"]["chat_action"]["type"] == "change_asset"
    assert (
        user_message["metadata"]["chat_action"]["labelKey"]
        == "chat.confirmation.actions.change_asset"
    )
    assert assistant_message["metadata"]["pending_strategy"]["requested_field"] == (
        "asset_universe"
    )


def test_change_dates_action_asks_natural_date_window_question() -> None:
    client = _client()
    conversation = _conversation(client)
    user_id = _user_id(client)
    create_message(
        user_id=user_id,
        conversation_id=conversation["id"],
        role="assistant",
        content="I read this as AAPL using a buy and hold approach.",
        metadata={
            "conversation_mode": "confirm",
            "agent_runtime_stage_outcome": "await_approval",
            "confirmation_payload": {
                "strategy": {
                    "strategy_type": "buy_and_hold",
                    "strategy_thesis": "Buy and hold Apple.",
                    "asset_universe": ["AAPL"],
                    "asset_class": "equity",
                    "date_range": {
                        "start": "2025-06-15",
                        "end": "2026-06-15",
                    },
                    "capital_amount": 100000,
                    "comparison_baseline": "SPY",
                },
                "optional_parameters": {},
            },
            "confirmation_card": {
                "title": "AAPL",
                "statusLabel": "Ready to run",
                "summary": "I read this as AAPL using a buy and hold approach.",
                "rows": [],
                "assumptions": ["Benchmark: SPY"],
                "actions": [
                    {
                        "id": "change-dates",
                        "type": "change_dates",
                        "label": "Change dates",
                        "labelKey": "chat.confirmation.actions.change_dates",
                        "presentation": "confirmation",
                        "payload": {},
                    }
                ],
            },
        },
    )

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "action": {
                "type": "change_dates",
                "label": "Change dates",
                "labelKey": "chat.confirmation.actions.change_dates",
                "presentation": "confirmation",
                "payload": {},
            },
            "language": "en",
        },
    )

    assert response.status_code == 200
    final = _stream_payloads(response.text, "final")[0]
    text = final["assistant_response"] or final.get("assistant_prompt") or ""
    assert final["stage_outcome"] == "await_user_reply"
    assert final["pending_strategy"]["requested_field"] == "date_range"
    assert final["pending_strategy"]["strategy"]["asset_universe"] == ["AAPL"]
    assert any(term in text.lower() for term in ("date", "window", "period", "range"))
    assert "could not phrase" not in text.lower()
    messages = client.get(f"/api/v1/conversations/{conversation['id']}/messages").json()[
        "items"
    ]
    user_message = messages[-2]
    assistant_message = messages[-1]
    assert user_message["metadata"]["chat_action"]["type"] == "change_dates"
    assert (
        user_message["metadata"]["chat_action"]["labelKey"]
        == "chat.confirmation.actions.change_dates"
    )
    assert assistant_message["metadata"]["pending_strategy"]["requested_field"] == (
        "date_range"
    )
