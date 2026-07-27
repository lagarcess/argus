# History malformed-cursor compatibility fix

## Outcome

Persistent History now rejects two cursor spellings that the starting
all-row implementation and memory path treated as invalid:

- an ISO timestamp without a timezone offset; and
- a UUID that is valid only after Python normalizes braces or uppercase text.

Both checks run in `PostgresHistoryReader.list_rows()` before pool acquisition
and raise the existing `HistoryCursorError`. The History API therefore keeps
its existing `400 validation_error` / `Invalid cursor.` response.

No emitted cursor, public payload, order, pivot query, candidate query,
archive/delete behavior, Guest behavior, or canonical legacy token changed.

## Reachability and root cause

The finding is reachable by any authenticated registered user with a crafted
opaque History cursor. Before the fix:

```text
naive_timestamp: accepted=True acquisitions=1 queries=2
brace_uppercase_uuid: accepted=True acquisitions=1 queries=2
```

`datetime.fromisoformat()` accepts a timezone-naive timestamp, and
`UUID(cursor_id)` accepts brace-wrapped and uppercase UUID text. The persistent
reader previously passed those normalized values to its pivot and candidate
queries. A naive datetime bound to `timestamptz` can depend on the database
session timezone. Noncanonical UUID spellings gained a persistent-mode meaning
even though Argus never emits them.

The correction requires:

- `cursor_activity_at.tzinfo` and `cursor_activity_at.utcoffset()` to be
  non-null; and
- the raw UUID text to equal `str(UUID(raw_text))`.

## TDD RED

Tests were added before production code for the timezone-naive timestamp,
brace-wrapped UUID, and uppercase UUID at both the reader and API boundary.

Command:

```bash
OPENROUTER_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest \
  tests/test_history_bounded_reads.py::test_history_cursor_rejects_timezone_naive_timestamp_before_pool_acquisition \
  tests/test_history_bounded_reads.py::test_history_cursor_rejects_noncanonical_uuid_before_pool_acquisition \
  tests/test_alpha_api_supabase.py::test_history_supabase_malformed_cursor_uses_invalid_cursor_problem_before_pool \
  -q --no-cov
```

Exact result:

```text
6 failed in 2.99s
```

The three reader cases reached the fake pool and failed with
`IndexError: pop from empty list` instead of `HistoryCursorError`. The three
route-plus-real-reader cases returned HTTP 200 instead of the existing HTTP 400
invalid-cursor response.

## GREEN and verification

The exact RED command after the minimum reader change:

```text
6 passed in 2.25s
```

Focused reader and History API matrix:

```bash
OPENROUTER_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest \
  tests/test_history_bounded_reads.py \
  tests/test_alpha_api_supabase.py \
  -k 'history' -q --no-cov
```

```text
27 passed, 84 deselected in 5.32s
```

Focused real-Postgres cursor, deleted-pivot, page-deletion, and owner-scope
matrix against the lane-local disposable Postgres 17 stack:

```bash
ARGUS_DISPOSABLE_DATABASE_URL=<lane-local-loopback-dsn> \
poetry run pytest tests/test_history_postgres.py \
  -k 'cursor or pivot or deletion or owner_scope' -q --no-cov
```

```text
4 passed, 27 deselected in 0.75s
```

Quality evidence:

```text
Ruff check: passed
Ruff format check (reader, bounded-reader tests, real-Postgres tests): passed
mypy src/argus/domain/postgres_history_reader.py: passed
```

`tests/test_alpha_api_supabase.py` has two unrelated pre-existing formatter
diffs; piping the exact `HEAD` version through the current Ruff formatter also
returns nonzero. Ruff's proposed diff does not touch the new malformed-cursor
test. Those unrelated lines are intentionally not reformatted in this bounded
commit.

## Rollback

Revert the single fix commit. There is no migration, schema state, public API
change, external write, or hosted state to unwind.

## Concerns and remaining gates

- The fix intentionally does not compare the token timestamp with the pivot
  row timestamp. Soft-deleted pivots must keep using the cursor's immutable
  timestamp boundary.
- Canonical lowercase-hyphenated UUID tokens and timezone-aware ISO timestamps
  remain accepted, including the existing `+00:00` legacy form.
- The full issue-level exact-head API/browser, performance, and promotion gates
  remain release-captain work. This backend-only correction performs no browser
  journey, provider call, hosted Supabase mutation, merge, push, or PR action.
