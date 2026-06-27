# Private Alpha Next Roadmap

Status: P1 checkpoint closed; P2 board defined; P2.0 guardrail gate + P2.1
capability truth are the active next slices
Date: 2026-06-26
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

Do not reopen P0 unless a new reproducible bug appears. The quarantine branch
`codex/private-alpha-next-quarantine-fc231e8` remains read-only reference
material for ideas, tests, and failure evidence. Do not broad cherry-pick
runtime code from quarantine.

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

These branches remain read-only reference for product direction, anti-patterns,
UI ideas, and test inspiration. Do not broad cherry-pick runtime code from them.

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
   parity is proven by eval, not hardcoded.
6. Backend stays canonical truth; the frontend renders backend-provided state and
   never invents it; one LLM intent-classification call per turn.

These ship as a review checklist plus failing-test tripwires in P2.0 so the
disease cannot recur silently.

#### Milestones

Each milestone owns a PMF gate, is demoable in a founder-guided session, and is
one revertable slice family. Sequence: P2.0 (now, ongoing) -> P2.1 (foundation)
-> P2.2 -> P2.3. P2.4 and P2.5 parallelize around the spine; start P2.5
instrumentation early so founder-guided sessions generate gate signal from day
one.

##### P2.0 Spine guardrail gate (active now)

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

##### P2.1 Capability truth, done right (spec first)

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

##### P2.2 Backtest credibility ladder and engine boundary

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

##### Design candidate: Conversational edit contract (macro pattern)

Status: design-only, not yet sliced or scheduled. Founder-identified 2026-06-27.
Captured here so it stays current and pickup-ready; do not implement until sliced.

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

Until a milestone is activated, do not implement its runtime, backend, schema, or
UI changes. P2.0 and P2.1 are the only active slices; P2.2-P2.5 are defined but
not yet authorized for implementation.

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
