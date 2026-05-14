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

export type ArtifactType =
  | "strategy_draft"
  | "confirmation"
  | "backtest_run"
  | "result_review"
  | "failed_action"
  | "saved_strategy";

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
  artifactId?: string;
  artifactType?: ArtifactType;
  artifactStatus?: string;
  savedStrategyId?: string | null;
  copyText?: string;
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
  template?: string;
  assetClass?: "equity" | "crypto";
  period: string;
  benchmarkNote?: string;
  statusLabel?: string;
  metrics: StrategyResultMetric[];
  assumptions?: string[];
  runId?: string;
  strategyId?: string | null;
  artifactId?: string;
  artifactType?: ArtifactType;
  artifactStatus?: string;
  savedStrategyId?: string | null;
  savingStrategy?: boolean;
  copyText?: string;
  actions?: ChatActionOption[];
  chart?: ResultChartPayload | null;
};

export type StrategyConfirmationRow = {
  label: string;
  value: string;
};

export type StrategyConfirmationPayload = {
  confirmation_id?: string;
  confirmation_state?: "active" | "superseded";
  artifactId?: string;
  artifactType?: ArtifactType;
  artifactStatus?: string;
  savedStrategyId?: string | null;
  copyText?: string;
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
  kind?: "text" | "strategy_result" | "strategy_confirmation" | "action";
  contentPresentation?: "result_breakdown";
  content?: string;
  mentions?: ChatMention[];
  selectedAction?: ChatActionOption;
  result?: StrategyResultPayload;
  confirmation?: StrategyConfirmationPayload;
  isLoadingResult?: boolean;
  actions?: ChatActionOption[];
  artifactId?: string;
  artifactType?: ArtifactType;
  artifactStatus?: string;
  savedStrategyId?: string | null;
  copyText?: string;
};
