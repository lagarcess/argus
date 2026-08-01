"use client";

import { useEffect, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

const COLLAPSED_NOTE_CHARACTER_THRESHOLD = 240;
const COLLAPSED_NOTE_LINE_THRESHOLD = 5;

export function decisionNoteNeedsDisclosure(note: string): boolean {
  return (
    note.length > COLLAPSED_NOTE_CHARACTER_THRESHOLD ||
    note.split(/\r?\n/).length > COLLAPSED_NOTE_LINE_THRESHOLD
  );
}

export function decisionNoteElementOverflows(
  element: Pick<HTMLElement, "clientHeight" | "scrollHeight">,
): boolean {
  return element.scrollHeight > element.clientHeight;
}

export function DecisionNoteDisplay({ note }: { note: string }) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);
  const [hasOverflow, setHasOverflow] = useState(() =>
    decisionNoteNeedsDisclosure(note),
  );
  const noteId = useId();
  const noteRef = useRef<HTMLParagraphElement>(null);
  const canExpand = hasOverflow || expanded;

  useEffect(() => {
    if (expanded) return;
    const element = noteRef.current;
    if (!element) return;

    const measure = () => {
      setHasOverflow(decisionNoteElementOverflows(element));
    };
    measure();

    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, [expanded, note]);

  return (
    <div className="mt-2 min-w-0">
      <p
        ref={noteRef}
        id={noteId}
        data-decision-note="true"
        className={`whitespace-pre-wrap border-l-2 border-black/15 pl-3 text-[13px] italic leading-relaxed text-black/70 dark:border-white/20 dark:text-white/70 ${
          !expanded ? "line-clamp-5" : ""
        }`}
      >
        <span className="sr-only">
          {t("command_palette.decision_note_label", "Decision note: ")}
        </span>
        {note}
      </p>
      {canExpand ? (
        <button
          type="button"
          aria-controls={noteId}
          aria-expanded={expanded}
          onClick={() => setExpanded((current) => !current)}
          className="relative mt-1.5 min-h-8 rounded-full px-2 text-[11px] font-medium text-black/50 transition-colors before:absolute before:-inset-y-1.5 before:inset-x-0 hover:bg-black/[0.03] hover:text-black/70 dark:text-white/50 dark:hover:bg-white/[0.05] dark:hover:text-white/70"
        >
          {expanded
            ? t("command_palette.show_less_note", "Show less")
            : t("command_palette.show_full_note", "Show full note")}
        </button>
      ) : null}
    </div>
  );
}
