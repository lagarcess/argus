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
chat_turn_lifecycles
strategies
collections
collection_strategies
backtest_jobs
backtest_runs
ideas
idea_versions
evidence_artifacts
decision_notes
cost_ledger_entries
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
   │      ├── chat_turn_lifecycles
   │      ├── backtest_jobs
   │      └── backtest_runs
   │
   ├── ideas
   │      ├── idea_versions
   │      │      └── evidence_artifacts
   │      └── decision_notes
   │
   ├── strategies
   │      ├── backtest_runs
   │      └── collection_strategies
   │
   ├── collections
   │      └── collection_strategies
   │
   ├── cost_ledger_entries
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
- Private-alpha signup persists `language` and its server-derived `locale` in
  the profile creation path. Browser detection is only a pre-auth hint; after
  authentication this row is authoritative and no frontend repair update is
  required.
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
- Message identity, owner, conversation, role, content, and ordering are
  immutable in Alpha. Narrow artifact metadata enrichments may update
  `metadata`, but they must not change message identity or ordering.
- Every durable message append uses the service-role-only
  `append_conversation_message` RPC. The function locks the owned conversation
  row, inserts the message, and updates `last_message_preview` in one
  transaction. `PUBLIC`, `anon`, and `authenticated` cannot execute the
  function or mutate `messages` directly.
- Conversation message order is deterministic by `(created_at DESC, id DESC)`.
  Under the conversation lock, a new append receives `created_at` at least one
  microsecond newer than the current maximum. Metadata-only updates do not
  change `created_at` or `id`, so they cannot promote an older message into the
  latest response-option source.
- A response-option request uses the same RPC as an atomic admission boundary.
  It matches the owner, conversation, exact latest assistant id, canonical
  metadata snapshot, option id, and replacement values before inserting the
  preallocated request id. An exact replay returns the existing request and the
  source immediately preceding it without inserting a duplicate; a stale or
  mismatched claim returns no row.
- `metadata` stores token usage, model identifiers, latency, and tool execution traces.
- Every terminal assistant message for an ordinary non-backtest chat turn stores
  immutable `metadata.agent_runtime_turn.turn_id`, `request_id`, `terminal`, and
  terminal `status`. These values match its `chat_turn_lifecycles` row and make
  terminal evidence discoverable if the lifecycle CAS does not complete.
- Message metadata may contain reloadable chat artifacts such as
  `pending_strategy`, `confirmation_card`, `confirmation_payload`,
  `result_card`, result identifiers, `chat_action`, `failed_action`,
  `retry_last_turn`, `recovery`, and `clarification`. These fields hydrate the
  transcript, action affordances, and localized degraded-fallback UI; they do
  not make free-form transcript text the source of truth for strategy state.
  A typed `clarification.prompt_source` distinguishes exact LLM-authored prose
  (`llm_generated`) from frontend-localized deterministic fallback
  (`degraded_fallback`); structured options remain reloadable in both cases.
  Degraded fallback `content` remains stored only as compatibility transport;
  it is not projected into later model history or `last_message_preview`, so
  Recents and conversation search do not expose the fallback language. Exact
  `llm_generated` prose remains eligible for those continuity surfaces.
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

## 8.1 chat_turn_lifecycles

Represents one mutable current-state recovery record for each accepted ordinary
chat turn: any `POST /api/v1/chat/stream` request not admitted as
`chat.run_backtest`. Run actions use `backtest_jobs` instead. This table is not a
second job queue, transcript, event ledger, or LangGraph state store. Messages
remain immutable; message reads project the current lifecycle row into
`metadata.agent_runtime_turn` without rewriting the message.

### Fields
- `turn_id`: `uuid` (Primary Key and reference to the accepted user
  `messages.id`; this is also the `request_message_id`)
- `user_id`: `uuid` (References `profiles.id` ON DELETE CASCADE)
- `conversation_id`: `uuid` (References `conversations.id` ON DELETE CASCADE)
- `assistant_message_id`: `uuid` (Nullable, unique, references `messages.id` ON
  DELETE SET NULL)
