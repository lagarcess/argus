"use client";

import { useEffect, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type {
  ResultChartCustomError,
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
  customOpen: boolean;
  customError: ResultChartCustomError | null;
  onSelect: (range: ResultChartRangeOption) => void;
  onOpenCustom: () => void;
  onApplyCustom: (startDate: string, endDate: string) => void;
  onCancelCustom: () => void;
  onReset: () => void;
};

const pillClassName =
  "inline-flex min-h-9 cursor-pointer items-center rounded-full border px-3 py-1 text-[11px] font-medium tracking-tight transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/20 dark:focus-visible:ring-white/30";
const pillIdleClassName =
  "border-black/10 bg-black/[0.02] text-black/62 hover:border-black/20 hover:bg-black/[0.05] dark:border-white/10 dark:bg-white/[0.03] dark:text-white/62 dark:hover:border-white/20 dark:hover:bg-white/[0.07]";
const pillSelectedClassName =
  "border-black/55 bg-black/[0.08] text-black dark:border-white/55 dark:bg-white/[0.12] dark:text-white";
const summaryLineClassName =
  "text-[11px] leading-snug tracking-[0.16px] text-black/55 dark:text-white/55";
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
  customOpen,
  customError,
  onSelect,
  onOpenCustom,
  onApplyCustom,
  onCancelCustom,
  onReset,
}: ResultChartExplorationProps) {
  const { t } = useTranslation();
  const formId = useId();
  const errorId = useId();
  const [startDraft, setStartDraft] = useState("");
  const [endDraft, setEndDraft] = useState("");
  const [announcement, setAnnouncement] = useState("");
  const lastAnnouncedSelectionRef = useRef<ResultChartSelection | null>(null);

  // Announce only discrete selection changes; continuous pan/zoom keeps
  // refreshing the visible summary without re-triggering the status region.
  useEffect(() => {
    if (!summary || lastAnnouncedSelectionRef.current === selection) return;
    lastAnnouncedSelectionRef.current = selection;
    setAnnouncement(
      t("chat.result_chart.range.visible_period", {
        start: formatSummaryTime(summary.startTime, locale),
        end: formatSummaryTime(summary.endTime, locale),
      }),
    );
  }, [selection, summary, locale, t]);

  if (options.length === 0 && !summary) return null;

  const showControls = options.length > 0;
  const visibleEventCount = summary?.suppliedEventCount ?? 0;

  return (
    <div className="border-t border-black/[0.04] px-3 pb-3 pt-2.5 dark:border-white/[0.06] sm:px-4">
      {showControls && (
        <div
          role="group"
          aria-label={t("chat.result_chart.range.group_label", "Chart range")}
          className="flex flex-wrap items-center gap-1.5"
        >
          {options.map((option) => {
            const selected = selection === option.key;
            return (
              <button
                key={option.key}
                type="button"
                aria-pressed={selected}
                data-testid={`result-chart-range-${option.key}`}
                className={`${pillClassName} ${selected ? pillSelectedClassName : pillIdleClassName}`}
                onClick={() => onSelect(option)}
              >
                {t(`chat.result_chart.range.presets.${option.key}`, option.key)}
              </button>
            );
          })}
          <button
            type="button"
            aria-pressed={selection === "CUSTOM"}
            aria-expanded={customOpen}
            aria-controls={formId}
            data-testid="result-chart-custom-toggle"
            className={`${pillClassName} ${selection === "CUSTOM" ? pillSelectedClassName : pillIdleClassName}`}
            onClick={onOpenCustom}
          >
            {t("chat.result_chart.range.custom", "Custom")}
          </button>
          {selection !== "ALL" && (
            <button
              type="button"
              data-testid="result-chart-reset"
              className={`${pillClassName} ${pillIdleClassName}`}
              onClick={onReset}
            >
              {t("chat.result_chart.range.reset", "Reset")}
            </button>
          )}
        </div>
      )}

      {showControls && customOpen && (
        <form
          id={formId}
          className="mt-2.5 flex flex-wrap items-end gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            onApplyCustom(startDraft, endDraft);
          }}
        >
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
          <div className="flex items-center gap-1.5">
            <button
              type="submit"
              data-testid="result-chart-custom-apply"
              className={`${pillClassName} ${pillSelectedClassName}`}
            >
              {t("chat.result_chart.range.apply", "Apply")}
            </button>
            <button
              type="button"
              data-testid="result-chart-custom-cancel"
              className={`${pillClassName} ${pillIdleClassName}`}
              onClick={onCancelCustom}
            >
              {t("chat.result_chart.range.cancel", "Cancel")}
            </button>
          </div>
          {customError && (
            <p
              id={errorId}
              data-testid="result-chart-custom-error"
              className="w-full text-[11px] leading-snug tracking-[0.16px] text-[#d66d75]"
            >
              {t(CUSTOM_ERROR_COPY_KEY[customError])}
            </p>
          )}
        </form>
      )}

      {summary && (
        <div className="mt-2.5 flex flex-col gap-1">
          <p className={summaryLineClassName} data-testid="result-chart-visible-period">
            {t("chat.result_chart.range.visible_period", {
              start: formatSummaryTime(summary.startTime, locale),
              end: formatSummaryTime(summary.endTime, locale),
            })}
          </p>
          <p className={summaryLineClassName} data-testid="result-chart-peak">
            {t("chat.result_chart.range.peak_label", "Highest visible value")}
            {": "}
            <span className="font-medium text-black/70 dark:text-white/70">
              {formatSummaryCurrency(summary.peak.value, currency, locale)}
            </span>
            {" · "}
            {formatSummaryTime(summary.peak.time, locale)}
          </p>
          <p className={summaryLineClassName} data-testid="result-chart-low">
            {t("chat.result_chart.range.low_label", "Lowest visible value")}
            {": "}
            <span className="font-medium text-black/70 dark:text-white/70">
              {formatSummaryCurrency(summary.low.value, currency, locale)}
            </span>
            {" · "}
            {formatSummaryTime(summary.low.time, locale)}
          </p>
          <p className={summaryLineClassName} data-testid="result-chart-event-count">
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
                  {formatSummaryTime(event.marker.time, locale)}
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

function formatSummaryTime(time: string, locale: string) {
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
    ...(hasTime ? { hour: "numeric", minute: "2-digit" } : {}),
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
