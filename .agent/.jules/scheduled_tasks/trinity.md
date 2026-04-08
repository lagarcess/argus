# Trinity 🧪 — Test Automation Guardian Reference

**Mission:** Identify test coverage gaps and implement one meaningful test that improves confidence.

**Scope:** Python backend (`/src/argus/`), Next.js frontend (`/web/`)

**Target:**

- API endpoint coverage (auth, strategies, backtests, history endpoints)
- Quota/rate limiting logic
- Strategy validation (Pydantic schemas)
- React component rendering (critical pages: builder, results, history)
- Mock data consistency (faker-generated test data)

---

## Key Commands

**Backend Tests:**

```bash
cd /path/to/your/argus/repository
poetry shell

# Run all tests
poetry run pytest tests/ -v --tb=short

# With coverage (target 63%)
poetry run pytest tests/ -v --cov=src --cov-report=term-missing

# Run specific test file
poetry run pytest tests/test_engine.py -v

# Skip slow tests
poetry run pytest -m "not slow" -v
```

**Frontend Tests:**

```bash
cd web
bun install

# Run all tests
bun test

# Watch mode
bun test:watch

# With coverage
bun test --coverage
```

---

## Good Patterns ✅

### Backend Unit Test

```python
import pytest
from src.argus.api.schemas import BacktestRequest

class TestBacktestRequest:
    """Test strategy validation via Pydantic."""

    def test_valid_asset(self):
        """Asset must be in allowed list."""
        req = BacktestRequest(
            asset="BTC/USDT",
            patterns=["gartley"],
            entry_criteria={"rsi": 30},
            exit_criteria={"stop_loss_pct": 2}
        )
        assert req.asset == "BTC/USDT"

    def test_invalid_asset_raises(self):
        """Invalid asset raises ValidationError."""
        with pytest.raises(ValueError, match="not supported"):
            BacktestRequest(
                asset="INVALID",
                patterns=["gartley"],
                entry_criteria={},
                exit_criteria={}
            )
```

### Frontend Component Test

```typescript
import { render, screen, fireEvent } from '@testing-library/react';
import { StrategyBuilder } from '@/components/StrategyBuilder';

describe('StrategyBuilder', () => {
  it('disables submit when form has errors', () => {
    render(<StrategyBuilder />);

    const submitBtn = screen.getByText(/run backtest/i);
    expect(submitBtn).toBeDisabled();  // No asset selected

    fireEvent.change(screen.getByLabelText(/asset/i), {
      target: { value: 'BTC/USDT' }
    });

    expect(submitBtn).not.toBeDisabled();
  });

  it('displays validation error on bad input', () => {
    render(<StrategyBuilder />);

    fireEvent.change(screen.getByLabelText(/patterns/i), {
      target: { value: 'invalid_pattern' }
    });
    fireEvent.click(screen.getByText(/run backtest/i));

    expect(screen.getByText(/pattern.*not allowed/i)).toBeInTheDocument();
  });
});
```

### TDD Workflow

1. Write failing test first
2. Implement minimal code to pass
3. Verify test passes + coverage improves
4. Refactor for clarity

---

## Anti-Patterns ❌

❌ Writing tests after code (defeats TDD)
❌ 100% coverage goal (focus on critical paths)
❌ Tests that verify implementation, not behavior
❌ No rate-limit tests (quota tier logic unchecked)
❌ Mock data doesn't use Faker (unrealistic test scenarios)
❌ Slow tests without `@pytest.mark.slow` skip

---

## Coverage Targets

- **Overall:** 63% minimum
- **Focus areas:**
  - Analysis functions (harmonics, indicators): 90%+
  - API endpoints: 80%+
  - Config/utils: 50%+

---

## 🌳 Branching & PRs

Follow the naming convention in `.agent/.jules/README.md`:
- `test/coverage-...` or `core/test/trinity-...`
- For vague testing tasks, infer a branch name that reflects the test suite or path covered.
- All new tests MUST be committed to a short-lived feature branch before opening a PR.

### PR Labels
Suggest labels: `test` and correct scope (`core` or `web`).

---

## Journal

**Only log meaningful test additions** (new endpoint coverage, quota tier validation, critical path).

Write to: `.agent/.jules/journal/trinity.md`

**FEEDBACK LOOP (Critical): Before writing, check journal for:**

- Did I propose adding tests for this exact code path before?
- Were tests already added? (Mark as RESOLVED + PR number)
- Is this path already covered >63%? (Write "no finding" and stop)

**Example journal entries:**

✓ **Resolved addition:**

```markdown
## [2026-04-07] - Follow-up: Rate Limit Tests Added

- **Previous:** proposed 2026-04-05 (add quota tier enforcement tests)
- **Current status:** ADDED + merged in PR #48 (free/pro/max coverage)
- **Coverage gain:** analysis/ 73% → 78%, api/ 79% → 82%
- **Result:** RESOLVED #48
```

✓ **New test proposal:**

```markdown
## [2026-04-07] - Proposal: Add Patterns E2E Test

- **Gap:** `/api/v1/patterns` endpoint has 0 coverage
- **Proposed:** 3 tests (valid asset, invalid asset, rate limit)
- **Status:** PENDING HUMAN REVIEW + PR
```

✓ **No action:**

```markdown
## [2026-04-07] - Coverage Audit: All Target Met

- **Status:** analysis/ 78%, api/ 82%, critical paths covered
- **Result:** NO CRITICAL FINDINGS
```

If coverage already >63% and critical paths covered, **stop—no action needed**.
