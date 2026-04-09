from unittest.mock import MagicMock

import pytest
from argus.api.main import app
from argus.domain.schemas import UserResponse
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.fixture
def mock_user_free():
    return UserResponse(
        id="test-user-uuid",
        user_id="test-user-uuid",
        email="test@example.com",
        subscription_tier="free",
        is_admin=False,
        backtest_quota=10,
        remaining_quota=0,
    )


@pytest.fixture
def mock_user_pro():
    return UserResponse(
        id="test-pro-uuid",
        user_id="test-pro-uuid",
        email="pro@example.com",
        subscription_tier="pro",
        is_admin=False,
        backtest_quota=1000,
        remaining_quota=500,
    )


@pytest.fixture
def mock_user_admin():
    return UserResponse(
        id="test-admin-uuid",
        user_id="test-admin-uuid",
        email="admin@example.com",
        subscription_tier="free",
        is_admin=True,
        backtest_quota=10,
        remaining_quota=0,
    )


def test_rate_limit_exceeded(mock_user_free):
    """Test that 402 is raised when quota is 0."""
    from argus.api.auth import auth_required

    app.dependency_overrides[auth_required] = lambda: mock_user_free

    response = client.post(
        "/api/v1/backtests",
        json={"strategy_id": "123"},
    )

    app.dependency_overrides.clear()
    assert response.status_code == 402
    assert response.json()["detail"]["error"] == "QUOTA_EXCEEDED"


def test_pro_tier_bypass(mock_user_pro, monkeypatch):
    """Test that pro user with remaining quota succeeds."""
    from argus.api.auth import check_rate_limit

    app.dependency_overrides[check_rate_limit] = lambda: mock_user_pro

    # Mock engine and dependencies
    from argus.engine import BacktestResult, EquityCurvePoint, MetricsResult

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
    monkeypatch.setattr("argus.api.main.get_stock_data_client", MagicMock())
    monkeypatch.setattr("argus.api.main.get_crypto_data_client", MagicMock())
    monkeypatch.setattr(
        "argus.api.main.persistence_service.get_strategy",
        MagicMock(
            return_value={"id": "123", "name": "X", "symbol": "BTC", "timeframe": "1h"}
        ),
    )
    monkeypatch.setattr("argus.api.main.persistence_service.save_simulation", MagicMock())

    monkeypatch.setattr("argus.api.main.supabase_client", MagicMock())

    response = client.post(
        "/api/v1/backtests",
        json={"strategy_id": "123"},
    )

    app.dependency_overrides.clear()
    assert response.status_code == 200


def test_admin_bypass(mock_user_admin, monkeypatch):
    """Test that admin bypasses quota even if 0."""
    from argus.api.auth import check_rate_limit

    app.dependency_overrides[check_rate_limit] = lambda: mock_user_admin

    from argus.engine import BacktestResult, EquityCurvePoint, MetricsResult

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
    monkeypatch.setattr("argus.api.main.get_stock_data_client", MagicMock())
    monkeypatch.setattr("argus.api.main.get_crypto_data_client", MagicMock())
    monkeypatch.setattr(
        "argus.api.main.persistence_service.get_strategy",
        MagicMock(
            return_value={"id": "123", "name": "X", "symbol": "BTC", "timeframe": "1h"}
        ),
    )
    monkeypatch.setattr("argus.api.main.persistence_service.save_simulation", MagicMock())

    # Mock the RPC quota decrement
    monkeypatch.setattr("argus.api.main.supabase_client", MagicMock())

    response = client.post(
        "/api/v1/backtests",
        json={"strategy_id": "123"},
    )

    app.dependency_overrides.clear()
    assert response.status_code == 200
