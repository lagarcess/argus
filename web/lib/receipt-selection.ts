import type { EvidenceReceipt, ReceiptCandidates, ReceiptPreview, ReceiptSelection } from "./evidence-receipts";
import { createSelectedEvidenceReceipt } from "./evidence-receipts";
import { interpolate, type ReceiptCopy } from "./receipt-copy";
import type { ReceiptRefusalField, ReceiptRefusalReason } from "./public-receipt-turns";

export type ReceiptShareTarget = { conversationId: string; messageId?: string };
export type ReceiptSelectionState = {
  page: ReceiptCandidates | null; selected: string[]; note: string; revision: number;
  phase: "loading" | "selecting" | "previewing" | "preview" | "creating" | "created";
  preview: ReceiptPreview | null; receipt: EvidenceReceipt | null; error: unknown;
};
export const initialReceiptSelection: ReceiptSelectionState = { page: null, selected: [], note: "", revision: 0, phase: "loading", preview: null, receipt: null, error: null };
type Action =
  | { type: "loaded"; page: ReceiptCandidates; messageId?: string }
  | { type: "toggle"; messageId: string }
  | { type: "select_all" | "clear" | "edit" }
  | { type: "note"; note: string }
  | { type: "busy"; phase: "previewing" | "creating" }
  | { type: "previewed"; preview: ReceiptPreview; revision: number }
  | { type: "created"; receipt: EvidenceReceipt }
  | { type: "failed"; error: unknown };

export function selectAllEligibleAvailable(page: ReceiptCandidates | null): boolean {
  return Boolean(page?.items.some((item) => item.eligible));
}
export function receiptSelectionRequest(state: ReceiptSelectionState): ReceiptSelection {
  return { message_ids: state.selected, owner_note: state.note.trim() || null };
}

/** The server revalidates even an existing link against the preview digest. */
export async function publishReceiptSelection(conversationId: string, state: ReceiptSelectionState, dispatch: (action: Action) => void): Promise<void> {
  if (!state.preview) return;
  dispatch({ type: "busy", phase: "creating" });
  try { dispatch({ type: "created", receipt: await createSelectedEvidenceReceipt(conversationId, receiptSelectionRequest(state), state.preview.payload_digest) }); }
  catch (error) { dispatch({ type: "failed", error }); }
}

/** The server owns eligibility and ordering. This only records choices. */
export function receiptSelectionReducer(state: ReceiptSelectionState, action: Action): ReceiptSelectionState {
  const invalidate = (change: Partial<ReceiptSelectionState>) => ({ ...state, ...change, preview: null, receipt: null, error: null, revision: state.revision + 1, phase: "selecting" as const });
  switch (action.type) {
    case "loaded": return { ...initialReceiptSelection, page: action.page, phase: "selecting", selected: action.page.items.some((item) => item.message_id === action.messageId && item.eligible) ? [action.messageId!] : [] };
    case "toggle": {
      if (!state.page?.items.some((item) => item.message_id === action.messageId && item.eligible)) return state;
      const chosen = state.selected.includes(action.messageId);
      return invalidate({ selected: chosen ? state.selected.filter((id) => id !== action.messageId) : [...state.selected, action.messageId] });
    }
    case "select_all": return selectAllEligibleAvailable(state.page) ? invalidate({ selected: state.page!.items.filter((item) => item.eligible).map((item) => item.message_id) }) : state;
    case "clear": return invalidate({ selected: [] });
    case "note": return invalidate({ note: action.note });
    case "edit": return invalidate({});
    case "busy": return { ...state, phase: action.phase, error: null };
    case "previewed": return action.revision === state.revision ? { ...state, preview: action.preview, phase: "preview", error: null } : state;
    case "created": return { ...state, receipt: action.receipt, phase: "created", error: null };
    case "failed": return { ...state, preview: null, phase: "selecting", error: action.error };
  }
}

export function receiptRefusalText(context: { reason?: unknown; field?: unknown }, copy: ReceiptCopy): string {
  // These assignments make both closed backend enums exhaustive at compile time.
  const reasons: Record<ReceiptRefusalReason, string> = copy.selection.reasons;
  const fields: Record<ReceiptRefusalField, string> = copy.selection.fields;
  const reason = typeof context.reason === "string" && Object.hasOwn(reasons, context.reason) ? reasons[context.reason as ReceiptRefusalReason] : copy.owner.errors.create;
  const field = typeof context.field === "string" && Object.hasOwn(fields, context.field) ? fields[context.field as ReceiptRefusalField] : null;
  return field ? interpolate(copy.selection.field_refusal, { field, reason }) : reason;
}
