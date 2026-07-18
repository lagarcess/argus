# Personalization Memory Program

Status: **PROPOSED — founder review pending. Not an active dispatch source.**

Date: 2026-07-18

Base: `claude/argus-personalization-memory-2a6257` at `390d5729` (same SHA as
`codex/private-alpha-next` tip at authoring time)

This document proposes the full personalization-memory program and records the
one walking skeleton implemented alongside it. It does not authorize activation.
Per decision memo §16.1, user-facing personalization memory — including a
user-confirmed `MemoryRecord` — stays post-PMF and requires earned opt-in plus
inspect/edit/delete/reset/disable/"why was this used?" controls. Nothing in this
program changes that boundary; the program prepares the machinery so activation
is a small, reviewable step when the founder opens it.

Authority order if documents disagree: canon docs (`PRODUCT.md`,
`API_CONTRACT.md`, `DATA_MODEL.md`, `ARCHITECTURE.md`, `DESIGN.md`), then
`docs/specs/private-alpha-interim-roadmap.md` for current ownership, then
`docs/specs/private-alpha-next-roadmap.md` for the paused P2 arc, then this
proposal.

Sources this proposal is built from:

- decision memo §5.6 (Decision memory), §15.3 (Memory Product Posture, including
  canonical memory categories and the Data Controls menu shape), §16 (Founder
  Resolution Addendum, especially §16.1);
- decision memo Slice H (Memory inspector MVP) and Slice I (analytics events);
- `docs/ARCHITECTURE.md` "Structured Recall Versus Personalization Memory" and
  "Deferred Direction" (no pgvector/embeddings in the launch loop);
- `docs/DATA_MODEL.md` §12.1 (P1 idea/evidence/decision spine and its RLS
  pattern) and §12.1.1 (observability envelope);
- the interim roadmap's Shared-Surface Serialization Matrix and Global Stop
  Conditions;
- the P2 roadmap's A1b/A2/A3/A4 cards.

## 1. Overnight Run Goal (bounded, 2026-07-18)

This section is the bounded Goal that governed the overnight run that produced
this document and the walking skeleton.

- **Outcome:** this proposed roadmap plus one locally functional walking
  skeleton proving the core memory lifecycle at domain/service level, committed
  locally in this worktree only.
- **Verification surfaces:** deterministic pytest under `tests/memory/`, ruff
  and mypy on the new package, `git diff --check`, and a hermetic
  agent-runtime sweep proving the runtime spine is untouched. All test
  invocations blank provider keys and force
  `ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture` because this nested
  worktree can inherit the parent `.env`.
- **No-touch areas:** interpreter/runtime spine (`runtime.py`,
  `interpret_types.py`, `llm_interpreter.py`, stages), `agent.py`, Profile
  menu/Data Controls UI, Omnisearch/search projection, result-card actions,
  `supabase_gateway.py`, `supabase/migrations/`, OpenAPI/public endpoints,
  A1b/A2/A4 code, deployment/release configuration, `tests/evals`, and every
  file owned by an active interim issue. The overnight diff contains only new
  files.
- **Stop conditions:** any need to edit a shared interim file, apply a
  migration, add a public endpoint, call a live provider, weaken a privacy or
  correctness requirement, or recreate A1b/A2/A4/recall behavior stops that
  portion and records the gate here instead.
- **Walking-skeleton use case:** explicit request or saved-decision fixture →
  typed `MemoryCandidate` → category/sensitivity/consent/suppression policy →
  explicit confirmation → canonical `MemoryRecord` → bounded retrieval with
  provenance and "why was this used?" → edit/delete → disable/reset. In-memory
  canonical store, deterministic fake provider behind an Argus-owned interface,
  synthetic data only, default-off configuration, no UI, no runtime wiring, no
  network.

## 2. Product Intention

Personalization that gives users a reason to return:

- Argus remembers confirmed decisions and explicit "remember this" requests;
- it recalls relevant preferences and past context across conversations;
- it helps users revisit, compare, and eventually refresh prior ideas;
- memory is off by default and earns a specific opt-in at a high-signal moment
  that names the exact future benefit (memo §15.3 — no first-session opt-in
  modal, no nagging).

