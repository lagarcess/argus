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
20/20 HTTP 200 samples, p95 total **31.085 ms** against the **250 ms** target.

Search remains unresolved and is not hidden by this commit. Its normalized
source scans still exceed the production-like two-second statement timeout:
20/20 samples returned HTTP 500, with p95 database time **2,008.348 ms**. The
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

## Review correction

A post-commit review reproduced the deployed large Conversation deep-page plan
with the exact PostgREST OR cursor:

```text
Index Scan using idx_conversations_active_page
root rows: 21
physical rows: 4,022
rows removed by filter: 4,001
shared buffers: 139
execution: 0.311 ms
```

The original harness used an equivalent row-value comparison. That comparison
let PostgreSQL turn the cursor into a tighter index bound and incorrectly
reported 21 physical rows. The committed PostgREST builder emits an explicit OR
tree, so the original deep-page scan claim was not valid.

The correction also found that the Message context witness used the wrong page
boundary. The real first page includes one earlier History message and ends at
page-message 50, while a large deep page after position 8,000 ends at 8,051.
The original harness used positions 51 and 8,000.

The corrected harness now:

- uses the exact committed Conversation and Message OR disjunctions;
- uses the actual end-of-page boundary for reload and lifecycle witnesses;
- captures the Conversation pivot query separately;
- drops all three kept indexes only inside the pre-index measurement
  transaction, then rolls back; and
- replaces decoded-payload re-serialization with timing around the actual
  `starlette.responses.JSONResponse.render` boundary.

No migration, runtime query, index, RLS, cursor, or response contract changed.

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
count. Conversation and Message use the exact committed PostgREST OR
disjunctions. History and Search import their exact committed private SQL.
UUID-shaped values are replaced in raw plans before they are written.

For corrected pre-index plans, the harness drops the three kept indexes inside
one database transaction, captures all plans, and rolls the transaction back.
The immediate catalog read returned all three indexes, proving no catalog
drift.

The important first-page baseline is:

| Query | Returned rows, small/large | Max physical rows, small/large | Shared buffers, small/large | Execution ms, small/large |
| --- | ---: | ---: | ---: | ---: |
| Conversation | 21 / 21 | 64 / 12,000 | 17 / 322 | 0.103 / 1.568 |
| Message candidate | 51 / 51 | 52 / 52 | 8 / 7 | 0.052 / 0.037 |
| History candidates | 84 / 84 | 12,064 / 12,064 | 3,596 / 39,401 | 8.791 / 63.616 |
| Search candidates | 147 / 147 | 772,096 / 144,768,000 | 22,142 / 3,113,832 | 49.869 / 6,551.450 |
| Search ledger | 4 / 4 | 12,064 / 12,064 | 741 / 738 | 3.140 / 174.925 |

Returned rows and statement counts are bounded, but the Conversation and
Search physical work grew with fixture volume. History and ledger work also
remain volume-sensitive even though the database returns a fixed candidate
budget. Deep Conversation and Message pages remain cursor-depth sensitive. A
`Limit` was therefore not treated as proof of bounded physical work.

## One-index-at-a-time decisions

Each candidate was created alone, analyzed, measured using the same queries,
and either kept or dropped before the next candidate.

### Kept

| Index | Exact large plan evidence | Decision |
| --- | --- | --- |
| `idx_conversations_active_page` on `(user_id, pinned desc, updated_at desc, id desc) where deleted_at is null` | First page: 12,000 physical rows, 322 buffers, 1.568 ms became 21 rows, 4 buffers, 0.017 ms. Exact deep OR page: 11,992 physical rows, 320 buffers, 1.428 ms became 4,022 rows, 139 buffers, 0.311 ms. | Keep. It exactly serves the active order and materially reduces first and deep work. It does not make deep work constant: 4,001 newer rows are still filtered because of the committed OR cursor shape. |
| `idx_messages_reload_artifact_page` on `(user_id, conversation_id, created_at, id)` with the assistant/artifact superset predicate | Exact deep reload: 12,001 physical rows, 399 buffers, 1.708 ms became 50 partial-index rows, 5 buffers, 0.018 ms. Exact deep lifecycle: 12,001 rows, 399 buffers, 1.202 ms became 50 rows, 5 buffers, 0.011 ms. First-page improvement is smaller: 55 to 26 physical rows. | Keep. One partial superset index sharply bounds deep artifact witness scans while exact value checks remain query-owned. The separate Message candidate page remains cursor-depth sensitive. |
| `idx_decision_notes_idea_latest` on `(user_id, idea_id, updated_at desc, id desc)` | Search first page: 144,768,000 max physical rows, 3,113,832 buffers, 6,551.450 ms became 12,064 rows, 41,832 buffers, 3,597.019 ms. Deep page changed from 96,499,936 max rows and 5,709.939 ms to 12,064 rows and 3,762.459 ms. | Keep. It removes the 12,000-by-12,000 latest-Decision scan. The deep pivot selects the index and removes its sort, but still examines up to 12,064 rows. |

