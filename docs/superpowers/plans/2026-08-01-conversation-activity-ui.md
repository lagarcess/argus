# Conversation Activity UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` for bounded implementation tasks or `superpowers:executing-plans` for a single-owner execution pass. The release captain retains sequencing, review, verification, branch, and Draft PR ownership.

**Goal:** Build the frontend-only consumer of PR #329's durable conversation-activity contract so users can see working, unseen terminal, needs-input, needs-attention, and manual-unread state without changing Recents ordering, geometry, shortcuts, or progressive disclosure.

**Architecture:** Keep the server projection canonical and layer a pure, conversation-keyed frontend reducer over it for request-scoped transport state and optimistic read mutations. A focused hook owns refresh triggers, bounded unresolved-work polling, mutation sequencing, announcements, and transcript invalidation. A separate viewport hook treats a dedicated latest-activity sentinel—not conversation opening or the 240px navigation threshold—as read proof. Shared presentation selectors drive Recents, collapsed aggregate, Quick Peek, selected rows, menus, and the one existing Jump to latest control.

**Tech Stack:** Next.js 15, React 19, TypeScript, Tailwind CSS, Bun test runner, React Testing Library, Playwright, existing Argus API client and locale catalogs.

## Starting Evidence and Boundaries

- Fresh linked worktree: `/Users/garces/.codex/worktrees/conversation-activity-ui/private-alpha-next`
- Branch: `codex/conversation-activity-ui`
- Exact starting SHA: `8a5d621b4375e018bb4ebeb711ad737a2d5a1d60`
- Starting remote: `origin/codex/private-alpha-next`
- PR #329 merge commit `8a5d621b4375e018bb4ebeb711ad737a2d5a1d60` is the exact starting head.
- Baseline focused frontend tests: 66 passed, 0 failed.
- Baseline merged activity backend regressions: 50 passed, 8 skipped because no disposable Postgres URL was supplied.
- Required visual references were present and inspected: the calm open working ring and the restrained three-dot Jump to latest treatment.
- Root `.env` and `web/.env.local` are `canonical-linked` symlinks. They must remain read-only shared inputs.
- Ports 3000, 8000, 5432, and 54321-54324 were free. A separate `argus-qa` local Supabase stack was already running on 54331-54334 and is shared state; it must not be stopped, reset, migrated, or reused without proving isolation.

### Protected surfaces

Do not change backend schemas, API semantics, migrations, RLS, OpenAPI, LangGraph, interpreter routing, stage taxonomy, SSE framing/order, backtest finalization, confirmation/run idempotency, quota accounting, durable artifacts, Recents ordering/grouping/pagination/progressive disclosure, shortcut bindings, Omnisearch, Idea Ledger, the conversation activity rail, providers/models, PostHog ownership, or PR #320 failure semantics.

The lane stops if the frontend would need prose matching, translated-string matching, timers as fake product truth, a succeeded job presented before canonical hydration, global cross-conversation stream ownership, a second Jump control, Recents reordering, backend contract expansion, WebSockets/Realtime/notifications/counts/inboxes/bulk read/per-message unread, hosted migration, deployment, tester exposure, or merge authority.

## Target Ownership Model

### Canonical API types and transport

`web/lib/argus-api.ts` will add exact wire types for:

- `ConversationOperationStatus`: `idle | queued | running | checking`
- `ConversationOperationKind`: `chat_turn | backtest_job | null`
- `ConversationOperation`
- `ConversationAttentionStatus`: `none | needs_input | needs_attention | new_activity | manual_unread`
- `ConversationAttention`
- `ConversationActivity`
- the discriminated PATCH actions `mark_read` and `mark_unread`

`Conversation.activity` and `HistoryItem.activity` remain optional/nullable at the wire boundary. Only chat history rows project activity; non-chat rows continue to omit it. Add `getConversationActivity` and `patchConversationActivity` helpers without changing backend semantics.

The caller will generate each ordinary-turn request id and pass it into `streamChatMessage` with an abort signal. This changes client ownership only; it does not alter SSE event types, order, or backend request semantics.

### Pure activity state

Replace the session-only `Set<string>` in `web/lib/chat-attention-state.ts` with `web/lib/conversation-activity-state.ts`. The pure reducer owns:

