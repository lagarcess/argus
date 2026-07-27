# Task 8B report: specialized persistent History source SQL

## Outcome

Implemented the query-only History specialization from Task 8B. Persistent
History no longer uses the dynamic `input` CTE or unspecialized four-field
source predicates. It now selects one of 36 finite cached SQL variants keyed by
archive state, delete state, cursor presence, pivot pin tier, and pivot type
rank.

The default active Run and Chat sources are physically page-proportional at both
64 and 12,000 owner rows. The public merged order, cursor token, response
projection, grouping, owner scope, and query count are unchanged.

This commit is independently reversible, but it is not complete physical
acceptance for every History state:

- Strategy and Collection still need exact state-and-order indexes.
- Archived/deleted Chat still needs an exact state-and-order index.
- Run parent archive/delete filtering is cross-table; a Conversation index alone
  cannot guarantee page-proportional Run work. That boundary needs a separate
  Task 8C design/stop decision rather than denormalization inside this slice.

No migration or speculative index was added.

## TDD evidence

Initial SQL-shape RED:

```text
9 failed
ImportError: cannot import name '_candidate_sql'
```

The focused tests were added before production code. They require:

- no dynamic `input` CTE;
- finite cached variants;
- direct archive/delete predicates;
- exact `<`, `<=`, and tuple-`<` source predicates for all four pivot ranks;
- separate pinned and unpinned bounded leaves; and
- no pinned Run cursor predicate when the pivot is pinned.

Exact physical RED against the existing 64/12,000-row disposable fixture:

| Current dynamic query | Root rows | Run | Run parent | Chat | Message EXISTS | Strategy | Collection |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Large first | 84 | 12,064 | 12,064 | 12,000 | 24,128 | 12,000 | 12,000 |
| Large deep | 84 | 12,064 | 12,064 | 12,000 | 24,128 | 12,000 | 12,000 |

Raw sanitized evidence:

- `temp/issue-232/task8b-red-current-plans.json`

A second TDD loop added a real pinned-pivot execution test. It failed with:

```text
UndefinedTable: missing FROM-clause entry for table "chat"
```

The smallest fix changed only the outer derived-table order columns. The
pinned-tier test and complete real-Postgres suite then passed.

A third TDD loop required first-page pin tiers to be separately bounded before
the source limit. It failed against the single unsplit leaf, then passed after
the first-page variant used the same two-leaf shape.

## Implementation

`src/argus/domain/postgres_history_reader.py` now:

- builds SQL only from trusted internal source columns, boolean variants, and
  ranks;
- binds the owner, cursor timestamp/id, and source limit as named parameters;
- caches at most 40 SQL strings for the 36 reachable variants;
- removes `input`, `not has_cursor`, and dynamic boolean filter branches;
- specializes a source in the pivot's pin tier by source rank:
  - lower type rank uses `activity_at <= cursor_activity_at`;
  - equal type rank uses `(activity_at, id) < (cursor_activity_at, cursor_id)`;
  - higher type rank uses `activity_at < cursor_activity_at`;
- excludes pinned rows after an unpinned cursor;
- returns all unpinned rows as the lower tier after a pinned cursor;
- keeps Run always unpinned and omits its cursor predicate after a pinned pivot;
- bounds pinned and unpinned Chat, Strategy, and Collection leaves before an
  outer source limit;
- keeps exact Collection counts after the bounded Collection candidate CTE; and
- keeps the final merged order
  `(pinned, activity_at, type_rank, id) DESC`.

The candidate query remains one statement. A first page remains one statement;
a cursor page remains one pivot statement plus one candidate statement.

## Preserved behavior

The focused unit, API, memory, Guest, and real-Postgres matrices preserve:

- first, middle, final, and empty pages;
- equal timestamps and UUID ordering;
- deletion between requests without duplicates;
- soft-deleted pivot resolution using the token timestamp;
- missing, foreign, and ambiguous pivot failure;
- owner isolation;
- all Run statuses;
- default-only orphan Runs;
- parent archive/delete filtering before the Run limit;
- Chat Message `EXISTS` before the Chat limit;
- raw Chat, Strategy, Collection, Run, and result-card identity;
- Strategy symbols and payload;
- exact owner-scoped Collection membership counts; and
- Guest returning before cursor parsing or registered multi-source reads.

All 36 archive/delete/cursor/pin/rank SQL variants prepare successfully against
the disposable Postgres database.

## Query-plan proof

