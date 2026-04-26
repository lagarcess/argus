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

- user profiles
- preferences
- conversations
- messages
- strategies
- collections
- backtest runs
- feedback
- telemetry-ready product state

Render/FastAPI owns orchestration and compute, not long-term state.

---

# 3. Core Entities

Alpha MVP requires these primary entities:

```text
profiles
conversations
messages
strategies
collections
collection_strategies
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

# 6. conversations

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

# 7. messages

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
---

# 8. strategies

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
- **Asset Classes**: `equity`, `crypto`.
- **Note**: Strategies may target multiple symbols but only within the same `asset_class`.

> [!TIP]
> **Global Rule**: Collections may mix asset classes organizationally. Backtest runs may not mix asset classes operationally.

### Notes
- Strategies can be created directly or derived from a chat conversation.
- Display metrics are derived from the most recent `backtest_runs`, not stored statically here.
---

# 9. collections

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

# 10. collection_strategies

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

# 11. backtest_runs

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
- `benchmark_symbol` is derived from `asset_class` defaults in Alpha (`SPY` for equities, `BTC` for crypto).
---

# 12. Backtest Metrics Shape

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
---

# 13. usage_counters

Tracks resource consumption for quotas and limits.

### Fields
- `id`: `uuid` (Primary Key)
- `user_id`: `uuid` (References `profiles.id`)
- `resource`: `text` (e.g., `backtest_runs`, `chat_messages`)
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
- **Resource**: `chat_messages`, `backtest_runs`
- **Period**: `hour`, `day`

### Notes
- Usage counters are operational safety data, not monetization data in Alpha.

---

# 14. feedback

Stores user-submitted bug reports and feature requests.

### Fields
- `id`: `uuid` (Primary Key)
- `user_id`: `uuid` (Nullable, references `profiles.id`)
- `type`: `text` (e.g., `bug`, `feature`)
- `message`: `text`
- `context`: `jsonb` (Default: `{}`)
- `created_at`: `timestamptz`

### Enums
- **type**: `bug`, `feature`, `general`
---

# 15. Soft Delete & Archive Rules

### Soft Delete
Used for **conversations**, **strategies**, and **collections**. These items should be filtered out by default but remain in the DB for "Recently Deleted" recovery.

### Archive
Used specifically for **conversations** to hide them from the primary sidebar without deleting the data.
---

# 16. Recents / History Model

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

# 17. Search Model

Alpha supports keyword-based search across core entities.

### Scope
- **Surface Search**: Filter-by-type search (e.g., searching only Strategies).
- **Global Search**: Omni-search spanning Conversations, Strategies, and Collections.

### Future
Semantic search using embeddings is deferred until post-Alpha.

---

# 18. RLS Ownership Rules

Every user-owned table must enforce strict Row Level Security (RLS).

### Primary Rule
- Users may only `SELECT`, `UPDATE`, or `DELETE` rows where `user_id = auth.uid()`.

### Tables Requiring RLS
- `profiles`, `conversations`, `messages`, `strategies`, `collections`, `collection_strategies`, `backtest_runs`, `feedback`, `usage_counters`.

---

# 19. Indexing Requirements

### Critical Performance Indexes
- **profiles**: `(id)`, `(username)`
- **conversations**: `(user_id, updated_at DESC)`, `(user_id, archived, deleted_at)`, `(user_id, pinned)`
- **messages**: `(conversation_id, created_at DESC)`
- **strategies**: `(user_id, updated_at DESC)`, `(user_id, pinned)`, `(user_id, deleted_at)`
- **strategies (gin)**: `USING gin(symbols)`
- **collections**: `(user_id, updated_at DESC)`, `(user_id, pinned)`, `(user_id, deleted_at)`
- **collection_strategies**: `(collection_id)`, `(strategy_id)`
- **backtest_runs**: `(user_id, created_at DESC)`, `(conversation_id)`, `(strategy_id)`
- **backtest_runs (gin)**: `USING gin(symbols)`
- **feedback**: `(user_id, created_at DESC)`
- **usage_counters**: `(user_id, resource, period_start DESC)`
- **usage_counters**: `(period_end)`
- **usage_counters unique**: `(user_id, resource, period, period_start)`
---

# 20. Naming & Title Defaults

AI-generated names and titles are the default for conversations, strategies, and collections.

### Source Tracking
- `system_default`: The initial placeholder before AI processing.
- `ai_generated`: Set after the AI generates a context-aware title.
- `user_renamed`: Set if the user manually overrides the title.

*Note: AI must never overwrite a `user_renamed` entry.*

---

# 21. Usage Controls, Quotas, and Limits

Argus Alpha MVP implements three defensive layers to protect system stability and manage compute/LLM costs while maintaining a generous user experience. These are "fair use" guardrails, not monetization tiers.

### Layer 1: Engine Constraints
Hard-coded technical limits in the backtesting logic.
- **Symbols**: Max 5 symbols per run.
- **Timeframe**: 1h, 2h, 4h, 6h, 12h, 1D.
- **Lookback**: Max 3 years.
- **Capital**: Min 1,000 / Max 100,000,000.
- **Side**: Long-only.

### Layer 2: Rate Limits
Short-window protection against abuse or runaway UI loops.
- **Backtests**: Max 10 per hour.
- **Chat**: Max 10 messages per minute.
- **Mechanism**: Enforced via standard `Retry-After` headers.

### Layer 3: Daily / Rolling Quotas
Generous usage boundaries tracked via the `usage_counters` table.
- **Backtest Runs**: 50 per day.
- **Chat Messages**: 200 per day.

---

# 22. Backend Enforcement Model

### Enforcement Flow
1. **Authenticate**: Resolve `user_id` from session.
2. **Hard Constraints**: Validate `backtest_run` inputs against Engine Constraints.
3. **Check Counters**: Query `usage_counters` for applicable resource/period.
4. **Exceedance Policy**:
   - If rate limit exceeded: Return `429 Too Many Requests`.
   - If daily quota exhausted: Return `429` (Alpha policy).
5. **Execute**: Perform the operation.
6. **Increment**: Update/Insert the `usage_counters` row.
7. **Response**: Return result with rate-limit headers.

### Admin Bypass
Users with `profiles.is_admin = true` may have quota and rate-limit checks bypassed by backend logic.
- Ownership and privacy rules still apply.
- Engine safety constraints (e.g., symbol limits) may still apply.

---

# 23. Historical State & Reproducibility (SCD)

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

# 24. Data Model Decision Filter

When adding or changing a table, ask:

> *Does this support fast, trustworthy conversational investing idea testing?*

If no, it likely should wait for post-Alpha.
