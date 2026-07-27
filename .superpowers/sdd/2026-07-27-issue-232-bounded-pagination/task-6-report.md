# Task 6 report: plan-proven indexes and measurement

## Outcome

Task 6 adds only three forward indexes whose current query plans showed a
material, reachable improvement:

1. `idx_conversations_active_page`
2. `idx_messages_reload_artifact_page`
3. `idx_decision_notes_idea_latest`

The migration does not add or change a function, view, RPC, generated column,
grant, RLS policy, API field, cursor, rank, group, or endpoint response.

The isolated Message endpoint passes its required uncached performance gate:
20/20 HTTP 200 samples, p95 total **32.084 ms** against the **250 ms** target.

Search remains unresolved and is not hidden by this commit. Its normalized
source scans still exceed the production-like two-second statement timeout:
20/20 samples returned HTTP 500, with p95 database time **2,008.266 ms**. The
remaining owner is the current normalized seven-source candidate query, not an
index missing from this bounded migration.

## Scope and safety

- Base: `4fdf2c870e2985f084b5eef55eafa0a6ecc33d4e`
- Isolated project only: `temp/issue-232/local-project`
- Local project id: `argus-issue-232-4e4b`
- No hosted or shared Supabase project was accessed.
- The exact isolated stack remains running for release-captain acceptance.
- Raw plans, seed tooling, and benchmark output remain ignored under
  `temp/issue-232/`.
- Durable evidence in this report contains no transcript text, raw user ids,
  credentials, provider keys, or authentication tokens.
- The measured routes are read-only database routes. Instrumentation observed
  only PostgREST and private Postgres channels; no interpreter or market-data
  provider path was invoked.

## Deterministic fixture

The seed uses two deterministic owner scopes. Counts below distinguish
per-owner source volume from totals across both owners:

| Fixture | Small owner | Large owner | Total |
| --- | ---: | ---: | ---: |
| Primary rows per source | 64 | 12,000 | 12,064 |
| Conversations | 64 | 12,000 | 12,064 |
| Messages | 128 | 24,000 | 24,128 |
| Message-page rows in measured conversation | 65 | 12,001 | 12,066 |
| Completed jobs used for Message hydration | 32 | 50 | 82 |
| Rows in each History source | 64 | 12,000 | 12,064 |
| Rows in each Search source | 64 | 12,000 | 12,064 |

The seed contains generic synthetic values and hashed fixture identities. It
can be removed completely by resetting the exact local project:

```bash
supabase --workdir temp/issue-232/local-project db reset --local
```

The stack is intentionally not stopped or reset after verification.

## Pre-index measurement

The plan harness imports the committed History and Search SQL constants and
captures:

```sql
EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
```

It records node type, selected index, actual rows, loops, rows removed, shared
buffers, sort method, planning time, execution time, and a derived physical-row
count. UUID-shaped values are replaced in raw plans before they are written.

The important first-page baseline is:

| Query | Returned rows, small/large | Max physical rows, small/large | Shared buffers, small/large | Execution ms, small/large |
| --- | ---: | ---: | ---: | ---: |
| Conversation | 21 / 21 | 64 / 12,000 | 21 / 629 | 0.180 / 1.827 |
| Message candidate | 51 / 51 | 52 / 52 | 107 / 106 | 0.176 / 0.041 |
| History candidates | 84 / 84 | 24,128 / 24,128 | 2,792 / 63,782 | 14.204 / 69.190 |
| Search candidates | 147 / 147 | 772,096 / 144,768,000 | 38,592 / 6,174,218 | 58.190 / 7,282.413 |
| Search ledger | 4 / 4 | 12,064 / 12,064 | 1,242 / 1,239 | 2.712 / 171.489 |

Returned rows and statement counts are bounded, but the Conversation and
Search physical work grew with fixture volume. History and ledger work also
remain volume-sensitive even though the database returns a fixed candidate
budget. A `Limit` was therefore not treated as proof of bounded physical work.

## One-index-at-a-time decisions