- `request_id`: `text` (The request correlation id used by responses, logs, and
  route-receipt metadata)
- `status`: `text`
- `reconciled_outcome`: `text` (Nullable)
- `failure_code`: `text` (Nullable, stable and user-safe)
- `retryable`: `boolean` (Default: `false`)
- `accepted_at`: `timestamptz`
- `running_at`: `timestamptz` (Nullable)
- `terminal_at`: `timestamptz` (Nullable)
- `reconciled_at`: `timestamptz` (Nullable)
- `created_at`: `timestamptz`
- `updated_at`: `timestamptz`

### Enums and constraints
- **status**: `accepted`, `running`, `completed`, `recoverable_failed`,
  `abandoned`, `reconciled`.
- **reconciled_outcome**: `completed` or `recoverable_failed`; required only
  when `status = reconciled` and null otherwise. No-proof recovery uses
  `status = abandoned` directly.
- `turn_id` makes lifecycle creation idempotent for the accepted user message.
- `assistant_message_id` is unique when present so one terminal assistant
  message cannot settle two turns.
- `abandoned` requires `assistant_message_id = null`; by definition no
  qualifying terminal assistant message settled that turn.
- Terminal statuses are `completed`, `recoverable_failed`, `abandoned`, and
  `reconciled`.

### Transition ownership and idempotency
- The user message and `accepted` row are created in one database-owned
  transaction after request admission succeeds.
- One database compare-and-set function locks the lifecycle row and permits only
  the transitions named in `docs/API_CONTRACT.md` under
  `contract-chat-turn-lifecycle`.
- Repeating the same target status, assistant-message link, failure code, and
  reconciliation outcome returns the current row as a no-op. A different
  terminal target is rejected.
- Route receipts correlate through the same `user_id`, `conversation_id`,
  `request_id`, and message ids; the lifecycle row does not duplicate receipt
  payloads.
- Owner-scoped RLS uses `auth.uid() = user_id`, and `authenticated` receives `SELECT` only. `INSERT`, `UPDATE`, and `DELETE` are revoked from `anon` and
  `authenticated`; lifecycle creation and transitions use the server-side
  transaction/CAS boundary only. Any database function used for that boundary
  also revokes execution from `PUBLIC`, `anon`, and `authenticated`. The
  frontend cannot mutate lifecycle state directly.

### Reconciliation boundary
- `accepted`/`running` rows become stale after 15 minutes according to database
  time and `stale_since = COALESCE(running_at, accepted_at)`.
- The next chat POST and conversation-message read reconcile at most 20 stale
  rows for that conversation in `stale_since ASC, turn_id ASC` order. Private
  alpha does not add a background sweeper.
- Qualifying terminal evidence is an immutable assistant message whose
  `user_id`, `conversation_id`, `metadata.agent_runtime_turn.turn_id`, and
  `metadata.agent_runtime_turn.request_id` match the lifecycle row, whose
  terminal flag is true, and whose terminal status is `completed` or
  `recoverable_failed`.
- Candidates use `created_at ASC, outcome_precedence ASC, id ASC`, with failure
  precedence 0 and completed precedence 1. The first candidate wins and becomes
  `assistant_message_id`; its status becomes `reconciled_outcome`. Checkpointer
  state may corroborate that message but cannot prove a terminal user-visible
  outcome alone. With no qualifying message, the row becomes `abandoned` with
  `failure_code = turn_abandoned`.
