"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Archive,
  Edit2,
  Maximize2,
  Minimize2,
  Search,
  Trash2,
  X,
  Loader2,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  searchGlobal,
  listHistory,
  getConversationMessages,
  patchConversation,
  deleteConversation as apiDeleteConversation,
  type SearchItem,
  type HistoryItem,
  type ApiMessage,
} from "@/lib/argus-api";
import ChatMessage from "@/components/chat/ChatMessage";
import { hydrateMessagesFromApi } from "@/components/chat/ChatInterface";

// ─── Types ────────────────────────────────────────────────────────────────────

type ChatOmniSearchProps = {
  /** Close the overlay */
  onClose: () => void;
  /** Navigate to a conversation */
  onOpenConversation: (conversationId: string) => void;
  /** Currently active conversation id */
  activeConversationId: string | null;
  /** Callback when a chat is mutated */
  onMutated?: () => void;
};

type LayoutMode = "expanded" | "collapsed";

type DisplayItem = {
  id: string;
  title: string;
  subtitle: string;
  updated_at: string;
  type: "chat";
  conversation_id?: string | null;
};

// ─── Highlight helper ─────────────────────────────────────────────────────────

function highlightText(text: string, query: string): React.ReactNode[] {
  if (!query.trim()) return [text];
  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const regex = new RegExp(`(${escaped})`, "gi");
  const parts = text.split(regex);
  return parts.map((part, i) =>
    regex.test(part) ? (
      <mark
        key={i}
        className="rounded-sm bg-[#c2a44d]/20 px-0.5 font-semibold text-[#c2a44d]"
        style={{ textDecoration: "none" }}
      >
        {part}
      </mark>
    ) : (
      part
    ),
  );
}

// ─── Date formatting ──────────────────────────────────────────────────────────

