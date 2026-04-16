import asyncio
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

    def _make_df(self, start, periods=100):
        start_naive = pd.to_datetime(start).replace(tzinfo=None)
        dates = pd.date_range(
            start=start_naive, periods=periods, freq="h", tz=timezone.utc
        )
        return pd.DataFrame(
            {
                "open": np.random.uniform(40000, 45000, periods),
                "high": np.random.uniform(45000, 46000, periods),
                "low": np.random.uniform(39000, 40000, periods),
                "close": np.random.uniform(40000, 45000, periods),
                "volume": np.random.uniform(1, 10, periods),
                "vwap": np.random.uniform(40000, 45000, periods),
            },
            index=dates,
        )

    def fetch_bars(self, symbol, timeframe, start, end=None):
        return self._make_df(start)

    def get_historical_bars(self, symbol, asset_class, timeframe_str, start_dt, end_dt):
        """MarketDataProvider-compatible interface used by ArgusEngine._run_single_symbol."""
        return self._make_df(start_dt)

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


def test_startup_skips_jit_warmup():
    from argus.api import main as api_main

    assert not hasattr(api_main, "warmup_jit")


def test_lifespan_primes_assets_only_in_production(monkeypatch):
    from types import SimpleNamespace

    from argus.api import main as api_main

    create_task_mock = MagicMock()

    def fake_create_task(coro):
        coro.close()
        return create_task_mock(coro)

    monkeypatch.setattr(api_main.asyncio, "create_task", fake_create_task)
    monkeypatch.setattr(
        api_main,
        "get_settings",
        lambda: SimpleNamespace(APP_ENV="production"),
    )
    mock_fetcher = MagicMock()
    mock_fetcher.get_active_assets.return_value = []
    monkeypatch.setattr(api_main, "get_alpaca_fetcher", lambda: mock_fetcher)

    async def run_lifespan():
        async with api_main.lifespan(api_main.app):
            pass

    asyncio.run(run_lifespan())

    assert create_task_mock.call_count == 1


def test_lifespan_skips_asset_priming_outside_production(monkeypatch):
    from types import SimpleNamespace

    from argus.api import main as api_main

    create_task_mock = MagicMock()
    monkeypatch.setattr(api_main.asyncio, "create_task", create_task_mock)
    monkeypatch.setattr(
        api_main,
        "get_settings",
        lambda: SimpleNamespace(APP_ENV="development"),
    )

    async def run_lifespan():
        async with api_main.lifespan(api_main.app):
            pass

    asyncio.run(run_lifespan())

    assert create_task_mock.call_count == 0


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
            None,
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
    from argus.api.main import (
        get_alpaca_fetcher,
        get_crypto_data_client,
        get_stock_data_client,
    )

    app.dependency_overrides[check_rate_limit] = lambda: mock_user
    app.dependency_overrides[get_alpaca_fetcher] = lambda: MagicMock()
    app.dependency_overrides[get_stock_data_client] = lambda: MagicMock()
    app.dependency_overrides[get_crypto_data_client] = lambda: MagicMock()

    # Neither ID nor inline
    response = client.post("/api/v1/backtests", json={})
    assert response.status_code == 422

    # Both ID and inline
    response = client.post(
        "/api/v1/backtests",
        json={
            "strategy_id": "123",
            "symbols": ["BTC/USDT"],
            "timeframe": "1h",
            "start_date": "2025-01-01T00:00:00Z",
            "end_date": "2025-02-01T00:00:00Z",
        },
    )
    assert response.status_code == 422