Each candidate was created alone, analyzed, measured using the same queries,
and either kept or dropped before the next candidate.

### Kept

| Index | Exact large plan evidence | Decision |
| --- | --- | --- |
| `idx_conversations_active_page` on `(user_id, pinned desc, updated_at desc, id desc) where deleted_at is null` | Deep page: 12,064 physical rows, 464 buffers, top-N sort, 3.443 ms became 21 rows, 3 buffers, no sort, 0.054 ms. Final reset proof: 21 rows, 5 buffers, 0.028 ms. | Keep. It exactly serves the active Conversation order and removes volume-growing scan/sort work. |
| `idx_messages_reload_artifact_page` on `(user_id, conversation_id, created_at, id)` with the assistant/artifact superset predicate | Reload first page: 11,950 physical rows, 393 buffers, 3.411 ms became an index lookup with 0 fixture matches, 2 buffers, 0.015 ms. Final seeded proof with a real artifact: 1 physical row, 2 buffers, 0.018 ms. Lifecycle first page also changed from 11,950 rows and 3.032 ms to 1 row and 0.012 ms. | Keep. One partial superset index serves both exact reload and lifecycle predicates while their stricter value checks stay query-owned. |
| `idx_decision_notes_idea_latest` on `(user_id, idea_id, updated_at desc, id desc)` | Search first page: 144,768,000 max physical rows, 6,174,218 buffers, 7,282.413 ms became 24,000 max rows, 42,106 buffers, 3,541.862 ms. Final reset proof was 12,064 max rows, 41,831 buffers, 3,535.503 ms. Deep page changed from 96,499,936 max rows and 6,240.361 ms to 12,064 rows and 3,750.340 ms. | Keep. It removes the 12,000-by-12,000 latest-Decision scan and also makes the deep cursor pivot use the exact latest-Decision order. |

The Decision index is independently useful, but it does not make Search
acceptable. The remaining seven source normalizers still scan 12,064 rows per
source. Search candidate execution remains about 3.5 seconds without a
statement timeout and reliably trips the two-second endpoint timeout.

### Dropped

| Rejected candidate | Large first-page evidence | Why dropped |
| --- | --- | --- |
| Full Message owner/conversation/page order | Message candidate stayed at 51 returned / 51-52 physical rows and about 0.05 ms. The existing conversation-created index already bounds the page. | No material improvement. |
| Partial Strategy History order | History remained 84 returned, 24,128 max physical rows, 39,121 buffers, 68.791 ms; the candidate was not selected. | Did not remove the merged History scans. |
| Full Strategy History order | Same 84 / 24,128 / 39,121 shape, 62.113 ms; candidate not selected. | Incidental timing only. |
| Collection History order | Same 84 / 24,128 / 39,121 shape, 64.408 ms; candidate not selected. | No plan improvement. |
| Backtest-run History order | Same 84 / 24,128 / 39,121 shape, 64.423 ms; candidate not selected. | No plan improvement. |
| Chat/History composite order | Same 84 / 24,128 / 39,121 shape, 64.870 ms; candidate not selected. | Did not remove parent, message, or merged-source work. |

Every rejected index was dropped. The post-reset catalog contains only the
three kept Task 6 indexes.

## Final plan state

The complete migration chain was reset from zero, fixtures were reseeded, and
plans were recaptured from that exact head:

| Query | Returned rows, small/large | Max physical rows, small/large | Shared buffers, small/large | Execution ms, small/large |
| --- | ---: | ---: | ---: | ---: |
| Conversation | 21 / 21 | 21 / 21 | 5 / 4 | 0.080 / 0.017 |
| Message candidate | 51 / 51 | 52 / 52 | 14 / 7 | 0.155 / 0.030 |
| Message reload artifact | 1 / 1 | 1 / 1 | 2 / 2 | 0.081 / 0.018 |
| History candidates | 84 / 84 | 12,064 / 12,064 | 3,573 / 39,378 | 8.601 / 64.479 |
| Search candidates | 147 / 147 | 12,064 / 12,064 | 5,757 / 41,831 | 32.749 / 3,535.503 |
| Search ledger | 4 / 4 | 12,064 / 12,064 | 739 / 736 | 3.369 / 175.462 |

