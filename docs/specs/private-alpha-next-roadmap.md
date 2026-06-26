# Private Alpha Next Roadmap

Status: P1 checkpoint closed; P2 planning intentionally parked
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

### P1 Next

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

### P2 Placeholder

P2 is intentionally blank until the founder slices it into one or more cohesive,
high-leverage milestones. Do not treat the decision memo's remaining roadmap
slices as authorized implementation scope yet.

Next step when work resumes:

1. Read `docs/specs/private-alpha-next-decision-memo.md`, especially:
   - `## 11. Updated Roadmap Slices`;
   - `## 16. Recommended Immediate Action`;
   - `### Backtest credibility ladder`;
   - `### Failure and recovery trust`;
   - `### 15.1 Idea, Strategy, Run, Evidence, and Decision Object Boundary`;
   - `### 15.2 Ledger UI, Recents, and Omnisearch`;
   - `### 15.3 Memory Product Posture`;
   - `### 15.5 Evaluation, Cost, and Analytics Instrumentation`.
2. Cross-reference the contaminated reference branches only for product
   direction, anti-patterns, UI ideas, and test inspiration:
   - `codex/private-alpha-next-quarantine-fc231e8`;
   - `codex/private-alpha-next-p2.1-quarantine`.
3. Draft a bounded P2 board here before implementation. The board must include
   user-facing outcome, allowed surfaces, forbidden surfaces, verification,
   browser QA, rollback posture, and explicit stop conditions.

Until that board exists, do not implement P2 runtime, backend, schema, or UI
changes from this roadmap.

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
