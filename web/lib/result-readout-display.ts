import type { TFunction } from "i18next";
import { contributionPhrase } from "./contribution-period-display";
import { compactDateRangeDisplay } from "./date-range-display";
import { formatCurrency } from "./result-card-display";
import { benchmarkComparisonView, signedPercentFigure } from "./result-figures";
import type { ResultReadoutFacts } from "./result-readout-facts";
import { strategyDisplayLabel } from "./strategy-display";
import { resultRuleGroupText } from "./result-readout-rules";

function figure(value: number, locale: string): string {
  return new Intl.NumberFormat(locale, { maximumFractionDigits: 2 }).format(value);
}

export function resultQuickTakeText(facts: ResultReadoutFacts | null | undefined, t: TFunction, locale: string): string {
  if (!facts || facts.totalReturnPct === undefined) return t("chat.result_readout.unavailable");
  const strategy = strategyDisplayLabel(facts.strategyType, t) ?? t("chat.result_readout.strategy");
  const period = compactDateRangeDisplay(facts.dateRange, locale);
  const lines = [t(period ? "chat.result_readout.tested_period" : "chat.result_readout.tested", {
    strategy, symbols: facts.symbols.join(", ") || t("chat.result_readout.assets_unavailable"), period,
  }), t(facts.strategyType === "dca_accumulation" ? "chat.result_readout.contribution_return" : "chat.result_readout.total_return", {
    value: signedPercentFigure(facts.totalReturnPct),
  })];
  if (facts.benchmarkSymbol && facts.benchmarkDeltaPct !== undefined) {
    // The engine's gap, printed by the same formatter the card uses.
    const comparison = benchmarkComparisonView(facts.benchmarkDeltaPct);
    lines.push(t(`chat.result_readout.${comparison.claim}`, {
      symbol: facts.benchmarkSymbol, value: comparison.magnitude,
    }));
  } else {
    lines.push(t("chat.result_readout.comparison_unavailable"));
  }
  if (facts.maxDrawdownPct !== undefined) lines.push(t("chat.result_readout.drawdown", { value: signedPercentFigure(facts.maxDrawdownPct) }));
  return lines.join(" ");
}

export function resultBreakdownText(facts: ResultReadoutFacts | null | undefined, t: TFunction, locale: string): string {
  const readout = resultQuickTakeText(facts, t, locale);
  if (!facts) return readout;
  const details: string[] = resultReadoutRuleDetails(facts, t, locale).map((rule) => `${rule.label}: ${rule.value}`);
  if (facts.startingCapital !== undefined) details.push(t("chat.result_readout.starting_capital", { value: formatCurrency(facts.startingCapital, locale) }));
  if (facts.recurringContribution !== undefined) details.push(t("chat.result_readout.contribution", {
    value: contributionPhrase(formatCurrency(facts.recurringContribution, locale), facts.contributionPeriod, t),
  }));
  if (facts.benchmarkSymbol && facts.benchmarkReturnPct !== undefined) details.push(t("chat.result_readout.benchmark_return", {
    symbol: facts.benchmarkSymbol, value: signedPercentFigure(facts.benchmarkReturnPct),
  }));
  const costs = facts.costs;
  if (costs && costs.fee_bps != null && costs.slippage_bps != null) details.push(t("chat.result_readout.costs", {
    fee: figure(costs.fee_bps, locale), slippage: figure(costs.slippage_bps, locale),
  }));
  if (costs?.gross_total_return_pct != null) details.push(t("chat.result_readout.gross_return", { value: signedPercentFigure(costs.gross_total_return_pct) }));
  if (costs?.net_total_return_pct != null) details.push(t("chat.result_readout.net_return", { value: signedPercentFigure(costs.net_total_return_pct) }));
  return [readout, ...details, t("chat.result_readout.historical")].join("\n\n");
}

export function resultReadoutRuleDetails(facts: ResultReadoutFacts | null | undefined, t: TFunction, locale: string): { label: string; value: string }[] {
  if (facts?.rules?.length) return facts.rules.map((group) => ({
    label: t(`chat.result_card.details.${group.side}_rule`), value: resultRuleGroupText(group, t, locale),
  }));
  const rules: { label: string; value: string }[] = [];
  const indicator = facts?.indicator;
  if (indicator?.entryThreshold !== undefined) rules.push({ label: t("chat.result_card.details.entry_rule"), value: t("chat.result_readout.rsi_entry", { threshold: figure(indicator.entryThreshold, locale), period: indicator.period ?? t("chat.result_readout.parameter_unavailable") }) });
  if (indicator?.exitThreshold !== undefined) rules.push({ label: t("chat.result_card.details.exit_rule"), value: t("chat.result_readout.rsi_exit", { threshold: figure(indicator.exitThreshold, locale), period: indicator.period ?? t("chat.result_readout.parameter_unavailable") }) });
  return rules;
}