The plan harness issues exactly one statement for each candidate or ledger
measurement. First and deep cursor-page proofs are captured for Conversation,
Message, History, and Search; the Search and History deep pivots are captured
separately. Existing real-Postgres suites cover first, middle, final,
equal-timestamp, deletion/lifecycle, invalid pivot, and cross-owner cases.

History has no Task 6 index claim: its final runtime is acceptable for the
seeded endpoint sample, but its remaining volume-sensitive merged-source work
is visible above. Search is the explicit unresolved owner.

## Uncached endpoint measurements

The application cache was disabled. Each route was sampled 20 times against
the large owner fixture. Database time includes only instrumented PostgREST or
private Postgres execution/fetch time; projection is residual route/artifact
work; serialization is measured separately using the decoded response.

| Endpoint | HTTP status | Queries / DB rows | DB p50 / p95 ms | Projection p50 / p95 ms | Serialization p50 / p95 ms | Total p50 / p95 ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Conversation | 20 × 200 | 1 / 21 | 1.679 / 2.127 | 1.447 / 1.888 | 0.005 / 0.006 | 3.204 / 3.549 |
| Message | 20 × 200 | 11 / 80 | 24.620 / 28.377 | 3.155 / 5.037 | 0.011 / 0.020 | 28.233 / **32.084** |
| History | 20 × 200 | 1 / 84 | 62.599 / 63.985 | 5.211 / 5.958 | 0.012 / 0.018 | 67.870 / 69.112 |
| Search | 20 × 500 | 1 / 0 | 2,006.797 / **2,008.266** | 4.413 / 7.363 | 0 / 0 | 2,011.548 / **2,012.626** |

Message passes the 250 ms p95 gate by 217.916 ms. Its 11 queries are the
current bounded page/context/hydration contract and its 80 database rows are
constant for the measured limit and completed-job context.

Search failure is preserved exactly: the shared private pool used
`statement_timeout=2000`, and every Search sample timed out before returning
rows. No cache, timeout increase, predicate rewrite, rank change, or weaker
target was used.

## Zero reset, catalog, grants, and RLS

The complete chain reset applied
`20260727000001_add_bounded_read_indexes.sql` successfully. The resulting
catalog contains exactly:

```text
idx_conversations_active_page
idx_decision_notes_idea_latest
idx_messages_reload_artifact_page
```

`relrowsecurity` remains true for `conversations`, `messages`, and
`decision_notes`. Persistent `authenticated` SELECT privilege remains false on
all three tables.

The real-RLS test:

1. creates two disposable Auth/Profile owners and their owned rows;
2. grants SELECT only inside an uncommitted transaction;
3. uses `set local role authenticated` and real `request.jwt.claims` for each
   owner;
4. proves each owner sees only its own Conversation, Message, and Decision;
5. rolls back the temporary grants; and
6. deletes both Auth users and dependent rows in cleanup.

The final catalog test reconfirms that persistent grants are still false.

## TDD evidence

The focused tests were written before the migration:

```bash
poetry run pytest tests/test_bounded_read_indexes.py -q --no-cov
```

Initial result: **3 failed**. Each failure reported that the bounded-read
migration was missing.

After the migration:

```bash
eval "$(supabase --workdir temp/issue-232/local-project status -o env 2>/dev/null)" &&
ARGUS_DISPOSABLE_DATABASE_URL="$DB_URL" \
poetry run pytest \
  tests/test_bounded_read_indexes.py \
  tests/test_bounded_read_indexes_postgres.py \
  -q --no-cov
```

Final result: **6 passed**. These tests cover the exact migration surface,
catalog, unchanged RLS/grants, two-owner authenticated isolation, and current
query-predicate selection of all three indexes.

## Verification

Zero reset and reseed:

```bash
supabase --workdir temp/issue-232/local-project db reset --local
docker exec -i supabase_db_argus-issue-232-4e4b \
  psql -U postgres -d postgres -v ON_ERROR_STOP=1 \
  < temp/issue-232/task6_seed.sql
```

