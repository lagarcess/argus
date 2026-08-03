import type { GuestConversionReason } from "./guest-conversion";
import { runActionIdempotencyKey } from "./usage-allowance";

type AccountKind = "guest" | "registered";

export type GuestGateDecision =
  | { kind: "allow" }
  | { kind: "reset_empty" }
  | { kind: "choose_non_empty" }
  | { kind: "convert"; reason: GuestConversionReason };

export function decideGuestMessageGate(input: {
  accountKind: AccountKind;
  availableNow: boolean;
}): GuestGateDecision {
  if (input.accountKind !== "guest" || input.availableNow) {
    return { kind: "allow" };
  }
  return { kind: "convert", reason: "message_limit" };
}

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

export function guestSimulationPrecheckResetAt(input: {
  day: { period_end: string } | null;
}): string | null {
  return input.day?.period_end ?? null;
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
