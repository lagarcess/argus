# Issue #462 measurement evidence

The finding is in `../../2026-09-08-turn-latency-by-type.md`. The JSONL files
contain real HTTP observations; the test fixtures under `tests/perf/` only test
recorder correctness and are not performance evidence.

## Measurement boundary

`time.perf_counter()` starts immediately before `POST /api/v1/chat/stream`.
Offsets are milliseconds at the measuring client's receipt of a complete SSE
frame. `first_token_ms` requires a non-whitespace `token.content`; headers,
keepalives, stage starts and confirmation cards cannot start that clock.
`first_visible_ms` also recognizes a delivered confirmation/result card or a
final-only answer. It describes content available to a renderer, not measured
browser paint. Browser rendering, the initial login and conversation creation
are outside the measured interval. Internet, API admission, persistence,
provider work and SSE delivery are inside it.

`done_ms` is transport completion. For background work, `completion_ms` instead
waits for the job's terminal response and result artifact. A thorough-research
acknowledgement is not its grounded answer. `answer_observed_ms` records the
later answer receipt. Polling is sequential with a one-second delay **plus each
GET's duration**: the recorded `polls` show the actual intervals. Completion is
an observed upper bound, not a subsecond server-completion estimate. Server
`queued_at`, `started_at` and `finished_at` are retained separately.

The research sidecar's `latency_ms` is not turn latency. A cached sidecar retains
the original provider duration, and a thorough job's field can describe a
provider poll. The report does not sum these into TTFT or use them as fresh
retrieval duration. Likewise, receipts may repeat the same runtime summary:
the export retains one maximum `recorded_runtime_elapsed_ms` per request,
instead of summing those copies.

`cohort.json` fixes the authored questions and ordering. Every category has ten
planned inputs, five English and five Spanish. Each accepted confirmation's
server-issued Run action is followed once. When an input does not reach a card,
the report records its actual turn type and does not invent a backtest sample.
Caches, models, timeouts, application flags and product prompts are unchanged.
The preliminary probe may warm shared research/cache entries; cache hits and
misses are disclosed, not pooled into a claim about cold retrieval.

## Reproduction

Recompute the committed distributions without a network request:

```bash
poetry run python -m scripts.benchmarks.summarize_turn_latency \
  docs/reports/evidence/issue-462/observations.jsonl \
  temp/issue-462-summary.json
```

The collector is an explicit paid, live command, using the existing configured
QA profile and the repository's no-email session helper:

```bash
poetry run python -m scripts.benchmarks.run_turn_latency --execute-live \
  --api-url https://api.arguschat.ai \
  --manifest docs/reports/evidence/issue-462/cohort.json \
  --output-dir temp/issue-462-new-run --limit 10
```

This creates ordinary test conversations and follows real backtest actions.
It does not deploy, change configuration, send an email, or create an account.
An existing QA profile is required. Receipt reads use
`default_transaction_read_only=on` and a 15-second statement timeout. Tokens,
raw model responses, user identifiers and private correlation maps must stay
out of committed evidence. The one-off cohort cleanup archives only the test
conversations created by this run; stored evidence remains available.

`history_queries.sql` documents the separate existing-telemetry snapshot. Bind
`cutoff` to `history.json`'s timestamp and execute in a read-only repeatable-read
transaction. Those historical provider/runtime durations are not TTFT.

The report uses empirical nearest-rank p50/p95 and includes the sample count
for every metric. With ten observations, p95 is the maximum. These samples
describe this fixed workload and run window, not a production SLO estimate.
Compute-intent probes have no calculator execution on the measured build;
they must never be relabeled as compute-answer measurements.
