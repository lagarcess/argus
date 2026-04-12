## 2026-04-12 - Phase C The Analytical Engine Wrapper

**Learning:** VectorBT multi-symbol matrices require strict Pydantic parsing inside tests when mapping to dictionary representations. Using `prange` allows us to parallelize across the matrix Asset dimension effectively when analyzing vectors, without looping using Python.

**Action:** Upgraded `ArgusEngine.run` with dual-sim reality gap metrics (fees and slippage variance logic). Refactored `BacktestConfig` to manage matrix alignment cleanly with memory constraints mapping.
