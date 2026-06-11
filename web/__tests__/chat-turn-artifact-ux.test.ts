import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import {
  actionHasCardScopedOwnership,
  visibleComposerActions,
} from "../lib/chat-action-ownership";
import type { ChatActionOption } from "../components/chat/types";

const root = join(import.meta.dir, "..");

describe("chat turn artifact UX", () => {
  test("shared action ownership keeps card actions out of composer and footer surfaces", () => {
    const actions: ChatActionOption[] = [
      { type: "run_backtest", label: "Run backtest", presentation: "confirmation" },
      { type: "show_breakdown", label: "Explain result", presentation: "result" },
      { type: "retry_failed_action", label: "Try again" },
      { type: "save_strategy", label: "Save", presentation: "result" },
      { id: "ask-follow-up", label: "Ask follow-up" },
      { id: "presentation-confirmation", label: "Presentation confirmation", presentation: "confirmation" },
      { id: "presentation-result", label: "Presentation result", presentation: "result" },
    ];

    expect(actions.filter(actionHasCardScopedOwnership).map((action) => action.label)).toEqual([
      "Run backtest",
      "Explain result",
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

    expect(card).toContain("confirmationToneClasses");
    expect(card).toContain("confirmationDisplayState");
    expect(card).toContain("font-display text-[18px]");
    expect(card).toContain("text-[#505a63] dark:text-[#8d969e]");
    expect(card).toContain("activeActions.length > 0");
    expect(card).toContain("confirmation.confirmation_state === \"active\"");
    expect(card).not.toContain("opacity-70");
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
    const chat = readFileSync(
      join(root, "components/chat/ChatInterface.tsx"),
      "utf-8",
    );

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
    expect(message).toContain("canRetry={Boolean(retryAction)}");
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
    const chat = readFileSync(
      join(root, "components/chat/ChatInterface.tsx"),
      "utf-8",
    );
    const errorStart = chat.indexOf('if (event.event === "error")');
    const errorEnd = chat.indexOf('if (event.event === "final")', errorStart);
    const errorBlock = chat.slice(errorStart, errorEnd);

    expect(errorStart).toBeGreaterThan(-1);
    expect(errorBlock).toContain("setInputActions([])");
    expect(errorBlock).toContain("settleOpenConfirmationsAfterStreamError(");
    expect(errorBlock).not.toContain("settleOpenConfirmationsAfterTextFinal(");
  });
});
