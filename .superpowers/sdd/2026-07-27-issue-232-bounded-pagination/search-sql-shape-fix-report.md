# Search SQL-shape and cursor fix report

## Status

Complete and independently committable.

Search now binds arbitrary normalized query tokens as one `text[]` parameter
and performs an exact all-token recheck with `unnest(...)`. The generated SQL
has a fixed shape as token count grows. When a query has a token of at least
three characters, one longest token is also bound as the existing trigram-index
anchor; it narrows candidates but does not replace the exact recheck.

Search also rejects noncanonical cursor UUID text before acquiring a database
connection. Public response fields, cursor encoding, rank order, migrations,
RLS, routes, frontend code, provider behavior, and History code did not change.

## Confirmed root causes

The reader previously rendered each token into every Search predicate. Because
the Unicode normalizer is a large SQL expression, repeating it once per token
amplified generated SQL linearly.

The seven ordinary source statements measured:

| Unique tokens | Rendered bytes | Normalizer occurrences |
| ---: | ---: | ---: |
| 1 | 147,705 | 31 |
| 20 | 827,226 | not separately recorded |
| 100 | 3,688,746 | not separately recorded |
| 400 | 14,422,446 | 4,021 |
| 500 | 18,000,346 | not separately recorded |

Across ordinary reads, direct pivots, Idea browse/pivot, and the ledger
aggregate, 500 tokens rendered 33,955,030 bytes.

`UUID(...)` also accepted alternate spellings such as brace-wrapped and
uppercase UUIDs. The reader passed those forms through to the pool even though
the cursor contract requires canonical lowercase hyphenated UUID text.

## TDD evidence

The SQL-shape regression failed before the implementation:

```text
poetry run pytest \
  tests/test_search_bounded_reads.py::test_search_sql_shape_is_constant_as_token_count_grows \
  -q --no-cov

assert (14422446, 4021) == (147705, 31)
```

The canonical UUID regression also failed before the implementation:

```text
poetry run pytest \
  tests/test_search_bounded_reads.py::test_search_noncanonical_cursor_uuid_fails_before_database_read \
  -q --no-cov

2 failed: DID NOT RAISE SearchCursorError
```

After the fix, both regressions pass. The cursor regression additionally
asserts that the pool recorded zero executions.

## Implementation

- Replaced generated `token_0_pattern`, `token_1_pattern`, and later
  placeholders with one bound `token_patterns::text[]`.
- Kept exact all-token substring semantics with:

  ```sql
  not exists (
      select 1
      from unnest(%(token_patterns)s::text[]) as required(pattern)
      where not coalesce(normalized_haystack like required.pattern, false)
  )
  ```

- Kept one optional bound `anchor_pattern` on the indexed candidate
  expression. One- and two-character tokens remain part of the exact recheck
  and are never dropped.
- Applied the same constant-shape contract to ordinary source reads, direct
  cursor pivots, Idea browse/pivots, and exact Idea Ledger counts.
- Required `str(UUID(cursor_id)) == cursor_id` before the pool boundary.

The seven ordinary source statements now render exactly 160,346 bytes and 73
normalizer occurrences for 1, 20, 100, 400, or 500 long tokens. All query
variants together render 316,539 bytes at both 1 and 500 tokens. Parameter
payload size still grows with the user's distinct tokens, but generated SQL
does not.

## Real-Postgres proof

The complete Search Postgres suite passed against the disposable local stack:

```text
17 passed
```

It covers multi-token completeness, mixed short tokens, NUL handling,
first/middle/final pages, cursor pivots, Guest scope, artifact identity, exact
ledger counts, and statement budgets.

The deterministic 12,000-row-per-source selective probe used query `12000`.
The disposable stack initially lacked the already-committed trigram-index
migration; applying that existing migration locally restored the intended
schema without a repository edit. All six indexed sources then selected their
expected GIN index:

| Source | Execution ms | Root rows | Expected GIN index |
| --- | ---: | ---: | --- |
| Conversations | 1.129 | 1 | `idx_conversations_search_norm_trgm` |
| Strategies | 0.325 | 1 | `idx_strategies_search_norm_trgm` |
| Collections | 0.285 | 1 | `idx_collections_search_norm_trgm` |
| Runs | 0.318 | 1 | `idx_backtest_runs_search_norm_trgm` |
| Ideas | 0.527 | 1 | `idx_ideas_search_norm_trgm` |
| Evidence | 0.361 | 1 | `idx_evidence_search_norm_trgm` |
| Decisions | 444.066 | 1 | intentionally no Search GIN index |

Every statement remained below the unchanged two-second ceiling. An actual
`alpha 12000` reader call returned exactly one row in each of the seven Search
groups, proving the anchor does not weaken all-token matching.

The deterministic fixture was removed after measurement:

```text
users=0
conversations=0
decisions=0
```

No hosted or shared Supabase project was touched.

## Final verification

```text
Focused Search unit/Postgres/API: 34 passed
Ruff format: passed
Ruff: passed
Mypy (Search reader): passed
git diff --check: passed
```

The first combined verification encountered the existing Python-3.10
`datetime.fromisoformat` fixture flake when Postgres emitted five fractional
digits. The exact failed test passed on rerun, and the complete 34-test command
then passed cleanly.

## Scope and rollback

Production change:

- `src/argus/domain/postgres_search_reader.py`

Regression coverage:

- `tests/test_search_bounded_reads.py`
- `tests/test_search_postgres.py`

Rollback is `git revert` of the isolated commit. There is no migration, public
contract, deployment, or data rollback for this correction.

Honest limitation: exact all-token matching still requires PostgreSQL to check
every true candidate returned by the anchor. A query that genuinely matches an
owner's full corpus is not a volume-constant physical scan. This fix removes
token-count-dependent SQL construction and preserves the bounded statement,
candidate, and payload contracts established by Task 7.
