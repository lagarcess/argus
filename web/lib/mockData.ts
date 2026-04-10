import { faker } from "@faker-js/faker";

export interface MockStrategy {
  id: string;
  name: string;
  patterns: string[];
  entry_criteria: Record<string, number | string>;
  exit_criteria: Record<string, number | string>;
  indicators: string[];
  created_at: string;
  executed_at: string | null;
}

export interface MockBacktest {
  id: string;
  strategy_id: string;
  asset: string;
  timeframe: string;
  start_date: string;
  end_date: string;
  config_snapshot: Record<string, unknown>;
  full_result: {
    equity_curve: number[];
    trades: Array<{
      entry_time: string;
      entry_price: number;
      exit_time: string;
      exit_price: number;
      pnl_pct: number;
    }>;
    metrics: {
      total_return_pct: number;
      win_rate: number;
      max_drawdown_pct: number;
      sharpe_ratio: number;
      sortino_ratio: number;
    };
    reality_gap: {
      slippage_impact_pct: number;
      fee_impact_pct: number;
    };
  };
  created_at: string;
}

export interface MockProfile {
  id: string;
  email: string;
  is_admin: boolean;
  subscription_tier: "free" | "plus" | "pro" | "max";
  remaining_quota: number;
  created_at: string;
}

const PATTERNS = ["gartley", "butterfly", "bat", "crab", "shark", "bearish_divergence"];
const INDICATORS = ["rsi", "macd", "atr", "sma", "ema", "bb"];
const ASSETS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT"];
const TIMEFRAMES = ["15m", "1h", "4h", "1d"];

/**
 * Generate a mock strategy
 */
export function generateMockStrategy(overrides?: Partial<MockStrategy>): MockStrategy {
  const patternCount = faker.number.int({ min: 1, max: 3 });
  const patterns = faker.helpers.arrayElements(PATTERNS, patternCount);

  return {
    id: faker.string.uuid(),
    name: `${faker.company.name()} Trading Strategy`,
    patterns,
    entry_criteria: {
      rsi: faker.number.int({ min: 20, max: 40 }),
      sma_period: faker.number.int({ min: 10, max: 50 }),
      min_volume: faker.number.int({ min: 1000, max: 10000 }),
    },
    exit_criteria: {
      stop_loss_pct: faker.number.float({ min: 0.5, max: 5, precision: 0.01 }),
      take_profit_pct: faker.number.float({ min: 1, max: 10, precision: 0.01 }),
      max_hold_hours: faker.number.int({ min: 1, max: 72 }),
    },
    indicators: faker.helpers.arrayElements(INDICATORS, faker.number.int({ min: 2, max: 4 })),
    created_at: faker.date.past({ years: 0.5 }).toISOString(),
    executed_at: faker.datatype.boolean(0.6) ? faker.date.past({ years: 0.3 }).toISOString() : null,
    ...overrides,
  };
}

/**
 * Generate a mock backtest result
 */
export function generateMockBacktest(overrides?: Partial<MockBacktest>): MockBacktest {
  const startDate = faker.date.past({ years: 1 });
  const endDate = new Date(startDate);
  endDate.setMonth(endDate.getMonth() + faker.number.int({ min: 1, max: 6 }));

  const tradeCount = faker.number.int({ min: 5, max: 50 });
  const trades = Array.from({ length: tradeCount }, () => ({
    entry_time: faker.date.between({ from: startDate, to: endDate }).toISOString(),
    entry_price: faker.number.float({ min: 25000, max: 70000, precision: 0.01 }),
    exit_time: faker.date.between({ from: startDate, to: endDate }).toISOString(),
    exit_price: faker.number.float({ min: 25000, max: 70000, precision: 0.01 }),
    pnl_pct: faker.number.float({ min: -5, max: 15, precision: 0.01 }),
  }));

  const totalReturn = trades.reduce((sum, trade) => sum + trade.pnl_pct, 0);
  const winningTrades = trades.filter((t) => t.pnl_pct > 0).length;
  const equityCurve = Array.from({ length: 100 }, (_, i) => {
    const progress = i / 100;
    const noise = faker.number.float({ min: -2, max: 2, precision: 0.01 });
    return 100 + totalReturn * progress + noise;
  });

  return {
    id: faker.string.uuid(),
    strategy_id: faker.string.uuid(),
    asset: faker.helpers.arrayElement(ASSETS),
    timeframe: faker.helpers.arrayElement(TIMEFRAMES),
    start_date: startDate.toISOString().split("T")[0],
    end_date: endDate.toISOString().split("T")[0],
    config_snapshot: {
      patterns: ["gartley", "butterfly"],
      entry_criteria: { rsi: 30 },
      exit_criteria: { stop_loss_pct: 2 },
      indicators: ["rsi", "macd"],
    },
    full_result: {
      equity_curve: equityCurve,
      trades,
      metrics: {
        total_return_pct: totalReturn,
        win_rate: parseFloat((winningTrades / trades.length).toFixed(2)),
        max_drawdown_pct: faker.number.float({ min: 5, max: 30, precision: 0.01 }),
        sharpe_ratio: faker.number.float({ min: 0.5, max: 3, precision: 0.01 }),
        sortino_ratio: faker.number.float({ min: 0.8, max: 4, precision: 0.01 }),
      },
      reality_gap: {
        slippage_impact_pct: faker.number.float({ min: 0.01, max: 0.5, precision: 0.01 }),
        fee_impact_pct: faker.number.float({ min: 0.05, max: 0.2, precision: 0.01 }),
      },
    },
    created_at: faker.date.past({ years: 0.5 }).toISOString(),
    ...overrides,
  };
}

/**
 * Generate a sparkline (15-point equity curve)
 */
export function generateMockSparkline(): number[] {
  const sparklineLength = 15;
  const baseValue = 100;
  const trend = faker.number.float({ min: -5, max: 20, precision: 0.1 });

  return Array.from({ length: sparklineLength }, (_, i) => {
    const progress = i / sparklineLength;
    const noise = faker.number.float({ min: -2, max: 2, precision: 0.01 });
    return baseValue + trend * progress + noise;
  });
}

/**
 * Generate a mock user profile
 */
export function generateMockProfile(overrides?: Partial<MockProfile>): MockProfile {
  const subscriptionTiers: Array<"free" | "plus" | "pro" | "max"> = ["free", "plus", "pro", "max"];
  const tier = faker.helpers.arrayElement(subscriptionTiers);

  return {
    id: faker.string.uuid(),
    email: faker.internet.email(),
    is_admin: false,
    subscription_tier: tier,
    remaining_quota:
      tier === "free" ? faker.number.int({ min: 0, max: 50 }) : tier === "pro" ? faker.number.int({ min: 0, max: 500 }) : 99999,
    created_at: faker.date.past({ years: 1 }).toISOString(),
    ...overrides,
  };
}

/**
 * Generate a batch of mock backtests
 */
export function generateMockBacktestHistory(count: number = 20): MockBacktest[] {
  return Array.from({ length: count }, () => generateMockBacktest());
}

/**
 * Generate a batch of mock strategies
 */
export function generateMockStrategies(count: number = 5): MockStrategy[] {
  return Array.from({ length: count }, () => generateMockStrategy());
}
