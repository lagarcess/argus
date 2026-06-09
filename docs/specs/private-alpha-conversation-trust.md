# Private Alpha Conversation Trust

Status: Working draft
Date: 2026-06-09
Audience: Founder, engineering agents, product/architecture review

## Purpose

This milestone hardens the current private-alpha conversation experience after
the workflow-backed backtest execution split. The goal is to make Argus feel
coherent, trustworthy, and harder to regress while preserving the architecture
that now works over the internet.

This is not a Perplexity Research Lab implementation milestone. Research Lab is
captured below as the next product thesis so the direction is not lost, but the
current milestone focuses on production-grade conversation trust for the
existing chat/backtest loop.

## Product Thesis

Argus should feel like a premium conversation workspace where investing
thinking accumulates. Each assistant turn should make clear:

- what Argus understood;
- what artifact, if any, Argus created;
- what state that artifact is in;
- what action the user can take next;
- whether Argus is finished and needs the user's attention;
- how the turn can be revisited, retried, shared, or reviewed later.

The current product already has strong pieces: workflow-backed job execution,
high-quality queued/running/result cards, durable Supabase state, and a canary
that detects LLM result-readout fallback drift. This milestone aligns the rest
of the conversation surface with that quality bar.

## Non-Negotiable Principles

- **Conversation remains the product.** Do not turn this into a dashboard or
  form-first workflow.
- **Frontend renders, it does not invent.** The web app may model local UI
  affordances, but backend-provided messages, artifacts, run facts, job facts,
  and persisted metadata remain source of truth.
- **No new chat brain.** LangGraph remains the only active conversational
  runtime.
- **No regex/NLU shortcuts before interpretation.** Normal language must reach
  the LLM-first interpreter before deterministic validation.
- **No deterministic voice expansion in happy paths.** Deterministic prose is
  allowed as fact building, validation, or explicit fallback only when
  observable.
- **No public sharing without privacy/revocation design.** Public conversation
  excerpts must be explicitly modeled before exposed to unauthenticated users.
- **Manual CD remains manual.** Add CI and local/manual canaries; do not enable
  auto-deploy.

## Scope

### In Scope

1. **CI baseline**
   - Re-enable a fast GitHub CI gate appropriate for the current codebase.
   - Cover backend lint, focused backend tests, frontend tests, frontend build,
     environment/render contract checks, and ownership gate.
   - Keep live Supabase writes and Render deploys out of automatic CI.

2. **Turn artifact UX unification**
   - Bring confirmation cards up to the visual and interaction quality of the
     queued/running/result cards.
   - Decide whether confirmation status remains visible or yields to a cleaner
     pending executable idea state once a durable job card exists.
   - Ensure confirmation, queued/running, succeeded, failed, canceled, and
     expired states hydrate consistently.

3. **Assistant turn action contract**
   - Thumbs up/down, retry where applicable, and more menu should be available
     on the latest assistant turn and on historical assistant turns on hover.
   - Action availability must be driven by structured turn/artifact metadata,
     not prose matching.
   - Feedback and retry must preserve the specific turn/action context.

4. **Out-of-focus chat attention**
   - When Argus finishes a turn in a conversation the user is not viewing, the
     side panel should show a subtle attention/unread state.
   - The state clears when the user opens that conversation.
   - The design should support future persisted unread state without requiring
     a database migration in the first pass unless local-only state proves
     insufficient.

5. **Small UX correctness fixes**
   - Empty composer send button gets a theme-aware tooltip: "Message is empty".
   - Restored archived/recently-deleted chats should reappear without confusing
     delay or stale list state.
   - The `@` composer feature should become a real, flexible Argus context tool
     instead of a static preview, within the existing supported context types.
     Asset selections must come from provider-backed discovery so the selected
     mention can bound the user's intended symbol/asset class before the backend
     resolver validates it.

6. **Result explanation cleanup**
   - Clarify the product distinction between Quick take, Explain result, and
     Try next.
   - Reduce overlap without creating a new deterministic result voice.
   - Preserve current LLM/schema-grounded readout provenance gates.

7. **Safe dead-code cleanup**
   - Remove or quarantine old dead code that is outside `archive-v0.1/`.
   - Avoid broad refactors unless they sit directly on touched boundaries.

