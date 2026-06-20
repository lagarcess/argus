# DATA_MODEL.md

## Argus Data Model Source of Truth (Alpha MVP)

**Status:** Active
**Audience:** Backend engineers, database agents, API agents, frontend agents
**Purpose:** Define the Alpha MVP database entities, relationships, ownership rules, and persistence expectations for Argus.

---

# 1. Data Model Philosophy

Argus is a chat-first AI investing sandbox.

The data model must support:

- multi-chat conversations
- persistent user preferences
- AI-generated titles/names
- saved strategies
- strategy collections
- reproducible backtest runs
- symbol-level and aggregate metrics
- soft deletion and archive behavior
- future expansion without schema churn

The database should make the Alpha experience reliable, not overly complex.

---

# 2. Source of Truth

Supabase Postgres is the canonical state store.

Supabase owns:

- private-alpha access allowlist
- user profiles
- preferences
- conversations
- messages
- strategies
- collections
- backtest jobs
- backtest runs
- feedback
- telemetry-ready product state

Render/FastAPI owns orchestration and compute, not long-term state. Render
Workflows own temporary backtest execution, but job lifecycle and result truth
remain in Supabase.

---

# 3. Core Entities

Alpha MVP requires these primary entities:

```text
private_alpha_allowlist
profiles
conversations
messages
strategies
collections
collection_strategies
backtest_jobs
backtest_runs
feedback
usage_counters
```

Optional or later:
```
- assets
- telemetry_events
- deleted_items view
- archived_items view
```

---
# 4. Entity Relationship Overview

```
auth.users
   └── profiles
profiles
   ├── conversations
   │      ├── messages
   │      ├── backtest_jobs
   │      └── backtest_runs
   │
   ├── strategies
   │      ├── backtest_runs
   │      └── collection_strategies
   │
   ├── collections
   │      └── collection_strategies
   │
   ├── usage_counters
   └── feedback
```

---

# 5. profiles

Represents the application-facing user profile. Supabase Auth owns identity and session, while the Argus `profiles` table owns product-specific preferences.

### Fields
- `id`: `uuid` (Primary Key, references `auth.users.id`)
- `email`: `text`
- `username`: `text` (Unique, Nullable)
- `display_name`: `text` (Nullable)
- `language`: `text` (Default: `'en'`)
- `locale`: `text` (Default: `'en-US'`)
- `theme`: `text` (Default: `'dark'`)
- `is_admin`: `boolean` (Default: `false`)
- `onboarding`: `jsonb` (Default: `{}`)
- `created_at`: `timestamptz`
- `updated_at`: `timestamptz`

### Onboarding Shape
```json
{
  "completed": false,
  "stage": "language_selection",
  "language_confirmed": false,
  "primary_goal": null
}
```

### Constraints & Notes
- **Supported Languages**: `en`, `es-419`
- **Supported Locales**: `en-US`, `es-419`
- `display_name` is used for personalization.
- `email` is for authentication, not primary UX identity.
- `username` is optional for Alpha.
---

# 6. private_alpha_allowlist

Server-side access list for private alpha. This table is checked before signup
and login; it should not be exposed as a frontend product surface.

### Fields
- `email`: `text` (Primary Key, lowercased)
- `role`: `text` (Default: `user`)
- `disabled_at`: `timestamptz` (Nullable)
- `created_at`: `timestamptz`
- `updated_at`: `timestamptz`

### Enums
- **role**: `admin`, `developer`, `user`

### Notes
- Rows are managed directly in Supabase during private alpha. No invite
  dashboard, waitlist, referral system, or public invite-code flow is part of
  this pass.
- Add a new private-alpha user with only an `email`; set `role` only for
  `admin` or `developer` access. Use `disabled_at` to revoke access.
- If an email is missing or `disabled_at` is set, `/auth/signup` and
  `/auth/login` still check the allowlist before provider signup/session work,
  but public auth responses are normalized to reduce invite enumeration:
  signup returns `400 auth_signup_failed`, login returns `401 unauthorized`,
  and authenticated API requests reject disabled/unlisted emails after token
  validation with `403 private_alpha_access_required`.
