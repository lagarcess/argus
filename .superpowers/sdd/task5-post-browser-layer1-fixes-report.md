# Task 5 Post-Browser Layer 1 Fixes

## Outcome

Implemented the two confirmed Layer 1 fixes as one bounded, independently
committable delta:

1. Concurrent first-load profile bootstrap now uses duplicate-safe create
   semantics and re-reads the canonical winning profile.
2. Unsupported-strategy response options render once on their owning assistant
   message and no longer mirror into the composer after either a live turn or
   reload.

No public API, schema, RLS, lifecycle vocabulary, dependency, model, runtime
architecture, or provider behavior changed.

## Branch and Base

- Branch: `codex/always-progresses-continuity`
- Starting SHA: `5fdcbffd31dd45cd45a73e2548446d3871bc4eca`

The worktree was clean before this slice. Only the files listed below were
changed.

## Confirmed Root Causes

### Concurrent profile creation

`SupabaseGateway.get_or_create_profile_for_auth_user` performed a read followed
by a plain insert. Two concurrent first requests could both observe no profile,
then the losing request would surface the profile primary-key conflict instead
of returning the profile created by the winner.

### Duplicated unsupported-strategy actions

The final turn correctly attached typed unsupported-strategy actions to the
assistant message, but also copied the same actions into composer state.
Reload hydration repeated that ownership mistake by deriving composer actions
from the latest assistant action list. The same three response options could
therefore appear twice.

## TDD Red Evidence

### Backend

Command:

```bash
poetry run pytest tests/test_alpha_api_supabase.py::test_gateway_profile_bootstrap_rereads_winner_after_concurrent_create -q --no-cov
```

Result before implementation: `1 failed`. The new regression reproduced the
plain-insert race and surfaced:

```text
RuntimeError: duplicate key value violates unique constraint profiles_pkey
```

from `supabase_gateway.py`.

### Frontend

Command:

```bash
cd web
bun test __tests__/chat-turn-artifact-ux.test.ts __tests__/chat-message-hydration.test.ts
```

Result before implementation: `2 failed`. The regressions required the missing
live/reload composer-ownership seam:

```text
SyntaxError: Export named 'latestInputActions' not found
SyntaxError: Export named 'visibleComposerResponseActions' not found
```

The tests then exposed two stale test-fixture/source assertions while turning
green; those assertions were updated to use the actual typed
`select_response_option` contract and the new narrow composer filter.

## Implementation

### Backend

- Replaced plain profile insert with an `id`-conflict upsert using
  `ignore_duplicates=True`.
- When a concurrent winner causes the create response to be empty, re-read by
  the authenticated owner id and return that canonical profile.
- Preserved the existing admin-promotion behavior.
- Kept unrelated Supabase errors fail-closed; no broad exception handler was
  added.

### Frontend

- Added a narrow typed filter for generated action ids beginning with
  `unsupported-strategy-`.
- Applied the filter to live composer state, reload-derived composer state, and
  final composer rendering.
- Left the assistant message action list unchanged, so all three typed
  alternatives remain adjacent to their owning response.
- Preserved exact `source_assistant_id`, `option_id`, and
  `replacement_values` payloads.
- Preserved coverage and unsupported-timeframe response options in the
  composer.

## Files Changed

- `src/argus/domain/supabase_gateway.py`
  - Duplicate-safe profile bootstrap and canonical re-read.
- `tests/test_alpha_api_supabase.py`
  - Concurrent-create regression and updated bootstrap mock contract.
- `web/components/chat/ChatInterface.tsx`
  - Narrow unsupported-strategy composer ownership filter.
- `web/__tests__/chat-message-hydration.test.ts`
  - Reload regression for three unique assistant-owned strategy alternatives.
- `web/__tests__/chat-turn-artifact-ux.test.ts`
  - Live-turn ownership, preservation, and exact-payload regression.
- `web/__tests__/alpha-frontend.test.ts`
  - Existing source-contract assertions updated for the new composer helper.

## Verification Evidence

### Backend focused contract

```bash
OPENROUTER_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest tests/test_alpha_api_supabase.py -q --no-cov
```

Result: `76 passed, 1 warning in 6.88s`.

The warning is an existing Starlette per-request-cookie deprecation warning.

### Backend lint

```bash
poetry run ruff check \
  src/argus/domain/supabase_gateway.py \
  tests/test_alpha_api_supabase.py
```

Result: `All checks passed!`

### Frontend focused regression

```bash
cd web
bun test \
  __tests__/chat-recovery-display.test.ts \
  __tests__/chat-message-hydration.test.ts \
  __tests__/chat-turn-artifact-ux.test.ts \
  __tests__/alpha-frontend.test.ts
```

Result: `132 pass, 0 fail`.

### Frontend full suite

```bash
cd web
bun test __tests__
```

Result: `467 pass, 0 fail`.

### Frontend lint

```bash
cd web
bun run lint
```

Result: passed with no findings.

Targeted ESLint for all touched frontend files also passed with no findings.

### Frontend production build

```bash
cd web
bun run build
```

Result: passed. Next.js compiled, type-checked, and generated all static pages.
The build emitted the existing Node `DEP0205` deprecation warning for
`module.register()`.

### Diff integrity

```bash
git diff --check
```

Result: passed.

## Browser QA

Not performed in this slice. Browser use was explicitly outside the delegated
scope; these two changes were prompted by already-confirmed post-browser
findings. The frontend regressions cover both the live-turn and reload ownership
paths. A later browser checkpoint may visually confirm that the three strategy
alternatives appear only under the owning assistant message.

## Complexity Reassessment and Rollback

The final change remains proportional:

- one duplicate-safe persistence operation plus one conditional canonical
  re-read;
- one narrow action-ownership predicate reused across live, reload, and render
  paths;
- no new state machine, API shape, database object, or compatibility layer.

Rollback is file-local: revert this commit to restore the previous plain insert
and composer action behavior. No data migration or cleanup is required.

## Known Caveats

- No hosted Supabase, live provider, live eval, or browser run was performed,
  per scope.
- The full backend repository suite was not run; the complete 76-test Supabase
  API contract file was used as the proportional backend gate.

## Commit Readiness

This slice is independently committable. It contains only the two requested
behavior fixes, their focused regressions, source-contract maintenance, and this
verification report.
