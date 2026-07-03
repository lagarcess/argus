# Private Alpha Next Roadmap

Status: P2.0 + P2.1 DONE (spine gate, capability registry, conversational edit
contract). Idea Ledger lightweight recall (#132) and spine modularization (#133)
merged into `codex/private-alpha-next`; recent follow-ups include modularity
budget guardrails (#136), the clean-checkout suite gate repair (#135), alpha
legal/Data Controls surfaces (#137), and date-window helper cleanup (#138).
Remaining P2 is reframed end-to-end around decision-memo execution gates, with
the compounding loop as the highest-leverage PMF gate. Fees/slippage realism is
an async isolated workstream (issue #130).
Current pointer: #141 refine routing is MERGED (PR #148 at `5fc7a9a`).
Promotion to `main` is PAUSED pending #140 (not started) and #142 (PR #146 in
review; must rebase onto `5fc7a9a` and rerun the interpret suite before merge).
Execution runs off the P2 execution board below: point an agent at any READY
lane. The interpret/edit spine has exactly one owner lane at a time (currently
unowned; A1b is next in the spine chain).
Date: 2026-07-01
Branch family: `codex/private-alpha-next`
Audience: Founder, Codex orchestrator, bounded subagents, reviewers

This is the current execution board for Private Alpha Next after the clean P0
continuity reintegration and P1 idea/evidence checkpoint. It turns the decision
memo into ordered, testable slices without importing contaminated runtime work
from quarantine.

## Source Order

Every agent starts here:

1. `AGENTS.md`
2. `docs/PRODUCT.md`
3. `docs/ARCHITECTURE.md`
4. `docs/API_CONTRACT.md`
5. `docs/DATA_MODEL.md`
6. `.agent/designs/argus/DESIGN.md`
7. This roadmap
8. `docs/specs/private-alpha-next-decision-memo.md`
9. `docs/specs/private-alpha-ci-cd-sota.md`
10. `docs/PRIVATE_LAUNCH_RUNBOOK.md`
11. `docs/release-manifests/TEMPLATE.md`
12. Supporting archived notes such as
    `docs/archive/private-alpha-performance-readiness-audit.md`, plus local
    memos such as `temp/bytebytego/bytebytego.md`

The decision memo is mandatory slice onboarding. Before a subagent works on a
slice, it must read the relevant memo sections and addenda for that slice.

## Current Checkpoint

P0 continuity is complete on the clean reintegration line at `bbd9f10`.

Done behavior:

- `add` / `append` merge new symbols into the active strategy.
- `replace` swaps the traded asset universe.
- explicit benchmark changes update `comparison_baseline`, not traded assets.
- default benchmarks remain `SPY` for equities and `BTC` for crypto.
- explicit same-asset-class benchmarks remain sticky until changed.
- dates, capital, asset class, fees/slippage, and benchmark intent survive
  multi-turn edits, reload, and run handoff.
- max 5 symbols is enforced with clarification rather than silent truncation.

Do not reopen P0 unless a new reproducible bug appears. The quarantine work is
preserved as local tags `archive/quarantine-fc231e8` and
`archive/p2.1-quarantine` (branches deleted 2026-07-01, all salvageable content
verified landed or on the execution board) — read-only reference material for
ideas, tests, and failure evidence. Do not broad cherry-pick runtime code from
quarantine.

## What P1 Means

P1 is the first clean decision-memo product slice after P0 continuity.

Goal: completed backtests should become durable, evidence-ready idea artifacts
without pretending that every captured artifact is an explicit user commitment.

The P1 spine is:

- `Idea`: persistent user thesis or question.
- `IdeaVersion`: canonical snapshot of that idea at a point in time.
- `Strategy`: executable method inside an idea version.
- internal `Run` / user-facing `Backtest`: execution record.
- `EvidenceArtifact`: human-readable proof object from run or research context.
- `DecisionNote`: explicit user judgment after seeing evidence.

Default product rule: persistence is automatic, commitment is explicit. A
completed result can be captured as evidence, but only a save, pin, or decision
action should mark the idea as saved or decided.

## P1 Scope

In scope for the next implementation wave:

- product/API/data spec for Idea, IdeaVersion, Strategy, Run/Backtest,
  EvidenceArtifact, DecisionNote, and lifecycle labels;
- artifact payload boundaries, provenance, assumptions, digest, and immutable
  evidence fields;
- completed backtest capture into the idea/evidence model;
- decision capture attached to evidence artifacts;
- Omnisearch-ledger recall as the first user-facing wedge, not a dashboard;
- typed search results and right-panel previews for Conversation, Backtest,
  Evidence, Decision, and Idea;
- measurement-only event envelope for continuity, evidence capture, decision
  capture, recall, and eval readiness.

Out of scope until explicitly started:

- generic RAG/vector memory as canonical truth;
- automatic personalization memory beyond explicit or assisted saved-decision
  moments;
- standalone Idea Ledger dashboard;
- broker account connection, broker execution, or order submission;
- public sharing/excerpts beyond design constraints;
- provider-backed voice implementation;
- native mobile.

## P1 Readiness Checklist

Before code:

- [x] Update spec/API/data-model docs for the exact P1 object contract.
- [x] Identify migrations, if any, and make them reversible and minimal.
- [x] Write failing backend tests for evidence capture, decision capture,
      hydration, reload, and search retrieval.
- [x] Write or update focused frontend tests for visible artifact states.
- [x] Define browser QA prompts before implementation, including messy language,
      reload, locale switch, and navigation during async changes.
- [x] Confirm rollback can be described as one clean commit revert per slice.

Before promotion to `codex/private-alpha-next`:

- [x] Focused backend tests pass for the final candidate SHA.
- [x] Focused frontend tests pass for the final candidate SHA.
- [x] Live Codex browser QA passes locally for the final candidate SHA.
- [x] Internal code review has no release-blocking findings.
- [x] Docs reflect the shipped behavior, not aspirational behavior.
- [x] No broad quarantine runtime diff was imported.

Verification note: these boxes must be checked only against the exact
`codex/private-alpha-next-reintegration` candidate SHA being considered for
promotion. Promotion to `codex/private-alpha-next` remains a separate
founder-directed action.

Current verification evidence for this recovery candidate:

- Backend P1/API: `poetry run pytest tests/test_alpha_api.py
  tests/test_alpha_api_supabase.py tests/test_supabase_gateway.py
  tests/test_alpha_artifacts.py tests/test_p1_evidence_spine.py -q` passed
  with 146 tests.
- Backend P0/date continuity: `poetry run pytest
  tests/agent_runtime/test_artifact_continuity.py
  tests/agent_runtime/test_llm_interpreter_date_window_repairs.py
  tests/agent_runtime/test_interpret_stage.py
  tests/agent_runtime/test_workflow.py -q` passed with 239 tests.
- Frontend: `cd web && bun test __tests__/alpha-frontend.test.ts
  __tests__/command-palette-items.test.ts __tests__/spanish-ui-smoke.test.ts`
  passed with 82 tests.
- Static checks: focused `poetry run ruff check ...` passed for touched backend
  files and focused tests; `git diff --check` passed.
- Codex in-app browser QA: `http://127.0.0.1:3031/chat` completed reload of a
  messy Spanish AAPL/MSFT/TSLA vs SPY result, verified one completed result
  card, no ready/failed duplicate card, saved decision hydration, Spanish
  period and benchmark prose, no raw internal search leaks, and Omnisearch rows
  ordered as Decision, Evidence, Idea, Backtest before Conversation for the
  `AAPL MSFT TSLA` ledger query.
- Internal review: two read-only reviewers found the same Omnisearch ranking
  blocker. The fix preserves pinned, exact, and symbol relevance ahead of P1
  artifact priority while keeping artifacts ahead of source conversation
  wrappers within the same relevance tier.

Stop immediately if:

- canonical payload and UI prose disagree;
- benchmark/traded assets regress from the P0 continuity contract;
- frontend invents state not supplied by backend artifacts;
- schema/API changes appear without matching docs and tests;
- slice size grows beyond one revertable commit;
- live browser QA fails after tests pass.

## Board

### P0 Done

- P0 continuity contract and canonical asset/benchmark edit semantics.
- Clean reintegration strategy from `codex/private-alpha-next` at the stable
  checkpoint.
- Quarantine branch preserved as read-only reference.

### P1 Done

P1 is closed, verified (see the readiness checklist and verification evidence
above), and promoted to `main` as part of the squash promotion `8b169e9`
("promote private alpha next checkpoint", validated against `3314e2c`). The
slices below describe delivered scope, not pending work.

1. **Object contract spec**
   - Define Idea, IdeaVersion, Strategy, Run/Backtest, EvidenceArtifact,
     DecisionNote, and lifecycle labels.
   - Update API/DATA_MODEL docs before implementation.

2. **Evidence capture**
   - Capture completed backtests into durable evidence artifacts.
   - Keep evidence automatic and commitment explicit.
   - Preserve immutable assumptions, metrics, provenance, and digest.

3. **Decision capture**
   - Add explicit user decision states such as watching, promising, rejected,
     and revisit later.
   - Attach notes to evidence artifacts.
   - Hydrate saved decisions back into result/artifact surfaces.

4. **Omnisearch-ledger wedge**
   - Promote recall through Omnisearch/search first.
   - Preview artifacts directly, with conversation as provenance.
   - Add artifact-aware hover/right-panel actions without duplicate action
     surfaces.

5. **Measurement envelope**
   - Define event schema for evidence capture, decision capture, recall,
     continuity mismatches, cost, and eval readiness.
   - Keep analytics measurement-only unless a later slice starts live reporting.
   - Current P1 implements the non-emitting `argus_observability_event/v1`
     envelope and privacy sanitizer; PostHog wiring, durable cost-ledger tables,
     and eval-result persistence remain deferred.

### Design-Only Until Later

- Memory/data controls.
- Voice-to-composer STT.
- Public evidence excerpts.
- Broker/export handoff.
- Native mobile.
- Research Lab / Perplexity-style deep research.

### P2 Board

P2 thesis: P1 proved Argus can capture evidence. P2 makes that evidence
trustworthy and comparable enough that the three founder-guided alpha users save
decisions and come back. P2 is measured against the PMF gates in
`docs/specs/private-alpha-next-decision-memo.md` section 15.8, not by feature
count.

In scope for P2: capability honesty, backtest credibility (assumptions a user
can explain), the comparison loop, graceful Spanish recovery, and the
measurement to know whether any of it moved a gate.

Deferred to design-only for P2 (no runtime, schema, or UI): memory
inspector/opt-in (memo 15.3, Slice H), voice-to-composer STT (Slice J), public
excerpts (Slice K), broker/export handoff (Slice N), iOS shell (Slice L), and
external engines beyond read-only reference (Slice M). Producing design notes for
these is allowed; shipping them is not P2 scope.

#### Why P2 is sliced this way: the quarantine lesson

Two branches attempted P2 work and both broke the language-agnostic, LLM-first
spine in the same way:

- `codex/private-alpha-next-quarantine-fc231e8` (broad umbrella) added
  deterministic ticker-shape classifiers (`$`-prefix, ALL-CAPS, length-2-to-5
  `.isalpha()`) and re-scanned `current_user_message` inside `interpret.py` to
  override the interpreter's grounding, deleting an interpreter-trusting
  short-circuit in the process.
- `codex/private-alpha-next-p2.1-quarantine` (narrow capability gate) substring-
  matched indicator names against LLM free-text and flipped intent to
  `unsupported` after interpretation, rejected RSI thresholds unless the number
  appeared literally in the raw message, and hand-wrote `if locale == "es-419"`
  copy tables to keep parity.

Single root cause: both implemented capability truth and continuity as
deterministic gates that run after the LLM and override it by re-scanning text.
Narrowing scope did not help; it produced a smaller copy of the same
anti-pattern. The earlier P2.1 board even sanctioned the seam with one sentence
permitting deterministic guardrails to "consult catalog-backed indicator tokens
after LLM interpretation." That sentence was the doorway. Note that neither
branch used `import re` or `if "word" in message`; the spine was broken with
heuristics that pass a naive grep, so the prohibitions below name mechanisms, not
just regex.

This work is preserved as local tags (`archive/quarantine-fc231e8`,
`archive/p2.1-quarantine`; the branches themselves were deleted 2026-07-01) —
read-only reference for product direction, anti-patterns, UI ideas, and test
inspiration. Do not broad cherry-pick runtime code from the tags.

#### Cross-cutting invariants (the P2.0 guardrail gate, inherited by every slice)

Sourced from `AGENTS.md` runtime rules, `ARCHITECTURE.md` agent-runtime decision
filter, and the quarantine autopsy above. Any P2 change that weakens these is a
release blocker.

1. No deterministic text re-scan to drive routing or grounding. Nothing in
   `interpret.py` or after it may re-inspect `current_user_message` to branch.
   Consume interpreter output only.
2. No post-LLM intent override. Code may not flip `intent` or
   `semantic_turn_act` (for example to `unsupported_or_out_of_scope`) from its
   own re-analysis. The `*_text_guardrail_response` shape is banned.
3. Capability and field validation read typed structured fields the LLM emits
   (for example a `strategy_type` enum or an `indicator.key` enum), never
   substring, keyword, or alias-span matching over prose or LLM free-text fields.
4. No "grounding" by literal text presence. Do not reject an LLM-extracted value
   because it is not a substring of the raw message; that punishes paraphrase and
   non-English phrasing.
5. No per-language copy tables or branches in the runtime (`if locale ==
   "es-419"`, `_english_*` helpers, `" y "` versus `" and "` connectors).
   Capability, clarification, and recovery copy is model-voiced; English/Spanish
   parity is proven by eval, not hardcoded. Localized stop-word lists, alias
   tables, or display-label token matching for semantic choice selection are the
   same anti-pattern; degraded fallbacks must consume typed ids / payloads.
6. Backend stays canonical truth; the frontend renders backend-provided state and
   never invents it; one LLM intent-classification call per turn.

These ship as a review checklist plus failing-test tripwires in P2.0 so the
disease cannot recur silently.

#### Milestones

Each slice owns a PMF gate, is demoable in a founder-guided session, and is one
revertable slice family.

##### P2 execution board: decision memo gates + unlock status (AUTHORITATIVE, 2026-07-01)

Evidence-grounded after a live walkthrough + code grounding pass. The decision memo's
moat is the loop where ideas are tested, remembered, compared, and trusted (memo §4.1,
§5.6, §5.7). P2's remaining work is closing that loop. Treat the items below as
execution gates, not as a second roadmap and not as hard order dependencies. The
P2.x specs further below remain the per-slice detail (PMF gates, verification, stop
conditions).

How to use this board: each gate lists lanes with an unlock status. Point an
agent at any READY lane without waiting on the others; the status IS the
authorization. Status legend:

- READY-BUILD: implement now (fresh worktree from `origin/codex/private-alpha-next`,
  child branch, tests, browser QA, review, one revertable slice family).
- READY-SPEC: write the spec and ask the founder product questions now;
  implementation stays locked until the board flips the lane to READY-BUILD.
- SCOUT: diagnosis, reproduction fixtures, and failing tests only. No runtime
  edits.
- ASYNC: isolated lane in its own worktree; cherry-pick discipline, no merge
  pressure, never blocks the board.
- BLOCKED(x): do not start; waiting on the named unlock.
- DESIGN-ONLY: notes/mocks allowed; no runtime, schema, or UI code.

Spine ownership rule: exactly one lane at a time may edit the interpret/edit
spine (`agent_runtime/stages/*`, `agent_runtime/interpreter/*`,
`llm_interpreter*.py`, `artifact_edit_planner.py`). The current owner is lane
A1 (#141). Parallel runtime lanes keep new logic in their own modules, touch
shared dispatch minimally, and take rebase duty; the spine owner merges first.

**Gate A: memory-backed compounding loop (highest leverage).**

End-to-end shape: messy idea -> canonical idea -> backtest/evidence artifact ->
saved decision -> refine creates a linked version -> compare versions -> revisit
later with context. This includes structured Argus product memory earlier in the
plan than generic retrieval work: `Idea`, `IdeaVersion`, `EvidenceArtifact`,
`DecisionNote`, user-confirmed `MemoryRecord`, and retrieval from those product
objects are the contract. RAG, graph RAG, agentic RAG, Mem0, Zep, Graphiti, and
similar tools are optional implementation leverage behind that contract, not the
source of truth.

**Gate B: trust, recovery, and measurement (runs alongside Gate A).**

Wire product events, eval cases, cost/latency ledger, correlation IDs, recovery
tests, Spanish parity, and browser QA evidence as the loop lands. This is not a
separate product surface; it makes founder-guided sessions measurable and keeps
runtime behavior honest. PR #139 (merged `128818f`) was a Gate B/P2.4 repair
slice, not a replacement for the Gate A product swing; issues #140 and #142
continue this gate.

**Gate C: evidence credibility (parallel, isolated).**

Execution realism, fees/slippage, benchmark clarity, data assumptions, and the
`BacktestEngine` boundary improve the trustworthiness of evidence artifacts. This
work is async under issue #130 and must remain flag-safe and surgically replayed
from any stale branch evidence; do not broad-merge an old engine branch.

**Gate D: memory controls and privacy (required for memory expansion).**

Memory must be earned opt-in, inspectable, editable, deletable, resettable, and
explainable ("why was this used?"). Alpha legal/Data Controls work (#137) is the
surface to extend. Do not add automatic broad personalization memory before these
controls exist.

**Parallel design/prototype lanes.**

These may progress without touching the runtime spine: sanitized public excerpt
design/mock, voice-to-composer STT prototype, thin iOS shell proof, broker/export
packet design, security/privacy review, and monetization/entitlement architecture.
They become implementation work only when the active gate explicitly starts them.

**Avoid for now.**

Do not add generic RAG as canonical memory, always-on automatic memory, a new
dashboard competing with chat, public raw conversation links, broker sandbox auth
or execution, speech-to-speech, a native iOS release, payments, or a second chat
interpreter/orchestrator.

DONE + landed on `codex/private-alpha-next`:

- P2.0 spine guardrail gate (tripwires live).
- P2.1.a capability registry (single derivation surface).
- Conversational edit contract (messy multi-op edits + chips -> one typed operation
  set, no silent drop, language-aware, model-voiced honesty note; 6 commits; verified
  unit + live probe EN/ES + EN browser). NOTE: the capability-honesty interpreter
  polish (the old "P2.1.b") was reassessed as LOW-VALUE — MACD is reachable via a
  generic `signal_strategy` rule, and draft strategies already 422 — so it is OFF the
  critical path.
- Idea Ledger — lightweight recall (loop Slice 3): saved-idea decision status surfaced
  in Omnisearch + a `?decision_state=` filter (#132, merged).
- Spine modularization: `llm_interpreter.py` + `stages/interpret.py` split into cohesive
  submodule packages behind behavior-preserving re-export facades (#133, merged;
  addresses #131 — issue kept OPEN until it lands on `main`).
- Gate B/P2.4 chat-continuity regression repair (#139, merged `128818f`):
  unsupported-recovery continuation, confirmation-card edits, pending date
  answers, RSI threshold edits, Recents attention, Omnisearch default-on QA;
  degraded fallbacks now consume typed ids/payloads instead of display-label
  text.
- `codex/p2.1a-capability-registry` is SUPERSEDED — its deploy work (onboarding-flag
  gate, grok-4.3/claude-haiku model swap, deploy contract, widened LLM timeouts) is
  already in integration; the branch carries no unique runtime. Retire it, no rescue.

LANES BY GATE (the board agents execute from):

**Gate A — compounding loop (highest leverage):**

- **A1 Refine routing + loop repair (#141).** DONE — merged as PR #148
  (`5fc7a9a`). Refine chip and natural-language edits now route through the
  typed edit contract; refinement pending state is a first-class edit context;
  same-period references bind silently to the latest run's window; the
  supported-edit discriminator counts date-window and cadence evidence.
  Regression suites added: `test_refine_action_edit_routing.py`,
  `test_post_result_edit_routing.py`, `test_latest_result_window_binding.py`.
  Spec: `docs/specs/private-alpha-next-refine-to-version.md`.

- **A1b Linked IdeaVersion emission.** READY-BUILD — next spine-chain slice;
  the spine is unowned until this lane starts. Emit a new `IdeaVersion` linked
  to the prior idea on refine (P1 spine supports lineage). Split out of #141
  by founder scope decision 2026-07-01; this is the slice that UNBLOCKS
  comparison (A2). Prefer starting it after PR #146 lands so only one lane at
  a time sits on the interpret surface.

- **A2 Comparison readout** (= P2.3 detail below). READY-SPEC (spec + founder
  questions now); BUILD is BLOCKED(A1b) — needs clean linked versions to
  compare. Stands on the BUILT P1 spine (each `IdeaVersion`/`EvidenceArtifact`
  carries its metrics; a `compare_started` event is pre-registered in the
  observability envelope). "vs your last version" — return Δ, drawdown Δ, what
  changed; short, model-voiced. The differentiator from one-off output.

- **A3 Idea Ledger portfolio view.** DONE — merged as PR #147 (`e9180c8`).
  Saved ideas browse inside Omnisearch grouped by decision state
  (promising/watching/rejected/revisit) with filter chips; backend-owned
  `ledger_groups` are the source of truth for group order and counts (clients
  must not synthesize groups — recorded in `API_CONTRACT.md`); EN/es-419
  localized; live browser QA passed in both languages.

- **A4 Freshness on return** (memo §5.6 SOTA north — the MOAT-DEFINER, the
  biggest). BLOCKED(research/web lane; A1-A3 landing first); design notes
  allowed. Freshness infra (`context/freshness.py`) exists for context packets,
  not saved ideas. Smallest version: saved ideas show "Last reviewed" + a
  re-run-on-fresh-data delta + "what changed since I saved this?". Phase LAST;
  its own arc.

**Gate B — trust, recovery, measurement:**

- **B1 Latest-result answers from run facts (#140).** READY-BUILD — dispatch
  now; it was founder-serialized behind #141, which is merged. Build on top of
  the landed refine routing. New logic lives in its own
  `stages/interpret_internal/` module (pattern: `requested_asset_answer.py`),
  thin dispatch hook only. Coexistence contract: consume the interpreter's
  typed intent only; if pending edit state is active and a turn classifies as
  a result question, answer it and leave the pending state intact — the #148
  regression suites must stay green. Scope fence: answer from canonical
  `backtest_runs`/result facts (peak date/value, drawdown date) or state the
  limitation via typed payloads; preserve `result_run_id` in response
  metadata. Do NOT rework recovery copy here (that is B4).

- **B2 Asset preservation in messy company-name prompts (#142).** ACTIVE (in
  flight). Scout verdict 2026-07-01: runs FREE of A1 — #142 lives on the
  first-pass `interpret -> asset resolution -> canonicalize -> confirmation`
  path, A1 in post-result refine/typed-edit routing. Likely drop zone:
  `asset_text_grounding.py`, `resolution.py`, `stages/interpret.py`
  (confirmation just renders `asset_universe`; the loss is upstream). Repro
  target: `tests/agent_runtime/test_interpret_stage.py` asserting TGT + WMT +
  COST all survive to confirmation. Discipline: keep the fix in
  grounding/resolution modules and touch `stages/interpret.py` minimally.
  A1 landed first (PR #148, heavy overlap on `stages/interpret.py`,
  `llm_interpreter.py`, `strategy_builder.py`): PR #146 MUST rebase onto
  `5fc7a9a` and rerun the interpret suite plus the new #148 regression suites
  before merge, even if GitHub reports a clean merge. Spine rules apply:
  provider-backed name resolution feeds INTO interpretation as context/tools,
  never a post-LLM text rescan.

- **B3 Measurement wiring** (= P2.5 below). READY-BUILD, off-spine. One lane,
  THREE atomic slices in this ORDER, each its own PR — never combined into one
  push:
  (1) **Eval harness** — MERGED (PR #143 at `e303aa3`, Fable-reviewed).
  `tests/evals/` with typed-outcome fixtures, prose-only judge
  (`argus-prose-quality-v1`), issue-tagged expected-fails (#142), gitignored
  scorecards, live spend behind `ARGUS_RUN_LIVE_EVALS=1`. Run policy: see
  `tests/evals/README.md` + the standing release discipline below. The
  landing gate is LIVE — runtime-behavior PRs run the live suite pre-merge
  from now on.
  (2) **Product events**: wire the BUILT non-emitting
  `argus_observability_event/v1` envelope to PostHog. Founder prerequisite
  before this slice starts: PostHog project + API key provisioned and
  redaction-tier sign-off (memo 15.5 posture).
  (3) **Append-only CostLedger**: the only schema-touching slice — reversible,
  minimal migration with docs updated in the same slice; goes last so it is
  informed by the events slice.
  The order is leverage-driven, not a hard chain: if PostHog provisioning
  stalls slice 2, slice 3 may proceed. Emission hooks + persistence only; no
  interpret logic. Weave in early; do not gate the loop on it.

- **B4 Recovery-copy retirement** (= P2.4 remainder). READY-SPEC; BUILD is
  BLOCKED(B3 eval harness) so English/Spanish parity is proven by eval, not
  hardcoded. Retire per-language recovery copy
  (`api/chat/streaming.py` `assistant_copy_for_result`,
  `recovery_messages.py`) toward model-voiced parity.

**Gate C — evidence credibility:**

- **C1 Execution realism — fees/slippage** (= P2.2 below). ASYNC: GitHub issue
  `lagarcess/argus#130` + worktree `codex/engine-realism`, flag-gated
  `ARGUS_ENABLE_EXECUTION_REALISM` (default off), cherry-pick per phase. Off
  the critical path; the founder deliberately disclaims assumptions for the PMF
  stage.

**Gate D — memory controls and privacy:**

- **D1 Memory controls spec** (inspect/edit/delete/reset/"why was this
  used?"). READY-SPEC (spec + founder questions; extends the #137 Data
  Controls surface). BUILD is BLOCKED(user-confirmed `MemoryRecord` landing in
  the Gate A contract). No automatic broad personalization memory before these
  controls exist.

**Design-only lanes** (all READY for notes/mocks; no runtime, schema, or UI
code): sanitized public excerpt design, voice-to-composer STT prototype, thin
iOS shell proof, broker/export packet design, security/privacy review,
monetization/entitlement architecture.

**Standing release discipline** (blocks `main`, not a lane): rerun the exact
clean-checkout suite gate (issue #134 / PR #135) before any branch or `main`
promotion instead of treating the repair as permanent proof for future SHAs.
Promotion to `main` stays PAUSED pending #140-#142.
Once the eval harness (B3 slice 1, PR #143) merges, it is a landing gate:
runtime-behavior PRs run the live eval suite once pre-merge; every `main`
promotion candidate runs the full live suite on its exact SHA with no
unexpected failures (expected-fails only for open issue-tagged bugs); rerun
the suite after any interpreter model or provider change. Integration stays a
fast checkpoint; `main` is the heavyweight gate.

"P2 done" = Argus **remembers, compares, and stays honest about staleness** — the memo's
moat, PMF-testable by the 3 founder-guided users (memo §15.8 gates).

##### P2.0 Spine guardrail gate (DONE — landed)

- Outcome: the six cross-cutting invariants above become an enforced review
  contract plus automated tripwire tests that fail when a deterministic text
  re-scan, post-LLM intent override, prose substring/alias match, literal-text
  grounding, or per-language copy table is introduced.
- Allowed surfaces: review docs (`CLAUDE.md`/`AGENTS.md` cross-reference),
  `docs/`, and focused guardrail tests under `tests/agent_runtime/`.
- Forbidden surfaces: any product runtime or UI behavior change. This slice only
  adds enforcement, not features.
- Verification: the new tripwire tests fail against a reverted/known-bad patch
  and pass against current `codex/private-alpha-next`.
- Browser QA: none required; not user-facing.
- Rollback: single docs+tests commit revert.
- Stop conditions: if enforcing a rule requires changing runtime behavior, stop
  and split that into its owning milestone.

##### P2.1 Capability truth (DONE — registry + edit contract landed; honesty polish deprioritized)

- Outcome: Argus stops overpromising. It honestly tells the user, in their own
  language, what it can and cannot run yet (for example "I can't run MACD yet,
  but I can test an RSI rule") without raw enums and without per-language copy.
- Mechanism: a canonical, typed Capability Registry with status per
  strategy/indicator (`executable`, `draft_only`, `future`). The registry is
  provided to the LLM interpreter as interpretation context/tools so the model
  itself knows what is supported. Post-LLM validation reads only typed canonical
  fields the LLM emits (`strategy_type` enum, `indicator.key` enum); it never
  scans prose and never flips intent from a text re-analysis.
- Folds in Slice D: inventory every current indicator/strategy code path (what is
  interpreted, validated, executable, rendered, documented), and feed truth into
  the registry. No broad indicator expansion until the audit proves current
  state.
- Surface containment: draft strategies (`momentum_breakout`, `trend_follow`) and
  draft/discovery indicators must have no user path. Today they are already hidden
  (the `@` indicator picker filters to supported only; the two draft strategies
  never appear in the frontend and are blocked at confirm), but containment is by
  convention, not construction. P2.1 makes it structural: derive the API template
  allow-list (`api/schemas.py` `StrategyTemplate`, `backtesting/config.py`
  `ALLOWED_TEMPLATES`), the save-passthrough set (`api/chat/strategies.py`), and
  discovery from the single executable registry; remove the latent frontend
  `draft_only` token plumbing (`web/components/chat/ChatInput.tsx`,
  `web/components/chat/types.ts`); and retire or guard the orphaned `signals.py`
  handlers for the two drafts. Stay narrow: do not widen the supported set in this
  slice. See `docs/specs/private-alpha-next-p2.1-capability-audit.md`.
- Allowed surfaces: capability registry domain module, interpreter
  context/tools wiring, typed post-LLM capability validation, registry-backed
  result/clarification copy that is model-voiced, docs (`API_CONTRACT.md`,
  `DATA_MODEL.md`, `CONVERSATIONAL_RUNTIME.md`), and focused tests.
- Forbidden surfaces: substring/keyword/alias matching over user text or LLM
  free-text; post-LLM intent override; per-language capability copy; reviving the
  quarantined `*_text_guardrail_response` or
  `non_alpha_indicator_text_guardrail_blocked_execution` paths; the legacy
  Strategies sidebar surface.
- Verification: focused backend tests for registry truth and typed-field
  validation; an eval set proving honest capability responses for messy English
  and Spanish prompts (capability honesty, not phrase gates); guardrail tripwires
  from P2.0 stay green.
- Browser QA: founder-guided run of an unsupported-indicator request in English
  and in Spanish; confirm honest model-voiced refusal-plus-alternative, no raw
  enums, no English leak in the Spanish session, supported path still runs.
- Rollback: revert the registry slice; capability behavior returns to current
  baseline with no schema debt.
- Stop conditions: any need to re-scan the user message, override intent
  post-LLM, or add language-specific copy. If the registry cannot express a
  capability truth as typed data, stop and redesign the data, not the gate.
- PMF gate: users describe a decision Argus clarified; trust foundation for all
  later slices.

##### P2.2 Backtest credibility — fees/slippage realism (ASYNC: Codex issue #130, worktree codex/engine-realism)

- Outcome: results carry assumptions a user can explain without founder help.
- Scope: a `BacktestEngine` interface with the current engine as an adapter (no
  VectorBT/engine internals leaking into product objects); audit and surface
  fees, slippage, splits/dividends, missing-data behavior, benchmark
  correctness, and drawdown/risk metrics into the EvidenceArtifact with
  provenance and digest.
- Forbidden surfaces: building a new quant engine; expanding metrics beyond the
  audited, trustworthy set.
- PMF gate: users can explain artifact assumptions without founder help. Full
  verification/QA/rollback spec is authored when this slice activates.

##### P2.3 Comparison loop

- Outcome: a user can compare the current backtest against a prior
  same-asset/same-strategy idea or a previous IdeaVersion and get a short,
  grounded, model-voiced readout.
- Surfaces: entry points from Omnisearch and the result card; readout-first, no
  new heavy comparison dashboard.
- PMF gate: at least two of five users voluntarily revisit or compare. This is
  the retention loop. Full verification/QA/rollback spec authored at activation.

##### P2.4 Failure and recovery trust

- Outcome: when Argus fails or hits an unsupported request, recovery preserves
  the user's idea, clarifies without making the user feel wrong, explains
  unsupported capability in product language, and never leaks raw provider/runtime
  errors or English fallback into a Spanish session.
- Establishes the model-voiced, language-agnostic recovery pattern (the hotspot
  where the quarantines hardcoded per-language copy).
- PMF gate: Spanish-preferring users complete the loop without founder help. Full
  spec authored at activation.

##### P2.5 Measurement and eval harness

- Outcome: the loop is instrumented so founder-guided sessions produce PMF-gate
  signal. Wire the P1 non-emitting `argus_observability_event/v1` envelope to
  PostHog product events and an append-only first-party CostLedger; stand up a
  portable eval harness over the locked categories (messy English/Spanish, UI/user
  language mismatch, capability honesty, recovery, comparison, metric
  correctness).
- Posture: analytics is measurement-only; privacy follows memo 15.5
  (`raw_alpha -> redacted_default -> metadata_only -> disabled`), never sending
  credentials, balances, holdings, audio, or route receipts to analytics.
- Start instrumentation early, in parallel with P2.1-P2.3, so gates are
  measurable as features land.

##### Conversational edit contract (macro pattern) — DONE (landed `0fb32c1`)

Status: BUILT + LANDED on `codex/private-alpha-next` (6 commits). Typed `EditOperation`
(add/remove/replace/set/clear × assets/benchmark/dates/capital/DCA/timeframe/fees/
slippage), deterministic applier (multi-op, no silent drop), language-aware planner,
conflict-aware prompt, model-voiced honesty note. Verified unit + live probe EN/ES + EN
browser. Spec: `docs/specs/private-alpha-next-conversational-edit-contract.md`. The
remaining seam is loop **Slice 1 (refine -> linked version)** above — refine routes to
the wrong brain. Original design notes preserved below for reference.

- Idea: the confirmation-card action chips (Run backtest, Change dates, Change
  asset, Adjust assumptions, Cancel) and natural-language turn edits should be two
  entry points to ONE canonical set of edit operations on the pending artifact. A
  user can say it in their turn ("change the start date to the beginning of this
  year and also add AMZN") and Argus interprets and applies it, or click a chip to
  be direct, or Argus can offer "what would you like to change?". Chips become a
  convenience layer over the contract, not a separate path (consistent with the
  "no duplicate action surfaces" rule and the LLM-first spine).
- Why it matters: a multi-intent natural-language edit currently applies one
  operation (asset add) but can silently drop another (the date change). That
  observed behavior is a symptom of an under-specified multi-operation edit
  contract, not a one-off bug. Designing the contract (what operations exist, how
  multi-op NL edits compose, how chips and NL both map to the same operations) is
  the adequate fix; a point patch risks baking in the wrong model.
- Spine constraint: relative dates ("beginning of this year") must be resolved by
  LLM interpretation and the planner must apply ALL operations in a turn. No
  regex/text-scan for date phrases, no per-language gate (P2.0 guardrails apply).
- Sequencing: candidate near P2.1, since both live on the confirmation/edit
  surface. Spec before implement.

#### P2 stop conditions (whole wave)

Stop immediately and escalate to the founder if:

- a slice requires re-scanning user text, overriding LLM intent post-hoc, or
  per-language runtime copy;
- canonical payload and UI prose disagree;
- the frontend invents state the backend did not supply;
- schema/API changes appear without matching docs and tests;
- a slice grows beyond one revertable commit family;
- live browser QA fails after tests pass, especially Spanish parity.

Until a lane is READY on the execution board, do not implement its runtime,
backend, schema, or UI changes. The board status is the authorization:
READY-BUILD lanes may implement now, READY-SPEC lanes may write specs and ask
the founder questions only, SCOUT lanes may add fixtures/failing tests only,
and BLOCKED/DESIGN-ONLY lanes stay out of runtime. The interpret/edit spine has
one owner lane at a time (currently A1, #141); parallel runtime lanes take
rebase duty.

## Parallelization Rules

Serialized:

- canonical object contract;
- migration/API contract if needed;
- evidence capture;
- reload/hydration path.

Parallelizable around the serialized spine:

- docs/spec updates;
- UX preview/action spec;
- analytics event schema;
- security/privacy review;
- indicator/evidence audit;
- voice, public excerpt, and broker/export design-only specs.

## Archive And Classification Rules

- Canon docs are never archived.
- This roadmap and the decision memo are active for Private Alpha Next.
- CI/CD SOTA, the launch runbook, and the release manifest template remain
  active release-discipline references, not product-roadmap owners.
- Historical superpowers plans and closed milestone specs should receive
  historical banners or move to `docs/archive/` only after confirming no active
  doc points to them as command sources.
- `temp/bytebytego/bytebytego.md` remains a supporting local memo unless the
  founder promotes it into `docs/specs/`.

## Integration Workflow After P0

The P0 reintegration strategy worked directionally:

- stable remote integration checkpoint stayed clean;
- contaminated autonomous work was preserved under quarantine instead of being
  mixed into the gate;
- reintegration restarted from the clean branch;
- P0 landed as a focused, tested, revertable slice.

Future P2 work should keep that discipline:

- work on a focused child branch from `codex/private-alpha-next`;
- promote to `codex/private-alpha-next` only after tests, browser QA, and review;
- keep each slice revertable;
- use bounded scouting, specs, tests, and reviews only when they reduce risk;
- keep architecture, prioritization, and final promotion with the main
  orchestrator and founder.
