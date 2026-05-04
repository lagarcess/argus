import { getSupabaseClient } from "./supabase-client";
import type { StrategyConfirmationPayload } from "@/components/chat/types";

// ─── Shared primitive types ──────────────────────────────────────────────────

export type AssetClass = "equity" | "crypto";
export type BacktestStatus = "queued" | "running" | "completed" | "failed";
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

export type ConversationResultCard = {
  title: string;
  date_range: {
    start: string;
    end: string;
    display: string;
  };
  status_label: string;
  rows: ApiMetricRow[];
  benchmark_note?: string;
  assumptions: string[];
  actions: Array<{ type: string; label: string }>;
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
  created_at: string;
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

/** Backend message shape (distinct from the frontend chat Message type) */
export type ApiMessage = {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  created_at: string;
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
  | { event: "confirmation"; data: { confirmation: StrategyConfirmationPayload } }
  | { event: "result"; data: { run: BacktestRun } }
  | { event: "error"; data: { detail: string } }
  | { event: "done"; data: { message_id: string } };

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

// ─── Utilities ────────────────────────────────────────────────────────────────

export function resultCardFromRun(run: BacktestRun) {
  const card = run.conversation_result_card;
  return {
    strategyName: card.title,
    period: card.date_range.display,
    statusLabel: card.status_label,
    metrics: card.rows.map((row) => ({ label: row.label, value: row.value })),
    benchmarkNote: card.benchmark_note,
    assumptions: card.assumptions,
    runId: run.id,
    strategyId: run.strategy_id ?? null,
    actions: card.actions,
  };
}

export function normalizeApiLanguage(language?: string | null): ApiLanguage {
  void language;
  return "en";
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

  console.log(`[argus-api] Fetching ${API_BASE}${path}`, options);
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...authHeaders, ...(options?.headers || {}) },
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

// ─── Profile ──────────────────────────────────────────────────────────────────

export type ProfilePatch = {
  language?: "en" | "es-419";
  locale?: string;
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
  return apiFetch<string[]>("/onboarding/starter-prompts");
}

// ─── Auth ─────────────────────────────────────────────────────────────────────

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

// ─── History ──────────────────────────────────────────────────────────────────

export async function listHistory(params: { limit?: number; cursor?: string; deleted?: boolean } = {}) {
  const { limit = 20, cursor, deleted } = params;
  const searchParams = new URLSearchParams({ limit: String(limit) });
  if (cursor) searchParams.append("cursor", cursor);
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

// ─── Chat stream ──────────────────────────────────────────────────────────────

export async function streamChatMessage(
  conversationId: string,
  message: string,
  language: string | null | undefined,
  onEvent: (event: ChatStreamEvent) => void,
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
      message,
      language: normalizeApiLanguage(language),
    }),
  });
  if (!response.ok || !response.body) {
    throw new Error("Chat stream failed");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const part of parts) {
      const eventLine = part
        .split("\n")
        .find((line) => line.startsWith("event: "));
      const dataLine = part
        .split("\n")
        .find((line) => line.startsWith("data: "));
      if (!eventLine || !dataLine) continue;
      onEvent({
        event: eventLine.replace("event: ", "") as ChatStreamEvent["event"],
        data: JSON.parse(dataLine.replace("data: ", "")),
      } as ChatStreamEvent);
    }
  }
}

export async function postFeedback(payload: {
  type: "bug" | "feature" | "general";
  message: string;
  context?: Record<string, unknown>;
}) {
  return apiFetch<{ success: boolean }>("/feedback", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
