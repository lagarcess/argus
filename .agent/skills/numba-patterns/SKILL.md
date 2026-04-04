---
name: Numba Patterns
description: Rules and patterns for Numba JIT-compiled code in src/argus/analysis/. Covers warmup, pure-math constraints, and performance targets.
---

# Numba JIT Patterns

## Core Rule
All functions decorated with `@njit` or `@jit(nopython=True)` in `src/argus/analysis/` must contain **pure math only**. No Python objects, no pandas, no logging inside JIT functions.

## Warmup Requirement
- Any change to `src/argus/analysis/structural.py` or any `@njit` function **must** call `warmup_jit()` in test setup.
- First JIT invocation triggers compilation (100-500ms). Second call is <1ms.
- Tests must warm up before timing benchmarks.

```python
# ✅ Correct: warmup before benchmark
def test_performance():
    warmup_jit()  # Compile first
    start = time.perf_counter()
    result = _zigzag_core(highs, lows, 0.05)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.05  # 50ms budget

# ❌ Wrong: timing includes compilation
def test_performance():
    start = time.perf_counter()
    result = _zigzag_core(highs, lows, 0.05)  # Includes 500ms compile!
```

## Pure Math Constraints
Inside `@njit` functions:
- ✅ NumPy arrays, scalars, tuples
- ✅ Simple loops, conditionals, math operations
- ❌ No `logger`, `print`, `pandas`, `pydantic`
- ❌ No string operations, dict comprehensions
- ❌ No class instantiation (except NamedTuples defined for Numba)

## Performance Targets
- ZigZag 1M points: <50ms (after warmup)
- FastPIP 100K points: <100ms (after warmup)
- Harmonic scan (15 pivots): <2ms

## Wrapper Pattern
JIT functions return raw arrays. Wrapper functions convert to Python objects:

```python
@njit
def _zigzag_core(highs, lows, threshold):
    """Pure math - returns numpy array."""
    ...

def find_pivots(df, pct_threshold=0.05):
    """Wrapper - converts to Pivot objects."""
    raw = _zigzag_core(highs, lows, pct_threshold)
    return [Pivot(...) for row in raw]
```
