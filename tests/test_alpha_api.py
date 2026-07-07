from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

import pandas as pd
import pytest
from argus.api import state as api_state
from argus.api.main import app
from argus.api.message_store import memory_conversation, memory_message
from argus.api.schemas import (
    BacktestRun,
    Collection,
    Conversation,
    DecisionNote,
    EvidenceArtifact,
    Idea,
    IdeaVersion,
    Strategy,
)
from argus.domain.market_data.assets import ResolvedAsset
from argus.domain.store import utcnow
from fastapi.testclient import TestClient


def _stream_events(stream: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for part in stream.split("\n\n"):
        data_line = next(
            (line for line in part.splitlines() if line.startswith("data: ")),
            None,
        )
        if data_line is None:
            continue
        raw = data_line.removeprefix("data: ").strip()
        if raw == "[DONE]":
            events.append({"type": "done"})
            continue
        events.append(json.loads(raw))
    return events


def _final_payload(stream: str) -> dict[str, Any]:
    final_events = [
        event for event in _stream_events(stream) if event.get("type") == "final"
    ]
    assert len(final_events) == 1
    payload = final_events[0]["payload"]
    assert isinstance(payload, dict)
    return payload


def _fake_resolve_asset(symbol: str) -> ResolvedAsset:
    candidate = symbol.strip().upper().replace("-", "/")
    if candidate == "TESLA":
        candidate = "TSLA"
    compact = candidate.replace("/", "")
    if compact.endswith("USD") and len(compact) > 3:
        compact = compact[:-3]

    if compact in {"AAPL", "TSLA", "MSFT", "SPY"}:
        return ResolvedAsset(
            canonical_symbol=compact,
            asset_class="equity",
            name=compact,
            raw_symbol=compact,
        )
    if compact in {"BTC", "ETH", "USDC", "USDT"}:
        return ResolvedAsset(
            canonical_symbol=compact,
            asset_class="crypto",
            name=compact,
            raw_symbol=compact,
        )
    raise ValueError("invalid_symbol")


def _fake_fetch_ohlcv(
    symbol: str,
    asset_class: str,  # noqa: ARG001
    start_date: date,
    end_date: date,
    timeframe: str,
) -> pd.DataFrame:
    freq_map = {"1D": "D", "1h": "h", "2h": "2h", "4h": "4h", "6h": "6h", "12h": "12h"}
    index = pd.date_range(
        start=start_date, end=end_date, freq=freq_map[timeframe], tz="UTC"
    )
    if len(index) < 80:
        index = pd.date_range(
            start=start_date, periods=80, freq=freq_map[timeframe], tz="UTC"
        )
    base_map = {"AAPL": 100.0, "TSLA": 200.0, "MSFT": 150.0, "SPY": 400.0, "BTC": 30000.0}
    base = base_map.get(symbol, 100.0)
    close = pd.Series(base + pd.RangeIndex(len(index)).astype(float) * 0.5, index=index)
    return pd.DataFrame(
        {
            "open": close * 0.999,
            "high": close * 1.002,
            "low": close * 0.998,
            "close": close,
            "volume": 5000.0,
        },
        index=index,
    )


def _fake_fetch_price_series(
    symbol: str,
    asset_class: str,
    start_date: date,
    end_date: date,
    timeframe: str,
) -> pd.Series:
    return _fake_fetch_ohlcv(
        symbol=symbol,
        asset_class=asset_class,
        start_date=start_date,
        end_date=end_date,
        timeframe=timeframe,
    )["close"]


def _runtime_success_result(
    *,
    symbol: str = "TSLA",
    timeframe: str = "1D",
    language: str = "en",
    assistant_response: str | None = None,
) -> dict[str, Any]:
    assistant_copy = assistant_response or (
        "Probé la idea con TSLA."
        if language.lower().startswith("es")
        else f"I tested that idea with {symbol}."
    )
    return {
        "stage_outcome": "ready_to_respond",
        "assistant_response": assistant_copy,
        "final_response_payload": {
            "result": {
                "execution_status": "succeeded",
                "resolved_strategy": {
                    "strategy_type": "rsi_mean_reversion",
                    "asset_universe": [symbol],
                },
                "resolved_parameters": {
                    "timeframe": timeframe,
                    "date_range": {
                        "start": "2025-01-01",
                        "end": "2025-12-31",
                    },
                },
                "metrics": {
                    "aggregate": {"performance": {"total_return_pct": 12.5}},
                    "by_symbol": {},
                },
                "benchmark_metrics": {
                    "benchmark_symbol": "BTC" if symbol == "BTC" else "SPY",
                    "benchmark_return_pct": 9.2,
                },
                "assumptions": ["Starting capital: $10,000."],
                "caveats": [],
            },
            "result_card": {
                "title": f"{symbol} RSI Mean Reversion",
                "status_label": "Simulation Complete",
                "rows": [{"label": "Total Return", "value": "+12.5%"}],
                "assumptions": ["Starting capital: $10,000."],
            },
        },
    }


def _runtime_success_for_message(**kwargs: Any) -> dict[str, Any]:
    message = str(kwargs.get("message", ""))
    language = str(getattr(kwargs.get("user"), "language_preference", "en"))
    upper_message = message.upper()
    symbol = "BTC" if "BTC" in upper_message or "BITCOIN" in upper_message else "TSLA"
    timeframe = "1h" if "1h" in message.lower() else "1D"
    return _runtime_success_result(
        symbol=symbol,
        timeframe=timeframe,
        language=language,
    )


async def _runtime_success_for_message_async(**kwargs: Any) -> dict[str, Any]:
    return _runtime_success_for_message(**kwargs)


async def _runtime_success_events(**kwargs: Any):
    result = _runtime_success_for_message(**kwargs)
    assistant_response = str(result.get("assistant_response") or "")
    yield {"type": "stage_start", "stage": "interpret"}
    yield {"type": "stage_outcome", "outcome": str(result["stage_outcome"])}
    if assistant_response:
        yield {"type": "token", "content": assistant_response}
    yield {"type": "final", "payload": result}


@pytest.fixture(autouse=True)
def _patch_engine_io(monkeypatch: pytest.MonkeyPatch) -> None:
    from argus.api import main as api_main
    from argus.api import state as api_state
    from argus.api.routers import agent as agent_router
    from argus.domain import engine as domain_engine

    monkeypatch.setattr(api_state, "supabase_gateway", None)
    monkeypatch.setattr(
        api_main,
        "".join(["orchestrate_chat", "_turn"]),
        lambda message, language, onboarding_required, primary_goal, **kwargs: (
            dict(
                intent="onboarding_prompt",
                assistant_message=(
                    "What is your current primary goal? Don't worry, "
                    "you can change it later in Settings."
                ),
                strategy_draft=None,
                title_suggestion=None,
            )
            if onboarding_required
            else dict(
                intent="run_backtest",
                assistant_message=(
                    "Probé la idea con TSLA."
                    if str(language).lower().startswith("es")
                    else "I tested that idea with TSLA."
                ),
                strategy_draft=dict(
                    template=dict(source="user_supplied", value="rsi_mean_reversion"),
                    asset_class=dict(source="user_supplied", value="equity"),
                    symbols=dict(source="user_supplied", value=["TSLA"]),
                    parameters={},
                ),
                title_suggestion="TSLA idea",
            )
        ),
        raising=False,
    )
    monkeypatch.setattr(agent_router, "stream_agent_turn_events", _runtime_success_events)
    monkeypatch.setattr(domain_engine, "resolve_asset", _fake_resolve_asset)
    monkeypatch.setattr(domain_engine, "fetch_ohlcv", _fake_fetch_ohlcv)
    monkeypatch.setattr(domain_engine, "fetch_price_series", _fake_fetch_price_series)


def _client() -> TestClient:
    client = TestClient(app)
    client.post("/api/v1/dev/reset")
    return client


def _set_onboarding_ready(client: TestClient, primary_goal: str = "surprise_me") -> None:
    response = client.patch(
        "/api/v1/me",
        json={
            "onboarding": {
                "stage": "ready",
                "language_confirmed": True,
                "primary_goal": primary_goal,
                "completed": False,
            }
        },
    )
    assert response.status_code == 200


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


def test_patch_me_merges_nested_onboarding_state() -> None:
    client = _client()

    response = client.patch(
        "/api/v1/me",
        json={
            "language": "es-419",
            "onboarding": {"language_confirmed": True},
        },
    )

    assert response.status_code == 200
    user = response.json()["user"]
    assert user["language"] == "es-419"
    assert user["onboarding"] == {
        "completed": False,
        "stage": "language_selection",
        "language_confirmed": True,
        "primary_goal": None,
    }


def test_patch_me_rejects_invalid_nested_onboarding_state() -> None:
    client = _client()

    response = client.patch(
        "/api/v1/me",
        json={"onboarding": {"stage": "complete"}},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_profile_patch"


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


def test_unknown_conversation_messages_return_not_found() -> None:
    client = _client()

    response = client.get(
        "/api/v1/conversations/00000000-0000-4000-8000-000000000000/messages"
    )

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_deleted_conversation_messages_return_not_found() -> None:
    client = _client()
    _set_onboarding_ready(client, primary_goal="test_stock_idea")
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]

    stream = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "Backtest Tesla when it dips",
            "language": "en",
        },
    )
    assert stream.status_code == 200

    hydrated = client.get(f"/api/v1/conversations/{conversation['id']}/messages")
    assert hydrated.status_code == 200
    assert len(hydrated.json()["items"]) > 0

    deleted = client.delete(f"/api/v1/conversations/{conversation['id']}")
    assert deleted.status_code == 200

    response = client.get(f"/api/v1/conversations/{conversation['id']}/messages")

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


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


