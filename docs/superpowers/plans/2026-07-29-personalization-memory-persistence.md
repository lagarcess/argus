# Argus Personalization Memory Persistence Implementation Plan

Status: **APPROVED INCUBATION EXECUTION PLAN — persistence checkpoint only**

> **For agentic workers:** REQUIRED SUB-SKILLS: Use
> `superpowers:subagent-driven-development`,
> `superpowers:test-driven-development`, and `supabase:supabase` to implement
> this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the verified personalization-memory domain tranche onto exact
integration SHA `88ab906dae8e329a526d4ada57318b6b7adcbc5d`, then add complete,
owner-scoped Postgres persistence whose database-canonical identity checks make
personalization memory unavailable to Guest users before any durable state or
conversion side effect.

**Architecture:** Keep `MemoryService` and its typed `CanonicalMemoryStore`
boundary as the product owner. Add one synchronous psycopg-backed store used by
future backend wiring, plus normalized private persistence tables. The tables
are not Data API surfaces: `anon`, `authenticated`, and `service_role` receive
no direct table privileges. Database triggers validate registered account truth
from `auth.users.is_anonymous` and active Guest workspace state before every
insert or update. A Guest-workspace claim trigger fails both same-identity link
and different-identity handoff transactions if any Guest memory state exists.
Canonical memory remains structured Argus-owned data; provider references are
derivative metadata only.

Two reviewed domain gaps must close before schema work: conversion zero-state
must count consent and reconciliation state, and every scope expansion must
create exact immutable consent evidence. The persistence migration must also
atomically revalidate ownership and the recorded revision of canonical
DecisionNote/Evidence provenance. These are repairs required by the already
approved privacy outcome, not new product scope.

**Tech Stack:** Python 3.10.20, Pydantic v2, psycopg 3, psycopg-pool,
PostgreSQL 17, Supabase CLI 2.109.0, PL/pgSQL, pytest, Ruff, and mypy.

## Global Constraints

- Authoritative base:
  `88ab906dae8e329a526d4ada57318b6b7adcbc5d`
  (`origin/codex/private-alpha-next` after the 2026-07-29 refresh).
- Read-only donor:
  `8b7ef339325b763c6396d7ed66e5f85835fcbbbc`
  (`origin/claude/argus-personalization-memory-2a6257`).
- Base/donor merge base:
  `390d57294cf9911becdb14ced126770d0124e4cb`.
- Base/donor divergence at branch creation: `90` base-only / `13` donor-only.
- Work only on
  `codex/personalization-memory-incubation-persistence-v1`.
- Do not merge, rebase, or cherry-pick the donor. Port only accepted Argus
  behavior from the verified Codex domain checkpoint.
- This is an isolated production-intent incubation. It does not override the
  roadmap's post-PMF integration/exposure gate.
- Read the exact-base versions of `docs/PRODUCT.md`,
  `docs/ARCHITECTURE.md`, `docs/API_CONTRACT.md`, `docs/DATA_MODEL.md`,
  `.agent/designs/argus/DESIGN.md`,
  `docs/specs/private-alpha-next-roadmap.md`, and the complete
  `docs/specs/private-alpha-next-decision-memo.md` before implementation.
- Structured Argus-owned product memory comes before generic RAG. Do not add
  embeddings, pgvector, LangMem, Mem0, a network provider, or transcript
  mining.
- Memory is off by default. A candidate is not a record. Explicit allowed
  confirmation is the only record-creation path.
- Direct enablement and candidate confirmation each create one immutable,
  idempotent consent action receipt. The receipt distinguishes the exact
  requested, newly granted, and complete effective scope.
- Guest denial must use database-canonical account truth and happen before
  candidate, settings, consent, prompt history, record, provider metadata,
  retrieval, or conversion side effects.
- Guest conversion starts at zero and never transfers or retrospectively mines
  Guest history. A corrupt Guest memory row blocks the conversion transaction.
- Durable zero-state counts settings, candidates, consent receipts, records,
  provenance rows, prompt/decline history, in-flight reconciliation, cleanup
  targets, and provider projections. Caller-supplied digests are never
  authoritative for conversion.
- Canonical EvidenceArtifact, DecisionNote, Idea, IdeaVersion, conversation,
  and message records remain source truth. Memory stores provenance pointers
  and cannot rewrite those artifacts.
- Memory cannot influence interpretation, routing, simulation, confirmation
  truth, execution, metrics, or canonical evidence.
