import type { BacktestRun } from "./argus-api";
import { resultCardFromRun } from "./argus-api";
import type {
  ResultChartMarker,
  ResultChartPoint,
  StrategyResultPayload,
} from "@/components/chat/types";

type ResultCardPlaygroundFixture = {
  id: string;
  name: string;
  note: string;
  result: StrategyResultPayload;
};

const resultActions = [
  {
    id: "explain-result",
    type: "show_breakdown" as const,
    label: "Show a breakdown",
    presentation: "result" as const,
  },
  {
    id: "refine-idea",
    type: "refine_strategy" as const,
    label: "Refine strategy",
    presentation: "result" as const,
  },
  {
    id: "save-strategy",
    type: "save_strategy" as const,
    label: "Save strategy",
    presentation: "result" as const,
  },
];

const defaultAssumptions = [
  "Timeframe: 1D",
  "Long-only",
  "Equal weight",
  "No fees/slippage",
  "Benchmark: SPY",
];

const HOUR_MS = 60 * 60 * 1000;
const DAY_MS = 24 * HOUR_MS;

// Two weeks of hourly portfolio equity from $1,000 to exactly $1,120 (+12.0%).
// The sin(pi * i / last) envelope zeroes the wiggle at both endpoints so the
// metrics text stays exact while peak/low stay non-trivial for range summaries.
function adaptiveHourlySeries(): ResultChartPoint[] {
  const first = Date.parse("2026-01-01T00:00:00Z");
  const last = 14 * 24;
  return Array.from({ length: last + 1 }, (_, index) => {
    const trend = 1000 + (120 * index) / last;
    const wiggle = 8 * Math.sin((Math.PI * index) / last) * Math.sin(index / 6);
    return {
      time: new Date(first + index * HOUR_MS).toISOString().slice(0, 19),
      value: Math.round((trend + wiggle) * 100) / 100,
    };
  });
}

// 80 persisted executed-fill groups evenly spread over the hourly series,
// mirroring a backend cap of 124 pre-cap groups down to 80 stored markers.
function adaptiveHourlyMarkers(series: ResultChartPoint[]): ResultChartMarker[] {
  const lastIndex = series.length - 1;
  return Array.from({ length: 80 }, (_, index) => {
    const sourceIndex = Math.round((index * lastIndex) / 79);
    const isEntry = index % 2 === 0;
    return {
      time: series[sourceIndex]!.time,
      type: isEntry ? ("entry" as const) : ("exit" as const),
      label: isEntry ? "Buy AAPL" : "Sell AAPL",
      symbols: ["AAPL"],
    };
  });
}

// Two years of daily portfolio equity that ends exactly flat at $1,000 with a
// gentle wave (about -2.2% worst drop), matching the DCA metrics text.
function dcaDailySeries(): ResultChartPoint[] {
  const first = Date.parse("2022-01-03T00:00:00Z");
  const last = (Date.parse("2023-12-29T00:00:00Z") - first) / DAY_MS;
  return Array.from({ length: last + 1 }, (_, index) => ({
    time: new Date(first + index * DAY_MS).toISOString().slice(0, 10),
    value:
      Math.round((1000 + 11 * Math.sin((3 * Math.PI * index) / last)) * 100) /
      100,
  }));
}

// One accumulating buy per month across the two-year DCA series.
function dcaMonthlyMarkers(series: ResultChartPoint[]): ResultChartMarker[] {
  const byMonth = new Map<string, ResultChartPoint>();
  for (const point of series) {
    const month = point.time.slice(0, 7);
    if (!byMonth.has(month)) byMonth.set(month, point);
  }
  return [...byMonth.values()].map((point) => ({
    time: point.time,
    type: "entry" as const,
    label: "Buy AAPL",
    symbols: ["AAPL"],
  }));
}

const adaptiveHourlySeriesPoints = adaptiveHourlySeries();
const dcaDailySeriesPoints = dcaDailySeries();

