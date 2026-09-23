import { z } from 'zod';
import { evidenceSchema } from '../../platform/types';

const jsonObjectSchema = z.record(z.string(), z.json());

export const conversationStateSchema = z.enum(['active', 'archived', 'trashed']);
export type ConversationState = z.infer<typeof conversationStateSchema>;

export const conversationSchema = z.object({
  id: z.string(),
  household_id: z.string(),
  user_id: z.string(),
  title: z.string(),
  state: conversationStateSchema,
  pinned: z.boolean(),
  created_at: z.string(),
  updated_at: z.string(),
});
export type Conversation = z.infer<typeof conversationSchema>;

export const mentionRequestSchema = z.object({
  record_kind: z.string().optional(),
  kind: z.enum(['account', 'record']),
  id: z.string(),
});

export const readActionSchema = z.enum([
  'spending',
  'budget_review',
  'net_worth',
  'goal_progress',
  'portfolio_review',
  'credit_review',
]);

const readPlanSchema = z.object({
  kind: z.literal('read'),
  action: readActionSchema,
  parameters: z.object({ currency: z.string().nullable().optional(), month: z.string().nullable().optional() }).default({}),
});
const recordsPlanSchema = z.object({
  kind: z.literal('records'),
  resource: z.enum(['accounts', 'transactions']),
  account_id: z.string().optional(),
  record_id: z.string().optional(),
  currency: z.string().optional(),
  date_from: z.string().optional(),
  date_to: z.string().optional(),
  category: z.string().optional(),
  limit: z.number().int().positive().max(50).optional(),
  offset: z.number().int().nonnegative().optional(),
});
const calculationPlanSchema = z.object({
  kind: z.literal('calculation'),
  tool_name: z.string(),
  arguments: jsonObjectSchema,
  artifact_id: z.string().optional(),
});
const proposalPlanSchema = z.object({
  kind: z.literal('proposal'),
  command_name: z.string(),
  arguments: jsonObjectSchema,
});
const revisionPlanSchema = z.object({
  kind: z.literal('revise_proposal'),
  proposal_id: z.string(),
  revision: z.number().int().positive(),
  changes: jsonObjectSchema,
});
export const preparedActionSchema = z.discriminatedUnion('kind', [
  readPlanSchema,
  recordsPlanSchema,
  calculationPlanSchema,
  proposalPlanSchema,
  revisionPlanSchema,
]);
export type PreparedAction = z.infer<typeof preparedActionSchema>;

const targetSchema = z.object({
  page: z.string(),
  query: z.record(z.string(), z.string()).default({}),
  record_ids: z.array(z.string()).default([]),
});

export const factSchema = z.object({
  key: z.string(),
  value: z.string(),
  unit: z.enum(['money', 'percent', 'count']),
  currency: z.string().nullable(),
  record_name: z.string().nullable(),
  notes: z.array(z.literal('partial_unpriced_holdings')),
  source: evidenceSchema,
  target: targetSchema,
});
export type ReadFact = z.infer<typeof factSchema>;

const localizedTextSchema = z.object({
  locale_key: z.string(),
  interpolation_args: z.record(z.string(), z.union([z.string(), z.number(), z.boolean(), z.null()])),
});
export type LocalizedText = z.infer<typeof localizedTextSchema>;

const toolFactSourceSchema = z.object({
  kind: z.enum(['user', 'page', 'market_data', 'account', 'record', 'assumption', 'computed', 'not_found']),
  title: z.string().optional(),
  url: z.string().optional(),
  date: z.string().optional(),
  ref: z.string().optional(),
  currency: z.string().optional(),
});

const toolFactSchema = z.object({
  name: z.string(),
  label: localizedTextSchema,
  value: z.union([z.string(), z.number(), z.boolean(), z.null()]),
  value_text: localizedTextSchema.nullable().optional(),
  unit: localizedTextSchema.nullable().optional(),
  source: toolFactSourceSchema.nullable().optional(),
  comparison_only: z.boolean().default(false),
});
export type ToolFact = z.infer<typeof toolFactSchema>;

const toolInputFactSchema = toolFactSchema.extend({
  editable: z.boolean().default(false),
  unknown: z.boolean().default(false),
  driving: z.boolean().default(false),
  visibility: z.enum(['public', 'private']).default('private'),
});
export type ToolInputFact = z.infer<typeof toolInputFactSchema>;

