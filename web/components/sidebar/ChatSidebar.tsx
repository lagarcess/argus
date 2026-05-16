"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { TFunction } from "i18next";
import {
  ChevronDown,
  Compass,
  Edit2,
  History,
  MessageCirclePlus,
  MoreVertical,
  Pin,
  Search,
  Archive,
  Trash2,
  User,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { ArgusLogo } from "@/components/ArgusLogo";
import SidebarNavButton from "./SidebarNavButton";
import ProfileMenu from "./ProfileMenu";
import { patchConversation, deleteConversation as apiDeleteConversation } from "@/lib/argus-api";

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

  // ── Recents ──────────────────────────────────────────────────────────────
  /** Whether the Recents accordion is expanded */
  isRecentsExpanded: boolean;
  onToggleRecents: () => void;
  /** History items for the Recents list */
  historyItems: HistoryItem[];
  /** Whether more history pages are available */
  historyNextCursor: string | null;
  /** Whether a history page load is in progress */
  isLoadingMoreHistory: boolean;

  // ── Callbacks ────────────────────────────────────────────────────────────
  onNewChat: () => void;
  onNavigate: (view: View) => void;
  onOpenItem: (item: HistoryItem | SearchItem) => void;
  onLoadMoreHistory: () => void;
  onOpenSettings: () => void;
  onOpenSearch: () => void;
  /** Callback when a chat is mutated (pin/archive/delete/rename) so parent can refresh */
  onHistoryMutated?: () => void;
  /** Logout handler */
  onLogout: () => void;
  /** Feedback handler */
  onFeedback?: (type: "bug" | "feature" | "general") => void;
};

// ─── Date grouping helpers ────────────────────────────────────────────────────

function groupByDate(
  items: HistoryItem[],
  t: TFunction,
) {
  const pinned: HistoryItem[] = [];
  const today: HistoryItem[] = [];
  const yesterday: HistoryItem[] = [];
  const last7Days: HistoryItem[] = [];
  const last30Days: HistoryItem[] = [];
  const older: HistoryItem[] = [];

  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const yesterdayStart = todayStart - 86400000;
  const last7Start = todayStart - 86400000 * 6;
  const last30Start = todayStart - 86400000 * 29;

  items.forEach((item) => {
    if (item.pinned) {
      pinned.push(item);
      return;
    }
    const d = new Date(item.created_at).getTime();
    if (d >= todayStart) {
      today.push(item);
    } else if (d >= yesterdayStart) {
      yesterday.push(item);
    } else if (d >= last7Start) {
      last7Days.push(item);
    } else if (d >= last30Start) {
      last30Days.push(item);
    } else {
      older.push(item);
    }
  });

  const groups: { label: string; items: HistoryItem[] }[] = [];
  if (pinned.length > 0) groups.push({ label: t("chat.history.pinned", "Pinned"), items: pinned });
  if (today.length > 0) groups.push({ label: t("chat.history.today"), items: today });
  if (yesterday.length > 0) groups.push({ label: t("chat.history.yesterday"), items: yesterday });
  if (last7Days.length > 0) groups.push({ label: t("chat.history.last_7_days"), items: last7Days });
  if (last30Days.length > 0) groups.push({ label: t("chat.history.last_30_days", "Last 30 Days"), items: last30Days });
  if (older.length > 0) groups.push({ label: t("chat.history.earlier"), items: older });
  return groups;
}

// ─── RecentChatActions (three-dot hover menu) ─────────────────────────────────

type RecentChatActionsProps = {
  item: HistoryItem;
  onPin: (id: string, pinned: boolean) => void;
  onRename: (id: string) => void;
  onArchive: (id: string) => void;
  onDelete: (id: string) => void;
};

