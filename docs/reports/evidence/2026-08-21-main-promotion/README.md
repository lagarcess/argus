# Promotion gate evidence, 2026-08-21

Production `811dcbcb` to candidate `a5f1139b`, 76 commits.

| run | sha | result | cases |
| --- | --- | --- | ---: |
| baseline | `811dcbcb` | 59 passed / 1 failed | 60 |
| candidate run 1 | `a5f1139b` | 59 passed / 3 failed | 62 |
| candidate run 2 | `a5f1139b` | 60 passed / 2 failed | 62 |

The candidate suite is two cases larger: PR #524 added the two chip-shaped
two-turn cases. The runbook's gate compares failed-ID subsets, not totals.

## Unresolved

`dca_capital_semantics_stated_seed_reaches_ready_to_run_issue_455` passes at
baseline, passed candidate run 1, and failed candidate run 2 on
`capability_verdict: expected 'executable', got 'unsupported'`. That is the
only candidate-only failure across both runs, and it is what holds the gate.

PR #524's own lane settled this same case with an interleaved A/B and measured
it unstable on both sides, 3/1 at head against 2/1 at base. That is evidence
the case flips, not evidence this candidate is clean.

The other two run-1 failures both passed in run 2:
`asset_discovery_trending_crypto_exact_issue_344` (a `discovery_search_failed`
recovery, so the search provider did not answer that turn) and
`asset_discovery_recent_ipo_exact_issue_344` (`prose_judge:honesty`, which is
the known judge blindness in #516).

`asset_discovery_spanish_generated_pharma_escalation_issue_344` fails in both
candidate runs and also fails at baseline, so it is not candidate-only.

## Correction recorded deliberately

An earlier reading of these logs claimed provider rate limiting caused the
run-1 discovery failures. That was wrong: the grep matched log line numbers,
not HTTP status codes, and all three runs contain zero rate-limit responses.
The run-1 discovery failure is unexplained rather than explained.

## Resolved, 2026-08-21, by an independent reader

The disputed case was settled by a targeted interleaved A/B rather than by
another full suite, because the question was about one case and a full run
would have re-introduced every other case's variance around it.

| side | result |
| --- | --- |
| baseline `811dcbcb` | 10 passed / 0 failed |
| candidate `a5f1139b` | 10 passed / 0 failed |

Ten rounds, baseline then candidate within each round, one session, live
provider on both sides. Scorecards: `targeted-ab-baseline-scorecard-811dcbcb.json`
and `targeted-ab-candidate-scorecard-a5f1139b.json`.

`dca_capital_semantics_stated_seed_reaches_ready_to_run_issue_455` is model
variance, not a regression. Its run-2 failure is unexplained rather than
attributed, and its provider calls all succeeded; the reader confirmed the
timeouts in that run occurred *after* the typed `unsupported` decision, so they
did not cause it.

**Final blocking sets are identical on both sides:**
`{asset_discovery_spanish_generated_pharma_escalation_issue_344}`. Every
candidate failure also fails at baseline, which is the runbook's condition.

Two corrections the reader made to the prior analysis, recorded because both
were wrong in the same direction, toward a tidier story:

- The disputed case is **one-turn**, not two. The earlier claim that a
  single-turn runner could not reproduce it was false, and it caused a working
  measurement to be abandoned.
- Provider disposition must be read from structured route receipts. The earlier
  rate-limit reading came from pattern-matching log text, where the matches were
  line numbers.

Cost of the settlement: about $0.20, against roughly $4.00 spent on the three
full runs that preceded it.
