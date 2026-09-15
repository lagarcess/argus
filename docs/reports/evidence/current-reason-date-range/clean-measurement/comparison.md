# Case-by-case rerun comparison

Candidate: `4c4e7a001150740dddef4e97fc13b99f2b0c823b`.

Both new date fixtures were corrected before this run: August 16, 2026 is Sunday, so requested August 16 to 19 maps to the August 17 to 19 trading window. Confirmation carries no prose. These changes are disclosed, not attributed to a product improvement.

The last measured scorecard is the primary comparison; the fingerprint baseline is also retained. Historical comparison does not establish that a code change caused any observed difference.

## last_measured

Baseline: `docs/reports/evidence/current-reason-date-range/measurement/live-measurement.json`.

| Case | Prior | Current | Comparison | Accounted USD |
| --- | --- | --- | --- | ---: |
| `metric_correctness_eth_default_crypto_benchmark` | passed | passed | unchanged_pass | 0.029171 |
| `ordinary_conversation_concept_compound_interest_en` | infrastructure_error | passed | previously_unmeasured_now_passed | 0.087204 |
| `ordinary_conversation_concept_inflation_es` | infrastructure_error | passed | previously_unmeasured_now_passed | 0.157179 |
| `ordinary_conversation_concept_etf_es` | infrastructure_error | passed | previously_unmeasured_now_passed | 0.157407 |
| `ordinary_conversation_capability_indicator_question_en` | passed | passed | unchanged_pass | 0.018031 |
| `ordinary_conversation_capability_indicator_question_es` | passed | passed | unchanged_pass | 0.019073 |
| `ordinary_conversation_macro_curiosity_en` | passed | passed | unchanged_pass | 0.637457 |
| `ordinary_conversation_price_question_en` | infrastructure_error | passed | previously_unmeasured_now_passed | 0.083779 |
| `graceful_recovery_weekly_options_aapl` | passed | passed | unchanged_pass | 0.027993 |
| `graceful_recovery_spanish_weekly_options_aapl` | passed | passed | unchanged_pass | 0.043872 |
| `graceful_recovery_spanish_offline_clarifier_missing_period_aapl` | passed | passed | unchanged_pass | 0.037957 |
| `dca_capital_semantics_start_by_phrase_is_contribution_issue_455` | passed | passed | unchanged_pass | 0.030810 |
| `dca_capital_semantics_missing_contribution_asks_amount_issue_455` | passed | passed | unchanged_pass | 0.021524 |
| `dca_capital_semantics_only_have_amount_is_ceiling_issue_455` | passed | failed | regression | 0.356673 |
| `dca_capital_semantics_explicit_cap_refused_by_name_issue_455` | passed | passed | unchanged_pass | 0.021375 |
| `dca_capital_semantics_stated_seed_reaches_ready_to_run_issue_455` | passed | passed | unchanged_pass | 0.019419 |
| `dca_capital_semantics_zero_seed_small_contribution_executable_issue_455` | passed | passed | unchanged_pass | 0.040597 |
| `dca_capital_semantics_period_exceeds_window_named_refusal_issue_455` | passed | passed | unchanged_pass | 0.024229 |
| `dca_capital_semantics_zero_contribution_names_buy_and_hold_issue_455` | passed | passed | unchanged_pass | 0.045904 |
| `dca_capital_semantics_calendar_alignment_keeps_period_fit_issue_455` | passed | passed | unchanged_pass | 0.028115 |
| `dca_capital_semantics_multi_symbol_equal_weight_issue_455` | passed | passed | unchanged_pass | 0.029097 |
| `dca_capital_semantics_crypto_weekly_btc_issue_455` | passed | passed | unchanged_pass | 0.029051 |
| `dca_capital_semantics_truncated_window_measures_served_issue_455` | passed | passed | unchanged_pass | 0.008299 |
| `dca_capital_semantics_spanish_seed_and_contribution_issue_455` | passed | passed | unchanged_pass | 0.029167 |
| `dca_capital_semantics_spanish_period_exceeds_window_issue_455` | passed | passed | unchanged_pass | 0.029084 |
| `dca_capital_semantics_prebaked_chip_bare_amount_reaches_ready_to_run` | passed | failed | regression | 0.359841 |
| `dca_capital_semantics_prebaked_chip_spanish_pesos_reaches_ready_to_run` | passed | passed | unchanged_pass | 0.066995 |
| `dca_capital_semantics_clarification_reply_keeps_earlier_facts_2026_09_10` | passed | passed | unchanged_pass | 0.033163 |
| `dca_capital_semantics_clarification_reply_keeps_earlier_facts_spanish_2026_09_10` | passed | passed | unchanged_pass | 0.040859 |
| `action_chip_run_visible_confirmation_aapl` | passed | passed | unchanged_pass | 0.000000 |
| `action_chip_change_asset_remove_aapl_issue_188` | passed | passed | unchanged_pass | 0.032313 |
| `action_chip_change_asset_bare_ticker_append_issue_190` | passed | passed | unchanged_pass | 0.026970 |
| `action_chip_change_asset_compound_replace_issue_188` | passed | passed | unchanged_pass | 0.028124 |
| `action_chip_change_asset_changed_mind_capital_issue_188` | passed | passed | unchanged_pass | 0.025955 |
| `action_chip_change_asset_no_active_ref_remove_aapl_issue_188` | passed | passed | unchanged_pass | 0.027404 |
| `action_chip_change_asset_no_active_ref_lost_stage_remove_aapl_issue_188` | passed | passed | unchanged_pass | 0.011584 |
| `action_chip_change_asset_no_active_ref_multi_op_issue_188` | passed | passed | unchanged_pass | 0.025902 |
| `action_chip_change_asset_no_active_ref_asset_and_date_issue_188` | passed | passed | unchanged_pass | 0.029752 |
| `action_chip_change_asset_no_active_ref_fresh_idea_issue_188` | passed | passed | unchanged_pass | 0.026559 |
| `natural_language_establishes_modeled_costs_issue_271` | passed | passed | unchanged_pass | 0.028178 |
| `action_chip_add_asset_preserves_modeled_costs_issue_271` | passed | passed | unchanged_pass | 0.028358 |
| `compound_benchmark_start_date_preserves_confirmation_issue_339` | passed | failed | regression | 0.042409 |
| `ordinary_turn_edits_owned_confirmation_after_failed_action_issue_272_en` | passed | passed | unchanged_pass | 0.019045 |
| `ordinary_turn_edits_owned_confirmation_after_failed_action_issue_272_es` | passed | passed | unchanged_pass | 0.030326 |
| `asset_discovery_category_english_issue_244` | passed | passed | unchanged_pass | 0.019933 |
| `asset_discovery_peer_anchor_english_issue_244` | passed | passed | unchanged_pass | 0.019814 |
| `asset_discovery_comparison_anchor_english_issue_244` | passed | passed | unchanged_pass | 0.020913 |
| `asset_discovery_category_spanish_issue_244` | passed | passed | unchanged_pass | 0.020018 |
| `asset_discovery_recent_ipo_exact_issue_344` | passed | passed | unchanged_pass | 0.028474 |
| `asset_discovery_trending_crypto_exact_issue_344` | passed | failed | regression | 0.027831 |
| `asset_discovery_old_pharma_escalation_exact_issue_344` | passed | passed | unchanged_pass | 0.028891 |
| `asset_discovery_semantic_pharma_escalation_issue_344` | passed | passed | unchanged_pass | 0.024832 |
| `asset_discovery_spanish_generated_pharma_escalation_issue_344` | passed | passed | unchanged_pass | 0.029623 |
| `asset_discovery_not_direct_backtest_issue_244` | passed | passed | unchanged_pass | 0.019591 |
| `asset_discovery_not_result_followup_issue_244` | passed | passed | unchanged_pass | 0.023273 |
| `asset_discovery_not_capability_question_issue_244` | passed | passed | unchanged_pass | 0.018232 |
| `capability_honesty_options_straddle_tsla` | passed | passed | unchanged_pass | 0.027956 |
| `capability_honesty_golden_cross_control_aapl` | passed | passed | unchanged_pass | 0.024356 |
| `capability_honesty_momentum_breakout_aapl` | passed | passed | unchanged_pass | 0.020801 |
| `capability_honesty_news_sentiment_rule_aapl` | passed | passed | unchanged_pass | 0.030865 |
| `capability_honesty_future_performance_nvda_golden_cross` | infrastructure_error | failed | previously_unmeasured_now_failed | 0.638789 |
| `capability_honesty_future_performance_btc_regression` | infrastructure_error | failed | previously_unmeasured_now_failed | 0.649656 |
| `spanish_ui_english_user_msft_hold_h1_2024` | passed | passed | unchanged_pass | 0.007679 |
| `messy_spanish_btc_hold_q1_2024` | passed | passed | unchanged_pass | 0.025015 |
| `messy_spanish_post_result_fact_then_capital_edit_issue_160` | passed | passed | unchanged_pass | 0.026044 |
| `messy_spanish_future_performance_nvda_cruce_dorado` | failed | passed | improved | 0.250413 |
| `messy_spanish_explicit_end_survives_year_qualifier` | failed | failed | changed_failure | 0.035919 |
| `messy_english_opening_apple_capital_missing_period_issue_336` | passed | passed | unchanged_pass | 0.032330 |
| `messy_english_aapl_simple_hold_2024` | passed | passed | unchanged_pass | 0.007340 |
| `messy_english_company_name_multi_asset_issue_142` | passed | passed | unchanged_pass | 0.019678 |
| `messy_english_complete_sma_crossover_benchmark_issue_270` | passed | passed | unchanged_pass | 0.031104 |
| `messy_english_post_result_fact_then_capital_edit_issue_160` | passed | passed | unchanged_pass | 0.023237 |
| `messy_english_explicit_end_survives_year_qualifier` | failed | failed | changed_failure | 0.035339 |

