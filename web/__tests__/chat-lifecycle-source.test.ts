import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const root = join(import.meta.dir, "..");

describe("chat archive/delete lifecycle source contract", () => {
  test("chat switching keeps prior messages visible until hydration completes", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");
    const loadConversationStart = chat.indexOf("const loadConversation = async (convId: string) => {");
    const loadConversationEnd = chat.indexOf("const loadConversationForRun", loadConversationStart);
    const loadConversation = chat.slice(loadConversationStart, loadConversationEnd);

    expect(loadConversationStart).toBeGreaterThan(-1);
    expect(loadConversation).toContain("setStreamStatus(t('common.loading'))");
    expect(loadConversation).not.toContain("setMessages([])");
    expect(loadConversation).not.toContain("setInputActions([])");
  });

  test("active archive and delete navigate away from the removed chat", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");
    const sidebar = readFileSync(join(root, "components/sidebar/ChatSidebar.tsx"), "utf-8");
    const palette = readFileSync(join(root, "components/sidebar/ChatCommandPalette.tsx"), "utf-8");

    expect(chat).toContain("handleConversationRemoved");
    expect(chat).toContain("onConversationRemoved={handleConversationRemoved}");
    expect(sidebar).toContain("onConversationRemoved?.(id)");
    expect(sidebar).toContain("onConversationRemoved?.(pendingDeleteId)");
    expect(palette).toContain("onConversationRemoved?.(item.conversationId)");
    expect(palette).toContain("onConversationRemoved?.(pendingDeleteItem.conversationId)");
  });
});
