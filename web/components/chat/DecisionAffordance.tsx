"use client";

import { useCallback, useState } from "react";
import { CalendarClock, Check, CircleX, Eye, FileText, TrendingUp } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { DecisionAttachment, DecisionNote } from "@/lib/decision-contract";
import {
  DECISION_NOTE_MAX_LENGTH,
  decisionNoteCharacterCount,
  decisionNoteCountIsVisible,
  nextDecisionNoteValue,
} from "@/lib/decision-note";
import { saveDecision } from "@/lib/decisions-api";
import { inlineFailureTextClass } from "@/lib/failure-treatment";
import type { DecisionState } from "@/lib/run-dossier-contract";
import type { Message } from "./types";

/**
 * One decision affordance, owned here, offered wherever an answer was
 * computed. The result card mounts it beside its actions; a computed answer
 * mounts it under its message. The route it posts to follows the attachment.
 */

export const DECISION_OPTIONS: readonly DecisionState[] = [
  "watching",
  "promising",
  "rejected",
  "revisit_later",
];

export const decisionActionClassName =
  "inline-flex min-h-9 cursor-pointer items-center gap-1.5 rounded-full border border-black/10 bg-black/[0.03] px-3 py-1.5 text-[12px] font-medium tracking-tight text-black/76 transition-colors hover:border-black/18 hover:bg-black/[0.06] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/20 active:scale-[0.98] dark:border-white/10 dark:bg-white/[0.04] dark:text-white/76 dark:hover:border-white/18 dark:hover:bg-white/[0.08] dark:focus-visible:ring-white/22";

type Translate = ReturnType<typeof useTranslation>["t"];

export function decisionStateLabel(state: DecisionState, t: Translate) {
  const fallback: Record<DecisionState, string> = {
    watching: "Watching",
    promising: "Promising",
    rejected: "Rejected",
    revisit_later: "Revisit later",
  };
  return t(`chat.result_card.decision_states.${state}`, fallback[state]);
}

export function decisionChipClassName(state: DecisionState, selected: boolean) {
  const base =
    "inline-flex min-h-9 items-center gap-1.5 rounded-full border px-3 py-1.5 text-[12px] font-medium tracking-tight transition-colors focus-visible:outline-none focus-visible:ring-2 active:scale-[0.98]";
  if (selected) {
    switch (state) {
      case "promising":
        return `${base} border-[#5ba897]/28 bg-[#5ba897]/10 text-[#3f816f] focus-visible:ring-[#5ba897]/20 dark:text-[#7bc1ad]`;
      case "rejected":
        return `${base} border-[#d66d75]/30 bg-[#d66d75]/10 text-[#ad4e56] focus-visible:ring-[#d66d75]/18 dark:text-[#e58c93]`;
      case "revisit_later":
        return `${base} border-[#b79246]/30 bg-[#b79246]/10 text-[#92722d] focus-visible:ring-[#b79246]/18 dark:text-[#d7b56f]`;
      case "watching":
      default:
        return `${base} border-[#6f8fb8]/30 bg-[#6f8fb8]/10 text-[#4f6f98] focus-visible:ring-[#6f8fb8]/18 dark:text-[#91afd1]`;
    }
  }
  switch (state) {
    case "promising":
      return `${base} border-[#5ba897]/18 bg-transparent text-[#4f8d7f] hover:bg-[#5ba897]/8 focus-visible:ring-[#5ba897]/14 dark:text-[#8abdad]`;
    case "rejected":
      return `${base} border-[#d66d75]/18 bg-transparent text-[#aa5c64] hover:bg-[#d66d75]/8 focus-visible:ring-[#d66d75]/14 dark:text-[#d9949a]`;
    case "revisit_later":
      return `${base} border-[#b79246]/18 bg-transparent text-[#8b743d] hover:bg-[#b79246]/8 focus-visible:ring-[#b79246]/14 dark:text-[#cdb074]`;
    case "watching":
    default:
      return `${base} border-[#6f8fb8]/18 bg-transparent text-[#5d7698] hover:bg-[#6f8fb8]/8 focus-visible:ring-[#6f8fb8]/14 dark:text-[#9eb4cf]`;
  }
}

