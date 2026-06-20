# Private Alpha Next Roadmap

Status: P1 verified on reintegration branch; awaiting promotion decision
Date: 2026-06-20
Branch family: `codex/private-alpha-next`
Audience: Founder, Codex orchestrator, bounded subagents, reviewers

This is the current execution board for Private Alpha Next after the clean P0
continuity reintegration. It turns the decision memo into ordered, testable
slices without importing contaminated runtime work from quarantine.

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
12. Supporting notes such as
    `docs/specs/private-alpha-performance-readiness-audit.md` and
    `temp/bytebytego/bytebytego.md`

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

- [x] Focused backend tests pass.
- [x] Focused frontend tests pass.
- [x] Live Codex browser QA passes locally.
- [x] Internal code review has no release-blocking findings.
- [x] Docs reflect the shipped behavior, not aspirational behavior.
- [x] No broad quarantine runtime diff was imported.

Verification note: these boxes describe the current
`codex/private-alpha-next-reintegration` candidate only. Promotion to
`codex/private-alpha-next` remains a separate founder-directed action.

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

### Design-Only Until Later

- Memory/data controls.
- Voice-to-composer STT.
- Public evidence excerpts.
- Broker/export handoff.
- Native mobile.
- Research Lab / Perplexity-style deep research.

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

The P1 workflow should keep that discipline:

- work on `codex/private-alpha-next-reintegration` or a focused child branch;
- promote to `codex/private-alpha-next` only after tests, browser QA, and review;
- keep each slice revertable;
- use subagents for bounded scouting, specs, tests, and reviews;
- keep architecture, prioritization, and final promotion with the main
  orchestrator and founder.
