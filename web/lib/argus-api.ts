import { getSupabaseClient } from "./supabase-client";
import type { AssetClass } from "./argus-types";
import type {
  ChatActionOption,
  ChatMention,
  StrategyConfirmationPayload,
} from "@/components/chat/types";
import { normalizeEnabledLanguage, type ArgusLocale } from "./language-features";
import {
  displayResultActionLabel,
  displayResultBenchmarkNote,
  displayResultMetricLabel,
  resultMetricDisplayOrder,
} from "./result-card-display";

// ─── Shared primitive types ──────────────────────────────────────────────────

export type { AssetClass } from "./argus-types";
export type BacktestStatus = "queued" | "running" | "completed" | "failed";
export type BacktestJobStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "canceled"
  | "expired";
export type TitleSource = "system_default" | "ai_generated" | "user_renamed";
export type HistoryItemType = "chat" | "strategy" | "collection" | "run";
export type OnboardingStage =
  | "language_selection"
  | "primary_goal_selection"
  | "ready"
  | "completed";
export type PrimaryGoal =
  | "learn_basics"
  | "build_passive_strategy"
  | "test_stock_idea"
  | "explore_crypto"
  | "surprise_me";

// ─── Metric / result card types ──────────────────────────────────────────────

export type ApiMetricRow = {
  key: string;
  label: string;
  value: string;
};

export type ResultChartPayload = {
  kind: "portfolio_equity";
  series: Array<{ time: string; value: number }>;
  markers?: Array<{
    time: string;
    type: "entry" | "exit";
    label: string;
    symbols?: string[];
  }>;
  currency?: string;
  base_value?: number | null;
  attribution?: string;
};

export type ConversationResultCard = {
  title: string;
  symbols?: string[];
  strategy_label?: string;
  asset_class?: AssetClass | null;
  date_range: {
    start: string;
    end: string;
    display: string;
  };
  status_label: string;
  rows: ApiMetricRow[];
  benchmark_note?: string | null;
  assumptions: string[];
  actions: ChatActionOption[];
  chart?: ResultChartPayload | null;
};

// ─── Domain objects ──────────────────────────────────────────────────────────

export type BacktestRun = {
  id: string;
  conversation_id?: string | null;
  strategy_id?: string | null;
  status: BacktestStatus;
  asset_class: AssetClass;
  symbols: string[];
  allocation_method: "equal_weight";
  benchmark_symbol: string;
  metrics: {
    aggregate: Record<string, unknown>;
    by_symbol: Record<string, unknown>;
  };
  config_snapshot: Record<string, unknown>;
  conversation_result_card: ConversationResultCard;
  chart?: ResultChartPayload | null;
  trades?: Record<string, unknown>[] | null;
  created_at: string;
};

