import { z } from 'zod';

export const profileSchema = z.object({ id: z.string(), display_name: z.string(), preferred_name: z.string().nullable(), avatar_color: z.string() });
export const preferencesSchema = z.object({ locale: z.enum(['es-419', 'en']), timezone: z.string(), appearance: z.enum(['light', 'dark', 'system']), sidebar_compact: z.boolean(), notifications: z.object({ bills: z.boolean(), account_changes: z.boolean(), product_updates: z.boolean() }) });
export const householdSchema = z.object({ id: z.string(), name: z.string(), country: z.string().nullable(), currency_override: z.string().nullable(), effective_currency: z.string().nullable(), role: z.enum(['owner', 'editor', 'viewer']) });
export const settingsSchema = z.object({ profile: profileSchema, preferences: preferencesSchema, household: householdSchema, supported_currencies: z.array(z.string()), memory: z.object({ enabled: z.boolean(), count: z.number() }), capabilities: z.object({ data_domains: z.array(z.string()) }).passthrough() });
export type Settings = z.infer<typeof settingsSchema>;
export const memorySchema = z.object({ id: z.string(), content: z.string(), created_at: z.string(), updated_at: z.string() });
export const memoriesSchema = z.object({ enabled: z.boolean(), items: z.array(memorySchema), local_only: z.boolean() });
export const sessionsSchema = z.object({ items: z.array(z.object({ id: z.string(), created_at: z.string(), expires_at: z.string(), last_seen_at: z.string(), current: z.boolean() })) });
export const membersSchema = z.object({ items: z.array(z.object({ user_id: z.string(), display_name: z.string(), preferred_name: z.string().nullable(), avatar_color: z.string(), role: z.enum(['owner', 'editor', 'viewer']) })) });
export const feedbackSchema = z.object({ id: z.string(), kind: z.string(), message: z.string(), created_at: z.string(), status: z.literal('saved_locally'), local_only: z.boolean().optional() });
export const usageSchema = z.object({ as_of: z.string(), local_only: z.boolean(), metrics: z.record(z.string(), z.number()), domains: z.record(z.string(), z.record(z.string(), z.number())) });
export const jsonObjectSchema = z.record(z.string(), z.unknown());
export type Text = (es: string, en: string) => string;
export const dateText = (date: string, locale: string) => new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(date));

export function downloadJson(data: unknown, filename: string) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