- `anon`, `authenticated`, and `service_role` get no direct privileges on
  personalization-memory tables. The future API must call the backend adapter
  through its direct database connection after canonical auth derivation.
- No API endpoint, runtime consumer, UI, Data Controls component, analytics
  sink, provider, hosted Supabase mutation, deployment, integration mutation,
  or production exposure belongs in this checkpoint.
- Use a disposable lane-unique local Supabase project. Do not touch the
  canonical `argus-qa` stack or unrelated Docker containers, networks, volumes,
  images, or caches.
- Use TDD for every behavior: record the expected red failure, implement the
  smallest safe change, run focused green, then the accumulated memory suite.
- Each use-case commit must be independently green, conventional, reversible,
  and free of merge commits.
- Every implementation task gets a fresh bounded implementation worker and a
  fresh review. Critical and Important findings are fixed and re-reviewed
  before the next task. Workers share the checkout and must not revert adjacent
  changes.
- Stop if a requirement needs API, runtime, UI, analytics, live providers,
  hosted data, deployment, or a privacy/correctness compromise.

## Memo Traceability

| Requirement | Exact authority | Persistence disposition | Owning evidence |
|---|---|---|---|
| Durable product memory differs from one-off analysis | §2.3 | Structured records only; no transcript persistence | Domain port + schema tests |
| Canonical artifacts, evidence, provenance, decision memory | §5.3–§5.6 | Records retain typed canonical provenance; no source artifact mutation | Tasks 2–4 |
| Argus owns product truth and may leverage infrastructure | §7.1–§7.2 | Argus tables/store canonical; provider refs derivative | Tasks 2 and 5 |
| Structured memory before generic RAG | §10.5 | No vector/RAG/provider implementation | Import and migration gates |
| Decision Capture, Omnisearch, Memory Inspector | §11 | DecisionNote provenance and inspector-ready queries; API/UI/Omnisearch wiring deferred | Tasks 3–4 |
| Explicit/assisted memory aggressiveness | §12.3 | Scoped settings, candidate history, explicit confirmation | Tasks 2–3 |
| Opacity, privacy, regulatory, and trust risk | §13 | RLS/grants, registered-owner triggers, provenance, deletion/reset | Tasks 1 and 4–6 |
| Evaluation as infrastructure | Follow-up item | Deterministic domain seams persist unchanged; shared eval runtime deferred | Domain tests + final matrix |
| Compliance, consent, data rights | Follow-up item | Versioned receipt, inspect/edit/delete/disable/reset persistence | Tasks 3–4 |
| Cost and latency routing | Follow-up item | Provider reconciliation metadata only; CostLedger wiring deferred | Task 5 |
| Memory privacy controls | Follow-up item | Durable settings and complete controls | Tasks 2–4 |
| Artifact commitment boundary | §15.1 | Candidate and receipt remain separate from canonical record | Task 3 |
| Memory Product Posture | §15.3 | Complete persistence under default-off, scoped-confirmation contract | Tasks 1–6 |
| Evaluation/cost/analytics | §15.5 | Existing typed seams retained; no analytics content persisted | Final verification |
| Broker/export suppression | §15.6 | Existing deterministic domain suppression retained | Port verification |
| PMF gates | §15.8 | Incubation only; no activation or integration claim | Contract and Draft PR |
| P2 Memory Boundary | §16.1 | Founder authority opens isolated incubation only | Contract reconciliation |
| Artifact/version/freshness/PMF boundaries | §16.2–§16.4 | Provenance references never mutate artifact or freshness truth | Migration constraints + tests |
| Curated, note-aware decision recall | Integration commit `88ab906d` | Memory points at canonical DecisionNotes/EvidenceArtifacts and does not replace Omnisearch | Tasks 3–4 |

## Planned Files

Create:

- `docs/specs/lanes/personalization-memory-contract.md`
- `docs/superpowers/plans/2026-07-29-personalization-memory-persistence.md`
- `.superpowers/sdd/personalization-memory-persistence/progress.md`
- `src/argus/memory/postgres_store.py`
- `tests/memory/test_consent_integrity.py`
- `tests/memory/test_postgres_store_settings_candidates.py`
- `tests/memory/test_postgres_store_confirmation.py`
- `tests/memory/test_postgres_store_controls.py`
- `tests/memory/test_postgres_store_provider_reconciliation.py`
- `tests/memory/test_postgres_guest_isolation.py`
- `supabase/migrations/20260729225600_add_personalization_memory_persistence.sql`

