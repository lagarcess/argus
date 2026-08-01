"use client";

import { useEffect, useRef } from "react";
import { Edit2, Mail, MailOpen, MoreVertical, Pin, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";

type ChatHeaderMenuProps = {
  isOpen: boolean;
  onToggleOpen: () => void;
  onRequestClose: () => void;
  isUnread: boolean;
  isReadMutationPending: boolean;
  onToggleUnread: () => void;
  isRenaming: boolean;
  renameValue: string;
  onRenameValueChange: (value: string) => void;
  onStartRename: () => void;
  onSaveRename: () => void;
  onCancelRename: () => void;
  isSavingRename: boolean;
  pinned: boolean;
  isPinning: boolean;
  onTogglePin: () => void;
  isDeleting: boolean;
  onRequestDelete: () => void;
};

/** Header owner menu for the active conversation. */
export default function ChatHeaderMenu({
  isOpen,
  onToggleOpen,
  onRequestClose,
  isUnread,
  isReadMutationPending,
  onToggleUnread,
  isRenaming,
  renameValue,
  onRenameValueChange,
  onStartRename,
  onSaveRename,
  onCancelRename,
  isSavingRename,
  pinned,
  isPinning,
  onTogglePin,
  isDeleting,
  onRequestDelete,
}: ChatHeaderMenuProps) {
  const { t } = useTranslation();
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        onRequestClose();
      }
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onRequestClose();
        triggerRef.current?.focus();
      }
    }
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      document.addEventListener("keydown", handleKeyDown);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, onRequestClose]);

  const handleToggleUnread = () => {
    onRequestClose();
    onToggleUnread();
  };

  return (
    <div className="relative animate-in fade-in duration-300" ref={containerRef}>
      <button
        ref={triggerRef}
        type="button"
        onClick={onToggleOpen}
        className="flex h-11 w-11 items-center justify-center rounded-full transition-all duration-200 hover:bg-black/5 dark:hover:bg-white/5 active:scale-95"
        aria-label={t("chat.chat_options", "Chat options")}
        aria-haspopup="menu"
        aria-expanded={isOpen}
      >
        <MoreVertical className="h-5 w-5" />
      </button>
      {isOpen && (
        <div className="fixed inset-x-0 bottom-0 z-50 rounded-t-[28px] border-t border-black/5 bg-white pb-7 pt-2 dark:border-white/5 dark:bg-[#1f2225] md:absolute md:bottom-auto md:right-0 md:left-auto md:top-full md:mt-2 md:w-[260px] md:rounded-[20px] md:border md:pb-2">
          <div className="mx-auto my-3 h-1.5 w-12 rounded-full bg-black/10 dark:bg-white/10 md:hidden" />
          {!isRenaming ? (
            <div role="menu" className="py-1">
              <button
                type="button"
                role="menuitem"
                disabled={isReadMutationPending}
                onClick={handleToggleUnread}
                className="flex w-full items-center gap-4 px-6 py-4 text-left text-[16px] font-medium transition-colors hover:bg-black/5 disabled:cursor-wait disabled:opacity-50 dark:hover:bg-white/5 md:px-5 md:py-3 md:text-[15px]"
              >
                {isUnread
                  ? <MailOpen className="h-[18px] w-[18px] text-black/60 dark:text-white/60 md:h-4 md:w-4" />
                  : <Mail className="h-[18px] w-[18px] text-black/60 dark:text-white/60 md:h-4 md:w-4" />}
                {isUnread
                  ? t("chat.activity.mark_read", "Mark as read")
                  : t("chat.activity.mark_unread", "Mark as unread")}
              </button>
              <button
                type="button"
                role="menuitem"
                disabled={isPinning}
                onClick={onTogglePin}
                className="flex w-full items-center gap-4 px-6 py-4 text-left text-[16px] font-medium transition-colors hover:bg-black/5 dark:hover:bg-white/5 md:px-5 md:py-3 md:text-[15px]"
              >
                <Pin className="h-[18px] w-[18px] text-black/60 dark:text-white/60 md:h-4 md:w-4" />
                {pinned
                  ? t('chat.unpin_chat', 'Unpin chat')
                  : t('chat.pin_chat', 'Pin chat')}
              </button>
              <button
                type="button"
                role="menuitem"
                onClick={onStartRename}
                className="flex w-full items-center gap-4 px-6 py-4 text-left text-[16px] font-medium transition-colors hover:bg-black/5 dark:hover:bg-white/5 md:px-5 md:py-3 md:text-[15px]"
              >
                <Edit2 className="h-[18px] w-[18px] text-black/60 dark:text-white/60 md:h-4 md:w-4" />
                {t('chat.rename_chat', 'Rename chat')}
              </button>
              <div role="separator" className="my-1 h-px bg-black/5 dark:bg-white/5" />
              <button
                type="button"
                role="menuitem"
                disabled={isDeleting}
                onClick={onRequestDelete}
                className="flex w-full items-center gap-4 px-6 py-4 text-left text-[16px] font-medium text-red-500 transition-colors hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-45 dark:hover:bg-red-500/10 md:px-5 md:py-3 md:text-[15px]"
              >
                <Trash2 className="h-[18px] w-[18px] md:h-4 md:w-4" />
                {t('chat.delete_chat', 'Delete')}
              </button>
            </div>
          ) : (
            <form
              className="space-y-2 px-5 py-3"
              onSubmit={(event) => {
                event.preventDefault();
                onSaveRename();
              }}
            >
              <label className="block text-[12px] font-medium text-black/45 dark:text-white/45">
                {t('chat.rename_chat', 'Rename chat')}
              </label>
              <input
                autoFocus
                value={renameValue}
                onChange={(event) => onRenameValueChange(event.target.value.slice(0, 80))}
                className="w-full rounded-[12px] border border-black/10 bg-black/[0.02] px-3 py-2 text-[14px] font-medium text-black outline-none focus:border-black/25 dark:border-white/10 dark:bg-white/[0.04] dark:text-white dark:focus:border-white/25"
                maxLength={80}
              />
              <div className="flex gap-2">
                <button
                  type="submit"
                  disabled={isSavingRename}
                  className="min-h-9 flex-1 rounded-full bg-black px-3 py-1.5 text-[13px] font-medium text-white transition-opacity hover:opacity-85 disabled:opacity-50 dark:bg-white dark:text-black"
                >
                  {t('common.save')}
                </button>
                <button
                  type="button"
                  disabled={isSavingRename}
                  onClick={onCancelRename}
                  className="min-h-9 flex-1 rounded-full border border-black/10 px-3 py-1.5 text-[13px] font-medium text-black/70 transition-colors hover:bg-black/5 disabled:opacity-50 dark:border-white/10 dark:text-white/70 dark:hover:bg-white/5"
                >
                  {t('common.cancel')}
                </button>
              </div>
            </form>
          )}
        </div>
      )}
    </div>
  );
}