First user-facing milestone (memo §15.3 locks this scope): decision-grounded
memory —

> "Remember saved decisions like this so I can help you revisit and compare
> ideas later."

Broader program, in trust order: explicit saved decisions → stable
personalization/workflow preferences → user-requested revisit intentions →
past-session anchors → semantic retrieval → freshness.

### Canonical memory categories (memo §15.3)

The allowlist is closed until the founder extends it:

1. `personalization_preference` — language, asset classes, default benchmark,
   risk explanation style;
2. `workflow_preference` — e.g. buy-and-hold baseline first, assumptions before
   execution, concise result reads;
3. `explicit_decision_note` — user tells Argus to remember a decision or
   preference;
4. `automation_intent` — reminders/revisit requests the user explicitly asks
   Argus to track;
5. `past_session_anchor` — references to prior saved ideas, evidence artifacts,
   and decision states.

## 3. Architecture Contract

```text
Supabase / Argus product records
  -> canonical MemoryCandidate, MemoryRecord, Ideas, IdeaVersions,
     EvidenceArtifacts, DecisionNotes; consent, provenance, ownership, RLS

Mem0 (or another provider) behind an Argus-owned adapter
  -> extraction, organization, tagging, ranked semantic retrieval

LangGraph
  -> receives a small bounded confirmed-memory context
  -> remains the only chat brain
```

Non-negotiable invariants, restated from canon:

- Supabase/Argus owns canonical memory truth. Mem0 is an accelerator and must
  never be the only place a decision or memory exists (memo §5.6).
- LangGraph stays the single conversational runtime. Memory adds no routing
  heuristics, no second orchestrator, no regex/phrase gates.
- Memory failure is fail-open: provider or memory-store trouble never blocks
  ordinary chat.
