# Monorepo Patterns Skill

**When to use:** Working in a Python + JavaScript monorepo (Argus), coordinating frontend and backend development, managing shared architecture decisions, deploying both services together.

---

## Overview

Argus is a **monorepo** with two main workspaces:

- **Backend:** `/src/argus/` + `/tests/` (Python, FastAPI, Numba)
- **Frontend:** `/web/` (Next.js 15, React 19, TypeScript)

Both are version-controlled together but have separate dependency managers (Poetry for Python, Bun for JavaScript).

**Key principle:** API contract is the interface between them. Changes to one side require coordinating with the other.

---

## Pattern 1: Independent Workspaces with Shared API Contract

### ✅ GOOD

```
argus/
├─ pyproject.toml          (backend dependencies)
├─ web/
│  └─ package.json         (frontend dependencies)
├─ src/argus/api/
│  └─ schemas.py           (← Pydantic models, source of truth)
├─ web/lib/
│  └─ api.ts               (← TypeScript types, mirror of Pydantic)
└─ docs/api_contract.md    (← Shared agreement)
```

**Backend** defines API in Pydantic:

```python
# src/argus/api/schemas.py
from pydantic import BaseModel

class BacktestRequest(BaseModel):
    asset: str
    patterns: list[str]
    entry_criteria: dict[str, float | int]

class BacktestResponse(BaseModel):
    simulation_id: str
    result: dict
```

**Frontend** mirrors types in TypeScript:

```typescript
// web/lib/api.ts
export interface BacktestRequest {
  asset: string;
  patterns: string[];
  entry_criteria: Record<string, number>;
}

export interface BacktestResponse {
  simulation_id: string;
  result: Record<string, unknown>;
}
```

### ❌ BAD

```
argus/
├─ src/argus/api/main.py   (API defined only here)
└─ web/lib/api.ts          (Frontend guesses types)
└─ docs/readme.md          (Outdated docs)

# Frontend breaks when backend changes schema
# No shared source of truth
```

---

## Pattern 2: Coordinated Deployments

### ✅ GOOD

**Both deploy together via startup.md:**

```bash
# 1. Initialize environment (downloads both backend + frontend deps)
chmod +x .github/setup.sh
.github/setup.sh

# 2. Run both in parallel terminals
Terminal 1: poetry shell && uvicorn src.argus.api.main:app --reload
Terminal 2: cd web && bun run dev

# Both live-reload on file changes → instant feedback
```

**Version alignment:**

- `pyproject.toml` has `fastapi` version (backend)
- `web/package.json` has `next` version (frontend)
- Both tested together before release

### ❌ BAD

```bash
# Backend requires manual install steps
# Frontend uses separate npm instead of Bun
# Different team members run different versions
# Deployments decouple (backend v1.2, frontend v1.0)
```

---

## Pattern 3: API Contract as Bridge

### ✅ GOOD

When adding a feature, **both sides evolve together:**

**Backend:**

```python
# 1. Define schema change in Pydantic
class BacktestRequest(BaseModel):
    asset: str
    patterns: list[str]
    # ← ADD new field
    custom_entry_condition: str | None = None

# 2. Update endpoint
@app.post("/api/v1/backtests")
async def run_backtest(req: BacktestRequest):
    if req.custom_entry_condition:
        # Handle new logic
        pass
```

**Frontend:**

```typescript
// 1. Update TypeScript types
export interface BacktestRequest {
  asset: string;
  patterns: string[];
  // ← ADD new field
  custom_entry_condition?: string;
}

// 2. Update form/UI
<input
  {...register("custom_entry_condition")}
  placeholder="Optional condition"
/>

// 3. No manual HTTP calls—fetch wrapper handles schema automatically
const result = await fetchApi("/backtests", {
  method: "POST",
  body: JSON.stringify(req)  // TypeScript ensures shape matches
});
```

### ❌ BAD

```typescript
// Frontend guesses schema
const backtest = {
  asset: "BTC",
  customEntryCondition: "...", // Different field name!
};

// Fetch call fails silently → 422 error
// Both teams blame each other
```

---

## Pattern 4: Shared Documentation

### ✅ GOOD

**Single source of truth for API:**

````markdown
# docs/api_contract.md

## POST /api/v1/backtests

**Request:**

