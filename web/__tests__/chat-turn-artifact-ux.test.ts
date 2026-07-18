import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import {
  actionHasCardScopedOwnership,
  visibleComposerActions,
} from "../lib/chat-action-ownership";
import {
  confirmationRowKey,
  confirmationStatusAllowsActions,
} from "../components/chat/confirmation-display";
import type { ChatActionOption } from "../components/chat/types";

const root = join(import.meta.dir, "..");

const readChatShellSource = () =>
  [
    readFileSync(join(root, "components/chat/transcript-hydration.ts"), "utf-8"),
    readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8"),
  ].join("\n");


describe("chat turn artifact UX", () => {
  test("shared action ownership keeps card actions out of composer and footer surfaces", () => {
    const actions: ChatActionOption[] = [
      { type: "run_backtest", label: "Run backtest", presentation: "confirmation" },
      { type: "change_dates", label: "Change dates", presentation: "confirmation" },
      { type: "change_asset", label: "Change asset", presentation: "confirmation" },
      { type: "adjust_assumptions", label: "Adjust assumptions", presentation: "confirmation" },
      { type: "cancel_confirmation", label: "Cancel", presentation: "confirmation" },
      { type: "show_breakdown", label: "Explain result", presentation: "result" },
      { type: "refine_strategy", label: "Refine idea", presentation: "result" },
      { type: "retry_failed_action", label: "Try again" },
      { type: "save_strategy", label: "Save", presentation: "result" },
      { id: "ask-follow-up", label: "Ask follow-up" },
      { id: "presentation-confirmation", label: "Presentation confirmation", presentation: "confirmation" },
      { id: "presentation-result", label: "Presentation result", presentation: "result" },
    ];

    expect(actions.filter(actionHasCardScopedOwnership).map((action) => action.label)).toEqual([
      "Run backtest",
      "Change dates",
      "Change asset",
      "Adjust assumptions",
      "Cancel",
      "Explain result",
      "Refine idea",
      "Save",
      "Presentation confirmation",
      "Presentation result",
    ]);
    expect(visibleComposerActions(actions).map((action) => action.label)).toEqual([
      "Try again",
      "Ask follow-up",
    ]);
  });

  test("confirmation cards share the premium artifact shell and avoid stale action duplication", () => {
    const card = readFileSync(
      join(root, "components/chat/StrategyConfirmationCard.tsx"),
      "utf-8",
    );

    expect(card).toContain("artifactStatusToneClassName");
    expect(card).not.toContain("const confirmationToneClasses");
    expect(card).toContain("confirmationDisplayState");
    expect(card).toContain("font-display text-[18px]");
    expect(card).not.toContain("{confirmation.summary}");
    expect(card).toContain("text-[#505a63] dark:text-[#8d969e]");
    expect(card).toContain("activeActions.length > 0");
    expect(card).toContain("confirmation.confirmation_state === \"active\"");
    expect(card).toContain("confirmationCardViewModel");
    expect(card).toContain("confirmationAssetTitle");
    expect(card).toContain("confirmationAssumptionDisplay({");
    expect(card).toContain("assetClass: confirmation.asset_class");
    expect(card).not.toContain("confirmation.rows.slice(0, 3)");
    expect(card).not.toContain("sm:grid-cols-3");
    expect(card).not.toContain("opacity-70");
  });

  test("confirmation status icons reflect status semantics, not localized labels", () => {
    const card = readFileSync(
      join(root, "components/chat/StrategyConfirmationCard.tsx"),
      "utf-8",
    );

    expect(card).toContain("CONFIRMATION_STATUS_ICON_STATE");
    expect(card).toContain("satisfies Record<StrategyConfirmationStatus, ConfirmationStatusIconState>");
    expect(card).toContain("function confirmationStatusIcon(");
    expect(card).toContain("TERMINAL_CONFIRMATION_STATUSES");
    expect(card).toContain("!TERMINAL_CONFIRMATION_STATUSES.has(status)");
    expect(card).toContain("data-confirmation-status={displayState.status}");
    expect(card).not.toContain('if (status === "editing")');
    expect(card).toContain("editing: { icon: Pencil, isSpinning: false }");
    expect(card).toContain("ready_to_run: { icon: Play, isSpinning: false }");
    expect(card).toContain("request_sent: { icon: Send, isSpinning: false }");
    expect(card).toContain("could_not_run: { icon: TriangleAlert, isSpinning: false }");
    expect(card).toContain("run_complete: { icon: CheckCircle2, isSpinning: false }");
    expect(card).toContain("updated: { icon: RefreshCw, isSpinning: false }");
  });

  test("confirmation actions are gated by semantic status, not stale action arrays", () => {
    expect(confirmationStatusAllowsActions("ready_to_run")).toBe(true);
    expect(confirmationStatusAllowsActions("needs_change")).toBe(true);
    expect(confirmationStatusAllowsActions("updated")).toBe(true);
    expect(confirmationStatusAllowsActions("running")).toBe(false);
    expect(confirmationStatusAllowsActions("request_sent")).toBe(false);
    expect(confirmationStatusAllowsActions("run_complete")).toBe(false);
    expect(confirmationStatusAllowsActions("could_not_run")).toBe(false);
    expect(confirmationStatusAllowsActions("draft_canceled")).toBe(false);
    expect(confirmationStatusAllowsActions("not_completed")).toBe(false);

    const card = readFileSync(
      join(root, "components/chat/StrategyConfirmationCard.tsx"),
      "utf-8",
    );
    const chat = readChatShellSource();

    expect(card).toContain("confirmationStatusAllowsActions(displayState.status)");
    expect(chat).toContain("confirmationStatusAllowsActions(confirmationStatus)");
  });

  test("confirmation row identity uses structured keys instead of translated labels", () => {
    expect(
      confirmationRowKey({
        label: "Capital inicial",
        labelKey: "chat.confirmation.rows.starting_capital",
      }),
    ).toBe("starting_capital");
    expect(confirmationRowKey({ label: "Capital inicial" })).toBeNull();
  });

  test("assistant turn controls render for artifact turns without duplicating card-scoped actions", () => {
    const message = readFileSync(
      join(root, "components/chat/ChatMessage.tsx"),
      "utf-8",
    );
    const ownership = readFileSync(
      join(root, "lib/chat-action-ownership.ts"),
      "utf-8",
    );
    const chat = readChatShellSource();

    expect(ownership).toContain("export function actionHasCardScopedOwnership");
    expect(ownership).toContain("export function visibleComposerActions");
    expect(chat).toContain("visibleComposerActions(latestAi?.actions ?? [])");
    expect(message).toContain('import { actionHasCardScopedOwnership } from "@/lib/chat-action-ownership";');
    expect(message).toContain("const footerMessageActions =");
    expect(message).toContain("!actionHasCardScopedOwnership(action)");
    expect(message).toContain("const shouldShowAssistantFooter =");
    expect(message).toContain("!isUser && !isStreaming");
    expect(message).toContain("{shouldShowAssistantFooter &&");
    expect(message).toContain("isLatest || rating || showOptions || Boolean(retryAction)");
    expect(message).toContain("group-hover:opacity-100");
    expect(message).toContain("focus-within:opacity-100");
    expect(message).not.toContain("const shouldShowTextFooter =");
  });

  test("card-scoped confirmation actions close the source card before sending", () => {
    const chat = readChatShellSource();
    const handleActionStart = chat.indexOf("const handleAction =");
    const handleActionEnd = chat.indexOf("// ── Chat options helpers", handleActionStart);
    const handleActionBlock = chat.slice(handleActionStart, handleActionEnd);

    expect(handleActionStart).toBeGreaterThan(-1);
    expect(handleActionBlock).toContain(
      "const confirmationEffect = confirmationActionEffectFromAction(action)",
    );
    expect(handleActionBlock).toContain("setMessages((prev) =>");
    expect(handleActionBlock).toContain("normalizeConfirmationHistory(");
    expect(handleActionBlock).toContain(
      "applyConfirmationActionEffects(prev, [confirmationEffect])",
    );
  });

  test("final recovery responses hydrate retry controls from structured metadata", () => {
    const chat = readChatShellSource();

    expect(chat).toContain("retryLastTurnActionFromMetadata");
    expect(chat).toContain("const finalMessageId =");
    expect(chat).toContain("failedActionRetryActionFromMetadata(finalPayload)");
    expect(chat).toContain("retryLastTurnActionFromMetadata(finalPayload");
    expect(chat).not.toContain("Please retry in a moment");
  });

  test("async job cards only promise retry when the turn has a retry action", () => {
    const card = readFileSync(
      join(root, "components/chat/BacktestJobCard.tsx"),
      "utf-8",
    );
    const message = readFileSync(
      join(root, "components/chat/ChatMessage.tsx"),
      "utf-8",
    );

    expect(card).toContain("canRetry?: boolean");
    expect(card).toContain("backtestJobCardCopy(job, { canRetry })");
    expect(card).toContain("artifactStatusToneClassName(copy.tone)");
    expect(card).not.toContain("const toneClasses");
    expect(message).toContain("canRetry={Boolean(retryAction)}");
  });

  test("result card keeps lifecycle completion neutral and saved state explicit", () => {
    const card = readFileSync(
      join(root, "components/chat/StrategyResultCard.tsx"),
      "utf-8",
    );

    expect(card).toContain('artifactStatusToneClassName("neutral")');
    expect(card).toContain('artifactStatusToneClassName("success")');
    expect(card).toContain("view.hero.tone === \"positive\"");
  });

  test("assistant more menu hides internal message ids", () => {
    const message = readFileSync(
      join(root, "components/chat/ChatMessage.tsx"),
      "utf-8",
    );

    expect(message).toContain("chat.copy_plaintext");
    expect(message).toContain("chat.report_issue");
    expect(message).not.toContain("chat.copy_id");
    expect(message).not.toContain("handleCopy(message.id)");
  });

  test("stream error handling settles confirmation artifacts and clears stale composer actions", () => {
    const chat = readChatShellSource();
    const errorStart = chat.indexOf('if (event.event === "error")');
    const errorEnd = chat.indexOf('if (event.event === "final")', errorStart);
    const errorBlock = chat.slice(errorStart, errorEnd);

    expect(errorStart).toBeGreaterThan(-1);
    expect(errorBlock).toContain("retryLastTurnActionFromMetadata(errorPayload");
    expect(errorBlock).toContain("setInputActions([])");
    expect(errorBlock).toContain("settleOpenConfirmationsAfterStreamError(");
    expect(errorBlock).not.toContain("settleOpenConfirmationsAfterTextFinal(");
  });
});
