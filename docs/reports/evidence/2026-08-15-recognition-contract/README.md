# Recognition contract (the 11-failure class), live measurement

Lane branch `claude/argus-recognition-contract-87e589`, integration base
`584e9a01` (the #515 merge; integration had not moved at measurement time).
Compare against the merged baseline scorecard
`2026-08-15-category-discovery-payload-routing/live-eval-scorecard-run2.json`
(49 passed / 11 failed at `9586a78d`).

| run | head | result | notes |
|---|---|---|---|
| baseline | `9586a78d` | 49 / 11 | all 11 failures typed |
| **run 1** | `b0c2623f` | **59 / 1** | the 1: prose-judge honesty on `graceful_recovery_weekly_options_aapl`, all typed checks passed |
| **run 2** | `69805356`* | **58 / 2** | 1 typed (`bare_ticker_append`, also failing at baseline), 1 prose-judge honesty (`recent_ipo`, the judge gap #515 documented) |

*Run 2's head differs from run 1's by a docs-only commit (run 1's scorecard);
the runtime tree is identical. A first run-2 attempt completed all 60 cases
but wrote no scorecard because copying run 1's scorecard into `docs/` mid-run
dirtied the worktree and the writer's final revalidation refused; that $1.33
bought a lesson, not an artifact, and the retry above is the recorded run 2.

## Case-by-case against the baseline

Ten of the eleven baseline failures flipped to pass in BOTH runs:

- `action_chip_change_asset_remove_aapl_issue_188`
- `action_chip_change_asset_compound_replace_issue_188`
- `action_chip_change_asset_no_active_ref_lost_stage_remove_aapl_issue_188`
- `action_chip_change_asset_no_active_ref_asset_and_date_issue_188`
- `compound_benchmark_start_date_preserves_confirmation_issue_339`
- `dca_capital_semantics_only_have_amount_is_ceiling_issue_455` (had failed in
  every committed scorecard before this lane)
- `dca_capital_semantics_zero_contribution_names_buy_and_hold_issue_455`
- `dca_capital_semantics_spanish_seed_and_contribution_issue_455` (the lane's
  documented flakiest tail)
- `graceful_recovery_weekly_options_aapl` (typed; run 1's residual failure on
  this case is judge-only)
- `graceful_recovery_spanish_weekly_options_aapl`

Zero typed pass→fail regressions in either run: every typed check that passed
at the baseline passed in both runs. Discovery routing (12/12), messy
English/Spanish, capability honesty, and language mismatch all held.

The three cases that were not green in both runs, each settled:

1. `action_chip_change_asset_bare_ticker_append_issue_190` (run 1 pass, run 2
   fail; baseline fail in both runs and in every earlier committed scorecard).
   Seam traces showed three distinct model emission modes losing the same bare
   "TSLA" answer. The first guard closed one mode; a same-session interleaved
   5v5 A/B at that intermediate head still read head 1/5 vs baseline 2/5
   (F F F F P vs F F P F P), so the rule was restated once at the right
   altitude — a bare single-asset answer to the pending asset slot is typed as
   that asset's inclusion, whatever labels the model guessed
   (`bare_asset_answer_typed_as_inclusion`, commit `b11c83aa`) — and the
   interleaved 5v5 at the final head read **head 5/5 (P P P P P) vs baseline
   2/5 (F F F P P)** in one session with frozen worktrees.
2. `asset_discovery_recent_ipo_exact_issue_344` (run 2 judge-only fail where
   the baseline run passed). Interleaved 3v3 with the judge on: **head 3/3,
   baseline 3/3**. The verdict is judge-side serving variance; #515's own
   evidence recorded the identical flip on this case, and no changed surface
   is reachable from a typed discovery turn (the knowledge-claim veto sits
   behind the `asset_discovery is not None` early return).
3. `graceful_recovery_weekly_options_aapl` run-1 prose verdict: the judged
   text reads "Argus can backtest equity strategies, but weekly options
   aren't currently supported. I can run a buy-and-hold test on AAPL for
   those same dates instead." — the judge's notes call it "truthful about
   the limitation" and then fail `honesty` for not acknowledging the
   limitation the text states in its first sentence. Judge blindness
   (#516 class), typed checks 7/7.

## Post-run delta

Two commits landed after the full runs (`35632a62`, `b11c83aa`); both touch
only the bare-asset-answer guard, reachable solely on a bare chip answer to
the pending asset slot. Per the reconciliation rule the affected acceptance
surface was re-measured instead of repeating the paid full runs: the 5v5
interleaved A/B above at the exact final head, plus live collateral probes of
`remove_aapl`, `compound_replace`, and `no_active_ref_multi_op` at the final
head (all passed).

## Compound-tier acceptance matrix

The acceptance bar: combining operations must cost nothing. Twelve live edit
turns against the same pending AAPL/MSFT/NVDA confirmation card, three
interleaved rounds per side (head `b11c83aa` vs frozen baseline `584e9a01`,
one session), pass = every stated fact lands and the turn reaches a
confirmation-ready stage.

The number that matters is the gap between one operation and three or more.

| tier | head `b11c83aa` | baseline `584e9a01` |
|---|---|---|
| 1 operation (6 cases x 3 rounds) | **18/18** | 13/18 |
| 2 operations (3 cases x 3 rounds) | **8/9** | 6/9 |
| 3+ operations, messy + Spanish (3 cases x 3 rounds) | **8/9** | 1/9 |
| total | **34/36** | 20/36 |

At the baseline, compounding collapses: three-plus operations land 1 time in
9 (the four-op messy English sentence and the three-op English sentence never
land). At head the tier gap is eleven points and flat: single operations are
perfect and stacking a second, third, and fourth operation costs one attempt
per tier, not the turn. The two head misses are one round each and are
primary-read variance, not layer drops: in round 1 the interpreter read
"change the benchmark to QQQ" with QQQ as a traded asset, and the messy
four-op sentence was answered as chat; both cases passed rounds 2 and 3 with
every stated operation landing. Per-round raw results and the matrix
definition sit under `compound-matrix/`.

The interleaved A/B distributions for the settled cases are also there:
`ab-bare-ticker-final-head.jsonl` (head 5/5 vs baseline 2/5, one session),
`ab-bare-ticker-intermediate-head.jsonl` (the 1/5-vs-2/5 draw that forced
the unified rule), and `ab-recent-ipo.jsonl` (3/3 both sides, judge on).

## What this measures

The class fix, not eleven cases: a turn now carries every typed fact the
model produced, and each layer that previously discarded one either respects
it or records why it fired. The interpreter prompt and schema descriptions
are byte-identical to the baseline — `tests/test_interpreter_prompt_freeze.py`
passes untouched, so no fingerprint regeneration applies and every behavior
change here is deterministic post-interpretation routing.

## Cost

Run 1 ≈ $1.33; lost run-2 attempt ≈ $1.33; run 2 ≈ $1.33; seam-trace probes
and collateral probes ≈ $0.9; interleaved case A/Bs ≈ $0.8; compound matrix
≈ $3.0 (72 live edit turns). Total ≈ $9.7.
