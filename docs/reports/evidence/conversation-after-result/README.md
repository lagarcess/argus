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
- **Cases whose snapshot holds a completed result, at `4248fdd4`.** The Codex review fixes change how a follow-up resolved to a stored fact is answered, so these ran again, and all five passed:
  - the English and Spanish `post_result_fact_then_capital_edit_issue_160`
  - `asset_discovery_not_result_followup_issue_244`
  - the English and Spanish `ordinary_turn_edits_owned_confirmation_after_failed_action_issue_272`

NVDA golden cross failed in both scorecards, for different reasons. In the baseline its research timed out. Here the publisher withheld a scenario whose inputs had no citation, and the reply said so.

Model-facing text is identical at the measured head `aef7d1c2`, at `9eddf710` and at `4248fdd4`, across the 23 files the fingerprint covers. The commits after the measured head change deterministic code only:

- one owner for the benchmark gap and cost drag;
- a stated cost the audit cannot ground is asked about, never confirmed at 0 bps;
- a refactor to stay within the line budget;
- a follow-up resolved to a stored fact is answered from the run without research, and its reply must declare the fact.

The fingerprint's `last_measured` points at this scorecard.

Billed spend was $1.770 in total:

| Run | Billed |
| --- | --- |
| Full run | $1.405 |
| Three retries | $0.094 |
| Cost cases | $0.107 |
| Integration BTC run | $0.017 |
| Slippage capture | $0.024 |
| Stored-fact cases | $0.123 |

Twelve route receipts came back without a price. They are not assumed to cost zero.

## The 0 bps slippage read

In the Part A live check, a Spanish card read the requested 10 bps slippage as 0 bps. That came from code, not model variance. When the cost fidelity audit cannot ground a stated cost, it removes the value and owes a question (`execution_cost_evidence_unresolved`, missing `assumption`). Two stages dropped that question, and confirmation then defaulted the slippage to 0 bps:

1. **The interpret stage** kept only the strategy's required fields. Fixed in `5d1105eb`.
2. **The clarify stage** also asked only for the strategy's required fields on a new request. A live capture of the same Spanish message showed it: the first read gave 1 bp, the audit read 10 bps, the two disagreed, so the cost stayed unresolved as designed, and the clarify stage sent the turn to confirmation. Fixed in `7a00b8e9`: the clarify stage asks for a missing `assumption`.

English and Spanish tests in `tests/agent_runtime/test_cost_fidelity_stage_clarification.py` run the whole turn and check that Argus asks and shows no card.

### The live recheck

The one live recheck on `a344b489` took a different path ([card](spanish-card-recheck/card.png), [route receipts](spanish-card-recheck/receipts.json)):

1. The first interpretation model timed out after 20 seconds.
2. The fallback model's reply failed validation, because `response_profile_overrides` was null.
3. The last-resort focused repair built the card.

That card showed no fees, no slippage and $0 starting capital, and Argus asked nothing. No stated-field audit ran after the repair. The focused repair's schema has no fee or slippage fields.

This branch does not change that path, so it is listed as a follow-up rather than fixed here. An offline replay of the repair, with a stub model that reads both costs, did reach the audit and kept 5 and 10 bps. The model read that skipped the audit live was not recorded. The final walk shows the Spanish card again.

## Two tabs on one conversation

The same new chat was open in a second tab while the first was answering ([branch report](two-tabs/branch-report.json), [integration report](two-tabs/integration-report.json)):

- Tab B shows "Argus is working on New chat." when it opens, and the status clears once tab A's answer lands.
- Tab B never shows the answer. Twenty seconds after it landed, tab A had 2 messages and tab B had 1 ([tab A](two-tabs/branch-tab-a.png), [tab B](two-tabs/branch-tab-b.png)).
- `origin/codex/private-alpha-next` at `b0a7cf08` behaves the same ([tab A](two-tabs/integration-tab-a.png), [tab B](two-tabs/integration-tab-b.png)). This branch did not cause it, so it is left as is.
