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
[`screenshots/issue-345/date-range-cost-continuity-en.png`](screenshots/issue-345/date-range-cost-continuity-en.png).

Automated coverage separately proves that both English and Spanish use the
clarifier response as the assistant prompt and declare
`prompt_source = llm_generated`. When the clarifier is unavailable, the typed
offline path declares `prompt_source = degraded_fallback`.

## Clean-head live-eval comparison

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