- The table may contain emails for existing Supabase Auth users; seeding the
  allowlist must not create auth users by itself.
---

# 7. conversations

Represents an isolated chat thread. Each conversation represents a single investing "idea journey."

### Fields
- `id`: `uuid` (Primary Key)
- `user_id`: `uuid` (References `profiles.id`)
- `title`: `text`
- `title_source`: `text` (Default: `'system_default'`)
- `language`: `text` (Nullable)
- `pinned`: `boolean` (Default: `false`)
- `archived`: `boolean` (Default: `false`)
- `deleted_at`: `timestamptz` (Nullable, for soft delete)
- `last_message_preview`: `text` (Nullable)
- `created_at`: `timestamptz`
- `updated_at`: `timestamptz`

### Enums
- **title_source**: `system_default`, `ai_generated`, `user_renamed`

### Notes
- Conversations use **soft delete** behavior.
- AI-generated titles should be created once sufficient context is established.
- `language` can be stored at the thread level for continuity, but the user profile remains the primary source.
---

# 8. messages

Represents individual messages within a conversation.

### Fields
- `id`: `uuid` (Primary Key)
- `conversation_id`: `uuid` (References `conversations.id`)
- `user_id`: `uuid` (References `profiles.id`)
- `role`: `text` (e.g., `user`, `assistant`)
- `content`: `text`
- `metadata`: `jsonb` (Default: `{}`)
- `created_at`: `timestamptz`

### Enums
- **role**: `user`, `assistant`, `system`, `tool`

### Notes
- Messages are immutable in Alpha.
- `metadata` stores token usage, model identifiers, latency, and tool execution traces.
- Message metadata may contain reloadable chat artifacts such as
  `pending_strategy`, `confirmation_card`, `confirmation_payload`,
  `result_card`, result identifiers, `chat_action`, `failed_action`, and
  `retry_last_turn`. These fields hydrate the transcript and action affordances;
  they do not make free-form transcript text the source of truth for strategy
  state.
- When a turn follows an artifact-backed setup, the runtime must reconstruct the
  working draft from canonical artifact state before applying the new user
  message as a patch. Canonical artifact state comes from, in order of
  specificity, the structured action payload, active confirmation payload,
  completed `backtest_runs.config_snapshot`, saved strategy state, or failed
  action launch payload.
- Persisted recovery or retry metadata is scoped to the failed turn/action it
  references. Later turns that create a new draft, active confirmation,
  completed result, or explicit cancellation should supersede stale retry
  affordances during hydration.
---

# 9. strategies

Represents a saved, executable strategy idea backed by an engine template.

### Fields
- `id`: `uuid` (Primary Key)
- `user_id`: `uuid` (References `profiles.id`)
- `conversation_id`: `uuid` (Nullable, references `conversations.id`)
- `name`: `text`
- `name_source`: `text` (Default: `'system_default'`)
- `template`: `text`
- `asset_class`: `text`
- `symbols`: `text[]`
- `parameters`: `jsonb` (Template-specific config)
- `metrics_preferences`: `text[]` (List of metric keys for UI priority)
- `benchmark_symbol`: `text`
- `pinned`: `boolean` (Default: `false`)
- `deleted_at`: `timestamptz` (Nullable)
- `created_at`: `timestamptz`
- `updated_at`: `timestamptz`

### Alpha Constraints
- **Symbols**: Min 1, Max 5.
- **Asset Class**: All symbols must share the same asset class.
- **Side**: Long-only (Short is deferred).
- **Asset Classes**: `equity`, `crypto`, `currency_pair`.
- **Note**: Strategies may target multiple symbols but only within the same `asset_class`.

> [!TIP]
> **Global Rule**: Collections may mix asset classes organizationally. Backtest runs may not mix asset classes operationally.

### Notes
- Strategies can be created directly or derived from a chat conversation.
- Display metrics are derived from the most recent `backtest_runs`, not stored statically here.
---

