import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import {
  attentionAfterConversationOpen,
  attentionAfterTurnSettled,
} from "../lib/chat-attention-state";

const root = join(import.meta.dir, "..");

describe("chat conversation attention state", () => {
  test("marks only out-of-focus completed turns for sidebar attention", () => {
    expect(
      [...attentionAfterTurnSettled([], "conversation-a", "conversation-a")],
    ).toEqual([]);
    expect(
      [...attentionAfterTurnSettled([], "conversation-a", "conversation-b")],
    ).toEqual(["conversation-a"]);
    expect(
      [...attentionAfterTurnSettled(["conversation-a"], "conversation-a", null)],
    ).toEqual(["conversation-a"]);
  });

  test("opening a conversation clears its local attention marker", () => {
    expect(
      [...attentionAfterConversationOpen(["conversation-a", "conversation-b"], "conversation-a")],
    ).toEqual(["conversation-b"]);
    expect(
      [...attentionAfterConversationOpen(["conversation-a"], null)],
    ).toEqual(["conversation-a"]);
  });

  test("chat shell keeps attention state local and clears it through recents navigation", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");
    const sidebar = readFileSync(join(root, "components/sidebar/ChatSidebar.tsx"), "utf-8");

    expect(chat).toContain('from "@/lib/chat-attention-state"');
    expect(chat).toContain("markConversationAttentionIfOutOfFocus(targetConversationId)");
    expect(chat).toContain("clearConversationAttention(conversationId)");
    expect(chat).toContain("attentionConversationIds={attentionConversationIds}");
    expect(sidebar).toContain("attentionConversationIds?: ReadonlySet<string>");
    expect(sidebar).toContain("data-has-attention");
    expect(sidebar).not.toContain("shadow-[0_0_0_3px");
  });
});
