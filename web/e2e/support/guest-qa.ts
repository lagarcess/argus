import { createHash, randomBytes, randomUUID } from "node:crypto";
import { execFileSync, spawn, type ChildProcess } from "node:child_process";
import {
  chmodSync,
  mkdirSync,
  renameSync,
  writeFileSync,
} from "node:fs";
import path from "node:path";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import {
  expect,
  type APIRequestContext,
  type BrowserContext,
  type Page,
} from "@playwright/test";

export const REPOSITORY_ROOT = path.resolve(__dirname, "../../..");
export const LOCAL_APP_ORIGIN = "http://localhost:3000";
export const LOCAL_API_ORIGIN = "http://localhost:8000";
export const LOCAL_API_BASE = `${LOCAL_API_ORIGIN}/api/v1`;
const LOCAL_DB_CONTAINER = "supabase_db_argus-qa";
const UUID_PATTERN =
  /\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b/gi;
const JWT_PATTERN = /\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b/g;
const EMAIL_PATTERN = /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi;

export const GUEST_ACCEPTANCE_CHECKS = [
  { number: 1, title: "Public entry opens chat without login" },
  { number: 2, title: "English and Spanish guest chrome is complete" },
  { number: 3, title: "Starter chip uses ordinary chat" },
  { number: 4, title: "Clarification and confirmation preserve the idea" },
  { number: 5, title: "One simulation completes in the ordinary result card" },
  { number: 6, title: "Chart switching creates zero writes" },
  { number: 7, title: "UI API and Postgres usage agree" },
  { number: 8, title: "Reload restores the exact conversation and result" },
  { number: 9, title: "Recents restores the temporary conversation and expiry" },
  { number: 10, title: "Omnisearch is owner scoped and honest" },
  { number: 11, title: "Second simulation converts before admission" },
  { number: 12, title: "Add decision preserves typed action identity" },
  { number: 13, title: "New chat choices match account-access mode" },
  { number: 14, title: "Canceling authentication loses nothing" },
  { number: 15, title: "New account conversion preserves UUID and resumes once" },
  { number: 16, title: "Existing account claim is atomic and lossless" },
  { number: 17, title: "Guest feedback is private and allowance neutral" },
  { number: 18, title: "Interrupted turn charges nothing and recovers" },
  { number: 19, title: "Expiry and cleanup are bounded and safe" },
  { number: 20, title: "Global browser ownership and secret safety hold" },
] as const;

export type GuestCheckNumber =
  (typeof GUEST_ACCEPTANCE_CHECKS)[number]["number"];

export type PersistedMessageItem = {
  id: string;
  conversation_id: string;
  role: string;
  content: string;
  metadata?: Record<string, unknown>;
};

export type ConfirmationDateRange = {
  start: string;
  end: string;
};

export type ConfirmationFacts = {
  messageId: string;
  confirmationId: string;
  assetUniverse: string[];
  benchmark: string;
  requestedDateRange: ConfirmationDateRange;
  effectiveDateRange: ConfirmationDateRange;
};

export type ConfirmationContinuityChecks = {
  updateMessagePersisted: boolean;
  assetUniverseExactlyMsft: boolean;
  benchmarkExactlySpy: boolean;
  requestedDateRangeUnchanged: boolean;
  effectiveDateRangeUnchanged: boolean;
};

export type ResultFacts = {
  messageId: string;
  runId: string;
  evidenceId: string;
};

export type ResultTruthFingerprint = {
  rows: number;
  fingerprint: string;
};

export const CONFIRMATION_CONTINUITY_ASSERTION_MESSAGES = {
  updateMessagePersisted:
    "The exact Check 4 update message was not durably persisted as a user message",
  assetUniverseExactlyMsft:
    'The refined confirmation asset universe must be exactly ["MSFT"]',
  benchmarkExactlySpy:
    "The refined confirmation typed benchmark must remain exactly SPY",
  requestedDateRangeUnchanged:
    "The refined confirmation requested date range must match the initial request",
  effectiveDateRangeUnchanged:
    "The refined confirmation effective canonical date range must remain unchanged",
} satisfies Record<keyof ConfirmationContinuityChecks, string>;

export type BrowserSafetyPhase = "product" | "teardown";

export type BrowserSafetyContext = {
  check: GuestCheckNumber | null;
  phase: BrowserSafetyPhase;
};

export type BrowserSafetyDetail = {
  event: "console_error" | "page_error" | "failed_request";
  component: "browser_console" | "browser_page" | "network";
  endpoint: string | null;
  status: number | null;
  category: string;
  check: GuestCheckNumber | null;
  phase: BrowserSafetyPhase;
};

type SafeConfirmationEvidence = {
  message_label: string;
  confirmation_label: string;
  asset_universe: string[];
  benchmark: string;
  requested_date_range: ConfirmationDateRange;
  effective_date_range: ConfirmationDateRange;
};

export type GuestMe = {
  account_kind: "guest" | "registered";
  public_account_access_enabled: boolean;
  user: {
    id: string;
    email: string | null;
    language: "en" | "es-419";
  };
  guest: {
    expires_at: string;
    message_limit: number;
    simulation_limit: number;
    feedback_limit: number;
  } | null;
};

export type UsageWindow = {
  used: number;
  limit: number;
  remaining: number;
  period_end: string;
};

export type GuestUsage = {
  allowances: {
    messages: {
      hour: null;
      day: null;
      guest_session: UsageWindow;
      available_now: boolean;
      limiting_window: "guest_session";
    };
    backtests: {
      hour: null;
      day: null;
      guest_session: UsageWindow;
      available_now: boolean;
      limiting_window: "guest_session";
    };
  };
};

export type OwnerSnapshot = {
  conversations: number;
  messages: number;
  user_messages: number;
  assistant_messages: number;
  jobs: number;
  succeeded_jobs: number;
  runs: number;
  completed_runs: number;
  ideas: number;
  idea_versions: number;
  evidence: number;
  decisions: number;
  feedback: number;
  chat_units: number;
  simulation_units: number;
  feedback_units: number;
  cost_rows: number;
  provider_cost_usd: number;
  provider_latency_ms: number;
  expires_at: string | null;
};

export type ConversationGraph = {
  conversation: string[];
  messages: string[];
  strategies: string[];
  jobs: string[];
  runs: string[];
  ideas: string[];
  idea_versions: string[];
  evidence: string[];
  decisions: string[];
  context_packets: string[];
  run_context_packets: string[];
  checkpoints: string[];
};

export type ZeroStateSnapshot = {
  auth_users: number;
  profiles: number;
  disposable_allowlist_rows: number;
  queued_jobs: number;
  running_jobs: number;
  usage_counters: number;
  product_rows: number;
};

export type SafeEvidence = {
  candidate_sha: string;
  status: "passed" | "failed";
  completed_checks: number[];
  failure_check: number | null;
  flags_restored_false: boolean;
  fresh_context_verified: boolean;
  owner_labels: string[];
  conversation_labels: string[];
  artifact_labels: string[];
  check4_initial_confirmation: SafeConfirmationEvidence | null;
  check4_refined_confirmation: SafeConfirmationEvidence | null;
  simulation_usage_matches: boolean;
  same_uuid_conversion: boolean;
  new_account_resume_count: number;
  existing_claim_owner_changed: boolean;
  existing_claim_duplicate_count: number;
  existing_claim_resume_count: number;
  feedback_rows_added: number;
  feedback_email_present: boolean;
  feedback_transcript_present: boolean;
  interrupted_usage_delta: number;
  cleanup_deleted_count: number;
  cleanup_permanent_control_preserved: boolean;
  cross_owner_result_count: number;
  console_error_count: number;
  page_error_count: number;
  failed_request_count: number;
  browser_safety_details: BrowserSafetyDetail[];
  teardown_console_error_count: number;
  teardown_page_error_count: number;
  teardown_failed_request_count: number;
  teardown_hosted_write_count: number;
  teardown_credential_exposure_count: number;
  hosted_write_count: number;
  server_product_analytics_disabled: boolean;
  credential_exposure_count: number;
  provider_cost_usd: number;
  provider_latency_ms: number;
  normalized_mutation_counts: Record<string, number>;
  teardown_clean: boolean;
};

