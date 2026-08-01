"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { History, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { QuickJumpBadge } from "@/components/keyboard/QuickJumpBadge";
import { useQuickJump } from "@/components/keyboard/useQuickJump";
import {
  ConversationActivityIndicator,
  conversationActivityLabelDescriptor,
  useConversationActivityPresentation,
} from "@/components/chat/ConversationActivityIndicator";
import { conversationDisplayTitle } from "@/lib/chat-title-display";
import type { HistoryItem } from "@/lib/argus-api";

type RecentsQuickPeekProps = {
  historyItems: HistoryItem[];
  activeConversationId: string | null;
  onOpenItem: (item: HistoryItem) => void;
  onClose: () => void;
};

function historyConversationId(item: HistoryItem): string {
  return item.conversation_id ?? item.id;
}

export default function RecentsQuickPeek({
  historyItems,
  activeConversationId,
  onOpenItem,
  onClose,
}: RecentsQuickPeekProps) {
  const { t } = useTranslation();
  const { selectOperationLabel, selectPresentation } =
    useConversationActivityPresentation();
  const [usesCommandKey, setUsesCommandKey] = useState(false);
  const visibleItems = useMemo(
    () => historyItems.filter((item) => item.type === "chat").slice(0, 9),
    [historyItems],
  );
  const quickJumpItems = useMemo(
    () =>
      visibleItems.map((item) => ({
        id: historyConversationId(item),
        pinned: item.pinned,
      })),
    [visibleItems],
  );
  const openItem = useCallback(
    (id: string) => {
      const item = visibleItems.find(
        (candidate) => historyConversationId(candidate) === id,
      );
      if (!item) return;
      onOpenItem(item);
      onClose();
    },
    [onClose, onOpenItem, visibleItems],
  );
  const { isQuickJumpActive, numberFor } = useQuickJump({
    enabled: true,
    items: quickJumpItems,
    onSelect: openItem,
    usesCommandKey,
  });

  useEffect(() => {
    setUsesCommandKey(
      /Mac|iPhone|iPad|iPod/.test(navigator.userAgent),
    );
  }, []);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-[65]">
      <button
        type="button"
        className="absolute inset-0 cursor-default"
        aria-label={t("recents_quick_peek.close", "Close Recents")}
        onClick={onClose}
      />
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="argus-recents-quick-peek-title"
        className="absolute left-4 top-20 w-[min(360px,calc(100vw-2rem))] overflow-hidden rounded-[18px] border border-black/10 bg-white p-3 text-black shadow-[0_12px_32px_rgba(0,0,0,0.12)] dark:border-white/10 dark:bg-[#1b1d20] dark:text-white"
      >
        <div className="mb-2 flex items-center justify-between gap-3 px-2 py-1">
          <div className="flex items-center gap-2">
            <History className="h-4 w-4 text-black/55 dark:text-white/60" />
            <h2
              id="argus-recents-quick-peek-title"
              className="font-display text-[15px] font-medium"
            >
              {t("recents_quick_peek.title", "Recents")}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full p-1.5 text-black/55 hover:bg-black/[0.05] dark:text-white/60 dark:hover:bg-white/[0.08]"
            aria-label={t("recents_quick_peek.close", "Close Recents")}
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {visibleItems.length === 0 ? (
          <p className="px-2 py-5 text-[13px] text-black/45 dark:text-white/45">
            {t("recents_quick_peek.empty", "No recent chats yet.")}
          </p>
        ) : (
          <div className="flex flex-col gap-1">
            {visibleItems.map((item) => {
              const conversationId = historyConversationId(item);
              const number = numberFor(conversationId);
              const displayTitle = conversationDisplayTitle(
                item,
                t("chat.new_chat", "New chat"),
              );
              const itemActivityPresentation =
                selectPresentation(conversationId);
              const itemOperationLabel = selectOperationLabel(conversationId);
              const activityLabel = conversationActivityLabelDescriptor(
                itemActivityPresentation,
                itemOperationLabel,
              );
              const rowAriaLabel = activityLabel
                ? `${displayTitle}. ${t(activityLabel.key, activityLabel.defaultValue)}.`
                : displayTitle;
              return (
                <button
                  key={conversationId}
                  type="button"
                  aria-label={rowAriaLabel}
                  aria-current={
                    activeConversationId === conversationId ? "page" : undefined
                  }
                  onClick={() => openItem(conversationId)}
                  className={`relative flex min-h-11 items-center gap-3 rounded-xl px-2 py-2 text-left hover:bg-black/[0.05] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/25 dark:hover:bg-white/[0.08] dark:focus-visible:ring-white/30 ${
                    activeConversationId === conversationId
                      ? "bg-black/[0.05] dark:bg-white/[0.08]"
                      : ""
                  }`}
                >
                  <span className="pointer-events-none absolute -left-2 top-1/2 flex h-6 w-4 -translate-y-1/2 items-center justify-center">
                    <ConversationActivityIndicator
                      presentation={itemActivityPresentation}
                      compact
                    />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="font-display block truncate text-[13px] font-medium">
                      {displayTitle}
                    </span>
                    <span className="mt-0.5 block truncate text-[11px] text-black/45 dark:text-white/45">
                      {item.subtitle}
                    </span>
                  </span>
                  {isQuickJumpActive && number !== null ? (
                    <span
                      data-quick-jump-hint={number}
                      className="pointer-events-none ml-auto flex h-[22px] shrink-0 items-center justify-end"
                    >
                      <QuickJumpBadge
                        number={number}
                        presentation="shortcut_hint"
                        usesCommandKey={usesCommandKey}
                      />
                    </span>
                  ) : null}
                </button>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