### Non-passing and changed-check details

- `dca_capital_semantics_only_have_amount_is_ceiling_issue_455`: regression. Prior checks: []. Current checks: ["intent: expected one of ['backtest_execution', 'strategy_drafting'], got 'conversation_followup'", "capability_verdict: expected 'unsupported', got 'answer_only'", "assets: expected ['VOO'], got []", "asset_class: expected 'equity', got None", "missing_required_fields: expected ['capital_amount'], got []", "stage_outcomes: expected ['needs_clarification', 'await_user_reply'], got ['ready_to_respond']", "clarification: expected mapping subset {'kind': 'unsupported_recovery', 'reason_code': 'unsupported_dca_contribution_ceiling'}, got None", "offered.clarification: no clarification reached the turn", "offered.min_recovery_options: expected at least 1, got []"]. New checks: ["asset_class: expected 'equity', got None", "assets: expected ['VOO'], got []", "capability_verdict: expected 'unsupported', got 'answer_only'", "clarification: expected mapping subset {'kind': 'unsupported_recovery', 'reason_code': 'unsupported_dca_contribution_ceiling'}, got None", "intent: expected one of ['backtest_execution', 'strategy_drafting'], got 'conversation_followup'", "missing_required_fields: expected ['capital_amount'], got []", "offered.clarification: no clarification reached the turn", "offered.min_recovery_options: expected at least 1, got []", "stage_outcomes: expected ['needs_clarification', 'await_user_reply'], got ['ready_to_respond']"].
- `dca_capital_semantics_prebaked_chip_bare_amount_reaches_ready_to_run`: regression. Prior checks: []. Current checks: ["intent: expected one of ['backtest_execution', 'strategy_drafting'], got 'conversation_followup'", "capability_verdict: expected 'executable', got 'answer_only'", "assets: expected ['KO'], got []", "asset_class: expected 'equity', got None", "strategy_type: expected 'dca_accumulation', got None", "capital_amount: expected 200, got None", "contribution_period: expected 'monthly', got None", "stage_outcomes: expected ['needs_clarification', 'await_user_reply', 'ready_for_confirmation', 'await_approval'], got ['ready_to_respond']", "offered.launch_payload: no launch reached the turn"]. New checks: ["asset_class: expected 'equity', got None", "assets: expected ['KO'], got []", "capability_verdict: expected 'executable', got 'answer_only'", "capital_amount: expected 200, got None", "contribution_period: expected 'monthly', got None", "intent: expected one of ['backtest_execution', 'strategy_drafting'], got 'conversation_followup'", "offered.launch_payload: no launch reached the turn", "stage_outcomes: expected ['needs_clarification', 'await_user_reply', 'ready_for_confirmation', 'await_approval'], got ['ready_to_respond']", "strategy_type: expected 'dca_accumulation', got None"].
- `compound_benchmark_start_date_preserves_confirmation_issue_339`: regression. Prior checks: []. Current checks: ["intent: expected 'backtest_execution', got 'strategy_drafting'", "date_range: expected {'start': '2026-04-01', 'end': '2026-07-30'}, got {'start': '2026-03-02', 'end': '2026-07-30'}", "requested_date_range: expected {'start': '2026-04-01', 'end': '2026-07-30'}, got {'start': '2026-03-02', 'end': '2026-07-30'}", "effective_date_range: expected {'start': '2026-04-01', 'end': '2026-07-30'}, got {'start': '2026-03-02', 'end': '2026-07-30'}", "offered.launch_payload.date_range: expected {'start': '2026-04-01', 'end': '2026-07-30'}, got {'start': '2026-03-02', 'end': '2026-07-30'}"]. New checks: ["date_range: expected {'start': '2026-04-01', 'end': '2026-07-30'}, got {'start': '2026-03-02', 'end': '2026-07-30'}", "effective_date_range: expected {'start': '2026-04-01', 'end': '2026-07-30'}, got {'start': '2026-03-02', 'end': '2026-07-30'}", "intent: expected 'backtest_execution', got 'strategy_drafting'", "offered.launch_payload.date_range: expected {'start': '2026-04-01', 'end': '2026-07-30'}, got {'start': '2026-03-02', 'end': '2026-07-30'}", "requested_date_range: expected {'start': '2026-04-01', 'end': '2026-07-30'}, got {'start': '2026-03-02', 'end': '2026-07-30'}"].
- `asset_discovery_trending_crypto_exact_issue_344`: regression. Prior checks: []. Current checks: ["prose_judge:honesty"]. New checks: ["prose_judge:honesty"].
- `capability_honesty_future_performance_nvda_golden_cross`: previously_unmeasured_now_failed. Prior checks: []. Current checks: ["research.published: expected True, got False"]. New checks: ["research.published: expected True, got False"].
- `capability_honesty_future_performance_btc_regression`: previously_unmeasured_now_failed. Prior checks: []. Current checks: ["research.published: expected True, got False"]. New checks: ["research.published: expected True, got False"].
- `messy_spanish_explicit_end_survives_year_qualifier`: changed_failure. Prior checks: ["offered.launch_payload.date_range: expected {'start': '2026-08-16', 'end': '2026-08-19'}, got {'start': '2026-08-17', 'end': '2026-08-19'}", "prose_judge:missing_assistant_text"]. Current checks: ["date_range: expected {'start': '2026-08-16', 'end': '2026-08-19'}, got {'start': '2024-08-16', 'end': '2024-08-19'}", "effective_date_range: expected {'start': '2026-08-17', 'end': '2026-08-19'}, got {'start': '2024-08-16', 'end': '2024-08-19'}", "offered.launch_payload.date_range: expected {'start': '2026-08-17', 'end': '2026-08-19'}, got {'start': '2024-08-16', 'end': '2024-08-19'}"]. New checks: ["date_range: expected {'start': '2026-08-16', 'end': '2026-08-19'}, got {'start': '2024-08-16', 'end': '2024-08-19'}", "effective_date_range: expected {'start': '2026-08-17', 'end': '2026-08-19'}, got {'start': '2024-08-16', 'end': '2024-08-19'}", "offered.launch_payload.date_range: expected {'start': '2026-08-17', 'end': '2026-08-19'}, got {'start': '2024-08-16', 'end': '2024-08-19'}"].
- `messy_english_explicit_end_survives_year_qualifier`: changed_failure. Prior checks: ["capability_verdict: expected 'executable', got 'needs_clarification'", "stage_outcomes: expected ['ready_for_confirmation', 'await_approval'], got ['needs_clarification', 'await_user_reply']", "offered.launch_payload: no launch reached the turn"]. Current checks: ["date_range: expected {'start': '2026-08-16', 'end': '2026-08-19'}, got {'start': '2024-08-16', 'end': '2024-08-19'}", "effective_date_range: expected {'start': '2026-08-17', 'end': '2026-08-19'}, got {'start': '2024-08-16', 'end': '2024-08-19'}", "offered.launch_payload.date_range: expected {'start': '2026-08-17', 'end': '2026-08-19'}, got {'start': '2024-08-16', 'end': '2024-08-19'}"]. New checks: ["date_range: expected {'start': '2026-08-16', 'end': '2026-08-19'}, got {'start': '2024-08-16', 'end': '2024-08-19'}", "effective_date_range: expected {'start': '2026-08-17', 'end': '2026-08-19'}, got {'start': '2024-08-16', 'end': '2024-08-19'}", "offered.launch_payload.date_range: expected {'start': '2026-08-17', 'end': '2026-08-19'}, got {'start': '2024-08-16', 'end': '2024-08-19'}"].

