from unittest.mock import MagicMock

import pytest
from argus.api.main import app, persistence_service
from argus.domain.schemas import User
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.fixture
def mock_user():
    return User(user_id="550e8400-e29b-41d4-a716-446655440000", email="test@example.com")


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "version": "1.0.0"}


def test_get_history(monkeypatch, mock_user):
    # Mock auth
    monkeypatch.setattr("argus.api.main.auth_required", lambda: mock_user)

    # Mock persistence
    mock_summaries = [
        {
            "id": "sim_123",
            "strategy_name": "Test Strategy",
            "symbols": ["BTC"],
            "timeframe": "1Day",
            "status": "completed",
            "total_return_pct": 10.5,
            "sharpe_ratio": 1.5,
            "win_rate_pct": 60.0,
            "max_drawdown_pct": -5.0,
            "total_trades": 10,
            "created_at": "2024-03-01T12:00:00Z",
        }
    ]
    persistence_service.get_user_simulations = MagicMock(return_value=(mock_summaries, 1))

    # Overriding dependency for the test
    from argus.api.auth import auth_required

    app.dependency_overrides[auth_required] = lambda: mock_user

    response = client.get("/api/v1/history")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["simulations"][0]["id"] == "sim_123"
    assert "total_return_pct" in data["simulations"][0]

    app.dependency_overrides.clear()


def test_backtest_endpoint_success(monkeypatch, mock_user):
    # Mock auth
    from argus.api.auth import auth_required

    app.dependency_overrides[auth_required] = lambda: mock_user

    # Mock engine and persistence
    monkeypatch.setattr("argus.api.main.get_stock_data_client", MagicMock())
    monkeypatch.setattr("argus.api.main.get_crypto_data_client", MagicMock())

    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"metrics": {"total_return_pct": 15.0}}
    monkeypatch.setattr(
        "argus.engine.ArgusEngine.run", MagicMock(return_value=mock_result)
    )

    persistence_service.save_strategy = MagicMock(return_value="strat_456")
    persistence_service.save_simulation = MagicMock(return_value="sim_789")

    payload = {
        "strategy_name": "My Strategy",
        "symbols": ["BTC"],
        "asset_class": "crypto",
        "timeframe": "1Day",
        "entry_patterns": ["RSI_OVERSOLD"],
        "exit_patterns": ["RSI_OVERBOUGHT"],
    }

    response = client.post("/api/v1/backtest", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["strategy_id"] == "strat_456"
    assert "simulation_id" in data

    app.dependency_overrides.clear()


def test_backtest_endpoint_value_error(monkeypatch, mock_user):
    # Mock auth
    from argus.api.auth import auth_required

    app.dependency_overrides[auth_required] = lambda: mock_user

    # Mock engine to raise ValueError
    monkeypatch.setattr("argus.api.main.get_stock_data_client", MagicMock())
    monkeypatch.setattr("argus.api.main.get_crypto_data_client", MagicMock())

    monkeypatch.setattr(
        "argus.engine.ArgusEngine.run",
        MagicMock(side_exception=ValueError("Data is empty")),
    )

    # Above doesn't work for side effects in MagicMock, use side_effect
    def mock_run(*args, **kwargs):
        raise ValueError("Data is empty")

    monkeypatch.setattr("argus.engine.ArgusEngine.run", mock_run)

    payload = {
        "strategy_name": "My Strategy",
        "symbols": ["BTC"],
        "asset_class": "crypto",
        "timeframe": "1Day",
        "entry_patterns": ["RSI_OVERSOLD"],
        "exit_patterns": ["RSI_OVERBOUGHT"],
    }

    response = client.post("/api/v1/backtest", json=payload)

    assert response.status_code == 400
    assert "Data is empty" in response.json()["detail"]

    app.dependency_overrides.clear()
