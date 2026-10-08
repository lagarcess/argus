import * as api from "@/lib/business-api";
import type { ArgusLanguage } from "@/lib/language-features";
import type {
  BusinessAccount,
  BusinessExpense,
  BusinessOverview,
  BusinessSpace,
  BusinessUpdate,
  BusinessWorkspaceInfo,
  ExpenseInput,
  ReceiptDetail,
  ReceiptReviewFields,
  ReceiptSummary,
} from "@/lib/business-api";

/**
 * Everything the Business screens read or write. The live source is the API;
 * the fixture source exists only for the local design preview and says so.
 */
export type BusinessDataSource = Readonly<{
  mode: "live" | "fixture";
  ensureSpace: (language: ArgusLanguage) => Promise<BusinessSpace>;
  workspace: () => Promise<BusinessWorkspaceInfo>;
  overview: (from: string, to: string) => Promise<BusinessOverview>;
  receipts: (view: "inbox" | "all") => Promise<ReceiptSummary[]>;
  receipt: (id: string) => Promise<ReceiptDetail>;
  receiptSource: (id: string) => Promise<Blob>;
  updates: () => Promise<BusinessUpdate[]>;
  expenses: (from: string, to: string) => Promise<BusinessExpense[]>;
  uploadReceipt: (file: File, consentToPrepare: boolean, key: string) => Promise<ReceiptSummary>;
  prepareReceipt: (id: string) => Promise<ReceiptSummary>;
  saveReview: (
    id: string,
    version: number,
    fields: Partial<ReceiptReviewFields>,
  ) => Promise<ReceiptDetail>;
  confirmReceipt: (id: string, version: number, key: string) => Promise<ReceiptDetail>;
  recordExpense: (input: ExpenseInput, key: string) => Promise<BusinessExpense>;
  createAccount: (
    input: { nickname: string; type: string; currency: string },
    key: string,
  ) => Promise<BusinessAccount>;
}>;

export const liveBusinessDataSource: BusinessDataSource = {
  mode: "live",
  ensureSpace: api.startBusinessSpace,
  workspace: api.getBusinessWorkspace,
  overview: api.getBusinessOverview,
  receipts: api.listBusinessReceipts,
  receipt: api.getBusinessReceipt,
  receiptSource: api.fetchBusinessReceiptSource,
  updates: api.listBusinessUpdates,
  expenses: api.listBusinessExpenses,
  uploadReceipt: api.uploadBusinessReceipt,
  prepareReceipt: api.prepareBusinessReceipt,
  saveReview: api.saveBusinessReceiptReview,
  confirmReceipt: api.confirmBusinessReceipt,
  recordExpense: api.recordBusinessExpense,
  createAccount: api.createBusinessAccount,
};

/**
 * Every Business call needs the person's space, so the first call starts it
 * once and every call waits for it; a failed start is retried by the next call.
 */
export function withBusinessSpace(
  source: BusinessDataSource,
  language: () => ArgusLanguage,
): BusinessDataSource {
  let started: Promise<BusinessSpace> | null = null;
  const ready = () => {
    started ??= source.ensureSpace(language()).catch((error: unknown) => {
      started = null;
      throw error;
    });
    return started;
  };
  const after =
    <A extends unknown[], R>(call: (...args: A) => Promise<R>) =>
    async (...args: A): Promise<R> => {
      await ready();
      return call(...args);
    };
  return {
    mode: source.mode,
    ensureSpace: ready,
    workspace: after(source.workspace),
    overview: after(source.overview),
    receipts: after(source.receipts),
    receipt: after(source.receipt),
    receiptSource: after(source.receiptSource),
    updates: after(source.updates),
    expenses: after(source.expenses),
    uploadReceipt: after(source.uploadReceipt),
    prepareReceipt: after(source.prepareReceipt),
    saveReview: after(source.saveReview),
    confirmReceipt: after(source.confirmReceipt),
    recordExpense: after(source.recordExpense),
    createAccount: after(source.createAccount),
  };
}
