"use client";

import { useMemo, useEffect, useRef, useState } from "react";
import {
  Archive,
  ChevronRight,
  History,
  PanelLeft,
  MessageSquarePlus,
  MoreHorizontal,
  Plus,
  Search,
  Settings,
  Trash2,
  TrendingUp,
  Bitcoin,
  LineChart,
  Layers,
  Compass,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { ArgusLogo } from "@/components/ArgusLogo";

import {
  createConversation,
  deleteCollection,
  deleteConversation,
  deleteStrategy,
  formatRelativeDate,
  getConversationMessages,
  listHistory,
  patchCollection,
  patchConversation,
  patchStrategy,
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
import FeedbackDialog from "../feedback/FeedbackDialog";
import { type ChatActionOption, type Message } from "./types";

// ─── Constants ────────────────────────────────────────────────────────────────

type View = "chat" | "strategies" | "collections" | "settings";

// ─── Component ────────────────────────────────────────────────────────────────

export default function ChatInterface() {
  const { t, i18n } = useTranslation();

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
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [showChatOptions, setShowChatOptions] = useState(false);
  const [activeChatOptionsPanel, setActiveChatOptionsPanel] = useState<
    "none" | "history" | "collection"
  >("none");
  const [searchText, setSearchText] = useState("");
  const [streamStatus, setStreamStatus] = useState<string | null>(null);
  const [historyItems, setHistoryItems] = useState<HistoryItem[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
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
  const [activeMenuId, setActiveMenuId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [feedbackState, setFeedbackState] = useState<{
    isOpen: boolean;
    type: "bug" | "feature" | "general" | "rating";
    rating?: "positive" | "negative";
    context?: Record<string, any>;
  }>({ isOpen: false, type: "general" });

  const bottomRef = useRef<HTMLDivElement>(null);
  const chatOptionsRef = useRef<HTMLDivElement>(null);

  // ── Toast helper ───────────────────────────────────────────────────────────

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  // ── History ────────────────────────────────────────────────────────────────

  /** Imperative refresh — safe to call from event handlers */
  const refreshHistory = () => {
    listHistory({ limit: 30 })
      .then(({ items }) => {
        const filtered = items.filter(
          (item) => !(item.type === "chat" && item.subtitle === "No messages yet")
        );
        setHistoryItems(filtered);
      })
      .catch(() => undefined);
  };

  useEffect(() => {
    const isMock = process.env.NEXT_PUBLIC_MOCK_AUTH === "true";
    listHistory({ limit: 30 })
      .then(({ items }) => {
        const filtered = items.filter(
          (item) => !(item.type === "chat" && item.subtitle === "No messages yet")
        );
        setHistoryItems(filtered);
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!isSidebarOpen) {
      setIsRecentsExpanded(false);
    }
  }, [isSidebarOpen]);

  // ── Init conversation ──────────────────────────────────────────────────────

  useEffect(() => {
    let cancelled = false;
    createConversation()
      .then(({ conversation }) => {
        if (cancelled) return;
        setConversationId(conversation.id);
        setMessages([]);
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
      setMessages(loaded);
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
    try {
      const { conversation } = await createConversation();
      setConversationId(conversation.id);
      setIsSidebarOpen(false);
      setCurrentView("chat");
      setMessages([]);
      void refreshHistory();
      return conversation.id;
    } catch (err) {
      console.error("Failed to start new chat:", err);
      return null;
    }
  };

  const handleTriggerPrompt = async (type: 'strategy' | 'collection', customPrompt?: string) => {
    // 1. Switch view
    setCurrentView("chat");
    setIsSidebarOpen(false);
    
    // 2. Start new chat
    const newConvId = await startNewChat();
    if (!newConvId) return;
    
    // 3. Define the localized prompt or use custom
    let prompt: string;
    if (customPrompt) {
      prompt = customPrompt;
    } else {
      const promptKey = type === 'strategy' 
        ? 'chat.trigger_create_strategy' 
        : 'chat.trigger_create_collection';
      
      const fallback = type === 'strategy'
        ? 'I want to create a new strategy.'
        : 'I want to create a new collection.';
      
      prompt = t(promptKey, fallback);
    }
      
    // 4. Send it
    void handleSend(prompt);
  };

  // ── Send message ───────────────────────────────────────────────────────────

  const handleSend = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || !conversationId) return;

    setIsSidebarOpen(false); // SOTA: Collapse sidebar to enter focus mode on message send

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
        if (event.event === "title") {
          setHistoryItems((prev) =>
            prev.map((item) =>
              item.id === event.data.conversation_id
                ? { ...item, title: event.data.title }
                : item
            )
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

  const handleRename = async (id: string, newTitle: string, type: string) => {
    try {
      if (type === 'chat') await patchConversation(id, { title: newTitle });
      else if (type === 'strategies') await patchStrategy(id, { name: newTitle });
      else if (type === 'collections') await patchCollection(id, { name: newTitle });
      
      setHistoryItems((prev) =>
        prev.map((item) => (item.id === id ? { ...item, title: newTitle } : item)),
      );
      setEditingId(null);
    } catch (err) {
      console.error("Failed to rename:", err);
      showToast(t('chat.error_generic'));
    }
  };

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

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (chatOptionsRef.current && !chatOptionsRef.current.contains(event.target as Node)) {
        closeChatOptions();
      }
    }
    if (showChatOptions) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [showChatOptions]);

  const handleArchiveChat = async () => {
    if (!conversationId) return;
    try {
      await patchConversation(conversationId, { archived: true });
      showToast(t("common.archived"));
      closeChatOptions();
      void startNewChat();
    } catch {
      showToast(t("common.error_occurred"));
    }
  };

  const handleAddToCollection = () => {
    // Find the latest strategy result in the message list
    const lastStrategyMsg = [...messages].reverse().find(m => m.kind === "strategy_result" && m.result);
    if (lastStrategyMsg?.result) {
      const res = lastStrategyMsg.result;
      setCollectionPickerTarget({
        runId: res.runId,
        strategyId: res.strategyId,
        strategyName: res.strategyName,
        symbols: [], 
        template: "", 
        assetClass: "equity", 
      });
      closeChatOptions();
    } else {
      showToast(t('chat.error_load'));
    }
  };

  // ── Recent items grouped by type ───────────────────────────────────────────
  const groupedHistory = useMemo(() => ({
    chat: historyItems.filter((h) => h.type === "chat").slice(0, 10),
    strategy: historyItems.filter((h) => h.type === "strategy").slice(0, 10),
    collection: historyItems.filter((h) => h.type === "collection").slice(0, 10),
  }), [historyItems]);

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="relative flex h-[100dvh] w-full overflow-hidden bg-[#f9f9f9] text-black dark:bg-[#141517] dark:text-white md:flex-row">

      {/* ── Desktop sidebar ── */}
      <aside 
        className={`flex flex-col border-r border-black/5 bg-white transition-all duration-300 ease-in-out overflow-x-hidden dark:border-white/5 dark:bg-[#141517] ${
          isSidebarOpen ? "w-72" : "w-14"
        }`}
      >
        {/* Sidebar Header: Brand & Toggle */}
        <div className="flex h-20 items-center px-[6px] pb-4 pt-6 overflow-hidden">
          <button
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-full transition-all duration-300 hover:bg-black/5 dark:hover:bg-white/5 active:scale-95"
            aria-label={isSidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
          >
            {isSidebarOpen ? (
              <PanelLeft className="h-5 w-5 text-black/60 dark:text-white/60" />
            ) : (
              <ArgusLogo variant="icon-only" className="h-8 w-8 text-black dark:text-white" />
            )}
          </button>
          <span className={`font-display pl-3 text-[22px] font-bold tracking-tight text-black transition-all duration-300 dark:text-white ${
            isSidebarOpen ? "opacity-100" : "absolute left-[72px] opacity-0 pointer-events-none"
          }`}>
            argus
          </span>
        </div>

        <div className="flex flex-1 flex-col overflow-y-auto overflow-x-hidden px-[6px] pb-4 pt-2">
          {/* Main Navigation */}
          <button
            onClick={() => {
              void startNewChat();
              setIsSidebarOpen(false);
            }}
            className="group mb-2 flex h-11 w-full items-center gap-3 rounded-[14px] px-0 transition-all duration-200 hover:bg-black/5 dark:hover:bg-white/5"
          >
            <div className="flex h-11 w-11 items-center justify-center">
              <Plus className="h-5 w-5 text-black/60 transition-colors group-hover:text-black dark:text-white/60 dark:group-hover:text-white" />
            </div>
            <span className={`font-display pl-3 text-[15px] font-medium tracking-tight transition-all duration-300 ${
              isSidebarOpen ? "opacity-100" : "absolute left-[72px] opacity-0 pointer-events-none"
            }`}>
              {t('chat.new_chat')}
            </span>
          </button>

          <button
            onClick={() => {
              setCurrentView("strategies");
              setIsSidebarOpen(false);
            }}
            className={`group mb-2 flex h-11 w-full items-center gap-3 rounded-[14px] px-0 transition-all duration-200 ${
              currentView === "strategies" ? "bg-black/5 dark:bg-white/5" : "hover:bg-black/5 dark:hover:bg-white/5"
            }`}
          >
            <div className="flex h-11 w-11 items-center justify-center">
              <Compass className="h-[22px] w-[22px] text-black/60 transition-colors group-hover:text-black dark:text-white/60 dark:group-hover:text-white" />
            </div>
            <span className={`font-display pl-3 text-[15px] font-medium tracking-tight transition-all duration-300 ${
              isSidebarOpen ? "opacity-100" : "absolute left-[72px] opacity-0 pointer-events-none"
            }`}>
              {t('common.strategies')}
            </span>
          </button>

          <button
            onClick={() => {
              setCurrentView("collections");
              setIsSidebarOpen(false);
            }}
            className={`group mb-6 flex h-11 w-full items-center gap-3 rounded-[14px] px-0 transition-all duration-200 ${
              currentView === "collections" ? "bg-black/5 dark:bg-white/5" : "hover:bg-black/5 dark:hover:bg-white/5"
            }`}
          >
            <div className="flex h-11 w-11 items-center justify-center">
              <Layers className="h-[22px] w-[22px] text-black/60 transition-colors group-hover:text-black dark:text-white/60 dark:group-hover:text-white" />
            </div>
            <span className={`font-display pl-3 text-[15px] font-medium tracking-tight transition-all duration-300 ${
              isSidebarOpen ? "opacity-100" : "absolute left-[72px] opacity-0 pointer-events-none"
            }`}>
              {t('common.collections')}
            </span>
          </button>

          {/* History Accordion */}
          <div className="mb-2">
            <button
              onClick={() => setIsRecentsExpanded(!isRecentsExpanded)}
              className="flex h-11 w-full items-center justify-between rounded-[14px] px-0 transition-all duration-200 hover:bg-black/5 dark:hover:bg-white/5"
            >
              <div className="flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center">
                  <History className="h-[22px] w-[22px] text-black/60 dark:text-white/60" />
                </div>
                <span className={`font-display pl-3 tracking-tight transition-all duration-300 ${
                  isSidebarOpen ? "opacity-100" : "absolute left-[72px] opacity-0 pointer-events-none"
                }`}>
                  {t('common.recents')}
                </span>
              </div>
              <div className={`pr-4 transition-opacity duration-300 ${
                isSidebarOpen ? "block opacity-100" : "hidden opacity-0 pointer-events-none"
              }`}>
                <ChevronRight className={`h-4 w-4 transition-transform duration-200 ${isRecentsExpanded ? "rotate-90" : ""}`} />
              </div>
            </button>

            {isRecentsExpanded && (
              <div className="space-y-0.5 pb-2">
                {historyItems.length === 0 ? (
                  <div className="px-11 py-6">
                    <p className={`text-[13px] leading-relaxed text-black/30 transition-all duration-300 dark:text-white/30 ${
                      isSidebarOpen ? "opacity-100" : "absolute left-[72px] opacity-0 pointer-events-none"
                    }`}>
                      {t('chat.no_recent_activity')}
                    </p>
                  </div>
                ) : (
                  historyItems.map((item) => (
                    <button
                      key={item.id}
                      onClick={() => {
                        setConversationId(item.id);
                        getConversationMessages(item.id).then(({ items }) => {
                          setMessages(
                            items.reverse().map((m) => ({
                              id: m.id,
                              role: m.role === "user" ? "user" : "ai",
                              content: m.content,
                              kind: m.content.includes("result") ? "strategy_result" : "text",
                            }))
                          );
                        });
                      }}
                      className={`group relative flex w-full items-center gap-3 rounded-[14px] px-0 py-2.5 transition-all duration-200 ${
                        conversationId === item.id ? "bg-black/5 dark:bg-white/5" : "hover:bg-black/5 dark:hover:bg-white/5"
                      }`}
                    >
                      <div className="flex h-6 w-11 flex-shrink-0 items-center justify-center" />
                      <div className={`min-w-0 flex-1 pl-3 pr-4 transition-all duration-300 ${
                        isSidebarOpen ? "opacity-100" : "absolute left-[72px] opacity-0 pointer-events-none"
                      }`}>
                        <span className="font-display block truncate text-[15px] font-medium tracking-tight">
                          {item.title}
                        </span>
                        <span className="mt-0.5 block text-[12px] text-black/40 dark:text-white/40">
                          {formatRelativeDate(
                            item.created_at,
                            { today: t('common.today'), yesterday: t('common.yesterday') },
                            i18n.language
                          )} · {t(`common.${item.type}`, item.type)}
                        </span>
                      </div>
                    </button>
                  ))
                )}
              </div>
            )}
          </div>
        </div>

        {/* Search & Settings */}
        <div className="border-t border-black/5 p-[6px] dark:border-white/5">
          <div className="relative mb-4 h-11 overflow-hidden">
            <div className="absolute left-0 top-0 flex h-11 w-11 items-center justify-center">
              <Search className="h-4 w-4 text-black/30 dark:text-white/30" />
            </div>
            <input
              type="text"
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              placeholder={t('common.search')}
              className={`font-display h-11 w-full rounded-[14px] bg-black/[0.03] pl-[62px] pr-4 text-[15px] font-medium outline-none transition-all placeholder:text-black/30 hover:bg-black/[0.05] focus:bg-white focus:ring-1 focus:ring-black/5 dark:bg-white/[0.03] dark:placeholder:text-white/30 dark:hover:bg-white/[0.05] dark:focus:bg-[#1f2225] dark:focus:ring-white/5 ${
                isSidebarOpen ? "block" : "hidden"
              }`}
            />
          </div>

          <button
            onClick={() => {
              setCurrentView("settings");
            }}
            className={`group flex h-11 w-full items-center gap-3 rounded-[14px] px-0 transition-all duration-200 ${
              currentView === "settings" ? "bg-black/5 dark:bg-white/5" : "hover:bg-black/5 dark:hover:bg-white/5"
            }`}
          >
            <div className="flex h-11 w-11 items-center justify-center">
              <Settings className="h-5 w-5 text-black/60 transition-colors group-hover:text-black dark:text-white/60 dark:group-hover:text-white" />
            </div>
            <span className={`font-display pl-3 text-[15px] font-medium tracking-tight transition-all duration-300 ${
              isSidebarOpen ? "opacity-100" : "absolute left-[72px] opacity-0 pointer-events-none"
            }`}>
              {t('common.settings')}
            </span>
          </button>
        </div>
      </aside>

      {/* ── Main panel ── */}
      <section
        className="relative z-10 flex h-full flex-1 flex-col overflow-hidden bg-[#f9f9f9] dark:bg-[#141517]"
      >
        {/* ── Unified View Header (SOTA: Absolute to content panel for perfect centering) ── */}
        {currentView !== "settings" && (
          <header className="absolute inset-x-0 top-0 z-[50] flex h-20 items-center justify-between px-4 pointer-events-none md:px-8">
          {/* Empty space for sidebar toggle alignment balance */}
          <div className="w-11 md:w-32" />

          {/* Title (Always Centered relative to Content) */}
          <h1 className="pointer-events-auto text-[17px] font-semibold tracking-tight text-black/80 dark:text-white/80 md:text-[18px]">
            {currentView === "chat" && (messages.length > 0 ? "Conversation" : t('chat.new_chat'))}
            {currentView === "strategies" && t('common.strategies')}
            {currentView === "collections" && t('common.collections')}
          </h1>

          {/* Action Button (Always Right-Anchored) */}
          <div className="flex w-11 justify-end pointer-events-auto md:w-32">
            {currentView === "chat" && (
              <div className="relative" ref={chatOptionsRef}>
                <button
                  type="button"
                  onClick={() => setShowChatOptions(!showChatOptions)}
                  className="flex h-11 w-11 items-center justify-center rounded-full transition-all duration-200 hover:bg-black/5 dark:hover:bg-white/5 active:scale-95"
                  aria-label="Chat options"
                >
                  <History className="h-5 w-5" />
                </button>
                {showChatOptions && (
                  <div className="fixed inset-x-0 bottom-0 z-50 rounded-t-[28px] border-t border-black/5 bg-white pb-7 pt-2 shadow-[0_-8px_30px_rgba(0,0,0,0.12)] dark:border-white/5 dark:bg-[#1f2225] md:absolute md:bottom-auto md:right-0 md:left-auto md:top-full md:mt-2 md:w-[260px] md:rounded-[20px] md:border md:pb-2 md:shadow-xl">
                    <div className="mx-auto my-3 h-1.5 w-12 rounded-full bg-black/10 dark:bg-white/10 md:hidden" />
                    {activeChatOptionsPanel === "none" && (
                      <div className="py-1">
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
                          onClick={handleAddToCollection}
                          className="flex w-full items-center gap-4 px-6 py-4 text-left text-[16px] font-medium transition-colors hover:bg-black/5 dark:hover:bg-white/5 md:px-5 md:py-3 md:text-[15px]"
                        >
                          <Layers className="h-[18px] w-[18px] text-black/60 dark:text-white/60 md:h-4 md:w-4" />
                          {t('common.add_to_collection')}
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
                          <ChevronRight className="h-4 w-4 text-black/30 dark:text-white/30 transition-transform group-hover:translate-x-0.5" />
                        </button>
                        <div className="my-1 h-px bg-black/5 dark:bg-white/5" />
                        <button
                          type="button"
                          onClick={() => {
                            if (!conversationId) return;
                            deleteConversation(conversationId)
                              .then(() => {
                                showToast(t('common.delete'));
                                refreshHistory();
                                void startNewChat();
                                closeChatOptions();
                              })
                              .catch(() => showToast(t('common.error_occurred')));
                          }}
                          className="flex w-full items-center gap-4 px-6 py-4 text-left text-[16px] font-medium text-red-500 transition-colors hover:bg-red-50 dark:hover:bg-red-500/10 md:px-5 md:py-3 md:text-[15px]"
                        >
                          <Trash2 className="h-[18px] w-[18px] md:h-4 md:w-4" />
                          {t('chat.delete_chat')}
                        </button>
                      </div>
                    )}
                    {activeChatOptionsPanel === "history" && (
                      <div className="py-1">
                        <button
                          type="button"
                          onClick={() => setActiveChatOptionsPanel("none")}
                          className="flex w-full items-center justify-between px-6 py-3 text-left text-[13px] font-medium text-black/60 transition-colors hover:text-black dark:text-white/60 dark:hover:text-white md:px-5"
                        >
                          {t('chat.past_sessions')}
                          <ChevronRight className="h-4 w-4 -rotate-90" />
                        </button>
                        <div className="max-h-[300px] overflow-y-auto pb-1">
                          {groupedHistory.chat.map((item) => (
                            <button
                              key={item.id}
                              type="button"
                              onClick={() => {
                                setConversationId(item.id);
                                getConversationMessages(item.id).then(({ items }) => {
                                  setMessages(
                                    items.reverse().map((m) => ({
                                      id: m.id,
                                      role: m.role === "user" ? "user" : "ai",
                                      content: m.content,
                                      kind: m.content.includes("result") ? "strategy_result" : "text",
                                    }))
                                  );
                                });
                                closeChatOptions();
                              }}
                              className="flex w-full flex-col px-6 py-4 text-left transition-colors hover:bg-black/5 dark:hover:bg-white/5 md:px-5 md:py-3"
                            >
                              <span className="truncate text-[15px] font-medium">{item.title}</span>
                              <span className="mt-1 truncate text-[13px] text-black/45 dark:text-white/45">{item.subtitle}</span>
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
            {(currentView === "strategies" || currentView === "collections") && (
              <button
                onClick={() => handleTriggerPrompt(currentView === "strategies" ? "strategy" : "collection")}
                className="flex h-11 w-11 items-center justify-center rounded-full transition-all duration-200 hover:bg-black/5 dark:hover:bg-white/5 active:scale-95"
                aria-label="New item"
              >
                <Plus className="h-5 w-5" />
              </button>
            )}
          </div>
          </header>
        )}
        {/* ── Chat view ── */}
        {currentView === "chat" && (
          <div className="relative mx-auto flex h-[100dvh] w-full max-w-5xl flex-col">

            {messages.length === 0 ? (
              <div className="flex h-full flex-col items-center justify-start px-4 pt-[35vh]">
                <h1 className="mb-8 text-[40px] font-medium tracking-tight text-black dark:text-white">
                  argus
                </h1>
                
                <div className="w-full max-w-2xl">
                  <ChatInput onSend={handleSend} />
                </div>

                {/* Show/Hide Suggestions Toggle */}
                <div className="mt-4">
                  <button
                    onClick={() => setShowSuggestions(!showSuggestions)}
                    className="text-[14px] font-medium text-black/60 transition-colors hover:text-black dark:text-white/60 dark:hover:text-white"
                  >
                    {showSuggestions ? t('chat.hide_suggestions') : t('chat.show_suggestions')}
                  </button>
                </div>

                <div className={`mt-6 w-full flex flex-col items-center transition-all duration-500 ease-in-out overflow-hidden ${
                  showSuggestions ? 'max-h-[600px] opacity-100' : 'max-h-0 opacity-0 pointer-events-none'
                }`}>
                  {/* Starter Actions / Chips */}
                  <div className="flex flex-wrap items-center justify-center gap-3">
                      <button 
                        onClick={() => handleSend(t('chat.starter_actions.tsla.value', 'Show me TSLA analysis'))} 
                        className="flex items-center gap-2 rounded-full border border-black/10 bg-white/50 px-4 py-2 text-[14px] font-medium text-black transition-colors hover:bg-black/5 dark:border-white/10 dark:bg-[#1f2225]/50 dark:text-white dark:hover:bg-white/5"
                      >
                        <TrendingUp className="h-4 w-4 text-black/60 dark:text-white/60" />
                        TSLA Analysis
                      </button>
                      <button 
                        onClick={() => handleSend(t('chat.starter_actions.btc.value', 'Show me BTC trends'))} 
                        className="flex items-center gap-2 rounded-full border border-black/10 bg-white/50 px-4 py-2 text-[14px] font-medium text-black transition-colors hover:bg-black/5 dark:border-white/10 dark:bg-[#1f2225]/50 dark:text-white dark:hover:bg-white/5"
                      >
                        <Bitcoin className="h-4 w-4 text-black/60 dark:text-white/60" />
                        BTC Trends
                      </button>
                      <button 
                        onClick={() => handleSend(t('chat.starter_actions.dca.value', 'Explain DCA strategy'))} 
                        className="flex items-center gap-2 rounded-full border border-black/10 bg-white/50 px-4 py-2 text-[14px] font-medium text-black transition-colors hover:bg-black/5 dark:border-white/10 dark:bg-[#1f2225]/50 dark:text-white dark:hover:bg-white/5"
                      >
                        <LineChart className="h-4 w-4 text-black/60 dark:text-white/60" />
                        DCA Strategy
                      </button>
                    </div>

                    {/* Example Questions */}
                    <div className="mt-12 flex flex-col items-center gap-4 text-center">
                      <button onClick={() => handleSend(t('chat.example_queries.q1', 'What if I bought Apple whenever it dipped hard?'))} className="text-[14px] text-black/50 hover:text-black hover:underline dark:text-white/50 dark:hover:text-white transition-colors">
                        {t('chat.example_queries.q1', 'What if I bought Apple whenever it dipped hard?')}
                      </button>
                      <button onClick={() => handleSend(t('chat.example_queries.q2', 'Test a momentum breakout strategy on Bitcoin.'))} className="text-[14px] text-black/50 hover:text-black hover:underline dark:text-white/50 dark:hover:text-white transition-colors">
                        {t('chat.example_queries.q2', 'Test a momentum breakout strategy on Bitcoin.')}
                      </button>
                      <button onClick={() => handleSend(t('chat.example_queries.q3', 'How would a simple DCA strategy perform on Tesla?'))} className="text-[14px] text-black/50 hover:text-black hover:underline dark:text-white/50 dark:hover:text-white transition-colors">
                        {t('chat.example_queries.q3', 'How would a simple DCA strategy perform on Tesla?')}
                      </button>
                    </div>
                  </div>
                </div>
            ) : (
              <>
                {/* Messages */}
                <div className="argus-scrollbar flex-1 overflow-y-auto px-4 pb-[126px] pt-[86px]">
                  <div className="space-y-8">
                    {messages.map((msg) => (
                      <ChatMessage
                        key={msg.id}
                        message={msg}
                        onAction={handleAction}
                        onFeedback={(type, context, rating) => {
                          setFeedbackState({ isOpen: true, type, context, rating });
                          setIsSidebarOpen(false);
                        }}
                        isLatest={msg.role === 'ai' && messages.findLastIndex(m => m.role === 'ai') === messages.indexOf(msg)}
                      />
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
              </>
            )}
          </div>
        )}

        {currentView === "strategies" && (
          <StrategiesView
            onMenuClick={() => setIsSidebarOpen((o) => !o)}
            onAddClick={() => handleTriggerPrompt('strategy')}
            searchText={searchText}
            onSearchChange={setSearchText}
            isSidebarOpen={isSidebarOpen}
            onTriggerPrompt={handleTriggerPrompt}
          />
        )}
        {currentView === "collections" && (
          <CollectionsView
            onMenuClick={() => setIsSidebarOpen((o) => !o)}
            onAddClick={() => handleTriggerPrompt('collection')}
            searchText={searchText}
            onSearchChange={setSearchText}
            isSidebarOpen={isSidebarOpen}
            onTriggerPrompt={handleTriggerPrompt}
          />
        )}
        {currentView === "settings" && (
          <SettingsView
            onClose={() => setCurrentView("chat")}
            onLogout={() => {
              window.location.href = "/";
            }}
            onFeedback={(type, context) => {
              setFeedbackState({ isOpen: true, type, context });
              setIsSidebarOpen(false);
            }}
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

      {/* ── Feedback Dialog ── */}
      <FeedbackDialog
        isOpen={feedbackState.isOpen}
        onClose={() => setFeedbackState((s) => ({ ...s, isOpen: false }))}
        type={feedbackState.type}
        rating={feedbackState.rating}
        context={feedbackState.context}
      />

      {/* ── Toast ── */}
      {toast && (
        <div className="fixed bottom-24 left-1/2 z-[100] -translate-x-1/2 animate-in fade-in slide-in-from-bottom-2 duration-300 rounded-full bg-black dark:bg-white px-5 py-2.5 text-[14px] font-medium text-white dark:text-black shadow-xl">
          {toast}
        </div>
      )}
    </div>
  );
}
