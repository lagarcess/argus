from __future__ import annotations

import json
from datetime import date
from typing import Any

import pandas as pd
import pytest
from argus.api.main import app
from argus.domain.backtest_state_machine import BacktestParamsUpdate
from argus.domain.market_data.assets import ResolvedAsset
from argus.domain.orchestrator import ChatTurnIntent
from fastapi.testclient import TestClient


def _fake_resolve_asset(symbol: str) -> ResolvedAsset:
    up = symbol.strip().upper()
    asset_class = "crypto" if up in {"BTC", "ETH", "SOL"} else "equity"
    return ResolvedAsset(
        canonical_symbol=up,
        asset_class=asset_class,
        name=up,
        raw_symbol=up,
    )


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
    close = pd.Series(100.0 + pd.RangeIndex(len(index)).astype(float), index=index)
    return pd.DataFrame(
        {
            "open": close,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": 1000,
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
    return _fake_fetch_ohlcv(symbol, asset_class, start_date, end_date, timeframe)["close"]


@pytest.fixture(autouse=True)
def _patch_io(monkeypatch: pytest.MonkeyPatch) -> None:
    from argus.api import main as api_main
    from argus.domain import engine as domain_engine

    monkeypatch.setattr(api_main, "supabase_gateway", None)
    monkeypatch.setattr(domain_engine, "resolve_asset", _fake_resolve_asset)
    monkeypatch.setattr(domain_engine, "fetch_ohlcv", _fake_fetch_ohlcv)
    monkeypatch.setattr(domain_engine, "fetch_price_series", _fake_fetch_price_series)


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


def _stream_payloads(stream: str, event_name: str) -> list[dict[str, Any]]:
    payloads = []
    for part in stream.split("\n\n"):
        if f"event: {event_name}" not in part:
            continue
        data_line = next(line for line in part.splitlines() if line.startswith("data: "))
        payloads.append(json.loads(data_line.removeprefix("data: ")))
    return payloads


def _latest_assistant_metadata(client: TestClient, conversation_id: str) -> dict[str, Any]:
    messages = client.get(f"/api/v1/conversations/{conversation_id}/messages").json()["items"]
    assistant = messages[-1]
    assert assistant["role"] == "assistant"
    return assistant["metadata"]


def test_chat_backtest_requires_confirmation_before_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api import main as api_main

    calls: list[dict[str, Any]] = []

    def _stub_intent(message: str, **_: Any) -> ChatTurnIntent:
        lower = message.lower()
        if "rsi" in lower:
            return ChatTurnIntent(
                intent="setup",
                backtest_update=BacktestParamsUpdate(template="rsi_mean_reversion"),
            )
        if "aapl" in lower:
            return ChatTurnIntent(
                intent="setup",
                backtest_update=BacktestParamsUpdate(symbols=["AAPL"]),
            )
        if lower.strip() == "yes":
            return ChatTurnIntent(intent="confirm", confirmation_action="accept_and_run")
        return ChatTurnIntent(intent="guide")

    original_create_run = api_main.create_run_from_payload

    def _spy_create_run(payload: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
        calls.append(payload)
        return original_create_run(payload, *args, **kwargs)

    monkeypatch.setattr(api_main, "classify_chat_turn_intent", _stub_intent)
    monkeypatch.setattr(api_main, "create_run_from_payload", _spy_create_run)

    client = _client()
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]

    first = client.post(
        "/api/v1/chat/stream",
        json={"conversation_id": conversation["id"], "message": "run RSI", "language": "en"},
    )
    assert first.status_code == 200
    assert "event: result" not in first.text
    assert calls == []

    second = client.post(
        "/api/v1/chat/stream",
        json={"conversation_id": conversation["id"], "message": "use AAPL", "language": "en"},
    )
    assert second.status_code == 200
    assert "event: result" not in second.text
    assert "Run this" in second.text
    assert "Change something" in second.text
    assert "Cancel" in second.text
    assert calls == []
    assert _latest_assistant_metadata(client, conversation["id"])["conversation_mode"] == "confirm"

    third = client.post(
        "/api/v1/chat/stream",
        json={"conversation_id": conversation["id"], "message": "yes", "language": "en"},
    )
    assert third.status_code == 200
    assert "event: result" in third.text
    assert len(calls) == 1
    assert calls[0]["template"] == "rsi_mean_reversion"
    assert calls[0]["symbols"] == ["AAPL"]

    result_payload = _stream_payloads(third.text, "result")[0]
    assert result_payload["run"]["conversation_result_card"]["status_label"]
    meta = _latest_assistant_metadata(client, conversation["id"])
    assert meta["conversation_mode"] == "result_review"
    assert meta["latest_run_id"] == result_payload["run"]["id"]


def test_chat_backtest_change_mind_updates_pending_state_before_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api import main as api_main

    calls: list[dict[str, Any]] = []

    def _stub_intent(message: str, **_: Any) -> ChatTurnIntent:
        lower = message.lower()
        if "buy" in lower and "aapl" in lower:
            return ChatTurnIntent(
                intent="setup",
                backtest_update=BacktestParamsUpdate(template="buy_the_dip", symbols=["AAPL"]),
            )
        if "msft" in lower:
            return ChatTurnIntent(
                intent="setup",
                backtest_update=BacktestParamsUpdate(symbols=["MSFT"]),
            )
        if lower.strip() == "yes":
            return ChatTurnIntent(intent="confirm", confirmation_action="accept_and_run")
        return ChatTurnIntent(intent="guide")

    original_create_run = api_main.create_run_from_payload

    def _spy_create_run(payload: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
        calls.append(payload)
        return original_create_run(payload, *args, **kwargs)

    monkeypatch.setattr(api_main, "classify_chat_turn_intent", _stub_intent)
    monkeypatch.setattr(api_main, "create_run_from_payload", _spy_create_run)

    client = _client()
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]

    initial = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "buy dips on AAPL",
            "language": "en",
        },
    )
    assert initial.status_code == 200
    assert "event: result" not in initial.text

    changed = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "use MSFT instead",
            "language": "en",
        },
    )
    assert changed.status_code == 200
    assert "MSFT" in changed.text
    assert "AAPL" not in changed.text
    assert calls == []

    confirmed = client.post(
        "/api/v1/chat/stream",
        json={"conversation_id": conversation["id"], "message": "yes", "language": "en"},
    )
    assert confirmed.status_code == 200
    assert "event: result" in confirmed.text
    assert len(calls) == 1
    assert calls[0]["symbols"] == ["MSFT"]


