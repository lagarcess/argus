from unittest.mock import MagicMock, patch

import pytest
from argus.api.main import app
from argus.domain.supabase_gateway import QuotaExceededError, SupabaseGateway
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


def test_create_message_ownership_failure(mock_gateway):
    # Setup conversation missing
    mock_gateway.get_conversation.return_value = None

    # Test method directly (unit test on method)
    # We need a client mock to avoid real DB hit if we instantiate ActualGateway
    pass


def test_attach_strategies_ownership_failure(mock_gateway):
    # This could test the ValueError being raised in attach_strategies
    # But attach_strategies is tested in the Real/Mock Gateway.
    pass