export const legacyPersistedRunFixture: BacktestRun = {
  id: "playground-legacy-run",
  conversation_id: "playground-conversation",
  strategy_id: null,
  status: "completed",
  asset_class: "equity",
  symbols: ["AAPL"],
  allocation_method: "equal_weight",
  benchmark_symbol: "SPY",
  metrics: { aggregate: {}, by_symbol: {} },
  config_snapshot: { template: "buy_and_hold" },
  created_at: "2026-05-30T00:00:00Z",
  conversation_result_card: {
    title: "AAPL Buy and Hold",
    symbols: ["AAPL"],
    strategy_label: "Legacy persisted shape",
    date_range: {
      start: "2021-01-04",
      end: "2025-12-31",
      display: "January 4, 2021 to December 31, 2025",
    },
    status_label: "Simulation Complete",
    rows: [
      { key: "cash_value", label: "Cash Value ($)", value: "$1,000 -> $2,002" },
      { key: "total_return_pct", label: "Total Return (%)", value: "+100.2%" },
      {
        key: "benchmark_delta",
        label: "Vs benchmark",
        value: "Beat SPY by 46.4 percentage points",
      },
      { key: "max_drawdown_pct", label: "Max Drawdown", value: "-16.8%" },
    ],
    assumptions: defaultAssumptions,
    actions: resultActions,
    benchmark_note: "Universe: AAPL. Benchmark: SPY.",
    chart: {
      kind: "portfolio_equity",
      currency: "USD",
      base_value: 1000,
      series: [
        { time: "2021-01-04", value: 1000 },
        { time: "2021-09-01", value: 1150 },
        { time: "2022-06-01", value: 980 },
        { time: "2023-02-01", value: 1325 },
        { time: "2023-11-01", value: 1510 },
        { time: "2024-08-01", value: 1780 },
        { time: "2025-04-01", value: 1888 },
        { time: "2025-12-31", value: 2002 },
      ],
    },
  },
  chart: null,
  trades: null,
};

