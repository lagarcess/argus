export type SearchConversationItem<TDecision extends string> = {
  type: "conversation";
  id: string;
  title: string;
  matched_text: string;
  updated_at: string;
  conversation_id: string;
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
      nudge:
        | "undecided"
        | "suggestion_untaken"
        | "stale_result"
        | null;
    } | null;
  };
  decision_states: TDecision[];
};
