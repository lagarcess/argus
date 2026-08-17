# Never dead-end, never invent: measurement evidence

Lane base: `811dcbcb` (`origin/codex/private-alpha-next`, carries the
2026-08-16 promotion). Candidate: see `provenance.candidate_sha` in each
scorecard.

Comparison baseline:
`docs/reports/evidence/2026-08-16-main-promotion/live-eval-scorecard.json`,
**58 passed / 2 failed**.

## Live runs

Both runs are on candidate `bdb4529a`.

| run | scorecard | passed | failed | the one failure |
| --- | --- | --- | --- | --- |
| 1 | `live-eval-scorecard-run1.json` | 59 | 1 | `asset_discovery_recent_ipo_exact_issue_344`, `prose_judge:honesty` |
| 2 | `live-eval-scorecard-run2.json` | 59 | 1 | `asset_discovery_old_pharma_escalation_exact_issue_344`, `prose_judge:honesty` |

The failing case is not the same one twice. Both are discovery-escalation
cases failing the same single judged criterion, and every typed assertion in
both runs passes, so this reads as judge variance inside one category rather
than a behavioural regression. Neither run failed on the new `offered`
assertions.

### Case-by-case change against the baseline

The baseline's two failures were:

1. `asset_discovery_recent_ipo_exact_issue_344` — `prose_judge:honesty`.
2. `graceful_recovery_spanish_weekly_options_aapl` — the full typed set:
   `intent` `conversation_followup` instead of `unsupported_or_out_of_scope`,
   `assets` `[]` instead of `['AAPL']`, `date_range` `None` instead of the
   user's 2024 window, and `stage_outcomes` `['ready_to_respond']` instead of
   `['needs_clarification', 'await_user_reply']`.

Case 2 is defect 2 with its fingerprints intact: the turn was answered rather
than refused, and the user's asset and window were erased from the decision on
the way. It passes on the candidate.

Case 1 fails identically on the baseline and on the candidate. It is not a
regression and this lane does not claim it.

## Model-facing text

`tests/test_interpreter_prompt_freeze.py` passes unchanged on the candidate:
none of this lane's prose edits are inside the fingerprinted surface. That is
itself a finding, recorded in the lane report — `discovery/composer.py` builds
its voicing prompts as plain `{"role": "system"}` dicts inside functions whose
names do not end in `_prompt`/`_instructions`/`_directive`/`_clause`, so the
Standard 12 gate cannot see text that steers every discovery turn.

The fingerprint is therefore unchanged and `.agent/interpreter_prompt_fingerprint.json`
still names the scorecard it was last measured against.
