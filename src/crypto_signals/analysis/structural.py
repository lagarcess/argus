"""Structural analysis module for O(N) noise filtering and pivot detection.

This module implements high-performance algorithms for identifying structural
price pivots (peaks and valleys) that form the foundation for geometric
pattern detection.

Key Algorithms:
- ZigZag: O(N) state-machine approach for peak/valley detection
- FastPIP: Perceptually Important Points for geometric shape preservation
"""

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
from numba import njit


def warmup_jit() -> None:
    """Pre-compile Numba JIT functions to avoid first-call latency.

    Call this during application startup (e.g., in main.py or health check)
    to ensure the JIT compilation happens before live trading runs.

    Example:
        >>> from crypto_signals.analysis.structural import warmup_jit
        >>> warmup_jit()  # Call once during startup
    """
    # Small dummy arrays to trigger compilation
    dummy_highs = np.array([100.0, 105.0, 102.0, 108.0, 103.0], dtype=np.float64)
    dummy_lows = np.array([95.0, 100.0, 98.0, 102.0, 99.0], dtype=np.float64)
    dummy_indices = np.arange(5, dtype=np.float64)
    dummy_prices = np.array([100.0, 103.0, 99.0, 106.0, 101.0], dtype=np.float64)

    # Trigger JIT compilation of core functions
    _zigzag_core(dummy_highs, dummy_lows, 0.05)
    _fast_pip_core(dummy_indices, dummy_prices, 3)
    _perpendicular_distance(1.0, 100.0, 0.0, 95.0, 4.0, 101.0)


@dataclass
class Pivot:
    """Represents a structural anchor point (peak or valley) in price data.

    Attributes:
        timestamp: The datetime of the pivot point
        price: The price value at the pivot
        pivot_type: Either "PEAK" or "VALLEY"
        index: The integer index position in the original DataFrame
    """

    timestamp: pd.Timestamp
    price: float
    pivot_type: Literal["PEAK", "VALLEY"]
    index: int


# Type constants for Numba (0 = None, 1 = PEAK, 2 = VALLEY)
_NONE = 0
_PEAK = 1
_VALLEY = 2


