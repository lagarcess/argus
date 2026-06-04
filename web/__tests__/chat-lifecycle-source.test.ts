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
    const beforeCatch = loadConversation.slice(0, loadConversation.indexOf("} catch (error)"));

    expect(loadConversationStart).toBeGreaterThan(-1);
    expect(loadConversation).toContain("setStreamStatus(t('common.loading'))");
    expect(beforeCatch).not.toContain("setMessages([])");
    expect(beforeCatch).not.toContain("setInputActions([])");
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

  test("stale or deleted active chats reset to a lazy empty chat instead of creating a new stored conversation", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");
    const initStart = chat.indexOf("// ── Init conversation");
    const initEnd = chat.indexOf("const updateScrollPositionState", initStart);
    const initBlock = chat.slice(initStart, initEnd);
    const removedStart = chat.indexOf("const handleConversationRemoved");
    const removedEnd = chat.indexOf("const handleTriggerPrompt", removedStart);
    const removedBlock = chat.slice(removedStart, removedEnd);

    expect(chat).toContain("resetToEmptyChatSurface");
    expect(initBlock).not.toContain("await createConversation(resolvedLanguage)");
    expect(initBlock).not.toContain("readActiveConversationIdFromUrl() ?? readActiveConversationId()");
    expect(initBlock).toContain("resetToEmptyChatSurface");
    expect(initBlock).toContain("hydrated.messages.length === 0");
    expect(initBlock).toContain("clear empty persisted conversations from the active route");
    expect(chat).toContain('import { useRouter } from "next/navigation";');
    expect(chat).toContain("const router = useRouter();");
    expect(chat).toContain("router.replace(clearedRoute, { scroll: false });");
    expect(removedBlock).toContain("resetToEmptyChatSurface");
    expect(removedBlock).not.toContain("startNewChat()");
  });

  test("missing recent conversations are pruned after a failed load", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");
    const loadConversationStart = chat.indexOf("const loadConversation = async (convId: string) => {");
    const loadConversationEnd = chat.indexOf("const loadConversationForRun", loadConversationStart);
    const loadConversation = chat.slice(loadConversationStart, loadConversationEnd);

    expect(chat).toContain("function isMissingConversationLoadError(error: unknown)");
    expect(loadConversation).toContain("catch (error)");
    expect(loadConversation).toContain("isMissingConversationLoadError(error)");
    expect(loadConversation).toContain("setHistoryItems((prev) =>");
    expect(loadConversation).toContain("!historyItemBelongsToConversation(item, convId)");
  });

  test("persisted result cards are validated before structured hydration", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");
    const hydrateStart = chat.indexOf("function hydrateMessagesFromApi(items: ApiMessage[]): HydratedMessages");
    const hydrateEnd = chat.indexOf("function createPendingAssistantMessage", hydrateStart);
    const hydrateBlock = chat.slice(hydrateStart, hydrateEnd);

    expect(chat).toContain("function isHydratableResultCard(value: unknown)");
    expect(hydrateBlock).toContain("isHydratableResultCard(resultCard)");
    expect(hydrateBlock).not.toContain("resultCard &&\n      Array.isArray(resultCard.rows)");
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

  test("chat disclaimer appears only after conversation activity and is localized", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");
    const en = JSON.parse(readFileSync(join(root, "public/locales/en/common.json"), "utf-8"));
    const es = JSON.parse(readFileSync(join(root, "public/locales/es-419/common.json"), "utf-8"));
    const coldStartBranchStart = chat.indexOf("{messages.length === 0 ? (");
    const coldStartBranchEnd = chat.indexOf(") : (", coldStartBranchStart);
    const coldStartBranch = chat.slice(coldStartBranchStart, coldStartBranchEnd);
    const conversationComposerStart = chat.indexOf("Input fade + bar");
    const conversationComposerEnd = chat.indexOf("</div>\n                </div>\n              </>", conversationComposerStart);
    const conversationComposer = chat.slice(conversationComposerStart, conversationComposerEnd);

    expect(chat).toContain("const showConversationDisclaimer = shouldShowConversationDisclaimer(");
    expect(coldStartBranch).not.toContain("chat.disclaimer");
    expect(conversationComposer).toContain("showConversationDisclaimer &&");
    expect(conversationComposer).toContain('data-testid="chat-disclaimer"');
    expect(conversationComposer).toContain('t("chat.disclaimer", "Argus can make mistakes. For education only. Not financial advice.")');
    expect(conversationComposer).toContain("text-[13px]");
    expect(conversationComposer).toContain("font-normal");
    expect(conversationComposer).toContain("text-black/40 dark:text-white/40");
    expect(en.chat.disclaimer).toBe("Argus can make mistakes. For education only. Not financial advice.");
    expect(es.chat.disclaimer).toBe("Argus puede equivocarse. Solo con fines educativos. No es asesoría financiera.");
  });
});
