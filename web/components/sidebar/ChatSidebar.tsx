"use client";

import { useMemo } from "react";
import {
  ChevronRight,
  Compass,
  History,
  Layers,
  PanelLeft,
  Plus,
  Search,
  Settings,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { ArgusLogo } from "@/components/ArgusLogo";

import type { HistoryItem, SearchItem } from "@/lib/argus-api";

// ─── Types ────────────────────────────────────────────────────────────────────

type View = "chat" | "strategies" | "collections" | "settings";

export type ChatSidebarProps = {
  /** Whether the sidebar is expanded or collapsed */
  isOpen: boolean;
  onToggle: () => void;

  /** Currently active view */
  currentView: View;

  /** Currently active conversation id (used for highlighting) */
  conversationId: string | null;

  /** Whether the collections feature flag is enabled */
  collectionsEnabled: boolean;

  // ── Recents ──────────────────────────────────────────────────────────────
  /** Whether the Recents accordion is expanded */
  isRecentsExpanded: boolean;
  onToggleRecents: () => void;
  /** Grouped history items for the Recents list */
  historyItems: HistoryItem[];
  /** Whether more history pages are available */
  historyNextCursor: string | null;
  /** Whether a history page load is in progress */
  isLoadingMoreHistory: boolean;

  // ── Search (inline, will be replaced by overlay later) ───────────────────
  searchText: string;
  onSearchChange: (text: string) => void;
  searchResults: SearchItem[];
  searchNextCursor: string | null;
  isSearching: boolean;
  isLoadingMoreSearch: boolean;

  // ── Callbacks ────────────────────────────────────────────────────────────
  onNewChat: () => void;
  onNavigate: (view: View) => void;
  onOpenItem: (item: HistoryItem | SearchItem) => void;
  onLoadMoreHistory: () => void;
  onLoadMoreSearch: () => void;
  onOpenSettings: () => void;
};

// ─── Component ────────────────────────────────────────────────────────────────

export default function ChatSidebar({
  isOpen,
  onToggle,
  currentView,
  conversationId,
  collectionsEnabled,
  isRecentsExpanded,
  onToggleRecents,
  historyItems,
  historyNextCursor,
  isLoadingMoreHistory,
  searchText,
  onSearchChange,
  searchResults,
  searchNextCursor,
  isSearching,
  isLoadingMoreSearch,
  onNewChat,
  onNavigate,
  onOpenItem,
  onLoadMoreHistory,
  onLoadMoreSearch,
  onOpenSettings,
}: ChatSidebarProps) {
  const { t } = useTranslation();

  // ── Recents grouped by time period ─────────────────────────────────────────
  const groupedHistory = useMemo(() => {
    const groups: { label: string; items: HistoryItem[] }[] = [];
    const today: HistoryItem[] = [];
    const yesterday: HistoryItem[] = [];
    const last7Days: HistoryItem[] = [];
    const earlier: HistoryItem[] = [];

    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const yesterdayStart = todayStart - 86400000;
    const last7DaysStart = todayStart - 86400000 * 6;

    historyItems.forEach((item) => {
      const d = new Date(item.created_at).getTime();
      if (d >= todayStart) {
        today.push(item);
      } else if (d >= yesterdayStart) {
        yesterday.push(item);
      } else if (d >= last7DaysStart) {
        last7Days.push(item);
      } else {
        earlier.push(item);
      }
    });

    if (today.length > 0) groups.push({ label: t("chat.history.today"), items: today });
    if (yesterday.length > 0) groups.push({ label: t("chat.history.yesterday"), items: yesterday });
    if (last7Days.length > 0) groups.push({ label: t("chat.history.last_7_days"), items: last7Days });
    if (earlier.length > 0) groups.push({ label: t("chat.history.earlier"), items: earlier });

    return groups;
  }, [historyItems, t]);

  return (
    <aside
      className={`flex flex-col border-r border-black/5 bg-white transition-all duration-300 ease-in-out overflow-x-hidden dark:border-white/5 dark:bg-[#141517] ${ isOpen ? "w-72" : "w-14" }`}
    >
      {/* Sidebar Header: Brand & Toggle */}
      <div className="flex h-20 items-center px-[6px] pb-4 pt-6 overflow-hidden">
        <button
          onClick={onToggle}
          className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-full transition-all duration-300 hover:bg-black/5 dark:hover:bg-white/5 active:scale-95"
          aria-label={isOpen ? "Collapse sidebar" : "Expand sidebar"}
        >
          {isOpen ? (
            <PanelLeft className="h-5 w-5 text-black/60 dark:text-white/60" />
          ) : (
            <ArgusLogo className="h-8 w-8 text-black dark:text-white" />
          )}
        </button>
        <span className={`font-display pl-3 text-[22px] font-bold tracking-tight text-black transition-all duration-300 dark:text-white ${ isOpen ? "opacity-100" : "absolute left-[72px] opacity-0 pointer-events-none" }`}>
          argus
        </span>
      </div>

      <div className="flex flex-1 flex-col overflow-y-auto overflow-x-hidden px-[6px] pb-4 pt-2">
        {/* Main Navigation */}
        <button
          onClick={onNewChat}
          className="group mb-2 flex h-11 w-full items-center gap-3 rounded-[14px] px-0 transition-all duration-200 hover:bg-black/5 dark:hover:bg-white/5"
        >
          <div className="flex h-11 w-11 items-center justify-center">
            <Plus className="h-5 w-5 text-black/60 transition-colors group-hover:text-black dark:text-white/60 dark:group-hover:text-white" />
          </div>
          <span className={`font-display pl-3 text-[15px] font-medium tracking-tight transition-all duration-300 ${ isOpen ? "opacity-100" : "absolute left-[72px] opacity-0 pointer-events-none" }`}>
            {t('chat.new_chat')}
          </span>
        </button>

        <button
          onClick={() => onNavigate("strategies")}
          className={`group mb-2 flex h-11 w-full items-center gap-3 rounded-[14px] px-0 transition-all duration-200 ${ currentView === "strategies" ? "bg-black/5 dark:bg-white/5" : "hover:bg-black/5 dark:hover:bg-white/5" }`}
        >
          <div className="flex h-11 w-11 items-center justify-center">
            <Compass className="h-[22px] w-[22px] text-black/60 transition-colors group-hover:text-black dark:text-white/60 dark:group-hover:text-white" />
          </div>
          <span className={`font-display pl-3 text-[15px] font-medium tracking-tight transition-all duration-300 ${ isOpen ? "opacity-100" : "absolute left-[72px] opacity-0 pointer-events-none" }`}>
            {t('common.strategies')}
          </span>
        </button>

        {collectionsEnabled && (
          <button
            onClick={() => onNavigate("collections")}
            className={`group mb-6 flex h-11 w-full items-center gap-3 rounded-[14px] px-0 transition-all duration-200 ${ currentView === "collections" ? "bg-black/5 dark:bg-white/5" : "hover:bg-black/5 dark:hover:bg-white/5" }`}
          >
            <div className="flex h-11 w-11 items-center justify-center">
              <Layers className="h-[22px] w-[22px] text-black/60 transition-colors group-hover:text-black dark:text-white/60 dark:group-hover:text-white" />
            </div>
            <span className={`font-display pl-3 text-[15px] font-medium tracking-tight transition-all duration-300 ${ isOpen ? "opacity-100" : "absolute left-[72px] opacity-0 pointer-events-none" }`}>
              {t('common.collections')}
            </span>
          </button>
        )}

        {/* History Accordion */}
        <div className="mb-2">
          <button
            onClick={onToggleRecents}
            className="flex h-11 w-full items-center justify-between rounded-[14px] px-0 transition-all duration-200 hover:bg-black/5 dark:hover:bg-white/5"
          >
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center">
                <History className="h-[22px] w-[22px] text-black/60 dark:text-white/60" />
              </div>
              <span className={`font-display pl-3 tracking-tight transition-all duration-300 ${ isOpen ? "opacity-100" : "absolute left-[72px] opacity-0 pointer-events-none" }`}>
                {t('common.recents')}
              </span>
            </div>
            <div className={`pr-4 transition-opacity duration-300 ${ isOpen ? "block opacity-100" : "hidden opacity-0 pointer-events-none" }`}>
              <ChevronRight className={`h-4 w-4 transition-transform duration-200 ${isRecentsExpanded ? "rotate-90" : ""}`} />
            </div>
          </button>

          {isRecentsExpanded && (
            <div className="space-y-0.5 pb-2">
              {currentView === "chat" && searchText.trim().length > 0 ? (
                <>
                  {isSearching ? (
                    <div className="px-11 py-4 text-[13px] text-black/45 dark:text-white/45">
                      {t("common.loading")}
                    </div>
                  ) : searchResults.length === 0 ? (
                    <div className="px-11 py-6">
                      <p className={`text-[13px] leading-relaxed text-black/30 transition-all duration-300 dark:text-white/30 ${ isOpen ? "opacity-100" : "absolute left-[72px] opacity-0 pointer-events-none" }`}>
                        {t("common.no_items")}
                      </p>
                    </div>
                  ) : (
                    <>
                      {searchResults.map((item) => (
                        <button
                          key={`${item.type}:${item.id}`}
                          onClick={() => onOpenItem(item)}
                          className="group relative flex w-full items-center gap-3 rounded-[14px] px-0 py-2.5 transition-all duration-200 hover:bg-black/5 dark:hover:bg-white/5"
                        >
                          <div className="flex h-6 w-11 flex-shrink-0 items-center justify-center" />
                          <div className={`min-w-0 flex-1 pl-3 pr-4 transition-all duration-300 ${ isOpen ? "opacity-100" : "absolute left-[72px] opacity-0 pointer-events-none" }`}>
                            <span className="font-display block truncate text-[15px] font-medium tracking-tight">
                              {item.title}
                            </span>
                            <span className="mt-0.5 block truncate text-[12px] text-black/40 dark:text-white/40">
                              {item.matched_text}
                            </span>
                          </div>
                        </button>
                      ))}
                      {searchNextCursor && (
                        <button
                          type="button"
                          onClick={onLoadMoreSearch}
                          disabled={isLoadingMoreSearch}
                          className="mx-11 mt-2 rounded-[12px] border border-black/10 px-3 py-1.5 text-[12px] font-medium text-black/70 hover:bg-black/5 disabled:opacity-50 dark:border-white/10 dark:text-white/70 dark:hover:bg-white/5"
                        >
                          {isLoadingMoreSearch ? t("common.loading") : t("common.retry")}
                        </button>
                      )}
                    </>
                  )}
                </>
              ) : historyItems.length === 0 ? (
                <div className="px-11 py-6">
                  <p className={`text-[13px] leading-relaxed text-black/30 transition-all duration-300 dark:text-white/30 ${ isOpen ? "opacity-100" : "absolute left-[72px] opacity-0 pointer-events-none" }`}>
                    {t('chat.no_recent_activity')}
                  </p>
                </div>
              ) : (
                <div className="flex flex-col gap-6 pb-4">
                  {groupedHistory.map((group) => (
                    <div key={group.label} className="flex flex-col">
                      <div className={`px-11 py-2 transition-all duration-300 ${ isOpen ? "opacity-100" : "opacity-0 invisible h-0 overflow-hidden" }`}>
                        <span className="text-[11px] font-semibold uppercase tracking-wider text-black/40 dark:text-white/40">
                          {group.label}
                        </span>
                      </div>
                      {group.items.map((item) => (
                        <button
                          key={`${item.type}:${item.id}`}
                          onClick={() => onOpenItem(item)}
                          className={`group relative flex w-full items-center gap-3 rounded-[14px] px-0 py-2.5 transition-all duration-200 ${ item.type === "chat" && conversationId === item.id ? "bg-black/5 dark:bg-white/5" : "hover:bg-black/5 dark:hover:bg-white/5" }`}
                        >
                          <div className="flex h-6 w-11 flex-shrink-0 items-center justify-center" />
                          <div className={`min-w-0 flex-1 pl-3 pr-4 transition-all duration-300 ${ isOpen ? "opacity-100" : "absolute left-[72px] opacity-0 pointer-events-none" }`}>
                            <span className="font-display block truncate text-[15px] font-medium tracking-tight">
                              {item.title}
                            </span>
                            <span className="mt-0.5 block text-[12px] text-black/40 dark:text-white/40">
                              {t(`common.${item.type}`, item.type)}
                            </span>
                          </div>
                        </button>
                      ))}
                    </div>
                  ))}
                </div>
              )}
              {historyNextCursor && currentView === "chat" && searchText.trim().length === 0 && (
                <button
                  type="button"
                  onClick={onLoadMoreHistory}
                  disabled={isLoadingMoreHistory}
                  className="mx-11 mt-2 rounded-[12px] border border-black/10 px-3 py-1.5 text-[12px] font-medium text-black/70 hover:bg-black/5 disabled:opacity-50 dark:border-white/10 dark:text-white/70 dark:hover:bg-white/5"
                >
                  {isLoadingMoreHistory ? t("common.loading") : t("common.retry")}
                </button>
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
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder={t('common.search')}
            className={`font-display h-11 w-full rounded-[14px] bg-black/[0.03] pl-[62px] pr-4 text-[15px] font-medium outline-none transition-all placeholder:text-black/30 hover:bg-black/[0.05] focus:bg-white focus:ring-1 focus:ring-black/5 dark:bg-white/[0.03] dark:placeholder:text-white/30 dark:hover:bg-white/[0.05] dark:focus:bg-[#1f2225] dark:focus:ring-white/5 ${ isOpen ? "block" : "hidden" }`}
          />
        </div>

        <button
          onClick={onOpenSettings}
          className={`group flex h-11 w-full items-center gap-3 rounded-[14px] px-0 transition-all duration-200 ${ currentView === "settings" ? "bg-black/5 dark:bg-white/5" : "hover:bg-black/5 dark:hover:bg-white/5" }`}
        >
          <div className="flex h-11 w-11 items-center justify-center">
            <Settings className="h-5 w-5 text-black/60 transition-colors group-hover:text-black dark:text-white/60 dark:group-hover:text-white" />
          </div>
          <span className={`font-display pl-3 text-[15px] font-medium tracking-tight transition-all duration-300 ${ isOpen ? "opacity-100" : "absolute left-[72px] opacity-0 pointer-events-none" }`}>
            {t('common.settings')}
          </span>
        </button>
      </div>
    </aside>
  );
}