- canonical server projections keyed by conversation id;
- request records keyed by both conversation id and request id;
- request-local queued/running/checking/settled state;
- per-conversation current-request identity;
- optimistic mark-read/unread operations with mutation sequence ids;
- stale mutation response rejection;
- rollback metadata scoped to the failed conversation;
- same-view manual-unread guards, including newly observed cross-tab manual unread;
- one-time transition announcement keys;
- presentation selectors using the locked precedence:
  `working > needs_attention > needs_input > new_activity > manual_unread > none`.

The reducer never reads message prose, translated labels, elapsed time, or one global streaming boolean.

### Side effects and refresh ownership

Add `web/components/chat/useConversationActivity.ts` to:

- merge optional activity projections from loaded Recents/history pages;
- refresh on initial load, conversation create/delete, tab focus, document visibility return, ordinary transport settlement, backtest settlement, and successful read mutation;
- poll at one short bounded cadence only while a loaded server projection or local request remains unresolved;
- stop polling when the unresolved set is empty;
- expose conversation-scoped lock and presentation selectors;
- perform optimistic mark-read/unread mutations and emit localized success/rollback toasts;
- refresh canonical state after successful mutation;
- invalidate an inactive transcript cache when its canonical background work settles;
- reset user-scoped state and abort registered transports on logout/account change.

`web/components/chat/useRecentConversations.ts` and `web/lib/chat-recents.ts` will carry the optional projection through pagination and replace refreshed rows in place. Existing order, grouping, cursors, page boundaries, progressive disclosure, and quick-jump indexes remain unchanged.

### Request identity and visible transcript ownership

`ChatInterface.tsx` will replace its single active-stream refs with request records keyed by conversation and request id. Each callback verifies both identities before changing visible messages or controls. Navigation does not cancel or retire an inactive conversation's logical request. A late callback for A can settle A and invalidate A's transcript cache, but it cannot unlock, clear, or overwrite B.

Active-composer locking is derived only from the current conversation's unresolved request. Inactive job polling uses activity projections and local request records, not the active `messages` array. Existing backtest-card queued/running states remain intact. A reopened ordinary running turn may render only the spec-authorized neutral working placeholder and only from typed activity state.

### Viewport read proof

Add `web/components/chat/useConversationActivityViewport.ts` and a dedicated one-pixel latest-activity sentinel immediately after the latest rendered activity and before the bottom padding element. Automatic mark-read is allowed only when all binding section 9.5 conditions hold:

- the route and loaded transcript belong to the same conversation;
- transcript hydration is complete;
- the document is visible and the window is focused;
- the sentinel is intersecting in the transcript viewport;
- the observed canonical cursor is still current;
- no same-view manual-unread guard is armed;
- that cursor has not already been acknowledged.

Opening a conversation is not read proof. The existing 240px threshold remains navigation/follow-mode behavior only. Explicit Mark as read may bypass the sentinel; automatic read may not.

### Shared presentation

Add one shared, aria-hidden `ConversationActivityIndicator` for row, aggregate, Quick Peek, and Jump variants:

- working: founder-approved calm open ring; static open ring under reduced motion;
- needs attention: PR #320's existing failure-state visual tokens;
- needs input: a distinct non-failure marker and localized label;
- new activity and manual unread: the existing teal dot vocabulary;
- none: no marker.

The left marker lane remains reserved and row text never moves. The right quick-jump/menu slot remains reserved. Selected rows keep their marker. The collapsed Recents aggregate overlays its status on the existing icon without replacing the icon or expanding the target. Mobile drawer and Quick Peek use the same selector and precedence as expanded Recents.

`RecentChatActions` and `ChatHeaderMenu` receive Mark as unread/read as the first menu item. The Recents ellipsis target becomes at least 44 by 44 pixels while the glyph stays visually restrained. The dot is not clickable and no second hover action is added. Escape closes and restores trigger focus; coarse pointers retain a discoverable menu trigger; PR #324 quick-jump precedence remains unchanged.

The current Jump to latest button remains the only viewport control:

- ordinary history: down arrow;
- working below: restrained three-dot wave, static dots under reduced motion;
- unread below: down arrow plus teal marker;
- needs input or attention below: down arrow plus the shared typed attention treatment.

All labels and transition announcements are localized. Announcements fire once per meaningful state transition, not once per poll.

## Risk-Ordered TDD Tasks

Every production step begins with a focused failing test. Keep each green change small and run the named focused command before moving on.

### Task 1: Lock the wire contract in frontend types

**Tests first**