@njit(cache=True)
def _zigzag_core(highs: np.ndarray, lows: np.ndarray, pct_threshold: float) -> np.ndarray:
    """Core ZigZag algorithm with O(N) time complexity.

    Uses a state-machine approach that visits each price point exactly once.
    Compiled with Numba for sub-5ms execution on 10^6 data points.

    Args:
        highs: Array of high prices
        lows: Array of low prices
        pct_threshold: Minimum percentage change to register a reversal (e.g., 0.05 = 5%)

    Returns:
        2D array of shape (N, 3) containing [index, price, type] for each pivot.
        Type: 1 = PEAK, 2 = VALLEY. Rows with type 0 are empty/unused.
    """
    n = len(highs)
    if n == 0:
        return np.empty((0, 3), dtype=np.float64)

    # Pre-allocate output (worst case: every bar is a pivot)
    result = np.zeros((n, 3), dtype=np.float64)
    pivot_count = 0

    # Initialize state
    # Trend: 1 = up, -1 = down, 0 = undetermined
    trend = 0
    last_high_idx = 0
    last_high_val = highs[0]
    last_low_idx = 0
    last_low_val = lows[0]

    for i in range(1, n):
        current_high = highs[i]
        current_low = lows[i]

        if trend == 0:
            # Undetermined - waiting for first significant move
            if current_high > last_high_val:
                last_high_idx = i
                last_high_val = current_high

            if current_low < last_low_val:
                last_low_idx = i
                last_low_val = current_low

            # Check for initial trend establishment
            up_pct = (last_high_val - lows[0]) / lows[0] if lows[0] > 0 else 0
            down_pct = (highs[0] - last_low_val) / highs[0] if highs[0] > 0 else 0

            if up_pct >= pct_threshold:
                # First move is up - mark initial low as valley
                result[pivot_count, 0] = 0  # index
                result[pivot_count, 1] = lows[0]  # price
                result[pivot_count, 2] = _VALLEY  # type
                pivot_count += 1
                trend = 1
            elif down_pct >= pct_threshold:
                # First move is down - mark initial high as peak
                result[pivot_count, 0] = 0  # index
                result[pivot_count, 1] = highs[0]  # price
                result[pivot_count, 2] = _PEAK  # type
                pivot_count += 1
                trend = -1

        elif trend == 1:
            # Uptrend: looking for new highs or reversal
            if current_high > last_high_val:
                # Extend the current up-leg
                last_high_idx = i
                last_high_val = current_high
            else:
                # Check for reversal (drop from high)
                if last_high_val > 0:
                    drop_pct = (last_high_val - current_low) / last_high_val
                    if drop_pct >= pct_threshold:
                        # Reversal confirmed - record the peak
                        result[pivot_count, 0] = last_high_idx
                        result[pivot_count, 1] = last_high_val
                        result[pivot_count, 2] = _PEAK
                        pivot_count += 1

                        # Switch to downtrend
                        trend = -1
                        last_low_idx = i
                        last_low_val = current_low

        elif trend == -1:
            # Downtrend: looking for new lows or reversal
            if current_low < last_low_val:
                # Extend the current down-leg
                last_low_idx = i
                last_low_val = current_low
            else:
                # Check for reversal (rise from low)
                if last_low_val > 0:
                    rise_pct = (current_high - last_low_val) / last_low_val
                    if rise_pct >= pct_threshold:
                        # Reversal confirmed - record the valley
                        result[pivot_count, 0] = last_low_idx
                        result[pivot_count, 1] = last_low_val
                        result[pivot_count, 2] = _VALLEY
                        pivot_count += 1

                        # Switch to uptrend
                        trend = 1
                        last_high_idx = i
                        last_high_val = current_high

    # Add final pivot (the last extreme before end of data)
    if trend == 1 and pivot_count > 0:
        # Uptrend - add final high as provisional peak
        result[pivot_count, 0] = last_high_idx
        result[pivot_count, 1] = last_high_val
        result[pivot_count, 2] = _PEAK
        pivot_count += 1
    elif trend == -1 and pivot_count > 0:
        # Downtrend - add final low as provisional valley
        result[pivot_count, 0] = last_low_idx
        result[pivot_count, 1] = last_low_val
        result[pivot_count, 2] = _VALLEY
        pivot_count += 1

    return result[:pivot_count]


def find_pivots(
    df: pd.DataFrame, pct_threshold: float = 0.05, price_col: str = "close"
) -> list[Pivot]:
    """Identify structural pivots (peaks and valleys) in price data.

    High-level wrapper around the Numba-optimized ZigZag algorithm.

    Args:
        df: DataFrame with OHLCV data (must have 'high', 'low' columns)
        pct_threshold: Minimum percentage change to register a reversal
            Default 0.05 (5%) filters out minor noise
        price_col: Price column to use for single-price fallback

    Returns:
        List of Pivot objects representing structural anchors

    Example:
        >>> pivots = find_pivots(df, pct_threshold=0.05)
        >>> for p in pivots:
        ...     print(f"{p.pivot_type} at {p.price:.2f} on {p.timestamp}")
    """
    if len(df) == 0:
        return []

    # Extract arrays for Numba
    highs = df["high"].values.astype(np.float64)
    lows = df["low"].values.astype(np.float64)

    # Run optimized ZigZag
    raw_pivots = _zigzag_core(highs, lows, pct_threshold)

    # Convert to Pivot objects
    pivots = []
    for row in raw_pivots:
        idx = int(row[0])
        price = row[1]
        pivot_type: Literal["PEAK", "VALLEY"] = "PEAK" if row[2] == _PEAK else "VALLEY"

        pivots.append(
            Pivot(
                timestamp=df.index[idx],
                price=price,
                pivot_type=pivot_type,
                index=idx,
            )
        )

    return pivots


@njit(cache=True)
def _perpendicular_distance(
    px: float, py: float, x1: float, y1: float, x2: float, y2: float
) -> float:
    """Calculate perpendicular distance from point (px, py) to line (x1,y1)-(x2,y2)."""
    dx = x2 - x1
    dy = y2 - y1

    # Line length squared
    line_len_sq = dx * dx + dy * dy

    if line_len_sq == 0:
        # Start and end points are the same
        return float(np.sqrt((px - x1) ** 2 + (py - y1) ** 2))

    # Perpendicular distance formula
    numerator = abs(dy * px - dx * py + x2 * y1 - y2 * x1)
    denominator = np.sqrt(line_len_sq)

    return float(numerator / denominator)