const toolVisualSchema = z.object({
  kind: z.enum(['portfolio_equity', 'value_path']),
  currency: z.string().nullable().optional(),
  base_value: z.number().nullable().optional(),
  series: z.array(z.object({ time: z.string(), value: z.number() })),
});

const toolRepairSchema = z.object({
  kind: z.literal('set_inputs'),
  label: localizedTextSchema,
  changes: z.record(z.string(), z.union([z.string(), z.number(), z.boolean(), z.null()])),
});

const toolFailureSchema = z.object({
  code: z.string(),
  fields: z.array(z.string()),
  repair: toolRepairSchema.nullable().optional(),
});

export const toolResultCardSchema = z.object({
  kind: z.literal('tool_result'),
  schema_version: z.literal(1),
  tool_name: z.string(),
  call_id: z.string(),
  artifact_id: z.string(),
  input_revision: z.number().int().nonnegative(),
  card_type: z.string(),
  card_version: z.number().int().positive(),
  arguments: jsonObjectSchema,
  outcome: z.object({
    status: z.enum(['succeeded', 'invalid', 'ambiguous', 'bounded', 'unavailable']),
    result: jsonObjectSchema.nullable(),
    failure: toolFailureSchema.nullable(),
  }),
  presentation: z.object({
    title: localizedTextSchema,
    answer: toolFactSchema.nullable(),
    narrative: z.string().nullable(),
    sources: z.array(z.object({
      title: z.string(),
      url: z.string(),
      snippet: z.string().optional(),
      published_at: z.string().nullable().optional(),
      source_type: z.string().optional(),
    }).passthrough()),
    visual: toolVisualSchema.nullable(),
    rows: z.array(toolFactSchema),
    inputs: z.array(toolInputFactSchema),
    notes: z.array(localizedTextSchema),
  }),
  artifact_state: z.enum(['active', 'consumed', 'cancelled', 'superseded']),
});
export type ToolResultCard = z.infer<typeof toolResultCardSchema>;

export const commandFieldSchema = z.object({
  key: z.string(),
  value: z.union([z.string(), z.number(), z.boolean(), z.array(z.string())]),
  kind: z.enum(['text', 'number', 'money', 'date', 'list']),
  currency: z.string().nullable(),
  editable: z.boolean().default(true),
});
export type CommandField = z.infer<typeof commandFieldSchema>;

const commandTargetSchema = z.object({
  page: z.string(),
  record_id: z.string().nullable(),
  query: z.record(z.string(), z.string()).default({}),
});
const commandCurrencySchema = z.object({
  kind: z.enum(['account', 'record', 'explicit', 'ui_default']),
  code: z.string(),
  record_id: z.string().nullable(),
  source_id: z.string().nullable(),
  stated_request_id: z.string().nullable(),
});

export const proposalSchema = z.object({
  proposal_id: z.string(),
  conversation_id: z.string(),
  command_name: z.string(),
  revision: z.number().int().positive(),
  status: z.enum(['pending', 'superseded', 'consumed', 'cancelled']),
  title_key: z.string(),
  fields: z.array(commandFieldSchema),
  arguments: jsonObjectSchema,
  currency: z.array(commandCurrencySchema),
  evidence: z.array(evidenceSchema),
  target: commandTargetSchema,
  created_at: z.string(),
  expires_at: z.string(),
});
export type Proposal = z.infer<typeof proposalSchema>;

export const receiptSchema = z.object({
  receipt_id: z.string(),
  proposal_id: z.string(),
  conversation_id: z.string(),
  command_name: z.string(),
  revision: z.number().int().positive(),
  title_key: z.string(),
  fields: z.array(commandFieldSchema),
  evidence: z.array(evidenceSchema),
  target: commandTargetSchema,
  record_id: z.string(),
  created_at: z.string(),
});
export type CommandReceipt = z.infer<typeof receiptSchema>;

