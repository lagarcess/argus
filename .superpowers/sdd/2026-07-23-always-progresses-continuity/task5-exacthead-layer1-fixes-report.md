# Task 5 Exact-HEAD Layer 1 Correction Report

## Scope and baseline

- Starting SHA: `42e719274510297fa4f7ba1ab624a3a4d176fd7f`.
- Worktree started clean on `codex/always-progresses-continuity`.
- Scope is limited to ordinary-turn admission/running ordering, idempotent
  terminal finalization replay, the adjacent user Retry tap target, one
  forward-only SQL migration, and directly covering tests.
- Run/backtest ownership remains message-only/job-owned. No polling, hosted
  database, shared database, paid eval, browser QA, deploy, push, PR, or merge
  is in this correction.

Focused baseline before new tests:

```text
OPENROUTER_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest tests/test_chat_turn_route_matrix.py \
  tests/test_chat_stream_contract.py \
  tests/test_chat_turn_lifecycle.py \
  tests/test_chat_turn_lifecycle_migration.py -q --no-cov
```

Result: `142 passed in 4.56s`.

```text
cd web
bun test __tests__/chat-lifecycle-source.test.ts
```

Result: `13 pass, 0 fail`.

## Recorded red evidence

### Admission and running must precede the first workflow operation

```text
OPENROUTER_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest tests/test_chat_turn_route_matrix.py \
  -k 'ordinary_turn_is_running_before_first_workflow_operation' \
  -q --no-cov
```

Result: `3 failed, 51 deselected in 1.94s`.

Observed assertion output:

```text
ordinary_text:
  actual ['workflow_acquire', 'admit']
  expected ['admit', 'running', 'workflow_acquire']

response_option:
  actual ['admit', 'workflow_acquire']
  expected ['admit', 'running', 'workflow_acquire']

durable_retry:
  actual ['admit', 'workflow_acquire']
  expected ['admit', 'running', 'workflow_acquire']
```

### Memory terminal finalization replay must be a no-op

```text
OPENROUTER_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest tests/test_chat_turn_lifecycle.py \
  -k 'finalization_exact_replay' -q --no-cov
```

Result: `2 failed, 47 deselected in 0.58s`.

Both completed and recoverable-failure replays raised:

```text
ValueError: Chat-turn finalization conflict.
src/argus/domain/chat_turn_lifecycle.py:393
```

The completed replay intentionally supplied different valid usage limits.
Settlement configuration is not replay identity; exact lifecycle/message
replay must return the existing message without charging again.

### Forward migration contract is absent

```text
OPENROUTER_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest tests/test_chat_turn_lifecycle_migration.py \
  -k 'forward_finalizer_migration_replays_exact_terminal_tuple_without_charge' \
  -q --no-cov
```

Result: `1 failed, 9 deselected in 0.11s`.

Observed assertion output:

```text
assert IDEMPOTENT_FINALIZATION_MIGRATION.exists()
AssertionError: assert False
```

### Real isolated PostgreSQL replay must be a no-op

Fresh owned container:
`argus-task5-exacthead-replay-019f91be`, using
`public.ecr.aws/supabase/postgres:17.6.1.140` on local port `55007`.
All `22` pre-correction migrations applied in lexical order with
`ON_ERROR_STOP=1`. The existing `supabase_db_argus-qa` stack was not touched.

```text
ARGUS_DISPOSABLE_DATABASE_URL=postgresql://postgres:REDACTED@127.0.0.1:55007/postgres \
OPENROUTER_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest tests/test_chat_turn_lifecycle_postgres.py \
  -k 'finalization_exact_replay' -q --no-cov
```

Result: `2 failed, 36 deselected in 0.20s`.

Both completed and recoverable-failure replays raised:

```text
psycopg.errors.SerializationFailure:
Chat-turn finalization conflict.
```

### Adjacent user Retry control must have a 44px minimum tap target

```text
cd web
bun test __tests__/chat-lifecycle-source.test.ts
```

Result: `13 pass, 1 fail`.

Observed assertion output:

```text
Expected to contain: "min-h-11"
Received: className="inline-flex min-h-9 ..."
```

## Green verification

### Production outcome

- Every non-deterministic ordinary turn now commits its accepted lifecycle and
  transitions it to `running` before workflow acquisition, checkpoint reads, or
  checkpoint writes.
- Response-option selection and server-owned durable Retry follow the same
  order. A forced workflow-acquisition failure ends in exactly one
  `recoverable_failed` lifecycle with zero usage, route-receipt, or cost-ledger
  rows.
- Deterministic onboarding/cancel controls preserve their prior timing: they
  avoid workflow initialization and transition to `running` inside the
  accepted-turn stream. Run remains message-only/job-owned.
- Memory and PostgreSQL finalizers return the existing assistant message for
  an exact direct terminal replay. They do not append or settle usage again.
  Changed immutable message or terminal tuple conflicts.
- Terminal-payload validation remains before replay. In particular,
  recoverable-failure finalization still rejects non-null settlement and leaves
  usage unchanged. A completed exact replay may supply different valid
  settlement limits because settlement configuration is not replay identity.
- The adjacent user Retry control now has a 44px `min-h-11` minimum target.
- The forward migration was generated by:

  ```text
  supabase migration new idempotent_chat_turn_finalization
  ```

  The CLI created
  `20260724214312_idempotent_chat_turn_finalization.sql`. Migration `00003`
  remains unchanged.

