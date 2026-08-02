"use client";

import { type ReactNode, useEffect, useRef, useState } from "react";
import { Archive, Edit2, Mail, MailOpen, MoreVertical, Pin, Trash2 } from "lucide-react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";
import type { HistoryItem } from "@/lib/argus-api";

type RecentChatActionsProps = {
  item: HistoryItem;
  onPin: (id: string, pinned: boolean) => Promise<void> | void;
  onRename: (id: string) => void;
  onArchive: (id: string) => Promise<void> | void;
  onDelete: (id: string) => Promise<void> | void;
  isUnread: boolean;
  isReadMutationPending: boolean;
  onToggleUnread: () => Promise<void> | void;
  quickJumpHint?: ReactNode;
};

export default function RecentChatActions({
  item,
  onPin,
  onRename,
  onArchive,
  onDelete,
  isUnread,
  isReadMutationPending,
  onToggleUnread,
  quickJumpHint,
}: RecentChatActionsProps) {
  const { t } = useTranslation();
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isTriggerFocused, setIsTriggerFocused] = useState(false);
  const [isBusy, setIsBusy] = useState(false);
  const [menuPosition, setMenuPosition] = useState<{ top: number; left: number } | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!isMenuOpen || !triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();
    setMenuPosition({
      top: rect.bottom + 4,
      left: Math.max(8, rect.right - 160),
    });
  }, [isMenuOpen]);

  useEffect(() => {
    if (!isMenuOpen) return;

    const onMouseDown = (event: MouseEvent) => {
      const target = event.target as Node;
      if (
        menuRef.current?.contains(target) ||
        triggerRef.current?.contains(target)
      ) {
        return;
      }
      setIsMenuOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsMenuOpen(false);
        triggerRef.current?.focus();
      }
    };

    document.addEventListener("mousedown", onMouseDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onMouseDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [isMenuOpen]);

  const runAction = async (action: () => Promise<void> | void) => {
    if (isBusy) return;
    setIsBusy(true);
    try {
      await action();
      setIsMenuOpen(false);
    } finally {
      setIsBusy(false);
    }
  };
  const showActionTrigger =
    isMenuOpen || isTriggerFocused || !quickJumpHint;
  const handleToggleUnread = () => {
    setIsMenuOpen(false);
    void onToggleUnread();
  };

  return (
    <div className="relative flex h-11 w-[88px] items-center justify-end">
      {showActionTrigger ? (
        <button
          ref={triggerRef}
          type="button"
          data-actions
          onFocus={() => setIsTriggerFocused(true)}
          onBlur={() => setIsTriggerFocused(false)}
          onClick={(event) => {
            event.stopPropagation();
            setIsMenuOpen((open) => !open);
          }}
          className={`flex h-11 w-11 items-center justify-center rounded-md transition-opacity duration-150 hover:bg-black/10 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/30 dark:hover:bg-white/10 dark:focus-visible:ring-white/40 [@media(pointer:coarse)]:opacity-100 ${
            isMenuOpen || isTriggerFocused
              ? "opacity-100"
              : "opacity-0 group-hover:opacity-100"
          }`}
          aria-label={t("common.more", "More")}
          aria-haspopup="menu"
          aria-expanded={isMenuOpen}
          title={t("common.more", "More")}
        >
          <MoreVertical className="h-3.5 w-3.5 text-black/50 dark:text-white/50" />
        </button>
      ) : (
        <span className="pointer-events-none flex items-center justify-end">
          {quickJumpHint}
        </span>
      )}

      {isMenuOpen && menuPosition && typeof document !== "undefined" && createPortal(
        <div
          ref={menuRef}
          role="menu"
          className="fixed z-[9999] min-w-[160px] rounded-[12px] border border-black/10 bg-white py-1 dark:border-white/10 dark:bg-[#1f2225]"
          style={{ top: menuPosition.top, left: menuPosition.left }}
          onClick={(event) => event.stopPropagation()}
          onMouseDown={(event) => event.stopPropagation()}
        >
          <button
            type="button"
            role="menuitem"
            disabled={isReadMutationPending}
            onClick={(event) => {
              event.stopPropagation();
              handleToggleUnread();
            }}
            className="font-display mx-1 my-0.5 flex w-[calc(100%-0.5rem)] items-center gap-2.5 rounded-[10px] px-3 py-2 text-[13px] text-black hover:bg-black/5 disabled:cursor-wait disabled:opacity-50 dark:text-white dark:hover:bg-white/5"
          >
            {isUnread ? <MailOpen className="h-3.5 w-3.5" /> : <Mail className="h-3.5 w-3.5" />}
            {isUnread
              ? t("chat.activity.mark_read", "Mark as read")
              : t("chat.activity.mark_unread", "Mark as unread")}
          </button>
          <button
            type="button"
            role="menuitem"
            disabled={isBusy}
            onClick={(event) => {
              event.stopPropagation();
              void runAction(() => onPin(item.id, !item.pinned));
            }}
            className="font-display mx-1 my-0.5 flex w-[calc(100%-0.5rem)] items-center gap-2.5 rounded-[10px] px-3 py-2 text-[13px] text-black hover:bg-black/5 disabled:opacity-50 dark:text-white dark:hover:bg-white/5"
          >
            <Pin className="h-3.5 w-3.5" />
            {item.pinned ? t("common.unpin", "Unpin") : t("common.pin", "Pin")}
          </button>
          <button
            type="button"
            role="menuitem"
            disabled={isBusy}
            onClick={(event) => {
              event.stopPropagation();
              onRename(item.id);
              setIsMenuOpen(false);
            }}
            className="font-display mx-1 my-0.5 flex w-[calc(100%-0.5rem)] items-center gap-2.5 rounded-[10px] px-3 py-2 text-[13px] text-black hover:bg-black/5 disabled:opacity-50 dark:text-white dark:hover:bg-white/5"
          >
            <Edit2 className="h-3.5 w-3.5" />
            {t("common.rename", "Rename")}
          </button>
          <button
            type="button"
            role="menuitem"
            disabled={isBusy}
            onClick={(event) => {
              event.stopPropagation();
              void runAction(() => onArchive(item.id));
            }}
            className="font-display mx-1 my-0.5 flex w-[calc(100%-0.5rem)] items-center gap-2.5 rounded-[10px] px-3 py-2 text-[13px] text-black hover:bg-black/5 disabled:opacity-50 dark:text-white dark:hover:bg-white/5"
          >
            <Archive className="h-3.5 w-3.5" />
            {t("common.archive", "Archive")}
          </button>
          <div role="separator" className="my-1 border-t border-black/10 dark:border-white/10" />
          <button
            type="button"
            role="menuitem"
            disabled={isBusy}
            onClick={(event) => {
              event.stopPropagation();
              void runAction(() => onDelete(item.id));
            }}
            className="font-display mx-1 my-0.5 flex w-[calc(100%-0.5rem)] items-center gap-2.5 rounded-[10px] px-3 py-2 text-[13px] text-[#d66d75] hover:bg-black/5 disabled:opacity-50 dark:hover:bg-white/5"
          >
            <Trash2 className="h-3.5 w-3.5" />
            {t("common.delete", "Delete")}
          </button>
        </div>,
        document.body,
      )}
    </div>
  );
}
