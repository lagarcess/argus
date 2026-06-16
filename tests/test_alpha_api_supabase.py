import json
from datetime import date
from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from argus.api.main import app
from argus.api.schemas import BacktestRun, Conversation, Message, OnboardingState, User
from argus.domain.market_data.assets import ResolvedAsset
from argus.domain.store import utcnow
from argus.domain.supabase_gateway import QuotaExceededError, SupabaseGateway
from fastapi.testclient import TestClient

client = TestClient(app)


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


def _mock_profile(*, language: str = "en", stage: str = "ready") -> User:
    now = utcnow()
    return User(
        id="00000000-0000-0000-0000-000000000001",
        email="developer@argus.local",
        username="mock-developer",
        display_name="Mock Developer",
        language=language,  # type: ignore[arg-type]
        locale="es-419" if language == "es-419" else "en-US",
        theme="dark",
        is_admin=True,
        onboarding=OnboardingState(
            completed=stage == "completed",
            stage=stage,  # type: ignore[arg-type]
            language_confirmed=True,
            primary_goal="test_stock_idea" if stage != "language_selection" else None,
        ),
        created_at=now,
        updated_at=now,
    )


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
    if compact in {"BTC", "ETH", "USDT", "USDC"}:
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


def test_gateway_auth_flows_use_separate_auth_client():
    service_client = MagicMock()
    auth_client = MagicMock()

    signup_response = MagicMock()
    signup_response.user = object()
    signup_response.model_dump.return_value = {"user": {"id": "auth-user"}}
    auth_client.auth.sign_up.return_value = signup_response

    login_response = MagicMock()
    login_response.session = object()
    login_response.model_dump.return_value = {"session": {"access_token": "token"}}
    auth_client.auth.sign_in_with_password.return_value = login_response

    gateway = SupabaseGateway(client=service_client, auth_client=auth_client)

    assert gateway.signup(email="alpha@example.com", password="password") == {
        "user": {"id": "auth-user"}
    }
    assert gateway.login(email="alpha@example.com", password="password") == {
        "session": {"access_token": "token"}
    }

    auth_client.auth.sign_up.assert_called_once()
    auth_client.auth.sign_in_with_password.assert_called_once()
    service_client.auth.sign_up.assert_not_called()
    service_client.auth.sign_in_with_password.assert_not_called()


def test_gateway_private_alpha_role_reads_active_allowlist_row():
    client_mock = MagicMock()
    query = MagicMock()
    query.select.return_value = query
    query.eq.return_value = query
    query.limit.return_value = query
    query.execute.return_value.data = [
        {"email": "lagarces1@gmail.com", "role": "admin", "disabled_at": None}
    ]
    client_mock.table.return_value = query

    gateway = SupabaseGateway(client=client_mock)

    assert gateway.private_alpha_role_for_email(" LAGARCES1@gmail.com ") == "admin"
    assert gateway.private_alpha_email_allowed("LAGARCES1@gmail.com") is True
    client_mock.table.assert_called_with("private_alpha_allowlist")


def test_gateway_private_alpha_role_ignores_disabled_allowlist_row():
    client_mock = MagicMock()
    query = MagicMock()
    query.select.return_value = query
    query.eq.return_value = query
    query.limit.return_value = query
    query.execute.return_value.data = [
        {
            "email": "disabled@example.com",
            "role": "user",
            "disabled_at": "2026-05-30T00:00:00Z",
        }
    ]
    client_mock.table.return_value = query

    gateway = SupabaseGateway(client=client_mock)

    assert gateway.private_alpha_role_for_email("disabled@example.com") is None
    assert gateway.private_alpha_email_allowed("disabled@example.com") is False