def test_backtest_run_requires_idempotency_key_header() -> None:
    client = _client()

    response = client.post(
        "/api/v1/backtests/run",
        json={
            "template": "rsi_mean_reversion",
            "asset_class": "equity",
            "symbols": ["AAPL"],
        },
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["code"] == "idempotency_key_required"
    assert payload["request_id"]


def test_backtest_rejects_explicit_asset_class_conflict() -> None:
    client = _client()

    response = client.post(
        "/api/v1/backtests/run",
        headers={"Idempotency-Key": "asset-class-conflict"},
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


def test_backtest_run_normalizes_defaults_persists_metrics_and_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "false")
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
    assert run["conversation_result_card"]["asset_class"] == "equity"
    assert run["benchmark_symbol"] == "SPY"
    assert run["config_snapshot"]["side"] == "long"
    assert run["config_snapshot"]["starting_capital"] == 1000
    assert "_execution_realism" not in run["config_snapshot"]
    assert "summary" not in run
    assert set(run["metrics"]) == {"aggregate", "by_symbol"}
    assert isinstance(
        run["metrics"]["aggregate"]["performance"]["total_return_pct"], float
    )
    assert run["conversation_result_card"]["assumptions"] == [
        "Long-only",
        "Equal weight",
        "No fees/slippage",
        "Benchmark: SPY",
    ]
    assert run["conversation_result_card"]["benchmark_note"] is None

    history = client.get("/api/v1/history")
    assert history.status_code == 200
    assert [item["type"] for item in history.json()["items"]] == ["run", "chat"]


def test_history_excludes_archived_and_deleted_chats_by_default() -> None:
    client = _client()

    client.post("/api/v1/conversations", json={"title": "Active idea"})
    archived = client.post(
        "/api/v1/conversations", json={"title": "Archived idea"}
    ).json()["conversation"]
    deleted = client.post("/api/v1/conversations", json={"title": "Deleted idea"}).json()[
        "conversation"
    ]

    assert (
        client.patch(
            f"/api/v1/conversations/{archived['id']}",
            json={"archived": True},
        ).status_code
        == 200
    )
    assert client.delete(f"/api/v1/conversations/{deleted['id']}").status_code == 200

    response = client.get("/api/v1/history")

    assert response.status_code == 200
    chat_titles = [
        item["title"] for item in response.json()["items"] if item["type"] == "chat"
    ]
    assert chat_titles == ["Active idea"]


def test_deleted_conversation_restore_moves_chat_back_to_recents() -> None:
    client = _client()

    conversation = client.post(
        "/api/v1/conversations",
        json={"title": "Restorable idea"},
    ).json()["conversation"]
    memory_message(
        conversation_id=conversation["id"],
        role="user",
        content="Can you test a DOGE buy-and-hold idea?",
    )

    assert client.delete(f"/api/v1/conversations/{conversation['id']}").status_code == 200
    default_deleted_ids = {
        item["id"]
        for item in client.get("/api/v1/history").json()["items"]
        if item["type"] == "chat"
    }
    recently_deleted_ids = {
        item["id"]
        for item in client.get("/api/v1/history?deleted=true").json()["items"]
        if item["type"] == "chat"
    }
    assert conversation["id"] not in default_deleted_ids
    assert conversation["id"] in recently_deleted_ids
    assert (
        client.get(f"/api/v1/conversations/{conversation['id']}/messages").status_code
        == 404
    )

    restore = client.patch(
        f"/api/v1/conversations/{conversation['id']}",
        json={"deleted_at": None},
    )

    assert restore.status_code == 200
    assert restore.json()["conversation"]["deleted_at"] is None
    restored_default_ids = {
        item["id"]
        for item in client.get("/api/v1/history").json()["items"]
        if item["type"] == "chat"
    }
    restored_deleted_ids = {
        item["id"]
        for item in client.get("/api/v1/history?deleted=true").json()["items"]
        if item["type"] == "chat"
    }
    assert conversation["id"] in restored_default_ids
    assert conversation["id"] not in restored_deleted_ids
    assert (
        client.get(f"/api/v1/conversations/{conversation['id']}/messages").status_code
        == 200
    )


def test_delete_all_conversations_soft_deletes_active_and_archived_chats() -> None:
    client = _client()

    active = client.post("/api/v1/conversations", json={"title": "Active idea"}).json()[
        "conversation"
    ]
    archived = client.post(
        "/api/v1/conversations", json={"title": "Archived idea"}
    ).json()["conversation"]
    already_deleted = client.post(
        "/api/v1/conversations", json={"title": "Deleted idea"}
    ).json()["conversation"]
    for conversation in (active, archived, already_deleted):
        memory_message(
            conversation_id=conversation["id"],
            role="user",
            content=f"Remember {conversation['title']}",
        )

    assert (
        client.patch(
            f"/api/v1/conversations/{archived['id']}",
            json={"archived": True},
        ).status_code
        == 200
    )
    assert (
        client.delete(f"/api/v1/conversations/{already_deleted['id']}").status_code == 200
    )

    response = client.delete("/api/v1/conversations")

    assert response.status_code == 200
    assert response.json() == {"success": True, "deleted_count": 2}
    assert client.delete("/api/v1/conversations").json()["deleted_count"] == 0
    default_chat_ids = {
        item["id"]
        for item in client.get("/api/v1/history").json()["items"]
        if item["type"] == "chat"
    }
    deleted_chat_ids = {
        item["id"]
        for item in client.get("/api/v1/history?deleted=true").json()["items"]
        if item["type"] == "chat"
    }
    deleted_archived_chat_ids = {
        item["id"]
        for item in client.get("/api/v1/history?deleted=true&archived=true").json()[
            "items"
        ]
        if item["type"] == "chat"
    }

    assert active["id"] not in default_chat_ids
    assert archived["id"] not in default_chat_ids
    assert active["id"] in deleted_chat_ids
    assert already_deleted["id"] in deleted_chat_ids
    assert archived["id"] in deleted_archived_chat_ids


def test_delete_all_conversations_memory_fallback_skips_other_users_chats() -> None:
    from argus.api import state as api_state

    client = _client()
    owned = client.post("/api/v1/conversations", json={"title": "Mine"}).json()[
        "conversation"
    ]
    other = memory_conversation(
        title="Not mine",
        title_source="system_default",
        language="en",
        user_id="other-user-id",
    )
    memory_message(
        conversation_id=owned["id"],
        role="user",
        content="Remember my idea",
    )
    memory_message(
        conversation_id=other.id,
        role="user",
        content="Keep the other user's idea",
    )

    response = client.delete("/api/v1/conversations")

    assert response.status_code == 200
    assert response.json() == {"success": True, "deleted_count": 1}
    assert api_state.store.conversations[owned["id"]].deleted_at is not None
    assert api_state.store.conversations[other.id].deleted_at is None


def test_history_can_return_archived_chats_without_deleted_chats() -> None:
    client = _client()

    active = client.post("/api/v1/conversations", json={"title": "Active idea"}).json()[
        "conversation"
    ]
    archived = client.post(
        "/api/v1/conversations", json={"title": "Archived idea"}
    ).json()["conversation"]
    deleted = client.post("/api/v1/conversations", json={"title": "Deleted idea"}).json()[
        "conversation"
    ]

    assert (
        client.patch(
            f"/api/v1/conversations/{archived['id']}",
            json={"archived": True},
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/v1/conversations/{deleted['id']}",
            json={"archived": True},
        ).status_code
        == 200
    )
    assert client.delete(f"/api/v1/conversations/{deleted['id']}").status_code == 200

    response = client.get("/api/v1/history?archived=true")

    assert response.status_code == 200
    chat_titles = [
        item["title"] for item in response.json()["items"] if item["type"] == "chat"
    ]
    assert chat_titles == ["Archived idea"]
    assert active["id"] not in {item["id"] for item in response.json()["items"]}


def test_history_filters_runs_by_parent_conversation_lifecycle() -> None:
    client = _client()

    active = client.post("/api/v1/conversations", json={"title": "Active idea"}).json()[
        "conversation"
    ]
    archived = client.post(
        "/api/v1/conversations", json={"title": "Archived idea"}
    ).json()["conversation"]
    deleted = client.post("/api/v1/conversations", json={"title": "Deleted idea"}).json()[
        "conversation"
    ]

    for symbol, conversation in (
        ("AAPL", active),
        ("TSLA", archived),
        ("MSFT", deleted),
    ):
        response = client.post(
            "/api/v1/backtests/run",
            headers={"Idempotency-Key": f"{symbol.lower()}-history-lifecycle"},
            json={
                "conversation_id": conversation["id"],
                "template": "rsi_mean_reversion",
                "asset_class": "equity",
                "symbols": [symbol],
            },
        )
        assert response.status_code == 200

    assert (
        client.patch(
            f"/api/v1/conversations/{archived['id']}",
            json={"archived": True},
        ).status_code
        == 200
    )
    assert client.delete(f"/api/v1/conversations/{deleted['id']}").status_code == 200

    default_history = client.get("/api/v1/history").json()["items"]
    archived_history = client.get("/api/v1/history?archived=true").json()["items"]
    deleted_history = client.get("/api/v1/history?deleted=true").json()["items"]

    assert {
        item["conversation_id"] for item in default_history if item["type"] == "run"
    } == {active["id"]}
    assert {
        item["conversation_id"] for item in archived_history if item["type"] == "run"
    } == {archived["id"]}
    assert {
        item["conversation_id"] for item in deleted_history if item["type"] == "run"
    } == {deleted["id"]}


def test_execution_realism_payload_is_ignored_when_feature_flag_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.domain.engine import normalize_backtest_config

    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "false")
    config = normalize_backtest_config(
        {
            "template": "rsi_mean_reversion",
            "asset_class": "equity",
            "symbols": ["AAPL"],
            "_execution_realism": {
                "enabled": True,
                "fee_bps": 25,
                "slippage_bps": 40,
            },
        }
    )

    assert "_execution_realism" not in config