8. **Docs and agent alignment**
   - Keep `docs/PRODUCT.md`, `docs/ARCHITECTURE.md`, `docs/API_CONTRACT.md`,
     `docs/DATA_MODEL.md`, `.agent/designs/argus/DESIGN.md`, and `AGENTS.md`
     aligned when this milestone introduces durable concepts or agent rules.

### Conditional Scope

**Public conversation excerpts** are included only as a design/spec slice unless
the privacy/revocation model is settled. The desired product is:

- user selects a subset of conversation turns;
- Argus serializes a minimal self-contained read-only view;
- Argus creates a unique unauthenticated public URL;
- the public page renders those turns like the original UI;
- owner can revoke/delete the excerpt.

Because this exposes content publicly, it must not be squeezed in as a
replacement for "copy conversation id".

### Out Of Scope For This Milestone

- Perplexity Research Lab implementation.
- Daily brief/inbox automation.
- Portfolio abstractions.
- New RAG/vector memory.
- TradingView comparison chart expansion unless a concrete current result UX
  cleanup requires it.
- Automatic production deploys.
- Supabase preview branches that add cost.

## Slices

### Slice 1: CI Baseline

Goal: make the repository catch obvious regressions before future work piles up.

Expected automated checks:

- ownership gate;
- `poetry run ruff check src tests workflows scripts`;
- focused backend tests:
  - `tests/test_environment_scripts.py`
  - `tests/test_api_import_boundary.py`
  - `tests/test_render_canary_script.py`
  - artifact/action tests touched by this milestone as they are added;
- `cd web && bun test`;
- `cd web && bun run build`.

CI must not:

- run live Render deploys;
- write to live Supabase;
- require private secrets for PR checks;
- run expensive browser matrices by default.

### Slice 2: Turn Artifact UX Unification

Goal: confirmation, job, and result artifacts feel like one coherent family.

Design direction:

- confirmation cards should use the same level of polish, status language, and
  stable dimensions as queued/running/result cards;
- status should be meaningful to the current lifecycle, not duplicated after a
  job card takes over;
- historical cards should remain understandable after reload;
- card actions should live where the artifact owns the action.

Hard guardrails:

- no frontend-invented strategy state;
- no duplicate run buttons across composer/footer/card surfaces;
- no local timers faking backend stage progress.

### Slice 3: Assistant Turn Actions

Goal: feedback, retry, and more-menu actions are consistently available without
cluttering the conversation.

Expected behavior:

- latest assistant turn shows the action collection persistently;
- previous assistant turns reveal the action collection on hover/focus;
- actions disappear when focus leaves that turn;
- retry appears only for retryable failures or actions with structured retry
  metadata;
- feedback attaches to the exact message/artifact context.

### Slice 4: Chat Attention State

Goal: if the user leaves a chat while Argus is still working, the side panel
quietly shows that chat needs attention when Argus finishes.

Expected behavior:

- active conversation never marks itself unread because of its own visible
  assistant completion;
- inactive conversation gets a subtle unread/attention treatment after an
  assistant turn reaches a final state;
- opening the conversation clears the attention state;
- refresh/reload behavior is explicit and tested.

### Slice 5: Composer And Restore Polish

Goal: fix small UX smells that reduce trust.

Included:

- empty send tooltip;
- restore-from-archive/recently-deleted list refresh;
- `@` composer context tool upgrade.

The `@` feature should stay within current Alpha capabilities. In this milestone
it surfaces provider-backed asset discovery and the existing indicator catalog
only. It must not pretend a tiny static list is the available universe.
Selected mentions remain composer provenance: they help bound ambiguous user
references, but they do not bypass LLM interpretation or backend validation.

Latency for this slice uses the existing server-side provider catalog cache in
the market-data layer plus bounded `/discovery/*` queries. Supabase-backed
discovery or market-data caching is deferred to a dedicated latency/freshness
slice because it needs schema ownership, invalidation, and market-clock policy.

### Slice 6: Result Explanation Cleanup

Goal: make Quick take, Explain result, and Try next complementary.

Working distinction:

- **Quick take:** concise, first-glance interpretation attached to the result.
  It may validate supported next experiments for provenance, but it should not
  render them as a visible "Try next" section.
- **Explain result:** deeper, fact-grounded breakdown when the user asks.
  It must not reuse "Quick take" or "Quick breakdown" as section framing.
- **Try next:** supported next experiment, not generic advice and not a buried
  afterthought.

Hard guardrails:

