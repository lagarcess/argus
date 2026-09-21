import { z } from 'zod';
import type { Locale } from '../contracts';

export type Page = 'overview' | 'accounts' | 'transactions' | 'spending' | 'budgets' | 'goals' | 'scenarios' | 'investments' | 'deposits' | 'credit' | 'tax-estate' | 'household' | 'membership' | 'help' | 'employer' | 'settings' | 'saved';

export interface PlatformPageProps {
  locale: Locale;
  currency: string;
  query: URLSearchParams;
  revision: number;
  onNavigate: (page: Page, query?: Record<string, string>) => void;
  onChanged: () => void;
}

export const evidenceSchema = z.object({
  id: z.string(),
  kind: z.enum(['synthetic', 'user', 'calculated', 'published']),
  title: z.string(),
  as_of: z.string(),
  recorded_at: z.string(),
  published_on: z.string().nullable(),
  method: z.string().nullable(),
  inputs: z.array(z.string()),
  url: z.string().nullable(),
});
export type Evidence = z.infer<typeof evidenceSchema>;
export type { Locale };
