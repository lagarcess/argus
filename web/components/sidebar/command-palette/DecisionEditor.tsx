"use client";

import { Check, Loader2 } from "lucide-react";
import { useId, type KeyboardEvent as ReactKeyboardEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  DECISION_NOTE_MAX_LENGTH,
  decisionNoteCharacterCount,
  decisionNoteCountIsVisible,
  nextDecisionNoteValue,
} from "@/lib/decision-note";
import type {
  DecisionState,
  SearchDecisionAction,
} from "@/lib/run-dossier-contract";

const DECISION_STATES: readonly DecisionState[] = [
  "watching",
  "promising",
  "rejected",
  "revisit_later",
];

type DecisionEditorProps = {
  action: SearchDecisionAction;
  decisionState: DecisionState;
  note: string;
  saving: boolean;
  error: boolean;
  onDecisionStateChange: (state: DecisionState) => void;
  onNoteChange: (note: string) => void;
  onCancel: () => void;
  onSave: (
    action: SearchDecisionAction,
    draft: { decision_state: DecisionState; note: string },
  ) => Promise<void> | void;
};

type DecisionEditorKeyboardInput = {
  key: string;
  metaKey: boolean;
  ctrlKey: boolean;
};

export function decisionEditorKeyboardAction({
  key,
  metaKey,
  ctrlKey,
}: DecisionEditorKeyboardInput) {
  const save = key === "Enter" && (metaKey || ctrlKey);
  return { save, preventDefault: save };
}

function decisionChipClassName(state: DecisionState, selected: boolean) {
  const base =
    "min-h-11 shrink-0 rounded-full border px-3 py-1 text-[11px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 disabled:opacity-60 active:scale-[0.98]";
  if (!selected) {
    return `${base} border-black/8 text-black/45 hover:bg-black/[0.03] focus-visible:ring-black/15 dark:border-white/10 dark:text-white/45 dark:hover:bg-white/[0.04] dark:focus-visible:ring-white/15`;
  }
  switch (state) {
    case "promising":
      return `${base} border-[#5ba897]/34 bg-[#5ba897]/11 text-[#3f816f] focus-visible:ring-[#5ba897]/20 dark:text-[#7bc1ad]`;
    case "rejected":
      return `${base} border-[#d66d75]/34 bg-[#d66d75]/11 text-[#ad4e56] focus-visible:ring-[#d66d75]/18 dark:text-[#e58c93]`;
    case "revisit_later":
      return `${base} border-[#b79246]/34 bg-[#b79246]/11 text-[#92722d] focus-visible:ring-[#b79246]/18 dark:text-[#d7b56f]`;
    case "watching":
    default:
      return `${base} border-[#6f8fb8]/34 bg-[#6f8fb8]/11 text-[#4f6f98] focus-visible:ring-[#6f8fb8]/18 dark:text-[#91afd1]`;
  }
}

function decisionStateFallback(state: DecisionState) {
  switch (state) {
    case "promising":
      return "Promising";
    case "rejected":
      return "Rejected";
    case "revisit_later":
      return "Revisit later";
    case "watching":
      return "Watching";
  }
}

export function DecisionEditor({
  action,
  decisionState,
  note,
  saving,
  error,
  onDecisionStateChange,
  onNoteChange,
  onCancel,
  onSave,
}: DecisionEditorProps) {
  const { t } = useTranslation();
  const countId = useId();
  const noteCount = decisionNoteCharacterCount(note);
  const showNoteCount = decisionNoteCountIsVisible(note);
  const noteTooLong = noteCount > DECISION_NOTE_MAX_LENGTH;

  const save = () => {
    if (saving || noteTooLong) return;
    void onSave(action, { decision_state: decisionState, note });
  };

  const handleKeyDown = (event: ReactKeyboardEvent<HTMLTextAreaElement>) => {
    const keyboardAction = decisionEditorKeyboardAction(event);
    if (keyboardAction.preventDefault) event.preventDefault();
    if (keyboardAction.save) save();
  };

  return (
    <div className="rounded-[14px] border border-black/8 bg-white/70 p-3 dark:border-white/10 dark:bg-white/[0.025]">
      <div className="flex flex-wrap gap-2">
        {DECISION_STATES.map((state) => (
          <button
            key={state}
            type="button"
            aria-pressed={decisionState === state}
            disabled={saving}
            onClick={() => onDecisionStateChange(state)}
            className={decisionChipClassName(
              state,
              decisionState === state,
            )}
          >
            {t(
              `chat.result_card.decision_states.${state}`,
              decisionStateFallback(state),
            )}
          </button>
        ))}
      </div>
      <label htmlFor="command-palette-decision-note" className="sr-only">
        {t("command_palette.decision_note_editor_label", "Decision note")}
      </label>
      <textarea
        id="command-palette-decision-note"
        value={note}
        aria-describedby={showNoteCount ? countId : undefined}
        disabled={saving}
        onChange={(event) =>
          onNoteChange(nextDecisionNoteValue(note, event.target.value))
        }
        onKeyDown={handleKeyDown}
        placeholder={t(
          "chat.result_card.decision_note_placeholder",
          "Optional note for future you",
        )}
        className="mt-3 min-h-24 w-full resize-y rounded-[12px] border border-black/10 bg-white px-3 py-2 text-[16px] leading-relaxed text-black outline-none focus:border-black/25 disabled:opacity-60 dark:border-white/10 dark:bg-[#1f2225] dark:text-white dark:focus:border-white/25"
      />
      {showNoteCount ? (
        <p
          id={countId}
          className={`mt-1 text-right text-[11px] ${
            noteTooLong
              ? "text-[#d66d75]"
              : "text-black/35 dark:text-white/35"
          }`}
        >
          {t("command_palette.decision_note_count", {
            count: noteCount,
            max: DECISION_NOTE_MAX_LENGTH,
            defaultValue: `${noteCount} / ${DECISION_NOTE_MAX_LENGTH}`,
          })}
        </p>
      ) : null}
      {error && (
        <p className="mt-2 text-[12px] text-[#d66d75]" role="alert">
          {t(
            "chat.error_generic",
            "Something went wrong. Please try again.",
          )}
        </p>
      )}
      <div className="mt-3 flex justify-end gap-2">
        <button
          type="button"
          disabled={saving}
          onClick={onCancel}
          className="min-h-11 rounded-full border border-black/10 px-4 text-[13px] font-medium text-black/55 disabled:opacity-60 dark:border-white/10 dark:text-white/55"
        >
          {t("common.cancel", "Cancel")}
        </button>
        <button
          type="button"
          disabled={saving || noteTooLong}
          onClick={save}
          className="inline-flex min-h-11 items-center gap-2 rounded-full bg-[#191c1f] px-4 text-[13px] font-medium text-white disabled:opacity-55 dark:bg-white dark:text-[#191c1f]"
        >
          {saving ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          ) : (
            <Check className="h-4 w-4" aria-hidden="true" />
          )}
          {t("command_palette.save_decision", "Save decision")}
        </button>
      </div>
    </div>
  );
}
