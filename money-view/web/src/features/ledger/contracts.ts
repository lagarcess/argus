import { z } from "zod";
import { evidenceSchema } from "../../platform/types";

export const accountSchema = z.object({
  id: z.string(),
  name: z.string(),
  institution: z.string(),
  kind: z.string(),
  currency: z.string(),
  balance: z.string(),
  opening_balance: z.string(),
  owner_id: z.string(),
  connection_id: z.string().nullable(),
  deleted_at: z.string().nullable(),
  source: evidenceSchema,
});
export type Account = z.infer<typeof accountSchema>;
export const accountsSchema = z.object({
  items: z.array(accountSchema),
  total: z.number(),
  limit: z.number(),
  offset: z.number(),
});
export const splitSchema = z.object({
  category: z.string(),
  amount: z.string(),
});
export const transactionSchema = z.object({
  id: z.string(),
  account_id: z.string(),
  account_name: z.string(),
  date: z.string(),
  merchant: z.string(),
  description: z.string(),
  amount: z.string(),
  currency: z.string(),
  category: z.string(),
  kind: z.string(),
  status: z.string(),
  notes: z.string(),
  splits: z.array(splitSchema),
  transfer_id: z.string().nullable(),
  reversal_of: z.string().nullable(),
  source: evidenceSchema,
});
export type Transaction = z.infer<typeof transactionSchema>;
export const cashflowSchema = z.object({
  currency: z.string(),
  income: z.string(),
  spending: z.string(),
  net: z.string(),
  transaction_count: z.number(),
  source: evidenceSchema,
});
export const transactionsSchema = z.object({
  items: z.array(transactionSchema),
  total: z.number(),
  limit: z.number(),
  offset: z.number(),
  aggregates: z.array(cashflowSchema),
});
export const categoriesSchema = z.object({
  items: z.array(z.object({ id: z.string(), kind: z.string() })),
});
export const spendingSchema = cashflowSchema.extend({
  month: z.string(),
  categories: z.array(
    z.object({
      category: z.string(),
      amount: z.string(),
      transaction_count: z.number(),
    }),
  ),
  merchants: z.array(
    z.object({
      merchant: z.string(),
      amount: z.string(),
      transaction_count: z.number(),
    }),
  ),
});
export const connectorSchema = z.object({
  id: z.string(),
  name: z.string(),
  countries: z.array(z.string()),
  currencies: z.array(z.string()),
  mode: z.literal("simulated"),
});
export const connectionSchema = z.object({
  id: z.string(),
  connector_id: z.string(),
  status: z.string(),
  last_good_at: z.string().nullable(),
  last_attempt_at: z.string().nullable(),
  error_code: z.string().nullable(),
  mode: z.literal("simulated"),
});
export const connectorsSchema = z.object({ items: z.array(connectorSchema) });
export const connectionsSchema = z.object({ items: z.array(connectionSchema) });
export const importInspectionSchema = z.object({
  stage: z.literal("mapping"),
  headers: z.array(z.string()),
  sample_rows: z.array(z.array(z.string())),
  row_count: z.number(),
  currency: z.string(),
  file_digest: z.string(),
  limits: z.object({
    max_bytes: z.number(),
    max_rows: z.number(),
    max_columns: z.number(),
    max_cell_chars: z.number(),
    max_header_row: z.number(),
  }),
});
export const previewSchema = z.object({
  id: z.string(),
  account_id: z.string(),
  rows: z.array(
    z.object({
      line: z.number(),
      date: z.string(),
      merchant: z.string(),
      description: z.string(),
      amount: z.string(),
      currency: z.string(),
      category: z.string(),
      kind: z.string(),
      duplicate: z.boolean(),
      duplicate_status: z.enum(["new", "exact", "possible"]).optional(),
      source_id: z.string().nullable().optional(),
    }),
  ),
  errors: z.array(z.object({ line: z.number(), code: z.string() })),
  valid_count: z.number(),
  duplicate_count: z.number(),
  can_commit: z.boolean(),
  source: evidenceSchema,
  stage: z.literal("review").optional(),
  review_count: z.number().optional(),
  preview_digest: z.string().optional(),
  expires_at: z.string().optional(),
  file_digest: z.string().optional(),
  parser_version: z.string().optional(),
});
export const importSchema = z.object({
  id: z.string(),
  imported: z.number(),
  duplicates: z.number(),
  transaction_ids: z.array(z.string()),
  source: evidenceSchema,
});
export const deletedSchema = z.object({ id: z.string(), deleted: z.boolean() });