# 10. collections

Collections grouping related strategies. These serve as lightweight organizational themes in Alpha.

### Fields
- `id`: `uuid` (Primary Key)
- `user_id`: `uuid` (References `profiles.id`)
- `name`: `text`
- `name_source`: `text` (Default: `'system_default'`)
- `description`: `text` (Nullable)
- `pinned`: `boolean` (Default: `false`)
- `deleted_at`: `timestamptz` (Nullable)
- `created_at`: `timestamptz`
- `updated_at`: `timestamptz`

### Notes
- Collections do **not** perform aggregate portfolio simulations in Alpha.
- They help users organize strategies by theme (e.g., "Tech Growth", "Crypto Dips").
- **Asset Mixing**: Collections may contain both Equity and Crypto strategies, but they cannot be executed as a mixed-asset batch.
---

# 11. collection_strategies

Join table mapping strategies to collections.

### Fields
- `id`: `uuid` (Primary Key)
- `collection_id`: `uuid` (References `collections.id` ON DELETE CASCADE)
- `strategy_id`: `uuid` (References `strategies.id` ON DELETE CASCADE)
- `user_id`: `uuid` (References `profiles.id` ON DELETE CASCADE)
- `created_at`: `timestamptz`

### Constraints
- `UNIQUE(collection_id, strategy_id)`
---

# 12. backtest_runs

Represents an immutable result of a simulation. Every run is reproducible from its `config_snapshot`.

### Fields
- `id`: `uuid` (Primary Key)
- `user_id`: `uuid` (References `profiles.id`)
- `conversation_id`: `uuid` (Nullable)
- `strategy_id`: `uuid` (Nullable)
- `status`: `text` (Default: `'queued'`)
- `asset_class`: `text`
- `symbols`: `text[]`
- `allocation_method`: `text` (Default: `'equal_weight'`)
- `benchmark_symbol`: `text`
- `config_snapshot`: `jsonb` (The exact parameters used for the run)
- `metrics`: `jsonb` (Canonical machine-readable results)
- `conversation_result_card`: `jsonb` (UI-friendly presentation object)
- `chart`: `jsonb` (Historical equity curve, detail-only)
- `trades`: `jsonb` (List of individual trades, detail-only)
- `error`: `jsonb` (Error details if status is `failed`)
- `created_at`: `timestamptz`
- `updated_at`: `timestamptz`

### Enums
- **status**: `queued`, `running`, `completed`, `failed`
- **allocation_method**: `equal_weight`

### Notes
- Runs are immutable after completion.
- `benchmark_symbol` is derived from `asset_class` defaults in Alpha (`SPY` for equities, `BTC` for crypto, tested pair for currency pairs).
- `metrics.aggregate.performance.portfolio_value_range` stores aggregate strategy portfolio equity close peak/lowest values for the run period.
- `chart` stores the aggregate portfolio equity curve, its matching `value_summary`, and capped executed-fill markers used by the result card. Multi-symbol runs store the portfolio curve, not separate comparison series.
- Direct run rows store the normalized engine config directly in
  `config_snapshot`; chat-launched rows may include
  `config_snapshot.engine_config` with the exact normalized engine config
  executed by the launch adapter. This replay payload is canonical when present.
- Benchmark comparisons are persisted only when benchmark observations cover the
  selected window sufficiently; late, early-ending, or sparse benchmark data
  should fail as data unavailable rather than being silently backfilled.
- Legacy persisted chart payloads may include `value_extrema`; readers may use it
  as a fallback, but new run writers should persist `value_summary`.
- `trades` may mirror chart event markers for lightweight UI hydration. Detailed execution ledgers can preserve signals, order intents, fills, ignored signals, and position snapshots, but list endpoints must expose only lightweight result metadata.
- Saved strategies must be created from completed run state or an equivalent canonical result snapshot, not reconstructed from frontend display text.
- Follow-up refinements from a result card must be seeded from
  `config_snapshot` or equivalent canonical run metadata. A user's partial
  change request may update the relevant field, but omitted run fields such as
  symbols, contribution amount, cadence, timeframe, benchmark, and strategy
  template must carry forward unless explicitly changed or invalidated by
  deterministic guardrails.
