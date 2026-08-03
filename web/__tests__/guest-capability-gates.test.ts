import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import {
  decideGuestMessageGate,
  decideGuestNewConversationGate,
  decideGuestSimulationGate,
  guestSimulationPrecheckResetAt,
  isExactGuestRunReplay,
} from "../lib/guest-capability-gates";

describe("guest capability gate policy", () => {
  test("stops an exhausted guest message before sending but never gates registered users", () => {
    expect(
      decideGuestMessageGate({
        accountKind: "guest",
        availableNow: false,
      }),
    ).toEqual({ kind: "convert", reason: "message_limit" });
    expect(
      decideGuestMessageGate({
        accountKind: "registered",
        availableNow: false,
      }),
    ).toEqual({ kind: "allow" });
  });

  test("allows exact replay before converting a third unique guest simulation", () => {
    expect(
      decideGuestSimulationGate({
        accountKind: "guest",
        availableNow: false,
        exactReplay: true,
      }),
    ).toEqual({ kind: "allow" });
    expect(
      decideGuestSimulationGate({
        accountKind: "guest",
        availableNow: false,
        exactReplay: false,
      }),
    ).toEqual({ kind: "convert", reason: "simulation_limit" });
    expect(
      isExactGuestRunReplay(
        [
          {
            selectedAction: {
              type: "run_backtest",
              payload: { confirmation_id: "confirmation-1" },
            },
          },
        ],
        {
          type: "run_backtest",
          payload: { confirmation_id: "confirmation-1" },
        },
      ),
    ).toBe(true);
    expect(
      isExactGuestRunReplay(
        [
          {
            selectedAction: {
              type: "run_backtest",
              payload: { confirmation_id: "confirmation-1" },
            },
          },
        ],
        {
          type: "run_backtest",
          payload: { idempotency_key: "resumed-action-2" },
        },
      ),
    ).toBe(false);
  });

  test("uses the visitor-day reset after a workspace renewal", () => {
    const newWorkspaceExpiresAt = "2026-08-10T12:00:00Z";

    expect(
      guestSimulationPrecheckResetAt({
        day: { period_end: "2026-08-04T00:00:00Z" },
      }),
    ).toBe("2026-08-04T00:00:00Z");
    expect(
      guestSimulationPrecheckResetAt({
        day: { period_end: "2026-08-04T00:00:00Z" },
      }),
    ).not.toBe(newWorkspaceExpiresAt);
  });

  test("resets an empty guest chat and asks before replacing accepted content", () => {
    expect(
      decideGuestNewConversationGate({
        accountKind: "guest",
        hasAcceptedContent: false,
      }),
    ).toEqual({ kind: "reset_empty" });
    expect(
      decideGuestNewConversationGate({
        accountKind: "guest",
        hasAcceptedContent: true,
      }),
    ).toEqual({ kind: "choose_non_empty" });
    expect(
      decideGuestNewConversationGate({
        accountKind: "registered",
        hasAcceptedContent: true,
      }),
    ).toEqual({ kind: "allow" });
  });

  test("keeps a composer draft when admission is blocked before send", () => {
    const composer = readFileSync(
      join(import.meta.dir, "../components/chat/ChatInput.tsx"),
      "utf-8",
    );

    expect(composer).toContain("const accepted = await onSend");
    expect(composer).toContain("if (accepted === false) return");
  });

  test("does not consume a confirmation action before guest admission", () => {
    const chat = readFileSync(
      join(import.meta.dir, "../components/chat/ChatInterface.tsx"),
      "utf-8",
    );
    const handleAction = chat.slice(
      chat.indexOf("const handleAction ="),
      chat.indexOf("// ── Chat options helpers"),
    );

    expect(handleAction).not.toContain("confirmationActionEffectFromAction");
    expect(chat).toContain("consumeConfirmationActionOnMessages");
  });

  test("carries the exact evidence artifact through the decision gate", () => {
    const result = readFileSync(
      join(import.meta.dir, "../components/chat/StrategyResultCard.tsx"),
      "utf-8",
    );

    expect(result).toContain(
      "onDecisionUnavailable?.(result.evidenceArtifactId!)",
    );
  });
});
