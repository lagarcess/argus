import { useEffect, useState } from "react";
import {
  CalendarClock,
  Check,
  ChevronDown,
  CircleX,
  Eye,
  FileText,
  ListTree,
  PencilLine,
  Save,
  TrendingUp,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { createEvidenceDecision, type DecisionState } from "@/lib/argus-api";
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
import {
  strategyDisplayLabel,
  strategyTypeFromResult,
} from "@/lib/strategy-display";
import ResultEquityChart from "./ResultEquityChart";
import type { ChatActionOption, StrategyResultPayload } from "./types";

type StrategyResultCardProps = {
  result: StrategyResultPayload;
  onAction?: (action: ChatActionOption) => void;
  appearance?: "light" | "dark";
};

const actionClassName =
  "inline-flex min-h-9 cursor-pointer items-center gap-1.5 rounded-full border border-black/10 bg-black/[0.03] px-3 py-1.5 text-[12px] font-medium tracking-tight text-black/76 transition-colors hover:border-black/18 hover:bg-black/[0.06] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/20 active:scale-[0.98] dark:border-white/10 dark:bg-white/[0.04] dark:text-white/76 dark:hover:border-white/18 dark:hover:bg-white/[0.08] dark:focus-visible:ring-white/22";

const decisionOptions: DecisionState[] = [
  "watching",
  "promising",
  "rejected",
  "revisit_later",
];

export default function StrategyResultCard({
  appearance,
  onAction,
  result,
}: StrategyResultCardProps) {
  const { t, i18n } = useTranslation();
  const [isDecisionOpen, setIsDecisionOpen] = useState(false);
  const [selectedDecisionState, setSelectedDecisionState] =
    useState<DecisionState>(result.decisionState ?? "watching");
  const [savedDecisionState, setSavedDecisionState] =
    useState<DecisionState | null>(result.decisionState ?? null);
  const [decisionNote, setDecisionNote] = useState("");
  const [isSavingDecision, setIsSavingDecision] = useState(false);
  const [decisionSaveFailed, setDecisionSaveFailed] = useState(false);
  useEffect(() => {
    setSavedDecisionState(result.decisionState ?? null);
    if (result.decisionState) {
      setSelectedDecisionState(result.decisionState);
    }
  }, [result.decisionState]);
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
  const renderedActions =
    result.savedStrategyId || result.savingStrategy
      ? orderedActions.filter((action) => action.type !== "save_strategy")
      : orderedActions;
  const showSavedState =
    strategiesEnabled && (result.savedStrategyId || result.savingStrategy);
  const visibleDecisionState =
    savedDecisionState ?? result.decisionState ?? null;
  const canAddDecision =
    Boolean(result.evidenceArtifactId) && !visibleDecisionState;
  const showActionRail =
    renderedActions.length > 0 ||
    Boolean(showSavedState) ||
    canAddDecision ||
    Boolean(visibleDecisionState);
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
    strategyDisplayLabel(
      strategyTypeFromResult(result),
      t,
      result.strategyLabel,
    ) ??
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
          {/* Passive status, not an action: plain muted text so it cannot be
              mistaken for another clickable pill. */}
          <span className="text-[11px] font-medium tracking-[0.16px] text-[#8d969e] dark:text-white/45">
            {t(
              "chat.simulation_complete",
              result.statusLabel || "Simulation Complete",
            )}
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

      {showActionRail && (
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
          {visibleDecisionState && (
            <span className="inline-flex min-h-9 items-center gap-1.5 rounded-full border border-black/10 bg-black/[0.02] px-3 py-1.5 text-[12px] font-medium tracking-tight text-[#505a63] dark:border-white/10 dark:bg-white/[0.03] dark:text-[#8d969e]">
              <FileText className="h-3.5 w-3.5" />
              {t("chat.result_card.decision", {
                state: decisionStateLabel(visibleDecisionState, t),
              })}
            </span>
          )}
          {canAddDecision && (
            <button
              type="button"
              onClick={() => {
                setDecisionSaveFailed(false);
                setIsDecisionOpen((current) => !current);
              }}
              className={actionClassName}
            >
              <FileText className="h-3.5 w-3.5" />
              {t("chat.result_card.add_decision", "Add decision")}
            </button>
          )}
        </div>
      )}

      {canAddDecision && isDecisionOpen && (
        <div className="border-t border-[#c9c9cd]/30 px-4 py-4 dark:border-white/[0.06] sm:px-5">
          <div className="flex flex-wrap gap-2">
            {decisionOptions.map((state) => (
              <button
                key={state}
                type="button"
                onClick={() => {
                  setSelectedDecisionState(state);
                  setDecisionSaveFailed(false);
                }}
                className={decisionChipClassName(
                  state,
                  selectedDecisionState === state,
                )}
              >
                <DecisionStateIcon state={state} />
                {decisionStateLabel(state, t)}
              </button>
            ))}
          </div>
          <textarea
            value={decisionNote}
            onChange={(event) => setDecisionNote(event.target.value)}
            placeholder={t(
              "chat.result_card.decision_note_placeholder",
              "Optional note for future you",
            )}
            className="mt-3 min-h-20 w-full resize-y rounded-[14px] border border-black/10 bg-white px-3 py-2 text-[13px] leading-relaxed text-[#191c1f] outline-none transition-colors placeholder:text-[#8d969e] focus:border-black/24 focus:ring-2 focus:ring-black/8 dark:border-white/10 dark:bg-[#1f2225] dark:text-white dark:focus:border-white/20 dark:focus:ring-white/10"
          />
          {decisionSaveFailed && (
            <p className="mt-2 text-[12px] text-[#d66d75]">
              {t(
                "chat.error_generic",
                "Something went wrong. Please try again.",
              )}
            </p>
          )}
          <div className="mt-3 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => {
                setIsDecisionOpen(false);
                setDecisionSaveFailed(false);
              }}
              className="inline-flex min-h-9 items-center rounded-full border border-black/10 px-3 py-1.5 text-[12px] font-medium text-[#505a63] transition-colors hover:bg-black/[0.03] dark:border-white/10 dark:text-[#8d969e] dark:hover:bg-white/[0.05]"
            >
              {t("common.cancel", "Cancel")}
            </button>
            <button
              type="button"
              disabled={isSavingDecision}
              onClick={async () => {
                if (!result.evidenceArtifactId || isSavingDecision) return;
                setIsSavingDecision(true);
                setDecisionSaveFailed(false);
                try {
                  const response = await createEvidenceDecision(
                    result.evidenceArtifactId,
                    {
                      decision_state: selectedDecisionState,
                      note: decisionNote,
                    },
                  );
                  setSavedDecisionState(response.decision.decision_state);
                  setDecisionNote("");
                  setIsDecisionOpen(false);
                } catch {
                  setDecisionSaveFailed(true);
                } finally {
                  setIsSavingDecision(false);
                }
              }}
              className="inline-flex min-h-9 items-center gap-1.5 rounded-full bg-[#191c1f] px-3.5 py-1.5 text-[12px] font-medium text-white transition-colors hover:bg-black disabled:cursor-not-allowed disabled:opacity-55 dark:bg-white dark:text-[#191c1f] dark:hover:bg-white/90"
            >
              <Check className="h-3.5 w-3.5" />
              {t("chat.result_card.save_decision", "Save decision")}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}

function decisionStateLabel(
  state: DecisionState,
  t: ReturnType<typeof useTranslation>["t"],
) {
  const fallback: Record<DecisionState, string> = {
    watching: "Watching",
    promising: "Promising",
    rejected: "Rejected",
    revisit_later: "Revisit later",
  };
  return t(`chat.result_card.decision_states.${state}`, fallback[state]);
}

function decisionChipClassName(state: DecisionState, selected: boolean) {
  const base =
    "inline-flex min-h-9 items-center gap-1.5 rounded-full border px-3 py-1.5 text-[12px] font-medium tracking-tight transition-colors focus-visible:outline-none focus-visible:ring-2 active:scale-[0.98]";
  if (selected) {
    switch (state) {
      case "promising":
        return `${base} border-[#5ba897]/28 bg-[#5ba897]/10 text-[#3f816f] focus-visible:ring-[#5ba897]/20 dark:text-[#7bc1ad]`;
      case "rejected":
        return `${base} border-[#d66d75]/30 bg-[#d66d75]/10 text-[#ad4e56] focus-visible:ring-[#d66d75]/18 dark:text-[#e58c93]`;
      case "revisit_later":
        return `${base} border-[#b79246]/30 bg-[#b79246]/10 text-[#92722d] focus-visible:ring-[#b79246]/18 dark:text-[#d7b56f]`;
      case "watching":
      default:
        return `${base} border-[#6f8fb8]/30 bg-[#6f8fb8]/10 text-[#4f6f98] focus-visible:ring-[#6f8fb8]/18 dark:text-[#91afd1]`;
    }
  }
  switch (state) {
    case "promising":
      return `${base} border-[#5ba897]/18 bg-transparent text-[#4f8d7f] hover:bg-[#5ba897]/8 focus-visible:ring-[#5ba897]/14 dark:text-[#8abdad]`;
    case "rejected":
      return `${base} border-[#d66d75]/18 bg-transparent text-[#aa5c64] hover:bg-[#d66d75]/8 focus-visible:ring-[#d66d75]/14 dark:text-[#d9949a]`;
    case "revisit_later":
      return `${base} border-[#b79246]/18 bg-transparent text-[#8b743d] hover:bg-[#b79246]/8 focus-visible:ring-[#b79246]/14 dark:text-[#cdb074]`;
    case "watching":
    default:
      return `${base} border-[#6f8fb8]/18 bg-transparent text-[#5d7698] hover:bg-[#6f8fb8]/8 focus-visible:ring-[#6f8fb8]/14 dark:text-[#9eb4cf]`;
  }
}

function DecisionStateIcon({ state }: { state: DecisionState }) {
  if (state === "promising") return <TrendingUp className="h-3.5 w-3.5" />;
  if (state === "rejected") return <CircleX className="h-3.5 w-3.5" />;
  if (state === "revisit_later")
    return <CalendarClock className="h-3.5 w-3.5" />;
  return <Eye className="h-3.5 w-3.5" />;
}

function StatRail({
  metrics,
}: {
  metrics: { label: string; value: string }[];
}) {
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

function resultDisplayCopy(
  t: ReturnType<typeof useTranslation>["t"],
): ResultCardDisplayCopy {
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
    lowestValueLabel: t(
      "chat.result_card.details.lowest_value",
      "Lowest value",
    ),
    dateRangeLabel: t("chat.result_card.details.date_range", "Date range"),
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