def test_hey_returns_guide_and_does_not_create_backtest_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api import main as api_main

    def _guide(**_: Any) -> ChatTurnIntent:
        return ChatTurnIntent(intent="guide")

    monkeypatch.setattr(api_main, "classify_chat_turn_intent", _guide)

    client = _client()
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]

    response = client.post(
        "/api/v1/chat/stream",
        json={"conversation_id": conversation["id"], "message": "hey", "language": "en"},
    )

    assert response.status_code == 200
    assert "Orchestration failed" not in response.text
    assert "event: result" not in response.text
    assert "I can help you learn" in response.text
    assert "test a strategy" in response.text

    metadata = _latest_assistant_metadata(client, conversation["id"])
    assert metadata.get("backtest_state") is None
    assert metadata["conversation_mode"] == "guide"


def test_education_chat_does_not_create_backtest_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api import main as api_main

    def _education(**_: Any) -> ChatTurnIntent:
        return ChatTurnIntent(
            intent="guide",
            educational_need="concept_explanation",
            assistant_guidance_seed="momentum",
        )

    monkeypatch.setattr(api_main, "classify_chat_turn_intent", _education)

    client = _client()
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "How does momentum trading work?",
            "language": "en",
        },
    )

    assert response.status_code == 200
    assert "event: result" not in response.text
    assert "Momentum looks for strength" in response.text

    metadata = _latest_assistant_metadata(client, conversation["id"])
    assert metadata.get("backtest_state") is None
    assert metadata["conversation_mode"] == "guide"


def test_confused_beginner_gets_guided_prompt_without_backtest_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api import main as api_main

    def _beginner(**_: Any) -> ChatTurnIntent:
        return ChatTurnIntent(
            intent="guide",
            educational_need="beginner_confused",
            assistant_guidance_seed="new investor confused",
        )

    monkeypatch.setattr(api_main, "classify_chat_turn_intent", _beginner)

    client = _client()
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "you tell me, i dont know anything about this",
            "language": "en",
        },
    )

    assert response.status_code == 200
    assert "event: result" not in response.text
    assert "No problem. Let's find a simple idea to test." in response.text
    assert "A specific stock" in response.text

    messages = client.get(f"/api/v1/conversations/{conversation['id']}/messages").json()["items"]
    assistant = messages[-1]
    assert assistant["metadata"].get("backtest_state") is None