function recordOrEmpty(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function requiredDateRange(
  value: unknown,
  field: string,
): ConfirmationDateRange {
  const record = recordOrEmpty(value);
  if (
    typeof record.start !== "string" ||
    record.start === "" ||
    typeof record.end !== "string" ||
    record.end === ""
  ) {
    throw new Error(`Canonical confirmation is missing typed ${field}`);
  }
  return { start: record.start, end: record.end };
}

export function latestConfirmationFacts(
  items: PersistedMessageItem[],
): ConfirmationFacts {
  for (const item of [...items].reverse()) {
    const metadata = recordOrEmpty(item.metadata);
    const payload = recordOrEmpty(metadata.confirmation_payload);
    const strategy = recordOrEmpty(payload.strategy);
    if (Object.keys(strategy).length === 0) continue;
    const launch = recordOrEmpty(payload.launch_payload);
    const card = recordOrEmpty(metadata.confirmation_card);
    const confirmationId = card.confirmation_id;
    if (typeof confirmationId !== "string" || confirmationId === "") {
      throw new Error(
        "Canonical confirmation is missing a typed confirmation id",
      );
    }
    const benchmark = launch.benchmark_symbol;
    if (typeof benchmark !== "string" || benchmark === "") {
      throw new Error("Canonical confirmation is missing a typed benchmark");
    }
    const assetUniverse = Array.isArray(strategy.asset_universe)
      ? strategy.asset_universe.filter(
          (value): value is string => typeof value === "string",
        )
      : [];
    return {
      messageId: item.id,
      confirmationId,
      assetUniverse,
      benchmark,
      requestedDateRange: requiredDateRange(
        launch.requested_date_range,
        "requested date range",
      ),
      effectiveDateRange: requiredDateRange(
        strategy.date_range,
        "effective canonical date range",
      ),
    };
  }
  throw new Error("A canonical confirmation artifact was not persisted");
}

export function distinctConfirmationFacts(
  items: PersistedMessageItem[],
  initial: Pick<ConfirmationFacts, "messageId" | "confirmationId">,
): ConfirmationFacts | null {
  const latest = latestConfirmationFacts(items);
  if (
    latest.messageId === initial.messageId ||
    latest.confirmationId === initial.confirmationId
  ) {
    return null;
  }
  return latest;
}

function sameDateRange(
  left: ConfirmationDateRange,
  right: ConfirmationDateRange,
): boolean {
  return left.start === right.start && left.end === right.end;
}

export function confirmationContinuityChecks(
  initial: ConfirmationFacts,
  refined: ConfirmationFacts,
  items: PersistedMessageItem[],
  updateMessage: string,
): ConfirmationContinuityChecks {
  return {
    updateMessagePersisted: items.some(
      (item) => item.role === "user" && item.content === updateMessage,
    ),
    assetUniverseExactlyMsft:
      refined.assetUniverse.length === 1 &&
      refined.assetUniverse[0] === "MSFT",
    benchmarkExactlySpy: refined.benchmark === "SPY",
    requestedDateRangeUnchanged: sameDateRange(
      refined.requestedDateRange,
      initial.requestedDateRange,
    ),
    effectiveDateRangeUnchanged: sameDateRange(
      refined.effectiveDateRange,
      initial.effectiveDateRange,
    ),
  };
}

export function latestResultFacts(
  items: PersistedMessageItem[],
): ResultFacts {
  for (const item of [...items].reverse()) {
    const metadata = recordOrEmpty(item.metadata);
    if (!Object.hasOwn(metadata, "result_card")) continue;
    const resultCard = recordOrEmpty(metadata.result_card);
    const runId = metadata.result_run_id;
    const evidenceId =
      resultCard.evidenceArtifactId ?? resultCard.evidence_artifact_id;
    if (
      typeof runId !== "string" ||
      runId === "" ||
      typeof evidenceId !== "string" ||
      evidenceId === ""
    ) {
      throw new Error("Canonical result is missing typed result identities");
    }
    return {
      messageId: item.id,
      runId,
      evidenceId,
    };
  }
  throw new Error("A canonical typed result artifact was not persisted");
}

export function binaryEvidenceDiffers(
  before: Uint8Array,
  after: Uint8Array,
): boolean {
  if (before.length !== after.length) return true;
  return before.some((value, index) => value !== after[index]);
}

export function resultTruthStayedStable(
  before: ResultTruthFingerprint,
  after: ResultTruthFingerprint,
): boolean {
  return (
    before.rows > 0 &&
    before.rows === after.rows &&
    before.fingerprint !== "" &&
    before.fingerprint === after.fingerprint
  );
}

type DisposableIdentity = {
  userId: string;
  email: string;
  password: string;
};

function requireUuid(value: string, label: string): string {
  if (
    !/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
      value,
    )
  ) {
    throw new Error(`${label} is not a UUID`);
  }
  return value;
}

function requireCandidateSha(): string {
  const candidate = process.env.ARGUS_CANDIDATE_SHA?.trim() ?? "";
  if (!/^[0-9a-f]{40}$/.test(candidate)) {
    throw new Error("ARGUS_CANDIDATE_SHA must be an exact 40-character SHA");
  }
  return candidate;
}

function localUrl(value: string | undefined, label: string): URL {
  if (!value) throw new Error(`${label} is required`);
  const parsed = new URL(value);
  if (
    !["http:", "postgresql:", "postgres:"].includes(parsed.protocol) ||
    !["localhost", "127.0.0.1"].includes(parsed.hostname)
  ) {
    throw new Error(`${label} must target loopback`);
  }
  return parsed;
}

export function assertExactLocalCandidate(): void {
  if (process.env.ARGUS_QA_APPROVED_SUPABASE_REF) {
    throw new Error("Hosted Supabase approval is forbidden for guest browser QA");
  }
  const candidate = requireCandidateSha();
  const head = execFileSync("git", ["rev-parse", "HEAD"], {
    cwd: REPOSITORY_ROOT,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "ignore"],
  }).trim();
  const root = execFileSync("git", ["rev-parse", "--show-toplevel"], {
    cwd: REPOSITORY_ROOT,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "ignore"],
  }).trim();
  const branch = execFileSync("git", ["branch", "--show-current"], {
    cwd: REPOSITORY_ROOT,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "ignore"],
  }).trim();
  const status = execFileSync("git", ["status", "--porcelain"], {
    cwd: REPOSITORY_ROOT,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "ignore"],
  }).trim();
  if (root !== REPOSITORY_ROOT) throw new Error("Wrong guest QA worktree");
  if (head !== candidate) throw new Error("Candidate SHA does not match HEAD");
  if (branch !== "codex/guest-experience") {
    throw new Error("Guest QA must run from codex/guest-experience");
  }
  if (status && process.env.ARGUS_GUEST_QA_ALLOW_TEST_DIFF !== "true") {
    throw new Error("Guest QA worktree must be clean");
  }

  localUrl(process.env.NEXT_PUBLIC_SUPABASE_URL, "NEXT_PUBLIC_SUPABASE_URL");
  localUrl(process.env.SUPABASE_PROJECT_URL, "SUPABASE_PROJECT_URL");
  localUrl(process.env.DATABASE_URL, "DATABASE_URL");
  const app = localUrl(
    process.env.PLAYWRIGHT_BASE_URL ?? LOCAL_APP_ORIGIN,
    "PLAYWRIGHT_BASE_URL",
  );
  const api = localUrl(
    process.env.NEXT_PUBLIC_ARGUS_API_URL ?? LOCAL_API_BASE,
    "NEXT_PUBLIC_ARGUS_API_URL",
  );
  if (app.origin !== LOCAL_APP_ORIGIN) {
    throw new Error("Guest QA app origin must be http://localhost:3000");
  }
  if (`${api.origin}${api.pathname.replace(/\/$/, "")}` !== LOCAL_API_BASE) {
    throw new Error("Guest QA API must be http://localhost:8000/api/v1");
  }
  if (process.env.NEXT_PUBLIC_MOCK_AUTH !== "false") {
    throw new Error("Guest QA requires real browser Auth");
  }
  if (process.env.ARGUS_MOCK_AUTH !== "false") {
    throw new Error("Guest QA requires real backend Auth");
  }
  if (process.env.ARGUS_GUEST_ACCESS_ENABLED !== "true") {
    throw new Error("Guest QA requires the process-only server guest flag");
  }
  if (process.env.NEXT_PUBLIC_GUEST_ACCESS_ENABLED !== "true") {
    throw new Error("Guest QA requires the process-only frontend guest flag");
  }
  for (const key of [
    "POSTHOG_PROJECT_TOKEN",
    "POSTHOG_REGION",
    "POSTHOG_HOST",
  ]) {
    if (process.env[key]?.trim()) {
      throw new Error("Guest QA requires server product analytics disabled");
    }
  }
}

function psqlJson<T>(sql: string): T {
  try {
    const output = execFileSync(
      "docker",
      [
        "exec",
        "-i",
        LOCAL_DB_CONTAINER,
        "psql",
        "-U",
        "postgres",
        "-d",
        "postgres",
        "-v",
        "ON_ERROR_STOP=1",
        "-A",
        "-t",
        "-c",
        sql,
      ],
      {
        cwd: REPOSITORY_ROOT,
        encoding: "utf8",
        stdio: ["ignore", "pipe", "pipe"],
      },
    ).trim();
    return JSON.parse(output) as T;
  } catch {
    throw new Error("Local guest QA database assertion failed");
  }
}