- P1 completed chat backtests also attach sidecar evidence metadata to
  `conversation_result_card`:
  - `idea_id`
  - `idea_version_id`
  - `evidence_artifact_id`
  - `evidence_lifecycle`
  - `artifact_type = "backtest"`
  - `decision_note_id` and `decision_state` after explicit decision capture.
  These fields are stable codes/ids, not localized display prose.
---

## 12.1 P1 Idea / Evidence / Decision Spine

P1 adds a light evidence ledger around completed backtests. Persistence is
automatic; user commitment is explicit.

### ideas

Represents a durable investing idea container.

Fields:
- `id`: `uuid` (Primary Key)
- `user_id`: `uuid` (References `profiles.id` ON DELETE CASCADE)
- `source_conversation_id`: `uuid` (Nullable, references `conversations.id`)
- `title`: `text`
- `summary`: `text`
- `lifecycle`: `text` (`captured`, `reviewed`, `saved`, `decided`, `archived`, `discarded`)
- `active_version_id`: `uuid` (Nullable, references `idea_versions.id`)
- `created_at`: `timestamptz`
- `updated_at`: `timestamptz`

Creation order:
- Insert the idea with `active_version_id = null`.
- Insert the corresponding `idea_versions` row.
- Update `ideas.active_version_id` to the inserted version id.

This ordering keeps the circular idea/version relationship compatible with
Supabase FK enforcement. If artifact creation fails after either sidecar is
created, the gateway discards the transient idea/version sidecars and re-checks
`UNIQUE(user_id, source_run_id)` before surfacing an error, so worker retries do
not leave orphaned evidence records.

### idea_versions

Immutable snapshot of an idea at the point evidence was created.

Fields:
- `id`: `uuid` (Primary Key)
- `idea_id`: `uuid` (References `ideas.id` ON DELETE CASCADE)
- `user_id`: `uuid` (References `profiles.id` ON DELETE CASCADE)
- `source_conversation_id`: `uuid` (Nullable, references `conversations.id`)
- `source_run_id`: `uuid` (Nullable, references `backtest_runs.id`)
- `version_number`: `integer`
- `canonical_spec`: `jsonb`
- `strategy_snapshot`: `jsonb`
- `title`: `text`
- `summary`: `text`
- `lifecycle`: `text`
- `created_at`: `timestamptz`

### evidence_artifacts

Immutable proof package. P1 writes `artifact_type = "backtest"` from completed
backtests.

Fields:
- `id`: `uuid` (Primary Key)
- `idea_id`: `uuid` (References `ideas.id` ON DELETE CASCADE)
- `idea_version_id`: `uuid` (References `idea_versions.id` ON DELETE CASCADE)
- `user_id`: `uuid` (References `profiles.id` ON DELETE CASCADE)
- `source_conversation_id`: `uuid` (Nullable, references `conversations.id`)
- `source_run_id`: `uuid` (Nullable, references `backtest_runs.id`)
- `artifact_type`: `text` (`backtest`)
- `lifecycle`: `text`
- `title`: `text`
- `digest`: `text`
- `payload`: `jsonb`
- `created_at`: `timestamptz`
- `updated_at`: `timestamptz`

Payload rules:
- `payload.result_card` is sanitized for recall and must not expose context
  packets, provider/model metadata, route receipts, retry payloads, or raw
  conversation transcripts.
- `payload.assumptions`, `payload.metrics`, `payload.provenance`,
  `payload.digest`, and when available `payload.quick_take` and
  `payload.breakdown` are first-class evidence context, not frontend-only copy.
- Search previews derive from this sanitized evidence payload and may expose
  digest, symbols, benchmark, assumptions, compact metric summaries, quick take,
  and breakdown context. Search previews must not expose internal ids inside
  `preview`; object identity remains on the top-level search result fields.
