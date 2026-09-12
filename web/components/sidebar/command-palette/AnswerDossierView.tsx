"use client";

import { ChevronRight } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import ComputedRerunPanel from "@/components/chat/ComputedRerunPanel";
import {
  AddDecisionButton,
  CurrentDecisionChip,
  DecisionEditorPanel,
  useDecisionDraft,
} from "@/components/chat/DecisionAffordance";
import type { AnswerDossier } from "@/lib/answer-dossier-contract";
import { rerunCard } from "@/lib/computed-rerun";
import type { DecisionNote } from "@/lib/decision-contract";
import { rerunMessageComputation } from "@/lib/decisions-api";
import { decisionRerunTreatment } from "@/lib/tool-outcome-treatment";
import { localizedToolText, parseToolResultCard, type ToolResultCard, type ToolScalar } from "@/lib/tool-result-card";
import { DecisionNoteDisplay } from "./DecisionNoteDisplay";

type AnswerDossierViewProps = {
  dossier: AnswerDossier;
  onOpenConversation?: () => void;
  openConversationDisabled?: boolean;
  onDecisionSaved?: (decision: DecisionNote) => void;
};

/**
 * A computed answer's dossier: what was asked, what Argus used with its
 * sources, what came out, the decision, and recompute. Editing an input is
 * free and instant through the message computation route and shows the new
 * result beside the stored one, which never changes. Nothing here calls a
 * model or retrieval.
 */
export function AnswerDossierView({
  dossier,
  onOpenConversation,
  openConversationDisabled = false,
  onDecisionSaved,
}: AnswerDossierViewProps) {
  const { t, i18n } = useTranslation();
  const locale = i18n.resolvedLanguage ?? i18n.language ?? "en";
  const stored = parseToolResultCard(dossier.card);
  const [latest, setLatest] = useState<ToolResultCard | null>(null);
  const [busy, setBusy] = useState(false);
  const [transportError, setTransportError] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState<ReturnType<typeof decisionRerunTreatment> | null>(null);
  useEffect(() => { setLatest(null); setTransportError(null); setUnavailable(null); }, [dossier.message_id]);
  const rerun = useCallback(async (changes: Record<string, ToolScalar>) => {
    setBusy(true);
    setTransportError(null);
    try {
      const response = await rerunMessageComputation(dossier.conversation_id, dossier.message_id, changes);
      if (response.rerun.status === "unavailable" && response.rerun.reason_code) {
        setUnavailable(decisionRerunTreatment(response.rerun.reason_code, t));
        setLatest(null);
      } else {
        setUnavailable(null);
        setLatest(rerunCard(response.rerun));
      }
    } catch {
      setTransportError(t("command_palette.answer_dossier.recompute_failed"));
    } finally {
      setBusy(false);
    }
  }, [dossier.conversation_id, dossier.message_id, t]);
  const action = dossier.actions.find((candidate) => candidate.type === "answer_decision") ?? null;
  const attachment = action && action.availability === "available"
    ? { kind: "message" as const, conversationId: dossier.conversation_id, messageId: dossier.message_id }
    : null;
  const [savedState, setSavedState] = useState(dossier.decision?.state ?? null);
  useEffect(() => { setSavedState(dossier.decision?.state ?? null); }, [dossier.decision?.state, dossier.message_id]);
  const draft = useDecisionDraft({
    attachment,
    initialState: dossier.decision?.state ?? null,
    onSaved: (decision) => { setSavedState(decision.decision_state); onDecisionSaved?.(decision); },
  });
  const computedAt = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" }).format(new Date(dossier.computed_at));
  // Decisions are for registered accounts; a guest sees no affordance here.
  const startDecision = () => draft.setOpen(!draft.open);
  return (
    <div data-answer-dossier={dossier.kind} data-dossier-scroll-region="true" className="flex min-h-0 flex-1 flex-col md:overflow-y-auto">
      <div className="rounded-[14px] border border-black/5 bg-white/70 p-4 dark:border-white/10 dark:bg-[#1f2225]/70">
        <div className="flex flex-wrap items-center gap-2">
          <span className="inline-flex rounded-full border border-black/8 bg-white/50 px-2.5 py-1 text-[11px] font-semibold text-black/45 dark:border-white/10 dark:bg-white/[0.03] dark:text-white/45">
            {t("command_palette.answer_dossier.type", "Calculation")}
          </span>
          <span className="text-[11px] text-black/35 dark:text-white/35">{computedAt}</span>
        </div>
        {stored ? (
          <h3 className="mt-3 font-display text-[20px] font-medium leading-tight text-black dark:text-white">
            {localizedToolText(stored.presentation.title, t)}
          </h3>
        ) : null}
        {dossier.asked ? (
          <div className="mt-3">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-black/40 dark:text-white/40">{t("command_palette.answer_dossier.asked", "You asked")}</p>
            <p data-answer-dossier-asked className="mt-1 text-[13px] leading-relaxed text-black/70 dark:text-white/70">{dossier.asked}</p>
          </div>
        ) : null}
        <div className="mt-4">
          {stored ? (
            <ComputedRerunPanel stored={stored} latest={latest} busy={busy} unavailable={unavailable} transportError={transportError}
              onRerun={(changes) => { void rerun(changes); }} t={t} locale={locale}
              labels={{ stored: t("command_palette.answer_dossier.stored", "Saved answer"), latest: t("command_palette.answer_dossier.latest", "With your changes") }} />
          ) : (
            <p role="status" className="text-sm text-black/60 dark:text-white/60">{t("tools.card.unavailable")}</p>
          )}
        </div>
        <div className="mt-4 border-t border-black/5 pt-4 dark:border-white/5">
          <div data-decision-state-row="true" className="flex min-h-8 flex-wrap items-center gap-2">
            {savedState ? <CurrentDecisionChip state={savedState} /> : attachment ? <AddDecisionButton onClick={startDecision} /> : (
              <p className="text-[13px] text-black/40 dark:text-white/40">{t("command_palette.no_decision_saved", "No decision saved")}</p>
            )}
          </div>
          {dossier.decision?.note ? <DecisionNoteDisplay key={`${dossier.message_id}:${dossier.decision.note}`} note={dossier.decision.note} /> : null}
          {!savedState && draft.open ? <DecisionEditorPanel draft={draft} /> : null}
        </div>
      </div>
      {onOpenConversation ? (
        <button type="button" disabled={openConversationDisabled} onClick={onOpenConversation}
          className="mt-auto flex min-h-11 shrink-0 items-center justify-between pt-4 text-left text-[12px] text-black/35 transition-colors hover:text-black disabled:cursor-not-allowed disabled:opacity-50 dark:text-white/35 dark:hover:text-white">
          <span>{t("command_palette.open_in_conversation", "Open in conversation")}</span>
          <ChevronRight className="h-4 w-4" aria-hidden="true" />
        </button>
      ) : null}
    </div>
  );
}