```json
{
  "asset": "BTC/USDT",
  "patterns": ["gartley"],
  "entry_criteria": { "rsi": 30 },
  "exit_criteria": { "stop_loss_pct": 2 },
  "custom_entry_condition": "optional string"
}
```
````

**Response:**

```json
{
  "simulation_id": "uuid-xxx",
  "result": {...}
}
```

```

Backend dev checks this before implementing.
Frontend dev reads this before consuming.

### ❌ BAD

```

Backend Slack: "Hey, added custom_entry_condition to backtests"
Frontend Slack: "Oh, I didn't know. I'll add it later"
Meanwhile, main branch breaks.

````

---

## Pattern 5: Synchronized Testing

### ✅ GOOD

**Backend:**
```python
# tests/test_api.py
def test_custom_entry_condition():
    req = BacktestRequest(
        asset="BTC/USDT",
        patterns=["gartley"],
        custom_entry_condition="price > 50000"
    )
    response = client.post("/api/v1/backtests", json=req.model_dump())
    assert response.status_code == 200
    assert response.json()["result"]["metrics"]["total_return_pct"]
````

**Frontend:**

```typescript
// web/__tests__/pages/builder.test.tsx
it("submits custom entry condition", async () => {
  render(<StrategyBuilder />);
  fireEvent.change(screen.getByLabelText(/custom entry/i), {
    target: { value: "price > 50000" }
  });
  fireEvent.click(screen.getByText(/run backtest/i));

  expect(await screen.findByText(/successful/i)).toBeInTheDocument();
});
```

Both test the new field → confidence it works end-to-end.

### ❌ BAD

```
Backend has test for new field.
Frontend has no test.
Integration breaks.
```

---

## Rules (Always Follow)

1. **API Contract First:** Before coding, update `docs/api_contract.md`
2. **Pydantic ↔ TypeScript Sync:** Changes in backend schemas must mirror in frontend types
3. **Shared Dependencies:** Use Poetry for Python, Bun for JS (not mixed)
4. **Deploy Together:** `setup.sh` initializes both backend + frontend
5. **Test Both Sides:** Backend + frontend changes need tests
6. **Mock Until Ready:** Frontend uses mock data while backend builds, then swaps API endpoint

---

## Workflow: Adding a Feature (API-First)

1. **Update API Contract** (`docs/api_contract.md`)

   ```markdown
   ## POST /api/v1/backtests

   Request: { ..., new_field: string }
   Response: { ..., new_metric: number }
   ```

2. **Backend Team:**
   - Add Pydantic field to schema
   - Implement endpoint logic
   - Write tests
   - Commit + PR

3. **Frontend Team (parallel):**
   - Add TypeScript interface field
   - Update UI form
   - Use mock API (`NEXT_PUBLIC_MOCK_API=true`)
   - Write tests
   - Commit + PR

4. **Integration:**
   - Drop `NEXT_PUBLIC_MOCK_API=false` (real API)
   - Run both locally: `setup.sh` → Terminal 1 backend, Terminal 2 frontend
   - Verify end-to-end
   - Merge PRs

---

## Git Workflow in Monorepo

```bash
# Branch naming includes which part changed
git checkout -b feat/api-custom-entry-condition
# or
git checkout -b feat/ui-custom-entry-form

# Commit messages are optional to prefix with scope
git commit -m "feat(api): add custom_entry_condition to BacktestRequest"
git commit -m "feat(web): add entry condition form field"

# Both PRs can be open simultaneously (separate reviewers)
# Review API contract changes first (affects both)
```

---

## Deployment Coordination

```bash
# Before release, ensure versions match:
grep "fastapi" pyproject.toml            # e.g., ^0.115.0
grep '"next"' web/package.json           # e.g., 15.0.0

# Deploy backend to Render, frontend to Vercel simultaneously
# Both read from same Supabase instance
# Environment variables align (.env in root, web/.env.local in frontend)
```

---

## Examples in This Project

- `docs/api_contract.md` – Shared API specification
- `src/argus/api/schemas.py` – Backend Pydantic models
- `web/lib/api.ts` – Frontend TypeScript types
- `web/lib/mockApi.ts` – Mock implementation while backend builds
- `.github/setup.sh` – Unified setup for both
- `startup.md` – Launch instructions for both
