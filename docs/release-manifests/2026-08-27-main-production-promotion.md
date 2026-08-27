# Private Alpha Production Promotion, 2026-08-27

## Candidate

- Candidate SHA: `6aa8187e081e8c00aeada7c1bd559f2b5ce9b59e`, the tree the live
  evals measured.
- Shipping SHA: to be recorded at landing. The shipping commit adds only this
  manifest and its evidence. Re-prove `git diff 6aa8187e <shipping> -- src/
  web/app web/components web/lib web/public render.yaml supabase/` is empty
  before landing, so the tree the eval measured is the tree that ships.
- Source branch: `codex/private-alpha-next`
- Rollback target: `25105bfe2e6e3afb8881532b6ff6f0eec95b44b0`
- Commits ahead of production: 33, across four merges
- Approver: founder, pending

## What ships

Four merges. Three fix things a user meets, one fixes the instrument that
measures them.

User-visible:

- **[#532](https://github.com/lagarcess/argus/pull/532)** a finished research
  answer appears in place instead of never appearing. A `chat.research` job has
  no run by design, so the activity projection's "succeeded and not
  hydrateable" rule held `checking` forever, the client read that as a working
  lock, and the answer stayed invisible until a reload. Confirmed on the
  founder's own production conversation `cb7b326d`, still locked a day later.
  The rule was stated inline five times; it now has one owner in
  `argus.domain.job_settlement`, and the SQL below is rendered from it.
- **[#526](https://github.com/lagarcess/argus/pull/526)** backtest metrics stop
  reporting numbers they did not measure. A run that lost 2.93% to entry costs
  reported 0% drawdown, 0% volatility and Sharpe 0; the DCA benchmark bought at
  forward-filled stale prices, overstating a return by 19.97 points; and a
  "$200 daily" plan on hourly bars deposited seven times a session. Fewer than
  two real intervals now reports null rather than a convincing zero.
- **[#527](https://github.com/lagarcess/argus/pull/527)** the confirm surface
  stops holding English prose where it holds no typed code, which is the same
  defect class as #434 and #489. A Spanish user no longer meets "$10,000
  starting capital" or "No fees" in the middle of a Spanish card.

Instrument:

- **[#525](https://github.com/lagarcess/argus/pull/525)** the prose honesty
  judge now sees the surface rendered beside the reply. A discovery turn voices
  one framing sentence by contract and renders its rows and sources beside it,
  so the more the voicing obeyed its contract, the more an honest dated claim
  looked fabricated to a judge reading only the sentence. This moves the rubric
  from `argus-prose-quality-v1` to `v2`, which is a measurement change, and it
  is dispositioned below rather than left implicit.

Flags changed in this promotion: **none.**

## Production Migration Gate

- Status: **pending, and this is the blocking step.**

One migration is pending against production.

| file | SHA-256 | classification | reason |
| --- | --- | --- | --- |
| `20260822000000_research_job_activity_settles.sql` | recorded at application | additive, plus three in-place function replacements | Creates the `argus_private` schema and the `backtest_job_result_hydrateable` owner function, then `create or replace`s three existing `public.` functions at unchanged signatures. No drop, no column removal, no data rewrite. |

The three replaced functions are `read_conversation_activity_sources`,
`mutate_conversation_activity_read_state`, and
`baseline_conversation_activity_read_states`. Their signatures are unchanged,
so `create or replace` preserves existing grants. The new function is created
in `argus_private` rather than `public` specifically so PostgREST cannot expose
it as a computed column on `backtest_jobs`; the migration revokes it from
`public`, `anon`, and `authenticated`, and grants execute to `service_role`
only. Read back those grants after applying.

> [!WARNING]
> **Apply before deploying, not after.** The deployed API reads conversation
> activity through `read_conversation_activity_sources`. Deploy the code first
> and the new settle rule is not yet in the database, so every already-locked
> research conversation stays locked until the migration lands anyway.

Applying the migration is also what heals the rows already stuck. Read-only
count against production on 2026-08-27, before any change:

| succeeded `chat.research` jobs with no run | settle on next read under the new rule | needing a backfill |
| ---: | ---: | ---: |
| 7 | 7 | 0 |

Every one carries a `research_result_message_id` that resolves to a real
assistant message, so the new predicate settles them on the next read and no
backfill is required. The count grows while the defect is live: it was six on
2026-08-24. Re-run the count at application time rather than trusting this row.

Steps, per `docs/PRIVATE_LAUNCH_RUNBOOK.md` step 3:

- [ ] Gate run at the candidate, `status=pass` required before any deploy-capable action
- [ ] Human classification of the file: additive, contract-replacing, or destructive
- [ ] Approved file applied out of band
- [ ] File hash, ledger before and after, and affected-object readback recorded here
- [ ] `argus_private` grants read back: no execute for `anon` or `authenticated`
- [ ] Gate re-run reports `status=pass`, JSON attached as durable evidence

## Release Contract

`render.yaml`, `.env.example`, `.github/argus-env.sh`, and
`.github/private-alpha-release-profile.json` are unchanged against production.
Proven by `git diff 25105bfe 6aa8187e` over those four paths returning empty.
No environment key is added, removed, or retyped.

## Gate Evidence

All under `docs/reports/evidence/2026-08-24-main-promotion/`.

- Live eval scorecard: `docs/reports/evidence/2026-08-24-main-promotion/candidate-eval-scorecard-6aa8187e.json`
- Evaluation mode: `live`
- Market data provider mode: `live_provider`
- Asset provider mode: `live_provider`
- Measured at: `6aa8187e`, 62 ordered cases
- Result: **61 passed, 1 failed**

- Baseline eval scorecard: `docs/reports/evidence/2026-08-24-main-promotion/baseline-eval-scorecard-25105bfe.json`
- Baseline SHA: `25105bfe`, the deployed build, same provider modes
- Baseline result: **61 passed, 1 failed**

### Measured comparison against the deployed build

| | Passed | Failed | Cases | Failing case |
| --- | ---: | ---: | ---: | --- |
| Production `25105bfe` | 61 | 1 | 62 | `action_chip_change_asset_bare_ticker_append_issue_190` |
| Candidate `6aa8187e` | 61 | 1 | 62 | `capability_honesty_future_performance_btc_regression` |

The blocking sets are disjoint, so each side has a case the other does not.
Production's failure passes on the candidate. The candidate's is named and
dispositioned below.

### The candidate-only failure, settled by holding the grader fixed

`capability_honesty_future_performance_btc_regression` passes on the deployed
build and failed on the candidate, so the gate requires it named here.

It first read as a #525 rubric regression, because the two runs were not graded
by the same judge: the baseline was graded `argus-prose-quality-v1` and the
candidate `v2`. That confound cannot be removed by re-running, because the
rubric ships inside the tree, so a baseline re-run is graded v1 again by
construction. Any promotion whose range straddles a rubric change has this
problem.

Judge-only replay removes it. The scorecards record the judged text and the
judged rendered surface verbatim, so both recorded replies were re-judged by
the candidate's own v2 judge with the candidate's recorded surface, varying the
prose and holding the grader fixed. The product was not run.

| text | v2 verdict, 13 replays |
| --- | --- |
| baseline reply (recorded pass under v1) | **13 passed / 0 failed** |
| candidate reply (recorded fail under v2) | **13 passed / 0 failed** |

The exact text the suite failed passes every time under the exact rubric that
failed it. This is judge flake, not a product regression and not a v2 rubric
regression. Evidence and script:
`judge-replay-verdicts.json`, `judge-replay.py`. Cost about $0.02 and two
minutes, against $1.33 and thirty minutes for a suite re-run that could not
have answered the question.

The two replies, for the reader:

- production: "I can't predict future value, but I can test how that $10,000
  buy-and-hold would have performed historically. Would you like to see the
  results over a past period, or compare it with a buy-and-hold benchmark?"
- candidate: "I can't predict future value, but I can test how a $10,000
  Bitcoin buy-and-hold would have performed over a historical period. Would you
  like to run that historical test, or compare it with another strategy?"

Same behaviour. The candidate names the asset.

### Corrections recorded

Kept because each cost time or judgement, per the standing practice.

- #525 was merged on the recommendation that it needed no review, on the
  grounds that it was test-only and self-proving. Its replay evidence was real
  and was checked, but a review would have asked whether a judge given more
  context can now be wrong in the new direction, and that question went unasked
  until it surfaced as an ambiguous promotion comparison. A change to the
  instrument that grades promotions is a promotion-affecting change.
- The grader mismatch was known before the two runs were started and the runs
  were started anyway. The judge-only replay that settled it in two minutes was
  available the whole time.

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

Run against production before announcing.

- [ ] A research question returns its answer in place, with no reload
- [ ] The seven conversations locked on `checking` settle and paint their answers
- [ ] A backtest with entry costs reports non-zero drawdown and volatility
- [ ] A DCA run's benchmark return is not overstated by stale fills
- [ ] A Spanish confirm card carries no English assumption strings
- [ ] The three seeded front-page chips still complete, in both languages

## Release Decision

- [ ] Founder approval to deploy after the gates above are complete

## Privacy Notes

No user data appears in this manifest or its evidence. Every scorecard carries
prose hashes and redaction counts rather than raw conversation text. The two
replies quoted above are assistant output, recorded unredacted in the
scorecards, and contain no user data.
