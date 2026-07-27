# Task 7 report: exact indexed Search execution

## Status

Complete and independently committable.

The persistent Search path no longer sends one seven-source candidate statement
through the two-second statement ceiling. Ordinary Omnisearch now performs one
bounded statement per source on one pooled connection, then preserves the
existing global merge/rank/cursor behavior. Idea Ledger browse/filter uses one
bounded Idea statement, and exact ledger group counts remain a separate
aggregate.

No public response field, cursor meaning, rank tuple, grouping rule, artifact
identity, Guest rule, RLS policy, interpreter/provider path, or frontend
production file changed.

## Root cause and implementation

The prior candidate SQL normalized and ranked all seven owned sources in one
statement. On the deterministic 12,000-row-per-source owner it took:

- first page: **3,628.624 ms**
- deep page: **3,755.315 ms**

The production-like pool keeps `statement_timeout=2000`, so the endpoint failed
20/20 samples with HTTP 500 before returning a row.

Task 7:

- replaces per-row `regexp_split_to_table` token splitting with parameterized
  per-token `LIKE` predicates;
- retains the canonical normalization expression as the exact final predicate,
  including one- and two-character tokens;
- runs seven fixed candidate statements in the same pool connection/transaction
  instead of one timeout-prone combined statement;
- limits and payload-hydrates each source independently;
- resolves ordinary cursors through direct owner/query/workspace-scoped primary
  key probes;
- removes the superseded combined candidate/pivot builders;
- batches latest Decision state hydration only for the bounded returned Ideas;
- keeps Decision-linked Evidence hydration bounded and owner-scoped;
- gives filtered/empty Idea Ledger browse its own bounded Idea query and direct
  cursor pivot; and
- retains the exact ledger aggregate outside candidate limits, so group counts
  never become candidate- or filter-relative.

The seven ordinary candidate queries, optional Idea/Decision hydrations, and
ledger aggregate all run serially on the connection yielded by one
`pool.connection(...)` context. There is no parallel database fan-out or second
pool.

## Forward migration

`20260727144043_add_search_trigram_indexes.sql` enables `pg_trgm` in the
extensions schema and adds six normalized-expression GIN indexes:

1. Conversations
2. Strategies
3. Collections
4. completed Runs
5. Ideas
6. EvidenceArtifacts

The expressions are the same checked-in Python-3.10-compatible normalizer used
by the reader. Partial predicates retain existing visibility/completion rules.
The migration adds no function, RPC, view, materialized view, generated column,
grant, or RLS change.

A proposed Decision index was discarded: its joined Decision/Evidence plan did
not select it. Decision search retains the exact joined predicate and existing
indexes rather than carrying speculative schema.

Rollback is explicit and independently understandable:

```sql
drop index if exists public.idx_evidence_search_norm_trgm;
drop index if exists public.idx_ideas_search_norm_trgm;
drop index if exists public.idx_backtest_runs_search_norm_trgm;
drop index if exists public.idx_collections_search_norm_trgm;
drop index if exists public.idx_strategies_search_norm_trgm;
drop index if exists public.idx_conversations_search_norm_trgm;
```

The runtime commit and migration can be reverted together to restore the prior
exact reader.

## TDD evidence

Initial focused RED, before the correction:

```text
3 failed

- row regexp token splitting remained
- the generic pivot_only scan remained
- the Search trigram migration was missing
```

The first real-Postgres run then found a missing token binding in the exact
ledger aggregate. That regression failed closed with:

```text
psycopg.ProgrammingError: query parameter missing: token_0_pattern
```

The token bindings were added without changing the aggregate contract.

Focused unit/static GREEN:

```text
15 passed
```

Real Postgres Search/index/RLS GREEN after reset/reseed:

```text
20 passed
```

Additional focused proofs cover:

- arbitrary short token `x`;
- mixed `alpha x` all-token matching;
- a Decision query split across Decision note and Evidence digest;
- first/middle/final/empty pages;
- equal timestamps plus deletion between page requests;
- direct cursor pivots and fail-closed missing/foreign pivots;
- filtered Idea Ledger cursor pages and exact group counts;
- Guest workspace filtering before limits;
- completed-Run and all P1 artifact identities;
- deterministic latest-Decision ties;
- owner isolation; and
- NUL-safe normalization.

## Query-plan proof

The selective 12,000-row/source probe (`12000`) proved all six retained GIN
indexes. Before the migration, each source examined 12,000 candidates and
removed 11,999:

| Source | Before ms | After ms | Candidate rows after |
| --- | ---: | ---: | ---: |
| Conversations | 176.304 | 0.907 | 1 |
| Strategies | 172.733 | 0.224 | 1 |
| Collections | 108.849 | 0.147 | 1 |
| Runs | 145.489 | 0.222 | 1 |
| Ideas | 161.666 | 0.157 | 1 |
| Evidence | 224.895 | 0.505 | 1 |

Every retained index appears in its post-migration plan.

For the deliberately common `alpha` fixture, every owned row is a true match.
Each source statement still completes below the unchanged two-second ceiling:

| Source | First-page ms | Returned candidates |
| --- | ---: | ---: |
| Conversations | 304.468 | 21 |
| Strategies | 493.815 | 21 |
| Collections | 213.190 | 21 |
| Runs | 387.942 | 21 |
| Ideas | 257.173 | 21 |
| Evidence | 558.996 | 21 |
| Decisions | 397.863 | 21 |

The max is **558.996 ms** and the seven-statement sum is **2,613.447
ms**. A large deep cursor also keeps every statement below two seconds; max
**619.190 ms**, sum **3,052.314 ms**.

Honest limitation: an all-matching predicate necessarily returns all 12,000
index matches to PostgreSQL's rank step. This slice bounds application-visible
rows and every database statement, and removes nonselective client reads, but
does not claim volume-constant physical scans for a predicate that truly matches
the complete owner corpus. Selective plans are physically bounded by the
retained indexes.

## Endpoint measurement

Fixture:

- 12,000 rows per large-owner Search source;
- 64 rows per small-owner Search source;
- sequential uncached requests;
- 20 samples;
- two-second database statement timeout;
- no transcript text, raw user id, token, credential, interpreter call, or
  provider call in evidence.

Final Search result:

| Metric | p50 | p95 | Max |
| --- | ---: | ---: | ---: |
| Database | 2,793.825 ms | 2,839.269 ms | 2,842.919 ms |
| Projection/route residual | 174.792 ms | 209.892 ms | 227.525 ms |
| Serialization | 0.133 ms | 0.168 ms | 0.260 ms |
| Total endpoint | 2,978.517 ms | 3,005.038 ms | 3,017.991 ms |

- HTTP status: **200 in 20/20**
- query count: **10 in every sample**
- returned database rows: **193 in every sample**
- response items: **20**
- continuation cursor: present

The fixed ten-query ledger path is:

1. seven candidate-source statements;
2. one returned-Idea latest-state batch;
3. one returned-Decision Evidence batch; and
4. one exact ledger aggregate.

The same final-head benchmark records the issue's seeded uncached Message
endpoint at **33.705 ms p95 total**, below the **250 ms** target.

## Migration and security proof

- Complete migration chain reset from zero: passed.
- New migration applied during reset: passed.
- Six-index catalog check: passed.
- RLS remains enabled on all affected tables: passed.
- Authenticated role has no durable direct SELECT grant change: passed.
- Transaction-local authenticated-role owner/other isolation across affected
  tables: passed.
- No hosted or shared Supabase project was touched.

## Other verification

```text
Search gateway delegation: 3 passed
Search API contracts: 8 passed
Frontend Omnisearch/Idea Ledger hydration: 80 passed
Ruff: passed
Ruff format: passed
Mypy (Search reader): passed
git diff --check: passed
```

The modularity check completed. It reports the inherited
`supabase_gateway.py` budget violation; Task 7 does not edit that file. The
Search reader is 1,374 lines after removing the superseded combined builders.

## Files changed

- `src/argus/domain/postgres_search_reader.py`
  - Exact per-token indexed candidate reads, direct cursor pivots, bounded
    per-source execution, bounded Idea hydration, and bounded Idea Ledger
    browse.
- `supabase/migrations/20260727144043_add_search_trigram_indexes.sql`
  - Six query-plan-proven normalized-expression GIN indexes and private
    `pg_trgm` enablement.
- `tests/test_search_bounded_reads.py`
  - Query shape, fixed budget, direct pivot, mixed-token, and bounded hydration
    tests.
- `tests/test_search_postgres.py`
  - Exact matching, pagination, deletion, owner/Guest scope, identity, ledger,
    scale, and plan proofs.
- `tests/test_bounded_read_indexes.py`
  - Static migration/rollback/no-public-surface proof.
- `tests/test_bounded_read_indexes_postgres.py`
  - Catalog, RLS, grant, and authenticated owner-isolation proof.

## Browser QA

No browser was launched by Task 7. Production frontend code and public API
shapes are unchanged, and the relevant frontend hydration contracts pass.
Release-captain exact-head browser/API QA remains the integration gate.
