# Recognition contract (the 11-failure class), live measurement

Lane branch `claude/argus-recognition-contract-87e589`, integration base
`584e9a01` (the #515 merge; integration had not moved at measurement time).
Compare against the merged baseline scorecard
`2026-08-15-category-discovery-payload-routing/live-eval-scorecard-run2.json`
(49 passed / 11 failed at `9586a78d`).

The review round on PR #517 (2026-08-16) invalidated the pre-review
scorecards; they sit under `superseded/` for provenance. The measurements
below are the post-review record.

| run | head | result | non-green detail |
|---|---|---|---|
| baseline | `9586a78d` | 49 / 11 | all 11 failures typed, stable across runs |
| regression catch | `9ebe8791` | 57 / 3 | caught a review-fix regression (below); superseded |
| **run 1** | `f2a06a4b` | **58 / 2** | 1 typed (a discovery negative the model itself typed unsupported; settled 5/5-vs-5/5), 1 prose-judge |
| **run 2** | `6e7d52e6`* | **58 / 2** | 1 typed (Spanish weekly options, payloadless mode A; settled 2/5-vs-0/5), 1 prose-judge |

*Run 2's head differs from run 1's only by the comment-scrub commit
(docstrings and comments; no executable change, prompt freeze byte-identical,
same 2299-test green sweep).

## The eleven baseline failures at the final heads

All eleven flipped to pass in run 1; ten of eleven in run 2:

| case | run 1 | run 2 |
|---|---|---|
| action_chip remove_aapl / bare_ticker / compound_replace / lost_stage / asset_and_date | pass | pass |
| compound_benchmark_start_date (#339) | pass | pass |
| dca ceiling / zero-contribution / spanish seed+contribution (#455) | pass | pass |
| graceful_recovery weekly options EN | pass | pass |
| graceful_recovery weekly options ES | pass | fail (mode A) |

Zero typed regressions persist across runs: each run's residual is a
different case (a rotating serving tail), where the baseline's 11 failures
were stable run over run.

## The review-fix regression the re-measurement caught

The first post-review run (57/3 at `9ebe8791`, kept under `superseded/`)
flipped `dca_capital_semantics_stated_seed_reaches_ready_to_run` to failed:
the review fix for the \$20,000-budget finding moved ANY differing
capital_amount to `total_capital` when the sidecar claimed a budget, so a
WRONG sidecar verdict on "start with \$5,000 and add \$200 monthly" re-roled
the typed \$200 contribution into a budget and refused the plan. Fixed at
`f2a06a4b`: the budget move fires only when the amount is role-ambiguous; a
capital_amount typed as the contribution, or any amount beside a present
`recurring_contribution`, is an explicit primary fact the sidecar cannot
re-role. Both shapes are unit-locked, and the case passed both final runs.

## Settled flips (interleaved same-session A/Bs, frozen worktrees)

Distributions under `compound-matrix/ab-*.jsonl`; the A/B runner asserts the
imported `argus` package's file path per side.

- `action_chip_change_asset_bare_ticker_append_issue_190`: **head 5/5 vs
  baseline 2/5** at the unified-inclusion head; the earlier intermediate
  head's 1/5-vs-2/5 draw (also committed) is what forced the unified rule.
  Passed both final full runs.
- `asset_discovery_not_capability_question_issue_244` (run-1 typed flip):
  **5/5 vs 5/5** with the judge on; the run-1 failure was a one-off
  primary-read tail where the model itself typed the turn unsupported with
  constraints, which the guards honor.
- `asset_discovery_recent_ipo_exact_issue_344` (judge verdicts): **3/3 vs
  3/3** with the judge on; judge-side serving variance of the #516 family,
  and no changed surface is reachable from a typed discovery turn.
- `graceful_recovery_spanish_weekly_options_aapl`: **head 2/5 vs baseline
  0/5**. Head closes the mode-B hijack (a typed payload can no longer be
  answered as statistics); the residual is mode A, where the model omits
  both the act and the `unsupported_constraints` payload, leaving no typed
  fact for any deterministic layer to route on. Closing mode A needs a
  focused second read (#515's mode-A pattern) and is named follow-up scope,
  not covered by this lane.

## Compound-tier acceptance matrix

Twelve live edit turns against the same pending AAPL/MSFT/NVDA confirmation
card, three interleaved rounds per side (head `6e7d52e6` vs frozen baseline
`584e9a01`, one session), pass = every stated fact lands and the turn
reaches a confirmation-ready stage. The number that matters is the gap
between one operation and three or more.

| tier | head | baseline |
|---|---|---|
| 1 operation (6 cases x 3 rounds) | **18/18** | 12/18 |
| 2 operations (3 cases x 3 rounds) | **8/9** | 5/9 |
| 3+ operations, messy + Spanish (3 cases x 3 rounds) | **7/9** | 1/9 |
| total | **33/36** | 18/36 |

At the baseline, compounding collapses to 1-in-9. At head the gradient is
100% / 89% / 78%, and the three misses are one QQQ-read-as-asset round and
two four-op rounds that ended in a clarification: the turn re-asked instead
of applying, which is the designed failure direction (a re-ask, never a
silent drop or a wrong card). Tier-3 is one round lower than the pre-review
matrix because the review round removed acceptance slack (a mention is no
longer evidence, requested adds must land); the trade is deliberate: the
slack it removed is exactly what let a card gain an asset the user never
asked for.

## What this measures

The class fix, not eleven cases: a turn now carries every typed fact the
model produced, and each layer that previously discarded one either respects
it or leaves a turn-correlated receipt. The interpreter prompt and schema
descriptions are byte-identical to the baseline; the prompt freeze passes
untouched, so no fingerprint regeneration applies.

Known residuals, stated: mode-A payload omission on capability-limit turns
(the focused-read follow-up above); the whole-set replace phrasing "drop X,
just use Y from now on" re-asks instead of applying, a written decision in
`interpreter/asset_role_constraints.py` that trades a clarification on the
rare phrasing for never wiping un-named card members; and prose-judge
honesty verdicts of the #516 family that rotate independently of this diff.

## Cost

Pre-review measurement ≈ \$9.7 (including one full run lost to a mid-run
worktree write, recorded in the superseded README history). Post-review:
regression-catch run, two final runs, re-run matrix, and four interleaved
A/Bs ≈ \$9.0. Lane total ≈ \$18.7.
