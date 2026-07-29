# Issue #245 Recents Progressive Disclosure — Implementation Plan

> Approved design: GitHub issue #245 and the founder dispatch. This plan maps
> that product decision to code and evidence; it does not create a second
> specification.

**Goal:** Make Recents a compact chat-navigation surface with a five-item
initial cap per unpinned time group, independent expansion, and explicit
cursor-bounded pagination while preserving PR #299 conversation switching.

**Authoritative base:** `origin/codex/private-alpha-next` at
`080e2458e5edb6662c8d7edb7d91258e3f978e71`.

**Constraints:** No new API shape or schema; no provider calls; no durable
browser storage; no replacement navigation/cache state machine; Draft PR
targets `codex/private-alpha-next`.

## Task 1: Prove the missing behavior red

**Files**

- Create: `web/__tests__/chat-recents.test.ts`
- Create: `web/e2e/issue-245-recents-progressive-disclosure.spec.ts`

Add deterministic tests for date grouping, the five-item cap, selected-row
visibility, independent expansion, explicit pagination, request deduplication,
cursor exhaustion, chat-only retrieval, mutations, localization, keyboard
behavior, and desktop/mobile layouts. Capture focused pre-fix failures.

## Task 2: Isolate the Recents projection

**Files**

- Create: `web/lib/chat-recents.ts`
- Modify: `web/components/chat/ChatInterface.tsx`

Map the existing bounded `/conversations` response to the sidebar's chat-only
projection. Use `updated_at` for Recents ordering, preserve the current blank
conversation exclusion, and carry the backend-owned guest expiry from the
account response. Merge cursor pages without duplicate conversation ids.

## Task 3: Add compact per-group disclosure

**Files**

- Modify: `web/components/sidebar/ChatSidebar.tsx`

Keep Pinned distinct and uncapped. Initially show at most five loaded records in
each unpinned group. Add group-local Show more/Show less controls with truthful
expanded state. When collapsed, include an active conversation beyond the cap
so navigation ownership stays visible.

## Task 4: Replace silent pagination with explicit loading

**Files**

- Modify: `web/components/sidebar/ChatSidebar.tsx`
- Modify: `web/components/chat/ChatInterface.tsx`

Remove the intersection observer. Render Load older only while a next cursor
exists, admit one request synchronously, show an honest loading state, and
settle or remove the action based on the returned cursor.

## Task 5: Localize and preserve interaction contracts

**Files**

- Modify: `web/public/locales/en/common.json`
- Modify: `web/public/locales/es-419/common.json`
- Modify focused frontend source/behavior tests

Add English and Spanish labels for expand, collapse, and pagination. Preserve
selected, attention, rename, pin/unpin, delete, reload, keyboard, focus,
reduced-motion, and mobile drawer behavior without changing PR #299's cache or
navigation machinery.

## Task 6: Run exact-head verification

Run focused Recents tests, PR #299 switching regressions, hydration/pagination
tests, the full frontend suite, ESLint, production build/TypeScript, modularity
checks, and `git diff --check`. Exercise the exact committed candidate through
the real provider-free application path with deterministic multi-page fixtures,
record sanitized request counts, and capture desktop/mobile screenshots.

## Task 7: Review and publish

Review the bounded diff, run the Argus review contract on the exact candidate,
and fix only confirmed reachable findings red-first. Create atomic conventional
commits, push `codex/issue-245-recents-progressive-disclosure`, open a Draft PR
to `codex/private-alpha-next`, update issue #245 criterion by criterion, and
drive candidate CI green. Finish only when local, remote, and PR heads match and
the worktree is clean.