The Decision index is independently useful, but it does not make Search
acceptable. The remaining seven source normalizers still scan 12,064 rows per
source. Search candidate execution remains about 3.6 seconds without a
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

Those rejected measurements are first-page runs and do not depend on the
corrected cursor expression. Every rejected index was dropped. Static migration
tests allow exactly three `CREATE INDEX` statements, and the post-correction
catalog contains only the three kept Task 6 indexes.

## Final plan state

The complete migration chain was reset from zero, fixtures were reseeded, and
plans were recaptured from that exact head:

| Query | Returned rows, small/large | Max physical rows, small/large | Shared buffers, small/large | Execution ms, small/large |
| --- | ---: | ---: | ---: | ---: |
| Conversation | 21 / 21 | 21 / 21 | 5 / 4 | 0.117 / 0.017 |
| Message candidate | 51 / 51 | 52 / 52 | 14 / 7 | 0.123 / 0.032 |
| Message reload artifact | 1 / 1 | 26 / 26 | 3 / 3 | 0.077 / 0.025 |
| History candidates | 84 / 84 | 12,064 / 12,064 | 3,596 / 39,401 | 10.081 / 64.082 |
| Search candidates | 147 / 147 | 12,064 / 12,064 | 5,758 / 41,832 | 31.550 / 3,597.019 |
| Search ledger | 4 / 4 | 12,064 / 12,064 | 741 / 738 | 3.302 / 174.586 |

Exact large deep-page comparison:

| Query | Pre-index physical rows / buffers / ms | Post-index physical rows / buffers / ms | Remaining sensitivity |
| --- | ---: | ---: | --- |
| Conversation candidate | 11,992 / 320 / 1.428 | 4,022 / 139 / 0.311 | The OR cursor filters 4,001 newer rows. |
| Conversation pivot | 1 / 3 / 0.009 | 1 / 3 / 0.007 | Constant primary-key lookup; unrelated to the new index. |
| Message candidate | 8,053 / 268 / 0.770 | 8,053 / 268 / 0.709 | Unchanged and cursor-depth sensitive. |
| Message reload artifact | 12,001 / 399 / 1.708 | 50 / 5 / 0.018 | Bounded by matching artifact rows, not page depth. |
| Message lifecycle artifact | 12,001 / 399 / 1.202 | 50 / 5 / 0.011 | Bounded by matching artifact rows, not page depth. |
| History candidates | 12,064 / 27,374 / 46.378 | 12,064 / 27,374 / 45.807 | Unchanged merged-source volume sensitivity. |
| Search candidates | 96,499,936 / 2,077,573 / 5,709.939 | 12,064 / 41,832 / 3,762.459 | Normalized source scans remain volume-sensitive. |

The plan harness issues exactly one statement for each candidate, pivot, or
ledger measurement. First and deep cursor-page proofs are captured for
Conversation, Message, History, and Search; Conversation, Search, and History
deep pivots are captured separately. Existing real-Postgres suites cover first,
middle, final, equal-timestamp, deletion/lifecycle, invalid pivot, and
cross-owner cases.

History has no Task 6 index claim: its final runtime is acceptable for the
seeded endpoint sample, but its remaining volume-sensitive merged-source work
is visible above. Search is the explicit unresolved owner.

## Uncached endpoint measurements

The application cache was disabled. Each route was sampled 20 times against
the large owner fixture. Database time includes only instrumented PostgREST or
private Postgres execution/fetch time. Serialization is timed inside the actual
`starlette.responses.JSONResponse.render` call. Route/response residual is
`total - database - JSONResponse.render`; it is an upper bound that includes
route logic, artifact projection, response-model conversion, TestClient
transport, and scheduler overhead. It is not presented as isolated artifact
projection time.

| Endpoint | HTTP status | Queries / DB rows | DB p50 / p95 ms | Route/response residual p50 / p95 ms | JSON render p50 / p95 ms | Total p50 / p95 ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Conversation | 20 × 200 | 1 / 21 | 2.070 / 3.184 | 1.488 / 1.639 | 0.034 / 0.045 | 3.575 / 5.109 |
| Message | 20 × 200 | 11 / 80 | 23.372 / 26.093 | 2.712 / 3.788 | 0.074 / 0.167 | 26.167 / **31.085** |
| History | 20 × 200 | 1 / 84 | 59.749 / 64.526 | 5.050 / 5.478 | 0.108 / 0.132 | 64.633 / 68.664 |
| Search | 20 × 500 | 1 / 0 | 2,007.338 / **2,008.348** | 4.575 / 7.691 | 0 / 0 | 2,011.843 / **2,017.274** |

