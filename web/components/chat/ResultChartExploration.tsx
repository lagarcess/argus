"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";
import { useTranslation } from "react-i18next";
import type {
  ResultChartCustomError,
  ResultChartRangeKey,
  ResultChartRangeOption,
  ResultChartSelection,
  VisibleResultChartSummary,
} from "@/lib/result-chart-range";

type ResultChartExplorationProps = {
  options: ResultChartRangeOption[];
  selection: ResultChartSelection;
  summary: VisibleResultChartSummary | null;
  currency?: string;
  locale: string;
  showTimes: boolean;
  detailsOpen: boolean;
  customError: ResultChartCustomError | null;
  onSelect: (range: ResultChartRangeOption) => void;
  onToggleDetails: () => void;
  onApplyCustom: (startDate: string, endDate: string) => void;
  onCancelCustom: () => void;
  onReset: () => void;
};

// Presentation order only; eligibility still comes from the pure range policy.
const CANONICAL_NON_ALL_ORDER: ResultChartRangeKey[] = [
  "1D", "1W", "1M", "3M", "YTD", "1Y",
];

const switcherButtonClassName =
  "group inline-flex min-h-11 cursor-pointer items-center rounded-[10px] text-[11px] tracking-tight transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/20 dark:focus-visible:ring-white/30";
const switcherLabelIdleClassName =
  "rounded-[8px] px-2 py-[5px] font-medium text-black/42 transition-colors group-hover:text-black/72 dark:text-white/42 dark:group-hover:text-white/72";
const switcherLabelSelectedClassName =
  "rounded-[8px] bg-black/[0.07] px-2 py-[5px] font-semibold text-black/85 dark:bg-white/[0.11] dark:text-white/90";
const quietActionClassName =
  "inline-flex min-h-11 cursor-pointer items-center px-1.5 text-[11px] font-medium text-black/45 underline-offset-2 transition-colors hover:text-black/75 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/20 dark:text-white/45 dark:hover:text-white/75 dark:focus-visible:ring-white/30";
const summaryLineClassName =
  "text-[11px] leading-snug tracking-[0.16px] text-black/55 dark:text-white/55";
const formButtonClassName =
  "inline-flex min-h-9 cursor-pointer items-center rounded-full px-3 py-1 text-[11px] font-medium tracking-tight transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/20 dark:focus-visible:ring-white/30";
const CUSTOM_ERROR_COPY_KEY: Record<ResultChartCustomError, string> = {
  missing_date: "chat.result_chart.range.error_missing_date",
  start_after_end: "chat.result_chart.range.error_start_after_end",
  insufficient_observations:
    "chat.result_chart.range.error_insufficient_observations",
};