def test_backtest_endpoint_success(monkeypatch, mock_user, make_engine_results):
    from argus.api.auth import check_rate_limit
    from argus.api.main import (
        get_alpaca_fetcher,
        get_crypto_data_client,
        get_stock_data_client,
    )
    from argus.engine import EngineBacktestResults

    app.dependency_overrides[check_rate_limit] = lambda: mock_user
    app.dependency_overrides[get_alpaca_fetcher] = lambda: MockAlpacaFetcher()
    app.dependency_overrides[get_stock_data_client] = lambda: MagicMock()
    app.dependency_overrides[get_crypto_data_client] = lambda: MagicMock()

    # Mock memory to prevent 503 Service Unavailable guard from triggering
    mock_mem = MagicMock()
    mock_mem.available = 800 * 1024 * 1024
    mock_mem.total = 1000 * 1024 * 1024  # 80% available
    monkeypatch.setattr("psutil.virtual_memory", lambda: mock_mem)

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
            "symbols": ["BTC/USDT"],
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
    assert data["results"]["win_rate"] == 62.0
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


def test_get_session(monkeypatch, mock_user):
    from argus.api.auth import auth_required

    monkeypatch.setitem(app.dependency_overrides, auth_required, lambda: mock_user)
    response = client.get("/api/v1/auth/session")
    assert response.status_code == 200
    assert response.json()["email"] == mock_user.email


def test_get_usage(monkeypatch, mock_user):
    from argus.api.auth import check_rate_limit

    monkeypatch.setitem(app.dependency_overrides, check_rate_limit, lambda: mock_user)
    response = client.get("/api/v1/usage")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 0
    assert data["limit"] == 50
    assert data["tier"] == "free"


def test_sso_login(monkeypatch):
    import faker

    fake = faker.Faker()
    url = fake.url()

    mock_auth_res = MagicMock()
    mock_auth_res.url = url

    # Needs to mock the auth.sign_in_with_oauth call
    mock_supabase = MagicMock()
    mock_supabase.auth.sign_in_with_oauth.return_value = mock_auth_res
    monkeypatch.setattr("argus.api.main.supabase_client", mock_supabase)

    response = client.post(
        "/api/v1/auth/sso",
        json={"provider": "google", "redirect_to": "http://localhost:3000/auth/callback"},
    )
    assert response.status_code == 200
    assert response.json()["auth_url"] == url

    # Test Exception handling for conflict
    mock_supabase.auth.sign_in_with_oauth.side_effect = Exception(
        "User already linked via conflict"
    )
    response_conflict = client.post(
        "/api/v1/auth/sso",
        json={"provider": "google", "redirect_to": "http://localhost:3000/auth/callback"},
    )
    assert response_conflict.status_code == 409

    # Test Exception handling for generic error
    mock_supabase.auth.sign_in_with_oauth.side_effect = Exception(
        "Generic internal error"
    )
    response_generic = client.post(
        "/api/v1/auth/sso",
        json={"provider": "google", "redirect_to": "http://localhost:3000/auth/callback"},
    )
    assert response_generic.status_code == 500

    # Test missing supabase
    monkeypatch.setattr("argus.api.main.supabase_client", None)
    response_missing = client.post(
        "/api/v1/auth/sso",
        json={"provider": "google", "redirect_to": "http://localhost:3000/auth/callback"},
    )
    assert response_missing.status_code == 500


def test_update_profile(monkeypatch, mock_user):
    import faker
    from argus.api.auth import auth_required

    fake = faker.Faker()
    theme = fake.word()
    lang = fake.language_code()

    monkeypatch.setitem(app.dependency_overrides, auth_required, lambda: mock_user)

    mock_supabase = MagicMock()
    mock_execute = MagicMock()
    # Mock update to return data
    mock_execute.execute.return_value.data = [{"theme": theme, "lang": lang}]
    mock_supabase.table.return_value.update.return_value.eq.return_value = mock_execute
    monkeypatch.setattr("argus.api.main.supabase_client", mock_supabase)

    # Mock user cache invalidation
    mock_invalidate = MagicMock()
    monkeypatch.setattr("argus.api.main._user_cache.invalidate", mock_invalidate)

    response = client.patch("/api/v1/auth/profile", json={"theme": theme, "lang": lang})
    assert response.status_code == 200
    assert response.json()["theme"] == theme
    assert response.json()["lang"] == lang
    mock_invalidate.assert_called_once_with(mock_user.id)

    # Test empty update
    response_empty = client.patch("/api/v1/auth/profile", json={})
    assert response_empty.status_code == 200

    # Test update not found
    mock_execute.execute.return_value.data = []
    response_not_found = client.patch("/api/v1/auth/profile", json={"theme": "dark"})
    assert response_not_found.status_code == 404

    # Test exception handling
    mock_execute.execute.side_effect = Exception("DB error")
    response_db_err = client.patch("/api/v1/auth/profile", json={"theme": "dark"})
    assert response_db_err.status_code == 500

    # Test missing supabase
    monkeypatch.setattr("argus.api.main.supabase_client", None)
    response_missing = client.patch("/api/v1/auth/profile", json={"theme": "light"})
    assert response_missing.status_code == 500


