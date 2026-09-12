"use client";

import React, { useEffect, useRef, useState } from "react";
import type { ToolTranslator } from "@/lib/tool-result-card";
import { localizedToolText, type ToolResultCard, type ToolScalar } from "@/lib/tool-result-card";
import { alreadyUpToDateText, toolOutcomeTreatment, type ToolOutcomeTreatment } from "@/lib/tool-outcome-treatment";
import { changesAreEmpty, rerunChanges } from "@/lib/computed-rerun";
import ToolCardPresentation from "./ToolCardPresentation";
import ToolInputEditor from "./ToolInputEditor";
import ToolOutcomeNotice from "./ToolOutcomeNotice";

/**
 * The stored result beside today's, with inputs editable. One panel serves a
 * reopened decision and the Search dossier: edits re-run through the caller's
 * route, the stored result never moves, and every unsuccessful outcome renders
 * through the treatment owner.
 */
export default function ComputedRerunPanel({ stored, latest, busy, unavailable, transportError, onRerun, t, locale, labels }: {
  stored: ToolResultCard;
  latest: ToolResultCard | null;
  busy: boolean;
  unavailable: ToolOutcomeTreatment | null;
  transportError: string | null;
  onRerun: (changes: Record<string, ToolScalar>) => void;
  t: ToolTranslator;
  locale: string;
  labels: { stored: string; latest: string };
}) {
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);
  const changes = rerunChanges(stored, drafts);
  const upToDate = Object.keys(drafts).length > 0 && changesAreEmpty(changes);
  const fieldLabel = (name: string) => {
    const input = stored.presentation.inputs.find((candidate) => candidate.name === name);
    return input ? localizedToolText(input.label, t) : name;
  };
  const change = (name: string, value: string) => {
    const next = { ...drafts, [name]: value };
    setDrafts(next);
    if (timer.current) clearTimeout(timer.current);
    const pending = rerunChanges(stored, next);
    if (!pending || Object.keys(pending).length === 0) return;
    timer.current = setTimeout(() => onRerun(pending), 300);
  };
  const storedTreatment = toolOutcomeTreatment(stored.outcome, t, fieldLabel);
  const latestTreatment = latest ? toolOutcomeTreatment(latest.outcome, t, fieldLabel) : null;
  const applyRepair = (repair: Record<string, ToolScalar>) => onRerun({ ...(changes ?? {}), ...repair });
  return (
    <div data-testid="computed-rerun-panel" aria-busy={busy} className="grid gap-4 md:grid-cols-2">
      <section data-computed-rerun="stored" className="min-w-0 rounded-2xl border border-black/10 bg-black/[0.015] p-4 dark:border-white/10 dark:bg-white/[0.025]">
        <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-black/40 dark:text-white/40">{labels.stored}</p>
        {storedTreatment ? <div className="mb-3"><ToolOutcomeNotice treatment={storedTreatment} repairLabel={storedTreatment.repair ? localizedToolText(storedTreatment.repair.label, t) : null} retryLabel={t("tools.card.retry")} onRepair={applyRepair} onRetry={() => onRerun({})} disabled={busy} /></div> : null}
        <ToolCardPresentation presentation={stored.presentation} t={t} locale={locale} withheld={stored.outcome.status !== "succeeded"}
          inputs={<ToolInputEditor idPrefix={`rerun-${stored.artifact_id}`} inputs={stored.presentation.inputs} drafts={drafts} editable={!unavailable} busy={busy} onChange={change} t={t} locale={locale} />} />
      </section>
      <section data-computed-rerun="latest" className="min-w-0 rounded-2xl border border-black/10 p-4 dark:border-white/10">
        <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-black/40 dark:text-white/40">{labels.latest}</p>
        {unavailable ? <ToolOutcomeNotice treatment={unavailable} testId="computed-rerun-unavailable" /> : null}
        {upToDate ? <p data-testid="computed-rerun-up-to-date" role="status" className="text-sm text-black/60 dark:text-white/60">{alreadyUpToDateText(t)}</p> : null}
        {transportError ? <p role="alert" className="text-xs text-rose-700 dark:text-rose-300">{transportError}</p> : null}
        {latest ? <>
          {latestTreatment ? <div className="mb-3"><ToolOutcomeNotice treatment={latestTreatment} repairLabel={latestTreatment.repair ? localizedToolText(latestTreatment.repair.label, t) : null} retryLabel={t("tools.card.retry")} onRepair={applyRepair} onRetry={() => onRerun(changes ?? {})} disabled={busy} /></div> : null}
          <ToolCardPresentation presentation={latest.presentation} t={t} locale={locale} withheld={latest.outcome.status !== "succeeded"} />
        </> : null}
        {!latest && !unavailable && !upToDate && !transportError ? <p className="text-sm text-black/45 dark:text-white/45">{t("tools.card.saved_result")}</p> : null}
      </section>
    </div>
  );
}
