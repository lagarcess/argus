# Mock Data Patterns Skill

**When to use:** Building frontend pages before backend is ready, developing UI components in isolation, testing loading states and error scenarios without hitting real API.

---

## Overview

The Argus frontend uses `@faker-js/faker` to generate realistic but fake test data during development. This allows frontend and backend teams to work in parallel—frontend team builds pages with mock data while backend team builds the actual API.

**Key files:**

- `web/lib/mockData.ts` – Faker generators (generateMockBacktest, generateMockStrategy, etc.)
- `web/lib/mockApi.ts` – Mock endpoint implementations (mockRunBacktest, mockGetHistory, etc.)
- `web/.env.local` – Toggle via `NEXT_PUBLIC_MOCK_API=true|false`

---

## Pattern 1: Generate Realistic Mock Data

### ✅ GOOD

```typescript
// web/lib/mockData.ts
import { faker } from "@faker-js/faker";

export function generateMockBacktest(): MockBacktest {
  const startDate = faker.date.past({ years: 1 });
  const endDate = new Date(startDate);
  endDate.setMonth(endDate.getMonth() + 3);

  const totalReturn = faker.number.float({
    min: -50,
    max: 200,
    precision: 0.01,
  });
  const equityCurve = Array.from({ length: 100 }, (_, i) => {
    const progress = i / 100;
    return (
      100 + totalReturn * progress + faker.number.float({ min: -2, max: 2 })
    );
  });

  return {
    id: faker.string.uuid(),
    asset: faker.helpers.arrayElement(["BTC/USDT", "ETH/USDT", "SOL/USDT"]),
    metrics: {
      total_return_pct: totalReturn,
      win_rate: faker.number.float({ min: 0.3, max: 0.9, precision: 0.01 }),
      max_drawdown_pct: faker.number.float({
        min: 5,
        max: 30,
        precision: 0.01,
      }),
    },
    equity_curve: equityCurve,
    created_at: startDate.toISOString(),
  };
}

// Usage in components
export function generateMockHistory(count: number = 20): MockBacktest[] {
  return Array.from({ length: count }, () => generateMockBacktest());
}
```

### ❌ BAD

```typescript
// ❌ Hardcoded values (not realistic, not diverse)
const mockBacktest = {
  total_return: 10,
  win_rate: 0.5,
  equity_curve: [100, 110, 120, 130, ...]
};

// ❌ Not matching API schema
const mockBacktest = {
  return: 10,  // Should be total_return_pct
  winRate: 0.5,  // Should be win_rate
}
```

---

## Pattern 2: Mock API Endpoints

### ✅ GOOD

```typescript
// web/lib/mockApi.ts
import { generateMockBacktest, generateMockHistory } from "./mockData";

export async function mockRunBacktest(
  request: BacktestRequest,
): Promise<BacktestResponse> {
  // Simulate actual backtest (1-3 seconds)
  await delay(faker.number.int({ min: 1000, max: 3000 }));

  const result = generateMockBacktest({ config_snapshot: request });
  return { simulation_id: result.id, result: result.full_result };
}

export async function mockGetHistory(
  cursor?: string,
  limit: number = 20,
): Promise<HistoryResponse> {
  await delay(400); // Network latency

  const allBacktests = generateMockHistory(100);
  const startIndex = cursor ? parseInt(atob(cursor), 10) : 0;
  const paginatedBacktests = allBacktests.slice(startIndex, startIndex + limit);

  const nextCursor =
    startIndex + limit < allBacktests.length
      ? btoa((startIndex + limit).toString())
      : null;

  return {
    simulations: paginatedBacktests.map((bt) => ({
      id: bt.id,
      total_return_pct: bt.full_result.metrics.total_return_pct,
      created_at: bt.created_at,
    })),
    total: allBacktests.length,
  };
}

// Helper: simulate network delay
function delay(ms: number = 500): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
```

### ❌ BAD

```typescript
// ❌ Returns instantly (not realistic UX)
export function mockRunBacktest() {
  return generateMockBacktest();  // No delay!
}

// ❌ Doesn't match API response shape
export function mockGetHistory() {
  return { backtests: [...] };  // Wrong key name
}
```