def test_logout(monkeypatch):
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 204


def test_get_simulation_detail(monkeypatch, mock_user):
    import faker
    from argus.api.auth import auth_required

    fake = faker.Faker()
    sim_id = f"sim_{fake.uuid4()}"
    strat_name = fake.sentence(nb_words=3)

    monkeypatch.setitem(app.dependency_overrides, auth_required, lambda: mock_user)

    # Mock persistence
    monkeypatch.setattr(
        "argus.api.main.persistence_service.get_simulation",
        lambda query_sim_id, user_id: {
            "id": query_sim_id,
            "strategy_name": strat_name,
            "symbols": ["BTC"],
            "timeframe": "1h",
            "summary": {"total_return_pct": 10.0},
        }
        if query_sim_id == sim_id
        else None,
    )

    response = client.get(f"/api/v1/simulations/{sim_id}")
    assert response.status_code == 200
    assert response.json()["id"] == sim_id

    # Test not found
    response_not_found = client.get("/api/v1/simulations/sim_999")
    assert response_not_found.status_code == 404

    # Test "latest" fallback
    monkeypatch.setattr(
        "argus.api.main.persistence_service.get_user_simulations",
        lambda user_id, limit, cursor=None: (
            [{"id": "sim_latest"}],
            1,
            None,
        ),
    )
    monkeypatch.setattr(
        "argus.api.main.persistence_service.get_simulation",
        lambda query_sim_id, user_id: {
            "id": query_sim_id,
        }
        if query_sim_id == "sim_latest"
        else None,
    )
    response_latest = client.get("/api/v1/simulations/latest")
    assert response_latest.status_code == 200
    assert response_latest.json()["id"] == "sim_latest"

    # Test exception handling
    monkeypatch.setattr(
        "argus.api.main.persistence_service.get_simulation",
        MagicMock(side_effect=Exception("Database down")),
    )
    response_error = client.get(f"/api/v1/simulations/{sim_id}")
    assert response_error.status_code == 500


