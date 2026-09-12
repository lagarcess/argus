# Conversation after a result: evidence

- [Interpreter payload](interpreter-payload/): the payload fix that shrank the interpreter prompt.
- [Part A live check](part-a/README.md): screenshots of the founder's ten fixes in the real web app.

## Measurement

[Full scorecard](live-measurement.json): **67 passed, 4 failed, 0 infrastructure errors** across 71 cases. It ran once on `aef7d1c2`, with a clean worktree and both provider modes assigned directly to `live_provider`. Baseline: the [model result readouts scorecard](../model-result-readouts/live-measurement.json) at `7d7ea88b`, with 67 passed, 3 failed and 1 infrastructure error.

[Case by case](measurement-comparison.json): 64 passed in both, 3 improved, 1 failed in both, and 3 failed after passing in the baseline. Every row carries, for both runs, the failed checks, structured-tier timeouts, failed route receipts and a receipt review.

[Reruns](measurement-retries.json) ran each case once and never replace the first result:

- **The three new failures, at `9eddf710`.**
  - Spanish pharma escalation: in the full run the judge failed the discovery reply on honesty. The retry passed.
  - Spanish pesos chip: in the full run "13,000 pesos" was read as starting capital. The retry passed.
  - BTC future performance: failed again. Both times the research provider returned HTTP 500, so nothing was published and the reply said the lookup had failed.
- **BTC on `origin/codex/private-alpha-next` (`509b7d03`), in a throwaway worktree.** It failed the same two checks, with the provider read timing out, so the failure does not come from this branch.
- **Cases with stated execution costs, at `9eddf710`.** The ungrounded-cost fix came after the measured head, so these ran again, and all four passed:
  - `natural_language_establishes_modeled_costs_issue_271`
  - `action_chip_add_asset_preserves_modeled_costs_issue_271`
  - the English and Spanish `dca_capital_semantics_clarification_reply_keeps_earlier_facts_2026_09_10`

NVDA golden cross failed in both scorecards, for different reasons. In the baseline its research timed out. Here the publisher withheld a scenario whose inputs had no citation, and the reply said so.

Model-facing text is identical at the measured head `aef7d1c2` and at `9eddf710`, across the 23 files the fingerprint covers. The commits after the measured head change deterministic code only:

- one owner for the benchmark gap and cost drag;
- a stated cost the audit cannot ground is asked about, never confirmed at 0 bps;
- a refactor to stay within the line budget.

The fingerprint's `last_measured` points at this scorecard.

Billed spend was $1.647 in total:

| Run | Billed |
| --- | --- |
| Full run | $1.405 |
| Three retries | $0.094 |
| Cost cases | $0.107 |
| Integration BTC run | $0.017 |
| Slippage capture | $0.024 |

Eleven route receipts came back without a price. They are not assumed to cost zero.

## The 0 bps slippage read

In the Part A live check, a Spanish card read the requested 10 bps slippage as 0 bps. That came from code, not model variance:

1. The cost fidelity audit could not ground the stated slippage, so it removed the value and owed a question (`execution_cost_evidence_unresolved`, missing `assumption`).
2. The interpret stage kept only the strategy's required fields, so it dropped that question.
3. Confirmation then defaulted the slippage to 0 bps.

That turn's model outputs were not recorded. A capture of the same message on this branch read 10 bps. The fix is `5d1105eb`, with English and Spanish stage tests in `tests/agent_runtime/test_cost_fidelity_stage_clarification.py`. Running the same message on the integration branch was not needed, because the code dropped the value whatever the model read.
