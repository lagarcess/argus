---
description: Numba JIT warmup, pure math in analysis/, performance targets.
globs: ["src/argus/analysis/**/*.py"]
---

# Performance Rule

1. **JIT Warmup**: Any change to `src/argus/analysis/` requires `warmup_jit()` in test setup.
2. **Pure math only** inside `@njit` functions — no pandas, logger, or Python objects.
3. **Performance targets** (after warmup):
   - ZigZag 1M points: <50ms
   - FastPIP 100K points: <100ms
   - Harmonic scan 15 pivots: <2ms
4. Wrapper functions convert raw arrays → Python objects (Pivot, etc.).

See: `.agent/skills/numba-patterns/SKILL.md` for full details.
