---
description: Numba JIT warmup, pure math in analysis/, backtest speed, build speed, performance targets.
globs: ["src/argus/analysis/**/*.py", "web/**/*.ts", "web/**/*.tsx"]
---

# Performance Rule

## Math & Analysis (Python)

1. **JIT Warmup**: Any change to `src/argus/analysis/` requires `warmup_jit()` in test setup.
2. **Pure math only** inside `@njit` functions — no pandas, logger, I/O operations, or Python objects.
3. **Analysis performance targets** (after warmup):
   - ZigZag 1M points: <50ms
   - FastPIP 100K points: <100ms
   - Harmonic scan 15 pivots: <2ms
   - Wrapper functions convert raw arrays → Python objects (Pivot, etc.)

## Backtest Execution

4. **<3 second backtest guarantee**: Single-symbol backtest (1Y historical data, 1H timeframe) must complete in <3s end-to-end:
   - API request → Alpaca fetch + validation: <500ms
   - Pattern analysis + indicator calc: <1s (Numba JIT)
   - Trade simulation: <600ms
   - Response formation: <200ms

   **If backtest exceeds 3s:** Profile with `py-spy` → identify bottleneck → optimize Numba function or caching strategy.

## Frontend Build & Startup

5. **Bun build <30s**: `bun run build` for production bundle must complete in <30 seconds.
6. **Bun dev <2s startup**: `bun run dev` hot-reload on file change must render in <2 seconds.
7. **No runtime blocking operations**: All data fetches (real API or mock) must be non-blocking (React Query or async/await).

---

See: `.agent/skills/numba-patterns/SKILL.md` for JIT details, `.agent/skills/monorepo-patterns/SKILL.md` for build coordination.
