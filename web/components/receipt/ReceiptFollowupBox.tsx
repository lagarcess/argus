"use client";

import type { FormEventHandler, ReactNode } from "react";
import { ArrowUp } from "lucide-react";
import type { ReceiptCopy } from "@/lib/receipt-copy";

/** Shared composer geometry. The caller owns authentication and submission. */
export default function ReceiptFollowupBox({ copy, value = "", onChange, onSubmit, disabled = true, busy = false, children }: {
  copy: ReceiptCopy;
  value?: string;
  onChange?: (value: string) => void;
  onSubmit?: FormEventHandler<HTMLFormElement>;
  disabled?: boolean;
  busy?: boolean;
  children?: ReactNode;
}) {
  return <form aria-label={copy.followup.label} onSubmit={onSubmit} className="w-full">
    <div className="flex items-end gap-3 rounded-[28px] border border-black/10 bg-black/[0.025] p-3 dark:border-white/15 dark:bg-white/[0.04]">
      <textarea aria-label={copy.followup.label} placeholder={copy.followup.placeholder} value={value} onChange={(event) => onChange?.(event.target.value)} disabled={disabled || busy} rows={2} className="min-h-11 min-w-0 flex-1 resize-none bg-transparent px-2 py-2 text-[16px] leading-6 text-black outline-none placeholder:text-black/45 focus-visible:ring-2 focus-visible:ring-[#5ba897] disabled:opacity-70 dark:text-white dark:placeholder:text-white/45" />
      <button type="submit" aria-label={busy ? copy.followup.starting : copy.followup.send} disabled={disabled || busy || !value.trim()} className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-[#191c1f] text-white transition-colors hover:bg-black/80 focus-visible:ring-2 focus-visible:ring-[#5ba897] disabled:opacity-35 dark:bg-white dark:text-[#191c1f] dark:hover:bg-white/85"><ArrowUp className="h-5 w-5" aria-hidden="true" /></button>
    </div>
    <p className="mt-2 px-3 text-[12px] leading-relaxed text-black/50 dark:text-white/50">{copy.followup.hint}</p>
    {children}
  </form>;
}
