"use client";

import { useEffect, useState, useRef } from "react";
import {
  AlertCircle,
  Edit2,
  Folder,
  Menu,
  Pin,
  Plus,
  Search,
  Settings,
  Trash2,
  X,
} from "lucide-react";

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

function mapCollection(c: Collection): DisplayCollection {
  return {
    id: c.id,
    title: c.name,
    subtitle:
      c.strategy_count === 0
        ? "No strategies yet"
        : `${c.strategy_count} ${c.strategy_count === 1 ? "strategy" : "strategies"}`,
    pinned: c.pinned,
    strategyCount: c.strategy_count,
    dateStr: formatRelativeDate(c.updated_at),
  };
}

// ─── Props ────────────────────────────────────────────────────────────────────

type CollectionsViewProps = {
  onMenuClick: () => void;
  onSettingsClick?: () => void;
};

// ─── Component ────────────────────────────────────────────────────────────────

export default function CollectionsView({
  onMenuClick,
  onSettingsClick,
}: CollectionsViewProps) {
  const [collections, setCollections] = useState<DisplayCollection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchText, setSearchText] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [activeContextMenu, setActiveContextMenu] = useState<string | null>(
    null,
  );
  const [isCreating, setIsCreating] = useState(false);

  const timerRef = useRef<NodeJS.Timeout | null>(null);

  // ── Fetch ──────────────────────────────────────────────────────────────────

  const refreshCollections = () => {
    listCollections(50)
      .then(({ items }) => setCollections(items.map(mapCollection)))
      .catch(() => setError("Could not load collections. Make sure the API is running."));
  };

  useEffect(() => {
    listCollections(50)
      .then(({ items }) => {
        setCollections(items.map(mapCollection));
        setError(null);
      })
      .catch(() => setError("Could not load collections. Make sure the API is running."))
      .finally(() => setLoading(false));
  }, []);

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
      const display = mapCollection(collection);
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
    <div className="flex h-[100dvh] w-full max-w-3xl flex-col overflow-hidden bg-[#f9f9f9] text-black dark:bg-[#141517] dark:text-white relative">
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

      {/* Header */}
      <div className="flex h-16 shrink-0 items-center justify-between px-4">
        <button
          type="button"
          onClick={onMenuClick}
          className="flex h-11 w-11 items-center justify-center rounded-full border border-black/10 transition-colors hover:bg-black/5 dark:border-white/10 dark:hover:bg-white/10"
          aria-label="Open menu"
        >
          <Menu className="h-5 w-5" />
        </button>
        <h1 className="text-[18px] font-medium tracking-tight">Collections</h1>
        <button
          type="button"
          onClick={() => void handleCreate()}
          disabled={isCreating}
          className="flex h-11 w-11 items-center justify-center rounded-full border border-black/10 transition-colors hover:bg-black/5 dark:border-white/10 dark:hover:bg-white/10 disabled:opacity-40"
          aria-label="Create collection"
        >
          <Plus className="h-5 w-5" />
        </button>
      </div>

      {/* Search */}
      <div className="px-5 pb-4">
        <div className="relative">
          <Search className="pointer-events-none absolute left-5 top-1/2 h-5 w-5 -translate-y-1/2 text-black/40 dark:text-white/40" />
          <input
            type="text"
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            placeholder="Search collections"
            className="h-[52px] w-full rounded-full border border-black/10 bg-white pl-12 pr-12 text-[16px] outline-none transition-colors focus:ring-2 focus:ring-black/10 dark:border-white/10 dark:bg-[#1f2225] dark:focus:ring-white/10"
          />
          {searchText && (
            <button
              onClick={() => setSearchText("")}
              className="absolute right-4 top-1/2 -translate-y-1/2 w-6 h-6 flex items-center justify-center rounded-full bg-black/10 dark:bg-white/10 text-black/60 dark:text-white/60 hover:bg-black/20 dark:hover:bg-white/20 transition-colors"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* List */}
      <div className="argus-scrollbar flex-1 overflow-y-auto px-5 pb-28">
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
              Retry
            </button>
          </div>
        ) : sorted.length === 0 ? (
          <div className="mt-16 flex flex-col items-center gap-3 text-center text-black/55 dark:text-white/55">
            <Folder className="h-8 w-8" />
            <p className="max-w-sm text-[15px] leading-6">
              {searchText
                ? "No collections match your search."
                : "Add strategy to collection or save from chat to see them here."}
            </p>
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
                          {collection.pinned ? "Unpin" : "Pin"}
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
                          Rename
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
                          Delete
                        </span>
                      </button>
                    </div>
                  )}

                  <article
                    className={`rounded-[20px] border border-black/10 bg-white p-5 dark:border-white/10 dark:bg-[#1f2225] transition-transform duration-150 select-none ${
                      isContextOpen ? "scale-[0.98]" : ""
                    }`}
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
                      {collection.subtitle} · {collection.dateStr}
                    </p>
                  </article>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Bottom settings button */}
      <div className="pointer-events-none absolute bottom-6 inset-x-0 px-4">
        <button
          type="button"
          onClick={onSettingsClick}
          className="pointer-events-auto flex h-[52px] w-[52px] items-center justify-center rounded-full border border-black/10 bg-white/70 backdrop-blur-xl transition-colors hover:bg-black/5 dark:border-white/10 dark:bg-[#1f2225]/70 dark:hover:bg-white/5"
          aria-label="Open settings"
        >
          <Settings className="h-5 w-5" />
        </button>
      </div>
    </div>
  );
}
