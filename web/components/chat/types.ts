import type { AssetClass } from "@/lib/argus-types";
import type { BacktestJob } from "@/lib/argus-api";
import type { ConfirmationDisplayFacts } from "@/lib/confirmation-assumptions-display";

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

export type ResultChartValueSummary = {
  peak_value?: number | null;
  lowest_value?: number | null;
  currency?: string | null;
  source?: "strategy_portfolio_equity_close" | string;
};

export type ResultChartValuePoint = {
  time: string;
  value: number;
};

export type ResultChartPayload = {
  kind: "portfolio_equity";
  series: ResultChartPoint[];
  markers?: ResultChartMarker[];
  currency?: string;
  base_value?: number | null;
  value_summary?: ResultChartValueSummary | null;
  value_extrema?: {
    peak?: ResultChartValuePoint | null;
    lowest?: ResultChartValuePoint | null;
  } | null;
  attribution?: string;
};

export type ArtifactType =
  | "strategy_draft"
  | "confirmation"
  | "backtest_job"
  | "backtest_run"
  | "result_review"
  | "failed_action"
  | "saved_strategy";

export type ChatActionOption = {
  id?: string;
  label: string;
  labelKey?: string;
  value?: string;
  type?:
    | "run_backtest"
    | "change_dates"
    | "change_asset"
    | "adjust_assumptions"
    | "cancel_confirmation"
    | "show_breakdown"
    | "refine_strategy"
    | "save_strategy"
    | "retry_failed_action"
    | "retry_last_turn"
    | "retry_load_conversation";
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
  asset_class?: AssetClass | null;
  description?: string | null;
  insert_text: string;
  provider?: string | null;
  support_status?: "supported" | "draft_only" | "unavailable";
};

export type StrategyResultPayload = {
  strategyName: string;
  strategyLabel?: string;
  symbols?: string[];
  template?: string;
  assetClass?: AssetClass;
  configSnapshot?: Record<string, unknown>;
  period: string;
  dateRange?: {
    start: string;
    end: string;
    display?: string;
  };
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

export type StrategyConfirmationRowKey =
  | "strategy"
  | "assets"
  | "period"
  | "cadence"
  | "buy_rule"
  | "exit_rule"
  | "starting_capital"
  | "contribution";

export type StrategyConfirmationStatus =
  | "ready_to_run"
  | "needs_change"
  | "running"
  | "request_sent"
  | "run_complete"
  | "could_not_run"
  | "not_completed"
  | "editing"
  | "draft_canceled"
  | "updated";

export type StrategyConfirmationRow = {
  key?: StrategyConfirmationRowKey;
  label: string;
  labelKey?: string;
  value: string;
};

export type StrategyConfirmationDateRange = {
  start: string;
  end: string;
  display?: string;
};

export type StrategyConfirmationPayload = {
  confirmation_id?: string;
  confirmation_state?: "active" | "superseded" | "cancelled";
  asset_class?: AssetClass | null;
  artifactId?: string;
  artifactType?: ArtifactType;
  artifactStatus?: string;
  savedStrategyId?: string | null;
  copyText?: string;
  title: string;
  status?: StrategyConfirmationStatus;
  statusLabel: string;
  summary: string;
  strategy_type?: string;
  display_facts?: ConfirmationDisplayFacts;
  date_range?: StrategyConfirmationDateRange;
  rows: StrategyConfirmationRow[];
  assumptions?: string[];
  actions?: ChatActionOption[];
};

export type Message = {
  id: string;
  role: "user" | "ai";
  kind?:
    | "text"
    | "strategy_result"
    | "strategy_confirmation"
    | "backtest_job"
    | "action";
  contentPresentation?:
    | "result_breakdown"
    | "conversation_load_failure"
    | "superseded_runtime_failure";
  content?: string;
  mentions?: ChatMention[];
  selectedAction?: ChatActionOption;
  result?: StrategyResultPayload;
  confirmation?: StrategyConfirmationPayload;
  backtestJob?: BacktestJob;
  isLoadingResult?: boolean;
  actions?: ChatActionOption[];
  artifactId?: string;
  artifactType?: ArtifactType;
  artifactStatus?: string;
  savedStrategyId?: string | null;
  copyText?: string;
};
