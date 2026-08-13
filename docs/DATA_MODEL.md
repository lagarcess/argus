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
- legacy saved strategies (read compatibility only)
- legacy strategy collections (read compatibility only)
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
strategies                         # legacy read compatibility; no new writes
collections                        # legacy read compatibility; no new writes
collection_strategies               # legacy read compatibility; no new writes
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

Incubation-only, with no API/runtime/UI consumer:
```text
memory_settings
memory_candidates
memory_consent_actions
memory_records
memory_provenance
memory_prompt_history
memory_reconciliations
memory_provider_projections
memory_provider_cleanup
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
- `email`: `text` (Nullable only for a verified anonymous Auth user)
- `username`: `text` (Unique, Nullable)
- `display_name`: `text` (Nullable)
- `preferred_name`: `text` (Nullable; 1 to 40 characters when present)
- `language`: `text` (Default: `'en'`)
- `locale`: `text` (Default: `'en-US'`)
- `theme`: `text` (Default: `'dark'`)
- `avatar_theme`: `avatar_theme` enum (Default: `'ocean'`; one of `ocean`,
  `plum`, `teal`, `ember`, `gold`, `indigo`, or `slate`)
- `is_admin`: `boolean` (Default: `false`)
- `onboarding`: `jsonb` (legacy/inert; the applied migration defaults new rows
  to the historical shape below)
- `created_at`: `timestamptz`
- `updated_at`: `timestamptz`

### Legacy Onboarding Shape (inert compatibility state)

The explicit onboarding flow is removed. This column persists only because
existing rows carry it and removing it would be a destructive migration. No
product behavior reads it, and no API path writes it.

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
- `display_name` is an identity field. It is what the account is called.
- `preferred_name` is what Argus calls the user when it addresses them, and
  it is deliberately separate from `display_name`: people fill an identity
  field with a legal name. It is optional, and null means surfaces use no
  name. It is stated in settings and never inferred from conversation, so no
  runtime path writes it. A registered-account preference: restrictive
  policies read the trusted `is_anonymous` JWT claim to keep it off the guest
  surface, because anonymous Auth users share the `authenticated` role.
- `profiles.email` is null only for a verified anonymous Auth user. Permanent
  profiles require the verified provider email. Fake or placeholder guest
  addresses are forbidden.
- `username` is optional for Alpha. When supplied at signup, it is trimmed and
  case-folded before the case-insensitive uniqueness check and profile write.
  Same-email and same-username signup attempts are serialized across API
  instances so only the request that owns the available username may create an
  Auth user. An already-existing Auth email follows the provider's obfuscated
  duplicate path without a profile write or a username-dependent public error.
---

## 5.1 guest_workspaces

Server-owned policy record for one temporary anonymous identity.

### Fields
- `user_id`: `uuid` (Primary Key, references `profiles.id`)
- `conversation_id`: `uuid` (Unique, nullable, references `conversations.id`)
- `status`: `active`, `claiming`, `claimed`, or `expired`
- `created_at`: `timestamptz`
- `expires_at`: `timestamptz`
- `claimed_by`: `uuid` (Nullable, references `profiles.id`)
- `claimed_at`: `timestamptz` (Nullable)
- `updated_at`: `timestamptz`

### Invariants
- The owner must be a verified anonymous Supabase Auth user when the workspace
  is created.
- Exactly one workspace exists per anonymous owner and at most one
  conversation may bind to it.
- Expiry uses a fixed seven-day window after creation. Message, simulation, feedback, and
  conversation activity cannot extend it.
- Browser roles may read only their own active workspace and cannot mutate
  expiry, claim, or cleanup state.
- Cleanup locks `auth.users` and the workspace, re-verifies anonymous identity
  truth, removes the eligible graph, and deletes the Auth row in the same
  database transaction. A converted or permanent account is never eligible.
- Cleanup deletes conversation messages/jobs, guest feedback text, and the
  checkpoint rows whose `thread_id` matches the guest conversation before the
  transactional Auth deletion removes the remaining owner-scoped product rows.
  It also removes safely transferred source identities after a fifteen-minute
  reconciliation grace and abandoned bootstrap identities after five minutes.
  Privacy-safe append-only cost and route/security evidence may retain nullable
  attribution; transcript-bearing state may not.
- Guest Start over is one service-owned transaction. It locks the workspace,
  validates the complete conversation-owned graph, removes that graph and its
  checkpoint thread, and binds one new empty conversation to the same
  workspace. It does not replace the Auth identity, move `expires_at`, or reset
  any lifetime allowance or feedback counter. Append-only cost, route, security,
  and audit evidence is not rewritten.

---

## 5.2 guest_workspace_handoffs

Server-owned claim record for moving one anonymous workspace into one permanent
account created by signup or verified by login.

### Fields
- `id`: `uuid` (Primary Key)
- `secret_hash`: `text` (SHA-256 hex digest; the opaque secret is never stored)
- `source_user_id`: `uuid` (References the anonymous `profiles.id`)
- `destination_email_hash`: `text` (SHA-256 of the normalized destination
  email; required)
- `destination_user_id`: `uuid` (Nullable until a signup insert trigger or
  verified login resolves the permanent `auth.users.id`; cleared if that Auth
  user is deleted)
- `source_conversation_id`: `uuid` (References the one guest conversation)
- `pending_action`: `jsonb` (Nullable typed reason, conversation, action id, and
  decision artifact id when applicable)
- `handoff_kind`: `existing_account` or `new_account_signup`
- `status`: `pending`, `consumed`, or `revoked`
- `created_at`: `timestamptz`
- `expires_at`: `timestamptz` (Exactly ten minutes after creation for an
  existing-account handoff; the fixed guest workspace expiry for signup)
- `consumed_at`: `timestamptz` (Nullable)

### Invariants
- Browser roles cannot read or execute against this table. Only the service
  role may create or claim a handoff.
- A pending source workspace has at most one handoff.
- Preparing a signup handoff locks the source state, reuses the same pending row
  for a same-email retry, rotates its opaque-secret hash, and refuses to change
  the email after a destination Auth UUID is bound.
- A server-only proof in password-signup metadata binds the newly inserted
  non-anonymous Auth UUID in the same database transaction, then is removed
  from Auth metadata. A signup handoff never outlives its source workspace.
- Claim locks the handoff and complete source product graph, resolves the
  destination only from verified Auth email truth, verifies every foreign
  owner, and transfers all mutable product rows in one transaction.
- A consumed handoff remains a read-only replay oracle for the same bound
  destination when a signup or login response is lost. It never repeats the
  transfer or accepts another destination.
- Conversation, message, strategy, job/run, Idea/IdeaVersion, evidence,
  decision, and context ids do not change. Checkpoint rows keep
  `thread_id == conversation_id`.
- Guest counters and feedback are not merged into registered allowances.
  Immutable cost, provider, security, and audit evidence is not rewritten.
- Source anonymous Auth deletion occurs in bounded cleanup only after a
  fifteen-minute claim-reconciliation grace, and in the same transaction that
  re-verifies the source owns no transferred product row. Any claim or cleanup
  failure changes zero owners.

---

# 6. private_alpha_allowlist

Server-side access list for private alpha. This table is checked before signup
and login; it should not be exposed as a frontend product surface.

### Fields
- `email`: `text` (Primary Key, lowercased)
- `role`: `text` (Default: `user`)
- `language`: `text` (Default: `en`)
- `disabled_at`: `timestamptz` (Nullable)
- `created_at`: `timestamptz`
- `updated_at`: `timestamptz`

### Enums
- **role**: `admin`, `developer`, `user`, `requested`
- **language**: `en`, `es-419`

### Notes
- The public access-request endpoint may insert a missing `requested` row. It
  never updates an existing requested, approved, privileged, or disabled row.
- `requested` and unknown roles never grant permanent account access.
- The ops approval action loads an active requested row and stored language,
  sends the localized approval email first, and only then compare-and-sets
  `requested` to `user` while `disabled_at` remains null.
- There is no invite dashboard, referral system, public invite-code flow,
  pre-created Auth user, or password-setup flow.
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
- The one sanctioned in-place rewrite, a non-turn edit of a pending
  confirmation card, uses the service-role-only
  `update_conversation_message_artifact` RPC on the same serialized spine: it
  locks the owned conversation row and applies only while the caller's read
  still holds, comparing both the row's `metadata` and the conversation's
  latest message id (an empty result is the conflict signal, never a silent
  last-writer win). When the rewritten row is the conversation's latest
  message it carries `last_message_preview` with it while leaving
  `updated_at` untouched, so a non-turn change never reorders recents.
- A confirmation card's liveness truth lives on its own row:
  `metadata.confirmation_card.confirmation_state` (`active`, `consumed`,
  `cancelled`, `superseded`). Run admission stamps `consumed` through the
  guarded writer before dispatch; a run that dies without a result restores
  `active`; a cancelled or superseded card is never restored. Every
  liveness reader derives from one oracle over this field
  (`confirmation_card_is_dead`), with a compatibility clause for durable
  transcripts that predate the stamp and carry consumption only as later
  result messages. No reader may re-implement the predicate or infer
  liveness from job tables.
- Job success is one-way against the card lifecycle: both success writers
  (the worker's SQL update and the API gateway's PostgREST update) embed a
  predicate generated beside the card-restore classification in
  `argus.domain.backtest_job_lifecycle`, so success can only follow a state
  a worker legitimately holds (queued, running, or a re-claimable failure).
  A state the card was restored from can never convert into a result; a
  refused success write leaves the terminal state standing and is logged by
  its caller. This tightens a spine invariant so it can carry the
  consumption feature; the unguarded write was correct self-healing before
  cards were consumed at admission.
- Recent-window reads use `list_messages(newest_first_window=True)`: the
  newest N messages of the conversation restored to chronological order.
  An ascending read with a limit returns the head of the conversation and
  starves every recent-state reader on long conversations (#433).
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
  `retry_last_turn`, `recovery`, `clarification`, and the additive
  `discovery` sidecar (`argus_discovery/v1`: bounded sources, provider-resolved
  candidates, and unverified names for grounded asset discovery; the Search
  provider id is excluded by contract). These fields hydrate the
  transcript, action affordances, and localized degraded-fallback UI; they do
  not make free-form transcript text the source of truth for strategy state.
  A typed `clarification.prompt_source` distinguishes exact LLM-authored prose
  (`llm_generated`) from frontend-localized deterministic fallback
  (`degraded_fallback`); structured options remain reloadable in both cases.
  Degraded fallback `content` remains stored only as compatibility transport;
  it is not projected into later model history or `last_message_preview`, so
  Recents and conversation search do not expose the fallback language. Exact
  `llm_generated` prose remains eligible for those continuity surfaces.
- User-message `metadata.mentions` may additionally preserve a selected asset
  or indicator's optional `message_range: { start, end }`. This is a UTF-16
  display span into immutable `content`, stored only when it exactly matches
  that mention's `insert_text`. It lets the transcript render the selected
  occurrence of repeated text after reload. A missing or malformed range falls
  back to legacy best-effort display matching; it is not resolution provenance,
  runtime state, or an Omnisearch input, and needs no migration.
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
- Omnisearch may recall only `role = 'user'` message content. The partial
  `idx_messages_user_content_norm_trgm` GIN index uses the same checked-in
  Python 3.10-compatible normalized-content SQL expression as the bounded
  search reader and `extensions.gin_trgm_ops`. The index adds no function,
  view, grant, or RLS change; owner, active-conversation, guest-workspace, and
  exact-token rechecks remain query predicates before ranking and limits.
- A transcript jump reuses the owner-scoped message page read with
  `anchor_message_id`. The anchor is resolved inside the requested
  conversation, and the response remains capped at the requested page limit;
  it is not a transcript scan or a new durable memory record.
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

## 8.2 conversation_read_states

Stores one durable read boundary and optional manual-unread flag for an owned
conversation. It is not an event log and does not duplicate lifecycle, job,
message, or result content.

### Fields

- `user_id`: `uuid` (Part of the primary key; references `profiles.id` with
  update/delete cascade)
- `conversation_id`: `uuid` (Part of the primary key)
- `read_through_occurred_at`: `timestamptz` (Nullable)
- `read_through_source_kind`: `text` (`chat_turn` or `backtest_job`, nullable)
- `read_through_source_id`: `uuid` (Nullable)
- `manual_unread_at`: `timestamptz` (Nullable and independent of read-through)
- `created_at`: `timestamptz`
- `updated_at`: `timestamptz`

The three read-through fields are either all null or all non-null. Boundaries
compare as `(occurred_at, source_kind_rank, source_id)`, with `chat_turn = 1`
and `backtest_job = 2`, and advance monotonically. The primary key is
`(user_id, conversation_id)`. A composite foreign key to
`conversations(id, user_id)` uses `ON UPDATE CASCADE` and `ON DELETE CASCADE`,
so guest claim transfers the state and conversation cleanup removes it in the
same transaction.

Authenticated owners may select their row through RLS but cannot insert,
update, or delete it directly. Server-only RPCs own mutation, lock the
conversation/read/source rows, and revalidate terminal eligibility before
advancing a cursor. Read RPCs accept at most 100 owned conversation ids and the
activity reconciler settles at most 20 stale turns across that batch using the
existing lifecycle evidence predicate.

The migration baseline is idempotent and keyset-batched at 500 conversations.
It marks only the newest eligible terminal boundary at or before the captured
migration-start cutoff as read. Activity completing after that cutoff remains
unread. The baseline and later activity reads do not update conversation,
message, job, Run, artifact, or sort timestamps.

---

# 9. strategies

Legacy saved executable-idea record. The table remains owner-scoped and readable
so historical runs and history entries do not break; no active product path
creates, patches, restores, or deletes Strategy rows.

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
> **Global Rule**: Historical Collection rows may contain mixed asset classes.
> Backtest runs may not mix asset classes operationally, and no current flow
> creates or manages Collections.

### Notes
- Existing rows may still parent an owner-scoped direct backtest through
  `backtest_runs.strategy_id` compatibility.
- Display metrics on old rows remain readable; there is no Strategies surface.
---

# 10. collections

Legacy groupings retained only for owner-scoped historical reads.

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
- No active product path creates, patches, restores, deletes, attaches, or
  detaches Collection records.
- Collections do **not** perform aggregate portfolio simulations.
- **Historical asset mixing**: Existing rows may contain Equity, Crypto, and
  Currency Pair strategies, but they cannot be executed as a mixed-asset batch.
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
- Historical `strategy_id` linkage must be read from canonical stored records,
  never reconstructed from frontend display text.
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
- The public decision write contract accepts at most 500 note characters. The
  durable column remains nullable `text` so previously accepted longer notes
  stay readable; no migration or destructive truncation is introduced.

### Run dossier read projection

Run dossier history is not a table or durable summary. The
`GET /api/v1/conversations/{conversation_id}/run-dossiers` endpoint projects
existing owner-scoped records in this order:

`Conversation -> completed BacktestRun -> EvidenceArtifact -> current
DecisionNote (optional) -> assistant result message anchor (optional)`.

Only completed evidence-backed runs are eligible. Ordering and pagination use
the run's effective completion activity, `coalesce(updated_at, created_at)`,
then run id, newest first. `total_runs` and `decided_runs` are scalar
server-owned counts over the complete eligible set; clients never accumulate
them from pages. This projection creates no record, migration, revision log,
embedding, or generated recap.

Durable decision capture:
- The API uses the service-role-only `upsert_current_decision_note` RPC so the
  decision row, evidence artifact lifecycle, idea lifecycle, and active
  idea-version lifecycle move to `decided` together.
- The RPC is not a public/client surface. Frontend code only calls
  `POST /evidence-artifacts/{id}/decision`.
- Omnisearch recall uses the same bounded normalized-text pattern over the
  existing canonical `decision_state` and `note` fields. The
  `idx_decision_notes_recall_norm_trgm` GIN index adds no new durable memory
  record, function, view, grant, or RLS change; owner and conversation checks
  remain in the recall query before ranking and limits.
- Asset rollups use the existing maximum-five-symbol BacktestRun contract as
  an index boundary. `argus_search_symbol_casefold(text)` is a pure immutable
  SQL helper with Python 3.10 raw-casefold parity, and
  `idx_backtest_runs_owner_symbol_{1..5}_prefix` are owner-first partial
  B-tree expression indexes for completed non-null symbol slots. They add no
  table, recall record, view, grant, or RLS change. The reader resolves an
  exact or unique indexed prefix before evidence/decision lineage hydration.

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
- Grounded-discovery turns append one `source = "research"` row per attempted
  Search call with `feature_area = "discovery"`, provider identity, latency,
  and provider-reported or documented cost.
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

## 12.1.3 public_excerpt_snapshots

A public evidence receipt: an immutable, sanitized snapshot of one completed
backtest, created by its owner and revocable by its owner. Behind the default-off
`ARGUS_EVIDENCE_RECEIPT_SHARING_ENABLED` flag.

The pipeline is `EvidenceArtifact -> PublicExcerptSnapshot -> PublicExcerptView`.
The snapshot is frozen at creation and the public read never queries the source
conversation. Immutable means the numbers never move: re-running the idea later
produces a new artifact and leaves the receipt showing what it showed the day it
was shared.

Fields:
- `id`: `uuid` (Primary Key)
- `public_id`: `text` (Unique, `^[A-Za-z0-9_-]{22,64}$`, 24 bytes of urlsafe
  entropy; this is the url token)
- `owner_id`: `uuid` (References `profiles.id` ON DELETE CASCADE)
- `evidence_artifact_id`: `uuid` (Nullable, references `evidence_artifacts.id`
  ON DELETE SET NULL)
- `source_conversation_id`: `uuid` (Nullable, references `conversations.id`
  ON DELETE SET NULL)
- `source_run_id`: `uuid` (Nullable, references `backtest_runs.id`
  ON DELETE SET NULL)
- `title`: `text`
- `payload`: `jsonb` (the closed public payload; see below)
- `payload_digest`: `text` (`^[0-9a-f]{64}$`, sha256 over the canonical payload)
- `created_at`: `timestamptz`
- `revoked_at`: `timestamptz` (Nullable)
- `revocation_reason`: `text` (Nullable, `owner_revoked` or `source_deleted`)

The source references are `ON DELETE SET NULL` rather than cascade so a tombstone
outlives whatever it pointed at. They exist only for revocation and the owner's
audit list; the public read never selects them.

### Closed payload

`payload` carries exactly these keys and no others, enforced by `extra="forbid"`
on every model in `argus.api.public_excerpt_schemas`: `schema_version`,
`idea_title`, `asset_class`, `symbols`, `strategy_facts`, `assumptions`,
`date_range`, `metrics`, `benchmark_symbol`, `visual`, `owner_note`,
`content_language`, `framing`, `provenance_mark`.

Source conversation ids, route receipts, provider or model metadata, retry
payloads, raw transcripts, broker or account data, and user-private memory are
never present. `argus.domain.public_excerpts.audit_public_excerpt_payload` audits
keys and values before any receipt is written and fails closed, so a payload that
cannot be proven clean is never stored.

### Nothing rendered is frozen

A receipt is read by strangers, so the payload freezes facts and never sentences.
`strategy_facts`, `assumptions`, and `metrics` are each a list of `{key, value}`
under a closed key enum (`StrategyFactKey`, `AssumptionKey`, `MetricKey`), where
`value` is the bare scalar the run reported, and `date_range` is `{start, end}` as
ISO dates. Labels, sentences, thousands separators, and date formats are all
composed by the client in the reader's language. There is deliberately no label
field, no rendered `display` string, and no free-text passthrough anywhere in the
list models.

`assumptions` keys are `long_only`, `equal_weight`, `no_costs`, `modeled_fee_bps`,
`modeled_slippage_bps`, `benchmark`, `benchmark_same_modeled_costs`,
`recurring_contribution`, `contribution_cadence`, and `starting_principal`. Costs
are read from the frozen run config rather than through the live execution-realism
flag, so a flag flipped after the run cannot rewrite what the receipt says the run
assumed.

`MetricKey` is `cash_value`, `total_return_pct`, `max_drawdown_pct`, `win_rate`,
`benchmark_return_pct`, and `delta_vs_benchmark_pct`. The first four are the result
card's own row keys. The card's `benchmark_delta` row is deliberately not carried
under its own key, because its value is a rendered sentence rather than a number;
the last two are read from the run's `metrics.aggregate.performance` instead, so
the comparison survives as figures the page can speak in either language. Values
are the run's own display strings, except `delta_vs_benchmark_pct`, which is a bare
signed number because its unit is percentage points and every way of writing that
unit is a word.

A metric key the projection does not know is refused, not dropped, and a payload
that names a `benchmark_symbol` must carry a benchmark figure. Dropping is how the
comparison could disappear from a receipt while the page went on naming a
benchmark. Likewise a run whose assumptions or tested window will not project is
refused rather than published with the prose the run happened to freeze.

### Reading a stored payload

The public read validates stored JSON against this model, and `extra="forbid"`
means a row written by a different shape raises rather than degrades. That path
answers `503` with `Retry-After`, which the viewer's page reads as temporarily
unavailable. It deliberately does not answer with the tombstone: the row is
intact, so saying the receipt is gone for good would be a permanent-sounding lie
about a live link. Owner-side reads are not wrapped this way; an owner's list is
the only place a receipt can be revoked, so a row it cannot parse should surface
loudly rather than vanish from that list.

`idea_title` and `owner_note` are the only author-written fields, and
`content_language` names the language they are in. `owner_note` is also the only
free-text field: bounded at 280 characters, stripped of control characters, and
refused if it contains an identifier or a credential-shaped token.

`visual` freezes the run's equity series, downsampled to at most 500 points with
the endpoints preserved. The public view renders it client side; nothing is
fetched at view time.

### Immutability and revocation

`prevent_public_excerpt_immutable_update` rejects any change to `id`,
`public_id`, `owner_id`, `title`, `payload`, `payload_digest`, or `created_at`,
and rejects any change to the revocation columns once `revoked_at` is set.
Revocation is one way.

`enforce_public_excerpt_source_is_live` refuses an insert whose source conversation
is soft-deleted or gone. Revocation-on-delete only revokes snapshots that exist when
`deleted_at` changes, so without this a stale result card, or a create racing behind
the delete, could publish a page for a conversation the owner had already removed.
The trigger takes `FOR SHARE` on the conversation row, which is the part an
application check cannot do: a check-then-insert could pass and have the delete
commit before the insert lands, whereas the lock makes a concurrent soft delete block
the insert, which then reads the delete's result and refuses.

`revoke_public_excerpts_for_deleted_source` revokes a receipt when its source
goes away, so deleting a chat cannot leave a live public page behind:
- `conversations` soft delete (`deleted_at` null to not null)
- `conversations`, `backtest_runs`, or `evidence_artifacts` hard delete

Every branch skips rows whose owner profile is already gone. Account deletion
cascades to conversations and fires the purge trigger while the profile no longer
exists; revoking there would fail the owner foreign key and take account deletion
with it. Those rows are cascade-deleted moments later, reaching the same outcome.

A partial unique index on `(owner_id, evidence_artifact_id) where revoked_at is
null` allows at most one live receipt per result, so re-sharing returns the
existing link instead of minting a second page the owner must revoke twice.
Revoked rows are excluded, so revoking does not forbid sharing that result again.

Note a pre-existing constraint: a conversation with a captured idea spine cannot
be hard deleted at all, because `idea_versions.source_conversation_id` is
`ON DELETE SET NULL` while `prevent_idea_version_immutable_update` forbids
changing that column. Argus only soft deletes conversations, so this never
surfaces in the product; the purge triggers are a backstop, not the live path.

### RLS

Row level security is enabled and there is deliberately **no** policy and **no**
grant for `anon` or `authenticated`. Neither the public read nor the owner's list
goes through the browser: both are served by the backend, which is where the
audience split is enforced. The public read selects only
`public_id, payload, created_at, revoked_at`. A select policy without a matching
grant would be dead code that reads like protection, and adding the grant would
put the owner and source columns one PostgREST call away from the browser.

## 12.1.2 Memory Persistence Incubation

Memory is an isolated, no-consumer persistence checkpoint. It
does not change P2 recall, Omnisearch, canonical Ideas, EvidenceArtifacts,
DecisionNotes, conversations, backtests, LangGraph state, or ordinary Guest
chat. Product exposure, API wiring, runtime retrieval, Data Controls, providers,
analytics, and hosted-database application remain closed.

Memory is registered-account-only and off by absence. Supabase Auth and
`guest_workspaces` are the database-canonical eligibility boundary:

- `auth.users.is_anonymous` must be false;
- no same-identity Guest workspace may be `active` or `claiming`;
- browser/Data API roles (`PUBLIC`, `anon`, `authenticated`, and
  `service_role`) have no direct table or sequence privileges;
- a fixed-search-path private predicate is called by every memory-table insert
  and update trigger;
- owner identity is immutable; forged JWT claims cannot replace Auth/workspace
  truth.

All memory tables have RLS enabled and forced, with no client policies. The
private backend Postgres adapter is the only intended access path and must
still derive a registered owner from a verified request before entering the
store.

### Canonical and derivative tables

- `memory_settings`: one enabled category row per owner. No rows means memory is
  disabled. Categories are closed to personalization preference, workflow
  preference, explicit decision note, and past-session anchor.
- `memory_candidates`: bounded pending proposal content, trigger/context,
  exact opt-in scope, and sensitivity-policy digest. A candidate is not a
  durable memory.
- `memory_consent_actions`: immutable direct-enable or
  candidate-confirmation evidence with exact requested, granted, and effective
  scopes plus schema/policy versions and idempotency identity. Direct enable
  has no candidate and grants a non-empty scope. Confirmation requires an
  existing same-owner candidate whose category appears in the requested scope.
- `memory_records`: confirmed canonical label/value state. The owner, candidate,
  consent action, category, and creation identity are immutable. An edit may
  change only label/value with the next positive revision and a later
  `updated_at`.
- `memory_provenance`: immutable, ordered owner-scoped pointers attached to
  exactly one candidate or record. Source kinds are closed to Argus-owned
  EvidenceArtifact, DecisionNote, Idea, IdeaVersion, Conversation, and Message
  identities.
- `memory_prompt_history`: category-scoped proactive-prompt and decline
  timestamps used for durable cooldown/suppression decisions.
- `memory_reconciliations`: positive, ordered provider-projection work
  generations. Rows start pending, then move through an exact leased claim to
  running before reaching immutable succeeded/failed terminal state. The claim
  token, expiry, and attempt count make restart recovery inspectable: a live
  lease cannot be stolen, an expired lease may be reclaimed with a new token,
  and only the exact, unexpired current claim may commit a provider pointer or
  terminal outcome. Terminal rows erase the bearer token and lease. Lower
  unfinished generations cause a bounded, lock-free wait before later work for
  the same record, while other owners remain independent. Unfinished work
  restricts record deletion so derivative cleanup cannot disappear silently.
  Owner-wide reset uses the reserved `operation = reset`, `record_id = ''`
  sentinel. Record operations require a non-empty record id. Reset first
  removes canonical and user-visible memory, snapshots every provider pointer
  into cleanup, and retains one retryable reset generation. Failed attempts
  remain terminal evidence; a retry appends the next generation, while a crash
  before a terminal outcome reuses or reclaims the unfinished generation.
  While reset metadata remains unresolved, fresh canonical memory may be
  confirmed after a new opt-in but record-specific provider work cannot claim
  a lease. A later reset recognizes the existing owner-reset history and
  atomically supersedes that post-reset canonical work instead of waiting on
  its intentionally blocked provider reconciliation. The first reset still
  performs a bounded wait for genuine pre-reset provider work.
- `memory_provider_projections`: the current derivative provider pointer and
  positive generation for a canonical record. A provider pointer is unique per
  owner but may be reused independently by another owner. Replacements are
  atomic with a durable cleanup snapshot of the prior pointer.
- `memory_provider_cleanup`: durable, owner-scoped cleanup targets that survive
  canonical record deletion and process restarts. Rows begin pending, may move
  only once to resolved, and never reopen; a successful resolution also removes
  the matching same-record projection when it still exists. Bounded reads
  return at most 100 unique pending targets in deterministic newest-first
  order. Cleanup scheduling refuses a pointer currently projected by another
  record for the same owner, preventing deletion of live reused provider state.
  While any cleanup row remains pending, its `(owner_id, provider_ref)` is a
  fail-closed reservation: neither application code nor direct SQL may assign
  that pointer to a live projection. The reservation ends only when cleanup is
  resolved.
  Provider pointers are derivative identifiers, never canonical memory content.

An owner reset calls any derivative provider only after the canonical
transaction commits and only when cleanup exists. A synchronized provider
result may clear cleanup, projections, and reset metadata only with the exact
unexpired reset claim. Provider failure, malformed output, or
`not_applicable` retains cleanup for retry. Completion never deletes canonical
records created after the earlier reset.

Composite foreign keys include `owner_id` at every live relationship so a
candidate, consent action, record, provenance row, reconciliation, or provider
projection cannot cross owners. Candidate-confirmation receipts survive
candidate consumption; records link to the immutable receipt by owner,
candidate identity, and receipt identity. Account deletion cascades the full
owner state, including durable cleanup targets.

### Guest conversion zero state

Memory never enters the Guest transfer graph. A `BEFORE UPDATE` trigger on
`guest_workspaces` counts all nine memory tables when an `active`/`claiming`
workspace moves to `claimed`. Any row blocks both same-identity link and
existing-account handoff, and the surrounding conversion transaction rolls
back without transferring memory. A clean conversion carries zero memory,
performs no retrospective extraction, and leaves personalization disabled until
the registered user later completes a fresh scoped opt-in.

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
- `operation_scope`: `text` (`chat.run_backtest`, `backtests.run`, or
  `chat.research`)
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
- **operation_scope**: `chat.run_backtest`, `backtests.run`, `chat.research`
  (thorough research runs ride this same lifecycle; a succeeded research job
  keeps `result_run_id` null and references its answer message through
  `execution_metadata.research_result_message_id`)
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
- `period`: `text` (e.g., `hour`, `day`, `guest_session`)
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
- **Resource**: `chat_messages`, `backtest_runs`, `backtest_jobs`, `feedback`,
  `discovery_searches`
- **Period**: `hour`, `day`, `guest_session`

### Discovery Search Accounting
- For registered accounts, `discovery_searches` counts grounded-discovery
  Search attempts in `usage_counters` (10/hour, 25/day defaults from
  `ARGUS_DISCOVERY_HOURLY_LIMIT` / `ARGUS_DISCOVERY_DAILY_LIMIT`).
- Guest discovery uses `visitor_usage_counters` instead. A guest workspace
  receives a fresh `user_id` when renewed, so an account-owned counter would
  incorrectly reset the allowance.
- Availability is read before the turn runs; the charge settles best-effort
  after the terminal assistant message commits, only when a Search call was
  actually attempted. This is an operational abuse guard with truthful attempt
  accounting, not billing truth; failed settlement never breaks the user turn.

### Notes
- Usage counters are operational safety data, not monetization data in Alpha.
- For `guest_session`, `period_start` equals `guest_workspaces.created_at` and
  `period_end` equals its fixed seven-day `expires_at`. Limits are ten completed
  assistant terminals, two unique simulation admissions, and five feedback
  submissions over the identity lifetime.
- Registered users continue to use the existing UTC hour/day accounting.

---

## 14.1 visitor_usage_counters

Tracks discovery allowances for callers who do not have a durable account.
This is intentionally separate from `usage_counters`, whose `user_id` is a
foreign key to `profiles.id`.

### Fields
- `visitor_key`: `text` (opaque keyed digest; never a raw address)
- `resource`: `text` (`discovery_searches`)
- `period`: `text` (`day`)
- `period_start`: `timestamptz`
- `period_end`: `timestamptz`
- `used_count`: `integer` (Default: `0`)
- `limit_count`: `integer`
- `created_at`: `timestamptz`
- `updated_at`: `timestamptz`

### Constraints, access, and retention
- **Primary key**:
  `(visitor_key, resource, period, period_start)`
- **Window lookup index**:
  `(visitor_key, resource, period_end)`
- RLS is enabled with no policies. Only `service_role` has table access and may
  execute `settle_visitor_usage` or `purge_expired_visitor_usage`.
- Expired rows are disposable operational data, but `period_end` is not a timer
  and nothing in the database acts on it. The row has no owner to cascade from,
  so it is deleted only when a successful non-dry-run of the guest cleanup job
  reaches the purge: `purge_expired_visitor_usage` is registered in
  `argus.domain.guest_cleanup.EXPIRING_DATA_PURGES` and runs on every non-dry-run
  `scripts/ops/cleanup_expired_guest_workspaces.py`. Retention therefore holds
  exactly as often as an operator runs that job. It is not a deployed release
  surface. See the runbook's Operator-Run Maintenance section.

### Discovery policy
- A guest receives two grounded searches per visitor per day. Renewing the
  temporary workspace does not reset that allowance.
- The same table holds the global attempted-search bucket. Its daily ceiling is
  configured by `ARGUS_DISCOVERY_GLOBAL_DAILY_CEILING` and defaults to `500`
  when the value is blank or invalid.
- If counter truth cannot be read, admission currently fails closed into the
  existing `discovery_limit_reached` recovery. Issue #244 retains that
  user-facing truth limitation for follow-up.

---

## 14.2 guest_funnel_milestones

Records that a guest funnel milestone has been reached, so it is emitted at most
once per subject. Milestone events are the acquisition funnel's numerator, and a
duplicate inflates conversion counts in one direction.

The subject is the same visitor key that meters guest allowances, not a
`user_id`: renewing a temporary workspace mints a fresh `user_id`, so a
user-keyed milestone would re-fire on every renewal. Like
`visitor_usage_counters` this table is deliberately not foreign-key bound.

### Fields
- `subject_key`: `text` (visitor key; falls back to a pseudonymous actor hash
  when no visitor key is bound to the request)
- `milestone`: `text` (guest funnel event kind)
- `recorded_at`: `timestamptz`
- `expires_at`: `timestamptz`

### Constraints, access, and retention
- **Primary key**: `(subject_key, milestone)`. The primary key is the
  idempotency guarantee. It holds across retries, restarts, concurrent
  requests, and multiple workers in a way application logic cannot.
- **Expiry index**: `(expires_at)`
- RLS is enabled with no policies. Only `service_role` has table access and may
  execute `claim_guest_funnel_milestone` or
  `purge_expired_guest_funnel_milestones`.
- Claims are marked expired 30 days after they are recorded, outliving the
  seven-day guest workspace with headroom. A visitor-keyed table with no expiry
  would become a durable visitor log.
- `expires_at` is not a timer, and nothing in the database acts on it. The row
  has no owner to cascade from, so the guest cleanup job is the only thing that
  deletes it: `purge_expired_guest_funnel_milestones` is registered
  in `argus.domain.guest_cleanup.EXPIRING_DATA_PURGES` and runs on every
  non-dry-run `scripts/ops/cleanup_expired_guest_workspaces.py`. A visitor who
  never returns is deleted by that job, not by the takeover path. Retention
  therefore holds exactly as often as an operator runs that job.
- `claim_guest_funnel_milestone` also takes over an already-expired claim in the
  same statement, so a returning visitor is correct even between purge runs.

### Milestone policy
- Milestone-class kinds are `first_useful_assistant_response_completed`,
  `first_simulation_admitted`, `first_result_completed`,
  `account_creation_completed`, `existing_account_sign_in_completed`, and
  `temporary_workspace_claimed`.
- Every other guest funnel kind is repeatable volume or step data and is not
  claimed. A guest reaches confirmation, sees a conversion prompt, hits a limit,
  and submits feedback as many times as they actually do.
- A duplicate claim is a silent no-op. A retried request must not fail because
  it already succeeded.
- A milestone whose claim cannot be resolved or persisted is suppressed rather
  than emitted, because duplicates bias the funnel in one direction.
- Visitor keys are IP-derived, so callers sharing one egress address share a
  subject and a second visitor's milestone can be suppressed. This is the same
  property guest allowance metering already accepts.

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
Used for **conversations** and retained on legacy **strategies** and
**collections** rows. Legacy rows remain filtered/read-safe, but only
conversation recovery is exposed in the current product.

### Archive
Used specifically for **conversations** to hide them from the primary sidebar without deleting the data.
---

# 17. Recents / History Model

Recents is a mixed-type feed displaying activity across the platform.

### Supported Types
- `chat`
- `run`
- `strategy` (legacy read compatibility only)
- `collection` (legacy read compatibility only)

### Standard History Shape
```json
{
  "type": "chat",
  "id": "uuid",
  "title": "Tesla dip thread",
  "subtitle": "Last message or metric preview",
  "pinned": false,
  "created_at": "timestamp",
  "activity": {
    "operation": {"status": "idle", "kind": null, "updated_at": null},
    "attention": {"status": "none", "cursor": null}
  }
}
```

`activity` is projected on `chat` rows only and omitted from all other History
types. It is not stored on the conversation and does not affect History order.
---

# 18. Search Model

Alpha supports keyword-based search across core entities.

### Scope
- **Global Search**: Omni-search spanning current Conversation, Run, Idea,
  Evidence, and Decision artifacts.

### Future
Semantic search using embeddings is deferred until post-Alpha.
- Do not add embedding or pgvector tables for the production readiness chat/backtest branch.
- Use structured Supabase records, run metadata, Idea/Evidence/Decision
  artifacts, and keyword search until Argus needs semantic recall across large
  histories.

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

### Conversation read state
- `conversation_read_states` grants authenticated owners `SELECT` only.
  `PUBLIC`, `anon`, and `authenticated` cannot write or execute its mutation,
  read-source, reconciliation, or baseline functions; service-role persistence
  owns those operations.

### Tables Requiring RLS
- `private_alpha_allowlist`, `profiles`, `conversations`, `messages`,
  `chat_turn_lifecycles`, `conversation_read_states`, `strategies`, `collections`,
  `collection_strategies`, `backtest_jobs`, `backtest_runs`, `feedback`,
  `usage_counters`, `guest_workspaces`, `memory_settings`,
  `memory_candidates`, `memory_consent_actions`, `memory_records`,
  `memory_provenance`, `memory_prompt_history`, `memory_reconciliations`,
  `memory_provider_projections`, `memory_provider_cleanup`.

### Guest ownership
- Supabase anonymous identities use the `authenticated` role, so every guest
  policy keeps `(select auth.uid()) = user_id`; role membership alone is never
  authorization.
- Expired guest identities cannot read or write product rows.
- Another guest and a permanent user see zero guest workspace rows.
- Guest memory state must be zero before either same-identity claim or
  existing-account handoff. Memory rows are rejected rather than transferred.
- `profiles.avatar_theme` is a registered-account preference. The database
  default keeps every row valid, but restrictive profile RLS policies use the
  trusted `is_anonymous` JWT claim so a guest cannot read or write it through
  the client role. The API omits the field from guest responses.

### Private Alpha Allowlist
- No `anon` or `authenticated` role access is required.
- All privileges remain revoked from `public`, `anon`, and `authenticated`;
  no client policy permits direct requested-row access.
- Backend service-role access owns request capture, approval transition, and
  access checks before auth signup/login.

---

# 20. Indexing Requirements

### Critical Performance Indexes
- **private_alpha_allowlist**: `(email)` with active-row partial index
- **profiles**: `(id)`, `(username)`
- **conversations**: `(user_id, updated_at DESC)`, `(user_id, archived, deleted_at)`, `(user_id, pinned)`
- **messages**: `(conversation_id, created_at DESC)`
- **chat_turn_lifecycles**: `(conversation_id, status, updated_at)`,
  `(user_id, status, updated_at)`, unique `(assistant_message_id)` where not null
- **chat_turn_lifecycles activity reads**:
  `(user_id, conversation_id, status, updated_at DESC, turn_id DESC)` for active
  rows and `(user_id, conversation_id, status, terminal_at DESC, turn_id DESC)`
  for terminal rows
- **strategies**: `(user_id, updated_at DESC)`, `(user_id, pinned)`, `(user_id, deleted_at)`
- **strategies (gin)**: `USING gin(symbols)`
- **collections**: `(user_id, updated_at DESC)`, `(user_id, pinned)`, `(user_id, deleted_at)`
- **collection_strategies**: `(collection_id)`, `(strategy_id)`
- **backtest_jobs**: `(user_id, status, queued_at DESC)`, `(conversation_id, created_at DESC)`, `(result_run_id)`
- **backtest_jobs activity reads**:
  `(user_id, conversation_id, status, updated_at DESC, id DESC)` for active or
  checking rows and `(user_id, conversation_id, status, finished_at DESC, id DESC)`
  for terminal rows
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
- **memory_candidates**: `(owner_id, created_at, id)`
- **memory_consent_actions**: `(owner_id, recorded_at, id)`, unique confirmed
  `(owner_id, candidate_id)`
- **memory_records**: `(owner_id, created_at, id)`, covering
  `(owner_id, consent_action_id, candidate_id)`, unique
  `(owner_id, candidate_id)`
- **memory_provenance**: unique ordered candidate and record indexes on
  `(owner_id, parent_id, ordinal)`
- **memory_reconciliations**: partial pending/running index on
  `(owner_id, status, record_id, generation)`
- **memory_provider_cleanup**: partial pending index on
  `(owner_id, status, created_at, record_id)`
---

# 21. Naming & Title Defaults

AI-generated titles are the default for conversations. Historical Strategy and
Collection names are read-only compatibility data.

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
