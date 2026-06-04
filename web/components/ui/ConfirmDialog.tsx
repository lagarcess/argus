"use client";

import { useEffect } from "react";

type ConfirmDialogProps = {
  isOpen: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  cancelLabel: string;
  isBusy?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
};

export function ConfirmDialog({
  isOpen,
  title,
  description,
  confirmLabel,
  cancelLabel,
  isBusy = false,
  onCancel,
  onConfirm,
}: ConfirmDialogProps) {
  useEffect(() => {
    if (!isOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onCancel();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [isOpen, onCancel]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[110] flex items-center justify-center bg-black/25 p-4 backdrop-blur-sm dark:bg-black/60">
      <button
        type="button"
        className="absolute inset-0"
        aria-label={cancelLabel}
        onClick={onCancel}
      />
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="argus-confirm-title"
        aria-describedby="argus-confirm-description"
        className="relative w-full max-w-sm rounded-[18px] border border-black/10 bg-white p-5 dark:border-white/10 dark:bg-[#1f2225]"
      >
        <h2
          id="argus-confirm-title"
          className="font-display text-[17px] font-semibold tracking-tight text-black dark:text-white"
        >
          {title}
        </h2>
        <p
          id="argus-confirm-description"
          className="mt-2 text-[13px] leading-relaxed text-black/55 dark:text-white/55"
        >
          {description}
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={isBusy}
            className="rounded-full border border-black/10 px-4 py-2 text-[13px] font-medium text-black transition-colors hover:bg-black/5 disabled:opacity-50 dark:border-white/10 dark:text-white dark:hover:bg-white/5"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isBusy}
            className="rounded-full bg-[#d66d75] px-4 py-2 text-[13px] font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
