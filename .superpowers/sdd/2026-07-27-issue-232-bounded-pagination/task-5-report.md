# Task 5 report: bounded Omnisearch and exact Idea Ledger

## Status

Complete and independently committable.

Base HEAD: `6a40d7c3c205d664d89054120b8a9180a1d74594`

Task commit: this report is part of the task commit; resolve its immutable SHA
with `git rev-parse HEAD` after commit. A commit cannot embed its own SHA.

The persistent Omnisearch path now ranks and limits candidates in private,
parameterized Postgres SQL. The public response models, rank tuple, cursor
token, object identities, completed-Run rule, Guest scope, and Idea Ledger group
contract remain unchanged.

## Implementation

- Added a private `PostgresSearchReader` that reuses the existing bounded
  History connection pool; no second pool or public database surface was added.
- Added a checked-in SQL normalizer expression generated for the repository's
  pinned Python 3.10 Unicode semantics. Runtime startup does not scan Unicode.
- Pushed owner, query, cursor, decision-state, ledger-browse, and Guest
  conversation scope into the database read.
- Applied the exact existing rank tuple before each source limit:
  pinned, exact title, exact symbol, type, activity timestamp, basic text rank,
  and descending UUID.
- Limited each of the seven sources independently to public `limit + 1`, then
  retained typed Python response assembly.
- Hydrated Decision-linked Evidence in one bounded, owner-scoped batch.
- Computed exact Idea Ledger counts on a separate query-matched aggregate before
  the optional decision-state result filter.
- Kept Guest ledger groups empty and excluded Strategy/Collection rows before
  candidate limits.
- Resolved cursor pivots inside the same owner/query/filter/workspace scope and
  failed closed on missing, foreign, cross-type ambiguous, or timezone-naive
  pivots.

No migration, index, public RPC/view, API schema, frontend, runtime/interpreter,
provider, PostHog, or deployment configuration changed.

## Files changed

- `src/argus/domain/postgres_search_reader.py`
  - Private seven-source SQL reader, scoped pivot recovery, bounded Decision
    evidence hydration, exact ledger aggregate, and typed raw-row result.
- `src/argus/domain/search_sql_text.py`
  - Checked-in Python-3.10-compatible SQL normalization expression.
- `src/argus/domain/supabase_gateway.py`
  - Injects the Search reader with the History pool and replaces the all-row
    PostgREST implementation with a fail-closed delegation.
- `src/argus/api/routers/search.py`
  - Decodes and pushes the existing cursor/filter/Guest scope before reads,
    maps reader cursor failures to the existing problem response, and renders
    exact ledger counts.
- `tests/test_search_bounded_reads.py`
  - Query-count, fail-closed pivot, projection, and bounded owner-scoped
    Decision evidence unit proofs.
- `tests/test_search_postgres.py`
  - Unicode, matching/ranking, empty optional text, pagination, scope,
    identity, ledger, scale, and `EXPLAIN ANALYZE` plan proofs.
- `tests/test_alpha_api_supabase.py`
  - Bounded argument forwarding and cursor-error mapping.
- `tests/test_guest_conversation_policy.py`
  - Guest workspace scope is passed before the database limit.
- `tests/test_history_bounded_reads.py`
  - Search reader injection reuses the History pool.
- `tests/test_supabase_gateway.py`
  - Private reader delegation and fail-closed persistence behavior.

## TDD evidence

Initial RED command:

```bash
ARGUS_DISPOSABLE_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:62332/postgres \
PYTEST_ADDOPTS=--no-cov poetry run pytest \
  tests/test_search_bounded_reads.py \
  tests/test_search_postgres.py \
  tests/test_history_bounded_reads.py \
  tests/test_alpha_api_supabase.py::test_search_supabase_pushes_bounded_cursor_and_filter_to_gateway \
  tests/test_alpha_api_supabase.py::test_search_reader_cursor_failure_maps_to_invalid_cursor_problem \
  tests/test_guest_conversation_policy.py::test_guest_search_is_limited_to_current_workspace_artifacts \
  -q
```

Result: **RED**, exit `1`: `19 failed, 5 passed in 2.50s`.

