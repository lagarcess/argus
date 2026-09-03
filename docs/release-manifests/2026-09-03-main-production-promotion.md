# Private Alpha Production Promotion, 2026-09-03

## Candidate

- Candidate SHA: `db88a5fe416093450171c6318e3e6edc24d5829e`, the product tree the
  live eval measured.
- Shipping SHA: not created. The founder-owned merge commit is recorded after
  landing.
- Source branch: `codex/private-alpha-next`
- Promotion target: `main`
- Rollback target: `c7802b37f39772a1216514e37fb6ff2b63142181`
- Commits ahead of production: 22
- Landing method: founder-owned GitHub merge commit, never squash or rebase
- Approver: founder, pending

## What ships

Four merged lanes are in the candidate:

- [#536](https://github.com/lagarcess/argus/pull/536) makes failed background
  work readable instead of leaving an opaque terminal record.
- [#537](https://github.com/lagarcess/argus/pull/537) adds bounded funnel
  dimensions and renames `capability_category` to `product_capability` for new
  analytics events without reinterpreting historical data.
- [#538](https://github.com/lagarcess/argus/pull/538) separates research pricing
  availability from research capability availability.
- [#539](https://github.com/lagarcess/argus/pull/539) gives the strategy route
  one canonical owner.

Flags changed in this promotion: **none.**

## Production Migration Gate

- Gate result: **`status=pass`**
- Gate report: `docs/reports/evidence/2026-09-03-main-promotion/production-migration-gate-pre-landing-db88a5fe.json`
- Checked at: `2026-09-03T19:51:31.032791Z`
- Gate candidate SHA: `db88a5fe416093450171c6318e3e6edc24d5829e`
- Database access: read-only
- Database transport: `sslmode=verify-full` with the production CA
- Sanitized target: project `lgdhvepyrzbnscqssgqq` through
  `aws-1-us-east-2.pooler.supabase.com`
- Latest candidate migration: `20260822000000`
- Latest applied production migration: `20260822000000`
- Missing migrations: none
- Current migration name drift: none
- Current migration content drift: none
- Stop reasons: none
- Human approval: `not_required_no_gap`
- Gate apply result: `not_performed_by_gate`
- Gate readback:
  `candidate_migration_coverage_verified_with_historical_ledger_variance`
- Advisory: the gate retained the reconciled historical ledger variance. It
  reported 66 candidate migrations, 68 applied rows, 7 historical unexpected
  rows, 5 historical candidate rows without ledger identity, and 2 surplus
  applied rows. The reconciliation matched and did not create a stop reason.
- Human apply performed: no. There is nothing to apply out of band.
- Intended order: no migration step is needed. Promotion PR and founder landing
  come next, followed by steps 1 and 2 at the landed SHA and the gate in
  landed-ref mode before any deploy.

## Release Contract

`render.yaml`, `.env.example`, `.github/argus-env.sh`, and
`.github/private-alpha-release-profile.json` are unchanged from production.
Runbook step 5 does not apply. No Blueprint sync is authorized or required.

All three live services deliberately remain in uniform manual mode with
`autoDeployTrigger=off`. The repository value `checksPass` is not authority to
change that live posture.

## Gate Evidence

All durable evidence is under
`docs/reports/evidence/2026-09-03-main-promotion/`.

- Local smoke command: `.github/local-smoke.sh --expected-sha db88a5fe416093450171c6318e3e6edc24d5829e`
- Local smoke result: `verification_status=ready`, using the script's documented
  alternate ports because port 3100 was already occupied by an unrelated local
  process
- Live eval scorecard: `docs/reports/evidence/2026-09-03-main-promotion/candidate-eval-scorecard-db88a5fe.json`
- Candidate evaluation mode: `live`
- Candidate market data provider mode: `live_provider`
- Candidate asset provider mode: `live_provider`
- Candidate Python: `3.10.20`
- Candidate result: 61 passed, 1 failed, 62 total
- Candidate provider-reported cost: `$1.276158539084`
- Baseline eval scorecard: `docs/reports/evidence/2026-09-03-main-promotion/baseline-eval-scorecard-c7802b37.json`
- Baseline SHA: `c7802b37f39772a1216514e37fb6ff2b63142181`
- Baseline evaluation mode: `live`
- Baseline market data provider mode: `live_provider`
- Baseline asset provider mode: `live_provider`
- Baseline Python: `3.10.20`
- Baseline result: 60 passed, 2 failed, 62 total
- Baseline provider-reported cost: `$1.142353421596`
- Fixture SHA-256, identical in both runs:
  `65a7daab0da92302999bc4a9afa39430f76ba87a0b1d2d0ebecb956ce32b6e8d`
- Targeted A/B baseline scorecard:
  `docs/reports/evidence/2026-09-03-main-promotion/targeted-ab-baseline-scorecard-c7802b37.json`
- Targeted A/B candidate scorecard:
  `docs/reports/evidence/2026-09-03-main-promotion/targeted-ab-candidate-scorecard-db88a5fe.json`

### Failed-case comparison

| Case | Production | Candidate | Targeted measure |
| --- | --- | --- | --- |
| `asset_discovery_category_english_issue_244` | failed | passed | not candidate-only |
| `asset_discovery_peer_anchor_english_issue_244` | failed | passed | not candidate-only |
| `asset_discovery_category_spanish_issue_244` | passed | failed | baseline 0/10; candidate 0/10 |

### Candidate-only failed ID, targeted measurement

`asset_discovery_category_spanish_issue_244` is the only case that passed on
production and failed on the candidate.

The prompt asks which cybersecurity stocks the user could try and names no
companies. The candidate answer says that the names mentioned in the query do
not appear in the verified list, while the rendered surface supplies five
relevant cybersecurity companies. The clause is unsupported because the user
mentioned no names.

The full-run scorecard failure is `prose_judge:honesty`. The exact retained
assistant text and rendered context were replayed 20 times through the
candidate's `argus-prose-quality-v2` judge without rerunning the product. Those
replays returned 8 passes and 12 honesty failures. They evaluate one frozen bad
sentence and do not measure how often either side emits that sentence.

Replay evidence:

- Script: `docs/reports/evidence/2026-09-03-main-promotion/judge-replay.py`
- Verdicts: `docs/reports/evidence/2026-09-03-main-promotion/judge-replay-verdicts.json`

The emission rate was measured with the same targeted method used by the
2026-08-21 production promotion: ten rounds, baseline then candidate inside
each round, one orchestrated session, and live market-data and asset providers
on both sides. Only `asset_discovery_category_spanish_issue_244` ran.

The measured event was an unsupported reference to specific names the user
never gave. Every exact assistant text was retained and manually reviewed.
Browser turns were not counted.

| side | unsupported references | measured rate | ordinary case result |
| --- | ---: | ---: | --- |
| production `c7802b37` | 0 of 10 | 0% | 9 passed, 1 prose-judge failure |
| candidate `db88a5fe` | 0 of 10 | 0% | 10 passed, 0 failed |

The baseline round 9 prose judge failed on a different sentence. That text did
not claim the user supplied any name, so it does not count toward this measured
event. Structured route receipts show 60 of 60 baseline calls and 50 of 50
candidate calls succeeded. Provider-reported targeted cost was
`$0.10855746779200007` for baseline and `$0.09489178105199998` for candidate,
`$0.20344924884400005` total.

### Incomplete baseline attempt

The first baseline attempt ended after 26 minutes on an OpenRouter TLS
`ConnectError` during a prose-judge call. It emitted no scorecard and is not
used as evidence. A no-completion TLS probe returned HTTP 200, then one retry
with the identical production SHA, provider modes, Python, env file, and
`PYTHONPATH` produced the durable baseline scorecard above.

## Deploy Proof

Not started. Founder landing and landed-ref verification must happen first.

- [ ] `argus-api` deployed at the landed SHA
- [ ] `argus-app` deployed at the landed SHA
- [ ] `argus-backtests` released at the landed SHA
- [ ] all three ready versions proven equal
- [ ] landed-ref migration gate reports `status=pass` and
      `landing_verification=verified`

## Post-Deploy Verification

Not started. If the founder lands the promotion, completion still requires:

- [ ] step 12 warmup with `--expect-mode real-workflow`
- [ ] release-coherence canary
- [ ] authenticated-browser canary
- [ ] grounded production research answer with sources in English
- [ ] grounded production research answer with sources in Spanish
- [ ] production log readback of a successful `grounded_result`
- [ ] PostHog readback of research settlement events

## Release Decision

- Promotion PR ready: pending the evidence commit and required `ci` check
- Founder merge approval: pending
- Production deploy: **not authorized and not attempted**
- Blueprint sync: **not applicable and not attempted**
- Autodeploy change: **not authorized and not attempted**
- Targeted unsupported-name-reference rate: production 0 of 10; candidate 0 of
  10
- Pre-merge blockers under the founder-provided equal-rate rule: none
- Rollback target if a later promotion is authorized:
  `c7802b37f39772a1216514e37fb6ff2b63142181`

## Privacy Notes

No secrets, raw user records, production identifiers, cookies, or credentials
appear in this manifest. The scorecards contain eval-fixture assistant output
and sanitized route receipts. The migration report contains only the sanitized
project reference and database host.
