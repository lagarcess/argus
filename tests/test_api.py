from datetime import timezone
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest
from argus.api.main import app, persistence_service
from argus.domain.schemas import UserResponse
from fastapi.testclient import TestClient

client = TestClient(app)


class MockAlpacaFetcher:
    def validate_asset(self, symbol):
        return True, "crypto"

    def fetch_bars(self, symbol, timeframe, start, end=None):
        # Generate 100 periods of mock data
        dates = pd.date_range(start=start, periods=100, freq="H", tz=timezone.utc)
        df = pd.DataFrame(
            {
                "open": np.random.uniform(40000, 45000, 100),
                "high": np.random.uniform(45000, 46000, 100),
                "low": np.random.uniform(39000, 40000, 100),
                "close": np.random.uniform(40000, 45000, 100),
                "volume": np.random.uniform(1, 10, 100),
                "vwap": np.random.uniform(40000, 45000, 100),
            },
            index=dates,
        )
        return df

    def close(self):
        pass


@pytest.fixture
def mock_user():
    return UserResponse(
        user_id="550e8400-e29b-41d4-a716-446655440000",
        id="550e8400-e29b-41d4-a716-446655440000",
        email="test@example.com",
        subscription_tier="free",
        is_admin=False,
        backtest_quota=50,
        remaining_quota=50,
    )


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "version": "1.0.0"}


