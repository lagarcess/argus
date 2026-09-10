# Registry private dependency repair

The founder clarified the scope after the reset checkpoint at `3f6c6727`:
private provider cost attribution belongs to this lane; public sharing does not.
Integration `34866139861a5f06a3572edb2533bc42733371e8` remains an ancestor through
normal merge `2c593c8d08c5c152fbfa8dc77c1b3d816f11f35c`.

## Change

- Restored `llm/tool_call_receipts.py` byte for byte from the pre-reset commit.
  OpenRouter keeps its existing import. Concurrent and nested scopes retain
  their own call identity and restore the enclosing context.
- Moved the backtest card projection to
  `agent_runtime/tools/backtest_result_facts.py`. The declared return now owns
  `facts: BacktestCardFacts` instead of a public receipt payload. It reads
  retained engine outputs through the existing configuration, DCA, indicator,
  cost and display-figure owners. It neither publishes nor fetches data.
- Preserved the rendered card contract and locale keys. Numeric assumptions
  remain typed numbers, including zero. Incomplete or invalid required facts
  withhold the answer. Tests cover DCA, buy-and-hold, RSI and crossover facts,
  independent exit windows, dates, costs, benchmarks, visuals and pending work.
- Removed obsolete public-sharing assertions from the private background-job
  test and built its successful fixture through the canonical engine envelope.
  Persistence, call binding and replay-once assertions remain.
- Consolidated repeated final-message identity and next-experiment reads in
  `ChatInterface.tsx`. It is 2,596 lines, below integration's original 2,598
  limit. The temporary budget increase was removed.

All 44 actual public paths in the historical reset manifest still match
integration, including absence for deleted files. The private cost module is
the explicit exception to that earlier 45-path list. Public excerpt code was
not restored or modified. The dispatcher and editable-input handler remain
byte-identical to the protected versions in that manifest. General tool
sharing remains a follow-up against the shipped card/receipt contract.

## Additional backend failures

The shared strategy-route label repair incorrectly changed `cannot` to
`calculate`, bypassing refusal admission. It now normalizes only `explain` and
`follow_up`; capability admission retains refusal authority. Seven original
failures and eight new canonical/legacy refusal controls went red to green.

The shared research test helper serialized a raw stage patch containing a
typed `ResponseProfile`. Its before/after snapshot now uses the stage model's
canonical JSON projection. Production settlement and every spend assertion
remain unchanged. The shared and registered spend suites pass 24 tests.

## Verification boundary

The final free backend sweep passes **7,214 tests**, skips 584 tests,
and fails only the owed measured-fingerprint check. The earlier run overlapped
the final projection edge fixes and is not the final verification result.
The full frontend suite passes **1,682 tests**, with zero failures and two
snapshots. Ruff, scoped mypy, changed-file ESLint, modularity and diff checks
pass. The 23 OpenAPI compatibility checks pass; runtime regeneration produces
no additional artifact change.

The 99 Lane C, neutral-import and checkpoint tests pass. A separate fresh
process builds the backtest declaration while rejecting imports from either
public excerpt namespace. No serializer-pinned class moved. These checks do
not substitute for current-head CI, browser evidence or the live measurement.

The subsequent [complete 68-case measurement](../live-gate-third.md) at clean
`72aa04a0` reports **49 passed and 19 failed**. Its accounted charges are $2.74
plus unknown costs; the announced estimate was $3–$5. The fingerprint
remains unchanged; earlier failed scorecards retain their original grades.
This is not a clear-lane or completed-review report.