- no unsupported causality;
- no deterministic happy-path prose expansion;
- no frontend-generated result explanation;
- result-readout source/fallback metadata remains observable.
- fallback copy remains explicitly marked by provenance and follows the same
  surface ownership rules when the LLM path is unavailable.

### Slice 7: Public Conversation Excerpt Design

Goal: replace "share conversation id" with a real public excerpt plan before
implementation.

Status: design-only for this milestone. Do not expose unauthenticated sharing in
this branch.

Target product behavior:

1. The top-right conversation menu offers **Share excerpt**, not "copy
   conversation id", once the feature is implemented.
2. The user enters excerpt selection mode and selects an ordered subset of turns
   from the current conversation. Non-contiguous turns are allowed but always
   rendered in original conversation order. The first implementation should cap
   excerpts at 20 turns.
3. Argus shows a preview of the read-only excerpt before creation.
4. Creating the excerpt snapshots the selected turns into a self-contained public
   artifact and returns a high-entropy public URL.
5. The public URL is unauthenticated and read-only. Anyone with the link can view
   the selected turns until the owner revokes the excerpt.

Data model:

- Add `public.conversation_excerpts`.
- Columns:
  - `id uuid primary key`;
  - `slug text unique not null`, generated from at least 128 bits of entropy;
  - `owner_user_id uuid not null`;
  - `source_conversation_id uuid not null`;
  - `title text`;
  - `status text not null check (status in ('active', 'revoked'))`;
  - `turn_count integer not null`;
  - `snapshot jsonb not null`;
  - `created_at timestamptz not null`;
  - `updated_at timestamptz not null`;
  - `revoked_at timestamptz`;
  - `expires_at timestamptz`.
- Use one immutable `snapshot` payload instead of a live join into messages. The
  public page renders the snapshot only, so later private conversation changes do
  not leak accidentally.
- `expires_at` is optional and can stay null for owner-revocable links. If the
  privacy posture changes later, a default expiration policy can be added without
  changing the public route shape.

Snapshot contract:

- Include only display-safe turn data:
  - role;
  - localized visible text;
  - display timestamp if needed;
  - selected confirmation/job/result card render payloads;
  - chart/display payloads already safe for frontend rendering.
- Exclude:
  - source conversation id in the public response;
  - user id, email, profile data, auth metadata;
  - message ids unless replaced with excerpt-local ids;
  - route receipts, OpenRouter/provider metadata, prompts, model names, token
    usage, job launch payloads, raw run config snapshots, feedback records,
    hidden retry payloads, and any backend-only provenance.
- Disallow sharing nonterminal queued/running job cards in the first
  implementation. Terminal result and failed-job artifacts may be shared if their
  public payload is already sanitized.

API contract:

- Authenticated owner endpoints:
  - `POST /api/v1/conversations/{conversation_id}/excerpts`
  - `GET /api/v1/conversation-excerpts`
  - `DELETE /api/v1/conversation-excerpts/{excerpt_id}` or a revoke `PATCH`.
- Public endpoint:
  - `GET /api/v1/public/conversation-excerpts/{slug}`
- The public endpoint returns sanitized snapshot data only. It must not require
  Supabase Auth, must not reveal whether a private conversation exists, and must
  return `404` or `410` for revoked/expired excerpts.
- Do not grant direct `anon` table privileges for the excerpt table. Prefer the
  FastAPI public endpoint as the public read boundary so the database table can
  keep strict RLS and the API can enforce response redaction/rate limits.

Ownership and security:

- Creation validates that the authenticated user owns the source conversation and
  every selected turn.
- Revocation is owner-only and immediate.
- Account deletion or source-conversation hard deletion revokes or deletes owned
  excerpts.
- RLS stays enabled. Authenticated users can list/create/revoke only their own
  excerpts. `anon` and `public` roles get no direct table grants.
- Slugs are unguessable and never derived from `conversation_id`.
- Public excerpt reads are rate-limited and cacheable only for active sanitized
  snapshots.

Frontend rendering:

- The public page should use read-only variants of existing chat message,
  confirmation, job/result, and breakdown components where possible.
- Hide all mutation affordances: composer, sidebar, thumbs, retry, more menus,
  save strategy, refine, and feedback.
- Show only minimal context: Argus branding, excerpt title, selected turns, and
  education/not-financial-advice footer.

Verification requirements before implementation can be merge-ready:

- backend tests for owner-only create/revoke and foreign conversation rejection;
- public response redaction tests proving internal ids/metadata are excluded;
- RLS/grant test proving no direct `anon`/`public` table access;
- frontend test for selection mode, preview, generated link, and revoked-link
  handling;
