# Task 8A report: persistent Conversation and Message keyset reads

## Outcome

Implemented physically bounded Postgres candidate reads for finite persistent
Conversation and Message pages. The public response models and opaque cursor
meaning are unchanged. Existing non-page reads remain on their compatibility
path, and message artifact projection still runs after candidate selection.

- Starting integration SHA: `31ade709059668ce7df1ad01d2a40263ea548f61`
- Branch: `codex/issue-232-bounded-pagination`
- Schema changes: none
- New pool: none; the reader reuses `PostgresHistoryReader.pool`
- Hosted Supabase access: none

## TDD evidence

The initial focused red tests failed before implementation:

- `tests/test_postgres_keyset_reader.py`: 11 failures with
  `ModuleNotFoundError: argus.domain.postgres_keyset_reader`
- the two initial disposable-Postgres plan cases failed for the same missing
  reader
- the three gateway injection tests failed because `keyset_reader` and its
  delegation path did not exist

The final consolidated command used the lane-isolated disposable database and
blanked provider credentials:

```text
ARGUS_DISPOSABLE_DATABASE_URL=<lane-local-url> \
OPENROUTER_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest \
  tests/test_postgres_keyset_reader.py \
  tests/test_postgres_keyset_reader_postgres.py \
  tests/test_bounded_read_indexes_postgres.py \
  tests/test_supabase_gateway_pagination.py \
  tests/test_history_bounded_reads.py \
  tests/test_backtest_message_projection.py \
  tests/test_alpha_api_supabase.py \
  tests/test_chat_turn_route_matrix.py \
  tests/test_chat_turn_lifecycle_gateway.py \
  tests/test_backtest_job_by_action.py \
  tests/test_degraded_recovery_history.py \
  tests/test_supabase_gateway.py -q --no-cov
```

Result: **299 collected, 297 passed, 2 skipped, 1 inherited Starlette
deprecation warning, 28.19 seconds**.

## Implementation

### Postgres keyset reader

`src/argus/domain/postgres_keyset_reader.py` contains the cohesive SQL boundary:

- Conversation pages use exact owner scope, the requested archive/deletion
  variant, `(pinned, updated_at, id) DESC`, and `limit + 1`.
- A cursor page performs one exact owner-scoped pivot lookup and one candidate
  query. The pivot lookup intentionally has no archive/deletion predicate, so a
  soft-deleted pivot remains usable.
- A first Conversation page uses one candidate query.
- Message pages use exact owner plus conversation scope,
  `(created_at, id) ASC`, retired USER-marker filtering before `limit`, and
  `limit + 1`.
- Message cursors do not require a pivot lookup, so deletion between requests
  does not invalidate the cursor.
- SQL variants are finite and cached. UUID inputs are validated before pool
  acquisition.

### Gateway delegation

`src/argus/domain/supabase_gateway.py` injects the new reader from the existing
history pool and delegates only:

- finite Conversation pages; and
- `page=True` Message reads.

Unlimited/compatibility reads remain on the existing PostgREST path. Message
job/run hydration and context projection remain after candidate selection, so
the existing batched hydration, Guest behavior, stale-card settlement, and
single-result-owner behavior are not reconstructed or bypassed.

## Compatibility and semantic proof

Focused unit and real-Postgres coverage proves:

- first, middle, final, and empty pages;
- equal-timestamp ordering by `id`;
- a soft-deleted Conversation pivot remains valid;
- deletion between Message page requests does not duplicate rows;
- archived and deleted Conversation variants;
- missing, foreign-owner, ambiguous, malformed, and incomplete pivots fail
  closed;
- exact owner isolation;
- retired USER markers are filtered before the page bound while an assistant
  message with the same text remains visible;
- `limit + 1` continuation reads;
- the existing opaque timestamp/id cursor contract;
- reader injection shares the existing Postgres pool; and
- message job/run projection remains batched after candidate selection.

## Query-plan evidence

The tests used the exact runtime SQL under `EXPLAIN (ANALYZE, BUFFERS, FORMAT
JSON)`, with 64-row and 12,000-row fixtures and deep cursors at positions 32 and
8,000.

| Read | Fixture | Returned root rows | Maximum scanned rows | Buffer blocks | Selected index |
| --- | ---: | ---: | ---: | ---: | --- |
| Conversation active page | 64 | 21 | 21 | 4 | `idx_conversations_active_page` |
| Conversation active page | 12,000 | 21 | 21 | 4 | `idx_conversations_active_page` |
| Message page | 64 | 21 | 33 | 10 | `idx_messages_conversation_created` |
| Message page | 12,000 | 21 | 23 | 13 | `idx_messages_conversation_created` |

The requested page size was 20, so root rows were bounded to the page plus one
continuation sentinel. Query work did not grow with the 187.5x fixture-size
increase for these accepted paths.

An additional diagnostic probe found:

- archived Conversation deep page: 21 returned, 21 scanned, 45 buffers via
  `idx_conversations_active_page`;
- deleted Conversation deep page: 21 returned, 12,001 scanned, 247 buffers via
  `idx_conversations_archive_delete`.

Therefore this task does **not** claim physical acceptance for dense deleted
Conversation pages. The semantic path is correct, but that proven index gap is
owned by the separate query-plan-justified Task 8B index micro-slice. No
speculative migration is included here.

## Quality evidence

- `poetry run mypy src/argus/domain/postgres_keyset_reader.py`: success
- focused Ruff check: passed
- focused Ruff format check for new files: passed
- `git diff --check`: passed
- modularity check: the new SQL logic is extracted; the existing
  `supabase_gateway.py` remains above its inherited file budget
- whole-file Ruff formatting would change unrelated pre-existing lines in
  `supabase_gateway.py` and `tests/test_supabase_gateway_pagination.py`, so this
  slice intentionally avoids that unrelated churn
- whole-gateway mypy still reports inherited errors; the new reader itself is
  clean

## Product QA and rollback

No frontend production code changed. Exact-head authenticated browser QA remains
required at the issue integration gate; it was not duplicated inside this
backend slice.

Rollback is one independent commit revert. There is no migration, external
state, new RPC/view dependency, or public contract change to unwind.

All performance evidence is aggregate-only. It contains no transcript content,
raw user identifiers, credentials, or tokens.