---

## Pattern 3: Toggle Mock Mode in Components

### ✅ GOOD

```typescript
// web/lib/useApi.ts
import { isMockModeEnabled } from "./mockApi";
import { fetchApi } from "./api";

export function useBacktest() {
  const isMock = isMockModeEnabled();

  const runBacktest = async (req: BacktestRequest) => {
    if (isMock) {
      return mockRunBacktest(req);  // Use mock
    } else {
      return fetchApi("/backtests", { method: "POST", body: JSON.stringify(req) });  // Real API
    }
  };

  return { runBacktest };
}

// Component
const ResultsPage = () => {
  const { runBacktest } = useBacktest();
  const [result, setResult] = useState(null);

  const handleRunBacktest = async (strategy: Strategy) => {
    const result = await runBacktest(strategy);  // Automatically uses mock or real API
    setResult(result);
  };

  return <div>...</div>;
};
```

### ❌ BAD

```typescript
// ❌ Hardcoded mock mode
export function useBacktest() {
  if (true) {
    // Always mock!
    return mockRunBacktest();
  }
}

// ❌ Mock mode hidden in environment, hard to toggle
const isMock = process.env.NODE_ENV === "development"; // Not clear!
```

---

## Pattern 4: Type Safety with Schemas

### ✅ GOOD

```typescript
// Ensure mock data matches real API schema
import { z } from "zod";

const MockBacktestSchema = z.object({
  id: z.string().uuid(),
  asset: z.enum(["BTC/USDT", "ETH/USDT", "SOL/USDT"]),
  metrics: z.object({
    total_return_pct: z.number(),
    win_rate: z.number().min(0).max(1),
  }),
  equity_curve: z.array(z.number()),
  created_at: z.string().datetime(),
});

export function generateMockBacktest(): z.infer<typeof MockBacktestSchema> {
  // Faker generation code ensures schema compliance via TypeScript
  const backtest = {
    /* ... */
  };
  return MockBacktestSchema.parse(backtest); // Validate at runtime
}
```

---

## Rules (Always Follow)

1. **Match API Schemas:** Mock data types must match `web/lib/api.ts` interfaces
2. **Realistic Values:** Use Faker ranges (e.g., `faker.number.float({ min: -50, max: 200 })`)
3. **Never Commit Secrets:** Mock files only use faker or public values
4. **Simulate Network:** Add `delay()` to mock API calls (realistic UX testing)
5. **Cursor Pagination:** Test pagination with mock data (use `btoa`/`atob` for cursor)
6. **Toggle Environment:** Use `NEXT_PUBLIC_MOCK_API=true|false` in `.env.local`

---

## When NOT to Use

- ❌ Don't use mock data in production (only when `NEXT_PUBLIC_MOCK_API=true`)
- ❌ Don't mock behavior that differs from real API
- ❌ Don't leave mock-only bugs unfound in real API testing

---

## Testing Mock Data

```typescript
// web/__tests__/lib/mockData.test.ts
import { generateMockBacktest } from "@/lib/mockData";

describe("Mock Data", () => {
  it("generates valid backtest structure", () => {
    const backtest = generateMockBacktest();
    expect(backtest.id).toMatch(/^[0-9a-f-]{36}$/); // UUID
    expect(backtest.asset).toMatch(/\/USDT$/);
    expect(backtest.metrics.win_rate).toBeLessThanOrEqual(1);
  });

  it("generates diverse data", () => {
    const backtests = Array.from({ length: 10 }, () => generateMockBacktest());
    const returns = backtests.map((b) => b.metrics.total_return_pct);
    const unique = new Set(returns);
    expect(unique.size).toBeGreaterThan(1); // Should vary
  });
});
```

---

## Examples in This Project

- `web/lib/mockData.ts` – All mock data generators
- `web/lib/mockApi.ts` – Mock endpoints with delay
- `web/.env.local` – `NEXT_PUBLIC_MOCK_API=false` (can toggle to `true`)
- `startup.md` – Section "Frontend Development (No Backend Yet)"