def test_beginner_choice_narrows_guide_without_backtest_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api import main as api_main

    def _choice(**_: Any) -> ChatTurnIntent:
        return ChatTurnIntent(
            intent="guide",
            educational_need="beginner_confused",
            guide_choice="compare_stocks",
        )

    monkeypatch.setattr(api_main, "classify_chat_turn_intent", _choice)

    client = _client()
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]

    response = client.post(
        "/api/v1/chat/stream",
        json={"conversation_id": conversation["id"], "message": "2", "language": "en"},
    )

    assert response.status_code == 200
    assert "event: result" not in response.text
    assert "compare two familiar tech stocks" in response.text
    assert "AAPL vs MSFT" in response.text

    messages = client.get(f"/api/v1/conversations/{conversation['id']}/messages").json()["items"]
    assistant = messages[-1]
    assert assistant["metadata"].get("backtest_state") is None


def test_concrete_symbol_from_single_pass_intent_starts_state_machine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api import main as api_main

    def _symbol(**_: Any) -> ChatTurnIntent:
        return ChatTurnIntent(
            intent="setup",
            backtest_update=BacktestParamsUpdate(symbols=["AAPL"]),
        )

    monkeypatch.setattr(api_main, "classify_chat_turn_intent", _symbol)

    client = _client()
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]

    response = client.post(
        "/api/v1/chat/stream",
        json={"conversation_id": conversation["id"], "message": "AAPL", "language": "en"},
    )

    assert response.status_code == 200
    assert "event: result" not in response.text
    assert "What strategy do you want to test?" in response.text

    metadata = _latest_assistant_metadata(client, conversation["id"])
    assert metadata.get("backtest_state") is not None
    assert metadata["conversation_mode"] == "setup"


def test_can_i_test_strategy_returns_beginner_safe_choices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api import main as api_main

    def _guide(**_: Any) -> ChatTurnIntent:
        return ChatTurnIntent(intent="guide", educational_need="strategy_help")

    monkeypatch.setattr(api_main, "classify_chat_turn_intent", _guide)

    client = _client()
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "can i test a strategy?",
            "language": "en",
        },
    )

    assert response.status_code == 200
    assert "event: result" not in response.text
    assert "Yes" in response.text
    assert "buy and hold" in response.text
    assert "buy the dip" in response.text


def test_chat_stream_passes_agent_model_to_intent_classifier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api import main as api_main

    seen: dict[str, Any] = {}

    def _guide(**kwargs: Any) -> ChatTurnIntent:
        seen.update(kwargs)
        return ChatTurnIntent(intent="guide")

    monkeypatch.setenv("AGENT_MODEL", "openrouter/test-intent-model")
    monkeypatch.setattr(api_main, "classify_chat_turn_intent", _guide)

    client = _client()
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]

    response = client.post(
        "/api/v1/chat/stream",
        json={"conversation_id": conversation["id"], "message": "hola", "language": "es-419"},
    )

    assert response.status_code == 200
    assert seen["model_name"] == "openrouter/test-intent-model"


def test_confirm_edit_and_cancel_paths_do_not_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api import main as api_main

    calls: list[dict[str, Any]] = []
    action = "edit_parameters"

    def _stub_intent(message: str, **_: Any) -> ChatTurnIntent:
        if "buy" in message.lower():
            return ChatTurnIntent(
                intent="setup",
                backtest_update=BacktestParamsUpdate(template="buy_the_dip", symbols=["AAPL"]),
            )
        return ChatTurnIntent(intent="confirm", confirmation_action=action)

    def _spy_create_run(payload: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
        calls.append(payload)
        return api_main.create_run_from_payload(payload, *args, **kwargs)

    monkeypatch.setattr(api_main, "classify_chat_turn_intent", _stub_intent)
    monkeypatch.setattr(api_main, "create_run_from_payload", _spy_create_run)

    client = _client()
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]

    ready = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "buy dips on AAPL",
            "language": "en",
        },
    )
    assert ready.status_code == 200
    assert "Run this" in ready.text

    edit = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "change something",
            "language": "en",
        },
    )
    assert edit.status_code == 200
    assert "event: result" not in edit.text
    assert "What would you like to change?" in edit.text
    assert calls == []
    assert _latest_assistant_metadata(client, conversation["id"])["conversation_mode"] == "setup"

    action = "cancel_backtest"
    cancel = client.post(
        "/api/v1/chat/stream",
        json={"conversation_id": conversation["id"], "message": "cancel", "language": "en"},
    )
    assert cancel.status_code == 200
    assert "event: result" not in cancel.text
    assert "cancelled" in cancel.text.lower()
    metadata = _latest_assistant_metadata(client, conversation["id"])
    assert metadata["conversation_mode"] == "guide"
    assert metadata.get("backtest_state") is None
    assert calls == []