The durable real-Postgres regression seeds independent owners at 64 and 12,000
rows and measures the exact runtime SQL for first and deep pages with source
limit 21.

| Active source plan | Small first | Small deep | Large first | Large deep |
| --- | ---: | ---: | ---: | ---: |
| Run | 22 | 22 | 22 | 22 |
| Run parent | 56 | 22 | 22 | 22 |
| Chat | 56 | 21 | 13 per leaf | 21 |
| Message `EXISTS` | 56 | 21 | 13 per leaf | 21 |
| Root returned rows | 42 | 42 | 42 | 42 |

Every tracked Run/parent/Chat/Message scan is at most
`4 * source_limit = 84`. The large plans select:

- `idx_backtest_runs_user_created`;
- `idx_conversations_active_page`;
- `idx_messages_conversation_created`; and
- the Conversation primary key for Run-parent lookups.

The exact full-source Task 6 fixture confirms the same default active result:

| Active plan | Run | Run parent | Chat | Message `EXISTS` | Strategy | Collection | Execution |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Large first | 22 | 22 | 13 per leaf | 13 per leaf | 11,992 | 11,992 | 17.197 ms |
| Large deep | 22 | 22 | 21 | 21 | 11,992 | 11,992 | 10.745 ms |

Sanitized evidence:

- `temp/issue-232/task8b-specialized-plans.json`

### Honest state-variant boundary

A transaction repartitioned the same 12,000 synthetic Conversations and their
Run parents evenly across archive/delete states, measured every first/deep
variant, then rolled back.

| State | Run/parent max | Chat max | Message max | Strategy max | Collection max |
| --- | ---: | ---: | ---: | ---: | ---: |
| Default active | 85 | 42 | 21 | 11,992 | 11,992 |
| Deleted active | 3,000 | 3,000 | 2,998 | 6,000 | 6,000 |
| Archived active | 3,000 | 3,000 | 2,998 | 11,992 | 11,992 |
| Archived deleted | 3,000 | 3,000 | 2,998 | 6,000 | 6,000 |

The 85-row default Run value is one row above the strict 84-row budget because
the artificial state partition makes every fourth parent eligible. The normal
all-active fixture stays at 22. The archived/deleted results prove that query
specialization alone cannot close every physical state gate with the current
indexes.

Sanitized evidence:

- `temp/issue-232/task8b-state-plans.json`

The transaction rolled back. No fixture state, schema, index, grant, RLS policy,
or hosted database changed.

## Verification

Focused SQL/unit:

```text
16 passed
```

Real disposable Postgres, including the 64/12,000-row plan regression:

```text
15 passed
```

API, memory, gateway, Recents, and Guest History:

```text
15 passed, 197 deselected
```

Quality:

```text
Ruff check: passed
Ruff format check: passed
mypy src/argus/domain/postgres_history_reader.py: passed
git diff --check: passed
```

The repository modularity script still reports only the inherited
`supabase_gateway.py` budget violation: 2,335 lines versus its stale 2,113-line
limit. Task 8B does not modify that file.

Provider credentials were blanked for the backend/API matrix. No interpreter,
market-data provider, hosted Supabase, or shared `argus-qa` path was called.

## Browser QA

Not performed in this backend-only slice. The public API and frontend production
code are unchanged. Exact-head authenticated browser/API QA remains owned by the
issue-level integration gate.

## Files changed

- `src/argus/domain/postgres_history_reader.py`
  - finite cached source-specific SQL and named bound parameters.
- `tests/test_history_bounded_reads.py`
  - SQL-shape, rank, pin-tier, cache, and parameter regressions.
- `tests/test_history_postgres.py`
  - pinned-tier execution, all-variant preparation, and 64/12,000 exact plans.

Ignored local tooling/evidence under `temp/issue-232/` contains synthetic
aggregate plan data only. It contains no transcript text, raw user identifiers,
tokens, or credentials.

## Rollback and remaining gate

Rollback is one commit revert. There is no migration, public object, or external
state to unwind.

Task 8C must measure and decide the smallest safe correction for:

1. Strategy state-and-order scans;
2. Collection state-and-order scans;
3. archived/deleted Chat state-and-order scans; and
4. the cross-table Run parent-state physical bound.

Do not claim full History physical acceptance until those exact plans pass or
the cross-table Run boundary is explicitly escalated. Do not denormalize parent
state, change the cursor, weaken archive/delete semantics, or add speculative
indexes to hide this evidence.