- Update `web/__tests__/argus-api.test.ts` to assert optional activity decoding on chat rows, omission on non-chat rows, exact GET/PATCH paths, discriminated request bodies, and preservation of caller-supplied stream request identity.
- Run: `bun test __tests__/argus-api.test.ts`
- Confirm the new assertions fail for missing types/helpers before implementation.

**Implementation**

- Modify `web/lib/argus-api.ts` with exact activity types, optional fields, GET/PATCH helpers, and caller-owned `requestId`/`AbortSignal` stream options.
- Do not add compatibility aliases or frontend-invented statuses.

**Green check**

- Run: `bun test __tests__/argus-api.test.ts`

### Task 2: Build the pure conversation-keyed reducer

**Tests first**

- Replace `web/__tests__/chat-attention-state.test.ts` with `web/__tests__/conversation-activity-state.test.ts`.
- Cover all pairwise presentation precedence, server/local merge, selected-row independence, aggregate selection, request identity, stale request callbacks, stale mutation responses, rollback scope, current-conversation lock isolation, same-view guard lifecycle, cross-tab guard arming, and announcement de-duplication.
- Run: `bun test __tests__/conversation-activity-state.test.ts`

**Implementation**

- Add `web/lib/conversation-activity-state.ts` with reducer actions, selectors, typed presentation state, request records, mutation records, guards, and announcement keys.
- Remove the session-only Set behavior from `web/lib/chat-attention-state.ts`; delete the file once imports and tests move.

**Green check**

- Run: `bun test __tests__/conversation-activity-state.test.ts`

### Task 3: Carry projections through Recents without reordering

**Tests first**

- Extend `web/__tests__/chat-recents.test.ts` and `web/__tests__/use-recent-conversations.test.tsx`.
- Assert chat projections survive mapping, non-chat rows omit activity, refreshed rows replace activity in place, pagination order is stable, no row is inserted/reordered, quick indexes remain stable, and progressive disclosure remains unchanged.
- Run: `bun test __tests__/chat-recents.test.ts __tests__/use-recent-conversations.test.tsx`

**Implementation**

- Modify `web/lib/chat-recents.ts` to retain activity and merge updated existing rows in their current positions.
- Modify `web/components/chat/useRecentConversations.ts` to retain canonical activity across bootstrap, refresh, load-more, create, and delete triggers.

**Green check**

- Run: `bun test __tests__/chat-recents.test.ts __tests__/use-recent-conversations.test.tsx`

### Task 4: Add bounded refresh, mutation, and inactive-settlement ownership

**Tests first**

- Add `web/__tests__/use-conversation-activity.test.tsx` with fake transport APIs, not fake product timers.
- Assert bounded refresh triggers, polling only while loaded/local unresolved work exists, no idle polling, inactive polling independent of active messages, focus/visibility refresh, optimistic mark read/unread, mutation sequence protection, scoped rollback toast, canonical refresh, inactive transcript invalidation, and logout/account reset with transport abort.
- Run: `bun test __tests__/use-conversation-activity.test.tsx`

**Implementation**

- Add `web/components/chat/useConversationActivity.ts`.
- Connect it to the recent-history refresh function and transcript cache invalidation.
- Keep the cadence an implementation detail tested by observable start/stop behavior.

**Green check**

- Run: `bun test __tests__/use-conversation-activity.test.tsx __tests__/chat-transcript-session-cache.test.ts`

### Task 5: Prove request-scoped ordinary-turn isolation

**Tests first**

- Replace global-stream assumptions in `web/__tests__/chat-conversation-routing.test.ts` with request-record assertions.
- Add focused `ChatInterface` integration cases in `web/__tests__/chat-conversation-activity.test.tsx` for A working while viewing B, simultaneous A/B work, a late A callback after B starts, current-only composer locking, inactive settlement invalidation, and no background overwrite of visible messages.
- Run: `bun test __tests__/chat-conversation-routing.test.ts __tests__/chat-conversation-activity.test.tsx`

**Implementation**

- Modify only focused request/transport ownership in `web/components/chat/ChatInterface.tsx`.
- Store abort controllers by conversation/request key.
- Verify identity in every token, stage, final, completion, error, and reconciliation callback.
- Do not broad-refactor the component or change SSE framing.

**Green check**

- Run: `bun test __tests__/chat-conversation-routing.test.ts __tests__/chat-conversation-activity.test.tsx __tests__/chat-backtest-jobs.test.ts __tests__/chat-run-reconciliation.test.ts`

### Task 6: Separate navigation threshold from read proof

**Tests first**

