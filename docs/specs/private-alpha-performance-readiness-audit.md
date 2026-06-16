# Private Alpha Performance Readiness Audit

**Status:** Draft performance audit addendum
**Date:** 2026-06-12
**Branch:** `codex/private-alpha-next`
**Purpose:** Capture the read-only performance panel findings for the controlled
alpha readiness slice.

This addendum is intentionally not an optimization plan yet. It identifies what
Argus should measure first, which speed wins look clean enough to consider, and
which tempting optimizations should be avoided until data proves they matter.

## Performance Charter

Speed is a product feature for Argus. A chat-first investing assistant feels
trustworthy only if it responds quickly, explains progress honestly, and keeps
the user oriented while expensive work runs.

The operating rules for this lane are:

- every millisecond counts, but only measured milliseconds should drive
  implementation priority;
- measure first, optimize second;
- do not sacrifice correctness, trust, or readability for micro-optimizations;
- prefer optimizations that are small, testable, and reversible;
- speed without correctness is useless.

## Executive Verdict

Argus does not need a broad performance rewrite before a small controlled alpha.
It does need a measurement-first performance gate before public guest mode or a
larger invite wave.

For the controlled alpha, the highest-leverage performance work is:

1. Measure chat perceived latency: first byte, first SSE event, first token,
   full stream, and result-card completion.
2. Verify Render workflow tier and live backtest timing before tester windows.
3. Split obvious cold frontend code from the default chat path.
4. Remove small, proven render-loop and repeated-read inefficiencies.
5. Defer deep engine, database, and UI rewrites until production-like data
   shows the bottleneck.

The current evidence says the most important speed question is not "can we shave
microseconds from a hot loop?" It is "where does the user wait, and do we know
why?"

## Worker Coverage

The read-only panel covered:

- frontend React/Next performance;
- backend chat, SSE, and LLM runtime latency;
- Supabase/Postgres query and index posture;
- backtest engine and Render workflow compute;
- measurement and automation, synthesized locally after the measurement worker
  timed out.

No runtime source changes were made as part of this audit.

## Current Evidence

### Frontend

- Existing build diagnostics show `/chat` as the heavier route, around `1.36 MB`
  first-load uncompressed JavaScript and around `388 KB` gzip by chunk readback.
- The chat route has no `next/dynamic` split for heavy chat sub-surfaces.
- `lightweight-charts` is pulled into the chat path through the result card even
  before a completed result exists.
- Cold surfaces such as command palette, feedback dialog, settings, and
  strategies are statically imported into `ChatInterface`.
- Good existing patterns are already present:
  - composer discovery is debounced;
  - asset and indicator discovery calls are parallelized;
  - discovery has a short client cache;
  - sidebar history paginates with an intersection observer;
  - chart marker density is bounded;
  - Next already optimizes package imports for `lucide-react`.

### Backend Runtime

- Route receipts already capture useful LLM-task latency, outcome, token, and
  model metadata.
- The live chat benchmark path measures full stream time, but does not yet split
  first byte, first SSE event, and first token.
- `chat_stream` does meaningful work before returning the stream: quota,
  profile, conversation, history, checkpoint, metadata fallback, and
  user-message persistence.
- Metadata fallback can repeat recent-message scans in the same turn, but the
  issue 112 confirmation-action case is resolved locally on
  `codex/private-alpha-readiness-clean`.
