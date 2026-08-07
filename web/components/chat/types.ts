import type { AssetClass } from "@/lib/argus-types";
import type {
  ArtifactLifecycle,
  BacktestJob,
  DecisionState,
} from "@/lib/argus-api";
import type { ConfirmationDisplayFacts } from "@/lib/confirmation-assumptions-display";
import type { RecoveryDisplay } from "@/lib/chat-recovery-display";
import type { MemoryRecallItem } from "@/lib/memory-recalls";

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

export type ResultChartExplorationPolicy = {
  minimum_visible_observations?: number;
  minimum_meaningful_duration?: string | null;
};

export type ResultChartMarkerSummary = {
  total_groups: number;
  included_groups: number;
  sampled: boolean;
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
  exploration_policy?: ResultChartExplorationPolicy | null;
  marker_summary?: ResultChartMarkerSummary | null;
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
    | "select_response_option"
    | "select_discovery_candidate"
    | "retry_last_turn"
    | "retry_load_conversation"
    | "retest_run";
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
  evidenceArtifactId?: string | null;
  evidenceLifecycle?: ArtifactLifecycle | null;
  decisionNoteId?: string | null;
  decisionState?: DecisionState | null;
  artifactId?: string;
  artifactType?: ArtifactType;
  artifactStatus?: string;
  savedStrategyId?: string | null;
  savingStrategy?: boolean;
  copyText?: string;
  actions?: ChatActionOption[];
  chart?: ResultChartPayload | null;
  executionCosts?: ExecutionCostEvidence | null;
};

export type ExecutionCostEvidence = {
  fee_bps?: number | null;
  slippage_bps?: number | null;
  gross_total_return_pct?: number | null;
  net_total_return_pct?: number | null;
  return_drag_pct?: number | null;
  benchmark_treatment?: string | null;
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

export type StrategyConfirmationPeriodAdjustment = {
  code: string;
  requested_date_range: StrategyConfirmationDateRange;
  effective_date_range: StrategyConfirmationDateRange;
};

export type StrategyConfirmationBenchmarkAdjustment = {
  code: string;
  requested_target: string;
  effective_benchmark: string;
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
  capabilities?: StrategyConfirmationCapabilities;
  date_range?: StrategyConfirmationDateRange;
  retest_period?: import("@/lib/chat-retest").RetestPeriodPayload | null;
  period_adjustment?: StrategyConfirmationPeriodAdjustment;
  benchmark_adjustment?: StrategyConfirmationBenchmarkAdjustment;
  rows: StrategyConfirmationRow[];
  assumptions?: string[];
  actions?: ChatActionOption[];
};

export type StrategyConfirmationCapabilities = {
  execution_costs_editable?: boolean;
};

export type StrategyPathContext = {
  kind: "clarification" | "confirmation";
  requestedField?: string | null;
  strategy: Record<string, unknown>;
  sourceResultRunId?: string | null;
  strategyPathId?: string | null;
  optionalParameters?: Record<string, unknown> | null;
};

export type Message = {
  id: string;
  /** Hidden durable message ids that should focus this projected transcript row. */
  transcriptAnchorIds?: string[];
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
  /** Canonical fact key for a latest-result fact answer; localized heading chrome. */
  resultFactHeadingKey?: string | null;
  /** Typed degraded/offline recovery display rendered through web i18n. */
  recoveryDisplay?: RecoveryDisplay | null;
  /** Existing backend-owned strategy facts used to prove turn continuity. */
  strategyPathContext?: StrategyPathContext | null;
  assistantRecoveryCode?: string | null;
  /** Backend-provided grounded-discovery sidecar (argus_discovery/v1). */
  discovery?: DiscoverySidecar | null;
  /** Backend post-turn saved-decision recalls; rendered as context only. */
  memoryRecalls?: MemoryRecallItem[] | null;
  /** Backend-owned structured context for a retest receipt turn. */
  retestReceipt?: import("@/lib/chat-retest").RetestReceipt | null;
  /** Ephemeral optimistic presentation; never hydrated or persisted. */
  retestReceiptPending?: boolean;
  nextExperiments?: import("@/lib/chat-next-experiments").NextExperimentRow[];
};

export type DiscoverySource = {
  title: string;
  domain: string;
  url: string;
  source_date?: string | null;
};

export type DiscoveryCandidate = {
  symbol: string;
  name: string;
  asset_class: AssetClass;
  reason_text: string;
  source_indices?: number[];
};

export type DiscoverySidecar = {
  schema_version: string;
  kind: "asset_discovery";
  relationship: "category" | "peer" | "comparison";
  query_summary: string;
  retrieved_at: string;
  sources: DiscoverySource[];
  candidates: DiscoveryCandidate[];
  unverified_names: string[];
  /** Backend-owned: the "search current results" escalation may render only
   * when true, so the row can never outlive the allowance. */
  can_request_search?: boolean;
};
