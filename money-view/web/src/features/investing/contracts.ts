import { z } from 'zod';
import { evidenceSchema } from '../../platform/types';

export const priceSchema = z.object({
  symbol: z.string(),
  currency: z.string(),
  price: z.string(),
  as_of: z.string(),
  source: evidenceSchema,
});

export const linkedAccountSchema = z.object({
  id: z.string(),
  name: z.string(),
  currency: z.string(),
  balance: z.string(),
  source: evidenceSchema,
});

export const holdingSchema = z.object({
  id: z.string(),
  symbol: z.string(),
  name: z.string(),
  quantity: z.string(),
  currency: z.string(),
  total_cost: z.string(),
  as_of: z.string(),
  price: priceSchema.nullable(),
  market_value: z.string().nullable(),
  gain_loss: z.string().nullable(),
  gain_loss_pct: z.string().nullable(),
  allocation_pct: z.string().nullable(),
  source: evidenceSchema,
});
export type Holding = z.infer<typeof holdingSchema>;

export const totalSchema = z.object({
  currency: z.string(),
  linked_accounts: z.string(),
  priced_alternatives: z.string(),
  portfolio_value: z.string(),
  alternative_cost_basis: z.string(),
  alternative_gain_loss: z.string(),
  alternative_gain_loss_pct: z.string().nullable(),
  is_partial: z.boolean(),
  unpriced_holding_ids: z.array(z.string()),
  source: evidenceSchema,
});

export const benchmarkSchema = z.object({
  id: z.string(),
  symbol: z.string(),
  name: z.string(),
  currency: z.string(),
  start_on: z.string(),
  end_on: z.string(),
  start_price: z.string(),
  end_price: z.string(),
  return_pct: z.string(),
  source: evidenceSchema,
});
export type Benchmark = z.infer<typeof benchmarkSchema>;

export const bookSchema = z.object({
  id: z.string(),
  name: z.string(),
  currency: z.string(),
  cash: z.string(),
  initial_cash: z.string(),
  source: evidenceSchema,
});
export type Book = z.infer<typeof bookSchema>;

export const orderLegSchema = z.object({
  symbol: z.string(),
  quantity: z.string(),
  price: z.string(),
  gross: z.string(),
  price_as_of: z.string(),
  price_source: evidenceSchema,
});

export const orderPreviewSchema = z.object({
  id: z.string(),
  book_id: z.string(),
  side: z.enum(['buy', 'sell']),
  kind: z.enum(['symbol', 'bundle']),
  symbol: z.string().nullable(),
  bundle_id: z.string().nullable(),
  currency: z.string(),
  legs: z.array(orderLegSchema),
  gross: z.string(),
  rounding_rule: z.literal('buy_ceiling_sell_floor'),
  rounding_cost: z.string(),
  fee: z.string(),
  cash_effect: z.string(),
  quoted_at: z.string(),
  expires_at: z.string(),
  source: evidenceSchema,
});
export type OrderPreview = z.infer<typeof orderPreviewSchema>;

export const orderReceiptSchema = z.object({
  id: z.string(),
  preview_id: z.string(),
  book_id: z.string(),
  side: z.enum(['buy', 'sell']),
  kind: z.enum(['symbol', 'bundle']),
  symbol: z.string().nullable(),
  bundle_id: z.string().nullable(),
  currency: z.string(),
  legs: z.array(orderLegSchema),
  gross: z.string(),
  rounding_rule: z.literal('buy_ceiling_sell_floor'),
  rounding_cost: z.string(),
  fee: z.string(),
  cash_effect: z.string(),
  cash_before: z.string(),
  cash_after: z.string(),
  confirmed_at: z.string(),
  source: evidenceSchema,
});
export type OrderReceipt = z.infer<typeof orderReceiptSchema>;

export const positionSchema = z.object({
  book_id: z.string(),
  symbol: z.string(),
  currency: z.string(),
  quantity: z.string(),
  total_cost: z.string(),
  average_cost: z.string(),
  price: priceSchema.nullable(),
  market_value: z.string().nullable(),
  gain_loss: z.string().nullable(),
  gain_loss_pct: z.string().nullable(),
  source: evidenceSchema,
});

export const portfolioSchema = z.object({
  as_of: z.string(),
  linked_accounts: z.array(linkedAccountSchema),
  alternative_holdings: z.array(holdingSchema),
  totals: z.array(totalSchema),
  net_worth_additions: z.array(z.object({ currency: z.string(), amount: z.string(), source: evidenceSchema })),
  benchmarks: z.array(benchmarkSchema),
  simulation: z.object({
    books: z.array(bookSchema),
    positions: z.array(positionSchema),
    recent_orders: z.array(orderReceiptSchema),
  }),
  source: evidenceSchema,
});
export type Portfolio = z.infer<typeof portfolioSchema>;

export const bundleSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string(),
  currency: z.string(),
  legs: z.array(z.object({ symbol: z.string(), weight_pct: z.string() })),
  source: evidenceSchema,
});
export type Bundle = z.infer<typeof bundleSchema>;

export const planSchema = z.object({
  id: z.string(),
  book_id: z.string(),
  cadence: z.enum(['weekly', 'monthly']),
  next_run_on: z.string(),
  symbol: z.string().nullable(),
  bundle_id: z.string().nullable(),
  amount: z.string(),
  currency: z.string(),
  active: z.boolean(),
  source: evidenceSchema,
});
export type RecurringPlan = z.infer<typeof planSchema>;

export const bundleListSchema = z.object({ items: z.array(bundleSchema) });
export const planListSchema = z.object({ items: z.array(planSchema) });
export const holdingListSchema = z.object({ items: z.array(holdingSchema) });
export const bookListSchema = z.object({ items: z.array(bookSchema) });
export const orderListSchema = z.object({ items: z.array(orderReceiptSchema) });
export const deletedSchema = z.object({ id: z.string(), deleted: z.boolean() });

export const importPreviewSchema = z.object({
  id: z.string(),
  rows: z.array(z.object({
    line: z.number(),
    symbol: z.string(),
    name: z.string(),
    quantity: z.string(),
    total_cost: z.string(),
    currency: z.string(),
    as_of: z.string(),
    duplicate: z.boolean(),
  })),
  errors: z.array(z.object({ line: z.number(), code: z.string() })),
  valid_count: z.number(),
  duplicate_count: z.number(),
  can_commit: z.boolean(),
  source: evidenceSchema,
});
export type ImportPreview = z.infer<typeof importPreviewSchema>;

export const importReceiptSchema = z.object({
  id: z.string(),
  imported: z.number(),
  duplicates: z.number(),
  holding_ids: z.array(z.string()),
  source: evidenceSchema,
});

export const priceLoadSchema = z.object({
  id: z.string(),
  status: z.string(),
  as_of: z.string().nullable(),
  completed_at: z.string(),
  error_code: z.string().nullable(),
  source: evidenceSchema.nullable(),
});

export const planRunSchema = z.object({
  id: z.string(),
  plan_id: z.string(),
  period_key: z.string(),
  run_on: z.string(),
  status: z.string(),
  order_receipt: orderReceiptSchema.nullable(),
  error_code: z.string().nullable(),
  source: evidenceSchema,
});

export const investingWorkspaceSchema = z.object({
  portfolio: portfolioSchema,
  bundles: z.array(bundleSchema),
  plans: z.array(planSchema),
});
export type InvestingWorkspace = z.infer<typeof investingWorkspaceSchema>;
