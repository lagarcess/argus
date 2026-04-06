"""
Shared test configuration for Argus test suite.
"""

import pytest


@pytest.fixture
def sample_ohlcv_data():
    """Return a minimal OHLCV DataFrame for analysis tests."""
    import numpy as np
    import pandas as pd

    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=200, freq="D")
    close = 100 + np.cumsum(np.random.randn(200) * 2)
    high = close + np.abs(np.random.randn(200)) * 3
    low = close - np.abs(np.random.randn(200)) * 3
    open_prices = close + np.random.randn(200) * 1
    volume = np.random.randint(1000, 100000, 200).astype(float)

    return pd.DataFrame(
        {
            "open": open_prices,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        },
        index=dates,
    )


@pytest.fixture
def mock_persistence_service(mocker):
    """
    Mock the PersistenceService to avoid live network calls to Supabase.
    Ensures user_id is handled as a UUID string consistently.
    """
    from argus.domain.persistence import PersistenceService

    mock_service = mocker.Mock(spec=PersistenceService)

    # Simple ID generation for mocks
    mock_service.save_strategy.return_value = "mock_strat_123"
    mock_service.save_simulation.return_value = "mock_sim_456"

    # Match frontend interface for history
    mock_service.get_user_simulations.return_value = (
        [
            {
                "id": "mock_sim_1",
                "strategy_name": "Mock Strategy",
                "symbols": ["AAPL", "BTC-USD"],
                "timeframe": "1Day",
                "status": "completed",
                "total_return_pct": 12.5,
                "sharpe_ratio": 2.1,
                "win_rate_pct": 65.0,
                "max_drawdown_pct": -5.2,
                "total_trades": 12,
                "created_at": "2024-03-01T10:00:00Z",
            }
        ],
        1,
    )

    return mock_service
