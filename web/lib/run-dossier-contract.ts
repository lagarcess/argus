export type DecisionState =
  | "watching"
  | "promising"
  | "rejected"
  | "revisit_later";

export type SearchRunFreshSetup = {
  strategy_type:
    | "buy_and_hold"
    | "dca_accumulation"
    | "indicator_threshold"
    | "signal_strategy";
  symbols: string[];
  asset_class: "equity" | "crypto" | "currency_pair";
  timeframe: string;
  date_range: { start: string; end: string };
  sizing_mode: "capital_amount" | "position_size";
  capital_amount: number | null;
  position_size: number | null;
  cadence: "daily" | "weekly" | "biweekly" | "monthly" | "quarterly" | null;
  recurring_contribution: number | null;
  starting_principal: number | null;
  benchmark_symbol: string;
  entry_rule: Record<string, unknown> | null;
  exit_rule: Record<string, unknown> | null;
  rule_spec: Record<string, unknown> | null;
  parameters: Record<string, unknown>;
  execution_realism: Record<string, unknown> | null;
};

export type SearchRunFreshAction = {
  type: "run_fresh";
  source_run_id: string;
  run_label: string;
  canonical_setup: SearchRunFreshSetup;
  send_text: string;
};

export type SearchDecisionAction = {
  type: "decision";
  evidence_artifact_id: string;
  decision_state: DecisionState | null;
  note: string | null;
  run_label: string;
};

export type SearchDossierAction =
  | SearchRunFreshAction
  | SearchDecisionAction;

export type RunDossier = {
  run_id: string;
  run_label: string;
  completed_at: string;
  result_message_id: string | null;
  tested: {
    symbols: string[];
    strategy_family: string | null;
    cadence: string | null;
    timeframe: string | null;
    start_date: string | null;
    end_date: string | null;
  };
  outcome: {
    run_label: string;
    completed_at: string;
    benchmark_symbol: string | null;
    quick_take: string | null;
    metrics: Array<{ name: string; value: string | number }>;
  };
  decision: {
    state: DecisionState;
    note: string | null;
    run_label: string | null;
  } | null;
  actions: SearchDossierAction[];
};

export type PaginatedRunDossiers = {
  items: RunDossier[];
  next_cursor: string | null;
  total_runs: number;
  decided_runs: number;
};