export function DecisionStateIcon({ state }: { state: DecisionState }) {
  if (state === "promising") return <TrendingUp className="h-3.5 w-3.5" />;
  if (state === "rejected") return <CircleX className="h-3.5 w-3.5" />;
  if (state === "revisit_later")
    return <CalendarClock className="h-3.5 w-3.5" />;
  return <Eye className="h-3.5 w-3.5" />;
}

export type DecisionDraft = {
  open: boolean;
  selectedState: DecisionState;
  note: string;
  saving: boolean;
  failed: boolean;
};

export type DecisionDraftController = DecisionDraft & {
  setOpen: (open: boolean) => void;
  selectState: (state: DecisionState) => void;
  setNote: (note: string) => void;
  cancel: () => void;
  save: () => Promise<void>;
};

/** Draft state and the save call for one attachment; the caller renders it. */
export function useDecisionDraft({
  attachment,
  initialState,
  onSaved,
}: {
  attachment: DecisionAttachment | null;
  initialState?: DecisionState | null;
  onSaved?: (decision: DecisionNote) => void;
}): DecisionDraftController {
  const [open, setOpenValue] = useState(false);
  const [selectedState, setSelectedState] = useState<DecisionState>(
    initialState ?? "watching",
  );
  const [note, setNoteValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [failed, setFailed] = useState(false);

  const selectState = useCallback((state: DecisionState) => {
    setSelectedState(state);
    setFailed(false);
  }, []);
  const setNote = useCallback((next: string) => {
    setNoteValue((current) => nextDecisionNoteValue(current, next));
  }, []);
  const setOpen = useCallback((next: boolean) => {
    setOpenValue(next);
    setFailed(false);
  }, []);
  const cancel = useCallback(() => setOpen(false), [setOpen]);
  const save = useCallback(async () => {
    if (!attachment || saving) return;
    setSaving(true);
    setFailed(false);
    try {
      const response = await saveDecision(attachment, {
        decision_state: selectedState,
        note,
      });
      onSaved?.(response.decision);
      setNoteValue("");
      setOpenValue(false);
    } catch {
      setFailed(true);
    } finally {
      setSaving(false);
    }
  }, [attachment, note, onSaved, saving, selectedState]);

  return {
    open,
    selectedState,
    note,
    saving,
    failed,
    setOpen,
    selectState,
    setNote,
    cancel,
    save,
  };
}

export function CurrentDecisionChip({ state }: { state: DecisionState }) {
  const { t } = useTranslation();
  return (
    <span className="inline-flex min-h-9 items-center gap-1.5 rounded-full border border-black/10 bg-black/[0.02] px-3 py-1.5 text-[12px] font-medium tracking-tight text-[#505a63] dark:border-white/10 dark:bg-white/[0.03] dark:text-[#8d969e]">
      <FileText className="h-3.5 w-3.5" />
      {t("chat.result_card.decision", { state: decisionStateLabel(state, t) })}
    </span>
  );
}

export function AddDecisionButton({ onClick }: { onClick: () => void }) {
  const { t } = useTranslation();
  return (
    <button type="button" onClick={onClick} className={decisionActionClassName}>
      <FileText className="h-3.5 w-3.5" />
      {t("chat.result_card.add_decision", "Add decision")}
    </button>
  );
}

/** The chips, note, and save row; identical wherever a decision is offered. */
export function DecisionEditorPanel({ draft }: { draft: DecisionDraftController }) {
  const { t } = useTranslation();
  const noteCount = decisionNoteCharacterCount(draft.note);
  return (
    <div className="border-t border-[#c9c9cd]/30 px-4 py-4 dark:border-white/[0.06] sm:px-5">
      <div className="flex flex-wrap gap-2">
        {DECISION_OPTIONS.map((state) => (
          <button
            key={state}
            type="button"
            onClick={() => draft.selectState(state)}
            className={decisionChipClassName(state, draft.selectedState === state)}
          >
            <DecisionStateIcon state={state} />
            {decisionStateLabel(state, t)}
          </button>
        ))}
      </div>
      <textarea
        value={draft.note}
        onChange={(event) => draft.setNote(event.target.value)}
        placeholder={t(
          "chat.result_card.decision_note_placeholder",
          "Optional note for future you",
        )}
        className="mt-3 min-h-20 w-full resize-y rounded-[14px] border border-black/10 bg-white px-3 py-2 text-[13px] leading-relaxed text-[#191c1f] outline-none transition-colors placeholder:text-[#8d969e] focus:border-black/24 focus:ring-2 focus:ring-black/8 dark:border-white/10 dark:bg-[#1f2225] dark:text-white dark:focus:border-white/20 dark:focus:ring-white/10"
      />
      {decisionNoteCountIsVisible(draft.note) ? (
        <p className="mt-1 text-right text-[11px] text-[#8d969e]">
          {t("command_palette.decision_note_count", {
            count: noteCount,
            max: DECISION_NOTE_MAX_LENGTH,
            defaultValue: `${noteCount} / ${DECISION_NOTE_MAX_LENGTH}`,
          })}
        </p>
      ) : null}
      {draft.failed && (
        <p role="alert" className={`mt-2 text-[12px] ${inlineFailureTextClass}`}>
          {t("chat.error_generic", "Something went wrong. Please try again.")}
        </p>
      )}
      <div className="mt-3 flex justify-end gap-2">
        <button
          type="button"
          onClick={draft.cancel}
          className="inline-flex min-h-9 items-center rounded-full border border-black/10 px-3 py-1.5 text-[12px] font-medium text-[#505a63] transition-colors hover:bg-black/[0.03] dark:border-white/10 dark:text-[#8d969e] dark:hover:bg-white/[0.05]"
        >
          {t("common.cancel", "Cancel")}
        </button>
        <button
          type="button"
          disabled={draft.saving}
          onClick={() => void draft.save()}
          className="inline-flex min-h-9 items-center gap-1.5 rounded-full bg-[#191c1f] px-3.5 py-1.5 text-[12px] font-medium text-white transition-colors hover:bg-black disabled:cursor-not-allowed disabled:opacity-55 dark:bg-white dark:text-[#191c1f] dark:hover:bg-white/90"
        >
          <Check className="h-3.5 w-3.5" />
          {t("chat.result_card.save_decision", "Save decision")}
        </button>
      </div>
    </div>
  );
}

/** The attachment a computed answer offers a decision on, or null. */
export function computedAnswerAttachment(
  message: Pick<Message, "id" | "computation">,
  conversationId: string | null | undefined,
): DecisionAttachment | null {
  if (!message.computation || !conversationId) return null;
  return { kind: "message", conversationId, messageId: message.id };
}

type ComputedAnswerDecisionProps = {
  message: Pick<Message, "id" | "computation" | "decisionState">;
  conversationId: string | null | undefined;
  onSaved?: (decision: DecisionNote) => void;
};

/**
 * The decision affordance under a computed answer. Rendered only when the
 * backend declared a computation on the message; the saved state it shows is
 * the backend's stamp, never inferred from prose.
 */
export function ComputedAnswerDecision({
  message,
  conversationId,
  onSaved,
}: ComputedAnswerDecisionProps) {
  const attachment = computedAnswerAttachment(message, conversationId);
  const [savedState, setSavedState] = useState<DecisionState | null>(
    message.decisionState ?? null,
  );
  const draft = useDecisionDraft({
    attachment,
    initialState: message.decisionState,
    onSaved: (decision) => {
      setSavedState(decision.decision_state);
      onSaved?.(decision);
    },
  });
  if (!attachment) return null;
  const visibleState = savedState ?? message.decisionState ?? null;
  return (
    <div
      data-testid="computed-answer-decision"
      className="mt-3 w-full max-w-[min(100%,660px)] overflow-hidden rounded-[20px] border border-[#c9c9cd] bg-white dark:border-white/12 dark:bg-[#191c1f]"
    >
      <div className="flex flex-wrap gap-2 px-4 py-3.5 sm:px-5">
        {visibleState ? (
          <CurrentDecisionChip state={visibleState} />
        ) : (
          <AddDecisionButton onClick={() => draft.setOpen(!draft.open)} />
        )}
      </div>
      {!visibleState && draft.open ? <DecisionEditorPanel draft={draft} /> : null}
    </div>
  );
}
