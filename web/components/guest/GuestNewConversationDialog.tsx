"use client";

import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { newConversationConversionMode } from "@/lib/guest-conversion";

type GuestNewConversationDialogProps = {
  isOpen: boolean;
  isReplacing: boolean;
  publicAccountAccessEnabled: boolean;
  onCancel: () => void;
  onConvert: () => void;
  onStartOver: () => void;
};

const focusableSelector =
  'button:not([disabled]), [href], input:not([disabled]), [tabindex]:not([tabindex="-1"])';

export default function GuestNewConversationDialog({
  isOpen,
  isReplacing,
  publicAccountAccessEnabled,
  onCancel,
  onConvert,
  onStartOver,
}: GuestNewConversationDialogProps) {
  const { t } = useTranslation();
  const dialogRef = useRef<HTMLDivElement>(null);
  const openerRef = useRef<HTMLElement | null>(null);
  const conversionMode = newConversationConversionMode(
    publicAccountAccessEnabled,
  );
  const isPublicAccountChoice = conversionMode === "signup";

  useEffect(() => {
    if (!isOpen) return;
    openerRef.current = document.activeElement as HTMLElement | null;
    const dialog = dialogRef.current;
    const focusable = dialog?.querySelectorAll<HTMLElement>(focusableSelector);
    focusable?.[0]?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !isReplacing) {
        event.preventDefault();
        onCancel();
        return;
      }
      if (event.key !== "Tab" || !focusable?.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      openerRef.current?.focus();
    };
  }, [isOpen, isReplacing, onCancel]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/30 px-4 backdrop-blur-sm"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !isReplacing) onCancel();
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="guest-new-conversation-title"
        className="w-full max-w-[430px] rounded-[24px] border border-black/10 bg-white p-6 text-black dark:border-white/10 dark:bg-[#1f2225] dark:text-white"
      >
        <h2
          id="guest-new-conversation-title"
          className="font-display text-[24px] font-medium tracking-[-0.4px]"
        >
          {t("guest.new_conversation.title", "Start a new conversation?")}
        </h2>
        <p className="mt-2 text-[14px] leading-relaxed text-black/60 dark:text-white/60">
          {t(
            isPublicAccountChoice
              ? "guest.new_conversation.public_description"
              : "guest.new_conversation.description",
            isPublicAccountChoice
              ? "Start over replaces this temporary conversation. Create an account to keep it and start another."
              : "Start over replaces this temporary conversation. Sign in to keep it and start another.",
          )}
        </p>
        <div className="mt-6 flex flex-col gap-2">
          <button
            type="button"
            disabled={isReplacing}
            onClick={onStartOver}
            className="min-h-11 rounded-full bg-black px-4 text-[14px] font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
          >
            {t("guest.new_conversation.start_over", "Start over")}
          </button>
          <button
            type="button"
            disabled={isReplacing}
            onClick={onConvert}
            className="min-h-11 rounded-full border border-black/12 px-4 text-[14px] font-medium dark:border-white/14"
          >
            {isPublicAccountChoice
              ? t("guest.new_conversation.create_account", "Create account")
              : t("guest.new_conversation.sign_in", "Sign in to keep it")}
          </button>
          <button
            type="button"
            disabled={isReplacing}
            onClick={onCancel}
            className="min-h-11 rounded-full px-4 text-[14px] text-black/60 dark:text-white/60"
          >
            {t("common.cancel", "Cancel")}
          </button>
        </div>
      </div>
    </div>
  );
}