export default function ResultChartExploration({
  options,
  selection,
  summary,
  currency,
  locale,
  showTimes,
  detailsOpen,
  customError,
  onSelect,
  onToggleDetails,
  onApplyCustom,
  onCancelCustom,
  onReset,
}: ResultChartExplorationProps) {
  const { t } = useTranslation();
  const panelId = useId();
  const errorId = useId();
  const [startDraft, setStartDraft] = useState("");
  const [endDraft, setEndDraft] = useState("");
  const [announcement, setAnnouncement] = useState("");
  const lastAnnouncedSelectionRef = useRef<ResultChartSelection | null>(null);
  const orderedOptions = useMemo(() => {
    const byKey = new Map(options.map((option) => [option.key, option]));
    const ordered = CANONICAL_NON_ALL_ORDER.flatMap((key) => {
      const option = byKey.get(key);
      return option ? [option] : [];
    });
    const all = byKey.get("ALL");
    return all ? [...ordered, all] : ordered;
  }, [options]);

  // Announce only discrete selection changes; continuous pan/zoom keeps
  // refreshing the visible summary without re-triggering the status region.
  useEffect(() => {
    if (!summary || lastAnnouncedSelectionRef.current === selection) return;
    lastAnnouncedSelectionRef.current = selection;
    setAnnouncement(
      t("chat.result_chart.range.visible_period", {
        start: formatSummaryTime(summary.startTime, locale, showTimes),
        end: formatSummaryTime(summary.endTime, locale, showTimes),
      }),
    );
  }, [selection, summary, locale, showTimes, t]);

  if (options.length === 0) return null;

  const visibleEventCount = summary?.suppliedEventCount ?? 0;

  return (
    <div className="border-t border-black/[0.04] px-3 pb-2.5 pt-1 dark:border-white/[0.06] sm:px-4">
      <div
        role="group"
        aria-label={t("chat.result_chart.range.group_label", "Chart range")}
        className="flex flex-wrap items-center gap-0.5"
      >
        {orderedOptions.map((option) => {
          const selected = selection === option.key;
          return (
            <button
              key={option.key}
              type="button"
              aria-pressed={selected}
              data-testid={`result-chart-range-${option.key}`}
              className={switcherButtonClassName}
              onClick={() => onSelect(option)}
            >
              <span
                className={
                  selected
                    ? switcherLabelSelectedClassName
                    : switcherLabelIdleClassName
                }
              >
                {t(`chat.result_chart.range.presets.${option.key}`, option.key)}
              </span>
            </button>
          );
        })}
        {selection === "CUSTOM" && (
          <span
            data-testid="result-chart-custom-indicator"
            className="inline-flex items-center rounded-[8px] bg-black/[0.07] px-2 py-[5px] text-[11px] font-semibold tracking-tight text-black/85 dark:bg-white/[0.11] dark:text-white/90"
          >
            {t("chat.result_chart.range.custom", "Custom")}
          </span>
        )}
        {selection !== "ALL" && (
          <button
            type="button"
            data-testid="result-chart-reset"
            className={quietActionClassName}
            onClick={onReset}
          >
            {t("chat.result_chart.range.reset", "Reset")}
          </button>
        )}
        <button
          type="button"
          aria-expanded={detailsOpen}
          aria-controls={panelId}
          data-testid="result-chart-details-toggle"
          className={`${switcherButtonClassName} ml-auto`}
          onClick={onToggleDetails}
        >
          <span className="inline-flex items-center gap-1 rounded-full border border-black/8 bg-black/[0.02] px-2.5 py-1 font-medium text-[#505a63] transition-colors group-hover:border-black/14 group-hover:bg-black/[0.04] dark:border-white/8 dark:bg-white/[0.03] dark:text-[#8d969e] dark:group-hover:border-white/14 dark:group-hover:bg-white/[0.06]">
            {t("chat.result_chart.range.details", "Range details")}
            <ChevronDown
              className={`h-3 w-3 transition-transform ${detailsOpen ? "rotate-180" : ""}`}
            />
          </span>
        </button>
      </div>

      {detailsOpen && (
        <div
          id={panelId}
          className="mb-1 mt-1.5 flex flex-col gap-2 rounded-[12px] bg-black/[0.018] px-3 py-2.5 dark:bg-white/[0.025]"
        >
          <form
            className="flex flex-col gap-1.5"
            onSubmit={(event) => {
              event.preventDefault();
              onApplyCustom(startDraft, endDraft);
            }}
          >
            <p className="text-[11px] font-medium tracking-[0.16px] text-[#505a63] dark:text-[#8d969e]">
              {t("chat.result_chart.range.custom_heading", "Custom range")}
            </p>
            <div className="flex flex-wrap items-end gap-2">
              <label className="flex flex-col gap-1 text-[11px] font-medium tracking-tight text-black/55 dark:text-white/55">
                {t("chat.result_chart.range.start_date", "Start date")}
                <input
                  type="date"
                  value={startDraft}
                  onChange={(event) => setStartDraft(event.target.value)}
                  aria-invalid={customError != null}
                  aria-describedby={customError ? errorId : undefined}
                  data-testid="result-chart-custom-start"
                  className="min-h-9 rounded-[10px] border border-black/12 bg-white px-2.5 text-[16px] text-black focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/20 dark:border-white/14 dark:bg-white/[0.05] dark:text-white dark:focus-visible:ring-white/30 sm:text-[12px]"
                />
              </label>
              <label className="flex flex-col gap-1 text-[11px] font-medium tracking-tight text-black/55 dark:text-white/55">
                {t("chat.result_chart.range.end_date", "End date")}
                <input
                  type="date"
                  value={endDraft}
                  onChange={(event) => setEndDraft(event.target.value)}
                  aria-invalid={customError != null}
                  aria-describedby={customError ? errorId : undefined}
                  data-testid="result-chart-custom-end"
                  className="min-h-9 rounded-[10px] border border-black/12 bg-white px-2.5 text-[16px] text-black focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/20 dark:border-white/14 dark:bg-white/[0.05] dark:text-white dark:focus-visible:ring-white/30 sm:text-[12px]"
                />
              </label>
              <div className="flex items-center gap-1">
                <button
                  type="submit"
                  data-testid="result-chart-custom-apply"
                  className={`${formButtonClassName} bg-black/[0.07] text-black/80 hover:bg-black/[0.1] dark:bg-white/[0.1] dark:text-white/85 dark:hover:bg-white/[0.14]`}
                >
                  {t("chat.result_chart.range.apply", "Apply")}
                </button>
                <button
                  type="button"
                  data-testid="result-chart-custom-cancel"
                  className={`${formButtonClassName} text-black/50 hover:text-black/75 dark:text-white/50 dark:hover:text-white/75`}
                  onClick={onCancelCustom}
                >
                  {t("chat.result_chart.range.cancel", "Cancel")}
                </button>
              </div>
            </div>
            {customError && (
              <p
                id={errorId}
                data-testid="result-chart-custom-error"
                className="text-[11px] leading-snug tracking-[0.16px] text-[#d66d75]"
              >
                {t(CUSTOM_ERROR_COPY_KEY[customError])}
              </p>
            )}
          </form>

          {summary && (
            <div className="flex flex-col gap-1 border-t border-black/[0.05] pt-2 dark:border-white/[0.07]">
              <p
                className={summaryLineClassName}
                data-testid="result-chart-visible-period"
              >
                {t("chat.result_chart.range.visible_period", {
                  start: formatSummaryTime(summary.startTime, locale, showTimes),
                  end: formatSummaryTime(summary.endTime, locale, showTimes),
                })}
              </p>
              <p className={summaryLineClassName} data-testid="result-chart-peak">
                {t("chat.result_chart.range.peak_label", "Highest visible value")}
                {": "}
                <span className="font-medium text-black/70 dark:text-white/70">
                  {formatSummaryCurrency(summary.peak.value, currency, locale)}
                </span>
                {" · "}
                {formatSummaryTime(summary.peak.time, locale, showTimes)}
              </p>
              <p className={summaryLineClassName} data-testid="result-chart-low">
                {t("chat.result_chart.range.low_label", "Lowest visible value")}
                {": "}
                <span className="font-medium text-black/70 dark:text-white/70">
                  {formatSummaryCurrency(summary.low.value, currency, locale)}
                </span>
                {" · "}
                {formatSummaryTime(summary.low.time, locale, showTimes)}
              </p>
              <p
                className={summaryLineClassName}
                data-testid="result-chart-event-count"
              >
                {visibleEventCount === 0
                  ? t("chat.result_chart.range.no_events")
                  : t("chat.result_chart.range.event_count", {
                      count: visibleEventCount,
                    })}
              </p>
              {summary.displayedEvents.length > 0 && (
                <ol
                  data-testid="result-chart-event-list"
                  className="mt-0.5 flex flex-col gap-0.5"
                >
                  {summary.displayedEvents.map((event) => (
                    <li
                      key={`${event.sourceIndex}`}
                      data-testid="result-chart-event-row"
                      className={summaryLineClassName}
                    >
                      {eventRowCopy(event.marker.type, event.marker.symbols, {
                        entry: t("chat.result_chart.markers.entry", "Buy"),
                        exit: t("chat.result_chart.markers.exit", "Sell"),
                      })}
                      {" · "}
                      {formatSummaryTime(event.marker.time, locale, showTimes)}
                    </li>
                  ))}
                </ol>
              )}
              {summary.eventListSampled && (
                <p
                  className={summaryLineClassName}
                  data-testid="result-chart-event-sampling"
                >
                  {t("chat.result_chart.range.event_sampling", {
                    shown: summary.displayedEvents.length,
                    total: summary.suppliedEventCount,
                  })}
                </p>
              )}
              {summary.markerSummary?.sampled && (
                <p
                  className={summaryLineClassName}
                  data-testid="result-chart-marker-cap"
                >
                  {t("chat.result_chart.range.marker_cap", {
                    included: summary.markerSummary.included_groups,
                    total: summary.markerSummary.total_groups,
                  })}
                </p>
              )}
            </div>
          )}
        </div>
      )}

      <p role="status" className="sr-only">
        {announcement}
      </p>
    </div>
  );
}

