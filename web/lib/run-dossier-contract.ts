export type DecisionState =
  | "watching"
  | "promising"
  | "rejected"
  | "revisit_later";

export type SearchRetestAction = {
  type: "retest_run";
  source_run_id: string;
  run_label: string;
  window_policy: "preserve_start_ending_latest_available";
  contract_version: "argus_retest_run/v2";
};

export type SearchDecisionAction = {
  type: "decision";
  availability: "available" | "account_conversion_required";
  evidence_artifact_id: string;
  decision_state: DecisionState | null;
  note: string | null;
  run_label: string;
};

export type SearchDossierAction =
  | SearchRetestAction
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
