import pytest
from argus.api.auth import auth_required
from argus.api.main import app
from argus.domain.schemas import User
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.fixture
def mock_user_free():
    return User(
        user_id="test-user-uuid",
        email="test@example.com",
        subscription_tier="free",
        is_admin=False,
        theme="dark",
        lang="en",
        backtest_quota=10,
        remaining_quota=0,  # Zero quota means exhausted
        last_quota_reset="2026-04-01T00:00:00Z",
        feature_flags={},
    )


@pytest.fixture
def mock_user_pro():
    return User(
        user_id="test-pro-uuid",
        email="pro@example.com",
        subscription_tier="pro",
        is_admin=False,
        theme="dark",
        lang="en",
        backtest_quota=1000,
        remaining_quota=500,
        last_quota_reset="2026-04-01T00:00:00Z",
        feature_flags={},
    )


@pytest.fixture
def mock_user_admin():
    return User(
        user_id="test-admin-uuid",
        email="admin@example.com",
        subscription_tier="free",
        is_admin=True,  # Admin bypasses quota even if 0
        theme="dark",
        lang="en",
        backtest_quota=10,
        remaining_quota=0,
        last_quota_reset="2026-04-01T00:00:00Z",
        feature_flags={},
    )


def test_rate_limit_exceeded(mock_user_free):
    """Test that 402 is raised when quota is 0."""
    app.dependency_overrides[auth_required] = lambda: mock_user_free

    response = client.post(
        "/api/v1/backtests",
        json={"strategy_id": "123"},
    )

    assert response.status_code == 402
    assert "Quota exceeded" in response.json()["detail"]["error"]


def test_pro_tier_bypass(mock_user_pro):
    """Test that pro user with remaining quota succeeds."""
    app.dependency_overrides[auth_required] = lambda: mock_user_pro

    # Needs to mock PostHog emit
    app.dependency_overrides[auth_required] = lambda: mock_user_pro

    response = client.post(
        "/api/v1/backtests",
        json={"strategy_id": "123"},
    )

    assert response.status_code == 200


def test_admin_bypass(mock_user_admin):
    """Test that admin bypasses quota even if 0."""
    app.dependency_overrides[auth_required] = lambda: mock_user_admin

    response = client.post(
        "/api/v1/backtests",
        json={"strategy_id": "123"},
    )

    assert response.status_code == 200