Message passes the 250 ms p95 gate by 218.915 ms. Its 11 queries are the
current bounded page/context/hydration contract and its 80 database rows are
constant for the measured limit and completed-job context.

The successful endpoints recorded exactly one `JSONResponse.render` call per
sample. Search recorded none because the unhandled database timeout is turned
into TestClient's plain 500 response outside that JSON rendering boundary;
therefore its JSON render value is correctly zero, not an estimate.

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

The final catalog test reconfirms that persistent grants are still false. A
second catalog read immediately after the transactional pre-index capture
returned all three Task 6 indexes, proving the temporary drops rolled back.

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

### Review RED and correction

The review reproduction was the evidence-level RED:

```text
reported deep Conversation physical rows: 21
exact committed OR cursor physical rows: 4,022
```

Inspection traced the mismatch to `row(pinned, updated_at, id) < row(...)` in
the ignored harness. The committed gateway instead creates a nested PostgREST
OR filter. Replacing the row comparison with that exact OR, and correcting the
Message context boundary, reproduced the reviewer result. The corrected
pre/post captures then proved:

```text
Conversation deep: 11,992 -> 4,022 physical rows
Message reload deep: 12,001 -> 50 physical rows
Message lifecycle deep: 12,001 -> 50 physical rows
Search first: 144,768,000 -> 12,064 max physical rows
```

All three keep decisions remain supported, but no report claim now says deep
Conversation or Message candidate work is constant.

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

Exact pre-index plan recapture with transactional rollback:

```bash
eval "$(supabase --workdir temp/issue-232/local-project status -o env 2>/dev/null)" &&
ARGUS_DISPOSABLE_DATABASE_URL="$DB_URL" \
poetry run python temp/issue-232/task6_measure_plans.py \
  --without-kept-indexes \
  --output temp/issue-232/task6-exact-pre-index-plans.json
```

Exact reset-head post-index plan recapture:

```bash
eval "$(supabase --workdir temp/issue-232/local-project status -o env 2>/dev/null)" &&
ARGUS_DISPOSABLE_DATABASE_URL="$DB_URL" \
poetry run python temp/issue-232/task6_measure_plans.py \
  --output temp/issue-232/task6-exact-post-index-plans.json
```

Result: both passed; summaries and UUID-sanitized raw plans were written under
the ignored Task 6 directory. The catalog immediately afterward still contained
all three kept indexes.

Endpoint benchmark:

```bash
eval "$(supabase --workdir temp/issue-232/local-project status -o env 2>/dev/null)" &&
ISSUE232_SUPABASE_URL="$API_URL" \
ISSUE232_SERVICE_ROLE_KEY="$SERVICE_ROLE_KEY" \
ARGUS_DISPOSABLE_DATABASE_URL="$DB_URL" \
ISSUE232_REPORT_PATH="temp/issue-232/task6-endpoint-benchmark-render-boundary.json" \
poetry run python temp/issue-232/measure_baseline.py
```

Result: 20 samples per endpoint with sequential instrumentation of the actual
`JSONResponse.render` boundary; detailed results are in the endpoint table
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
  tests/test_bounded_read_indexes_postgres.py \
  temp/issue-232/task6_measure_plans.py \
  temp/issue-232/measure_baseline.py
poetry run ruff format --check \
  tests/test_bounded_read_indexes.py \
  tests/test_bounded_read_indexes_postgres.py \
  temp/issue-232/task6_measure_plans.py \
  temp/issue-232/measure_baseline.py
git diff --check
```

Result: Ruff passed, all four files are formatted, and `git diff --check`
passed.

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
  p95 is 68.664 ms. None of the isolated History candidates earned a migration.
- Conversation deep pages still filter rows proportional to cursor depth under
  the committed OR predicate; the index reduces but does not eliminate that
  work.
- Message candidate deep pages remain cursor-depth sensitive. The partial
  artifact index bounds reload/lifecycle witness scans, not the candidate page.
- The modularity script remains red only on the inherited
  `supabase_gateway.py` budget.
- One inherited database-lint warning remains in an unchanged function.
- The disposable stack is seeded and running. Its fixture can be fully removed
  with the exact local reset command above.

The original three-index migration/tests commit remains independently
revertible. This follow-up changes only durable evidence; the ignored harness
and raw measurement files stay local to the isolated acceptance stack.