Expected failures showed the private reader/normalizer were absent, persistence
did not inject a Search reader, `/search` still requested `limit=None`, and the
database cursor/filter/Guest scope was not forwarded. The first command attempt
named the Guest test incorrectly and collected no tests; it is not counted.

First implementation run: `12 passed, 3 failed`. No production SQL fault was
hidden by those three failures:

- the fake owner assertion compared a `UUID` parameter to a string;
- a supposed plain Evidence fixture also carried exact `AAPL` provenance;
- the direct reader Guest fixture omitted the explicit `guest_scope=True`.

Those fixtures were corrected without weakening production semantics. A later
rank-parity review added a focused red regression that exposed one real SQL
projection mismatch: an empty chat preview, Idea summary, or Evidence digest
did not fall back to the title like Python assembly. SQL selected the lower UUID
at an equal timestamp. `nullif(..., '')` title fallback fixed all three surfaces.

## Final green evidence

```text
82 passed
  tests/test_search_bounded_reads.py
  tests/test_search_postgres.py
  tests/test_history_bounded_reads.py
  tests/test_supabase_gateway.py

89 passed, 1 inherited deprecation warning
  tests/test_alpha_api_supabase.py

12 passed, 47 deselected
  tests/test_alpha_api.py -k search

1 passed
  Guest current-workspace Search proof

Success: no issues found in 2 source files
  mypy --follow-imports=skip on the new Search reader and SQL normalizer

All checks passed
  Ruff lint on every changed Python file

7 files already formatted
  Ruff format check on the new files and format-clean changed files

0
  residual `search-%@argus.local` disposable Auth users

clean
  git diff --check
```

The three edited legacy files reported by repository-wide Ruff format are
already non-format-clean at base:

- `src/argus/domain/supabase_gateway.py`
- `tests/test_alpha_api_supabase.py`
- `tests/test_supabase_gateway.py`

They were not bulk-formatted because that would create unrelated churn. The
new reader, normalizer, and dedicated tests are format-clean.

The repository modularity script remains red on its inherited/stale
`supabase_gateway.py` baseline (`2,300` current lines versus a `2,113` limit).
Base HEAD has `2,467` lines; this slice improves the file by 167 lines and does
not create the violation.

## Query, row, and plan budgets

- First page: one candidate SQL statement; at most three statements when both
  bounded Decision evidence hydration and ledger counts are requested.
- Cursor page: one scoped pivot plus candidates; at most four statements when
  Decision evidence and ledger counts are also needed.
- Candidate rows: at most `7 * (limit + 1)`, or 707 at the public maximum
  `limit=100`.
- Decision evidence rows: at most `limit + 1`, deduplicated and owner-scoped.
- Ledger rows: at most four stable decision-state aggregates, including zeros
  filled in Python.
- Pivot rows: exactly one is required; zero or more than one fails closed.
- Scale proof: 40 and 400 matching Strategies both used one query and returned
  exactly six rows for `source_limit=6`.
- Unicode proof: every non-NUL Unicode scalar supported by Python 3.10 plus
  2,000 deterministic random strings produced zero SQL/Python normalization
  mismatches.

The dedicated local Postgres plan proof used:

```text
EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
```

It verified at least seven inner `Limit` nodes, each with
`Actual Rows <= 6`, a merged root with `Actual Rows <= 42`, and execution below
the shared two-second statement ceiling.

## Browser QA

Not performed. This is a backend-only, response-preserving read-side slice.
Issue-level browser acceptance remains with the release captain after
integration; focused API and real-Postgres tests are Task 5's acceptance
surfaces.

## Cleanup and environment

- Reused the dedicated issue-232 local Postgres stack.
- Test identities cascade-cleaned their product rows.
- Final cleanup found zero Task 5 temporary Auth users.
- No canonical environment file or shared secret was read or modified.
- The already-running local stack was left running.

## Rollback

Revert the task commit to restore the prior Python all-row Search assembly.

## Risks and caveats

- No index or generated column was allowed in this slice. The shared pool's
  two-second statement timeout remains the fail-closed ceiling; the local plan
  proof does not claim production-scale index sufficiency.
- The checked-in normalization literals intentionally follow pinned Python 3.10
  semantics. A future Python/Unicode upgrade must regenerate and rerun the
  full-scalar parity proof.
