# ARCHITECTURE.md

## Argus System Architecture Source of Truth (Alpha MVP)

**Status:** Active | **Alpha Architecture v1 Locked**
**Audience:** Engineers, AI agents, founders
**Purpose:** Define how Argus is structured technically, how systems communicate, where state lives, what services own what responsibilities, and how to build the Alpha MVP with low complexity and high iteration speed.

> [!IMPORTANT]
> **Locked Status**: No structural architecture shifts (service ownership changes or protocol swaps) are allowed without explicit approval. Additive refinements and implementation detail documentation are permitted.

> [!NOTE]
> This document describes the **target architecture** — the intended production state of the Argus agent runtime. It is the north star for implementation. Where current code diverges from this doc, the doc is correct and the code must change.

---

# 1. Architecture Philosophy

Argus is a **chat-first product powered by a backtesting engine**.

This means:

- Conversation UX is the primary product surface.
- Quantitative execution is supporting infrastructure.
- Simplicity and speed are favored over premature complexity.
- Systems should be modular enough to evolve without rewrites.
- Launch speed matters more than theoretical perfection.

---

# 2. Core Technical Principles

## Single Source of Truth

Persistent user and product state must live in one canonical system.

## Stateless Compute

APIs, AI orchestration, and execution workers should remain stateless whenever possible.

## Clear Boundaries

Each service must have a narrow responsibility.

## Contract Driven Development

Frontend and backend should integrate through explicit API contracts.

## Async Where Valuable

Use streaming or jobs only where they materially improve UX.

## Replace Complexity with Iteration

Prefer simpler architecture that can ship now.

---

# 3. Product Surface Architecture

## Primary Surface

### Chat Workspace

The main Argus experience.

Contains:

- conversation thread
- AI messages
- user messages
- starter prompts
- progress states
- result cards
- follow-up actions

## Supporting Surfaces

### Recents

Mixed chronological feed of:

- chats
- strategies
- collections

### Strategies

Saved executable ideas with at-a-glance metrics.

### Collections

Grouped strategies by user theme/topic.

### Settings

Preferences, language, theme, feedback, account actions.

---

# 4. High-Level System Topology

```text
Client (Next.js Web/PWA)
        |
        v
API Layer (FastAPI / Render)
        |
        +--> Supabase (Auth + Postgres + Storage)
        |
        +--> OpenRouter (LLM)
        |
        +--> Market Data Provider (alpaca)
        |
        +--> Cache Layer (Optional Early Alpha)
        |
        +--> Backtest Engine (Simulation Logic)
```

**Later Optional:**
- **Queue / Job Runner**: (RQ / Celery / Dramatiq) for long-running backtests, retries, and burst smoothing.
---
# 5. Frontend Architecture

## Current Launch Surface

Web app / PWA.

**Chosen because:**

- Fastest route to market
- Easiest iteration loop
- Shared codebase
- Mobile-accessible enough for alpha

## Long-Term Direction

Native mobile + web parity where valuable.

## Frontend Responsibilities

- Chat UI
- Streaming responses
- Optimistic interactions
- Auth flows
- Surface navigation
- Rendering metrics/results
- Settings/preferences
- Local UI state

# 6. Backend API Architecture

## Primary Role

Thin orchestration layer.

The backend should coordinate systems, not become monolithic business chaos.

## Responsibilities

- Validate auth/session
- Route requests
- Persist data
- Call LLM provider
- Call engine
- Call market data provider
- Stream responses
- Enforce quotas (Usage Counters)
- Enforce rate limits
- Enforce engine constraints
- Enforce asset_class coherence (Same-asset runs only)
- Expose clean APIs

## Non-Goals

- Rendering UI logic
- Storing long-term state in memory
- Becoming deeply stateful

# 7. Communication Protocols

## Chat Messaging

**Preferred MVP Transport:** SSE (Server Sent Events)

**Use for:**

- AI token streaming
- Progress updates
- "Running backtest..."
- Partial explanations

**Why:**

- Simpler than WebSockets
- Ideal for one-way streaming
- Lower implementation overhead

## Standard Request / Response (REST)

**Use for:**

- Auth
- Settings
- CRUD operations
- History
- Collections
- Strategies
- Run requests
- Detail fetches

## Deferred: WebSockets

Only introduce later if required for:

- Collaborative sessions
- Many concurrent background jobs
- Persistent live market feeds

# 8. Stateful vs Stateless Systems

## Stateful Systems

### Supabase

Canonical state store.

**Owns:**

