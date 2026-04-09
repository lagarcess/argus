from unittest.mock import MagicMock

import pytest
from argus.api.main import app, persistence_service
from argus.domain.schemas import UserResponse
from fastapi.testclient import TestClient

client = TestClient(app)


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
                    "win_rate_pct": 62.0,
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
    from argus.engine import BacktestResult

    app.dependency_overrides[check_rate_limit] = lambda: mock_user

    # Mock the emit_posthog_event
    monkeypatch.setattr("argus.api.main.emit_posthog_event", MagicMock())

    # Mock engine and dependencies to avoid real DB/API calls/instantiation
    from argus.engine import EquityCurvePoint, MetricsResult

    metrics = MetricsResult(
        total_return_pct=14.5,
        sharpe_ratio=1.8,
        sortino_ratio=2.1,
        max_drawdown_pct=0.05,
        win_rate_pct=62.0,
        total_trades=10,
        profit_factor=1.5,
        volatility=0.12,
        expectancy=0.05,
        alpha=0.02,
        beta=1.1,
        calmar_ratio=1.2,
        avg_trade_duration="2d 4h",
        avg_trade_duration_bars=50,
    )
    equity_curve = [
        EquityCurvePoint(timestamp="2024-01-01T00:00:00Z", value=100.0),
        EquityCurvePoint(timestamp="2024-01-02T00:00:00Z", value=114.5),
    ]
    mock_result = BacktestResult(
        metrics=metrics,
        equity_curve=equity_curve,
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
    assert data["config_snapshot"]["timeframe"] == "1h"


def test_get_assets(monkeypatch, mock_user):
    from argus.api.auth import check_asset_search_rate_limit

    # Mock dependencies
    app.dependency_overrides[check_asset_search_rate_limit] = lambda: {
        "X-RateLimit-Limit": "100",
        "X-RateLimit-Remaining": "99",
        "X-RateLimit-Reset": "1712534400",
    }

    # Mock alpaca_fetcher's get_active_assets instead of trading client
    mock_assets = ["BTC/USDT", "AAPL", "ETH/USD", "TSLA"]
    monkeypatch.setattr(
        "argus.api.main.alpaca_fetcher.get_active_assets", lambda: mock_assets
    )

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
