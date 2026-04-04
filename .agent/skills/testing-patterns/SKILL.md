---
name: Testing Patterns
description: pytest best practices, TDD methodology, and test organization for the Argus engine.
---

# Testing Patterns

## TDD Workflow
1. **Red**: Write a failing test that describes the expected behavior.
2. **Green**: Write the minimum code to make the test pass.
3. **Refactor**: Clean up while keeping tests green.

For bug fixes: **always** write a failing test that reproduces the bug before fixing it.

## Test Organization
```
tests/
├── conftest.py              # Shared fixtures (OHLCV data, etc.)
├── analysis/
│   ├── test_structural.py   # ZigZag, FastPIP, pivot detection
│   ├── test_patterns.py     # Candlestick & chart patterns
│   ├── test_harmonics.py    # Harmonic/Fibonacci patterns
│   └── test_indicators.py   # Technical indicators
└── market/                  # Future: data provider tests
    └── test_data_provider.py
```

## Naming Conventions
- Test files: `test_<module>.py`
- Test classes: `Test<Feature>` (e.g., `TestZigZagCore`)
- Test methods: `test_<behavior>` (e.g., `test_detects_simple_peak`)

## Fixtures
- Use `conftest.py` for shared fixtures.
- Prefer small, focused fixtures over large all-in-one ones.
- Use `@pytest.fixture` with descriptive names.

```python
@pytest.fixture
def simple_ohlcv_df():
    """Create a simple OHLCV DataFrame with clear peaks and valleys."""
    ...
```

## Markers
- `@pytest.mark.slow` — Performance benchmarks requiring large datasets.
- No integration markers currently (all tests are unit tests).

## Assertions
- Use plain `assert` — pytest rewrites them for clear failure messages.
- Use `pytest.approx()` for floating-point comparisons.
- Avoid `assertTrue`/`assertEqual` from unittest.

## Coverage
- Target: **63%** minimum (enforced in CI).
- Focus coverage on analysis logic, not boilerplate.
- Run: `poetry run pytest tests/ --cov=src/argus --cov-report=term-missing`

## Numba Test Patterns
- Always call `warmup_jit()` before timing tests.
- Use `@pytest.mark.xfail(reason="CI environment variability")` for strict timing assertions.
- Test with both small (correctness) and large (performance) datasets.
