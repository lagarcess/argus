# Money-question recovery: scripted verification

This lane addresses four acceptance failures from PR #631. History-only
research admission is excluded by the founder. All providers are scripted;
these checks establish runtime behavior, not live model quality.

## Lineage

- Original branch base: `0893c27e878f8b55c39afb467cba15ed0ed3cfee`.
- Before implementation, fast-forwarded to integration
  `6ec3679750fb6fb4cded21443c1ab4635a4687b5`.
- Integration remained at that SHA when reconciliation was checked. There is
  no intervening integration diff and no reconciliation merge.
- The exact final head, CI and Codex review outcome belong to the terminal PR
  comment written after review completes, not this pre-review record.

## Reproduce the red baseline

Archive integration `6ec3679750fb6fb4cded21443c1ab4635a4687b5` into an isolated
directory with no `.env`, copy these three new test files into the archive, and
run the repository Python environment with that directory as its working
directory:

```sh
python -m pytest \
  tests/agent_runtime/test_money_question_recovery.py \
  tests/agent_runtime/test_money_question_recovery_copy.py \
  tests/research/test_research_turn_deadline.py \
  -k 'not last_resort_repair_preserves_only_a_typed_test_read' -q --no-cov
```

Observed: **13 failed, 3 deselected**. The three positive typed-repair controls
exercise the new internal argument and are intentionally outside the baseline
run. Baseline failures are behavioral assertions, not dependency or collection
errors:

| Surface | Baseline failure | Fixed behavior |
| --- | --- | --- |
| Q4 bond, Q8 arithmetic text, named stock question after both candidates fail | Focused repair receives a fabricated strategy seed | No strategy repair without this turn's typed test read; ordinary retry recovery |
| Q8 follow-up with pending buy-and-hold or DCA | Knowledge path returns before arithmetic | Real growth kernel computes the inflation-adjusted value; no requested test window; pending snapshot unchanged |
| Concept follow-up with pending test | Question misses the knowledge answer | Current interpreted question reaches the answer |
| Q1 savings, EN/ES, retryable and nonretryable | Copy names test setup or an asset/period | Existing recovery codes name failed question understanding, with locale parity and no em dashes |
| Q2 Porsche, slow sync provider | Real keepalive raises `agent_runtime_event_timeout` | Existing no-lookup answer runs before the deadline, asks for missing user inputs, and the follow-up computes income through `debt_to_income` |
| Research retries | Each gets 150 seconds despite only 40 then 35 seconds remaining | Attempts share the shrinking turn budget and preserve canonical voicing time |
| Budget expires before provider dispatch | Provider still runs | No provider call; unused admission claim released |

The Q2 test releases its deliberately blocked provider after the fallback has
returned. It verifies the admission charge is retained and no late response
enters the shared cache. Every owned thread is joined before the test exits.

## Candidate checks

The three test files above, without the baseline exclusion, pass **16/16**.
The required mocked eval harness passes **270/270**. The frontend suite passes
**1,981/1,981**. Frontend lint has zero errors (eight existing warnings), and
the production build passes. Backend lint and modularity budget pass. The
ownership tool reports no lane-specific policy. The full backend suite passes
**8,614 tests**, with **604 skips**
(disposable database/live gates and optional environments) and **89% coverage**.
The initial sandbox run also exposed local socket/process restrictions; the
provider-free rerun with those permissions passed. No provider credentials or
worktree `.env` were available to that run.

The old cost/fidelity and seven-call corridor fixtures now supply a typed test
read before expecting strategy repair. Their money-role, fee, slippage and call
budget assertions remain. Separate outage tests assert the safer unread-turn
outcome for both default and explicitly selected interpreter models.

## First review fixes

Codex reviewed `407ce0186e75dac9a38719b3e843f3d0f0a5c967` and raised two
distinct findings. Each was reproduced before its fix:

- A typed `backtest_execution` / `retry_failed_action` with no reusable launch
  payload was excluded by the new semantic guard even though the existing repair
  predicate permits it. The guard now preserves that typed retry path. Its new
  parameterized case failed before the one-line guard change.
- The full Q2 path can consume all seven ordinary calls before research starts.
  The test now enters `interpret_stage_async`, uses real OpenRouter admission
  with scripted HTTP responses, and spends four asset-preflight attempts plus
  three interpretation attempts. Before the fix, the slow lookup expired but
  recovery voicing was skipped with `turn_call_allowance_exhausted`. The turn now
  owns one observable, single-use voicing reservation scoped to the existing
  no-lookup answer. It cannot extend the deadline or fund another task.

The combined acceptance, focused-repair and execution-budget checks pass
**73 tests**. The expanded Q2 test retains the real calculation follow-up and
late-worker cleanup. The unchanged-integration red run remains **13 failures**.
Final review disposition belongs to the terminal PR audit.

## Limits

- No model-facing text/schema descriptions or `render.yaml` changes.
- No paid eval, provider calls, live backtests, or browser provider turns.
- If every interpreter candidate is unreadable, even a naturally worded test
  request takes honest retry recovery; text heuristics do not invent its intent.
- Cancelling an async wait cannot stop an already running synchronous provider.
  Its charge remains admitted; a late invoice may remain unavailable, as with
  existing abandoned workers. This change never publishes or caches that reply.
- No merge or deployment. Live quality and release acceptance are not claimed.