export type BacktestJob = {
  id: string;
  conversation_id: string;
  request_message_id?: string | null;
  confirmation_message_id?: string | null;
  status: BacktestJobStatus;
  result_run_id?: string | null;
  failure_code?: string | null;
  failure_detail?: string | null;
  retryable: boolean;
  queued_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type BacktestJobResponse = {
  job: BacktestJob;
  run: BacktestRun | null;
  result_readout?: string | null;
  result_readout_source?: string | null;
  result_readout_fallback_used?: boolean | null;
  result_readout_failure_mode?: string | null;
};

export type Conversation = {
  id: string;
  title: string;
  title_source: TitleSource;
  pinned: boolean;
  archived: boolean;
  created_at: string;
  updated_at: string;
  last_message_preview?: string | null;
  language?: "en" | "es-419" | null;
};

export type ApiUser = {
  id: string;
  email: string;
  username: string | null;
  display_name: string | null;
  language: "en" | "es-419";
  locale: "en-US" | "es-419";
  onboarding: {
    completed: boolean;
    stage: OnboardingStage;
    language_confirmed: boolean;
    primary_goal: PrimaryGoal | null;
  };
};

type AuthSessionPayload = {
  access_token?: string;
  refresh_token?: string;
  expires_in?: number;
};

type AuthResponsePayload = {
  session?: AuthSessionPayload | null;
  user?: Record<string, unknown> | null;
};

/** Backend message shape (distinct from the frontend chat Message type) */
export type ApiMessage = {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  created_at: string;
  metadata?: Record<string, unknown> | null;
};

export type StrategySurfaceMetricRow = {
  symbol: string;
  asset_name: string;
  values: Record<string, string>;
};

export type StrategySurfaceMetrics = {
  display_mode: string;
  as_of_run_id: string | null;
  columns: Array<{ key: string; label: string }>;
  rows: StrategySurfaceMetricRow[];
  headline?: { label: string; value: string } | null;
};

export type Strategy = {
  id: string;
  name: string;
  name_source: TitleSource;
  template: string;
  asset_class: AssetClass;
  symbols: string[];
  parameters: Record<string, unknown>;
  metrics_preferences: string[];
  benchmark_symbol: string;
  pinned: boolean;
  deleted_at: string | null;
  created_at: string;
  updated_at: string;
  strategy_surface_metrics?: StrategySurfaceMetrics | null;
};

export type Collection = {
  id: string;
  name: string;
  name_source: TitleSource;
  pinned: boolean;
  strategy_count: number;
  deleted_at: string | null;
  created_at: string;
  updated_at: string;
};

export type HistoryItem = {
  type: HistoryItemType;
  id: string;
  title: string;
  subtitle: string;
  pinned: boolean;
  created_at: string;
  conversation_id?: string | null;
};

export type SearchItem = {
  type: "chat" | "strategy" | "collection" | "run";
  id: string;
  title: string;
  matched_text: string;
  updated_at: string;
  conversation_id?: string | null;
};

// ─── Chat stream event types ──────────────────────────────────────────────────

export type ChatStreamEvent =
  | { event: "token"; data: { text: string } }
  | { event: "title"; data: { conversation_id: string; title: string } }
  | { event: "status"; data: { status: string } }
  | { event: "stage_start"; data: { stage: string } }
  | { event: "stage_outcome"; data: { outcome: string } }
  | { event: "final"; data: ChatFinalPayload }
  | { event: "confirmation"; data: { confirmation: StrategyConfirmationPayload } }
  | { event: "result"; data: { run: BacktestRun } }
  | { event: "error"; data: { code?: string; detail: string; message_id?: string } }
  | { event: "done"; data: { message_id: string | null } };

export type ChatFinalPayload = {
  stage_outcome?: string;
  assistant_response?: string | null;
  assistant_prompt?: string | null;
  confirmation?: StrategyConfirmationPayload | null;
  confirmation_cancelled?: { confirmation_id?: string | null } | null;
  confirmation_payload?: Record<string, unknown> | null;
  pending_strategy?: {
    strategy: Record<string, unknown>;
    requested_field?: string | null;
    missing_required_fields?: string[];
    pending_resolution?: Record<string, unknown> | null;
  } | null;
  run?: BacktestRun | null;
  backtest_job?: BacktestJob | null;
  next_actions?: string[];
  message_id?: string | null;
};

export type ChatActionRequest = {
  type: NonNullable<ChatActionOption["type"]>;
  label?: string;
  labelKey?: string;
  payload?: Record<string, unknown>;
  presentation?: "confirmation" | "result";
};

export class ChatStreamError extends Error {
  status: number;
  code: string;

  constructor(message: string, status: number, code = "unknown") {
    super(message);
    this.name = "ChatStreamError";
    this.status = status;
    this.code = code;
  }
}

const CHAT_STREAM_INTERRUPTED_MESSAGE =
  "The connection ended before Argus finished responding. Please try again.";

export type DiscoveryItem = {
  id: string;
  type: "asset" | "indicator";
  label: string;
  symbol?: string | null;
  asset_class?: AssetClass | null;
  description?: string | null;
  insert_text: string;
  provider: string;
  support_status: "supported" | "draft_only" | "unavailable";
};

type DiscoveryResponsePayload = { items: DiscoveryItem[] };

// ─── Config ───────────────────────────────────────────────────────────────────

const API_BASE = (() => {
  if (process.env.NEXT_PUBLIC_ARGUS_API_URL) {
    return process.env.NEXT_PUBLIC_ARGUS_API_URL;
  }
  if (typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname}:8000/api/v1`;
  }
  return "http://127.0.0.1:8000/api/v1";
})();

export type ApiLanguage = "en" | "es-419";

const DISCOVERY_SEARCH_CACHE_TTL_MS = 30_000;
const DISCOVERY_SEARCH_CACHE_MAX_ENTRIES = 80;
const discoverySearchCache = new Map<
  string,
  { expiresAt: number; promise: Promise<DiscoveryResponsePayload> }
>();

function discoverySearchCacheKey(
  kind: "assets" | "indicators",
  query: string,
  limit: number,
) {
  return `${kind}:${limit}:${query.trim().toLowerCase()}`;
}

function cachedDiscoverySearch(
  key: string,
  now: number,
): Promise<DiscoveryResponsePayload> | null {
  const cached = discoverySearchCache.get(key);
  if (!cached) return null;
  if (cached.expiresAt <= now) {
    discoverySearchCache.delete(key);
    return null;
  }
  discoverySearchCache.delete(key);
  discoverySearchCache.set(key, cached);
  return cached.promise;
}

function rememberDiscoverySearch(
  key: string,
  promise: Promise<DiscoveryResponsePayload>,
  expiresAt: number,
) {
  discoverySearchCache.delete(key);
  discoverySearchCache.set(key, { expiresAt, promise });
  while (discoverySearchCache.size > DISCOVERY_SEARCH_CACHE_MAX_ENTRIES) {
    const oldestKey = discoverySearchCache.keys().next().value;
    if (!oldestKey) break;
    discoverySearchCache.delete(oldestKey);
  }
}

// ─── Utilities ────────────────────────────────────────────────────────────────

export function resultCardFromConversationCard(
  card: ConversationResultCard,
  run?: Pick<BacktestRun, "id" | "strategy_id"> &
    Partial<
      Pick<BacktestRun, "asset_class" | "benchmark_symbol" | "config_snapshot">
    >,
) {
  const rows = [...card.rows].sort(
    (a, b) => resultMetricDisplayOrder(a) - resultMetricDisplayOrder(b),
  );

  return {
    strategyName: card.title,
    strategyLabel: card.strategy_label,
    symbols: card.symbols,
    period: card.date_range.display,
    dateRange: card.date_range,
    statusLabel: card.status_label,
    metrics: rows.map((row) => ({
      label: displayResultMetricLabel(row, run?.benchmark_symbol),
      value: row.value,
    })),
    benchmarkNote: displayResultBenchmarkNote(card.benchmark_note),
    assumptions: card.assumptions,
    assetClass: run?.asset_class ?? card.asset_class ?? undefined,
    configSnapshot: run?.config_snapshot,
    runId: run?.id,
    strategyId: run?.strategy_id ?? null,
    actions: card.actions.map((action) => ({
      ...action,
      label: displayResultActionLabel(action),
    })),
    chart: card.chart ?? null,
  };
}

export function resultCardFromRun(run: BacktestRun) {
  return {
    ...resultCardFromConversationCard(run.conversation_result_card, run),
    symbols: run.symbols,
    template: String(run.config_snapshot?.template ?? ""),
    assetClass: run.asset_class,
    configSnapshot: run.config_snapshot,
  };
}

export function normalizeApiLanguage(language?: string | null): ApiLanguage {
  return normalizeEnabledLanguage(language);
}

/**
 * Formats an ISO timestamp as a human-readable relative date string.
 * Returns "today", "yesterday", or a short locale date string.
 */
export function formatRelativeDate(
  isoString: string,
  labels: { today: string; yesterday: string },
  locale: string = "en-US",
): string {
  const date = new Date(isoString);
  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterdayStart = new Date(todayStart);
  yesterdayStart.setDate(yesterdayStart.getDate() - 1);

  if (date >= todayStart) return labels.today;
  if (date >= yesterdayStart) return labels.yesterday;

  return date.toLocaleDateString(locale, {
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

// ─── Generic fetch helper ─────────────────────────────────────────────────────

async function apiFetch<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const isMockAuth = process.env.NEXT_PUBLIC_MOCK_AUTH === "true";
  const authHeaders: Record<string, string> = {};

  if (!isMockAuth) {
    const supabase = getSupabaseClient();
    if (!supabase) {
      throw new Error("Supabase auth client is unavailable in non-mock mode.");
    }
    const { data, error } = await supabase.auth.getSession();
    if (!error && data.session) {
      authHeaders["Authorization"] = `Bearer ${data.session.access_token}`;
    }
  }

  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...authHeaders, ...(options?.headers || {}) },
    credentials: "include",
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = (body as { detail?: unknown }).detail;
    const errorMsg = typeof detail === 'object' && detail !== null
      ? (detail as { title?: unknown }).title as string
      : detail;

    const error = new Error(
      (errorMsg as string) ?? `API error ${response.status}`,
    ) as Error & { status: number; code: string };
    (error as Error & { status: number }).status = response.status;
    (error as Error & { code: string }).code =
      (body as Record<string, unknown>).code as string ?? "unknown";
    throw error;
  }
  return response.json() as Promise<T>;
}

async function unauthenticatedApiFetch<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers || {}),
    },
    credentials: "include",
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = (body as { detail?: unknown }).detail;
    const message =
      typeof detail === "object" && detail !== null && "detail" in detail
        ? String((detail as { detail?: unknown }).detail ?? "")
        : typeof detail === "string"
          ? detail
          : `API error ${response.status}`;
    const error = new Error(message) as Error & { status: number; code: string };
    error.status = response.status;
    error.code = String((body as Record<string, unknown>).code ?? "unknown");
    throw error;
  }
  return response.json() as Promise<T>;
}

async function persistBrowserSession(payload: AuthResponsePayload) {
  const session = payload.session;
  if (!session?.access_token || !session.refresh_token) {
    return;
  }
  const supabase = getSupabaseClient();
  if (!supabase) {
    return;
  }
  await supabase.auth.setSession({
    access_token: session.access_token,
    refresh_token: session.refresh_token,
  });
}

// ─── Profile ──────────────────────────────────────────────────────────────────

export type ProfilePatch = {
  language?: "en" | "es-419";
  locale?: ArgusLocale;
  theme?: string;
  display_name?: string;
  onboarding?: Partial<{
    completed: boolean;
    stage: OnboardingStage;
    language_confirmed: boolean;
    primary_goal: PrimaryGoal | null;
  }>;
};

export async function getMe() {
  return apiFetch<{ user: ApiUser }>("/me");
}

export async function patchMe(patch: ProfilePatch) {
  return apiFetch<{ user: ApiUser }>("/me", {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export async function getStarterPrompts() {
  const response = await apiFetch<{ prompts: string[] }>("/chat/starter-prompts");
  return response.prompts;
}

// ─── Auth ─────────────────────────────────────────────────────────────────────

export async function signupWithEmail(payload: {
  email: string;
  password: string;
  display_name?: string | null;
  username?: string | null;
}) {
  const response = await unauthenticatedApiFetch<AuthResponsePayload>("/auth/signup", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  await persistBrowserSession(response);
  return response;
}

export async function loginWithEmail(payload: { email: string; password: string }) {
  const response = await unauthenticatedApiFetch<AuthResponsePayload>("/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  await persistBrowserSession(response);
  return response;
}

export async function logoutFromApi() {
  try {
    return await apiFetch<{ success: boolean }>("/auth/logout", { method: "POST" });
  } finally {
    await getSupabaseClient()?.auth.signOut().catch(() => null);
  }
}

export async function createConversation(language?: string | null) {
  const payload: { title: null; language?: ApiLanguage } = { title: null };
  if (language) {
    payload.language = normalizeApiLanguage(language);
  }

  return apiFetch<{ conversation: Conversation }>("/conversations", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// ─── Conversations ────────────────────────────────────────────────────────────

export async function listConversations(params: { limit?: number; cursor?: string; archived?: boolean; deleted?: boolean } = {}) {
  const { limit = 20, cursor, archived, deleted } = params;
  const searchParams = new URLSearchParams({ limit: String(limit) });
  if (cursor) searchParams.append("cursor", cursor);
  if (archived !== undefined) searchParams.append("archived", String(archived));
  if (deleted !== undefined) searchParams.append("deleted", String(deleted));

  return apiFetch<{ items: Conversation[]; next_cursor: string | null }>(
    `/conversations?${searchParams.toString()}`,
  );
}

export async function getConversationMessages(
  conversationId: string,
  limit = 50,
  cursor?: string,
) {
  const searchParams = new URLSearchParams({ limit: String(limit) });
  if (cursor) searchParams.append("cursor", cursor);
  return apiFetch<{ items: ApiMessage[]; next_cursor: string | null }>(
    `/conversations/${conversationId}/messages?${searchParams.toString()}`,
  );
}

export async function patchConversation(
  conversationId: string,
  patch: { title?: string; pinned?: boolean; archived?: boolean; deleted_at?: string | null },
) {
  return apiFetch<{ conversation: Conversation }>(
    `/conversations/${conversationId}`,
    { method: "PATCH", body: JSON.stringify(patch) },
  );
}

export async function deleteConversation(conversationId: string) {
  return apiFetch<{ success: boolean }>(`/conversations/${conversationId}`, {
    method: "DELETE",
  });
}

export async function deleteAllConversations() {
  return apiFetch<{ success: boolean; deleted_count: number }>("/conversations", {
    method: "DELETE",
  });
}

// ─── History ──────────────────────────────────────────────────────────────────

export async function listHistory(params: { limit?: number; cursor?: string; archived?: boolean; deleted?: boolean } = {}) {
  const { limit = 20, cursor, archived, deleted } = params;
  const searchParams = new URLSearchParams({ limit: String(limit) });
  if (cursor) searchParams.append("cursor", cursor);
  if (archived !== undefined) searchParams.append("archived", String(archived));
  if (deleted !== undefined) searchParams.append("deleted", String(deleted));

  return apiFetch<{ items: HistoryItem[]; next_cursor: string | null }>(
    `/history?${searchParams.toString()}`,
  );
}

// ─── Strategies ───────────────────────────────────────────────────────────────

export async function listStrategies(params: { limit?: number; cursor?: string; deleted?: boolean } = {}) {
  const { limit = 50, cursor, deleted } = params;
  const searchParams = new URLSearchParams({ limit: String(limit) });
  if (cursor) searchParams.append("cursor", cursor);
  if (deleted !== undefined) searchParams.append("deleted", String(deleted));

  return apiFetch<{ items: Strategy[]; next_cursor: string | null }>(
    `/strategies?${searchParams.toString()}`,
  );
}

export async function createStrategy(payload: {
  name?: string | null;
  template: string;
  asset_class: AssetClass;
  symbols: string[];
  parameters?: Record<string, unknown>;
  metrics_preferences?: string[];
  benchmark_symbol?: string | null;
}) {
  return apiFetch<{ strategy: Strategy }>("/strategies", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function patchStrategy(
  strategyId: string,
  patch: { name?: string; pinned?: boolean; deleted_at?: string | null },
) {
  return apiFetch<{ strategy: Strategy }>(`/strategies/${strategyId}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export async function deleteStrategy(strategyId: string) {
  return apiFetch<{ success: boolean }>(`/strategies/${strategyId}`, {
    method: "DELETE",
  });
}

// ─── Collections ──────────────────────────────────────────────────────────────

export async function listCollections(
  params: number | { limit?: number; cursor?: string } = 50,
) {
  const limit = typeof params === "number" ? params : (params.limit ?? 50);
  const cursor = typeof params === "number" ? undefined : params.cursor;
  const searchParams = new URLSearchParams({ limit: String(limit) });
  if (cursor) searchParams.append("cursor", cursor);
  return apiFetch<{ items: Collection[]; next_cursor: string | null }>(
    `/collections?${searchParams.toString()}`,
  );
}

export async function searchGlobal(params: { q: string; limit?: number; cursor?: string }) {
  const { q, limit = 20, cursor } = params;
  const searchParams = new URLSearchParams({
    q,
    limit: String(limit),
  });
  if (cursor) searchParams.append("cursor", cursor);
  return apiFetch<{ items: SearchItem[]; next_cursor: string | null }>(
    `/search?${searchParams.toString()}`,
  );
}

export async function createCollection(name?: string) {
  return apiFetch<{ collection: Collection }>("/collections", {
    method: "POST",
    body: JSON.stringify({ name: name ?? null }),
  });
}

export async function patchCollection(
  collectionId: string,
  patch: { name?: string; pinned?: boolean },
) {
  return apiFetch<{ collection: Collection }>(`/collections/${collectionId}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export async function deleteCollection(collectionId: string) {
  return apiFetch<{ success: boolean }>(`/collections/${collectionId}`, {
    method: "DELETE",
  });
}

export async function attachStrategyToCollection(
  collectionId: string,
  strategyId: string,
) {
  return apiFetch<{ collection: Collection }>(
    `/collections/${collectionId}/strategies`,
    { method: "POST", body: JSON.stringify({ strategy_ids: [strategyId] }) },
  );
}

// ─── Backtests ────────────────────────────────────────────────────────────────

export async function runBacktest(payload: {
  template?: string;
  asset_class?: AssetClass;
  symbols: string[];
  strategy_id?: string;
  conversation_id?: string;
  timeframe?: string;
  start_date?: string;
  end_date?: string;
  starting_capital?: number;
}) {
  return apiFetch<{ run: BacktestRun }>("/backtests/run", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": crypto.randomUUID(),
    },
    body: JSON.stringify(payload),
  });
}

export async function getBacktestRun(runId: string) {
  return apiFetch<{ run: BacktestRun }>(`/backtests/${runId}`);
}

export async function getBacktestJob(jobId: string) {
  return apiFetch<BacktestJobResponse>(`/backtest-jobs/${jobId}`);
}

// ─── Chat stream ──────────────────────────────────────────────────────────────

export async function streamChatMessage(
  conversationId: string,
  input: string | ChatActionRequest,
  language: string | null | undefined,
  onEvent: (event: ChatStreamEvent) => void,
  mentions: ChatMention[] = [],
) {
  const isMockAuth = process.env.NEXT_PUBLIC_MOCK_AUTH === "true";
  const authHeaders: Record<string, string> = {};

  if (!isMockAuth) {
    const supabase = getSupabaseClient();
    if (!supabase) {
      throw new Error("Supabase auth client is unavailable in non-mock mode.");
    }
    const { data, error } = await supabase.auth.getSession();
    if (!error && data.session) {
      authHeaders["Authorization"] = `Bearer ${data.session.access_token}`;
    }
  }

  const response = await fetch(`${API_BASE}/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": crypto.randomUUID(),
      ...authHeaders,
    },
    body: JSON.stringify({
      conversation_id: conversationId,
      ...(typeof input === "string" ? { message: input } : { action: input }),
      ...(typeof input === "string" && mentions.length > 0 ? { mentions } : {}),
      language: normalizeApiLanguage(language),
    }),
  });
  if (!response.ok || !response.body) {
    const body = await response.json().catch(() => ({}));
    const detail = (body as { detail?: unknown }).detail;
    const code = (body as { code?: unknown }).code;
    const message =
      typeof detail === "string"
        ? detail
        : typeof detail === "object" && detail !== null && "title" in detail
          ? String((detail as { title?: unknown }).title ?? "Chat stream failed")
          : "Chat stream failed";
    throw new ChatStreamError(
      message,
      response.status,
      typeof code === "string" ? code : "unknown",
    );
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let receivedDone = false;

  const dispatchParsedFrame = (part: string) => {
    const parsed = parseChatStreamFrame(part);
    if (!parsed) return;
    onEvent(parsed);
    if (parsed.event === "done" || parsed.event === "error") {
      receivedDone = true;
    }
  };

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() ?? "";
      for (const part of parts) {
        dispatchParsedFrame(part);
      }
    }

    buffer += decoder.decode();
    if (buffer.trim()) {
      dispatchParsedFrame(buffer);
    }
  } catch (err) {
    if (err instanceof ChatStreamError) {
      throw err;
    }
    throw new ChatStreamError(
      CHAT_STREAM_INTERRUPTED_MESSAGE,
      0,
      "stream_interrupted",
    );
  }

  if (!receivedDone) {
    throw new ChatStreamError(
      CHAT_STREAM_INTERRUPTED_MESSAGE,
      0,
      "stream_interrupted",
    );
  }
}

