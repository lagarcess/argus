"use client";

import { useState, useRef, useEffect } from "react";
import {
  Menu,
  Plus,
  ChevronDown,
  Trash2,
  Pin,
  Edit2,
  Search,
  Settings,
  X,
  Play,
  AlertCircle,
  Loader2,
} from "lucide-react";
import { useTranslation } from "react-i18next";

import {
  listStrategies,
  patchStrategy,
  deleteStrategy as apiDeleteStrategy,
  formatRelativeDate,
  runBacktest,
  type Strategy,
  type StrategySurfaceMetricRow,
} from "@/lib/argus-api";

// ─── Display types ────────────────────────────────────────────────────────────

type MetricPill = {
  value: string;
  isPositive: boolean;
};

type DisplayAsset = {
  ticker: string;
  name: string;
  overallProfit: MetricPill;
  maxDrawdown: MetricPill;
  winRate: MetricPill;
};

type DisplayStrategy = {
  id: string;
  name: string;
  dateStr: string;
  isPinned: boolean;
  hasMetrics: boolean;
  assets: DisplayAsset[];
  // Raw strategy kept for re-run
  raw: Strategy;
};

// ─── Mapping helpers ──────────────────────────────────────────────────────────

function parsePill(value: string): MetricPill {
  const isPositive = value.startsWith("+") || (!value.startsWith("-") && parseFloat(value) >= 0);
  return { value, isPositive };
}

function mapStrategyToDisplay(s: Strategy): DisplayStrategy {
  const rows: StrategySurfaceMetricRow[] =
    s.strategy_surface_metrics?.rows ?? [];

  const assets: DisplayAsset[] = rows.map((row) => ({
    ticker: row.symbol,
    name: row.asset_name,
    overallProfit: parsePill(row.values["total_return_pct"] ?? "—"),
    maxDrawdown: parsePill(row.values["max_drawdown_pct"] ?? "—"),
    winRate: parsePill(row.values["win_rate"] ?? "—"),
  }));

  return {
    id: s.id,
    name: s.name,
    dateStr: formatRelativeDate(s.updated_at),
    isPinned: s.pinned,
    hasMetrics: rows.length > 0,
    assets,
    raw: s,
  };
}

// ─── Props ────────────────────────────────────────────────────────────────────

type StrategiesViewProps = {
  onMenuClick: () => void;
  onAddClick?: () => void;
  searchText: string;
  onSearchChange: (val: string) => void;
  isSidebarOpen: boolean;
  onTriggerPrompt?: (type: "strategy" | "collection", customPrompt?: string) => void;
};

// ─── Skeleton ─────────────────────────────────────────────────────────────────

