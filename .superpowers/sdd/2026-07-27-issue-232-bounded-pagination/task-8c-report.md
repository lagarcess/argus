# Task 8C report: History state-filter physical bounds

## Outcome

Implemented the smallest query/index correction for the remaining History
state-filter plan gaps.

- Run parent state is now checked by an owner-scoped correlated scalar subquery
  while the Run index remains the ordered driving scan.
- Deleted Conversations now have the same stable
  `(pinned, updated_at, id)` keyset order as active Conversations.
- Strategy and Collection History sources now have owner-scoped ordered indexes.
- The deleted Conversation index also bounds archived/deleted Chat candidates,
  so no separate Chat index is needed.

Public cursor meaning, merged order, grouping, owner scope, payload/artifact
identity, API fields, RLS, grants, and frontend behavior are unchanged. There is
no denormalized parent state, generated column, function, RPC, view, cache, or
materialized view.

Starting integration/task head: `9c144867facd33396c3f734c5dc461c5d20fc35a`.

## TDD RED

The physical regressions were added before the migration.

On the isolated 12,000-row owner fixture:

- the deleted Conversation deep keyset page returned 21 rows only after
  24,130 physical Conversation rows;
- all eight large History archive/delete and first/deep variants failed;
- Strategy and Collection scans reached 6,000 to 24,128 rows;
- deleted Chat/Message paths reached owner-sized scans; and
- Run/parent state paths inspected 85 to 88 rows to produce 21 rows.

The combined RED was:

```text
9 failed, 8 passed
```

The migration contract RED was:

```text
1 failed
History state-page migration is missing or ambiguous
```

The first complete focused run after implementation found one test-fixture
expectation, not a runtime regression:

```text
69 passed, 1 failed
test_history_run_and_chat_plans_are_page_bounded_at_64_and_12k
assert 84 <= 42
```

The scale fixture now includes all four bounded History sources, so the merged
root can contain `4 * 21 = 84` candidates instead of the former two-source 42.
The Run, parent, Chat, and Message per-node assertions were already green. The
smallest correction changed only the aggregate root expectation to 84. The
full focused suite then passed.

## Run query decision

Three shapes were measured on the same 12,000-row four-way parent-state
partition:

| Run parent-state shape | Run rows | Parent probes | Execution |
| --- | ---: | ---: | ---: |
| Existing left join | 85-86 | 85-86 | 0.08-0.18 ms |
| Correlated scalar with `OFFSET 0` | 85-86 | 85-86 | 0.08-0.10 ms |
| Correlated `EXISTS` with `OFFSET 0` | 85-86 | 85-86 | 0.08-0.09 ms |

The original scout-derived four-page threshold of 84 was too exact for a
four-way state filter: depending on ordering, the 21st eligible parent can
naturally occur at row 85 or 86. The release captain therefore classified the
85-88-row result as stable page-proportional work, not an owner-sized scan.

The durable regression uses an internal five-page sentinel budget
(`5 * source_limit = 105`) for this dense four-way fixture and proves it at both
64 and 12,000 owner rows. This is test methodology, not a public product target.
Sparse or final Run state pages can inherently inspect more ordered Runs because
parent archive/delete state is cross-table and is intentionally not denormalized
onto `backtest_runs`.

The correlated scalar form was retained because it makes the bounded ordered
Run scan the explicit driver and prevents join flattening. `coalesce` preserves
the existing behavior exactly:

- a missing/null parent is included only in the default active state;
- a missing/null parent is excluded from archived/deleted states;
- an existing parent must match the owner and requested archive/delete state;
- all Run statuses, cursor/order behavior, and Run/result identity are unchanged.

## One-index-at-a-time proof

Each candidate was built and measured alone before the cumulative measurement.

| Candidate | Before | Candidate alone |
| --- | ---: | ---: |
| Deleted Conversation ordered partial index | 12,064-24,128 | 37-42 |
| Strategy owner/pin/activity order | 12,064 | 33-42 |
| Collection owner/pin/activity order | 12,064 | 33-42 |

The cumulative exact runtime plan on 12,000 rows:

| State | Run/parent | Chat | Message `EXISTS` | Strategy | Collection | SQL execution |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Active | 85 | 37-42 | 19-21 | 33-42 | 33-41 | 0.385-0.463 ms |
| Deleted | 88 | 38-42 | 19-21 | 34-41 | 34-42 | 0.346-0.349 ms |
| Archived | 87 | 38-41 | 19-21 | 33-42 | 33-41 | 0.321-0.333 ms |
| Archived deleted | 86 | 37-41 | 19-21 | 34-41 | 34-42 | 0.314-0.341 ms |

Every source returns at most 21 candidates per bounded leaf, and the merged root
returns at most 84 rows before the existing service projection.

Rejected index designs:

- per-state partial Strategy/Collection indexes add duplicate write/storage
  cost; one ordered index already bounds both states;
- boolean-expression state indexes are unnecessary because filtering at most
  roughly two ordered rows per returned Strategy/Collection row stays bounded;
- an additional Chat-state index is unnecessary because active Chat uses the
  existing active Conversation page index and deleted Chat uses the new deleted
  Conversation page index; and
- no Run parent-state index can replace the primary-key parent probe without
  denormalizing state onto Run, which is outside the approved boundary.

Sanitized evidence:

- `temp/issue-232/task8c-index-candidates.json`
- `temp/issue-232/task8c-final-state-plans.json`
- `temp/issue-232/task8c_measure_index_candidates.py`

These files contain aggregate synthetic plan data only. They contain no
transcript text, raw user identifiers, tokens, or credentials.

## Migration and security

Forward migration:

`supabase/migrations/20260727161406_add_history_state_page_indexes.sql`

It creates exactly:

- `idx_conversations_deleted_page`;
- `idx_strategies_history_page`; and
- `idx_collections_history_page`.

Rollback is three independent `drop index if exists` statements recorded in the
migration. The migration changes no table, column, constraint, policy, grant,
function, trigger, RPC, or view.

The lane-isolated disposable Supabase project was reset from zero through the
complete chain and applied the new migration successfully. Post-reset catalog
tests proved all expected indexes exist, current predicates select them, RLS
remains enabled, direct authenticated table grants remain absent, and temporary
authenticated-role grants still preserve owner isolation. No hosted or shared
Supabase project was touched.

## Verification

Focused History/keyset/index suite after reset:

```text
70 passed in 102.03s
```

This includes:

- all finite History SQL/unit checks;
- History semantics and real Postgres plans;
- small/12,000-row four-state first/deep plan regressions;
- deleted Conversation deep keyset;
- existing keyset reader coverage;
- migration catalog and exact selected-index checks; and
- authenticated-role owner-isolation/RLS checks.

Additional gates:

```text
Ruff check: passed
Ruff format check: passed
mypy src/argus/domain/postgres_history_reader.py: passed
git diff --check: passed
supabase db reset: passed
```

The modularity check reports only the inherited
`src/argus/domain/supabase_gateway.py` violation (2,335 lines versus its
2,113-line limit). Task 8C does not modify that file.

## Browser QA

Not performed in this backend query/index slice. The public API, projection,
cursor, response model, and frontend production code are unchanged. Exact-head
authenticated browser/API QA remains owned by the issue-level integration gate.

## Files changed

- `src/argus/domain/postgres_history_reader.py`
  - owner-scoped non-flattenable correlated Run parent-state check.
- `supabase/migrations/20260727161406_add_history_state_page_indexes.sql`
  - three plan-proven ordered indexes and explicit rollback.
- `tests/test_history_postgres.py`
  - 64/12,000 four-state first/deep physical-plan regression.
- `tests/test_postgres_keyset_reader_postgres.py`
  - 12,000-row deleted Conversation deep-keyset regression.
- `tests/test_bounded_read_indexes.py`
  - exact private index-only migration contract.
- `tests/test_bounded_read_indexes_postgres.py`
  - catalog, selected-plan, RLS, grant, and owner-isolation coverage.

## Caveats and committability

This slice is independently reversible and committable as one coherent unit:
the correlated query makes Run ownership/state evaluation explicit, and the
single forward migration closes the measured Conversation/Chat/Strategy/
Collection physical gaps.

The honest remaining physical caveat is the sparse/final cross-table Run state
case described above. Closing that theoretical case absolutely would require
duplicating mutable Conversation state onto Run or changing History semantics,
both explicitly forbidden here. The measured dense 64/12,000 fixtures prove
volume stability without either change.
