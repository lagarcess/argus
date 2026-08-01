# Task 4 — Bounded conversation-activity effects owner

## Scope

- Added `web/components/chat/useConversationActivity.ts` as the single
  frontend effects owner around the existing pure activity reducer.
- Added `web/__tests__/use-conversation-activity.test.tsx` with injected
  transport and browser-effect adapters for deterministic behavior tests.
- No reducer, API, transcript-cache, recent-history, locale, or UI component
  contract was changed.

## RED

The focused test was added before the implementation.

```text
bun test __tests__/use-conversation-activity.test.tsx
Cannot find module '../components/chat/useConversationActivity'
0 pass, 1 fail, 1 error
```

The navigation-refresh case was then tightened before its implementation.

```text
Expected refresh count: 2
Received refresh count: 1
```

## GREEN

The hook/runtime now owns:

- optional activity projection merges from loaded chat history;
- bootstrap, navigation, local start/settle, focus, visibility-resume, and
  successful-mutation refreshes through the injected bounded-history refresh;
- one short poll only while a loaded canonical operation or local request is
  unresolved, with immediate idle cancellation;
- conversation-scoped presentation, aggregate, lock, current-request,
  manual-unread-guard, and announcement accessors;
- optimistic exact-cursor mark-read and mark-unread mutations, current-mutation
  response checks, one-conversation rollback, and typed success/error notices;
- inactive transcript invalidation on canonical or explicit local settlement;
- transport registration keyed by conversation and request identity, including
  account-change/logout abort and local-state reset without durable rewrites.

## Files changed

- `web/components/chat/useConversationActivity.ts` — runtime effects owner and
  React hook adapter.
- `web/__tests__/use-conversation-activity.test.tsx` — focused lifecycle,
  concurrency, mutation, cache-invalidation, selector, and account-reset proof.
- `.superpowers/sdd/2026-08-01-conversation-activity-ui/task-4-report.md` — this
  implementation and verification record.

## Verification

```text
bun test __tests__/use-conversation-activity.test.tsx __tests__/chat-transcript-session-cache.test.ts
26 pass, 0 fail

bun test
912 pass, 0 fail

bunx eslint components/chat/useConversationActivity.ts __tests__/use-conversation-activity.test.tsx
pass

git diff --cached --check
pass
```

`bunx tsc --noEmit` is not a usable repository gate in this checkout: it fails
across existing tests on the repository's `bun:test` expectation typings and an
unrelated E2E timestamp literal. The new production hook file was not named by
that diagnostic. Focused lint and the complete Bun suite are green.

## Browser QA

Not performed for this headless effects-owner slice. It adds no rendered UI and
is not wired into `ChatInterface` yet; the later integration slice owns live
browser proof for cross-conversation rendering and navigation.

## Concerns

- Mutation notices are deliberately typed rather than localized here. The
  integration owner maps them to the existing localized toast surface.
- The polling cadence remains private; tests prove only observable start/stop
  behavior as required.

## Commit readiness

Yes. The slice is independently committable and does not require a schema,
public API contract, backend runtime, or release-environment change.
