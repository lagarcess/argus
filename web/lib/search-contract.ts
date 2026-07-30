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

export type SearchDossierAction<TDecision extends string> =
  | {
      type: "run_fresh";
      source_run_id: string;
      run_label: string;
      canonical_setup: SearchRunFreshSetup;
      send_text: string;
    }
  | {
      type: "decision";
      evidence_artifact_id: string;
      decision_state: TDecision | null;
      note: string | null;
      run_label: string;
    };

export type SearchConversationItem<TDecision extends string> = {
  type: "conversation";
  id: string;
  title: string;
  matched_text: string;
  updated_at: string;
  conversation_id: string;
  match: {
    layer:
      "conversation" | "message" | "run" | "idea" | "evidence" | "decision";
    fragment: string;
    count: number;
    message_id?: string;
  };
  dossier: {
    decision: {
      state: TDecision;
      note: string | null;
      run_label: string | null;
    } | null;
    tested: {
      symbols: string[];
      strategy_families: string[];
      run_count: number;
      start_date: string | null;
      end_date: string | null;
    };
    outcome: {
      run_label: string;
      completed_at: string;
      benchmark_symbol: string | null;
      quick_take: string | null;
      metrics: Array<{ name: string; value: string | number }>;
    } | null;
    left_off: {
      run_label: string;
      completed_at: string;
      nudge: "undecided" | "suggestion_untaken" | "stale_result" | null;
    } | null;
  };
  actions: SearchDossierAction<TDecision>[];
  decision_states: TDecision[];
};
