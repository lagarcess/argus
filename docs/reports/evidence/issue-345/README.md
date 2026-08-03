# Issue 345 evidence

## Model-voiced date clarification

On 2026-08-02, local real-API browser QA exercised the full result follow-up
path with a live OpenRouter clarifier, synthetic market data, and in-memory
persistence. Argus asked:

> What date range would you like to test instead?

The persisted assistant-message metadata declared:

```json
{
  "kind": "clarification",
  "prompt_source": "llm_generated",
  "requested_field": "date_range",
  "requested_fields": ["date_range"]
}
```

After the user supplied January 3 through December 29, 2023, the new
confirmation preserved AAPL, the $1,000 weekly contribution, daily data, SPY,
the 40 bps fee, and 0.25 bps slippage. See
[`date-range-cost-continuity-en.png`](date-range-cost-continuity-en.png).

Automated coverage separately proves that both English and Spanish use the
clarifier response as the assistant prompt and declare
`prompt_source = llm_generated`. When the clarifier is unavailable, the typed
offline path declares `prompt_source = degraded_fallback`.

The Spanish buy-and-hold recommendation continuity capture is
[`buy-and-hold-continuity-es.png`](buy-and-hold-continuity-es.png).

## Reconciled browser revalidation

On 2026-08-03, browser QA repeated the complete English path after merging
`origin/codex/private-alpha-next` and applying the clarified-date repair at code
commit `5691eb10`. The live clarifier again persisted
`prompt_source = llm_generated` and `requested_field = date_range`. The first
answer attempt ended in an honest recoverable failure when every configured
interpretation candidate failed; the durable Retry replayed the same request
and produced the corrected confirmation.

The final confirmation used January 3 through December 29, 2023 while
preserving the non-buy-and-hold DCA contract: AAPL,
`recurring_contribution = 1000`, `cadence = weekly`, daily data, SPY, the 40 bps
fee, and 0.25 bps slippage. The rendered confirmation visibly labels the
amount as **CONTRIBUTION** and the cadence as **Weekly**. Its typed patch metadata declared
`source = user_patch` with only `date_range` in `changed_fields`. See
[`date-range-cost-continuity-en-exact-head.png`](date-range-cost-continuity-en-exact-head.png).

Targeted regressions additionally assert that the source-result adapter keeps
the DCA contribution as a typed `recurring_contribution` with prior-artifact
provenance through both the recommendation clarification and the refined
confirmation. A separate indicator-driven regression carries a 50/200 SMA
crossover's `entry_rule`, `exit_rule`, and `rule_spec` through the same
date-range recommendation/refine path.

## Final-head DCA browser revalidation

On 2026-08-03, local real-API browser QA repeated the complete non-buy-and-hold
journey at code head `731730aa`. The source run was a weekly AAPL DCA strategy
with an explicit `recurring_contribution = 1000`. Selecting **Test a different
date range** produced a model-voiced clarification whose persisted metadata
declared `prompt_source = llm_generated` and `requested_field = date_range`.
The pending strategy retained:

- `strategy_type = dca_accumulation`
- `recurring_contribution = 1000` with `prior` provenance
- `cadence = weekly` with `prior` provenance
- daily data, SPY, a 40 bps fee, and 0.25 bps slippage

After the user supplied January 3 through December 29, 2023, the final
confirmation retained every field above. Its typed artifact patch declared
`source = user_patch` and `changed_fields = ["date_range"]`. The viewport
capture visibly shows **CONTRIBUTION $1,000**, **Cadence Weekly**, the refined
dates, costs, daily data, and SPY:
[`date-range-dca-continuity-exact-head-731730aa.png`](date-range-dca-continuity-exact-head-731730aa.png).

## Historical blocked-run comparison

This record explains why PR #359 correctly remained Draft before issue #361's
live-eval environment repair landed. It is historical failure evidence, not the
readiness scorecard. Readiness requires a new full live suite on the reconciled
exact head with no waiver; that scorecard is attached durably to PR #359 after
the run so recording it does not move the evaluated Git head.

Both runs used the identical command and canonical linked `.env` topology on
Python 3.10.20:

```bash
ARGUS_RUN_LIVE_EVALS=1 ARGUS_EVAL_ENV_FILE=.env \
poetry run pytest tests/evals/test_measurement_eval_live.py -q --no-cov
```

| Run | Git SHA | Scorecard generated | Totals | Raw scorecard SHA-256 |
| --- | --- | --- | --- | --- |
| Issue 345 candidate | `5a8fba7a5cac5fce7fbec79232faa6f6ae4629b1` | `2026-08-02T11:47:21.575433+00:00` | 22 passed, 17 failed | `53c71f1a9d39670969dda0b68518b15b7e3770057a03a1fd114cfefe0c9478dc` |
| Clean detached `codex/private-alpha-next` | `6533377c1a08539136a622a7d53eee20d0efd845` | `2026-08-02T13:30:49.209215+00:00` | 22 passed, 17 failed | `b4001dfbdbecb1d74fa4db2d6d5fe627a01d78310c6028a47aef30474d05e651` |

The clean comparison worktree had no tracked or untracked Git changes before or
after the run. For each scorecard, the blocking records were normalized to
sorted `{id, category, failed_checks}` objects. Both normalized outputs have
the same SHA-256:

```text
b9d48e7ba345358ff37fdf5912bd5c979ab7f258b29b069ca75bcce025d2e30f
```

Therefore, all 17 failing case ids and their failed checks match exactly:

1. `action_chip_change_asset_bare_ticker_append_issue_190`
2. `action_chip_change_asset_changed_mind_capital_issue_188`
3. `action_chip_change_asset_compound_replace_issue_188`
4. `action_chip_change_asset_no_active_ref_asset_and_date_issue_188`
5. `action_chip_change_asset_no_active_ref_fresh_idea_issue_188`
6. `action_chip_change_asset_no_active_ref_lost_stage_remove_aapl_issue_188`
7. `action_chip_change_asset_no_active_ref_multi_op_issue_188`
8. `action_chip_change_asset_no_active_ref_remove_aapl_issue_188`
9. `action_chip_change_asset_remove_aapl_issue_188`
10. `asset_discovery_not_direct_backtest_issue_244`
11. `capability_honesty_golden_cross_control_aapl`
12. `messy_english_aapl_simple_hold_2024`
13. `messy_english_company_name_multi_asset_issue_142`
14. `messy_english_post_result_fact_then_capital_edit_issue_160`
15. `ordinary_turn_edits_owned_confirmation_after_failed_action_issue_272_en`
16. `ordinary_turn_edits_owned_confirmation_after_failed_action_issue_272_es`
17. `spanish_ui_english_user_msft_hold_h1_2024`

Every failed check is an effective-date/calendar-alignment mismatch: the
expected trading-calendar-adjusted range was returned as the unadjusted date
range, and `adjustment_reason` was `none` instead of `calendar_alignment`.
This comparison proves those 17 failures are present on the clean integration
head; it does not waive the standing live-eval gate or make this Draft ready.
