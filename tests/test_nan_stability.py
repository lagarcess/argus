import numpy as np
import pandas as pd
import pytest
from argus.analysis.structural import fast_pip, find_pivots, warmup_jit
from loguru import logger


def test_nan_stability():
    """Verify that NaNs in input do not cause crashes or incorrect behavior under fastmath."""
    warmup_jit()

    # Create data with NaNs
    n = 100
    price = np.linspace(100, 110, n)
    price[10:20] = np.nan

    df = pd.DataFrame(
        {"high": price + 1, "low": price - 1, "close": price, "open": price},
        index=pd.date_range("2024-01-01", periods=n),
    )

    # This should NOT crash (it did before because fastmath + NaN is unstable)
    try:
        pivots = find_pivots(df, pct_threshold=0.01)
        assert len(pivots) > 0
        logger.info(
            f"NaN Stability Test Passed: Found {len(pivots)} pivots with NaN input."
        )
    except Exception as e:
        pytest.fail(f"find_pivots failed with NaNs: {e}")

    try:
        pips = fast_pip(df, max_points=10)
        assert len(pips) > 0
        logger.info(f"NaN Stability Test Passed: Found {len(pips)} PIPs with NaN input.")
    except Exception as e:
        pytest.fail(f"fast_pip failed with NaNs: {e}")


if __name__ == "__main__":
    test_nan_stability()
