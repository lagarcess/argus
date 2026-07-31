"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  type CSSProperties,
} from "react";
import { useTranslation } from "react-i18next";
import type {
  ConversationRailTick,
  ConversationRailTickKind,
} from "@/lib/conversation-rail";
import {
  conversationRailVisible,
  INITIAL_RAIL_DWELL_STATE,
  RAIL_PREVIEW_DWELL_MS,
  railDwellReducer,
  railRevealProgress,
  railTickOffsets,
} from "@/lib/conversation-rail";
import { recoveryDisplayText } from "@/lib/chat-recovery-display";

type ConversationActivityRailProps = {
  ticks: ConversationRailTick[];
  totalMessages: number;
  onSelectTick: (messageId: string) => void;
};

const TICK_BAR_KIND_CLASSES: Record<ConversationRailTickKind, string> = {
  backtest_completed: "bg-[#5ba897]",
  decision_saved: "bg-[#6f8fb8]",
  error_recovery: "bg-[#d66d75]",
};

const KIND_LABEL_CLASSES: Record<ConversationRailTickKind, string> = {
  backtest_completed: "text-[#3f816f] dark:text-[#7bc1ad]",
  decision_saved: "text-[#4f6f98] dark:text-[#91afd1]",
  error_recovery: "text-[#ad4e56] dark:text-[#e58c93]",
};

