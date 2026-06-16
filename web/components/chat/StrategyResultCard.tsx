import { ChevronDown, ListTree, PencilLine, Save } from "lucide-react";
import { useTranslation } from "react-i18next";
import {
  type ResultCardDisplayCopy,
  displayResultActionLabel,
  heroDeltaEvidenceView,
} from "@/lib/result-card-display";
import { artifactStatusToneClassName } from "@/lib/artifact-status-tones";
import { assetClassDisplayLabel } from "@/lib/asset-class-display";
import { cadenceDisplayLabel } from "@/lib/cadence-display";
import { compactDateRangeDisplay } from "@/lib/date-range-display";
import { isVisibleResultAction } from "@/lib/chat-result-actions";
import { strategiesEnabled } from "@/lib/private-alpha-flags";
import { strategyDisplayLabel, strategyTypeFromResult } from "@/lib/strategy-display";
import ResultEquityChart from "./ResultEquityChart";
import type { ChatActionOption, StrategyResultPayload } from "./types";

type StrategyResultCardProps = {
  result: StrategyResultPayload;
  onAction?: (action: ChatActionOption) => void;
  appearance?: "light" | "dark";
};

const actionClassName =
  "inline-flex min-h-9 cursor-pointer items-center gap-1.5 rounded-full border border-black/10 bg-black/[0.03] px-3 py-1.5 text-[12px] font-medium tracking-tight text-black/76 transition-colors hover:border-black/18 hover:bg-black/[0.06] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/20 active:scale-[0.98] dark:border-white/10 dark:bg-white/[0.04] dark:text-white/76 dark:hover:border-white/18 dark:hover:bg-white/[0.08] dark:focus-visible:ring-white/22";

