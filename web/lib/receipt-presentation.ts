import type { PublicReceiptPayload, PublicReceiptVisual } from "./public-receipt-contract";
import type { PublicReceiptDocument, PublicReceiptTurn, ResearchReceiptTurn } from "./public-receipt-turns";
import type { ArgusLanguage } from "./language-features";
import { formatReceiptDate, formatReceiptDateRange, interpolate, receiptCopy, receiptTranslator } from "./receipt-copy";
import { benchmarkReturn, benchmarkVerdict, receiptAssumptions, receiptPlan } from "./receipt-plan";
import { resultReadoutFacts } from "./result-readout-facts";
import { resultCardViewModel } from "./result-card-view-model";
import { signedPercentText } from "./result-figures";
import { resultReadoutPlanDetails } from "./result-readout-display";

export type ReceiptPresentation = {
  title: string; language: ArgusLanguage; stamp: string | null;
  headline?: string; verdict?: string | null; benchmark?: string | null; benchmarkSymbol?: string | null;
  rows: { label: string; value: string }[];
  visual?: PublicReceiptVisual | null;
  plan?: { heading: string; rows: { text: string; exact?: string | null }[]; assumptions: string[]; footer?: string };
  research?: { answer: string; sources: ResearchReceiptTurn["sources"]; nextStep: string | null };
  ownerNote?: string | null; framing: string;
};

/** Isolated v1 compatibility. Its display strings and markup stay frozen. */
function legacyPresentation(payload: PublicReceiptPayload, createdAt: string | null, language: ArgusLanguage): ReceiptPresentation {
  const copy = receiptCopy(language);
  const metric = (...keys: string[]) => payload.metrics.find((entry) => keys.includes(entry.key));
  const drawdown = metric("max_drawdown_pct", "max_drawdown");
  const testedWindow = formatReceiptDateRange(payload.date_range, copy, language);
  return {
    title: payload.idea_title, language: payload.content_language, stamp: formatReceiptDate(createdAt, language),
    headline: metric("total_return_pct", "contribution_return_pct", "total_return")?.value,
    verdict: benchmarkVerdict(payload, copy), benchmark: benchmarkReturn(payload), benchmarkSymbol: payload.benchmark_symbol,
    rows: [
      ...(payload.symbols.length ? [{ label: copy.fields.asset, value: payload.asset_class ? `${payload.symbols.join(", ")} · ${copy.asset_class_values[payload.asset_class]}` : payload.symbols.join(", ") }] : []),
      ...(testedWindow ? [{ label: copy.fields.dates, value: testedWindow }] : []),
      ...(drawdown ? [{ label: copy.metric_labels[drawdown.key] ?? drawdown.key, value: drawdown.value }] : []),
    ],
    visual: payload.visual,
    plan: { heading: copy.plan.heading, rows: receiptPlan(payload, copy).rows, assumptions: receiptAssumptions(payload, copy, language), footer: copy.plan.long_only },
    ownerNote: payload.owner_note, framing: copy.framing.detail,
  };
}

function turnPresentation(turn: PublicReceiptTurn, createdAt: string | null, language: ArgusLanguage): ReceiptPresentation {
  const copy = receiptCopy(language);
  const base = { language: turn.content_language, ownerNote: turn.owner_note };
  if (turn.kind === "research_answer") {
    const date = formatReceiptDate(turn.retrieved_at, language) ?? "";
    const nextStepTemplate = turn.offered_next_step ? copy.research[turn.offered_next_step.kind] : null;
    return {
      ...base, title: turn.question, stamp: interpolate(copy.research.stamp, { date }), rows: [], framing: copy.research.framing,
      research: { answer: turn.answer, sources: turn.sources, nextStep: typeof nextStepTemplate === "string" && turn.offered_next_step ? interpolate(nextStepTemplate, { symbols: turn.offered_next_step.symbols.join(", ") }) : null },
    };
  }
  const facts = resultReadoutFacts(turn.fact_bank);
  const view = resultCardViewModel({
    strategyName: turn.idea_title, period: "", metrics: [], symbols: turn.fact_bank.symbols,
    assetClass: turn.fact_bank.asset_class ?? undefined, configSnapshot: turn.fact_bank.config_snapshot,
    dateRange: facts?.dateRange, readoutFacts: facts, executionCosts: facts?.costs,
  }, { t: receiptTranslator(language), locale: language });
  return {
    ...base, title: turn.idea_title, stamp: formatReceiptDate(createdAt, language),
    headline: facts?.totalReturnPct === undefined ? undefined : signedPercentText(facts.totalReturnPct, language),
    verdict: view.evidence.benchmark.unavailable ? null : view.evidence.benchmark.value,
    benchmarkSymbol: facts?.benchmarkSymbol,
    benchmark: facts?.benchmarkReturnPct === undefined ? null : signedPercentText(facts.benchmarkReturnPct, language),
    rows: [
      { label: copy.fields.asset, value: view.symbols.join(", ") },
      { label: copy.fields.dates, value: view.periodDisplay },
      ...(view.evidence.worstDrop.unavailable ? [] : [view.evidence.worstDrop]),
    ],
    visual: turn.visual,
    plan: {
      heading: copy.plan.heading,
      rows: [
        { text: view.strategyLabel },
        ...resultReadoutPlanDetails(facts, receiptTranslator(language), language).map((text) => ({ text })),
        ...view.evidence.details.filter((row) => ![view.copy.dateRangeLabel, view.copy.startingCapitalLabel, view.copy.contributionLabel, view.copy.entryRuleLabel, view.copy.exitRuleLabel].includes(row.label)).map((row) => ({ text: `${row.label}: ${row.value}` })),
      ],
      assumptions: [view.copy.longOnlyValue, view.copy.equalWeightValue, ...view.evidence.trustGroups],
    },
    framing: copy.framing.detail,
  };
}

export function receiptPresentations(payload: PublicReceiptDocument, createdAt: string | null, language: ArgusLanguage): ReceiptPresentation[] {
  return payload.schema_version === 1 ? [legacyPresentation(payload, createdAt, language)] : payload.turns.map((turn) => turnPresentation(turn, createdAt, language));
}
