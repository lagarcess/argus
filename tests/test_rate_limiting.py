"""
Tests for Argus rate limiting and usage API.
"""

from unittest.mock import MagicMock, patch

import pytest
from argus.api.auth import auth_required, check_rate_limit
from argus.api.main import app
from argus.domain.schemas import User
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.fixture
def mock_user():
    return User(
        user_id="test-user-uuid", email="test@example.com", subscription_tier="free"
    )


@pytest.fixture
def mock_supabase():
    # Mocking the client where it is USED, not just where it is defined.
    # This ensures that components that already imported the module-level variable see the mock.
    with (
        patch("argus.api.auth.supabase_client") as mock_auth,
        patch("argus.api.main.supabase_client"),
    ):
        yield mock_auth  # Both are the same mock object anyway if we patch correctly,
        # but let's just use mock_auth for configuration and assume both see it if we use the same mock.
        # Wait, let's just configure one and return it.


@pytest.fixture
def configured_mock_supabase():
    mock = MagicMock()
    # Chain: .table().select().eq().gte().execute().count
    mock_count_res = MagicMock()
    mock.table.return_value.select.return_value.eq.return_value.gte.return_value.execute.return_value = mock_count_res
    # Also for main.py which might not have .gte() in some queries
    mock.table.return_value.select.return_value.eq.return_value.execute.return_value = (
        mock_count_res
    )

    with (
        patch("argus.api.auth.supabase_client", mock),
        patch("argus.api.main.supabase_client", mock),
    ):
        yield mock


def test_usage_endpoint_free_tier(mock_user, configured_mock_supabase):
    """Test that the usage endpoint returns correct data for free tier."""
    app.dependency_overrides[auth_required] = lambda: mock_user

    # Configure mock count
    configured_mock_supabase.table.return_value.select.return_value.eq.return_value.gte.return_value.execute.return_value.count = 5

    response = client.get("/api/v1/usage")

    if response.status_code != 200:
        print(f"Response: {response.status_code} - {response.text}")

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 5
    assert data["limit"] == 10
    assert data["tier"] == "free"

    app.dependency_overrides.clear()


def test_rate_limit_exceeded(mock_user, configured_mock_supabase):
    """Test that 403 is raised when rate limit is exceeded."""
    # Configure mock count above limit
    configured_mock_supabase.table.return_value.select.return_value.eq.return_value.gte.return_value.execute.return_value.count = 10

    app.dependency_overrides[auth_required] = lambda: mock_user

    # Act: Request backtest.
    response = client.post(
        "/api/v1/backtest",
        json={
            "strategy_name": "Test",
            "symbols": ["BTC-USD"],
            "asset_class": "crypto",
            "timeframe": "1Day",
            "entry_patterns": ["rsi_oversold"],
            "exit_patterns": ["rsi_overbought"],
            "confluence_mode": "OR",
            "slippage": 0.001,
            "fees": 0.001,
            "rsi_period": 14,
            "rsi_oversold": 30,
            "rsi_overbought": 70,
            "ema_period": 200,
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
        },
    )

    if response.status_code != 403:
        print(f"Response: {response.status_code} - {response.text}")

    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "Monthly limit reached"

    app.dependency_overrides.clear()


def test_pro_tier_bypass():
    """Test that pro tier users bypass the rate limit check."""
    pro_user = User(
        user_id="pro-user-uuid", email="pro@example.com", subscription_tier="pro"
    )
    result = check_rate_limit(user=pro_user)
    assert result == pro_user