- For `abandoned`, the read-time projection belongs to the accepted user message
  whose `id = turn_id`. It overlays terminal lifecycle, `turn_abandoned`
  recovery, and typed `retry_last_turn` metadata without changing the immutable
  message row. The frontend places the presentation-only recovery row directly
  after that user message; the API does not create or persist an assistant
  message for this projection.

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
- New chart writers also persist two optional additive objects inside the same
  immutable `chart` JSON: `exploration_policy` (generic range-eligibility hints
  resolved from the strategy capability: `minimum_visible_observations`,
  optional `minimum_meaningful_duration`) and `marker_summary` (exact
  `total_groups`/`included_groups`/`sampled` marker-cap evidence). Legacy rows
  omit both fields and remain valid; readers degrade to observation-only range
  behavior and make no marker-completeness claim. No migration is required, and
  these fields never change execution, metrics, or the effective window.
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
- When execution realism is enabled and the engine models nonzero fees/slippage,
  `conversation_result_card.execution_costs` stores structured result evidence:
  `fee_bps`, `slippage_bps`, gross/net total return, return drag, and benchmark
  cost treatment. Idealized runs omit this object.
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
- Local/in-process and Render Workflow writers pass a stable, preallocated run
  id into the same typed finalizer. Finalization commits the completed run,
  Idea, IdeaVersion, EvidenceArtifact, and result-card identity as one logical
  transaction. Readers must not observe a run as completed before that tuple is
  finalized, and retries must reuse the same run id.
- Reload reconciliation projects a succeeded job from that canonical finalized
  tuple. Its result-card evidence identity and any decision note/state remain
  attached to the same owner-scoped run, rather than being rebuilt from display
  copy or a stale queued-job projection.
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

Immutable material experiment definition that evidence can reference.

Version boundary:
- One `IdeaVersion` represents one material experiment definition.
- Material changes to the traded assets, date range, benchmark, strategy or
  executable rules, cadence, capital, or modeled fees/slippage create a new
  version linked to the same `Idea`.
- Multiple edits before one confirmed run collapse into one new version.
- Wording changes, explanations, retries, and abandoned edits do not create
  versions.
- An updated date range is a material change. Its new run/evidence belongs to a
  new version so Argus can compare performance and assumptions with the prior
  version.

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

DB immutability:
- After insert, immutable fields are enforced by a database trigger:
  `id`, `user_id`, `idea_id`, `source_conversation_id`, `source_run_id`,
  `version_number`, `canonical_spec`, `strategy_snapshot`, `title`, `summary`,
  and `created_at`.
- `lifecycle` may change for review, save, archive/discard, and decision
  transitions without creating a new version row.

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

DB immutability:
- After insert, immutable fields are enforced by a database trigger:
  `id`, `user_id`, `idea_id`, `idea_version_id`, `source_conversation_id`,
  `source_run_id`, `artifact_type`, `title`, `digest`, `payload`, and
  `created_at`.
- `lifecycle` and `updated_at` may change for lifecycle transitions and
  timestamp bookkeeping.

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
- Evidence search and recall require the source run's finalized identity. An
  incomplete finalization is not eligible for conversation reload, history, or
  Omnisearch, even if metric computation already finished.
- A rerun on fresher provider data may create a new immutable
  `EvidenceArtifact` on the same `IdeaVersion` only when the canonical experiment
  definition is unchanged. The artifact must retain its own run identity,
  data-through/freshness provenance, metrics, and timestamps.
- Freshness comparison may use multiple evidence artifacts from the same
  version or evidence from successive material versions. It must not overwrite
  historical evidence.
- Research/news context is not part of the implemented P1 table contract.
  A later freshness/research slice may attach sanitized, source-backed context
  only after its artifact type, source, timestamp, and ownership contract are
  explicitly specified.

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

P1 defines the private-alpha observability envelope in code. Product events now
flow to PostHog, and B3 measurement slice 3 adds the first durable internal cost
ledger while keeping product analytics and eval-result persistence separate.

Current behavior:
- `argus_observability_event/v1` is the canonical event-envelope schema.
- Default privacy mode is `metadata_only`.
- Product-event categories emitted to PostHog are evidence capture, decision
  capture, recall usage, continuity mismatch, compare started, and eval
  readiness.
- The exact registered product-event name is carried as
  `attributes.product_event`; envelope `event_type` remains in the broader memo
  15.5 event taxonomy.
- The sanitizer strips raw prompts, transcripts, context packets, route
  receipts, provider/model metadata, auth tokens, API keys, broker credentials,
  account balances, exact holdings, payment identifiers, and similar sensitive
  payloads.
- Raw user, session, conversation, turn, message, job, and run identifiers are
  hashed in the PostHog projection.