function StrategySkeleton() {
  return (
    <div className="flex flex-col gap-4 animate-pulse">
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          className="w-full h-[72px] rounded-[24px] bg-black/5 dark:bg-white/5"
        />
      ))}
    </div>
  );
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function StrategiesView({
  onMenuClick,
  onAddClick,
  searchText,
  onSearchChange,
  isSidebarOpen,
  onTriggerPrompt,
}: StrategiesViewProps) {
  const { t } = useTranslation();
  const [strategies, setStrategies] = useState<DisplayStrategy[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [activeContextMenu, setActiveContextMenu] = useState<string | null>(
    null,
  );
  const [isScrolling, setIsScrolling] = useState(false);
  const [scrollIndicator, setScrollIndicator] = useState({
    top: 0,
    height: 0,
    visible: false,
  });
  // Removed local searchText state
  const [editingId, setEditingId] = useState<string | null>(null);
  const [runningId, setRunningId] = useState<string | null>(null);

  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const scrollTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // ── Fetch ──────────────────────────────────────────────────────────────────

  const refreshStrategies = async () => {
    try {
      const { items } = await listStrategies({ limit: 50 });
      setStrategies(items.map(mapStrategyToDisplay));
    } catch {
      setError(t('strategies.error_load'));
    }
  };

  useEffect(() => {
    listStrategies({ limit: 50 })
      .then(({ items }) => {
        setStrategies(items.map(mapStrategyToDisplay));
        setError(null);
      })
      .catch(() => {
        setError(t('strategies.error_load'));
      })
      .finally(() => setLoading(false));
  }, [t]);

  useEffect(() => {
    return () => {
      if (scrollTimeoutRef.current) clearTimeout(scrollTimeoutRef.current);
    };
  }, []);

  // ── Scroll indicator ───────────────────────────────────────────────────────

  const handleScrollActivity = (e: React.UIEvent<HTMLDivElement>) => {
    setIsScrolling(true);
    if (scrollTimeoutRef.current) clearTimeout(scrollTimeoutRef.current);
    scrollTimeoutRef.current = setTimeout(() => setIsScrolling(false), 220);
    const { scrollTop, scrollHeight, clientHeight } = e.currentTarget;
    if (scrollHeight > clientHeight) {
      const thumbHeight = Math.max(
        (clientHeight / scrollHeight) * clientHeight,
        28,
      );
      const maxTop = clientHeight - thumbHeight;
      const top =
        (scrollTop / Math.max(scrollHeight - clientHeight, 1)) * maxTop;
      setScrollIndicator({ top, height: thumbHeight, visible: true });
    } else {
      setScrollIndicator({ top: 0, height: 0, visible: false });
    }
  };

  // ── Long press ─────────────────────────────────────────────────────────────

  const handlePointerDown = (id: string, e: React.PointerEvent) => {
    if ((e.target as HTMLElement).closest(".ignore-long-press")) return;
    timerRef.current = setTimeout(() => {
      setActiveContextMenu(id);
      if (window.navigator?.vibrate) window.navigator.vibrate(50);
    }, 500);
  };

  const handlePointerUp = () => {
    if (timerRef.current) clearTimeout(timerRef.current);
  };

  // ── Mutations ──────────────────────────────────────────────────────────────

  const handleDelete = async (id: string) => {
    // Optimistic update
    setStrategies((prev) => prev.filter((s) => s.id !== id));
    setActiveContextMenu(null);
    try {
      await apiDeleteStrategy(id);
    } catch {
      // Rollback not trivial here — just refetch
      refreshStrategies();
    }
  };

  const handleTogglePin = async (id: string) => {
    const target = strategies.find((s) => s.id === id);
    if (!target) return;
    const newPinned = !target.isPinned;
    // Optimistic update
    setStrategies((prev) =>
      prev.map((s) => (s.id === id ? { ...s, isPinned: newPinned } : s)),
    );
    setActiveContextMenu(null);
    try {
      await patchStrategy(id, { pinned: newPinned });
    } catch {
      refreshStrategies();
    }
  };

  const handleRename = async (id: string, newName: string) => {
    const trimmed = newName.trim();
    if (!trimmed) {
      setEditingId(null);
      return;
    }
    // Optimistic update
    setStrategies((prev) =>
      prev.map((s) => (s.id === id ? { ...s, name: trimmed } : s)),
    );
    setEditingId(null);
    try {
      await patchStrategy(id, { name: trimmed });
    } catch {
      refreshStrategies();
    }
  };

  // ── Run (Option B CTA) ─────────────────────────────────────────────────────

  const handleRunStrategy = async (strategy: DisplayStrategy) => {
    setRunningId(strategy.id);
    try {
      await runBacktest({
        template: strategy.raw.template,
        asset_class: strategy.raw.asset_class,
        symbols: strategy.raw.symbols,
        strategy_id: strategy.id,
      });
      // Refetch to get populated metrics
      await refreshStrategies();
      setExpandedId(strategy.id);
    } catch {
      // Surface error inline — non-blocking
    } finally {
      setRunningId(null);
    }
  };

  // ── Derived state ──────────────────────────────────────────────────────────

  const filteredStrategies = strategies.filter((s) =>
    s.name.toLowerCase().includes(searchText.toLowerCase()),
  );

  const sortedStrategies = [...filteredStrategies].sort((a, b) => {
    if (a.isPinned && !b.isPinned) return -1;
    if (!a.isPinned && b.isPinned) return 1;
    return 0;
  });

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col w-full h-[100dvh] max-w-5xl mx-auto overflow-hidden bg-[#f9f9f9] dark:bg-[#141517] relative">
      {/* Global Header handled by ChatInterface */}

      {/* Context menu backdrop */}
      {activeContextMenu && (
        <div
          className="fixed inset-0 z-40 touch-none pointer-events-auto"
          onPointerDown={(e) => {
            e.stopPropagation();
            setActiveContextMenu(null);
            e.preventDefault();
          }}
          onTouchStart={(e) => {
            e.stopPropagation();
            setActiveContextMenu(null);
          }}
        />
      )}

      {/* List */}
      <div className="relative flex-1 min-h-0">
        <div
          onScroll={handleScrollActivity}
          className="argus-scrollbar h-full overflow-y-auto px-6 pt-24 pb-32"
        >
          {loading ? (
            <StrategySkeleton />
          ) : error ? (
            <div className="mt-16 flex flex-col items-center gap-3 text-center text-black/55 dark:text-white/55">
              <AlertCircle className="h-8 w-8" />
              <p className="max-w-sm text-[15px] leading-6">{error}</p>
              <button
                onClick={() => refreshStrategies()}
                className="mt-2 rounded-full border border-black/10 dark:border-white/10 px-4 py-2 text-[14px] font-medium hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
              >
                {t('common.retry')}
              </button>
            </div>
          ) : sortedStrategies.length === 0 ? (
            <div className="mt-12 flex flex-col items-center gap-8">
              <div className="flex flex-col items-center gap-3 text-center text-black/55 dark:text-white/55">
                <p className="max-w-sm text-[15px] leading-6">
                  {searchText
                    ? t('strategies.no_match')
                    : t('strategies.empty_state')}
                </p>
              </div>

              {!searchText && (
                <div className="grid w-full grid-cols-1 md:grid-cols-2 gap-4">
                  {(t('strategies.suggestions', { returnObjects: true }) as Array<{title: string, desc: string, prompt: string}>).map((recipe, idx) => (
                    <button
                      key={idx}
                      onClick={() => onTriggerPrompt?.("strategy", recipe.prompt)}
                      className="group flex flex-col items-start gap-2 rounded-[24px] border border-black/5 bg-white p-5 text-left transition-all hover:border-black/10 hover:shadow-md dark:border-white/5 dark:bg-[#1f2225] dark:hover:border-white/10"
                    >
                      <div className="rounded-full bg-black/[0.03] p-2 dark:bg-white/[0.03]">
                        <Play className="h-4 w-4 text-black/40 dark:text-white/40" />
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
            <div className="flex flex-col gap-4">
              {sortedStrategies.map((strategy) => {
                const isExpanded = expandedId === strategy.id;
                const isContextOpen = activeContextMenu === strategy.id;
                const isRunning = runningId === strategy.id;

                return (
                  <div key={strategy.id} className="flex flex-col">
                    <div
                      className={`relative flex flex-col w-full bg-white dark:bg-[#1f2225] border border-black/10 dark:border-white/10 overflow-hidden transition-all duration-300 rounded-[24px] ${
                        isContextOpen
                          ? "scale-[0.98] shadow-inner bg-black/5 z-50"
                          : "shadow-sm z-10"
                      }`}
                      onPointerDown={(e) => handlePointerDown(strategy.id, e)}
                      onPointerUp={handlePointerUp}
                      onPointerLeave={handlePointerUp}
                      onPointerCancel={handlePointerUp}
                      onTouchMove={handlePointerUp}
                      onContextMenu={(e) => e.preventDefault()}
                    >
                      {/* Header row */}
                      <div className="flex items-center justify-between p-5 select-none touch-none">
                        {editingId === strategy.id ? (
                          <input
                            type="text"
                            defaultValue={strategy.name}
                            autoFocus
                            onBlur={(e) =>
                              void handleRename(
                                strategy.id,
                                e.target.value.trim() || strategy.name,
                              )
                            }
                            onKeyDown={(e) => {
                              if (e.key === "Enter")
                                void handleRename(
                                  strategy.id,
                                  e.currentTarget.value.trim() || strategy.name,
                                );
                              if (e.key === "Escape") setEditingId(null);
                            }}
                            className="text-[18px] font-medium text-black dark:text-white bg-transparent border-b border-black/20 dark:border-white/20 focus:outline-none focus:border-black dark:focus:border-white pointer-events-auto"
                            onClick={(e) => e.stopPropagation()}
                          />
                        ) : (
                          <span className="text-[18px] font-medium text-black dark:text-white flex items-center gap-2">
                            {strategy.name}
                            {strategy.isPinned && (
                              <Pin
                                className="w-3.5 h-3.5 text-black/40 dark:text-white/40 fill-black/40 dark:fill-white/40"
                                style={{ transform: "rotate(45deg)" }}
                              />
                            )}
                          </span>
                        )}
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setExpandedId(isExpanded ? null : strategy.id);
                          }}
                          className="ignore-long-press flex items-center justify-center w-8 h-8 rounded-[8px] hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
                          aria-label={isExpanded ? "Collapse" : "Expand"}
                        >
                          <ChevronDown
                            className={`w-5 h-5 text-black/40 dark:text-white/40 transition-transform duration-200 ${
                              isExpanded ? "rotate-0" : "-rotate-90"
                            }`}
                          />
                        </button>
                      </div>

                      {/* Long-press context menu */}
                      {isContextOpen && (
                        <div className="absolute top-0 inset-x-0 h-[72px] z-50 animate-in fade-in zoom-in-95 duration-200 bg-white dark:bg-[#1f2225] flex items-center justify-center gap-4 px-2 py-0 border-b border-black/10 dark:border-white/10 rounded-t-[24px]">
                          <button
                            onClick={() => void handleTogglePin(strategy.id)}
                            className="flex flex-col items-center gap-1.5 hover:opacity-70 transition-opacity"
                          >
                            <div className="w-10 h-10 rounded-full bg-black/5 dark:bg-white/5 flex items-center justify-center">
                              <Pin className="w-4 h-4" />
                            </div>
                            <span className="text-[11px] font-medium tracking-tight">
                              {strategy.isPinned ? t('common.unpin') : t('common.pin')}
                            </span>
                          </button>
                          <button
                            onClick={() => {
                              setActiveContextMenu(null);
                              setEditingId(strategy.id);
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
                            onClick={() => void handleDelete(strategy.id)}
                            className="flex flex-col items-center gap-1.5 hover:opacity-70 transition-opacity text-red-500"
                          >
                            <div className="w-10 h-10 rounded-full bg-red-500/10 flex items-center justify-center">
                              <Trash2 className="w-4 h-4" />
                            </div>
                            <span className="text-[11px] font-medium tracking-tight">
                              {t('common.delete')}
                            </span>
                          </button>
                          <div className="absolute inset-x-0 bottom-[-16px] h-4 flex justify-center items-center opacity-50 text-[9px] tracking-widest uppercase pointer-events-none drop-shadow-sm">
                            Tap elsewhere to cancel
                          </div>
                        </div>
                      )}

                      {/* Expanded content */}
                      <div
                        className={`argus-scrollbar overflow-y-auto transition-all duration-300 ease-in-out relative ${
                          isExpanded
                            ? "max-h-[280px] border-t border-black/5 dark:border-white/5"
                            : "max-h-0"
                        }`}
                      >
                        {strategy.hasMetrics ? (
                          <div className="flex flex-col px-5 py-4 gap-4">
                            {/* Header row */}
                            <div className="grid grid-cols-4 gap-2 items-end pb-2 sticky top-[-1px] bg-white dark:bg-[#1f2225] z-10 pt-1 -mt-1 shadow-[0_4px_10px_-5px_rgba(0,0,0,0.1)] dark:shadow-[0_4px_10px_-5px_rgba(0,0,0,0.5)]">
                              <div className="col-span-1" />
                              <div className="col-span-1 flex flex-col items-center justify-center">
                                <span className="text-[10px] lowercase font-medium text-black/40 dark:text-white/40 tracking-normal text-center leading-tight">
                                  {t('strategies.metrics.overall_profit')}
                                </span>
                              </div>
                              <div className="col-span-1 flex flex-col items-center justify-center">
                                <span className="text-[10px] lowercase font-medium text-black/40 dark:text-white/40 tracking-normal text-center leading-tight">
                                  {t('strategies.metrics.max_drawdown')}
                                </span>
                              </div>
                              <div className="col-span-1 flex flex-col items-center justify-center">
                                <span className="text-[10px] lowercase font-medium text-black/40 dark:text-white/40 tracking-normal text-center leading-tight">
                                  {t('strategies.metrics.win_rate')}
                                </span>
                              </div>
                            </div>

                            {/* Data rows */}
                            {strategy.assets.map((asset, idx) => (
                              <div
                                key={idx}
                                className="grid grid-cols-4 gap-2 items-center"
                              >
                                <div className="col-span-1 flex flex-col pl-1">
                                  <span className="text-[16px] font-medium text-black dark:text-white tracking-tight">
                                    {asset.ticker}
                                  </span>
                                  <span className="text-[11px] text-black/50 dark:text-white/50 truncate pr-2">
                                    {asset.name}
                                  </span>
                                </div>
                                {[
                                  asset.overallProfit,
                                  asset.maxDrawdown,
                                  asset.winRate,
                                ].map((pill, pi) => (
                                  <div
                                    key={pi}
                                    className="col-span-1 flex items-center justify-center"
                                  >
                                    <div
                                      className={`flex items-center justify-center w-full py-1.5 px-1 rounded-[8px] border text-[12px] font-medium tracking-tight ${
                                        pill.isPositive
                                          ? "bg-green-500/10 text-green-600 border-green-500/20"
                                          : "bg-red-500/10 text-red-600 border-red-500/20"
                                      }`}
                                    >
                                      {pill.value}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            ))}
                          </div>
                        ) : (
                          /* Option B — unexecuted strategy empty state */
                          <div className="flex flex-col items-center justify-center gap-4 px-5 py-8">
                            <p className="text-[14px] text-black/50 dark:text-white/50 text-center leading-relaxed max-w-[240px]">
                              Run this strategy to see how{" "}
                              {strategy.raw.symbols.join(", ")} would have
                              performed.
                            </p>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                void handleRunStrategy(strategy);
                              }}
                              disabled={isRunning}
                              className="ignore-long-press flex items-center gap-2 rounded-full bg-black dark:bg-white text-white dark:text-black px-5 py-2.5 text-[14px] font-medium hover:opacity-80 transition-opacity disabled:opacity-40"
                            >
                              {isRunning ? (
                                <Loader2 className="w-4 h-4 animate-spin" />
                              ) : (
                                <Play className="w-4 h-4" />
                              )}
                              {isRunning ? t('common.loading') : t('common.run_simulation')}
                            </button>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Date subtitle */}
                    <span className="text-[12px] text-black/40 dark:text-white/40 mt-2 px-2">
                      {strategy.dateStr}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {scrollIndicator.visible && (
          <div
            className={`absolute right-[2px] top-0 w-px rounded-full argus-scroll-indicator pointer-events-none ${
              isScrolling ? "opacity-100" : "opacity-0"
            }`}
            style={{
              height: `${scrollIndicator.height}px`,
              transform: `translateY(${scrollIndicator.top}px)`,
            }}
            aria-hidden="true"
          />
        )}
      </div>

      {/* Bottom glass blur */}
      <div className="absolute bottom-0 inset-x-0 h-40 z-10 pointer-events-none backdrop-blur-[0.8px] bg-[#f9f9f9]/10 dark:bg-[#141517]/20 [mask-image:linear-gradient(to_top,black_50%,transparent_100%)] [-webkit-mask-image:linear-gradient(to_top,black_50%,transparent_100%)]" />

      <div 
        className={`absolute bottom-6 inset-x-0 w-full px-4 z-20 pointer-events-none transition-all duration-300 ${
          isSidebarOpen ? "opacity-0 translate-y-4 pointer-events-none" : "opacity-100 translate-y-0"
        }`}
      >
        <div className="pointer-events-auto max-w-3xl mx-auto flex items-center gap-4 transition-all duration-300 opacity-50 hover:opacity-100 focus-within:opacity-100 group">
          <div className="relative flex-1">
            <Search className="w-5 h-5 absolute left-5 top-1/2 -translate-y-1/2 text-black/40 dark:text-white/40 pointer-events-none" />
            <input
              type="text"
              placeholder={t('strategies.search_placeholder')}
              value={searchText}
              onChange={(e) => onSearchChange(e.target.value)}
              className="w-full h-[52px] pl-[48px] pr-12 rounded-full border border-black/10 dark:border-white/10 bg-white/50 dark:bg-[#1f2225]/50 backdrop-blur-xl focus:bg-white dark:focus:bg-[#1f2225] focus:outline-none focus:ring-2 focus:ring-black/5 dark:focus:ring-white/5 transition-all text-[15px] shadow-lg text-black dark:text-white placeholder:text-black/40 dark:placeholder:text-white/40"
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
