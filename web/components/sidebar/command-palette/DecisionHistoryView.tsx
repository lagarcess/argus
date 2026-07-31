"use client";

import { ArrowLeft, ChevronRight, Loader2 } from "lucide-react";
import type { KeyboardEvent as ReactKeyboardEvent, ReactElement } from "react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { commandPaletteDecisionStateFallback } from "@/lib/command-palette-items";
import type { RunDossier } from "@/lib/run-dossier-contract";
import type { RunDossierHistoryState } from "@/lib/run-dossier-history-state";

type DecisionHistoryViewProps = Pick<
  RunDossierHistoryState,
  "items" | "nextCursor" | "status"
> & {
  onBack: () => void;
  onLoadOlder: () => Promise<void> | void;
  onRetry: () => Promise<void> | void;
  onSelectRun: (dossier: RunDossier) => void;
};

type DecisionHistoryKeyboardInput = {
  key: string;
  activeIndex: number;
  count: number;
};

export type DecisionHistoryKeyboardAction = {
  activeIndex: number;
  selectedIndex: number | null;
  back: boolean;
  handled: boolean;
};

export function decisionHistoryKeyboardAction({
  key,
  activeIndex,
  count,
}: DecisionHistoryKeyboardInput): DecisionHistoryKeyboardAction {
  const boundedIndex =
    count > 0 ? Math.min(Math.max(activeIndex, 0), count - 1) : 0;
  if (key === "Escape") {
    return {
      activeIndex: boundedIndex,
      selectedIndex: null,
      back: true,
      handled: true,
    };
  }
  if (count === 0) {
    return {
      activeIndex: 0,
      selectedIndex: null,
      back: false,
      handled: false,
    };
  }
  if (key === "ArrowDown") {
    return {
      activeIndex: Math.min(boundedIndex + 1, count - 1),
      selectedIndex: null,
      back: false,
      handled: true,
    };
  }
  if (key === "ArrowUp") {
    return {
      activeIndex: Math.max(boundedIndex - 1, 0),
      selectedIndex: null,
      back: false,
      handled: true,
    };
  }
  if (key === "Enter" || key === " ") {
    return {
      activeIndex: boundedIndex,
      selectedIndex: boundedIndex,
      back: false,
      handled: true,
    };
  }
  return {
    activeIndex: boundedIndex,
    selectedIndex: null,
    back: false,
    handled: false,
  };
}

function formatCompletedAt(value: string, locale: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat(locale, { dateStyle: "medium" }).format(date);
}