def test_backtest(monkeypatch, mock_user):
    """
    High-fidelity E2E test integrated into test_api.py.
    Verifies full Engine-to-Response logic flow using MockAlpacaFetcher.
    """
    from argus.api.auth import check_rate_limit
    from argus.api.main import (
        get_alpaca_fetcher,
        get_crypto_data_client,
        get_stock_data_client,
    )

    app.dependency_overrides[check_rate_limit] = lambda: mock_user
    app.dependency_overrides[get_alpaca_fetcher] = lambda: MockAlpacaFetcher()
    app.dependency_overrides[get_stock_data_client] = lambda: MagicMock()
    app.dependency_overrides[get_crypto_data_client] = lambda: MagicMock()

    # Mock memory to prevent 503 Service Unavailable guard from triggering
    mock_mem = MagicMock()
    mock_mem.available = 800 * 1024 * 1024
    mock_mem.total = 1000 * 1024 * 1024  # 80% available
    monkeypatch.setattr("psutil.virtual_memory", lambda: mock_mem)

    # Mock persistence
    monkeypatch.setattr(
        "argus.api.main.persistence_service.save_simulation",
        lambda **kwargs: "mock-sim-id",
    )
    monkeypatch.setattr(
        "argus.api.main.persistence_service.save_strategy",
        lambda user_id, data: {"id": "mock-strat-id"},
    )
    monkeypatch.setattr("argus.api.main.supabase_client", MagicMock())

    # Patch MarketDataProvider so the real engine gets valid OHLCV data
    _fetcher = MockAlpacaFetcher()
    monkeypatch.setattr(
        "argus.market.data_provider.MarketDataProvider.get_historical_bars",
        lambda self, symbol, asset_class, timeframe_str, start_dt, end_dt, **kw: (
            _fetcher.get_historical_bars(
                symbol, asset_class, timeframe_str, start_dt, end_dt
            )
        ),
    )

    payload = {
        "symbols": ["BTC/USD"],
        "timeframe": "1h",
        "start_date": "2024-01-01T00:00:00Z",
        "end_date": "2024-01-05T00:00:00Z",
        "strategy_id": None,
        "name": "E2E Strategy",
        "entry_criteria": [
            {"indicator": "rsi", "period": 14, "condition": "is_below", "target": 30}
        ],
        "exit_criteria": [],
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


def test_metrics_parity_history_vs_detail_same_simulation(monkeypatch, mock_user):
    from argus.api.auth import auth_required

    monkeypatch.setitem(app.dependency_overrides, auth_required, lambda: mock_user)

    simulation_id = "sim_parity_001"

    persistence_service.get_user_simulations = MagicMock(
        return_value=(
            [
                {
                    "id": simulation_id,
                    "strategy_name": "Parity Strategy",
                    "symbols": ["AAPL"],
                    "timeframe": "1h",
                    "status": "completed",
                    "total_return_pct": 8.3,
                    "sharpe_ratio": 1.2,
                    "max_drawdown_pct": 4.1,
                    "win_rate": 0.62,
                    "total_trades": 12,
                    "created_at": "2026-04-15T13:15:00Z",
                }
            ],
            1,
            None,
        )
    )

    persistence_service.get_simulation = MagicMock(
        return_value={
            "id": simulation_id,
            "summary": {
                "total_return_pct": 8.3,
                "win_rate": 0.62,
                "sharpe_ratio": 1.2,
                "sortino_ratio": 1.5,
                "calmar_ratio": 1.0,
                "profit_factor": 1.1,
                "expectancy": 0.02,
                "max_drawdown_pct": 4.1,
            },
            "full_result": {"equity_curve": [100.0, 108.3], "trades": []},
            "config_snapshot": {"symbols": ["AAPL"], "timeframe": "1h"},
            "reality_gap_metrics": {"fidelity_score": 0.91},
        }
    )

    history_response = client.get("/api/v1/history")
    detail_response = client.get(f"/api/v1/backtests/{simulation_id}")

    assert history_response.status_code == 200
    assert detail_response.status_code == 200

    history_win_rate = history_response.json()["simulations"][0]["win_rate"]
    detail_win_rate = detail_response.json()["results"]["win_rate"]

    assert history_win_rate == 0.62
    assert detail_win_rate == 0.62


def test_backtest_detail_handles_null_win_rate(monkeypatch, mock_user):
    from argus.api.auth import auth_required

    monkeypatch.setitem(app.dependency_overrides, auth_required, lambda: mock_user)

    simulation_id = "sim_null_win_rate_001"
    persistence_service.get_simulation = MagicMock(
        return_value={
            "id": simulation_id,
            "summary": {
                "total_return_pct": 3.0,
                "win_rate": None,
                "sharpe_ratio": 1.1,
                "sortino_ratio": 1.2,
                "calmar_ratio": 0.9,
                "profit_factor": 1.0,
                "expectancy": 0.01,
                "max_drawdown_pct": 2.0,
            },
            "full_result": {"equity_curve": [100.0, 103.0], "trades": []},
            "config_snapshot": {"symbols": ["AAPL"], "timeframe": "1h"},
            "reality_gap_metrics": {"fidelity_score": 0.95},
        }
    )

    response = client.get(f"/api/v1/backtests/{simulation_id}")
    assert response.status_code == 200
    assert response.json()["results"]["win_rate"] == 0.0
