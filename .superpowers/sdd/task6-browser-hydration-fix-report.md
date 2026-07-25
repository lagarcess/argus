# Task 6 Browser Hydration Correction

## Scope

- Base: `c46114ebb25a7e27773388faa4bfaaab52c376c4`
- Owned production file: `web/components/chat/artifact-history.ts`
- Owned test file: `web/__tests__/chat-artifact-history.test.ts`
- No backend, API, schema, lifecycle vocabulary, action-admission, environment, or external-service change.

## Reproduced failure and root cause

The lane-exclusive browser checkpoint showed a non-retryable Run capacity
failure as `Could not run` before reload, but reload rehydrated the same
confirmation as `Running`.

Persisted history contained:

1. the user `run_backtest` `chat_action`; and
2. the assistant terminal with the same `chat_action` identity plus typed
   `failed_action.action_type = run_backtest`.

`confirmationActionEffectsFromApi` projected both messages as the optimistic
Run effect. It did not consult the assistant's typed `failed_action`, so the
later effect remained `running`.

## Exact-final red

Added
`persisted failed run action remains could not run after hydration normalization`.
The test uses a user Run action followed by an assistant `failed_action` with
the same `confirmation_id`, then applies the API effects and confirmation
normalization.

Command:

```text
cd web
bun test __tests__/chat-artifact-history.test.ts
```

Observed before the production correction:

```text
Expected: "could_not_run"
Received: "running"
1 tests failed
31 pass
1 fail
```

## Minimal correction

During persisted confirmation-effect projection, an assistant-authored
`failed_action` whose typed `action_type` exactly matches its persisted
confirmation `chat_action.type` now projects the existing `could_not_run`
terminal status and label.

The correction:

- does not inspect assistant prose;
- does not depend on `retryable`;
- does not trust user-authored `failed_action` metadata;
- does not apply when the two typed action identities disagree; and
- reuses the existing confirmation identity, status vocabulary, and close-card
  behavior.

## Green verification

```text
cd web
bun test __tests__/chat-artifact-history.test.ts

32 pass
0 fail
138 expect() calls
```

```text
cd web
bunx eslint components/chat/artifact-history.ts __tests__/chat-artifact-history.test.ts

exit 0
```

```text
git diff --check

exit 0
```

## Complexity reassessment

The production delta is one narrow typed projection branch. It adds no new
state, parser, helper layer, public contract, or retry path. The regression
would fail if the typed assistant terminal were ignored or incorrectly
projected back to `running`.

The slice is independently committable. The release captain should rerun the
lane-exclusive browser failure/reload journey at the resulting exact SHA to
confirm the visible card remains `Could not run` after reload.