def test_get_history(monkeypatch, mock_user):
    from argus.api.auth import auth_required

    app.dependency_overrides[auth_required] = lambda: mock_user

    # Mock the persistence layer to avoid real DB calls
    persistence_service.get_user_simulations = MagicMock(
        return_value=(
            [
                {
                    "id": "sim_123",
                    "strategy_name": "Golden Cross DR",
                    "symbols": ["BTC/USDT"],
                    "timeframe": "1h",
                    "status": "completed",
                    "total_return_pct": 14.5,
                    "sharpe_ratio": 1.8,
                    "max_drawdown_pct": 5.2,
                    "win_rate": 62.0,  # Legacy pct in DB, should be mapped to 0.62 by API
                    "total_trades": 42,
                    "created_at": "2026-04-07T13:15:00Z",
                }
            ],
            100,
        )
    )

    response = client.get("/api/v1/history")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 100
    assert len(data["simulations"]) == 1
    assert data["simulations"][0]["strategy_name"] == "Golden Cross DR"
    assert data["simulations"][0]["win_rate"] == 0.62


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
    from argus.api.main import (
        get_alpaca_fetcher,
        get_crypto_data_client,
        get_stock_data_client,
    )
    from argus.engine import EngineBacktestResults

    app.dependency_overrides[check_rate_limit] = lambda: mock_user
    app.dependency_overrides[get_alpaca_fetcher] = lambda: MagicMock()
    app.dependency_overrides[get_stock_data_client] = lambda: MagicMock()
    app.dependency_overrides[get_crypto_data_client] = lambda: MagicMock()

    # Mock the emit_posthog_event
    monkeypatch.setattr("argus.api.main.emit_posthog_event", MagicMock())

    # Mock engine and dependencies to avoid real DB/API calls/instantiation
    mock_result = EngineBacktestResults(
        total_return_pct=14.5,
        win_rate=62.0,  # Engine returns percentage
        sharpe_ratio=1.8,
        sortino_ratio=2.1,
        calmar_ratio=1.2,
        profit_factor=1.5,
        expectancy=0.05,
        max_drawdown_pct=0.05,
        equity_curve=[100.0, 114.5],
        trades=[],
        reality_gap_metrics={"slippage_impact_pct": 1.2, "fee_impact_pct": 0.4},
        pattern_breakdown={},
    )

    mock_engine = MagicMock()
    mock_engine.run.return_value = mock_result
    monkeypatch.setattr("argus.api.main.ArgusEngine", MagicMock(return_value=mock_engine))
    # Mock the RPC quota decrement
    monkeypatch.setattr("argus.api.main.supabase_client", MagicMock())

    # Mock persistence service calls
    persistence_service.get_strategy = MagicMock(
        return_value={
            "id": "123",
            "name": "Test Strategy",
            "symbol": "BTC/USDT",
            "timeframe": "1h",
            "start_date": None,
            "end_date": None,
            "fees": 0.001,
            "slippage": 0.001,
        }
    )
    persistence_service.save_strategy = MagicMock(return_value={"id": "strat_456"})
    persistence_service.save_simulation = MagicMock(return_value="sim_789")

    # Mock the RPC quota decrement
    monkeypatch.setattr("argus.api.main.supabase_client", MagicMock())

    response = client.post(
        "/api/v1/backtests",
        json={"strategy_id": "123"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["results"]["total_return_pct"] == 14.5
    assert data["results"]["win_rate"] == 0.62
    assert data["config_snapshot"]["timeframe"] == "1h"


def test_get_assets(monkeypatch, mock_user):
    from argus.api.auth import check_asset_search_rate_limit

    # Mock dependencies
    app.dependency_overrides[check_asset_search_rate_limit] = lambda: {
        "X-RateLimit-Limit": "100",
        "X-RateLimit-Remaining": "99",
        "X-RateLimit-Reset": "1712534400",
    }

    # Mock the get_alpaca_fetcher function to return a mock fetcher
    mock_assets = [
        {"symbol": "BTC/USDT", "name": "Bitcoin"},
        {"symbol": "AAPL", "name": "Apple Inc."},
        {"symbol": "ETH/USD", "name": "Ethereum"},
        {"symbol": "TSLA", "name": "Tesla Inc."},
    ]
    mock_fetcher = MagicMock()
    mock_fetcher.get_active_assets.return_value = mock_assets
    monkeypatch.setattr("argus.api.main.get_alpaca_fetcher", lambda: mock_fetcher)

    # Clear cache to ensure hit
    from argus.api.main import asset_cache

    asset_cache.set([])

    # Test search
    response = client.get("/api/v1/assets?search=btc")

    assert response.status_code == 200
    data = response.json()
    assert "BTC/USDT" in data
    assert "AAPL" not in data
    assert response.headers["X-RateLimit-Limit"] == "100"


def test_v1_backtest_e2e_high_fidelity(monkeypatch, mock_user):
    """
    High-fidelity E2E test integrated into test_api.py.
    Verifies full Engine-to-Response logic flow using MockAlpacaFetcher.
    """
    from argus.api.auth import check_rate_limit
    from argus.api.main import get_alpaca_fetcher

    app.dependency_overrides[check_rate_limit] = lambda: mock_user
    app.dependency_overrides[get_alpaca_fetcher] = lambda: MockAlpacaFetcher()

    # Mock persistence
    monkeypatch.setattr(
        "argus.api.main.persistence_service.save_simulation",
        lambda **kwargs: "mock-sim-id",
    )
    monkeypatch.setattr(
        "argus.api.main.persistence_service.save_strategy",
        lambda user_id, data: {"id": "mock-strat-id"},
    )

    payload = {
        "symbol": "BTC/USD",
        "timeframe": "1h",
        "start_date": "2024-01-01T00:00:00Z",
        "end_date": "2024-01-05T00:00:00Z",
        "strategy_id": None,
        "name": "E2E Strategy",
        "entry_criteria": [
            {"indicator": "rsi", "period": 14, "condition": "is_below", "target": 30}
        ],
        "exit_criteria": {"stop_loss_pct": 0.02, "take_profit_pct": 0.05},
        "indicators_config": {"rsi": {"period": 14}},
        "slippage": 0.001,
        "fees": 0.001,
    }

    response = client.post("/api/v1/backtests", json=payload)
    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["results"]["win_rate"] <= 1.0
    assert len(data["results"]["trades"]) <= 5
    assert "config_snapshot" in data
    assert "rsi" in data["config_snapshot"]["indicators_config"]
