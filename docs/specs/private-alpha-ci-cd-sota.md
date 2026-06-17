# Private Alpha CI/CD SOTA Plan

Status: Draft
Date: 2026-06-17
Branch: `codex/private-alpha-next`
Audience: Founder, Codex, reviewers, release-captains

## Purpose

This spec defines the long-term release and validation system Argus needs to
avoid the failure modes surfaced during the private-alpha branch deploy and
issue #117.

The goal is not merely to fix one bug. The goal is to establish a release
system where:

- branch state, deploy state, runtime env state, and feature-flag state are
  visible and checked together;
- private-alpha testing can happen on an internet-reachable surface without
  exposing users to unverified behavior;
- language support, runtime mode, and workflow mode are part of the release
  contract, not informal knowledge;
- a reload cannot resurrect contradictory chat state after a stream failure;
- the path from `codex/private-alpha-next` to `main` is explicit and safe.

## What Broke

Issue #117 exposed a multi-layer drift, not a single bug:

1. A supported user prompt was treated as slow/unstable enough to exceed the
   visible stream contract.
2. The UI rendered a generic failure state, which encouraged a retry.
3. The backend later completed interpretation/confirmation and persisted a
   successful artifact for the same logical request.
4. On refresh, the transcript hydrated into a contradictory state: the failure
   text remained, the duplicate retry remained, and the completed artifact
   appeared below it.
5. The live private-alpha deploy was internet-reachable before the work was in
   `main`, which made the branch act like a public staging surface without a
   disciplined promotion boundary.
6. The current runtime/env management relies on a mix of `render.yaml`,
   `render-env-sync.sh`, manual Render changes, and repo defaults, which makes
   it hard to prove what the service is actually running.

## Root Cause Summary

### Issue #117

The proximate root cause is an ownership gap between stream failure handling,
runtime completion, and hydration.

- The API stream can time out or fall back slowly while still allowing the
  runtime to complete later.
- The frontend can decide the stream has failed and show a generic retry state
  before the backend has finished reconciling the turn.
- On reload, persisted conversation/messages/artifact state can hydrate from a
  later successful path without reconciling the earlier failure surface.

That creates a broken user story:

- failure message
- duplicate user retry
- late completed artifact

This is not PR-ready behavior because it violates conversation trust.

### Release-Process Drift

The branch/deploy process also drifted from a SOTA approach:

- `render.yaml` still points at `main`, but private-alpha validation was being
  performed on manually deployed branch commits.
- Render environment state is partially documented in repo scripts and partially
  synchronized manually.
- The current release path checks deploy commit and warmup, but not all effective
  env/feature/runtime modes as a single contract.
- Spanish support was enabled/assumed inconsistently, revealing that locale is a
  product behavior dimension, not just a translation file concern.

## Target State

The long-term target is a promotion-based system with explicit release
contracts.

### Environment Topology

- `main`: the clean release checkpoint and the normal production promotion
  source.
- `codex/private-alpha-next`: integration staging branch only.
- `staging`: the internet-reachable validation surface, with controlled config
  and no automatic promotion to production.
- `private-alpha prod`: the private-audience production surface. It should be
  treated like production for release discipline, even if access is limited.
- production: only receives promoted `main` releases or equivalent tagged
  release artifacts.

### Contract Layers

Release readiness should be checked at four layers together:

1. Commit layer: what SHA is deployed?
2. Runtime layer: what mode is the service actually running in?
3. Locale/feature layer: what user-visible surfaces are enabled?
4. Behavior layer: do canaries and reloads preserve the right artifact lifecycle?

### Ownership Rules

- Render/CI/CD config is owned by Codex release-captains, not left to ad hoc
  manual toggles.
- Locale enablement is part of release scope, not hidden UI debt.
- Runtime mode flags are part of the release contract, not optional tuning.
- Frontend hydration must not invent or merge backend facts; it only renders
  canonical state.
- Every promoted release should have a release manifest containing commit SHA,
  expected env fingerprint, flag state, canary matrix, rollback target, and a
  go/no-go decision record.

## Implementation Phases

