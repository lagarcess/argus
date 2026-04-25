from __future__ import annotations

import json

from argus.api.main import app
from fastapi.testclient import TestClient


def _client() -> TestClient:
    client = TestClient(app)
    client.post("/api/v1/dev/reset")
    return client


def test_me_returns_contract_user_profile() -> None:
    client = _client()

    response = client.get("/api/v1/me")

    assert response.status_code == 200
    assert response.headers["x-request-id"]
    payload = response.json()
    assert payload["user"]["language"] == "en"
    assert payload["user"]["locale"] == "en-US"
    assert payload["user"]["theme"] == "dark"
    assert payload["user"]["onboarding"] == {
        "completed": False,
        "stage": "language_selection",
        "language_confirmed": False,
        "primary_goal": None,
    }


def test_conversation_messages_and_patch_follow_contract() -> None:
    client = _client()

    created = client.post(
        "/api/v1/conversations", json={"title": None, "language": "es-419"}
    )
    assert created.status_code == 200
    conversation = created.json()["conversation"]
    assert conversation["title_source"] == "system_default"
    assert conversation["language"] == "es-419"

    messages = client.get(f"/api/v1/conversations/{conversation['id']}/messages")
    assert messages.status_code == 200
    assert messages.json() == {"items": [], "next_cursor": None}

    patched = client.patch(
        f"/api/v1/conversations/{conversation['id']}",
        json={"title": "Tesla dip idea", "pinned": True, "archived": False},
    )
    assert patched.status_code == 200
    assert patched.json()["conversation"]["title_source"] == "user_renamed"
    assert patched.json()["conversation"]["pinned"] is True


def test_backtest_rejects_mixed_asset_symbols_with_problem_details() -> None:
    client = _client()

    response = client.post(
        "/api/v1/backtests/run",
        headers={"Idempotency-Key": "mixed-assets"},
        json={
            "template": "rsi_mean_reversion",
            "asset_class": "equity",
            "symbols": ["AAPL", "BTC"],
        },
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["code"] == "mixed_asset_not_supported"
    assert payload["request_id"]
    assert payload["context"]["conflicting_symbols"] == [
        {"symbol": "AAPL", "asset_class": "equity"},
        {"symbol": "BTC", "asset_class": "crypto"},
    ]


def test_backtest_rejects_explicit_asset_class_conflict() -> None:
    client = _client()

    response = client.post(
        "/api/v1/backtests/run",
        json={
            "template": "rsi_mean_reversion",
            "asset_class": "crypto",
            "symbols": ["AAPL"],
        },
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["code"] == "asset_class_conflict"
    assert payload["context"] == {
        "requested_asset_class": "crypto",
        "inferred_asset_class": "equity",
        "symbols": ["AAPL"],
    }


def test_backtest_run_normalizes_defaults_persists_metrics_and_history() -> None:
    client = _client()
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]

    response = client.post(
        "/api/v1/backtests/run",
        headers={"Idempotency-Key": "tsla-dip"},
        json={
            "conversation_id": conversation["id"],
            "template": "rsi_mean_reversion",
            "asset_class": "equity",
            "symbols": ["TSLA"],
        },
    )

    assert response.status_code == 200
    run = response.json()["run"]
    assert run["status"] == "completed"
    assert run["asset_class"] == "equity"
    assert run["benchmark_symbol"] == "SPY"
    assert run["config_snapshot"]["side"] == "long"
    assert run["config_snapshot"]["starting_capital"] == 10000
    assert "summary" not in run
    assert set(run["metrics"]) == {"aggregate", "by_symbol"}
    assert run["metrics"]["aggregate"]["performance"]["total_return_pct"] != 0
    assert run["conversation_result_card"]["assumptions"] == [
        "Universe: TSLA.",
        "Simulation uses long-only preset.",
        "Starting capital: $10,000.",
        "Allocation: equal weight.",
        "No slippage or fees included.",
        "Benchmark: SPY.",
    ]

    history = client.get("/api/v1/history")
    assert history.status_code == 200
    assert [item["type"] for item in history.json()["items"]] == ["run", "chat"]


def test_collections_are_organizational_and_can_mix_strategy_asset_classes() -> None:
    client = _client()
    equity_strategy = client.post(
        "/api/v1/strategies",
        json={
            "name": "Tesla dips",
            "template": "rsi_mean_reversion",
            "asset_class": "equity",
            "symbols": ["TSLA"],
            "parameters": {},
        },
    ).json()["strategy"]
    crypto_strategy = client.post(
        "/api/v1/strategies",
        json={
            "name": "Bitcoin momentum",
            "template": "momentum_breakout",
            "asset_class": "crypto",
            "symbols": ["BTC"],
            "parameters": {},
        },
    ).json()["strategy"]
    collection = client.post(
        "/api/v1/collections", json={"name": "Ideas to revisit"}
    ).json()["collection"]

    attached = client.post(
        f"/api/v1/collections/{collection['id']}/strategies",
        json={"strategy_ids": [equity_strategy["id"], crypto_strategy["id"]]},
    )

    assert attached.status_code == 200
    assert attached.json()["collection"]["strategy_count"] == 2


def test_chat_stream_persists_messages_and_emits_contract_events() -> None:
    client = _client()
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]

    response = client.post(
        "/api/v1/chat/stream",
        headers={"Idempotency-Key": "chat-tsla"},
        json={
            "conversation_id": conversation["id"],
            "message": "What if I bought Tesla whenever it dipped hard?",
            "language": "en",
        },
    )

    assert response.status_code == 200
    stream = response.text
    assert "event: status" in stream
    assert '"status":"extracting_strategy"' in stream
    assert '"status":"running_backtest"' in stream
    assert "event: result" in stream
    assert "event: done" in stream

    result_line = next(
        line.removeprefix("data: ")
        for line in stream.splitlines()
        if line.startswith("data: {") and '"run"' in line
    )
    assert json.loads(result_line)["run"]["conversation_result_card"]["status_label"]

    messages = client.get(f"/api/v1/conversations/{conversation['id']}/messages")
    assert [message["role"] for message in messages.json()["items"]] == [
        "user",
        "assistant",
    ]
