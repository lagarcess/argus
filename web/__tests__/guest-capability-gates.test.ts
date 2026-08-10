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

describe("a spent allowance always explains itself", () => {
  // The defect: `if (!conversationId) return false` ran before the conversion
  // prompt, so a guest returning on a fresh page typed a question, pressed
  // send, and got silence: no message, no signup path, no request made.
  const source = readFileSync(
    join(import.meta.dir, "../components/guest/useGuestExperience.ts"),
    "utf-8",
  );

  test("neither gate drops the send before requesting conversion", () => {
    const start = source.indexOf("const usage = await getUsageAllowances()");
    // Anchor on the call site; the bare name also appears in the imports, and
    // slicing from there produced an empty body that asserted nothing.
    const end = source.indexOf("return true;", source.indexOf("decideGuestMessageGate({"));
    expect(start).toBeGreaterThan(-1);
    expect(end).toBeGreaterThan(start);

    const gateBody = source.slice(start, end);
    expect(gateBody).toContain("decideGuestSimulationGate({");
    expect(gateBody).toContain("decideGuestMessageGate({");
    expect(gateBody).not.toContain("if (!conversationId) return false;");
  });

  test("the pending action is what needs a conversation, not the prompt", () => {
    for (const reason of ["simulation_limit", "message_limit"]) {
      const at = source.indexOf(`reason: "${reason}"`);
      expect(at).toBeGreaterThan(-1);
      // The payload is built conditionally and collapses to null without a
      // conversation, rather than the whole prompt being skipped.
      const around = source.slice(Math.max(0, at - 400), at + 400);
      expect(around).toContain("conversationId");
      expect(around).toContain(": null,");
    }
  });
});

describe("no send is refused in silence", () => {
  // The class, not the two instances: any path that declines a real message
  // has to leave the person something to react to. Two refusals are allowed
  // to stay quiet because nothing was asked of Argus, and they are named here
  // so a new silent one cannot hide among them.
  const chat = readFileSync(
    join(import.meta.dir, "../components/chat/ChatInterface.tsx"),
    "utf-8",
  );
  const SILENT_BY_DESIGN = [
    "if (!trimmed) return false;",
    "if (sendAdmissionInFlightRef.current || isStreamingResponse) {",
  ];

  function sendHandlerBody() {
    const start = chat.indexOf("const handleSend = async (");
    expect(start).toBeGreaterThan(-1);
    const end = chat.indexOf("\n  const ", start + 40);
    expect(end).toBeGreaterThan(start);
    return chat.slice(start, end);
  }

  test("every bare refusal in the send handler is one of the named exceptions", () => {
    const body = sendHandlerBody();
    const lines = body.split("\n");
    const bare: string[] = [];
    let scanned = 0;
    lines.forEach((line, index) => {
      if (!/^\s*return false;\s*$/.test(line)) return;
      scanned += 1;
      // Surfaced here, or delegated to admitSend, which surfaces on its own
      // for every refusal that is not a superseded admission. The sibling
      // block above is what holds admitSend to that.
      const preceding = lines.slice(Math.max(0, index - 8), index + 1).join("\n");
      if (
        /refuseSend|showToast|setGuestSubmissionError|onGateError|admitSend/.test(
          preceding,
        )
      ) {
        return;
      }
      if (SILENT_BY_DESIGN.some((allowed) => preceding.includes(allowed))) return;
      bare.push(
        `${index + 1}: ${lines.slice(Math.max(0, index - 1), index + 1).join(" / ").trim()}`,
      );
    });
    // Guards the scan itself: an empty result has to mean every refusal was
    // classified, not that the slice found none to look at.
    expect(lines.length).toBeGreaterThan(200);
    expect(scanned).toBeGreaterThanOrEqual(3);
    expect(bare).toEqual([]);
  });

  test("the busy refusal says the same thing on both paths", () => {
    const body = sendHandlerBody();
    const busy = body.match(/refuseSend\("chat\.send_busy", SEND_BUSY_FALLBACK\)/g) ?? [];
    expect(busy.length).toBe(2);
  });
});
