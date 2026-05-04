export type StrategyResultMetric = {
  label: string;
  value: string;
};

export type ChatActionOption = {
  id: string;
  label: string;
  value: string;
};

export type StrategyResultPayload = {
  strategyName: string;
  period: string;
  benchmarkNote?: string;
  statusLabel?: string;
  metrics: StrategyResultMetric[];
  assumptions?: string[];
  runId?: string;
  strategyId?: string | null;
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
  result?: StrategyResultPayload;
  confirmation?: StrategyConfirmationPayload;
  isLoadingResult?: boolean;
  actions?: ChatActionOption[];
};
