import cProfile
import pstats
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from crypto_signals.analysis.patterns import PatternAnalyzer


def main():
    """Sets up data and profiles the pattern analysis."""
    # Create a dummy DataFrame
    n = 10000
    start_time = datetime(2023, 1, 1)
    dates = [start_time + timedelta(days=i) for i in range(n)]

    np.random.seed(42)
    prices = 100 * np.cumprod(np.random.lognormal(mean=0, sigma=0.01, size=n))
    high = prices * (1 + np.abs(np.random.normal(0, 0.005, n)))
    low = prices * (1 - np.abs(np.random.normal(0, 0.005, n)))
    open_price = prices * (1 + np.random.normal(0, 0.002, n))
    close = prices

    df = pd.DataFrame(
        {
            "timestamp": dates,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": np.random.randint(100, 10000, n).astype(float),
            "RSI_14": np.random.uniform(20, 80, n),
            "EMA_50": prices * 0.95,
            "VOL_SMA_20": np.random.uniform(500, 5000, n),
            "ATR_14": np.random.uniform(1, 5, n),
            "ATR_SMA_20": np.random.uniform(1, 5, n),
            "BBL_20_2.0": prices * 0.9,
            "MFI_14": np.random.uniform(10, 90, n),
            "KCUe_20_2.0": prices * 1.05,
        }
    )
    df.set_index("timestamp", inplace=True)

    analyzer = PatternAnalyzer(df)

    profiler = cProfile.Profile()
    profiler.enable()
    _ = analyzer.check_patterns()
    profiler.disable()

    stats = pstats.Stats(profiler).sort_stats("cumtime")
    stats.print_stats(30)


if __name__ == "__main__":
    main()