Port from the accepted Codex checkpoint:

- `src/argus/memory/**`
- `tests/memory/**`

Modify:

- `src/argus/memory/__init__.py`
- `docs/DATA_MODEL.md`
- the current lane contract

No API, OpenAPI, runtime, observability, web, provider, or deployment file may
change.

---

## Task 0: Reconcile the contract and port the verified domain checkpoint

**Files:**

- Create: `docs/specs/lanes/personalization-memory-contract.md`
- Create:
  `docs/superpowers/plans/2026-07-29-personalization-memory-persistence.md`
- Port: `src/argus/memory/**`
- Port: `tests/memory/**`

- [ ] Record the refreshed integration SHA, donor SHA, merge base, `90/13`
  divergence, changed paths, and the semantic overlap with note-aware
  Omnisearch.
- [ ] Update the lane contract so the later founder authority opens only the
  isolated persistence surface. Keep API, runtime, UI, provider, analytics,
  hosted DB, deploy, merge, and exposure closed.
- [ ] Port each accepted domain use-case commit from
  `codex/personalization-memory-incubation-v2` without bringing donor history.
- [ ] After each ported commit, run:

```bash
poetry run pytest tests/memory -q --no-cov
git diff --check
```

- [ ] Run the lane validator:

```bash
python3 /Users/garces/.codex/skills/argus-development-lane-planner/scripts/validate_lane_contract.py \
  docs/specs/lanes/personalization-memory-contract.md
```

- [ ] Commit the reconciled contract first:

```text
docs(memory): open isolated persistence incubation
```

- [ ] Preserve the six accepted domain commits as separate green use-case
  commits.

### Task 0A: Repair consent and conversion truth before persistence

**Files:**

- Modify: `src/argus/memory/contracts.py`
- Modify: `src/argus/memory/conversion.py`
- Modify: `src/argus/memory/service.py`
- Modify: `src/argus/memory/store.py`
- Modify: `src/argus/memory/policy.py`
- Modify: `src/argus/memory/__init__.py`
- Create: `tests/memory/test_consent_integrity.py`
- Modify: `tests/memory/test_conversion_zero_state.py`

- [ ] Add red tests proving a receipt-only Guest or same-identity destination
  is non-zero and rejected. Include provenance and reconciliation state in the
  digest contract.
- [ ] Add a frozen `MemoryConsentActionReceipt` with action
  `direct_enable | candidate_confirmation`, exact `requested_scope`,
  `granted_scope`, `effective_scope`, candidate identity when applicable,
  schema/policy version, timestamp, and idempotency key.
- [ ] Make direct enable plus receipt creation atomic. Repeating an already
  effective enable is idempotent and creates no receipt.
- [ ] Make candidate confirmation create one receipt and one record atomically.
  The receipt records the exact scope shown/requested, newly granted scope, and
  complete post-action scope. The record validates its category against the
  effective scope.
- [ ] Receipts survive individual record deletion and disable, but reset/account
  deletion removes them.
- [ ] Replace enum-derived safe categories with an explicit literal allowlist;
  a new enum member is denied until reviewed.
- [ ] Bind sensitivity assessment to a policy version and exact content digest.
  Bound stored value and future-benefit lengths, require primary candidate
  provenance equality, and revalidate the bound assessment at confirmation.
- [ ] Add `revision` and `updated_at` to `MemoryRecord`; edit changes only
  value/label/revision/updated time while identity, category, receipt, and
  provenance stay immutable.
- [ ] Record red/green evidence, run the full memory suite and static checks,
  then commit the repairs in two independently green chunks:

```text
fix(memory): count complete conversion zero state
fix(memory): record exact scoped consent evidence
```

## Task 1: Add private durable schema and database-canonical Guest guards

**Files:**

- Create:
  `supabase/migrations/20260729225600_add_personalization_memory_persistence.sql`
- Modify: `docs/DATA_MODEL.md`
- Create: `tests/memory/test_postgres_guest_isolation.py`

- [ ] Start a lane-unique local Supabase stack only after recording Docker
  context and current resource ownership. Use a scratch copy of `supabase/`
  whose project id and ports cannot collide with `argus-qa`.
- [ ] Create the empty migration with:

```bash
supabase migration new add_personalization_memory_persistence
```

- [ ] Write a real-Postgres test that first fails because the memory tables,
  grants, triggers, and conversion zero-state guard do not exist.
