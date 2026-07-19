import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const root = join(import.meta.dir, "..");

const chatMessageSource = () =>
  readFileSync(join(root, "components/chat/ChatMessage.tsx"), "utf-8");

// #240: the abandoned-turn recovery renders immediately beneath its owning
// user message as presentation only — not an assistant bubble, no API
// message identity, no assistant feedback/copy affordances — and its retry
// stays the typed retry_last_turn action. Because it is derived from the
// user message itself, it stays attached across cursor pages and a page
// without the owning message can never render an orphan row.

describe("abandoned-turn recovery row", () => {
  test("renders inside the user-message branch beneath the bubble", () => {
    const source = chatMessageSource();
    const userBranchStart = source.indexOf("if (isUser) {");
    const userBranchEnd = source.indexOf("return (", userBranchStart + 20);
    expect(userBranchStart).toBeGreaterThan(-1);

    const userBranch = source.slice(
      userBranchStart,
      source.indexOf("\n  return (\n", userBranchStart),
    );
    expect(userBranch).toContain("message.abandonedRecovery");
    expect(userBranch).toContain('data-testid="abandoned-recovery-row"');
    // The row derives its text through the shared localized recovery path
    // and fires the typed retry action through the normal action handler —
    // but only when the backend still provides the action (a superseded
    // recovery renders its state with no retry affordance).
    expect(userBranch).toContain("recoveryDisplayText(abandonedRecovery.display, t)");
    expect(userBranch).toContain("abandonedRetryAction && (");
    expect(userBranch).toContain("onAction?.(abandonedRetryAction)");
    expect(userBranchEnd).toBeGreaterThan(-1);
  });

  test("is not an assistant bubble and has no feedback or copy affordances", () => {
    const source = chatMessageSource();
    const rowStart = source.indexOf('data-testid="abandoned-recovery-row"');
    expect(rowStart).toBeGreaterThan(-1);
    // Slice the user-branch return containing the row; assistant-only
    // affordances must not appear there.
    const branchStart = source.lastIndexOf("if (isUser) {", rowStart);
    const branchEnd = source.indexOf("\n  return (\n", branchStart);
    const branch = source.slice(branchStart, branchEnd);
    expect(branch).not.toContain("ThumbsUp");
    expect(branch).not.toContain("ThumbsDown");
    expect(branch).not.toContain("handleRating");
    expect(branch).not.toContain("handleCopy");
    expect(branch).not.toContain("postFeedback");
    // Presentation only: the row carries no message id of its own.
    expect(branch).not.toContain("turn-recovery-");
  });

  test("action-kind user messages share the same recovery row", () => {
    // #240: an abandoned structured action renders its chip presentation AND
    // the recovery row — one user branch owns both message kinds, so the row
    // cannot be bypassed by an early action-kind return.
    const source = chatMessageSource();
    expect(source).not.toContain('if (isUser && message.kind === "action")');
    const userBranchStart = source.indexOf("if (isUser) {");
    const userBranch = source.slice(
      userBranchStart,
      source.indexOf("\n  return (\n", userBranchStart),
    );
    expect(userBranch).toContain('message.kind === "action"');
    expect(
      userBranch.split('data-testid="abandoned-recovery-row"').length,
    ).toBe(2);
  });

  test("the click path resolves the persisted owning message before replay", () => {
    const source = readFileSync(
      join(root, "components/chat/ChatInterface.tsx"),
      "utf-8",
    );
    const handlerStart = source.indexOf('if (action.type === "retry_last_turn")');
    const handlerEnd = source.indexOf(
      'if (action.type === "retry_load_conversation")',
      handlerStart,
    );
    const handler = source.slice(handlerStart, handlerEnd);
    expect(handlerStart).toBeGreaterThan(-1);
    // The bound replay consumes the owning request-message identity through
    // the resolver; raw payload text is never sent directly.
    expect(handler).toContain("resolveRetryLastTurnReplay(action, messages)");
    expect(handler).not.toContain("retryLastTurnMessageFromAction(action)");
  });

  test("recovery copy is localized in both languages", () => {
    const en = JSON.parse(
      readFileSync(join(root, "public/locales/en/common.json"), "utf-8"),
    );
    const es = JSON.parse(
      readFileSync(join(root, "public/locales/es-419/common.json"), "utf-8"),
    );
    expect(typeof en.chat.recovery.turn_abandoned).toBe("string");
    expect(en.chat.recovery.turn_abandoned.length).toBeGreaterThan(0);
    expect(typeof es.chat.recovery.turn_abandoned).toBe("string");
    expect(es.chat.recovery.turn_abandoned.length).toBeGreaterThan(0);
  });
});
