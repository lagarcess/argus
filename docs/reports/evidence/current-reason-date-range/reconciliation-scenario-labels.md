# Reconciliation after the scenario-label repair

The founder authorized one complete serial 73-case measurement under a fresh $7 hard admission cap after merging the latest integration. This supersedes the previous instruction to stop on the first observed failure. Finish every case once, record failures, write the complete scorecard, then decide whether refreezing is justified. Stop early only when admission would exceed the cap. A provider HTTP 500 without an invoice is a provider failure, not a regression. Retain its reservation and evidence. Do not waive a product failure as a provider failure merely because a provider error also occurred.

## Lineage and overlap

- Original lane base: `039189128ea6ffcf59be73f3564fd936f191f662`.
- Previous candidate: `f8d378c53b5ac5bdb405b63694f7bed66b263350`.
- Incoming integration: `b5169455ce2a201fcc617a89164e0e0901bf5658`.
- The new merge commit will be recorded as the exact candidate in measurement provenance.

Integration adds the bounded scenario-label recovery in `answer_calculation.py`, its tests, and the roadmap record. The merge has no textual conflicts. The semantic overlap is the research answer rendering path that failed the prior BTC measurement. Keep integration's recovery and all existing lane changes: current-reason grounding, language-correct degraded replies, nullable-object handling, explicit-end preservation, and New York clock year binding. No API, persistence, environment, or UI contract is changed by this reconciliation. The earlier full-run attempt remains incomplete historical evidence and is not reused as acceptance.

## Run discipline

Rerun free backend lint, merged-tree modularity, the complete backend suite including the mocked eval harness, frontend lint/tests/build, and the admission guard against the real Agent request builder before committing and pushing the candidate. Prompt freeze is expected to fail until measurement acceptance. The local driver is tested to attempt all 73 cases despite failures and exceptions, without repeating a case. Disable Agent transport retries only in the measurement process; normal configured interpretation/voicing fallbacks remain part of a single case. The production source is unchanged by this run policy.

Use the same highest-priced fallback admission reservation, at least $0.625 per Agent attempt, and retain missing-invoice reservations. Refresh public pricing metadata without paid inference. Save raw structured responses and the spend ledger. Keep the worktree clean during measurement, make no commits while it runs, restore the original dotenv link, and delete the temporary credential file on exit.

Compare the complete scorecard case by case with the last full scorecard, the fingerprint's named scorecard, and the prior targeted/partial observations. Preserve raw failure statuses and add any provider classification as separate evidence. Refreeze only with a complete run and no regression under the founder's stated rule. Otherwise stop and report with trace evidence. After acceptance, commit the scorecard and regenerated fingerprint, obtain green CI, mark PR #626 ready, and work current-head Codex findings until clean with zero unresolved threads. The founder owns the merge.

## Free results before measurement

The full backend suite reports 8,919 passed, 614 skipped, the expected prompt-freeze failure, and one local Git fixture setup error (`unable to create temporary file: Invalid argument`). The complete affected fixture module passed on rerun: 93 tests. No source fix was needed for that environment error. Backend lint and merged-tree modularity pass. Frontend lint has zero errors, all 2,061 tests pass, and the production build passes. Logs are in [scenario-repaired-free-verification](scenario-repaired-free-verification/); trailing whitespace is normalized in these free-check logs.

The real-client guard tests pass. The actual driver loop was exercised offline with 73 case doubles, two recorded failures, and one injected exception: it ran all cases exactly once. A cap rejection stops the loop. The run-local Agent attempt limit prevents a second dispatch after HTTP 500. The saved prior NVDA and BTC outcomes also verify that provider classification separates the uninvoiced HTTP 500 from a successful-provider product failure. No paid inference was used for these checks.