### Focused green

```text
OPENROUTER_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest tests/test_chat_turn_route_matrix.py \
  -k 'ordinary_turn_is_running_before_first_workflow_operation' \
  -q --no-cov
```

Result: `3 passed, 51 deselected`.

```text
OPENROUTER_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest tests/test_chat_turn_lifecycle.py \
  -k 'finalization_exact_replay' -q --no-cov
```

Result: `2 passed, 47 deselected`.

```text
OPENROUTER_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest tests/test_chat_turn_lifecycle_migration.py \
  -k 'forward_finalizer_migration_replays_exact_terminal_tuple_without_charge' \
  -q --no-cov
```

Result: `1 passed, 9 deselected`.

```text
cd web
bun test __tests__/chat-lifecycle-source.test.ts
```

Result: `14 pass, 0 fail`.

### Full directly relevant hermetic gates

```text
OPENROUTER_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest \
  tests/test_chat_turn_route_matrix.py \
  tests/test_chat_request_admission.py \
  tests/test_chat_runtime_reload_guardrails.py \
  tests/test_allowance_accounting.py \
  tests/test_chat_stream_contract.py \
  tests/test_chat_turn_lifecycle.py \
  tests/test_chat_turn_lifecycle_migration.py \
  -q --no-cov
```

Result: `239 passed in 6.38s`.

Fresh disposable PostgreSQL:

- The red container was removed and recreated from zero.
- All `23` checked-in migrations, including the CLI-generated forward
  migration, applied in lexical order with `ON_ERROR_STOP=1`.
- No shared or hosted database was used.

```text
ARGUS_DISPOSABLE_DATABASE_URL=postgresql://postgres:REDACTED@127.0.0.1:55007/postgres \
OPENROUTER_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest tests/test_chat_turn_lifecycle_postgres.py -q --no-cov
```

Result: `38 passed in 0.72s`.

```text
ARGUS_DISPOSABLE_DATABASE_URL=postgresql://postgres:REDACTED@127.0.0.1:55007/postgres \
OPENROUTER_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest tests/test_allowance_accounting_postgres.py -q --no-cov
```

Result: `15 passed in 0.38s`.

The owned container `argus-task5-exacthead-replay-019f91be` was removed after
verification. Its exact name is absent and local port `55007` has no listener.

### Frontend, build, and static gates

```text
cd web
bun test __tests__
```

Result: `468 pass, 0 fail`.

```text
cd web
bun run lint
bun run build
```

Result: ESLint passed; Next production build and TypeScript passed. Build
reported only the existing Node `DEP0205` deprecation warning.

```text
poetry run python scripts/check_modularity_budget.py
poetry run pytest tests/test_modularity_budget.py -q --no-cov
```

Result: no modularity violations; `6 passed`.

```text
poetry run ruff check \
  src/argus/api/routers/agent.py \
  src/argus/domain/chat_turn_lifecycle.py \
  tests/test_chat_turn_route_matrix.py \
  tests/test_chat_turn_lifecycle.py \
  tests/test_chat_turn_lifecycle_postgres.py \
  tests/test_chat_turn_lifecycle_migration.py
git diff --check
```

Result: all checks passed.

One earlier Ruff invocation was run from `web/` with repo-root-relative paths
and produced six `E902 No such file or directory` invocation errors. The same
command was immediately rerun from the repository root and passed; this was not
a source or test failure.

## Actual-diff complexity reassessment

The production correction remains proportionate:

- route ordering reuses the existing admission object and lifecycle hooks;
- deterministic controls and Run retain their prior ownership/timing;
- replay uses the existing lifecycle tuple and immutable message comparison;
- PostgreSQL replaces one existing function forward-only without a new table,
  column, lifecycle status, RLS policy, API shape, or durable settlement state;
- the frontend change is one existing Tailwind size token.

The larger test delta is intentional parity proof. Existing `_accept`,
`_message`, `_finalize`, and route gateway helpers are reused. Completed and
recoverable finalization cannot be safely collapsed because their settlement
rules differ. Ordinary text, response-option selection, and server-owned Retry
cannot be collapsed because each takes a distinct admission path. No redundant
production machinery or clear reusable setup remains to remove without hiding
one of those contracts.

## Files changed

- `src/argus/api/routers/agent.py`: admit and mark non-deterministic ordinary
  turns running before workflow/checkpoint work.
- `src/argus/domain/chat_turn_lifecycle.py`: exact terminal replay no-op in the
  memory twin while retaining strict payload validation.
- `supabase/migrations/20260724214312_idempotent_chat_turn_finalization.sql`:
  forward-only idempotent finalizer replacement.
- `web/components/chat/ChatMessage.tsx`: 44px adjacent Retry target.
- Directly covering backend, migration, PostgreSQL, and frontend tests listed
  in the diff.

## Browser QA

Not performed in this worker correction. The release captain owns the exact-HEAD
browser matrix and will rerun the corrected slices after this commit.

## Caveats and handoff

- No browser QA, live provider call, paid eval, hosted/shared database mutation,
  deploy, push, PR, or merge was performed.
- The release captain still owns exact-HEAD browser proof and promotion.
- This correction is coherent and independently committable on top of
  `42e719274510297fa4f7ba1ab624a3a4d176fd7f`.