- Users
- Profiles
- Preferences
- Onboarding state
- Conversations
- Messages
- Strategies
- Collections
- Backtest history
- Archived / deleted records
- Feedback records

### Cache Layer (Optional Early Alpha)

Temporary performance state. In-memory fallback (e.g. `cachetools`) is allowed for non-critical acceleration, but must not be the source of truth for persistence or quotas.

**Owns:**

- Hot market data (acceleration only)
- Response caches
- Rate-limit buckets (if Redis is present)

## Stateless Systems

### API Layer

Request in -> response out. Decomposed into focused routers (`api/routers/auth`, `conversations`, `strategies`, `collections`, `backtest`, `agent`). The `api/main.py` registers routers and contains no business logic.

### AI Orchestrator (Stateless Per Request)

Build prompt → call LLM → parse response → validate facts → route.
- **Rule**: Orchestrator memory is reconstructed per turn from the LangGraph checkpointer (backed by Supabase `AsyncPostgresSaver` in production, `MemorySaver` in development).
- No in-process session state is stored outside the checkpointer. `InMemorySessionManager` is not used.
- One LLM call per turn for intent classification. Downstream calls (explain, clarify, name suggestion) are permitted but do not reclassify intent.

### Execution Worker (Stateless)

The runtime compute process that executes simulations.

### Backtest Engine (Domain Logic)

The simulation logic (Numba/Python) that calculates metrics and returns results.

*Stateless systems should scale horizontally later.*

# 9. Third Party Systems

### Supabase

**Use for:**

- Auth
- Database
- Row Security
- Storage (if needed)
- Realtime (later)

### OpenRouter

**Use for:**

- Chat intelligence
- Onboarding guidance
- Strategy extraction
- Explanations

### Market Data Provider

**Use for:**

- Historical price data
- Supported symbols

Provider ownership:

- Alpaca is primary for equity and crypto availability.
- Kraken public REST complements coverage for currency pairs and crypto fallback.
- Provider-specific windows are execution truth. Kraken OHLC returns only the latest 720 candles per interval, so the runtime must ask the user to shorten the request or widen the timeframe when the requested window cannot be served.
- Backtests remain single asset class per run: `equity`, `crypto`, or `currency_pair`.

### PostHog (When Enabled)

**Use for:**

- Analytics
- Funnels
- Feature flags

### Observability Stack

Minimal but critical for Alpha stability.

- **Logs**: Structured logs (Loguru) sent to service provider logs.
- **Request Tracking**: `X-Request-Id` headers across all flows.
- **Error Alerts**: Error monitoring (e.g. Sentry) for exception tracking.
- **Latency Monitoring**: Request-time tracking for API and Engine.

# 10. Canonical Product Objects

Argus does not have one canonical object. It has multiple first-class objects.

- **User**: Identity + preferences.
- **Conversation**: A thread representing one isolated idea journey.
- **Message**: A unit inside a conversation.
- **Strategy**: A supported executable template + parameters.
- **Backtest Run**: Immutable simulation result.
- **Collection**: User grouping of strategies.
- **Asset**: Supported symbol/instrument metadata (includes `asset_class`).

# 11. Conversation Model

## Multi-Chat Required

Each conversation is isolated.

**Reasons:**

- Cleaner context windows
- Lower memory leakage
- Easier retrieval
- Idea-oriented UX
- Better organization

## Memory Boundary (Alpha)

**AI may use:**

- Current thread history
- User profile/preferences

*AI should not depend on unrelated thread memory.*

> [!TIP]
> **Global Rule**: Collections may mix asset classes organizationally. Backtest runs may not mix asset classes operationally.

## Conversational Runtime Architecture

The agent runtime is a **LangGraph `StateGraph`** executing a pipeline of named stages. The graph is the execution contract. No routing logic exists outside the graph's conditional edge functions.

### Tool Stack

| Tool | Role | Scope |
|---|---|---|
| **LangChain** (`langchain_openrouter`, `langchain_core`) | LLM call layer | `ChatOpenRouter`, `.with_structured_output()`, `.ainvoke()`, `SystemMessage`/`HumanMessage`/`AIMessage` types |
| **LangGraph** (`langgraph.graph`, `langgraph.checkpoint`) | Graph execution layer | `StateGraph`, `checkpointer`, `astream_events()`, thread-scoped state |

These responsibilities are absolute and do not cross. Routing is not implemented inside LangChain calls. Session persistence is not implemented outside the checkpointer.

### Pipeline (Per Turn)

