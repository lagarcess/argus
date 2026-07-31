"use client";

import { ChevronRight, FileText, RotateCcw } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  commandPaletteDecisionStateFallback,
  commandPaletteDecisionVerb,
} from "@/lib/command-palette-items";
import type {
  DecisionState,
  RunDossier,
  SearchDecisionAction,
  SearchRunFreshAction,
} from "@/lib/run-dossier-contract";
import {
  formatRunDossierMetrics,
  formatRunDossierSetup,
} from "@/lib/run-dossier-items";

import { DecisionEditor } from "./DecisionEditor";

type RunDossierViewProps = {
  dossier: RunDossier;
  totalRuns: number;
  decidedRuns: number;
  onOpenHistory?: () => void;
  onOpenConversation: () => void;
  onRunFresh: (action: SearchRunFreshAction) => Promise<void> | void;
  onSaveDecision: (
    action: SearchDecisionAction,
    draft: { decision_state: DecisionState; note: string },
  ) => Promise<void>;
  openConversationDisabled?: boolean;
  runFreshDisabled?: boolean;
};

type DecisionDraft = {
  state: DecisionState;
  note: string;
};

function formatCompletedAt(value: string, locale: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function RunDossierView({
  dossier,
  totalRuns,
  decidedRuns,
  onOpenHistory,
  onOpenConversation,
  onRunFresh,
  onSaveDecision,
  openConversationDisabled = false,
  runFreshDisabled = false,
}: RunDossierViewProps) {
  const { t, i18n } = useTranslation();
  const locale = i18n.resolvedLanguage ?? i18n.language ?? "en";
  const decisionAction = dossier.actions.find(
    (action): action is SearchDecisionAction => action.type === "decision",
  );
  const runFreshAction = dossier.actions.find(
    (action): action is SearchRunFreshAction => action.type === "run_fresh",
  );
  const [draft, setDraft] = useState<DecisionDraft | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveFailed, setSaveFailed] = useState(false);
  const [saved, setSaved] = useState(false);
  const activeRunIdRef = useRef(dossier.run_id);

  useEffect(() => {
    activeRunIdRef.current = dossier.run_id;
    setDraft(null);
    setSaving(false);
    setSaveFailed(false);
    setSaved(false);
  }, [decisionAction?.evidence_artifact_id, dossier.run_id]);

  useEffect(() => {
    if (!saved) return;
    const timeout = window.setTimeout(() => setSaved(false), 2000);
    return () => window.clearTimeout(timeout);
  }, [saved]);

  const setup = useMemo(
    () => formatRunDossierSetup(dossier, t, locale),
    [dossier, locale, t],
  );
  const metrics = useMemo(
    () => formatRunDossierMetrics(dossier, t, locale),
    [dossier, locale, t],
  );
  const completedAt = formatCompletedAt(dossier.completed_at, locale);

  const startDecisionEdit = () => {
    if (!decisionAction) return;
    setSaved(false);
    setSaveFailed(false);
    setDraft({
      state: decisionAction.decision_state ?? "watching",
      note: decisionAction.note ?? "",
    });
  };

  const saveDecision = async (
    action: SearchDecisionAction,
    nextDraft: { decision_state: DecisionState; note: string },
  ) => {
    if (saving) return;
    const runId = dossier.run_id;
    setSaving(true);
    setSaveFailed(false);
    try {
      await onSaveDecision(action, nextDraft);
      if (activeRunIdRef.current !== runId) return;
      setDraft(null);
      setSaved(true);
    } catch {
      if (activeRunIdRef.current !== runId) return;
      setSaveFailed(true);
    } finally {
      if (activeRunIdRef.current === runId) setSaving(false);
    }
  };

  const conversationUnavailable =
    openConversationDisabled || dossier.result_message_id === null;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="rounded-[14px] border border-black/5 bg-white/70 p-4 dark:border-white/10 dark:bg-[#1f2225]/70">
        <div className="flex flex-wrap items-center gap-2">
          <span className="inline-flex rounded-full border border-black/8 bg-white/50 px-2.5 py-1 text-[11px] font-semibold text-black/45 dark:border-white/10 dark:bg-white/[0.03] dark:text-white/45">
            {t("command_palette.type.backtest", "Backtest")}
          </span>
          {completedAt && (
            <span className="text-[11px] text-black/35 dark:text-white/35">
              {completedAt}
            </span>
          )}
        </div>

        <h3 className="mt-3 font-display text-[20px] font-medium leading-tight text-black dark:text-white">
          {dossier.run_label}
        </h3>

        {setup.length > 0 && (
          <p className="mt-3 text-[12px] leading-relaxed text-black/50 dark:text-white/50">
            {setup.join(" · ")}
          </p>
        )}

        {(dossier.outcome.quick_take || metrics.length > 0) && (
          <div className="mt-4 border-t border-black/5 pt-4 dark:border-white/5">
            {dossier.outcome.quick_take && (
              <p className="text-[13px] leading-relaxed text-black/65 dark:text-white/65">
                {dossier.outcome.quick_take}
              </p>
            )}
            {metrics.length > 0 && (
              <dl className="mt-3 grid grid-cols-2 gap-2">
                {metrics.map((metric) => (
                  <div
                    key={metric.name}
                    className="rounded-[10px] bg-black/[0.025] px-3 py-2 dark:bg-white/[0.035]"
                  >
                    <dt className="text-[10px] font-semibold uppercase tracking-wider text-black/30 dark:text-white/30">
                      {metric.name}
                    </dt>
                    <dd className="mt-1 text-[13px] font-medium text-black/70 dark:text-white/70">
                      {metric.value}
                    </dd>
                  </div>
                ))}
              </dl>
            )}
          </div>
        )}

        <div className="mt-4 border-t border-black/5 pt-4 dark:border-white/5">
          {draft && decisionAction ? (
            <DecisionEditor
              action={decisionAction}
              decisionState={draft.state}
              note={draft.note}
              saving={saving}
              error={saveFailed}
              onDecisionStateChange={(state) => {
                setSaveFailed(false);
                setDraft((current) =>
                  current ? { ...current, state } : current,
                );
              }}
              onNoteChange={(note) => {
                setSaveFailed(false);
                setDraft((current) =>
                  current ? { ...current, note } : current,
                );
              }}
              onCancel={() => {
                setDraft(null);
                setSaveFailed(false);
              }}
              onSave={saveDecision}
            />
          ) : (
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                {dossier.decision ? (
                  <>
                    <span className="inline-flex rounded-full border border-black/8 px-2.5 py-1 text-[11px] font-semibold text-black/55 dark:border-white/10 dark:text-white/55">
                      {t(
                        `chat.result_card.decision_states.${dossier.decision.state}`,
                        commandPaletteDecisionStateFallback(
                          dossier.decision.state,
                        ),
                      )}
                    </span>
                    {dossier.decision.note && (
                      <p className="mt-2 whitespace-pre-wrap border-l-2 border-black/15 pl-3 text-[13px] italic leading-relaxed text-black/70 dark:border-white/20 dark:text-white/70">
                        <span className="sr-only">
                          {t(
                            "command_palette.decision_note_label",
                            "Decision note: ",
                          )}
                        </span>
                        {dossier.decision.note}
                      </p>
                    )}
                  </>
                ) : (
                  <p className="text-[13px] text-black/40 dark:text-white/40">
                    {t(
                      "command_palette.no_decision_saved",
                      "No decision saved",
                    )}
                  </p>
                )}
              </div>
              {decisionAction && (
                <button
                  type="button"
                  onClick={startDecisionEdit}
                  className="inline-flex min-h-11 shrink-0 items-center gap-2 rounded-full border border-black/10 px-3 text-[12px] font-medium text-black/60 transition-colors hover:bg-black/[0.03] dark:border-white/10 dark:text-white/60 dark:hover:bg-white/[0.05]"
                >
                  <FileText className="h-4 w-4" aria-hidden="true" />
                  {commandPaletteDecisionVerb(decisionAction) === "add"
                    ? t("command_palette.add_decision_short", "Add decision")
                    : t(
                        "command_palette.change_decision_short",
                        "Change decision",
                      )}
                </button>
              )}
            </div>
          )}
          {saved && (
            <p
              className="mt-2 text-[12px] text-[#3f816f] dark:text-[#7bc1ad]"
              aria-live="polite"
            >
              {t("command_palette.decision_saved", "Saved")}
            </p>
          )}
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {runFreshAction && (
          <button
            type="button"
            disabled={runFreshDisabled}
            onClick={() => void onRunFresh(runFreshAction)}
            className="inline-flex min-h-11 items-center gap-2 rounded-full bg-[#191c1f] px-4 text-[13px] font-medium text-white transition-colors hover:bg-black disabled:cursor-not-allowed disabled:opacity-50 dark:bg-white dark:text-[#191c1f] dark:hover:bg-white/90"
          >
            <RotateCcw className="h-4 w-4" aria-hidden="true" />
            {t("command_palette.run_fresh_short", "Run it fresh")}
          </button>
        )}
      </div>

      <button
        type="button"
        aria-label={t(
          "command_palette.open_in_conversation",
          "Open in conversation",
        )}
        disabled={conversationUnavailable}
        onClick={onOpenConversation}
        className="mt-auto flex min-h-11 shrink-0 items-center justify-between border-t border-black/5 pt-4 text-left text-[12px] text-black/35 transition-colors hover:text-black disabled:cursor-not-allowed disabled:opacity-50 dark:border-white/5 dark:text-white/35 dark:hover:text-white"
      >
        <span>
          {t(
            "command_palette.open_in_conversation",
            "Open in conversation",
          )}
        </span>
        <ChevronRight className="h-4 w-4" aria-hidden="true" />
      </button>

      <button
        type="button"
        disabled={!onOpenHistory}
        onClick={onOpenHistory}
        className="flex min-h-11 shrink-0 items-center justify-between border-t border-black/5 text-left text-[12px] text-black/45 transition-colors hover:text-black disabled:cursor-not-allowed disabled:opacity-50 dark:border-white/5 dark:text-white/45 dark:hover:text-white"
      >
        <span>{t("command_palette.decision_history", "Decision history")}</span>
        <span className="inline-flex items-center gap-1">
          {t("command_palette.decision_history_count", {
            decided: decidedRuns,
            total: totalRuns,
            defaultValue: `${decidedRuns} of ${totalRuns} decided`,
          })}
          <ChevronRight className="h-4 w-4" aria-hidden="true" />
        </span>
      </button>
    </div>
  );
}