- No pgvector/embeddings/semantic retrieval inside the launch chat/backtest
  loop until the roadmap explicitly starts that slice (ARCHITECTURE "Deferred
  Direction"; interim Global Stop Conditions).
- Frontend renders backend-provided memory state; it never invents it.
- Explicit confirmation precedes durable storage. There is no automatic
  "remember everything" mode.

### Trust controls required before any user activation

Memories must be: inspectable; editable; deletable and resettable; disableable;
explainable ("why was this used?"); category-allowlisted and
sensitivity-policied; suppressed in sensitive broker/financial contexts;
explicitly confirmed before durable storage. Temporary/private chats (no-memory
mode) ship with or before broad memory activation (memo §15.3).

### Never stored automatically

Broker credentials, account balances, exact holdings, tax or legal status,
personally identifying financial details, health/employment/family details, raw
conversation history as a memory.

## 4. Relationship To The Interim Roadmap And P2

### Interim (issues #228–#253)

This program builds in an isolated lane while the interim runs. Shared-surface
integration follows the interim's Shared-Surface Serialization Matrix; the
memory lane is always the junior owner and integrates last. Concretely:

| Shared surface | Interim owner order | Memory lane behavior |
| --- | --- | --- |
| Interpreter/runtime spine | #238 → #239 → #241 → #249 runtime | wait for release; inject only inside #239's turn budget |
| `agent.py` request boundary | #235 → #240 | wait |
| Supabase gateway/migrations | #230 → #232 → #240 → proven #246 repair | author SQL early; apply only in a post-chain window |
| Profile menu | #247 → #248 | memory Data Controls mounts third |
| Omnisearch/search | #232 → #253 | extend #253's projection; no parallel recall system |
| Result-card actions | #249 | add memory affordances only after #249 lands |
| Public API/OpenAPI | #229 → #234 | endpoints go through the contract gate |

### P2 inheritance contract (A1b/A2/A4)

The paused P2 arc owns linked versions, comparison, and freshness:

- **A1b** owns linked `IdeaVersion` creation on refine.
- **A2** owns comparison readouts.
- **A4** owns freshness on return (`context/freshness.py` exists for context
  packets; A4 extends the concept to saved ideas).
- **A3** (Idea Ledger in Omnisearch) is DONE and is reused, not duplicated.

The memory program **wraps and extends** these capabilities. It must not create
parallel linked-version, comparison, freshness, or recall systems. Where a
memory slice appears to need one of them, the slice is blocked on the P2 arc,
not reimplemented. "Revisit / compare / refresh" in the program's product
language resolves to A1b/A2/A4 plus decision-grounded memory context — never to
new machinery.

## 5. Program Slices

Legend for `Status`: `implemented-skeleton` (built tonight, local-only),
`local-only` (buildable now in isolation), `ready-deterministic` (spec-complete,
deterministic implementation can start), `blocked-interim(...)` (waits on named
interim ownership), `founder-approval` (needs an explicit decision),
`live-eval` (needs a live-provider evaluation gate).

Every slice inherits the architecture contract, the trust controls, the
interim serialization table, and the P2 inheritance contract above. Rollback
boundary for every slice: the slice's commits revert cleanly without touching
durable user data; slices that create durable data must ship their down
migration in the same review.

### S1. Canonical memory contract and consent state

- **User outcome:** none directly; every later trust control depends on these
  types meaning one thing.
- **Product meaning:** `MemoryCandidate` (proposed, not durable) vs
  `MemoryRecord` (user-confirmed canonical memory) with consent state/version,
  provenance, category, sensitivity — the vocabulary of the whole program.
- **Allowed surfaces:** `src/argus/memory/` (new), `tests/memory/`.
- **Forbidden:** everything in the no-touch list; no imports from `argus.api`.
- **Dependencies:** none.
- **Owner/handoff:** memory lane only.
- **Data/privacy boundary:** synthetic data only; no persistence.
- **Deterministic tests:** contract validation, allowlist closure, consent
  transitions.
- **Live evidence:** none.
- **Flag:** `ARGUS_MEMORY_ENABLED` (backend, default off) — read by the service
  factory; no runtime consumer yet.
- **Stop conditions:** speculative fields creeping in "for completeness."
- **Status:** `implemented-skeleton`.

### S2. Memory policy and suppression engine

- **User outcome:** users are never nagged, never silently profiled, and
  sensitive content is never proposed as memory.
- **Product meaning:** one policy authority for category allowlist, sensitivity
  suppression, per-user enablement (default off), and proposal cooldown.
- **Allowed/forbidden/owner:** as S1.
- **Dependencies:** S1.
- **Data/privacy boundary:** policy operates on typed candidate flags;
  extraction-side flagging quality is S8's evaluation subject.
- **Deterministic tests:** allowlisted category passes; non-allowlisted denied;
  any sensitivity flag suppresses; disabled user proposes/retrieves nothing;
  cooldown suppresses repeat prompts with an injected clock.
- **Live evidence:** none.
- **Flag:** same as S1.
- **Stop conditions:** policy decisions drifting into text heuristics that
  belong to LLM extraction.
- **Status:** `implemented-skeleton`.

### S3. Local lifecycle and provider interface

- **User outcome:** none directly; proves the lifecycle end to end so later
  slices wire surfaces, not invent behavior.
- **Product meaning:** propose → policy → confirm → canonical record →
  bounded retrieval with provenance → edit/delete → disable/reset, with an
  Argus-owned provider protocol (Mem0-shaped) and a deterministic fake.
  Provider projection is derivative; deleting canonical deletes projection
  (fail-open if the provider is down, with reconciliation owned by S7).
- **Allowed/forbidden/owner:** as S1.
- **Dependencies:** S1, S2.
- **Data/privacy boundary:** in-memory store, synthetic fixtures shaped like
  `DecisionNote`/`EvidenceArtifact` references (ids only).
- **Deterministic tests:** the walking-skeleton suite (see §7).
- **Live evidence:** none.
- **Flag:** same as S1.
- **Stop conditions:** the fake provider growing Mem0-specific behavior that
  belongs behind the real adapter.
- **Status:** `implemented-skeleton`.

### S4. Supabase persistence and owner-scoped RLS

- **User outcome:** confirmed memories survive reload and device changes;
  deletion/reset is real.
- **Product meaning:** `memory_candidates` (short-lived proposals, prunable) and
  `memory_records` tables mirroring the P1 spine pattern
  (`20260619000001_p1_evidence_decision_spine.sql`): owner `user_id`, RLS
  `auth.uid() = user_id` for select/insert/update/delete, service-role writes
  server-side. Both tables join the delete-all user-data set in the gateway.
- **Allowed surfaces:** `supabase/migrations/` (authoring), gateway methods, in
  a serialized window.
- **Forbidden:** applying migrations while #230/#232/#240/#246 hold ownership;
  any client-visible RPC.
- **Dependencies:** S1–S3; interim migration chain release.
- **Owner/handoff:** memory lane authors; integrates after the interim chain;
  founder approves the migration window.
- **Data/privacy boundary:** real user data appears here for the first time;
  consent state and provenance are non-nullable; no memory content in logs.
- **Deterministic tests:** gateway-level CRUD with the established Supabase
  test doubles; RLS assertions in the migration test pattern used by the spine.
- **Live evidence:** migration + RLS proof on a staging Supabase branch (see
  live-gate L2).
- **Rollback:** down migration in the same PR; tables are additive.
- **Flag:** storage lands dark behind `ARGUS_MEMORY_ENABLED=false`.
- **Stop conditions:** any second write path outside the gateway.
- **Status:** `ready-deterministic` to author; `blocked-interim(#230→#232→#240→#246)` +
  `founder-approval` to apply.

### S5. Data Controls: inspect/edit/delete/reset/disable UI

- **User outcome:** users see and control everything Argus remembers —
  Personalization/Memory under Data Controls, per memo §15.3's menu shape.
- **Product meaning:** the trust surface: list memories with label, category,
  provenance, "why was this stored"; edit; delete; reset all; disable; entry
  point for "why was this used?" explanations.
- **Allowed surfaces:** new components under `web/components/settings/`;
  fixture-driven stories/tests now; `ProfileMenu.tsx` mount only in the
  serialized window (menu already has the Data Controls submenu and disabled
  placeholder pattern).
- **Forbidden:** mounting while #247/#248 own the menu; inventing state the
  backend does not provide.
- **Dependencies:** S1 contracts (fixtures now); S4 + API slice for real data.
- **Owner/handoff:** build on fixtures now; mount third after #247 → #248;
  coordinate §15.3's label evolution (Data & Information → Data Controls,
  Settings → Preferences) with whoever owns that rename.