export const resultCardPlaygroundFixtures: ResultCardPlaygroundFixture[] = [
  {
    id: "positive-single-symbol",
    name: "Positive single-symbol buy-and-hold",
    note: "AAPL ends higher, beats SPY, and keeps drawdown moderate.",
    result: {
      strategyName: "AAPL Buy and Hold",
      strategyLabel: "Buy and hold",
      symbols: ["AAPL"],
      assetClass: "equity",
      period: "January 4, 2021 to December 31, 2025",
      statusLabel: "Simulation Complete",
      metrics: [
        { label: "Ending value", value: "$1,000 -> $1,560" },
        { label: "Total return", value: "+56.0%" },
        { label: "Compared with SPY", value: "Beat SPY by 27.9 percentage points" },
        { label: "Worst drop", value: "-12.4%" },
      ],
      assumptions: defaultAssumptions,
      actions: resultActions,
      chart: {
        kind: "portfolio_equity",
        currency: "USD",
        base_value: 1000,
        value_extrema: {
          peak: { time: "2025-12-31", value: 1560 },
          lowest: { time: "2022-06-01", value: 984 },
        },
        series: [
          { time: "2021-01-04", value: 1000 },
          { time: "2021-09-01", value: 1110 },
          { time: "2022-06-01", value: 984 },
          { time: "2023-02-01", value: 1218 },
          { time: "2023-11-01", value: 1322 },
          { time: "2024-08-01", value: 1468 },
          { time: "2025-04-01", value: 1512 },
          { time: "2025-12-31", value: 1560 },
        ],
      },
    },
  },
  {
    id: "modeled-execution-costs",
    name: "Modeled execution costs",
    note: "Trust strip shows net vs gross when backend models fees and slippage.",
    result: {
      strategyName: "AAPL Buy and Hold With Costs",
      strategyLabel: "Buy and hold",
      symbols: ["AAPL"],
      assetClass: "equity",
      period: "January 1, 2025 to January 7, 2025",
      dateRange: {
        start: "2025-01-01",
        end: "2025-01-07",
        display: "January 1, 2025 to January 7, 2025",
      },
      configSnapshot: { benchmark_symbol: "SPY" },
      statusLabel: "Simulation Complete",
      metrics: [
        { label: "Ending value", value: "$1,000 -> $1,118" },
        { label: "Total return", value: "+11.8%" },
        { label: "Compared with SPY", value: "Beat SPY by 5.8 percentage points" },
        { label: "Worst drop", value: "-0.2%" },
      ],
      assumptions: [
        "Long-only",
        "Equal weight",
        "Net of 10 bps fee + 5 bps slippage",
        "Benchmark: SPY (same modeled costs)",
      ],
      executionCosts: {
        fee_bps: 10,
        slippage_bps: 5,
        gross_total_return_pct: 12.0,
        net_total_return_pct: 11.8,
        return_drag_pct: 0.2,
        benchmark_treatment: "same_modeled_costs",
      },
      actions: resultActions,
      chart: {
        kind: "portfolio_equity",
        currency: "USD",
        base_value: 1000,
        value_summary: {
          peak_value: 1118,
          lowest_value: 1000,
          currency: "USD",
          source: "strategy_portfolio_equity_close",
        },
        series: [
          { time: "2025-01-01", value: 1000 },
          { time: "2025-01-02", value: 1018 },
          { time: "2025-01-03", value: 1038 },
          { time: "2025-01-06", value: 1098 },
          { time: "2025-01-07", value: 1118 },
        ],
      },
    },
  },
  {
    id: "negative-single-symbol",
    name: "Negative single-symbol result",
    note: "Single symbol loses money, lags the benchmark, and has a larger drawdown.",
    result: {
      strategyName: "PYPL Buy and Hold",
      strategyLabel: "Buy and hold",
      symbols: ["PYPL"],
      assetClass: "equity",
      period: "January 3, 2022 to December 29, 2023",
      statusLabel: "Simulation Complete",
      metrics: [
        { label: "Ending value", value: "$1,000 -> $820" },
        { label: "Total return", value: "-18.0%" },
        { label: "Compared with SPY", value: "Lagged SPY by 9.4 percentage points" },
        { label: "Worst drop", value: "-24.6%" },
      ],
      assumptions: defaultAssumptions,
      actions: resultActions,
      chart: {
        kind: "portfolio_equity",
        currency: "USD",
        base_value: 1000,
        series: [
          { time: "2022-01-03", value: 1000 },
          { time: "2022-04-01", value: 930 },
          { time: "2022-08-01", value: 861 },
          { time: "2022-12-30", value: 754 },
          { time: "2023-04-03", value: 802 },
          { time: "2023-08-01", value: 786 },
          { time: "2023-12-29", value: 820 },
        ],
      },
    },
  },
  {
    id: "benchmark-underperformance-positive",
    name: "Positive return, benchmark lag",
    note: "Outcome is green but trails the default benchmark.",
    result: {
      strategyName: "MSFT Conservative Hold",
      strategyLabel: "Buy and hold",
      symbols: ["MSFT"],
      assetClass: "equity",
      period: "January 3, 2023 to December 29, 2023",
      statusLabel: "Simulation Complete",
      metrics: [
        { label: "Ending value", value: "$1,000 -> $1,143" },
        { label: "Total return", value: "+14.3%" },
        { label: "Compared with SPY", value: "Lagged SPY by 10.1 percentage points" },
        { label: "Worst drop", value: "-11.9%" },
      ],
      assumptions: defaultAssumptions,
      actions: resultActions,
      chart: {
        kind: "portfolio_equity",
        currency: "USD",
        base_value: 1000,
        series: [
          { time: "2023-01-03", value: 1000 },
          { time: "2023-03-01", value: 1042 },
          { time: "2023-05-01", value: 1095 },
          { time: "2023-07-03", value: 1188 },
          { time: "2023-09-01", value: 1069 },
          { time: "2023-11-01", value: 1124 },
          { time: "2023-12-29", value: 1143 },
        ],
      },
    },
  },
  {
    id: "dca-result",
    name: "DCA result",
    note: "Recurring contribution context stays clear in a near-flat outcome.",
    result: {
      strategyName: "AAPL Monthly DCA",
      strategyLabel: "Monthly contribution",
      symbols: ["AAPL"],
      template: "dca_accumulation",
      assetClass: "equity",
      configSnapshot: {
        template: "dca_accumulation",
        timeframe: "1D",
        benchmark_symbol: "SPY",
        resolved_parameters: {
          strategy_type: "dca_accumulation",
          timeframe: "1D",
          benchmark_symbol: "SPY",
          cadence: "monthly",
          capital_amount: 250,
        },
        parameters: {
          dca_cadence: "monthly",
        },
      },
      period: "January 3, 2022 to December 29, 2023",
      statusLabel: "Simulation Complete",
      metrics: [
        { label: "Ending value", value: "$1,000 -> $1,000" },
        { label: "Total return", value: "0.0%" },
        { label: "Compared with SPY", value: "In line with SPY" },
        { label: "Worst drop", value: "-2.2%" },
      ],
      assumptions: [
        "Timeframe: 1D",
        "Monthly contribution: $250",
        "Long-only",
        "No fees/slippage",
        "Benchmark: SPY",
      ],
      actions: resultActions,
      chart: {
        kind: "portfolio_equity",
        currency: "USD",
        base_value: 1000,
        series: dcaDailySeriesPoints,
        markers: dcaMonthlyMarkers(dcaDailySeriesPoints),
        marker_summary: {
          total_groups: 24,
          included_groups: 24,
          sampled: false,
        },
        exploration_policy: {
          minimum_visible_observations: 6,
          minimum_meaningful_duration: "P2M",
        },
      },
    },
  },
  {
    id: "trade-based-strategy",
    name: "Trade-based strategy",
    note: "RSI-style execution markers use existing chart marker support.",
    result: {
      strategyName: "AAPL RSI Rebound",
      strategyLabel: "RSI below 30, exit above 55",
      symbols: ["AAPL"],
      assetClass: "equity",
      period: "January 3, 2022 to December 29, 2023",
      statusLabel: "Simulation Complete",
      metrics: [
        { label: "Ending value", value: "$1,000 -> $1,184" },
        { label: "Total return", value: "+18.4%" },
        { label: "Compared with SPY", value: "Beat SPY by 7.1 percentage points" },
        { label: "Worst drop", value: "-9.6%" },
      ],
      assumptions: [
        ...defaultAssumptions,
        "Entry: RSI below 30",
        "Exit: RSI above 55",
      ],
      actions: resultActions,
      chart: {
        kind: "portfolio_equity",
        currency: "USD",
        base_value: 1000,
        series: [
          { time: "2022-01-03", value: 1000 },
          { time: "2022-03-15", value: 1034 },
          { time: "2022-06-01", value: 956 },
          { time: "2022-09-12", value: 1088 },
          { time: "2023-01-06", value: 1042 },
          { time: "2023-05-15", value: 1130 },
          { time: "2023-09-18", value: 1102 },
          { time: "2023-12-29", value: 1184 },
        ],
        markers: [
          { time: "2022-03-15", type: "entry", label: "Entered AAPL", symbols: ["AAPL"] },
          { time: "2022-09-12", type: "exit", label: "Exited AAPL", symbols: ["AAPL"] },
          { time: "2023-01-06", type: "entry", label: "Entered AAPL", symbols: ["AAPL"] },
          { time: "2023-05-15", type: "exit", label: "Exited AAPL", symbols: ["AAPL"] },
          { time: "2023-09-18", type: "entry", label: "Entered AAPL", symbols: ["AAPL"] },
        ],
      },
    },
  },
  {
    id: "adaptive-intraday-result",
    name: "Adaptive intraday result",
    note: "Two weeks of hourly data with capped executed-fill markers for range exploration.",
    result: {
      strategyName: "AAPL Two-Week Hold",
      strategyLabel: "Buy and hold",
      symbols: ["AAPL"],
      assetClass: "equity",
      configSnapshot: {
        template: "buy_and_hold",
        timeframe: "1h",
        benchmark_symbol: "SPY",
      },
      period: "January 1, 2026 to January 15, 2026",
      dateRange: {
        start: "2026-01-01",
        end: "2026-01-15",
        display: "January 1, 2026 to January 15, 2026",
      },
      statusLabel: "Simulation Complete",
      metrics: [
        { label: "Ending value", value: "$1,000 -> $1,120" },
        { label: "Total return", value: "+12.0%" },
        { label: "Compared with SPY", value: "Beat SPY by 5.2 percentage points" },
        { label: "Worst drop", value: "-1.8%" },
      ],
      assumptions: [
        "Timeframe: 1h",
        "Long-only",
        "Equal weight",
        "No fees/slippage",
        "Benchmark: SPY",
      ],
      actions: resultActions,
      chart: {
        kind: "portfolio_equity",
        currency: "USD",
        base_value: 1000,
        series: adaptiveHourlySeriesPoints,
        markers: adaptiveHourlyMarkers(adaptiveHourlySeriesPoints),
        marker_summary: {
          total_groups: 124,
          included_groups: 80,
          sampled: true,
        },
        exploration_policy: {
          minimum_visible_observations: 6,
          minimum_meaningful_duration: "P1M",
        },
        value_summary: {
          peak_value: 1120,
          lowest_value: 1000,
          currency: "USD",
          source: "strategy_portfolio_equity_close",
        },
      },
    },
  },
  {
    id: "multi-symbol-same-asset",
    name: "Multi-symbol same-asset result",
    note: "Uses existing symbol chip behavior for an equal-weight equity basket.",
    result: {
      strategyName: "Mega-cap Equal Weight",
      strategyLabel: "Equal-weight basket",
      symbols: ["AAPL", "MSFT", "NVDA", "GOOGL"],
      assetClass: "equity",
      period: "January 3, 2023 to December 29, 2023",
      statusLabel: "Simulation Complete",
      metrics: [
        { label: "Ending value", value: "$1,000 -> $1,427" },
        { label: "Total return", value: "+42.7%" },
        { label: "Compared with SPY", value: "Beat SPY by 18.3 percentage points" },
        { label: "Worst drop", value: "-12.4%" },
      ],
      assumptions: defaultAssumptions,
      actions: resultActions,
      chart: {
        kind: "portfolio_equity",
        currency: "USD",
        base_value: 1000,
        series: [
          { time: "2023-01-03", value: 1000 },
          { time: "2023-03-01", value: 1054 },
          { time: "2023-05-01", value: 1136 },
          { time: "2023-07-03", value: 1268 },
          { time: "2023-09-01", value: 1198 },
          { time: "2023-11-01", value: 1344 },
          { time: "2023-12-29", value: 1427 },
        ],
      },
    },
  },
  {
    id: "old-persisted-card-shape",
    name: "Old persisted card shape",
    note: "Raw fixture uses legacy labels and the existing mapper hydrates display labels.",
    result: resultCardFromRun(legacyPersistedRunFixture),
  },
];