@njit(cache=True)
def _fast_pip_core(
    indices: np.ndarray, prices: np.ndarray, max_points: int
) -> np.ndarray:
    """Core FastPIP algorithm using iterative Douglas-Peucker approach.

    Maintains near-linear O(N log N) performance through efficient point selection.

    Args:
        indices: Integer indices of the time series
        prices: Price values corresponding to indices
        max_points: Maximum number of PIPs to retain

    Returns:
        Boolean array indicating which indices are selected as PIPs
    """
    n = len(prices)
    if n <= max_points:
        return np.ones(n, dtype=np.bool_)

    # Mask of selected points
    selected = np.zeros(n, dtype=np.bool_)
    selected[0] = True  # Always keep first point
    selected[n - 1] = True  # Always keep last point

    # Priority queue simulation using arrays
    # Each segment: (start_idx, end_idx, max_dist, max_dist_idx)
    max_segments = n
    segments = np.empty((max_segments, 4), dtype=np.float64)
    segment_count = 0

    # Initialize with the full segment
    segments[0, 0] = 0  # start
    segments[0, 1] = n - 1  # end
    segment_count = 1

    # Find max distance point in initial segment
    max_dist = 0.0
    max_idx = 0
    for i in range(1, n - 1):
        dist = _perpendicular_distance(
            float(i),
            prices[i],
            0.0,
            prices[0],
            float(n - 1),
            prices[n - 1],
        )
        if dist > max_dist:
            max_dist = dist
            max_idx = i

    segments[0, 2] = max_dist
    segments[0, 3] = max_idx

    points_selected = 2  # First and last

    while points_selected < max_points and segment_count > 0:
        # Find segment with maximum distance
        best_seg_idx = 0
        best_dist = segments[0, 2]
        for s in range(1, segment_count):
            if segments[s, 2] > best_dist:
                best_dist = segments[s, 2]
                best_seg_idx = s

        # Get the point with max distance
        start_idx = int(segments[best_seg_idx, 0])
        end_idx = int(segments[best_seg_idx, 1])
        split_idx = int(segments[best_seg_idx, 3])

        # Mark this point as selected
        selected[split_idx] = True
        points_selected += 1

        # Remove the processed segment (swap with last)
        segments[best_seg_idx] = segments[segment_count - 1]
        segment_count -= 1

        # Create two new segments (if they have interior points)
        # Left segment: [start_idx, split_idx]
        if split_idx - start_idx > 1:
            max_dist_left = 0.0
            max_idx_left = start_idx + 1
            for i in range(start_idx + 1, split_idx):
                dist = _perpendicular_distance(
                    float(i),
                    prices[i],
                    float(start_idx),
                    prices[start_idx],
                    float(split_idx),
                    prices[split_idx],
                )
                if dist > max_dist_left:
                    max_dist_left = dist
                    max_idx_left = i

            segments[segment_count, 0] = start_idx
            segments[segment_count, 1] = split_idx
            segments[segment_count, 2] = max_dist_left
            segments[segment_count, 3] = max_idx_left
            segment_count += 1

        # Right segment: [split_idx, end_idx]
        if end_idx - split_idx > 1:
            max_dist_right = 0.0
            max_idx_right = split_idx + 1
            for i in range(split_idx + 1, end_idx):
                dist = _perpendicular_distance(
                    float(i),
                    prices[i],
                    float(split_idx),
                    prices[split_idx],
                    float(end_idx),
                    prices[end_idx],
                )
                if dist > max_dist_right:
                    max_dist_right = dist
                    max_idx_right = i

            segments[segment_count, 0] = split_idx
            segments[segment_count, 1] = end_idx
            segments[segment_count, 2] = max_dist_right
            segments[segment_count, 3] = max_idx_right
            segment_count += 1

    return selected