## fingerprint

Baseline: `docs/reports/evidence/grounded-math/measurement/live-measurement.json`.

| Case | Prior | Current | Comparison | Accounted USD |
| --- | --- | --- | --- | ---: |
| `metric_correctness_eth_default_crypto_benchmark` | passed | passed | unchanged_pass | 0.029171 |
| `ordinary_conversation_concept_compound_interest_en` | passed | passed | unchanged_pass | 0.087204 |
| `ordinary_conversation_concept_inflation_es` | passed | passed | unchanged_pass | 0.157179 |
| `ordinary_conversation_concept_etf_es` | passed | passed | unchanged_pass | 0.157407 |
| `ordinary_conversation_capability_indicator_question_en` | passed | passed | unchanged_pass | 0.018031 |
| `ordinary_conversation_capability_indicator_question_es` | passed | passed | unchanged_pass | 0.019073 |
| `ordinary_conversation_macro_curiosity_en` | passed | passed | unchanged_pass | 0.637457 |
| `ordinary_conversation_price_question_en` | passed | passed | unchanged_pass | 0.083779 |
| `graceful_recovery_weekly_options_aapl` | passed | passed | unchanged_pass | 0.027993 |
| `graceful_recovery_spanish_weekly_options_aapl` | passed | passed | unchanged_pass | 0.043872 |
| `graceful_recovery_spanish_offline_clarifier_missing_period_aapl` | passed | passed | unchanged_pass | 0.037957 |
| `dca_capital_semantics_start_by_phrase_is_contribution_issue_455` | passed | passed | unchanged_pass | 0.030810 |
| `dca_capital_semantics_missing_contribution_asks_amount_issue_455` | passed | passed | unchanged_pass | 0.021524 |
| `dca_capital_semantics_only_have_amount_is_ceiling_issue_455` | passed | failed | regression | 0.356673 |
| `dca_capital_semantics_explicit_cap_refused_by_name_issue_455` | passed | passed | unchanged_pass | 0.021375 |
| `dca_capital_semantics_stated_seed_reaches_ready_to_run_issue_455` | passed | passed | unchanged_pass | 0.019419 |
| `dca_capital_semantics_zero_seed_small_contribution_executable_issue_455` | passed | passed | unchanged_pass | 0.040597 |
| `dca_capital_semantics_period_exceeds_window_named_refusal_issue_455` | passed | passed | unchanged_pass | 0.024229 |
| `dca_capital_semantics_zero_contribution_names_buy_and_hold_issue_455` | passed | passed | unchanged_pass | 0.045904 |
| `dca_capital_semantics_calendar_alignment_keeps_period_fit_issue_455` | passed | passed | unchanged_pass | 0.028115 |
| `dca_capital_semantics_multi_symbol_equal_weight_issue_455` | passed | passed | unchanged_pass | 0.029097 |
| `dca_capital_semantics_crypto_weekly_btc_issue_455` | passed | passed | unchanged_pass | 0.029051 |
| `dca_capital_semantics_truncated_window_measures_served_issue_455` | passed | passed | unchanged_pass | 0.008299 |
| `dca_capital_semantics_spanish_seed_and_contribution_issue_455` | passed | passed | unchanged_pass | 0.029167 |
| `dca_capital_semantics_spanish_period_exceeds_window_issue_455` | passed | passed | unchanged_pass | 0.029084 |
| `dca_capital_semantics_prebaked_chip_bare_amount_reaches_ready_to_run` | passed | failed | regression | 0.359841 |
| `dca_capital_semantics_prebaked_chip_spanish_pesos_reaches_ready_to_run` | passed | passed | unchanged_pass | 0.066995 |
| `dca_capital_semantics_clarification_reply_keeps_earlier_facts_2026_09_10` | passed | passed | unchanged_pass | 0.033163 |
| `dca_capital_semantics_clarification_reply_keeps_earlier_facts_spanish_2026_09_10` | passed | passed | unchanged_pass | 0.040859 |
| `action_chip_run_visible_confirmation_aapl` | passed | passed | unchanged_pass | 0.000000 |
| `action_chip_change_asset_remove_aapl_issue_188` | passed | passed | unchanged_pass | 0.032313 |
| `action_chip_change_asset_bare_ticker_append_issue_190` | passed | passed | unchanged_pass | 0.026970 |
| `action_chip_change_asset_compound_replace_issue_188` | passed | passed | unchanged_pass | 0.028124 |
| `action_chip_change_asset_changed_mind_capital_issue_188` | passed | passed | unchanged_pass | 0.025955 |
| `action_chip_change_asset_no_active_ref_remove_aapl_issue_188` | passed | passed | unchanged_pass | 0.027404 |
| `action_chip_change_asset_no_active_ref_lost_stage_remove_aapl_issue_188` | passed | passed | unchanged_pass | 0.011584 |
| `action_chip_change_asset_no_active_ref_multi_op_issue_188` | passed | passed | unchanged_pass | 0.025902 |
| `action_chip_change_asset_no_active_ref_asset_and_date_issue_188` | passed | passed | unchanged_pass | 0.029752 |
| `action_chip_change_asset_no_active_ref_fresh_idea_issue_188` | passed | passed | unchanged_pass | 0.026559 |
| `natural_language_establishes_modeled_costs_issue_271` | passed | passed | unchanged_pass | 0.028178 |
| `action_chip_add_asset_preserves_modeled_costs_issue_271` | passed | passed | unchanged_pass | 0.028358 |
| `compound_benchmark_start_date_preserves_confirmation_issue_339` | passed | failed | regression | 0.042409 |
| `ordinary_turn_edits_owned_confirmation_after_failed_action_issue_272_en` | passed | passed | unchanged_pass | 0.019045 |
| `ordinary_turn_edits_owned_confirmation_after_failed_action_issue_272_es` | passed | passed | unchanged_pass | 0.030326 |
| `asset_discovery_category_english_issue_244` | passed | passed | unchanged_pass | 0.019933 |
| `asset_discovery_peer_anchor_english_issue_244` | passed | passed | unchanged_pass | 0.019814 |
| `asset_discovery_comparison_anchor_english_issue_244` | passed | passed | unchanged_pass | 0.020913 |
| `asset_discovery_category_spanish_issue_244` | passed | passed | unchanged_pass | 0.020018 |
| `asset_discovery_recent_ipo_exact_issue_344` | passed | passed | unchanged_pass | 0.028474 |
| `asset_discovery_trending_crypto_exact_issue_344` | passed | failed | regression | 0.027831 |
| `asset_discovery_old_pharma_escalation_exact_issue_344` | passed | passed | unchanged_pass | 0.028891 |
| `asset_discovery_semantic_pharma_escalation_issue_344` | passed | passed | unchanged_pass | 0.024832 |
| `asset_discovery_spanish_generated_pharma_escalation_issue_344` | passed | passed | unchanged_pass | 0.029623 |
| `asset_discovery_not_direct_backtest_issue_244` | passed | passed | unchanged_pass | 0.019591 |
| `asset_discovery_not_result_followup_issue_244` | passed | passed | unchanged_pass | 0.023273 |
| `asset_discovery_not_capability_question_issue_244` | passed | passed | unchanged_pass | 0.018232 |
| `capability_honesty_options_straddle_tsla` | passed | passed | unchanged_pass | 0.027956 |
| `capability_honesty_golden_cross_control_aapl` | passed | passed | unchanged_pass | 0.024356 |
| `capability_honesty_momentum_breakout_aapl` | passed | passed | unchanged_pass | 0.020801 |
| `capability_honesty_news_sentiment_rule_aapl` | passed | passed | unchanged_pass | 0.030865 |
| `capability_honesty_future_performance_nvda_golden_cross` | failed | failed | changed_failure | 0.638789 |
| `capability_honesty_future_performance_btc_regression` | passed | failed | regression | 0.649656 |
| `spanish_ui_english_user_msft_hold_h1_2024` | passed | passed | unchanged_pass | 0.007679 |
| `messy_spanish_btc_hold_q1_2024` | passed | passed | unchanged_pass | 0.025015 |
| `messy_spanish_post_result_fact_then_capital_edit_issue_160` | passed | passed | unchanged_pass | 0.026044 |
| `messy_spanish_future_performance_nvda_cruce_dorado` | failed | passed | improved | 0.250413 |
| `messy_spanish_explicit_end_survives_year_qualifier` | new | failed | new_failure | 0.035919 |
| `messy_english_opening_apple_capital_missing_period_issue_336` | passed | passed | unchanged_pass | 0.032330 |
| `messy_english_aapl_simple_hold_2024` | passed | passed | unchanged_pass | 0.007340 |
| `messy_english_company_name_multi_asset_issue_142` | passed | passed | unchanged_pass | 0.019678 |
| `messy_english_complete_sma_crossover_benchmark_issue_270` | passed | passed | unchanged_pass | 0.031104 |
| `messy_english_post_result_fact_then_capital_edit_issue_160` | passed | passed | unchanged_pass | 0.023237 |
| `messy_english_explicit_end_survives_year_qualifier` | new | failed | new_failure | 0.035339 |