export default function ConversationActivityRail({
  ticks,
  totalMessages,
  onSelectTick,
}: ConversationActivityRailProps) {
  const { t } = useTranslation();
  const rootRef = useRef<HTMLDivElement | null>(null);
  const columnRef = useRef<HTMLElement | null>(null);
  const awakeRef = useRef(false);
  const pointerRef = useRef<{ x: number; y: number } | null>(null);
  const dwellTimerRef = useRef<number | null>(null);
  const [dwell, dispatch] = useReducer(
    railDwellReducer,
    INITIAL_RAIL_DWELL_STATE,
  );

  const offsets = useMemo(
    () => railTickOffsets(ticks, totalMessages),
    [ticks, totalMessages],
  );

  const visible = conversationRailVisible(totalMessages, ticks.length);

  // Magnetic reveal: track pointer proximity and ramp the rail awake through
  // a CSS variable instead of firing the instant the strip is touched.
  useEffect(() => {
    if (!visible) {
      return;
    }
    let frame = 0;
    const applyProximity = () => {
      frame = 0;
      const node = rootRef.current;
      const column = columnRef.current;
      const pointer = pointerRef.current;
      if (!node || !column || !pointer) {
        return;
      }
      const rect = column.getBoundingClientRect();
      const dx = Math.max(rect.left - pointer.x, pointer.x - rect.right, 0);
      const dy = Math.max(rect.top - pointer.y, pointer.y - rect.bottom, 0);
      const reveal = railRevealProgress(Math.hypot(dx, dy));
      node.style.setProperty("--rail-reveal", reveal.toFixed(3));
      const awake = reveal > 0;
      if (awake !== awakeRef.current) {
        awakeRef.current = awake;
        node.dataset.railAwake = awake ? "true" : "false";
        if (!awake) {
          dispatch({ type: "rail_exit" });
        }
      }
    };
    const handlePointerMove = (event: PointerEvent) => {
      pointerRef.current = { x: event.clientX, y: event.clientY };
      if (!frame) {
        frame = requestAnimationFrame(applyProximity);
      }
    };
    window.addEventListener("pointermove", handlePointerMove, {
      passive: true,
    });
    return () => {
      window.removeEventListener("pointermove", handlePointerMove);
      if (frame) {
        cancelAnimationFrame(frame);
      }
    };
  }, [visible]);

  const clearDwellTimer = useCallback(() => {
    if (dwellTimerRef.current !== null) {
      window.clearTimeout(dwellTimerRef.current);
      dwellTimerRef.current = null;
    }
  }, []);

  useEffect(() => clearDwellTimer, [clearDwellTimer]);

  const handleTickEnter = useCallback(
    (tickId: string) => {
      clearDwellTimer();
      dispatch({ type: "tick_enter", tickId, at: Date.now() });
      dwellTimerRef.current = window.setTimeout(() => {
        dwellTimerRef.current = null;
        dispatch({ type: "elapse", at: Date.now() });
      }, RAIL_PREVIEW_DWELL_MS + 20);
    },
    [clearDwellTimer],
  );

  const handleTickLeave = useCallback(() => {
    clearDwellTimer();
    dispatch({ type: "tick_leave" });
  }, [clearDwellTimer]);

  if (!visible) {
    return null;
  }

  const openIndex = dwell.openTickId
    ? ticks.findIndex((tick) => tick.messageId === dwell.openTickId)
    : -1;
  const openTick = openIndex >= 0 ? ticks[openIndex] : null;

  const kindLabel = (kind: ConversationRailTickKind): string => {
    if (kind === "decision_saved") {
      return t("chat.result_card.decision_saved", "Decision saved");
    }
    if (kind === "error_recovery") {
      return t("chat.activity_rail.needs_attention", "Needed attention");
    }
    return t("chat.activity_rail.backtest_completed", "Backtest finished");
  };

  const tickAriaLabel = (tick: ConversationRailTick): string => {
    const label = kindLabel(tick.kind);
    return tick.strategyTitle ? `${label} — ${tick.strategyTitle}` : label;
  };

  const errorBody = (tick: ConversationRailTick): string => {
    if (tick.recovery) {
      const text = recoveryDisplayText(tick.recovery, t).trim();
      if (text) {
        return text;
      }
    }
    if (tick.failedJobStatus === "failed") {
      return t("chat.backtest_job.failed_title", "Backtest could not finish");
    }
    if (tick.failedJobStatus) {
      return t("chat.backtest_job.expired_title", "Backtest not completed");
    }
    return t(
      "chat.activity_rail.needs_attention_body",
      "This turn hit an issue and offered a way forward.",
    );
  };

  return (
    <div
      ref={rootRef}
      data-testid="conversation-activity-rail"
      data-rail-awake="false"
      className="pointer-events-none absolute bottom-40 right-0 top-24 z-30 hidden md:block"
      style={{ "--rail-reveal": "0" } as CSSProperties}
    >
      <nav
        ref={columnRef}
        aria-label={t("chat.activity_rail.aria_label", "Conversation activity")}
        className="pointer-events-auto relative h-full w-9"
        onPointerLeave={handleTickLeave}
      >
        {ticks.map((tick, index) => (
          <button
            key={tick.messageId}
            type="button"
            aria-label={tickAriaLabel(tick)}
            onPointerEnter={() => handleTickEnter(tick.messageId)}
            onPointerLeave={handleTickLeave}
            onFocus={() => dispatch({ type: "focus_open", tickId: tick.messageId })}
            onBlur={handleTickLeave}
            onClick={() => {
              handleTickLeave();
              onSelectTick(tick.messageId);
            }}
            className="absolute right-1.5 flex h-5 w-7 -translate-y-1/2 items-center justify-end rounded-full outline-none focus-visible:ring-2 focus-visible:ring-black/25 dark:focus-visible:ring-white/30"
            style={{ top: `${(offsets[index] * 100).toFixed(2)}%` }}
          >
            <span
              aria-hidden="true"
              className={`h-[3px] w-[calc(10px+8px*var(--rail-reveal))] rounded-full opacity-[calc(0.35+0.65*var(--rail-reveal))] transition-[width,opacity] duration-150 motion-reduce:transition-none ${TICK_BAR_KIND_CLASSES[tick.kind]}`}
            />
          </button>
        ))}

        {openTick && (
          <div
            role="status"
            data-testid="conversation-activity-rail-preview"
            className="pointer-events-none absolute right-[calc(100%+10px)] w-64 -translate-y-1/2 rounded-[14px] border border-black/10 bg-white/[0.97] p-3 shadow-[0_8px_28px_rgba(0,0,0,0.12)] backdrop-blur dark:border-white/10 dark:bg-[#1d2023]/[0.97]"
            style={{
              top: `clamp(76px, ${(offsets[openIndex] * 100).toFixed(2)}%, calc(100% - 76px))`,
            }}
          >
            <div
              className={`text-[11px] font-semibold uppercase tracking-[0.08em] ${KIND_LABEL_CLASSES[openTick.kind]}`}
            >
              {kindLabel(openTick.kind)}
            </div>
            {openTick.strategyTitle && (
              <div className="mt-1 truncate text-[13px] font-medium text-black/80 dark:text-white/80">
                {openTick.strategyTitle}
              </div>
            )}
            {openTick.periodDisplay && (
              <div className="text-[12px] text-black/50 dark:text-white/50">
                {openTick.periodDisplay}
              </div>
            )}
            {openTick.kind === "decision_saved" && openTick.decisionState && (
              <div className="mt-1 text-[12px] font-medium text-black/70 dark:text-white/70">
                {t(
                  `chat.result_card.decision_states.${openTick.decisionState}`,
                  openTick.decisionState,
                )}
              </div>
            )}
            {openTick.kind !== "error_recovery" &&
              openTick.metrics.length > 0 && (
                <div className="mt-2 flex flex-col divide-y divide-black/8 dark:divide-white/8">
                  {openTick.metrics.map((metric) => (
                    <div
                      key={metric.label}
                      className="flex items-baseline justify-between gap-3 py-1 text-[12px]"
                    >
                      <span className="text-black/50 dark:text-white/50">
                        {metric.label}
                      </span>
                      <span className="font-medium text-black/80 dark:text-white/80">
                        {metric.value}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            {openTick.kind === "error_recovery" && (
              <div className="mt-1 line-clamp-3 text-[12px] leading-[1.45] text-black/60 dark:text-white/60">
                {errorBody(openTick)}
              </div>
            )}
            <div className="mt-2 border-t border-black/8 pt-1.5 text-[11px] text-black/45 dark:border-white/8 dark:text-white/45">
              {t("chat.activity_rail.jump_hint", "Click to jump to this turn")}
            </div>
          </div>
        )}
      </nav>
    </div>
  );
}
