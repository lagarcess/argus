import type { AssetClass } from "./argus-types";
import type { PublicReceiptDateRange, PublicReceiptPayload, PublicReceiptVisual } from "./public-receipt-contract";
import { parseToolPresentation, type ToolCardPresentation } from "./tool-result-card";

export type ReceiptKind = "backtest" | "research_answer" | "tool_result" | "mixed";
export type ReceiptRefusalReason = "not_completed" | "unsupported_turn" | "unsupported_shape" | "missing_sources" | "degraded" | "memory_used" | "missing_question" | "text_too_long" | "unsafe_text" | "unlisted_url" | "invalid_selection" | "preview_changed" | "invalid_source" | "unsupported_backtest";
export type ReceiptRefusalField = "question" | "answer" | "owner_note" | "sources";

type ReceiptRuleSeries = {
  kind: "price" | "volume" | "indicator"; key?: string | null; field?: "open" | "high" | "low" | "close" | null;
  period?: number | null; output?: string | null;
  parameters?: { fast?: number | null; slow?: number | null; signal?: number | null; length?: number | null; std?: number | null } | null;
};
type ReceiptRuleGroup = { combinator?: "all" | "any"; conditions: { left: number | ReceiptRuleSeries; right: number | ReceiptRuleSeries; operator: "lt" | "lte" | "gt" | "gte" | "cross_above" | "cross_below" }[] };
type ReceiptRuleSpec = { entry?: ReceiptRuleGroup | null; exit?: ReceiptRuleGroup | null };
type ReceiptLegacyRule = {
  type?: string | null; indicator?: string | null; period?: number | null; threshold?: number | null; direction?: string | null;
  fast_indicator?: string | null; fast_period?: number | null; slow_indicator?: string | null; slow_period?: number | null; signal_period?: number | null;
};
type ReceiptParameters = {
  strategy_type?: string | null; starting_capital?: number | null; recurring_contribution?: number | null; cadence?: string | null;
  timeframe?: string | null; benchmark_symbol?: string | null; indicator?: string | null; indicator_period?: number | null;
  entry_threshold?: number | null; exit_threshold?: number | null; rule_spec?: ReceiptRuleSpec | null;
};
/** Mirrors the closed public subset of the existing result fact bank. */
export type PublicReceiptFactBank = {
  symbols: string[]; asset_class?: AssetClass | null; benchmark_symbol?: string | null;
  config_snapshot: {
    template?: string | null; start_date?: string | null; end_date?: string | null; date_range?: PublicReceiptDateRange | null;
    starting_capital?: number | null; timeframe?: string | null; benchmark_symbol?: string | null;
    resolved_strategy?: {
      strategy_type?: string | null; initial_capital?: number | null; capital_amount?: number | null; recurring_contribution?: number | null;
      contribution_period?: string | null; cadence?: string | null; entry_rule?: ReceiptLegacyRule | null; exit_rule?: ReceiptLegacyRule | null; rule_spec?: ReceiptRuleSpec | null;
    } | null;
    resolved_parameters?: ReceiptParameters | null; parameters?: ReceiptParameters | null;
  };
  figures: {
    total_return_pct?: number | null; benchmark_return_pct?: number | null; delta_vs_benchmark_pct?: number | null;
    benchmark_comparison_claim?: "beat_benchmark" | "lagged_benchmark" | "matched_benchmark" | "unknown" | null; max_drawdown_pct?: number | null; gross_total_return_pct?: number | null; net_total_return_pct?: number | null;
  };
  result_card: { execution_costs?: { fee_bps?: number | null; slippage_bps?: number | null; benchmark_treatment?: "same_modeled_costs" | null } | null };
};
type ReceiptTurnBase = {
  owner_note?: string | null; content_language: "en" | "es-419"; provenance_mark: "tested_with_argus";
};
export type ResearchReceiptTurn = ReceiptTurnBase & {
  kind: "research_answer"; question: string; answer: string;
  sources: { title: string; domain: string; url: string; source_date?: string | null }[];
  retrieved_at: string; anchor_symbols: string[]; asset_class?: AssetClass | null;
  offered_next_step?: { kind: "research_test_single" | "research_test_versus"; symbols: string[] } | null;
  framing: "research_snapshot_not_advice";
};
export type BacktestReceiptTurn = ReceiptTurnBase & {
  kind: "backtest"; idea_title: string; fact_bank: PublicReceiptFactBank; visual?: PublicReceiptVisual | null;
  framing: "historical_simulation_not_advice";
};
export type PublicToolReceiptCard = { card_type: string; card_version: 1; presentation: ToolCardPresentation };
type ToolReceiptBase = {
  owner_note?: string | null; content_language: "en" | "es-419";
  framing: "computed_result_not_advice"; provenance_mark: "computed_with_argus";
};
export type ToolReceiptTurn = ToolReceiptBase & { kind: "tool_result"; question: string; cards: PublicToolReceiptCard[] };
/** Frozen registry snapshots from before selected-turn sharing remain read-only. */
export type LegacyToolReceiptDocument = ToolReceiptBase & PublicToolReceiptCard & { schema_version: 2 };
export type PublicReceiptTurn = ResearchReceiptTurn | BacktestReceiptTurn | ToolReceiptTurn;
export type SelectedReceiptDocument = { schema_version: 2; kind: "turns"; turns: PublicReceiptTurn[] };
export type PublicReceiptDocument = PublicReceiptPayload | SelectedReceiptDocument | LegacyToolReceiptDocument;