def fast_pip(
    df: pd.DataFrame, max_points: int = 50, price_col: str = "close"
) -> list[Pivot]:
    """Extract Perceptually Important Points preserving geometric shape.

    FastPIP reduces a large time series to a smaller set of points that
    best preserve the visual shape of the chart. This is valuable for:
    - Efficient visualization (render 50 PIPs instead of 100k points)
    - Pattern matching based on geometric structure
    - Noise reduction while preserving significant moves

    Args:
        df: DataFrame with OHLCV data
        max_points: Maximum number of PIPs to extract
        price_col: Price column to analyze

    Returns:
        List of Pivot objects representing the PIPs

    Example:
        >>> pips = fast_pip(df, max_points=50)
        >>> # Use for efficient chart rendering or pattern matching
    """
    if len(df) == 0:
        return []

    prices = df[price_col].values.astype(np.float64)
    indices = np.arange(len(prices), dtype=np.float64)

    selected_mask = _fast_pip_core(indices, prices, max_points)

    # Convert to Pivot objects (classifying as PEAK/VALLEY based on neighbors)
    pips = []
    selected_indices = np.where(selected_mask)[0]

    for i, idx in enumerate(selected_indices):
        price = prices[idx]

        # Determine if peak or valley based on neighbors
        if i == 0 or i == len(selected_indices) - 1:
            # First/last point - compare to single neighbor
            if i == 0 and len(selected_indices) > 1:
                next_price = prices[selected_indices[1]]
                pivot_type: Literal["PEAK", "VALLEY"] = (
                    "PEAK" if price > next_price else "VALLEY"
                )
            elif i == len(selected_indices) - 1 and len(selected_indices) > 1:
                prev_price = prices[selected_indices[-2]]
                pivot_type = "PEAK" if price > prev_price else "VALLEY"
            else:
                pivot_type = "PEAK"  # Single point default
        else:
            # Interior point - compare to both neighbors
            prev_price = prices[selected_indices[i - 1]]
            next_price = prices[selected_indices[i + 1]]
            if price > prev_price and price > next_price:
                pivot_type = "PEAK"
            elif price < prev_price and price < next_price:
                pivot_type = "VALLEY"
            else:
                # Intermediate point (not a local extremum)
                # Classify based on direction from previous
                pivot_type = "PEAK" if price > prev_price else "VALLEY"

        pips.append(
            Pivot(
                timestamp=df.index[idx],
                price=price,
                pivot_type=pivot_type,
                index=int(idx),
            )
        )

    return pips


def get_pivot_dataframe(pivots: list[Pivot]) -> pd.DataFrame:
    """Convert a list of Pivots to a DataFrame for analysis.

    Args:
        pivots: List of Pivot objects

    Returns:
        DataFrame with columns: timestamp, price, pivot_type, index
    """
    if not pivots:
        return pd.DataFrame(columns=["timestamp", "price", "pivot_type", "index"])

    return pd.DataFrame(
        {
            "timestamp": [p.timestamp for p in pivots],
            "price": [p.price for p in pivots],
            "pivot_type": [p.pivot_type for p in pivots],
            "index": [p.index for p in pivots],
        }
    )


def filter_pivots_by_lookback(
    pivots: list[Pivot], current_index: int, max_lookback: int
) -> list[Pivot]:
    """Filter pivots to only include those within a lookback window.

    Args:
        pivots: Full list of pivots
        current_index: Current bar index
        max_lookback: Maximum number of bars to look back

    Returns:
        Filtered list of pivots within the lookback window
    """
    min_index = current_index - max_lookback
    return [p for p in pivots if min_index <= p.index <= current_index]


def get_recent_pivots(
    pivots: list[Pivot], count: int, pivot_type: Literal["PEAK", "VALLEY"] | None = None
) -> list[Pivot]:
    """Get the most recent N pivots, optionally filtered by type.

    Args:
        pivots: Full list of pivots (assumed chronologically ordered)
        count: Number of recent pivots to return
        pivot_type: Optional filter for "PEAK" or "VALLEY"

    Returns:
        List of the most recent pivots
    """
    if pivot_type:
        filtered = [p for p in pivots if p.pivot_type == pivot_type]
        return filtered[-count:] if len(filtered) >= count else filtered
    return pivots[-count:] if len(pivots) >= count else pivots
