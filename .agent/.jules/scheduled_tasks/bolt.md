# Bolt ⚡ — Performance Guardian Reference

**Mission:** Identify and implement performance improvements for <3s backtest execution, <30s build time.

**Scope:** Numba analysis loops, FastAPI backtest endpoints, Next.js chart rendering, API payloads

**Focus on:**

- Compute-heavy backtest endpoints (< 3 second target)
- Numba pattern detection loops (JIT cache, vectorization)
- Strategy JSON handling (minimize copies, early returns)
- Equity curve rendering (memoization, lazy loading)
- API payload size (decimation, compression)

---

## Key Commands

**Backend Profiling:**

```bash
cd d:\Users\garce\git-repos\argus
poetry shell
poetry run pytest tests/ -v --tb=short

# Profile single backtest
poetry run python -c "
from src.argus.analysis.harmonics import detect_harmonics
import numpy as np
prices = np.random.rand(1000)
%timeit detect_harmonics(prices)
"

# Check compilation bottlenecks
python -m cProfile -s cumtime src/argus/api/main.py
```

**Frontend Performance:**

```bash
cd web
bun run dev  # Check DevTools Performance tab
bun run build && ls -lh .next/static/chunks/
```

---

## Good Patterns ✅

### Numba Caching

```python
from functools import lru_cache
import numba

@lru_cache(maxsize=128)
def get_pattern_params(pattern_name: str) -> dict:
    """Cache repeated lookups"""
    return {"gartley": {...}, "butterfly": {...}}[pattern_name]

@numba.njit(cache=True, fastmath=True)
def detect_zigzag(prices: np.ndarray) -> np.ndarray:
    """Numba caches compiled bytecode"""
    pass
```

### React Memoization

```typescript
const EquityCurve = React.memo(({ data, interval }: Props) => {
  const decimatedData = React.useMemo(() => {
    return decimate(data, interval);  // Cached computation
  }, [data, interval]);

  return <LineChart data={decimatedData} />;
});
```

### Early Return

```python
@app.post("/api/v1/backtests")
async def run_backtest(req: BacktestRequest):
    user = await get_current_user(request)

    # Exit early if quota exhausted
    if user.remaining_quota <= 0:
        return JSONResponse({"error": "quota_exceeded"}, 402)

    # Only compute if quota OK
    result = engine.run_backtest(req)
    await decrement_quota(user.id)
    return result
```

---

## Anti-Patterns ❌

❌ Repeated expensive computations in loops
❌ React re-renders entire chart on every data change
❌ Numba @njit functions without `cache=True`
❌ Large API payloads without compression
❌ No lazy-loading for long equity curves (1000+ points)
❌ Backtest >3s due to redundant Alpaca API calls

---

## Performance Targets

- **Backtest execution:** <3 seconds end-to-end
- **Bun build:** <30 seconds
- **Hot reload:** <2 seconds
- **Numba analysis:** <50ms per indicator on 1M+ points

---

## Journal

**Only log critical performance improvements** (>20% speedup, new <3s guarantee, build time reduction).

Write to: `.agent/.jules/journal/bolt.md`

**FEEDBACK LOOP (Critical): Before writing, check journal for:**

- Did I propose optimizing this exact bottleneck before?
- Was it already fixed? (Mark as RESOLVED + PR number)
- Has performance already improved? (Write "no finding" and stop)

**Example journal entries:**

✓ **Resolved improvement:**

```markdown
## [2026-04-07] - Follow-up: Backtest <3s Achieved

- **Previous:** proposed 2026-04-05 (cache market data fetch)
- **Current status:** FIXED + merged in PR #45 (4.2s → 2.8s)
- **Result:** RESOLVED #45
```

✓ **New performance proposal:**

```markdown
## [2026-04-07] - Proposal: Numba Warmup for Harmonics Analysis

- **Issue:** First backtest slow (~3.5s) due to JIT compilation
- **Proposal:** Add warmup_jit() in test suite, verify >20% gain
- **Expected:** 3.5s → <2.8s after warmup
- **Status:** PENDING HUMAN REVIEW + PR
```

✓ **No action:**

```markdown
## [2026-04-07] - Performance Audit: All Targets Met

- **Status:** Backtest <3s, Bun build <30s, Numba analysis <50ms
- **Result:** NO CRITICAL FINDINGS
```

If backtest already <3s and no bottleneck found, **stop—no action needed**.