- Live PostHog capture is enabled only when `POSTHOG_PROJECT_TOKEN` and an
  explicit PostHog region/host are present; missing token suppresses with
  `reason = "posthog_not_configured"`, and missing or unsupported region/host
  suppresses with `reason = "posthog_region_not_configured"`.
- PostHog is server-side only and personless (`$process_person_profile = false`).
- US Cloud is the current PostHog region choice for private alpha compliance
  posture.

Deferred durable surfaces:
- Eval run/case result persistence.
- Route-receipt to cost/eval/product-event joins beyond existing product
  records.

### cost_ledger_entries

Append-only operational spend records. This table is the first-party source for
provider/runtime cost attribution; PostHog is not the spend ledger.

Fields:
- `id`: `uuid` (Primary Key)
- `source`: `text` (`api_turn`, `render_workflow`, `eval_harness`,
  `manual_reconciliation`, `runtime_compute`, `storage`, `market_data`, `stt`,
  `research`)
- `service`: `text` (billing service, e.g. `openrouter`, `render`, `supabase`)
- `provider`: `text` (provider inside the service, e.g. `openrouter`, `alpaca`,
  `kraken`, `openai`, `elevenlabs`)
- `model`: `text` (Nullable; LLM/STT model when applicable)
- `feature_area`: `text` (e.g. `chat_runtime`, `result_readout`,
  `eval_readiness`)
- `task`: `text` (Nullable; OpenRouter task or future runtime task)
- `user_id`: `uuid` (Nullable, references `profiles.id` ON DELETE SET NULL)
- `conversation_id`: `uuid` (Nullable, references `conversations.id` ON DELETE SET NULL)
- `message_id`: `uuid` (Nullable, references `messages.id` ON DELETE SET NULL)
- `backtest_run_id`: `uuid` (Nullable, references `backtest_runs.id` ON DELETE SET NULL)
- `backtest_job_id`: `uuid` (Nullable, references `backtest_jobs.id` ON DELETE SET NULL)
- `route_receipt_id`: `uuid` (Nullable, references `route_receipts.id` ON DELETE SET NULL)
- `request_id`: `text` (Nullable)
- `correlation_id`: `text` (Required; joins cost records to a turn, run, or eval)
- `provider_request_id`: `text` (Nullable; for providers that return request ids)
- `upstream_id`: `text` (Nullable; future reconciliation id)
- `usage_metadata`: `jsonb` (Default: `{}`)
- `input_tokens`, `output_tokens`, `total_tokens`: `integer` (Nullable)
- `billable_unit`: `text` (`token`, `request`, `compute_second`,
  `audio_second`, `storage_byte`, `row`, `unknown`)
- `billable_quantity`: `numeric` (Nullable)
- `cost_amount`: `numeric` (Nullable)
- `cost_currency`: `text` (Default: `USD`)
- `cost_source`: `text` (`provider_reported`, `estimated`, `derived`,
  `reconciled`, `unavailable`)
- `latency_ms`: `integer` (Nullable)
- `status`: `text` (`succeeded`, `failed`, `skipped`, `estimated`,
  `reconciled`)
- `metadata`: `jsonb` (Default: `{}`)
- `occurred_at`: `timestamptz`
- `created_at`: `timestamptz`

Append-only rules:
- Product code may insert rows only. There are no update, upsert, delete, or
  frontend read paths in the private-alpha slice.
- The migration grants service-role `insert` and `select` only. RLS is enabled,
  and no `anon` or `authenticated` policies are added.
- Rollback is one reversible step: drop `public.cost_ledger_entries`.

Current write hooks:
- API chat turns append OpenRouter cost rows from persisted route receipts.
- Render workflow result-readout LLM calls append rows correlated to
  `backtest_job_id` and `backtest_run_id`.
- Eval harness judge calls can append rows with `source = "eval_harness"` and a
  stable eval correlation id.

Cost model notes:
- OpenRouter rows store provider-reported `usage.cost` when available and token
  counts in both dedicated columns and `usage_metadata`.