- Add `web/__tests__/use-conversation-activity-viewport.test.tsx`.
- Assert 240px only controls navigation visibility, opening is not read proof, the sentinel is mandatory, hydration/ownership/cursor/focus/visibility conditions gate automatic read, one cursor is acknowledged once, blur/hidden blocks read, explicit read bypasses visibility proof, and same-view guards block automatic read until leave/re-enter or reload.
- Extend `web/__tests__/quick-jump.test.ts` to prove scroll/follow behavior does not change and tokens/completion never force a scrolled-up user to the head.
- Run: `bun test __tests__/use-conversation-activity-viewport.test.tsx __tests__/quick-jump.test.ts`

**Implementation**

- Add `web/components/chat/useConversationActivityViewport.ts`.
- Place a dedicated sentinel in `ChatInterface.tsx` immediately after the latest rendered activity and before existing bottom padding.
- Preserve `useChatScrollControls.ts`'s 240px navigation threshold, remembered scroll, and follow-mode behavior.

**Green check**

- Run: `bun test __tests__/use-conversation-activity-viewport.test.tsx __tests__/quick-jump.test.ts __tests__/chat-conversation-switching.test.ts`

### Task 7: Implement shared markers and the single Jump state machine

**Tests first**

- Add `web/__tests__/conversation-activity-indicator.test.tsx` and `web/__tests__/conversation-activity-jump.test.tsx`.
- Extend `web/__tests__/chat-sidebar-attention.test.ts`, `web/__tests__/recents-quick-peek.test.tsx`, and `web/__tests__/sidebar-nav-button.test.tsx`.
- Assert locked precedence, selected-row markers, aggregate/Quick Peek parity, calm ring shape, PR #320 failure token reuse, teal unread dot, all Jump variants, localized accessible labels, and static reduced-motion variants.
- Run: `bun test __tests__/conversation-activity-indicator.test.tsx __tests__/conversation-activity-jump.test.tsx __tests__/chat-sidebar-attention.test.ts __tests__/recents-quick-peek.test.tsx __tests__/sidebar-nav-button.test.tsx`

**Implementation**

- Add `web/components/chat/ConversationActivityIndicator.tsx`.
- Add `web/components/chat/ConversationActivityJumpButton.tsx` or keep only its focused rendering helper beside the shared indicator.
- Modify `web/components/sidebar/ChatSidebar.tsx`, `RecentsQuickPeek.tsx`, and `SidebarNavButton.tsx` without changing row layout, ordering, grouping, pagination, or shortcut behavior.
- Evolve the existing Jump to latest control in `ChatInterface.tsx`; do not add a second button.

**Green check**

- Run the focused command above plus `bun test __tests__/quick-jump.test.ts __tests__/chat-recents.test.ts`.

### Task 8: Add first-position read controls and accessible interaction

**Tests first**

- Add or extend component tests for `RecentChatActions` and `ChatHeaderMenu`.
- Assert Mark as unread/read is first, optimistic state appears immediately, stale and failed responses cannot revert newer intent, rollback toast is localized, the Recents target is at least 44 by 44, restrained glyph sizing is unchanged, hover/focus behavior works, Escape closes and returns focus, coarse pointers keep the menu discoverable, the dot is not interactive, no extra hover action exists, and quick-jump wins the right slot.
- Run: `bun test __tests__/recent-chat-actions.test.tsx __tests__/chat-header-menu.test.tsx`

**Implementation**

- Modify `web/components/sidebar/RecentChatActions.tsx` and `web/components/chat/ChatHeaderMenu.tsx`.
- Wire both through the same activity mutation owner.
- Keep guest manual-unread controls unavailable while leaving automatic read behavior intact.

**Green check**

- Run the focused menu tests plus sidebar/Quick Peek tests.

### Task 9: Add localized transition announcements and copy

**Tests first**

- Extend `web/__tests__/locales.test.ts` and activity integration tests for exact English/es-419 labels, success/rollback toasts, Jump variants, row status phrases, and once-per-transition polite announcements.
- Run: `bun test __tests__/locales.test.ts __tests__/chat-conversation-activity.test.tsx`

**Implementation**

- Modify `web/public/locales/en/common.json` and `web/public/locales/es-419/common.json`.
- Add one polite live region in the active chat shell driven by transition keys, not polling ticks.

**Green check**

- Run the focused locale and integration tests.

### Task 10: Add deterministic browser journeys and visual evidence

**Tests first**

