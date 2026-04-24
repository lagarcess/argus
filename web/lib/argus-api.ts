// ─── Shared primitive types ──────────────────────────────────────────────────

export type AssetClass = "equity" | "crypto";
export type BacktestStatus = "queued" | "running" | "completed" | "failed";
export type TitleSource = "system_default" | "ai_generated" | "user_renamed";
export type HistoryItemType = "chat" | "strategy" | "collection" | "run";

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
};

// ─── Chat stream event types ──────────────────────────────────────────────────

export type ChatStreamEvent =
  | { event: "token"; data: { text: string } }
  | { event: "title"; data: { conversation_id: string; title: string } }
  | { event: "status"; data: { status: string } }
  | { event: "result"; data: { run: BacktestRun } }
  | { event: "done"; data: { message_id: string } };

// ─── Config ───────────────────────────────────────────────────────────────────

const API_BASE =
  process.env.NEXT_PUBLIC_ARGUS_API_URL ?? "http://localhost:8000/api/v1";

// ─── Utilities ────────────────────────────────────────────────────────────────

export function resultCardFromRun(run: BacktestRun) {
  const card = run.conversation_result_card;
  return {
    strategyName: card.title,
    period: card.date_range.display,
    metrics: card.rows.map((row) => ({ label: row.label, value: row.value })),
    benchmarkNote: card.assumptions.join(" "),
    runId: run.id,
    strategyId: run.strategy_id ?? null,
  };
}

/**
 * Formats an ISO timestamp as a human-readable relative date string.
 * Returns "today", "yesterday", or a short locale date string.
 */
export function formatRelativeDate(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterdayStart = new Date(todayStart);
  yesterdayStart.setDate(yesterdayStart.getDate() - 1);

  if (date >= todayStart) return "today";
  if (date >= yesterdayStart) return "yesterday";
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: date.getFullYear() !== now.getFullYear() ? "numeric" : undefined,
  });
}

// ─── Generic fetch helper ─────────────────────────────────────────────────────

async function apiFetch<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = (body as any).detail;
    const errorMsg = typeof detail === 'object' && detail !== null 
      ? detail.title 
      : detail;

    const error = new Error(
      errorMsg ?? `API error ${response.status}`,
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
};

export async function patchMe(patch: ProfilePatch) {
  return apiFetch<{ user: any }>("/me", {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

// ─── Auth ─────────────────────────────────────────────────────────────────────

export async function createConversation(language: "en" | "es-419" = "en") {
  return apiFetch<{ conversation: Conversation }>("/conversations", {
    method: "POST",
    body: JSON.stringify({ title: null, language }),
  });
}

// ─── Conversations ────────────────────────────────────────────────────────────

export async function listConversations(limit = 20) {
  return apiFetch<{ items: Conversation[]; next_cursor: string | null }>(
    `/conversations?limit=${limit}`,
  );
}

export async function getConversationMessages(
  conversationId: string,
  limit = 50,
) {
  return apiFetch<{ items: ApiMessage[]; next_cursor: string | null }>(
    `/conversations/${conversationId}/messages?limit=${limit}`,
  );
}

export async function patchConversation(
  conversationId: string,
  patch: { title?: string; pinned?: boolean; archived?: boolean },
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

export async function listHistory(limit = 20) {
  return apiFetch<{ items: HistoryItem[]; next_cursor: string | null }>(
    `/history?limit=${limit}`,
  );
}

// ─── Strategies ───────────────────────────────────────────────────────────────

export async function listStrategies(limit = 50) {
  return apiFetch<{ items: Strategy[]; next_cursor: string | null }>(
    `/strategies?limit=${limit}`,
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

export async function listCollections(limit = 50) {
  return apiFetch<{ items: Collection[]; next_cursor: string | null }>(
    `/collections?limit=${limit}`,
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
  onEvent: (event: ChatStreamEvent) => void,
) {
  const response = await fetch(`${API_BASE}/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": crypto.randomUUID(),
    },
    body: JSON.stringify({
      conversation_id: conversationId,
      message,
      language: "en",
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
