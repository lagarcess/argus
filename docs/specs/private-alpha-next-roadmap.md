# Private Alpha Next Roadmap

Status: P2.0 + P2.1 DONE (spine gate, capability registry, conversational edit
contract). The Gate A/B loop landed through 2026-07-07: refine routing
(#141/PR #148), Idea Ledger portfolio browse (#147), latest-result fact answers
(#140/PR #153), messy company-name asset preservation (#142/PR #146), and the
B3 measurement trio (eval harness #143, PostHog product events #144, append-only
cost ledger #145). B4 retired the per-language copy tables — runtime prose and
recovery copy now compose from typed facts/codes (#154, PRs #174-177). Execution
realism (fees/slippage, #130/PR #178) merged flag-off, and a new interpreter
cost/perf lane added prompt caching + per-tier reasoning controls (#156/#157,
PR #172). Remaining P2 is the compounding loop's back half: linked versions
(A1b) and comparison (A2), the highest-leverage PMF gate.
The 2026-07-08 burn-down pass landed the bulk of the interpret-surface cluster:
PR #182 fixed #171 Sig1+Sig2, #160(B), and #150's behavior half (with the #179/
#180 repro gates un-xfailed); PR #183 replaced the degraded-fallback English
copy with typed clarification contracts rendered by frontend static i18n
(es-419 parity restored, the 9 stale copy tests re-pointed at typed asserts);
and PR #169 landed the Agent Runtime Regression sweep — the full agent_runtime
suite + spine guardrails now run hermetically (synthetic_unit_fixture catalog)
on every runtime PR, zero hidden failures at tip (999 passed, 2 xfailed).
Current pointer: the interpret/edit spine is between owners; A1b (linked
IdeaVersion emission) is the next spine-chain slice and is unblocked.
Promotion to `main` is PAUSED. Remaining live blockers: #160(A) composer-None
fall-through and #151 card materialization (strict-xfailed, the only two xfails
in the suite), then a full live-eval rerun on the exact promotion SHA. #164
trails the cluster.
Execution runs off the P2 execution board below: point an agent at any READY
lane. The interpret/edit spine has exactly one owner lane at a time (currently
unowned; A1b is next in the spine chain).
Date: 2026-07-08
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

##### P2 execution board: decision memo gates + unlock status (AUTHORITATIVE, 2026-07-07)

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
`llm_interpreter*.py`, `artifact_edit_planner.py`). The spine is currently
between owners — A1 (#141), B1 (#140), and the B4 typed-prose series all landed;
A1b is next in the chain. Parallel runtime lanes keep new logic in their own
modules, touch shared dispatch minimally, and take rebase duty; the spine owner
merges first.

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
- A1 refine routing + loop repair (#141, PR #148): refine chip + NL edits route
  through the typed edit contract; same-period references bind to the latest run.
- A3 Idea Ledger portfolio browse (#147): saved ideas grouped by decision state
  in Omnisearch; backend-owned `ledger_groups` are the source of truth.
- B1 latest-result fact answers (#140, PR #153): peak-date/drawdown follow-ups
  answered from canonical `backtest_runs` facts, pending edit state preserved.
- B2 company-name asset preservation (#142, PR #146): messy multi-symbol
  company-name baskets survive to confirmation. CAVEAT: #171 reports this case
  regressed on the live eval at `4eae18e` — verify before `main`.
- B3 measurement trio: eval harness (#143), server-side PostHog product events
  (#144), append-only CostLedger (#145). The eval harness is a live landing gate.
- B4 language-gate retirement (#154, PRs #174-177): runtime prose composes from
  typed facts; degraded recovery copy and result chrome render from typed
  codes/keys; per-language copy tables retired, parity proven by eval.
- C1 execution realism — fees/slippage (#130, PR #178): merged flag-off behind
  `ARGUS_ENABLE_EXECUTION_REALISM`; legacy float path preserved when inert.
- Interpreter cost/perf (#156/#157, PR #172): automatic stable-prefix prompt
  caching on structured-artifact calls + per-tier reasoning-effort env overrides
  (`ARGUS_STRUCTURED_REASONING_EFFORT`, `ARGUS_CAPABILITY_REASONING_EFFORT`).
- #149 result-followup timeout recovery fixed for Python 3.10 (#168).
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

- **B1 Latest-result answers from run facts (#140).** DONE — merged as PR #153.
  Peak-date/value and drawdown follow-ups answer from canonical
  `backtest_runs`/result facts; when pending edit state is active and a turn
  classifies as a result question, it answers and leaves the pending state
  intact (the #148 regression suites stayed green); `result_run_id` is preserved
  in response metadata. FOLLOW-UP: #164 (OPEN) tracks the residual refine wall
  for untyped fact questions — emit a typed result-followup fact focus/key.

- **B2 Asset preservation in messy company-name prompts (#142).** DONE — merged
  as PR #146. Messy multi-symbol company-name baskets (TGT + WMT + COST) survive
  through `interpret -> asset resolution -> canonicalize -> confirmation`;
  provider-backed name resolution feeds INTO interpretation as context, never a
  post-LLM text rescan. REGRESSION WATCH: #171 (OPEN) reports the company-name
  case regressed on the live eval at `4eae18e` (alongside calendar-year windows
  nulled on recovery drafts). Re-verify the `test_interpret_stage.py` basket
  assertions before any `main` promotion; likely fallout from the recovery-draft
  work in #166 / the B4 typed-prose series.

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
  (2) **Product events** — MERGED (PR #144): server-side-only PostHog capture
  through the sanitizer; US Cloud region recorded; frontend key stays
  present-but-empty per the launch runbook. Review fixes landed: off-loop
  emission (no event-loop stalls), payload built inside the guard, loud
  unrecognized-region warning, real `privacy_mode` emission.
  (3) **Append-only CostLedger** — MERGED (PR #145): reversible migration with
  structural append-only enforcement (revoke before grant), correlation ids,
  eval-run metering, shared entry normalizer; OpenRouter usage/cost parsers
  extracted to `openrouter_usage.py` to satisfy the merged-state modularity
  budget. Apply the migration to dev/prod Supabase at next deploy.
  B3 lane COMPLETE — harness gates merges, events flow, spend is metered.

- **B4 Recovery-copy / language-gate retirement (#154).** DONE — merged as PRs
  #174-177. Runtime prose composes from typed facts (#174); degraded recovery
  copy renders from typed codes (#175); result chrome renders from typed keys
  (#177); migrated language surfaces are test-guarded (#176). Per-language copy
  tables (`assistant_copy_for_result`, `recovery_messages.py`) are retired;
  prose follows the detected turn language everywhere and EN/ES parity is proven
  by the B3 eval harness, not hardcoded. WATCH: #171 flags calendar-year windows
  nulled on recovery drafts — re-verify the recovery path before `main`.

- **B5 Interpreter cost/perf (#156, #157).** DONE — merged as PR #172. Automatic
  stable-prefix prompt caching on structured-artifact calls
  (interpretation/repair/field-fidelity/capability-conflict) and per-tier
  reasoning-effort env overrides (`ARGUS_STRUCTURED_REASONING_EFFORT`,
  `ARGUS_CAPABILITY_REASONING_EFFORT`) so dev runs cheap and production runs at
  full effort. OPEN follow-up on this lane: #159 (quality-gated model cascade —
  cheap primary, capable escalation; low-priority/deferred). NOTE: #160
  (interpreter dead-ends) surfaced from this lane's investigation but is a
  high-priority `main` blocker, not cost/perf polish — it lives in the
  main-promotion burn-down below, not here.

**Gate C — evidence credibility:**

- **C1 Execution realism — fees/slippage (#130).** DONE — merged as PR #178 into
  `codex/private-alpha-next` (9 atomic commits). Fees + slippage model end to
  end behind `ARGUS_ENABLE_EXECUTION_REALISM` (default OFF); the legacy float
  cost path is preserved byte-identical when the flag is inert; cost-surface
  fields recorded in API_CONTRACT and DATA_MODEL. Still OFF the critical path —
  the founder deliberately disclaims assumptions for the PMF stage — but it is
  now integration truth, not an async cherry-pick lane.

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

**Integration health (filed during #148 review verification; triaged
2026-07-03, refreshed 2026-07-07):**

- **#149** — FIXED (PR #168). Result-followup timeout recovery no longer dead on
  Python 3.10 (`asyncio.TimeoutError` vs builtin mismatch resolved); the failing
  test now passes on a 3.10 venv.
- **#150** — CLOSED (2026-07-08). Behavior half fixed by #166 (calendar-year
  audit drift) and PR #182 (stale provenance, cadence de-promotion, benchmark-
  owner repair — all #150 xfails removed). CI-visibility half fixed by PR #169:
  the full agent_runtime suite now runs on every runtime PR.
- **#151** — the last surviving #141 corner: an executable-complete draft plus
  model readiness prose never materializes the confirmation card, so bare
  affirmations re-confirm verbally (violates "canonical payload and UI prose
  disagree"). Still OPEN; queue before or alongside A1b. A `main` promotion
  blocker.
- **#171** — CLOSED (2026-07-08, PR #182). Sig1: refusal drafts materialize
  typed date intents into date_range (plus focused recovery for dropped
  windows); Sig2: missing fields recompute after the focused-repair context
  merge so provider-grounded baskets stay executable. The #179/#180 strict-xfail
  gates are un-xfailed and enforced by the #169 sweep. Residual risk is model-
  side only (grok options-classification nondeterminism), not spine logic.

##### Main-promotion burn-down — the interpret-surface lane (updated 2026-07-08: steps 1-2 SHIPPED via PR #182; #169 + #183 landed off-spine)

The remaining `main`-promotion blockers are not four scattered bugs; they are one
regression cluster on the interpret/edit spine, most introduced by the
07-06/07-07 merges. Treat them as a single burn-down lane with one owner.

Shared surface (why they cannot be parallel implementers): `stages/interpret.py`,
`interpreter/artifact_assumption_edit.py`,
`interpreter/unsupported_request_context.py`,
`interpreter/date_window_repair.py`, `llm_interpreter.py`. This is the spine —
exactly one implementation owner at a time. Parallel SCOUT/repro is fine;
parallel edits are not.

Members and roots:

- **#171 (high) — live eval red, the gate.** Two regressions: Sig1 (calendar-year
  windows nulled on recovery drafts) traces to #166 (`a5ac38b`,
  `date_window_repair.py` + `llm_interpreter.py`); Sig2 (#142 basket dropped,
  verdict flips to `unsupported`) traces to #165 (`a80d681`,
  `artifact_assumption_edit.py` + `unsupported_request_context.py`).
- **#150 (re-triaged high) — the mocked half of #171 Sig2.** The strict xfails
  tagged #150 (e.g. cadence terms promoted to assets) are the free, deterministic
  repro; the CI-gap half is OPEN PR #169 (off-spine). Closes with #171 Sig2.
- **#160 (high) — interpreter dead-ends.** (A) composer-`None` fall-through at
  `_latest_result_followup_recovery_if_applicable`; (B) silent trailing-year date
  default. (B) co-designs with #171 Sig1 as one date-provenance-on-recovery
  policy (trust or clarify — never null, never silent-default). (A)'s blocker
  status is conditional on the deployed grok/haiku tier.
- **#151 (high) — card materialization.** An executable-complete post-result draft
  plus a model `assistant_response` emits prose instead of `ready_for_confirmation`,
  so a bare "yes" has nothing typed to launch (`_stage_result_from_interpretation`
  + `artifact_assumption_edit.py`).
- **#164 (med) — trailing follow-up.** Typed result-followup fact focus/key; the
  residual refine wall behind #160(A). Not a gate; lands after the cluster.

Landing order (serial on the spine):

1. ~~#171 Sig2 + #150~~ — DONE (PR #182): basket survives the underfilled
   repair; all #150 xfails removed.
2. ~~#171 Sig1 + #160(B)~~ — DONE (PR #182): typed-intent materialization on
   refusal drafts + year-contradiction guard on invented default windows; the
   #179/#180 gates are un-xfailed.
3. #160(A) — composer-`None` falls through to the edit path. Still open;
   strict-xfailed (test_workflow_fact_answer_then_composer_none_edit_reroutes_
   to_planner). Principled fix is upstream LLM classification of edits as
   refine_current_idea (needs live eval coverage), not a deterministic patch.
4. #151 — materialize the confirmation card from the executable-complete draft.
   Still open; strict-xfailed; needs a multi-turn live repro shape.
5. Full live eval on the exact SHA → gate green. Then #164.

Off-spine, now LANDED: PR #169 (regression-sweep CI, hermetic
synthetic_unit_fixture catalog, runs on every runtime PR + nightly) and PR #183
(typed degraded-fallback clarifications + es-419 static rendering; the 9 stale
per-language copy tests re-pointed at typed asserts). Waiver valve: #171 permits issue-tagged scoped expected-fails to
unblock promotion if the founder accepts the regression short-term; the roots are
known data-dropping regressions, so fix is preferred over waive.

**Standing release discipline** (blocks `main`, not a lane): rerun the exact
clean-checkout suite gate (issue #134 / PR #135) before any branch or `main`
promotion instead of treating the repair as permanent proof for future SHAs.
Promotion to `main` stays PAUSED — #140-#142 are merged and the #171/#150/
#160(B) cluster is fixed; the remaining blockers are #160(A) and #151 (the only
two strict xfails in the suite), sequenced in the burn-down above.
The eval harness (B3 slice 1, PR #143) is now a live landing gate:
runtime-behavior PRs run the live eval suite once pre-merge; every `main`
promotion candidate runs the full live suite on its exact SHA with no
unexpected failures (expected-fails only for open issue-tagged bugs); rerun
the suite after any interpreter model or provider change. #171 is fixed in the
mocked + repro gates; the live suite must be re-run on the exact promotion SHA
before promotion (known model-side risk: grok classifies options ideas
nondeterministically — a tier/prompt concern tracked with #159, not spine
logic). Integration stays a fast checkpoint; `main` is the heavyweight
gate.

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
  slice. See `docs/archive/private-alpha-next-p2.1-capability-audit.md`.
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

##### P2.2 Backtest credibility — fees/slippage realism (DONE — merged as PR #178, flag-off)

- Status: DONE (PR #178, 9 atomic commits). Fees + slippage model end to end
  behind `ARGUS_ENABLE_EXECUTION_REALISM` (default OFF); legacy float cost path
  preserved byte-identical when inert; cost-surface fields recorded in
  API_CONTRACT and DATA_MODEL. The scope below is delivered, not pending.
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

##### P2.4 Failure and recovery trust (recovery pattern DONE via B4; live parity gate open)

- Status: the model-voiced, language-agnostic recovery pattern is DELIVERED — B4
  (#154, PRs #174-177) retired per-language copy so recovery/degraded prose
  renders from typed codes/keys in the detected turn language. The PMF gate below
  (Spanish-preferring users complete the loop unaided) is validated by the live
  eval harness, which is currently RED on #171 — close that before claiming the
  gate.
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
