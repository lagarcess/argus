import cProfile
import pstats
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from crypto_signals.analysis.indicators import TechnicalIndicators


def main():
    """Sets up data and profiles the indicator calculations."""
    n = 1000
    start_time = datetime(2023, 1, 1)
    dates = [start_time + timedelta(days=i) for i in range(n)]
    np.random.seed(42)
    prices = 100 * np.cumprod(np.random.lognormal(mean=0, sigma=0.01, size=n))
    df = pd.DataFrame(
        {
            "timestamp": dates,
            "open": prices * (1 + np.random.normal(0, 0.002, n)),
            "high": prices * (1 + np.abs(np.random.normal(0, 0.005, n))),
            "low": prices * (1 - np.abs(np.random.normal(0, 0.005, n))),
            "close": prices,
            "volume": np.random.randint(100, 10000, n).astype(float),
        }
    )
    df.set_index("timestamp", inplace=True)

    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(100):
        TechnicalIndicators.add_all_indicators(df)
    profiler.disable()

    stats = pstats.Stats(profiler).sort_stats("cumtime")
    stats.print_stats(30)


if __name__ == "__main__":
    main()
