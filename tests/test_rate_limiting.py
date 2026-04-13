from unittest.mock import MagicMock

import pytest
from argus.api.auth import auth_required, check_rate_limit
from argus.api.main import (
    app,
    get_alpaca_fetcher,
    get_crypto_data_client,
    get_stock_data_client,
)
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
    app.dependency_overrides[auth_required] = lambda: mock_user_free

    response = client.post(
        "/api/v1/backtests",
        json={"strategy_id": "123"},
    )

    app.dependency_overrides.clear()
    assert response.status_code == 402
    assert response.json()["detail"]["error"] == "QUOTA_EXCEEDED"


def test_pro_tier_bypass(mock_user_pro, monkeypatch, make_engine_results):
    """Test that pro user with remaining quota succeeds."""
    app.dependency_overrides[check_rate_limit] = lambda: mock_user_pro
    app.dependency_overrides[get_stock_data_client] = lambda: MagicMock()
    app.dependency_overrides[get_crypto_data_client] = lambda: MagicMock()
    # Create a mock that supports unpacking for validate_asset
    fetcher_mock = MagicMock()
    fetcher_mock.validate_asset.return_value = (True, "equity")
    app.dependency_overrides[get_alpaca_fetcher] = lambda: fetcher_mock

    # Mock memory to prevent 503 Service Unavailable guard from triggering
    mock_mem = MagicMock()
    mock_mem.available = 800 * 1024 * 1024
    mock_mem.total = 1000 * 1024 * 1024  # 80% available
    monkeypatch.setattr("psutil.virtual_memory", lambda: mock_mem)

    # Mock engine and dependencies
    from argus.engine import EngineBacktestResults

    mock_result = EngineBacktestResults(
        total_return_pct=14.5,
        win_rate=0.62,
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

    monkeypatch.setattr(
        "argus.api.main.persistence_service.get_strategy",
        MagicMock(
            return_value={"id": "123", "name": "X", "symbols": ["BTC"], "timeframe": "1h"}
        ),
    )
    monkeypatch.setattr(
        "argus.api.main.persistence_service.save_strategy",
        MagicMock(return_value={"id": "123"}),
    )
    monkeypatch.setattr("argus.api.main.persistence_service.save_simulation", MagicMock())

    monkeypatch.setattr("argus.api.main.supabase_client", MagicMock())

    response = client.post(
        "/api/v1/backtests",
        json={"strategy_id": "123"},
    )

    app.dependency_overrides.clear()
    assert response.status_code == 200


def test_admin_bypass(mock_user_admin, monkeypatch, make_engine_results):
    """Test that admin bypasses quota even if 0."""
    app.dependency_overrides[check_rate_limit] = lambda: mock_user_admin
    app.dependency_overrides[get_stock_data_client] = lambda: MagicMock()
    app.dependency_overrides[get_crypto_data_client] = lambda: MagicMock()
    # Create a mock that supports unpacking for validate_asset
    fetcher_mock = MagicMock()
    fetcher_mock.validate_asset.return_value = (True, "equity")
    app.dependency_overrides[get_alpaca_fetcher] = lambda: fetcher_mock

    # Mock memory to prevent 503 Service Unavailable guard from triggering
    mock_mem = MagicMock()
    mock_mem.available = 800 * 1024 * 1024
    mock_mem.total = 1000 * 1024 * 1024  # 80% available
    monkeypatch.setattr("psutil.virtual_memory", lambda: mock_mem)

    from argus.engine import EngineBacktestResults

    mock_result = EngineBacktestResults(
        total_return_pct=14.5,
        win_rate=0.62,
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
    monkeypatch.setattr("argus.api.main.get_stock_data_client", MagicMock())
    monkeypatch.setattr("argus.api.main.get_crypto_data_client", MagicMock())
    monkeypatch.setattr(
        "argus.api.main.persistence_service.get_strategy",
        MagicMock(
            return_value={"id": "123", "name": "X", "symbols": ["BTC"], "timeframe": "1h"}
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


def test_check_rate_limit_december_rollover(monkeypatch, mock_user_free):
    from datetime import datetime, timezone

    from argus.api.auth import check_rate_limit

    class MockDatetime:
        @classmethod
        def now(cls, tz=None):
            return datetime(2025, 12, 15, tzinfo=timezone.utc)

    monkeypatch.setattr("argus.api.auth.datetime", MockDatetime)

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        check_rate_limit(mock_user_free)

    assert exc.value.status_code == 402
    assert "2026-01-01" in exc.value.detail["details"]["next_reset"]


def test_check_asset_search_rate_limit_headers(mock_user_free):
    from argus.api.auth import check_asset_search_rate_limit

    headers = check_asset_search_rate_limit(user=mock_user_free)
    assert "X-RateLimit-Limit" in headers
    assert "X-RateLimit-Remaining" in headers
    assert "X-RateLimit-Reset" in headers
    assert headers["X-RateLimit-Limit"] == "100"


def test_tier_gating_symbol_count_violation(monkeypatch, make_engine_results):
    from argus.api.auth import check_rate_limit

    mock_user_free = UserResponse(
        id="test-free-uuid",
        email="free@example.com",
        is_admin=False,
        subscription_tier="free",
        theme="dark",
        lang="en",
        backtest_quota=50,
        remaining_quota=50,
    )
    app.dependency_overrides[check_rate_limit] = lambda: mock_user_free
    app.dependency_overrides[get_stock_data_client] = lambda: MagicMock()
    app.dependency_overrides[get_crypto_data_client] = lambda: MagicMock()
    fetcher_mock = MagicMock()
    fetcher_mock.validate_asset.return_value = (True, "equity")
    app.dependency_overrides[get_alpaca_fetcher] = lambda: fetcher_mock

    # Mock memory for this test
    mock_mem = MagicMock()
    mock_mem.available = 80 * 1024 * 1024
    mock_mem.total = 100 * 1024 * 1014
    monkeypatch.setattr("psutil.virtual_memory", lambda: mock_mem)
    monkeypatch.setattr(
        "argus.api.main.persistence_service.save_strategy",
        lambda *args, **kwargs: {"id": "mock-strat-id"},
    )
    monkeypatch.setattr(
        "argus.api.main.persistence_service.save_simulation",
        lambda *args, **kwargs: "mock-sim-id",
    )

    payload = {
        "symbols": ["BTC/USD", "ETH/USD"],  # Free tier allows 1
        "timeframe": "1Day",
        "start_date": "2024-01-01T00:00:00Z",
        "end_date": "2024-01-05T00:00:00Z",
        "strategy_id": None,
        "name": "E2E Strategy",
        "entry_criteria": [],
    }

    response = client.post("/api/v1/backtests", json=payload)
    app.dependency_overrides.clear()

    assert response.status_code == 403
    assert "limited to 1 symbols" in response.json()["detail"]


def test_tier_gating_daily_lookback_violation(monkeypatch, make_engine_results):
    from argus.api.auth import check_rate_limit

    mock_user_free = UserResponse(
        id="test-free-uuid",
        email="free@example.com",
        is_admin=False,
        subscription_tier="free",
        theme="dark",
        lang="en",
        backtest_quota=50,
        remaining_quota=50,
    )
    app.dependency_overrides[check_rate_limit] = lambda: mock_user_free
    app.dependency_overrides[get_stock_data_client] = lambda: MagicMock()
    app.dependency_overrides[get_crypto_data_client] = lambda: MagicMock()
    fetcher_mock = MagicMock()
    fetcher_mock.validate_asset.return_value = (True, "equity")
    app.dependency_overrides[get_alpaca_fetcher] = lambda: fetcher_mock

    # Mock memory for this test
    mock_mem = MagicMock()
    mock_mem.available = 80 * 1024 * 1024
    mock_mem.total = 100 * 1024 * 1014
    monkeypatch.setattr("psutil.virtual_memory", lambda: mock_mem)
    monkeypatch.setattr(
        "argus.api.main.persistence_service.save_strategy",
        lambda *args, **kwargs: {"id": "mock-strat-id"},
    )
    monkeypatch.setattr(
        "argus.api.main.persistence_service.save_simulation",
        lambda *args, **kwargs: "mock-sim-id",
    )

    payload = {
        "symbols": ["BTC/USD"],
        "timeframe": "1Day",
        "start_date": "2020-01-01T00:00:00Z",  # Free tier daily lookback is 365 days
        "end_date": "2024-01-05T00:00:00Z",
        "strategy_id": None,
        "name": "E2E Strategy",
        "entry_criteria": [],
    }

    response = client.post("/api/v1/backtests", json=payload)
    app.dependency_overrides.clear()

    assert response.status_code == 403
    assert "limited to 365 days" in response.json()["detail"]


def test_tier_gating_intraday_lookback_violation(monkeypatch, make_engine_results):
    from argus.api.auth import check_rate_limit

    mock_user_free = UserResponse(
        id="test-free-uuid",
        email="free@example.com",
        is_admin=False,
        subscription_tier="free",
        theme="dark",
        lang="en",
        backtest_quota=50,
        remaining_quota=50,
    )
    app.dependency_overrides[check_rate_limit] = lambda: mock_user_free
    app.dependency_overrides[get_stock_data_client] = lambda: MagicMock()
    app.dependency_overrides[get_crypto_data_client] = lambda: MagicMock()
    fetcher_mock = MagicMock()
    fetcher_mock.validate_asset.return_value = (True, "equity")
    app.dependency_overrides[get_alpaca_fetcher] = lambda: fetcher_mock

    # Mock memory for this test
    mock_mem = MagicMock()
    mock_mem.available = 80 * 1024 * 1024
    mock_mem.total = 100 * 1024 * 1014
    monkeypatch.setattr("psutil.virtual_memory", lambda: mock_mem)
    monkeypatch.setattr(
        "argus.api.main.persistence_service.save_strategy",
        lambda *args, **kwargs: {"id": "mock-strat-id"},
    )
    monkeypatch.setattr(
        "argus.api.main.persistence_service.save_simulation",
        lambda *args, **kwargs: "mock-sim-id",
    )

    payload = {
        "symbols": ["BTC/USD"],
        "timeframe": "1Hour",
        "start_date": "2024-01-01T00:00:00Z",  # Free tier intraday lookback is 3 days
        "end_date": "2024-01-05T00:00:00Z",
        "strategy_id": None,
        "name": "E2E Strategy",
        "entry_criteria": [],
    }

    response = client.post("/api/v1/backtests", json=payload)
    app.dependency_overrides.clear()

    assert response.status_code == 403
    assert "limited to 3 days" in response.json()["detail"]
