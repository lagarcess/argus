import { z } from 'zod';
import { evidenceSchema } from '../../platform/types';

export const decimalSchema = z
  .string()
  .regex(/^-?\d+(\.\d+)?$/)
  .refine((value) => Number.isFinite(Number(value)));

export const budgetSchema = z.object({
  id: z.string(),
  category: z.string(),
  currency: z.string(),
  month: z.string(),
  limit: decimalSchema,
  actual: decimalSchema,
  remaining: decimalSchema,
  evidence: evidenceSchema,
  input_evidence: evidenceSchema,
  actual_evidence: evidenceSchema,
});
export const budgetsResponseSchema = z.object({ items: z.array(budgetSchema) });

export const billSchema = z.object({
  id: z.string(),
  name: z.string(),
  account_id: z.string(),
  category: z.string(),
  currency: z.string(),
  amount: decimalSchema,
  cadence: z.enum(['weekly', 'monthly', 'quarterly', 'yearly']),
  anchor_date: z.string(),
  next_due: z.string(),
  status: z.string(),
  evidence: evidenceSchema,
});
export const billsResponseSchema = z.object({ items: z.array(billSchema) });

export const allocationSchema = z.object({
  account_id: z.string(),
  amount: decimalSchema,
  account_balance: decimalSchema.nullable(),
  account_evidence: evidenceSchema.nullable(),
  account_unavailable: z.boolean(),
  underfunded: z.boolean(),
});
export const goalSchema = z.object({
  id: z.string(),
  name: z.string(),
  target_date: z.string(),
  target_amount: decimalSchema,
  monthly_contribution: decimalSchema,
  currency: z.string(),
  status: z.string(),
  allocations: z.array(allocationSchema),
  allocated: decimalSchema,
  remaining: decimalSchema,
  evidence: evidenceSchema,
});
export const goalsResponseSchema = z.object({ items: z.array(goalSchema) });

export const accountSchema = z.object({
  id: z.string(),
  name: z.string(),
  currency: z.string(),
  balance: decimalSchema,
  source: evidenceSchema,
});
export const accountsResponseSchema = z.object({
  items: z.array(accountSchema),
  total: z.number().int(),
  limit: z.number().int(),
  offset: z.number().int(),
});
export const categoriesResponseSchema = z.object({
  items: z.array(z.object({ id: z.string(), kind: z.string() })),
});

export const scenarioInputsSchema = z.object({
  currency: z.string(),
  initial_balance: decimalSchema,
  monthly_contribution: decimalSchema,
  monthly_withdrawal: decimalSchema,
  horizon_years: z.number().int().min(1).max(100),
  annual_return_pct: decimalSchema,
  inflation_pct: decimalSchema,
  annual_fee_pct: decimalSchema,
  contribution_start_month: z.number().int().min(1).max(1200),
  contribution_end_month: z.number().int().min(1).max(1200).nullable(),
  withdrawal_start_month: z.number().int().min(1).max(1200),
  withdrawal_end_month: z.number().int().min(1).max(1200).nullable(),
  timing: z.enum(['begin', 'end']),
});

export const scenarioTemplateIdSchema = z.enum([
  'home',
  'kids',
  'job',
  'move',
  'marriage',
  'retirement',
  'sabbatical',
]);
export const scenarioTemplateSchema = z.object({
  id: scenarioTemplateIdSchema,
  inputs: scenarioInputsSchema,
});
export const scenarioTemplatesResponseSchema = z.object({
  items: z.array(scenarioTemplateSchema),
});

export const scenarioMonthSchema = z.object({
  month: z.number().int(),
  balance: decimalSchema,
  real_balance: decimalSchema,
  contribution: decimalSchema,
  withdrawal: decimalSchema,
  unfunded_withdrawal: decimalSchema,
  fee: decimalSchema,
});
export const scenarioYearSchema = z.object({
  year: z.number().int(),
  balance: decimalSchema,
  real_balance: decimalSchema,
});
export const scenarioResultSchema = z.object({
  currency: z.string(),
  ending_balance: decimalSchema,
  real_ending_balance: decimalSchema,
  total_contributions: decimalSchema,
  total_withdrawals: decimalSchema,
  total_fees: decimalSchema,
  depletion_month: z.number().int().nullable(),
  months: z.array(scenarioMonthSchema),
  years: z.array(scenarioYearSchema),
  method: z.string(),
});
export const scenarioCalculationSchema = scenarioResultSchema.extend({
  evidence: evidenceSchema,
});
export const scenarioReceiptSchema = z.object({
  id: z.string(),
  name: z.string(),
  template: scenarioTemplateIdSchema,
  inputs: scenarioInputsSchema,
  result: scenarioResultSchema,
  evidence: evidenceSchema,
});
export const scenarioResultSummarySchema = scenarioResultSchema.omit({ months: true, years: true });
export const scenarioSummarySchema = scenarioReceiptSchema.extend({
  result: scenarioResultSummarySchema,
});
export const scenariosResponseSchema = z.object({
  items: z.array(scenarioSummarySchema),
  total: z.number().int(),
  limit: z.number().int(),
  offset: z.number().int(),
});
export const scenarioComparisonSchema = z.object({
  before: scenarioReceiptSchema,
  after: scenarioReceiptSchema,
  delta_ending_balance: decimalSchema,
});

export type Budget = z.infer<typeof budgetSchema>;
export type Bill = z.infer<typeof billSchema>;
export type Goal = z.infer<typeof goalSchema>;
export type Account = z.infer<typeof accountSchema>;
export type ScenarioInputs = z.infer<typeof scenarioInputsSchema>;
export type ScenarioTemplate = z.infer<typeof scenarioTemplateSchema>;
export type ScenarioTemplateId = z.infer<typeof scenarioTemplateIdSchema>;
export type ScenarioResult = z.infer<typeof scenarioResultSchema>;
export type ScenarioCalculation = z.infer<typeof scenarioCalculationSchema>;
export type ScenarioReceipt = z.infer<typeof scenarioReceiptSchema>;
export type ScenarioSummary = z.infer<typeof scenarioSummarySchema>;
export type ScenarioComparison = z.infer<typeof scenarioComparisonSchema>;

export const planningPaths = {
  budgets: '/budgets',
  bills: '/bills',
  goals: '/goals',
  accounts: '/accounts',
  categories: '/categories',
  scenarioTemplates: '/scenarios/templates',
  scenarios: '/scenarios',
  scenarioCalculate: '/scenarios/calculate',
  scenarioCompare: '/scenarios/compare',
} as const;