const readCardSchema = z.object({
  kind: z.literal('read'),
  action: readActionSchema,
  code: z.enum(['grounded_records', 'no_records']),
  facts: z.array(factSchema),
});
const calculationCardSchema = z.object({
  kind: z.literal('calculation'),
  card: toolResultCardSchema,
  evidence: z.array(evidenceSchema),
});
const proposalCardSchema = z.object({ kind: z.literal('proposal'), proposal: proposalSchema });
const receiptCardSchema = z.object({ kind: z.literal('receipt'), receipt: receiptSchema });
const recordsCardSchema = z.object({
  kind: z.literal('records'),
  resource: z.enum(['accounts', 'transactions']),
  query: recordsPlanSchema,
  rows: z.array(z.object({
    record_id: z.string(),
    title: z.string(),
    fields: z.array(commandFieldSchema),
    evidence: z.array(evidenceSchema),
    target: commandTargetSchema,
  })),
  total: z.number().int().nonnegative(),
  limit: z.number().int().positive(),
  offset: z.number().int().nonnegative(),
});
export const chatCardSchema = z.discriminatedUnion('kind', [readCardSchema, recordsCardSchema, calculationCardSchema, proposalCardSchema, receiptCardSchema]);
export type ChatCard = z.infer<typeof chatCardSchema>;

export const chatMessageSchema = z.object({
  id: z.string(),
  role: z.enum(['user', 'assistant']),
  turn_id: z.string(),
  text: z.string().nullable(),
  code: z.string(),
  cards: z.array(chatCardSchema),
  created_at: z.string(),
});
export type ChatMessage = z.infer<typeof chatMessageSchema>;

export const conversationListSchema = z.object({
  items: z.array(conversationSchema),
  total: z.number().int().nonnegative(),
  limit: z.number().int().positive(),
  offset: z.number().int().nonnegative(),
});
export const conversationDetailSchema = z.object({
  conversation: conversationSchema,
  messages: z.array(chatMessageSchema),
  total: z.number().int().nonnegative(),
  limit: z.number().int().positive(),
  offset: z.number().int().nonnegative(),
});
export type ConversationDetail = z.infer<typeof conversationDetailSchema>;

const declarationSchema = z.object({ name: z.string(), description: z.string(), input_schema: jsonObjectSchema });
export const capabilitiesSchema = z.object({
  read_actions: z.array(z.string()),
  record_reads: z.array(z.enum(['accounts', 'transactions'])).default([]),
  calculations: z.array(declarationSchema),
  commands: z.array(declarationSchema.extend({
    title_key: z.string(),
    target_page: z.string(),
    target_query: z.record(z.string(), z.string()).default({}),
    requires_confirmation: z.literal(true),
  })),
  examples: z.array(z.object({
    id: z.string(),
    label: z.object({ en: z.string(), 'es-419': z.string() }),
    action: preparedActionSchema,
  })),
  model_available: z.boolean(),
  legacy_history_path: z.string(),
});
export type ChatCapabilities = z.infer<typeof capabilitiesSchema>;

export const contextSchema = z.object({
  accounts: z.array(z.object({
    id: z.string(), name: z.string(), currency: z.string(), balance: z.string(), source: evidenceSchema,
  })),
  records: z.array(z.object({ id: z.string(), kind: z.string(), name: z.string(), currency: z.string().nullable().optional() })),
  selected_account: z.object({
    id: z.string(), name: z.string(), currency: z.string(), balance: z.string(), source: evidenceSchema,
  }).nullable(),
  current_proposal: proposalSchema.nullable(),
});
export type ChatContext = z.infer<typeof contextSchema>;

export const proposalMutationSchema = z.object({ proposal: proposalSchema, message: chatMessageSchema.nullable() });
export const proposalConfirmSchema = z.object({ receipt: receiptSchema, message: chatMessageSchema });

export const stageEventSchema = z.discriminatedUnion('type', [
  z.object({ type: z.literal('stage_start'), stage: z.enum(['interpret', 'execute']) }),
  z.object({ type: z.literal('stage_outcome'), stage: z.enum(['interpret', 'execute']), status: z.string() }),
]);
export const finalEventSchema = z.object({
  type: z.literal('final'),
  turn_id: z.string(),
  conversation_id: z.string(),
  status: z.enum(['completed', 'model_unavailable', 'interrupted', 'in_progress', 'failed']),
  code: z.string(),
  message: chatMessageSchema.nullable(),
});
export type FinalEvent = z.infer<typeof finalEventSchema>;

export type CommandDeclaration = ChatCapabilities['commands'][number];
export type CalculationDeclaration = ChatCapabilities['calculations'][number];
