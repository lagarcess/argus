import numpy as np
import pandas as pd
import pytest
from crypto_signals.analysis.structural import (
    _fast_pip_core,
    _perpendicular_distance,
    _zigzag_core,
    fast_pip,
)


def test_zigzag_downward_establishment():
    """Test initial trend establishment when first move is downward."""
    highs = np.array([100.0, 95.0, 90.0, 85.0, 80.0, 85.0, 90.0], dtype=np.float64)
    lows = np.array([98.0, 93.0, 88.0, 83.0, 78.0, 83.0, 88.0], dtype=np.float64)

    # 10% move from 100 to 90 is enough if highs[0] is 100
    # down_pct = (100 - 80) / 100 = 20% > 10%
    result = _zigzag_core(highs, lows, 0.10)

    assert len(result) >= 2
    assert result[0, 2] == 1  # First is PEAK at 100
    assert result[1, 2] == 2  # Followed by VALLEY at 78


def test_zigzag_no_pivots_detected():
    """Test ZigZag with no significant moves."""
    highs = np.array([100.0, 101.0, 100.0, 101.0], dtype=np.float64)
    lows = np.array([99.0, 100.0, 99.0, 100.0], dtype=np.float64)

    result = _zigzag_core(highs, lows, 0.10)  # 10% threshold
    assert len(result) == 0


def test_perpendicular_distance_zero_length():
    """Test perpendicular distance with a zero-length line (p1 == p2)."""
    # Expected: distance from (2, 10) to point (5, 5)
    # dist = sqrt((2-5)^2 + (10-5)^2) = sqrt(3^2 + 5^2) = sqrt(34) approx 5.83
    dist = _perpendicular_distance(2.0, 10.0, 5.0, 5.0, 5.0, 5.0)
    assert dist == pytest.approx(np.sqrt(34))


def test_fast_pip_intermediate_points():
    """Test FastPIP with a monotonic line where points are intermediate."""
    prices = np.array([100.0, 110.0, 150.0, 130.0, 140.0], dtype=np.float64)

    # FastPIP always preserves endpoints.
    # Intermediate points (1, 2, 3) should be classified based on direction.
    df = pd.DataFrame(
        {"close": prices, "high": prices, "low": prices},
        index=pd.date_range("2024-01-01", periods=5),
    )
    pips = fast_pip(df, max_points=3)

    assert len(pips) == 3
    # First point 100 (VALLEY because next is 110)
    # Last point 140 (PEAK because prev is 130)
    # Mid point could be anything depending on distance, but here it's a straight line
    # Distance is 0 for all interior points on a straight line.
    # But FastPIP core might still pick one.


def test_fast_pip_small_data():
    """Test FastPIP with count <= max_points (lines 280-281)."""
    prices = np.array([100.0, 110.0], dtype=np.float64)
    indices = np.arange(2, dtype=np.float64)

    selected = _fast_pip_core(indices, prices, 5)
    assert all(selected)


def test_zigzag_final_provisional_pivots():
    """Test the final provisional pivot logic in ZigZag (lines 175-186)."""
    # Uptrend ending
    highs = np.array([100.0, 120.0, 110.0, 130.0], dtype=np.float64)
    lows = np.array([90.0, 110.0, 100.0, 120.0], dtype=np.float64)
    result = _zigzag_core(highs, lows, 0.10)
    # Should have a valley at 90, peak at 120, valley at 100, and final peak at 130
    assert result[-1, 2] == 1  # Final PEAK

    # Downtrend ending
    highs = np.array([130.0, 110.0, 120.0, 100.0], dtype=np.float64)
    lows = np.array([120.0, 100.0, 110.0, 90.0], dtype=np.float64)
    result = _zigzag_core(highs, lows, 0.10)
    # Final VALLEY
    assert result[-1, 2] == 2  # Final VALLEY
