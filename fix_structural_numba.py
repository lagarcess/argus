import re

with open("src/argus/analysis/structural.py", "r") as f:
    content = f.read()

# Add numba.prange import
if "from numba import njit, prange" not in content:
    content = content.replace("from numba import njit", "from numba import njit, prange")

# Replace _zigzag_core with _zigzag_batch again since it seems to have been lost
zigzag_batch = """
# PERFORMANCE: fastmath=True allows aggressive LLVM mathematical optimizations.
# parallel=True and prange allow parallel execution across the Asset dimension.
@njit(parallel=True, fastmath=True, cache=True)
def _zigzag_batch(highs: np.ndarray, lows: np.ndarray, pct_threshold: float) -> np.ndarray:
    \"\"\"Batch ZigZag algorithm processing multiple assets concurrently.

    Args:
        highs: 2D array of high prices (Time x Assets)
        lows: 2D array of low prices (Time x Assets)
        pct_threshold: Minimum percentage change to register a reversal

    Returns:
        3D array of shape (Assets, Time, 3) containing [index, price, type] for each pivot.
        Type: 1 = PEAK, 2 = VALLEY. Rows with type 0 are empty/unused.
    \"\"\"
    n_time, n_assets = highs.shape

    # Pre-allocate output for all assets
    result = np.zeros((n_assets, n_time, 3), dtype=np.float64)

    for a in prange(n_assets):
        asset_highs = highs[:, a]
        asset_lows = lows[:, a]

        pivot_count = 0
        trend = 0
        last_high_idx = 0
        last_high_val = asset_highs[0]
        last_low_idx = 0
        last_low_val = asset_lows[0]

        for i in range(1, n_time):
            current_high = asset_highs[i]
            current_low = asset_lows[i]

            if trend == 0:
                if current_high > last_high_val:
                    last_high_idx = i
                    last_high_val = current_high
                if current_low < last_low_val:
                    last_low_idx = i
                    last_low_val = current_low

                up_pct = (last_high_val - asset_lows[0]) / asset_lows[0] if asset_lows[0] > 0 else 0
                down_pct = (asset_highs[0] - last_low_val) / asset_highs[0] if asset_highs[0] > 0 else 0

                if up_pct >= pct_threshold:
                    result[a, pivot_count, 0] = 0
                    result[a, pivot_count, 1] = asset_lows[0]
                    result[a, pivot_count, 2] = _VALLEY
                    pivot_count += 1
                    trend = 1
                elif down_pct >= pct_threshold:
                    result[a, pivot_count, 0] = 0
                    result[a, pivot_count, 1] = asset_highs[0]
                    result[a, pivot_count, 2] = _PEAK
                    pivot_count += 1
                    trend = -1
            elif trend == 1:
                if current_high > last_high_val:
                    last_high_idx = i
                    last_high_val = current_high

                down_pct = (last_high_val - current_low) / last_high_val if last_high_val > 0 else 0
                if down_pct >= pct_threshold:
                    result[a, pivot_count, 0] = last_high_idx
                    result[a, pivot_count, 1] = last_high_val
                    result[a, pivot_count, 2] = _PEAK
                    pivot_count += 1
                    trend = -1
                    last_low_idx = i
                    last_low_val = current_low
            elif trend == -1:
                if current_low < last_low_val:
                    last_low_idx = i
                    last_low_val = current_low

                up_pct = (current_high - last_low_val) / last_low_val if last_low_val > 0 else 0
                if up_pct >= pct_threshold:
                    result[a, pivot_count, 0] = last_low_idx
                    result[a, pivot_count, 1] = last_low_val
                    result[a, pivot_count, 2] = _VALLEY
                    pivot_count += 1
                    trend = 1
                    last_high_idx = i
                    last_high_val = current_high

        # Add final point as a pivot
        if trend == 1:
            result[a, pivot_count, 0] = last_high_idx
            result[a, pivot_count, 1] = last_high_val
            result[a, pivot_count, 2] = _PEAK
        elif trend == -1:
            result[a, pivot_count, 0] = last_low_idx
            result[a, pivot_count, 1] = last_low_val
            result[a, pivot_count, 2] = _VALLEY

    return result
"""

# Try to find and replace _zigzag_core
pattern = re.compile(r"# PERFORMANCE: fastmath=True.*?(?=\n@njit|\Z)", re.DOTALL)
content = pattern.sub(zigzag_batch, content, count=1)

with open("src/argus/analysis/structural.py", "w") as f:
    f.write(content)