export function DecisionHistoryView({
  items,
  nextCursor,
  status,
  onBack,
  onLoadOlder,
  onRetry,
  onSelectRun,
}: DecisionHistoryViewProps): ReactElement {
  const { t, i18n } = useTranslation();
  const locale = i18n.resolvedLanguage ?? i18n.language ?? "en";
  const [activeIndex, setActiveIndex] = useState(0);
  const boundedActiveIndex =
    items.length > 0 ? Math.min(activeIndex, items.length - 1) : 0;
  const activeDescendant =
    items.length > 0
      ? `decision-history-run-${items[boundedActiveIndex].run_id}`
      : undefined;

  const handleKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>): void => {
    const action = decisionHistoryKeyboardAction({
      key: event.key,
      activeIndex: boundedActiveIndex,
      count: items.length,
    });
    if (!action.handled) return;
    event.preventDefault();
    if (action.back) {
      onBack();
      return;
    }
    setActiveIndex(action.activeIndex);
    if (action.selectedIndex !== null) {
      onSelectRun(items[action.selectedIndex]);
    }
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex min-h-11 items-center justify-between border-b border-black/5 pb-3 dark:border-white/5">
        <button
          type="button"
          onClick={onBack}
          className="inline-flex min-h-11 items-center gap-2 rounded-full px-2 text-[12px] font-medium text-black/55 transition-colors hover:bg-black/[0.03] hover:text-black dark:text-white/55 dark:hover:bg-white/[0.05] dark:hover:text-white"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          {t("command_palette.dossier_back", "Dossier")}
        </button>
        <h3 className="font-display text-[16px] font-medium text-black dark:text-white">
          {t("command_palette.decision_history", "Decision history")}
        </h3>
      </div>

      {status === "loading" && items.length === 0 ? (
        <div
          className="flex min-h-28 items-center justify-center gap-2 text-[13px] text-black/40 dark:text-white/40"
          role="status"
        >
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          {t(
            "command_palette.decision_history_loading",
            "Loading decision history",
          )}
        </div>
      ) : null}

      {items.length > 0 ? (
        <div
          role="listbox"
          aria-label={t(
            "command_palette.decision_history",
            "Decision history",
          )}
          aria-activedescendant={activeDescendant}
          tabIndex={0}
          onKeyDown={handleKeyDown}
          className="mt-3 min-h-0 flex-1 space-y-2 overflow-y-auto outline-none focus-visible:ring-2 focus-visible:ring-black/10 dark:focus-visible:ring-white/10"
        >
          {items.map((item, index) => {
            const selected = index === boundedActiveIndex;
            const completedAt = formatCompletedAt(item.completed_at, locale);
            return (
              <button
                id={`decision-history-run-${item.run_id}`}
                key={item.run_id}
                type="button"
                role="option"
                aria-selected={selected}
                tabIndex={-1}
                onMouseEnter={() => setActiveIndex(index)}
                onFocus={() => setActiveIndex(index)}
                onClick={() => onSelectRun(item)}
                className={`flex min-h-11 w-full flex-col items-start rounded-[14px] border p-3 text-left transition-colors ${
                  selected
                    ? "border-black/12 bg-black/[0.035] dark:border-white/15 dark:bg-white/[0.05]"
                    : "border-black/5 bg-white/50 hover:bg-black/[0.025] dark:border-white/8 dark:bg-white/[0.02] dark:hover:bg-white/[0.04]"
                }`}
              >
                <span className="flex w-full items-center justify-between gap-3">
                  <span className="min-w-0">
                    {completedAt ? (
                      <span className="mr-2 text-[11px] text-black/35 dark:text-white/35">
                        {completedAt}
                      </span>
                    ) : null}
                    <span className="text-[13px] font-medium text-black/75 dark:text-white/75">
                      {item.run_label}
                    </span>
                  </span>
                  <ChevronRight
                    className="h-4 w-4 shrink-0 text-black/25 dark:text-white/25"
                    aria-hidden="true"
                  />
                </span>
                {item.decision ? (
                  <span className="mt-2 flex flex-col items-start gap-2">
                    <span className="inline-flex rounded-full border border-black/8 px-2.5 py-1 text-[11px] font-semibold text-black/55 dark:border-white/10 dark:text-white/55">
                      {t(
                        `chat.result_card.decision_states.${item.decision.state}`,
                        commandPaletteDecisionStateFallback(item.decision.state),
                      )}
                    </span>
                    {item.decision.note ? (
                      <span className="whitespace-pre-wrap border-l-2 border-black/15 pl-3 text-[12px] italic leading-relaxed text-black/65 dark:border-white/20 dark:text-white/65">
                        <span className="sr-only">
                          {t(
                            "command_palette.decision_note_label",
                            "Decision note: ",
                          )}
                        </span>
                        {item.decision.note}
                      </span>
                    ) : null}
                  </span>
                ) : (
                  <span className="mt-2 text-[12px] text-black/40 dark:text-white/40">
                    {t(
                      "command_palette.no_decision_saved",
                      "No decision saved",
                    )}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      ) : null}

      {status === "loading" && items.length > 0 && !nextCursor ? (
        <p
          className="mt-3 inline-flex items-center gap-2 text-[12px] text-black/35 dark:text-white/35"
          role="status"
        >
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          {t(
            "command_palette.decision_history_loading",
            "Loading decision history",
          )}
        </p>
      ) : null}

      {status === "error" ? (
        <div
          className="mt-3 rounded-[12px] border border-[#d66d75]/20 bg-[#d66d75]/[0.06] p-3"
          role="alert"
        >
          <p className="text-[12px] text-[#ad4e56] dark:text-[#e58c93]">
            {t(
              "command_palette.decision_history_error",
              "Could not load decision history",
            )}
          </p>
          <button
            type="button"
            onClick={() => void onRetry()}
            className="mt-2 min-h-11 rounded-full border border-[#d66d75]/25 px-4 text-[12px] font-medium text-[#ad4e56] dark:text-[#e58c93]"
          >
            {t("common.retry", "Retry")}
          </button>
        </div>
      ) : null}

      {status !== "error" && nextCursor ? (
        <button
          type="button"
          disabled={status === "loading"}
          onClick={() => void onLoadOlder()}
          className="mt-3 min-h-11 rounded-full border border-black/10 px-4 text-[12px] font-medium text-black/55 disabled:cursor-not-allowed disabled:opacity-55 dark:border-white/10 dark:text-white/55"
        >
          {status === "loading"
            ? t(
                "command_palette.decision_history_loading_older",
                "Loading older decisions",
              )
            : t("command_palette.load_older", "Load older")}
        </button>
      ) : null}
    </div>
  );
}