function RecentChatActions({ item, onPin, onRename, onArchive, onDelete }: RecentChatActionsProps) {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const { t } = useTranslation();

  // Close on click-outside
  useEffect(() => {
    if (!isMenuOpen) return;
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setIsMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [isMenuOpen]);

  // Close on Escape
  useEffect(() => {
    if (!isMenuOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setIsMenuOpen(false);
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [isMenuOpen]);

  return (
    <div ref={menuRef} className="relative">
      <button
        onClick={(e) => {
          e.stopPropagation();
          setIsMenuOpen(!isMenuOpen);
        }}
        className="flex h-7 w-7 items-center justify-center rounded-md opacity-0 transition-opacity duration-150 group-hover:opacity-100 hover:bg-black/5 dark:hover:bg-white/10"
        title={t("common.more", "More")}
      >
        <MoreVertical className="h-3.5 w-3.5 text-black/50 dark:text-white/50" />
      </button>

      {isMenuOpen && (
        <div className="absolute right-0 top-full z-50 mt-1 min-w-[160px] rounded-[12px] border border-black/10 bg-white py-1 dark:border-white/10 dark:bg-[#1f2225]">
          <button
            onClick={(e) => {
              e.stopPropagation();
              onPin(item.id, !item.pinned);
              setIsMenuOpen(false);
            }}
            className="flex w-full items-center gap-2.5 px-3 py-2 text-[13px] hover:bg-black/5 dark:hover:bg-white/5"
          >
            <Pin className="h-3.5 w-3.5" />
            {item.pinned ? t("common.unpin", "Unpin") : t("common.pin", "Pin")}
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onRename(item.id);
              setIsMenuOpen(false);
            }}
            className="flex w-full items-center gap-2.5 px-3 py-2 text-[13px] hover:bg-black/5 dark:hover:bg-white/5"
          >
            <Edit2 className="h-3.5 w-3.5" />
            {t("common.rename", "Rename")}
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onArchive(item.id);
              setIsMenuOpen(false);
            }}
            className="flex w-full items-center gap-2.5 px-3 py-2 text-[13px] hover:bg-black/5 dark:hover:bg-white/5"
          >
            <Archive className="h-3.5 w-3.5" />
            {t("common.archive", "Archive")}
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDelete(item.id);
              setIsMenuOpen(false);
            }}
            className="flex w-full items-center gap-2.5 px-3 py-2 text-[13px] text-[#d66d75] hover:bg-black/5 dark:hover:bg-white/5"
          >
            <Trash2 className="h-3.5 w-3.5" />
            {t("common.delete", "Delete")}
          </button>
        </div>
      )}
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function ChatSidebar({
  isOpen,
  onToggle,
  currentView,
  conversationId,
  isRecentsExpanded,
  onToggleRecents,
  historyItems,
  historyNextCursor,
  isLoadingMoreHistory,
  onNewChat,
  onNavigate,
  onOpenItem,
  onLoadMoreHistory,
  onOpenSettings,
  onOpenSearch,
  onHistoryMutated,
  onLogout,
  onFeedback,
}: ChatSidebarProps) {
  const { t } = useTranslation();
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [isProfileMenuOpen, setIsProfileMenuOpen] = useState(false);
  const profileButtonRef = useRef<HTMLElement | null>(null);
  const recentsScrollRef = useRef<HTMLDivElement>(null);

  // ── Filter to chats only ────────────────────────────────────────────────
  const chatItems = useMemo(
    () => historyItems.filter((item) => item.type === "chat"),
    [historyItems],
  );

  // ── Date-grouped history ────────────────────────────────────────────────
  const groupedHistory = useMemo(() => groupByDate(chatItems, t), [chatItems, t]);

  // ── Chat actions ────────────────────────────────────────────────────────
  const handlePin = useCallback(async (id: string, pinned: boolean) => {
    try {
      await patchConversation(id, { pinned });
      onHistoryMutated?.();
    } catch (err) {
      console.error("Failed to pin/unpin conversation", err);
    }
  }, [onHistoryMutated]);

  const handleArchive = useCallback(async (id: string) => {
    try {
      await patchConversation(id, { archived: true });
      onHistoryMutated?.();
    } catch (err) {
      console.error("Failed to archive conversation", err);
    }
  }, [onHistoryMutated]);

  const handleDelete = useCallback(async (id: string) => {
    try {
      await apiDeleteConversation(id);
      onHistoryMutated?.();
    } catch (err) {
      console.error("Failed to delete conversation", err);
    }
  }, [onHistoryMutated]);

  const handleStartRename = useCallback((id: string) => {
    const item = chatItems.find((i) => i.id === id);
    setRenamingId(id);
    setRenameValue(item?.title ?? "");
  }, [chatItems]);

  const handleSaveRename = useCallback(async () => {
    if (!renamingId) return;
    const trimmed = renameValue.trim();
    if (!trimmed) {
      setRenamingId(null);
      return;
    }
    try {
      await patchConversation(renamingId, { title: trimmed });
      onHistoryMutated?.();
    } catch (err) {
      console.error("Failed to rename conversation", err);
    }
    setRenamingId(null);
  }, [renamingId, renameValue, onHistoryMutated]);

  const handleCancelRename = useCallback(() => {
    setRenamingId(null);
  }, []);

  // ── Infinite scroll for recents ─────────────────────────────────────────
  useEffect(() => {
    const el = recentsScrollRef.current;
    if (!el || !historyNextCursor || isLoadingMoreHistory) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          onLoadMoreHistory();
        }
      },
      { root: el, threshold: 0.1 },
    );

    // Observe the last item in the list as a sentinel
    const sentinel = el.querySelector("[data-sentinel]");
    if (sentinel) observer.observe(sentinel);

    return () => observer.disconnect();
  }, [historyNextCursor, isLoadingMoreHistory, onLoadMoreHistory, groupedHistory]);

  return (
    <aside
      className={`flex flex-col border-r border-black/5 bg-white transition-all duration-300 ease-in-out overflow-x-hidden will-change-[width] dark:border-white/5 dark:bg-[#141517] ${
        isOpen ? "w-72" : "w-14"
      }`}
    >
      {/* Sidebar Header: Brand & Toggle */}
      <div className="flex h-20 items-center px-[6px] pb-4 pt-6 overflow-hidden">
        <button
          onClick={onToggle}
          title={isOpen ? t("sidebar.close", "Close sidebar") : t("sidebar.open", "Open sidebar")}
          className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-full transition-all duration-300 hover:bg-black/5 dark:hover:bg-white/5 active:scale-95"
          aria-label={isOpen ? "Collapse sidebar" : "Expand sidebar"}
        >
          <ArgusLogo className="h-8 w-8 text-black dark:text-white" />
        </button>
        <span
          className={`font-display pl-3 text-[22px] font-bold tracking-tight text-black transition-all duration-300 dark:text-white ${
            isOpen ? "opacity-100" : "pointer-events-none absolute left-[72px] opacity-0"
          }`}
        >
          argus
        </span>
      </div>

      <div className="flex flex-1 flex-col overflow-y-auto overflow-x-hidden px-[6px] pb-4 pt-2">
        {/* Main Navigation */}
        <SidebarNavButton
          icon={MessageCirclePlus}
          label={t("chat.new_chat")}
          collapsed={!isOpen}
          onClick={() => {
            onNewChat();
            // Auto-collapse sidebar when creating a new chat (if open)
          }}
          iconSize={20}
        />

        <SidebarNavButton
          icon={Search}
          label={t("common.search", "Search")}
          collapsed={!isOpen}
          onClick={onOpenSearch}
          iconSize={20}
        />

        <SidebarNavButton
          icon={Compass}
          label={t("common.strategies")}
          active={currentView === "strategies"}
          collapsed={!isOpen}
          onClick={() => onNavigate("strategies")}
        />

        {/* Recents Accordion */}
        <div className="mb-2 mt-2">
          <SidebarNavButton
            icon={History}
            label={t("common.recents")}
            collapsed={!isOpen}
            onClick={onToggleRecents}
            trailing={
              <ChevronDown
                className={`h-4 w-4 text-black/40 transition-transform duration-200 dark:text-white/40 ${
                  isRecentsExpanded ? "rotate-180" : ""
                }`}
              />
            }
          />

          {isRecentsExpanded && isOpen && (
            <div ref={recentsScrollRef} className="max-h-[50vh] overflow-y-auto pb-2">
              {chatItems.length === 0 ? (
                <div className="px-11 py-6">
                  <p className="text-[13px] leading-relaxed text-black/30 dark:text-white/30">
                    {t("chat.no_recent_activity")}
                  </p>
                </div>
              ) : (
                <div className="flex flex-col gap-4 pb-2">
                  {groupedHistory.map((group) => (
                    <div key={group.label} className="flex flex-col">
                      <div className="px-11 py-2">
                        <span className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-black/40 dark:text-white/40">
                          {group.label === t("chat.history.pinned", "Pinned") && (
                            <Pin className="h-3 w-3" />
                          )}
                          {group.label}
                        </span>
                      </div>
                      {group.items.map((item) => (
                        <button
                          key={`chat:${item.id}`}
                          onClick={() => {
                            if (renamingId !== item.id) {
                              onOpenItem(item);
                            }
                          }}
                          className={`group relative flex w-full items-center gap-3 rounded-[14px] px-0 py-2 transition-all duration-200 ${
                            conversationId === item.id
                              ? "bg-black/5 dark:bg-white/5"
                              : "hover:bg-black/5 dark:hover:bg-white/5"
                          }`}
                        >
                          <div className="flex h-6 w-11 flex-shrink-0 items-center justify-center" />
                          <div className="min-w-0 flex-1 pl-3 pr-2">
                            {renamingId === item.id ? (
                              <input
                                autoFocus
                                type="text"
                                value={renameValue}
                                onChange={(e) => setRenameValue(e.target.value.slice(0, 80))}
                                onKeyDown={(e) => {
                                  if (e.key === "Enter") {
                                    e.preventDefault();
                                    void handleSaveRename();
                                  } else if (e.key === "Escape") {
                                    handleCancelRename();
                                  }
                                }}
                                onBlur={() => void handleSaveRename()}
                                onClick={(e) => e.stopPropagation()}
                                className="w-full rounded-md border border-black/20 bg-transparent px-1.5 py-0.5 text-[14px] font-medium outline-none focus:border-black/40 dark:border-white/20 dark:focus:border-white/40"
                                maxLength={80}
                              />
                            ) : (
                              <>
                                <span className="font-display block truncate text-[14px] font-medium tracking-tight text-black dark:text-white">
                                  {item.title}
                                </span>
                                <span className="mt-0.5 block truncate text-[12px] text-black/40 dark:text-white/40">
                                  {item.subtitle}
                                </span>
                              </>
                            )}
                          </div>
                          {renamingId !== item.id && (
                            <div className="absolute right-2 top-1/2 -translate-y-1/2">
                              <RecentChatActions
                                item={item}
                                onPin={handlePin}
                                onRename={handleStartRename}
                                onArchive={handleArchive}
                                onDelete={handleDelete}
                              />
                            </div>
                          )}
                        </button>
                      ))}
                    </div>
                  ))}
                  {/* Infinite scroll sentinel */}
                  {historyNextCursor && (
                    <div data-sentinel className="h-4">
                      {isLoadingMoreHistory && (
                        <p className="px-11 text-[12px] text-black/30 dark:text-white/30">
                          {t("common.loading")}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Footer: Profile menu trigger */}
      <div className="relative border-t border-black/5 p-[6px] dark:border-white/5">
        <ProfileMenu
          isOpen={isProfileMenuOpen}
          onClose={() => setIsProfileMenuOpen(false)}
          onLogout={onLogout}
          onFeedback={onFeedback}
          anchorRef={profileButtonRef}
        />
        <div ref={profileButtonRef as React.RefObject<HTMLDivElement>}>
          <SidebarNavButton
            icon={User}
            label={t("common.settings")}
            collapsed={!isOpen}
            onClick={() => setIsProfileMenuOpen(!isProfileMenuOpen)}
            iconSize={20}
          />
        </div>
      </div>
    </aside>
  );
}
