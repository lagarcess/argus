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
    expect(chat).toContain("historyItemBelongsToConversation");
    expect(chat).toContain("setHistoryItems((prev) =>");
    expect(chat).toContain("onConversationRemoved={handleConversationRemoved}");
    expect(sidebar).toContain("function historyConversationId");
    expect(sidebar).toContain("const itemConversationId = historyConversationId(item)");
    expect(sidebar).toContain("item.id === itemConversationId ? item : { ...item, id: itemConversationId }");
    expect(sidebar).toContain('aria-current={isActiveConversation ? "page" : undefined}');
    expect(sidebar).toContain('data-active-conversation={isActiveConversation ? "true" : undefined}');
    expect(sidebar).toContain("onConversationRemoved?.(id)");
    expect(sidebar).toContain("onConversationRemoved?.(pendingDeleteId)");
    expect(palette).toContain("onConversationRemoved?.(item.conversationId)");
    expect(palette).toContain("onConversationRemoved?.(pendingDeleteItem.conversationId)");
  });

  test("header delete requires a selected chat and confirmation", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");

    expect(chat).toContain('import { ConfirmDialog } from "@/components/ui/ConfirmDialog";');
    expect(chat).toContain("const [pendingHeaderDeleteId, setPendingHeaderDeleteId] = useState<string | null>(null);");
    expect(chat).toContain("const [isDeletingHeaderChat, setIsDeletingHeaderChat] = useState(false);");
    expect(chat).toContain("if (!conversationId) return;");
    expect(chat).toContain("setPendingHeaderDeleteId(conversationId);");
    expect(chat).toContain("deleteConversation(pendingHeaderDeleteId)");
    expect(chat).toContain("handleConversationRemoved(pendingHeaderDeleteId);");
    expect(chat).toContain("isOpen={Boolean(pendingHeaderDeleteId)}");
    expect(chat).toContain("disabled={!conversationId || isDeletingHeaderChat}");
  });
});
