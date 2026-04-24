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

export type BacktestRun = {
  id: string;
  conversation_id?: string | null;
  strategy_id?: string | null;
  status: "queued" | "running" | "completed" | "failed";
  asset_class: "equity" | "crypto";
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
  title_source: "system_default" | "ai_generated" | "user_renamed";
  pinned: boolean;
  archived: boolean;
  created_at: string;
  updated_at: string;
  last_message_preview?: string | null;
  language?: "en" | "es-419" | null;
};

export type ChatStreamEvent =
  | { event: "token"; data: { text: string } }
  | { event: "title"; data: { conversation_id: string; title: string } }
  | { event: "status"; data: { status: string } }
  | { event: "result"; data: { run: BacktestRun } }
  | { event: "done"; data: { message_id: string } };

const API_BASE = process.env.NEXT_PUBLIC_ARGUS_API_URL ?? "http://localhost:8000/api/v1";

export function resultCardFromRun(run: BacktestRun) {
  const card = run.conversation_result_card;
  return {
    strategyName: card.title,
    period: card.date_range.display,
    metrics: card.rows.map((row) => ({ label: row.label, value: row.value })),
    benchmarkNote: card.assumptions.join(" "),
  };
}

export async function createConversation(language: "en" | "es-419" = "en") {
  const response = await fetch(`${API_BASE}/conversations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title: null, language }),
  });
  if (!response.ok) {
    throw new Error("Failed to create conversation");
  }
  return (await response.json()) as { conversation: Conversation };
}

export async function listHistory() {
  const response = await fetch(`${API_BASE}/history`);
  if (!response.ok) {
    throw new Error("Failed to load history");
  }
  return (await response.json()) as {
    items: Array<{
      type: "chat" | "strategy" | "collection" | "run";
      id: string;
      title: string;
      subtitle: string;
      pinned: boolean;
      created_at: string;
    }>;
    next_cursor: string | null;
  };
}

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
      const eventLine = part.split("\n").find((line) => line.startsWith("event: "));
      const dataLine = part.split("\n").find((line) => line.startsWith("data: "));
      if (!eventLine || !dataLine) continue;
      onEvent({
        event: eventLine.replace("event: ", "") as ChatStreamEvent["event"],
        data: JSON.parse(dataLine.replace("data: ", "")),
      } as ChatStreamEvent);
    }
  }
}
