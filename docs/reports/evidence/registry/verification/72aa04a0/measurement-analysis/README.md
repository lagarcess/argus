# Third registry measurement: preserved comparison

Clean measured candidate `72aa04a06d00a76421414e778d67fc2cf3ccd0f2`: **49 passed, 19 failed, 0 infrastructure errors, 0 skipped**, across 68 cases. Original statuses and exact failed-check strings are preserved; this report does not regrade an earlier run.

| Prior run | Recorded prior result | Common cases | Pass → fail | Fail → pass | Failed in both |
| --- | --- | ---: | ---: | ---: | ---: |
| 411 | 61 pass / 1 fail | 62 | 18 | 0 | 1 |
| 565 | 65 pass / 3 fail | 68 | 16 | 0 | 3 |
| second | 52 pass / 16 fail | 68 | 9 | 6 | 10 |

The 411 run contains 62 cases; the other three runs contain the same 68 case IDs. Fixture hashes differ for 411 and 565. The second and third full runs have the same fixture hash, but the third uses collective selection evidence and the added evaluator-level selection-relevance criterion. These are recorded status transitions across different code/evaluation contracts, not isolated causal regression estimates.

## Cases with a failed grade in the second or third full run

P = passed, F = failed, absent = no case in that source. The final column groups exact third-run check strings for readability; comparison.json retains every string and per-case check delta.

| Case ID | 411 | 565 | Second | Third | Third failed-check families |
| --- | --- | --- | --- | --- | --- |
| `natural_language_establishes_modeled_costs_issue_271` | P | P | F | F | capability_verdict, launch_execution_realism, offered.launch_payload, stage_outcomes |
| `asset_discovery_comparison_anchor_english_issue_244` | P | P | F | P | — |
| `asset_discovery_category_spanish_issue_244` | P | P | P | F | prose_judge:selection_relevance |
| `asset_discovery_recent_ipo_exact_issue_344` | P | P | F | F | asset_discovery, offered.actionable, prose_judge:selection_relevance, tool_dispatch |
| `asset_discovery_trending_crypto_exact_issue_344` | P | P | F | F | asset_discovery, offered.actionable, offered.min_discovery_rows, offered.names_unavailable, prose_judge:selection_relevance |
| `asset_discovery_old_pharma_escalation_exact_issue_344` | P | P | F | F | asset_discovery, prose_judge:selection_relevance |
| `asset_discovery_semantic_pharma_escalation_issue_344` | P | F | P | F | asset_discovery |
| `asset_discovery_spanish_generated_pharma_escalation_issue_344` | P | F | F | F | asset_discovery, prose_judge:selection_relevance |
| `asset_discovery_not_result_followup_issue_244` | P | F | F | F | offered.min_next_experiment_rows |
| `metric_correctness_eth_default_crypto_benchmark` | P | P | P | F | capability_verdict, offered.launch_payload, stage_outcomes |
| `capability_honesty_golden_cross_control_aapl` | P | P | F | F | adjustment_reason, capability_verdict, effective_date_range, offered.launch_payload, stage_outcomes |
| `dca_capital_semantics_start_by_phrase_is_contribution_issue_455` | P | P | P | F | adjustment_reason, capability_verdict, effective_date_range, offered.launch_payload, recurring_contribution, stage_outcomes, starting_capital |
| `dca_capital_semantics_only_have_amount_is_ceiling_issue_455` | P | P | F | F | missing_required_fields |
| `dca_capital_semantics_stated_seed_reaches_ready_to_run_issue_455` | P | P | F | F | adjustment_reason, capability_verdict, effective_date_range, offered.launch_payload, recurring_contribution, stage_outcomes, starting_capital |
| `dca_capital_semantics_spanish_seed_and_contribution_issue_455` | P | P | P | F | adjustment_reason, capability_verdict, effective_date_range, offered.launch_payload, recurring_contribution, stage_outcomes, starting_capital |
| `dca_capital_semantics_spanish_period_exceeds_window_issue_455` | P | P | F | P | — |
| `dca_capital_semantics_prebaked_chip_bare_amount_reaches_ready_to_run` | P | P | F | P | — |
| `dca_capital_semantics_prebaked_chip_spanish_pesos_reaches_ready_to_run` | F | P | P | F | capability_verdict, offered.launch_payload, stage_outcomes |
| `graceful_recovery_spanish_weekly_options_aapl` | P | P | F | P | — |
| `messy_english_complete_sma_crossover_benchmark_issue_270` | P | P | F | F | capability_verdict, offered.launch_payload, stage_outcomes |
| `messy_english_post_result_fact_then_capital_edit_issue_160` | P | P | P | F | capital_amount, offered.launch_payload.capital_amount |
| `messy_spanish_btc_hold_q1_2024` | P | P | F | P | — |
| `messy_spanish_post_result_fact_then_capital_edit_issue_160` | P | P | P | F | capital_amount, offered.launch_payload.capital_amount |
| `ordinary_conversation_macro_curiosity_en` | absent | P | F | P | — |
| `spanish_ui_english_user_msft_hold_h1_2024` | P | P | P | F | adjustment_reason, capability_verdict, effective_date_range, offered.launch_payload, stage_outcomes |

## Observed intents and calls

| Observation | Third full run |
| --- | --- |
| Primary intent | calculate 44; explain 16; follow_up 1; cannot 6; null 1 |
| Effective intent | calculate 45; explain 6; follow_up 11; cannot 6 |
| Selected call counts | 34 cases with zero calls; 34 with one call; none with multiple calls |
| Selected tools | backtest 24; peer_expansion 7; screening 2; balanced_lookup 1 |
| Actual execution records | 10 research records: 9 succeeded, 1 unavailable |
| Backtest execution records | 0; the 24 selected calls are preparation/confirmation observations, not executed simulations |

All four canonical labels occur. Ten primary explain turns select a research call and finish with effective follow_up. This supports tool selection without forcing every call into calculate. It does not prove all seven historical intents were exercised: the 411/565 scorecards observe only four legacy labels and do not retain primary-intent or tool-call fields. Missing historical call fields are reported as unobserved, never as zero calls. This live suite has no multi-call or repeated-call turn, so it does not establish composition or repetition behavior. The 19 failures also prevent a claim of behavioral parity or a clear lane.

## Cost disclosure

OpenRouter reports **$2.068219816178** across 357 priced receipt records out of 381. The 24 records without costs comprise 6 timeouts, 3 validation errors and 15 zero-latency local rejection records; none retains token usage. These are not 24 extra requests.

Three separate Search API observations retain **$0.015** in total, using the configured $0.005 fee. Four distinct Research Agent responses report **$0.65469** in invoices. All four have tariff mismatches, so that amount is provider-reported, not independently validated. Eight billing log lines describe those four responses; each duplicate is excluded. The invoices already include 1 finance-search, 14 web-search and 3 fetch-url invocations, so no additional embedded-tool fee is added.

The accounted reported/estimated total is **$2.737909816178**. It already includes the unvalidated Agent invoices; additional spend behind missing-cost OpenRouter records remains unquantified. OpenRouter plus the separate Search estimate alone is **$2.083219816178**. No per-request charge for market-data/asset-provider access is retained, so none is invented. The report is not a complete validated invoice.

Detailed evidence: comparison.json (all case/check/intent observations), cost-accounting.json (exact decimal sums, per-case amounts and deduplication), provenance.json (input hashes), analyze_scorecards.py (reproducible read-only analysis).