@pytest.mark.parametrize("timeframe", ["1h", "2h", "4h", "6h", "12h", "1D"])
def test_backtest_accepts_supported_timeframes(timeframe: str) -> None:
    client = _client()
    response = client.post(
        "/api/v1/backtests/run",
        headers={"Idempotency-Key": f"timeframe-{timeframe.lower()}"},
        json={
            "template": "dca_accumulation",
            "asset_class": "equity",
            "symbols": ["AAPL"],
            "timeframe": timeframe,
            "parameters": {"dca_cadence": "monthly"},
        },
    )
    assert response.status_code == 200
    assert response.json()["run"]["config_snapshot"]["timeframe"] == timeframe


def test_backtest_rejects_stablecoin_symbol() -> None:
    client = _client()
    response = client.post(
        "/api/v1/backtests/run",
        headers={"Idempotency-Key": "stablecoin-rejected"},
        json={
            "template": "dca_accumulation",
            "asset_class": "crypto",
            "symbols": ["USDT"],
            "timeframe": "1D",
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "stablecoin_not_supported"


def test_backtest_rejects_unsupported_parameters_payload() -> None:
    client = _client()
    response = client.post(
        "/api/v1/backtests/run",
        headers={"Idempotency-Key": "unsupported-parameters"},
        json={
            "template": "rsi_mean_reversion",
            "asset_class": "equity",
            "symbols": ["AAPL"],
            "parameters": {"rsi_length": 21},
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "unsupported_parameters"


def test_backtest_allows_equity_lookback_beyond_three_years() -> None:
    client = _client()
    response = client.post(
        "/api/v1/backtests/run",
        headers={"Idempotency-Key": "equity-long-lookback"},
        json={
            "template": "dca_accumulation",
            "asset_class": "equity",
            "symbols": ["AAPL"],
            "start_date": "2020-01-01",
            "end_date": "2024-01-10",
        },
    )
    assert response.status_code == 200
    assert response.json()["run"]["asset_class"] == "equity"


def test_backtest_rejects_equity_start_before_provider_history() -> None:
    client = _client()
    response = client.post(
        "/api/v1/backtests/run",
        headers={"Idempotency-Key": "provider-history-start"},
        json={
            "template": "buy_and_hold",
            "asset_class": "equity",
            "symbols": ["AAPL"],
            "start_date": "2015-12-31",
            "end_date": "2016-01-15",
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "provider_history_start_unavailable"


def test_backtest_rejects_unknown_symbol() -> None:
    client = _client()
    response = client.post(
        "/api/v1/backtests/run",
        headers={"Idempotency-Key": "unknown-symbol"},
        json={
            "template": "dca_accumulation",
            "asset_class": "equity",
            "symbols": ["FAKE123"],
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_symbol"


def test_draft_strategy_templates_have_no_api_path() -> None:
    """Containment by construction: draft templates are rejected at the API boundary.

    StrategyTemplate is derived from the capability registry's executable set, so the
    two draft strategies (momentum_breakout, trend_follow) cannot be saved or run via a
    direct API call outside the chat UI.
    """
    client = _client()
    for template in ("momentum_breakout", "trend_follow"):
        created = client.post(
            "/api/v1/strategies",
            json={
                "name": "Draft probe",
                "template": template,
                "asset_class": "equity",
                "symbols": ["AAPL"],
                "parameters": {},
            },
        )
        assert created.status_code == 422, f"{template} accepted by POST /strategies"

        ran = client.post(
            "/api/v1/backtests/run",
            headers={"Idempotency-Key": f"draft-{template}"},
            json={
                "template": template,
                "asset_class": "equity",
                "symbols": ["AAPL"],
            },
        )
        assert ran.status_code == 422, f"{template} accepted by POST /backtests/run"


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
            "name": "Bitcoin buy and hold",
            "template": "buy_and_hold",
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


def test_collection_attach_rejects_unowned_memory_strategy() -> None:
    client = _client()
    now = utcnow()
    collection = client.post(
        "/api/v1/collections", json={"name": "Ideas to revisit"}
    ).json()["collection"]
    other_strategy = Strategy(
        id="other-strategy",
        name="Other user's strategy",
        name_source="user_renamed",
        template="buy_and_hold",
        asset_class="equity",
        symbols=["AAPL"],
        parameters={},
        metrics_preferences=["total_return_pct"],
        benchmark_symbol="SPY",
        created_at=now,
        updated_at=now,
    )
    api_state.store.strategies[other_strategy.id] = other_strategy
    api_state.store.strategy_owners[other_strategy.id] = "other-user"

    response = client.post(
        f"/api/v1/collections/{collection['id']}/strategies",
        json={"strategy_ids": [other_strategy.id]},
    )

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
    assert api_state.store.collection_strategies[collection["id"]] == set()


def test_chat_stream_persists_messages_and_emits_contract_events() -> None:
    client = _client()
    _set_onboarding_ready(client, primary_goal="test_stock_idea")
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
    assert '"type":"stage_start","stage":"interpret"' in stream
    assert '"type":"stage_outcome","outcome":"ready_to_respond"' in stream
    assert '"type":"token"' in stream
    assert '"type":"final"' in stream
    assert "data: [DONE]" in stream

    result_line = next(
        line.removeprefix("data: ")
        for line in stream.splitlines()
        if line.startswith("data: {") and '"run"' in line
    )
    assert json.loads(result_line)["payload"]["run"]["conversation_result_card"][
        "status_label"
    ]

    messages = client.get(f"/api/v1/conversations/{conversation['id']}/messages")
    assert [message["role"] for message in messages.json()["items"]] == [
        "user",
        "assistant",
    ]


def test_chat_stream_with_es_419_emits_spanish_assistant_copy() -> None:
    client = _client()
    _set_onboarding_ready(client, primary_goal="test_stock_idea")
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]

    response = client.post(
        "/api/v1/chat/stream",
        headers={"Idempotency-Key": "chat-spanish"},
        json={
            "conversation_id": conversation["id"],
            "message": "Backtest Tesla when it dips",
            "language": "es-419",
        },
    )

    assert response.status_code == 200
    assert '"type":"token"' in response.text

    messages = client.get(f"/api/v1/conversations/{conversation['id']}/messages")
    assert messages.status_code == 200
    assistant_message = messages.json()["items"][-1]
    assert assistant_message["role"] == "assistant"
    assert "Probé la idea con TSLA." in assistant_message["content"]


def test_chat_stream_defaults_to_english_assistant_copy() -> None:
    client = _client()
    _set_onboarding_ready(client, primary_goal="test_stock_idea")
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]

    response = client.post(
        "/api/v1/chat/stream",
        headers={"Idempotency-Key": "chat-default-language"},
        json={
            "conversation_id": conversation["id"],
            "message": "Backtest Tesla when it dips",
        },
    )

    assert response.status_code == 200
    assert '"type":"token"' in response.text

    messages = client.get(f"/api/v1/conversations/{conversation['id']}/messages")
    assert messages.status_code == 200
    assistant_message = messages.json()["items"][-1]
    assert assistant_message["role"] == "assistant"
    assert "I tested that idea with TSLA." in assistant_message["content"]


def test_chat_stream_prompts_for_onboarding_before_first_run() -> None:
    client = _client()
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "Backtest Tesla when it dips",
            "language": "en",
        },
    )

    assert response.status_code == 200
    stream = response.text
    assert "event:" not in stream
    assert stream.count("data: [DONE]") == 1
    events = _stream_events(stream)
    token_events = [event for event in events if event.get("type") == "token"]
    assert len(token_events) == 1
    assert "primary goal" in token_events[0]["content"]
    final_payload = _final_payload(stream)
    assert set(final_payload) == {
        "stage_outcome",
        "assistant_response",
        "message_id",
    }
    assert final_payload["stage_outcome"] == "await_user_reply"
    assert final_payload["assistant_response"] == token_events[0]["content"]
    assert final_payload["message_id"]


def test_chat_stream_onboarding_goal_selection_sets_ready_stage() -> None:
    client = _client()
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "__ONBOARDING_GOAL__:test_stock_idea",
            "language": "en",
        },
    )
    assert response.status_code == 200
    stream = response.text
    assert "event:" not in stream
    assert stream.count("data: [DONE]") == 1
    events = _stream_events(stream)
    token_events = [event for event in events if event.get("type") == "token"]
    assert len(token_events) == 1
    assert "stock idea" in token_events[0]["content"]
    final_payload = _final_payload(stream)
    assert set(final_payload) == {
        "stage_outcome",
        "assistant_response",
        "message_id",
    }
    assert final_payload["stage_outcome"] == "ready_to_respond"
    assert final_payload["assistant_response"] == token_events[0]["content"]
    assert final_payload["message_id"]

    me = client.get("/api/v1/me")
    onboarding = me.json()["user"]["onboarding"]
    assert onboarding["stage"] == "ready"
    assert onboarding["primary_goal"] == "test_stock_idea"
    assert onboarding["completed"] is False

    messages = client.get(f"/api/v1/conversations/{conversation['id']}/messages")
    assert messages.status_code == 200
    items = messages.json()["items"]
    assert all(not message["content"].startswith("__ONBOARDING_") for message in items)


def test_first_successful_backtest_transitions_onboarding_to_completed() -> None:
    client = _client()
    _set_onboarding_ready(client, primary_goal="test_stock_idea")
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "Backtest Tesla when it dips",
            "language": "en",
        },
    )

    assert response.status_code == 200
    assert '"type":"final"' in response.text
    assert '"run"' in response.text

    me = client.get("/api/v1/me")
    onboarding = me.json()["user"]["onboarding"]
    assert onboarding["stage"] == "completed"
    assert onboarding["completed"] is True
    assert onboarding["primary_goal"] == "test_stock_idea"


