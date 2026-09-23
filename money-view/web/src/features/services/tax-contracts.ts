import { z } from 'zod';
import { evidenceSchema } from '../../platform/types';

export const taxScenarioSchema = z.object({
  id: z.string(), organizer_id: z.string(), recorded_at: z.string(),
  income: z.string(), expenses: z.string(), net_amount: z.string(),
  user_rate_pct: z.string(), scenario_amount: z.string(), currency: z.string(),
  formula: z.string(), legal_status: z.literal('worksheet_only'),
  evidence: evidenceSchema, rate_evidence: evidenceSchema,
  inputs: z.object({
    organizer: z.object({ id: z.string(), country: z.string(), year: z.number(), currency: z.string() }),
    user_rate_pct: z.string(),
    items: z.array(z.object({ id: z.string(), title: z.string(), kind: z.string(), amount: z.string().nullable(), effective_on: z.string(), recorded_at: z.string() })),
  }),
});

export const taxScenarioListSchema = z.object({
  items: z.array(z.object({ id: z.string(), recorded_at: z.string(), user_rate_pct: z.string() })),
  count: z.number(), limit: z.number(), offset: z.number(),
});
