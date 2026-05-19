"use client";

import { useEffect, useState } from "react";
import {
  Archive,
  ChevronLeft,
  Loader2,
  RotateCcw,
  X,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { Tooltip } from "@/components/ui/Tooltip";
import { listConversations, patchConversation, type Conversation } from "@/lib/argus-api";

type ArchivedChatsViewProps = {
  onClose: () => void;
};

/**
 * Centered blur modal showing archived conversations with restore functionality.
 * Extracted from SettingsView for reuse in ProfileMenu > Data submenu.
 */
export default function ArchivedChatsView({ onClose }: ArchivedChatsViewProps) {
  const { t } = useTranslation();
  const [archivedChats, setArchivedChats] = useState<Conversation[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    listConversations({ archived: true })
      .then(({ items }) => setArchivedChats(items))
      .finally(() => setIsLoading(false));
  }, []);

  const handleUnarchive = async (id: string) => {
    try {
      await patchConversation(id, { archived: false });
      setArchivedChats((prev) => prev.filter((c) => c.id !== id));
    } catch (err) {
      console.error("Failed to unarchive", err);
    }
  };

  return (
    <div className="fixed inset-0 z-[70] bg-black/25 dark:bg-black/60 backdrop-blur-sm p-4 flex items-center justify-center">
      <button
        className="absolute inset-0"
        aria-label="Close archived chats"
        onClick={onClose}
      />
      <div className="relative w-full max-w-md max-h-[70vh] bg-white dark:bg-[#1b1d20] rounded-[18px] border border-black/5 dark:border-white/10 overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-black/5 dark:border-white/5">
          <h2 className="text-[16px] font-medium text-black dark:text-white">
            {t("settings.data.archived_chats")}
          </h2>
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
          ) : archivedChats.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-center gap-4">
              <div className="w-16 h-16 rounded-full bg-black/5 dark:bg-white/5 flex items-center justify-center">
                <Archive className="w-8 h-8 text-black/20 dark:text-white/20" />
              </div>
              <p className="text-[15px] text-black/40 dark:text-white/40">
                {t("common.no_items") || "No archived chats"}
              </p>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              {archivedChats.map((chat) => (
                <div
                  key={chat.id}
                  className="group flex items-center justify-between p-4 bg-black/[0.02] dark:bg-white/[0.03] border border-black/5 dark:border-white/5 rounded-[16px]"
                >
                  <div className="flex flex-col min-w-0 pr-4">
                    <span className="text-[15px] font-medium text-black dark:text-white truncate">
                      {chat.title || t("chat.new_chat")}
                    </span>
                    <span className="text-[13px] text-black/40 dark:text-white/40 truncate">
                      {chat.last_message_preview || t("chat.no_messages")}
                    </span>
                  </div>
                  <Tooltip content={t("common.restore") || "Restore"} side="top">
                    <button
                      onClick={() => void handleUnarchive(chat.id)}
                      className="shrink-0 p-2 rounded-full hover:bg-black/5 dark:hover:bg-white/5 text-black/50 dark:text-white/50 transition-colors"
                      aria-label="Restore"
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
