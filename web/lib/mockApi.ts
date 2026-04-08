/**
 * Mock API layer for frontend development
 * Toggle mock mode via NEXT_PUBLIC_MOCK_API=true
 *
 * In development, set NEXT_PUBLIC_MOCK_API=true in .env.local to bypass backend
 * Mock data is generated using @faker-js/faker for realistic-looking test data
 */

import { faker } from "@faker-js/faker";
import {
  generateMockBacktest,
  generateMockBacktestHistory,
  generateMockProfile,
  generateMockStrategies,
  generateMockStrategy,
  type MockBacktest,
  type MockProfile,
  type MockStrategy,
} from "./mockData";
import type {
  BacktestRequest,
  BacktestResponse,
  HistoryResponse,
  SimulationLogEntry,
} from "./api";

// Enable mock mode via environment variable
const MOCK_MODE = process.env.NEXT_PUBLIC_MOCK_API === "true";

/**
 * Simulate network delay for realistic UX
 */
function delay(ms: number = 500): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Mock authentication endpoint
 */
export async function mockLogin(email: string, password: string): Promise<{ // eslint-disable-line @typescript-eslint/no-unused-vars
  access_token: string;
  user: MockProfile;
}> {
  if (!MOCK_MODE) throw new Error("Mock mode is disabled");
  await delay(300);

  return {
    access_token: `mock_token_${Date.now()}`,
    user: generateMockProfile({
      email,
      is_admin: email.includes("admin"),
    }),
  };
}

/**
 * Mock user session endpoint
 */
export async function mockGetSession(): Promise<MockProfile> {
  if (!MOCK_MODE) throw new Error("Mock mode is disabled");
  await delay(200);

  return generateMockProfile({
    remaining_quota: 25,
    subscription_tier: "free",
  });
}

/**
 * Mock strategy creation endpoint
 */
export async function mockCreateStrategy(name: string): Promise<MockStrategy> {
  if (!MOCK_MODE) throw new Error("Mock mode is disabled");
  await delay(200);

  return generateMockStrategy({ name, executed_at: null });
}

/**
 * Mock strategies list endpoint
 */
export async function mockGetStrategies(): Promise<MockStrategy[]> {
  if (!MOCK_MODE) throw new Error("Mock mode is disabled");
  await delay(300);

  return generateMockStrategies(5);
}

/**
 * Mock backtest execution endpoint
 * Simulates a 1-3 second backtest with realistic delays
 */
export async function mockRunBacktest(
  request: BacktestRequest
): Promise<BacktestResponse> {
  if (!MOCK_MODE) throw new Error("Mock mode is disabled");
  // Simulate actual backtest (1-3 seconds)
  await delay(faker.number.int({ min: 1000, max: 3000 }));

  const mockBacktest = generateMockBacktest({
    config_snapshot: request as unknown as Record<string, unknown>,
  });

  return {
    simulation_id: mockBacktest.id,
    result: mockBacktest.full_result,
  };
}

/**
 * Mock backtest detail endpoint
 */
export async function mockGetBacktest(id: string): Promise<MockBacktest> {
  if (!MOCK_MODE) throw new Error("Mock mode is disabled");
  await delay(200);

  return generateMockBacktest({ id });
}

/**
 * Mock history/pagination endpoint
 * Supports cursor-based pagination with mock data
 */
export async function mockGetHistory(
  cursor?: string,
  limit: number = 20
): Promise<HistoryResponse> {
  if (!MOCK_MODE) throw new Error("Mock mode is disabled");
  await delay(400);

  const allBacktests = generateMockBacktestHistory(100);
  const startIndex = cursor ? parseInt(atob(cursor), 10) : 0;
  const paginatedBacktests = allBacktests.slice(startIndex, startIndex + limit);

  const simulations: SimulationLogEntry[] = paginatedBacktests.map((bt) => ({
    id: bt.id,
    strategy_name: `Strategy ${faker.string.alphaNumeric(4).toUpperCase()}`,
    symbols: [bt.asset],
    timeframe: bt.timeframe,
    status: bt.full_result ? "completed" : "pending",
    total_return_pct: bt.full_result.metrics.total_return_pct,
    sharpe_ratio: bt.full_result.metrics.sharpe_ratio,
    max_drawdown_pct: bt.full_result.metrics.max_drawdown_pct,
    win_rate_pct: bt.full_result.metrics.win_rate * 100,
    total_trades: bt.full_result.trades.length,
    created_at: bt.created_at,
    completed_at: bt.created_at,
  }));

  // Generate next cursor if more data exists
  const nextCursor =
    startIndex + limit < allBacktests.length
      ? btoa((startIndex + limit).toString())
      : null;

  return {
    simulations,
    total: allBacktests.length,
    next_cursor: nextCursor,
  };
}

/**
 * Mock asset search endpoint
 */
export async function mockGetAssets(): Promise<
  Array<{ symbol: string; name: string }>
> {
  if (!MOCK_MODE) throw new Error("Mock mode is disabled");
  await delay(150);

  return [
    { symbol: "BTC/USDT", name: "Bitcoin" },
    { symbol: "ETH/USDT", name: "Ethereum" },
    { symbol: "SOL/USDT", name: "Solana" },
    { symbol: "XRP/USDT", name: "Ripple" },
    { symbol: "ADA/USDT", name: "Cardano" },
  ];
}

/**
 * Check if mock mode is enabled
 */
export function isMockModeEnabled(): boolean {
  return MOCK_MODE;
}
