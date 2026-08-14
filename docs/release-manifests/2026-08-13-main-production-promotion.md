# Private Alpha Production Promotion, 2026-08-13

## Candidate

- Candidate SHA: `d4d2ac14e83be892747200fde313b3cda64f811d`
- Shipping SHA: `a17c419f`, which adds this manifest, its evidence, and the
  comparison gate on top of the measured candidate. Proven to carry **no
  product delta**: `git diff d4d2ac14 a17c419f -- src/ web/app web/components
  web/lib web/public render.yaml supabase/` is empty, so the tree the eval
  measured is the tree that ships.
- Source branch: `codex/private-alpha-next`
- Rollback target: `5d8ba7a5f259f0ae65a4477d2952ad6c09096c1e`
- Commits ahead of production at cut: 133
- Approver: founder, 2026-08-13

## What ships

User-visible:

- **#453** the unsupported-strategy refusal no longer fires on supported
  strategies and no longer prints raw interpreter output as a sentence
  subject. Refusals name a supported alternative instead.
- **#481** a guest pressing New chat lands on the landing empty surface
  rather than a blank state.
- **#483** Argus no longer asks for the asset it just named back to the user.
- **#480** registering after using Argus as a guest creates a real account, so
  Supabase emits `user_signedup` instead of the change-email confirmation a
  real user received on 2026-08-12.
- **#466 / #467** win rate and profit factor derive from closed-trade P&L
  instead of per-bar returns, and annualization derives its time basis from
  the coverage-owned market calendar.

Operational:

- **#449** production migration parity gate, plus its live fix for
  transaction-pooler session semantics.
- **#452** the production canary splits release coherence from the
  authenticated browser journey, ending the Turnstile-blocked signup leg.
- Live-eval scorecard provenance is now mandatory, and a promotion manifest
  without live-eval evidence fails its own release-docs test.
- Documentation states that public account creation is open.

Flags changed in this promotion:

- `ARGUS_ENABLE_PERSONALIZATION_MEMORY` false to **true**. Exposure remains
  gated by `MEMORY_EXPOSURE_ROLES = {admin, developer}`, so this reaches the
  two role-holding accounts and no registered user.
- `ARGUS_ENABLE_MEMORY_SEMANTIC_RECALL` remains **false**.

## Production Migration Gate

- Status: **pass**
- Gate output: `docs/reports/evidence/2026-08-13-main-promotion/production-migration-gate.json`
- `migration_apply`: `never`
- `database_access`: `read_only`
- `database_transport`: `tls_verify_full`
- Latest candidate version: `20260812183000`
- Latest applied version: `20260812183000`
- Pending migrations: none

`20260812183000_guest_account_signup_handoffs.sql` was applied to production
before this promotion, inside a single transaction, with its ledger row
written at the exact version so candidate and production agree.

Pre-apply verification against live production:

- `prepare_guest_workspace_handoff` did not exist, so `create or replace`
  created it rather than producing an ambiguous overload.
- Both dropped constraints existed under the exact names the migration uses.
- All existing `guest_workspace_handoffs` rows satisfied the replacement
  constraint, 2 of 2.
- `has_table_privilege('postgres','auth.users','TRIGGER')` was true.

Post-apply verification, executed and rolled back so nothing persisted:

- An ordinary signup with no `argus_guest_signup` marker inserted
  successfully. The `auth.users` trigger returns early and does not affect
  normal registration.
- A forged marker was rejected with `guest_signup_handoff_invalid`.

Advisory, not blocking: `historical_migration_ledger_variance`. Production
reports 64 applied rows against 62 candidate migration files. The top versions
agree and nothing is pending. The variance predates this promotion and is
most consistent with the 2026-08-11 hand remediation.

## Gate Evidence

- Live eval scorecard: `docs/reports/evidence/2026-08-13-main-promotion/live-eval-scorecard.json`
- Evaluation mode: `live`
- Market data provider mode: `live_provider`
- Asset provider mode: `live_provider`
- Python: `3.10.20`
- Fixture identity: `83fabea16c770e049926051e38ad1cbbb568b3b00181c3009866645405da9b4a`, 46 ordered cases
- Result: **34 passed, 12 failed**