def _runtime_success_result(
    *,
    symbol: str = "TSLA",
    timeframe: str = "1D",
    language: str = "en",
) -> dict[str, Any]:
    return {
        "stage_outcome": "ready_to_respond",
        "assistant_response": (
            "Probé la idea con TSLA."
            if language.lower().startswith("es")
            else f"I tested that idea with {symbol}."
        ),
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
    language = str(getattr(kwargs.get("user"), "language_preference", "en"))
    return _runtime_success_result(language=language)


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
    from argus.api.routers import agent as agent_router
    from argus.domain import engine as domain_engine

    monkeypatch.setattr(
        api_main,
        "".join(["orchestrate_chat", "_turn"]),
        lambda **kwargs: (
            dict(
                intent="onboarding_prompt",
                assistant_message=(
                    "What is your current primary goal? Don't worry, "
                    "you can change it later in Settings."
                ),
                strategy_draft=None,
                title_suggestion=None,
            )
            if kwargs.get("onboarding_required")
            else dict(
                intent="run_backtest",
                assistant_message=(
                    "Probé la idea con TSLA."
                    if str(kwargs.get("language")).lower().startswith("es")
                    else "I tested that idea with TSLA."
                ),
                strategy_draft=dict(
                    template=dict(value="rsi_mean_reversion", source="user_supplied"),
                    symbols=dict(value=["TSLA"], source="user_supplied"),
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


@pytest.fixture
def mock_gateway():
    gateway = MagicMock(spec=SupabaseGateway)
    gateway.get_user.return_value = _mock_profile()
    gateway.get_or_create_mock_user.return_value = _mock_profile()
    gateway.get_auth_user_from_token.return_value = {
        "id": "00000000-0000-0000-0000-000000000001",
        "email": "developer@argus.local",
    }
    gateway.private_alpha_email_allowed.return_value = True
    gateway.count_completed_runs.return_value = 1
    gateway.list_messages.return_value = []
    with patch("argus.api.state.supabase_gateway", gateway):
        yield gateway


def test_run_backtest_quota_exceeded(mock_gateway):
    mock_gateway.check_and_increment_usage.side_effect = QuotaExceededError(
        "Quota exceeded for backtest_runs (day)"
    )

    response = client.post(
        "/api/v1/backtests/run",
        json={"symbols": ["AAPL"]},
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 429
    data = response.json()
    assert data["code"] == "too_many_requests"
    assert "Quota exceeded for backtest_runs" in data["detail"]
    assert response.headers.get("Retry-After") == "60"


def test_chat_stream_quota_exceeded(mock_gateway):
    mock_gateway.check_and_increment_usage.side_effect = QuotaExceededError(
        "Quota exceeded for chat_messages (day)"
    )

    response = client.post(
        "/api/v1/chat/stream",
        json={"conversation_id": "test-conv", "message": "hello"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 429
    data = response.json()
    assert data["code"] == "too_many_requests"
    assert "Quota exceeded for chat_messages" in data["detail"]
    assert response.headers.get("Retry-After") == "60"


def test_chat_stream_checks_daily_and_hourly_quotas(mock_gateway):
    now = utcnow()
    conversation = Conversation(
        id="conv-1",
        title="New conversation",
        title_source="system_default",
        language="en",
        pinned=False,
        archived=False,
        last_message_preview=None,
        deleted_at=None,
        created_at=now,
        updated_at=now,
    )
    mock_gateway.get_conversation.return_value = conversation
    mock_gateway.create_backtest_run.side_effect = lambda *, user_id, run: run
    mock_gateway.create_message.side_effect = lambda **kwargs: Message(
        id="msg-1",
        conversation_id=kwargs["conversation_id"],
        role=kwargs["role"],  # type: ignore[arg-type]
        content=kwargs["content"],
        created_at=utcnow(),
    )

    response = client.post(
        "/api/v1/chat/stream",
        json={"conversation_id": "conv-1", "message": "Test TSLA dip idea"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    quota_calls = [
        call.kwargs for call in mock_gateway.check_and_increment_usage.call_args_list
    ]
    assert {
        "user_id": "00000000-0000-0000-0000-000000000001",
        "resource": "chat_messages",
        "period": "day",
        "limit_count": 200,
    } in quota_calls
    assert {
        "user_id": "00000000-0000-0000-0000-000000000001",
        "resource": "chat_messages",
        "period": "hour",
        "limit_count": 60,
    } in quota_calls


def test_successful_api_response_omits_static_rate_limit_headers(mock_gateway):
    response = client.get("/api/v1/me", headers={"Authorization": "Bearer test-token"})

    assert response.status_code == 200
    assert "X-RateLimit-Limit" not in response.headers
    assert "X-RateLimit-Remaining" not in response.headers
    assert "X-RateLimit-Reset" not in response.headers


def test_me_reads_profile_from_supabase_gateway(mock_gateway):
    profile = _mock_profile(language="es-419")
    mock_gateway.get_user.return_value = profile

    response = client.get("/api/v1/me", headers={"Authorization": "Bearer test-token"})

    assert response.status_code == 200
    assert response.json()["user"]["language"] == "es-419"
    assert mock_gateway.get_user.call_count >= 1


def test_patch_me_supabase_merges_onboarding_and_persists(mock_gateway):
    before = _mock_profile(stage="language_selection")
    mock_gateway.get_user.return_value = before

    def _updated_user(_user_id: str, payload: dict) -> User:
        return User.model_validate(payload)

    mock_gateway.update_user.side_effect = _updated_user

    response = client.patch(
        "/api/v1/me",
        json={"onboarding": {"language_confirmed": True}},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    onboarding = response.json()["user"]["onboarding"]
    assert onboarding["stage"] == "language_selection"
    assert onboarding["language_confirmed"] is True
    assert onboarding["primary_goal"] is None
    mock_gateway.update_user.assert_called_once()


def test_feedback_accepts_account_deletion_request_and_enriches_context(mock_gateway):
    response = client.post(
        "/api/v1/feedback",
        json={
            "type": "account_deletion_request",
            "message": "Private alpha account deletion requested.",
            "context": {"source": "profile_modal"},
        },
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload == {"success": True}
    mock_gateway.create_feedback.assert_called_once()
    call = mock_gateway.create_feedback.call_args.kwargs
    assert call["feedback_type"] == "account_deletion_request"
    assert call["user_id"] == "00000000-0000-0000-0000-000000000001"
    assert call["message"] == "Private alpha account deletion requested."
    context = call["context"]
    assert context["source"] == "profile_modal"
    assert context["account_email"] == "developer@argus.local"
    assert context["profile_language"] == "en"
    assert context["request_user_id"] == "00000000-0000-0000-0000-000000000001"
    assert isinstance(context["requested_at"], str)


def test_create_conversation_uses_dev_memory_fallback_when_supabase_fails(
    mock_gateway,
    monkeypatch,
):
    mock_gateway.create_conversation.side_effect = RuntimeError("supabase unavailable")
    monkeypatch.setenv("ARGUS_DEV_MEMORY_FALLBACK", "true")

    response = client.post(
        "/api/v1/conversations",
        json={"language": "en"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    conversation = response.json()["conversation"]
    assert conversation["title"] == "New idea"
    assert conversation["title_source"] == "system_default"


def test_deleted_conversation_messages_supabase_return_not_found(mock_gateway):
    now = utcnow()
    mock_gateway.get_conversation.return_value = Conversation(
        id="deleted-conversation",
        title="Deleted idea",
        title_source="system_default",
        language="en",
        pinned=False,
        archived=False,
        last_message_preview="Old turn",
        deleted_at=now,
        created_at=now,
        updated_at=now,
    )

    response = client.get(
        "/api/v1/conversations/deleted-conversation/messages",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
    mock_gateway.list_messages.assert_not_called()


def test_delete_all_conversations_supabase_delegates_with_user_ownership(
    mock_gateway,
):
    mock_gateway.soft_delete_all_conversations.return_value = 3

    response = client.delete(
        "/api/v1/conversations",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.json() == {"success": True, "deleted_count": 3}
    mock_gateway.soft_delete_all_conversations.assert_called_once_with(
        user_id="00000000-0000-0000-0000-000000000001"
    )


def test_run_backtest_supabase_persists_normalized_snapshot_and_assumptions(mock_gateway):
    mock_gateway.create_backtest_run.side_effect = lambda *, user_id, run: run

    response = client.post(
        "/api/v1/backtests/run",
        json={"template": "rsi_mean_reversion", "symbols": ["TSLA"]},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    run = response.json()["run"]
    assert run["config_snapshot"]["side"] == "long"
    assert run["config_snapshot"]["starting_capital"] == 1000
    assert run["config_snapshot"]["benchmark_symbol"] == "SPY"
    assert "_execution_realism" not in run["config_snapshot"]
    assert run["conversation_result_card"]["assumptions"][-1] == "Benchmark: SPY"
    assert run["conversation_result_card"]["benchmark_note"] is None
    mock_gateway.create_backtest_run.assert_called_once()
    called_run = mock_gateway.create_backtest_run.call_args.kwargs["run"]
    assert isinstance(called_run, BacktestRun)
    assert called_run.config_snapshot["starting_capital"] == 1000


def test_run_backtest_rejects_unowned_parent_conversation(mock_gateway):
    mock_gateway.get_conversation.return_value = None

    response = client.post(
        "/api/v1/backtests/run",
        json={
            "conversation_id": "conversation-other",
            "template": "rsi_mean_reversion",
            "symbols": ["AAPL"],
        },
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
    mock_gateway.create_backtest_run.assert_not_called()
    mock_gateway.get_conversation.assert_called_once_with(
        user_id="00000000-0000-0000-0000-000000000001",
        conversation_id="conversation-other",
    )


def test_create_strategy_rejects_unowned_parent_conversation(mock_gateway):
    mock_gateway.get_conversation.return_value = None

    response = client.post(
        "/api/v1/strategies",
        json={
            "name": "Apple hold",
            "template": "buy_and_hold",
            "asset_class": "equity",
            "symbols": ["AAPL"],
            "parameters": {},
            "conversation_id": "conversation-other",
        },
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
    mock_gateway.create_strategy.assert_not_called()
    mock_gateway.get_conversation.assert_called_once_with(
        user_id="00000000-0000-0000-0000-000000000001",
        conversation_id="conversation-other",
    )


def test_get_backtest_supabase_reads_from_gateway(mock_gateway):
    mock_gateway.create_backtest_run.side_effect = lambda *, user_id, run: run
    create = client.post(
        "/api/v1/backtests/run",
        json={"template": "rsi_mean_reversion", "symbols": ["AAPL"]},
        headers={"Authorization": "Bearer test-token"},
    )
    assert create.status_code == 200
    created_run = create.json()["run"]
    mock_gateway.get_backtest_run.return_value = BacktestRun.model_validate(created_run)

    response = client.get(
        f"/api/v1/backtests/{created_run['id']}",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    mock_gateway.get_backtest_run.assert_called_once()
    assert response.json()["run"]["id"] == created_run["id"]


def test_chat_stream_supabase_persists_backtest_run(mock_gateway):
    now = utcnow()
    conversation = Conversation(
        id="conv-1",
        title="New conversation",
        title_source="system_default",
        language="en",
        pinned=False,
        archived=False,
        last_message_preview=None,
        deleted_at=None,
        created_at=now,
        updated_at=now,
    )
    mock_gateway.get_conversation.return_value = conversation
    mock_gateway.create_backtest_run.side_effect = lambda *, user_id, run: run
    mock_gateway.create_message.side_effect = lambda **kwargs: Message(
        id="msg-1",
        conversation_id=kwargs["conversation_id"],
        role=kwargs["role"],  # type: ignore[arg-type]
        content=kwargs["content"],
        created_at=utcnow(),
    )

    response = client.post(
        "/api/v1/chat/stream",
        json={"conversation_id": "conv-1", "message": "Test TSLA dip idea"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert "event:" not in response.text
    assert response.text.count("data: [DONE]") == 1
    mock_gateway.create_backtest_run.assert_called_once()
    persisted_run = mock_gateway.create_backtest_run.call_args.kwargs["run"]
    final_payload = _final_payload(response.text)
    assert final_payload["message_id"] == "msg-1"
    assert final_payload["run"]["id"] == persisted_run.id
    assert final_payload["run"]["conversation_result_card"]["title"] == (
        "TSLA RSI Mean Reversion"
    )


def test_chat_stream_supabase_rejects_memory_only_conversation(mock_gateway):
    from argus.api import state as api_state

    now = utcnow()
    memory_only_conversation = Conversation(
        id="memory-only-conversation",
        title="Memory only",
        title_source="system_default",
        language="en",
        pinned=False,
        archived=False,
        last_message_preview=None,
        deleted_at=None,
        created_at=now,
        updated_at=now,
    )
    api_state.store.conversations[memory_only_conversation.id] = (
        memory_only_conversation
    )
    api_state.store.messages[memory_only_conversation.id] = []
    mock_gateway.get_conversation.return_value = None

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": memory_only_conversation.id,
            "message": "Test TSLA dip idea",
        },
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404
    mock_gateway.get_conversation.assert_called_with(
        user_id="00000000-0000-0000-0000-000000000001",
        conversation_id=memory_only_conversation.id,
    )
    mock_gateway.create_message.assert_not_called()


def test_chat_stream_supabase_prompts_onboarding_before_running_backtest(mock_gateway):
    now = utcnow()
    conversation = Conversation(
        id="conv-2",
        title="New conversation",
        title_source="system_default",
        language="en",
        pinned=False,
        archived=False,
        last_message_preview=None,
        deleted_at=None,
        created_at=now,
        updated_at=now,
    )
    mock_gateway.get_conversation.return_value = conversation
    mock_gateway.get_user.return_value = _mock_profile(stage="language_selection")
    mock_gateway.count_completed_runs.return_value = 0
    mock_gateway.create_message.side_effect = lambda **kwargs: Message(
        id="msg-2",
        conversation_id=kwargs["conversation_id"],
        role=kwargs["role"],  # type: ignore[arg-type]
        content=kwargs["content"],
        created_at=utcnow(),
    )

    response = client.post(
        "/api/v1/chat/stream",
        json={"conversation_id": "conv-2", "message": "Test TSLA dip idea"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert "event:" not in response.text
    assert response.text.count("data: [DONE]") == 1
    events = _stream_events(response.text)
    token_events = [event for event in events if event.get("type") == "token"]
    assert len(token_events) == 1
    assert "primary goal" in token_events[0]["content"]
    final_payload = _final_payload(response.text)
    assert final_payload == {
        "stage_outcome": "await_user_reply",
        "assistant_response": token_events[0]["content"],
        "message_id": "msg-2",
    }
    mock_gateway.create_backtest_run.assert_not_called()


def test_chat_stream_supabase_does_not_persist_hidden_onboarding_messages(mock_gateway):
    now = utcnow()
    conversation = Conversation(
        id="conv-3",
        title="New conversation",
        title_source="system_default",
        language="en",
        pinned=False,
        archived=False,
        last_message_preview=None,
        deleted_at=None,
        created_at=now,
        updated_at=now,
    )
    mock_gateway.get_conversation.return_value = conversation
    mock_gateway.get_user.return_value = _mock_profile(stage="language_selection")
    mock_gateway.count_completed_runs.return_value = 0
    mock_gateway.create_message.side_effect = lambda **kwargs: Message(
        id="msg-3",
        conversation_id=kwargs["conversation_id"],
        role=kwargs["role"],  # type: ignore[arg-type]
        content=kwargs["content"],
        created_at=utcnow(),
    )

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": "conv-3",
            "message": "__ONBOARDING_GOAL__:test_stock_idea",
        },
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    roles = [call.kwargs["role"] for call in mock_gateway.create_message.call_args_list]
    assert "user" not in roles


def test_unauthorized_missing_token(mock_gateway):
    import os

    os.environ["NEXT_PUBLIC_MOCK_AUTH"] = "false"
    os.environ["ARGUS_MOCK_AUTH"] = "false"

    response = client.get("/api/v1/me")
    assert response.status_code == 401


def test_unauthorized_invalid_token(mock_gateway):
    import os

    os.environ["NEXT_PUBLIC_MOCK_AUTH"] = "false"
    os.environ["ARGUS_MOCK_AUTH"] = "false"
    mock_gateway.get_auth_user_from_token.side_effect = Exception("Invalid token")

    response = client.get("/api/v1/me", headers={"Authorization": "Bearer invalid-token"})
    assert response.status_code == 401


def test_profile_creation_on_first_login(mock_gateway):
    import os

    os.environ["NEXT_PUBLIC_MOCK_AUTH"] = "false"
    os.environ["ARGUS_MOCK_AUTH"] = "false"
    mock_gateway.get_auth_user_from_token.return_value = {
        "id": "00000000-0000-0000-0000-000000000001",
        "email": "developer@argus.local",
    }
    mock_gateway.private_alpha_email_allowed.return_value = True

    # simulate user not found initially
    mock_gateway.get_user.return_value = None
    mock_gateway.get_or_create_profile_for_auth_user.return_value = _mock_profile(
        stage="language_selection"
    )

    response = client.get("/api/v1/me", headers={"Authorization": "Bearer valid-token"})
    assert response.status_code == 200
    mock_gateway.private_alpha_email_allowed.assert_called_once_with(
        "developer@argus.local"
    )
    mock_gateway.get_or_create_profile_for_auth_user.assert_called_once()


def test_authenticated_request_blocks_private_alpha_email_without_access(mock_gateway):
    import os

    os.environ["NEXT_PUBLIC_MOCK_AUTH"] = "false"
    os.environ["ARGUS_MOCK_AUTH"] = "false"
    mock_gateway.get_auth_user_from_token.return_value = {
        "id": "user-1",
        "email": "disabled@example.com",
    }
    mock_gateway.private_alpha_email_allowed.return_value = False

    response = client.get("/api/v1/me", headers={"Authorization": "Bearer valid-token"})

    assert response.status_code == 403
    assert response.json()["code"] == "private_alpha_access_required"
    mock_gateway.private_alpha_email_allowed.assert_called_once_with(
        "disabled@example.com"
    )
    mock_gateway.get_or_create_profile_for_auth_user.assert_not_called()


def test_login_sets_session_cookie_for_browser_auth(mock_gateway):
    import os

    email = os.environ.get("MOCK_USER_EMAIL", "developer@argus.local")
    password = os.environ.get("MOCK_USER_PASSWORD", "password")
    mock_gateway.private_alpha_email_allowed.return_value = True
    mock_gateway.login.return_value = {
        "session": {
            "access_token": "access-token-123",
            "refresh_token": "refresh-token-123",
            "expires_in": 3600,
        },
        "user": {"id": "user-1", "email": email},
    }

    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )

    assert response.status_code == 200
    mock_gateway.private_alpha_email_allowed.assert_called_once_with(email)
    assert "mark_private_alpha_login" not in [
        call[0] for call in mock_gateway.method_calls
    ]
    assert response.cookies.get("sb-auth-token") == "access-token-123"
    assert response.cookies.get("sb-refresh-token") == "refresh-token-123"


def test_login_forces_secure_session_cookies_in_production(
    mock_gateway, monkeypatch
):
    monkeypatch.setenv("APP_ENV", "production")
    mock_gateway.private_alpha_email_allowed.return_value = True
    mock_gateway.login.return_value = {
        "session": {
            "access_token": "access-token-123",
            "refresh_token": "refresh-token-123",
            "expires_in": 3600,
        },
        "user": {"id": "user-1", "email": "beta@example.com"},
    }

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "beta@example.com", "password": "password123"},
    )

    assert response.status_code == 200
    set_cookie = response.headers.get("set-cookie", "").lower()
    assert "sb-auth-token" in set_cookie
    assert "sb-refresh-token" in set_cookie
    assert "secure" in set_cookie


def test_feedback_submission_persists_with_user_ownership(mock_gateway):
    profile = _mock_profile()
    mock_gateway.get_or_create_mock_user.return_value = profile

    response = client.post(
        "/api/v1/feedback",
        json={
            "type": "general",
            "message": "The private alpha flow feels clear.",
            "context": {"surface": "settings", "metadata": {"path": "/chat"}},
        },
    )

    assert response.status_code == 200
    assert response.json() == {"success": True}
    assert {
        "user_id": profile.id,
        "resource": "feedback",
        "period": "day",
        "limit_count": 50,
    } in [call.kwargs for call in mock_gateway.check_and_increment_usage.call_args_list]
    assert {
        "user_id": profile.id,
        "resource": "feedback",
        "period": "hour",
        "limit_count": 20,
    } in [call.kwargs for call in mock_gateway.check_and_increment_usage.call_args_list]
    mock_gateway.create_feedback.assert_called_once_with(
        user_id=profile.id,
        feedback_type="general",
        message="The private alpha flow feels clear.",
        context={"surface": "settings", "page_path": "/chat"},
    )


def test_feedback_submission_sanitizes_browser_context(mock_gateway):
    profile = _mock_profile()
    mock_gateway.get_or_create_mock_user.return_value = profile

    response = client.post(
        "/api/v1/feedback",
        json={
            "type": "bug",
            "message": "The result card copy action felt broken.",
            "context": {
                "source": "message_more_menu",
                "surface": "chat",
                "message_id": "msg-1",
                "conversation_id": "conv-1",
                "artifact_type": "result_card",
                "url": (
                    "https://argus.example/chat?conversation=conv-1&auth=secret"
                    "#private"
                ),
                "timestamp": "2026-06-15T08:00:00.000Z",
                "rating": "negative",
                "tags": ["incorrect", "slow"],
                "hasAttachments": False,
                "attachmentCount": 0,
                "metadata": {"path": "/chat?conversation=conv-1", "token": "secret"},
                "raw_prompt": "buy AAPL with my personal note",
                "email": "person@example.com",
            },
        },
    )

    assert response.status_code == 200
    context = mock_gateway.create_feedback.call_args.kwargs["context"]
    assert context == {
        "source": "message_more_menu",
        "surface": "chat",
        "message_id": "msg-1",
        "conversation_id": "conv-1",
        "artifact_type": "result_card",
        "page_path": "/chat",
        "timestamp": "2026-06-15T08:00:00.000Z",
        "rating": "negative",
        "tags": ["incorrect", "slow"],
        "has_attachments": False,
        "attachment_count": 0,
    }


def test_feedback_rejects_oversized_message(mock_gateway):
    response = client.post(
        "/api/v1/feedback",
        json={
            "type": "general",
            "message": "x" * 5001,
            "context": {"surface": "settings"},
        },
    )

    assert response.status_code == 422
    mock_gateway.create_feedback.assert_not_called()


def test_feedback_quota_exceeded_returns_retry_after(mock_gateway):
    mock_gateway.check_and_increment_usage.side_effect = QuotaExceededError(
        "Quota exceeded for feedback (hour)"
    )

    response = client.post(
        "/api/v1/feedback",
        json={
            "type": "general",
            "message": "The private alpha flow feels clear.",
            "context": {"surface": "settings"},
        },
    )

    assert response.status_code == 429
    assert response.json()["code"] == "too_many_requests"
    assert response.headers.get("Retry-After") == "60"
    mock_gateway.create_feedback.assert_not_called()


def test_signup_allows_email_on_private_alpha_allowlist(mock_gateway, monkeypatch):
    monkeypatch.setenv("NEXT_PUBLIC_MOCK_AUTH", "false")
    monkeypatch.setenv("ARGUS_MOCK_AUTH", "false")
    mock_gateway.private_alpha_email_allowed.return_value = True
    mock_gateway.signup.return_value = {
        "session": {
            "access_token": "access-token-123",
            "refresh_token": "refresh-token-123",
            "expires_in": 3600,
        },
        "user": {"id": "user-1", "email": "beta@example.com"},
    }

    response = client.post(
        "/api/v1/auth/signup",
        json={"email": "beta@example.com", "password": "password123"},
    )

    assert response.status_code == 200
    mock_gateway.private_alpha_email_allowed.assert_called_once_with(
        "beta@example.com"
    )
    mock_gateway.signup.assert_called_once()
    assert "mark_private_alpha_signup_accepted" not in [
        call[0] for call in mock_gateway.method_calls
    ]
    assert response.cookies.get("sb-auth-token") == "access-token-123"


def test_signup_blocks_email_before_supabase_creation_when_not_allowlisted(
    mock_gateway,
    monkeypatch,
):
    monkeypatch.setenv("NEXT_PUBLIC_MOCK_AUTH", "false")
    monkeypatch.setenv("ARGUS_MOCK_AUTH", "false")
    mock_gateway.private_alpha_email_allowed.return_value = False

    response = client.post(
        "/api/v1/auth/signup",
        json={"email": "stranger@example.com", "password": "password123"},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "private_alpha_access_required"
    assert "private alpha" in response.json()["detail"].lower()
    mock_gateway.signup.assert_not_called()
    mock_gateway.private_alpha_email_allowed.assert_called_once_with(
        "stranger@example.com"
    )
    assert "mark_private_alpha_signup_accepted" not in [
        call[0] for call in mock_gateway.method_calls
    ]


def test_signup_sanitizes_provider_errors(mock_gateway, monkeypatch):
    monkeypatch.setenv("NEXT_PUBLIC_MOCK_AUTH", "false")
    monkeypatch.setenv("ARGUS_MOCK_AUTH", "false")
    mock_gateway.private_alpha_email_allowed.return_value = True
    mock_gateway.signup.side_effect = RuntimeError(
        "Supabase provider leaked an internal auth reason"
    )

    response = client.post(
        "/api/v1/auth/signup",
        json={"email": "alpha@example.com", "password": "password123"},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "auth_signup_failed"
    assert response.json()["detail"] == "Signup failed. Please try again."
    assert "Supabase provider" not in response.text


def test_login_normalizes_private_alpha_access_failures(
    mock_gateway,
    monkeypatch,
):
    monkeypatch.setenv("NEXT_PUBLIC_MOCK_AUTH", "false")
    monkeypatch.setenv("ARGUS_MOCK_AUTH", "false")
    mock_gateway.private_alpha_email_allowed.return_value = False

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "disabled@example.com", "password": "password123"},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"
    assert response.json()["detail"] == "Invalid email or password."
    mock_gateway.login.assert_not_called()
    mock_gateway.private_alpha_email_allowed.assert_called_once_with(
        "disabled@example.com"
    )
    assert "mark_private_alpha_login" not in [
        call[0] for call in mock_gateway.method_calls
    ]


def test_login_normalizes_provider_auth_failures(mock_gateway, monkeypatch):
    monkeypatch.setenv("NEXT_PUBLIC_MOCK_AUTH", "false")
    monkeypatch.setenv("ARGUS_MOCK_AUTH", "false")
    mock_gateway.private_alpha_email_allowed.return_value = True
    mock_gateway.login.side_effect = RuntimeError("invalid provider password")

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "alpha@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"
    assert response.json()["detail"] == "Invalid email or password."
    mock_gateway.login.assert_called_once_with(
        email="alpha@example.com",
        password="wrong-password",
    )


def test_login_rate_limit_blocks_extra_attempt_before_provider(
    mock_gateway,
    monkeypatch,
):
    from argus.api.routers import auth as auth_router

    auth_router.reset_auth_attempt_limiter_for_tests()
    monkeypatch.setenv("NEXT_PUBLIC_MOCK_AUTH", "false")
    monkeypatch.setenv("ARGUS_MOCK_AUTH", "false")
    mock_gateway.private_alpha_email_allowed.return_value = True
    mock_gateway.login.side_effect = RuntimeError("invalid provider password")
    headers = {"X-Forwarded-For": "203.0.113.10"}

    for _ in range(auth_router.AUTH_LOGIN_ATTEMPT_LIMIT):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "alpha@example.com", "password": "wrong-password"},
            headers=headers,
        )
        assert response.status_code == 401

    blocked = client.post(
        "/api/v1/auth/login",
        json={"email": "alpha@example.com", "password": "wrong-password"},
        headers=headers,
    )

    assert blocked.status_code == 429
    assert blocked.json()["code"] == "too_many_requests"
    assert blocked.headers.get("Retry-After")
    assert mock_gateway.login.call_count == auth_router.AUTH_LOGIN_ATTEMPT_LIMIT


def test_signup_rate_limit_blocks_extra_attempt_before_allowlist_check(
    mock_gateway,
    monkeypatch,
):
    from argus.api.routers import auth as auth_router

    auth_router.reset_auth_attempt_limiter_for_tests()
    monkeypatch.setenv("NEXT_PUBLIC_MOCK_AUTH", "false")
    monkeypatch.setenv("ARGUS_MOCK_AUTH", "false")
    mock_gateway.private_alpha_email_allowed.return_value = False
    headers = {"X-Forwarded-For": "203.0.113.11"}

    for _ in range(auth_router.AUTH_SIGNUP_ATTEMPT_LIMIT):
        response = client.post(
            "/api/v1/auth/signup",
            json={"email": "stranger@example.com", "password": "password123"},
            headers=headers,
        )
        assert response.status_code == 403

    blocked = client.post(
        "/api/v1/auth/signup",
        json={"email": "stranger@example.com", "password": "password123"},
        headers=headers,
    )

    assert blocked.status_code == 429
    assert blocked.json()["code"] == "too_many_requests"
    assert blocked.headers.get("Retry-After")
    assert mock_gateway.private_alpha_email_allowed.call_count == (
        auth_router.AUTH_SIGNUP_ATTEMPT_LIMIT
    )
    mock_gateway.signup.assert_not_called()


def test_search_supabase_returns_cursor_page_and_supported_types(mock_gateway):
    now = utcnow()
    mock_gateway.search_rows.return_value = {
        "conversations": [
            {
                "id": "chat-1",
                "title": "Tesla chat",
                "last_message_preview": "Discussing TSLA",
                "updated_at": now.isoformat(),
                "pinned": True,
            }
        ],
        "strategies": [
            {
                "id": "strat-1",
                "name": "Tesla strategy",
                "symbols": ["TSLA"],
                "template": "rsi_mean_reversion",
                "updated_at": now.isoformat(),
                "pinned": False,
            }
        ],
        "collections": [
            {
                "id": "col-1",
                "name": "Tesla collection",
                "updated_at": now.isoformat(),
                "pinned": False,
            }
        ],
        "runs": [
            {
                "id": "run-1",
                "conversation_result_card": {"title": "TSLA backtest"},
                "created_at": now.isoformat(),
            }
        ],
    }

    response = client.get(
        "/api/v1/search?q=tesla&limit=2",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 2
    assert payload["next_cursor"] is not None
    assert {item["type"] for item in payload["items"]}.issubset(
        {"chat", "strategy", "collection", "run"}
    )


def test_history_supabase_requests_non_archived_rows_by_default(mock_gateway):
    mock_gateway.list_history_rows.return_value = {
        "runs": [],
        "conversations": [],
        "strategies": [],
        "collections": [],
    }

    response = client.get(
        "/api/v1/history",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    mock_gateway.list_history_rows.assert_called_once_with(
        user_id="00000000-0000-0000-0000-000000000001",
        limit=None,
        deleted=False,
        archived=False,
    )


def test_history_supabase_can_request_archived_rows(mock_gateway):
    mock_gateway.list_history_rows.return_value = {
        "runs": [],
        "conversations": [],
        "strategies": [],
        "collections": [],
    }

    response = client.get(
        "/api/v1/history?archived=true",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    mock_gateway.list_history_rows.assert_called_once_with(
        user_id="00000000-0000-0000-0000-000000000001",
        limit=None,
        deleted=False,
        archived=True,
    )


def test_conversations_cursor_supabase_pages_without_duplicates(mock_gateway):
    now = utcnow()
    mock_gateway.list_conversations.return_value = [
        Conversation(
            id="conv-1",
            title="Idea 1",
            title_source="system_default",
            language="en",
            pinned=True,
            archived=False,
            last_message_preview="A",
            deleted_at=None,
            created_at=now,
            updated_at=now,
        ),
        Conversation(
            id="conv-2",
            title="Idea 2",
            title_source="system_default",
            language="en",
            pinned=False,
            archived=False,
            last_message_preview="B",
            deleted_at=None,
            created_at=now,
            updated_at=now,
        ),
        Conversation(
            id="conv-3",
            title="Idea 3",
            title_source="system_default",
            language="en",
            pinned=False,
            archived=False,
            last_message_preview="C",
            deleted_at=None,
            created_at=now,
            updated_at=now,
        ),
    ]

    first_page = client.get(
        "/api/v1/conversations?limit=2",
        headers={"Authorization": "Bearer test-token"},
    )
    assert first_page.status_code == 200
    payload = first_page.json()
    assert len(payload["items"]) == 2
    assert payload["next_cursor"] is not None

    second_page = client.get(
        f"/api/v1/conversations?limit=2&cursor={payload['next_cursor']}",
        headers={"Authorization": "Bearer test-token"},
    )
    assert second_page.status_code == 200
    second_payload = second_page.json()
    first_ids = {item["id"] for item in payload["items"]}
    second_ids = {item["id"] for item in second_payload["items"]}
    assert first_ids.isdisjoint(second_ids)


def test_conversations_cursor_supabase_pages_beyond_one_hundred_items(mock_gateway):
    now = utcnow()
    mock_gateway.list_conversations.return_value = [
        Conversation(
            id=f"conv-{idx}",
            title=f"Idea {idx}",
            title_source="system_default",
            language="en",
            pinned=False,
            archived=False,
            last_message_preview=f"Preview {idx}",
            deleted_at=None,
            created_at=now,
            updated_at=now,
        )
        for idx in range(130)
    ]

    first_page = client.get(
        "/api/v1/conversations?limit=50",
        headers={"Authorization": "Bearer test-token"},
    )
    assert first_page.status_code == 200
    first_payload = first_page.json()
    assert len(first_payload["items"]) == 50
    assert first_payload["next_cursor"] is not None

    second_page = client.get(
        f"/api/v1/conversations?limit=50&cursor={first_payload['next_cursor']}",
        headers={"Authorization": "Bearer test-token"},
    )
    assert second_page.status_code == 200
    second_payload = second_page.json()
    assert len(second_payload["items"]) == 50
    assert second_payload["next_cursor"] is not None

    third_page = client.get(
        f"/api/v1/conversations?limit=50&cursor={second_payload['next_cursor']}",
        headers={"Authorization": "Bearer test-token"},
    )
    assert third_page.status_code == 200
    third_payload = third_page.json()
    assert len(third_payload["items"]) == 30
    assert third_payload["next_cursor"] is None