export function zeroStateSnapshot(): ZeroStateSnapshot {
  return psqlJson<ZeroStateSnapshot>(`
    select json_build_object(
      'auth_users', (select count(*) from auth.users),
      'profiles', (select count(*) from public.profiles),
      'disposable_allowlist_rows', (
        select count(*)
        from public.private_alpha_allowlist
        where email like 'guest-qa-%@example.test'
           or email like 'guest-link-%@example.test'
      ),
      'queued_jobs', (select count(*) from public.backtest_jobs where status = 'queued'),
      'running_jobs', (select count(*) from public.backtest_jobs where status = 'running'),
      'usage_counters', (select count(*) from public.usage_counters),
      'product_rows', (
        (select count(*) from public.guest_workspaces) +
        (select count(*) from public.guest_workspace_handoffs) +
        (select count(*) from public.conversations) +
        (select count(*) from public.messages) +
        (select count(*) from public.strategies) +
        (select count(*) from public.collections) +
        (select count(*) from public.collection_strategies) +
        (select count(*) from public.backtest_jobs) +
        (select count(*) from public.backtest_runs) +
        (select count(*) from public.ideas) +
        (select count(*) from public.idea_versions) +
        (select count(*) from public.evidence_artifacts) +
        (select count(*) from public.decision_notes) +
        (select count(*) from public.feedback) +
        (select count(*) from public.context_packets) +
        (select count(*) from public.run_context_packets) +
        (select count(*) from public.route_receipts) +
        (select count(*) from public.cost_ledger_entries) +
        (select count(*) from public.checkpoints) +
        (select count(*) from public.checkpoint_writes) +
        (select count(*) from public.checkpoint_blobs)
      )
    )::text
  `);
}

export function assertZeroState(): ZeroStateSnapshot {
  const state = zeroStateSnapshot();
  for (const value of Object.values(state)) {
    if (value !== 0) throw new Error("Guest QA database is not at zero state");
  }
  return state;
}

export function ownerSnapshot(userId: string): OwnerSnapshot {
  const owner = requireUuid(userId, "owner");
  return psqlJson<OwnerSnapshot>(`
    select json_build_object(
      'conversations', (select count(*) from public.conversations where user_id = '${owner}'),
      'messages', (select count(*) from public.messages where user_id = '${owner}'),
      'user_messages', (select count(*) from public.messages where user_id = '${owner}' and role = 'user'),
      'assistant_messages', (select count(*) from public.messages where user_id = '${owner}' and role = 'assistant'),
      'jobs', (select count(*) from public.backtest_jobs where user_id = '${owner}'),
      'succeeded_jobs', (select count(*) from public.backtest_jobs where user_id = '${owner}' and status = 'succeeded'),
      'runs', (select count(*) from public.backtest_runs where user_id = '${owner}'),
      'completed_runs', (select count(*) from public.backtest_runs where user_id = '${owner}' and status = 'completed'),
      'ideas', (select count(*) from public.ideas where user_id = '${owner}'),
      'idea_versions', (select count(*) from public.idea_versions where user_id = '${owner}'),
      'evidence', (select count(*) from public.evidence_artifacts where user_id = '${owner}'),
      'decisions', (select count(*) from public.decision_notes where user_id = '${owner}'),
      'feedback', (select count(*) from public.feedback where user_id = '${owner}'),
      'chat_units', coalesce((select sum(used_count) from public.usage_counters where user_id = '${owner}' and resource = 'chat_messages'), 0),
      'simulation_units', coalesce((select sum(used_count) from public.usage_counters where user_id = '${owner}' and resource = 'backtest_runs'), 0),
      'feedback_units', coalesce((select sum(used_count) from public.usage_counters where user_id = '${owner}' and resource = 'feedback'), 0),
      'cost_rows', (select count(*) from public.cost_ledger_entries where user_id = '${owner}'),
      'provider_cost_usd', coalesce((select sum(cost_amount) from public.cost_ledger_entries where user_id = '${owner}' and status = 'succeeded'), 0),
      'provider_latency_ms', coalesce((select sum(latency_ms) from public.cost_ledger_entries where user_id = '${owner}' and status = 'succeeded'), 0),
      'expires_at', (select expires_at::text from public.guest_workspaces where user_id = '${owner}')
    )::text
  `);
}

export function resultSummaryCost(userId: string): {
  rows: number;
  cost_usd: number;
  latency_ms: number;
} {
  const owner = requireUuid(userId, "owner");
  return psqlJson<{ rows: number; cost_usd: number; latency_ms: number }>(`
    select json_build_object(
      'rows', count(*),
      'cost_usd', coalesce(sum(cost_amount), 0),
      'latency_ms', coalesce(sum(latency_ms), 0)
    )::text
    from public.cost_ledger_entries
    where user_id = '${owner}'
      and task = 'result_summary'
      and status = 'succeeded'
  `);
}

export function resultTruthFingerprint(
  userId: string,
  conversationId: string,
): ResultTruthFingerprint {
  const owner = requireUuid(userId, "owner");
  const conversation = requireUuid(conversationId, "conversation");
  return psqlJson<ResultTruthFingerprint>(`
    select json_build_object(
      'rows', count(*),
      'fingerprint', md5(
        coalesce(
          jsonb_agg(
            jsonb_build_object(
              'id', id,
              'strategy_id', strategy_id,
              'status', status,
              'asset_class', asset_class,
              'symbols', symbols,
              'allocation_method', allocation_method,
              'benchmark_symbol', benchmark_symbol,
              'config_snapshot', config_snapshot,
              'metrics', metrics,
              'conversation_result_card', conversation_result_card,
              'chart', chart,
              'trades', trades,
              'error', error
            )
            order by id
          )::text,
          '[]'
        )
      )
    )::text
    from public.backtest_runs
    where user_id = '${owner}'
      and conversation_id = '${conversation}'
  `);
}

export function conversationGraph(
  userId: string,
  conversationId: string,
): ConversationGraph {
  const owner = requireUuid(userId, "owner");
  const conversation = requireUuid(conversationId, "conversation");
  return psqlJson<ConversationGraph>(`
    select json_build_object(
      'conversation', coalesce((select json_agg(id::text order by id) from public.conversations where id = '${conversation}' and user_id = '${owner}'), '[]'::json),
      'messages', coalesce((select json_agg(id::text order by id) from public.messages where conversation_id = '${conversation}' and user_id = '${owner}'), '[]'::json),
      'strategies', coalesce((select json_agg(id::text order by id) from public.strategies where conversation_id = '${conversation}' and user_id = '${owner}'), '[]'::json),
      'jobs', coalesce((select json_agg(id::text order by id) from public.backtest_jobs where conversation_id = '${conversation}' and user_id = '${owner}'), '[]'::json),
      'runs', coalesce((select json_agg(id::text order by id) from public.backtest_runs where conversation_id = '${conversation}' and user_id = '${owner}'), '[]'::json),
      'ideas', coalesce((select json_agg(id::text order by id) from public.ideas where source_conversation_id = '${conversation}' and user_id = '${owner}'), '[]'::json),
      'idea_versions', coalesce((select json_agg(id::text order by id) from public.idea_versions where source_conversation_id = '${conversation}' and user_id = '${owner}'), '[]'::json),
      'evidence', coalesce((select json_agg(id::text order by id) from public.evidence_artifacts where source_conversation_id = '${conversation}' and user_id = '${owner}'), '[]'::json),
      'decisions', coalesce((select json_agg(id::text order by id) from public.decision_notes where source_conversation_id = '${conversation}' and user_id = '${owner}'), '[]'::json),
      'context_packets', coalesce((select json_agg(id::text order by id) from public.context_packets where user_id = '${owner}'), '[]'::json),
      'run_context_packets', coalesce((
        select json_agg(link.id::text order by link.id)
        from public.run_context_packets as link
        join public.backtest_runs as run on run.id = link.run_id
        where link.user_id = '${owner}'
          and run.conversation_id = '${conversation}'
      ), '[]'::json),
      'checkpoints', coalesce((select json_agg(checkpoint_id order by checkpoint_id) from public.checkpoints where thread_id = '${conversation}'), '[]'::json)
    )::text
  `);
}

export function sameGraphIds(
  before: ConversationGraph,
  after: ConversationGraph,
): boolean {
  return (Object.keys(before) as Array<keyof ConversationGraph>).every(
    (key) =>
      JSON.stringify([...before[key]].sort()) ===
      JSON.stringify([...after[key]].sort()),
  );
}

export function graphDuplicateCount(graph: ConversationGraph): number {
  return (Object.keys(graph) as Array<keyof ConversationGraph>).reduce(
    (total, key) =>
      total + graph[key].length - new Set(graph[key]).size,
    0,
  );
}

