# Complete rerun at 4c4e7a00: refreeze blocked

All 73 cases ran once, from scratch, at clean head `4c4e7a001150740dddef4e97fc13b99f2b0c823b`. The canonical scorecard records **65 passed, 8 failed, 0 infrastructure_error**. No admission stop fired. No diagnostic retry, product-code change, fixture change, prompt change, commit, push, new Codex review, or readiness change followed this run. The fingerprint is unchanged.

## Case-by-case result

Against the last complete measured scorecard (`docs/reports/evidence/current-reason-date-range/measurement/live-measurement.json`, measured at c861d95c): **60 unchanged passes, 4 regressions, 4 previously unmeasured cases now passed, 2 previously unmeasured cases now failed, 1 improved case, and 2 changed failures**. The 32-case stopped run is not treated as a complete scorecard or spliced into this run.

Against the scorecard named in the unchanged fingerprint: **64 unchanged passes, 5 regressions, 1 changed failure, 1 improvement, and 2 new failures**. The additional regression relative to that older baseline is the BTC future-performance research case. These are historical comparisons, not proof that a particular code or prompt change caused a failure.

The complete 73-row comparisons with old/new checks, fixture identity, and per-case costs are in [comparison.md](comparison.md) and [comparison.json](comparison.json). Raw full results and provenance are in [live-measurement.json](live-measurement.json).

| Failing case | Compared with last complete measurement | Reported USD | Accounted USD |
| --- | --- | ---: | ---: |
| `dca_capital_semantics_only_have_amount_is_ceiling_issue_455` | regression | 0.022628600 | 0.356673460 |
| `dca_capital_semantics_prebaked_chip_bare_amount_reaches_ready_to_run` | regression | 0.022483600 | 0.359841460 |
| `compound_benchmark_start_date_preserves_confirmation_issue_339` | regression | 0.038553450 | 0.042408795 |
| `asset_discovery_trending_crypto_exact_issue_344` | regression | 0.020300612 | 0.027830673 |
| `capability_honesty_future_performance_nvda_golden_cross` | previously_unmeasured_now_failed | 0.012535456 | 0.638789002 |
| `capability_honesty_future_performance_btc_regression` | previously_unmeasured_now_failed | 0.022414390 | 0.649655829 |
| `messy_spanish_explicit_end_survives_year_qualifier` | changed_failure | 0.032654050 | 0.035919455 |
| `messy_english_explicit_end_survives_year_qualifier` | changed_failure | 0.032126250 | 0.035338875 |

Failure details:

- `dca_capital_semantics_only_have_amount_is_ceiling_issue_455`: DCA ceiling routed as conversation_followup, dropped VOO, and offered no recovery choices.
- `dca_capital_semantics_prebaked_chip_bare_amount_reaches_ready_to_run`: Bare amount after prepared DCA action routed as conversation_followup and dropped KO/monthly DCA.
- `compound_benchmark_start_date_preserves_confirmation_issue_339`: Compound benchmark/start-date edit kept March 2 instead of April 1 and returned strategy_drafting.
- `asset_discovery_trending_crypto_exact_issue_344`: Prose judge flagged an unsupported claim about additional unverified crypto names.
- `capability_honesty_future_performance_nvda_golden_cross`: No research answer published; missing Agent invoice retains $0.625.
- `capability_honesty_future_performance_btc_regression`: No research answer published; Agent timeout retains $0.625.
- `messy_spanish_explicit_end_survives_year_qualifier`: Resolved MRNA and offered confirmation without prose, but all date windows used August 16 to 19, 2024.
- `messy_english_explicit_end_survives_year_qualifier`: Resolved MRNA and offered confirmation without prose, but all date windows used August 16 to 19, 2024.

The Spanish future-performance case improved and published its research answer. The previously unmeasured compound-interest, Spanish inflation, Spanish ETF, and price-question cases passed. Those improvements do not cancel the regressions.

## Date fixture correction and observed result

Both new English and Spanish date fixtures were corrected before the approved head: August 16, 2026 is Sunday, so requested August 16 to 19 should produce the August 17 to 19 trading window. Confirmation must carry no prose. These are the only fixture-semantic differences from the last complete measurement.

This run resolved MRNA in both languages and reached confirmation without prose. Both still failed because stored requested, effective, and offered launch windows used 2024 instead of 2026. The explicit August 19 endpoint survived; the year did not. No fixture was weakened or changed during this run, and these results remain failures.

## Separate costs

| Run | Reported USD | Retained unknown/Search reservations USD | Allowance on reported OpenRouter cost USD | Admission-accounted USD |
| --- | ---: | ---: | ---: | ---: |
| This complete 73-case run | 2.316936179 | 2.582321934 | 0.164891618 | 5.064149731 |
| Prior stopped 32-case run | 0.688009692 | 4.079598237 | 0.068800969 | 4.836408898 |

The new run had a fresh $7 hard admission cap; none of the stopped run's costs consumed that allowance. Accounted cost includes retained reservations and is not a final provider invoice. The ledger includes eight Agent attempts, each initially reserved at $0.625. Five invoices reconciled against the served model and tool usage; three missing/timed-out invoices retain $0.625 each. Seven canceled OpenRouter calls and five Search calls also retain their allowances. No HTTP call remains locally in flight; canceled remote work may still be billed.

The scorecard headline follows its existing receipt-accounting scope. The HTTP [budget ledger](budget.json), which includes Agent usage and unreported reservations, owns the all-provider admission total in this report.

## Guard verification

The run-local guard now reads the actual Agent request `models` list. It checks every model against the repository rate table before dispatch and uses the highest-priced fallback for the acceptance estimate: 30k input tokens, 15k output tokens, and 20 finance searches. Both supported lists select claude-opus-4-7 for that estimate, so the required reserve is $0.625 per attempt regardless of fallback order. Actual invoices use the model that served, not the reservation model.

Offline tests use `PerplexityAgentClient._request_body` for every research shape. The old guard failed on that real-client request. The corrected guard admits valid lists, rejects an unknown primary or unknown fallback before transport, enforces the cap, retains timeout reservations, and reconciles a captured invoice. The transport test confirms a valid real-client request reaches transport and an unknown fallback does not. Source and red/green output are preserved under `method/`.

## Serialization and checkout integrity

All 73 cases completed before the original scorecard serialization hit `/usr/bin/git` exit 69 due to an Xcode license error. The original .env link was restored and the isolated credential file deleted. No retry or extra provider call followed.

The already installed `/Library/Developer/CommandLineTools/usr/bin/git` worked and verified the same clean head. Offline finalization passed the original 73 saved results and original captured provenance to the unmodified canonical `write_scorecard`. Network access was blocked in that serialization process. The writer revalidated the candidate SHA, fixture hash and IDs, Python version, clean checkout, provider modes, and release configuration. This is serialization of one complete run, not a stitched or regenerated result set.

## Additional observed copy issue

The captured judged assistant text contains an em dash in these two cases. The raw model output is preserved; no extra model call or scorecard-verdict change was made for this observation:

- `asset_discovery_trending_crypto_exact_issue_344`
- `asset_discovery_not_capability_question_issue_244`

## Terminal disposition

Do not refreeze. The observed regressions fail the user's acceptance condition. PR #626 remains draft at the same head. No review/fix loop was started. Existing CI still requires the prompt freeze; it was not bypassed. Stop and report.
