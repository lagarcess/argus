from datetime import date
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
    from argus.domain.orchestrator import ChatOrchestrationDecision, StrategyExtraction

    monkeypatch.setattr(
        api_main,
        "orchestrate_chat_turn",
        lambda message, language, onboarding_required, primary_goal: (
            ChatOrchestrationDecision(
                intent="onboarding_prompt",
                assistant_message=(
                    "What is your current primary goal? Don't worry, "
                    "you can change it later in Settings."
                ),
                strategy=None,
                title_suggestion=None,
            )
            if onboarding_required
            else ChatOrchestrationDecision(
                intent="run_backtest",
                assistant_message=(
                    "Probé la idea con TSLA."
                    if str(language).lower().startswith("es")
                    else "I tested that idea with TSLA."
                ),
                strategy=StrategyExtraction(
                    template="rsi_mean_reversion",
                    asset_class="equity",
                    symbols=["TSLA"],
                    parameters={},
                ),
                title_suggestion="TSLA idea",
            )
        ),
    )
    monkeypatch.setattr(domain_engine, "resolve_asset", _fake_resolve_asset)
    monkeypatch.setattr(domain_engine, "fetch_ohlcv", _fake_fetch_ohlcv)
    monkeypatch.setattr(domain_engine, "fetch_price_series", _fake_fetch_price_series)


@pytest.fixture
def mock_gateway():
    gateway = MagicMock(spec=SupabaseGateway)
    gateway.get_user.return_value = _mock_profile()
    gateway.get_or_create_mock_user.return_value = _mock_profile()
    gateway.count_completed_runs.return_value = 1
    gateway.list_messages.return_value = []
    with patch("argus.api.main.supabase_gateway", gateway):
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


def test_chat_stream_quota_exceeded(mock_gateway):
    mock_gateway.check_and_increment_usage.side_effect = QuotaExceededError(
        "Quota exceeded for chat_messages (minute)"
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


def test_me_reads_profile_from_supabase_gateway(mock_gateway):
    profile = _mock_profile(language="es-419")
    mock_gateway.get_user.return_value = profile

    response = client.get("/api/v1/me", headers={"Authorization": "Bearer test-token"})

    assert response.status_code == 200
    assert response.json()["user"]["language"] == "es-419"
    mock_gateway.get_user.assert_called_once()


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


def test_create_conversation_uses_dev_memory_fallback_when_supabase_fails(
    mock_gateway,
):
    mock_gateway.create_conversation.side_effect = RuntimeError("supabase unavailable")

    response = client.post(
        "/api/v1/conversations",
        json={"language": "en"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    conversation = response.json()["conversation"]
    assert conversation["title"] == "New idea"
    assert conversation["title_source"] == "system_default"


def test_run_backtest_supabase_persists_normalized_snapshot_and_assumptions(mock_gateway):
    mock_gateway.create_backtest_run.side_effect = (
        lambda *, user_id, run: run
    )

    response = client.post(
        "/api/v1/backtests/run",
        json={"template": "rsi_mean_reversion", "symbols": ["TSLA"]},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    run = response.json()["run"]
    assert run["config_snapshot"]["side"] == "long"
    assert run["config_snapshot"]["starting_capital"] == 10000
    assert run["config_snapshot"]["benchmark_symbol"] == "SPY"
    assert run["conversation_result_card"]["assumptions"][-1] == "Benchmark: SPY."
    mock_gateway.create_backtest_run.assert_called_once()
    called_run = mock_gateway.create_backtest_run.call_args.kwargs["run"]
    assert isinstance(called_run, BacktestRun)
    assert called_run.config_snapshot["starting_capital"] == 10000


def test_get_backtest_supabase_reads_from_gateway(mock_gateway):
    mock_gateway.create_backtest_run.side_effect = (
        lambda *, user_id, run: run
    )
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
    mock_gateway.create_backtest_run.side_effect = (
        lambda *, user_id, run: run
    )
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
    assert "event: result" in response.text
    mock_gateway.create_backtest_run.assert_called_once()


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
    assert "event: result" not in response.text
    assert "event: token" in response.text
    assert "primary goal" in response.text
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