export function isSelectedReceiptDocument(payload: PublicReceiptDocument): payload is SelectedReceiptDocument {
  return payload.schema_version === 2 && "kind" in payload && payload.kind === "turns";
}

export function receiptDocumentLanguage(payload: PublicReceiptDocument): "en" | "es-419" {
  return isSelectedReceiptDocument(payload) ? payload.turns[0].content_language : payload.content_language;
}

export function receiptDocumentKind(payload: PublicReceiptDocument): ReceiptKind {
  if (payload.schema_version === 1) return "backtest";
  if (!isSelectedReceiptDocument(payload)) return "tool_result";
  const first = payload.turns[0].kind;
  return payload.turns.every((turn) => turn.kind === first) ? first : "mixed";
}

const record = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const only = (value: Record<string, unknown>, keys: string[]) => Object.keys(value).every((key) => keys.includes(key));
const toolBaseKeys = ["owner_note", "content_language", "framing", "provenance_mark"];
function toolBase(value: Record<string, unknown>): boolean {
  return (value.owner_note == null || typeof value.owner_note === "string") &&
    (value.content_language === "en" || value.content_language === "es-419") &&
    value.framing === "computed_result_not_advice" && value.provenance_mark === "computed_with_argus";
}
function toolCard(value: unknown): boolean {
  if (!record(value) || typeof value.card_type !== "string" || !value.card_type.trim() || value.card_version !== 1) return false;
  const presentation = parseToolPresentation(value.presentation);
  return Boolean(presentation?.answer) && presentation?.narrative == null;
}
export function receiptDocumentSupported(payload: unknown): payload is PublicReceiptDocument {
  if (!record(payload)) return false;
  if (payload.schema_version === 1) return true;
  if (payload.schema_version !== 2) return false;
  if (payload.kind === "turns") return only(payload, ["schema_version", "kind", "turns"]) &&
    Array.isArray(payload.turns) && payload.turns.length > 0 && payload.turns.length <= 4 && payload.turns.every((turn) => {
      if (!record(turn)) return false;
      if (turn.kind === "backtest" || turn.kind === "research_answer") return true;
      return turn.kind === "tool_result" && toolBase(turn) &&
        only(turn, ["kind", "question", "cards", ...toolBaseKeys]) && typeof turn.question === "string" && Boolean(turn.question.trim()) &&
        Array.isArray(turn.cards) && turn.cards.length > 0 && turn.cards.length <= 8 &&
        turn.cards.every((card) => record(card) && only(card, ["card_type", "card_version", "presentation"]) && toolCard(card));
    });
  return only(payload, ["schema_version", "card_type", "card_version", "presentation", ...toolBaseKeys]) && toolBase(payload) && toolCard(payload);
}