- `UNIQUE(user_id, source_run_id)` keeps completed-run capture idempotent.
  Replays or worker restarts must reuse the existing sidecar instead of
  creating another evidence artifact for the same completed run.

### decision_notes

Explicit user judgment after reviewing evidence. P1 stores the current decision
for an evidence artifact, not an append-only decision history. A later slice may
add history if the product needs audit trails.

Fields:
- `id`: `uuid` (Primary Key)
- `idea_id`: `uuid` (References `ideas.id` ON DELETE CASCADE)
- `idea_version_id`: `uuid` (References `idea_versions.id` ON DELETE CASCADE)
- `evidence_artifact_id`: `uuid` (References `evidence_artifacts.id` ON DELETE CASCADE)
- `user_id`: `uuid` (References `profiles.id` ON DELETE CASCADE)
- `source_conversation_id`: `uuid` (Nullable, references `conversations.id`)
- `decision_state`: `text` (`watching`, `promising`, `rejected`, `revisit_later`)
- `note`: `text` (Nullable)
- `created_at`: `timestamptz`
- `updated_at`: `timestamptz`

Constraints:
- `UNIQUE(user_id, evidence_artifact_id)` enforces one current decision per
  user-owned evidence artifact.
- Duplicate POST/retry semantics update the existing decision row and return the
  canonical current decision.

Durable decision capture:
- The API uses the service-role-only `upsert_current_decision_note` RPC so the
  decision row, evidence artifact lifecycle, idea lifecycle, and active
  idea-version lifecycle move to `decided` together.
- The RPC is not a public/client surface. Frontend code only calls
  `POST /evidence-artifacts/{id}/decision`.

### RLS

All four P1 tables are owner-scoped by `user_id`. Select, insert, update, and
delete policies require `auth.uid() = user_id`. Backend P1 persistence uses the
service role server-side; service-role grants do not relax frontend/client RLS.

## 12.1.1 P1 Observability Envelope

P1 defines the private-alpha observability envelope in code without adding a new
durable analytics or cost table in this slice.

Current behavior:
- `argus_observability_event/v1` is the canonical event-envelope schema.
- Default privacy mode is `metadata_only`.
- Event categories include chat interpretation, continuity, evidence capture,
  decision capture, recall, cost-ledger entries, and eval-suite readiness.
- The sanitizer strips raw prompts, transcripts, context packets, route
  receipts, provider/model metadata, auth tokens, API keys, broker credentials,
  account balances, exact holdings, payment identifiers, and similar sensitive
  payloads.
- Live analytics capture is suppressed with `reason = "p1_measurement_only"`.

Deferred durable surfaces:
- PostHog product analytics wiring.
- Append-only provider cost ledger.
- Eval run/case result persistence.
- Route-receipt to cost/eval/product-event joins beyond existing product
  records.

## 12.2 backtest_jobs

Represents durable lifecycle state for an asynchronous backtest execution job.
Jobs are the bridge between the chat/API control plane and the Render Workflow
execution plane.

`backtest_jobs` is not the canonical result record. Successful jobs write a
canonical immutable `backtest_runs` row and reference it through
`result_run_id`.

### Fields
- `id`: `uuid` (Primary Key)
- `user_id`: `uuid` (References `profiles.id`)
- `conversation_id`: `uuid` (References `conversations.id`)
- `request_message_id`: `uuid` (Nullable, references `messages.id`)
- `confirmation_message_id`: `uuid` (Nullable, references `messages.id`)
- `idempotency_key`: `text` (Nullable)
- `payload_hash`: `text`
- `launch_payload`: `jsonb`
- `status`: `text`
- `priority`: `text` (Default: `'normal'`)
- `attempts`: `integer` (Default: `0`)
- `max_attempts`: `integer` (Default: `1`)
- `queued_at`: `timestamptz`
- `started_at`: `timestamptz` (Nullable)
- `finished_at`: `timestamptz` (Nullable)
- `result_run_id`: `uuid` (Nullable, references `backtest_runs.id`)
- `failure_code`: `text` (Nullable)
- `failure_detail`: `text` (Nullable)
- `retryable`: `boolean` (Default: `false`)
- `execution_metadata`: `jsonb` (Default: `{}`)
- `created_at`: `timestamptz`
- `updated_at`: `timestamptz`