function eventRowCopy(
  type: "entry" | "exit",
  symbols: string[] | undefined,
  labels: { entry: string; exit: string },
) {
  const label = type === "entry" ? labels.entry : labels.exit;
  const cleaned = (symbols ?? [])
    .map((symbol) => symbol.trim())
    .filter(Boolean);
  return cleaned.length > 0 ? `${label} ${cleaned.join(", ")}` : label;
}

function resolveIntlLocale(locale: string) {
  const normalized = locale.trim().toLowerCase();
  if (normalized.startsWith("es")) return "es-419";
  if (normalized === "" || normalized === "en") return "en-US";
  return locale;
}

function formatSummaryTime(time: string, locale: string, showTimes: boolean) {
  const trimmed = time.trim();
  const hasTime = trimmed.length >= 16 && trimmed[10] === "T";
  const date = new Date(
    hasTime ? `${trimmed.slice(0, 19)}Z` : `${trimmed}T00:00:00Z`,
  );
  if (Number.isNaN(date.getTime())) return time;
  return new Intl.DateTimeFormat(resolveIntlLocale(locale), {
    month: "short",
    day: "numeric",
    year: "numeric",
    ...(hasTime && showTimes ? { hour: "numeric", minute: "2-digit" } : {}),
    timeZone: "UTC",
  }).format(date);
}

function formatSummaryCurrency(
  value: number,
  currency: string | undefined,
  locale: string,
) {
  return new Intl.NumberFormat(resolveIntlLocale(locale), {
    style: "currency",
    currency: currency ?? "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}