Result: complete chain applied; seed committed with two owners, 12,064
Conversations, 24,128 Messages, and 82 completed jobs.

Plan recapture:

```bash
eval "$(supabase --workdir temp/issue-232/local-project status -o env 2>/dev/null)" &&
ARGUS_DISPOSABLE_DATABASE_URL="$DB_URL" \
poetry run python temp/issue-232/task6_measure_plans.py \
  --output temp/issue-232/task6-post-reset-index-plans.json
```

Result: passed; the summary and UUID-sanitized raw plan evidence were written
under the ignored Task 6 directory.

Endpoint benchmark:

```bash
eval "$(supabase --workdir temp/issue-232/local-project status -o env 2>/dev/null)" &&
ISSUE232_SUPABASE_URL="$API_URL" \
ISSUE232_SERVICE_ROLE_KEY="$SERVICE_ROLE_KEY" \
ARGUS_DISPOSABLE_DATABASE_URL="$DB_URL" \
ISSUE232_REPORT_PATH="temp/issue-232/task6-endpoint-benchmark.json" \
poetry run python temp/issue-232/measure_baseline.py
```

Result: 20 samples per endpoint; detailed results are in the endpoint table
above.

Focused migration/RLS:

```text
6 passed
```

Focused pagination, History, and Search:

```bash
poetry run pytest \
  tests/test_supabase_gateway_pagination.py \
  tests/test_history_bounded_reads.py \
  tests/test_search_bounded_reads.py \
  tests/test_history_postgres.py \
  tests/test_search_postgres.py \
  -q --no-cov
```

Result without the disposable DSN: **31 passed, 29 skipped**.

The real-Postgres files were then run with the isolated DSN:

```text
27 passed
```

Message projection/API/lifecycle matrix:

```text
105 passed
```

Focused History/Search Supabase API routes:

```text
14 passed, 75 deselected
```

Database lint:

```bash
supabase --workdir temp/issue-232/local-project db lint \
  --local --schema public --level warning --fail-on error
```

Result: exit 0. It reports one inherited warning in
`public.append_conversation_message` for an unread local variable; the Task 6
migration adds no function.

Static gates:

```bash
poetry run ruff check \
  tests/test_bounded_read_indexes.py \
  tests/test_bounded_read_indexes_postgres.py
poetry run ruff format --check \
  tests/test_bounded_read_indexes.py \
  tests/test_bounded_read_indexes_postgres.py
git diff --check
```

Result: Ruff passed, both files are formatted, and `git diff --check` passed.

Modularity:

```bash
poetry run python scripts/check_modularity_budget.py
```

Result: inherited red. `src/argus/domain/supabase_gateway.py` is 2,300 lines
against its stale 2,113-line limit. Task 6 changes no production Python or
TypeScript and does not affect that count.

## Browser QA

Not performed. This is a backend-only forward-index migration with no frontend
or public response-shape change. The release captain owns issue-level browser
acceptance against the still-running isolated stack.

## Rollback

Rollback is independent of Tasks 2 through 5:

```sql
drop index if exists public.idx_decision_notes_idea_latest;
drop index if exists public.idx_messages_reload_artifact_page;
drop index if exists public.idx_conversations_active_page;
```

## Known caveats and promotion boundary

- Search remains 20/20 timeout failures under the two-second statement
  timeout. Solving its normalized-source scan requires a separate runtime query
  design/review slice; it must not be smuggled into this index commit.
- History remains physically volume-sensitive, although its 20-sample endpoint
  p95 is 69.112 ms. None of the isolated History candidates earned a migration.
- The modularity script remains red only on the inherited
  `supabase_gateway.py` budget.
- One inherited database-lint warning remains in an unchanged function.
- The disposable stack is seeded and running. Its fixture can be fully removed
  with the exact local reset command above.

Subject to review of the preserved Search follow-up, the three-index
migration, tests, and this report form one coherent, independently revertible
commit.
