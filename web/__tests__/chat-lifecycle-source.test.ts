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
    expect(loadConversation).toContain('setStreamStatus(t("common.loading"))');
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
    const lifecycle = readFileSync(
      join(root, "components/chat/useChatSurfaceLifecycle.ts"),
      "utf-8",
    );
    const initStart = chat.indexOf("// ── Init conversation");
    const initEnd = chat.indexOf("const updateScrollPositionState", initStart);
    const initBlock = chat.slice(initStart, initEnd);
    const removedStart = lifecycle.indexOf("const handleConversationRemoved");
    const removedEnd = lifecycle.indexOf(
      "const handleAllConversationsDeleted",
      removedStart,
    );
    const removedBlock = lifecycle.slice(removedStart, removedEnd);

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

  test("restoring archived or deleted chats refreshes visible history", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");
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
    const projection = readFileSync(
      join(root, "components/chat/chat-message-projection.ts"),
      "utf-8",
    );
    const hydration = readFileSync(join(root, "lib/chat-message-hydration.ts"), "utf-8");
    const hydrateStart = projection.indexOf(
      "export function hydrateMessagesFromApi(",
    );
    const hydrateBlock = projection.slice(hydrateStart);

    expect(hydration).toContain("export function isHydratableResultCard(");
    expect(hydrateBlock).toContain(
      "isHydratableResultCard(metadata.result_card)",
    );
    expect(hydrateBlock).not.toContain(
      "metadata.result_card &&\n        Array.isArray(metadata.result_card.rows)",
    );
  });

  test("header delete requires a selected chat and confirmation", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");

    expect(chat).toContain('import { ConfirmDialog } from "@/components/ui/ConfirmDialog";');
    expect(chat).toMatch(
      /const \[pendingHeaderDeleteId, setPendingHeaderDeleteId\] = useState<\s*string \| null\s*>\(null\);/,
    );
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
    const legal = readFileSync(join(root, "components/chat/ChatLegalNotice.tsx"), "utf-8");
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
    expect(conversationComposer).toContain(
      "showRegisteredDisclaimer={showConversationDisclaimer}",
    );
    expect(legal).toContain('data-testid="chat-disclaimer"');
    expect(legal).toContain('"chat.disclaimer"');
    expect(legal).toContain("text-[13px]");
    expect(legal).toContain("font-normal");
    expect(legal).toContain("text-black/40 dark:text-white/40");
    expect(en.chat.disclaimer).toBe("Argus can make mistakes. For education only. Not financial advice.");
    expect(es.chat.disclaimer).toBe("Argus puede equivocarse. Solo con fines educativos. No es asesoría financiera.");
  });

  test("guest expiry stays composer-owned across empty and active chat layouts", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");
    const legal = readFileSync(join(root, "components/chat/ChatLegalNotice.tsx"), "utf-8");
    const footer = readFileSync(join(root, "components/guest/GuestLegalFooter.tsx"), "utf-8");
    const sidebar = readFileSync(join(root, "components/sidebar/ChatSidebar.tsx"), "utf-8");

    expect(chat.match(/<ChatLegalNotice/g)?.length).toBe(2);
    expect(chat).not.toContain("temporaryExpiresAt=");
    expect(legal).toContain("<GuestLegalFooter");
    expect(footer.match(/data-testid="guest-temporary-notice"/g)?.length).toBe(1);
    expect(sidebar).not.toContain("guest-sidebar-expiry");
    expect(sidebar).not.toContain("temporaryExpiresAt");
  });

  test("durable retry renders beside its owning row and creates a visible new attempt", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");
    const message = readFileSync(join(root, "components/chat/ChatMessage.tsx"), "utf-8");

    expect(chat).toContain("normalizeDurableRetryActionHistory");
    expect(chat).toContain("retryLastTurnRequestMessageIdFromAction");
    expect(chat).toContain("renderUserMessage: true");
    expect(message).toContain("data-testid=\"user-turn-recovery\"");
    expect(message).toContain("data-testid=\"user-turn-retry\"");
  });

  test("the adjacent user-turn Retry control keeps a 44px minimum tap target", () => {
    const message = readFileSync(join(root, "components/chat/ChatMessage.tsx"), "utf-8");
    const retryStart = message.indexOf('data-testid="user-turn-retry"');
    const retryEnd = message.indexOf("</button>", retryStart);
    const retryButton = message.slice(retryStart, retryEnd);

    expect(retryStart).toBeGreaterThan(-1);
    expect(retryEnd).toBeGreaterThan(retryStart);
    expect(retryButton).toContain("min-h-11");
    expect(retryButton).not.toContain("min-h-9");
  });

  test("ordinary transport ambiguity follows durable pages and never builds composer retry", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");
    const hydration = readFileSync(join(root, "lib/chat-message-hydration.ts"), "utf-8");
    const catchStart = chat.indexOf("const isOrdinaryTransportAmbiguity =");
    const catchEnd = chat.indexOf("const handleOnboardingGoalChoice", catchStart);
    const sendCatch = chat.slice(catchStart, catchEnd);

    expect(catchStart).toBeGreaterThan(-1);
    expect(sendCatch).toContain("resolveOrdinaryTransportAmbiguityView");
    expect(sendCatch).toContain("loadAllConversationMessagePages");
    expect(sendCatch).toContain("conversationLoadFailureMessage");
    expect(sendCatch).toContain('t("chat.status.checking")');
    expect(sendCatch.indexOf('setStreamStatus(t("chat.status.checking"))')).toBeLessThan(
      sendCatch.indexOf("await resolveOrdinaryTransportAmbiguityView"),
    );
    expect(sendCatch).toContain("signal: reconciliationController.signal");
    expect(sendCatch).toContain("if (!view.showChecking)");
    expect(chat).toContain("cancelOrdinaryTransportReconciliation();");
    expect(hydration).toContain("resolveOrdinaryTransportAmbiguity");
    expect(hydration).toContain('resolution.kind !== "terminal"');
    expect(hydration).toContain("message.id !== fallback.assistantId");
    expect(sendCatch).not.toContain(
      "actions: retryLastTurnAction ? [retryLastTurnAction] : m.actions",
    );
  });

  test("text and structured ordinary turns snapshot ids before paged reconciliation", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");
    const sendStart = chat.indexOf("const handleSend = async");
    const sendEnd = chat.indexOf("const handleOnboardingGoalChoice", sendStart);
    const send = chat.slice(sendStart, sendEnd);

    expect(send).toContain('action?.type !== "run_backtest"');
    expect(send).toContain("snapshotOrdinaryTransportMessageIds");
    expect(send).toContain("ordinaryTransportMessageIds");
    expect(send).toContain("resolveOrdinaryTransportAmbiguityView");
    expect(send).not.toContain(
      'const isOrdinaryTransportAmbiguity =\n        !action?.type',
    );
    const ambiguityStart = send.indexOf("if (isOrdinaryTransportAmbiguity)");
    const ambiguityEnd = send.indexOf(
      "const confirmationId = ambiguousRunConfirmationId",
      ambiguityStart,
    );
    expect(send.slice(ambiguityStart, ambiguityEnd)).not.toContain(
      "streamToConversation(",
    );
  });

  test("onboarding typed stream errors cannot be overwritten by done or profile completion", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");
    const start = chat.indexOf("const handleOnboardingGoalChoice");
    const end = chat.indexOf("// ── Action routing", start);
    const onboarding = chat.slice(start, end);

    expect(onboarding).toContain("let onboardingStreamFailed = false");
    expect(onboarding).toContain("onboardingStreamFailed = true");
    expect(onboarding).toContain("if (onboardingStreamFailed) return");
    expect(onboarding).toContain("setShowOnboardingGoalCards(true)");
    expect(onboarding).not.toMatch(
      /if \(event\.event === "done"\) \{\s+setStreamStatus/,
    );
    expect(onboarding.indexOf("if (onboardingStreamFailed) return")).toBeLessThan(
      onboarding.indexOf("await patchMe"),
    );
  });

  test("pending onboarding choices return when a recoverable conversation reloads", () => {
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");
    const initStart = chat.indexOf("// ── Init conversation");
    const initEnd = chat.indexOf("const updateScrollPositionState", initStart);
    const init = chat.slice(initStart, initEnd);

    expect(init).toContain("const showRegisteredOnboarding =");
    expect(init).toContain('meResponse?.account_kind !== "guest"');
    expect(init).toContain('stage === "language_selection"');
    expect(init).toContain('stage === "primary_goal_selection"');
    expect(init).toContain("setShowOnboardingGoalCards(");
    expect(init).toContain(
      "setShowOnboardingGoalCards(showRegisteredOnboarding)",
    );
    expect(init).not.toContain(
      'hydrated.messages.length === 0\n              && (stage === "language_selection"',
    );
  });
});
