"use client";

import { RotateCcw } from "lucide-react";
import { useTranslation } from "react-i18next";

import {
  retestReceiptContextLine,
  type RetestReceipt as RetestReceiptPayload,
} from "@/lib/chat-retest";

type RetestReceiptProps = {
  receipt: RetestReceiptPayload;
  actionLabel: string;
};

/**
 * The submitted action is valid, so the receipt stays neutral: amber belongs to
 * a system recovery response rendered beneath it.
 */
export function RetestReceipt({ receipt, actionLabel }: RetestReceiptProps) {
  const { t, i18n } = useTranslation();
  const contextLine = retestReceiptContextLine(receipt, (key, defaultValue, options) =>
    t(key, { defaultValue, ...(options ?? {}) }),
    i18n.language,
  );
  return (
    <div className="max-w-[85%] rounded-[20px] border border-black/10 bg-black/[0.03] px-4 py-2.5 text-black/75 dark:border-white/12 dark:bg-white/[0.06] dark:text-white/75">
      <p className="flex items-center gap-2 text-[14px] font-medium leading-[1.45]">
        <RotateCcw aria-hidden className="h-3.5 w-3.5 shrink-0 opacity-70" />
        <span>{actionLabel}</span>
      </p>
      {contextLine && (
        <p className="mt-0.5 pl-[22px] text-[13px] leading-[1.45] text-black/55 dark:text-white/55">
          {contextLine}
        </p>
      )}
    </div>
  );
}
