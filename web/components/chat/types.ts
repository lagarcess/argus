export type StrategyResultMetric = {
  label: string;
  value: string;
};

export type ResultChartPoint = {
  time: string;
  value: number;
};

export type ResultChartMarker = {
  time: string;
  type: "entry" | "exit";
  label: string;
  symbols?: string[];
};

export type ResultChartPayload = {
  kind: "portfolio_equity";
  series: ResultChartPoint[];
  markers?: ResultChartMarker[];
  currency?: string;
  base_value?: number | null;
  attribution?: string;
};

export type ChatActionOption = {
  id?: string;
  label: string;
  value?: string;
  type?:
    | "run_backtest"
    | "change_dates"
    | "change_asset"
    | "adjust_assumptions"
    | "cancel_confirmation"
    | "show_breakdown"
    | "refine_strategy"
    | "save_strategy";
  presentation?: "confirmation" | "result";
  payload?: Record<string, unknown>;
};

export type ChatMention = {
  id: string;
  type: "asset" | "indicator";
  label: string;
  symbol?: string | null;
  description?: string | null;
  insert_text: string;
  support_status?: "supported" | "draft_only" | "unavailable";
};

export type StrategyResultPayload = {
  strategyName: string;
  strategyLabel?: string;
  symbols?: string[];
  period: string;
  benchmarkNote?: string;
  statusLabel?: string;
  metrics: StrategyResultMetric[];
  assumptions?: string[];
  runId?: string;
  strategyId?: string | null;
  actions?: ChatActionOption[];
  chart?: ResultChartPayload | null;
};

export type StrategyConfirmationRow = {
  label: string;
  value: string;
};

export type StrategyConfirmationPayload = {
  title: string;
  statusLabel: string;
  summary: string;
  rows: StrategyConfirmationRow[];
  assumptions?: string[];
  actions?: ChatActionOption[];
};

export type Message = {
  id: string;
  role: "user" | "ai";
  kind?: "text" | "strategy_result" | "strategy_confirmation";
  content?: string;
  mentions?: ChatMention[];
  result?: StrategyResultPayload;
  confirmation?: StrategyConfirmationPayload;
  isLoadingResult?: boolean;
  actions?: ChatActionOption[];
};
