import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const root = join(import.meta.dir, "..");

const readChatShellSource = () =>
  [
    readFileSync(join(root, "components/chat/transcript-hydration.ts"), "utf-8"),
    readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8"),
  ].join("\n");


describe("chat archive/delete lifecycle source contract", () => {
  test("chat switching keeps prior messages visible until hydration completes", () => {
    const chat = readChatShellSource();
    const loadConversationStart = chat.indexOf("const loadConversation = async (convId: string) => {");
    const loadConversationEnd = chat.indexOf("const loadConversationForRun", loadConversationStart);
    const loadConversation = chat.slice(loadConversationStart, loadConversationEnd);

    expect(loadConversationStart).toBeGreaterThan(-1);
    // #252: hydration flows through the session cache; loading state is
    // honest and prior messages stay visible until a snapshot is ready.
    expect(loadConversation).toContain("transcriptSessionCache.navigate");
    expect(loadConversation).toContain("setStreamStatus(loading ? t('common.loading') : null)");
    expect(loadConversation).not.toContain("setMessages([])");
    expect(loadConversation).toContain("applyTranscriptNavigationState(state,");
  });

  test("active archive and delete navigate away from the removed chat", () => {
    const chat = readChatShellSource();
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
    const chat = readChatShellSource();
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
    const chat = readChatShellSource();
    const loadConversationStart = chat.indexOf("const loadConversation = async (convId: string) => {");
    const loadConversationEnd = chat.indexOf("const loadConversationForRun", loadConversationStart);
    const loadConversation = chat.slice(loadConversationStart, loadConversationEnd);

    expect(chat).toContain("function isMissingConversationLoadError(error: unknown)");
    expect(loadConversation).toContain(
      "isMissingConversationError: isMissingConversationLoadError",
    );
    expect(loadConversation).toContain("onMissingConversation: () => {");
    expect(loadConversation).toContain("setHistoryItems((prev) =>");
    expect(loadConversation).toContain("!historyItemBelongsToConversation(item, convId)");
  });

  test("restoring archived or deleted chats refreshes visible history", () => {
    const chat = readChatShellSource();
    const sidebar = readFileSync(join(root, "components/sidebar/ChatSidebar.tsx"), "utf-8");
    const profileMenu = readFileSync(join(root, "components/sidebar/ProfileMenu.tsx"), "utf-8");
    const settings = readFileSync(join(root, "components/views/SettingsView.tsx"), "utf-8");
    const archived = readFileSync(join(root, "components/settings/ArchivedChatsView.tsx"), "utf-8");
    const deleted = readFileSync(join(root, "components/settings/DeletedItemsView.tsx"), "utf-8");

    expect(chat).toContain("onHistoryMutated={refreshHistory}");
    expect(sidebar).toContain("onHistoryMutated={onHistoryMutated}");
    expect(profileMenu).toContain("onHistoryMutated?: () => void");
    expect(profileMenu).toContain("onRestored={onHistoryMutated}");
    expect(settings).toContain("onHistoryMutated?: () => void");
    expect(settings).toContain("onHistoryMutated?.()");
    expect(archived).toContain("onRestored?: () => void");
    expect(archived).toContain("onRestored?.()");
    expect(deleted).toContain("onRestored?: () => void");
    expect(deleted).toContain("onRestored?.()");
  });

  test("persisted result cards are validated before structured hydration", () => {
    const chat = readChatShellSource();
    const hydrateStart = chat.indexOf("function hydrateMessagesFromApi(items: ApiMessage[]): HydratedMessages");
    const hydrateEnd = chat.indexOf("function createPendingAssistantMessage", hydrateStart);
    const hydrateBlock = chat.slice(hydrateStart, hydrateEnd);

    expect(chat).toContain("function isHydratableResultCard(value: unknown)");
    expect(hydrateBlock).toContain("isHydratableResultCard(resultCard)");
    expect(hydrateBlock).not.toContain("resultCard &&\n      Array.isArray(resultCard.rows)");
  });

  test("header delete requires a selected chat and confirmation", () => {
    const chat = readChatShellSource();

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
    const chat = readChatShellSource();
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
