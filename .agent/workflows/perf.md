---
description: Benchmark Numba JIT logic and backtest performance paths.
---

# /perf — Performance Benchmarking

1. **Warm up JIT**:
   ```python
   from argus.analysis.structural import warmup_jit
   warmup_jit()
   ```

2. **Run performance tests**:
   ```
   poetry run pytest tests/analysis/test_structural.py -v -k "Performance" --no-header
   ```

3. **Targets** (after warmup):
   | Operation | Dataset | Target |
   |-----------|---------|--------|
   | ZigZag | 1M points | <50ms |
   | FastPIP | 100K points | <100ms |
   | Harmonic scan | 15 pivots | <2ms |

4. **Report** any regressions vs targets.

> References: `numba-patterns` skill