```
HTTP POST /api/v1/chat/stream (SSE)
    │
    ▼
[Pre-flight] Auth validation, quota check (stateless, no LLM)
    │
    ▼
[LangGraph: astream_events()]
    ├── [interpret]  LLM classifies intent, extracts strategy fields, detects semantic_turn_act.
    │                Post-LLM validation only: symbol resolution, asset parity, date limits,
    │                missing required fields. → streams stage_start event immediately.
    │
    ├── [clarify]    if needs_clarification → LLM generates context-aware question.
    │                No hardcoded prompt templates. → streams question tokens.
    │
    ├── [confirm]    if ready_for_confirmation → deterministic confirmation card assembly.
    │                → streams stage_outcome event; frontend renders card.
    │
    ├── [execute]    if approved_for_execution → RealBacktestTool call.
    │                → streams stage_start event; frontend shows "Running backtest..."
    │
    ├── [explain]    if execution_succeeded → LLM generates result narrative from metrics.
    │                → streams explanation tokens.
    │
    └── [next_step]  LLM suggests follow-up actions. → streams next-step chips.
    │
    ▼
[checkpointer] Persists WorkflowState to Supabase (AsyncPostgresSaver) or memory.
    │
    ▼
SSE stream: done event with final payload
```

### NLU Ownership Rule

The LLM is the **only NLU layer**. Deterministic code validates facts it cannot know — it does not classify intent, detect approval signals, or generate user-facing text.

Structured action chips are not natural-language NLU shortcuts. They enter LangGraph as explicit product operations attached to the current confirmation or result artifact. Normal user text still reaches the structured LLM interpreter before routing decisions.

| Layer | Owns |
|---|---|
| LLM (interpret node) | Intent, task_relation, semantic_turn_act, strategy field extraction, social/approval/education detection, assistant_response |
| Deterministic (post-LLM) | Symbol resolution via `domain/market_data.resolve_asset()`, asset class parity check, date range limit check, missing required fields check |

No regex gate intercepts a user message before the LLM sees it. No hardcoded natural language string competes with the LLM's response in any stage file.

### Session State Rule

`TaskSnapshot` is the authoritative in-turn state. It stores only non-derivable fields:
- `pending_strategy_summary` — strategy under construction
- `confirmed_strategy_summary` — strategy approved for execution
- `last_stage_outcome` — what the runtime last did
- `latest_backtest_result_reference` — artifact pointer to last completed run

Derived state (missing fields, pending needs, field provenance) is computed fresh each turn from `pending_strategy_summary`. It is never persisted.

### Conversation Artifact Continuity

Conversation text is input, not state truth. Once a confirmation card, result
card, saved strategy, or failed-action artifact exists, every subsequent turn
must first resolve the active artifact anchor before interpreting the user
message as a new task.

Artifact anchors are resolved in this order:

1. The structured action payload attached to the user turn.
2. The latest active confirmation card in the same conversation.
3. The latest completed backtest result referenced by the turn or conversation.
4. The latest retryable failed-action artifact, if the user is retrying that
   failure.
5. No artifact anchor, which means the turn starts a new idea.

After an anchor is resolved, the runtime builds the working draft from the
artifact's canonical configuration (`confirmation_payload`, completed
`backtest_run.config_snapshot`, saved strategy state, or failed-action launch
payload). The LLM may interpret the user's messy text as a patch over that
draft, but omitted artifact fields must carry forward. A date-only edit cannot
erase assets, contribution amount, cadence, timeframe, benchmark, or strategy
type that were already canonical in the anchored artifact.

The deterministic guardrail layer applies the patch and validates the resulting
draft. If the patched draft is executable, Argus emits a new confirmation card.
If required information is genuinely missing, Argus asks a targeted
clarification. Generic guidance such as "try next" must never replace an
artifact-patch response when the user is attempting to modify or rerun a known
setup.

Failure and retry artifacts follow the same rule. A retry button represents one
specific failed action and payload. Later turns that create a new active draft,
new confirmation, completed result, or explicit cancellation must supersede or
expire stale retry affordances so the user never has to guess what "Retry" will
do after reload.

# 12. Strategy Architecture (Alpha)

## Controlled Template System

Users speak freely. AI maps requests into supported templates.

**Example:**

User says: *"Buy Tesla after oversold dips."*

Mapped internally to:
```json
{
  "template": "rsi_mean_reversion",
  "symbol": "TSLA",
  "rsi_threshold": 30
}
```

## Why This Model

- Reliable execution
- Lower hallucination risk
- Simpler engine integration
- Faster shipping

# 13. Backtest Execution Flow

