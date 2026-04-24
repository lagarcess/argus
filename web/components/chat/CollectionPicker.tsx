"use client";

import { useEffect, useState } from "react";
import { Check, Folder, Loader2, Plus, X } from "lucide-react";
import {
  listCollections,
  createCollection,
  attachStrategyToCollection,
  createStrategy,
  type Collection,
  type AssetClass,
} from "@/lib/argus-api";

type CollectionPickerProps = {
  /** The backtest run's strategy_id. If null, we create one first. */
  strategyId: string | null;
  /** Fallback info to create a strategy if strategyId is null */
  strategyFallback?: {
    name: string;
    template: string;
    asset_class: AssetClass;
    symbols: string[];
  };
  onClose: () => void;
  onSuccess: (collectionName: string) => void;
};

export default function CollectionPicker({
  strategyId,
  strategyFallback,
  onClose,
  onSuccess,
}: CollectionPickerProps) {
  const [collections, setCollections] = useState<Collection[]>([]);
  const [loading, setLoading] = useState(true);
  const [attaching, setAttaching] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [done, setDone] = useState<string | null>(null);

  useEffect(() => {
    listCollections(50)
      .then(({ items }) => setCollections(items))
      .catch(() => setCollections([]))
      .finally(() => setLoading(false));
  }, []);

  const resolveStrategyId = async (): Promise<string | null> => {
    if (strategyId) return strategyId;
    if (!strategyFallback) return null;
    try {
      const { strategy } = await createStrategy({
        name: strategyFallback.name,
        template: strategyFallback.template,
        asset_class: strategyFallback.asset_class,
        symbols: strategyFallback.symbols,
      });
      return strategy.id;
    } catch {
      return null;
    }
  };

  const handleAttach = async (collection: Collection) => {
    setAttaching(collection.id);
    try {
      const sid = await resolveStrategyId();
      if (!sid) throw new Error("No strategy");
      await attachStrategyToCollection(collection.id, sid);
      setDone(collection.name);
      setTimeout(() => onSuccess(collection.name), 900);
    } catch {
      setAttaching(null);
    }
  };

  const handleCreateAndAttach = async () => {
    setCreating(true);
    try {
      const { collection } = await createCollection();
      setCollections((prev) => [collection, ...prev]);
      await handleAttach(collection);
    } catch {
      setCreating(false);
    }
  };

  return (
    <>
      {/* Backdrop */}
      <button
        type="button"
        aria-label="Close"
        className="fixed inset-0 z-40 bg-black/20 dark:bg-black/50 cursor-default"
        onClick={onClose}
      />

      {/* Sheet */}
      <div className="fixed inset-x-0 bottom-0 z-50 rounded-t-[28px] border-t border-black/5 bg-white pb-8 pt-2 shadow-[0_-8px_30px_rgba(0,0,0,0.12)] dark:border-white/5 dark:bg-[#1f2225] animate-in slide-in-from-bottom-4 duration-300">
        {/* Drag handle */}
        <div className="mx-auto my-3 h-1.5 w-12 rounded-full bg-black/10 dark:bg-white/10" />

        <div className="flex items-center justify-between px-6 pb-4">
          <h2 className="text-[17px] font-semibold tracking-tight">
            Add to collection
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-full hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
            aria-label="Close"
          >
            <X className="h-4 w-4 text-black/50 dark:text-white/50" />
          </button>
        </div>

        {/* Collection list */}
        <div className="max-h-[45vh] overflow-y-auto px-4">
          {loading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-black/30 dark:text-white/30" />
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {/* Create new */}
              <button
                type="button"
                onClick={() => void handleCreateAndAttach()}
                disabled={creating || attaching !== null}
                className="flex w-full items-center gap-4 rounded-[16px] px-4 py-3.5 text-left hover:bg-black/5 dark:hover:bg-white/5 transition-colors disabled:opacity-40"
              >
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-black/5 dark:bg-white/5">
                  {creating ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Plus className="h-4 w-4" />
                  )}
                </div>
                <span className="text-[16px] font-medium">New collection</span>
              </button>

              {collections.length > 0 && (
                <div className="my-1 h-px bg-black/5 dark:bg-white/5" />
              )}

              {collections.map((col) => {
                const isAttaching = attaching === col.id;
                const isDone = done === col.name;
                return (
                  <button
                    key={col.id}
                    type="button"
                    onClick={() => void handleAttach(col)}
                    disabled={attaching !== null}
                    className="flex w-full items-center gap-4 rounded-[16px] px-4 py-3.5 text-left hover:bg-black/5 dark:hover:bg-white/5 transition-colors disabled:opacity-40"
                  >
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-black/5 dark:bg-white/5">
                      {isAttaching || isDone ? (
                        isDone ? (
                          <Check className="h-4 w-4 text-green-500" />
                        ) : (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        )
                      ) : (
                        <Folder className="h-4 w-4" />
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <span className="block text-[16px] font-medium truncate">
                        {col.name}
                      </span>
                      <span className="block text-[12px] text-black/45 dark:text-white/45">
                        {col.strategy_count}{" "}
                        {col.strategy_count === 1 ? "strategy" : "strategies"}
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