### Enums
- **status**: `queued`, `running`, `succeeded`, `failed`, `canceled`, `expired`
- **priority**: `normal` initially; future values may support admin or canary
  jobs.

### Failure Semantics
Job lifecycle status is separate from engine/runtime failure semantics.

- `status` answers where the job is in its lifecycle.
- `failure_code` is a stable machine code such as `market_data_unavailable`,
  `invalid_date_range`, `unsupported_indicator`, or `workflow_timeout`.
- `failure_detail` is a user-safe grouping such as `market_data_issue`,
  `invalid_date_window`, `unsupported_rule`, or `execution_failed`.
- `retryable` is computed from the failure category, failure code, attempts, and
  whether an intent-preserving corrected payload exists.
- `execution_metadata` may store private operational evidence such as workflow
  run id, cache hit/miss, provider fetch duration, compute duration, attempt
  count, and source error kind.

Unknown failures default to `failed`, `failed_internal` semantics,
`retryable=false`, and a safe generic user message until a new stable
`failure_code` is intentionally added.

### Notes
- Jobs are idempotent by user and payload/idempotency key.
- The UI must hydrate queued/running/succeeded/failed/canceled/expired state
  from durable rows, not frontend-invented state.
- The current private-alpha UI hydrates status through the API polling endpoint;
  Supabase Realtime remains the selected target transport once the workflow path
  is stable enough to add subscriptions.
- API SSE remains request-scoped and should not be used as a long-lived stream
  for workflow-duration jobs.

---

# 13. Backtest Metrics Shape

Backtest results use a standardized nested shape.

```json
{
  "aggregate": {
    "performance": {},
    "risk": {},
    "efficiency": {}
  },
  "by_symbol": {
    "AAPL": {
      "performance": {},
      "risk": {},
      "efficiency": {}
    }
  }
}
```

### Notes
- Multi-symbol aggregate metrics use equal weighting.
- `by_symbol` allows AI follow-ups like *"Why did the Tesla strategy underperform in 2023?"*
- Aggregate metrics for grouped symbols compare against the class benchmark:
  - Equity groups vs **SPY**
  - Crypto groups vs **BTC** (excluding stablecoins)
  - Currency-pair groups vs the tested pair itself
---

# 14. usage_counters

Tracks resource consumption for quotas and limits.

### Fields
- `id`: `uuid` (Primary Key)
- `user_id`: `uuid` (References `profiles.id`)
- `resource`: `text` (e.g., `backtest_runs`, `backtest_jobs`, `chat_messages`)
- `period`: `text` (e.g., `hour`, `day`)
- `period_start`: `timestamptz`
- `period_end`: `timestamptz`
- `used_count`: `integer` (Default: `0`)
- `limit_count`: `integer`
- `updated_at`: `timestamptz`
- `created_at`: `timestamptz`

### Constraints & Indexes
- **Unique Logic**: `UNIQUE(user_id, resource, period, period_start)`
- **Lookup Index**: `(user_id, resource, period_start DESC)`
- **Cleanup Index**: `(period_end)`

### Alpha Enums
- **Resource**: `chat_messages`, `backtest_runs`, `backtest_jobs`, `feedback`
- **Period**: `hour`, `day`

### Notes
- Usage counters are operational safety data, not monetization data in Alpha.

---

# 15. feedback

Stores user-submitted bug reports, feature requests, general feedback, and
private-alpha support requests such as account deletion requests.

### Fields
- `id`: `uuid` (Primary Key)
- `user_id`: `uuid` (Nullable, references `profiles.id`)
- `type`: `text` (e.g., `bug`, `feature`)
- `message`: `text`
- `context`: `jsonb` (Default: `{}`)
- `created_at`: `timestamptz`

