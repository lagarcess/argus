from unittest.mock import MagicMock

import pytest
from argus.api.main import app
from argus.domain.schemas import User
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.fixture
def mock_user():
    return User(
        user_id="550e8400-e29b-41d4-a716-446655440000",
        email="test@example.com",
        subscription_tier="free",
        is_admin=False,
        theme="dark",
        lang="en",
        backtest_quota=10,
        remaining_quota=10,
        last_quota_reset="2026-04-01T00:00:00Z",
        feature_flags={},
    )


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "version": "1.0.0"}


def test_get_history(monkeypatch, mock_user):
    from argus.api.auth import auth_required

    app.dependency_overrides[auth_required] = lambda: mock_user

    response = client.get("/api/v1/history")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 100
    assert len(data["simulations"]) == 1
    assert data["simulations"][0]["strategy_name"] == "Golden Cross DR"


def test_backtest_endpoint_xor_validation(monkeypatch, mock_user):
    from argus.api.auth import check_rate_limit

    app.dependency_overrides[check_rate_limit] = lambda: mock_user

    # Neither ID nor inline
    response = client.post("/api/v1/backtests", json={})
    assert response.status_code == 422

    # Both ID and inline
    response = client.post(
        "/api/v1/backtests",
        json={
            "strategy_id": "123",
            "symbol": "BTC/USDT",
            "timeframe": "1h",
            "start_date": "2025-01-01T00:00:00Z",
            "end_date": "2025-02-01T00:00:00Z",
        },
    )
    assert response.status_code == 422


def test_backtest_endpoint_success(monkeypatch, mock_user):
    from argus.api.auth import check_rate_limit

    app.dependency_overrides[check_rate_limit] = lambda: mock_user

    # Mock the emit_posthog_event
    monkeypatch.setattr("argus.api.main.emit_posthog_event", MagicMock())

    response = client.post("/api/v1/backtests", json={"strategy_id": "123"})

    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["results"]["total_return_pct"] == 14.5
    assert data["config_snapshot"]["timeframe"] == "1h"
