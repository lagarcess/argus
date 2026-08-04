# Issue #252 Instant Conversation Switching — Implementation Plan

> Approved design: GitHub issue #252. This plan maps that design to code and
> evidence; it does not introduce a second product specification.

**Goal:** Wire the existing bounded `TranscriptSessionCache` into the real chat
surface so cached switches are instant, cold loads are honest, and rapid
navigation can never commit retired conversation state.

**Authoritative base:** `origin/codex/private-alpha-next` at
`069102b29c0471da455b84cb8861c83530ce5752`.

**Constraints:** Frontend only; no API/schema changes; no durable browser
storage; no provider calls; Draft PR targets `codex/private-alpha-next`.

## Task 1: Prove the missing behavior red

**Files**

- Modify: `web/__tests__/chat-message-hydration.test.ts`
- Create: `web/e2e/issue-252-conversation-switching.spec.ts`

Add a focused unit test proving one abort signal reaches every paginated message
request. Add exact-product-path browser fixtures for fresh, stale, cold,
interrupted, failure/retry, scroll, reload, auth, locale, keyboard,
reduced-motion, request-count, and render-latency behavior. Run the smallest
tests needed to capture the pre-fix failures.

## Task 2: Add abort-aware message hydration

**Files**

- Modify: `web/lib/argus-api.ts`
- Modify: `web/lib/chat-message-hydration.ts`

Thread an optional `AbortSignal` through the existing messages endpoint helper
and every pagination request. Preserve the current endpoint contract and
injected test loader compatibility.

## Task 3: Wire the existing cache into the chat shell

**Files**

- Modify: `web/components/chat/ChatInterface.tsx`
- Create: `web/components/chat/ConversationRetrievalState.tsx`

Route bootstrap, sidebar, and command-palette transcript loads through one
`TranscriptSessionCache<Message[]>`. Commit only cache navigation states:

- fresh: render immediately, no request or loading state;
- stale: render immediately and keep the composer usable while one background
  request revalidates;
- cold: clear the previous transcript immediately, delay the transcript-owned
  retrieval status by 150 ms, and keep the destination composer unavailable
  until ready;
- failure: retain destination identity and render destination-owned retry.

Keep the shared shell and selected conversation identity stable. Restore
per-conversation scroll only for the current navigation.

## Task 4: Complete lifecycle invalidation

**Files**

- Modify: `web/components/chat/ChatInterface.tsx`
- Modify: `web/components/chat/useChatSurfaceLifecycle.ts`
- Modify: `web/lib/chat-run-reconciliation.ts`
- Modify focused tests under `web/__tests__/`

Use user-plus-conversation keys. Clear all in-memory state on logout or user
change. Evict the owning transcript on send, retry/recovery, delete/archive,
delete-all, and durable job completion. Preserve it on rename/pin. Cancel active
navigation when leaving the conversation surface or starting New Chat.

## Task 5: Localize and verify the retrieval surface

**Files**

- Modify: `web/public/locales/en/common.json`
- Modify: `web/public/locales/es-419/common.json`
- Modify: `web/components/chat/ConversationRetrievalState.tsx`

Add truthful transcript-retrieval copy in English and Spanish. Give the
transcript region busy/status semantics, retain keyboard focus on the selected
conversation control, and disable decorative motion under
`prefers-reduced-motion`.

## Task 6: Run exact-head verification

Run focused cache/navigation/hydration/race tests, the full frontend suite,
ESLint, production build/TypeScript, modularity budget, and `git diff --check`.
Run the issue #252 browser fixture against the exact candidate head with
controlled response delays. Record p50/p95 for cold, fresh, stale, and
long-transcript fixtures; add no virtualization unless the measurements show a
material render bottleneck.

## Task 7: Review and publish

Review the bounded diff, run the Argus review contract, and fix only confirmed
reachable findings red-first. Create atomic conventional commits, push
`codex/issue-252-instant-conversation-switching`, open a Draft PR to
`codex/private-alpha-next`, update issue #252 criterion by criterion, and wait
for candidate CI. Finish only when local, remote, and PR heads match and the
worktree is clean.
