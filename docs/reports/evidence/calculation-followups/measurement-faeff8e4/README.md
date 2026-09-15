# Complete measurement failed the no-regression gate

All 93 authored cases ran once from scratch at clean head
`faeff8e448a22032989895426b06b3a32af781ed` on 2026-09-15. The run completed
in 3,087.47 seconds and wrote a failing scorecard: **65 passed, 28 failed**.
Pytest exited with code 1 because the completed scorecard contains failures.
There was no budget stop and no commit during the live run.

**No refreeze, ready claim, follow-up paid run or Codex review was performed.**
The founder's clean-refreeze prerequisite for marking ready and starting the
review loop was not met. The PR remains draft. No git stash, merge or deployment
occurred.

## Comparison and traces

The baseline is the frozen 71-case
[grounded-math scorecard](../../grounded-math/measurement/live-measurement.json)
at `dc8608c8a09252ff8c51ef077f32d449bb0b6e8b`: 69 passed and two failed.
The [93-row comparison](case-comparison.json) records each prior/current status,
failed checks, new-run settled spend, retained reservation and send count.

| Group | Passed | Failed |
| --- | ---: | ---: |
| Existing 71 cases | 60 | 11 |
| New 22 bilingual lane cases | 5 | 17 |
| Total | 65 | 28 |

Nine previously passing cases failed. The two previously failed cases remain
failed, with their old and new checks retained separately. The five passing new
cases were rewards-input completion and comparison without a personal product
pick in both languages, plus the Spanish changed-goal currency-risk answer.

[Every failed case](failures.md) has its exact checks, per-case costs and a
link to the full recorded result. The [native scorecard](live-measurement.json)
retains typed outcomes, judged prose and rendered context, judge notes, route
receipts and escaped failure frames. The [run summary](run-summary.json)
records exact-head provenance and the original scorecard digest.

The nine recorded regressions are:

- `action_chip_change_asset_bare_ticker_append_issue_190`: TSLA was not added.
- `compound_benchmark_start_date_preserves_confirmation_issue_339`: the April 1 start-date edit was not applied.
- `asset_discovery_category_english_issue_244`: no discovery payload or actionable candidates.
- `asset_discovery_comparison_anchor_english_issue_244`: prose honesty verdict.
- `asset_discovery_category_spanish_issue_244`: prose honesty verdict.
- `asset_discovery_trending_crypto_exact_issue_344`: prose honesty verdict.
- `capability_honesty_options_straddle_tsla`: unsupported-operation and recovery contracts were not met.
- `capability_honesty_future_performance_btc_regression`: no published research and failed scenario framing.
- `graceful_recovery_spanish_weekly_options_aapl`: prose honesty verdict.

The 17 new failures cover missing or inconsistent calculations, missing drawdown,
unnecessary research attempts and missing research publication. The English
card-recall case used an assumed 10% instead of the stated 15%. Both languages'
48-payment cards conflicted with prose still asking for inputs. The English
changed-goal case and both explanation-only cases attempted forbidden research;
the guard denied those sends and continued. English generic crypto rendered
symbol `BTC` where the fixture expected `BTC-USD`; that exact contract failure is
retained without claiming the underlying asset was necessarily wrong.

Four failed cases also have `prose_judge:no_structured_result` infrastructure
observations. Their independent typed failures remain failures. Some judge
explanations require adjudication: for example, the Spanish conversion judge
calls a Spanish sentence English. We retain all original scores and observations;
this run alone does not establish the cause of every recorded regression.

## Costs and admission

The [append-only ledger](cost-events.jsonl) and [budget summary](budget-summary.json)
include the approved carryover: $0.093172736 settled plus $0.10 reserved.

| Provider | Settled, including carryover | Unbilled reservation | Counted total | New sends |
| --- | ---: | ---: | ---: | ---: |
| OpenRouter | $2.12395208832 | $1.90 | $4.02395208832 | 480 |
| Agent | $0.81904 | $3.00 | $3.81904 | 8 |
| Search | $0.025 | $0 | $0.025 | 5 |
| Total | $2.96799208832 | $4.90 | $7.86799208832 | 493 |

This run added $2.87481935232 settled and $4.80 reserved. Final invoices remain
unknown for 21 sends including the prior run: 19 OpenRouter and two Agent.
Reservations remain counted; they are estimates, not provider invoice ceilings.
`accounting_complete=false` is preserved. The highest observed settled-plus-
reserved total was $9.28298962932, below the $15 monitored cap. Agent ended at
$3.81904 counted, below $8, and eight sends, below 16. Each admitted Agent case
had one send. One attempted Agent retry was denied before dispatch and its case
failed; it was not retried by the measurement runner.

Calls were serial at the case level. Cancellation and missing invoices did not
end the run. The runner carried their reservations forward and finished all 93
cases. Normal OpenRouter runtime fallback activity remains visible in receipts;
the explicit one-send/no-retry bound applies to Agent research.

## Evidence identity and free checks

The founder explicitly selected `faeff8e4` for this rerun. The prepared ignored
environment retained live market and asset providers; the native scorecard
records the actual release configuration and successful live holiday probe.
Before dispatch, all 38 budget tests passed and the worktree was clean.
[CI at the measured head](https://github.com/lagarcess/argus/actions/runs/35012722492)
had 8,873 backend tests passed, 605 skipped and only seven pending freeze failures;
frontend, guest-release, ownership, lint and modularity checks passed.

Original integration base: `0893c27e878f8b55c39afb467cba15ed0ed3cfee`.
Previously reconciled integration: `bed233b0cdc96366acc5fc9d5a8d9193723612af`.
Reconciliation merge: `1a3f5316537457133a4c063632f3ef964d5f24da`.
This is failed evidence at the requested head, not a fresh integration readiness
claim. The evidence commit is made only after process exit and changes no
runtime, fixture, model-facing text, recorded retrieval request or fingerprint.
