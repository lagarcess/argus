import { APIError, requestResponse } from '../../platform/client';
import { finalEventSchema, stageEventSchema, type FinalEvent, type PreparedAction } from './contracts';

export type TurnPayload = {
  turn_id: string;
  conversation_id?: string;
  text?: string;
  action?: PreparedAction;
  locale: 'es-419' | 'en';
  currency?: string;
  default_currency?: string;
  account_id?: string;
  mentions?: Array<{ kind: 'account' | 'record'; id: string; record_kind?: string }>;
};

/** Keeps the view default separate from a denomination explicitly owned by a typed action. */
export function turnCurrencyContext(defaultCurrency: string, action?: PreparedAction) {
  const explicit = !action ? undefined
    : action.kind === 'read' ? action.parameters.currency ?? undefined
    : action.kind === 'records' ? action.currency ?? undefined
    : 'arguments' in action && typeof action.arguments.currency === 'string' ? action.arguments.currency
    : 'changes' in action && typeof action.changes.currency === 'string' ? action.changes.currency
    : undefined;
  return {
    ...(defaultCurrency ? { default_currency: defaultCurrency } : {}),
    ...(explicit ? { currency: explicit } : {}),
  };
}

type StageEvent = { type: 'stage_start' | 'stage_outcome'; stage: 'interpret' | 'execute'; status?: string };

function eventData(frame: string) {
  return frame
    .split(/\r?\n/)
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).trimStart())
    .join('\n');
}

function parseEvent(data: string): StageEvent | FinalEvent | null {
  if (!data || data === '[DONE]') return null;
  let value: unknown;
  try {
    value = JSON.parse(data);
  } catch {
    throw new APIError('invalid_response');
  }
  const final = finalEventSchema.safeParse(value);
  if (final.success) return final.data;
  const stage = stageEventSchema.safeParse(value);
  if (stage.success) return stage.data;
  throw new APIError('invalid_response');
}

export async function streamTurn(
  payload: TurnPayload,
  options: { signal: AbortSignal; onStage: (event: StageEvent) => void },
): Promise<FinalEvent> {
  const response = await requestResponse('/chat/turn', {
    method: 'POST',
    body: JSON.stringify(payload),
    signal: options.signal,
  });
  if (!response.body) throw new APIError('invalid_response', response.status);
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let final: FinalEvent | null = null;
  let done = false;

  const consume = (frame: string) => {
    const data = eventData(frame);
    if (data === '[DONE]') {
      done = true;
      return;
    }
    const event = parseEvent(data);
    if (!event) return;
    if (event.type === 'final') final = event;
    else options.onStage(event);
  };

  while (true) {
    const chunk = await reader.read();
    buffer += decoder.decode(chunk.value, { stream: !chunk.done }).replaceAll('\r\n', '\n');
    let boundary = buffer.indexOf('\n\n');
    while (boundary >= 0) {
      consume(buffer.slice(0, boundary));
      buffer = buffer.slice(boundary + 2);
      boundary = buffer.indexOf('\n\n');
    }
    if (chunk.done) break;
  }
  if (buffer.trim()) consume(buffer);
  if (!done || !final) throw new APIError('stream_incomplete');
  return final as FinalEvent;
}