- **Data/privacy boundary:** renders backend truth only; no memory content in
  client logs/analytics.
- **Deterministic tests:** component tests over fixtures for every control and
  empty/disabled states, EN + es-419.
- **Live evidence:** browser behavior gate L6.
- **Flag:** `NEXT_PUBLIC_MEMORY_ENABLED` default off (`=== "true"` form in
  `web/lib/private-alpha-flags.ts`).
- **Stop conditions:** the popover growing into a settings dashboard (§15.3).
- **Status:** `ready-deterministic` on fixtures; `blocked-interim(#247→#248)`
  for the mount.

### S6. Managed Mem0 versus OSS/self-hosted evaluation

- **User outcome:** none directly; decides where user memory content may live.
- **Product meaning:** the data-processing decision. Memo §5.6 default:
  Supabase/Postgres + Argus-owned compute is the control plane; Mem0
  OSS/self-hosted is the default evaluation target; managed Mem0 SaaS requires
  an explicit founder data-processing decision before any user content flows.
- **Allowed surfaces:** evaluation notes/doc + offline benchmarks in the memory
  lane; no product wiring.
- **Dependencies:** S3's provider interface (the evaluation implements it).
- **Data/privacy boundary:** synthetic corpora only for evaluation; no real
  user data to any external endpoint.
- **Deterministic tests:** adapter-contract conformance suite runs identically
  against fake and candidate implementations.
- **Live evidence:** gate L1 (quality/latency/cost on synthetic corpora; ops
  burden of self-hosting).
- **Flag:** n/a (no product path).
- **Stop conditions:** any evaluation that requires sending real user content
  externally.
- **Status:** `founder-approval` + `live-eval`.

### S7. Mem0 adapter: projection, reconciliation, deletion propagation

- **User outcome:** deletion means deletion — everywhere; retrieval quality
  improves without new truth sources.