def test_conversations_cursor_pagination_is_stable() -> None:
    client = _client()
    for idx in range(3):
        created = client.post(
            "/api/v1/conversations",
            json={"title": f"Idea {idx + 1}"},
        )
        assert created.status_code == 200

    first_page = client.get("/api/v1/conversations?limit=2")
    assert first_page.status_code == 200
    payload = first_page.json()
    assert len(payload["items"]) == 2
    assert payload["next_cursor"] is not None

    second_page = client.get(
        f"/api/v1/conversations?limit=2&cursor={payload['next_cursor']}"
    )
    assert second_page.status_code == 200
    second_payload = second_page.json()
    assert second_payload["items"]
    first_ids = {item["id"] for item in payload["items"]}
    second_ids = {item["id"] for item in second_payload["items"]}
    assert first_ids.isdisjoint(second_ids)


def test_messages_cursor_pagination_is_stable() -> None:
    client = _client()
    _set_onboarding_ready(client, primary_goal="test_stock_idea")
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]
    for idx in range(3):
        response = client.post(
            "/api/v1/chat/stream",
            json={
                "conversation_id": conversation["id"],
                "message": f"Test message {idx}",
                "language": "en",
            },
        )
        assert response.status_code == 200

    first_page = client.get(
        f"/api/v1/conversations/{conversation['id']}/messages?limit=2"
    )
    assert first_page.status_code == 200
    first_payload = first_page.json()
    assert len(first_payload["items"]) == 2
    assert first_payload["next_cursor"] is not None

    second_page = client.get(
        f"/api/v1/conversations/{conversation['id']}/messages?limit=2&cursor={first_payload['next_cursor']}"
    )
    assert second_page.status_code == 200
    second_payload = second_page.json()
    assert second_payload["items"]
    first_ids = {item["id"] for item in first_payload["items"]}
    second_ids = {item["id"] for item in second_payload["items"]}
    assert first_ids.isdisjoint(second_ids)


