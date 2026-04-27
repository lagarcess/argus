"use client";

import { useEffect, useState, useRef } from "react";
import {
  AlertCircle,
  Edit2,
  Layers,
  Menu,
  Pin,
  Plus,
  Search,
  Settings,
  Trash2,
  X,
} from "lucide-react";
import { useTranslation } from "react-i18next";

import {
  listCollections,
  createCollection,
  patchCollection,
  deleteCollection as apiDeleteCollection,
  formatRelativeDate,
  type Collection,
} from "@/lib/argus-api";

// ─── Display type ─────────────────────────────────────────────────────────────

type DisplayCollection = {
  id: string;
  title: string;
  subtitle: string;
  pinned: boolean;
  strategyCount: number;
  dateStr: string;
};

function mapCollection(c: Collection, labels: { today: string; yesterday: string }): DisplayCollection {
  return {
    id: c.id,
    title: c.name,
    subtitle:
      c.strategy_count === 0
        ? "no_strategies"
        : "strategy_count",
    pinned: c.pinned,
    strategyCount: c.strategy_count,
    dateStr: formatRelativeDate(c.updated_at, labels),
  };
}

// ─── Props ────────────────────────────────────────────────────────────────────

type CollectionsViewProps = {
  onMenuClick: () => void;
  onAddClick?: () => void;
  searchText: string;
  onSearchChange: (val: string) => void;
  isSidebarOpen: boolean;
  onTriggerPrompt?: (type: "strategy" | "collection", customPrompt?: string) => void;
};

// ─── Component ────────────────────────────────────────────────────────────────

