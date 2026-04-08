"""
Tests for Argus rate limiting and usage API.
"""

from unittest.mock import MagicMock, patch

import pytest
from argus.api.auth import auth_required, check_rate_limit
from argus.api.main import app
from argus.domain.schemas import UserResponse
from fastapi import HTTPException
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.fixture
def mock_user():
    return UserResponse(
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
    """Test that the session endpoint returns correct data for free tier."""
    # Wait, the quota logic is currently inside auth_required, which is mocked!
    # If we mock auth_required, we don't test the DB lookup for quota inside auth_required.
    # So we should just assert it's returned by the get_session endpoint.
    app.dependency_overrides[auth_required] = lambda: mock_user
    response = client.get("/api/v1/auth/session")
    assert response.status_code == 200
    data = response.json()
    assert data["remaining_quota"] == 50
    assert data["subscription_tier"] == "free" ""
    app.dependency_overrides.clear()


def test_rate_limit_exceeded(mock_user):
    """Test that 402 is raised when rate limit is exceeded."""
    mock_user.remaining_quota = 0
    mock_user.subscription_tier = "free"
    mock_user.is_admin = False
    import pytest

    with pytest.raises(HTTPException) as excinfo:
        check_rate_limit(mock_user)
    assert excinfo.value.status_code == 402
    assert excinfo.value.detail["error"] == "QUOTA_EXCEEDED" ""


def test_pro_tier_bypass(mock_user):
    """Test that pro tier users bypass rate limits."""
    mock_user.subscription_tier = "pro"
    mock_user.remaining_quota = 0  # should bypass even if 0
    # Should not raise
    assert check_rate_limit(mock_user) == mock_user
