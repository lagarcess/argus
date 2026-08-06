"use client";

import { RotateCcw } from "lucide-react";
import { useTranslation } from "react-i18next";

import {
  retestReceiptContextLine,
  type RetestReceipt as RetestReceiptPayload,
} from "@/lib/chat-retest";

type RetestReceiptProps = {
  receipt: RetestReceiptPayload | null;
  actionLabel: string;
  pending?: boolean;
};

/**
 * The submitted action is valid, so the receipt stays neutral: amber belongs to
 * a system recovery response rendered beneath it.
 */
export function RetestReceipt({
  receipt,
  actionLabel,
  pending = false,
}: RetestReceiptProps) {
  const { t, i18n } = useTranslation();
  const contextLine = receipt
    ? retestReceiptContextLine(receipt, (key, defaultValue, options) =>
        t(key, { defaultValue, ...(options ?? {}) }),
        i18n.language,
      )
    : "";
  const receiptState = receipt ? "ready" : "pending";
  return (
    <div
      data-retest-receipt-state={receiptState}
      className="max-w-[85%] rounded-[20px] border border-black/10 bg-black/[0.03] px-4 py-2.5 text-black/75 dark:border-white/12 dark:bg-white/[0.06] dark:text-white/75"
    >
      <p className="flex items-center gap-2 text-[14px] font-medium leading-[1.45]">
        <RotateCcw aria-hidden className="h-3.5 w-3.5 shrink-0 opacity-70" />
        <span>{actionLabel}</span>
      </p>
      {(pending || contextLine) && (
        <p
          data-retest-receipt-context-row="true"
          className="mt-0.5 flex min-h-[95px] items-center pl-[22px] text-[13px] leading-[1.45] text-black/55 sm:min-h-[57px] dark:text-white/55"
        >
          {pending ? (
            <span
              aria-hidden="true"
              className="flex h-[95px] w-full flex-col justify-center gap-2 sm:h-[57px]"
            >
              <span className="flex items-center gap-1.5">
                <span className="h-1.5 w-14 animate-pulse rounded-full bg-black/10 motion-reduce:animate-none dark:bg-white/10" />
                <span className="h-1.5 w-24 animate-pulse rounded-full bg-black/10 motion-reduce:animate-none dark:bg-white/10" />
              </span>
              <span className="h-1.5 w-4/5 animate-pulse rounded-full bg-black/10 motion-reduce:animate-none dark:bg-white/10" />
              <span className="h-1.5 w-3/5 animate-pulse rounded-full bg-black/10 motion-reduce:animate-none dark:bg-white/10" />
              <span className="h-1.5 w-2/3 animate-pulse rounded-full bg-black/10 motion-reduce:animate-none sm:hidden dark:bg-white/10" />
              <span className="h-1.5 w-2/5 animate-pulse rounded-full bg-black/10 motion-reduce:animate-none sm:hidden dark:bg-white/10" />
            </span>
          ) : (
            <span>{contextLine}</span>
          )}
        </p>
      )}
    </div>
  );
}
