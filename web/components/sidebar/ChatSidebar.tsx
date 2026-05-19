"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { TFunction } from "i18next";
import {
  ChevronDown,
  Compass,
  History,
  MessageCirclePlus,
  PanelLeft,
  Pin,
  Search,
  User,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { ArgusLogo } from "@/components/ArgusLogo";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Tooltip } from "@/components/ui/Tooltip";
import SidebarNavButton from "./SidebarNavButton";
import ProfileMenu from "./ProfileMenu";
import RecentChatActions from "./RecentChatActions";
import { patchConversation, deleteConversation as apiDeleteConversation } from "@/lib/argus-api";

import type { HistoryItem, SearchItem } from "@/lib/argus-api";

// ─── Types ────────────────────────────────────────────────────────────────────

export type SidebarMode = "expanded" | "collapsed" | "hover";

type View = "chat" | "strategies" | "collections" | "settings";

export type ChatSidebarProps = {
  /** Whether the sidebar is expanded or collapsed */
  isOpen: boolean;
  onToggle: () => void;

  /** Sidebar behavior mode */
  mode?: SidebarMode;

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
  /** Sidebar preference handler */
  onOpenSidebarPreference?: () => void;
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

// ─── Main Component ───────────────────────────────────────────────────────────

export default function ChatSidebar({
  isOpen,
  onToggle,
  mode = "expanded",
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
  onOpenSidebarPreference,
}: ChatSidebarProps) {
  const { t } = useTranslation();
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [renameError, setRenameError] = useState<string | null>(null);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isProfileMenuOpen, setIsProfileMenuOpen] = useState(false);
  const profileButtonRef = useRef<HTMLElement | null>(null);
  const recentsScrollRef = useRef<HTMLDivElement>(null);
  const hoverTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const isPointerInsideSidebarRef = useRef(false);

  // ─── Hover Logic ────────────────────────────────────────────────────────────

  const handleMouseEnter = () => {
    isPointerInsideSidebarRef.current = true;
    if (mode !== "hover") return;
    if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current);
    
    hoverTimeoutRef.current = setTimeout(() => {
      if (!isOpen) {
        onToggle();
      }
    }, 300);
  };

  const handleMouseLeave = () => {
    isPointerInsideSidebarRef.current = false;
    if (mode !== "hover") return;
    if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current);
    if (isProfileMenuOpen) return;
    
    hoverTimeoutRef.current = setTimeout(() => {
      if (isOpen) {
        onToggle();
      }
    }, 300);
  };

  useEffect(() => {
    return () => {
      if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current);
    };
  }, []);

  useEffect(() => {
    if (
      mode === "hover" &&
      isOpen &&
      !isProfileMenuOpen &&
      !isPointerInsideSidebarRef.current
    ) {
      hoverTimeoutRef.current = setTimeout(() => {
        onToggle();
      }, 300);
    }
    return () => {
      if (hoverTimeoutRef.current) clearTimeout(hoverTimeoutRef.current);
    };
  }, [isProfileMenuOpen, isOpen, mode, onToggle]);

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

  const handleRequestDelete = useCallback((id: string) => {
    setPendingDeleteId(id);
  }, []);

  const handleConfirmDelete = useCallback(async () => {
    if (!pendingDeleteId || isDeleting) return;
    setIsDeleting(true);
    try {
      await apiDeleteConversation(pendingDeleteId);
      onHistoryMutated?.();
    } catch (err) {
      console.error("Failed to delete conversation", err);
    } finally {
      setIsDeleting(false);
      setPendingDeleteId(null);
    }
  }, [isDeleting, onHistoryMutated, pendingDeleteId]);

  const handleStartRename = useCallback((id: string) => {
    const item = chatItems.find((i) => i.id === id);
    setRenamingId(id);
    setRenameValue(item?.title ?? "");
    setRenameError(null);
  }, [chatItems]);

  const handleSaveRename = useCallback(async () => {
    if (!renamingId) return;
    const trimmed = renameValue.trim();
    setRenameError(null);
    if (!trimmed) {
      setRenamingId(null);
      return;
    }
    try {
      await patchConversation(renamingId, { title: trimmed });
      onHistoryMutated?.();
    } catch (err) {
      console.error("Failed to rename conversation", err);
      setRenameError(t("chat.rename_failed", "Could not rename this chat. Try again."));
      return;
    }
    setRenamingId(null);
  }, [renamingId, renameValue, onHistoryMutated, t]);

  const handleCancelRename = useCallback(() => {
    setRenamingId(null);
    setRenameError(null);
  }, []);

  const pendingDeleteItem = useMemo(
    () => chatItems.find((item) => item.id === pendingDeleteId) ?? null,
    [chatItems, pendingDeleteId],
  );

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
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      className={`flex flex-col border-r border-black/5 bg-white transition-[width] duration-300 ease-in-out overflow-hidden will-change-[width] dark:border-white/5 dark:bg-[#141517] ${
        isOpen ? "w-72" : "w-14"
      }`}
    >
      {/* Sidebar Header: Brand + Panel Toggle */}
      <div className="flex h-20 items-center px-[6px] pb-4 pt-6">
        <Tooltip
          content={isOpen ? t("sidebar.close", "Close sidebar") : t("sidebar.open", "Open sidebar")}
          side="right"
          delay={150}
        >
          <button
            onClick={onToggle}
            className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-full transition-all duration-200 hover:bg-black/5 dark:hover:bg-white/5 active:scale-95"
            aria-label={isOpen ? "Collapse sidebar" : "Expand sidebar"}
          >
            {/* Swap: PanelLeft when open → ArgusLogo when collapsed */}
            {isOpen ? (
              <PanelLeft className="h-5 w-5 text-black/60 dark:text-white/60" />
            ) : (
              <ArgusLogo className="h-8 w-8 text-black dark:text-white" />
            )}
          </button>
        </Tooltip>
        {/* "argus" text — font-display (Space Grotesk) per DESIGN.md */}
        <span
          className={`ml-1 whitespace-nowrap font-display text-[22px] font-medium tracking-tight text-black transition-[opacity,max-width] duration-300 ease-in-out dark:text-white ${
            isOpen ? "max-w-[200px] opacity-100" : "max-w-0 overflow-hidden opacity-0"
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
            onClick={() => {
              if (!isOpen) {
                // When collapsed: expand sidebar + open recents
                onToggle();
                if (!isRecentsExpanded) onToggleRecents();
              } else {
                onToggleRecents();
              }
            }}
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
                        <div
                          key={`chat:${item.id}`}
                          role="button"
                          tabIndex={0}
                          onClick={(e) => {
                            // Only navigate if click was on this element or its text children,
                            // not on nested interactive elements (three-dot menu)
                            const target = e.target as HTMLElement;
                            if (target.closest('[data-actions]')) return;
                            if (renamingId !== item.id) {
                              onOpenItem(item);
                            }
                          }}
                          onKeyDown={(e) => {
                            if (e.key === "Enter" && renamingId !== item.id) {
                              onOpenItem(item);
                            }
                          }}
                          className={`group relative flex w-full cursor-pointer items-center gap-3 rounded-[14px] px-0 py-2 transition-all duration-200 ${
                            conversationId === item.id
                              ? "bg-black/5 dark:bg-white/5"
                              : "hover:bg-black/5 dark:hover:bg-white/5"
                          }`}
                        >
                          <div className="flex h-6 w-11 flex-shrink-0 items-center justify-center" />
                          <div className="min-w-0 flex-1 pl-3 pr-10">
                            {renamingId === item.id ? (
                              <>
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
                                  aria-invalid={Boolean(renameError)}
                                  className="w-full rounded-md border border-black/20 bg-transparent px-1.5 py-0.5 text-[14px] font-medium outline-none focus:border-black/40 dark:border-white/20 dark:focus:border-white/40"
                                  maxLength={80}
                                />
                                {renameError && (
                                  <p className="mt-1 text-[11px] font-medium text-[#d66d75]" role="alert">
                                    {renameError}
                                  </p>
                                )}
                              </>
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
                            <div data-actions className="absolute right-2 top-1/2 -translate-y-1/2">
                              <RecentChatActions
                                item={item}
                                onPin={handlePin}
                                onRename={handleStartRename}
                                onArchive={handleArchive}
                                onDelete={handleRequestDelete}
                              />
                            </div>
                          )}
                        </div>
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
      <ConfirmDialog
        isOpen={Boolean(pendingDeleteItem)}
        title={t("sidebar.delete_confirm.title", "Delete this conversation?")}
        description={t(
          "sidebar.delete_confirm.description",
          "This moves “{{title}}” to Recently Deleted. You can restore it before permanent removal.",
          { title: pendingDeleteItem?.title ?? t("common.conversation", "Conversation") },
        )}
        confirmLabel={t("sidebar.delete_confirm.confirm", "Delete conversation")}
        cancelLabel={t("common.cancel", "Cancel")}
        isBusy={isDeleting}
        onCancel={() => {
          if (!isDeleting) setPendingDeleteId(null);
        }}
        onConfirm={() => void handleConfirmDelete()}
      />

      {/* Footer: Profile menu trigger */}
      <div className="relative border-t border-black/5 p-[6px] dark:border-white/5">
        <ProfileMenu
          isOpen={isProfileMenuOpen}
          onClose={() => setIsProfileMenuOpen(false)}
          onLogout={onLogout}
          onFeedback={onFeedback}
          onOpenSidebarPreference={onOpenSidebarPreference}
          anchorRef={profileButtonRef}
          sidebarCollapsed={!isOpen}
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