- Render, Supabase, market-data providers, STT providers, research/freshness
  providers, and future broker/export services may bill by request, compute
  time, storage, rows, audio duration, or provider reconciliation ids. The
  `billable_unit`, `billable_quantity`, `cost_source`, `provider_request_id`,
  and `upstream_id` fields are intentionally generic so those services can be
  added without changing the private-alpha chat runtime.
- Cost rows never store raw prompts, transcripts, credentials, balances,
  holdings, full audio, or frontend-only payloads.

## 12.2 backtest_jobs

Represents durable lifecycle state for a backtest execution job. Jobs bridge
the chat/API control plane to asynchronous Render Workflow execution and also
own the admitted synchronous direct compatibility path.

`backtest_jobs` is not the canonical result record. Successful jobs write a
canonical immutable `backtest_runs` row and reference it through
`result_run_id`.

### Fields
- `id`: `uuid` (Primary Key)
- `user_id`: `uuid` (References `profiles.id`)
- `conversation_id`: `uuid` (Nullable only for direct `backtests.run` admission;
  otherwise references `conversations.id`)
- `request_message_id`: `uuid` (Nullable, references `messages.id`)
- `confirmation_message_id`: `uuid` (Required for `chat.run_backtest`, null for
  `backtests.run`; references the retained immutable confirmation `messages.id`)