- Add `web/e2e/conversation-activity-ui.spec.ts` using deterministic route fixtures and typed activity payloads.
- Reuse existing PR #324 and conversation-switching fixtures where they already prove geometry, quick-jump ownership, restored scroll, Omnisearch anchors, mobile, and reduced motion.
- Make each scenario fail against the pre-feature UI before filling its implementation gaps.

**Implementation and evidence**

- Cover section 16.3 journeys 1-9 using the exact mapping below.
- Save exact-head screenshots under `temp/qa/conversation-activity-ui/<head-sha>/` with deterministic filenames for locale, theme, viewport, state, and interaction.
- Record Playwright result counts and screenshot paths in `docs/reports/2026-08-01-conversation-activity-ui-qa.md` only after the final head is known.

**Green check**

- Run: `bun run test:e2e e2e/conversation-activity-ui.spec.ts e2e/issue-245-recents-progressive-disclosure.spec.ts e2e/issue-252-conversation-switching.spec.ts`

### Task 11: Document the locked UI contract

- Update `.agent/designs/argus/DESIGN.md` with marker precedence, selected-row behavior, the Jump to latest state machine, the 44px menu target, and reduced-motion behavior.
- Add the historical follow-up pointer to `docs/superpowers/specs/2026-07-31-recents-quick-jump-attention-marker.md` without rewriting its accepted history.
- Do not mark the roadmap complete; acceptance and landing remain founder-owned.

## Section 16.2 Frontend Acceptance Matrix

| Case | Required proof | Deterministic artifact |
|---|---|---|
| 16.2.1 | Pairwise marker precedence | `web/__tests__/conversation-activity-state.test.ts` table over every conflicting state pair |
| 16.2.2 | Selected rows retain markers | `web/__tests__/chat-sidebar-attention.test.ts` plus selected-row Playwright screenshots |
| 16.2.3 | Collapsed aggregate precedence and working dominance | reducer aggregate selector tests and `web/__tests__/sidebar-nav-button.test.tsx` |
| 16.2.4 | Quick Peek equals expanded Recents | `web/__tests__/recents-quick-peek.test.tsx` and Playwright parity screenshot |
| 16.2.5 | Optimistic read/unread, success, rollback, stale response | reducer mutation-sequence tests, hook tests, and both-menu integration cases |
| 16.2.6 | 44px, hover/focus, Escape, coarse pointer | menu component tests plus keyboard/mobile Playwright journeys |
| 16.2.7 | No row movement and quick-jump coexistence | `chat-recents` order tests plus bounding-box assertions in Playwright |
| 16.2.8 | Only current conversation lock affects current controls | reducer request selector tests and `chat-conversation-activity` integration test |
| 16.2.9 | Late A callback cannot clear B | reducer identity tests, integration test, and simultaneous-work Playwright journey |
| 16.2.10 | Inactive polling independent of active messages | `use-conversation-activity.test.tsx` with empty/unrelated active transcript |
| 16.2.11 | 240px navigation threshold differs from sentinel read proof | viewport hook tests, `quick-jump` tests, and scrolled-up Playwright journey |
| 16.2.12 | All Jump to latest variants | `conversation-activity-jump.test.tsx` and visual state matrix screenshots |
| 16.2.13 | Same-view manual-unread guard | reducer and viewport hook tests plus menu Playwright journey |
| 16.2.14 | Window blur and hidden document block read | viewport hook tests and browser focus/visibility journey |
| 16.2.15 | Reduced-motion ring and dots are static | indicator/jump component tests and computed-style Playwright assertions |
| 16.2.16 | Polite announcements occur once per transition | reducer announcement-key tests and live-region integration test |

## Section 16.3 Browser Journey Matrix

