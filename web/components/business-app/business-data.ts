import * as api from "@/lib/business-api";
import type {
  BusinessAccount,
  BusinessExpense,
  BusinessOverview,
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
  workspace: () => Promise<BusinessWorkspaceInfo>;
  overview: (from: string, to: string) => Promise<BusinessOverview>;
  receipts: (view: "inbox" | "all") => Promise<ReceiptSummary[]>;
  receipt: (id: string) => Promise<ReceiptDetail>;
  receiptSource: (id: string) => Promise<Blob>;
  updates: () => Promise<BusinessUpdate[]>;
  expenses: (from: string, to: string) => Promise<BusinessExpense[]>;
  uploadReceipt: (file: File, consentToPrepare: boolean) => Promise<ReceiptSummary>;
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
