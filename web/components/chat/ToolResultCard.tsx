"use client";

import React, { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  localizedToolText, toolInputChanges, type ToolResultCard as Card,
  type ToolRecompute, type ToolScalar,
} from "@/lib/tool-result-card";
import { toolOutcomeTreatment } from "@/lib/tool-outcome-treatment";
import ToolCardPresentation from "./ToolCardPresentation";
import ToolInputEditor from "./ToolInputEditor";
import ToolOutcomeNotice from "./ToolOutcomeNotice";

export default function ToolResultCard({ card, onRecompute, disabled = false }: {
  card: Card; onRecompute?: ToolRecompute; disabled?: boolean;
}) {
  const { t, i18n } = useTranslation();
  const locale = i18n.resolvedLanguage ?? i18n.language ?? "en";
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const eligible = Boolean(onRecompute) && !disabled && card.artifact_state === "active";
  const [draft, setDraft] = useState<Record<string, string>>({});
  const changes = toolInputChanges(card, draft);
  const hasDraftChanges = eligible && (changes === null || Object.keys(changes).length > 0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const drafts = useRef<Record<string, string>>({});
  const active = useRef(true);
  useEffect(() => { active.current = true; return () => { active.current = false; if (timer.current) clearTimeout(timer.current); }; }, []);
  useEffect(() => { if (!eligible && timer.current) { clearTimeout(timer.current); timer.current = null; } }, [eligible]);
  const submit = async (next: Record<string, ToolScalar>) => {
    setPending(true);
    try { await onRecompute?.(card, next); }
    catch { if (active.current) setError(t("tools.card.recompute_failed")); }
    finally { if (active.current) setPending(false); }
  };
  const change = (name: string, value: string) => {
    if (!eligible) return;
    drafts.current = { ...drafts.current, [name]: value };
    setDraft(drafts.current);
    if (timer.current) clearTimeout(timer.current);
    const changes = toolInputChanges(card, drafts.current);
    if (!changes) { setError(t("tools.card.enter_value")); return; }
    setError(null);
    if (Object.keys(changes).length === 0) return;
    timer.current = setTimeout(() => { void submit(changes); }, 300);
  };
  const fieldLabel = (name: string) => {
    const input = card.presentation.inputs.find((candidate) => candidate.name === name);
    return input ? localizedToolText(input.label, t) : name;
  };
  const treatment = toolOutcomeTreatment(card.outcome, t, fieldLabel);
  const controls = <ToolInputEditor idPrefix={card.artifact_id} inputs={card.presentation.inputs} drafts={draft} editable={eligible} busy={disabled || pending} onChange={change} t={t} locale={locale} />;
  return <article data-tool-result-card={card.card_type} data-input-revision={card.input_revision} aria-busy={pending} className="w-full min-w-0 rounded-2xl border border-black/10 bg-black/[0.015] p-5 dark:border-white/10 dark:bg-white/[0.025]">
    {treatment ? <div className="mb-3"><ToolOutcomeNotice treatment={treatment} repairLabel={treatment.repair ? localizedToolText(treatment.repair.label, t) : null} retryLabel={t("tools.card.retry")}
      onRepair={eligible ? (repairChanges) => { void submit(repairChanges); } : undefined}
      onRetry={eligible ? () => { void submit({ ...card.arguments } as Record<string, ToolScalar>); } : undefined}
      disabled={disabled || pending} /></div> : null}
    {hasDraftChanges ? <p data-previous-tool-result className="mb-3 text-xs text-black/50 dark:text-white/50">{t("tools.card.saved_result")}</p> : null}
    <ToolCardPresentation presentation={card.presentation} t={t} locale={locale} inputs={controls} withheld={card.outcome.status !== "succeeded"} />
    {pending ? <p role="status" className="mt-3 text-xs text-black/50 dark:text-white/50">{t("tools.card.updating")}</p> : null}
    {eligible && error ? <p role="alert" className="mt-3 text-xs text-rose-700 dark:text-rose-300">{error}</p> : null}
  </article>;
}
