"use client";

import { Brain } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { MemoryRecallItem } from "@/lib/memory-recalls";

type MemoryRecallNoteProps = {
  recalls: MemoryRecallItem[];
};

/** Quiet post-answer context block: what Argus remembered, and why it is
 * visible. Never interactive with the turn itself. */
export default function MemoryRecallNote({ recalls }: MemoryRecallNoteProps) {
  const { t } = useTranslation();
  if (recalls.length === 0) return null;
  return (
    <aside
      aria-label={t("chat.memory.recall_title", "From your memory")}
      className="mt-3 w-full max-w-[min(100%,660px)] rounded-xl border border-black/[0.06] bg-black/[0.02] px-3.5 py-2.5 dark:border-white/[0.08] dark:bg-white/[0.03]"
    >
      <p className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-black/40 dark:text-white/40">
        <Brain className="h-3 w-3" />
        {t("chat.memory.recall_title", "From your memory")}
      </p>
      <ul className="mt-1.5 space-y-1">
        {recalls.map((recall) => (
          <li
            key={recall.record_id}
            className="text-[12.5px] leading-snug text-black/60 dark:text-white/60"
          >
            <span className="font-medium text-black/70 dark:text-white/70">
              {recall.label}
            </span>
            {": "}
            {recall.value}
          </li>
        ))}
      </ul>
      <p className="mt-1.5 text-[11px] text-black/35 dark:text-white/35">
        {t(
          "chat.memory.recall_note",
          "Saved decisions you confirmed. Manage them in Data Controls.",
        )}
      </p>
    </aside>
  );
}
