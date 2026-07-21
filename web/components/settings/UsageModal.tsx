"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type RefObject,
} from "react";
import { ChevronDown, Loader2, RefreshCw, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { getUsageAllowances } from "@/lib/argus-api";
import {
  classifyAllowance,
  formatAllowancePeriodEnd,
  showsHourlyWindow,
  type UsageAllowance,
  type UsageAllowanceResponse,
} from "@/lib/usage-allowance";
import { dialogTabTarget } from "@/lib/dialog-focus";

const FOCUSABLE_SELECTOR =
  'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

type UsageModalProps = {
  locale: "en-US" | "es-419";
  onClose: () => void;
  returnFocusRef?: RefObject<HTMLElement | null>;
};

type AllowanceSectionProps = {
  allowance: UsageAllowance;
  label: string;
  locale: "en-US" | "es-419";
};

function AllowanceSection({ allowance, label, locale }: AllowanceSectionProps) {
  const { t } = useTranslation();
  const state = classifyAllowance(allowance);
  const day = allowance.day;
  const dayExhausted = state === "exhausted";
  const hourLimited = state === "hourly_limited";
  const progress =
    day.limit === 0
      ? 100
      : Math.min(100, Math.round((day.used / day.limit) * 100));
  const resetDisplay = formatAllowancePeriodEnd(day.period_end, locale);

  return (
    <section aria-label={label}>
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="text-[14px] font-medium text-black dark:text-white">
          {label}
        </h3>
        <p
          className={`text-[13px] font-medium ${
            dayExhausted
              ? "text-[#b94c55] dark:text-[#e7a2a8]"
              : "text-black/70 dark:text-white/75"
          }`}
        >
          {t("settings.data.usage_panel.left_today", { count: day.remaining })}
        </p>
      </div>

      <div
        className="mt-2.5 h-1 overflow-hidden rounded-full bg-black/[0.07] dark:bg-white/[0.08]"
        role="progressbar"
        aria-label={t("settings.data.usage_panel.used_of_limit", {
          used: day.used,
          limit: day.limit,
        })}
        aria-valuemin={0}
        aria-valuemax={day.limit}
        aria-valuenow={Math.min(day.used, day.limit)}
      >
        <div
          className={`h-full rounded-full transition-[width] ${
            dayExhausted ? "bg-[#d66d75]" : "bg-[#5d7f72]"
          }`}
          style={{ width: `${progress}%` }}
        />
      </div>

      <p className="mt-2 text-[12px] text-black/45 dark:text-white/45">
        {t("settings.data.usage_panel.resets", { time: "" })}
        <time dateTime={day.period_end}>{resetDisplay}</time>
      </p>

      {showsHourlyWindow(allowance) ? (
        <p
          className={`mt-1 text-[12px] ${
            hourLimited
              ? "text-[#b94c55] dark:text-[#e7a2a8]"
              : "text-black/45 dark:text-white/45"
          }`}
        >
          {t("settings.data.usage_panel.hourly_available", {
            count: allowance.hour.remaining,
            time: "",
          })}
          <time dateTime={allowance.hour.period_end}>
            {formatAllowancePeriodEnd(allowance.hour.period_end, locale)}
          </time>
        </p>
      ) : null}
    </section>
  );
}

export default function UsageModal({
  locale,
  onClose,
  returnFocusRef,
}: UsageModalProps) {
  const { t } = useTranslation();
  const dialogRef = useRef<HTMLDivElement>(null);
  const [usage, setUsage] = useState<UsageAllowanceResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);
  const [requestVersion, setRequestVersion] = useState(0);
  const [rulesOpen, setRulesOpen] = useState(false);

  const retry = useCallback(() => {
    setRequestVersion((current) => current + 1);
  }, []);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    const previousFocus =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    const returnFocusRoot = returnFocusRef?.current ?? null;
    const fallbackReturnFocus = returnFocusRoot?.matches(FOCUSABLE_SELECTOR)
      ? returnFocusRoot
      : returnFocusRoot?.querySelector<HTMLElement>(FOCUSABLE_SELECTOR);
    const focusableElements = () =>
      Array.from(dialog.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR));

    (focusableElements()[0] ?? dialog).focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab") return;

      const focusable = focusableElements();
      if (focusable.length === 0) {
        event.preventDefault();
        dialog.focus();
        return;
      }
      const target = dialogTabTarget(
        focusable,
        document.activeElement as HTMLElement | null,
        event.shiftKey,
      );
      if (target) {
        event.preventDefault();
        target.focus();
      }
    };

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      const previousFocusIsPageRoot =
        previousFocus === document.body ||
        previousFocus === document.documentElement;
      const returnTarget =
        previousFocus?.isConnected && !previousFocusIsPageRoot
          ? previousFocus
          : fallbackReturnFocus;
      returnTarget?.focus();
    };
  }, [onClose, returnFocusRef]);

  useEffect(() => {
    let isCurrent = true;
    setIsLoading(true);
    setHasError(false);
    getUsageAllowances()
      .then((response) => {
        if (isCurrent) setUsage(response);
      })
      .catch(() => {
        if (isCurrent) setHasError(true);
      })
      .finally(() => {
        if (isCurrent) setIsLoading(false);
      });
    return () => {
      isCurrent = false;
    };
  }, [requestVersion]);

  return (
    <div className="fixed inset-0 z-[70] flex items-end justify-center bg-black/25 p-4 backdrop-blur-sm sm:items-center dark:bg-black/60">
      <button
        className="absolute inset-0"
        aria-label={t("settings.data.usage_panel.close")}
        onClick={onClose}
      />
      <div
        ref={dialogRef}
        tabIndex={-1}
        className="relative flex max-h-[85vh] w-full max-w-md flex-col overflow-hidden rounded-[20px] border border-black/5 bg-white dark:border-white/10 dark:bg-[#1b1d20]"
        role="dialog"
        aria-modal="true"
        aria-labelledby="argus-usage-modal-title"
      >
        <header className="flex items-start justify-between gap-4 px-5 pt-4 pb-3">
          <div>
            <h2
              id="argus-usage-modal-title"
              className="font-display text-[17px] font-medium text-black dark:text-white"
            >
              {t("settings.data.usage_panel.title")}
            </h2>
            <p className="mt-1 text-[12px] text-black/45 dark:text-white/45">
              {t("settings.data.usage_panel.description")}
            </p>
          </div>
          <button
            onClick={onClose}
            className="flex min-h-11 min-w-11 shrink-0 items-center justify-center rounded-full text-black/45 transition-colors hover:bg-black/5 hover:text-black dark:text-white/45 dark:hover:bg-white/[0.08] dark:hover:text-white"
            aria-label={t("settings.data.usage_panel.close")}
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="overflow-y-auto px-5 pb-5" aria-live="polite">
          {isLoading ? (
            <div
              className="flex min-h-56 flex-col items-center justify-center gap-3 text-[13px] text-black/40 dark:text-white/40"
              role="status"
            >
              <Loader2 className="h-5 w-5 animate-spin" />
              {t("settings.data.usage_panel.loading")}
            </div>
          ) : hasError || !usage ? (
            <div className="flex min-h-56 flex-col items-center justify-center gap-4 text-center">
              <p className="text-[13px] text-black/50 dark:text-white/50">
                {t("settings.data.usage_panel.load_error")}
              </p>
              <button
                type="button"
                onClick={retry}
                className="flex min-h-11 items-center gap-2 rounded-xl bg-black/[0.06] px-3.5 py-2 text-[12px] font-medium text-black/70 hover:bg-black/[0.09] dark:bg-white/[0.08] dark:text-white/70 dark:hover:bg-white/[0.12]"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                {t("settings.data.usage_panel.retry")}
              </button>
            </div>
          ) : (
            <>
              <div className="pt-2">
                <AllowanceSection
                  allowance={usage.allowances.messages}
                  label={t("settings.data.usage_panel.messages")}
                  locale={locale}
                />
                <div className="my-4 border-t border-black/[0.05] dark:border-white/[0.06]" />
                <AllowanceSection
                  allowance={usage.allowances.backtests}
                  label={t("settings.data.usage_panel.simulations")}
                  locale={locale}
                />
              </div>

              <div className="mt-5">
                <button
                  type="button"
                  onClick={() => setRulesOpen((open) => !open)}
                  aria-expanded={rulesOpen}
                  aria-controls="argus-usage-what-counts"
                  className="flex min-h-11 items-center gap-1.5 rounded-lg text-[12px] font-medium text-black/55 hover:text-black dark:text-white/55 dark:hover:text-white"
                >
                  {t("settings.data.usage_panel.what_counts")}
                  <ChevronDown
                    className={`h-3.5 w-3.5 transition-transform ${
                      rulesOpen ? "rotate-180" : ""
                    }`}
                  />
                </button>
                {rulesOpen ? (
                  <div
                    id="argus-usage-what-counts"
                    className="space-y-2 pb-1 text-[12px] leading-relaxed text-black/45 dark:text-white/45"
                  >
                    <p>{t("settings.data.usage_panel.message_rule")}</p>
                    <p>{t("settings.data.usage_panel.simulation_rule")}</p>
                  </div>
                ) : null}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
