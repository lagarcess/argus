import type { PublicReceiptPayload } from "../../lib/public-receipt-contract";
import type { PublicReceiptTurn } from "../../lib/public-receipt-turns";
import { toolCardFixture } from "./tool-result-card";

export const legacyReceipt: PublicReceiptPayload = {
  schema_version: 1,
  idea_title: "Monthly AAPL investing",
  asset_class: "equity",
  symbols: ["AAPL"],
  strategy_facts: [{ key: "strategy_type", value: "dca_accumulation" }, { key: "cadence", value: "monthly" }],
  assumptions: [{ key: "long_only" }, { key: "equal_weight" }, { key: "recurring_contribution", value: "250" }, { key: "contribution_cadence", value: "monthly" }, { key: "starting_principal", value: "0" }, { key: "no_costs" }],
  date_range: { start: "2024-01-02", end: "2024-12-31" },
  metrics: [{ key: "contribution_return_pct", value: "+18.4%" }, { key: "max_drawdown_pct", value: "-6.2%" }, { key: "benchmark_return_pct", value: "+9.1%" }, { key: "delta_vs_benchmark_pct", value: "9.3" }],
  benchmark_symbol: "SPY",
  visual: null,
  owner_note: "A small monthly experiment.",
  content_language: "en",
  framing: "historical_simulation_not_advice",
  provenance_mark: "tested_with_argus",
};

export const researchTurn = {
  kind: "research_answer" as const,
  question: "Why did AAPL move?",
  answer: "**Revenue increased.**\n\nThe filing provides context. [Read the filing](https://www.apple.com/newsroom/).",
  sources: [{ title: "Apple quarterly results", domain: "apple.com", url: "https://www.apple.com/newsroom/", source_date: "2026-08-06" }],
  retrieved_at: "2026-09-09T14:32:00Z",
  anchor_symbols: ["AAPL"],
  asset_class: "equity" as const,
  offered_next_step: { kind: "research_test_single" as const, symbols: ["AAPL"] },
  owner_note: null,
  content_language: "en" as const,
  framing: "research_snapshot_not_advice" as const,
  provenance_mark: "tested_with_argus" as const,
};

export const backtestTurn = {
  kind: "backtest" as const,
  idea_title: legacyReceipt.idea_title,
  fact_bank: {
    symbols: legacyReceipt.symbols, asset_class: legacyReceipt.asset_class, benchmark_symbol: "SPY",
    config_snapshot: {
      template: "dca_accumulation", start_date: legacyReceipt.date_range.start, end_date: legacyReceipt.date_range.end,
      timeframe: "1Day", benchmark_symbol: "SPY",
      resolved_parameters: { strategy_type: "dca_accumulation", starting_capital: 0, recurring_contribution: 250, cadence: "monthly" },
      resolved_strategy: { strategy_type: "dca_accumulation", initial_capital: 0, recurring_contribution: 250, contribution_period: "monthly" },
    },
    figures: { total_return_pct: 18.4, max_drawdown_pct: -6.2, benchmark_return_pct: 9.1, delta_vs_benchmark_pct: 9.3, benchmark_comparison_claim: "beat_benchmark" as const, gross_total_return_pct: 19.2, net_total_return_pct: 18.4 },
    result_card: { execution_costs: { fee_bps: 10, slippage_bps: 5, benchmark_treatment: "same_modeled_costs" as const } },
  },
  visual: null, owner_note: legacyReceipt.owner_note, content_language: legacyReceipt.content_language,
  framing: legacyReceipt.framing, provenance_mark: legacyReceipt.provenance_mark,
};

export function toolTurnFixture() {
  const card = toolCardFixture();
  return {
    kind: "tool_result" as const, question: "Read these values.",
    cards: [0, 40].map((value) => ({ card_type: card.card_type, card_version: card.card_version,
      presentation: { ...card.presentation, answer: { ...card.presentation.answer!, value },
        inputs: card.presentation.inputs.map((input) => ({ ...input, editable: false })),
      },
    })),
    owner_note: null, content_language: "en" as const,
    framing: "computed_result_not_advice" as const, provenance_mark: "computed_with_argus" as const,
  };
}

export function legacyToolDocument() {
  const turn = toolTurnFixture();
  return { schema_version: 2 as const, ...turn.cards[0], owner_note: turn.owner_note,
    content_language: turn.content_language, framing: turn.framing, provenance_mark: turn.provenance_mark };
}

export function turnDocument(...turns: PublicReceiptTurn[]) {
  return { schema_version: 2 as const, kind: "turns" as const, turns };
}
