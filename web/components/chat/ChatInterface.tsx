"use client";

import { useMemo, useEffect, useRef, useState } from "react";
import {
  ChevronRight,
  History,
  Menu,
  MessageSquarePlus,
  Plus,
  Search,
  Settings,
  Trash2,
} from "lucide-react";
import { useTranslation } from "react-i18next";

import {
  createConversation,
  formatRelativeDate,
  getConversationMessages,
  listHistory,
  resultCardFromRun,
  streamChatMessage,
  type HistoryItem,
  type BacktestRun,
} from "@/lib/argus-api";
import CollectionPicker from "./CollectionPicker";
import CollectionsView from "../views/CollectionsView";
import SettingsView from "../views/SettingsView";
import StrategiesView from "../views/StrategiesView";
import ChatInput from "./ChatInput";
import ChatMessage from "./ChatMessage";
import { type ChatActionOption, type Message } from "./types";

// ─── Constants ────────────────────────────────────────────────────────────────

type View = "chat" | "strategies" | "collections" | "settings";

// ─── Component ────────────────────────────────────────────────────────────────

export default function ChatInterface() {
  const { t } = useTranslation();

  const starterActions = useMemo<ChatActionOption[]>(() => [
    {
      id: "starter-tsla",
      label: t('chat.starter_actions.tsla.label'),
      value: t('chat.starter_actions.tsla.value'),
    },
    {
      id: "starter-btc",
      label: t('chat.starter_actions.btc.label'),
      value: t('chat.starter_actions.btc.value'),
    },
    {
      id: "starter-dca",
      label: t('chat.starter_actions.dca.label'),
      value: t('chat.starter_actions.dca.value'),
    },
  ], [t]);

  const [messages, setMessages] = useState<Message[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [currentView, setCurrentView] = useState<View>("chat");
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [showChatOptions, setShowChatOptions] = useState(false);
  const [activeChatOptionsPanel, setActiveChatOptionsPanel] = useState<
    "none" | "history" | "collection"
  >("none");
  const [searchText, setSearchText] = useState("");
  const [streamStatus, setStreamStatus] = useState<string | null>(null);
  const [historyItems, setHistoryItems] = useState<HistoryItem[]>([]);
  const [collectionPickerTarget, setCollectionPickerTarget] = useState<{
    runId: string;
    strategyId: string | null;
    strategyName: string;
    symbols: string[];
    template: string;
    assetClass: "equity" | "crypto";
  } | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [isRecentsExpanded, setIsRecentsExpanded] = useState(true);

  const bottomRef = useRef<HTMLDivElement>(null);

  // ── Toast helper ───────────────────────────────────────────────────────────

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  // ── History ────────────────────────────────────────────────────────────────

  /** Imperative refresh — safe to call from event handlers */
  const refreshHistory = () => {
    listHistory(30)
      .then(({ items }) => setHistoryItems(items))
      .catch(() => undefined);
  };

  useEffect(() => {
    const isMock = process.env.NEXT_PUBLIC_MOCK_AUTH === "true";
    listHistory(30)
      .then(({ items }) => {
        if (items.length === 0 && isMock) {
          // Inject high-fidelity mocks for design verification
          setHistoryItems([
            {
              id: "mock-1",
              type: "chat",
              title: "Tesla Mean Reversion",
              subtitle: "today",
              pinned: true,
              created_at: new Date().toISOString(),
            },
            {
              id: "mock-2",
              type: "strategy",
              title: "BTC Halving Play",
              subtitle: "yesterday",
              pinned: false,
              created_at: new Date(Date.now() - 86400000).toISOString(),
            },
            {
              id: "mock-3",
              type: "collection",
              title: "Dividend Aristocrats",
              subtitle: "Apr 20, 2026",
              pinned: false,
              created_at: new Date(Date.now() - 400000000).toISOString(),
            },
          ]);
        } else {
          setHistoryItems(items);
        }
      })
      .catch(() => undefined);
  }, []);

  // ── Init conversation ──────────────────────────────────────────────────────

  useEffect(() => {
    let cancelled = false;
    createConversation()
      .then(({ conversation }) => {
        if (cancelled) return;
        setConversationId(conversation.id);
        setMessages([
          {
            id: "welcome",
            role: "ai",
            kind: "text",
            content: t('chat.welcome'),
            actions: starterActions,
          },
        ]);
      })
      .catch(() => {
        if (cancelled) return;
        setMessages([
          {
            id: "offline",
            role: "ai",
            kind: "text",
            content: t('chat.error_offline'),
          },
        ]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, streamStatus]);

  // ── Load existing conversation ─────────────────────────────────────────────

  const loadConversation = async (convId: string, convTitle: string) => {
    setIsSidebarOpen(false);
    closeChatOptions();
    setCurrentView("chat");
    setConversationId(convId);
    setMessages([]);
    setStreamStatus(t('common.loading'));
    try {
      const { items } = await getConversationMessages(convId, 50);
      const loaded: Message[] = items.map((m) => ({
        id: m.id,
        role: m.role === "user" ? "user" : "ai",
        kind: "text",
        content: m.content,
      }));
      setMessages(
        loaded.length > 0
          ? loaded
          : [
              {
                id: "resume-empty",
                role: "ai",
                kind: "text",
                content: t('chat.resume_prompt', { title: convTitle }),
                actions: starterActions,
              },
            ],
      );
    } catch {
      setMessages([
        {
          id: "resume-error",
          role: "ai",
          kind: "text",
          content: t('chat.error_load'),
        },
      ]);
    } finally {
      setStreamStatus(null);
    }
  };

  // ── Start new chat ─────────────────────────────────────────────────────────

  const startNewChat = async () => {
    const { conversation } = await createConversation();
    setConversationId(conversation.id);
    setCurrentView("chat");
    setMessages([
      {
        id: `welcome-${conversation.id}`,
        role: "ai",
        kind: "text",
        content: t('chat.new_chat_ready'),
        actions: starterActions,
      },
    ]);
    void refreshHistory();
  };

  // ── Send message ───────────────────────────────────────────────────────────

  const handleSend = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || !conversationId) return;

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      kind: "text",
      content: trimmed,
    };
    const assistantId = crypto.randomUUID();

    setMessages((prev) => [
      ...prev.map((m) => ({ ...m, actions: undefined })),
      userMsg,
      { id: assistantId, role: "ai", kind: "text", content: "" },
    ]);
    setStreamStatus(t('chat.status.understanding'));

    try {
      await streamChatMessage(conversationId, trimmed, (event) => {
        if (event.event === "status") {
          setStreamStatus(t(`chat.status.${event.data.status}`) || t('chat.status.preparing'));
        }
        if (event.event === "token") {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, content: `${m.content ?? ""}${event.data.text}` }
                : m,
            ),
          );
        }
        if (event.event === "result") {
          const run = event.data.run as BacktestRun;
          const card = resultCardFromRun(run);
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    kind: "strategy_result",
                    content: undefined,
                    result: card,
                    actions: [
                      {
                        id: "add-to-collection",
                        label: t('common.add_to_collection'),
                        value: `/action:add-to-collection:${run.id}:${run.strategy_id ?? ""}:${run.symbols.join(",")}:${run.asset_class}`,
                      },
                      {
                        id: "try-new",
                        label: t('chat.try_new_strategy'),
                        value: "/action:new-chat",
                      },
                    ],
                  }
                : m,
            ),
          );
        }
        if (event.event === "done") {
          setStreamStatus(null);
          refreshHistory();
        }
      });
    } catch (err: unknown) {
      setStreamStatus(null);
      const status = (err as { status?: number }).status;
      const isRateLimit = status === 429;
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? {
                ...m,
                content: isRateLimit
                  ? t('chat.rate_limit_error')
                  : t('chat.error_backtest'),
              }
            : m,
        ),
      );
    }
  };

  // ── Action routing ─────────────────────────────────────────────────────────

  const handleAction = (value: string) => {
    if (value === "/action:new-chat") {
      void startNewChat();
      return;
    }
    if (value.startsWith("/action:add-to-collection:")) {
      // Format: /action:add-to-collection:<runId>:<strategyId>:<symbols>:<assetClass>
      const parts = value.split(":");
      const runId = parts[2];
      const strategyId = parts[3] || null;
      const symbols = (parts[4] ?? "").split(",").filter(Boolean);
      const assetClass = (parts[5] ?? "equity") as "equity" | "crypto";
      // Find the result card title from messages for strategy name
      const resultMsg = messages.find(
        (m) => m.kind === "strategy_result" && m.result,
      );
      const strategyName = resultMsg?.result?.strategyName ?? "My strategy";
      setCollectionPickerTarget({
        runId,
        strategyId,
        strategyName,
        symbols,
        template: "rsi_mean_reversion",
        assetClass,
      });
      return;
    }
    void handleSend(value);
  };

  // ── Chat options helpers ───────────────────────────────────────────────────

  const closeChatOptions = () => {
    setShowChatOptions(false);
    setActiveChatOptionsPanel("none");
  };

  // ── Recent items grouped by type ───────────────────────────────────────────
  const groupedHistory = useMemo(() => ({
    chat: historyItems.filter((h) => h.type === "chat").slice(0, 10),
    strategy: historyItems.filter((h) => h.type === "strategy").slice(0, 10),
    collection: historyItems.filter((h) => h.type === "collection").slice(0, 10),
  }), [historyItems]);

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="relative flex h-[100dvh] w-full overflow-hidden bg-[#f9f9f9] text-black dark:bg-[#141517] dark:text-white">
      {/* ── Desktop sidebar ── */}
      <aside className="absolute inset-y-0 left-0 z-0 flex w-full flex-col px-6 pb-8 pt-12 md:w-[320px]">
        <div className="mb-10 flex items-center justify-between">
          <h1 className="text-[26px] font-medium tracking-tight">argus</h1>
          <button
            type="button"
            onClick={() => void startNewChat()}
            className="flex h-11 w-11 items-center justify-center rounded-full border border-black/10 transition-colors hover:bg-black/5 dark:border-white/10 dark:hover:bg-white/10"
            aria-label={t('chat.new_chat')}
          >
            <MessageSquarePlus className="h-5 w-5" />
          </button>
        </div>

        <nav className="mb-8 flex flex-col gap-3">
          <button
            type="button"
            onClick={() => { setCurrentView("collections"); setIsSidebarOpen(false); }}
            className="h-12 rounded-full border border-black/10 text-[15px] font-medium transition-colors hover:bg-black/5 dark:border-white/10 dark:hover:bg-white/10"
          >
            {t('common.collections')}
          </button>
          <button
            type="button"
            onClick={() => { setCurrentView("strategies"); setIsSidebarOpen(false); }}
            className="h-12 rounded-full border border-black/10 text-[15px] font-medium transition-colors hover:bg-black/5 dark:border-white/10 dark:hover:bg-white/10"
          >
            {t('common.strategies')}
          </button>
        </nav>

        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
          <button
            type="button"
            onClick={() => setIsRecentsExpanded(!isRecentsExpanded)}
            className="group mb-2 flex items-center justify-between pr-2 text-[13px] font-medium uppercase tracking-wide text-black/45 transition-colors hover:text-black dark:text-white/45 dark:hover:text-white"
          >
            <div className="flex items-center gap-2">
              <History className="h-4 w-4" />
              {t('common.recents')}
            </div>
            <ChevronRight className={`h-4 w-4 transition-transform duration-200 ${isRecentsExpanded ? "rotate-90" : ""}`} />
          </button>

          {isRecentsExpanded && (
            <div className="argus-scrollbar flex flex-1 flex-col gap-0.5 overflow-y-auto pr-2">
              {historyItems.length === 0 ? (
                <p className="px-4 py-3 text-[13px] text-black/35 dark:text-white/35">
                  {t('chat.empty_history')}
                </p>
              ) : (
                historyItems.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className="group rounded-[16px] px-4 py-3 text-left transition-colors hover:bg-black/5 dark:hover:bg-white/5"
                    onClick={() => {
                      if (item.type === "chat") void loadConversation(item.id, item.title);
                      if (item.type === "strategies") setCurrentView("strategies");
                      if (item.type === "collections") setCurrentView("collections");
                    }}
                  >
                    <span className="block truncate text-[15px] font-medium">
                      {item.title}
                    </span>
                    <span className="mt-0.5 block text-[12px] text-black/40 dark:text-white/40">
                      {formatRelativeDate(item.created_at)} · {t(`common.${item.type}`, item.type)}
                    </span>
                  </button>
                ))
              )}
            </div>
          )}
        </div>

        <div className="mt-auto flex items-center gap-4 pt-4">
          <button
            type="button"
            onClick={() => { setCurrentView("settings"); setIsSidebarOpen(false); }}
            className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full border border-black/10 transition-colors hover:bg-black/5 dark:border-white/10 dark:hover:bg-white/5"
            aria-label={t('common.settings')}
          >
            <Settings className="h-5 w-5" />
          </button>
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-5 top-1/2 h-5 w-5 -translate-y-1/2 text-black/40 dark:text-white/40" />
            <input
              type="text"
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              placeholder={t('common.search')}
              className="h-[52px] w-full rounded-full border border-black/10 bg-white/50 pl-12 pr-4 text-[16px] outline-none focus:bg-white focus:ring-2 focus:ring-black/5 dark:border-white/10 dark:bg-[#1f2225]/50 dark:focus:bg-[#1f2225] dark:focus:ring-white/5"
            />
          </div>
        </div>
      </aside>

      {/* ── Main panel ── */}
      <section
        className={`absolute inset-0 z-10 flex h-full w-full flex-col overflow-hidden bg-[#f9f9f9] transition-all duration-500 dark:bg-[#141517] ${
          isSidebarOpen
            ? "translate-x-[75%] scale-[0.93] rounded-[32px] md:translate-x-[320px]"
            : "translate-x-0 scale-100 rounded-none"
        }`}
        onClick={() => { if (isSidebarOpen) setIsSidebarOpen(false); }}
      >
        {/* ── Chat view ── */}
        {currentView === "chat" && (
          <div className="relative mx-auto flex h-[100dvh] w-full max-w-3xl flex-col">
            {/* Header */}
            <header className="absolute inset-x-0 top-0 z-20 flex h-16 items-center justify-between px-4 backdrop-blur-[8px]">
              <button
                type="button"
                onClick={() => setIsSidebarOpen((o) => !o)}
                className="flex h-11 w-11 items-center justify-center rounded-full transition-colors hover:bg-black/5 dark:hover:bg-white/10"
                aria-label="Open menu"
              >
                <Menu className="h-5 w-5" />
              </button>
              <h1 className="text-[16px] font-medium tracking-tight">argus</h1>

              {/* Chat options menu */}
              <div className="relative z-30">
                <button
                  type="button"
                  onClick={() => {
                    if (showChatOptions) { closeChatOptions(); return; }
                    setShowChatOptions(true);
                  }}
                  className="flex h-11 w-11 items-center justify-center rounded-full transition-colors hover:bg-black/5 dark:hover:bg-white/10"
                  aria-label="Chat options"
                >
                  <History className="h-5 w-5" />
                </button>

                {showChatOptions && (
                  <>
                    <button
                      type="button"
                      aria-label="Close chat options"
                      className="fixed inset-0 z-40 cursor-default bg-black/15 md:bg-transparent dark:bg-black/50 md:dark:bg-transparent"
                      onClick={closeChatOptions}
                    />
                    <div className="fixed inset-x-0 bottom-0 z-50 rounded-t-[28px] border-t border-black/5 bg-white pb-7 pt-2 shadow-[0_-8px_30px_rgba(0,0,0,0.12)] dark:border-white/5 dark:bg-[#1f2225] md:absolute md:bottom-auto md:right-0 md:left-auto md:top-full md:mt-1 md:w-[260px] md:rounded-[20px] md:border md:pb-2 md:shadow-xl">
                      <div className="mx-auto my-3 h-1.5 w-12 rounded-full bg-black/10 dark:bg-white/10 md:hidden" />

                      {activeChatOptionsPanel === "none" && (
                        <div>
                          <button
                            type="button"
                            onClick={() => { closeChatOptions(); void startNewChat(); }}
                            className="flex w-full items-center gap-4 px-6 py-4 text-left text-[16px] font-medium transition-colors hover:bg-black/5 dark:hover:bg-white/5 md:px-5 md:py-3 md:text-[15px]"
                          >
                            <Plus className="h-[18px] w-[18px] text-black/60 dark:text-white/60 md:h-4 md:w-4" />
                            {t('chat.new_chat')}
                          </button>
                          <button
                            type="button"
                            onClick={(e) => { e.stopPropagation(); setActiveChatOptionsPanel("history"); }}
                            className="group flex w-full items-center justify-between px-6 py-4 text-left text-[16px] font-medium transition-colors hover:bg-black/5 dark:hover:bg-white/5 md:px-5 md:py-3 md:text-[15px]"
                          >
                            <span className="flex items-center gap-4">
                              <History className="h-[18px] w-[18px] text-black/60 dark:text-white/60 md:h-4 md:w-4" />
                              {t('chat.view_history')}
                            </span>
                            <ChevronRight className="h-5 w-5 text-black/40 transition-transform group-hover:translate-x-0.5 dark:text-white/40 md:h-4 md:w-4" />
                          </button>
                          <div className="my-2 h-px bg-black/5 dark:bg-white/5" />
                          <button
                            type="button"
                            disabled
                            className="flex w-full cursor-not-allowed items-center gap-4 px-6 py-4 text-left text-[16px] font-medium text-black/35 dark:text-white/35 md:px-5 md:py-3 md:text-[15px]"
                          >
                            <Trash2 className="h-[18px] w-[18px] md:h-4 md:w-4" />
                            {t('chat.delete_chat')}
                          </button>
                        </div>
                      )}

                      {activeChatOptionsPanel === "history" && (
                        <div>
                          <button
                            type="button"
                            onClick={() => setActiveChatOptionsPanel("none")}
                            className="flex w-full items-center justify-between px-6 py-3 text-left text-[13px] font-medium uppercase text-black/60 transition-colors hover:text-black dark:text-white/60 dark:hover:text-white md:px-5"
                          >
                            {t('chat.past_sessions')}
                            <ChevronRight className="h-4 w-4 -rotate-90" />
                          </button>
                          {groupedHistory.chat.length === 0 ? (
                            <p className="px-6 py-4 text-[14px] text-black/40 dark:text-white/40 md:px-5">
                              {t('chat.no_past_sessions')}
                            </p>
                          ) : (
                            groupedHistory.chat.map((item) => (
                              <button
                                key={item.id}
                                type="button"
                                onClick={() => { closeChatOptions(); void loadConversation(item.id, item.title); }}
                                className="flex w-full flex-col px-6 py-4 text-left transition-colors hover:bg-black/5 dark:hover:bg-white/5 md:px-5 md:py-3"
                              >
                                <span className="truncate text-[15px] font-medium">
                                  {item.title}
                                </span>
                                <span className="mt-1 truncate text-[13px] text-black/45 dark:text-white/45 capitalize">
                                  {item.subtitle}
                                </span>
                              </button>
                            ))
                          )}
                        </div>
                      )}
                    </div>
                  </>
                )}
              </div>
            </header>

            {/* Messages */}
            <div className="argus-scrollbar flex-1 overflow-y-auto px-4 pb-[126px] pt-[86px]">
              <div className="space-y-8">
                {messages.map((msg) => (
                  <ChatMessage key={msg.id} message={msg} onAction={handleAction} />
                ))}
                {streamStatus && (
                  <div className="ml-12 text-[13px] text-black/45 dark:text-white/45">
                    {streamStatus}
                  </div>
                )}
                <div ref={bottomRef} />
              </div>
            </div>

            {/* Input fade + bar */}
            <div className="pointer-events-none absolute bottom-0 inset-x-0 z-10 h-40 bg-[#f9f9f9]/80 backdrop-blur-[0.8px] [mask-image:linear-gradient(to_top,black_50%,transparent_100%)] dark:bg-[#141517]/80" />
            <div className="pointer-events-none absolute bottom-6 inset-x-0 z-20 px-4">
              <div className="pointer-events-auto mx-auto max-w-3xl rounded-full">
                <ChatInput onSend={handleSend} />
              </div>
            </div>
          </div>
        )}

        {currentView === "strategies" && (
          <StrategiesView
            onMenuClick={() => setIsSidebarOpen((o) => !o)}
            onSettingsClick={() => setCurrentView("settings")}
          />
        )}
        {currentView === "collections" && (
          <CollectionsView
            onMenuClick={() => setIsSidebarOpen((o) => !o)}
            onSettingsClick={() => setCurrentView("settings")}
          />
        )}
        {currentView === "settings" && (
          <SettingsView
            onClose={() => setCurrentView("chat")}
            onLogout={() => { window.location.href = "/"; }}
          />
        )}
      </section>

      {/* ── Collection picker sheet ── */}
      {collectionPickerTarget && (
        <CollectionPicker
          strategyId={collectionPickerTarget.strategyId}
          strategyFallback={{
            name: collectionPickerTarget.strategyName,
            template: collectionPickerTarget.template,
            asset_class: collectionPickerTarget.assetClass,
            symbols: collectionPickerTarget.symbols,
          }}
          onClose={() => setCollectionPickerTarget(null)}
          onSuccess={(collectionName) => {
            setCollectionPickerTarget(null);
            showToast(t('chat.added_to_collection', { name: collectionName }));
          }}
        />
      )}

      {/* ── Toast ── */}
      {toast && (
        <div className="fixed bottom-24 left-1/2 z-[100] -translate-x-1/2 animate-in fade-in slide-in-from-bottom-2 duration-300 rounded-full bg-black dark:bg-white px-5 py-2.5 text-[14px] font-medium text-white dark:text-black shadow-xl">
          {toast}
        </div>
      )}
    </div>
  );
}
