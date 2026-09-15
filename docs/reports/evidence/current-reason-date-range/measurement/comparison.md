# Case-by-case historical comparison

Baseline: `docs/reports/evidence/grounded-math/measurement/live-measurement.json` at `dc8608c8a09252ff8c51ef077f32d449bb0b6e8b`, named by the unchanged prompt fingerprint.
Candidate: `c861d95cf0e69003e99d935ffe57c16269e9172b`. The 71 existing fixture definitions are semantically unchanged; two date cases were added.

This is a historical comparison, not a paired causal A/B. The baseline has schema-v2 provenance; the candidate records schema-v3 release configuration. A budget-blocked case is unmeasured, not a product regression or pass.

| Case | Baseline | Candidate | Comparison |
| --- | --- | --- | --- |
| `action_chip_run_visible_confirmation_aapl` | passed | passed | unchanged_pass |
| `action_chip_change_asset_remove_aapl_issue_188` | passed | passed | unchanged_pass |
| `action_chip_change_asset_bare_ticker_append_issue_190` | passed | passed | unchanged_pass |
| `action_chip_change_asset_compound_replace_issue_188` | passed | passed | unchanged_pass |
| `action_chip_change_asset_changed_mind_capital_issue_188` | passed | passed | unchanged_pass |
| `action_chip_change_asset_no_active_ref_remove_aapl_issue_188` | passed | passed | unchanged_pass |
| `action_chip_change_asset_no_active_ref_lost_stage_remove_aapl_issue_188` | passed | passed | unchanged_pass |
| `action_chip_change_asset_no_active_ref_multi_op_issue_188` | passed | passed | unchanged_pass |
| `action_chip_change_asset_no_active_ref_asset_and_date_issue_188` | passed | passed | unchanged_pass |
| `action_chip_change_asset_no_active_ref_fresh_idea_issue_188` | passed | passed | unchanged_pass |
| `natural_language_establishes_modeled_costs_issue_271` | passed | passed | unchanged_pass |
| `action_chip_add_asset_preserves_modeled_costs_issue_271` | passed | passed | unchanged_pass |
| `compound_benchmark_start_date_preserves_confirmation_issue_339` | passed | passed | unchanged_pass |
| `ordinary_turn_edits_owned_confirmation_after_failed_action_issue_272_en` | passed | passed | unchanged_pass |
| `ordinary_turn_edits_owned_confirmation_after_failed_action_issue_272_es` | passed | passed | unchanged_pass |
| `asset_discovery_category_english_issue_244` | passed | passed | unchanged_pass |
| `asset_discovery_peer_anchor_english_issue_244` | passed | passed | unchanged_pass |
| `asset_discovery_comparison_anchor_english_issue_244` | passed | passed | unchanged_pass |
| `asset_discovery_category_spanish_issue_244` | passed | passed | unchanged_pass |
| `asset_discovery_recent_ipo_exact_issue_344` | passed | passed | unchanged_pass |
| `asset_discovery_trending_crypto_exact_issue_344` | passed | passed | unchanged_pass |
| `asset_discovery_old_pharma_escalation_exact_issue_344` | passed | passed | unchanged_pass |
| `asset_discovery_semantic_pharma_escalation_issue_344` | passed | passed | unchanged_pass |
| `asset_discovery_spanish_generated_pharma_escalation_issue_344` | passed | passed | unchanged_pass |
| `asset_discovery_not_direct_backtest_issue_244` | passed | passed | unchanged_pass |
| `asset_discovery_not_result_followup_issue_244` | passed | passed | unchanged_pass |
| `asset_discovery_not_capability_question_issue_244` | passed | passed | unchanged_pass |
| `metric_correctness_eth_default_crypto_benchmark` | passed | passed | unchanged_pass |
| `capability_honesty_options_straddle_tsla` | passed | passed | unchanged_pass |
| `capability_honesty_golden_cross_control_aapl` | passed | passed | unchanged_pass |
| `capability_honesty_momentum_breakout_aapl` | passed | passed | unchanged_pass |
| `capability_honesty_news_sentiment_rule_aapl` | passed | passed | unchanged_pass |
| `capability_honesty_future_performance_nvda_golden_cross` | failed | unmeasured (budget guard) | unmeasured_budget_guard |
| `capability_honesty_future_performance_btc_regression` | passed | unmeasured (budget guard) | unmeasured_budget_guard |
| `dca_capital_semantics_start_by_phrase_is_contribution_issue_455` | passed | passed | unchanged_pass |
| `dca_capital_semantics_missing_contribution_asks_amount_issue_455` | passed | passed | unchanged_pass |
| `dca_capital_semantics_only_have_amount_is_ceiling_issue_455` | passed | passed | unchanged_pass |
| `dca_capital_semantics_explicit_cap_refused_by_name_issue_455` | passed | passed | unchanged_pass |
| `dca_capital_semantics_stated_seed_reaches_ready_to_run_issue_455` | passed | passed | unchanged_pass |
| `dca_capital_semantics_zero_seed_small_contribution_executable_issue_455` | passed | passed | unchanged_pass |
| `dca_capital_semantics_period_exceeds_window_named_refusal_issue_455` | passed | passed | unchanged_pass |
| `dca_capital_semantics_zero_contribution_names_buy_and_hold_issue_455` | passed | passed | unchanged_pass |
| `dca_capital_semantics_calendar_alignment_keeps_period_fit_issue_455` | passed | passed | unchanged_pass |
| `dca_capital_semantics_multi_symbol_equal_weight_issue_455` | passed | passed | unchanged_pass |
| `dca_capital_semantics_crypto_weekly_btc_issue_455` | passed | passed | unchanged_pass |
| `dca_capital_semantics_truncated_window_measures_served_issue_455` | passed | passed | unchanged_pass |
| `dca_capital_semantics_spanish_seed_and_contribution_issue_455` | passed | passed | unchanged_pass |
| `dca_capital_semantics_spanish_period_exceeds_window_issue_455` | passed | passed | unchanged_pass |
| `dca_capital_semantics_prebaked_chip_bare_amount_reaches_ready_to_run` | passed | passed | unchanged_pass |
| `dca_capital_semantics_prebaked_chip_spanish_pesos_reaches_ready_to_run` | passed | passed | unchanged_pass |
| `dca_capital_semantics_clarification_reply_keeps_earlier_facts_2026_09_10` | passed | passed | unchanged_pass |
| `dca_capital_semantics_clarification_reply_keeps_earlier_facts_spanish_2026_09_10` | passed | passed | unchanged_pass |
| `graceful_recovery_weekly_options_aapl` | passed | passed | unchanged_pass |
| `graceful_recovery_spanish_weekly_options_aapl` | passed | passed | unchanged_pass |
| `graceful_recovery_spanish_offline_clarifier_missing_period_aapl` | passed | passed | unchanged_pass |
| `messy_english_opening_apple_capital_missing_period_issue_336` | passed | passed | unchanged_pass |
| `messy_english_aapl_simple_hold_2024` | passed | passed | unchanged_pass |
| `messy_english_company_name_multi_asset_issue_142` | passed | passed | unchanged_pass |
| `messy_english_complete_sma_crossover_benchmark_issue_270` | passed | passed | unchanged_pass |
| `messy_english_post_result_fact_then_capital_edit_issue_160` | passed | passed | unchanged_pass |
| `messy_english_explicit_end_survives_year_qualifier` | new | failed | new_failure |
| `messy_spanish_btc_hold_q1_2024` | passed | passed | unchanged_pass |
| `messy_spanish_post_result_fact_then_capital_edit_issue_160` | passed | passed | unchanged_pass |
| `messy_spanish_future_performance_nvda_cruce_dorado` | failed | failed | changed_failure |
| `messy_spanish_explicit_end_survives_year_qualifier` | new | failed | new_failure |
| `ordinary_conversation_concept_compound_interest_en` | passed | unmeasured (budget guard) | unmeasured_budget_guard |
| `ordinary_conversation_concept_inflation_es` | passed | unmeasured (budget guard) | unmeasured_budget_guard |
| `ordinary_conversation_concept_etf_es` | passed | unmeasured (budget guard) | unmeasured_budget_guard |
| `ordinary_conversation_capability_indicator_question_en` | passed | passed | unchanged_pass |
| `ordinary_conversation_capability_indicator_question_es` | passed | passed | unchanged_pass |
| `ordinary_conversation_macro_curiosity_en` | passed | passed | unchanged_pass |
| `ordinary_conversation_price_question_en` | passed | unmeasured (budget guard) | unmeasured_budget_guard |
| `spanish_ui_english_user_msft_hold_h1_2024` | passed | passed | unchanged_pass |

