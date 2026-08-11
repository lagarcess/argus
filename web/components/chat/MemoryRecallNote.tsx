"use client";

import { Brain, ChevronDown } from "lucide-react";
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import type { MemoryRecallItem } from "@/lib/memory-recalls";

type MemoryRecallNoteProps = {
  recalls: MemoryRecallItem[];
};

type MemoryRecallDisclosureProps = MemoryRecallNoteProps & {
  open: boolean;
  panelId: string;
  onToggle: () => void;
};

/** Persistent one-line trigger; the recalled memory stays behind a click.
 *
 * The trigger must stay outside the hover-gated footer to remain reachable.
 */
export function MemoryRecallDisclosure({
  recalls,
  open,
  panelId,
  onToggle,
}: MemoryRecallDisclosureProps) {
  const { t } = useTranslation();
  if (recalls.length === 0) return null;
  return (
    <aside className="mt-3 w-full max-w-[min(100%,660px)]">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        aria-controls={panelId}
        data-testid="memory-recall-toggle"
        className="flex h-7 w-full items-center gap-1.5 rounded-md text-left outline-none transition-colors hover:text-black/60 focus-visible:ring-2 focus-visible:ring-black/20 dark:hover:text-white/60 dark:focus-visible:ring-white/30 motion-reduce:transition-none text-black/40 dark:text-white/40"
      >
        <Brain className="h-3 w-3 shrink-0" aria-hidden="true" />
        <span className="whitespace-nowrap text-[11px] font-medium uppercase tracking-wide">
          {t("chat.memory.recall_title", "From your memory")}
        </span>
        <span className="h-px flex-1 bg-black/10 dark:bg-white/10" aria-hidden="true" />
        <span className="whitespace-nowrap text-[11px] text-black/35 dark:text-white/35">
          {open
            ? t("chat.memory.recall_hide", "Hide")
            : t("chat.memory.recall_show", "Show")}
        </span>
        <ChevronDown
          className={`h-3.5 w-3.5 shrink-0 text-black/35 transition-transform duration-200 motion-reduce:transition-none dark:text-white/35 ${
            open ? "rotate-180" : ""
          }`}
          aria-hidden="true"
        />
      </button>
      <div
        id={panelId}
        className={`grid transition-[grid-template-rows,opacity] duration-200 ease-out motion-reduce:transition-none ${
          open ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"
        }`}
        aria-hidden={!open}
        inert={!open}
      >
        <div className="min-h-0 overflow-hidden">
          <div className="mt-1 rounded-xl border border-black/[0.06] bg-black/[0.02] px-3.5 py-2.5 dark:border-white/[0.08] dark:bg-white/[0.03]">
            <ul className="space-y-1">
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
          </div>
        </div>
      </div>
    </aside>
  );
}

/** Quiet post-answer context block: what Argus remembered, and why it is
 * visible. Never interactive with the turn itself. */
export default function MemoryRecallNote({ recalls }: MemoryRecallNoteProps) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  return (
    <MemoryRecallDisclosure
      recalls={recalls}
      open={open}
      panelId={panelId}
      onToggle={() => setOpen((current) => !current)}
    />
  );
}