- manual browser smoke on a local fixture conversation;
- no live public-link canary until the founder explicitly approves creating a
  durable public artifact.

## Research Lab Thesis For Next Milestone

The larger product direction is strong and should be preserved separately:

Argus becomes a simplified research lab where users can educate themselves,
observe markets, form hypotheses, test supported ideas, explain outcomes,
compare alternatives, refine experiments, monitor changes, and share artifacts.

Perplexity Agent API is a candidate research provider because it supports
multi-provider access, tool use, model fallback chains, streaming, source
results/citations, presets, and finance/web/people/fetch-url tools.

The first Research Lab slice should be **Research-to-Test Bridge**:

1. user asks a broad finance question;
2. Argus performs cited research through Perplexity;
3. Argus extracts only supported, testable hypotheses;
4. Argus presents pre-baked confirmation cards for ideas it can actually test;
5. current workflow-backed backtesting executes the selected idea;
6. Argus explains and suggests supported next experiments.

Research Lab must update canon docs before implementation because it broadens
Argus from "strategy builder chat" to "durable investing thinking workspace".

## Existing Debt Carried Forward

From the private-alpha execution milestone:

- result-facing deterministic prose must remain audited;
- route receipts can still be lost on mid-stream process failure;
- `public.set_updated_at` still has a Supabase security hygiene warning;
- Supabase migration history has older drift;
- Render Workflow CPU/peak RSS need platform-level measurement;
- async failure taxonomy is coarse;
- currency-pair benchmark normalization has a known correctness test failure in
  broader recovery work;
- large mixed-concern runtime files should be refactored only when a cohesive
  touched boundary justifies it.

New debt or smells from this milestone inventory:

- confirmation card presentation lags behind job/result card quality;
- assistant turn actions are not consistent across text, confirmation, job, and
  result turns;
- inactive chat completion is not clearly surfaced in the side panel;
- current share action exposes an internal conversation id instead of a real
  public excerpt artifact;
- streaming/error behavior needs a stronger contract before broader provider
  streaming changes;
- Quick take, Explain result, and Try next overlap enough to confuse product
  hierarchy.

Addressed in this branch:

- confirmation, job, result, and assistant-turn actions now share one artifact
  action ownership model for the current chat surface;
- inactive completed turns now create a local side-panel attention marker that
  clears when the user opens the conversation;
- the empty composer send button now has a localized, theme-aware tooltip and
  a stable, optically centered control slot;
- restoring archived or recently deleted chats now notifies the owning history
  surface to refresh visible recents;
- the `@` composer affordance now behaves as a keyboardable, provider-backed
  listbox for asset and indicator discovery, with selected assets preserved as
  bounded mention provenance for backend validation.
- Quick take no longer renders supported next experiments as visible next-check
  prose, and Explain result rejects "Quick take" headings while using a deeper
  Setup / How to read it / Risk and assumptions / Useful next check fallback.
- retired `src/argus/api/chat_service.py` has been deleted, and static guards now
  fail if launch code or tests import the old facade.

## Hard Gates

This milestone is not merge-ready until:

- CI baseline passes locally and in GitHub for the milestone branch.
- Frontend build passes.
- Focused backend tests pass without live Supabase writes.
- Existing canary remains available for manual release gates.
- New UI behavior has tests covering hydration/reload where relevant.
- No user-facing result voice regression is introduced.
- Docs and `AGENTS.md` reflect any new durable architecture/product rules.
- `main` remains untouched except through normal protected review/merge flow.

## Local Baseline Evidence

Initial sandbox baseline on `codex/private-alpha-conversation-trust` from
`origin/main`:

```text
poetry run pytest tests/test_environment_scripts.py tests/test_api_import_boundary.py tests/test_render_canary_script.py -q --no-cov
# 38 passed

poetry run ruff check src tests workflows scripts
# passed

cd web && bun test
# 155 passed

cd web && bun run build
# passed
```

## Operating Model

- Work happens in isolated branch/worktree slices.
- Each coherent slice gets a conventional commit.
- Pushes are allowed for traceability.
- Do not open PRs unless explicitly requested.
- Do not merge to `main`.
- Run local verification before claiming a slice is complete.
- Use Docker/local Supabase when it reduces internet dependency.
- Use live providers only when the slice requires production-like behavior.
