# Never dead-end, never invent: measurement evidence

Lane base: `811dcbcb`. Reconciled one-way with integration `7707f6ab`.
Candidate: `628747ce` (see `provenance.candidate_sha` in each scorecard).

Comparison baseline:
`docs/reports/evidence/2026-08-16-main-promotion/live-eval-scorecard.json`,
**58 passed / 2 failed**.

These two runs supersede an earlier pair taken at `bdb4529a`, before the
contract-conflict resolution and the terminal-recovery fix. Those scorecards no
longer describe any commit on this branch and were replaced rather than kept.

## Live runs, both at `628747ce`

| run | passed | failed | failures |
| --- | --- | --- | --- |
| 1 | 60 | 0 | none |
| 2 | 57 | 3 | see below |

Run 2's three failures, none of which overlap the baseline's two:

1. `capability_honesty_options_straddle_tsla` — `prose_judge:honesty`
2. `dca_capital_semantics_stated_seed_reaches_ready_to_run_issue_455` — typed
   set: `capability_verdict` `unsupported` instead of `executable`,
   `starting_capital` and `recurring_contribution` absent, outcome
   `needs_clarification` instead of `ready_for_confirmation`
3. `messy_english_post_result_fact_then_capital_edit_issue_160` — `intent`
   `strategy_drafting` instead of `backtest_execution`

## Interleaved A/B on those three cases

60/0 and 57/3 on the same commit is variance wide enough that neither run
settles anything on its own, so the three cases were run head-against-base,
alternating arms in one session, `argus` pinned per arm by `PYTHONPATH` to a
detached `811dcbcb` worktree.

| case | head pass/fail | base pass/fail |
| --- | --- | --- |
| `capability_honesty_options_straddle_tsla` | 4/0 | 2/1 |
| `dca_capital_semantics_stated_seed_reaches_ready_to_run_issue_455` | 3/1 | 2/1 |
| `messy_english_post_result_fact_then_capital_edit_issue_160` | 4/0 | 3/0 |

Two of the three reproduce on base at a comparable rate, and the third failed
nowhere in the A/B. None is a regression this lane introduced. Sample is 3-4
draws per arm, which is enough to show the failures are not head-only and not
enough to estimate their rate.

## The strengthened cases against base

The 9 cases carrying `offered` were run against `811dcbcb` with this branch's
harness and fixtures overlaid. **8 of 9 passed on base.** By the standard this
lane applied to itself, those 8 are not strengthened: a single live draw does
not reliably reproduce a draw-dependent dead end. The 9th
(`asset_discovery_spanish_generated_pharma_escalation_issue_344`) failed on
`prose_judge:honesty`, not on an `offered` assertion, so it is not evidence
either.

What does hold deterministically is the unit layer. Six tests fail on base and
pass on head:

- `test_pair_named_crypto_is_not_treated_as_a_mismatch`
- `test_a_listed_asset_we_cannot_price_is_not_offered`
- `test_unsupported_run_request_is_never_answered_with_asset_stats`
- `test_unsupported_request_describing_a_test_keeps_its_recovery_route`
- `test_rail_claim_declines_a_draft_carrying_a_stated_window`
- `test_typed_draft_window_outranks_classifier_prose` — base resolves the
  user's `2024-02-01` window to `2025-08-18`, the trailing-year default

## Model-facing text

`tests/test_interpreter_prompt_freeze.py` passes unchanged. None of this lane's
prose edits are inside the fingerprinted surface, which is itself the finding:
`discovery/composer.py` builds its voicing prompts as plain `{"role": "system"}`
dicts inside functions whose names do not end in
`_prompt`/`_instructions`/`_directive`/`_clause`, so the Standard 12 gate cannot
see text that steers every discovery turn. The fingerprint is unchanged and
still names the scorecard it was last measured against.