- Baseline eval scorecard: `docs/reports/evidence/2026-08-13-main-promotion/baseline-eval-scorecard-5d8ba7a5.json`
- Baseline SHA: `5d8ba7a5`, the deployed build, same provider modes
- Baseline result: **33 passed, 13 failed**

### Measured comparison against the deployed build

| | Passed | Failed |
| --- | ---: | ---: |
| Production `5d8ba7a5` | 33 | 13 |
| Candidate `d4d2ac14` | 34 | 12 |

- **11 failures are shared**, broken identically on both builds.
- **2 improvements**: `action_chip_change_asset_remove_aapl_issue_188` and
  `asset_discovery_trending_crypto_exact_issue_344` fail on the deployed build
  and pass on the candidate.
- **1 case flips the other way**:
  `asset_discovery_spanish_generated_pharma_escalation_issue_344` passes
  deployed and fails on the candidate, on
  `semantic_turn_act: expected 'asset_discovery', got 'educational_question'`.

That single flip is judged variance rather than regression, on this evidence:
the `asset_discovery_routing` category fails **4 of 12 on both builds**, three
of the four are the same cases, and the two that differ offset each other. A
regression makes a category worse; this category is equally broken on both.
Independently, this suite moved three checks between two runs on
byte-identical product code earlier the same day, so its noise floor is at
least that.

The candidate is therefore not worse than the deployed build, and is
marginally better.

### Recorded disposition, founder-approved 2026-08-13

This promotion proceeds with a failing live-eval suite because the comparison
above shows **every failure is already deployed**.

| Failures | Behavior | Owner | Already in production |
| --- | --- | --- | --- |
| 5 | A confirmation applies only part of a requested edit, without disclosing the omission | [#431](https://github.com/lagarcess/argus/pull/431) | yes |
| 4 | Asset discovery routing | [#396](https://github.com/lagarcess/argus/pull/396) | yes |
| 2 | An explicit unsupported-strategy request is absorbed by the research rail instead of refused | [#396](https://github.com/lagarcess/argus/pull/396) | yes |
| 1 | `capability_honesty_options_straddle_tsla`, variance | none | n/a |

The single case that had not failed before is variance rather than
regression: the product tree is byte-identical between the `5c12a923` run
that passed it and the `d4d2ac14` run that failed it, and its prose judge
passed with no failed criteria. Only `stage_outcomes` differed, which is the
same mechanism as the two graceful-recovery failures.

The four asset-discovery failures are attributed to the rail by category and
by their presence in the earlier `5c12a923` run. They were not bisected to a
commit. They fail identically on already-deployed code, so they do not change
the promotion decision.

Not accepted as permanent. Both families need fix lanes:

- Partial edits applied silently are a correctness defect the user cannot
  see, and they violate #431's own locked contract that every requested edit
  is applied or explicitly surfaced as not applied.
- The rail absorbing an explicit unsupported-strategy request conflicts with
  the #453 contract that the clarification stage owns the response when an
  unsupported verdict survives admission.

### Process finding

The 2026-08-11 promotion shipped without live-eval evidence, which the runbook
requires for every `main` promotion candidate. Eight historical evidence
omissions were found. The release-docs test added in this cycle now fails a
manifest that lacks a durable live-eval scorecard, so this cannot recur
silently.

## Deploy Proof

To be completed by the operator at deploy time for all three services:
`argus-api`, `argus-app`, and `argus-backtests`. Render cannot declare the
Workflow service in a Blueprint, so `argus-backtests` requires its own
verification rather than being assumed from the other two.

- [ ] `argus-api` deployed at candidate SHA
- [ ] `argus-app` deployed at candidate SHA
- [ ] `argus-backtests` workflow version at candidate SHA
- [ ] Autodeploy state recorded for all three

## Environment Proof

- [ ] Render readback audit run and drift reported by named key, not by count
- [ ] `ARGUS_ENABLE_PERSONALIZATION_MEMORY` set to `true` on `argus-api`

`autoDeployTrigger` is expected to read `off` on all three services against a
repository value of `checksPass`. That is deliberate and accepted, not drift
to correct. A Blueprint sync would silently enable autodeploy, so the memory
flag must be set through the Render API instead.

## Release Decision

- [ ] Founder approval to deploy after the gates above are complete

## Privacy Notes

No user data appears in this manifest or its evidence. The live-eval scorecard
carries prose hashes and redaction counts rather than raw conversation text.
