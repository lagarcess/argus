import type { TFunction } from "i18next";

import type { StrategyResultPayload } from "@/components/chat/types";
import { assetClassDisplayLabel } from "@/lib/asset-class-display";
import { contributionPhrase } from "@/lib/contribution-period-display";
import { compactDateRangeDisplay } from "@/lib/date-range-display";
import {
  heroDeltaEvidenceView,
  type HeroDeltaEvidenceView,
  type ResultCardDisplayCopy,
} from "@/lib/result-card-display";
import {
  strategyDisplayLabel,
  strategyTypeFromResult,
} from "@/lib/strategy-display";

export type ResultCardViewModel = {
  strategyLabel: string;
  symbols: string[];
  statusLabel: string;
  periodDisplay: string;
  evidence: HeroDeltaEvidenceView;
  copy: ResultCardDisplayCopy;
};

/** The one localized read of a result payload: the card paints it and Copy
 * serializes it, so the clipboard cannot drift back to backend English. */
export function resultCardViewModel(
  result: StrategyResultPayload,
  { t, locale }: { t: TFunction; locale: string },
): ResultCardViewModel {
  const copy = resultDisplayCopy(t);
  return {
    strategyLabel:
      strategyDisplayLabel(strategyTypeFromResult(result), t, result.strategyLabel) ??
      result.strategyLabel ??
      result.strategyName,
    symbols: result.symbols ?? [],
    statusLabel: t(
      "chat.simulation_complete",
      result.statusLabel || "Simulation Complete",
    ),
    periodDisplay: compactDateRangeDisplay(result.dateRange, locale) ?? result.period,
    evidence: heroDeltaEvidenceView(result, { copy, locale }),
    copy,
  };
}

export function resultDisplayCopy(t: TFunction): ResultCardDisplayCopy {
  return {
    endingValueLabel: t("chat.result_card.ending_value", "Ending value"),
    totalReturnLabel: t("chat.result_card.total_return", "Total return"),
    contributionReturnLabel: t(
      "chat.result_card.contribution_return",
      "Return on contributions",
    ),
    comparedWithBenchmarkLabel: t(
      "chat.result_card.compared_with_benchmark",
      "Compared with benchmark",
    ),
    comparedWithSymbolLabel: (symbol) =>
      t("chat.result_card.compared_with_symbol", {
        defaultValue: "Compared with {{symbol}}",
        symbol,
      }),
    worstDropLabel: t("chat.result_card.worst_drop", "Worst drop"),
    explainResultAction: t("chat.result_card.explain_result", "Explain result"),
    refineIdeaAction: t("chat.result_card.refine_idea", "Refine idea"),
    unavailable: t("chat.result_card.unavailable", "Unavailable"),
    returnUnavailable: t(
      "chat.result_card.return_unavailable",
      "return unavailable",
    ),
    changeNoun: t("chat.result_card.change", "change"),
    gainNoun: t("chat.result_card.gain", "gain"),
    lossNoun: t("chat.result_card.loss", "loss"),
    totalReturnSuffix: t(
      "chat.result_card.total_return_suffix",
      "total return",
    ),
    contributionReturnSuffix: t(
      "chat.result_card.contribution_return_suffix",
      "return on contributions",
    ),
    benchmarkUnavailable: t(
      "chat.result_card.benchmark_unavailable",
      "Benchmark unavailable",
    ),
    percentagePoints: (value) =>
      t("chat.result_card.percentage_points", {
        defaultValue: "{{value}} percentage points",
        value,
      }),
    inLineWith: (symbol) =>
      t("chat.result_card.in_line_with", {
        defaultValue: "In line with {{symbol}}",
        symbol,
      }),
    beatBy: (value) =>
      t("chat.result_card.beat_by", {
        defaultValue: "Beat by {{value}}",
        value,
      }),
    laggedBy: (value) =>
      t("chat.result_card.lagged_by", {
        defaultValue: "Lagged by {{value}}",
        value,
      }),
    assetClassLabel: (assetClass) =>
      assetClassDisplayLabel(assetClass, t) ?? assetClass,
    trustStrip: t(
      "chat.result_trust_strip",
      "Historical simulation · No fees/slippage · Not advice",
    ),
    startingCapitalLabel: t(
      "chat.result_card.details.starting_capital",
      "Starting capital",
    ),
    totalContributedLabel: t(
      "chat.result_card.details.total_contributed",
      "Total contributed",
    ),
    peakValueLabel: t("chat.result_card.details.peak_value", "Peak value"),
    lowestValueLabel: t(
      "chat.result_card.details.lowest_value",
      "Lowest value",
    ),
    dateRangeLabel: t("chat.result_card.details.date_range", "Date range"),
    timeframeLabel: t("chat.result_card.details.timeframe", "Timeframe"),
    sideLabel: t("chat.result_card.details.side", "Side"),
    allocationLabel: t("chat.result_card.details.allocation", "Allocation"),
    benchmarkLabel: t("chat.result_card.details.benchmark", "Benchmark"),
    contributionPhrase: (amount, period) => contributionPhrase(amount, period, t),
    contributionLabel: t(
      "chat.result_card.details.contribution",
      "Contribution",
    ),
    entryRuleLabel: t("chat.result_card.details.entry_rule", "Entry rule"),
    exitRuleLabel: t("chat.result_card.details.exit_rule", "Exit rule"),
    grossReturnLabel: t("chat.result_card.details.gross_return", "Gross return"),
    netReturnLabel: t("chat.result_card.details.net_return", "Net of costs"),
    modeledCostsLabel: t(
      "chat.result_card.details.modeled_costs",
      "Costs modeled",
    ),
    modeledCostsValue: (feeBps, slippageBps) =>
      t("chat.result_card.details.modeled_costs_value", {
        defaultValue: "{{fee}} bps fee + {{slippage}} bps slippage",
        fee: feeBps,
        slippage: slippageBps,
      }),
    benchmarkSameCostsValue: (benchmark) =>
      t("chat.result_card.details.benchmark_same_costs", {
        defaultValue: "{{benchmark}} (same modeled costs)",
        benchmark,
      }),
    dailyData: t("chat.result_card.timeframe.daily", "Daily data"),
    hourlyData: t("chat.result_card.timeframe.hourly", "Hourly data"),
    intervalData: (amount, unit) =>
      t("chat.result_card.timeframe.interval", {
        amount,
        defaultValue: "{{amount}}-{{unit}} data",
        unit,
      }),
    timeframeData: (value) =>
      t("chat.result_card.timeframe.generic", {
        defaultValue: "{{value}} data",
        value,
      }),
  };
}