export default function StrategyResultCard({
  appearance,
  onAction,
  result,
}: StrategyResultCardProps) {
  const { t, i18n } = useTranslation();
  const resultCardCopy = resultDisplayCopy(t);
  const view = heroDeltaEvidenceView(result, {
    copy: resultCardCopy,
    locale: i18n.language,
  });
  const symbols = result.symbols ?? [];
  const resultActions = (result.actions ?? []).filter(isVisibleResultAction);
  const showBreakdownAction = resultActions.find(
    (action) => action.type === "show_breakdown",
  );
  const refineStrategyAction = resultActions.find(
    (action) => action.type === "refine_strategy",
  );
  const saveAction = strategiesEnabled
    ? resultActions.find((action) => action.type === "save_strategy")
    : undefined;
  const orderedActions: ChatActionOption[] = [];
  if (showBreakdownAction) orderedActions.push(showBreakdownAction);
  if (refineStrategyAction) orderedActions.push(refineStrategyAction);
  if (saveAction) orderedActions.push(saveAction);
  const renderedActions = result.savedStrategyId || result.savingStrategy
    ? orderedActions.filter((action) => action.type !== "save_strategy")
    : orderedActions;
  const showSavedState =
    strategiesEnabled && (result.savedStrategyId || result.savingStrategy);
  const revealClass =
    view.hero.tone === "negative"
      ? "argus-result-reveal-caution"
      : "argus-result-reveal-positive";
  const toneClassName =
    view.hero.tone === "positive"
      ? "text-[#5ba897]"
      : view.hero.tone === "negative"
        ? "text-[#d66d75]"
        : "text-[#5a677d] dark:text-[#7da0ca]";
  const trustGroups = view.trustGroups;
  const periodDisplay =
    compactDateRangeDisplay(result.dateRange, i18n.language) ?? result.period;
  const strategyLabel =
    strategyDisplayLabel(strategyTypeFromResult(result), t, result.strategyLabel) ??
    result.strategyLabel ??
    result.strategyName;

  return (
    <section
      aria-label="Hero + Delta Evidence Card"
      className={`argus-card-reveal ${revealClass} w-full overflow-hidden rounded-[20px] border border-[#c9c9cd] bg-white text-[#191c1f] dark:border-white/12 dark:bg-[#191c1f] dark:text-white`}
    >
      <div className="flex items-start justify-between gap-4 px-4 py-4 sm:px-5">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5">
            {symbols.length > 0 && <AssetSymbols symbols={symbols} />}
            <h3 className="font-display text-[18px] font-medium leading-tight tracking-[-0.18px] text-[#191c1f] dark:text-white">
              {strategyLabel}
            </h3>
          </div>
          <p className="mt-1.5 text-[13px] leading-snug tracking-[0.16px] text-[#8d969e]">
            {view.timeframeDisplay
              ? `${periodDisplay} · ${view.timeframeDisplay}`
              : periodDisplay}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          <span className={`rounded-full border px-2.5 py-1 text-[11px] font-medium tracking-tight ${artifactStatusToneClassName("neutral")}`}>
            {t("chat.simulation_complete", result.statusLabel || "Simulation Complete")}
          </span>
        </div>
      </div>

      {result.chart && (
        <ResultEquityChart
          appearanceOverride={appearance}
          chart={result.chart}
          presentation="heroDeltaEvidence"
        />
      )}

      <div className="px-4 pb-4 pt-3 sm:px-5 sm:pb-4 sm:pt-3.5">
        <div>
          <p className="text-[14px] leading-snug tracking-[0.16px] text-[#505a63] dark:text-[#8d969e]">
            {view.hero.label}
          </p>
          <p
            className={`mt-1 font-display text-[38px] font-medium leading-none tracking-[-0.38px] sm:text-[46px] ${toneClassName}`}
          >
            {view.hero.value}
          </p>
          <p className="mt-1.5 text-[15px] leading-snug tracking-[0.16px] text-[#505a63] dark:text-[#8d969e]">
            {view.hero.detail}
          </p>
        </div>

        <StatRail metrics={[view.benchmark, view.worstDrop]} />

        <TrustRail
          groups={trustGroups}
          label={t("chat.result_trust_strip_label", "Result trust context")}
        />

        <ExecutionDetails
          details={view.details}
          triggerLabel={t("chat.view_details", "View details")}
        />
      </div>

      {(renderedActions.length > 0 || showSavedState) && (
        <div className="flex flex-wrap gap-2 border-t border-[#c9c9cd]/30 px-4 py-3.5 dark:border-white/[0.06] sm:px-5">
          {renderedActions.map((action) => (
            <button
              key={action.id ?? action.type ?? action.label}
              type="button"
              onClick={() => onAction?.(action)}
              className={actionClassName}
            >
              <ResultActionIcon action={action} />
              {displayResultActionLabel(action, { copy: resultCardCopy })}
            </button>
          ))}
          {showSavedState && (
            <button
              type="button"
              disabled
              className={`inline-flex min-h-9 cursor-default items-center gap-1.5 rounded-full border px-3 py-1.5 text-[12px] font-medium tracking-tight ${artifactStatusToneClassName("success")}`}
            >
              <Save className="h-3.5 w-3.5" />
              {result.savedStrategyId ? t("chat.saved") : t("chat.saving")}
            </button>
          )}
        </div>
      )}
    </section>
  );
}

function StatRail({ metrics }: { metrics: { label: string; value: string }[] }) {
  return (
    <dl className="mt-3 grid gap-y-2.5 border-y border-[#c9c9cd]/22 py-2.5 dark:border-white/[0.04] sm:grid-cols-[minmax(0,1.55fr)_1px_minmax(104px,0.45fr)] sm:gap-x-5">
      <StatItem metric={metrics[0]} variant="benchmark" />
      <div
        aria-hidden="true"
        className="hidden h-8 self-center bg-[#c9c9cd]/18 dark:bg-white/[0.04] sm:block"
      />
      <StatItem metric={metrics[1]} />
    </dl>
  );
}

function StatItem({
  metric,
  variant = "default",
}: {
  metric?: { label: string; value: string };
  variant?: "default" | "benchmark";
}) {
  if (!metric) return null;
  const isBenchmark = variant === "benchmark";

  return (
    <div className="min-w-0">
      <dt className="text-[13px] leading-snug tracking-[0.16px] text-[#8d969e]">
        {metric.label}
      </dt>
      <dd
        className={`mt-1.5 leading-snug tracking-[-0.08px] ${isBenchmark ? "text-[15px] font-normal text-[#505a63] dark:text-[#8d969e] sm:whitespace-nowrap" : "text-[16px] font-medium text-[#191c1f] dark:text-white"}`}
      >
        {metric.value}
      </dd>
    </div>
  );
}

