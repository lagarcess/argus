import { z } from 'zod';
import {
  homeSchema,
  interpretationSchema,
  resultSchema,
  decisionSchema,
  type PlacementInputs,
  type Locale,
  type Scenario,
} from './contracts';

export class ApiError extends Error {
  constructor(public readonly code: string) {
    super(code);
  }
}
async function request<T>(path: string, schema: z.ZodType<T>, body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(
      `/api${path}`,
      body === undefined
        ? undefined
        : {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
          },
    );
  } catch {
    throw new ApiError('network_error');
  }
  const data: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const error = z.object({ code: z.string() }).safeParse(data);
    throw new ApiError(error.success ? error.data.code : 'request_failed');
  }
  const parsed = schema.safeParse(data);
  if (!parsed.success) throw new ApiError('invalid_response');
  return parsed.data;
}
export const api = {
  home: () => request('/home', homeSchema),
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
    request('/demo/events', z.object({ load_id: z.string() }), { scenario }),
  source: (id: string) => request(`/sources/${encodeURIComponent(id)}`, z.unknown()),
};