def test_search_supports_cursor_and_mixed_types() -> None:
    client = _client()
    _set_onboarding_ready(client, primary_goal="test_stock_idea")
    conversation = client.post(
        "/api/v1/conversations", json={"title": "Tesla alpha chat"}
    ).json()["conversation"]
    client.post(
        "/api/v1/strategies",
        json={
            "name": "Tesla strategy",
            "template": "rsi_mean_reversion",
            "asset_class": "equity",
            "symbols": ["TSLA"],
            "parameters": {},
        },
    )
    client.post("/api/v1/collections", json={"name": "Tesla collection"})
    run = client.post(
        "/api/v1/backtests/run",
        headers={"Idempotency-Key": "search-mixed-types-run"},
        json={
            "conversation_id": conversation["id"],
            "template": "rsi_mean_reversion",
            "asset_class": "equity",
            "symbols": ["TSLA"],
        },
    )
    assert run.status_code == 200

    first_page = client.get("/api/v1/search?q=tesla&limit=2")
    assert first_page.status_code == 200
    payload = first_page.json()
    assert payload["items"]
    assert payload["next_cursor"] is not None
    result_types = {item["type"] for item in payload["items"]}
    assert result_types.issubset({"chat", "strategy", "collection", "run"})

    second_page = client.get(
        f"/api/v1/search?q=tesla&limit=2&cursor={payload['next_cursor']}"
    )
    assert second_page.status_code == 200
    second_payload = second_page.json()
    first_ids = {(item["type"], item["id"]) for item in payload["items"]}
    second_ids = {(item["type"], item["id"]) for item in second_payload["items"]}
    assert first_ids.isdisjoint(second_ids)


def test_search_memory_mode_matches_multi_word_queries_like_supabase() -> None:
    # Memory mode shares the Supabase matcher semantics: a multi-word query
    # matches when every token appears, not only as one contiguous substring.
    client = _client()
    _set_onboarding_ready(client, primary_goal="test_stock_idea")
    conversation = client.post(
        "/api/v1/conversations", json={"title": "Tesla alpha chat"}
    ).json()["conversation"]

    response = client.get("/api/v1/search", params={"q": "tesla chat"})
    assert response.status_code == 200
    items = response.json()["items"]
    assert [
        item["id"] for item in items if item["type"] == "chat"
    ] == [conversation["id"]]


def test_search_emits_recall_usage_product_event(monkeypatch) -> None:
    observed: list[dict[str, object]] = []

    def fake_capture(kind: str, **kwargs: object) -> None:
        observed.append({"kind": kind, **kwargs})

    monkeypatch.setattr(
        "argus.api.routers.search.capture_product_event",
        fake_capture,
        raising=False,
    )
    client = _client()
    user_id = api_state.store.get_or_create_dev_user().id
    memory_conversation(
        title="Tesla recall source",
        title_source="user_renamed",
        language="en",
        user_id=user_id,
    )

    response = client.get("/api/v1/search?q=tesla&limit=20")

    assert response.status_code == 200
    assert observed == [
        {
            "kind": "recall_usage",
            "user_id": user_id,
            "status": "completed",
            "attributes": {
                "query_present": True,
                "decision_state_filter_present": False,
                "result_count": 1,
                "returned_types": ["chat"],
                "has_more": False,
                "source": "memory",
            },
        }
    ]


def test_search_orders_p1_artifacts_before_source_conversation() -> None:
    client = _client()
    user_id = api_state.store.get_or_create_dev_user().id
    now = utcnow()
    conversation = Conversation(
        id="conversation-evidence-order",
        title="AAPL evidence source conversation",
        title_source="user_renamed",
        pinned=False,
        archived=False,
        deleted_at=None,
        created_at=now - timedelta(minutes=5),
        updated_at=now + timedelta(minutes=5),
        last_message_preview="AAPL evidence chat wrapper",
        language="en",
    )
    run = BacktestRun(
        id="run-evidence-order",
        conversation_id=conversation.id,
        strategy_id=None,
        status="completed",
        asset_class="equity",
        symbols=["AAPL"],
        allocation_method="equal_weight",
        benchmark_symbol="SPY",
        metrics={"aggregate": {}, "by_symbol": {}},
        config_snapshot={"symbols": ["AAPL"], "benchmark_symbol": "SPY"},
        conversation_result_card={
            "title": "AAPL evidence backtest",
            "artifact_type": "backtest",
            "evidence_artifact_id": "artifact-evidence-order",
            "evidence_lifecycle": "captured",
        },
        created_at=now,
    )
    idea = Idea(
        id="idea-evidence-order",
        source_conversation_id=conversation.id,
        title="AAPL evidence idea",
        summary="AAPL evidence summary",
        lifecycle="captured",
        active_version_id="version-evidence-order",
        created_at=now,
        updated_at=now,
    )
    version = IdeaVersion(
        id="version-evidence-order",
        idea_id=idea.id,
        source_conversation_id=conversation.id,
        source_run_id=run.id,
        version_number=1,
        canonical_spec={"symbols": ["AAPL"], "benchmark_symbol": "SPY"},
        strategy_snapshot={"symbols": ["AAPL"]},
        title=idea.title,
        summary=idea.summary,
        lifecycle="captured",
        created_at=now,
    )
    artifact = EvidenceArtifact(
        id="artifact-evidence-order",
        idea_id=idea.id,
        idea_version_id=version.id,
        source_conversation_id=conversation.id,
        source_run_id=run.id,
        artifact_type="backtest",
        lifecycle="captured",
        title="AAPL evidence artifact",
        digest="AAPL evidence artifact digest.",
        payload={"provenance": {"symbols": ["AAPL"], "benchmark_symbol": "SPY"}},
        created_at=now,
        updated_at=now,
    )
    decision = DecisionNote(
        id="decision-evidence-order",
        idea_id=idea.id,
        idea_version_id=version.id,
        evidence_artifact_id=artifact.id,
        source_conversation_id=conversation.id,
        decision_state="promising",
        note="AAPL evidence decision note.",
        created_at=now,
        updated_at=now,
    )
    api_state.store.conversations[conversation.id] = conversation
    api_state.store.conversation_owners[conversation.id] = user_id
    api_state.store.backtest_runs[run.id] = run
    api_state.store.backtest_run_owners[run.id] = user_id
    api_state.store.ideas[idea.id] = idea
    api_state.store.idea_owners[idea.id] = user_id
    api_state.store.idea_versions[version.id] = version
    api_state.store.idea_version_owners[version.id] = user_id
    api_state.store.evidence_artifacts[artifact.id] = artifact
    api_state.store.evidence_artifact_owners[artifact.id] = user_id
    api_state.store.decision_notes[decision.id] = decision
    api_state.store.decision_note_owners[decision.id] = user_id

    response = client.get("/api/v1/search?q=evidence&limit=10")

    assert response.status_code == 200
    ordered_types = [item["type"] for item in response.json()["items"]]
    chat_index = ordered_types.index("chat")
    for artifact_type in ("backtest", "evidence", "idea", "decision"):
        assert ordered_types.index(artifact_type) < chat_index


def test_search_idea_result_carries_latest_decision_state() -> None:
    client = _client()
    user_id = api_state.store.get_or_create_dev_user().id
    now = utcnow()
    idea = Idea(
        id="idea-ledger-status",
        source_conversation_id="conversation-ledger-status",
        title="NVDA momentum ledger idea",
        summary="NVDA momentum ledger summary",
        lifecycle="decided",
        active_version_id="version-ledger-status",
        created_at=now - timedelta(minutes=10),
        updated_at=now,
    )
    older_decision = DecisionNote(
        id="decision-ledger-older",
        idea_id=idea.id,
        idea_version_id="version-ledger-status",
        evidence_artifact_id="artifact-ledger-status",
        source_conversation_id="conversation-ledger-status",
        decision_state="watching",
        note="Initial watch.",
        created_at=now - timedelta(minutes=5),
        updated_at=now - timedelta(minutes=5),
    )
    latest_decision = DecisionNote(
        id="decision-ledger-latest",
        idea_id=idea.id,
        idea_version_id="version-ledger-status",
        evidence_artifact_id="artifact-ledger-status",
        source_conversation_id="conversation-ledger-status",
        decision_state="promising",
        note="Upgraded after a fresh re-run.",
        created_at=now,
        updated_at=now,
    )
    api_state.store.ideas[idea.id] = idea
    api_state.store.idea_owners[idea.id] = user_id
    for decision in (older_decision, latest_decision):
        api_state.store.decision_notes[decision.id] = decision
        api_state.store.decision_note_owners[decision.id] = user_id

    response = client.get("/api/v1/search?q=ledger&limit=10")

    assert response.status_code == 200
    idea_items = [item for item in response.json()["items"] if item["type"] == "idea"]
    assert idea_items, "expected the saved idea in search results"
    assert idea_items[0]["decision_state"] == "promising"