- [ ] Add owner-keyed settings, candidate, consent-action receipt, record,
  provenance, prompt history, in-flight reconciliation, and provider-cleanup
  tables. Provider pointers remain derivative fields, never canonical content.
- [ ] Add constraints for closed categories, non-empty scoped consent,
  canonical receipt/record linkage, immutable owner and provenance identity,
  bounded labels, non-negative generations, and owner-scoped foreign keys.
- [ ] Enable and force RLS on every table. Revoke all table and sequence
  privileges from `public`, `anon`, `authenticated`, and `service_role`.
- [ ] Add one `SECURITY DEFINER` registered-owner predicate with
  `search_path = ''`. Table triggers call it before every insert/update using
  `auth.users.is_anonymous` and Guest workspace status.
- [ ] Add a `BEFORE UPDATE` trigger on `guest_workspaces` that rejects a move to
  `claimed` when any source Guest memory state exists. This guards both
  same-identity link and existing-account handoff without adding memory to the
  transfer graph.
- [ ] Prove with real Postgres:
  anonymous-JWT denial, registered-JWT denial, service-role denial, direct
  backend registered insertion success, direct backend Guest insertion
  rejection, cross-owner isolation, same-identity conversion zero state,
  handoff zero state, and corrupt Guest state fail-closed behavior.
- [ ] Run the existing Guest Postgres suites to detect handoff regression.
- [ ] Commit:

```text
feat(memory): add registered-only durable memory schema
```

## Task 2: Persist settings, candidates, and proactive history atomically

**Files:**

- Create: `src/argus/memory/postgres_store.py`
- Create: `tests/memory/test_postgres_store_settings_candidates.py`
- Modify: `src/argus/memory/__init__.py`

- [ ] Add failing store-contract tests for default-off reads, scoped enable,
  settings replacement, candidate add/get/list/discard, atomic proactive prompt
  compare-and-set, atomic decline history, owner isolation, duplicate IDs, and
  registered-owner revalidation.
- [ ] Implement `PostgresCanonicalMemoryStore` over an injected
  `psycopg_pool.ConnectionPool`. Validate UUID owner ids before opening a
  transaction.
- [ ] Each public store operation calls database-canonical registered-owner
  validation before reading or mutating memory tables.
- [ ] Serialize candidate/history admission with a transaction-scoped advisory
  lock keyed by owner and category. Stale expected history returns `False`
  without candidate or history mutation.
- [ ] Round-trip all persisted values through the existing frozen Pydantic
  contracts.
- [ ] Run focused red/green, accumulated memory tests, Ruff, format, and mypy.
- [ ] Commit:

```text
feat(memory): persist scoped candidates and consent settings
```

## Task 3: Make confirmation, consent, provenance, and record creation atomic

**Files:**

- Modify: `src/argus/memory/postgres_store.py`
- Create: `tests/memory/test_postgres_store_confirmation.py`

- [ ] Add failing tests for confirmation as the only record-creation path,
  candidate row locking, expired/missing candidate no-op behavior, scoped
  settings union, exact versioned consent-action receipt creation, canonical
  record/provenance round-trip, candidate consumption, ID collision rollback,
  owner isolation, and confirmation replay.
- [ ] Implement one transaction that locks the candidate, creates the receipt
  and record, updates scoped settings, registers reconciliation generation one,
  and consumes the candidate.
- [ ] In that same transaction, revalidate every primary/supporting provenance
  row against the registered owner. For saved decisions, validate the current
  `DecisionNote`, linked `EvidenceArtifact`, and recorded DecisionNote
  `updated_at` revision. A mismatch consumes nothing and creates nothing.
- [ ] Ensure any clock, ID, validation, constraint, or collision failure rolls
  back the entire transaction and leaves the candidate pending.
- [ ] Prove DecisionNote and EvidenceArtifact provenance ids are preserved and
  no source artifact row is updated. Memory is a sidecar and never an
  Omnisearch/Recents/decision source.
- [ ] Run focused red/green and the accumulated verification set.
- [ ] Commit:

```text
feat(memory): persist atomic confirmed memory records
```

## Task 4: Persist retrieval and complete user controls

**Files:**

- Modify: `src/argus/memory/postgres_store.py`
- Create: `tests/memory/test_postgres_store_controls.py`

