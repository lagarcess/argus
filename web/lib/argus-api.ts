import { getSupabaseClient } from "./supabase-client";
import type { AssetClass } from "./argus-types";
import type { SearchConversationItem as SearchConversationContract } from "./search-contract";
import type { DecisionState as RunDossierDecisionState } from "./run-dossier-contract";
import type {
  ChatActionOption,
  ChatMention,
  ExecutionCostEvidence,
  StrategyConfirmationPayload,
} from "@/components/chat/types";
import {
  normalizeEnabledLanguage,
  type ArgusLocale,
} from "./language-features";
import { isConversationMemoryOptOut } from "./memory-privacy";
import { runActionIdempotencyKey } from "./usage-allowance";
import type { UsageAllowanceResponse } from "./usage-allowance";
import type { AvatarTheme } from "./avatar-theme";
import type { GuestPendingActionSummary } from "./guest-conversion";
import {
  displayResultActionLabel,
  displayResultBenchmarkNote,
  displayResultMetricLabel,
  resultMetricDisplayOrder,
} from "./result-card-display";
import { acquirePasswordAuthCaptchaToken } from "./guest-captcha";
import {
  ARGUS_API_BASE_URL,
  apiFetch,
  unauthenticatedApiFetch,
} from "./argus-api-transport";

export { apiFetch, unauthenticatedApiFetch } from "./argus-api-transport";

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
export type ConversationOperationStatus =
  | "idle"
  | "queued"
  | "running"
  | "checking";
export type ConversationOperationKind = "chat_turn" | "backtest_job" | null;
export type ConversationOperation = {
  status: ConversationOperationStatus;
  kind?: ConversationOperationKind;
  updated_at?: string | null;
};
export type ConversationAttentionStatus =
  | "none"
  | "new_activity"
  | "manual_unread"
  | "needs_input"
  | "needs_attention";
export type ConversationAttention = {
  status: ConversationAttentionStatus;
  cursor?: string | null;
};
export type ConversationActivity = {
  operation: ConversationOperation;
  attention: ConversationAttention;
};
export type ConversationActivityPatch =
  | { action: "mark_unread" }
  | { action: "mark_read"; through_attention_cursor?: string | null };

// ─── Metric / result card types ──────────────────────────────────────────────

export type ApiMetricRow = {
  key: string;
  label: string;
  value: string;
};

export type ResultChartExplorationPolicy = {
  minimum_visible_observations?: number;
  minimum_meaningful_duration?: string | null;
};

export type ResultChartMarkerSummary = {
  total_groups: number;
  included_groups: number;
  sampled: boolean;
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
  value_summary?: {
    peak_value?: number | null;
    lowest_value?: number | null;
    currency?: string | null;
    source?: "strategy_portfolio_equity_close" | string;
  } | null;
  value_extrema?: {
    peak?: { time: string; value: number } | null;
    lowest?: { time: string; value: number } | null;
  } | null;
  exploration_policy?: ResultChartExplorationPolicy | null;
  marker_summary?: ResultChartMarkerSummary | null;
  attribution?: string;
};

export type ConversationResultCard = {
  title: string;
  symbols?: string[];
  strategy_label?: string;
  asset_class?: AssetClass | null;
  idea_id?: string | null;
  idea_version_id?: string | null;
  evidence_artifact_id?: string | null;
  evidence_lifecycle?: ArtifactLifecycle | null;
  artifact_type?: "backtest" | string | null;
  decision_note_id?: string | null;
  decision_state?: DecisionState | null;
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
  execution_costs?: ExecutionCostEvidence | null;
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
  next_experiments?: Record<string, unknown> | null;
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
  activity?: ConversationActivity | null;
};

type AuthSessionPayload = {
  access_token?: string;
  refresh_token?: string;
  expires_in?: number;
};