export function markWorkspaceExpired(userId: string): void {
  const owner = requireUuid(userId, "owner");
  const changed = psqlJson<{ ok: boolean }>(`
    with changed as (
      update public.guest_workspaces
         set created_at = now() - interval '7 days 20 minutes',
             expires_at = now() - interval '20 minutes',
             updated_at = now() - interval '20 minutes'
       where user_id = '${owner}'
       returning 1
    )
    select json_build_object('ok', exists(select 1 from changed))::text
  `);
  if (!changed.ok) {
    throw new Error("Local guest QA expiry fixture was incomplete");
  }
}

export function markClaimedWorkspaceCleanupReady(userId: string): void {
  const owner = requireUuid(userId, "claimed guest owner");
  const changed = psqlJson<{ ok: boolean }>(`
    with changed as (
      update public.guest_workspaces
         set claimed_at = now() - interval '20 minutes',
             updated_at = now() - interval '20 minutes'
       where user_id = '${owner}'
         and status = 'claimed'
         and claimed_by is not null
       returning 1
    )
    select json_build_object('ok', exists(select 1 from changed))::text
  `);
  if (!changed.ok) {
    throw new Error("Claimed guest cleanup fixture was incomplete");
  }
}

export function cleanupExpectedGuestCandidates(
  userIds: string[],
): {
  dry_run_count: number;
  deleted_count: number;
  claimed_identity_count: number;
  expired_workspace_count: number;
} {
  if (userIds.length < 1 || userIds.length > 100) {
    throw new Error("Cleanup fixture must contain between one and 100 owners");
  }
  const expected = userIds.map((value) => requireUuid(value, "cleanup owner"));
  const expectedSet = new Set(expected);
  if (expectedSet.size !== expected.length) {
    throw new Error("Cleanup fixture owners must be unique");
  }
  const dryRun = psqlJson<
    Array<{ user_id: string; cleanup_reason: string }>
  >(`
    select coalesce(
      json_agg(
        json_build_object(
          'user_id', user_id,
          'cleanup_reason', cleanup_reason
        )
      ),
      '[]'::json
    )::text
    from public.claim_expired_guest_workspaces(${expected.length}, true)
  `);
  if (
    dryRun.length !== expected.length ||
    dryRun.some((row) => !expectedSet.has(row.user_id))
  ) {
    throw new Error("Cleanup dry run did not select the exact fixture set");
  }
  const claimed = psqlJson<
    Array<{
      user_id: string;
      auth_deleted: boolean;
      cleanup_reason: string;
    }>
  >(`
    select coalesce(
      json_agg(
        json_build_object(
          'user_id', user_id,
          'auth_deleted', auth_deleted,
          'cleanup_reason', cleanup_reason
        )
      ),
      '[]'::json
    )::text
    from public.claim_expired_guest_workspaces(${expected.length}, false)
  `);
  if (
    claimed.length !== expected.length ||
    claimed.some(
      (row) => !expectedSet.has(row.user_id) || row.auth_deleted !== true,
    )
  ) {
    throw new Error("Cleanup claim did not match the bounded dry run");
  }
  return {
    dry_run_count: dryRun.length,
    deleted_count: claimed.length,
    claimed_identity_count: claimed.filter(
      (row) => row.cleanup_reason === "claimed_identity",
    ).length,
    expired_workspace_count: claimed.filter(
      (row) => row.cleanup_reason === "expired_workspace",
    ).length,
  };
}

export function cleanupOneExpiredGuest(): {
  dry_run_count: number;
  deleted_count: number;
} {
  assertExactLocalCandidate();
  const dryRun = psqlJson<Array<{ user_id: string }>>(`
    select coalesce(json_agg(json_build_object('user_id', user_id)), '[]'::json)::text
    from public.claim_expired_guest_workspaces(1, true)
  `);
  if (dryRun.length !== 1) {
    throw new Error("Cleanup dry run did not select exactly one fixture");
  }
  const claimed = psqlJson<Array<{ user_id: string; auth_deleted: boolean }>>(`
    select coalesce(
      json_agg(json_build_object('user_id', user_id, 'auth_deleted', auth_deleted)),
      '[]'::json
    )::text
    from public.claim_expired_guest_workspaces(1, false)
  `);
  if (
    claimed.length !== 1 ||
    claimed[0].user_id !== dryRun[0].user_id ||
    claimed[0].auth_deleted !== true
  ) {
    throw new Error("Cleanup claim did not match the bounded dry run");
  }
  return { dry_run_count: 1, deleted_count: 1 };
}

export function authUserExists(userId: string): boolean {
  const owner = requireUuid(userId, "owner");
  return psqlJson<{ exists: boolean }>(`
    select json_build_object(
      'exists',
      exists(select 1 from auth.users where id = '${owner}')
    )::text
  `).exists;
}

export function handoffCount(userId: string): number {
  const owner = requireUuid(userId, "owner");
  return psqlJson<{ count: number }>(`
    select json_build_object(
      'count',
      (select count(*) from public.guest_workspace_handoffs where source_user_id = '${owner}')
    )::text
  `).count;
}

export function handoffState(userId: string): {
  total: number;
  consumed: number;
} {
  const owner = requireUuid(userId, "owner");
  return psqlJson<{ total: number; consumed: number }>(`
    select json_build_object(
      'total', count(*),
      'consumed', count(*) filter (where status = 'consumed')
    )::text
    from public.guest_workspace_handoffs
    where source_user_id = '${owner}'
  `);
}

export function decisionTargetsEvidence(params: {
  userId: string;
  conversationId: string;
  evidenceId: string;
}): boolean {
  const owner = requireUuid(params.userId, "owner");
  const conversation = requireUuid(params.conversationId, "conversation");
  const evidence = requireUuid(params.evidenceId, "evidence");
  return psqlJson<{ matches: boolean }>(`
    select json_build_object(
      'matches',
      exists(
        select 1
        from public.decision_notes
        where user_id = '${owner}'
          and source_conversation_id = '${conversation}'
          and evidence_artifact_id = '${evidence}'
      )
    )::text
  `).matches;
}

export function profileAccountKind(userId: string): {
  is_anonymous: boolean;
  email_present: boolean;
} {
  const owner = requireUuid(userId, "owner");
  return psqlJson<{ is_anonymous: boolean; email_present: boolean }>(`
    select json_build_object(
      'is_anonymous', coalesce((select is_anonymous from auth.users where id = '${owner}'), false),
      'email_present', exists(select 1 from public.profiles where id = '${owner}' and nullif(email, '') is not null)
    )::text
  `);
}

export function workspaceFacts(userId: string): {
  exists: boolean;
  active: boolean;
  fixed_seven_days: boolean;
  conversation_id: string | null;
  claimed_by: string | null;
} {
  const owner = requireUuid(userId, "owner");
  return psqlJson<{
    exists: boolean;
    active: boolean;
    fixed_seven_days: boolean;
    conversation_id: string | null;
    claimed_by: string | null;
  }>(`
    select json_build_object(
      'exists', exists(select 1 from public.guest_workspaces where user_id = '${owner}'),
      'active', exists(select 1 from public.guest_workspaces where user_id = '${owner}' and status = 'active' and expires_at > now()),
      'fixed_seven_days', exists(select 1 from public.guest_workspaces where user_id = '${owner}' and expires_at = created_at + interval '7 days'),
      'conversation_id', (select conversation_id::text from public.guest_workspaces where user_id = '${owner}'),
      'claimed_by', (select claimed_by::text from public.guest_workspaces where user_id = '${owner}')
    )::text
  `);
}

export function feedbackPrivacy(params: {
  userId: string;
  conversationId: string;
}): {
  rows: number;
  email_present: boolean;
  transcript_present: boolean;
  forbidden_context_fields: number;
  unchecked_rows: number;
  approved_context_rows: number;
  unapproved_key_rows: number;
  sensitive_value_rows: number;
} {
  const owner = requireUuid(params.userId, "owner");
  const conversation = requireUuid(
    params.conversationId,
    "feedback conversation",
  );
  return psqlJson<{
    rows: number;
    email_present: boolean;
    transcript_present: boolean;
    forbidden_context_fields: number;
    unchecked_rows: number;
    approved_context_rows: number;
    unapproved_key_rows: number;
    sensitive_value_rows: number;
  }>(`
    select json_build_object(
      'rows', count(*),
      'email_present', coalesce(bool_or(message ~* '[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}'), false),
      'transcript_present', coalesce(bool_or(context ? 'transcript' or context ? 'messages' or context ? 'raw_transcript'), false),
      'forbidden_context_fields', coalesce(sum(
        case when context ?| array['token','cookie','authorization','headers','email','url_query','transcript','messages'] then 1 else 0 end
      ), 0),
      'unchecked_rows', count(*) filter (where not (context ? 'conversation_id')),
      'approved_context_rows', count(*) filter (
        where context ->> 'conversation_id' = '${conversation}'
          and context ->> 'surface' = 'guest_header'
      ),
      'unapproved_key_rows', count(*) filter (
        where exists (
          select 1
          from jsonb_object_keys(context) as context_key(key)
          where context_key.key <> all(array[
            'source','surface','conversation_id','message_id','message_kind',
            'artifact_id','artifact_type','artifact_status','result_run_id',
            'strategy_id','saved_strategy_id','confirmation_id',
            'confirmation_state','confirmation_status','backtest_job_id',
            'backtest_job_status','failure_code','retryable','rating','tags',
            'timestamp','page_path','has_attachments','attachment_count'
          ])
        )
      ),
      'sensitive_value_rows', count(*) filter (
        where context::text ~* (
          'Preserved local QA idea'
          || '|The preserved local QA simulation completed'
          || '|[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}'
          || '|bearer|refresh[_ -]?token|cookie|authorization'
        )
      )
    )::text
    from public.feedback
    where user_id = '${owner}'
  `);
}