function formatRelativeDate(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const d = date.getTime();

  if (d >= todayStart) return "Today";
  if (d >= todayStart - 86400000) return "Yesterday";
  // For older dates, use abbreviated format: "Apr 10"
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

/** Group label for date segmentation (more granular for cold start) */
function getDateGroupLabel(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const d = date.getTime();

  if (d >= todayStart) return "Today";
  if (d >= todayStart - 86400000) return "Yesterday";
  if (d >= todayStart - 86400000 * 6) return "Last 7 Days";
  if (d >= todayStart - 86400000 * 29) return "Last 30 Days";
  return "Earlier";
}

// ─── Group results by date ────────────────────────────────────────────────────

function groupItems(items: DisplayItem[]) {
  const groups: { label: string; items: DisplayItem[] }[] = [];
  const buckets = new Map<string, DisplayItem[]>();

  for (const item of items) {
    const label = getDateGroupLabel(item.updated_at);
    if (!buckets.has(label)) {
      buckets.set(label, []);
      groups.push({ label, items: buckets.get(label)! });
    }
    buckets.get(label)!.push(item);
  }

  return groups;
}

// ─── Preview Message Bubble ───────────────────────────────────────────────────

// ─── Preview Message Bubble Removed in favor of ChatMessage ───────────────

// ─── Component ────────────────────────────────────────────────────────────────

export default function ChatOmniSearch({
  onClose,
  onOpenConversation,
  activeConversationId,
  onMutated,
}: ChatOmniSearchProps) {
  const { t } = useTranslation();
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchItem[]>([]);
  const [coldStartItems, setColdStartItems] = useState<HistoryItem[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [isColdStartLoading, setIsColdStartLoading] = useState(true);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [previewMessages, setPreviewMessages] = useState<ApiMessage[]>([]);
  const [isLoadingPreview, setIsLoadingPreview] = useState(false);
  const [layoutMode, setLayoutMode] = useState<LayoutMode>(() => {
    if (typeof window === "undefined") return "expanded";
    return (localStorage.getItem("argus:omni_search_layout") as LayoutMode) ?? "expanded";
  });
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const previewDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Cold start: load recent chats ───────────────────────────────────────
  useEffect(() => {
    setIsColdStartLoading(true);
    listHistory({ limit: 50 })
      .then(({ items }) => {
        setColdStartItems(items.filter((i) => i.type === "chat"));
      })
      .catch(() => setColdStartItems([]))
      .finally(() => setIsColdStartLoading(false));
  }, []);

  // Normalize to DisplayItem
  const coldStartDisplay: DisplayItem[] = useMemo(
    () =>
      coldStartItems.map((item) => ({
        id: item.id,
        title: item.title,
        subtitle: item.subtitle ?? "",
        updated_at: item.created_at,
        type: "chat" as const,
      })),
    [coldStartItems],
  );

  const searchDisplay: DisplayItem[] = useMemo(
    () =>
      searchResults
        .filter((item) => item.type === "chat")
        .map((item) => ({
          id: item.id,
          title: item.title,
          subtitle: item.matched_text ?? "",
          updated_at: item.updated_at,
          type: "chat" as const,
          conversation_id: item.conversation_id,
        })),
    [searchResults],
  );

  // Which items to show: search results when typing, cold start otherwise
  const isFiltering = query.trim().length > 0;
  const displayItems = isFiltering ? searchDisplay : coldStartDisplay;
  const groupedItems = useMemo(() => groupItems(displayItems), [displayItems]);

  // ── Auto-focus ──────────────────────────────────────────────────────────
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // ── Close on Escape ─────────────────────────────────────────────────────
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  // ── Debounced search ────────────────────────────────────────────────────
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);

    const trimmed = query.trim();
    if (!trimmed) {
      setSearchResults([]);
      setIsSearching(false);
      return;
    }

    setIsSearching(true);
    debounceRef.current = setTimeout(async () => {
      try {
        const { items } = await searchGlobal({ q: trimmed, limit: 30 });
        setSearchResults(items);
      } catch (err) {
        console.error("Search failed", err);
        setSearchResults([]);
      } finally {
        setIsSearching(false);
      }
    }, 200);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query]);

  // ── Preview panel: load messages on hover (expanded mode) ───────────────
  useEffect(() => {
    if (layoutMode !== "expanded" || !hoveredId) {
      setPreviewMessages([]);
      return;
    }

    if (previewDebounceRef.current) clearTimeout(previewDebounceRef.current);
    setIsLoadingPreview(true);

    previewDebounceRef.current = setTimeout(async () => {
      try {
        const { items } = await getConversationMessages(hoveredId, 50);
        setPreviewMessages(items);
      } catch {
        setPreviewMessages([]);
      } finally {
        setIsLoadingPreview(false);
      }
    }, 150);

    return () => {
      if (previewDebounceRef.current) clearTimeout(previewDebounceRef.current);
    };
  }, [hoveredId, layoutMode]);

  // ── Layout persistence ──────────────────────────────────────────────────
  const toggleLayout = useCallback(() => {
    setLayoutMode((prev) => {
      const next = prev === "expanded" ? "collapsed" : "expanded";
      localStorage.setItem("argus:omni_search_layout", next);
      return next;
    });
  }, []);

  // ── Actions ─────────────────────────────────────────────────────────────
  const handleRename = useCallback(
    async (id: string) => {
      const item = displayItems.find((r) => r.id === id);
      if (!item) return;
      const newTitle = prompt("Rename conversation:", item.title);
      if (!newTitle?.trim()) return;
      try {
        await patchConversation(id, { title: newTitle.trim() });
        // Update local state
        if (isFiltering) {
          setSearchResults((prev) =>
            prev.map((r) => (r.id === id ? { ...r, title: newTitle.trim() } : r)),
          );
        } else {
          setColdStartItems((prev) =>
            prev.map((r) => (r.id === id ? { ...r, title: newTitle.trim() } : r)),
          );
        }
        onMutated?.();
      } catch (err) {
        console.error("Failed to rename", err);
      }
    },
    [displayItems, isFiltering, onMutated],
  );

  const handleArchive = useCallback(
    async (id: string) => {
      try {
        await patchConversation(id, { archived: true });
        if (isFiltering) {
          setSearchResults((prev) => prev.filter((r) => r.id !== id));
        } else {
          setColdStartItems((prev) => prev.filter((r) => r.id !== id));
        }
        onMutated?.();
      } catch (err) {
        console.error("Failed to archive", err);
      }
    },
    [isFiltering, onMutated],
  );

  const handleDelete = useCallback(
    async (id: string) => {
      try {
        await apiDeleteConversation(id);
        if (isFiltering) {
          setSearchResults((prev) => prev.filter((r) => r.id !== id));
        } else {
          setColdStartItems((prev) => prev.filter((r) => r.id !== id));
        }
        onMutated?.();
      } catch (err) {
        console.error("Failed to delete", err);
      }
    },
    [isFiltering, onMutated],
  );

  const handleSelectChat = useCallback(
    (item: DisplayItem) => {
      const convId = item.conversation_id ?? item.id;
      onOpenConversation(convId);
      onClose();
    },
    [onOpenConversation, onClose],
  );

  const isLoading = isFiltering ? isSearching : isColdStartLoading;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 sm:p-8">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/20 backdrop-blur-sm dark:bg-black/60"
        role="button"
        tabIndex={-1}
        onClick={onClose}
        onKeyDown={(e) => { if (e.key === "Enter") onClose(); }}
        aria-label="Close search"
      />

      {/* Modal */}
      <div
        className={`relative flex flex-col overflow-hidden rounded-[18px] border border-black/10 bg-white dark:border-white/10 dark:bg-[#1b1d20] transition-all duration-300 ${
          layoutMode === "expanded"
            ? "h-[75vh] w-full max-w-4xl"
            : "h-[65vh] w-full max-w-lg"
        }`}
      >
        {/* Search input */}
        <div className="flex items-center gap-3 border-b border-black/5 px-5 py-3.5 dark:border-white/5">
          <Search className="h-4 w-4 shrink-0 text-black/30 dark:text-white/30" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("common.search", "Search conversations...")}
            className="w-full bg-transparent font-display text-[15px] font-medium text-black outline-none placeholder:text-black/35 dark:text-white dark:placeholder:text-white/35"
          />
          {query && (
            <button
              onClick={() => setQuery("")}
              className="shrink-0 rounded-full p-1 hover:bg-black/5 dark:hover:bg-white/10"
            >
              <X className="h-3.5 w-3.5 text-black/40 dark:text-white/40" />
            </button>
          )}
        </div>

        {/* Body */}
        <div className="flex flex-1 overflow-hidden">
          {/* Left panel: results list */}
          <div
            className={`flex-1 overflow-y-auto ${
              layoutMode === "expanded" ? "border-r border-black/5 dark:border-white/5" : ""
            }`}
          >
            {isLoading ? (
              <div className="flex items-center justify-center py-20">
                <Loader2 className="h-5 w-5 animate-spin text-black/20 dark:text-white/20" />
              </div>
            ) : displayItems.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 text-center">
                <Search className="mb-3 h-8 w-8 text-black/10 dark:text-white/10" />
                <p className="text-[14px] text-black/30 dark:text-white/30">
                  {isFiltering ? "No results found" : "No conversations yet"}
                </p>
              </div>
            ) : (
              <div className="flex flex-col gap-3 p-3">
                {groupedItems.map((group) => (
                  <div key={group.label}>
                    <div className="px-2 pb-1.5 pt-1">
                      <span className="font-display text-[11px] font-semibold uppercase tracking-wider text-black/40 dark:text-white/40">
                        {group.label}
                      </span>
                    </div>
                    {group.items.map((item) => (
                      <div
                        key={item.id}
                        role="button"
                        tabIndex={0}
                        onClick={(e) => {
                          const target = e.target as HTMLElement;
                          if (target.closest("[data-actions]")) return;
                          handleSelectChat(item);
                        }}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") handleSelectChat(item);
                        }}
                        onMouseEnter={() => setHoveredId(item.id)}
                        className={`group relative flex w-full cursor-pointer items-start gap-2 rounded-[12px] px-3 py-2.5 text-left transition-colors ${
                          hoveredId === item.id
                            ? "bg-black/5 dark:bg-white/5"
                            : "hover:bg-black/[0.03] dark:hover:bg-white/[0.03]"
                        }`}
                      >
                        {/* Content — with right padding to prevent overlap with actions */}
                        <div className="min-w-0 flex-1 pr-20">
                          <div className="flex items-center gap-2">
                            <span className="font-display truncate text-[14px] font-medium text-black dark:text-white">
                              {isFiltering ? highlightText(item.title, query) : item.title}
                            </span>
                            {activeConversationId === item.id && (
                              <span className="shrink-0 rounded-full bg-[#5ba897]/15 px-2 py-0.5 text-[10px] font-semibold text-[#5ba897]">
                                Current
                              </span>
                            )}
                          </div>
                          {/* Subtitle: only in collapsed mode or when no preview panel */}
                          {(layoutMode === "collapsed" || !item.subtitle) && item.subtitle && (
                            <span className="mt-0.5 line-clamp-1 text-[12px] leading-relaxed text-black/40 dark:text-white/40">
                              {isFiltering ? highlightText(item.subtitle, query) : item.subtitle}
                            </span>
                          )}
                        </div>

                        {/* Date + hover actions — fixed right */}
                        <div data-actions className="absolute right-3 top-3 flex shrink-0 items-center gap-1">
                          {/* Date label — hidden when hover actions show */}
                          <span className="text-[11px] text-black/30 group-hover:hidden dark:text-white/30">
                            {formatRelativeDate(item.updated_at)}
                          </span>
                          {/* Hover actions */}
                          <div className="hidden items-center gap-0.5 group-hover:flex">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                void handleRename(item.id);
                              }}
                              className="rounded-md p-1.5 hover:bg-black/10 dark:hover:bg-white/10"
                              title={t("common.rename", "Rename")}
                            >
                              <Edit2 className="h-3 w-3 text-black/50 dark:text-white/50" />
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                void handleArchive(item.id);
                              }}
                              className="rounded-md p-1.5 hover:bg-black/10 dark:hover:bg-white/10"
                              title={t("common.archive", "Archive")}
                            >
                              <Archive className="h-3 w-3 text-black/50 dark:text-white/50" />
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                void handleDelete(item.id);
                              }}
                              className="rounded-md p-1.5 hover:bg-black/10 dark:hover:bg-white/10"
                              title={t("common.delete", "Delete")}
                            >
                              <Trash2 className="h-3 w-3 text-[#d66d75]" />
                            </button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Right panel: elevated chat preview (expanded mode only) */}
          {layoutMode === "expanded" && (
            <div className="hidden w-[45%] flex-col overflow-y-auto md:flex">
              {isLoadingPreview ? (
                <div className="flex flex-1 items-center justify-center">
                  <Loader2 className="h-5 w-5 animate-spin text-black/15 dark:text-white/15" />
                </div>
              ) : hoveredId && previewMessages.length > 0 ? (
                <div className="flex flex-1 flex-col gap-3 p-4">
                  {hydrateMessagesFromApi(previewMessages).messages.map((msg) => (
                    <div key={msg.id} className="pointer-events-none opacity-90">
                      <ChatMessage message={msg} isLatest={false} />
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex flex-1 flex-col items-center justify-center p-6 text-center">
                  <p className="text-[13px] text-black/30 dark:text-white/30">
                    {hoveredId ? "No messages in this conversation" : "Hover over a conversation to preview"}
                  </p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer: count + layout toggle */}
        <div className="flex items-center justify-between border-t border-black/5 px-4 py-2 dark:border-white/5">
          <span className="text-[11px] text-black/30 dark:text-white/30">
            {displayItems.length > 0 && `${displayItems.length} conversation${displayItems.length !== 1 ? "s" : ""}`}
          </span>
          <button
            onClick={toggleLayout}
            className="flex items-center gap-1.5 rounded-md px-2 py-1 text-[11px] text-black/40 hover:bg-black/5 dark:text-white/40 dark:hover:bg-white/5"
          >
            {layoutMode === "expanded" ? (
              <>
                <Minimize2 className="h-3 w-3" />
                Collapse
              </>
            ) : (
              <>
                <Maximize2 className="h-3 w-3" />
                Expand
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