- [ ] Add failing tests for bounded deterministic list/get, receipt listing,
  inspect/explain support, edit atomicity, delete, disable, reset, enabled
  category filtering, cross-owner isolation, and reset-to-zero completeness.
- [ ] Keep record identity, candidate identity, receipt, provenance, category,
  and creation time immutable during edit.
- [ ] Disable clears settings, candidates, and prompt/decline history while
  retaining inspectable confirmed records.
- [ ] Reset waits for prior reconciliation work and atomically removes every
  owner row from all memory tables without touching canonical Argus artifacts.
- [ ] Use bounded ordered queries; no generic semantic retrieval or transcript
  search.
- [ ] Run focused red/green and the accumulated verification set.
- [ ] Commit:

```text
feat(memory): persist inspectable memory controls
```

## Task 5: Persist provider reconciliation without making it canonical

**Files:**

- Modify: `src/argus/memory/postgres_store.py`
- Create:
  `tests/memory/test_postgres_store_provider_reconciliation.py`

- [ ] Add failing tests for provider ref set/get, ordered reconciliation
  generations, compare-and-set, losing projection cleanup, cleanup target
  tracking/resolution, delete/reset waiting, cross-owner independence, and
  restart durability.
- [ ] Use owner-and-record transaction advisory locks for generation
  allocation. Store in-flight generations and cleanup targets as inspectable,
  owner-scoped derivative metadata.
- [ ] Implement bounded database waiting for reconciliation turn with no
  process-local truth. Provider exceptions remain outside the store and cannot
  roll back canonical confirmation, edits, deletion, or reset.
- [ ] Prove canonical record rows remain authoritative when provider metadata
  is absent, stale, or marked for cleanup.
- [ ] Run focused red/green, concurrency repeats, and accumulated verification.
- [ ] Commit:

```text
feat(memory): persist provider reconciliation state
```

## Task 6: Run full-stack privacy, conversion, and regression proof

**Files:**

- Modify tests only if a verified coverage gap requires it.
- Update:
  `.superpowers/sdd/personalization-memory-persistence/progress.md`

- [ ] Reset the lane-unique local Supabase stack from all checked-in
  migrations.
- [ ] Run:

```bash
ARGUS_DISPOSABLE_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:<lane-db-port>/postgres \
  poetry run pytest tests/memory -q --no-cov

ARGUS_DISPOSABLE_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:<lane-db-port>/postgres \
  poetry run pytest \
    tests/test_guest_workspace_postgres.py \
    tests/test_guest_handoff_postgres.py \
    -q --no-cov

poetry run ruff check src/argus/memory tests/memory
poetry run ruff format --check src/argus/memory tests/memory
poetry run mypy src/argus/memory tests/memory
poetry run ruff check src tests workflows scripts

OPENROUTER_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest tests/agent_runtime tests/test_spine_guardrails.py \
  -q --no-cov
```

- [ ] Prove no production consumer imports `argus.memory`, no provider/network
  package entered the tranche, no donor ancestry exists, no merge commit
  exists, and every commit is path-bounded and green.
- [ ] Run `git diff --check` and list exact changed files and commits.
- [ ] Run the lane contract validator and repair every failure.
- [ ] Stop and remove only the lane-unique Supabase resources. Confirm the
  canonical `argus-qa` and unrelated Docker resources are untouched.

## Task 7: Independent review and persistence Draft PR checkpoint

- [ ] Run one independent whole-branch memory/privacy/security review against
  exact base `88ab906d`.
- [ ] Fix and re-review all Critical or Important findings using fresh workers.
- [ ] Push only
  `codex/personalization-memory-incubation-persistence-v1`.
- [ ] Create a Draft PR targeting `codex/private-alpha-next`. Do not mark it
  ready and do not merge it.
- [ ] Refresh integration read-only. Record its latest SHA and divergence
  without rebasing or merging.
- [ ] Report the frozen previous branch
  `codex/personalization-memory-incubation-v2` as retained until the cumulative
  persistence checkpoint is accepted, then eligible for remote deletion.
- [ ] Report commits by use case, changed files, exact test/static evidence,
  contract deviations, unresolved decisions, next API/Data Controls/runtime
  slices, and confirmation that no forbidden surface was touched.

## Persistence Checkpoint Stop

Stop at the Draft PR. The next cumulative branch starts fresh from the then
latest integration SHA, ports the accepted persistence checkpoint commit by
commit, and adds only the API slice. Never rebase the frozen persistence branch
to chase integration.
