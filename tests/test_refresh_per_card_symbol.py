"""Refreshing an answer that weighs two assets prices each card at its own close."""

from __future__ import annotations

import json

from argus.api.main import app
from argus.api.message_store import create_message
from argus.domain.computation_marker import computation_from_tool_cards
from faker import Faker
from fastapi.testclient import TestClient

from tests.domain.calculations.support import run_calculation

fake = Faker()
PAGE = "https://example.com/eps"


def _card(symbol: str, price: float, per_share: float):
    return run_calculation(
        "price_multiple",
        {
            "currency": "USD",
            "symbol": symbol,
            "price": price,
            "per_share": per_share,
            "multiple": None,
            "sources": {
                "price": {"kind": "market_data", "date": "2026-09-01"},
                "per_share": {
                    "kind": "page",
                    "title": f"{symbol} earnings",
                    "url": PAGE,
                    "date": "2026-09-01",
                },
            },
        },
    ).model_copy(
        update={"artifact_id": fake.uuid4(), "call_id": f"answer-{fake.uuid4()}"}
    )


def test_refreshing_two_assets_prices_each_card_at_its_own_close(monkeypatch) -> None:
    from argus.agent_runtime import answer_calculation
    from argus.agent_runtime import research_grounded as grounded
    from argus.domain.research.perplexity_agent import PerplexityAgentClient

    from tests.research.conftest import RecordingTransport, agent_response

    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "true")
    closes = {"AAPL": (230.0, "2026-09-12"), "MSFT": (500.0, "2026-09-12")}
    monkeypatch.setattr(
        answer_calculation, "latest_market_close", lambda symbol: closes.get(symbol)
    )
    looked_up = {
        "answer_markdown": "Earnings as of today.",
        "rows": [],
        "source_urls": [PAGE],
        "calculations": [
            {
                "name": name,
                "kind": "price_multiple",
                "inputs": [
                    {
                        "name": "per_share",
                        "value": value,
                        "source": "page",
                        "source_url": PAGE,
                        "as_of": "2026-09-12",
                    }
                ],
            }
            for name, value in (("apple", 7.0), ("microsoft", 14.0))
        ],
        "follow_up_questions": [],
        "declined": False,
    }
    transport = RecordingTransport(
        [
            agent_response(
                text=json.dumps(looked_up), sources=[PAGE], tickers=["AAPL", "MSFT"]
            )
        ]
    )
    monkeypatch.setattr(
        grounded, "_client", lambda: PerplexityAgentClient("k", transport=transport)
    )
    client = TestClient(app)
    client.post("/api/v1/dev/reset")
    owner = client.get("/api/v1/me").json()["user"]["id"]
    conversation = client.post(
        "/api/v1/conversations", json={"title": "Two multiples"}
    ).json()["conversation"]["id"]
    create_message(
        user_id=owner,
        conversation_id=conversation,
        role="user",
        content="Is Apple or Microsoft pricier for its earnings?",
    )
    cards = [_card("AAPL", 200, 6), _card("MSFT", 400, 12)]
    computation = computation_from_tool_cards(cards)
    assert computation is not None
    message = create_message(
        user_id=owner,
        conversation_id=conversation,
        role="assistant",
        content="Both multiples.",
        metadata={
            "tool_result_cards": [card.model_dump(mode="json") for card in cards],
            "computation": computation.model_dump(mode="json"),
            "answer_text_template": {
                "cards": {
                    "apple": cards[0].artifact_id,
                    "microsoft": cards[1].artifact_id,
                },
                "text": "Apple {{apple.multiple}}, Microsoft {{microsoft.multiple}}.",
                "language": "en",
            },
        },
    )

    response = client.post(
        f"/api/v1/conversations/{conversation}/messages/{message.id}/computation/refresh"
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "refreshed"
    reruns = [rerun["result"]["arguments"] for rerun in body["reruns"]]
    assert [(item["symbol"], item["price"], item["per_share"]) for item in reruns] == [
        ("AAPL", 230.0, 7.0),
        ("MSFT", 500.0, 14.0),
    ]
