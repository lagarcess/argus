from __future__ import annotations

import json
from datetime import date

import pandas as pd
import pytest
from argus.api.main import app
from argus.domain.market_data.assets import ResolvedAsset
from fastapi.testclient import TestClient


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
    index = pd.date_range(start=start_date, end=end_date, freq=freq_map[timeframe], tz="UTC")
    if len(index) < 80:
        index = pd.date_range(start=start_date, periods=80, freq=freq_map[timeframe], tz="UTC")
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


@pytest.fixture(autouse=True)
def _patch_engine_io(monkeypatch: pytest.MonkeyPatch) -> None:
    from argus.api import main as api_main
    from argus.domain import engine as domain_engine

    monkeypatch.setattr(api_main, "supabase_gateway", None)
    monkeypatch.setattr(
        api_main,
        "extract_strategy_request",
        lambda message: {
            "template": "rsi_mean_reversion",
            "asset_class": "equity",
            "symbols": ["TSLA"],
            "parameters": {},
        },
    )
    monkeypatch.setattr(domain_engine, "resolve_asset", _fake_resolve_asset)
    monkeypatch.setattr(domain_engine, "fetch_ohlcv", _fake_fetch_ohlcv)
    monkeypatch.setattr(domain_engine, "fetch_price_series", _fake_fetch_price_series)


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
    assert isinstance(run["metrics"]["aggregate"]["performance"]["total_return_pct"], float)
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


@pytest.mark.parametrize("timeframe", ["1h", "2h", "4h", "6h", "12h", "1D"])
def test_backtest_accepts_supported_timeframes(timeframe: str) -> None:
    client = _client()
    response = client.post(
        "/api/v1/backtests/run",
        json={
            "template": "dca_accumulation",
            "asset_class": "equity",
            "symbols": ["AAPL"],
            "timeframe": timeframe,
        },
    )
    assert response.status_code == 200
    assert response.json()["run"]["config_snapshot"]["timeframe"] == timeframe


def test_backtest_rejects_stablecoin_symbol() -> None:
    client = _client()
    response = client.post(
        "/api/v1/backtests/run",
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
        json={
            "template": "rsi_mean_reversion",
            "asset_class": "equity",
            "symbols": ["AAPL"],
            "parameters": {"rsi_length": 21},
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "unsupported_parameters"


def test_backtest_rejects_lookback_over_three_years() -> None:
    client = _client()
    response = client.post(
        "/api/v1/backtests/run",
        json={
            "template": "dca_accumulation",
            "asset_class": "equity",
            "symbols": ["AAPL"],
            "start_date": "2020-01-01",
            "end_date": "2024-01-10",
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_lookback_window"


def test_backtest_rejects_unknown_symbol() -> None:
    client = _client()
    response = client.post(
        "/api/v1/backtests/run",
        json={
            "template": "dca_accumulation",
            "asset_class": "equity",
            "symbols": ["FAKE123"],
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_symbol"


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


def test_chat_stream_with_es_419_emits_spanish_assistant_copy() -> None:
    client = _client()
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
    assert "event: token" in response.text

    messages = client.get(f"/api/v1/conversations/{conversation['id']}/messages")
    assert messages.status_code == 200
    assistant_message = messages.json()["items"][-1]
    assert assistant_message["role"] == "assistant"
    assert "Probé la idea con TSLA." in assistant_message["content"]


def test_chat_stream_defaults_to_english_assistant_copy() -> None:
    client = _client()
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
    assert "event: token" in response.text

    messages = client.get(f"/api/v1/conversations/{conversation['id']}/messages")
    assert messages.status_code == 200
    assistant_message = messages.json()["items"][-1]
    assert assistant_message["role"] == "assistant"
    assert "I tested that idea with TSLA." in assistant_message["content"]
