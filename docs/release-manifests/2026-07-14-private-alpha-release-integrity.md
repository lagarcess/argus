# Private Alpha Release Integrity Checkpoint

## Status

- Status: validated private-alpha checkpoint

This records the runtime candidate that was deployed and canaried on the
existing branch-deployed private-alpha Render validation surface. It is not a
production release or tester-access approval.

## Runtime Candidate and Scope

- Validated runtime candidate SHA:
  `373d1a12dd5f538a81150b20903f4f43db27c639`
- Candidate branch: `codex/private-alpha-next`
- Validation surface: existing private-alpha Render validation surface
- Runtime mode: `real-workflow`
- Market-data provider mode: `live_provider`
- Workflow task: `argus-backtests/run_backtest_job`
- Locale: `es-419`
- Immediate rollback SHA: `6985c6443de89374d019a61907127f1eba4c032f`

This manifest is runtime evidence only. The later documentation commit and PR
merge are documentation provenance, not deployed or canaried runtime evidence;
their SHA is recorded in the #198 closure comment after that merge.

## Deploy Proof

- API service: `argus-api`
  - deploy: `dep-d9arv80js32c73a9kc0g`
  - status: `live`
  - candidate SHA: `373d1a12dd5f538a81150b20903f4f43db27c639`
- App service: `argus-app`
  - deploy: `dep-d9as0gtaeets739rifkg`
  - status: `live`
  - candidate SHA: `373d1a12dd5f538a81150b20903f4f43db27c639`
- Workflow service: `argus-backtests`
  - workflow version: `wfv-d9as1gfavr4c73av09ig`
  - status: `ready`
  - candidate SHA: `373d1a12dd5f538a81150b20903f4f43db27c639`

## Release Configuration Proof

- Release profile status: `ready`
- Release-profile hash:
  `72b4780c28c091e08ce60a94746041ee808ad8831685b00b9cb368fbd0212a46`
- API/app environment fingerprint:
  `fce527a58871f0d0451f63eaa3eba29747f47bc631783319b7b2562963ff7d4b`
- Workflow environment fingerprint:
  `41218caa15717c2c0e0aa246487f8d19b64c532acd0c27ca584d9335cc0bc2c4`
- Workflow environment status: `ready`
- Effective workflow runtime proof: `ready`

Fast local mode remains distinct from this checkpoint: it uses memory-backed,
synthetic, mock-auth execution for quick deterministic feedback. This checkpoint
used the deployed production-parity private-alpha configuration: Supabase and
Postgres persistence, real auth, live provider-backed resolution, and Render
Workflow execution.

## Gate Evidence

- Local smoke: passed.
- Render warmup: passed, including the ready workflow proof and live-provider
  effective mode.
- Authoritative Spanish canary: passed on the exact runtime candidate.
  - Spanish signup request carried `es-419`; the privacy-safe duplicate-signup
    and login journey passed.
  - Authenticated Spanish Chromium journey passed.
  - The real asynchronous Render Workflow backtest completed.
  - Canonical result and evidence metadata were present before success.
  - Add decision saved a note successfully.
  - Result, evidence, and decision state hydrated after reload.
  - Omnisearch preserved canonical artifact identity.
  - Required visible Spanish static UI passed without English fallback.
  - Failure stage/reason: none.

The durable audit record for the full canary is the
[#197 closure evidence](https://github.com/lagarcess/argus/issues/197#issuecomment-4965556704),
not a temporary local artifact path.

## Privacy and Release Decision

- Privacy policy: `no_raw_ids; labels are sha256 prefixes`.
- No credentials or raw user, conversation, job, run, evidence, or decision
  identifiers are recorded here.
- No `main` merge occurred.
- No production deployment occurred.
- No automatic production deployment was enabled.
- No tester invitation or tester exposure occurred.
- Founder approval for later promotion or tester access is not recorded by this
  checkpoint.

## Sources

- [#197 closure evidence](https://github.com/lagarcess/argus/issues/197#issuecomment-4965556704)
- [#198 documentation closure](https://github.com/lagarcess/argus/issues/198)