### Enums
- **type**: `bug`, `feature`, `general`, `account_deletion_request`
---

# 16. Soft Delete & Archive Rules

### Soft Delete
Used for **conversations**, **strategies**, and **collections**. These items should be filtered out by default but remain in the DB for "Recently Deleted" recovery.

### Archive
Used specifically for **conversations** to hide them from the primary sidebar without deleting the data.
---

# 17. Recents / History Model

Recents is a mixed-type feed displaying activity across the platform.

### Supported Types
- `chat`
- `strategy`
- `collection`
- `run`

### Standard History Shape
```json
{
  "type": "chat",
  "id": "uuid",
  "title": "Tesla dip thread",
  "subtitle": "Last message or metric preview",
  "pinned": false,
  "created_at": "timestamp"
}
```
---

# 18. Search Model

Alpha supports keyword-based search across core entities.

### Scope
- **Surface Search**: Filter-by-type search (e.g., searching only Strategies).
- **Global Search**: Omni-search spanning Conversations, Strategies, and Collections.

### Future
Semantic search using embeddings is deferred until post-Alpha.
- Do not add embedding or pgvector tables for the production readiness chat/backtest branch.
- Use structured Supabase records, run metadata, saved strategies, and keyword search until Argus needs semantic recall across large histories.

---

# 19. RLS Ownership Rules

Every user-owned table must enforce strict Row Level Security (RLS).

### Primary Rule
- Users may only `SELECT`, `UPDATE`, or `DELETE` rows where `user_id = auth.uid()`.

### Tables Requiring RLS
- `private_alpha_allowlist`, `profiles`, `conversations`, `messages`, `strategies`, `collections`, `collection_strategies`, `backtest_jobs`, `backtest_runs`, `feedback`, `usage_counters`.

### Private Alpha Allowlist
- No `anon` or `authenticated` role access is required.
- Backend service-role access checks the table before auth signup/login.

---

# 20. Indexing Requirements

### Critical Performance Indexes
- **private_alpha_allowlist**: `(email)` with active-row partial index
- **profiles**: `(id)`, `(username)`
- **conversations**: `(user_id, updated_at DESC)`, `(user_id, archived, deleted_at)`, `(user_id, pinned)`
- **messages**: `(conversation_id, created_at DESC)`
- **strategies**: `(user_id, updated_at DESC)`, `(user_id, pinned)`, `(user_id, deleted_at)`
- **strategies (gin)**: `USING gin(symbols)`
- **collections**: `(user_id, updated_at DESC)`, `(user_id, pinned)`, `(user_id, deleted_at)`
- **collection_strategies**: `(collection_id)`, `(strategy_id)`
- **backtest_jobs**: `(user_id, status, queued_at DESC)`, `(conversation_id, created_at DESC)`, `(result_run_id)`
- **backtest_jobs unique/idempotency**: `(user_id, idempotency_key)` where `idempotency_key is not null`
- **backtest_jobs payload lookup**: `(user_id, payload_hash, created_at DESC)`
- **backtest_runs**: `(user_id, created_at DESC)`, `(conversation_id)`, `(strategy_id)`
- **backtest_runs (gin)**: `USING gin(symbols)`
- **feedback**: `(user_id, created_at DESC)`
- **usage_counters**: `(user_id, resource, period_start DESC)`
- **usage_counters**: `(period_end)`
- **usage_counters unique**: `(user_id, resource, period, period_start)`
---

# 21. Naming & Title Defaults

AI-generated names and titles are the default for conversations, strategies, and collections.

### Source Tracking
- `system_default`: The initial placeholder before AI processing.
- `ai_generated`: Set after the AI generates a context-aware title.
- `user_renamed`: Set if the user manually overrides the title.

*Note: AI must never overwrite a `user_renamed` entry.*

---

# 22. Usage Controls, Quotas, and Limits