export function seedDurableRetryableFailure(params: {
  userId: string;
  conversationId: string;
}): {
  inserted: boolean;
  failedAssistantId: string;
} {
  const owner = requireUuid(params.userId, "failure owner");
  const conversation = requireUuid(
    params.conversationId,
    "failure conversation",
  );
  const userMessage = randomUUID();
  const assistantMessage = randomUUID();
  const prompt = "Retry this local QA recovery turn";
  const seeded = psqlJson<{ inserted: boolean }>(`
    with owned_conversation as (
      select 1
      from public.conversations
      where id = '${conversation}'
        and user_id = '${owner}'
    ),
    inserted_user as (
      insert into public.messages (
        id, conversation_id, user_id, role, content, metadata, created_at
      )
      select
        '${userMessage}', '${conversation}', '${owner}', 'user',
        '${prompt}', '{}'::jsonb, now()
      from owned_conversation
      returning 1
    ),
    inserted_assistant as (
      insert into public.messages (
        id, conversation_id, user_id, role, content, metadata, created_at
      )
      select
        '${assistantMessage}', '${conversation}', '${owner}', 'assistant',
        'Something went wrong. Your conversation is saved. Please try again.',
        jsonb_build_object(
          'conversation_mode', 'recovery',
          'agent_runtime_stage_outcome', 'agent_runtime_failure',
          'recovery', jsonb_build_object(
            'code', 'runtime_failure',
            'retryable', true,
            'language', 'en'
          ),
          'retry_last_turn', jsonb_build_object('message', '${prompt}')
        ),
        now() + interval '1 millisecond'
      from owned_conversation
      cross join inserted_user
      returning 1
    )
    select json_build_object(
      'inserted',
      exists(select 1 from inserted_user)
      and exists(select 1 from inserted_assistant)
    )::text
  `);
  if (!seeded.inserted) {
    throw new Error("Durable recovery fixture was not inserted");
  }
  return {
    inserted: true,
    failedAssistantId: assistantMessage,
  };
}

export function seedClaimSourceResultFixture(params: {
  userId: string;
  conversationId: string;
}): void {
  const owner = requireUuid(params.userId, "claim source owner");
  const conversation = requireUuid(
    params.conversationId,
    "claim source conversation",
  );
  const strategy = randomUUID();
  const run = randomUUID();
  const assistantMessage = randomUUID();
  const seeded = psqlJson<{ ok: boolean }>(`
    with owned_conversation as (
      select 1
      from public.conversations
      where id = '${conversation}'
        and user_id = '${owner}'
    ),
    inserted_strategy as (
      insert into public.strategies (
        id, user_id, conversation_id, name, template, asset_class,
        symbols, benchmark_symbol
      )
      select
        '${strategy}', '${owner}', '${conversation}',
        'Guest QA claim source', 'buy_and_hold', 'equity',
        array['MSFT']::text[], 'SPY'
      from owned_conversation
      returning 1
    ),
    inserted_run as (
      insert into public.backtest_runs (
        id, user_id, conversation_id, strategy_id, status, asset_class,
        symbols, benchmark_symbol, config_snapshot, conversation_result_card
      )
      select
        '${run}', '${owner}', '${conversation}', '${strategy}', 'completed',
        'equity', array['MSFT']::text[], 'SPY', '{}'::jsonb,
        jsonb_build_object(
          'status', 'completed',
          'symbols', jsonb_build_array('MSFT'),
          'benchmark_symbol', 'SPY'
        )
      from inserted_strategy
      returning 1
    ),
    inserted_message as (
      insert into public.messages (
        id, conversation_id, user_id, role, content, metadata
      )
      select
        '${assistantMessage}', '${conversation}', '${owner}', 'assistant',
        'Completed local claim source.',
        jsonb_build_object(
          'result_run_id', '${run}',
          'result_card', jsonb_build_object(
            'status', 'completed',
            'symbols', jsonb_build_array('MSFT'),
            'benchmark_symbol', 'SPY'
          )
        )
      from inserted_run
      returning 1
    )
    select json_build_object(
      'ok',
      exists(select 1 from inserted_strategy)
      and exists(select 1 from inserted_run)
      and exists(select 1 from inserted_message)
    )::text
  `);
  if (!seeded.ok) {
    throw new Error("Local claim source fixture was incomplete");
  }
}

