"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
} from "react";
import {
  Archive,
  ChevronRight,
  Edit2,
  Loader2,
  Maximize2,
  MessageSquare,
  Minimize2,
  Search,
  Trash2,
  X,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Tooltip } from "@/components/ui/Tooltip";
import {
  deleteConversation as apiDeleteConversation,
  listHistory,
  patchConversation,
  searchGlobal,
  type HistoryItem,
  type SearchItem,
} from "@/lib/argus-api";
import {
  commandPaletteDecisionStateFallback,
  commandPaletteItemFromHistory,
  commandPaletteItemFromSearch,
  commandPaletteOpenFallback,
  commandPaletteOpenLabelKey,
  commandPalettePreviewFields,
  commandPaletteSelectedPreview,
  commandPaletteTypeFallback,
  commandPaletteTypeLabelKey,
  type CommandPaletteDisplayItem,
} from "@/lib/command-palette-items";

type ChatCommandPaletteProps = {
  onClose: () => void;
  onOpenConversation: (conversationId: string) => void;
  activeConversationId: string | null;
  onMutated?: () => void;
  onConversationRemoved?: (conversationId: string) => void;
};

type LayoutMode = "expanded" | "collapsed";

function formatRelativeDate(
  value: string,
  t: ReturnType<typeof useTranslation>["t"],
  locale: string,
) {
  const date = new Date(value);
  const now = new Date();
  const todayStart = new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate(),
  ).getTime();
  const time = date.getTime();

  if (time >= todayStart) return t("chat.history.today", "Today");
  if (time >= todayStart - 86400000)
    return t("chat.history.yesterday", "Yesterday");
  return new Intl.DateTimeFormat(locale, {
    month: "short",
    day: "numeric",
  }).format(date);
}

function dateGroup(value: string, t: ReturnType<typeof useTranslation>["t"]) {
  const date = new Date(value);
  const now = new Date();
  const todayStart = new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate(),
  ).getTime();
  const time = date.getTime();

  if (time >= todayStart) return t("chat.history.today", "Today");
  if (time >= todayStart - 86400000)
    return t("chat.history.yesterday", "Yesterday");
  if (time >= todayStart - 86400000 * 6)
    return t("chat.history.last_7_days", "Last 7 days");
  if (time >= todayStart - 86400000 * 29)
    return t("chat.history.last_30_days", "Last 30 days");
  return t("chat.history.earlier", "Earlier");
}

