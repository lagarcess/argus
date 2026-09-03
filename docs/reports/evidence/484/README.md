# Issue #484: readable failure records

Integration base: `c7802b37f39772a1216514e37fb6ff2b63142181`.
Production reads: 2026-09-03 UTC. No deployment, provider call, backtest, or
database mutation was performed for this evidence.

## A real production failure, before and after

At **2026-09-02 20:37:39 UTC**, a clarification call to
`deepseek/deepseek-v4-flash` timed out after **12,028 ms**. Its receipt was
unreadable in Render:

```text
2026-09-02 20:37:39.408 | INFO | argus.llm.openrouter:record_openrouter_route_receipt:321 - OpenRouter route receipt
```

The exact returned message, timestamp, log ID, and query are in
[`production-before.json`](production-before.json). Its persisted receipt is
[`production-receipt.json`](production-receipt.json), selected from
`public.route_receipts` by receipt ID
`a7c9f61d-f96e-4df8-9408-35ce251a5654`. The timestamp matches the Render line
to the millisecond. Only operational receipt fields were selected; user,
conversation, message, and run IDs and their contents are excluded.
The linked cost ledger row has `cost_amount=null`, `cost_source=unavailable`,
`status=failed`, and `latency_ms=12028`; context packet IDs are empty.

Replaying those fields through the changed **real emitter and default Loguru
sink** produces [`local-after.txt`](local-after.txt). Its message alone says:

```text
OpenRouter route receipt {"task":"clarification","tier":"chat","model":"deepseek/deepseek-v4-flash","fallback_model":"qwen/qwen3.5-9b","mode":"json_schema","schema_name":"ClarificationResponse","latency_ms":12028,"outcome":"failed","failure_mode":"TimeoutError","fallback_used":false,"token_usage":null,"usage_cost_usd":null,"context_packet_ids":[],"created_at":"2026-09-03T00:09:23.625526+00:00"}
```

This identifies the operation, model, failed attempt, timeout, elapsed time,
and whether this attempt used the fallback, without a database lookup or a
neighboring warning. The null usage/cost values do not invent a zero bill.
The timestamp in the after line is the local replay time, not a rewritten
production timestamp. This proves emitted text, **not hosted activation**.

Reproduce from the repository root, without making any model call:

```bash
poetry run python docs/reports/evidence/484/replay_receipt.py
```

The JSON comes from `OpenRouterRouteReceipt.as_dict()`, which also supplies the
structured log fields. No global formatter or dump of arbitrary logger context
is added. The emitted-output tests independently assert the required fields
and exercise success, failure, skip, fallback, null usage, and newline escaping.

## Approved-window rejection

The integration base already logs the mismatched clause and both hashes.
This PR adds **both compared date ranges even for a hash-only mismatch**.
The public `prepare_market_data` path is tested with requested-range,
effective-range, and hash mismatches; assertions read the default sink's text.
For hash drift, the line now includes:

```text
Approved data window rejected: dataset_id approved=sha256:000... current=sha256:a445...; requested_range approved=2026-08-05..2026-08-12 current=2026-08-05..2026-08-12; effective_range approved=2026-08-05..2026-08-12 current=2026-08-05..2026-08-12
```

The shortened hashes above are illustrative; the actual emitter preserves full
hashes. Matching ranges with different hashes identify changed data for the same
window, consistent with cache/provider revision drift. They do not claim which
cache was stale. Different ranges identify a window change instead.

## Workflow logs are reachable

[`task-log-queries.json`](task-log-queries.json) records two live GETs for the
same production task, `trn-08d4gdac8fqh1a67c73flu080`, with identical time bounds:

| Query | Result |
| --- | --- |
| `resource=trn-08d4gdac8fqh1a67c73flu080` | HTTP 500 |
| `resource=wfl-d8hpsmuq1p3s73duv3q0&taskRun=trn-08d4gdac8fqh1a67c73flu080` | HTTP 200, three log entries, `hasMore=true` |

This is a wrong resource/filter combination, not a current API limitation.
Workflow-only retrieval also returned HTTP 200 with logs during the probe;
the historical null response is not reproducible now. Render's
[List logs API](https://api-docs.render.com/reference/list-logs) documents
`resource` as the workflow and `taskRun` as a separate filter.
The [launch runbook](../../../PRIVATE_LAUNCH_RUNBOOK.md#retrieving-workflow-task-logs)
now contains the working command, time bounds, and pagination instructions.
No additional `execution_metadata` store is justified by this result.

## Relationship to #535 and #408

Both issues were read. The three `grounded_result` production warnings cited
by [#535](https://github.com/lagarcess/argus/issues/535) were independently
confirmed in Render: 2026-08-31 17:01:53, 2026-09-02 18:56:17, and
2026-09-02 20:12:08 UTC, all pricing-table rejections.
The before/after above is an actual **OpenRouter timeout**, not a fabricated
receipt for Perplexity. Perplexity Agent calls use a separate path; making
OpenRouter receipts readable does not repair #535 or add coverage for direct
Perplexity calls. Pricing/answer decoupling remains owned by #535.

`src/argus/observability/envelope.py` is unchanged. These are service logs,
not PostHog events; no #408 allowlist addition is required.

## Verification

- Before implementation: all seven new emitted-output cases failed because
  fields/ranges were missing. After implementation: all seven passed.
- Baseline focused suite: 144 passed, one failed before production edits:
  `test_openrouter_failure_log_reports_raising_origin`. The origin filter
  requires an `/argus/` path component, absent in this worktree's test path.
- Baseline repository lint errors: three existing E401/I001 findings in
  `docs/reports/evidence/2026-08-24-main-promotion/judge-replay.py`.
- Full deterministic suite: **5,664 passed, 532 skipped, 29 failed, 87% coverage**.
  All 29 failed cases also fail on an archived copy of the integration base
  using the same local environment. The mocked/logging subset has 151 passed
  and three of those baseline failures.
- CI-scoped lint (`ruff check src tests workflows scripts`) and modularity
  pass. The ownership script skips this branch because it has no specific policy.
- Bounded independent review: **no actionable findings**, with all seven focused
  emitted-output cases rerun and passing.
- [verification.json](verification.json) records commands and the exact baseline
  failure list. The PR records final-head CI separately.
