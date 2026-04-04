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