- **Product meaning:** the real adapter behind S3's protocol: project confirmed
  records, reconcile drift (canonical is authoritative), propagate
  delete/reset, tolerate provider absence indefinitely (no-op fallback).
  Provider ids remain derivative metadata on the canonical record.
- **Allowed surfaces:** `src/argus/memory/` adapter module; config.
- **Dependencies:** S3, S6 decision; S4 for durable reconciliation state.
- **Data/privacy boundary:** only confirmed, non-sensitive, allowlisted memory
  content is projected; candidates are never projected.
- **Deterministic tests:** contract conformance against the fake; drift and
  failure-injection reconciliation tests.
- **Live evidence:** gate L3 (deletion/reset reconciliation proven against a
  real provider instance).
- **Flag:** `ARGUS_MEMORY_PROVIDER` (`none` default | `fake` | `mem0`).
- **Stop conditions:** reconciliation logic that treats provider state as
  authoritative.
- **Status:** `ready-deterministic` against the fake; `live-eval` for real
  provider; `blocked` on S6.

### S8. Offline extraction and retrieval evaluation

- **User outcome:** proposals are worth confirming; retrieval is relevant.
- **Product meaning:** an offline eval harness for (a) extraction: given
  transcript/decision fixtures, does the extractor propose correct, correctly
  categorized, correctly flagged candidates? (b) retrieval: given a memory set
  and queries, is the bounded context relevant? Mocked-first per
  `tests/evals` doctrine; EN + es-419 fixtures from the start.
- **Allowed surfaces:** `tests/evals/` conventions (read its README first) or a
  memory-lane eval module; fixtures.
- **Dependencies:** S1–S3.
- **Data/privacy boundary:** synthetic fixtures only; live-LLM extraction runs
  only at the documented live gates.