- `operation_scope`: `text` (`chat.run_backtest` or `backtests.run`)
- `idempotency_key`: `text` (Required, 1-128 visible ASCII characters)
- `identity_hash`: `text` (`sha256:` plus 64 lowercase hex characters for the
  operation's canonical identity object)
- `payload_hash`: `text` (`sha256:` plus 64 lowercase hex characters for the
  full normalized `LaunchBacktestRequest` payload)
- `launch_payload`: `jsonb`
- `status`: `text`
- `priority`: `text` (Default: `'normal'`)
- `attempts`: `integer` (Default: `0`)
- `max_attempts`: `integer` (Default: `1`)
- `queued_at`: `timestamptz` (Required for chat jobs; null for conforming direct
  jobs that never enter `queued`)
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
- **operation_scope**: `chat.run_backtest`, `backtests.run`
- **priority**: `normal` initially; future values may support admin or canary
  jobs.
- A new `chat.run_backtest` row starts `queued` with `queued_at` set and
  `started_at` null. Its `confirmation_message_id` is non-null and the linked
  message owns the confirmed `confirmation_id` and full `launch_payload_hash`
  for the job record's lifetime. A new `backtests.run` row starts `running` with
  `queued_at` and `confirmation_message_id` null and `started_at` set to the
  admission transaction timestamp.

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
- `succeeded` is valid only after `result_run_id` links to the fully finalized
  run/evidence tuple. A recoverable persistence-side failure uses
  `status = failed`, `failure_code = finalization_failed`, and
  `retryable = true`; `result_run_id` remains null until retry finalizes the
  stable run identity. `finalization_failed` is a failure code, not a new job
  status.

Unknown failures default to `failed`, `failed_internal` semantics,
`retryable=false`, and a safe generic user message until a new stable
`failure_code` is intentionally added.

A direct `backtests.run` row becomes stale when it remains `running` through
`started_at + interval '15 minutes'`. Before new direct admission and before an
owner-scoped direct-job read, the database-owned recovery path checks the stable
job-derived identity for a fully finalized Run/evidence tuple. A complete tuple
reconciles the job to `succeeded`. With no complete tuple, the same transaction
sets `status = failed`, `failure_code = direct_execution_abandoned`,
`failure_detail = execution_interrupted`, and `retryable = true`. Both terminal
transitions release running capacity immediately. The finalizer and stale
reconciler serialize on the same locked job row; after the stale failure wins,
late finalization cannot create or attach a public Run or replace the terminal
outcome.

### Notes
- Jobs are idempotent at
  `UNIQUE(user_id, operation_scope, idempotency_key)`. Exact retries return the
  current row before capacity/usage checks; a different `identity_hash` is a
  collision and never returns the old row.
- The reservation lasts for the durable job record's lifetime. A caller does
  not reuse the same key for a new execution after an elapsed retention window.
- Chat Run actions use `confirmation_id` as `idempotency_key`. Direct jobs may
  omit `conversation_id` so the existing direct request shape remains
  compatible, but they remain owner-scoped by `user_id`.
- `confirmation_message_id` is required for `chat.run_backtest` and the linked
  immutable confirmation artifact is retained for the job record's lifetime;
  direct `backtests.run` jobs keep this field null.
- For chat jobs, the confirmation artifact's `launch_payload_hash` is exactly
  the persisted `payload_hash`, not a shortened confirmation fingerprint.
- Direct admissions atomically start in `running` after both queued and running
  ceilings pass; new conforming direct jobs never enter `queued`.
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
- Unless a table-specific rule below is stricter, users may only `SELECT`,
  `UPDATE`, or `DELETE` rows where `user_id = auth.uid()`. Server-owned or
  immutable tables may revoke some of those operations; this default never
  grants a client write that a table-specific rule forbids.

### Chat-turn lifecycle
- `chat_turn_lifecycles` grants authenticated owners `SELECT` only. No client
  role may insert, update, delete, or execute its server transition function;
  the server-side persistence boundary owns every write.

### Tables Requiring RLS
- `private_alpha_allowlist`, `profiles`, `conversations`, `messages`,
  `chat_turn_lifecycles`, `strategies`, `collections`,
  `collection_strategies`, `backtest_jobs`, `backtest_runs`, `feedback`,
  `usage_counters`.

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
- **chat_turn_lifecycles**: `(conversation_id, status, updated_at)`,
  `(user_id, status, updated_at)`, unique `(assistant_message_id)` where not null
- **strategies**: `(user_id, updated_at DESC)`, `(user_id, pinned)`, `(user_id, deleted_at)`
- **strategies (gin)**: `USING gin(symbols)`
- **collections**: `(user_id, updated_at DESC)`, `(user_id, pinned)`, `(user_id, deleted_at)`
- **collection_strategies**: `(collection_id)`, `(strategy_id)`
- **backtest_jobs**: `(user_id, status, queued_at DESC)`, `(conversation_id, created_at DESC)`, `(result_run_id)`
- **backtest_jobs unique/idempotency**:
  `UNIQUE(user_id, operation_scope, idempotency_key)`
- **backtest_jobs payload lookup**: `(user_id, payload_hash, created_at DESC)`
- **backtest_jobs identity lookup**:
  `(user_id, operation_scope, identity_hash, created_at DESC)`
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
- **Mechanism**: The database-owned admission operation resolves idempotency,
  checks both scopes, charges one unique admission, and inserts the job
  atomically. Chat admission inserts `queued`; the synchronous direct path
  checks both queued and running ceilings and inserts `running`. Per-user
  exhaustion is evaluated before global exhaustion and returns
  `429 backtest_capacity_exceeded`; global exhaustion returns
  `503 backtest_capacity_exceeded`; both include `Retry-After: 15`.

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
3. **Atomic Admission**: In one database operation, resolve exact replay versus
   identity collision, check the applicable usage period plus per-user/global
   queued/running capacity, charge one unique simulation, and insert the job.
   Chat admission starts `queued`; direct admission starts `running`. The exact
   order is replay/collision, usage allowance, per-user capacity, global
   capacity, then insert plus charge.
4. **Exceedance Policy**:
   - If rate limit exceeded: Return `429 Too Many Requests`.
   - If daily quota exhausted: Return `429` (Alpha policy).
   - If per-user capacity is exhausted: return
     `429 backtest_capacity_exceeded` with `Retry-After: 15`.
   - If global capacity is exhausted: return
     `503 backtest_capacity_exceeded` with `Retry-After: 15`.
   - If the same reservation key carries a different identity: return
     `409 idempotency_conflict` without returning the old job.
5. **Execute**: Dispatch workflow execution, or run the admitted direct
   compatibility path synchronously, against the durable job.
6. **Response**: Return result or job state. Include rate-limit headers only
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
