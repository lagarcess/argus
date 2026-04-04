"""Unit tests for the indicators module."""

import pandas as pd
from crypto_signals.analysis.indicators import TechnicalIndicators


def test_add_all_indicators():
    """Test that all indicators are correctly added to the DataFrame."""
    # 1. Create Mock Data
    dates = pd.date_range(start="2023-01-01", periods=100, freq="h")
    data = {
        "open": [100.0] * 100,
        "high": [105.0] * 100,
        "low": [95.0] * 100,
        "close": [102.0] * 100,
        "volume": [1000] * 100,
    }
    df = pd.DataFrame(data, index=dates)

    # 2. Add Indicators
    df_result = TechnicalIndicators.add_all_indicators(df)

    # 3. Verify Columns Exist

    # Note: pandas-ta ATR name might vary ('ATRr_14' vs 'ATR_14').
    # Usually it is 'ATRr_14' (RMA based) or 'ATR_14' (SMA based) depending
    # on config.
    # We check if at least one variant exists or check strict names if we
    # enforced them.
    # In our implementation we let default behavior rule.
    # Let's inspect what's actually there if we fail, but for now strict check
    # on typical defaults.

    for col in ["EMA_50", "RSI_14", "VOL_SMA_20"]:
        assert col in df_result.columns, f"Column {col} missing"

    # Check ATR loosely
    assert any("ATR" in col for col in df_result.columns), "ATR column missing"
