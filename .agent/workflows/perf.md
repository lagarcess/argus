---
description: Benchmarks Numba JIT logic and backtest paths to catch latency spikes
---

1. **JIT Warmup Verification**
   // turbo
   - Ensure `warmup_jit()` is called successfully without crashing.
   - Run python command: `poetry run python -c "from crypto_signals.analysis.structural import warmup_jit; warmup_jit()"`

2. **Slow Test Execution**
   // turbo
   - Run tests marked with `@pytest.mark.slow`. These are typically performance benchmarks on historical datasets.
   - Execute: `poetry run pytest -m slow -v`

3. **Profiling**
   // turbo
   - If the user provides a specific entry point script or symbol, run a cProfile trace.
   - Execute: `poetry run python -m cProfile -s tottime -m crypto_signals.main --smoke-test > temp/perf/profile_results.txt` (ensure `temp/perf` exists).

4. **Analysis & Report**
   - Read `temp/perf/profile_results.txt`.
   - Identify the top 5 most expensive function calls.
   - If any domain or I/O boundary functions appear higher than the math/analysis functions, raise a warning.
   - Present a concise performance report to the user.