def test_search_decision_state_filter_returns_only_matching_ideas() -> None:
    client = _client()
    user_id = api_state.store.get_or_create_dev_user().id
    now = utcnow()
    promising_idea = Idea(
        id="idea-ledger-promising",
        source_conversation_id="conversation-ledger-promising",
        title="QQQ trend idea",
        summary="QQQ trend summary",
        lifecycle="decided",
        active_version_id="version-ledger-promising",
        created_at=now,
        updated_at=now,
    )
    rejected_idea = Idea(
        id="idea-ledger-rejected",
        source_conversation_id="conversation-ledger-rejected",
        title="ARKK reversion idea",
        summary="ARKK reversion summary",
        lifecycle="decided",
        active_version_id="version-ledger-rejected",
        created_at=now,
        updated_at=now,
    )
    promising_decision = DecisionNote(
        id="decision-ledger-promising",
        idea_id=promising_idea.id,
        idea_version_id="version-ledger-promising",
        evidence_artifact_id="artifact-ledger-promising",
        source_conversation_id="conversation-ledger-promising",
        decision_state="promising",
        note="Keep.",
        created_at=now,
        updated_at=now,
    )
    rejected_decision = DecisionNote(
        id="decision-ledger-rejected",
        idea_id=rejected_idea.id,
        idea_version_id="version-ledger-rejected",
        evidence_artifact_id="artifact-ledger-rejected",
        source_conversation_id="conversation-ledger-rejected",
        decision_state="rejected",
        note="Drop.",
        created_at=now,
        updated_at=now,
    )
    for idea in (promising_idea, rejected_idea):
        api_state.store.ideas[idea.id] = idea
        api_state.store.idea_owners[idea.id] = user_id
    for decision in (promising_decision, rejected_decision):
        api_state.store.decision_notes[decision.id] = decision
        api_state.store.decision_note_owners[decision.id] = user_id

    response = client.get("/api/v1/search?q=&decision_state=promising&limit=20")

    assert response.status_code == 200
    items = response.json()["items"]
    assert items, "expected the promising idea"
    assert all(item["type"] == "idea" for item in items)
    assert all(item["decision_state"] == "promising" for item in items)
    returned_ids = {item["id"] for item in items}
    assert promising_idea.id in returned_ids
    assert rejected_idea.id not in returned_ids


def test_search_ledger_groups_are_backend_ordered_and_counted() -> None:
    client = _client()
    user_id = api_state.store.get_or_create_dev_user().id
    now = utcnow()
    ideas = [
        Idea(
            id="idea-ledger-group-promising-1",
            source_conversation_id="conversation-ledger-group-promising-1",
            title="AAPL promising idea",
            summary="AAPL promising summary",
            lifecycle="decided",
            active_version_id="version-ledger-group-promising-1",
            created_at=now - timedelta(minutes=3),
            updated_at=now - timedelta(minutes=3),
        ),
        Idea(
            id="idea-ledger-group-promising-2",
            source_conversation_id="conversation-ledger-group-promising-2",
            title="MSFT promising idea",
            summary="MSFT promising summary",
            lifecycle="decided",
            active_version_id="version-ledger-group-promising-2",
            created_at=now - timedelta(minutes=2),
            updated_at=now - timedelta(minutes=2),
        ),
        Idea(
            id="idea-ledger-group-watching",
            source_conversation_id="conversation-ledger-group-watching",
            title="BTC watching idea",
            summary="BTC watching summary",
            lifecycle="decided",
            active_version_id="version-ledger-group-watching",
            created_at=now - timedelta(minutes=1),
            updated_at=now - timedelta(minutes=1),
        ),
    ]
    decisions = [
        DecisionNote(
            id="decision-ledger-group-promising-1",
            idea_id=ideas[0].id,
            idea_version_id="version-ledger-group-promising-1",
            evidence_artifact_id="artifact-ledger-group-promising-1",
            source_conversation_id=ideas[0].source_conversation_id,
            decision_state="promising",
            note="Keep reviewing.",
            created_at=now - timedelta(minutes=3),
            updated_at=now - timedelta(minutes=3),
        ),
        DecisionNote(
            id="decision-ledger-group-promising-2",
            idea_id=ideas[1].id,
            idea_version_id="version-ledger-group-promising-2",
            evidence_artifact_id="artifact-ledger-group-promising-2",
            source_conversation_id=ideas[1].source_conversation_id,
            decision_state="promising",
            note="Still promising.",
            created_at=now - timedelta(minutes=2),
            updated_at=now - timedelta(minutes=2),
        ),
        DecisionNote(
            id="decision-ledger-group-watching",
            idea_id=ideas[2].id,
            idea_version_id="version-ledger-group-watching",
            evidence_artifact_id="artifact-ledger-group-watching",
            source_conversation_id=ideas[2].source_conversation_id,
            decision_state="watching",
            note="Watch for a better window.",
            created_at=now - timedelta(minutes=1),
            updated_at=now - timedelta(minutes=1),
        ),
    ]
    for idea in ideas:
        api_state.store.ideas[idea.id] = idea
        api_state.store.idea_owners[idea.id] = user_id
    for decision in decisions:
        api_state.store.decision_notes[decision.id] = decision
        api_state.store.decision_note_owners[decision.id] = user_id

    response = client.get("/api/v1/search?q=&include_ledger_groups=true&limit=20")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ledger_groups"] == [
        {"decision_state": "promising", "count": 2},
        {"decision_state": "watching", "count": 1},
        {"decision_state": "rejected", "count": 0},
        {"decision_state": "revisit_later", "count": 0},
    ]
    assert {item["id"] for item in payload["items"]} == {idea.id for idea in ideas}
    assert all(item["type"] == "idea" for item in payload["items"])


def test_search_decision_state_filter_keeps_unfiltered_ledger_groups() -> None:
    client = _client()
    user_id = api_state.store.get_or_create_dev_user().id
    now = utcnow()
    promising_idea = Idea(
        id="idea-ledger-filter-group-promising",
        source_conversation_id="conversation-ledger-filter-group-promising",
        title="NVDA promising idea",
        summary="NVDA promising summary",
        lifecycle="decided",
        active_version_id="version-ledger-filter-group-promising",
        created_at=now,
        updated_at=now,
    )
    watching_idea = Idea(
        id="idea-ledger-filter-group-watching",
        source_conversation_id="conversation-ledger-filter-group-watching",
        title="ETH watching idea",
        summary="ETH watching summary",
        lifecycle="decided",
        active_version_id="version-ledger-filter-group-watching",
        created_at=now,
        updated_at=now,
    )
    promising_decision = DecisionNote(
        id="decision-ledger-filter-group-promising",
        idea_id=promising_idea.id,
        idea_version_id="version-ledger-filter-group-promising",
        evidence_artifact_id="artifact-ledger-filter-group-promising",
        source_conversation_id=promising_idea.source_conversation_id,
        decision_state="promising",
        note="Promising.",
        created_at=now,
        updated_at=now,
    )
    watching_decision = DecisionNote(
        id="decision-ledger-filter-group-watching",
        idea_id=watching_idea.id,
        idea_version_id="version-ledger-filter-group-watching",
        evidence_artifact_id="artifact-ledger-filter-group-watching",
        source_conversation_id=watching_idea.source_conversation_id,
        decision_state="watching",
        note="Watching.",
        created_at=now,
        updated_at=now,
    )
    for idea in (promising_idea, watching_idea):
        api_state.store.ideas[idea.id] = idea
        api_state.store.idea_owners[idea.id] = user_id
    for decision in (promising_decision, watching_decision):
        api_state.store.decision_notes[decision.id] = decision
        api_state.store.decision_note_owners[decision.id] = user_id

    response = client.get(
        "/api/v1/search?q=&decision_state=promising&include_ledger_groups=true&limit=20"
    )

    assert response.status_code == 200
    payload = response.json()
    assert [item["id"] for item in payload["items"]] == [promising_idea.id]
    assert payload["ledger_groups"] == [
        {"decision_state": "promising", "count": 1},
        {"decision_state": "watching", "count": 1},
        {"decision_state": "rejected", "count": 0},
        {"decision_state": "revisit_later", "count": 0},
    ]


