"use client";

import { createContext, useContext, useEffect, useReducer, useState, type Dispatch, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useResponsiveLayout } from "@/components/layout/useResponsiveLayout";
import { listReceiptCandidates, type ReceiptCandidate } from "@/lib/evidence-receipts";
import { normalizeEnabledLanguage } from "@/lib/language-features";
import { interpolate, receiptCopy } from "@/lib/receipt-copy";
import { initialReceiptSelection, receiptSelectionReducer, receiptRefusalText, selectAllEligibleAvailable, type ReceiptSelectionState, type ReceiptShareTarget } from "@/lib/receipt-selection";

export const RECEIPT_OUTLINE_BUTTON = "inline-flex min-h-11 items-center justify-center gap-1.5 rounded-full border border-black/10 px-3 py-1.5 text-[13px] font-medium transition-colors hover:bg-black/[0.03] disabled:cursor-not-allowed disabled:opacity-50 dark:border-white/10 dark:hover:bg-white/[0.05]";
export const RECEIPT_SOLID_BUTTON = "inline-flex min-h-11 items-center justify-center gap-1.5 rounded-full bg-[#191c1f] px-3.5 py-1.5 text-[13px] font-medium text-white disabled:cursor-not-allowed disabled:opacity-55 dark:bg-white dark:text-[#191c1f]";

type ReceiptConversationState = {
  state: ReceiptSelectionState; dispatch: Dispatch<Parameters<typeof receiptSelectionReducer>[1]>;
  active: boolean; panelOpen: boolean; setPanelOpen: (open: boolean) => void;
  onClose: () => void; retry: () => void;
};
const ReceiptConversationContext = createContext<ReceiptConversationState | null>(null);
export const useReceiptConversation = () => useContext(ReceiptConversationContext);

/** The transcript and publication panel read one selection, without copying messages. */
export function ReceiptConversationProvider({ target, conversationId, onClose, children }: {
  target: ReceiptShareTarget | null; conversationId: string | null; onClose: () => void; children: ReactNode;
}) {
  const [state, dispatch] = useReducer(receiptSelectionReducer, initialReceiptSelection);
  const [panelOpen, setPanelOpen] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const active = Boolean(target && target.conversationId === conversationId);
  const targetId = target?.conversationId;
  const messageId = target?.messageId;
  useEffect(() => {
    if (!targetId || !active) return;
    let cancelled = false;
    dispatch({ type: "reset" });
    setPanelOpen(false);
    listReceiptCandidates(targetId)
      .then((page) => { if (!cancelled) dispatch({ type: "loaded", page, messageId }); })
      .catch((error) => { if (!cancelled) dispatch({ type: "failed", error }); });
    return () => { cancelled = true; };
  }, [targetId, messageId, active, attempt]);
  return <ReceiptConversationContext.Provider value={{ state, dispatch, active, panelOpen, setPanelOpen, onClose, retry: () => setAttempt((value) => value + 1) }}>{children}</ReceiptConversationContext.Provider>;
}

/** The checkbox lives next to the actual final answer, never in a title list. */
export function ReceiptTurnChoice({ candidate, selected, onToggle }: { candidate: ReceiptCandidate; selected: boolean; onToggle: () => void }) {
  const { i18n } = useTranslation();
  const copy = receiptCopy(normalizeEnabledLanguage(i18n.resolvedLanguage ?? i18n.language));
  return <div className="mb-3 rounded-xl border border-black/10 px-3 py-2 dark:border-white/10">
    <label className="flex min-h-11 cursor-pointer items-center gap-3 text-[13px]">
      <input type="checkbox" checked={selected} disabled={!candidate.eligible} onChange={onToggle} className="h-5 w-5 shrink-0 accent-[#5ba897]" />
      <span>{copy.selection.choose_turn}</span>
    </label>
    {!candidate.eligible && <p className="pb-2 text-[12px] text-black/60 dark:text-white/60">{receiptRefusalText(candidate, copy)}</p>}
  </div>;
}

export function ReceiptConversationTurn({ messageId, children }: { messageId: string; children: ReactNode }) {
  const sharing = useReceiptConversation();
  const candidate = sharing?.active ? sharing.state.page?.items.find((item) => item.message_id === messageId) : undefined;
  if (!candidate || !sharing) return children;
  const selected = sharing.state.selected.includes(messageId);
  return <div className={selected ? "rounded-2xl bg-[#5ba897]/10 p-2 ring-1 ring-[#5ba897]/40" : undefined}>
    <ReceiptTurnChoice candidate={candidate} selected={selected} onToggle={() => sharing.dispatch({ type: "toggle", messageId })} />
    {children}
  </div>;
}

/** Selection temporarily takes the composer's place so the conversation stays readable. */
export function ReceiptSelectionComposer({ children }: { children: ReactNode }) {
  const sharing = useReceiptConversation();
  const { t, i18n } = useTranslation();
  const { isBelowTablet } = useResponsiveLayout();
  if (!sharing?.active) return children;
  const { state, dispatch } = sharing;
  const copy = receiptCopy(normalizeEnabledLanguage(i18n.resolvedLanguage ?? i18n.language));
  const eligible = state.page?.items.filter((item) => item.eligible).length ?? 0;
  return <section aria-label={copy.selection.title} className="rounded-2xl border border-black/10 bg-[#f9f9f9] p-3 shadow-lg dark:border-white/10 dark:bg-[#191c1f]">
    <p className="text-[13px] leading-relaxed">{copy.selection.hint}</p>
    {!state.page && <p role={state.error ? "alert" : "status"} className="mt-2 text-[13px]">{state.error ? <button type="button" className={RECEIPT_OUTLINE_BUTTON} onClick={sharing.retry}>{t("common.retry")}</button> : copy.selection.loading}</p>}
    {state.page && <p aria-live="polite" className="mt-2 text-[12px] text-black/60 dark:text-white/60">{eligible ? interpolate(copy.selection.count, { selected: state.selected.length, eligible }) : copy.selection.empty}</p>}
    <div className={`mt-2 flex gap-2 ${isBelowTablet ? "flex-wrap" : "items-center"}`}>
      <button type="button" className={RECEIPT_OUTLINE_BUTTON} disabled={!selectAllEligibleAvailable(state.page)} onClick={() => dispatch({ type: "select_all" })}>{copy.selection.all}</button>
      {state.selected.length > 0 && <button type="button" className={RECEIPT_OUTLINE_BUTTON} onClick={() => dispatch({ type: "clear" })}>{copy.selection.clear}</button>}
      <button type="button" className={`${RECEIPT_OUTLINE_BUTTON} ml-auto`} onClick={sharing.onClose}>{copy.selection.cancel}</button>
      <button type="button" className={RECEIPT_SOLID_BUTTON} disabled={!state.selected.length} onClick={() => sharing.setPanelOpen(true)}>{copy.selection.continue}</button>
    </div>
  </section>;
}
