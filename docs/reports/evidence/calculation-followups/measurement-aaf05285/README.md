# Measurement stopped: unresolved OpenRouter invoice

The authorized 93-case run at clean head
`aaf0528591ec4372c8e98f9b7636c32e043231f1` stopped after five completed cases.
It ran for 139.83 seconds on 2026-09-15. No commit occurred during the run.
The runner exited with `MeasurementBudgetStop: unresolved_invoice`; no ordinary
scorecard was produced and no model-facing text was refrozen.

## Case outcome

The first five cases passed, as they did in the baseline. Case six,
`action_chip_change_asset_no_active_ref_remove_aapl_issue_188`, was interrupted
before producing a result. It passed in the baseline. The remaining 87 cases
were not run, including all 22 new bilingual calculation-follow-up cases.
This is an incomplete measurement, not evidence of a regression-free candidate.
The interrupted case cannot be classified as a model-quality regression from
this trace.

The [93-row comparison](case-comparison.json) keeps every planned case,
its prior status and failed checks, current status, settled spend and sends.
The baseline is `grounded-math/measurement/live-measurement.json` at
`dc8608c8a09252ff8c51ef077f32d449bb0b6e8b`: 69 passed, two failed among 71 cases.
[Partial results](partial-results.json) retain exact-head provenance,
completed typed outcomes, route receipts and the interrupted case ID.

## Failure trace

The [failure trace](failure-trace.txt) reaches `clarify_stage_async`,
`llm_clarifier.astream`, and `invoke_openrouter_json_schema`. The runtime wraps
its HTTP request in `asyncio.wait_for(..., timeout=permit.timeout_seconds)`.
Cancellation surfaced during `await response.aread()` inside the measurement
transport wrapper. The wrapper marked the invoice unresolved and raised the
fatal stop, preventing another paid send. The process exited with code 1.

The trace proves cancellation while reading the response. It does not provide
a complete response invoice or enough evidence to blame model quality, the
provider service, or a local transport condition. No request was repeated after
the stop. [Route receipts](route-receipts.json) preserve the completed-call
observations, including normal OpenRouter fallback activity in preceding cases;
there were no Agent requests or Agent retries.

## Costs and limits

- Settled OpenRouter spend: **$0.093172736** across 19 invoices.
- One additional OpenRouter send has an unresolved invoice and a **$0.10
  admission reservation**. That reservation is not its actual bill or a ceiling.
- Final billed total: **unknown** until that outstanding invoice is reconciled.
- Agent: **0 sends, $0**. Search: **0 sends, $0**.
- Total HTTP sends: **20**, all OpenRouter.
- The approved limits remain $15 monitored total, $8 Agent, at most 16 Agent
  sends, one per eligible case, serially, with no Agent retries.

The [append-only cost ledger](cost-events.jsonl) retains every admission,
settlement and the terminal stop. Its final state has one outstanding send.
No automatic retry or replacement measurement was launched.

## Integration and free evidence

Original lane base: `0893c27e878f8b55c39afb467cba15ed0ed3cfee`.
Latest fetched integration: `bed233b0cdc96366acc5fc9d5a8d9193723612af`.
Merge: `1a3f5316537457133a4c063632f3ef964d5f24da`.
Research asset identity and terminal drawdown behavior were both retained;
see [preflight](../measurement-preflight.md) for the overlap audit.

At the measured head, local and hosted backend checks both reported
8,864 passed, 605 skipped and seven expected pending model-contract freezes.
Frontend, guest-release and ownership CI passed. Local frontend tests
(1,991), lint, production build, Ruff and merged-tree modularity passed.
The interrupted live evidence does not authorize refreshing those seven freezes.
No fresh Codex review or ready claim is requested after this failed gate.

The evidence files were checked for sensitive content. The public release flag
`ARGUS_MOCK_AUTH=false` is retained as required provenance, although the generic
text redactor classifies any AUTH assignment as credential-shaped. No keys,
account records, or raw provider credentials are retained here.

The run is stopped as instructed. No merge, deployment, or git stash occurred.
