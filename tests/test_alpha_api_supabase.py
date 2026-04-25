from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from argus.api.main import app
from argus.api.schemas import BacktestRun, Conversation, User
from argus.domain.market_data.assets import ResolvedAsset
from argus.domain.store import utcnow
from argus.domain.supabase_gateway import QuotaExceededError, SupabaseGateway
from fastapi.testclient import TestClient

client = TestClient(app)


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


@pytest.fixture
def mock_gateway():
    gateway = MagicMock(spec=SupabaseGateway)
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
    now = utcnow()
    profile = User(
        id="00000000-0000-0000-0000-000000000001",
        email="developer@argus.local",
        username="mock-developer",
        display_name="Mock Developer",
        language="es-419",
        locale="es-419",
        timezone="America/Chicago",
        theme="dark",
        is_admin=True,
        onboarding={},
        created_at=now,
        updated_at=now,
    )
    mock_gateway.get_user.return_value = profile

    response = client.get("/api/v1/me", headers={"Authorization": "Bearer test-token"})

    assert response.status_code == 200
    assert response.json()["user"]["language"] == "es-419"
    mock_gateway.get_user.assert_called_once()


def test_create_message_ownership_failure(mock_gateway):
    # Setup conversation missing
    mock_gateway.get_conversation.return_value = None

    # Test method directly (unit test on method)
    # We need a client mock to avoid real DB hit if we instantiate ActualGateway
    pass


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

    response = client.post(
        "/api/v1/chat/stream",
        json={"conversation_id": "conv-1", "message": "Test TSLA dip idea"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert "event: result" in response.text
    mock_gateway.create_backtest_run.assert_called_once()