## Checks for every non-passing candidate case

### `capability_honesty_future_performance_nvda_golden_cross`

Baseline failed checks:

- intent: expected one of ['conversation_followup', 'beginner_guidance'], got 'backtest_execution'
- capability_verdict: expected 'answer_only', got 'unsupported'
- stage_outcomes: expected ['ready_to_respond'], got ['needs_clarification', 'await_user_reply']
- offered.min_next_experiment_rows: expected at least 1, got []
- research: expected a research sidecar, got None

Candidate failed checks:

- None evaluated: stopped before Agent dispatch. This is missing evidence.

New failed checks relative to the baseline:

- None recorded; this does not turn an unmeasured case into a pass.

### `capability_honesty_future_performance_btc_regression`

Baseline failed checks:

- None (new or previously passing).

Candidate failed checks:

- None evaluated: stopped before Agent dispatch. This is missing evidence.

New failed checks relative to the baseline:

- None recorded; this does not turn an unmeasured case into a pass.

### `messy_english_explicit_end_survives_year_qualifier`

Baseline failed checks:

- None (new or previously passing).

Candidate failed checks:

- capability_verdict: expected 'executable', got 'needs_clarification'
- stage_outcomes: expected ['ready_for_confirmation', 'await_approval'], got ['needs_clarification', 'await_user_reply']
- offered.launch_payload: no launch reached the turn