export function seedClaimGraphFromConversation(params: {
  sourceOwnerId: string;
  sourceConversationId: string;
  targetOwnerId: string;
}): { conversationId: string; evidenceId: string } {
  const sourceOwner = requireUuid(params.sourceOwnerId, "source owner");
  const sourceConversation = requireUuid(
    params.sourceConversationId,
    "source conversation",
  );
  const targetOwner = requireUuid(params.targetOwnerId, "target owner");
  const ids = {
    conversation: randomUUID(),
    userMessage: randomUUID(),
    assistantMessage: randomUUID(),
    strategy: randomUUID(),
    run: randomUUID(),
    job: randomUUID(),
    idea: randomUUID(),
    version: randomUUID(),
    evidence: randomUUID(),
    decisionEvidence: randomUUID(),
    decision: randomUUID(),
    contextPacket: randomUUID(),
    runContextPacket: randomUUID(),
  };
  const resultCardExpression = `
    jsonb_set(
      jsonb_set(source_run.conversation_result_card, '{evidenceArtifactId}', to_jsonb('${ids.evidence}'::text), true),
      '{evidence_artifact_id}', to_jsonb('${ids.evidence}'::text), true
    )
  `;
  const seeded = psqlJson<{ ok: boolean }>(`
    with source_run as (
      select *
      from public.backtest_runs
      where user_id = '${sourceOwner}'
        and conversation_id = '${sourceConversation}'
        and status = 'completed'
      order by created_at desc
      limit 1
    ),
    source_result_message as (
      select *
      from public.messages
      where user_id = '${sourceOwner}'
        and conversation_id = '${sourceConversation}'
        and metadata ? 'result_card'
      order by created_at desc
      limit 1
    ),
    inserted_conversation as (
      insert into public.conversations (
        id, user_id, title, title_source, language, last_message_preview
      ) values (
        '${ids.conversation}', '${targetOwner}', 'Guest QA preserved result',
        'system_default', 'en', 'Preserved result'
      )
      returning 1
    ),
    linked_workspace as (
      update public.guest_workspaces
         set conversation_id = '${ids.conversation}',
             updated_at = now()
       where user_id = '${targetOwner}'
       returning 1
    ),
    inserted_user_message as (
      insert into public.messages (
        id, conversation_id, user_id, role, content, metadata
      ) values (
        '${ids.userMessage}', '${ids.conversation}', '${targetOwner}',
        'user', 'Preserved local QA idea', '{}'::jsonb
      )
      returning 1
    ),
    inserted_strategy as (
      insert into public.strategies (
        id, user_id, conversation_id, name, template, asset_class,
        symbols, benchmark_symbol
      )
      select
        '${ids.strategy}', '${targetOwner}', '${ids.conversation}',
        'Preserved local QA strategy', 'buy_and_hold',
        source_run.asset_class, source_run.symbols, source_run.benchmark_symbol
      from source_run
      returning 1
    ),
    inserted_run as (
      insert into public.backtest_runs (
        id, user_id, conversation_id, strategy_id, status, asset_class,
        symbols, benchmark_symbol, config_snapshot, conversation_result_card
      )
      select
        '${ids.run}', '${targetOwner}', '${ids.conversation}',
        '${ids.strategy}', 'completed', source_run.asset_class,
        source_run.symbols, source_run.benchmark_symbol,
        source_run.config_snapshot, ${resultCardExpression}
      from source_run
      returning 1
    ),
    inserted_job as (
      insert into public.backtest_jobs (
        id, user_id, conversation_id, request_message_id,
        confirmation_message_id, idempotency_key, payload_hash,
        launch_payload, status, result_run_id
      ) values (
        '${ids.job}', '${targetOwner}', '${ids.conversation}',
        '${ids.userMessage}', '${ids.userMessage}',
        'guest-qa-preserved-run', 'guest-qa-preserved-payload',
        '{}'::jsonb, 'succeeded', '${ids.run}'
      )
      returning 1
    ),
    inserted_idea as (
      insert into public.ideas (
        id, user_id, source_conversation_id, title, summary, lifecycle
      ) values (
        '${ids.idea}', '${targetOwner}', '${ids.conversation}',
        'Preserved local QA idea', 'Preserved for atomic claim', 'reviewed'
      )
      returning 1
    ),
    inserted_version as (
      insert into public.idea_versions (
        id, user_id, idea_id, source_conversation_id, source_run_id,
        canonical_spec, strategy_snapshot, title, summary, lifecycle
      ) values (
        '${ids.version}', '${targetOwner}', '${ids.idea}',
        '${ids.conversation}', '${ids.run}', '{}'::jsonb, '{}'::jsonb,
        'Preserved local QA idea', 'Version one', 'reviewed'
      )
      returning 1
    ),
    inserted_evidence as (
      insert into public.evidence_artifacts (
        id, user_id, idea_id, idea_version_id, source_conversation_id,
        source_run_id, lifecycle, title, digest, payload
      ) values (
        '${ids.evidence}', '${targetOwner}', '${ids.idea}', '${ids.version}',
        '${ids.conversation}', '${ids.run}', 'reviewed',
        'Preserved local QA result', 'local-qa-digest', '{}'::jsonb
      )
      returning 1
    ),
    inserted_decision_evidence as (
      insert into public.evidence_artifacts (
        id, user_id, idea_id, idea_version_id, source_conversation_id,
        source_run_id, lifecycle, title, digest, payload
      ) values (
        '${ids.decisionEvidence}', '${targetOwner}', '${ids.idea}',
        '${ids.version}', '${ids.conversation}', null, 'decided',
        'Preserved local QA prior decision', 'local-qa-decision-digest',
        '{}'::jsonb
      )
      returning 1
    ),
    inserted_decision as (
      insert into public.decision_notes (
        id, user_id, idea_id, idea_version_id, evidence_artifact_id,
        source_conversation_id, decision_state, note
      ) values (
        '${ids.decision}', '${targetOwner}', '${ids.idea}', '${ids.version}',
        '${ids.decisionEvidence}', '${ids.conversation}', 'watching',
        'Preserved prior decision'
      )
      returning 1
    ),
    inserted_context_packet as (
      insert into public.context_packets (
        id, user_id, provider, packet_type, retrieved_at
      ) values (
        '${ids.contextPacket}', '${targetOwner}', 'alpaca', 'news', now()
      )
      returning 1
    ),
    inserted_run_context_packet as (
      insert into public.run_context_packets (
        id, user_id, run_id, context_packet_id
      ) values (
        '${ids.runContextPacket}', '${targetOwner}', '${ids.run}',
        '${ids.contextPacket}'
      )
      returning 1
    ),
    inserted_assistant_message as (
      insert into public.messages (
        id, conversation_id, user_id, role, content, metadata
      )
      select
        '${ids.assistantMessage}', '${ids.conversation}', '${targetOwner}',
        'assistant', 'The preserved local QA simulation completed.',
        jsonb_set(
          jsonb_set(
            jsonb_set(
              jsonb_set(
                source_result_message.metadata,
                '{result_card}', ${resultCardExpression}, true
              ),
              '{result_run_id}', to_jsonb('${ids.run}'::text), true
            ),
            '{latest_run_id}', to_jsonb('${ids.run}'::text), true
          ),
          '{result_strategy_id}', to_jsonb('${ids.strategy}'::text), true
        )
      from source_result_message
      cross join source_run
      returning 1
    ),
    inserted_checkpoint as (
      insert into public.checkpoints (
        thread_id, checkpoint_ns, checkpoint_id, checkpoint
      ) values (
        '${ids.conversation}', '', 'guest-qa-preserved-checkpoint', '{}'::jsonb
      )
      returning 1
    ),
    inserted_usage as (
      insert into public.usage_counters (
        user_id, resource, period, period_start, period_end,
        used_count, limit_count
      )
      select
        '${targetOwner}', resource, 'guest_session',
        workspace.created_at, workspace.expires_at, used_count, limit_count
      from public.guest_workspaces as workspace
      cross join (
        values
          ('chat_messages'::text, 1, 10),
          ('backtest_runs'::text, 1, 1)
      ) as policy(resource, used_count, limit_count)
      where workspace.user_id = '${targetOwner}'
      returning 1
    )
    select json_build_object(
      'ok',
      exists(select 1 from inserted_conversation)
      and exists(select 1 from linked_workspace)
      and exists(select 1 from inserted_user_message)
      and exists(select 1 from inserted_strategy)
      and exists(select 1 from inserted_run)
      and exists(select 1 from inserted_job)
      and exists(select 1 from inserted_idea)
      and exists(select 1 from inserted_version)
      and exists(select 1 from inserted_evidence)
      and exists(select 1 from inserted_decision_evidence)
      and exists(select 1 from inserted_decision)
      and exists(select 1 from inserted_context_packet)
      and exists(select 1 from inserted_run_context_packet)
      and exists(select 1 from inserted_assistant_message)
      and exists(select 1 from inserted_checkpoint)
      and (select count(*) from inserted_usage) = 2
    )::text
  `);
  if (!seeded.ok) {
    throw new Error("Local guest QA claim fixture was incomplete");
  }
  return {
    conversationId: ids.conversation,
    evidenceId: ids.evidence,
  };
}

export class BackendController {
  private process: ChildProcess | null = null;
  private publicAccountsEnabled = false;

  async start(publicAccountsEnabled: boolean): Promise<void> {
    await this.stop();
    this.publicAccountsEnabled = publicAccountsEnabled;
    this.process = spawn(
      "poetry",
      [
        "run",
        "uvicorn",
        "argus.api.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
      ],
      {
        cwd: REPOSITORY_ROOT,
        env: {
          ...process.env,
          ARGUS_GUEST_ACCESS_ENABLED: "true",
          ARGUS_PUBLIC_ACCOUNT_ACCESS_ENABLED: String(publicAccountsEnabled),
          ARGUS_PRIVATE_ALPHA_ONBOARDING_ENABLED: "false",
          ARGUS_MOCK_AUTH: "false",
        },
        stdio: "ignore",
      },
    );
    await expect
      .poll(
        async () => {
          if (this.process?.exitCode !== null) return "exited";
          const response = await fetch(`${LOCAL_API_BASE}/auth/session`).catch(
            () => null,
          );
          return response?.status === 200 || response?.status === 401;
        },
        {
          message: "local Argus API should become healthy",
          timeout: 90_000,
          intervals: [100, 250, 500, 1_000],
        },
      )
      .toBe(true);
  }

  async stop(): Promise<void> {
    const child = this.process;
    this.process = null;
    if (!child || child.exitCode !== null) return;
    child.kill("SIGTERM");
    await new Promise<void>((resolve) => {
      const timer = setTimeout(() => {
        if (child.exitCode === null) child.kill("SIGKILL");
        resolve();
      }, 5_000);
      child.once("exit", () => {
        clearTimeout(timer);
        resolve();
      });
    });
  }

  get flagsRestoredFalse(): boolean {
    return !this.publicAccountsEnabled;
  }
}

export async function waitForBackendHealthy(): Promise<void> {
  await expect
    .poll(
      async () => {
        const response = await fetch(`${LOCAL_API_BASE}/auth/session`).catch(
          () => null,
        );
        return response?.status === 200 || response?.status === 401;
      },
      {
        message: "local Argus API should answer",
        timeout: 90_000,
        intervals: [100, 250, 500, 1_000],
      },
    )
    .toBe(true);
}

export async function assertFreshContext(
  context: BrowserContext,
): Promise<void> {
  const storage = await context.storageState();
  expect(storage.cookies).toEqual([]);
  expect(storage.origins).toEqual([]);
  expect(context.serviceWorkers()).toEqual([]);
}

export async function apiJson<T>(
  request: APIRequestContext,
  pathname: string,
  options: {
    method?: "GET" | "POST" | "PATCH" | "DELETE";
    data?: unknown;
  } = {},
): Promise<{ status: number; body: T }> {
  const method = options.method ?? "GET";
  const response = await request.fetch(`${LOCAL_API_BASE}${pathname}`, {
    method,
    data: options.data,
  });
  let body: T;
  try {
    body = (await response.json()) as T;
  } catch {
    throw new Error("Local guest QA API returned an unexpected response");
  }
  return { status: response.status(), body };
}