export type AuthResponsePayload = {
  session?: AuthSessionPayload | null;
  user?: Record<string, unknown> | null;
  guest_claim?: { conversation_id: string; pending_action: GuestPendingActionSummary | null } | null;
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

type HistoryItemBase = {
  type: HistoryItemType;
  id: string;
  title: string;
  /** Present on chat items; retained as optional for existing history consumers. */
  title_source?: TitleSource | null;
  subtitle: string;
  pinned: boolean;
  created_at: string;
  conversation_id?: string | null;
  expires_at?: string | null;
};

export type ChatHistoryItem = HistoryItemBase & {
  type: "chat";
  activity?: ConversationActivity | null;
};

export type NonChatHistoryItem = HistoryItemBase & {
  type: Exclude<HistoryItemType, "chat">;
  activity?: never;
};

export type HistoryItem = ChatHistoryItem | NonChatHistoryItem;

export type ArtifactLifecycle =
  | "captured"
  | "reviewed"
  | "saved"
  | "decided"
  | "archived"
  | "discarded";

export type DecisionState = RunDossierDecisionState;

export type EvidenceArtifact = {
  id: string;
  idea_id: string;
  idea_version_id: string;
  source_conversation_id?: string | null;
  source_run_id?: string | null;
  artifact_type: "backtest";
  lifecycle: ArtifactLifecycle;
  title: string;
  digest: string;
  payload: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type DecisionNote = {
  id: string;
  idea_id: string;
  idea_version_id: string;
  evidence_artifact_id: string;
  source_conversation_id?: string | null;
  decision_state: DecisionState;
  note?: string | null;
  created_at: string;
  updated_at: string;
};

export type SearchConversationItem = SearchConversationContract;

export type SearchAssetRollupItem = {
  type: "asset_rollup";
  symbol: string;
  run_count: number;
  decision_counts: Record<DecisionState, number>;
  last_touched_at: string;
};

export type SearchItem = SearchConversationItem | SearchAssetRollupItem;

export type SearchLedgerGroup = {
  decision_state: DecisionState;
  count: number;
};

export type SearchResponse = {
  items: SearchItem[];
  next_cursor: string | null;
  ledger_groups?: SearchLedgerGroup[] | null;
};

// ─── Chat stream event types ──────────────────────────────────────────────────

export type ChatStreamEvent =
  | { event: "token"; data: { text: string } }
  | { event: "title"; data: { conversation_id: string; title: string } }
  | { event: "status"; data: { status: string } }
  | { event: "stage_start"; data: { stage: string; detail?: string } }
  | { event: "stage_outcome"; data: { outcome: string } }
  | { event: "final"; data: ChatFinalPayload }
  | {
      event: "confirmation";
      data: { confirmation: StrategyConfirmationPayload };
    }
  | { event: "result"; data: { run: BacktestRun } }
  | {
      event: "error";
      data: {
        code?: string;
        detail: string;
        message_id?: string;
        recovery?: Record<string, unknown>;
        retry_last_turn?: Record<string, unknown>;
      };
    }
  | { event: "done"; data: { message_id: string | null } };

export type ChatFinalPayload = {
  code?: string;
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
  recovery?: Record<string, unknown> | null;
  retry_last_turn?: Record<string, unknown> | null;
};

export type ChatActionRequest = {
  type: NonNullable<ChatActionOption["type"]>;
  label?: string;
  labelKey?: string;
  payload?: Record<string, unknown>;
  presentation?: "confirmation" | "result";
};

export class ChatStreamError extends Error {
  constructor(
    message: string,
    public status: number,
    public code = "unknown",
    public requestId: string | null = null,
  ) {
    super(message);
    this.name = "ChatStreamError";
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
  // Optional: provider-backed discovery items carry it (the picker filters indicators
  // to "supported"); composer tokens reconstructed from the DOM do not need it.
  support_status?: "supported" | "draft_only" | "unavailable";
};

type DiscoveryResponsePayload = { items: DiscoveryItem[] };

// ─── Config ───────────────────────────────────────────────────────────────────

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
    evidenceArtifactId: card.evidence_artifact_id ?? null,
    evidenceLifecycle: card.evidence_lifecycle ?? null,
    decisionNoteId: card.decision_note_id ?? null,
    decisionState: card.decision_state ?? null,
    actions: card.actions.map((action) => ({
      ...action,
      label: displayResultActionLabel(action),
    })),
    chart: card.chart ?? null,
    executionCosts: card.execution_costs ?? null,
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

export async function persistBrowserSession(payload: AuthResponsePayload) {
  const session = payload.session;
  if (!session?.access_token || !session.refresh_token) {
    return;
  }
  const supabase = getSupabaseClient();
  if (!supabase) {
    return;
  }
  const { error } = await supabase.auth.setSession({
    access_token: session.access_token,
    refresh_token: session.refresh_token,
  });
  if (error) {
    throw error;
  }
}

// ─── Profile ──────────────────────────────────────────────────────────────────

export type ProfilePatch = {
  language?: "en" | "es-419";
  locale?: ArgusLocale;
  theme?: string;
  display_name?: string;
  avatar_theme?: AvatarTheme;
};

export async function getMe() {
  return apiFetch<UserResponse>("/me");
}

export async function getUsageAllowances() {
  return apiFetch<UsageAllowanceResponse>("/me/usage");
}

export async function patchMe(patch: ProfilePatch) {
  return apiFetch<UserResponse>("/me", {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export async function getStarterPrompts() {
  const response = await apiFetch<{ prompts: string[] }>(
    "/chat/starter-prompts",
  );
  return response.prompts;
}

// ─── Auth ─────────────────────────────────────────────────────────────────────

export async function signupWithEmail(payload: {
  email: string;
  password: string;
  language: ApiLanguage;
  display_name?: string | null;
  username?: string | null;
}) {
  const captchaToken = await acquirePasswordAuthCaptchaToken();
  const response = await unauthenticatedApiFetch<AuthResponsePayload>(
    "/auth/signup",
    {
      method: "POST",
      body: JSON.stringify({ ...payload, captcha_token: captchaToken }),
    },
  );
  await persistBrowserSession(response);
  return { response, needsEmailConfirmation: !response.session };
}

export async function loginWithEmail(payload: {
  email: string;
  password: string;
}) {
  const captchaToken = await acquirePasswordAuthCaptchaToken();
  const response = await unauthenticatedApiFetch<AuthResponsePayload>(
    "/auth/login",
    {
      method: "POST",
      body: JSON.stringify({ ...payload, captcha_token: captchaToken }),
    },
  );
  await persistBrowserSession(response);
  return response;
}

export async function clearArgusSessionCookies() {
  return unauthenticatedApiFetch<{ success: boolean }>("/auth/logout", {
    method: "POST",
  });
}

export type CurrentBrowserLogoutResult = {
  revocation: "complete" | "failed";
  cookieSync: "cleared" | "failed";
};

export async function synchronizeCurrentBrowserLogout<T>(
  revokeCurrentSession: () => Promise<{ error: unknown | null }>,
  clearCookies: () => Promise<T>,
): Promise<CurrentBrowserLogoutResult> {
  const [revocation, cookieSync] = await Promise.allSettled([
    Promise.resolve().then(revokeCurrentSession),
    Promise.resolve().then(clearCookies),
  ]);
  return {
    revocation:
      revocation.status === "fulfilled" && !revocation.value.error
        ? "complete"
        : "failed",
    cookieSync: cookieSync.status === "fulfilled" ? "cleared" : "failed",
  };
}

export async function logoutFromApi() {
  return synchronizeCurrentBrowserLogout(
    async () => {
      const supabase = getSupabaseClient();
      if (!supabase) return { error: null };
      return supabase.auth.signOut({ scope: "local" });
    },
    clearArgusSessionCookies,
  );
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

export async function listConversations(
  params: {
    limit?: number;
    cursor?: string;
    archived?: boolean;
    deleted?: boolean;
  } = {},
) {
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
  options: Readonly<{
    signal?: AbortSignal;
    anchorMessageId?: string;
  }> = {},
) {
  const searchParams = new URLSearchParams({ limit: String(limit) });
  if (cursor) searchParams.append("cursor", cursor);
  if (options.anchorMessageId) {
    searchParams.append("anchor_message_id", options.anchorMessageId);
  }
  return apiFetch<{ items: ApiMessage[]; next_cursor: string | null }>(
    `/conversations/${conversationId}/messages?${searchParams.toString()}`,
    { signal: options.signal },
  );
}

export async function patchConversation(
  conversationId: string,
  patch: {
    title?: string;
    pinned?: boolean;
    archived?: boolean;
    deleted_at?: string | null;
  },
) {
  return apiFetch<{ conversation: Conversation }>(
    `/conversations/${conversationId}`,
    { method: "PATCH", body: JSON.stringify(patch) },
  );
}

export async function getConversationActivity(conversationId: string) {
  return apiFetch<ConversationActivity>(
    `/conversations/${conversationId}/activity`,
  );
}

export async function patchConversationActivity(
  conversationId: string,
  patch: ConversationActivityPatch,
  options: Readonly<{ signal?: AbortSignal }> = {},
) {
  return apiFetch<ConversationActivity>(
    `/conversations/${conversationId}/activity`,
    {
      method: "PATCH",
      body: JSON.stringify(patch),
      signal: options.signal,
    },
  );
}

export async function deleteConversation(conversationId: string) {
  return apiFetch<{ success: boolean }>(`/conversations/${conversationId}`, {
    method: "DELETE",
  });
}

export async function deleteAllConversations() {
  return apiFetch<{ success: boolean; deleted_count: number }>(
    "/conversations",
    {
      method: "DELETE",
    },
  );
}

// ─── History ──────────────────────────────────────────────────────────────────

export async function listHistory(
  params: {
    limit?: number;
    cursor?: string;
    archived?: boolean;
    deleted?: boolean;
  } = {},
) {
  const { limit = 20, cursor, archived, deleted } = params;
  const searchParams = new URLSearchParams({ limit: String(limit) });
  if (cursor) searchParams.append("cursor", cursor);
  if (archived !== undefined) searchParams.append("archived", String(archived));
  if (deleted !== undefined) searchParams.append("deleted", String(deleted));

  return apiFetch<{ items: HistoryItem[]; next_cursor: string | null }>(
    `/history?${searchParams.toString()}`,
  );
}

export async function searchGlobal(params: {
  q: string;
  limit?: number;
  cursor?: string;
  decisionState?: DecisionState | null;
  includeLedgerGroups?: boolean;
  conversationIds?: string[];
}) {
  const {
    q,
    limit = 20,
    cursor,
    decisionState,
    includeLedgerGroups = false,
    conversationIds,
  } = params;
  const searchParams = new URLSearchParams({
    q,
    limit: String(limit),
  });
  if (cursor) searchParams.append("cursor", cursor);
  if (decisionState) searchParams.append("decision_state", decisionState);
  if (includeLedgerGroups) {
    searchParams.append("include_ledger_groups", "true");
  }
  for (const id of conversationIds ?? [])
    searchParams.append("conversation_id", id);
  return apiFetch<SearchResponse>(
    `/search?${searchParams.toString()}`,
  );
}

export async function createEvidenceDecision(
  artifactId: string,
  payload: { decision_state: DecisionState; note?: string | null },
) {
  return apiFetch<{
    decision: DecisionNote;
    evidence_artifact: EvidenceArtifact;
  }>(`/evidence-artifacts/${artifactId}/decision`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
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

export type ChatStreamOptions = Readonly<{
  requestId?: string;
  signal?: AbortSignal;
}>;

export async function streamChatMessage(
  conversationId: string,
  input: string | ChatActionRequest,
  language: string | null | undefined,
  onEvent: (event: ChatStreamEvent) => void,
  mentions: ChatMention[] = [],
  options: ChatStreamOptions = {},
) {
  const isMockAuth = process.env.NEXT_PUBLIC_MOCK_AUTH === "true";
  const authHeaders: Record<string, string> = {};
  const submittedRequestId = options.requestId ?? crypto.randomUUID();
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

  const response = await fetch(`${ARGUS_API_BASE_URL}/chat/stream`, {
    method: "POST",
    credentials: "include",
    signal: options.signal,
    headers: {
      "Content-Type": "application/json",
      "X-Request-Id": submittedRequestId,
      "Idempotency-Key":
        (typeof input !== "string" && runActionIdempotencyKey(input)) ||
        crypto.randomUUID(),
      ...authHeaders,
    },
    body: JSON.stringify({
      conversation_id: conversationId,
      ...(typeof input === "string" ? { message: input } : { action: input }),
      // Callers decide which turns carry mentions; this layer only forwards
      // them. Gating on a string input silently dropped the resolver identity
      // that a discovery selection attaches to its action turn.
      ...(mentions.length > 0 ? { mentions } : {}),
      language: normalizeApiLanguage(language),
      // Temporary chat: only ever narrows behavior, so the transport layer
      // owns it and ordinary conversations send an unchanged body.
      ...(isConversationMemoryOptOut(conversationId)
        ? { memory_opt_out: true }
        : {}),
    }),
  }).catch(() => { throw new ChatStreamError(CHAT_STREAM_INTERRUPTED_MESSAGE, 0, "stream_interrupted", submittedRequestId); });
  const responseRequestId = response.headers.get("X-Request-Id")?.trim() || submittedRequestId;
  if (!response.ok || !response.body) {
    const body = await response.json().catch(() => ({}));
    const detail = (body as { detail?: unknown }).detail;
    const code = (body as { code?: unknown }).code;
    const message =
      typeof detail === "string"
        ? detail
        : typeof detail === "object" && detail !== null && "title" in detail
          ? String(
              (detail as { title?: unknown }).title ?? "Chat stream failed",
            )
          : "Chat stream failed";
    throw new ChatStreamError(
      message,
      response.status,
      typeof code === "string" ? code : "unknown", responseRequestId,
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
      responseRequestId,
    );
  }

  if (!receivedDone) {
    throw new ChatStreamError(
      CHAT_STREAM_INTERRUPTED_MESSAGE,
      0,
      "stream_interrupted", responseRequestId,
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
    return {
      event: "stage_start",
      data: {
        stage: String(payload.stage ?? ""),
        ...(typeof payload.detail === "string" && payload.detail
          ? { detail: payload.detail }
          : {}),
      },
    };
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
    return {
      event: "final",
      data: (payload.payload ?? {}) as ChatFinalPayload,
    };
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
        detail: String(
          payload.message ?? payload.detail ?? "Chat stream failed",
        ),
        message_id:
          typeof payload.message_id === "string"
            ? payload.message_id
            : undefined,
        recovery: recordFromPayload(payload.recovery),
        retry_last_turn: recordFromPayload(payload.retry_last_turn),
      },
    };
  }
  return null;
}

function recordFromPayload(
  value: unknown,
): Record<string, unknown> | undefined {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return undefined;
  }
  return value as Record<string, unknown>;
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
import type { UserResponse } from "./guest-account";

export type {
  AccountCapabilities,
  ApiUser,
  GuestAccountSummary,
  UserResponse,
} from "./guest-account";