export default function CollectionsView({
  onMenuClick,
  onAddClick,
  searchText,
  onSearchChange,
  isSidebarOpen,
  onTriggerPrompt,
}: CollectionsViewProps) {
  const { t } = useTranslation();
  const [collections, setCollections] = useState<DisplayCollection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Removed local searchText state
  const [editingId, setEditingId] = useState<string | null>(null);
  const [activeContextMenu, setActiveContextMenu] = useState<string | null>(
    null,
  );
  const [isCreating, setIsCreating] = useState(false);

  const timerRef = useRef<NodeJS.Timeout | null>(null);

  // ── Fetch ──────────────────────────────────────────────────────────────────

  const refreshCollections = () => {
    listCollections(50)
      .then(({ items }) => {
        const dateLabels = { today: t('common.today'), yesterday: t('common.yesterday') };
        setCollections(items.map(c => mapCollection(c, dateLabels)));
      })
      .catch(() => setError(t('collections.error_load')));
  };

  useEffect(() => {
    listCollections(50)
      .then(({ items }) => {
        const dateLabels = { today: t('common.today'), yesterday: t('common.yesterday') };
        setCollections(items.map(c => mapCollection(c, dateLabels)));
        setError(null);
      })
      .catch(() => setError(t('collections.error_load')))
      .finally(() => setLoading(false));
  }, [t]);

  // ── Long press ─────────────────────────────────────────────────────────────

  const handlePointerDown = (id: string) => {
    timerRef.current = setTimeout(() => {
      setActiveContextMenu(id);
      if (window.navigator?.vibrate) window.navigator.vibrate(50);
    }, 500);
  };

  const handlePointerUp = () => {
    if (timerRef.current) clearTimeout(timerRef.current);
  };

  // ── Mutations ──────────────────────────────────────────────────────────────

  const handleCreate = async () => {
    setIsCreating(true);
    try {
      const { collection } = await createCollection();
      const dateLabels = { today: t('common.today'), yesterday: t('common.yesterday') };
      const display = mapCollection(collection, dateLabels);
      setCollections((prev) => [display, ...prev]);
      // Immediately enter rename mode for the new collection
      setEditingId(display.id);
    } catch {
      // No-op — silently fail for now
    } finally {
      setIsCreating(false);
    }
  };

  const handleRename = async (id: string, newName: string) => {
    const trimmed = newName.trim();
    if (!trimmed) {
      setEditingId(null);
      return;
    }
    // Optimistic update
    setCollections((prev) =>
      prev.map((c) => (c.id === id ? { ...c, title: trimmed } : c)),
    );
    setEditingId(null);
    try {
      await patchCollection(id, { name: trimmed });
    } catch {
      refreshCollections();
    }
  };

  const handleTogglePin = async (id: string) => {
    const target = collections.find((c) => c.id === id);
    if (!target) return;
    const newPinned = !target.pinned;
    setCollections((prev) =>
      prev.map((c) => (c.id === id ? { ...c, pinned: newPinned } : c)),
    );
    setActiveContextMenu(null);
    try {
      await patchCollection(id, { pinned: newPinned });
    } catch {
      refreshCollections();
    }
  };

  const handleDelete = async (id: string) => {
    setCollections((prev) => prev.filter((c) => c.id !== id));
    setActiveContextMenu(null);
    try {
      await apiDeleteCollection(id);
    } catch {
      refreshCollections();
    }
  };

  // ── Derived state ──────────────────────────────────────────────────────────

  const sorted = [...collections]
    .filter((c) => c.title.toLowerCase().includes(searchText.toLowerCase()))
    .sort((a, b) => {
      if (a.pinned && !b.pinned) return -1;
      if (!a.pinned && b.pinned) return 1;
      return 0;
    });

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="flex h-[100dvh] w-full max-w-5xl mx-auto flex-col overflow-hidden bg-[#f9f9f9] text-black dark:bg-[#141517] dark:text-white relative">
      {/* Context menu backdrop */}
      {activeContextMenu && (
        <div
          className="fixed inset-0 z-40 touch-none pointer-events-auto"
          onPointerDown={(e) => {
            e.stopPropagation();
            setActiveContextMenu(null);
            e.preventDefault();
          }}
        />
      )}

      {/* Global Header handled by ChatInterface */}

      {/* List */}
      <div className="argus-scrollbar flex-1 overflow-y-auto px-5 pt-24 pb-32">
        {loading ? (
          <div className="flex flex-col gap-3 animate-pulse">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="w-full h-[80px] rounded-[20px] bg-black/5 dark:bg-white/5"
              />
            ))}
          </div>
        ) : error ? (
          <div className="mt-16 flex flex-col items-center gap-3 text-center text-black/55 dark:text-white/55">
            <AlertCircle className="h-8 w-8" />
            <p className="max-w-sm text-[15px] leading-6">{error}</p>
              <button
                onClick={() => refreshCollections()}
                className="mt-2 rounded-full border border-black/10 dark:border-white/10 px-4 py-2 text-[14px] font-medium hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
              >
                {t('common.retry')}
              </button>
          </div>
        ) : sorted.length === 0 ? (
          <div className="mt-8 flex flex-col items-center gap-8">
            <div className="flex flex-col items-center gap-3 text-center text-black/55 dark:text-white/55">
              <Layers className="h-8 w-8" />
              <p className="max-w-sm text-[15px] leading-6">
                {searchText
                  ? t('collections.no_match')
                  : t('collections.empty_state')}
              </p>
            </div>

            {!searchText && (
                <div className="grid w-full grid-cols-1 gap-4 md:grid-cols-2">
                  {(t('collections.suggestions', { returnObjects: true }) as Array<{title: string, desc: string, prompt: string}>).map((recipe, idx) => (
                    <button
                      key={idx}
                      onClick={() => onTriggerPrompt?.("collection", recipe.prompt)}
                      className="group flex flex-col items-start gap-2 rounded-[24px] border border-black/5 bg-white p-5 text-left transition-all hover:border-black/10 dark:border-white/5 dark:bg-[#1f2225] dark:hover:border-white/10"
                    >
                      <div className="rounded-full bg-black/[0.03] p-2 dark:bg-white/[0.03]">
                        <Layers className="h-4 w-4 text-black/40 dark:text-white/40" />
                      </div>
                      <h3 className="text-[15px] font-semibold text-black dark:text-white">
                        {recipe.title}
                      </h3>
                      <p className="text-[13px] leading-relaxed text-black/45 dark:text-white/45">
                        {recipe.desc}
                      </p>
                    </button>
                  ))}
                </div>
            )}
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {sorted.map((collection) => {
              const isContextOpen = activeContextMenu === collection.id;

              return (
                <div key={collection.id} className="relative">
                  {/* Context menu overlay */}
                  {isContextOpen && (
                    <div className="absolute inset-x-0 top-0 h-[72px] z-50 animate-in fade-in zoom-in-95 duration-200 bg-white dark:bg-[#1f2225] border border-black/10 dark:border-white/10 rounded-t-[20px] flex items-center justify-center gap-4 px-4">
                      <button
                        onClick={() => void handleTogglePin(collection.id)}
                        className="flex flex-col items-center gap-1.5 hover:opacity-70 transition-opacity"
                      >
                        <div className="w-10 h-10 rounded-full bg-black/5 dark:bg-white/5 flex items-center justify-center">
                          <Pin className="w-4 h-4" />
                        </div>
                        <span className="text-[11px] font-medium tracking-tight">
                          {collection.pinned ? t('common.unpin') : t('common.pin')}
                        </span>
                      </button>
                      <button
                        onClick={() => {
                          setActiveContextMenu(null);
                          setEditingId(collection.id);
                        }}
                        className="flex flex-col items-center gap-1.5 hover:opacity-70 transition-opacity"
                      >
                        <div className="w-10 h-10 rounded-full bg-black/5 dark:bg-white/5 flex items-center justify-center">
                          <Edit2 className="w-4 h-4" />
                        </div>
                        <span className="text-[11px] font-medium tracking-tight">
                          {t('common.rename')}
                        </span>
                      </button>
                      <button
                        onClick={() => void handleDelete(collection.id)}
                        className="flex flex-col items-center gap-1.5 hover:opacity-70 transition-opacity text-red-500"
                      >
                        <div className="w-10 h-10 rounded-full bg-red-500/10 flex items-center justify-center">
                          <Trash2 className="w-4 h-4" />
                        </div>
                        <span className="text-[11px] font-medium tracking-tight">
                          {t('common.delete')}
                        </span>
                      </button>
                    </div>
                  )}

                  <article
                    className={`rounded-[20px] border border-black/10 bg-white p-5 dark:border-white/10 dark:bg-[#1f2225] transition-transform duration-150 select-none ${ isContextOpen ? "scale-[0.98]" : "" }`}
                    onPointerDown={() => handlePointerDown(collection.id)}
                    onPointerUp={handlePointerUp}
                    onPointerLeave={handlePointerUp}
                    onPointerCancel={handlePointerUp}
                    onTouchMove={handlePointerUp}
                    onContextMenu={(e) => e.preventDefault()}
                  >
                    {editingId === collection.id ? (
                      <input
                        type="text"
                        defaultValue={collection.title}
                        autoFocus
                        onBlur={(e) =>
                          void handleRename(
                            collection.id,
                            e.target.value.trim() || collection.title,
                          )
                        }
                        onKeyDown={(e) => {
                          if (e.key === "Enter")
                            void handleRename(
                              collection.id,
                              e.currentTarget.value.trim() || collection.title,
                            );
                          if (e.key === "Escape") setEditingId(null);
                        }}
                        className="w-full text-[17px] font-medium text-black dark:text-white bg-transparent border-b border-black/20 dark:border-white/20 focus:outline-none focus:border-black dark:focus:border-white"
                        onClick={(e) => e.stopPropagation()}
                      />
                    ) : (
                      <h2 className="text-[17px] font-medium tracking-tight flex items-center gap-2">
                        {collection.title}
                        {collection.pinned && (
                          <Pin
                            className="w-3 h-3 text-black/30 dark:text-white/30 fill-black/30 dark:fill-white/30"
                            style={{ transform: "rotate(45deg)" }}
                          />
                        )}
                      </h2>
                    )}
                     <p className="mt-1 text-[13px] text-black/50 dark:text-white/50">
                      {collection.subtitle === "no_strategies"
                        ? t('collections.no_strategies')
                        : t('collections.strategy_count', { count: collection.strategyCount })} · {collection.dateStr}
                    </p>
                  </article>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Bottom bar */}
      <div
        className={`absolute bottom-6 inset-x-0 w-full px-4 z-20 pointer-events-none transition-all duration-300 ${ isSidebarOpen ? "opacity-0 translate-y-4 pointer-events-none" : "opacity-100 translate-y-0" }`}
      >
        <div className="pointer-events-auto max-w-3xl mx-auto flex items-center gap-4 transition-all duration-300 opacity-50 hover:opacity-100 focus-within:opacity-100 group">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-5 top-1/2 h-5 w-5 -translate-y-1/2 text-black/40 dark:text-white/40" />
            <input
              type="text"
              value={searchText}
              onChange={(e) => onSearchChange(e.target.value)}
              placeholder={t('collections.search_placeholder')}
              className="w-full h-[52px] pl-[48px] pr-12 rounded-full border border-black/10 bg-white/50 dark:bg-[#1f2225]/50 backdrop-blur-xl focus:bg-white dark:focus:bg-[#1f2225] focus:outline-none focus:ring-2 focus:ring-black/5 dark:focus:ring-white/5 transition-all text-[15px] text-black dark:text-white placeholder:text-black/40 dark:placeholder:text-white/40"
            />
            {searchText && (
              <button
                onClick={() => onSearchChange("")}
                className="absolute right-4 top-1/2 -translate-y-1/2 w-6 h-6 flex items-center justify-center rounded-full bg-black/10 dark:bg-white/10 text-black/60 dark:text-white/60 hover:bg-black/20 dark:hover:bg-white/20 transition-colors"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
