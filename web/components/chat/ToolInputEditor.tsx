import React from "react";
import {
  localizedToolText, toolFactSourceText, toolFactValue, toolInputAwaitsValue,
  type ToolInputFact, type ToolTranslator,
} from "@/lib/tool-result-card";

/**
 * The editable inputs under a computed answer, one owner for chat, the Search
 * dossier and the decision view. Each input shows where it came from. Values
 * are transport only; every calculation stays in Python.
 */
export default function ToolInputEditor({ idPrefix, inputs, drafts, editable, busy, onChange, t, locale }: {
  idPrefix: string; inputs: ToolInputFact[]; drafts: Record<string, string>; editable: boolean; busy: boolean;
  onChange: (name: string, value: string) => void; t: ToolTranslator; locale: string;
}) {
  return <>{inputs.map((input) => {
    const label = localizedToolText(input.label, t);
    const provenance = toolFactSourceText(input, t, locale);
    const canEdit = input.editable && !input.unknown && editable;
    const awaiting = toolInputAwaitsValue(input);
    const id = `${idPrefix}-${input.name}`;
    return <div key={input.name} data-tool-input={input.name} data-tool-input-source={input.source?.kind} className="flex min-h-11 items-center justify-between gap-4 py-1">
      <div className="min-w-0">
        <label htmlFor={id} className="block text-sm text-black/60 dark:text-white/60">{label}</label>
        {provenance ? <span data-tool-input-provenance className="block text-[11px] text-black/40 dark:text-white/40">{provenance}</span> : null}
      </div>
      {canEdit ? <div className="flex min-w-0 items-center gap-2">
        {typeof input.value === "boolean"
          ? <select id={id} disabled={busy} value={drafts[input.name] ?? String(input.value)} onChange={(event) => onChange(input.name, event.target.value)} className="min-h-11 rounded-lg border border-black/15 bg-transparent px-3 text-base dark:border-white/20"><option value="true">{t("tools.card.yes")}</option><option value="false">{t("tools.card.no")}</option></select>
          : <input id={id} type={typeof input.value === "number" || awaiting ? "number" : "text"} step="any" disabled={busy}
              placeholder={awaiting ? t("tools.card.source.not_found") : undefined}
              value={drafts[input.name] ?? String(input.value ?? "")} onChange={(event) => onChange(input.name, event.target.value)}
              className={`min-h-11 w-32 min-w-0 rounded-lg border bg-transparent px-3 text-right text-base tabular-nums outline-none focus-visible:ring-2 focus-visible:ring-teal-600 disabled:opacity-50 ${awaiting ? "border-amber-700/40 dark:border-amber-300/40" : "border-black/15 dark:border-white/20"}`} />}
        {input.unit ? <span className="text-xs text-black/50 dark:text-white/50">{localizedToolText(input.unit, t)}</span> : null}
      </div> : <span id={id} className="text-sm tabular-nums text-black/60 dark:text-white/60">{toolFactValue(input, t, locale)}</span>}
    </div>;
  })}</>;
}