function TrustRail({ groups, label }: { groups: string[]; label: string }) {
  return (
    <div
      aria-label={label}
      className="mt-3 flex flex-col gap-1 text-[12px] leading-snug tracking-[0.16px] text-[#8d969e] sm:flex-row sm:flex-wrap sm:gap-x-4 sm:gap-y-1"
    >
      {groups.map((group) => (
        <p key={group}>{group}</p>
      ))}
    </div>
  );
}

function ExecutionDetails({
  details,
  triggerLabel,
}: {
  details: { label: string; value: string }[];
  triggerLabel: string;
}) {
  if (details.length === 0) return null;

  return (
    <details className="group mt-3 rounded-[14px] text-[11px] leading-snug tracking-[0.16px] text-[#8d969e]">
      <summary className="inline-flex cursor-pointer select-none items-center gap-1 rounded-full border border-black/8 bg-black/[0.02] px-2.5 py-1 font-medium text-[#505a63] transition-colors marker:text-transparent hover:border-black/14 hover:bg-black/[0.04] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/14 dark:border-white/8 dark:bg-white/[0.03] dark:text-[#8d969e] dark:hover:border-white/14 dark:hover:bg-white/[0.06] dark:focus-visible:ring-white/14">
        {triggerLabel}
        <ChevronDown className="h-3 w-3 transition-transform group-open:rotate-180" />
      </summary>
      <dl className="mt-2 grid gap-x-5 gap-y-2 rounded-[12px] bg-black/[0.018] px-3 py-2.5 dark:bg-white/[0.025] sm:grid-cols-2">
        {details.map((detail) => (
          <div
            key={`${detail.label}-${detail.value}`}
            className="grid min-w-0 grid-cols-[96px_minmax(0,1fr)] gap-x-3"
          >
            <dt className="text-[#8d969e]">{detail.label}</dt>
            <dd className="break-words font-medium text-[#191c1f] dark:text-white/76">
              {detail.value}
            </dd>
          </div>
        ))}
      </dl>
    </details>
  );
}

function ResultActionIcon({ action }: { action: ChatActionOption }) {
  if (action.type === "show_breakdown") {
    return <ListTree className="h-3.5 w-3.5" />;
  }
  if (action.type === "refine_strategy") {
    return <PencilLine className="h-3.5 w-3.5" />;
  }
  if (action.type === "save_strategy") {
    return <Save className="h-3.5 w-3.5" />;
  }
  return null;
}

function AssetSymbols({ symbols }: { symbols: string[] }) {
  return (
    <span className="flex flex-wrap gap-1.5">
      {symbols.map((symbol) => (
        <span
          key={symbol}
          className="rounded-[7px] border border-[#c9c9cd]/65 px-2 py-1 text-[12px] font-medium leading-none tracking-[0.16px] text-[#505a63] dark:border-white/14 dark:text-[#8d969e]"
        >
          {symbol}
        </span>
      ))}
    </span>
  );
}

function resultDisplayCopy(t: ReturnType<typeof useTranslation>["t"]): ResultCardDisplayCopy {
  return {
    endingValueLabel: t("chat.result_card.ending_value", "Ending value"),
    totalReturnLabel: t("chat.result_card.total_return", "Total return"),
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
    saveAction: t("chat.result_card.save", "Save"),
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
    lowestValueLabel: t("chat.result_card.details.lowest_value", "Lowest value"),
    dateRangeLabel: t("chat.result_card.details.date_range", "Date range"),
    peakValueLabel: t("chat.result_card.details.peak_value", "Peak value"),
    lowestValueLabel: t("chat.result_card.details.lowest_value", "Lowest value"),
    timeframeLabel: t("chat.result_card.details.timeframe", "Timeframe"),
    sideLabel: t("chat.result_card.details.side", "Side"),
    allocationLabel: t("chat.result_card.details.allocation", "Allocation"),
    benchmarkLabel: t("chat.result_card.details.benchmark", "Benchmark"),
    cadenceLabel: t("chat.result_card.details.cadence", "Cadence"),
    cadenceValueLabel: (cadence) => cadenceDisplayLabel(cadence, t) ?? cadence,
    contributionLabel: t(
      "chat.result_card.details.contribution",
      "Contribution",
    ),
    entryRuleLabel: t("chat.result_card.details.entry_rule", "Entry rule"),
    exitRuleLabel: t("chat.result_card.details.exit_rule", "Exit rule"),
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
