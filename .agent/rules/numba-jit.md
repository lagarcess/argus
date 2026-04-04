---
description: Numba JIT Rules (Model Decision - Trigger on any task modifying src/crypto_signals/analysis/**/*.py)
---

# Numba JIT Rules

You are editing code in the `analysis` directory. This is the mathematical core of the engine, optimized with Numba Just-In-Time compiling.

## 1. No External Dependencies inside JIT
- Numba `@njit` compiling will fail if you use external Python objects (like Pandas DataFrames, lists of dicts, or custom classes) inside the compiled function.
- **Rule**: The function signature of an `@njit` decorated function must be strictly primitive types (float, int, bool) and NumPy arrays (`np.ndarray`).

## 2. JIT Warmup Requirement
- Numba compiles functions on their *first execution*. This causes a massive latency spike on the first run.
- **Rule**: If you add a new `@njit` function, you MUST add a corresponding "warmup" call in the `warmup_jit()` function (or module initialization block) to trigger compilation at startup, before real market data arrives.

## 3. Performance First
- Loop unrolling and pure mathematical logic are preferred here.
- Avoid allocating large temporary arrays inside the JIT function loop if possible.
