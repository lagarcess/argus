# Main Production Promotion Checkpoint

## Status

- Status: production deployment validated
- Runtime candidate SHA:
  `5d1eec11a29867f420b20f1240f1d432f2317e51`
- Candidate branch: `main`
- Promotion PR: [#209](https://github.com/lagarcess/argus/pull/209)
- Validation surface: stable manual Render production topology
- Release captain: Codex
- Approver: founder-directed production deployment after PR #209 approval

This checkpoint records the exact `main` merge commit deployed after the
Private Alpha Next promotion. It authorizes neither automatic deployment nor
tester invitation or exposure.

## Promotion And Ancestry Proof

- PR #209 merge commit:
  `5d1eec11a29867f420b20f1240f1d432f2317e51`
- First parent, prior `main`:
  `e82a9fa0d31310dfe151163d73d1193853b87ed3`
- Second parent, reviewed integration candidate:
  `b3fc38ea6257aef36bd694a42ed928297c97051d`
- Promoted tree:
  `59582f430a2a812b713a3a3166168a639a415ce4`
- The merge tree exactly matched the reviewed integration tree.
- Post-merge `main` CI passed with no non-green checks.

## Deploy Proof

- API service: `argus-api`
  - deploy: `dep-d9bfio7avr4c73aisvg0`
  - status: `live`
  - deployed SHA: `5d1eec11a29867f420b20f1240f1d432f2317e51`
- App service: `argus-app`
  - deploy: `dep-d9bfjternols73elei4g`
  - status: `live`
  - deployed SHA: `5d1eec11a29867f420b20f1240f1d432f2317e51`
- Workflow service: `argus-backtests`
  - workflow version: `wfv-d9bfl1ucjfls7388udn0`
  - status: `ready`
  - released SHA: `5d1eec11a29867f420b20f1240f1d432f2317e51`
- Automatic deploys remained off on all three surfaces.

## Environment Proof

- Expected mode: `real-workflow`
- Release profile status: `ready`
- Release-profile hash:
  `72b4780c28c091e08ce60a94746041ee808ad8831685b00b9cb368fbd0212a46`
- API/app environment fingerprint:
  `fce527a58871f0d0451f63eaa3eba29747f47bc631783319b7b2562963ff7d4b`
- Workflow environment fingerprint:
  `41218caa15717c2c0e0aa246487f8d19b64c532acd0c27ca584d9335cc0bc2c4`
- Workflow environment status: `ready`
- Effective workflow provider mode: `live_provider`
- Effective workflow runtime proof: `ready`
- Workflow proof task: `argus-backtests/workflow_proof`
- Real workflow task: `argus-backtests/run_backtest_job`
- Required workflow secrets were present with redacted proof only.
- Effective capabilities: English and Spanish (`es-419`), Omnisearch enabled,
  real workflow execution enabled; strategies, collections, onboarding, and
  exploratory suggestions disabled.
- Production Supabase contained migration
  `20260713000001_finalize_backtest_completion`; its RPC remained
  security-invoker with `search_path=public` and service-role-only execution.

## Gate Evidence

- Clean checkout/setup: passed on Python `3.10.20`.
- Exact-SHA local smoke:
  `.github/local-smoke.sh --expected-sha 5d1eec11a29867f420b20f1240f1d432f2317e51`
  passed. The first cold-checkout readiness request exceeded its client timeout
  while dependencies initialized; a direct runtime-build diagnostic completed
  in 1.961 seconds and the one bounded exact-SHA rerun passed.
- Render warmup:
  `.github/warmup-render.sh --expect-mode real-workflow` passed, including
  product readiness, stale-job scan, release-config audit, workflow proof, and
  effective live-provider mode.
- Authoritative Spanish canary:
  - First attempt completed the real backtest but correctly failed the release
    gate because a model-generated Quick Take was rejected and Argus used its
    deterministic fallback (`quick_take_draft_rejected`).
  - The one permitted settling rerun passed at the same SHA without model,
    provider, budget, runtime, or deployment changes.
  - Real asynchronous workflow backtest completed.
  - Result readout used the expected LLM explain-stage voice.
  - Finalized run/evidence labels:
    `backtest_run_e6e8ecccdb09`, `evidence_artifact_9e070e487a88`.
  - Idea/version labels: `idea_9657eacfb988`,
    `idea_version_b93e366606c5`.
  - Decision label: `decision_note_1bd17d6dc39e`.
  - Result, evidence, and decision state hydrated after reload.
  - Omnisearch preserved canonical artifact identity.
  - Authenticated Spanish Chromium signup/login journey passed: 1 test passed.
  - Canary evidence SHA-256:
    `a3b619bbb3118e495154535baf3dcaf6ec576b1df5bd4bf1fa7b2896db10d7b8`.
  - Exit status: `0`.
- Final API health was `healthy`, app returned HTTP `200`, and the stale-job
  scan reported zero stale, unresolved, reconciled, or errored jobs.

## Rollback

- Same-tree provenance fallback SHA:
  `b3fc38ea6257aef36bd694a42ed928297c97051d`
  - API deploy: `dep-d9bepfrtqb8s73cf71lg`
  - App deploy: `dep-d9beqm6cjfls738761r0`
  - Workflow version: `wfv-d9beromrnols73ek1e0g`
  - This tree is identical to the promoted production tree. Redeploying it can
    restore pre-merge SHA provenance, but it is not a functional rollback for
    health, canary, workflow, or product defects.
- Immediate functional rollback SHA:
  `373d1a12dd5f538a81150b20903f4f43db27c639`
  - API deploy: `dep-d9arv80js32c73a9kc0g`
  - App deploy: `dep-d9as0gtaeets739rifkg`
  - Workflow version: `wfv-d9as1gfavr4c73av09ig`
- Deeper source rollback SHA:
  `6985c6443de89374d019a61907127f1eba4c032f`
- Rollback remains manual and founder/release-captain owned.
- Use the functional rollback for persistent health/warmup/canary failure,
  workflow finalization failure, or contradictory persisted artifact state.
  Exact-SHA provenance drift alone may use the same-tree fallback after the
  running tree is independently verified.

## Release Decision And Boundaries

- Production deployment: performed and technically validated.
- Automatic production deployment: not enabled.
- Tester invitation or exposure: not authorized and not performed.
- A1b or A2 work: not started.
- Known deferred model caveat: options-idea classification nondeterminism from
  #159 remains founder-accepted for this no-user checkpoint; no additional
  waiver was invented by this deployment.
- Any tester exposure remains a separate founder decision after the checked-in
  manifest record and applicable legal/consent gates are complete.

## Privacy Notes

- Privacy policy: `no_raw_ids; labels are sha256 prefixes`.
- No raw user, conversation, job, run, evidence, decision, cookie, credential,
  prompt, or route-receipt payload is recorded here.
- Canary labels are stable SHA-256 prefixes for audit correlation only.
- Release profile and evidence hashes contain no credentials or account ids.

## Sources

- [PR #209 promotion](https://github.com/lagarcess/argus/pull/209)
- [Private-alpha release-integrity checkpoint](2026-07-14-private-alpha-release-integrity.md)
