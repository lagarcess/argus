# ARCHITECTURE.md

## Argus System Architecture Source of Truth (Alpha MVP)

**Status:** Active | **Alpha Architecture v1 Locked**
**Audience:** Engineers, AI agents, founders
**Purpose:** Define how Argus is structured technically, how systems communicate, where state lives, what services own what responsibilities, and how to build the Alpha MVP with low complexity and high iteration speed.

> [!IMPORTANT]
> **Locked Status**: No structural architecture shifts (service ownership changes or protocol swaps) are allowed without explicit approval. Additive refinements and implementation detail documentation are permitted.

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

Request in -> response out.

### AI Orchestrator (Stateless)

Build prompt -> call model -> parse response.
- **Rule**: Orchestrator memory is reconstructed per request from Supabase-backed conversation/profile state, with optional cache acceleration only.
- No durable or required session state is stored in orchestrator processes.

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
5. Engine runs simulation (using class-default benchmark)
6. Results persisted
7. Results streamed/rendered to user
8. Run appears in history

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

> *Does this help Argus deliver fast, trustworthy conversational idea testing with lower friction?*

If not, it likely should wait.