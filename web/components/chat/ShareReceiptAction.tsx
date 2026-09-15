"use client";

import { useId, useState } from "react";
import { Check, Copy, Link2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import AdaptivePanel from "@/components/ui/AdaptivePanel";
import { Tooltip } from "@/components/ui/Tooltip";
import ReceiptBody from "@/components/receipt/ReceiptBody";
import { normalizeEnabledLanguage } from "@/lib/language-features";
import { receiptCopy } from "@/lib/receipt-copy";
import {
  RECEIPT_OWNER_NOTE_MAX_LENGTH, copyReceiptLink,
  previewEvidenceReceipt, receiptFailureReason, receiptUrl,
} from "@/lib/evidence-receipts";
import {
  receiptSelectionRequest, publishReceiptSelection,
  receiptRefusalText, type ReceiptShareTarget,
} from "@/lib/receipt-selection";

import { useReceiptConversation, RECEIPT_OUTLINE_BUTTON as OUTLINE_BUTTON, RECEIPT_SOLID_BUTTON as SOLID_BUTTON } from "./ReceiptConversationSelection";

export type ReceiptShareRequest = (conversationId: string) => void;

/** The header opens the one conversation selection and publication flow. */
export default function ShareReceiptAction({ conversationId, onShare }: { conversationId: string; onShare: ReceiptShareRequest }) {
  const { t } = useTranslation();
  const label = t("receipt.selection.title");
  return <Tooltip content={label}>
    <button type="button" onClick={() => onShare(conversationId)} aria-label={label} className="flex h-11 w-11 items-center justify-center rounded-full transition-colors hover:bg-black/5 dark:hover:bg-white/5">
      <Link2 className="h-5 w-5" aria-hidden="true" />
    </button>
  </Tooltip>;
}

/** One publication flow. Opening and previewing are reads; Make the link writes. */
export function ShareReceiptPanel({ conversationId, onClose }: ReceiptShareTarget & { onClose: () => void }) {
  const { i18n } = useTranslation();
  const language = normalizeEnabledLanguage(i18n.resolvedLanguage ?? i18n.language);
  const copy = receiptCopy(language);
  const id = useId();
  const sharing = useReceiptConversation();
  const [copied, setCopied] = useState(false);
  const [copyFailed, setCopyFailed] = useState(false);
  if (!sharing?.active || !sharing.panelOpen) return null;
  const { state, dispatch } = sharing;

  const preview = async () => {
    const revision = state.revision;
    dispatch({ type: "busy", phase: "previewing" });
    try { dispatch({ type: "previewed", revision, preview: await previewEvidenceReceipt(conversationId, receiptSelectionRequest(state)) }); }
    catch (error) { dispatch({ type: "failed", error }); }
  };
  const failure = receiptFailureReason(state.error);
  const errorText = !state.error ? null : failure === "source_unsupported"
    ? receiptRefusalText((state.error as { context?: Record<string, unknown> }).context ?? {}, copy)
    : failure === "unavailable" ? copy.owner.errors.create
    : copy.owner.errors[failure];
  const busy = state.phase === "previewing" || state.phase === "creating";
  const url = state.receipt ? receiptUrl(state.receipt) : null;
  const footer = state.phase === "created" ? null : <div className="flex flex-wrap justify-end gap-2">
    {state.preview ? <>
      <button type="button" disabled={busy} className={OUTLINE_BUTTON} onClick={() => { dispatch({ type: "edit" }); sharing.setPanelOpen(false); }}>{copy.selection.edit}</button>
      <button type="button" disabled={busy} className={SOLID_BUTTON} onClick={() => void publishReceiptSelection(conversationId, state, dispatch)}>{state.phase === "creating" ? copy.owner.creating : state.preview.existing_receipt ? copy.selection.reuse : copy.owner.create}</button>
    </> : <button type="button" className={SOLID_BUTTON} disabled={busy || state.selected.length === 0} onClick={() => void preview()}>{busy ? copy.selection.previewing : copy.selection.preview}</button>}
  </div>;

  return <AdaptivePanel title={copy.selection.title} closeLabel={copy.selection.close} onClose={state.phase === "created" ? onClose : () => sharing.setPanelOpen(false)} width="lg" footer={footer}>
    <div className="px-5 py-4">
      {errorText && <p role="alert" className="mb-3 text-[13px] leading-relaxed text-[#b94c55] dark:text-[#e7a2a8]">{errorText}</p>}
      {url ? <>
        <div className="flex flex-wrap items-center gap-2">
          <input readOnly aria-label={copy.owner.copy} value={url} onFocus={(event) => event.target.select()} className="min-h-11 min-w-0 flex-1 rounded-lg border border-black/10 bg-transparent px-3 text-[16px] dark:border-white/10" />
          <button type="button" className={SOLID_BUTTON} onClick={async () => { const ok = await copyReceiptLink(url); setCopied(ok); setCopyFailed(!ok); }}>{copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}{copied ? copy.owner.copied : copy.owner.copy}</button>
        </div>
        {copyFailed && <p role="alert" className="mt-2 text-[13px]">{copy.owner.copy_failed}</p>}
        <p className="mt-3 text-[13px] leading-relaxed text-black/55 dark:text-white/55">{copy.owner.created_note}</p>
      </> : state.preview ? <>
        {state.preview.existing_receipt && <p className="mb-3 text-[13px] leading-relaxed text-black/55 dark:text-white/55">{copy.selection.existing}</p>}
        <div lang={language} className="-mx-5 bg-[#191c1f]"><ReceiptBody payload={state.preview.payload} createdAt={state.preview.existing_receipt?.created_at ?? null} language={language} copy={copy} preview /></div>
      </> : <>
        <fieldset disabled={busy}>
          <legend className="sr-only">{copy.selection.title}</legend>
          <label htmlFor={`${id}-note`} className="mt-4 block text-[13px] font-medium">{copy.owner.note_label}</label>
          <textarea id={`${id}-note`} value={state.note} rows={3} maxLength={RECEIPT_OWNER_NOTE_MAX_LENGTH} onChange={(event) => dispatch({ type: "note", note: event.target.value })} placeholder={copy.owner.note_placeholder} className="mt-2 w-full resize-y rounded-lg border border-black/10 bg-transparent px-3 py-2 text-[16px] focus-visible:ring-2 focus-visible:ring-[#5ba897] dark:border-white/10" />
          <p className="mt-2 text-[12.5px] leading-relaxed text-[#8a7530] dark:text-[#d3bb6a]">{copy.owner.note_public_warning}</p>
        </fieldset>
      </>}
    </div>
  </AdaptivePanel>;
}
