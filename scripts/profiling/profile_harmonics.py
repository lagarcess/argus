import time
from datetime import datetime, timedelta

import numpy as np
from crypto_signals.analysis.harmonics import HarmonicAnalyzer
from crypto_signals.analysis.structural import Pivot


def main():
    """Sets up data and times the harmonic pattern scan."""
    # Generate some dummy pivots
    start_time = datetime(2023, 1, 1)
    pivots = []
    np.random.seed(42)
    prices = np.random.lognormal(mean=0, sigma=0.01, size=100)
    prices = 100 * np.cumprod(prices)
    for i in range(100):
        timestamp = start_time + timedelta(days=i)
        pivot_type = "PEAK" if i % 2 == 0 else "VALLEY"
        pivots.append(
            Pivot(timestamp=timestamp, price=prices[i], pivot_type=pivot_type, index=i)
        )

    analyzer = HarmonicAnalyzer(pivots)

    start = time.perf_counter()
    patterns = analyzer.scan_all_patterns()
    end = time.perf_counter()

    print(f"Time taken for scan_all_patterns: {(end - start) * 1000:.3f} ms")
    print(f"Number of patterns found: {len(patterns)}")


if __name__ == "__main__":
    main()
