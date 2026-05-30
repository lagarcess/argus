import { ListTree, PencilLine, Save } from "lucide-react";
import { StrategyResultPayload } from "./types";
import { useTranslation } from "react-i18next";
import { splitPeriodDisplay } from "./card-formatting";
import ResultEquityChart from "./ResultEquityChart";
import { type ChatActionOption } from "./types";
import { strategiesEnabled } from "@/lib/private-alpha-flags";
import { displayResultActionLabel } from "@/lib/result-card-display";

type StrategyResultCardProps = {
  result: StrategyResultPayload;
  onAction?: (action: ChatActionOption) => void;
};

export default function StrategyResultCard({ result, onAction }: StrategyResultCardProps) {
  const { t } = useTranslation();
  const period = splitPeriodDisplay(result.period);
  const symbols = result.symbols ?? [];
  const resultActions = result.actions ?? [];
  const showBreakdownAction = resultActions.find((action) => action.type === "show_breakdown");
  const refineStrategyAction = resultActions.find((action) => action.type === "refine_strategy");
  const saveAction = strategiesEnabled
    ? resultActions.find((action) => action.type === "save_strategy")
    : undefined;
  const orderedActions = [
    showBreakdownAction,
    refineStrategyAction,
    saveAction,
    ...resultActions.filter(
      (action) =>
        action.type !== "show_breakdown" &&
        action.type !== "refine_strategy" &&
        action.type !== "save_strategy",
    ),
  ].filter((action): action is ChatActionOption => Boolean(action));
  const renderedActions = result.savedStrategyId || result.savingStrategy
    ? orderedActions.filter((action) => action.type !== "save_strategy")
    : orderedActions;
  const showSavedState = strategiesEnabled && (result.savedStrategyId || result.savingStrategy);
  const returnMetric = result.metrics.find((metric) => metric.label.toLowerCase().includes("return"));
  const isNegative = returnMetric?.value.trim().startsWith("-");
  const revealClass = isNegative ? "argus-result-reveal-caution" : "argus-result-reveal-positive";
  const assumptionLine = result.assumptions?.filter(Boolean).join(" · ");
  return (
    <section className={`argus-card-reveal w-full rounded-[20px] border border-black/12 dark:border-white/12 bg-white dark:bg-[#1d2023] overflow-hidden ${revealClass}`}>
      <div className="flex items-center justify-between gap-3 px-4 sm:px-5 py-3.5 border-b border-black/8 dark:border-white/8">
        <div className="min-w-0">
          {symbols.length > 0 ? (
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
              <AssetSymbols symbols={symbols} />
              <span className="text-[14px] font-medium leading-snug tracking-tight text-black dark:text-white sm:text-[15px]">
                {result.strategyLabel ?? result.strategyName}
              </span>
            </div>
          ) : (
            <p className="text-[14px] sm:text-[15px] font-medium leading-snug tracking-tight text-black dark:text-white">
              {result.strategyName}
            </p>
          )}
          <p className="mt-1 text-[12px] leading-snug text-black/45 dark:text-white/45">
            <span className="block">{period.label}</span>
            {period.dates && <span className="block">{period.dates}</span>}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className="rounded-full border border-black/10 dark:border-white/10 bg-black/[0.03] dark:bg-white/[0.04] px-2.5 py-1 text-[11px] font-medium tracking-tight text-black/70 dark:text-white/70">
            {result.statusLabel || t('chat.simulation_complete')}
          </span>
        </div>
      </div>

      {result.chart && <ResultEquityChart chart={result.chart} />}

      <div className="px-4 sm:px-5 py-5">
        {result.metrics.length > 0 && (
          <div className="mb-6">
            <dt className="text-[12px] uppercase tracking-wider text-black/45 dark:text-white/45 font-semibold">
              {result.metrics[0].label}
            </dt>
            <dd className="text-[32px] sm:text-[40px] font-bold tracking-tight text-black dark:text-white leading-tight">
              {result.metrics[0].value}
            </dd>
          </div>
        )}

        <dl className="grid grid-cols-2 gap-4">
          {result.metrics.slice(1).map((metric) => (
            <div key={metric.label} className="flex flex-col gap-0.5">
              <dt className="text-[12px] leading-snug text-black/45 dark:text-white/45">{metric.label}</dt>
              <dd className="whitespace-normal break-words text-[15px] font-semibold leading-snug tracking-tight text-black dark:text-white">
                {metric.value}
              </dd>
            </div>
          ))}
        </dl>
      </div>

      {(renderedActions.length > 0 || showSavedState) && (
        <div className="flex flex-wrap gap-2 border-t border-black/8 px-4 py-3 dark:border-white/8 sm:px-5">
          {renderedActions.map((action) => (
            <button
              key={action.id ?? action.type ?? action.label}
              type="button"
              onClick={() => onAction?.(action)}
              className="inline-flex min-h-9 cursor-pointer items-center gap-1.5 rounded-full border border-black/10 bg-black/[0.03] px-3 py-1.5 text-[12px] font-medium tracking-tight text-black/76 transition-colors hover:border-black/18 hover:bg-black/[0.06] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/20 active:scale-[0.98] dark:border-white/10 dark:bg-white/[0.04] dark:text-white/76 dark:hover:border-white/18 dark:hover:bg-white/[0.08] dark:focus-visible:ring-white/22"
            >
              <ResultActionIcon action={action} />
              {displayResultActionLabel(action)}
            </button>
          ))}
          {showSavedState && (
            <button
              type="button"
              disabled
              className="inline-flex min-h-9 cursor-default items-center gap-1.5 rounded-full border border-[#70a38d]/25 bg-[#70a38d]/10 px-3 py-1.5 text-[12px] font-medium tracking-tight text-[#4f806d] dark:border-[#70a38d]/30 dark:bg-[#70a38d]/12 dark:text-[#9bc6b4]"
            >
              <Save className="h-3.5 w-3.5" />
              {result.savedStrategyId ? t("chat.saved") : t("chat.saving")}
            </button>
          )}
        </div>
      )}

      <div className="px-4 py-3 border-t border-black/8 dark:border-white/8 sm:px-5">
        <div className="flex flex-col gap-1.5">
          <p
            aria-label={t("chat.result_trust_strip_label", "Result trust context")}
            className="text-[11px] font-medium leading-snug text-black/50 dark:text-white/50"
          >
            {t(
              "chat.result_trust_strip",
              "Historical simulation · Not investment advice",
            )}
          </p>
          {assumptionLine && (
            <p className="text-[11px] leading-snug text-black/45 dark:text-white/45">
              {assumptionLine}
            </p>
          )}
          {result.benchmarkNote && (
            <p className="text-[11px] leading-snug text-black/45 dark:text-white/45">
              {result.benchmarkNote}
            </p>
          )}
        </div>
      </div>
    </section>
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
    <span className="flex flex-wrap gap-x-1.5 gap-y-1">
      {symbols.map((symbol) => (
        <span
          key={symbol}
          className="rounded-[5px] border border-[#c2a44d]/25 bg-[#c2a44d]/10 px-1.5 py-0.5 text-[12px] font-semibold leading-none tracking-tight text-[#8b7329] dark:border-[#c2a44d]/30 dark:bg-[#c2a44d]/12 dark:text-[#d9c574]"
        >
          {symbol}
        </span>
      ))}
    </span>
  );
}
