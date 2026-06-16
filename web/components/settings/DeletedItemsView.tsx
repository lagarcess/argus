"use client";

import { useEffect, useState } from "react";
import {
  BarChart2,
  History,
  Layers,
  Loader2,
  MessageSquare,
  RotateCcw,
  X,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { Tooltip } from "@/components/ui/Tooltip";
import {
  listHistory,
  patchConversation,
  patchStrategy,
  type HistoryItem,
} from "@/lib/argus-api";

type DeletedItemsViewProps = {
  onClose: () => void;
  onRestored?: () => void;
};

export default function DeletedItemsView({ onClose, onRestored }: DeletedItemsViewProps) {
  const { t } = useTranslation();
  const [deletedItems, setDeletedItems] = useState<HistoryItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    listHistory({ deleted: true })
      .then(({ items }) => setDeletedItems(items))
      .finally(() => setIsLoading(false));
  }, []);

  const handleRestore = async (item: HistoryItem) => {
    try {
      if (item.type === "chat") {
        await patchConversation(item.id, { deleted_at: null });
      } else if (item.type === "strategy") {
        await patchStrategy(item.id, { deleted_at: null });
      }
      setDeletedItems((prev) => prev.filter((i) => i.id !== item.id));
      onRestored?.();
    } catch (err) {
      console.error("Failed to restore", err);
    }
  };

  const typeIcon = (type: string) => {
    if (type === "chat") return <MessageSquare className="w-4 h-4" />;
    if (type === "strategy") return <BarChart2 className="w-4 h-4" />;
    return <Layers className="w-4 h-4" />;
  };

  return (
    <div className="fixed inset-0 z-[70] bg-black/25 dark:bg-black/60 backdrop-blur-sm p-4 flex items-center justify-center">
      <button
        className="absolute inset-0"
        aria-label={t("settings.data.close_recently_deleted", "Close recently deleted")}
        onClick={onClose}
      />
      <div className="relative w-full max-w-md max-h-[70vh] bg-white dark:bg-[#1b1d20] rounded-[18px] border border-black/5 dark:border-white/10 overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-black/5 dark:border-white/5">
          <div>
            <h2 className="text-[16px] font-medium text-black dark:text-white">
              {t("settings.data.recently_deleted")}
            </h2>
            <p className="text-[12px] text-black/40 dark:text-white/40 mt-0.5">
              {t(
                "settings.data.deleted_retention_note",
                "Items stay here temporarily before permanent deletion.",
              )}
            </p>
          </div>
          <button
            onClick={onClose}
            className="flex items-center justify-center p-1.5 rounded-full hover:bg-black/5 dark:hover:bg-white/10 transition-colors"
          >
            <X className="w-4 h-4 text-black/50 dark:text-white/50" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {isLoading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="w-6 h-6 animate-spin text-black/20 dark:text-white/20" />
            </div>
          ) : deletedItems.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-center gap-4">
              <div className="w-16 h-16 rounded-full bg-black/5 dark:bg-white/5 flex items-center justify-center">
                <History className="w-8 h-8 text-black/20 dark:text-white/20" />
              </div>
              <p className="text-[15px] text-black/40 dark:text-white/40">
                {t("settings.data.no_deleted_items", "No recently deleted items")}
              </p>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              {deletedItems.map((item) => (
                <div
                  key={item.id}
                  className="group flex items-center justify-between p-4 bg-black/[0.02] dark:bg-white/[0.03] border border-black/5 dark:border-white/5 rounded-[16px]"
                >
                  <div className="flex items-center gap-3 min-w-0 pr-4">
                    <div className="shrink-0 w-8 h-8 rounded-lg bg-black/5 dark:bg-white/5 flex items-center justify-center text-black/40 dark:text-white/40">
                      {typeIcon(item.type)}
                    </div>
                    <div className="flex flex-col min-w-0">
                      <span className="text-[15px] font-medium text-black dark:text-white truncate">
                        {item.title}
                      </span>
                      {/* Deferred(future): exact restore windows need deleted_at or retention_expires_at on HistoryItem. */}
                      <span className="text-[12px] text-black/40 dark:text-white/40">
                        {t(
                          "settings.data.deleted_item_note",
                          "Eligible for permanent deletion soon",
                        )}
                      </span>
                    </div>
                  </div>
                  <Tooltip content={t("common.restore") || "Restore"} side="top">
                    <button
                      onClick={() => void handleRestore(item)}
                      className="shrink-0 p-2 rounded-full hover:bg-black/5 dark:hover:bg-white/5 text-black/50 dark:text-white/50 transition-colors"
                      aria-label={t("common.restore", "Restore")}
                    >
                      <RotateCcw className="w-5 h-5" />
                    </button>
                  </Tooltip>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