Argus Alpha MVP implements three defensive layers to protect system stability and manage compute/LLM costs while maintaining a generous user experience. These are "fair use" guardrails, not monetization tiers.

### Layer 1: Engine Constraints
Hard-coded technical limits in the backtesting logic.
- **Symbols**: Max 5 symbols per run.
- **Timeframe**: 1h, 2h, 4h, 6h, 12h, 1D.
- **Provider windows**: Stored run configs must reflect provider-available history for the selected asset class and timeframe. Alpaca equity history starts in 2016 for the launch path; Kraken OHLC currency-pair windows are limited to the latest 720 candles for the requested interval.
- **Capital**: Min 1,000 / Max 100,000,000.
- **Side**: Long-only.

### Layer 2: Rate Limits
Short-window protection against abuse or runaway UI loops.
- **Backtests**: Max 10 per hour.
- **Chat**: Max 60 messages per hour.
- **Feedback**: Max 20 submissions per hour.
- **Unauthenticated auth attempts**: Login max 8 attempts and signup max 5 attempts per 10 minutes, keyed by endpoint plus client IP/email. This is an alpha abuse guard before provider calls, not a replacement for Supabase Auth protections.
- **Mechanism**: Enforced via standard `Retry-After` headers.

### Layer 2.5: Backtest Concurrency
Durable job backpressure protects the chat API from compute spikes.
- **Per user**: 1 running backtest, 2 queued backtests.
- **Global**: 5 running backtests, 10 queued backtests.
- **Mechanism**: Enforced against `backtest_jobs` before creating or starting a
  new workflow job.

### Layer 3: Daily / Rolling Quotas
Generous usage boundaries tracked via the `usage_counters` table.
- **Backtest Runs**: 50 per day.
- **Chat Messages**: 200 per day.
- **Feedback**: 50 submissions per day.

---

# 23. Backend Enforcement Model

### Enforcement Flow
1. **Authenticate**: Resolve `user_id` from session.
2. **Hard Constraints**: Validate `backtest_run` inputs against Engine Constraints.
3. **Check Counters**: Query `usage_counters` for applicable resource/period.
4. **Check Job Backpressure**: Query `backtest_jobs` for per-user and global
   queued/running limits before creating a workflow job.
5. **Exceedance Policy**:
   - If rate limit exceeded: Return `429 Too Many Requests`.
   - If daily quota exhausted: Return `429` (Alpha policy).
   - If job backpressure limit is hit: return a product-safe queued/try-later
     response instead of starting unbounded compute.
6. **Execute**: Create a durable job and trigger workflow execution.
7. **Increment**: Update/Insert the `usage_counters` row.
8. **Response**: Return result or job state. Include rate-limit headers only
   when they are backed by an active limiter; do not emit placeholder quota
   values.

### Admin Bypass
Users with `profiles.is_admin = true` may have quota and rate-limit checks bypassed by backend logic.
- Ownership and privacy rules still apply.
- Engine safety constraints (e.g., symbol limits) may still apply.

---

# 24. Historical State & Reproducibility (SCD)

Full Slowly Changing Dimension (SCD) systems (e.g., Type 2 historical tracking) are **NOT required for Alpha MVP**.

### Historical Strategy
- **Overwrite (SCD Type 1)**: User profiles and metadata are updated in place.
- **Reproducibility**: Rather than tracking history in the `strategies` table, every `backtest_run` preserves the exact inputs in `config_snapshot`. This ensures a run's results are always tied to its execution-time state.
- **Future Growth**: If strategy versioning becomes central, a `strategy_versions` table can be added without breaking the core model.

### Product Philosophy
"Protect the system without making legitimate exploration feel constrained."
- Real users should comfortably test multiple ideas per session.
- Abusive loops and bot activity must be blocked.
- Limits are operational defaults, not permanent product promises.

---

# 25. Data Model Decision Filter

When adding or changing a table, ask:

> *Does this store durable truth, recovery state, or useful research memory without turning context into simulation truth?*

If no, it likely should wait for post-Alpha.
