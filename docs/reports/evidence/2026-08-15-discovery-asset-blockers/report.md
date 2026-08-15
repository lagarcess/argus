# Discovery routing and preserved-fact blockers: live measurement evidence

## Identity

- Branch: `claude/discovery-asset-blockers-73dfc5`
- Base: integration after PR #513 (`7138a1ec`)
- Fix commit: `6044f87c`; guidance carve-out: `9409599a`
- Measured SHA: `9409599a6c5f753e5295c561f3811fb181d00e6a` (scorecard provenance `candidate_sha`)
- Baseline: `docs/reports/evidence/2026-08-15-interpreter-prompt-freeze/live-eval-scorecard.json`, 43 passed / 17 failed at `eaf5d52b`
- Command: `ARGUS_RUN_LIVE_EVALS=1 ARGUS_EVAL_ENV_FILE=<live env> ARGUS_MARKET_DATA_PROVIDER_MODE=live_provider pytest tests/evals/test_measurement_eval_live.py`
- Environment: live OpenRouter (`x-ai/grok-4.3` primary, `anthropic/claude-haiku-4.5` fallback, matching render.yaml), live Alpaca asset catalog, live market data.
- No provider credential, key, or account detail is preserved in this report.

## Defect class

One class, three mechanisms, each captured live before the fix: layers after
the primary interpretation discarded information the user had already
supplied.

1. The knowledge answerer's `unsupported_request` shortcut claimed
   correctly-typed unsupported execution asks and voiced the underlying
   asset's statistics as a fabricated result ("A backtest of weekly options
   on Apple ... shows a 32.07% total return"), wiping the draft the
   interpreter audits had just restored. The shortcut is removed; the
   knowledge classifier, whose contract already rules run/build requests
   out, owns that boundary on every turn.
2. A typed unsupported route without a constraint payload dissolved into
   plain chat, discarding the user's asset, window, and benchmark. The
   constraint is now materialized deterministically from the typed fields,
   recorded as `unsupported_request_recovery_materialized`, so the turn
   reaches unsupported recovery with every supported fact intact.
3. The focused repair merge let a degraded re-read (`APPLE`) replace the
   primary's provider-grounded canonical asset (`AAPL`); symbol-mode
   resolution then failed and clarify asked for the asset the user had
   named. Repair asset entries matching a runtime preflight provider record
   now keep the record's canonical symbol, recorded as
   `focused_repair_assets_reconciled_with_provider_context`. Preflight
   records also count as grounding in the asset-suspicion check.

Discovery misrouting (the issue #344 family) is a borderline model
classification, stable within a serving day and flipping across days: all
five cases failed twice at the `eaf5d52b` baseline and passed unmodified in
a pre-fix probe twelve days of serving later. `DISCOVERY_ACT_GUIDANCE` now
names the imperative find/search and current-facts family, including
Argus's own generated chips, with the capability-question carve-out kept
explicit. The prompt freeze extractor also fingerprints module-level
`*_GUIDANCE` string constants and `*_clause` builders, which previously
escaped the frozen surface entirely.

## Measured runs

- Run 1 at `6044f87c`: 51 passed / 9 failed, 24m25s. All 8 target cases
  fixed. Two regressions against baseline:
  `asset_discovery_not_capability_question_issue_244` returned an empty
  `semantic_turn_act` once, and `asset_discovery_peer_anchor_english_issue_244`
  failed only `prose_judge:honesty` on a thin composer lead. The carve-out
  commit `9409599a` addresses the first; both cases then passed 3/3 targeted
  live re-probes with the prose judge on.
- Run 2 at `9409599a`: 52 passed / 8 failed. Both run-1 regressions cleared.
  One new variance regression:
  `dca_capital_semantics_stated_seed_reaches_ready_to_run_issue_455`, where
  the model read "Start with $5,000" as a total budget and the pre-existing
  DCA ceiling audit fired; the failing shape carries the ceiling
  constraint's role-choice options, not this branch's materialized
  constraint, and this branch does not touch DCA money-role text. The case
  passed 3/3 targeted re-probes at the same SHA.
- Run 3 at `9409599a` (this scorecard): **53 passed / 7 failed, zero
  regressions**. $0.91 reported provider cost.

## Case-by-case against the baseline (run 3)

Fixed (10):

- `asset_discovery_recent_ipo_exact_issue_344`
- `asset_discovery_trending_crypto_exact_issue_344`
- `asset_discovery_old_pharma_escalation_exact_issue_344`
- `asset_discovery_semantic_pharma_escalation_issue_344`
- `asset_discovery_spanish_generated_pharma_escalation_issue_344`
- `graceful_recovery_weekly_options_aapl`
- `graceful_recovery_spanish_weekly_options_aapl`
- `messy_english_opening_apple_capital_missing_period_issue_336`
- `compound_benchmark_start_date_preserves_confirmation_issue_339`
- `dca_capital_semantics_zero_contribution_names_buy_and_hold_issue_455`

Regressed: none. All 43 baseline-passing cases pass.

Still failing (7, all failing at baseline, owned by other lanes):

- `action_chip_change_asset_remove_aapl_issue_188`
- `action_chip_change_asset_bare_ticker_append_issue_190`
- `action_chip_change_asset_compound_replace_issue_188`
- `action_chip_change_asset_no_active_ref_remove_aapl_issue_188`
- `action_chip_change_asset_no_active_ref_lost_stage_remove_aapl_issue_188`
- `action_chip_change_asset_no_active_ref_asset_and_date_issue_188`
- `dca_capital_semantics_only_have_amount_is_ceiling_issue_455`

## Compensation observability

Both deterministic layers added by this branch record when they fire, per
the runtime principle that redundancy over an LLM read must be observable:
`unsupported_request_recovery_materialized` and
`focused_repair_assets_reconciled_with_provider_context`.
