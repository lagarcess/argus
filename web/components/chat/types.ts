export type StrategyResultMetric = {
  label: string;
  value: string;
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
    | "add_to_collection"
    | "refine_strategy";
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
