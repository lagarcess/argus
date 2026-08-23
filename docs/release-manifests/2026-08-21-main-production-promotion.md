# Private Alpha Production Promotion, 2026-08-21

## Candidate

- Candidate SHA: `a5f1139bb686d44053adf7b4fdf0e1c8b76598ce`, the tree the live
  evals measured.
- Shipping SHA: to be recorded at landing. The integration tip when this
  manifest was prepared was `e9ff4757d9999256a50e43f2dd6fc2612d2a1ddd`, which
  adds only promotion evidence on top of the measured candidate. The shipping
  commit adds only this release-gate correction, its regression test, and
  release documentation. Re-prove `git diff a5f1139b <shipping> -- src/ web/app
  web/components web/lib web/public render.yaml supabase/` is empty before
  landing, so the tree the eval measured is the tree that ships.
- Source branch: `codex/private-alpha-next`
- Rollback target: `811dcbcb96edbc8b392e80f981a6c73ed252ffe6`
- Commits ahead of production at draft: 78
- Approver: founder, pending

## What ships

Four merges, and the theme is the front door. Production data for 2026-08-11 to
08-13 showed **37 real users, 42 sessions, 2 of whom returned**, and all three
seeded chips on the landing surface failing. Every user-visible item below was
verified by driving it, not by reading a report.

User-visible:

- **[#524](https://github.com/lagarcess/argus/pull/524)** every front-page chip
  completes end to end, in both languages. Before: Netflix 0 of 3 in English
  ("I couldn't complete the data lookup"), the Costco comparison complete
  server-side but invisible until a reload, and the Coca-Cola chip dying on
  "200$", "13,000 pesos", and "un millón de pesos". Five root causes, of which
  the widest was a **stale Perplexity `fetch_url` rate that rejected every
  grounded answer that fetched a URL** — no test in the repo could catch it,
  because the rate table validated itself.
- **[#522](https://github.com/lagarcess/argus/pull/522)** a search that finds
  assets it cannot price now names them and says why, instead of answering "I
  could not confirm any of the names I found" and stopping. Provider outages no
  longer read as facts about the asset: the tradability probe returns three
  values, so an unknown takes the retryable route rather than telling a user
  Bitcoin is unconfirmable.
- **[#521](https://github.com/lagarcess/argus/pull/521)** copying a card yields
  the language the card is rendered in. The English clipboard was also wrong,
  hiding behind a Spanish bug report.
- **[#476](https://github.com/lagarcess/argus/pull/476)** a bilingual welcome
  email when a user is promoted off the allowlist, with a durable claim and
  delivery record that make retries safe.

Flags changed in this promotion: **none.**

## Production Migration Gate

- Status: **pending, and this is the blocking step.**

Three migrations are pending against production. Unlike the 2026-08-16
promotion, which carried none, this one requires a real production database
session, a human classification, out-of-band application, and a gate re-run.

| file | SHA-256 | classification | reason |
| --- | --- | --- | --- |
| `20260812142717_add_access_welcome_deliveries.sql` | `5c06f12586858b4e16d69805aab61cfa6fe6d4e64e482df336a53255149c1ab8` | contract-replacing | Creates the delivery table and functions, but its trigger also rejects allowlist updates that the existing contract permits. |
| `20260812173805_claim_access_welcome_delivery.sql` | `a59fc95194223314b2db6fbffd04527fc61f58286fae703ec8fffb3861939aea` | contract-replacing | Replaces the five-argument completion function with the six-argument claim contract, revokes direct delivery inserts, and adds the claim-freeze trigger. |
| `20260816150000_scope_access_welcome_enforcement.sql` | `1d7055d6ef26f78cd960c52bb66123409f49b0c96b1547ec306c6fb50948bed2` | destructive | Drops the guard trigger/function and the `consumed_at` column, then replaces five callable functions. |

The third is the one to read closely: it **drops a trigger and the
`consumed_at` column**, and narrows the delivery trigger to the exact
`requested -> user` transition. That narrowing is what makes a backfill
unnecessary, and it is why re-enabling a pre-migration user does not fail.

> [!WARNING]
> **Apply before deploying, not after.** `.github/canary-render.sh` and the ops
> approve route call five functions these migrations create, including
> `delete_private_alpha_access_welcome_artifacts`, which is how the daily canary
> tears down the allowlist and delivery rows it creates. Deploy first and the
> canary makes rows it cannot delete, on every run, in production. The runbook
> records this rule at the migration-gate section.

Steps, per `docs/PRIVATE_LAUNCH_RUNBOOK.md` step 3:

- [ ] Gate run at the candidate, `status=pass` required before any deploy-capable action
- [ ] Human classification of each file: additive, contract-replacing, or destructive
- [ ] Approved files applied out of band, in repository order
- [ ] File hash, ledger before and after, and affected-object readback recorded here
- [ ] Gate re-run reports `status=pass`, JSON attached as durable evidence

The intended order is fixed: run the read-only gate; record the production
ledger and affected-object readback; confirm the destructive-migration backup
and approval; apply only these three pinned files in repository order; read the
ledger and affected objects again; rerun to `status=pass`; only then land and
deploy. The third file must not run until the newly created claims table is
read back with zero live claim state, because its `consumed_at` drop is
irreversible without the production backup.

## Release Contract

`render.yaml`, `.env.example`, `.github/argus-env.sh`, and
`.github/private-alpha-release-profile.json` are unchanged against production.
No environment key is added, removed, or retyped.

## Gate Evidence

All under `docs/reports/evidence/2026-08-21-main-promotion/`.

- Live eval scorecard: `docs/reports/evidence/2026-08-21-main-promotion/candidate-eval-scorecard-run2.json`
- Evaluation mode: `live`
- Market data provider mode: `live_provider`
- Asset provider mode: `live_provider`
- Measured at: `a5f1139b`, 62 ordered cases
- Result: **60 passed, 2 failed**

- Baseline eval scorecard: `docs/reports/evidence/2026-08-21-main-promotion/baseline-eval-scorecard-811dcbcb.json`
- Baseline SHA: `811dcbcb`, the deployed build, same provider modes
- Baseline result: **59 passed, 1 failed**

- Baseline: `baseline-eval-scorecard-811dcbcb.json`, run at the deployed SHA
  from a detached worktree with `PYTHONPATH` pinned to that tree, so the
  editable install could not silently measure the candidate.
  **59 passed / 1 failed**, 60 cases.
- Candidate: `candidate-eval-scorecard-run1.json` (59/3) and
  `candidate-eval-scorecard-run2.json` (60/2), 62 cases. The candidate suite is
  two larger because #524 added two chip-shaped two-turn cases.

### Measured comparison against the deployed build

| | Passed | Failed | Cases |
| --- | ---: | ---: | ---: |
| Production `811dcbcb` | 59 | 1 | 60 |
| Candidate `a5f1139b` | 60 | 2 | 62 |

Three cases moved between the two candidate runs of identical code, which is
why the runbook compares failed-ID subsets rather than counts. The aggregate
count assertion was removed generically: totals are not a promotion signal,
while every candidate-only failure still must be named and dispositioned.

### The one disputed case, settled independently

`dca_capital_semantics_stated_seed_reaches_ready_to_run_issue_455` passes at
baseline, passed candidate run 1, and failed candidate run 2. It was the only
candidate-only failure across both runs, and it was settled by an independent
reader with a targeted interleaved A/B rather than by argument:

| side | result |
| --- | --- |
| baseline `811dcbcb` | **10 passed / 0 failed** |
| candidate `a5f1139b` | **10 passed / 0 failed** |

Ten rounds, baseline then candidate within each round, one session, live
provider both sides. Scorecards `targeted-ab-*.json`. Cost about $0.20.

**Final blocking sets are identical on both sides:**
`{asset_discovery_spanish_generated_pharma_escalation_issue_344}`, which fails
in production today.

**Every candidate failure also fails at baseline. The gate passes.**

### Browser verification, before merge rather than after

The three seeded chips were driven by hand on the merged tree, because the eval
cannot see the landing surface and a green case had already been mistaken for a
working feature once this cycle.

| chip | production | merged tree |
| --- | --- | --- |
| Netflix | 0 of 3 | grounded answer, 5 sources, backtest bridge |
| Costco comparison | invisible until reload | rendered in the open view |
| Coca-Cola then "200$" | "I could not resolve that choice" | KO recurring-buys card, ready to run |

The live DOM was grepped for the exact production failure strings; zero hits.

### Corrections recorded

Kept because each was stated with more confidence than the evidence carried,
and each cost time or money:

- A review finding was called critical and did not reproduce on either tree.
  The fix is harmless and stayed in; the severity was repeated from a code
  trace rather than tested.
- Provider rate limiting was offered as the cause of the run-1 discovery
  failures. There were zero rate limits in any run; the pattern matched log
  line numbers. That failure is unexplained rather than explained.
- The disputed case was described as two-turn. It is one-turn, and that error
  caused a working measurement to be abandoned in favour of three full runs
  costing roughly $4.00, against the $0.20 the correct measurement cost.

## Deploy Proof

All three services, in order. Render cannot declare the `argus-backtests`
Workflow in a Blueprint, so it needs its own verification rather than being
assumed from the other two.

- [ ] `argus-api` deployed at the landed SHA
- [ ] `argus-app` deployed at the landed SHA
- [ ] `argus-backtests` workflow version at the landed SHA
- [ ] Autodeploy state recorded for all three

## Environment Proof

- [ ] Render readback audit run, drift reported by named key rather than by count

No environment change is required. `autoDeployTrigger` is expected to read `off`
on all three against a repository value of `checksPass`. That is deliberate and
accepted, not drift to correct.

## Post-Deploy Verification

Run against production before announcing. Each of these failed on the deployed
build.

- [ ] Netflix chip returns a grounded answer with sources
- [ ] Costco chip renders in the open view without a reload
- [ ] Coca-Cola chip, then "200$", reaches a runnable card
- [ ] The same three in Spanish
- [ ] "find me trending cryptos" names something actionable, or names what it
      found and could not use
- [ ] Copying a Spanish card yields Spanish
- [ ] An allowlist promotion sends exactly one welcome email

## Release Decision

- [ ] Founder approval to deploy after the gates above are complete

## Privacy Notes

No user data appears in this manifest or its evidence. Every scorecard carries
prose hashes and redaction counts rather than raw conversation text.