export async function waitForMe(
  page: Page,
  timeoutMs = 60_000,
): Promise<GuestMe> {
  const response = await page.waitForResponse(
    (candidate) =>
      candidate.request().method() === "GET" &&
      new URL(candidate.url()).pathname.endsWith("/api/v1/me") &&
      candidate.status() === 200,
    { timeout: timeoutMs },
  );
  return (await response.json()) as GuestMe;
}

export async function freshGuest(
  page: Page,
  options: {
    timeoutMs?: number;
    onBootstrapOwner?: (owner: string) => void;
  } = {},
): Promise<GuestMe> {
  const timeoutMs = options.timeoutMs ?? 60_000;
  const bootstrapOwnerPromise = page
    .waitForResponse(
      (candidate) =>
        candidate.request().method() === "POST" &&
        new URL(candidate.url()).pathname.endsWith("/api/v1/auth/guest") &&
        candidate.status() === 200,
      { timeout: timeoutMs },
    )
    .then(async (response) => {
      const payload = (await response.json()) as {
        user?: { id?: unknown } | null;
      };
      const owner = requireUuid(
        typeof payload.user?.id === "string" ? payload.user.id : "",
        "guest bootstrap owner",
      );
      options.onBootstrapOwner?.(owner);
      return owner;
    });
  const mePromise = Promise.all([
    waitForMe(page, timeoutMs),
    bootstrapOwnerPromise,
  ]).then(([me, bootstrapOwner]) => {
    if (me.user.id !== bootstrapOwner) {
      throw new Error("Guest bootstrap and verified profile owners differ");
    }
    return { kind: "authenticated" as const, me };
  });
  const entryErrorPromise = page
    .getByRole("button", { name: /Try again|Intentar de nuevo/i })
    .waitFor({ state: "visible", timeout: timeoutMs })
    .then(() => ({ kind: "entry_error" as const }));
  await page.goto("/", { waitUntil: "domcontentloaded" });
  let outcome:
    | Awaited<typeof mePromise>
    | Awaited<typeof entryErrorPromise>;
  try {
    outcome = await Promise.race([mePromise, entryErrorPromise]);
  } catch (error) {
    throw new Error("Guest public entry failed before authentication", {
      cause: error,
    });
  }
  if (outcome.kind === "entry_error") {
    throw new Error("Guest public entry failed before authentication");
  }
  expect(new URL(page.url()).pathname).toBe("/chat");
  return outcome.me;
}

export function evidenceLabel(namespace: string, value: string): string {
  const candidate = requireCandidateSha();
  return createHash("sha256")
    .update(`argus-guest-qa:${candidate}:${namespace}:${value}`)
    .digest("hex")
    .slice(0, 20);
}

export function safeConfirmationEvidence(
  facts: ConfirmationFacts,
): SafeConfirmationEvidence {
  return {
    message_label: evidenceLabel("message", facts.messageId),
    confirmation_label: evidenceLabel("confirmation", facts.confirmationId),
    asset_universe: [...facts.assetUniverse],
    benchmark: facts.benchmark,
    requested_date_range: { ...facts.requestedDateRange },
    effective_date_range: { ...facts.effectiveDateRange },
  };
}

export function normalizeRoute(rawUrl: string): string {
  const url = new URL(rawUrl);
  return url.pathname.replace(UUID_PATTERN, ":id");
}

function sanitizedEndpoint(rawUrl: string, method: string): string {
  let route = "unknown";
  try {
    route = normalizeRoute(rawUrl)
      .replace(EMAIL_PATTERN, ":redacted")
      .replace(JWT_PATTERN, ":redacted");
  } catch {
    route = "unknown";
  } finally {
    UUID_PATTERN.lastIndex = 0;
    EMAIL_PATTERN.lastIndex = 0;
    JWT_PATTERN.lastIndex = 0;
  }
  return `${method.toUpperCase()} ${route}`;
}

function browserErrorCategory(
  event: BrowserSafetyDetail["event"],
  rawError: string,
  status?: number | null,
): string {
  if (typeof status === "number" && status >= 500) {
    return "http_server_error";
  }
  if (typeof status === "number" && status >= 400) {
    return "http_client_error";
  }
  const value = rawError.toLowerCase();
  if (
    value.includes("err_connection_refused") ||
    value.includes("connection refused")
  ) {
    return "connection_refused";
  }
  if (
    value.includes("err_connection_reset") ||
    value.includes("connection reset")
  ) {
    return "connection_reset";
  }
  if (value.includes("err_aborted") || value.includes("abort")) {
    return "aborted";
  }
  if (value.includes("timeout") || value.includes("timed out")) {
    return "timeout";
  }
  if (value.includes("hydration")) return "hydration_error";
  if (value.includes("fetch") || value.includes("network")) {
    return "network_error";
  }
  return event;
}

export function browserSafetyDetail(input: {
  event: BrowserSafetyDetail["event"];
  rawUrl?: string;
  method?: string;
  rawError?: string;
  status?: number | null;
  context: BrowserSafetyContext;
}): BrowserSafetyDetail {
  const isNetwork = input.event === "failed_request";
  return {
    event: input.event,
    component:
      input.event === "console_error"
        ? "browser_console"
        : input.event === "page_error"
          ? "browser_page"
          : "network",
    endpoint:
      isNetwork && input.rawUrl
        ? sanitizedEndpoint(input.rawUrl, input.method ?? "REQUEST")
        : null,
    status:
      typeof input.status === "number" && Number.isInteger(input.status)
        ? input.status
        : null,
    category: browserErrorCategory(
      input.event,
      input.rawError ?? "",
      input.status,
    ),
    check: input.context.check,
    phase: input.context.phase,
  };
}

export function productFailedRequestsForCheck(
  details: BrowserSafetyDetail[],
  check: GuestCheckNumber,
): BrowserSafetyDetail[] {
  return details.filter(
    (detail) =>
      detail.event === "failed_request" &&
      detail.check === check &&
      detail.phase === "product",
  );
}

export class BrowserSafetyMonitor {
  consoleErrors = 0;
  pageErrors = 0;
  failedRequests = 0;
  hostedWrites = 0;
  credentialExposure = 0;
  readonly mutations = new Map<string, number>();
  private readonly details: BrowserSafetyDetail[] = [];

  constructor(
    private readonly context: () => BrowserSafetyContext = () => ({
      check: null,
      phase: "product",
    }),
  ) {}

  attach(page: Page): void {
    page.on("console", (message) => {
      if (message.type() === "error") {
        this.consoleErrors += 1;
        this.details.push(
          browserSafetyDetail({
            event: "console_error",
            rawError: message.text(),
            context: this.context(),
          }),
        );
      }
      this.scan(message.text());
    });
    page.on("pageerror", (error) => {
      this.pageErrors += 1;
      this.details.push(
        browserSafetyDetail({
          event: "page_error",
          rawError: error.message,
          context: this.context(),
        }),
      );
      this.scan(error.message);
    });
    page.on("requestfailed", (request) => {
      this.failedRequests += 1;
      this.details.push(
        browserSafetyDetail({
          event: "failed_request",
          rawUrl: request.url(),
          method: request.method(),
          rawError: request.failure()?.errorText ?? "",
          context: this.context(),
        }),
      );
    });
    page.on("response", (response) => {
      if (response.status() < 400) return;
      this.failedRequests += 1;
      this.details.push(
        browserSafetyDetail({
          event: "failed_request",
          rawUrl: response.url(),
          method: response.request().method(),
          status: response.status(),
          context: this.context(),
        }),
      );
    });
    page.on("request", (request) => {
      const url = new URL(request.url());
      const isWrite = !["GET", "HEAD", "OPTIONS"].includes(request.method());
      if (isWrite) {
        const key = sanitizedEndpoint(request.url(), request.method());
        this.mutations.set(key, (this.mutations.get(key) ?? 0) + 1);
        if (!["localhost", "127.0.0.1"].includes(url.hostname)) {
          this.hostedWrites += 1;
        }
      }
      if (!["localhost", "127.0.0.1"].includes(url.hostname)) {
        const headers = request.headers();
        const sensitiveShape = [
          url.search,
          Object.keys(headers).join(" "),
          request.postData() ?? "",
        ].join(" ");
        if (
          /token|cookie|authorization|bearer|password|email|session|secret/i.test(
            sensitiveShape,
          )
        ) {
          this.credentialExposure += 1;
        }
      }
    });
  }

  private scan(value: string): void {
    if (
      JWT_PATTERN.test(value) ||
      EMAIL_PATTERN.test(value) ||
      /refresh[_ -]?token|service[_ -]?role|authorization:\s*bearer/i.test(value)
    ) {
      this.credentialExposure += 1;
    }
    JWT_PATTERN.lastIndex = 0;
    EMAIL_PATTERN.lastIndex = 0;
  }