This plan is intentionally split so the highest-risk work can be done in
parallel where possible.

### Phase 1: Reproduce And Freeze The Failure Shape

Objective:
- Encode issue #117 as a durable regression test before changing behavior.

Scope:
- Use the exact prompt and the exact contradictory lifecycle observed in Render.
- Capture both the live-stream failure and the reload/hydration contradiction.

Likely files:
- `tests/test_chat_stream_contract.py`
- `tests/test_chat_runtime_reload_guardrails.py`
- `web/e2e/chat-action-recovery.spec.ts`
- `web/__tests__/chat-artifact-history.test.ts`

Parallel sub-slices:
- backend stream contract test
- frontend hydration/reload test
- E2E browser reproduction

Verification:
- The test suite fails until the stream/reload contradiction is fixed.
- The tests assert that one logical turn cannot both fail visibly and later
  hydrate as a completed success without reconciliation.

### Phase 2: Fix Runtime Finalization Ownership

Objective:
- Ensure a chat turn has one authoritative terminal path.

Scope:
- The backend stream must not let a late runtime success reappear as a
  contradictory artifact after a visible failure.
- Cancellation, final-state fetch, and runtime completion need to agree on a
  single terminal outcome.
- Preserve LangGraph as the only chat brain.

Likely files:
- `src/argus/api/routers/agent.py`
- `src/argus/api/chat/runtime_worker.py`
- `src/argus/agent_runtime/runtime.py`
- `tests/test_chat_stream_contract.py`

Parallel sub-slices:
- stream timeout / cancellation boundary
- request / turn correlation and logging
- final-state reconciliation

Verification:
- A slow or fallback-heavy turn either resolves within the visible contract or
  fails cleanly without later contradictory artifact mutation.
- Late runtime completion cannot create a second truth for the same request.

### Phase 3: Fix Reload And Hydration Reconciliation

Objective:
- Make refresh load one coherent state, not a failure plus a later success for
  the same request.

Scope:
- The UI should hydrate from canonical backend state and suppress stale retry
  affordances when a later authoritative artifact exists.
- It must not infer strategy facts from prose.

Likely files:
- `web/components/chat/ChatInterface.tsx`
- `web/components/chat/ArtifactHistory.tsx`
- `web/lib/chat-backtest-jobs.ts`
- `web/e2e/chat-action-recovery.spec.ts`

Parallel sub-slices:
- transcript normalization
- visible action derivation
- reload persistence coverage

Verification:
- Refresh shows one consistent artifact lifecycle.
- No duplicate user turn remains paired with a stale generic failure if a later
  authoritative result exists.

### Phase 4: Harden Slow Interpretation Recovery

Objective:
- Supported prompts that hit model fallback churn still produce a valid,
  bounded outcome.

Scope:
- Keep the LLM interpreter first for normal user language.
- Validate facts after interpretation, not before.
- Make slow interpretation/fallback paths explicit in logs and tests.

Likely files:
- `src/argus/agent_runtime/llm_interpreter.py`
- `src/argus/llm/openrouter.py`
- `tests/agent_runtime/test_llm_interpreter.py`
- `tests/test_openrouter_policy.py`

Parallel sub-slices:
- timeout/fallback policy
- structured interpreter repair path
- request receipts and traceability

Verification:
- The issue prompt no longer degrades into a misleading
  `unsupported_or_out_of_scope` path because of fallback churn.
- Route receipts make it clear what happened and why.

### Phase 5: Close The SNDK Data-Window Gap

Objective:
- Handle the market-data edge honestly instead of collapsing it into a generic
  stream failure.

Scope:
- `SNDK` should either produce a supported confirmation or a clear data-window
  explanation.
- No regex phrase gates, no special-case ticker hacks, no strategy-name routing.

Likely files:
- `src/argus/domain/market_data/assets.py`
- engine launch/provider tests
- interpreter tests involving explicit asset/date windows

Verification:
- The exact `SNDK` prompt produces a supported, transparent response path.

### Phase 6: Build A Release-Config Drift Gate

Objective:
- Compare live Render config against the repo contract before tester invites.

