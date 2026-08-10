"""The edit contract's dividing line, encoded once.

Turn-based edits mint a new card: the conversation records a change, so a new
card is the record. Non-turn changes update the existing card: nothing was
spent, so nothing new appears. The line is whether a turn was spent, not
which affordance was used. This test walks every non-turn producer that can
change a pending confirmation through one card and asserts the transcript
never grows, the message identity never changes, and the confirmation id
never changes, so a producer added later cannot append by omission without
failing here.
"""

from __future__ import annotations

from typing import Any

import pytest
from argus.api.chat.confirmation import (
    research_peer_add_rows_for_confirmation,
    runtime_confirmation_card,
)
from argus.api.main import app
from argus.api.message_store import create_message
from fastapi.testclient import TestClient

CONFIRMATION_ID = "77777777-7777-4777-8777-777777777777"

PEERS = [
    {"symbol": "AAPL", "name": "Apple", "asset_class": "equity"},
    {"symbol": "MSFT", "name": "Microsoft", "asset_class": "equity"},
]


def _confirmation_payload() -> dict[str, Any]:
    return {
        "confirmation_id": CONFIRMATION_ID,
        "artifact_id": CONFIRMATION_ID,
        "strategy": {
            "strategy_type": "buy_and_hold",
            "asset_universe": ["NFLX"],
            "asset_class": "equity",
            "timeframe": "1D",
            "date_range": {"start": "2023-01-02", "end": "2023-06-30"},
            "sizing_mode": "capital_amount",
            "capital_amount": 10000,
        },
        "optional_parameters": {},
        "launch_payload": {
            "strategy_type": "buy_and_hold",
            "symbol": "NFLX",
            "symbols": ["NFLX"],
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


def test_no_nonturn_change_ever_grows_the_transcript(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "true")
    client = TestClient(app)
    client.post("/api/v1/dev/reset")
    user_id = client.get("/api/v1/me").json()["user"]["id"]
    conversation_id = client.post("/api/v1/conversations", json={}).json()[
        "conversation"
    ]["id"]

    payload = _confirmation_payload()
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
        PEERS, confirmation_payload=payload, language="en"
    )
    assert rows is not None
    metadata["next_experiments"] = rows
    planted = create_message(
        user_id=user_id,
        conversation_id=conversation_id,
        role="assistant",
        content=str(card.get("summary") or ""),
        metadata=metadata,
        settle_usage=None,
    )

    def transcript() -> list[dict[str, Any]]:
        return client.get(f"/api/v1/conversations/{conversation_id}/messages").json()[
            "items"
        ]

    baseline = transcript()
    base = f"/api/v1/conversations/{conversation_id}/confirmations/{CONFIRMATION_ID}"
    usage_before = client.get("/api/v1/me/usage").json()

    non_turn_changes = [
        ("direct-edit capital", f"{base}/direct-edit", {"capital": 25000}),
        (
            "direct-edit dates",
            f"{base}/direct-edit",
            {"date_window": {"start": "2023-02-01", "end": "2023-05-31"}},
        ),
        (
            "direct-edit costs",
            f"{base}/direct-edit",
            {"fee_rate": 0.002, "slippage": 0.001},
        ),
        ("peer add", f"{base}/peer-assets", {"symbols": ["AAPL"]}),
        ("peer restore", f"{base}/peer-assets", {"restore_previous": True}),
    ]
    for name, url, body in non_turn_changes:
        response = client.post(url, json=body)
        assert response.status_code == 200, f"{name}: {response.text}"
        message = response.json()["message"]
        assert (
            message["id"] == planted.id
        ), f"{name}: a non-turn change must rewrite the card's own message"
        assert (
            message["metadata"]["confirmation_card"]["confirmation_id"] == CONFIRMATION_ID
        ), f"{name}: the card keeps its identity"
        after = transcript()
        assert len(after) == len(baseline), (
            f"{name}: a non-turn change to a pending confirmation must never "
            "increase the transcript's message count"
        )

    out_of_envelope = [
        ("capital below the engine minimum", f"{base}/direct-edit", {"capital": 50}),
        (
            "future end date",
            f"{base}/direct-edit",
            {"date_window": {"start": "2029-01-01", "end": "2030-01-01"}},
        ),
        ("fee above the cap", f"{base}/direct-edit", {"fee_rate": 7.5}),
    ]
    for name, url, body in out_of_envelope:
        response = client.post(url, json=body)
        assert response.status_code == 422, f"{name}: {response.text}"
        after = transcript()
        assert len(after) == len(baseline), (
            f"{name}: a refused non-turn change must also leave the "
            "transcript untouched"
        )

    assert (
        client.get("/api/v1/me/usage").json() == usage_before
    ), "no non-turn change may spend any allowance"
    final = transcript()[-1]["metadata"]["confirmation_payload"]
    assert final["strategy"]["asset_universe"] == ["NFLX"], "restore undid the add"
    assert final["strategy"]["capital_amount"] == 25000
    assert final["launch_payload"]["date_range"]["start"] == "2023-02-01"
    assert final["strategy"]["extra_parameters"]["fee_rate"] == 0.002