| Journey | Deterministic Playwright proof | Bounded real-auth proof |
|---|---|---|
| 16.3.1 Ordinary work A → view B → settle A | `conversation-activity-ui.spec.ts`: marker, current lock, transcript invalidation, and return hydration | Real-auth ordinary-turn background journey |
| 16.3.2 Backtest A → view B → queued/running/succeeded/checking | fixture journey covering typed states and durable hydration | One authorized real backtest background journey |
| 16.3.3 Simultaneous A and B | fixture journey with interleaved request ids and late callbacks | Not repeated with live tokens |
| 16.3.4 Completion while scrolled up | fixture journey proving stable scroll and Jump variant | Not repeated with live tokens |
| 16.3.5 Restored older position and older Omnisearch anchor | dedicated fixture plus existing `issue-252-conversation-switching.spec.ts` regressions | Not repeated with live tokens |
| 16.3.6 Mark unread/read from row and header menus without reordering | keyboard and pointer journey with before/after row bounding boxes and order | Included only if naturally reached in the ordinary live journey; no extra provider call |
| 16.3.7 Needs-input, shared needs-attention, canceled/expired failure, checking | table-driven typed fixture screenshots and labels | Not repeated with live tokens |
| 16.3.8 EN light/dark, es-419, 390px/coarse, keyboard, reduced motion, expanded/collapsed/Quick Peek/selected | named screenshot matrix under the exact-head evidence directory | Auth shell sanity only within the two authorized journeys |
| 16.3.9 Predecessor quick-jump, geometry, scroll, and rail regressions | new spec plus existing issue #245/#252, quick-jump, and rail suites | Not repeated with live tokens |

## Commit Sequence

1. `docs(chat): plan conversation activity UI`
2. `feat(web): add conversation activity state`
3. `feat(web): surface conversation activity controls`
4. `test(web): cover conversation activity lifecycle`
5. `docs(chat): document activity UI behavior`

Split a commit further if a change is independently revertible; do not combine the plan with production changes.

## Verification Gates

### Focused TDD loop

Run the task-specific Bun command after each red/green step. Before each commit, run `git diff --check` and the focused suites covering changed ownership.

### Full deterministic frontend gate

From `web`:

```bash
bun install --frozen-lockfile
bun test
bun run lint
bun run build
bun run test:e2e e2e/conversation-activity-ui.spec.ts e2e/issue-245-recents-progressive-disclosure.spec.ts e2e/issue-252-conversation-switching.spec.ts
```

### Full deterministic repository gate

From the repository root:

```bash
poetry run pytest tests/test_conversation_activity.py tests/test_conversation_activity_migration.py tests/test_conversation_activity_postgres.py -q --no-cov
poetry run ruff check src tests workflows scripts
poetry run python scripts/check_modularity_budget.py
poetry run pytest tests -q --no-cov
git diff --check
```

If root timing environment variables affect pre-existing streaming tests, reproduce the result on untouched `origin/codex/private-alpha-next` with the same environment before changing any code. Do not change streaming behavior to mask an environment leak.

### Browser and visual gate

Capture exact-head evidence for:

- English desktop light and dark;
- es-419 desktop;
- 390px mobile/coarse pointer;
- keyboard-only menus and Jump to latest;
- reduced-motion working ring and three-dot state;
- expanded Recents, collapsed aggregate, Quick Peek, and selected rows;
- ordinary work in A while viewing B;
- simultaneous work in A and B;
- completion while scrolled up;
- restored older scroll position and older Omnisearch anchor;
- Mark unread/read from both menus without reordering;
- needs-input, shared needs-attention, and checking states.

The QA report must record the exact tested head SHA, commands, pass/fail counts, screenshot paths, viewport/theme/locale, and any skipped proof with its reason. A screenshot from an earlier SHA is not final evidence.

### Two bounded production-parity local journeys

Run only after deterministic gates pass:

1. one real-auth ordinary-turn background journey;
2. one authorized real backtest background journey.

Before either journey, prove a disposable/local-only Supabase target, apply PR #329's migration only there, prove real auth and required local providers, and ensure the shared `argus-qa` stack is not being reset or mutated unintentionally. Do not apply migrations to hosted Supabase. Stop after these two token/provider-spending journeys.

## Rebase, Final Review, and Delivery

1. Fetch `origin/codex/private-alpha-next` before final verification.
2. If it advanced, verify `8a5d621b4375e018bb4ebeb711ad737a2d5a1d60` is still an ancestor, rebase the feature branch onto the new remote head, and rerun the complete deterministic and exact-head browser gates.
3. Perform a proportional code review focused on typed truth, request isolation, read-proof correctness, geometry, localization, accessibility, and no protected-surface drift.
4. Push `codex/conversation-activity-ui` only after final exact-head verification.
5. Open a Draft PR targeting `codex/private-alpha-next` with exact base/head SHAs; structured Summary, Changes, Motivation, Impact, Testing, Risks/Rollback, and Checklist sections; deterministic counts; browser matrix and screenshot paths; and explicit confirmation that backend contracts, hosted Supabase, deployment, and tester exposure were untouched.
6. Do not merge. Founder approval and integration are outside this lane.