function groupItems(
  items: CommandPaletteDisplayItem[],
  t: ReturnType<typeof useTranslation>["t"],
) {
  const groups: { label: string; items: CommandPaletteDisplayItem[] }[] = [];
  const buckets = new Map<string, CommandPaletteDisplayItem[]>();

  for (const item of items) {
    const label = dateGroup(item.updatedAt, t);
    const existing = buckets.get(label);
    if (existing) {
      existing.push(item);
    } else {
      const bucket = [item];
      buckets.set(label, bucket);
      groups.push({ label, items: bucket });
    }
  }

  return groups;
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function highlightText(text: string, query: string): ReactNode {
  const trimmed = query.trim();
  if (!trimmed) return text;

  const parts = text.split(new RegExp(`(${escapeRegExp(trimmed)})`, "gi"));
  return parts.map((part, index) =>
    part.toLowerCase() === trimmed.toLowerCase() ? (
      <mark
        key={`${part}-${index}`}
        className="rounded-sm bg-[#c2a44d]/20 px-0.5 font-semibold text-[#c2a44d]"
      >
        {part}
      </mark>
    ) : (
      <span key={`${part}-${index}`}>{part}</span>
    ),
  );
}

function rawConversationId(item: HistoryItem | SearchItem) {
  return item.conversation_id ?? item.id;
}

export default function ChatCommandPalette({
  onClose,
  onOpenConversation,
  activeConversationId,
  onMutated,
  onConversationRemoved,
}: ChatCommandPaletteProps) {
  const { t, i18n } = useTranslation();
  const [query, setQuery] = useState("");
  const [recentItems, setRecentItems] = useState<HistoryItem[]>([]);
  const [searchResults, setSearchResults] = useState<SearchItem[]>([]);
  const [searchNextCursor, setSearchNextCursor] = useState<string | null>(null);
  const [isColdStartLoading, setIsColdStartLoading] = useState(true);
  const [isSearching, setIsSearching] = useState(false);
  const [isLoadingMoreSearch, setIsLoadingMoreSearch] = useState(false);
  const [previewItem, setPreviewItem] =
    useState<CommandPaletteDisplayItem | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");
  const [isSubmittingEdit, setIsSubmittingEdit] = useState(false);
  const [pendingDeleteItem, setPendingDeleteItem] =
    useState<CommandPaletteDisplayItem | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [layoutMode, setLayoutMode] = useState<LayoutMode>("expanded");
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    inputRef.current?.focus();
    const saved = window.localStorage.getItem("argus:command_palette_layout");
    if (saved === "expanded" || saved === "collapsed") setLayoutMode(saved);
  }, []);

  useEffect(() => {
    setIsColdStartLoading(true);
    listHistory({ limit: 50 })
      .then(({ items }) => {
        setRecentItems(items.filter((item) => item.type === "chat"));
      })
      .catch(() => setRecentItems([]))
      .finally(() => setIsColdStartLoading(false));
  }, []);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);

    const trimmed = query.trim();
    setPreviewItem(null);
    if (!trimmed) {
      setSearchResults([]);
      setSearchNextCursor(null);
      setIsSearching(false);
      return;
    }

    setIsSearching(true);
    debounceRef.current = setTimeout(() => {
      searchGlobal({ q: trimmed, limit: 30 })
        .then(({ items, next_cursor }) => {
          setSearchResults(items);
          setSearchNextCursor(next_cursor);
        })
        .catch(() => {
          setSearchResults([]);
          setSearchNextCursor(null);
        })
        .finally(() => setIsSearching(false));
    }, 200);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query]);

  const isFiltering = query.trim().length > 0;
  const displayItems = useMemo(() => {
    const items = isFiltering
      ? searchResults.map((item) =>
          commandPaletteItemFromSearch(item, {
            decisionStateLabel: (state) =>
              t(
                `chat.result_card.decision_states.${state}`,
                commandPaletteDecisionStateFallback(state),
              ),
          }),
        )
      : recentItems.map(commandPaletteItemFromHistory);
    return items.filter((item): item is CommandPaletteDisplayItem =>
      Boolean(item),
    );
  }, [isFiltering, recentItems, searchResults, t]);
  const groupedItems = useMemo(
    () => groupItems(displayItems, t),
    [displayItems, t],
  );
  const selectedPreview = commandPaletteSelectedPreview(previewItem, displayItems);
  const selectedPreviewFields = useMemo(
    () =>
      selectedPreview
        ? commandPalettePreviewFields(selectedPreview, {
            decisionStateLabel: (state) =>
              t(
                `chat.result_card.decision_states.${state}`,
                commandPaletteDecisionStateFallback(state),
              ),
          })
        : [],
    [selectedPreview, t],
  );

  const updateLocalTitle = useCallback(
    (conversationId: string, title: string) => {
      setRecentItems((current) =>
        current.map((item) =>
          rawConversationId(item) === conversationId
            ? { ...item, title }
            : item,
        ),
      );
      setSearchResults((current) =>
        current.map((item) =>
          rawConversationId(item) === conversationId
            ? { ...item, title }
            : item,
        ),
      );
      setPreviewItem((current) =>
        current?.conversationId === conversationId
          ? { ...current, title }
          : current,
      );
    },
    [],
  );

  const removeLocalConversation = useCallback((conversationId: string) => {
    setRecentItems((current) =>
      current.filter((item) => rawConversationId(item) !== conversationId),
    );
    setSearchResults((current) =>
      current.filter((item) => rawConversationId(item) !== conversationId),
    );
    setPreviewItem((current) =>
      current?.conversationId === conversationId ? null : current,
    );
  }, []);

  const loadMoreSearch = async () => {
    const trimmed = query.trim();
    if (!trimmed || !searchNextCursor || isLoadingMoreSearch) return;

    setIsLoadingMoreSearch(true);
    try {
      const { items, next_cursor } = await searchGlobal({
        q: trimmed,
        limit: 30,
        cursor: searchNextCursor,
      });
      setSearchResults((current) => {
        const seen = new Set(current.map((item) => `${item.type}:${item.id}`));
        const next = [...current];
        for (const item of items) {
          const key = `${item.type}:${item.id}`;
          if (!seen.has(key)) {
            seen.add(key);
            next.push(item);
          }
        }
        return next;
      });
      setSearchNextCursor(next_cursor);
    } finally {
      setIsLoadingMoreSearch(false);
    }
  };

  const openSourceConversation = useCallback(
    (item: CommandPaletteDisplayItem) => {
      if (!item.conversationId) return;
      onOpenConversation(item.conversationId);
      onClose();
    },
    [onClose, onOpenConversation],
  );

  const activateItem = useCallback(
    (item: CommandPaletteDisplayItem) => {
      if (item.activation === "select_preview") {
        setPreviewItem(item);
        return;
      }
      openSourceConversation(item);
    },
    [openSourceConversation],
  );

  const startRename = useCallback((item: CommandPaletteDisplayItem) => {
    if (!item.canManageConversation || !item.conversationId) return;
    setEditingId(item.conversationId);
    setEditingTitle(item.title.slice(0, 80));
    setPreviewItem(item);
  }, []);

  const cancelRename = useCallback(() => {
    setEditingId(null);
    setEditingTitle("");
  }, []);

  const handleRenameSave = useCallback(
    async (item: CommandPaletteDisplayItem) => {
      if (isSubmittingEdit) return;
      if (!item.canManageConversation || !item.conversationId) return;

      const nextTitle = editingTitle.trim();
      if (!nextTitle || nextTitle === item.title) {
        cancelRename();
        return;
      }

      setIsSubmittingEdit(true);
      try {
        await patchConversation(item.conversationId, { title: nextTitle });
        updateLocalTitle(item.conversationId, nextTitle);
        onMutated?.();
        setEditingId(null);
        setEditingTitle("");
      } finally {
        setIsSubmittingEdit(false);
      }
    },
    [cancelRename, editingTitle, isSubmittingEdit, onMutated, updateLocalTitle],
  );

  const handleArchive = useCallback(
    async (item: CommandPaletteDisplayItem) => {
      if (!item.canManageConversation || !item.conversationId) return;
      removeLocalConversation(item.conversationId);
      onConversationRemoved?.(item.conversationId);
      await patchConversation(item.conversationId, { archived: true });
      onMutated?.();
    },
    [onConversationRemoved, onMutated, removeLocalConversation],
  );

  const handleDelete = useCallback((item: CommandPaletteDisplayItem) => {
    if (!item.canManageConversation) return;
    setPendingDeleteItem(item);
  }, []);

  const handleCancelDelete = useCallback(() => {
    if (!isDeleting) setPendingDeleteItem(null);
  }, [isDeleting]);

  const handleConfirmDelete = useCallback(async () => {
    if (!pendingDeleteItem || isDeleting) return;
    if (!pendingDeleteItem.conversationId) return;

    setIsDeleting(true);
    removeLocalConversation(pendingDeleteItem.conversationId);
    onConversationRemoved?.(pendingDeleteItem.conversationId);
    try {
      await apiDeleteConversation(pendingDeleteItem.conversationId);
      onMutated?.();
      setPendingDeleteItem(null);
    } finally {
      setIsDeleting(false);
    }
  }, [
    isDeleting,
    onConversationRemoved,
    onMutated,
    pendingDeleteItem,
    removeLocalConversation,
  ]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        if (editingId) {
          cancelRename();
          return;
        }
        onClose();
        return;
      }
      if (!editingId && event.key === "Enter" && selectedPreview) {
        event.preventDefault();
        activateItem(selectedPreview);
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [activateItem, cancelRename, editingId, onClose, selectedPreview]);

  const toggleLayout = () => {
    setLayoutMode((current) => {
      const next = current === "expanded" ? "collapsed" : "expanded";
      window.localStorage.setItem("argus:command_palette_layout", next);
      return next;
    });
  };

  const isLoading = isFiltering ? isSearching : isColdStartLoading;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 sm:p-8">
      <button
        type="button"
        className="absolute inset-0 bg-black/20 backdrop-blur-sm dark:bg-black/60"
        onClick={onClose}
        aria-label={t("command_palette.close", "Close search")}
      />

      <div
        className={`relative flex flex-col overflow-hidden rounded-[18px] border border-black/10 bg-white transition-all duration-300 dark:border-white/10 dark:bg-[#1b1d20] ${
          layoutMode === "expanded"
            ? "h-[85vh] w-[96vw] max-w-6xl"
            : "h-[65vh] w-full max-w-lg"
        }`}
      >
        <div className="flex items-center gap-3 border-b border-black/5 px-5 py-3.5 dark:border-white/5">
          <Search className="h-4 w-4 shrink-0 text-black/30 dark:text-white/30" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t("command_palette.search_placeholder", "Search Argus...")}
            className="w-full bg-transparent font-display text-[15px] font-medium text-black outline-none placeholder:text-black/35 dark:text-white dark:placeholder:text-white/35"
          />
          {query && (
            <button
              type="button"
              onClick={() => setQuery("")}
              className="shrink-0 rounded-full p-1 hover:bg-black/5 dark:hover:bg-white/10"
              aria-label="Clear search"
            >
              <X className="h-3.5 w-3.5 text-black/40 dark:text-white/40" />
            </button>
          )}
        </div>

        <div className="flex flex-1 flex-col overflow-hidden md:flex-row">
          <div
            className={`flex-1 overflow-y-auto ${
              layoutMode === "expanded"
                ? "border-b border-black/5 dark:border-white/5 md:border-b-0 md:border-r"
                : ""
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
                  {isFiltering
                    ? t("command_palette.no_results", "No results found")
                    : t(
                        "command_palette.no_conversations",
                        "No conversations yet",
                      )}
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
                    {group.items.map((item) => {
                      const isCurrent =
                        item.type === "chat" &&
                        activeConversationId === item.conversationId;
                      const isEditing = editingId === item.conversationId;
                      const handleRowKeyDown = (
                        event: ReactKeyboardEvent<HTMLDivElement>,
                      ) => {
                        if (isEditing) return;
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          activateItem(item);
                        }
                      };
                      return (
                        <div
                          key={`${item.source}:${item.id}`}
                          onClick={() => activateItem(item)}
                          onKeyDown={handleRowKeyDown}
                          onMouseEnter={() => setPreviewItem(item)}
                          onFocus={() => setPreviewItem(item)}
                          role="button"
                          tabIndex={0}
                          className={`group relative flex w-full items-start gap-2 rounded-[12px] px-3 py-2.5 text-left transition-colors ${
                            selectedPreview?.id === item.id &&
                            selectedPreview.type === item.type
                              ? "bg-black/5 dark:bg-white/5"
                              : "hover:bg-black/[0.03] dark:hover:bg-white/[0.03]"
                          }`}
                        >
                          <div className="min-w-0 flex-1 pr-24">
                            <div className="flex items-center gap-2">
                              {isEditing ? (
                                <input
                                  autoFocus
                                  value={editingTitle}
                                  maxLength={80}
                                  onChange={(event) =>
                                    setEditingTitle(event.target.value)
                                  }
                                  onClick={(event) => event.stopPropagation()}
                                  onFocus={(event) =>
                                    event.currentTarget.select()
                                  }
                                  onBlur={() => {
                                    void handleRenameSave(item);
                                  }}
                                  onKeyDown={(event) => {
                                    if (event.key === "Enter") {
                                      event.preventDefault();
                                      event.stopPropagation();
                                      void handleRenameSave(item);
                                    }
                                    if (event.key === "Escape") {
                                      event.preventDefault();
                                      event.stopPropagation();
                                      cancelRename();
                                    }
                                  }}
                                  className="min-w-0 flex-1 rounded-md border border-black/10 bg-white px-2 py-1 font-display text-[14px] font-medium text-black outline-none focus:border-black/30 dark:border-white/10 dark:bg-[#24272b] dark:text-white dark:focus:border-white/30"
                                  aria-label={t(
                                    "command_palette.rename_conversation",
                                    "Rename conversation",
                                  )}
                                />
                              ) : (
                                <span className="truncate font-display text-[14px] font-medium text-black dark:text-white">
                                  {highlightText(item.title, query)}
                                </span>
                              )}
                              {isCurrent && (
                                <span className="shrink-0 rounded-full bg-[#5ba897]/15 px-2 py-0.5 text-[10px] font-semibold text-[#5ba897]">
                                  {t("common.current", "Current")}
                                </span>
                              )}
                              <span className="shrink-0 rounded-full border border-black/8 px-2 py-0.5 text-[10px] font-semibold text-black/40 dark:border-white/10 dark:text-white/40">
                                {t(
                                  commandPaletteTypeLabelKey(item.type),
                                  commandPaletteTypeFallback(item.type),
                                )}
                              </span>
                            </div>
                            {item.snippet && (
                              <span className="mt-0.5 line-clamp-1 text-[12px] leading-relaxed text-black/40 dark:text-white/40">
                                {highlightText(item.snippet, query)}
                              </span>
                            )}
                          </div>
                          <span className="absolute right-3 top-3 text-[11px] text-black/30 dark:text-white/30">
                            {formatRelativeDate(
                              item.updatedAt,
                              t,
                              i18n.language,
                            )}
                          </span>
                          {!isEditing && item.canManageConversation && (
                            <div
                              className="absolute bottom-2 right-2 flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100"
                              data-row-action
                            >
                              <Tooltip
                                content={t("common.rename", "Rename")}
                                side="top"
                                delay={120}
                              >
                                <button
                                  type="button"
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    startRename(item);
                                  }}
                                  className="rounded-full p-1.5 text-black/45 transition-colors hover:bg-black/5 hover:text-black dark:text-white/45 dark:hover:bg-white/10 dark:hover:text-white"
                                  aria-label={t(
                                    "command_palette.rename_conversation",
                                    "Rename conversation",
                                  )}
                                >
                                  <Edit2 className="h-3.5 w-3.5" />
                                </button>
                              </Tooltip>
                              <Tooltip
                                content={t("common.archive", "Archive")}
                                side="top"
                                delay={120}
                              >
                                <button
                                  type="button"
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    void handleArchive(item);
                                  }}
                                  className="rounded-full p-1.5 text-black/45 transition-colors hover:bg-black/5 hover:text-black dark:text-white/45 dark:hover:bg-white/10 dark:hover:text-white"
                                  aria-label={t(
                                    "command_palette.archive_conversation",
                                    "Archive conversation",
                                  )}
                                >
                                  <Archive className="h-3.5 w-3.5" />
                                </button>
                              </Tooltip>
                              <Tooltip
                                content={t("common.delete", "Delete")}
                                side="top"
                                delay={120}
                              >
                                <button
                                  type="button"
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    handleDelete(item);
                                  }}
                                  className="rounded-full p-1.5 text-[#d66d75]/75 transition-colors hover:bg-[#d66d75]/10 hover:text-[#d66d75]"
                                  aria-label={t(
                                    "command_palette.delete_conversation",
                                    "Delete conversation",
                                  )}
                                >
                                  <Trash2 className="h-3.5 w-3.5" />
                                </button>
                              </Tooltip>
                            </div>
                          )}
                          {!isEditing &&
                            !item.canManageConversation &&
                            item.conversationId && (
                              <div
                                className="absolute bottom-2 right-2 flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100"
                                data-row-action
                              >
                                <Tooltip
                                  content={t(
                                    "command_palette.open_source_conversation",
                                    "Open source conversation",
                                  )}
                                  side="top"
                                  delay={120}
                                >
                                  <button
                                    type="button"
                                    onClick={(event) => {
                                      event.stopPropagation();
                                      openSourceConversation(item);
                                    }}
                                    className="rounded-full p-1.5 text-black/45 transition-colors hover:bg-black/5 hover:text-black dark:text-white/45 dark:hover:bg-white/10 dark:hover:text-white"
                                    aria-label={t(
                                      "command_palette.open_source_conversation",
                                      "Open source conversation",
                                    )}
                                  >
                                    <MessageSquare className="h-3.5 w-3.5" />
                                  </button>
                                </Tooltip>
                              </div>
                            )}
                        </div>
                      );
                    })}
                  </div>
                ))}
                {isFiltering && searchNextCursor && (
                  <button
                    type="button"
                    onClick={() => void loadMoreSearch()}
                    disabled={isLoadingMoreSearch}
                    className="mx-2 rounded-[12px] border border-black/10 px-3 py-2 text-[12px] font-medium text-black/60 hover:bg-black/5 disabled:opacity-50 dark:border-white/10 dark:text-white/60 dark:hover:bg-white/5"
                  >
                    {isLoadingMoreSearch
                      ? t("common.loading")
                      : t("common.more", "More")}
                  </button>
                )}
              </div>
            )}
          </div>

          {layoutMode === "expanded" && (
            <div className="flex max-h-[42%] w-full shrink-0 flex-col bg-black/[0.02] p-5 dark:bg-white/[0.02] md:max-h-none md:w-[44%] md:p-6">
              {selectedPreview ? (
                <div className="flex h-full flex-col">
                  <div className="mb-6">
                    <span className="mb-3 inline-flex rounded-full border border-black/8 bg-white/50 px-2.5 py-1 text-[11px] font-semibold text-black/45 dark:border-white/10 dark:bg-white/[0.03] dark:text-white/45">
                      {selectedPreview.type === "chat" &&
                      activeConversationId === selectedPreview.conversationId
                        ? t("common.current", "Current")
                        : t(
                            commandPaletteTypeLabelKey(selectedPreview.type),
                            commandPaletteTypeFallback(selectedPreview.type),
                          )}
                    </span>
                    <h2 className="font-display text-[24px] font-medium leading-tight text-black dark:text-white">
                      {selectedPreview.title}
                    </h2>
                    <p className="mt-2 text-[13px] text-black/40 dark:text-white/40">
                      {formatRelativeDate(
                        selectedPreview.updatedAt,
                        t,
                        i18n.language,
                      )}
                    </p>
                  </div>
                  <div className="rounded-[14px] border border-black/5 bg-white/70 p-4 dark:border-white/10 dark:bg-[#1f2225]/70">
                    <p className="text-[12px] font-semibold uppercase tracking-wider text-black/35 dark:text-white/35">
                      {t("command_palette.preview", "Preview")}
                    </p>
                    {selectedPreviewFields.length > 0 ? (
                      <div className="mt-3 space-y-3">
                        {selectedPreviewFields.map((field) => (
                          <div key={field.id}>
                            <p className="text-[10px] font-semibold uppercase tracking-wider text-black/30 dark:text-white/30">
                              {t(field.labelKey, field.labelFallback)}
                            </p>
                            <p className="mt-1 text-[13px] leading-relaxed text-black/60 dark:text-white/60">
                              {field.value}
                            </p>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="mt-2 text-[14px] leading-relaxed text-black/60 dark:text-white/60">
                        {selectedPreview.snippet ||
                        t(
                          "command_palette.preview_empty",
                          "Open this conversation to view its messages.",
                        )}
                      </p>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => openSourceConversation(selectedPreview)}
                    disabled={!selectedPreview.conversationId}
                    className="mt-auto flex items-center justify-between border-t border-black/5 pt-4 text-left text-[12px] text-black/35 transition-colors hover:text-black disabled:cursor-default disabled:hover:text-black/35 dark:border-white/5 dark:text-white/35 dark:hover:text-white dark:disabled:hover:text-white/35"
                  >
                    <span>
                      {t(
                        commandPaletteOpenLabelKey(selectedPreview),
                        commandPaletteOpenFallback(selectedPreview),
                      )}
                    </span>
                    <ChevronRight className="h-4 w-4" />
                  </button>
                </div>
              ) : (
                <div className="flex flex-1 items-center justify-center text-center">
                  <p className="text-[13px] text-black/30 dark:text-white/30">
                    {t(
                      "command_palette.select_preview",
                      "Select a conversation to preview its metadata.",
                    )}
                  </p>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="flex items-center justify-between border-t border-black/5 px-4 py-2 dark:border-white/5">
          <span className="text-[11px] text-black/30 dark:text-white/30">
            {displayItems.length > 0 &&
              t(
                isFiltering
                  ? "command_palette.result_count"
                  : "command_palette.conversation_count",
                {
                  count: displayItems.length,
                  defaultValue_one: isFiltering
                    ? "{{count}} result"
                    : "{{count}} conversation",
                  defaultValue_other: isFiltering
                    ? "{{count}} results"
                    : "{{count}} conversations",
                },
              )}
          </span>
          <button
            type="button"
            onClick={toggleLayout}
            className="flex items-center gap-1.5 rounded-md px-2 py-1 text-[11px] text-black/40 hover:bg-black/5 dark:text-white/40 dark:hover:bg-white/5"
          >
            {layoutMode === "expanded" ? (
              <>
                <Minimize2 className="h-3 w-3" />
                {t("common.collapse", "Collapse")}
              </>
            ) : (
              <>
                <Maximize2 className="h-3 w-3" />
                {t("common.expand", "Expand")}
              </>
            )}
          </button>
        </div>
        <ConfirmDialog
          isOpen={Boolean(pendingDeleteItem)}
          title={t("sidebar.delete_confirm.title", "Delete this conversation?")}
          description={t(
            "sidebar.delete_confirm.description",
            "This removes “{{title}}” from your visible history.",
            {
              title:
                pendingDeleteItem?.title ??
                t("common.conversation", "Conversation"),
            },
          )}
          confirmLabel={t(
            "sidebar.delete_confirm.confirm",
            "Delete conversation",
          )}
          cancelLabel={t("common.cancel", "Cancel")}
          isBusy={isDeleting}
          onCancel={handleCancelDelete}
          onConfirm={() => void handleConfirmDelete()}
        />
      </div>
    </div>
  );
}