def test_search_preserves_pinned_chat_above_p1_artifacts() -> None:
    client = _client()
    user_id = api_state.store.get_or_create_dev_user().id
    now = utcnow()
    conversation = Conversation(
        id="conversation-pinned-search-order",
        title="AAPL pinned conversation",
        title_source="user_renamed",
        pinned=True,
        archived=False,
        deleted_at=None,
        created_at=now - timedelta(minutes=5),
        updated_at=now + timedelta(minutes=10),
        last_message_preview="AAPL pinned source",
        language="en",
    )
    artifact = EvidenceArtifact(
        id="artifact-pinned-search-order",
        idea_id="idea-pinned-search-order",
        idea_version_id="version-pinned-search-order",
        source_conversation_id=conversation.id,
        source_run_id="run-pinned-search-order",
        artifact_type="backtest",
        lifecycle="captured",
        title="AAPL evidence artifact",
        digest="AAPL evidence artifact digest.",
        payload={"provenance": {"symbols": ["AAPL"], "benchmark_symbol": "SPY"}},
        created_at=now,
        updated_at=now,
    )
    api_state.store.conversations[conversation.id] = conversation
    api_state.store.conversation_owners[conversation.id] = user_id
    api_state.store.evidence_artifacts[artifact.id] = artifact
    api_state.store.evidence_artifact_owners[artifact.id] = user_id

    response = client.get("/api/v1/search?q=aapl&limit=10")

    assert response.status_code == 200
    ordered_types = [item["type"] for item in response.json()["items"]]
    assert ordered_types.index("chat") < ordered_types.index("evidence")


def test_search_preserves_exact_chat_above_lower_relevance_p1_artifacts() -> None:
    client = _client()
    user_id = api_state.store.get_or_create_dev_user().id
    now = utcnow()
    conversation = Conversation(
        id="conversation-exact-search-order",
        title="AAPL",
        title_source="user_renamed",
        pinned=False,
        archived=False,
        deleted_at=None,
        created_at=now - timedelta(minutes=5),
        updated_at=now + timedelta(minutes=10),
        last_message_preview="AAPL exact source",
        language="en",
    )
    artifact = EvidenceArtifact(
        id="artifact-exact-search-order",
        idea_id="idea-exact-search-order",
        idea_version_id="version-exact-search-order",
        source_conversation_id=conversation.id,
        source_run_id="run-exact-search-order",
        artifact_type="backtest",
        lifecycle="captured",
        title="AAPL evidence artifact",
        digest="AAPL evidence artifact digest.",
        payload={"provenance": {"symbols": ["AAPL"], "benchmark_symbol": "SPY"}},
        created_at=now,
        updated_at=now,
    )
    api_state.store.conversations[conversation.id] = conversation
    api_state.store.conversation_owners[conversation.id] = user_id
    api_state.store.evidence_artifacts[artifact.id] = artifact
    api_state.store.evidence_artifact_owners[artifact.id] = user_id

    response = client.get("/api/v1/search?q=aapl&limit=10")

    assert response.status_code == 200
    ordered_types = [item["type"] for item in response.json()["items"]]
    assert ordered_types.index("chat") < ordered_types.index("evidence")


def test_search_memory_mode_excludes_other_users_owned_objects() -> None:
    client = _client()
    _set_onboarding_ready(client, primary_goal="test_stock_idea")
    other_user_id = "00000000-0000-0000-0000-000000000099"
    now = utcnow()
    memory_conversation(
        title="Leaky Tesla alpha chat",
        title_source="user_renamed",
        language="en",
        user_id=other_user_id,
    )
    strategy = Strategy(
        id="other-strategy",
        name="Leaky Tesla strategy",
        name_source="user_renamed",
        template="rsi_mean_reversion",
        asset_class="equity",
        symbols=["TSLA"],
        parameters={},
        metrics_preferences=["total_return_pct"],
        benchmark_symbol="SPY",
        created_at=now,
        updated_at=now,
    )
    collection = Collection(
        id="other-collection",
        name="Leaky Tesla collection",
        name_source="user_renamed",
        created_at=now,
        updated_at=now,
    )
    run = BacktestRun(
        id="other-run",
        conversation_id=None,
        strategy_id=None,
        status="completed",
        asset_class="equity",
        symbols=["TSLA"],
        allocation_method="equal_weight",
        benchmark_symbol="SPY",
        metrics={},
        config_snapshot={"template": "rsi_mean_reversion"},
        conversation_result_card={"title": "Leaky Tesla backtest"},
        created_at=now,
    )
    api_state.store.strategies[strategy.id] = strategy
    api_state.store.collections[collection.id] = collection
    api_state.store.backtest_runs[run.id] = run
    api_state.store.backtest_run_owners[run.id] = other_user_id
    api_state.store.strategy_owners = {strategy.id: other_user_id}
    api_state.store.collection_owners = {collection.id: other_user_id}

    response = client.get("/api/v1/search?q=leaky&limit=20")

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_decision_endpoint_marks_evidence_artifact_decided() -> None:
    client = _client()
    _set_onboarding_ready(client, primary_goal="test_stock_idea")
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]

    response = client.post(
        "/api/v1/chat/stream",
        headers={"Idempotency-Key": "chat-p1-evidence"},
        json={
            "conversation_id": conversation["id"],
            "message": "Backtest TSLA from 2025 to 2025",
            "language": "en",
        },
    )
    payload = _final_payload(response.text)
    artifact_id = payload["run"]["conversation_result_card"]["evidence_artifact_id"]

    decision = client.post(
        f"/api/v1/evidence-artifacts/{artifact_id}/decision",
        json={"decision_state": "promising", "note": "Worth revisiting."},
    )

    assert decision.status_code == 200
    body = decision.json()
    assert body["decision"]["decision_state"] == "promising"
    assert body["decision"]["note"] == "Worth revisiting."
    assert body["evidence_artifact"]["lifecycle"] == "decided"
    artifact = api_state.store.evidence_artifacts[artifact_id]
    assert api_state.store.ideas[artifact.idea_id].lifecycle == "decided"
    assert api_state.store.idea_versions[artifact.idea_version_id].lifecycle == "decided"
    assistant_result_cards = [
        message.metadata.get("result_card")
        for messages in api_state.store.messages.values()
        for message in messages
        if message.role == "assistant"
        and isinstance(message.metadata.get("result_card"), dict)
    ]
    assert any(
        card.get("evidence_artifact_id") == artifact_id
        and card.get("decision_state") == "promising"
        for card in assistant_result_cards
    )


