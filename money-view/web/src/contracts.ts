import { z } from 'zod';

const decimal = z
  .string()
  .regex(/^-?\d+(\.\d+)?([eE][+-]?\d+)?$/)
  .refine((value) => Number.isFinite(Number(value)));
export const localeSchema = z.enum(['es-419', 'en']);
export type Locale = z.infer<typeof localeSchema>;
export const sourceSchema = z.object({
  id: z.string(),
  title: z.string(),
  url: z.string(),
  published_on: z.string(),
  retrieved_at: z.string(),
  kind: z.enum(['synthetic', 'published']),
});
export type Source = z.infer<typeof sourceSchema>;
export const inputSourceSchema = z.object({
  kind: z.enum(['user', 'assumption']),
  recorded_on: z.string(),
});
export type InputSource = z.infer<typeof inputSourceSchema>;
export const inputsSchema = z.object({
  amount: decimal,
  currency: z.string(),
  horizon_days: z.number().int(),
  country: z.string(),
  current_annual_rate_pct: decimal.nullable(),
});
export type PlacementInputs = z.infer<typeof inputsSchema>;
const inflationSchema = z.object({
  country: z.string(),
  currency: z.string(),
  annual_rate_pct: decimal,
  source: sourceSchema,
});
const formulaSchema = z.object({
  amount: decimal,
  horizon_days: z.number(),
  year_fraction: decimal,
  annual_rate_pct: decimal,
  annual_fee: decimal,
  interest: decimal,
  fee_amount: decimal,
  nominal_end_value: decimal,
  inflation_annual_rate_pct: decimal,
  inflation_factor: decimal,
  real_value: decimal,
});
export const rowSchema = z.object({
  id: z.string(),
  institution: z.string(),
  product_type: z.enum(['cash', 'savings', 'certificate']),
  is_baseline: z.boolean(),
  annual_rate_pct: decimal,
  end_value: decimal,
  effective_annual_rate_pct: decimal,
  real_value: decimal,
  interest: decimal,
  fees: decimal,
  source: z.union([sourceSchema, inputSourceSchema]),
  fee_source: sourceSchema.nullable(),
  formula: formulaSchema,
});
export type ComparisonRow = z.infer<typeof rowSchema>;
export const resultSchema = z.object({
  id: z.string(),
  inputs: inputsSchema,
  dataset_id: z.string(),
  created_at: z.string(),
  input_source: inputSourceSchema,
  rows: z.array(rowSchema),
  winner_ids: z.array(z.string()),
  inflation: inflationSchema,
  assumptions: z.array(z.string()),
  synthetic: z.boolean(),
});
export type ComparisonResult = z.infer<typeof resultSchema>;
export const confirmationSchema = z.object({
  id: z.string(),
  inputs: inputsSchema,
  dataset_id: z.string(),
  created_at: z.string(),
  expires_at: z.string(),
  assumptions: z.array(z.string()),
  synthetic: z.boolean(),
});
export type Confirmation = z.infer<typeof confirmationSchema>;
const checkFields = z.object({
  id: z.string(),
  decision_id: z.string(),
  load_id: z.string(),
  created_at: z.string(),
  before_comparison_id: z.string(),
  reasons: z.array(z.string()),
  reference_annual_rate_pct: decimal.nullable(),
  read_at: z.string().nullable(),
});
const checkSchema = z.discriminatedUnion('status', [
  checkFields.extend({
    status: z.literal('failed'),
    after_comparison_id: z.null(),
    error_code: z.string(),
  }),
  checkFields.extend({
    status: z.enum(['unchanged', 'changed']),
    after_comparison_id: z.string(),
    error_code: z.null(),
  }),
]);
export const decisionSchema = z.object({
  id: z.string(),
  comparison_id: z.string(),
  created_at: z.string(),
  baseline: resultSchema,
  latest: resultSchema,
  checks: z.array(checkSchema),
});
export type SavedDecision = z.infer<typeof decisionSchema>;
export const noticeSchema = z.object({
  id: z.string(),
  decision_id: z.string(),
  created_at: z.string(),
  reasons: z.array(z.string()),
  before: resultSchema,
  after: resultSchema,
  reference_annual_rate_pct: decimal.nullable(),
  read_at: z.string().nullable(),
});
export type Notice = z.infer<typeof noticeSchema>;
export const exampleSchema = z.object({
  id: z.string(),
  messages: z.object({ 'es-419': z.string(), en: z.string() }),
  inputs: inputsSchema,
  source: sourceSchema,
});
export type Example = z.infer<typeof exampleSchema>;
export const homeSchema = z.object({
  demo: z.boolean(),
  interpreter_mode: z.string(),
  countries: z.array(
    z.object({ code: z.string(), name: z.string(), currencies: z.array(z.string()) }),
  ),
  examples: z.array(exampleSchema),
  source_status: z.object({
    state: z.enum(['ready', 'loading', 'stale', 'unavailable']),
    last_success_at: z.string().nullable(),
    last_attempt_at: z.string().nullable(),
    error_code: z.string().nullable(),
    dataset_id: z.string().nullable(),
    load_id: z.string().nullable(),
  }),
  saved: z.array(decisionSchema),
  notices: z.array(noticeSchema),
});
export type Home = z.infer<typeof homeSchema>;
export const interpretationSchema = z.discriminatedUnion('status', [
  z.object({ status: z.literal('confirmation'), confirmation: confirmationSchema }),
  z.object({
    status: z.enum(['needs_input', 'unsupported', 'model_unavailable']),
    code: z.string().optional(),
    missing_fields: z.array(z.string()).optional(),
  }),
]);
export type Scenario = 'same_winner' | 'leader_changed' | 'inflation_crossed' | 'failure';