New failed checks relative to the baseline:

- capability_verdict: expected 'executable', got 'needs_clarification'
- offered.launch_payload: no launch reached the turn
- stage_outcomes: expected ['ready_for_confirmation', 'await_approval'], got ['needs_clarification', 'await_user_reply']

### `messy_spanish_future_performance_nvda_cruce_dorado`

Baseline failed checks:

- research.published: expected True, got False
- prose_judge:scenario_framing

Candidate failed checks:

- intent: expected one of ['conversation_followup', 'beginner_guidance'], got 'backtest_execution'
- capability_verdict: expected 'answer_only', got 'unsupported'
- stage_outcomes: expected ['ready_to_respond'], got ['needs_clarification', 'await_user_reply']
- offered.min_next_experiment_rows: expected at least 1, got []
- research: expected a research sidecar, got None

New failed checks relative to the baseline:

- capability_verdict: expected 'answer_only', got 'unsupported'
- intent: expected one of ['conversation_followup', 'beginner_guidance'], got 'backtest_execution'
- offered.min_next_experiment_rows: expected at least 1, got []
- research: expected a research sidecar, got None
- stage_outcomes: expected ['ready_to_respond'], got ['needs_clarification', 'await_user_reply']

### `messy_spanish_explicit_end_survives_year_qualifier`

Baseline failed checks:

- None (new or previously passing).

Candidate failed checks:

- offered.launch_payload.date_range: expected {'start': '2026-08-16', 'end': '2026-08-19'}, got {'start': '2026-08-17', 'end': '2026-08-19'}
- prose_judge:missing_assistant_text

New failed checks relative to the baseline:

- offered.launch_payload.date_range: expected {'start': '2026-08-16', 'end': '2026-08-19'}, got {'start': '2026-08-17', 'end': '2026-08-19'}
- prose_judge:missing_assistant_text

### `ordinary_conversation_concept_compound_interest_en`

Baseline failed checks:

- None (new or previously passing).

Candidate failed checks:

- None evaluated: stopped before Agent dispatch. This is missing evidence.

New failed checks relative to the baseline:

- None recorded; this does not turn an unmeasured case into a pass.

### `ordinary_conversation_concept_inflation_es`

Baseline failed checks:

- None (new or previously passing).

Candidate failed checks:

- None evaluated: stopped before Agent dispatch. This is missing evidence.

New failed checks relative to the baseline:

- None recorded; this does not turn an unmeasured case into a pass.

### `ordinary_conversation_concept_etf_es`

Baseline failed checks:

- None (new or previously passing).

Candidate failed checks:

- None evaluated: stopped before Agent dispatch. This is missing evidence.

New failed checks relative to the baseline:

- None recorded; this does not turn an unmeasured case into a pass.

### `ordinary_conversation_price_question_en`

Baseline failed checks:

- None (new or previously passing).

Candidate failed checks:

- None evaluated: stopped before Agent dispatch. This is missing evidence.

New failed checks relative to the baseline:

- None recorded; this does not turn an unmeasured case into a pass.