export function parseChatStreamFrame(part: string): ChatStreamEvent | null {
  const lines = part.split("\n");
  const eventLine = lines.find((line) => line.startsWith("event: "));
  const dataLine = lines.find((line) => line.startsWith("data: "));
  if (!dataLine) return null;

  const raw = dataLine.replace("data: ", "").trim();
  if (raw === "[DONE]") {
    return { event: "done", data: { message_id: null } };
  }

  const payload = JSON.parse(raw) as Record<string, unknown>;
  if (eventLine) {
    return {
      event: eventLine.replace("event: ", "") as ChatStreamEvent["event"],
      data: payload,
    } as ChatStreamEvent;
  }

  const type = payload.type;
  if (type === "stage_start") {
    return { event: "stage_start", data: { stage: String(payload.stage ?? "") } };
  }
  if (type === "stage_outcome") {
    return {
      event: "stage_outcome",
      data: { outcome: String(payload.outcome ?? "") },
    };
  }
  if (type === "token") {
    return {
      event: "token",
      data: { text: String(payload.content ?? payload.text ?? "") },
    };
  }
  if (type === "final") {
    return { event: "final", data: (payload.payload ?? {}) as ChatFinalPayload };
  }
  if (type === "title") {
    return {
      event: "title",
      data: {
        conversation_id: String(payload.conversation_id ?? ""),
        title: String(payload.title ?? ""),
      },
    };
  }
  if (type === "error") {
    return {
      event: "error",
      data: {
        code: typeof payload.code === "string" ? payload.code : undefined,
        detail: String(payload.message ?? payload.detail ?? "Chat stream failed"),
        message_id:
          typeof payload.message_id === "string" ? payload.message_id : undefined,
      },
    };
  }
  return null;
}

export async function searchDiscovery(
  kind: "assets" | "indicators",
  query: string,
  limit = 8,
) {
  const cacheKey = discoverySearchCacheKey(kind, query, limit);
  const now = Date.now();
  const cached = cachedDiscoverySearch(cacheKey, now);
  if (cached) return cached;

  const searchParams = new URLSearchParams({ q: query, limit: String(limit) });
  const promise = apiFetch<DiscoveryResponsePayload>(
    `/discovery/${kind}?${searchParams.toString()}`,
  ).catch((error) => {
    if (discoverySearchCache.get(cacheKey)?.promise === promise) {
      discoverySearchCache.delete(cacheKey);
    }
    throw error;
  });
  rememberDiscoverySearch(
    cacheKey,
    promise,
    now + DISCOVERY_SEARCH_CACHE_TTL_MS,
  );
  return promise;
}

export async function postFeedback(payload: {
  type: "bug" | "feature" | "general" | "account_deletion_request";
  message: string;
  context?: Record<string, unknown>;
}) {
  return apiFetch<{ success: boolean }>("/feedback", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
