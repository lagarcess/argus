import re

with open("src/argus/analysis/structural.py", "r") as f:
    content = f.read()

# Add a one bar mock dual sim sequence to warmup_jit
dummy_seq = """def warmup_jit() -> None:
    \"\"\"Pre-compile Numba JIT functions to avoid first-call latency.

    Call this during application startup (e.g., in main.py or health check)
    to ensure the JIT compilation happens before live trading runs.
    \"\"\"
    # Small dummy arrays to trigger compilation
    dummy_highs = np.array([100.0, 105.0, 102.0, 108.0, 103.0], dtype=np.float64).reshape(-1, 1)
    dummy_lows = np.array([95.0, 100.0, 98.0, 102.0, 99.0], dtype=np.float64).reshape(-1, 1)
    dummy_indices = np.arange(5, dtype=np.float64)
    dummy_prices = np.array([100.0, 103.0, 99.0, 106.0, 101.0], dtype=np.float64)

    # Trigger JIT compilation of core functions
    _zigzag_batch(dummy_highs, dummy_lows, 0.05)
    _fast_pip_core(dummy_indices, dummy_prices, 3)
    _perpendicular_distance(1.0, 100.0, 0.0, 95.0, 4.0, 101.0)
"""

content = re.sub(
    r"def warmup_jit\(\) -> None:[\s\S]*?_perpendicular_distance\(1\.0, 100\.0, 0\.0, 95\.0, 4\.0, 101\.0\)",
    dummy_seq,
    content,
)

with open("src/argus/analysis/structural.py", "w") as f:
    f.write(content)
