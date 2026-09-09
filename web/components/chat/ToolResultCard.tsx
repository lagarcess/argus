"use client";

import React, { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  localizedToolText, toolFactValue, toolInputChanges, type ToolResultCard as Card,
  type ToolRecompute,
} from "@/lib/tool-result-card";
import ToolCardPresentation from "./ToolCardPresentation";
import ShareReceiptAction from "./ShareReceiptAction";
import type { ToolReceiptSource } from "@/lib/evidence-receipts";
import { evidenceReceiptSharingEnabled } from "@/lib/private-alpha-flags";

export default function ToolResultCard({ card, onRecompute, disabled = false, shareSource }: {
  card: Card; onRecompute?: ToolRecompute; disabled?: boolean; shareSource?: ToolReceiptSource;
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
  const change = (name: string, value: string) => {
    if (!eligible) return;
    drafts.current = { ...drafts.current, [name]: value };
    setDraft(drafts.current);
    if (timer.current) clearTimeout(timer.current);
    const changes = toolInputChanges(card, drafts.current);
    if (!changes) { setError(t("tools.card.enter_value")); return; }
    setError(null);
    if (Object.keys(changes).length === 0) return;
    timer.current = setTimeout(async () => {
      setPending(true);
      try { await onRecompute?.(card, changes); }
      catch { if (active.current) setError(t("tools.card.recompute_failed")); }
      finally { if (active.current) setPending(false); }
    }, 300);
  };
  const controls = card.presentation.inputs.map((input) => {
    const label = localizedToolText(input.label, t);
    const editable = input.editable && !input.unknown && eligible;
    return <div key={input.name} className="flex min-h-11 items-center justify-between gap-4 py-1">
      <label htmlFor={`${card.artifact_id}-${input.name}`} className="text-sm text-black/60 dark:text-white/60">{label}</label>
      {editable ? <div className="flex min-w-0 items-center gap-2">
        {typeof input.value === "boolean" ? <select id={`${card.artifact_id}-${input.name}`} disabled={disabled || pending} value={draft[input.name] ?? String(input.value)} onChange={(event) => change(input.name, event.target.value)} className="min-h-11 rounded-lg border border-black/15 bg-transparent px-3 text-base dark:border-white/20"><option value="true">{t("tools.card.yes")}</option><option value="false">{t("tools.card.no")}</option></select> :
        <input id={`${card.artifact_id}-${input.name}`} type={typeof input.value === "number" ? "number" : "text"} step="any" disabled={disabled || pending} value={draft[input.name] ?? String(input.value ?? "")} onChange={(event) => change(input.name, event.target.value)} className="min-h-11 w-32 min-w-0 rounded-lg border border-black/15 bg-transparent px-3 text-right text-base tabular-nums outline-none focus-visible:ring-2 focus-visible:ring-teal-600 disabled:opacity-50 dark:border-white/20" />}
        {input.unit ? <span className="text-xs text-black/50 dark:text-white/50">{localizedToolText(input.unit, t)}</span> : null}
      </div> : <span id={`${card.artifact_id}-${input.name}`} className="text-sm tabular-nums text-black/60 dark:text-white/60">{toolFactValue(input, t, locale)}</span>}
    </div>;
  });
  return <article data-tool-result-card={card.card_type} data-input-revision={card.input_revision} aria-busy={pending} className="w-full min-w-0 rounded-2xl border border-black/10 bg-black/[0.015] p-5 dark:border-white/10 dark:bg-white/[0.025]">
    {card.outcome.status !== "succeeded" ? <p role="status" className="mb-3 text-sm text-amber-800 dark:text-amber-200">{t(`tools.card.status.${card.outcome.status}`)}</p> : null}
    {hasDraftChanges ? <p data-previous-tool-result className="mb-3 text-xs text-black/50 dark:text-white/50">{t("tools.card.saved_result")}</p> : null}
    <ToolCardPresentation presentation={card.presentation} t={t} locale={locale} inputs={controls} withheld={card.outcome.status !== "succeeded"} />
    {evidenceReceiptSharingEnabled && shareSource && card.outcome.status === "succeeded" && !pending && !hasDraftChanges ? <ShareReceiptAction toolSource={shareSource} /> : null}
    {pending ? <p role="status" className="mt-3 text-xs text-black/50 dark:text-white/50">{t("tools.card.updating")}</p> : null}
    {eligible && error ? <p role="alert" className="mt-3 text-xs text-rose-700 dark:text-rose-300">{error}</p> : null}
  </article>;
}
