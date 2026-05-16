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
} from "lucide-react";
import { useTranslation } from "react-i18next";
import {
  searchGlobal,
  patchConversation,
  deleteConversation as apiDeleteConversation,
  type SearchItem,
} from "@/lib/argus-api";

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

// ─── Highlight helper ─────────────────────────────────────────────────────────

/**
 * Highlight search keywords in text using Dusty Gold (#c2a44d).
 * Returns an array of React nodes with <mark> tags around matches.
 */
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
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

// ─── Group results by date ────────────────────────────────────────────────────

function groupSearchResults(items: SearchItem[]) {
  const groups: { label: string; items: SearchItem[] }[] = [];
  const buckets = new Map<string, SearchItem[]>();

  for (const item of items) {
    const label = formatRelativeDate(item.updated_at);
    if (!buckets.has(label)) {
      buckets.set(label, []);
      groups.push({ label, items: buckets.get(label)! });
    }
    buckets.get(label)!.push(item);
  }

  return groups;
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function ChatOmniSearch({
  onClose,
  onOpenConversation,
  activeConversationId,
  onMutated,
}: ChatOmniSearchProps) {
  const { t } = useTranslation();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchItem[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [layoutMode, setLayoutMode] = useState<LayoutMode>(() => {
    if (typeof window === "undefined") return "expanded";
    return (localStorage.getItem("argus:omni_search_layout") as LayoutMode) ?? "expanded";
  });
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Filter to chats only
  const chatResults = useMemo(
    () => results.filter((item) => item.type === "chat"),
    [results],
  );

  const groupedResults = useMemo(
    () => groupSearchResults(chatResults),
    [chatResults],
  );

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
      setResults([]);
      setIsSearching(false);
      return;
    }

    setIsSearching(true);
    debounceRef.current = setTimeout(async () => {
      try {
        const { items } = await searchGlobal({ q: trimmed, limit: 30 });
        setResults(items);
      } catch (err) {
        console.error("Search failed", err);
        setResults([]);
      } finally {
        setIsSearching(false);
      }
    }, 200);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query]);

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
      const item = chatResults.find((r) => r.id === id);
      if (!item) return;
      const newTitle = prompt("Rename conversation:", item.title);
      if (!newTitle?.trim()) return;
      try {
        await patchConversation(id, { title: newTitle.trim() });
        setResults((prev) =>
          prev.map((r) => (r.id === id ? { ...r, title: newTitle.trim() } : r)),
        );
        onMutated?.();
      } catch (err) {
        console.error("Failed to rename", err);
      }
    },
    [chatResults, onMutated],
  );

  const handleArchive = useCallback(
    async (id: string) => {
      try {
        await patchConversation(id, { archived: true });
        setResults((prev) => prev.filter((r) => r.id !== id));
        onMutated?.();
      } catch (err) {
        console.error("Failed to archive", err);
      }
    },
    [onMutated],
  );

  const handleDelete = useCallback(
    async (id: string) => {
      try {
        await apiDeleteConversation(id);
        setResults((prev) => prev.filter((r) => r.id !== id));
        onMutated?.();
      } catch (err) {
        console.error("Failed to delete", err);
      }
    },
    [onMutated],
  );

  const handleSelectChat = useCallback(
    (item: SearchItem) => {
      const convId = item.conversation_id ?? item.id;
      onOpenConversation(convId);
      onClose();
    },
    [onOpenConversation, onClose],
  );

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 sm:p-8">
      {/* Backdrop */}
      <button
        className="absolute inset-0 bg-black/20 backdrop-blur-sm dark:bg-black/60"
        onClick={onClose}
        aria-label="Close search"
      />

      {/* Modal */}
      <div
        className={`relative flex flex-col overflow-hidden rounded-[18px] border border-black/10 bg-white dark:border-white/10 dark:bg-[#1b1d20] transition-all duration-300 ${
          layoutMode === "expanded"
            ? "h-[70vh] w-full max-w-4xl"
            : "h-[60vh] w-full max-w-lg"
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
            className="w-full bg-transparent text-[15px] font-medium text-black outline-none placeholder:text-black/35 dark:text-white dark:placeholder:text-white/35"
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
            {!query.trim() ? (
              <div className="flex flex-col items-center justify-center py-20 text-center">
                <Search className="mb-3 h-8 w-8 text-black/10 dark:text-white/10" />
                <p className="text-[14px] text-black/30 dark:text-white/30">
                  {t("common.search", "Search")} your conversations
                </p>
              </div>
            ) : isSearching ? (
              <div className="flex items-center justify-center py-20">
                <div className="h-5 w-5 animate-spin rounded-full border-2 border-black/10 border-t-black/40 dark:border-white/10 dark:border-t-white/40" />
              </div>
            ) : chatResults.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 text-center">
                <p className="text-[14px] text-black/30 dark:text-white/30">
                  No results found
                </p>
              </div>
            ) : (
              <div className="flex flex-col gap-4 p-3">
                {groupedResults.map((group) => (
                  <div key={group.label}>
                    <div className="px-2 pb-1.5 pt-1">
                      <span className="text-[11px] font-semibold uppercase tracking-wider text-black/40 dark:text-white/40">
                        {group.label}
                      </span>
                    </div>
                    {group.items.map((item) => (
                      <button
                        key={item.id}
                        onClick={() => handleSelectChat(item)}
                        onMouseEnter={() => setSelectedId(item.id)}
                        className={`group relative flex w-full flex-col gap-1 rounded-[12px] px-3 py-2.5 text-left transition-colors ${
                          selectedId === item.id
                            ? "bg-black/5 dark:bg-white/5"
                            : "hover:bg-black/[0.03] dark:hover:bg-white/[0.03]"
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="truncate text-[14px] font-medium text-black dark:text-white">
                            {highlightText(item.title, query)}
                          </span>
                          <div className="flex shrink-0 items-center gap-1">
                            {activeConversationId === item.id && (
                              <span className="rounded-full bg-[#5ba897]/15 px-2 py-0.5 text-[10px] font-semibold text-[#5ba897]">
                                Current
                              </span>
                            )}
                            <span className="text-[11px] text-black/30 dark:text-white/30">
                              {formatRelativeDate(item.updated_at)}
                            </span>
                          </div>
                        </div>
                        {item.matched_text && (
                          <span className="line-clamp-2 text-[12px] leading-relaxed text-black/50 dark:text-white/50">
                            {highlightText(item.matched_text, query)}
                          </span>
                        )}

                        {/* Hover actions */}
                        <div className="absolute right-2 top-1/2 flex -translate-y-1/2 items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
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
                      </button>
                    ))}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Right panel: preview (expanded mode only) */}
          {layoutMode === "expanded" && (
            <div className="hidden w-[45%] flex-col overflow-y-auto md:flex">
              {selectedId ? (
                <div className="flex flex-1 flex-col items-center justify-center p-6 text-center">
                  <p className="text-[13px] text-black/30 dark:text-white/30">
                    Chat preview will be available when conversation messages are loaded.
                  </p>
                </div>
              ) : (
                <div className="flex flex-1 flex-col items-center justify-center p-6 text-center">
                  <p className="text-[13px] text-black/30 dark:text-white/30">
                    Select a conversation to preview
                  </p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer: layout toggle */}
        <div className="flex items-center justify-between border-t border-black/5 px-4 py-2 dark:border-white/5">
          <span className="text-[11px] text-black/30 dark:text-white/30">
            {chatResults.length > 0 && `${chatResults.length} result${chatResults.length !== 1 ? "s" : ""}`}
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
