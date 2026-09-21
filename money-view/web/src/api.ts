import { z } from 'zod';
import { request as platformRequest } from './platform/client';
export { APIError as ApiError } from './platform/client';
import {
  homeSchema,
  interpretationSchema,
  resultSchema,
  decisionSchema,
  confirmationSchema,
  type PlacementInputs,
  type Locale,
  type Scenario,
} from './contracts';

async function request<T>(path: string, schema: z.ZodType<T>, body?: unknown): Promise<T> {
  return platformRequest(`/api${path}`, schema, body === undefined ? {} : {
    method: 'POST', body: JSON.stringify(body),
  });
}
export const api = {
  home: () => request('/home', homeSchema),
  prepare: (inputs: PlacementInputs) => request('/confirmations', confirmationSchema, { inputs }),
  interpret: (message: string, locale: Locale, demo_example_id?: string) =>
    request('/interpret', interpretationSchema, {
      message,
      locale,
      ...(demo_example_id ? { demo_example_id } : {}),
    }),
  compute: (id: string, inputs: PlacementInputs) =>
    request(`/confirmations/${encodeURIComponent(id)}/compute`, resultSchema, { inputs }),
  save: (id: string) => request(`/comparisons/${encodeURIComponent(id)}/save`, decisionSchema, {}),
  decision: (id: string) => request(`/decisions/${encodeURIComponent(id)}`, decisionSchema),
  readNotice: (id: string) => request(`/notices/${encodeURIComponent(id)}/read`, z.unknown(), {}),
  simulate: (scenario: Scenario) =>
    request('/demo/events', z.object({ load_id: z.string(), job_id: z.string() }), { scenario, idempotency_key: crypto.randomUUID() }),
  job: (id: string) => request(`/platform/jobs/${encodeURIComponent(id)}`, z.object({
    id: z.string(), status: z.enum(['queued', 'running', 'succeeded', 'failed']), error_code: z.string().nullable(),
  })),
  source: (id: string) => request(`/sources/${encodeURIComponent(id)}`, z.unknown()),
};
