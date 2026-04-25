from unittest.mock import MagicMock, patch

import pytest
from argus.api.main import app
from argus.api.schemas import BacktestRun, Conversation, User
from argus.domain.supabase_gateway import QuotaExceededError, SupabaseGateway
from argus.domain.store import utcnow
from fastapi.testclient import TestClient

client = TestClient(app)


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