- [GitHub issue 112](https://github.com/lagarcess/argus/issues/112) remains open
  until merge; focused tests now prove valid confirmation actions reuse one
  recent-message read while stale confirmation actions still stop before
  runtime.
- Context packet collection can block final result persistence/stream completion
  up to its budget after a result card.

### Supabase And Query Shape

- Core timeline, message, run, feedback, usage-counter, and job indexes exist.
- The largest database performance risk is list/search shape, not missing
  obvious primary indexes.
- Several list endpoints fetch all rows and page/filter in Python. This is fine
  for tiny alpha usage, but it becomes the first database risk before guest mode.
- Search is currently app-side substring filtering, despite architecture docs
  pointing toward Postgres FTS for Alpha search.
- Global backtest job backpressure checks may need a global status/active partial
  index if queue rows grow.
- Latest completed run lookup may need a partial composite index if production
  `EXPLAIN` shows sort or bitmap work.

### Backtest And Workflow

- The API import boundary looks healthy: `/health` stays clear of the heavy
  backtest stack.
- Prior capacity evidence showed local synthetic non-DCA cases around
  `1.23-1.44s`, while DCA cases were much faster because they avoid the heavy
  vectorbt path.
- The sharper live signal is the Render workflow canary: around `55.2s` total,
  with about `14.16s` dependency/tool load, `33.19s` backtest tool run,
  `0.63s` provider fetch, `33.08s` engine compute, and `6.69s` result readout.
- That evidence points more toward workflow tier/import/engine compute than
  provider latency.
- Metrics and chart generation appear to duplicate OHLCV/benchmark fetches and
  some local compute inside one run.

## Do Now: Measurement Gate

These are not user-facing optimizations. They are the low-risk measurement work
that should happen before making performance claims.

1. Add first-byte, first SSE event, first token, and full-stream timing to the
   Render chat benchmark.
2. Add internal timing spans around pre-stream setup in `chat_stream`:
   quota/profile/conversation reads, history, checkpoint, fallback probes, and
   user-message write.
3. Add result persistence timing for context packet collection and final
   assistant-message persistence.
4. Keep issue 112 regression tests green until merge: valid confirmation actions
   must use one recent-message read while stale confirmation behavior remains
   unchanged.
5. Confirm the live Render workflow plan/tier before each tester window and
   record cold/warm workflow timings.
6. Capture `/chat` route bundle size, gzip estimate, duplicate `/me` request
   count, and React commit time on a restored long conversation.
7. Use `pg_stat_statements` and targeted `EXPLAIN (analyze, buffers)` before
   adding database indexes.

## Low-Risk Shortlist

These are good candidates once the measurement gate is in place.

### Frontend

- Dynamically import `ResultEquityChart` so `lightweight-charts` is not part of
  the default chat path before a result exists.
- Dynamically import cold overlays: `FeedbackDialog`, `ChatCommandPalette`, and
  possibly settings/strategies surfaces.
- Compute the latest assistant-message index once before mapping messages,
  instead of doing a `findLastIndex` inside each row render.
- Avoid duplicate `/me` profile fetches on `/chat` when private-alpha onboarding
  is disabled, or share the gate result with `ChatInterface`.
- Measure the i18n boot blank screen before changing loading behavior; locale
  files are small enough that the perceived delay may be more important than the
  transfer size.

### Backend Runtime

- Collapse repeated metadata fallback scans into one recent-message read per
  turn where measurement proves it matters; the confirmation-action issue 112
  case is already covered locally.
- For issue 112 specifically, keep preserving stale confirmation behavior: old
  `confirmation_id` values must still return the stale-card recovery message and
  must not execute runtime.
- Log row count and duration for history/search/conversations/messages before
  changing pagination semantics.
- Keep OpenRouter receipt and response-style guardrails intact. LLM latency is
  not an excuse to restore brittle deterministic conversation logic.

### Supabase

- Push keyset pagination into the database for active list endpoints before
  guest mode or broader invite traffic.
- Add a global active-status partial index on `backtest_jobs` only if
  `EXPLAIN` shows global queued/running counts scanning too much data.
- Add a latest-completed-run partial composite index only if real production
  stats show the lookup sorting or bitmap-scanning.
- Consider Supabase-style cached `select auth.uid()` RLS predicates during the
  next approved RLS migration, not as an isolated performance detour.

### Backtest And Workflow

- Confirm whether the workflow is running on the intended plan/tier before
  optimizing code. A plan mismatch can dwarf code-level wins.
- Add a per-run in-memory fetch cache for OHLCV and benchmark series inside one
  engine launch, returning copies to preserve correctness.
- Lazy-import vectorbt on non-DCA paths if import/RSS evidence confirms the DCA
  path pays unnecessary cost.
- Add one missing timing span around run snapshot/card construction so the
  engine pipeline can be split into fetch, signal, ledger, portfolio, metrics,
  chart, and readout phases.

## Avoid For Now

- Do not sprinkle `React.memo` everywhere without React Profiler evidence.
- Do not add full chat virtualization before long-thread behavior proves it is
  needed; scroll anchoring and streaming are sensitive.
- Do not replace `react-markdown`, charting, or vectorbt as broad dependency
  swaps before measured bundle/CPU evidence.
- Do not add durable Supabase market-data caching yet; the live canary's
  provider fetch time was not the bottleneck.
- Do not add pgvector, broad JSONB GIN indexes, covering indexes, partitioning,
  or FTS migrations without query stats and usage evidence.
- Do not reduce LLM reasoning, audits, or response voice quality just to save
  seconds. Speed that damages trust is not a product win.
- Do not optimize cold paths or internal admin surfaces before the chat and
  backtest happy path is measured.

## Readiness Slice Impact

Performance should not displace the current first blocker: Spanish backend
execution. The readiness slice should add performance gates in parallel with the
Spanish and trust work, then decide whether to implement speed fixes from
evidence.

Recommended order:

1. Spanish backend execution.
2. Measurement gate for chat, workflow, and bundle size.
3. Frontend cold-code splitting and the message-loop O(n2) cleanup if the build
   metrics confirm the expected win.
4. Runtime setup timing and fallback-scan consolidation if TTFB or first-event
   timing shows backend setup is visible.
5. Workflow tier verification and engine subphase timing before any engine
   optimization.
6. Database pagination/index work before guest mode, not necessarily before a
   tiny named-user alpha.

## Verification Matrix

Use these checks when this audit turns into implementation.

### Frontend

```bash
cd web
bun test __tests__/result-equity-chart.test.ts __tests__/alpha-frontend.test.ts
bun test __tests__/chat-message-display.test.ts __tests__/chat-turn-artifact-ux.test.ts
bun run build
```

Metrics to record:

- `/chat` first-load JavaScript before/after;
- gzip total for the chat route chunks;
- duplicate `/me` request count on `/chat?conversation=...`;
- React Profiler commit time on a restored long conversation;
- completed result card chart still renders after dynamic import.

### Backend Runtime

```bash
poetry run pytest tests/test_chat_stream_contract.py \
  tests/perf/test_backtest_infra_benchmark.py \
  tests/perf/test_render_internet_benchmark.py -q
```

Metrics to record:

- first byte;
- first SSE event;
- first token;
- full stream time;
- OpenRouter receipt waterfall;
- Supabase call count before first event;
- context packet duration and status.

### Backtest And Workflow

```bash
poetry run pytest tests/test_api_import_boundary.py \
  tests/perf/test_backtest_infra_benchmark.py \
  tests/section3/test_engine_simulation.py -q --no-cov

poetry run python scripts/benchmarks/backtest_infra_benchmark.py \
  --case equity_1_symbol_7y_1d_buy_hold \
  --case equity_5_symbol_7y_1d_buy_hold \
  --output-dir /tmp/argus-backtest-cache-bench
```

Metrics to record:

- workflow queued-to-started;
- dependency/tool load;
- provider fetch calls and total time;
- engine compute net/total;
- chart build time;
- result readout time;
- peak RSS;
- result equality before/after any cache or lazy import.

### Database

```sql
select calls, round(mean_exec_time::numeric, 2) as mean_ms, rows, query
from pg_stat_statements
where query ilike any(array[
  '%conversations%',
  '%messages%',
  '%backtest_jobs%',
  '%backtest_runs%',
  '%search%'
])
order by total_exec_time desc
limit 20;

explain (analyze, buffers)
select id
from public.backtest_jobs
where status = 'queued'
limit 11;

explain (analyze, buffers)
select *
from public.backtest_runs
where user_id = '<user_uuid>'
  and conversation_id = '<conversation_uuid>'
  and status = 'completed'
order by created_at desc
limit 1;
```

## Decision Summary

For controlled alpha, performance work should be focused and disciplined:
instrument the experience, verify the workflow tier, and take only the small
wins that improve default chat or backtest perception without changing product
semantics.

For guest mode, performance becomes a launch gate: database pagination/search,
workflow latency, first-token latency, and frontend bundle shape must be measured
and kept inside explicit thresholds.