### Non-passing and changed-check details

- `dca_capital_semantics_only_have_amount_is_ceiling_issue_455`: regression. Prior checks: []. Current checks: ["intent: expected one of ['backtest_execution', 'strategy_drafting'], got 'conversation_followup'", "capability_verdict: expected 'unsupported', got 'answer_only'", "assets: expected ['VOO'], got []", "asset_class: expected 'equity', got None", "missing_required_fields: expected ['capital_amount'], got []", "stage_outcomes: expected ['needs_clarification', 'await_user_reply'], got ['ready_to_respond']", "clarification: expected mapping subset {'kind': 'unsupported_recovery', 'reason_code': 'unsupported_dca_contribution_ceiling'}, got None", "offered.clarification: no clarification reached the turn", "offered.min_recovery_options: expected at least 1, got []"]. New checks: ["asset_class: expected 'equity', got None", "assets: expected ['VOO'], got []", "capability_verdict: expected 'unsupported', got 'answer_only'", "clarification: expected mapping subset {'kind': 'unsupported_recovery', 'reason_code': 'unsupported_dca_contribution_ceiling'}, got None", "intent: expected one of ['backtest_execution', 'strategy_drafting'], got 'conversation_followup'", "missing_required_fields: expected ['capital_amount'], got []", "offered.clarification: no clarification reached the turn", "offered.min_recovery_options: expected at least 1, got []", "stage_outcomes: expected ['needs_clarification', 'await_user_reply'], got ['ready_to_respond']"].
- `dca_capital_semantics_prebaked_chip_bare_amount_reaches_ready_to_run`: regression. Prior checks: []. Current checks: ["intent: expected one of ['backtest_execution', 'strategy_drafting'], got 'conversation_followup'", "capability_verdict: expected 'executable', got 'answer_only'", "assets: expected ['KO'], got []", "asset_class: expected 'equity', got None", "strategy_type: expected 'dca_accumulation', got None", "capital_amount: expected 200, got None", "contribution_period: expected 'monthly', got None", "stage_outcomes: expected ['needs_clarification', 'await_user_reply', 'ready_for_confirmation', 'await_approval'], got ['ready_to_respond']", "offered.launch_payload: no launch reached the turn"]. New checks: ["asset_class: expected 'equity', got None", "assets: expected ['KO'], got []", "capability_verdict: expected 'executable', got 'answer_only'", "capital_amount: expected 200, got None", "contribution_period: expected 'monthly', got None", "intent: expected one of ['backtest_execution', 'strategy_drafting'], got 'conversation_followup'", "offered.launch_payload: no launch reached the turn", "stage_outcomes: expected ['needs_clarification', 'await_user_reply', 'ready_for_confirmation', 'await_approval'], got ['ready_to_respond']", "strategy_type: expected 'dca_accumulation', got None"].
- `compound_benchmark_start_date_preserves_confirmation_issue_339`: regression. Prior checks: []. Current checks: ["intent: expected 'backtest_execution', got 'strategy_drafting'", "date_range: expected {'start': '2026-04-01', 'end': '2026-07-30'}, got {'start': '2026-03-02', 'end': '2026-07-30'}", "requested_date_range: expected {'start': '2026-04-01', 'end': '2026-07-30'}, got {'start': '2026-03-02', 'end': '2026-07-30'}", "effective_date_range: expected {'start': '2026-04-01', 'end': '2026-07-30'}, got {'start': '2026-03-02', 'end': '2026-07-30'}", "offered.launch_payload.date_range: expected {'start': '2026-04-01', 'end': '2026-07-30'}, got {'start': '2026-03-02', 'end': '2026-07-30'}"]. New checks: ["date_range: expected {'start': '2026-04-01', 'end': '2026-07-30'}, got {'start': '2026-03-02', 'end': '2026-07-30'}", "effective_date_range: expected {'start': '2026-04-01', 'end': '2026-07-30'}, got {'start': '2026-03-02', 'end': '2026-07-30'}", "intent: expected 'backtest_execution', got 'strategy_drafting'", "offered.launch_payload.date_range: expected {'start': '2026-04-01', 'end': '2026-07-30'}, got {'start': '2026-03-02', 'end': '2026-07-30'}", "requested_date_range: expected {'start': '2026-04-01', 'end': '2026-07-30'}, got {'start': '2026-03-02', 'end': '2026-07-30'}"].
- `asset_discovery_trending_crypto_exact_issue_344`: regression. Prior checks: []. Current checks: ["prose_judge:honesty"]. New checks: ["prose_judge:honesty"].
- `capability_honesty_future_performance_nvda_golden_cross`: changed_failure. Prior checks: ["intent: expected one of ['conversation_followup', 'beginner_guidance'], got 'backtest_execution'", "capability_verdict: expected 'answer_only', got 'unsupported'", "stage_outcomes: expected ['ready_to_respond'], got ['needs_clarification', 'await_user_reply']", "offered.min_next_experiment_rows: expected at least 1, got []", "research: expected a research sidecar, got None"]. Current checks: ["research.published: expected True, got False"]. New checks: ["research.published: expected True, got False"].
- `capability_honesty_future_performance_btc_regression`: regression. Prior checks: []. Current checks: ["research.published: expected True, got False"]. New checks: ["research.published: expected True, got False"].
- `messy_spanish_explicit_end_survives_year_qualifier`: new_failure. Prior checks: []. Current checks: ["date_range: expected {'start': '2026-08-16', 'end': '2026-08-19'}, got {'start': '2024-08-16', 'end': '2024-08-19'}", "effective_date_range: expected {'start': '2026-08-17', 'end': '2026-08-19'}, got {'start': '2024-08-16', 'end': '2024-08-19'}", "offered.launch_payload.date_range: expected {'start': '2026-08-17', 'end': '2026-08-19'}, got {'start': '2024-08-16', 'end': '2024-08-19'}"]. New checks: ["date_range: expected {'start': '2026-08-16', 'end': '2026-08-19'}, got {'start': '2024-08-16', 'end': '2024-08-19'}", "effective_date_range: expected {'start': '2026-08-17', 'end': '2026-08-19'}, got {'start': '2024-08-16', 'end': '2024-08-19'}", "offered.launch_payload.date_range: expected {'start': '2026-08-17', 'end': '2026-08-19'}, got {'start': '2024-08-16', 'end': '2024-08-19'}"].
- `messy_english_explicit_end_survives_year_qualifier`: new_failure. Prior checks: []. Current checks: ["date_range: expected {'start': '2026-08-16', 'end': '2026-08-19'}, got {'start': '2024-08-16', 'end': '2024-08-19'}", "effective_date_range: expected {'start': '2026-08-17', 'end': '2026-08-19'}, got {'start': '2024-08-16', 'end': '2024-08-19'}", "offered.launch_payload.date_range: expected {'start': '2026-08-17', 'end': '2026-08-19'}, got {'start': '2024-08-16', 'end': '2024-08-19'}"]. New checks: ["date_range: expected {'start': '2026-08-16', 'end': '2026-08-19'}, got {'start': '2024-08-16', 'end': '2024-08-19'}", "effective_date_range: expected {'start': '2026-08-17', 'end': '2026-08-19'}, got {'start': '2024-08-16', 'end': '2024-08-19'}", "offered.launch_payload.date_range: expected {'start': '2026-08-17', 'end': '2026-08-19'}, got {'start': '2024-08-16', 'end': '2024-08-19'}"].