- **Deterministic tests:** the harness itself runs mocked in CI.
- **Live evidence:** scoped live-LLM extraction eval before S11 activation
  (part of gate L7's evidence).
- **Flag:** n/a.
- **Stop conditions:** eval spend outside documented live gates.
- **Status:** `ready-deterministic` (mocked); `live-eval` for LLM extraction
  quality.

### S9. Shadow-mode memory retrieval

- **User outcome:** none visible; proves value and safety before any injection.
- **Product meaning:** for opted-in internal/test users, retrieval runs beside
  the turn and logs what *would* have been offered (ids/categories/scores, not
  content) to the observability envelope. No effect on responses.
- **Allowed surfaces:** a read-only tap after the runtime releases; envelope
  events.
- **Forbidden:** any mutation of turn state; any prompt change.
- **Dependencies:** S3 (+S4 for durable memories); interim spine release for
  the tap point.
- **Owner/handoff:** after #241 closes the spine chain; founder approves
  shadow scope.
- **Data/privacy boundary:** metadata-only logging (`metadata_only` privacy
  mode); no memory content in events.
- **Deterministic tests:** shadow path produces events and provably does not
  alter turn output (byte-equality assertions on responses).
- **Live evidence:** feeds gate L4's go/no-go with real relevance data.
- **Flag:** `ARGUS_MEMORY_SHADOW_ENABLED` default off.
- **Stop conditions:** any measurable turn-behavior difference with shadow on.
- **Status:** `blocked-interim(spine)` + `founder-approval`.

### S10. Bounded LangGraph context injection

- **User outcome:** Argus actually uses confirmed memories in conversation,
  visibly and explainably.
- **Product meaning:** a small typed confirmed-memory packet enters the turn at
  exactly three seams: `runtime.build_workflow_input`,
  `InterpretationRequest`, and `llm_interpreter._messages` (new
  `SystemMessage`), reusing the context-packet shape (immutable, budgeted,
  `not_for: simulation_truth`). Bounded K, provenance ids attached, fetched
  inside #239's turn budget, fail-open on any failure. Responses that use a
  memory can explain why (S12/S5 link).
- **Allowed surfaces:** the three seams + a new pre-interpret assembly module
  mirroring `api/chat/context_packets.py`.
- **Forbidden:** new routing heuristics; retrieval influencing route selection;
  a second orchestrator; unbudgeted latency.
- **Dependencies:** S3/S4/S9 evidence; interim spine + `agent.py` release;
  #239's budget exists.
- **Owner/handoff:** single-owner change after #241/#249-runtime close; founder
  approves activation cohort.
- **Data/privacy boundary:** only confirmed, enabled, allowlisted memories;
  suppressed in sensitive contexts per policy.
- **Deterministic tests:** flag-off byte-identity on the turn (cross-commit
  full-precision proof, per the established flag-off discipline); packet
  bounding; fail-open on store/provider failure.
- **Live evidence:** gates L4 (injection behavior) and L5 (off-neutrality).
- **Flag:** `ARGUS_MEMORY_CONTEXT_ENABLED` default off; independent from
  storage flags.
- **Stop conditions:** interpreter-facing change without the live gate
  (standing release discipline); any routing effect.
- **Status:** `blocked-interim(#238→#239→#241)` + `founder-approval`;
  activation post-PMF per §16.1.

### S11. Explicit saved-decision opt-in (first user-facing milestone)

- **User outcome:** at the moment a user saves a decision, Argus offers —
  once, plainly — "Remember saved decisions like this so I can help you
  revisit and compare ideas later." Accepting creates the scoped opt-in;
  declining is remembered and cooldown-controlled.
- **Product meaning:** the earned, high-signal opt-in moment memo §15.3
  requires; scope limited to `explicit_decision_note` + `past_session_anchor`
  categories grounded in the existing decision spine.
- **Allowed surfaces:** decision-capture flow adjacent to the result card
  (after #249 lands), one API slice for opt-in state, S5's surface for
  management.
- **Forbidden:** first-session modals; broad "turn on memories" prompts;
  result-card duplicate actions (#249 boundary).
- **Dependencies:** S1–S5; #249 released; S8 extraction evidence for the
  candidate quality bar; A3 ledger reused for "revisit."
- **Owner/handoff:** after interim closes #249/#253; founder approves copy and
  moment.
- **Data/privacy boundary:** opt-in is category-scoped consent v1, recorded on
  the record; no other categories activate.
- **Deterministic tests:** opt-in/decline/cooldown flows; consent scoping;
  EN/es-419 copy.
- **Live evidence:** gates L6/L7 + Spanish/English gate L8.
- **Flag:** the user-facing activation flag for the milestone.
- **Stop conditions:** opt-in prompting more than the cooldown allows.
- **Status:** `blocked-interim(#249,#253)` + `founder-approval`; post-PMF.

### S12. Assisted stable-preference proposals

- **User outcome:** Argus notices stable preferences ("you prefer concise
  reads") and asks before remembering them; every use is explainable.
- **Product meaning:** extends proposals beyond decisions to
  `personalization_preference`/`workflow_preference`, still
  confirmation-gated, cooldown-controlled, sensitivity-suppressed.
- **Dependencies:** S11 proving the opt-in pattern; S8 extraction quality;
  founder approval of the category expansion.
- **Surfaces/boundaries/tests:** as S11, plus "why was this used?" links into
  S5.
- **Live evidence:** L7/L8.
- **Status:** `founder-approval`; post-PMF.

### S13. Omnisearch and artifact recall integration

- **User outcome:** confirmed memories and revisit intents surface where users
  already search and browse ideas.
- **Product meaning:** extend #253's decision-first projection and A3's ledger
  with memory-aware entries. No new digest model, no parallel recall system —
  the #253 boundary holds unless separately approved.
- **Allowed surfaces:** `search_assembly.py` projection + palette components,
  after #232/#253 land.
- **Dependencies:** S4; interim #232→#253 closed.
- **Deterministic tests:** projection tests over fixtures; bounded-read
  semantics preserved.
- **Live evidence:** part of L6/L9 browser proofs.
- **Flag:** rides `NEXT_PUBLIC_MEMORY_ENABLED`.
- **Status:** `blocked-interim(#232→#253)`.

### S14. A1b/A2/A4 revisit, comparison, and freshness inheritance

- **User outcome:** "revisit this idea," "compare with my last version," and
  "what changed since I saved this?" work with memory context attached.
- **Product meaning:** the memory program consumes A1b's linked versions, A2's
  comparison readouts, and A4's freshness arc. Memory adds: the user's stated
  revisit intent, the confirmed decision context, and "you saved this because…"
  provenance. It implements none of the underlying version/comparison/freshness
  machinery.
- **Dependencies:** P2 arc resumed and landed (founder sequencing decision
  outside this program).
- **Stop conditions:** any code in this program that creates versions, computes
  comparisons, or fetches freshness context itself.
- **Status:** `blocked` on P2 resumption; inheritance-only by contract.

### S15. Analytics, cost, latency, and privacy evidence

- **User outcome:** trust is provable; the program's cost is known before
  activation.
- **Product meaning:** the observability envelope already reserves the
  vocabulary (`decision_saved`, `revisit_opened`, `compare_started`,
  `memory_candidate_proposed/suppressed`; feature areas `recall`,
  `decision_capture`, `memory_candidate_proposal`). This slice emits those
  events from the memory lifecycle (metadata only), adds cost-ledger entries
  for provider/LLM spend, and defines the latency budget evidence for S10.
- **Dependencies:** S3 (emission points); S4 (durable evidence).
- **Deterministic tests:** event emission with `metadata_only` privacy
  assertions (no memory content in any event).
- **Live evidence:** cost/latency numbers gathered at L4/L7.
- **Status:** `local-only` emission now; `live-eval` for cost/latency numbers.

### S16. Exact-SHA browser and release verification

- **User outcome:** activation ships with the same discipline as everything
  else in private alpha.
- **Product meaning:** extend the #233-style rendered canary and the release
  integrity contract with memory journeys: opt-in at a decision moment, recall
  in a later conversation, inspect/edit/delete in Data Controls, disable, and
  off-neutrality — EN and es-419, one exact deployed candidate SHA.
- **Dependencies:** everything user-facing above; release references
  (`private-alpha-ci-cd-sota.md`, launch runbook, manifest template).
- **Live evidence:** gate L9; blocks tester exposure of memory.
- **Status:** `blocked` until an activation candidate exists.

### S17. Temporal/graph memory (contingent)

- **Product meaning:** graph/temporal memory (Graphiti/Zep-class) only if
  relational + semantic retrieval prove insufficient for a named user problem.
  Explicit v1 non-goal; revisit with evidence, not enthusiasm.
- **Status:** `deferred`; `founder-approval` to even evaluate.

## 6. Live-Test Matrix

No live gate runs during the overnight lane. Each gate must be planned before
its slice is implementation-ready. Common columns: privacy = synthetic or
consenting-internal users only, `metadata_only` telemetry, no memory content in
logs; failure = stop, record, re-scope (never weaken the requirement).

| # | Gate | Why live | Environment / dependency | Data | Visible behavior checked | Hidden evidence checked | Cost/latency expectation | Exact-SHA | Blocks |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| L1 | Managed vs self-hosted Mem0 | retrieval quality/latency/ops can't be judged from docs | isolated eval env; Mem0 OSS self-hosted (+ managed only if founder approves data-processing) | synthetic corpora | n/a | relevance metrics, latency distribution, ops burden notes | bounded eval budget; report actuals | no | S6 decision |
| L2 | Supabase migration + RLS proof | RLS and delete-all behavior must be proven on real Postgres | Supabase staging branch | synthetic users | n/a | cross-user isolation, delete-all includes memory tables, down-migration works | trivial | no | S4 merge |
| L3 | Mem0 deletion/reset reconciliation | deletion propagation across systems can't be faked | staging + provider instance | synthetic | n/a | canonical delete ⇒ provider delete; provider-down delete ⇒ reconciled later | trivial | no | S7 merge |
| L4 | LangGraph context injection | interpreter-facing change ⇒ standing live gate | QA-mode full stack | synthetic + internal users | memory-informed responses stay in voice contract; no routing drift | route receipts, packet ids, latency inside #239 budget | one bounded live session set | yes | S10 merge |
| L5 | Memory-off neutrality | byte/behavior identity needs the real path | QA-mode full stack | synthetic | identical turn output flag-off | cross-commit full-precision diff (established flag-off proof pattern) | trivial | yes | S10 merge |
| L6 | Data Controls browser behavior | trust surface must be seen working | QA mode, real auth, Playwright + manual | synthetic users | inspect/edit/delete/reset/disable all function; disabled states honest | API/Supabase postconditions after each control | trivial | yes | S5/S11 activation |
| L7 | Reload + cross-conversation recall | the core promise spans sessions | QA-mode full stack | internal consenting users | confirmed memory recalled in a new conversation with "why" | persistence, provenance ids, cost ledger | small bounded token spend | yes | S11 activation |
| L8 | Spanish + English memory behavior | es-419 is first-class | QA-mode full stack | synthetic | opt-in copy, labels, explanations in both locales | locale fields on records/events | small | yes | S11 activation |
| L9 | Exact-SHA release/browser canary | activation is a release event | deployed candidate (Render), #233 pattern | privacy-safe captured identities | full memory journey inside the Golden Path | manifest + postcondition checks | one charged journey | yes | tester exposure |

## 7. Walking Skeleton (implemented tonight)

Local, deterministic, default-off, no UI, no runtime wiring, no network, no
migrations. New files only.

- `src/argus/memory/contracts.py` — categories (the five §15.3 categories),
  sensitivity flags, consent state/version, source refs, `MemoryCandidate`,
  `MemoryRecord`, retrieval result with `why_selected` + provenance.
- `src/argus/memory/policy.py` — allowlist, sensitivity suppression, per-user
  enablement (default off), proposal cooldown (injected clock).
- `src/argus/memory/store.py` — owner-scoped in-memory canonical store
  (protocol + implementation); cross-user access is structurally impossible
  through the API.
- `src/argus/memory/provider.py` — Argus-owned retrieval-provider protocol
  (Mem0-shaped: project/search/delete/reset), deterministic fake, no-op
  fallback; provider ids are derivative metadata.
- `src/argus/memory/service.py` — the lifecycle: propose (explicit request or
  saved-decision fixture) → policy → confirm/decline → record → bounded
  retrieve with why/provenance → explain → edit → delete → disable → reset;
  fail-open on provider errors; global flag + per-user opt-in both default
  off.
- `tests/memory/` — focused suites per module plus one end-to-end
  walking-skeleton test.

What it proves: memory off by default; confirmation precedes durability;
allowlist closed; sensitive categories suppressed; cooldown works; disabled
memory neither proposes nor retrieves; owner scoping; deletion/reset removes
canonical and propagates; provider failure never blocks the lifecycle;
retrieval is bounded and explains itself.

What it intentionally does not do: persist, render, inject, extract from real
conversations, or talk to any real provider.

## 8. Founder Decisions Needed

1. Adopt this program structure and slice order (or amend).
2. S6: data-processing posture — confirm self-hosted-default; whether managed
   Mem0 may ever hold user memory content.
3. S11: the opt-in moment's exact copy and placement (after #249).
4. Category expansion beyond the decision-grounded scope (S12).
5. When to schedule S4's migration window relative to the interim chain.
6. Sensitive-context suppression signal: broker context is out of Alpha scope,
   so define the content-derived signal (category + sensitivity flags) as the
   suppression basis — confirm this is sufficient for "suppressed during
   sensitive broker/financial contexts."
7. Whether shadow mode (S9) runs for internal users pre-PMF.
8. Reconcile activation timing with §16.1's post-PMF boundary when the PMF
   gate becomes measurable again (§16.4 compute blocker).

## 9. Integration Gates Checklist

1. Flag-off neutrality proven (cross-commit full-precision diff) before any
   flag flips.
2. No two-owner edits on spine/gateway/menu/search surfaces — the memory lane
   integrates last, per the serialization table.
3. RLS parity with the P1 spine + membership in delete-all before any durable
   write.
4. Recall reuse: no new digest/projection systems without separate approval.
5. External-processor boundary: no user memory content leaves Argus-owned
   infrastructure without the S6 founder decision.
6. Consent-before-durable: no `MemoryRecord` without explicit confirmation —
   enforced in code, tested, and re-verified at every live gate.
7. Contract-first: every endpoint lands through #229 decisions and the #234
   OpenAPI gate.