  mutationSnapshot(): Record<string, number> {
    return Object.fromEntries([...this.mutations.entries()].sort());
  }

  detailSnapshot(): BrowserSafetyDetail[] {
    return this.details.map((detail) => ({ ...detail }));
  }
}

function evidenceDirectory(): string {
  const directory = path.join(
    REPOSITORY_ROOT,
    "temp",
    "qa-evidence-guest",
    requireCandidateSha(),
    "authoritative",
  );
  mkdirSync(directory, { recursive: true, mode: 0o700 });
  chmodSync(directory, 0o700);
  return directory;
}

export async function safeScreenshot(
  page: Page,
  name: string,
  target?: ReturnType<Page["locator"]>,
): Promise<void> {
  if (!/^[a-z0-9-]+$/.test(name)) throw new Error("Unsafe screenshot name");
  const destination = path.join(evidenceDirectory(), `${name}.png`);
  const mask = [
    page.locator('input[type="email"]'),
    page.locator('input[type="password"]'),
    page.locator("textarea"),
    page.locator('[data-conversation-id]'),
  ];
  if (target) {
    await target.screenshot({ path: destination, mask });
  } else {
    await page.screenshot({
      path: destination,
      fullPage: false,
      mask,
    });
  }
  chmodSync(destination, 0o600);
}

export function assertSafeEvidence(evidence: SafeEvidence): void {
  const candidate = requireCandidateSha();
  if (evidence.candidate_sha !== candidate) {
    throw new Error("Evidence SHA does not match candidate");
  }
  const labels = [
    ...evidence.owner_labels,
    ...evidence.conversation_labels,
    ...evidence.artifact_labels,
  ];
  if (labels.some((label) => !/^[0-9a-f]{20}$/.test(label))) {
    throw new Error("Evidence contains a non-hashed product identifier");
  }
  const safeEndpoint = /^[A-Z]+ \/[A-Za-z0-9_./:@-]+$/;
  const safeCategories = new Set([
    "connection_refused",
    "connection_reset",
    "aborted",
    "timeout",
    "hydration_error",
    "network_error",
    "console_error",
    "page_error",
    "failed_request",
    "http_client_error",
    "http_server_error",
  ]);
  for (const detail of evidence.browser_safety_details) {
    if (
      (detail.endpoint !== null && !safeEndpoint.test(detail.endpoint)) ||
      !safeCategories.has(detail.category) ||
      (detail.check !== null && (detail.check < 1 || detail.check > 20))
    ) {
      throw new Error("Evidence contains an unsafe browser safety detail");
    }
  }
  if (
    Object.keys(evidence.normalized_mutation_counts).some(
      (endpoint) => !safeEndpoint.test(endpoint),
    )
  ) {
    throw new Error("Evidence contains an unsafe mutation endpoint");
  }
  const serialized = JSON.stringify(evidence);
  if (
    UUID_PATTERN.test(serialized) ||
    JWT_PATTERN.test(serialized) ||
    EMAIL_PATTERN.test(serialized) ||
    serialized.includes("?")
  ) {
    throw new Error("Evidence contains a forbidden identifier or secret shape");
  }
  UUID_PATTERN.lastIndex = 0;
  JWT_PATTERN.lastIndex = 0;
  EMAIL_PATTERN.lastIndex = 0;
}

export function writeEvidence(evidence: SafeEvidence): void {
  assertSafeEvidence(evidence);
  const directory = evidenceDirectory();
  const finalPath = path.join(directory, "summary.json");
  const temporaryPath = path.join(
    directory,
    `.summary-${process.pid}-${Date.now()}.tmp`,
  );
  writeFileSync(temporaryPath, `${JSON.stringify(evidence, null, 2)}\n`, {
    encoding: "utf8",
    mode: 0o600,
    flag: "wx",
  });
  chmodSync(temporaryPath, 0o600);
  renameSync(temporaryPath, finalPath);
  chmodSync(finalPath, 0o600);
}

function serviceClient(): SupabaseClient {
  const url = localUrl(
    process.env.SUPABASE_PROJECT_URL,
    "SUPABASE_PROJECT_URL",
  ).origin;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!key) throw new Error("Local service role key is required");
  return createClient(url, key, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
}

export async function createDisposableRegisteredIdentity(): Promise<DisposableIdentity> {
  const client = serviceClient();
  const email = `guest-qa-${randomBytes(10).toString("hex")}@example.test`;
  const password = `Qa!${randomBytes(24).toString("base64url")}`;
  const { data, error } = await client.auth.admin.createUser({
    email,
    password,
    email_confirm: true,
  });
  if (error || !data.user) {
    throw new Error("Could not create the local registered QA identity");
  }
  const userId = data.user.id;
  const { error: profileError } = await client.from("profiles").upsert({
    id: userId,
    email,
    display_name: "Local QA",
    language: "en",
  });
  if (profileError) {
    await client.auth.admin.deleteUser(userId);
    throw new Error("Could not create the local registered QA profile");
  }
  const { error: allowlistError } = await client
    .from("private_alpha_allowlist")
    .upsert({ email });
  if (allowlistError) {
    await client.auth.admin.deleteUser(userId);
    throw new Error("Could not allowlist the local registered QA identity");
  }
  return { userId, email, password };
}

export function newSignupCredentials(): Pick<
  DisposableIdentity,
  "email" | "password"
> {
  return {
    email: `guest-link-${randomBytes(10).toString("hex")}@example.test`,
    password: `Qa!${randomBytes(24).toString("base64url")}`,
  };
}

export async function deleteDisposableIdentity(userId: string): Promise<void> {
  requireUuid(userId, "disposable identity");
  const client = serviceClient();
  const { data: identity, error: identityError } =
    await client.auth.admin.getUserById(userId);
  if (identityError && !/not found/i.test(identityError.message)) {
    throw new Error("Could not inspect the local disposable identity");
  }
  const email = identity.user?.email;
  if (email) {
    const { error: allowlistError } = await client
      .from("private_alpha_allowlist")
      .delete()
      .eq("email", email);
    if (allowlistError) {
      throw new Error("Could not remove the local disposable allowlist row");
    }
  }
  const { error } = await client.auth.admin.deleteUser(userId);
  if (error && !/not found/i.test(error.message)) {
    throw new Error("Could not delete the local disposable identity");
  }
}

export function purgeDisposableQaEvidence(): void {
  const state = zeroStateSnapshot();
  if (state.auth_users !== 0 || state.profiles !== 0) {
    throw new Error("Guest QA refused to purge evidence before identity cleanup");
  }
  const purged = psqlJson<{ ok: boolean }>(`
    with deleted_cost as (
      delete from public.cost_ledger_entries returning 1
    ),
    deleted_feedback as (
      delete from public.feedback returning 1
    ),
    deleted_receipts as (
      delete from public.route_receipts returning 1
    ),
    deleted_writes as (
      delete from public.checkpoint_writes returning 1
    ),
    deleted_blobs as (
      delete from public.checkpoint_blobs returning 1
    ),
    deleted_checkpoints as (
      delete from public.checkpoints returning 1
    )
    select json_build_object('ok', true)::text
  `);
  if (!purged.ok) {
    throw new Error("Guest QA could not purge disposable local evidence");
  }
}

export function emptyEvidence(): SafeEvidence {
  return {
    candidate_sha: requireCandidateSha(),
    status: "failed",
    completed_checks: [],
    failure_check: null,
    flags_restored_false: false,
    fresh_context_verified: false,
    owner_labels: [],
    conversation_labels: [],
    artifact_labels: [],
    check4_initial_confirmation: null,
    check4_refined_confirmation: null,
    simulation_usage_matches: false,
    same_uuid_conversion: false,
    new_account_resume_count: 0,
    existing_claim_owner_changed: false,
    existing_claim_duplicate_count: 0,
    existing_claim_resume_count: 0,
    feedback_rows_added: 0,
    feedback_email_present: false,
    feedback_transcript_present: false,
    interrupted_usage_delta: 0,
    cleanup_deleted_count: 0,
    cleanup_permanent_control_preserved: false,
    cross_owner_result_count: 0,
    console_error_count: 0,
    page_error_count: 0,
    failed_request_count: 0,
    browser_safety_details: [],
    teardown_console_error_count: 0,
    teardown_page_error_count: 0,
    teardown_failed_request_count: 0,
    teardown_hosted_write_count: 0,
    teardown_credential_exposure_count: 0,
    hosted_write_count: 0,
    server_product_analytics_disabled: false,
    credential_exposure_count: 0,
    provider_cost_usd: 0,
    provider_latency_ms: 0,
    normalized_mutation_counts: {},
    teardown_clean: false,
  };
}