1. User requests simulation in chat
2. API validates request (symbol set, **asset_class parity**, and quota)
3. AI extracts supported strategy config if needed
4. Backend fetches market data (cache first)
5. Strategy kernel produces raw signals
6. Execution reducer applies long-only position state, cash, sizing, and policy
   constraints
7. Engine computes metrics and chart markers from executed fills only
8. Results persisted
9. Results streamed/rendered to user
10. Run appears in history

The execution ledger is the boundary between strategy logic and result
presentation. Signals are diagnostics until they become order intents and fills.
Long-only runs must ignore exit signals while flat and duplicate full-position
entries while already long. Chart markers, trade counts, win-rate inputs, and
user-facing trade explanations consume fills, not raw triggers.

# 14. Search Architecture

## Surface Search

Scoped search.

**Examples:**

- Strategies page searches strategies
- Collections page searches collections

## Global Search

Alpha search is implemented using **Postgres Full-Text Search (FTS)** + recency + pin boost.

**Ranking Criteria:**
1. Pinned boost (explicit user intent)
2. Exact title/name match
3. Symbol match
4. Recency (updated_at)
5. Basic text relevance

## Deferred Direction

Semantic retrieval (Vector embeddings) is deferred from Alpha.
- Use SQL/Text search first.
- Re-evaluate semantic search for Beta.
- Do not add pgvector or embedding tables for the launch chat/backtest branch. Structured Supabase state, run metadata, and saved strategies are sufficient until Argus needs semantic recall across large histories.

# 15. Deletion / Archival Model

## Soft Delete Preferred

Use soft-delete patterns where practical.

**Supports:**

- Recently deleted
- Recovery UX
- Analytics continuity

## Archive Preferred for Chats

Chats may be archived without loss.

# 16. Security Model

## MVP Priorities

- Secure auth flows
- Row ownership enforcement
- Protected private user data
- Safe API boundaries

## Defer Complexity

- Enterprise roles
- Team accounts
- Advanced permissions

# 17. Scalability Philosophy

Design clean seams now, not heavy systems now.

## Good Now

- Stateless APIs
- Explicit contracts
- Isolated workers
- Cache layer
- Normalized data model

## Later

- Autoscaling workers
- Queue systems
- Advanced quotas
- Distributed tracing
- Realtime fanout systems
- **Mixed-Asset Support**: Deferred until custom benchmark and complex allocation systems exist.

# 18. Deployment Shape

Simple, scalable, and practical Alpha hosting.

- **Frontend**: Next.js deployment (Render Static Site).
- **Backend**: Render Web Service (FastAPI).
- **Database/Auth**: Supabase (Postgres + Auth).
- **Workers**: Initially bundled with backend service; split into dedicated Execution Workers later.

# 19. Failure Handling Standards

## AI Failure

User must still receive graceful fallback and retry path.

## Engine Failure

Show honest error + preserve conversation.

## Market Data Failure

Retry or explain temporary issue.

## Partial Failure

Never leave user confused.

# 20. Implementation Dependency Order

### Layer 1: Truth Layer
- `PRODUCT.md`
- `ARCHITECTURE.md`
- `API_CONTRACT.md`
- `DATA_MODEL.md`

### Layer 2: Runtime Foundation
- Auth
- Conversations
- Messages
- Persistence

### Layer 3: Intelligence Layer
- Onboarding prompts
- Extraction prompts
- Response streaming

### Layer 4: Engine Layer
- Templates
- Execution
- Metrics
- History

### Layer 5: Polish Layer
- Search
- Collections
- Feedback
- Feature flags

# 21. Architecture Decision Filter

When choosing any technical path, ask:

> *Does this preserve the separation between deterministic simulation truth, LLM-owned language, and contextual intelligence?*

If not, it likely should wait.

# 22. Agent Runtime Decision Filter

When writing any code that touches `agent_runtime/`, ask:

1. **Does this add a regex or early-return gate before the LLM call?** If yes, stop. Move the logic to the LLM system prompt instead.
2. **Does this store derived state in `TaskSnapshot`?** If yes, stop. Compute it fresh from `pending_strategy_summary` instead.
3. **Does this add natural language strings to a stage file?** If yes, stop. The LLM generates the response; stage files orchestrate only.
4. **Does this use `.invoke()` on the graph in production?** If yes, stop. Use `astream_events()` instead.
5. **Does this write session state outside the checkpointer?** If yes, stop. The checkpointer is the only session store.
6. **Does this add a second LLM call for intent classification?** If yes, stop. One classification call per turn.

If the answer to any of these is "yes", the change reintroduces the brittleness the runtime remediation exists to eliminate.
