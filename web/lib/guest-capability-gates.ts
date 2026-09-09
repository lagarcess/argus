import type { GuestConversionReason } from "./guest-conversion";
import { runActionIdempotencyKey } from "./usage-allowance";

type AccountKind = "guest" | "registered";

export type GuestGateDecision =
  | { kind: "allow" }
  | { kind: "reset_empty" }
  | { kind: "choose_non_empty" }
  | { kind: "convert"; reason: GuestConversionReason };

export function decideGuestSimulationGate(input: {
  accountKind: AccountKind;
  availableNow: boolean;
  exactReplay: boolean;
}): GuestGateDecision {
  if (
    input.accountKind !== "guest" ||
    input.availableNow ||
    input.exactReplay
  ) {
    return { kind: "allow" };
  }
  return { kind: "convert", reason: "simulation_limit" };
}

export type GuestSimulationReset = {
  resetAt: string | null;
  resetKind: "daily" | "workspace";
};

/** The horizon that holds the guest, as the backend named it. */
export function guestSimulationPrecheckReset(input: {
  day: { period_end: string } | null;
  guest_session: { period_end: string } | null;
  limiting_window: "hour" | "day" | "guest_session" | null;
}): GuestSimulationReset {
  if (input.limiting_window === "guest_session" && input.guest_session) {
    return { resetAt: input.guest_session.period_end, resetKind: "workspace" };
  }
  return { resetAt: input.day?.period_end ?? null, resetKind: "daily" };
}

export function decideGuestNewConversationGate(input: {
  accountKind: AccountKind;
  hasAcceptedContent: boolean;
}): GuestGateDecision {
  if (input.accountKind !== "guest") {
    return { kind: "allow" };
  }
  return input.hasAcceptedContent
    ? { kind: "choose_non_empty" }
    : { kind: "reset_empty" };
}

export function isExactGuestRunReplay(
  messages: Array<{
    selectedAction?: {
      type?: string;
      payload?: Record<string, unknown>;
    };
  }>,
  action: {
    type?: string;
    payload?: Record<string, unknown>;
  },
) {
  if (action.type !== "run_backtest") return false;
  const requestedKey = runActionIdempotencyKey({
    type: action.type,
    payload: action.payload,
  });
  if (!requestedKey) return false;
  return messages.some((message) => {
    const prior = message.selectedAction;
    if (prior?.type !== "run_backtest") return false;
    return (
      runActionIdempotencyKey({
        type: prior.type,
        payload: prior.payload,
      }) === requestedKey
    );
  });
}