def test_result_review_explains_metrics_without_rerunning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api import main as api_main

    calls: list[dict[str, Any]] = []
    phase = "run"

    def _stub_intent(message: str, **_: Any) -> ChatTurnIntent:
        if phase == "explain":
            return ChatTurnIntent(
                intent="explain_result",
                result_action="explain_metrics",
                educational_need="metric_explanation",
            )
        if message.lower().strip() == "yes":
            return ChatTurnIntent(intent="confirm", confirmation_action="accept_and_run")
        return ChatTurnIntent(
            intent="setup",
            backtest_update=BacktestParamsUpdate(template="buy_the_dip", symbols=["AAPL"]),
        )

    original_create_run = api_main.create_run_from_payload

    def _spy_create_run(payload: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
        calls.append(payload)
        return original_create_run(payload, *args, **kwargs)

    monkeypatch.setattr(api_main, "classify_chat_turn_intent", _stub_intent)
    monkeypatch.setattr(api_main, "create_run_from_payload", _spy_create_run)

    client = _client()
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]

    client.post(
        "/api/v1/chat/stream",
        json={"conversation_id": conversation["id"], "message": "buy dips on AAPL", "language": "en"},
    )
    run_response = client.post(
        "/api/v1/chat/stream",
        json={"conversation_id": conversation["id"], "message": "yes", "language": "en"},
    )
    assert "event: result" in run_response.text
    assert len(calls) == 1

    phase = "explain"
    explain = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "what does drawdown mean?",
            "language": "en",
        },
    )

    assert explain.status_code == 200
    assert "event: result" not in explain.text
    assert "drawdown" in explain.text.lower()
    assert len(calls) == 1
    assert _latest_assistant_metadata(client, conversation["id"])["conversation_mode"] == "result_review"


def test_result_refine_and_save_actions_do_not_rerun(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api import main as api_main

    calls: list[dict[str, Any]] = []
    phase = "run"

    def _stub_intent(message: str, **_: Any) -> ChatTurnIntent:
        if phase == "save":
            return ChatTurnIntent(intent="refine", result_action="save_or_organize")
        if phase == "refine":
            return ChatTurnIntent(
                intent="refine",
                result_action="compare_or_refine",
                backtest_update=BacktestParamsUpdate(symbols=["MSFT"]),
            )
        if message.lower().strip() == "yes":
            return ChatTurnIntent(intent="confirm", confirmation_action="accept_and_run")
        return ChatTurnIntent(
            intent="setup",
            backtest_update=BacktestParamsUpdate(template="buy_the_dip", symbols=["AAPL"]),
        )

    original_create_run = api_main.create_run_from_payload

    def _spy_create_run(payload: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
        calls.append(payload)
        return original_create_run(payload, *args, **kwargs)

    monkeypatch.setattr(api_main, "classify_chat_turn_intent", _stub_intent)
    monkeypatch.setattr(api_main, "create_run_from_payload", _spy_create_run)

    client = _client()
    conversation = client.post("/api/v1/conversations", json={}).json()["conversation"]

    client.post(
        "/api/v1/chat/stream",
        json={"conversation_id": conversation["id"], "message": "buy dips on AAPL", "language": "en"},
    )
    client.post(
        "/api/v1/chat/stream",
        json={"conversation_id": conversation["id"], "message": "yes", "language": "en"},
    )
    assert len(calls) == 1

    phase = "refine"
    refine = client.post(
        "/api/v1/chat/stream",
        json={"conversation_id": conversation["id"], "message": "try MSFT too", "language": "en"},
    )
    assert refine.status_code == 200
    assert "event: result" not in refine.text
    assert "MSFT" in refine.text
    assert len(calls) == 1
    assert _latest_assistant_metadata(client, conversation["id"])["conversation_mode"] == "confirm"

    phase = "save"
    save = client.post(
        "/api/v1/chat/stream",
        json={"conversation_id": conversation["id"], "message": "save this", "language": "en"},
    )
    assert save.status_code == 200
    assert "event: result" not in save.text
    assert "save" in save.text.lower()
    assert len(calls) == 1
