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

export type Message = {
  id: string;
  role: "user" | "ai";
  kind?: "text" | "strategy_result";
  content?: string;
  result?: StrategyResultPayload;
  isLoadingResult?: boolean;
  actions?: ChatActionOption[];
};