def test_decision_endpoint_is_idempotent_per_evidence_artifact() -> None:
    client = _client()
    _set_onboarding_ready(client, primary_goal="test_stock_idea")
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]

    response = client.post(
        "/api/v1/chat/stream",
        headers={"Idempotency-Key": "chat-p1-decision-idempotent"},
        json={
            "conversation_id": conversation["id"],
            "message": "Backtest TSLA from 2025 to 2025",
            "language": "en",
        },
    )
    artifact_id = _final_payload(response.text)["run"]["conversation_result_card"][
        "evidence_artifact_id"
    ]

    first = client.post(
        f"/api/v1/evidence-artifacts/{artifact_id}/decision",
        json={"decision_state": "watching", "note": "Track it."},
    )
    second = client.post(
        f"/api/v1/evidence-artifacts/{artifact_id}/decision",
        json={"decision_state": "promising", "note": "Still promising."},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    first_body = first.json()
    second_body = second.json()
    assert second_body["decision"]["id"] == first_body["decision"]["id"]
    assert second_body["decision"]["decision_state"] == "promising"
    assert second_body["decision"]["note"] == "Still promising."
    decisions_for_artifact = [
        decision
        for decision in api_state.store.decision_notes.values()
        if decision.evidence_artifact_id == artifact_id
    ]
    assert len(decisions_for_artifact) == 1


def test_decision_endpoint_invalid_body_returns_problem_details() -> None:
    client = _client()
    response = client.post(
        "/api/v1/evidence-artifacts/artifact-1/decision",
        json={},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["type"] == "https://api.argus.app/problems/validation-error"
    assert body["title"] == "Validation Error"
    assert body["status"] == 422
    assert body["code"] == "validation_error"
    assert body["request_id"]
    assert isinstance(body["context"]["errors"], list)
    assert "decision_state" in str(body["context"]["errors"])


def test_search_returns_typed_p1_artifacts() -> None:
    client = _client()
    _set_onboarding_ready(client, primary_goal="test_stock_idea")
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]

    response = client.post(
        "/api/v1/chat/stream",
        headers={"Idempotency-Key": "chat-p1-search"},
        json={
            "conversation_id": conversation["id"],
            "message": "Backtest TSLA from 2025 to 2025",
            "language": "en",
        },
    )
    artifact_id = _final_payload(response.text)["run"]["conversation_result_card"][
        "evidence_artifact_id"
    ]
    client.post(
        f"/api/v1/evidence-artifacts/{artifact_id}/decision",
        json={"decision_state": "watching", "note": "Track it."},
    )

    payload = client.get("/api/v1/search?q=TSLA&limit=20").json()

    types = {item["type"] for item in payload["items"]}
    assert {"chat", "backtest", "evidence", "idea", "decision"}.issubset(types)
    evidence = next(item for item in payload["items"] if item["type"] == "evidence")
    assert evidence["conversation_id"] == conversation["id"]
    assert evidence["preview"]["digest"]
    assert evidence["preview"]["quick_take"] == "I tested that idea with TSLA."
    assert evidence["preview"]["assumptions"] == ["Starting capital: $10,000."]
    assert evidence["preview"]["metrics_summary"] == {"total_return_pct": 12.5}
    assert evidence["preview"]["symbols"] == ["TSLA"]
    assert evidence["preview"]["benchmark_symbol"] == "SPY"
    assert "context_packets" not in evidence["preview"]
    assert not any(key.endswith("_id") for key in evidence["preview"])
    idea = next(item for item in payload["items"] if item["type"] == "idea")
    assert idea["conversation_id"] == conversation["id"]
    assert idea["preview"]["digest"]
    assert not any(key.endswith("_id") for key in idea["preview"])
    decision = next(item for item in payload["items"] if item["type"] == "decision")
    assert decision["preview"]["decision_state"] == "watching"
    assert not any(key.endswith("_id") for key in decision["preview"])
    assert decision["matched_text"].startswith("Track it.")
    assert "I tested that idea with TSLA." in decision["matched_text"]
    assert "backtest versus" not in decision["matched_text"]
    assert "watching" not in decision["matched_text"]


def test_invalid_cursor_returns_problem_details() -> None:
    client = _client()
    response = client.get("/api/v1/search?q=tesla&limit=5&cursor=not-a-valid-cursor")
    assert response.status_code == 400
    payload = response.json()
    assert payload["code"] == "validation_error"


def test_chat_missing_symbol_asks_clarifying_question(monkeypatch) -> None:
    from argus.api.routers import agent as agent_router

    client = _client()
    _set_onboarding_ready(client)
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]

    async def _missing_symbol_events(**_: Any):
        yield {
            "type": "final",
            "payload": {
                "stage_outcome": "await_user_reply",
                "assistant_prompt": "Which symbols do you want to test?",
                "final_response_payload": {"error": "missing_required_input"},
            },
        }

    monkeypatch.setattr(
        agent_router,
        "stream_agent_turn_events",
        _missing_symbol_events,
    )

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "Run RSI",
            "language": "en",
        },
    )

    assert response.status_code == 200
    assert "Which symbols do you want to test?" in response.text
    assert "running_backtest" not in response.text
    assert '"run"' not in response.text


def test_chat_run_uses_extracted_timeframe_not_hardcoded_1d(monkeypatch) -> None:
    from argus.api.routers import agent as agent_router

    client = _client()
    _set_onboarding_ready(client)
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]

    async def _btc_1h_events(**_: Any):
        result = _runtime_success_result(symbol="BTC", timeframe="1h")
        yield {"type": "final", "payload": result}

    monkeypatch.setattr(agent_router, "stream_agent_turn_events", _btc_1h_events)

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "Run BTC 1h",
        },
    )

    assert response.status_code == 200
    # The timeframe "1h" should be in the result run config_snapshot
    assert '"timeframe":"1h"' in response.text or '"timeframe": "1h"' in response.text


def test_chat_stream_passes_thread_context_to_runtime(monkeypatch) -> None:
    from argus.api import state as api_state
    from argus.api.routers import agent as agent_router

    client = _client()
    _set_onboarding_ready(client)
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]

    # Insert a message into memory store manually
    from datetime import datetime, timezone

    from argus.api.schemas import Message

    msg1 = Message(
        id="msg1",
        conversation_id=conversation["id"],
        role="user",
        content="Tell me about AAPL",
        created_at=datetime.now(timezone.utc),
    )
    api_state.store.messages[conversation["id"]] = [msg1]

    captured_runtime: dict[str, Any] = {}

    async def _fake_stream_agent_turn_events(**kwargs: Any):
        captured_runtime.update(kwargs)
        yield {
            "type": "final",
            "payload": _runtime_success_result(symbol="AAPL", assistant_response="ok"),
        }

    monkeypatch.setattr(
        agent_router,
        "stream_agent_turn_events",
        _fake_stream_agent_turn_events,
    )

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "Backtest it",
        },
    )

    assert response.status_code == 200
    assert captured_runtime["thread_id"] == conversation["id"]
    assert captured_runtime["message"] == "Backtest it"


def test_starter_prompts_returns_personalized_suggestions() -> None:
    client = _client()

    # Default goal: surprise_me (via OnboardingState default in Profile)
    # Actually OnboardingState primary_goal is None by default, which maps to surprise_me
    resp = client.get("/api/v1/chat/starter-prompts")
    assert resp.status_code == 200
    assert len(resp.json()["prompts"]) == 4
    assert "Test Apple against SPY over the last 12 months." in resp.json()["prompts"]

    # Set specific goal
    _set_onboarding_ready(client, primary_goal="explore_crypto")
    resp = client.get("/api/v1/chat/starter-prompts")
    assert resp.status_code == 200
    assert "Hold Bitcoin this year so far." in resp.json()["prompts"]


def test_starter_prompts_follow_profile_language() -> None:
    client = _client()

    response = client.patch(
        "/api/v1/me",
        json={
            "language": "es-419",
            "onboarding": {
                "stage": "ready",
                "language_confirmed": True,
                "primary_goal": "explore_crypto",
                "completed": False,
            },
        },
    )
    assert response.status_code == 200

    resp = client.get("/api/v1/chat/starter-prompts")
    assert resp.status_code == 200
    prompts = resp.json()["prompts"]
    assert len(prompts) == 4
    assert "Mantén Bitcoin en lo que va del año." in prompts
    assert all("2024" not in prompt for prompt in prompts)
