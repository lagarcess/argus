import type { Message } from "@/components/chat/types";
import type { DecisionState } from "@/lib/argus-api";
import type { RecoveryDisplay } from "@/lib/chat-recovery-display";

/**
 * Conversation activity rail ("turn map") derivation and interaction gating.
 *
 * Ticks are derived at render time from the transcript's existing message
 * payloads — no durable model, no LLM/provider calls. See
 * docs/superpowers/specs/2026-07-31-conversation-activity-rail.md.
 */

export type ConversationRailTickKind =
  | "backtest_completed"
  | "decision_saved"
  | "error_recovery";

export type ConversationRailMetric = { label: string; value: string };

export type ConversationRailTick = {
  messageId: string;
  /** Position of the source message in the transcript array. */
  messageIndex: number;
  kind: ConversationRailTickKind;
  strategyTitle: string | null;
  periodDisplay: string | null;
  /** Display-ready metric rows copied from the result card payload. */
  metrics: ConversationRailMetric[];
  decisionState: DecisionState | null;
  recovery: RecoveryDisplay | null;
  failedJobStatus: "failed" | "canceled" | "expired" | null;
};

/** The rail only earns space on longer conversations. */
export const RAIL_MIN_TRANSCRIPT_MESSAGES = 12;
export const RAIL_MIN_TICKS = 2;

const RAIL_PREVIEW_METRIC_LIMIT = 3;

const FAILED_JOB_STATUSES = new Set(["failed", "canceled", "expired"]);

export function deriveConversationRailTicks(
  messages: Message[],
): ConversationRailTick[] {
  const ticks: ConversationRailTick[] = [];
  messages.forEach((message, index) => {
    if (message.role !== "ai") {
      return;
    }
    if (
      message.kind === "strategy_result" &&
      message.result &&
      !message.isLoadingResult
    ) {
      const result = message.result;
      ticks.push({
        messageId: message.id,
        messageIndex: index,
        kind: result.decisionState ? "decision_saved" : "backtest_completed",
        strategyTitle: result.strategyLabel ?? result.strategyName ?? null,
        periodDisplay: result.dateRange?.display ?? result.period ?? null,
        metrics: (result.metrics ?? []).slice(0, RAIL_PREVIEW_METRIC_LIMIT),
        decisionState: result.decisionState ?? null,
        recovery: null,
        failedJobStatus: null,
      });
      return;
    }
    if (message.kind === "backtest_job" && message.backtestJob) {
      const status = message.backtestJob.status;
      if (FAILED_JOB_STATUSES.has(status)) {
        ticks.push({
          messageId: message.id,
          messageIndex: index,
          kind: "error_recovery",
          strategyTitle: null,
          periodDisplay: null,
          metrics: [],
          decisionState: null,
          recovery: null,
          failedJobStatus: status as "failed" | "canceled" | "expired",
        });
      }
      return;
    }
    if (
      message.recoveryDisplay ||
      message.assistantRecoveryCode ||
      message.contentPresentation === "superseded_runtime_failure"
    ) {
      ticks.push({
        messageId: message.id,
        messageIndex: index,
        kind: "error_recovery",
        strategyTitle: null,
        periodDisplay: null,
        metrics: [],
        decisionState: null,
        recovery: message.recoveryDisplay ?? null,
        failedJobStatus: null,
      });
    }
  });
  return ticks;
}

export function conversationRailVisible(
  messageCount: number,
  tickCount: number,
): boolean {
  return (
    messageCount >= RAIL_MIN_TRANSCRIPT_MESSAGES && tickCount >= RAIL_MIN_TICKS
  );
}

/**
 * Proximity reveal: the rail wakes up gradually as the cursor approaches
 * instead of firing the instant it is touched. ~56px is roughly half an inch
 * at standard density.
 */
export const RAIL_PROXIMITY_RADIUS_PX = 56;

export function railRevealProgress(distancePx: number): number {
  if (!Number.isFinite(distancePx) || distancePx >= RAIL_PROXIMITY_RADIUS_PX) {
    return 0;
  }
  if (distancePx <= 0) {
    return 1;
  }
  return 1 - distancePx / RAIL_PROXIMITY_RADIUS_PX;
}

/**
 * Dwell gating: a preview opens only after the pointer has rested on a tick,
 * never on first contact. Keyboard focus opens immediately because focusing a
 * tick is already a deliberate act.
 */
export const RAIL_PREVIEW_DWELL_MS = 180;

export type RailDwellState = {
  hoveredTickId: string | null;
  hoverStartedAt: number | null;
  openTickId: string | null;
};

export const INITIAL_RAIL_DWELL_STATE: RailDwellState = {
  hoveredTickId: null,
  hoverStartedAt: null,
  openTickId: null,
};

export type RailDwellEvent =
  | { type: "tick_enter"; tickId: string; at: number }
  | { type: "tick_leave" }
  | { type: "elapse"; at: number }
  | { type: "rail_exit" }
  | { type: "focus_open"; tickId: string };

export function railDwellReducer(
  state: RailDwellState,
  event: RailDwellEvent,
): RailDwellState {
  switch (event.type) {
    case "tick_enter":
      return {
        hoveredTickId: event.tickId,
        hoverStartedAt: event.at,
        openTickId: null,
      };
    case "elapse": {
      if (
        state.hoveredTickId === null ||
        state.hoverStartedAt === null ||
        event.at - state.hoverStartedAt < RAIL_PREVIEW_DWELL_MS
      ) {
        return state;
      }
      if (state.openTickId === state.hoveredTickId) {
        return state;
      }
      return { ...state, openTickId: state.hoveredTickId };
    }
    case "tick_leave":
    case "rail_exit":
      return INITIAL_RAIL_DWELL_STATE;
    case "focus_open":
      return {
        hoveredTickId: event.tickId,
        hoverStartedAt: null,
        openTickId: event.tickId,
      };
    default:
      return state;
  }
}

/**
 * Vertical placement: proportional to transcript position (a true minimap),
 * nudged apart so adjacent ticks never overlap. Returned values are fractions
 * of the rail height in [0, 1], in tick order.
 */
export const RAIL_TICK_MIN_GAP_FRACTION = 0.05;

export function railTickOffsets(
  ticks: ConversationRailTick[],
  totalMessages: number,
  minGap: number = RAIL_TICK_MIN_GAP_FRACTION,
): number[] {
  if (ticks.length === 0) {
    return [];
  }
  const lastIndex = Math.max(totalMessages - 1, 1);
  const offsets = ticks.map((tick) =>
    Math.min(Math.max(tick.messageIndex / lastIndex, 0), 1),
  );
  for (let i = 1; i < offsets.length; i += 1) {
    offsets[i] = Math.max(offsets[i], offsets[i - 1] + minGap);
  }
  offsets[offsets.length - 1] = Math.min(offsets[offsets.length - 1], 1);
  for (let i = offsets.length - 2; i >= 0; i -= 1) {
    offsets[i] = Math.min(offsets[i], offsets[i + 1] - minGap);
  }
  return offsets;
}
