# Private Alpha Production Promotion, 2026-08-16

## Candidate

- Candidate SHA: `6e7d52e6a385431613cd159748decc207750d88b`, the tree both
  live runs measured.
- Shipping SHA: `830a9688beadfe32b1a5e24ab0f52ea71ab75443`, which adds the
  browser-QA evidence, this manifest, and a modularity baseline registration
  on top of the measured candidate. Proven to carry **no product delta**:
  `git diff 6e7d52e6 830a9688 -- src/ web/app web/components web/lib
  web/public render.yaml supabase/` is empty, so the tree the eval measured is
  the tree that ships.
- Source branch: `codex/private-alpha-next`
- Final shipping tip at landing: `738fd53952988f2fb51c5b0df20f22d8c65c5d40`, which adds
  only the staged promotion evidence commit on top of `830a9688`.
  `git diff 6e7d52e6 738fd539 -- src/ web/app web/components web/lib web/public
  render.yaml supabase/` is empty, so the measured tree is still the tree that
  shipped. Commits ahead of production at landing: 100.
- Landed on `main` as merge commit `3134388255ad74161cecee7b37622c67a09f0840`
  (PR #518, merge method, parents `78c2d6c2` and `738fd539`; landed tree is
  byte-identical to the candidate tree). Landed-ref migration gate rerun at the
  landed SHA: `status=pass`, `landing_verification.status=verified`.
- Rollback target: `78c2d6c264c660483ab5deb8ea197077945a7755`
- Commits ahead of production at cut: 99
- Approver: founder, 2026-08-16

## What ships

This promotion is one theme: **Argus stops discarding what the user said.**
Every user-visible item below is an instance of that, and each was measured
live rather than accepted on a lane's report.

User-visible:

- **[#517](https://github.com/lagarcess/argus/pull/517)** the recognition
  contract. Editing a confirmation card applies every operation the user
  stated, in all three shapes: remove, add, and compound. Measured 1 in 5
  before, and the compound tier moved from 1 of 9 to 7 of 9. The root cause
  was not the model: five deterministic layers were destroying correct model
  reads, and on the traced case three independent reads were correct and code
  refused all three.
- **[#515](https://github.com/lagarcess/argus/pull/515)** category discovery
  routes on its typed payload instead of a single-choice act label. "Find me
  trending crypto", sector screens, and recent IPOs now reach the search path
  that was already built and configured, in English and Spanish. It was dark
  because one gate read the label.
- **[#514](https://github.com/lagarcess/argus/pull/514)** repair and
  unsupported routes stop discarding user-supplied facts.
- **[#511](https://github.com/lagarcess/argus/pull/511)** DCA volatility,
  Sharpe, and drawdown measure performance instead of counting deposits as
  gains, annualization is money-weighted, and the card names its return basis.
  On the audit example drawdown moved from −20% to −36% and Sharpe from +4.83
  to −13.75, so a losing run finally reads as one.
- **[#491](https://github.com/lagarcess/argus/pull/491)** starting capital and
  recurring contribution are separate facts that can never substitute for each
  other.
- **[#507](https://github.com/lagarcess/argus/pull/507)** confirmation,
  clarification, and capacity prose render in the workspace language instead
  of leaking English.
- **[#506](https://github.com/lagarcess/argus/pull/506)** one-click feedback,
  and registration emits a signal that distinguishes guest conversion from
  direct signup.

Operational:

- **[#513](https://github.com/lagarcess/argus/pull/513)** the text the
  interpretation model reads is fingerprinted against a committed scorecard.
  Prompt builders and schema field descriptions are one measured surface, and
  changing either requires evidence. This exists because #491 rewrote the
  shared prompt for a DCA change, passed its own tests and CI, and silently
  regressed asset extraction, date preservation, and discovery routing.
- **[#505](https://github.com/lagarcess/argus/pull/505)** DCA capital
  semantics coverage, 14 cases. The suite had zero before.
- **[#494](https://github.com/lagarcess/argus/pull/494)** the canary splits
  release coherence from the authenticated browser journey.

Flags changed in this promotion: **none.**

## Production Migration Gate

- Status: **pass, trivially**
- `git diff --name-only 78c2d6c2 830a9688 -- supabase/migrations/` is empty.
  This promotion introduces no migration, so there is nothing to apply and
  nothing to verify against live production.

## Release Contract

`render.yaml`, `.env.example`, `.github/argus-env.sh`, and
`.github/private-alpha-release-profile.json` are unchanged against production.
No environment key is added, removed, or retyped by this promotion.

## Gate Evidence

- Live eval scorecard: `docs/reports/evidence/2026-08-16-main-promotion/live-eval-scorecard.json`
- Evaluation mode: `live`
- Market data provider mode: `live_provider`
- Asset provider mode: `live_provider`
- Measured at: `6e7d52e6`, 60 ordered cases
- Result: **58 passed, 2 failed**

- Baseline eval scorecard: `docs/reports/evidence/2026-08-16-main-promotion/baseline-eval-scorecard-78c2d6c2.json`
- Baseline SHA: `78c2d6c2`, the deployed build, same provider modes, run from a
  detached worktree with `PYTHONPATH` pinned to that tree so the editable
  install could not silently measure the candidate's source
- Baseline result: **32 passed, 14 failed**

### Measured comparison against the deployed build

| | Passed | Failed | Cases |
| --- | ---: | ---: | ---: |
| Production `78c2d6c2` | 32 | 14 | 46 |
| Candidate `6e7d52e6` | 58 | 2 | 60 |

- **Zero candidate-only failures.** Both candidate residuals also fail on the
  deployed build, so nothing that works in production breaks here.
- **12 of production's 14 failures are fixed.**
- The candidate suite is 14 cases larger; the DCA capital-semantics category
  did not exist at the deployed SHA.

The comparison the runbook requires is the failed-ID subset, not the counts.
That subset test passes outright.

### Residual failures, both already deployed

| Case | Why | Owner |
| --- | --- | --- |
| `asset_discovery_recent_ipo_exact_issue_344` | Typed routing is correct; the prose judge cannot see the discovery sidecar's rows and sources and rejects a sentence those rows support | [#516](https://github.com/lagarcess/argus/issues/516) |
| `graceful_recovery_spanish_weekly_options_aapl` | Mode-A payload omission: the model emits neither the act nor the constraints, so no typed fact exists to route on | named follow-up, needs a focused unsupported read |

Neither is a regression. The second improved rather than closed: an
interleaved A/B at the fix head measured 2 of 5 against 0 of 5 on the
baseline.

### Measurement discipline applied in this cycle

Recorded because it changed the outcome twice, not as process narration.

- Every lane's numbers were re-derived from its committed scorecards against a
  baseline run independently, never accepted from a report. Two lanes' headline
  claims did not survive that check: #514 reported 10 fixes and 2 held after
  merge, and #510 reported an edit fix that an interleaved A/B later measured
  at 2 of 10 on the very baseline that contained it.
- Cases that changed status were settled by interleaved A/B distributions at
  frozen commits in one session, not by re-probing a single head. That is what
  showed the #510 win was a favorable draw rather than a fix.
- An independent code review of #517 found 12 defects, 3 of them mirror-image
  losses introduced by the fix itself. The re-run it forced then caught the
  review fix over-rotating, re-roling a typed $200 contribution as a budget.
  Both the review and the re-run were load-bearing.
- Browser QA drove every scenario by hand against the rendered card. It found
  a clarification-continuity defect no eval case covers: after answering a
  date question, a parked removal is silently lost and the asset returns to
  the card undisclosed. Pre-existing, outside this lane, and not a promotion
  blocker, but it is the same class this promotion closes elsewhere.

## Deploy Proof

To be completed by the operator at deploy time for all three services:
`argus-api`, `argus-app`, and `argus-backtests`. Render cannot declare the
Workflow service in a Blueprint, so `argus-backtests` requires its own
verification rather than being assumed from the other two.

- [x] `argus-api` deployed at candidate SHA: deploy `dep-da10j3s9v7es73ab3amg`,
      status `live`, commit `3134388255ad74161cecee7b37622c67a09f0840`
- [x] `argus-app` deployed at candidate SHA: deploy `dep-da10jttbedkc73bovs3g`,
      status `live`, commit `3134388255ad74161cecee7b37622c67a09f0840`
- [x] `argus-backtests` workflow version at candidate SHA: version
      `wfv-da10kspt0dsc73aoign0`, status `ready`, commit `3134388`
- [x] Autodeploy state recorded for all three: `off` on `argus-api`,
      `argus-app`, and `argus-backtests`; all three deployed explicitly in the
      runbook order with no Blueprint sync
- Deploy readback: `deploy/deploy-status.txt`. Render workflow runtime proof,
  run separately per the 2026-08-12 disposition:
  `deploy/workflow-runtime-proof.json` (`status=succeeded`,
  `provider_mode=live_provider`)

## Environment Proof

- [x] Render readback audit run and drift reported by named key, not by count:
      `release-config-audit --expect-mode real-workflow` reported every env key
      `ok` on all three services (zero env drift), API mode pairs matched
      real-workflow, `workflow_env_status=ready`. The only drift rows were
      `autoDeployTrigger expected=checksPass actual=off` on all three services,
      the deliberate accepted state below. Warmup components (API health,
      readiness, stale-job scan with zero stale, frontend, mode readback) all
      passed; the monolithic wrapper stops at that accepted audit reading and
      was not recorded as green (`deploy/warmup-components.txt`).

No environment change is required by this promotion. `autoDeployTrigger` is
expected to read `off` on all three services against a repository value of
`checksPass`. That is deliberate and accepted, not drift to correct.

## Canary, both surfaces

Run 2026-08-16 as dispatched `Private Alpha Canary` workflow run
[31967388628](https://github.com/lagarcess/argus/actions/runs/31967388628) at
head `31343882`, with the dedicated canary identity.

- **Authenticated browser journey: PASSED.** Spanish Golden Path completed one
  real workflow backtest at the exact deployed SHA, zero console and page
  errors, finalized evidence identity, decision captured
  (`canary/authenticated-browser.json`).
- **Release coherence: FAILED at `warmup: warmup_probe_failed`, structurally.**
  Its own pre-warmup probes passed: all three deployed SHAs matched `31343882`,
  health, readiness, stale-job scan, and frontend green. The wrapper then
  stopped because the config audit folds the three accepted
  `autoDeployTrigger off vs checksPass` rows into its overall status. This
  surface cannot report green while live triggers are deliberately manual
  against a repository value of `checksPass`; the same is true for every
  scheduled canary run until the founder either enables `checksPass` on all
  three or the audit learns an accepted-manual state. The two sub-proofs the
  surface never reached were covered separately: the Render workflow runtime
  proof passed (`deploy/workflow-runtime-proof.json`), and the API
  signup-denial probe was deliberately not reproduced by hand outside the
  script's cleanup traps, so it remains outstanding for the first green
  coherence run (`canary/release-coherence.json`,
  `canary/release-coherence-capture.json`).

A local coherence attempt before the dispatch failed identically, and a local
browser-journey attempt failed closed at
`browser_auth: canary_identity_is_not_dedicated` because the dedicated canary
credentials exist only in GitHub secrets; both recorded in the operator log,
neither spent a paid journey.

## Post-Deploy Verification

Run against production before announcing. These are the behaviors this
promotion claims, and each failed before it.

Run 2026-08-16 against production at `31343882` by scripted Playwright with an
operator session; captures in `post-deploy/`. Note the identity confound: the
operator account is admin on hosted, so admin-gated memory exposure is in play
for these draws while the eval identities never had it.

- [x] On a card with three assets, "remove AAPL" removes it and re-runs:
      MSFT+NVDA card re-ran to completion, +96.1% (`check1/`)
- [x] "add TSLA" keeps all four: AAPL, MSFT, NVDA, TSLA re-ran, +72.4%
      (`check2/`)
- [x] "remove AAPL and replace with TSLA and GOOGL" lands every operation:
      MSFT, NVDA, TSLA, GOOGL re-ran, +72.9% (`check3/`)
- [ ] "find me trending crypto" returns searched rows, not an explanation:
      0 of 3 draws rendered rows in English. Every draw did execute the search
      (real trending names surfaced: Worldcoin, Lighter, Pudgy Penguins), so the
      #515 routing fix is live, but none of the serving day's English candidates
      resolved to a tradable asset and the turn ended in a re-ask
      (`check4/`, `check4b/`, `check4c/`)
- [x] The same in Spanish: searched row rendered, `Probar AAVE/USD` with price,
      volume, and sources, 5 fuentes (`check5b/`; first Spanish draw captured
      mid-stream and is inconclusive, kept for completeness)
- [x] A DCA run's return row reads as return on contributions: card reads
      "+10.2% retorno sobre aportes" with $500 monthly and $0 starting capital
      (`check6/`). Observation, not part of this check: the Quick read prose
      under that card mixed English into a Spanish workspace, the #507 prose
      class on the DCA readout path
- [ ] "backtest weekly options on apple from 2024-01-01 to 2024-12-31" names
      the limit and keeps the asset and window: 1 of 3 draws correct (named
      the equities-only limit, kept AAPL and offered the same period). The
      other 2 draws returned a fabricated "weekly options strategy" stat
      readout over a trailing year ending on the serving date, the
      knowledge-answer hijack class; the gate's English eval case passed at the
      candidate, so this residual is distributional in production
      (`check7/`, `check7b/`, `check7c/`)

Five of seven verified; the two open boxes are measured distributions recorded
above, in the same defect classes the manifest already names as residuals, and
neither is a candidate-only regression relative to the gate evidence.

## Release Decision

- [ ] Founder approval to deploy after the gates above are complete

## Privacy Notes

No user data appears in this manifest or its evidence. Both live-eval
scorecards carry prose hashes and redaction counts rather than raw
conversation text.