Scope:
- Check effective env values, not just deploy SHA.
- Surface missing baseline runtime keys and mismatched locale/feature settings.
- Keep secrets redacted.

Likely files:
- `.github/argus-env.sh`
- `.github/render-env-sync.sh`
- `.github/warmup-render.sh`
- `tests/test_environment_scripts.py`
- `tests/test_render_runtime_compatibility.py`

Parallel sub-slices:
- env contract extraction
- redacted live env audit
- CI assertion for required runtime flags

Verification:
- The gate fails if the live deploy is missing baseline runtime vars or is in
  the wrong mode.
- The gate reports drift in a way a release captain can act on quickly.
- The gate should emit an env fingerprint that can be attached to the release
  manifest and canary record.

### Phase 7: Expand Canary Coverage

Objective:
- Make the canary cover the real failure class, not just happy-path completion.

Scope:
- Include English and Spanish.
- Include stream failure/reload/recovery behavior.
- Include workflow mode verification.
- Keep canary output privacy-safe.

Likely files:
- `.github/canary-render.sh`
- `.github/workflows/private-alpha-canary.yml`
- `tests/test_render_canary_script.py`

Verification:
- Canary fails when the environment contract drifts or when reload hydration
  contradicts the runtime state.
- Canary passes only when commit, env, and behavior all agree.
- Canary evidence should be stored with the release manifest so the same SHA
  and env fingerprint can be audited later.

### Phase 8: Update Runbooks And Source-Of-Truth Docs

Objective:
- Make the promotion path understandable and repeatable.

Scope:
- Document branch promotion rules.
- Document environment ownership.
- Document the release gate sequence.
- Document the Spanish readiness requirement as a release criterion, not a
  one-off test.

Likely files:
- `docs/PRIVATE_LAUNCH_RUNBOOK.md`
- `docs/specs/private-alpha-next-integration.md`
- `docs/specs/private-alpha-ci-cd-sota.md` if this becomes the active roadmap

Verification:
- A new release captain can follow the gate without tribal knowledge.

## Serialization And Parallelism

Recommended order:

1. Phase 1 first, because it freezes the actual bug shape.
2. Phase 2 and Phase 3 can then proceed in parallel, since backend finalization
   and frontend hydration are separate ownership areas once the contract is
   pinned.
3. Phase 4 and Phase 5 can run in parallel with Phase 2/3 if they do not touch
   the same files.
4. Phase 6 should land before any new tester invite, because it governs the
   promotion gate itself.
5. Phase 7 follows the drift gate so the canary reflects the final release
   contract.
6. Phase 8 is last, but it should be drafted during implementation so the gate
   instructions stay in sync with the code.

## Acceptance Criteria

The system is ready only when all of the following are true:

- Issue #117 no longer reproduces a generic error followed by a late completed
  artifact for the same logical request.
- Reload/hydration cannot preserve contradictory state.
- Spanish support is validated as a release dimension, not assumed.
- The live deploy’s effective runtime env matches the documented contract.
- The canary asserts both commit and runtime mode.
- `main` is the promotion target, not a surprise prerequisite.
- Public tester exposure only happens after the release gate passes.
- A release manifest exists for each promoted candidate and includes SHA,
  env fingerprint, canary evidence, rollback target, and approver.

## Non-Goals

- Do not add new product surfaces unrelated to release hygiene.
- Do not implement the Perplexity Research Lab thesis here.
- Do not widen the backtesting feature set beyond private-alpha scope.
- Do not invent frontend truth to paper over backend drift.
- Do not change Supabase schema or RLS as part of the CI/CD spec.

## Notes From Investigation

The current checkout and private-alpha deploy evidence show:

- `codex/private-alpha-next` is the active integration lane.
- Render services are still configured with branch `main`, while the private
  alpha flow relies on manual deploys and env sync helpers.
- The live API is in `real-workflow` mode now, but the effective env contract
  should still be audited before each invite.
- The web feature flags are intentionally off for private alpha.
- Spanish support exists in the codebase and tests, but the release process
  must treat it as a contract, not a memory.
