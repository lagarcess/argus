# Conversation activity, attention, and unread lifecycle

Give users one truthful, durable way to understand which conversations are
working, which finished out of sight, which need attention, and which they
deliberately marked for later—without adding more chat clutter.

Status: **BACKEND/DATA FOUNDATION DELIVERED** by PR #329, merged into
`codex/private-alpha-next` as `8a5d621b`. The conversation-activity UI PR named
in section 15 remains the next bounded slice; this file remains its contract.

Implementation base: `codex/private-alpha-next` at
`403ea11410da2746f132223e44aac70c4a4b5534`. The specification review began
against `53c36d40bbc6e058af7d27c687504235c2fd48d8`.

Predecessors:

- PR #302 / issue #245: bounded progressive Recents disclosure.
- PR #299: race-safe conversation switching and transcript scroll restoration.
- PR #268: durable ordinary-turn recovery and exact-once Run reconciliation.
- PR #315: the current-conversation activity rail.
- PR #324: right-aligned Recents quick-jump hints and preserved left attention
  lane.

This is a new follow-up lane. It intentionally changes the session-local
attention lifecycle protected by the narrow PR #324 correction, while
preserving PR #324's accepted geometry: activity stays in the left marker lane,
and quick-jump hints plus the owner menu continue to share the trailing slot.

## 1. Why

`docs/PRODUCT.md` says the conversation is the product, Recents exists to help
people resume prior work, and Argus should feel fast, clear, and continuous.
Today that continuity has three gaps:

1. A conversation can keep working after the user leaves it, but Recents has no
   truthful in-progress signal.
2. If the user remains inside a conversation but scrolls to older turns, new or
   ongoing work below the viewport is easy to miss. Adding a second floating
   control would conflict with the existing **Jump to latest** button.
3. The current teal dot means only "a local turn settled while another
   conversation was focused." It is session-local, clears when a conversation
   merely opens, cannot represent durable backtest work, and cannot support a
   deliberate **Mark as unread** reminder.

The current behavior is like a mailbox that shows a badge only after delivery,
never shows that a package is still on the way, and removes the badge when the
mailbox door opens even if the user is looking at an older letter. This lane
separates those concepts while keeping one calm visual language.

The architecture already has the required truth owners:

- `chat_turn_lifecycles` owns accepted/running/terminal ordinary turns;
- `backtest_jobs` owns queued/running/terminal Run actions;
- persisted messages and canonical results own what the user can actually see;
- Supabase owns durable product and recovery state.

The frontend should project those facts. It must not infer work from prose,
keep a fake timer alive, or treat SSE completion as proof that a queued/running
backtest is finished.

## 2. User job and success definition

The user should be able to answer these questions at a glance:

- Is Argus still working in this conversation?
- Did something finish while I was elsewhere or above it in the transcript?
- Does Argus need my input or attention?
- Which conversation did I intentionally leave unread as a reminder?
- How do I reach the newest content without hunting for another control?

The feature succeeds when:

- every visible status comes from canonical turn/job/read state;
- leaving a working conversation does not make its activity disappear;
- multiple conversations can remain independently active;
- a completion stays unread until the newest activity is actually visible or
  the user explicitly marks it read;
- **Mark as unread** works as a durable reminder without moving the chat;
- the existing **Jump to latest** control carries below-viewport state instead
  of gaining a competing floating button;
- English and Spanish, desktop and mobile web, keyboard, screen reader, and
  reduced-motion users receive equivalent meaning.

## 3. Canonical mental model

Conversation state has two independent axes.

### 3.1 Operation state: what Argus is doing now

Machine values:

- `idle`
- `queued`
- `running`
- `checking`

`checking` is a derived presentation/reconciliation state. It is never stored
as a new `chat_turn_lifecycles` or `backtest_jobs` status.

### 3.2 Attention state: what the user has not dealt with yet

Machine values:

- `none`
- `new_activity`
- `manual_unread`
- `needs_input`
- `needs_attention`

These axes may coexist. A conversation can be working while an older completion
or manual reminder remains unread. The operation signal wins visually until
work settles; the underlying unread state is not discarded.

### 3.3 Presentation precedence

| Priority | Canonical condition | Recents presentation | Meaning |
| ---: | --- | --- | --- |
| 1 | `running`, `queued`, or `checking` | Calm ring in the left marker lane | Argus is still working or reconciling truth |
| 2 | `needs_attention` | Static shared attention/failure treatment | The latest unseen terminal outcome needs recovery |
| 3 | `needs_input` | Static attention marker with accurate label | Argus is waiting for the user |
| 4 | `new_activity` | Teal dot | New terminal content is ready |
| 5 | `manual_unread` | Teal dot | The user deliberately left a reminder |
| 6 | `none` | No marker | Seen and idle |

There is never more than one left-lane marker on a row. State is preserved
under the winning presentation and appears when the higher-priority state
settles.

## 4. Locked product decisions

1. **One model, multiple projections.** Recents, collapsed Recents, Quick Peek,
   the open transcript, and the jump control consume the same conversation
   activity/read projection. They do not maintain separate meanings.
2. **Backend state is canonical.** Ordinary activity comes from
   `chat_turn_lifecycles`; Run activity comes from `backtest_jobs`; read/unread
   state is durable Supabase product state. Local state may provide an
   optimistic overlay but cannot contradict canonical truth after refresh.
3. **SSE is request-scoped.** Navigating away does not convert an accepted turn
   into failure and does not end a durable job. API SSE is not extended into a
   long-running cross-conversation status channel.
4. **Backtest completion means canonical result readiness.** An SSE `[DONE]`, a
   succeeded transport request, or `backtest_jobs.status = succeeded` without
   the finalized result projection does not display as ready. It remains
   working/checking until the canonical result is hydrateable.
5. **Multiple conversations are first-class.** Activity is keyed by
   conversation id, not a single global streaming boolean or active-stream ref.
   Starting or finishing work in conversation A cannot clear, unlock, or
   overwrite conversation B.
6. **The current conversation may still show activity.** A selected Recents row
   keeps its working ring. A selected row may also show unread when the newest
   activity is below the viewport, the tab is hidden, or the user manually
   marked it unread.
7. **Opening is not reading.** Selecting a conversation never clears unread by
   itself. Automatic clearing requires the latest-activity sentinel to be
   visible in the correct transcript while the document is visible and the
   conversation is active.
8. **Scroll restoration is respected.** Opening a conversation at a cached
   older scroll position or an Omnisearch message anchor keeps attention until
   the latest boundary is reached.
9. **The 240px threshold remains navigation-only.** It continues to decide when
   **Jump to latest** appears and whether auto-scroll is allowed. It is not
   accurate enough to mark activity read.
10. **A separate read sentinel is required.** Use a small sentinel immediately
    after the latest rendered activity and before bottom composer padding. Do
    not reuse the current tall bottom spacer as read proof.
11. **No forced scroll.** New tokens, a durable job transition, or completion
    never drags a user away from older content. Auto-scroll continues only when
    the user was already following the head.
12. **Reuse Jump to latest.** No second floating three-dot button is added.
    The existing 44px control changes its inner presentation according to what
    exists below the viewport.
13. **Working below uses the three-dot wave.** When the current conversation is
    queued/running/checking and the user is above the head, the button shows the
    restrained three-dot wave from the founder-supplied reference. Clicking it
    still scrolls to latest.
14. **Ready below uses an arrow plus marker.** When terminal unread content is
    below the viewport, the same control shows the down arrow with a small
    attention badge. Failure/needs-input presentation reuses the approved
    shared attention treatment rather than inventing another alarm color.
15. **Plain history uses the plain arrow.** If the user is merely scrolled up
    and no work or unread activity is below, the control remains the existing
    down arrow.
16. **Working wins over unread visually.** If work is active and unread is also
    present, Recents shows the ring and the jump control shows the three-dot
    wave. When work settles, the correct attention state appears.
17. **The ring is calm.** It occupies the existing left marker gutter, does not
    move row text, does not flash, and remains visually distinct from the solid
    unread dot.
18. **Mark as unread is a conversation-level reminder.** It does not mark a
    specific message, create a note, or change conversation content.
19. **Mark as unread is durable.** It survives reload and normal cross-device
    refresh for registered users. It never depends on local storage.
20. **Mark as unread does not reorder.** Read-state writes do not change
    `conversations.updated_at`, Recents cursors, titles, previews, pinning, or
    archive state.
21. **Mark as unread has two entry points.** It is the first item in the
    Recents row overflow menu and the first item in the active chat header
    owner menu.
22. **Do not add another hover icon.** The Recents row continues to reveal one
    ellipsis. The unread action lives inside its menu.
23. **The dot is not a button.** Clicking the tiny marker would be ambiguous and
    fail touch-target requirements. Row navigation and labeled menus remain the
    interaction paths.
24. **The menu action toggles.** A read conversation offers **Mark as unread**;
    any unread conversation offers **Mark as read**.
25. **Explicit Mark as read is authoritative.** It may clear unread without
    scrolling because the user deliberately chose the action. Automatic
    clearing still requires viewport proof.
26. **Marking the open chat unread does not self-cancel.** The current view is
    guarded from automatic clearing until that conversation becomes inactive
    once or the page reloads. The user is not forcibly navigated away. The
    explicit **Mark as read** action remains available immediately.
    An already-open second tab that newly observes the manual-unread transition
    arms the same guard; it cannot erase the reminder merely because it was
    already sitting at the bottom.
27. **A newer terminal event survives a stale read.** Mark-read requests carry
    the latest server-issued attention cursor the user actually saw. A terminal
    event after that cursor remains unread.
28. **The owner menu remains coherent.** Recommended order is Mark as
    unread/read, Pin/Unpin, Rename, Archive (Recents only), separator, Delete.
    The active header keeps its existing owner-specific actions and adds the
    same unread toggle first.
29. **The overflow target becomes touch-safe.** The visible ellipsis may stay
    visually small, but its hit area is at least 44px. It reveals on desktop
    hover and keyboard focus and remains available on coarse-pointer/touch
    layouts. Right-click or long-press may be a later accelerator, never the
    only route.
30. **Quick-jump behavior is preserved.** The right-aligned full chord, pinned
    priority, nine-row cap, physical digit matching, and open/focused menu
    precedence from PR #324 do not change. Activity stays in the left lane and
    cannot cover the trailing keycap/menu slot.
31. **The activity rail remains separate.** PR #315's right-edge rail continues
    to navigate significant artifact turns inside the current conversation. It
    does not become a live-progress or unread control.
32. **Collapsed and mobile modes aggregate without counts.** If any loaded
    conversation is active, the Recents nav icon shows one ring. Otherwise, if
    any loaded conversation is unread, it shows one dot. Opening Recents/Quick
    Peek reveals per-row truth. No numeric inbox badge is added.
33. **No idle polling.** Refresh on bootstrap, conversation/turn transitions,
    window focus, and visibility resume. Poll at the existing short cadence
    only while at least one loaded conversation is queued/running/checking or a
    known local request is unresolved; stop when none remain.
34. **Transport ambiguity is not failure.** Network loss or an empty response
    becomes checking/reconciliation. Only durable terminal state may show
    completion or failure.
35. **No invented stage after navigation.** A live SSE may show its backend
    `stage_start` label in the active chat. A reopened/background ordinary turn
    with only durable running truth shows neutral localized copy such as
    "Argus is working…". A durable backtest may truthfully say queued or running
    backtest from its job state.
36. **Meaning does not rely on motion or color.** Shape, accessible labels, and
    text/status semantics carry every state. Reduced motion replaces rotation
    and the dot wave with static equivalents.
37. **Announcements are transition-based.** A single polite live region may
    announce meaningful changes such as "Tesla dip idea is ready." It must not
    announce every polling response, token, or animation cycle.
38. **No OS/browser notifications in this lane.** Notification permissions,
    push, email, and background service workers remain parked. In-app durable
    attention is the Alpha scope.
39. **No new unread inbox.** Unread filters, counts, bulk **Mark all as read**,
    per-message unread bookmarks, snooze/reminders, and notification settings
    require later usage evidence.
40. **No analytics-owned behavior.** PostHog does not decide or store read
    state. No new product event is added unless the approved event registry is
    separately expanded.

## 5. End-to-end behavior table

| Situation | Recents row | Open-chat head | Scrolled-up jump control | Clear rule |
| --- | --- | --- | --- | --- |
| Idle and read | No marker | Normal transcript | Plain arrow if needed | Already clear |
| Ordinary turn accepted/running | Animated ring, including selected row | Backend stage label while connected; neutral working status after reload/reopen | Three-dot wave | Not clearable as completion yet |
| Backtest queued/running | Animated ring | Queued/running card status from job | Three-dot wave | Remains working through SSE end |
| Transport/result reconciliation | Ring/static checking treatment | Neutral checking status | Three-dot wave or static ellipsis under reduced motion | Durable truth decides next state |
| Completed while latest is visible and tab active | Ring settles; no dot after read receipt | Completed response/result | Hidden | Latest sentinel plus cursor marks read |
| Completed outside focused chat | Ring becomes teal dot | Completed response on return | Arrow plus teal badge until reached | Latest sentinel or explicit Mark as read |
| Completed in selected chat while user is scrolled up | Selected row gets teal dot | New content remains below without forced scroll | Arrow plus teal badge | Latest sentinel or explicit Mark as read |
| Clarification awaiting user | Static attention marker | Question/actions at head | Arrow plus attention badge | Latest sentinel records it seen; the question remains actionable |
| Recoverable failure/canceled/expired/abandoned | Static shared attention treatment | Typed recovery at head | Arrow plus attention badge | Latest sentinel records it seen; recovery remains actionable |
| Manually marked unread | Teal dot and label "Marked unread" | Content is unchanged | Arrow plus teal badge when above latest | Explicit Mark as read, or latest sentinel on a later visit |
| Working and manually unread | Ring wins; manual unread remains underneath | Working presentation | Three-dot wave | Terminal result then normal read rules |

## 6. Primary journeys

### 6.1 Background ordinary turn

1. The user sends a turn in conversation A.
2. The accepted lifecycle makes A `queued`/`running`; A shows a ring.
3. The user opens conversation B. A's request-scoped stream may continue, but
   its activity ownership is not retired or transferred to B.
4. Recents continues to show A's ring. The composer in B is governed by B's
   own state, so the user may start work there if backend admission permits.
5. A reaches durable terminal state. The ring becomes the correct attention
   marker; a polite one-time announcement may say A is ready.
6. Opening A loads/caches the transcript without clearing attention.
7. If the latest sentinel is visible, the client marks read through A's current
   attention cursor. If scroll restoration places the user higher, the marker
   remains and the jump control carries the state.

When terminal state and a visible latest sentinel arrive together, the client
may optimistically coalesce the read receipt so the row does not intentionally
flash a dot between ring and idle. Canonical cursor acknowledgement still owns
the final state.

### 6.2 Durable backtest beyond SSE

1. A Run action creates a `backtest_jobs` row in `queued`.
2. Conversation A shows the ring even after the chat SSE final payload says the
   job was started.
3. Navigation does not cancel the job projection. Activity-list polling can
   track A without requiring A's messages to remain the active React array.
4. `queued` and `running` remain working. `succeeded` without a hydrateable
   canonical Run/result remains checking.
5. A fully finalized result creates new activity. Failed, canceled, or expired
   creates needs-attention state. The result/failure is never inferred from
   elapsed time or a fetch exception.

### 6.3 Same conversation, user scrolled up

1. The user scrolls more than the existing navigation threshold from latest.
2. Auto-scroll stops and **Jump to latest** appears.
3. While work continues below, its inner icon becomes the three-dot wave.
4. Tokens or job transitions do not change the user's scroll position.
5. On terminal success, the icon becomes arrow plus teal badge. On a typed
   failure or question, it becomes arrow plus the shared attention treatment.
6. Clicking any variant scrolls to latest, resumes follow mode, and marks read
   only after the separate latest-activity sentinel is visible.

### 6.4 Mark as unread from Recents

1. The user hovers/focuses the row or uses its visible touch overflow.
2. The single ellipsis opens the existing owner menu.
3. **Mark as unread** sets durable manual unread optimistically, closes the
   menu, and leaves the row in place.
4. The teal dot appears with accessible text "Marked unread." No notification
   fires and `updated_at` does not change.
5. The next visit clears only when latest is visible, or the user can choose
   **Mark as read** directly.
6. On API failure, optimistic state rolls back and a localized toast explains
   that the reminder could not be saved.

### 6.5 Mark the currently open chat unread

1. The user opens the header owner menu and chooses **Mark as unread**.
2. Argus confirms with a localized toast and keeps the user in place.
3. The active row shows the marker, but the existing visible sentinel cannot
   immediately clear it during the same view epoch.
4. After the user leaves and deliberately returns—or reloads—the normal latest
   sentinel rule is armed again.
5. Choosing **Mark as read** explicitly bypasses the view-epoch guard.

### 6.6 Multiple simultaneous conversations

1. Conversations A and B may each have an accepted/running operation.
2. Each row has independent canonical state; collapsed Recents shows one
   aggregate ring rather than a count.
3. Completion of A cannot clear B's ring, composer lock, active request, or
   transcript ownership.
4. A can become unread while B stays working. The aggregate ring remains until
   B settles, then the aggregate unread dot appears if any unread remains.

## 7. Surface contracts

### 7.1 Expanded Recents rows

- The existing left `w-11` lane remains the fixed activity/attention lane.
- The ring/dot never changes row height or title/subtitle coordinates.
- Active-row background, pin grouping, five-row progressive disclosure,
  pagination, and title-source behavior remain unchanged.
- The row's accessible name appends one current state phrase: `Working`,
  `Queued`, `Checking status`, `New activity`, `Marked unread`, `Needs your
  input`, or `Needs attention`.
- The marker is decorative (`aria-hidden`) because the row label carries the
  meaning.
- Activity changes do not move the row. Normal message activity may already
  move a conversation through existing `updated_at` behavior; status/read
  writes alone may not.

### 7.2 Collapsed Recents and Quick Peek

- The History/Recents nav button gains a non-numeric aggregate overlay.
- Any active loaded conversation gives the nav button a ring; otherwise any
  unread loaded conversation gives it a dot.
- The overlay never replaces the History icon or changes the 44px nav target.
- Quick Peek renders the same per-row left-lane state and accurate accessible
  labels as expanded Recents.
- Quick-jump keycaps remain right-aligned and win their existing trailing-slot
  precedence only against the ellipsis, not against the left status lane.

### 7.3 Recents owner menu

- Keep one ellipsis, not a row of quick actions.
- Minimum interactive target: 44px in both axes. A smaller glyph is allowed.
- Desktop: reveal on row hover, ellipsis focus, and menu-open state.
- Keyboard: focus makes the ellipsis visible; Escape closes the menu and returns
  focus to the trigger.
- Coarse pointer/mobile: the ellipsis is visibly available without hover.
- Menu order:
  1. Mark as unread / Mark as read
  2. Pin / Unpin
  3. Rename
  4. Archive
  5. separator
  6. Delete
- Delete remains visually separated/destructive. Unread is not destructive and
  requires no confirmation.

### 7.4 Active chat header menu

- Add Mark as unread/read first.
- Keep the current mobile bottom-sheet and desktop popover behavior.
- The action is disabled only while its own mutation is pending; unrelated
  rename/pin state does not hide it.
- A successful action closes the menu and announces a localized toast.

### 7.5 Transcript and inline working state

- Connected SSE continues to render exact backend `stage_start` labels.
- A cold/reopened ordinary `accepted` or `running` lifecycle renders one
  neutral working placeholder attached to the head. It does not invent the
  hidden stage or duplicate an already-persisted assistant terminal.
- A queued/running backtest continues to use its existing confirmation/job card
  status.
- There is one current-conversation in-flight lock shared by composer and
  next-move rows. It is derived per conversation, not from unrelated work.
- When activity settles in a non-current conversation, its inactive transcript
  is invalidated for the next open; background tokens are not spliced into the
  wrong message list.

### 7.6 Jump to latest state machine

| Viewport condition | Current conversation state | Inner presentation | Accessible label |
| --- | --- | --- | --- |
| Latest visible | Any | Control hidden | N/A |
| Above latest | Idle/read | Down arrow | Jump to latest |
| Above latest | Queued/running/checking | Three-dot wave | Jump to latest; Argus is working below |
| Above latest | New/manual unread | Arrow plus teal marker | Jump to new activity |
| Above latest | Needs input | Arrow plus attention marker | Jump to the latest question |
| Above latest | Needs attention | Arrow plus shared attention marker | Jump to the latest recovery |

All variants keep one 44px button and the same click behavior. They may use a
localized tooltip, but the tooltip is not the only label.

## 8. Canonical backend and data contract

### 8.1 Activity projection

Add one typed projection to chat `Conversation` records and chat
`HistoryItem`s:

```json
{
  "activity": {
    "operation": {
      "status": "idle | queued | running | checking",
      "kind": "chat_turn | backtest_job | null",
      "updated_at": "timestamp-or-null"
    },
    "attention": {
      "status": "none | new_activity | manual_unread | needs_input | needs_attention",
      "cursor": "opaque-owner-scoped-cursor-or-null"
    }
  }
}
```

Rules:

- The projection is additive and present on chat items only.
- The server computes it from owner-scoped lifecycle/job/read state.
- `checking` may be derived when durable finalization/reconciliation is not yet
  readable. It is not written into lifecycle/job status columns.
- `kind` permits truthful generic-chat versus backtest copy without exposing a
  provider, model, workflow id, prompt, title, or transcript.
- If several operations exist, choose one deterministic presentation state:
  `running` before `queued`, then `checking`; any non-idle state still counts as
  aggregate working.
- The latest terminal attention kind comes only from typed metadata/status:
  ordinary completion, typed awaiting-input outcome, ordinary recoverable/
  abandoned failure, or terminal job success/failure. Never scan prose.
- A succeeded job is new activity only after its canonical result is complete
  and hydrateable.

### 8.2 Read-state endpoint

Add an owner-scoped subresource:

```text
GET   /api/v1/conversations/{conversation_id}/activity
PATCH /api/v1/conversations/{conversation_id}/activity
```

Patch requests:

```json
{ "action": "mark_unread" }
```

```json
{
  "action": "mark_read",
  "through_attention_cursor": "opaque-cursor-or-null"
}
```

Both return the current activity projection.

Contract rules:

- The cursor is server-issued, opaque, owner/conversation scoped, and maps to a
  real canonical terminal boundary.
- The client never sends its clock as read truth.
- Mark read advances monotonically only through the supplied visible cursor.
  It cannot consume a later terminal event.
- Mark read is idempotent. Mark unread is idempotent while already manually
  unread.
- Mark read clears the manual flag even when the cursor is null; any newer
  automatic activity remains unread.
- `mark_read` is available to any active conversation owner, including a guest,
  so automatic viewport clearing can remain durable. `mark_unread` requires the
  registered-account conversation-management capability and is not exposed in
  the guest UI.
- Missing, deleted, foreign, or out-of-workspace conversations return the
  existing non-leaking `404 not_found` shape.
- Validation and state conflicts use the existing RFC 9457 boundary.
- GET has no mutation side effect. Stale reconciliation may run through the
  existing bounded server reconciliation owner before projection, but simply
  viewing the endpoint never marks content read.

### 8.3 Terminal event ordering

The opaque attention cursor is derived from canonical terminal sources, not a
new transcript or analytics event log:

- ordinary turns: `chat_turn_lifecycles` terminal identity/time and its linked
  terminal assistant typed metadata; abandoned turns use their terminal
  lifecycle identity;
- Run actions: `backtest_jobs` terminal identity and `finished_at`, with
  succeeded eligible only after full finalization.

Typed actions that stop at confirmation, including `retest_run`, remain ordinary
chat turns until the user admits a Run action. They do not introduce a third
operation owner: `chat_turn_lifecycles` owns the confirmation turn, then
`backtest_jobs` owns any later admitted Run.

The server orders a boundary by canonical terminal time plus a stable source
kind/id tie-break. The database stores the normalized boundary fields, not a
client-provided opaque string. Reconciliation of one source remains idempotent
and cannot create two unread events for the same turn/job.

### 8.4 New read-state table

Add `conversation_read_states` as a narrow current-state table:

- `user_id uuid` — owner, references `profiles.id` with cascade;
- `conversation_id uuid` — references `conversations.id` with cascade;
- `read_through_occurred_at timestamptz null`;
- `read_through_source_kind text null`;
- `read_through_source_id uuid null`;
- `manual_unread_at timestamptz null`;
- `created_at timestamptz`;
- `updated_at timestamptz`;
- primary key `(user_id, conversation_id)`;
- unique conversation ownership must match the parent conversation owner.

Boundary constraints:

- `read_through_source_kind` is `chat_turn` or `backtest_job` when present;
- read-through time, kind, and id are either all null or all non-null;
- `manual_unread_at` is independent of the read-through boundary and is cleared
  only by a valid Mark-read mutation;
- read-through ordering can advance but never move backward.

The row stores read state only. It contains no title, message prose, model,
provider, route receipt, result metrics, or job payload.

RLS and writes:

- authenticated owners receive `SELECT` only;
- `PUBLIC`, `anon`, and `authenticated` cannot insert/update/delete or execute
  the server mutation function;
- server-owned read/unread RPCs verify `auth/user_id`, conversation ownership,
  cursor ownership, and monotonic advancement in one transaction;
- guest cleanup cascades the row; a guest workspace claim transfers it with
  the conversation graph if one exists.

### 8.5 Migration baseline

Existing history must not light up as unread on release.

- For each existing owned conversation, initialize read-through to its latest
  canonical terminal turn/job boundary.
- Conversations with no terminal boundary begin read and have null boundary
  fields.
- Existing manual unread does not exist, so `manual_unread_at` starts null.
- Do not modify conversation/message/job/lifecycle timestamps, ordering,
  titles, previews, artifacts, or evidence.
- The first new terminal boundary after migration may become unread normally.
- The backfill must be bounded/restart-safe for hosted migration practice and
  verified with owner/RLS readback before promotion.

### 8.6 List and reconciliation performance

- `GET /conversations`, chat rows from `GET /history`, and the single-activity
  endpoint return the same projection.
- Projection uses bounded indexed reads. It must not run one unbounded query per
  conversation or scan full messages/transcripts.
- Before projecting list state, the server may reconcile at most 20 stale
  ordinary lifecycle rows for the authenticated owner using the existing
  15-minute/database-clock rules. This extends the trigger surface, not the
  allowed outcomes or evidence predicate.
- Existing pagination order and cursors remain based on their current
  conversation/history activity fields. Read/status projection cannot become a
  new cursor pivot.

## 9. Frontend ownership and data flow

### 9.1 Replace the session-only attention Set

`attentionConversationIds: Set<string>` and the two-function
`chat-attention-state.ts` lifecycle are no longer sufficient as product truth.
Replace them with a typed conversation-id map that can merge:

1. server activity/read projections;
2. request-scoped local optimistic operation state;
3. presentation-only transport checking;
4. same-view manual-unread clearing guards.

The reducer/hook must be pure and independently tested. The existing Set may
remain temporarily only as a compatibility overlay during the rollout; it must
not survive as a competing owner.

### 9.2 Request ownership

- Replace the single `activeStreamConversationIdRef` as cross-conversation
  ownership with request/turn records keyed by conversation id and request id.
- Navigating away retires only active-transcript rendering and current
  `stage_start` presentation. It does not erase the local/canonical operation.
- A late callback verifies its own request identity before mutating state.
- Logout/account change clears authenticated local maps and aborts client
  transports without rewriting durable server state.
- The current conversation's composer/next-move lock reads only that
  conversation's unresolved work.

### 9.3 Polling and refresh

- `useRecentConversations` hydrates the additive activity projection.
- Refresh on bootstrap, local start/settle, navigation, window focus, and
  visibility resume.
- While at least one loaded/local operation is unresolved, refresh the bounded
  first conversation page at the current short polling cadence.
- Stop polling when no operation remains. Do not add a permanent idle poll.
- The active transcript may continue its existing job-id polling for result
  hydration, but inactive-conversation activity cannot depend on the current
  `messages` array or `ownsConversation` gate.
- On inactive completion, invalidate that transcript's browser-session cache so
  the next open reads the canonical result/recovery.

### 9.4 Optimistic read actions

- Mark unread/read updates the local row/header state immediately.
- The mutation is scoped to one conversation and one action request.
- Success replaces the optimistic state with the returned server projection.
- Failure rolls back only that mutation and shows localized recovery.
- A stale mutation response cannot overwrite a newer activity projection.

### 9.5 Viewport read proof

Automatic mark-read requires all of these at once:

- the active route, active transcript ref, and rendered transcript all belong
  to the same conversation;
- hydration is complete;
- `document.visibilityState === "visible"` and the window is focused;
- the dedicated latest-activity sentinel intersects the transcript scroll root;
- the client has the current server attention cursor;
- the same-view manual-unread guard is not armed.

The observer sends one idempotent mark-read per cursor and does not loop on
every render. Explicit **Mark as read** bypasses the viewport and view-epoch
requirements. If an already-open tab observes a new manual-unread state for its
active conversation, it arms the guard until that tab leaves/re-enters or
reloads, matching the tab where the action originated.

## 10. Failure and recovery behavior

- A stream disconnect, fetch exception, empty response, or `404` Run-action
  lookup alone never becomes completion/failure.
- Preserve a last-known active state and show localized checking while durable
  reconciliation runs.
- If the client has no known local or server activity and a cold activity read
  fails, it must not invent a spinner. It may show normal Recents plus a
  recoverable load error in the relevant surface.
- A stale ordinary turn reconciled to `abandoned` becomes needs attention and
  uses the existing adjacent Retry projection on open.
- A failed/canceled/expired backtest becomes needs attention and hydrates the
  existing job recovery. The sidebar does not invent retry controls.
- Failure to mark read leaves the marker in place. Failure to mark unread rolls
  back the reminder. Neither failure affects conversation content.
- Unknown future activity enums render safely as neutral checking/attention,
  never as completed and never by matching localized text.

## 11. Accessibility, localization, and motion

### 11.1 Keyboard and focus

- Row, ellipsis, menu items, header menu, and jump control retain visible focus
  rings.
- The row remains one navigation target; nested actions stop row navigation.
- Space and Enter open the focused row. Escape closes menus and returns focus.
- The 44px target rule applies even when the visual glyph/ring is smaller.

### 11.2 Screen reader semantics

- Every static string exists in `en` and `es-419`.
- Row labels announce one current state phrase, not every hidden underlying
  state.
- Ring, dot, and wave graphics are `aria-hidden`.
- Jump variants have explicit localized labels.
- One `aria-live="polite"` region announces meaningful transitions once. It
  does not read animated dots, polling, or token updates.
- Suggested English copy:
  - Working
  - Queued
  - Checking status
  - New activity
  - Marked unread
  - Needs your input
  - Needs attention
  - Mark as unread
  - Mark as read
  - Jump to new activity
  - Jump to the latest question
  - Jump to the latest recovery
- Spanish copy must be product-reviewed rather than generated at runtime.

### 11.3 Reduced motion

- Respect `prefers-reduced-motion` and existing Tailwind `motion-reduce`
  conventions.
- The spinner becomes a static open ring with the same accessible label.
- The three-dot wave becomes a static three-dot glyph.
- No flashing, rapid pulsing, or repeated scale animation.
- State changes may use one restrained fade; meaning is immediate without it.

### 11.4 Visual restraint

- Preserve the muted teal/neutral Argus palette and zero-shadow sidebar style.
- Do not introduce terminal-like green/red blinking.
- Failure/needs-attention styling reuses the shared failure-class visual owner.
- Test light and dark contrast; screenshots alone do not prove full WCAG
  compliance, so keyboard and assistive-technology behavior needs direct QA.

## 12. Edge-case disposition

| Edge case | Locked behavior |
| --- | --- |
| Active row is working | Ring remains visible even though row is selected |
| Active row completes at visible latest | Read receipt clears automatic unread after cursor arrives |
| Active row completes while scrolled up | Selected row gains attention; no auto-scroll |
| Tab hidden at completion | Remains unread until visible latest or explicit Mark as read |
| Open from Omnisearch to an older anchor | Does not clear; jump control leads to latest |
| Restore cached old scroll position | Does not clear |
| Multiple working conversations | Independent row state; one aggregate ring |
| Prior unread plus new work | Ring wins; unread survives underneath |
| Manual unread plus newer terminal failure | Needs-attention presentation wins; Mark as read clears through the visible newest cursor |
| Stale mark-read response | Cannot consume later activity or overwrite newer projection |
| Mark unread during active work | Manual state persists under ring; terminal activity becomes the more informative attention reason |
| Explicit Mark as read above latest | Clears by direct user choice; transcript position does not move |
| Pin/rename/archive after mark unread | Read state survives; action-specific `updated_at` behavior stays unchanged |
| Archive/soft delete | Item hides through existing filters; read state is preserved if restored |
| Hard deletion/guest cleanup | Read-state row cascades away |
| Guest workspace claim | Existing automatic read state transfers with the conversation graph |
| Guest manual unread | No new guest overflow management menu; manual action remains registered-account only |
| Quick-jump modifier held | Keycap stays right; marker/ring stays left; open/focused menu wins trailing slot |
| Activity rail visible | No overlap or taxonomy change; rail remains artifact navigation |
| Unknown server enum | Neutral safe state plus telemetry/logging; never silently "read" |
| Activity/read API unavailable | Keep last-known state; do not clear or fabricate terminal truth |

## 13. Reserved / parked scope

- **OS/browser push, email, and notification permissions** — parked until an
  explicit notification/revisit lane; the decision memo places push/local
  reminders later.
- **Mark all as read and unread filters/counts** — parked until the number of
  concurrent unread chats proves a need.
- **Snooze, remind me, due dates, or scheduled revisit** — these are reminder
  products, not read state.
- **Mark unread from a specific message** — this lane marks the conversation as
  a whole; per-message bookmarks need their own UX and durable boundary.
- **Right-click, swipe, or long-press accelerators** — optional follow-up after
  the discoverable overflow/header path is proven.
- **Notification settings or badges outside Argus** — no permission prompts or
  service-worker work.
- **Supabase Realtime/WebSockets** — current bounded polling remains the private
  Alpha transport. Realtime may replace the transport later without changing
  the projection contract.
- **Activity-rail changes** — no new tick type, progress tick, or unread tick.
- **Omnisearch unread decoration** — Omnisearch remains artifact recall;
  Recents remains chat navigation.
- **Conversation sorting changes** — working/unread does not become a rank
  boost or a new section.
- **Analytics event expansion** — no PostHog behavior ownership or raw read
  telemetry.
- **Broad `ChatInterface.tsx` refactor** — extract only the focused activity/
  viewport/request owners needed for this lane.

## 14. Contract gates

- `docs/PRODUCT.md` — add working/read/unread continuity and Mark as unread/read
  to chat management without creating an inbox product.
- `docs/ARCHITECTURE.md` — add `conversation_read_states`, the derived activity
  projection, request-scoped SSE versus durable lifecycle ownership, and
  bounded polling/reconciliation.
- `docs/API_CONTRACT.md` — define `ConversationActivity`, additive Conversation/
  History fields, GET/PATCH activity endpoints, cursor semantics, guest rules,
  and errors.
- `docs/DATA_MODEL.md` — define the read-state table, indexes, RLS, migration
  baseline, cleanup/claim behavior, and no-`updated_at` sorting side effect.
- `.agent/designs/argus/DESIGN.md` — document Recents ring/dot precedence,
  state-aware Jump to latest, overflow placement, reduced motion, and 44px
  target requirements.
- `docs/api/openapi.yaml` — regenerate from FastAPI after the additive public
  contract lands.
- `docs/superpowers/specs/2026-07-31-recents-quick-jump-attention-marker.md` —
  add a historical follow-up pointer explaining that this approved later lane
  evolves attention semantics while preserving its geometry.
- `docs/specs/private-alpha-next-roadmap.md` and
  `docs/specs/private-alpha-interim-roadmap.md` — record exact landing evidence
  only after implementation is accepted; do not claim completion from this
  spec.
- EN/es-419 locale catalogs — every new static label and toast.
- Supabase migration — additive table/RLS/RPC/backfill only; no hosted apply in
  the feature lane.

## 15. Execution contract

### Delivery mode

`normal_feature_branch` from the current remote `codex/private-alpha-next`
integration head. This specification was reviewed at
`53c36d40bbc6e058af7d27c687504235c2fd48d8`; the implementation branch was
rebased onto `403ea11410da2746f132223e44aac70c4a4b5534` before delivery.

### PR shape

Use two serialized, independently reviewable PRs because durable read truth and
the visible projection cross schema/API/frontend ownership:

1. **Activity/read foundation PR**
   - this spec as its first commit;
   - canon/API/data-model updates;
   - additive migration, RLS, backfill, typed schemas, owner-scoped endpoint,
     list/history projection, memory/Postgres parity, and backend tests;
   - no user-visible marker replacement yet.
2. **Conversation activity UI PR**
   - typed frontend projection/reducer and request ownership;
   - Recents expanded/collapsed/Quick Peek states;
   - header/row unread actions;
   - state-aware Jump to latest and viewport read sentinel;
   - frontend/E2E/accessibility/localization/browser evidence.

The second PR begins only after the first contract is approved and available on
the integration base. Do not stack unreviewed schema and UI branches.

### Expected implementation surfaces

Backend/data, bounded to the contract:

- `src/argus/api/schemas.py`
- `src/argus/api/routers/conversations.py`
- `src/argus/api/routers/history.py`
- Supabase gateway/history reader and the existing lifecycle/job
  reconciliation/finalization seams
- one additive Supabase migration
- focused API, Postgres, RLS, history-bound, and lifecycle/job tests

Frontend, bounded to the projection:

- `web/lib/argus-api.ts`
- replacement/evolution of `web/lib/chat-attention-state.ts`
- a focused conversation-activity hook/reducer rather than more unrelated
  `ChatInterface.tsx` state
- `web/components/chat/ChatInterface.tsx`
- `web/components/chat/useChatScrollControls.ts` or one focused viewport hook
- `web/components/chat/ChatHeaderMenu.tsx`
- `web/components/sidebar/ChatSidebar.tsx`
- `web/components/sidebar/RecentChatActions.tsx`
- `web/components/sidebar/RecentsQuickPeek.tsx`
- `web/components/sidebar/SidebarNavButton.tsx` only for the aggregate overlay
- locale catalogs and focused tests

### Protected surfaces

- LangGraph interpretation/routing and stage taxonomy
- SSE frame ordering and request-scoped transport
- confirmation/run idempotency and quota accounting
- immutable messages, results, evidence, and DecisionNotes
- Recents grouping, pagination, sorting, progressive disclosure, and quick-jump
  shortcut semantics
- Omnisearch/Idea Ledger behavior
- conversation activity rail taxonomy/geometry
- provider/model routing and all provider-facing code
- production deploys, hosted migrations, and tester exposure

### Proof required

Foundation PR:

- focused memory and Supabase API tests for projection/action parity;
- RLS proof: owner select, foreign/anon denial, server-only mutation;
- migration proof that existing conversations start read and no content/sort
  timestamps change;
- cursor-race proof that a stale mark-read cannot consume a newer terminal;
- ordinary terminal, awaiting-input, abandoned/reconciled, job queued/running/
  succeeded/failed/canceled/expired, and multiple-operation precedence tests;
- pagination/cursor and bounded-query regression tests;
- generated OpenAPI structural compatibility.

UI PR:

- focused Bun tests for state reduction, request ownership, menu actions,
  scroll sentinel, Recents/Quick Peek/aggregate presentation, job polling
  decoupling, localization, reduced motion, and quick-jump coexistence;
- browser E2E for every primary journey in section 6;
- EN and es-419 desktop evidence;
- 390px mobile/coarse-pointer evidence;
- keyboard-only and reduced-motion evidence;
- one real-auth ordinary-turn background journey and one authorized real
  backtest job journey in production-parity local QA; Browser QA spends real
  tokens and provider calls, so keep it to the documented gate;
- full frontend `bun test`, `bun run lint`, and `bun run build`;
- focused backend suites, full `tests/` gate where required by branch policy,
  modularity budget, and `git diff --check`.

### Where it stops

Each implementation slice stops at a Draft or posted PR targeting
`codex/private-alpha-next` with exact-SHA evidence. The founder reviews and
merges. No hosted migration, Render deploy, tester invitation, production
promotion, or merge is authorized by this spec.

## 16. Acceptance matrix

### 16.1 Deterministic backend cases

1. Ordinary `accepted -> running -> completed` projects working then new
   activity.
2. Typed clarification projects needs input without prose matching.
3. `recoverable_failed`, `abandoned`, and reconciled failure project needs
   attention.
4. Job queued/running remains working after chat SSE finishes.
5. Job succeeded without hydrateable Run projects checking, not ready.
6. Finalized succeeded job projects new activity exactly once.
7. Failed/canceled/expired job projects needs attention.
8. Multiple active rows in one conversation use deterministic precedence.
9. Multiple conversations remain isolated.
10. Mark unread is idempotent and does not change conversation ordering.
11. Mark read through the current cursor clears current state.
12. Mark read through a stale cursor leaves a newer event unread.
13. Manual unread plus newer event produces the newer, more useful attention
    reason.
14. Existing-row migration baseline starts read.
15. Guest read projection, cleanup, and claim stay owner-safe; manual unread UI
    remains absent for guests.
16. Foreign/deleted/out-of-workspace endpoints return non-leaking 404.
17. List/history pagination and bounded-query limits remain unchanged.

### 16.2 Deterministic frontend cases

1. Row visual precedence matches section 3.3.
2. Selected working/unread rows keep their marker.
3. Collapsed aggregate ring wins over aggregate unread dot.
4. Quick Peek matches expanded Recents.
5. Menu labels toggle and optimistic failures roll back.
6. Ellipsis meets 44px, focus, hover, Escape, and coarse-pointer behavior.
7. Quick-jump hint and left marker coexist without title/subtitle movement.
8. Current-conversation lock ignores unrelated working chats.
9. Late completion from A cannot clear B's request or composer state.
10. Inactive job polling/activity no longer depends on active `messages`.
11. Scroll threshold shows the control but only sentinel visibility marks read.
12. Working/new/failure/plain jump variants preserve one target and behavior.
13. Same-view manual unread guard prevents immediate clearing.
14. Window blur/hidden document prevents automatic read.
15. Reduced motion removes rotation/wave without removing meaning.
16. Announcements fire once per meaningful transition.

### 16.3 Browser journeys

1. Start ordinary work in A, switch to B, observe A ring, settle A, observe dot,
   reopen A, and clear only at visible latest.
2. Start a durable backtest in A, switch away after SSE ends, observe ring
   through queued/running, and transition only after canonical terminal truth.
3. Start work in A and B; settle them in both orders and verify isolation.
4. Stay in A, scroll up, observe the three-dot jump state, receive completion
   without scroll movement, then jump and clear.
5. Reopen unread A at a restored older scroll position and through an older
   Omnisearch anchor; keep attention until latest.
6. Mark read/unread from the Recents menu and active header, including the
   same-view guard and no reorder.
7. Verify needs-input, retryable failure, canceled/expired, and transport-
   ambiguity checking presentation.
8. Verify expanded, collapsed, Quick Peek, mobile drawer/coarse pointer,
   keyboard, English, Spanish, dark/light, and reduced-motion states.
9. Preserve PR #302 disclosure, PR #299 switching/scroll, PR #315 activity rail,
   and PR #324 quick-jump/menu precedence.

## 17. Stop conditions

Stop and report to the founder if:

- any visual activity state would require frontend prose matching, timers, or
  inference beyond typed lifecycle/job/read contracts;
- a backtest would be presented as complete before canonical result
  finalization/hydration;
- the read-state write would change conversation ordering or message/artifact
  timestamps;
- an opaque read cursor cannot be validated owner/conversation-scoped and
  monotonically;
- existing conversations cannot be baselined as read without mutating durable
  content or running an unsafe hosted backfill;
- list projection requires unbounded transcript scans, N+1 queries, or a new
  maintained history architecture;
- stale lifecycle projection requires changing the approved terminal evidence
  predicate or 15-minute reconciliation outcomes rather than only adding a
  bounded trigger;
- multiple-conversation request isolation would require a second chat runtime,
  WebSocket, or change to LangGraph/SSE ownership;
- the UI needs to change Recents sorting, progressive disclosure, quick-jump
  bindings, Omnisearch, or the activity rail to make room;
- the menu cannot meet 44px touch and keyboard focus requirements in its
  existing trailing slot;
- the feature would expose providers, models, workflow ids, raw errors,
  conversation prose, or private titles in read-state records/analytics;
- guest support requires broadening guest conversation management beyond the
  bounded automatic-read projection;
- implementation expands into OS/browser notifications, reminders, bulk unread
  management, per-message bookmarks, Realtime, or a new inbox surface;
- required English/Spanish, mobile, keyboard, reduced-motion, persistence, or
  live browser evidence fails after deterministic tests pass;
- any hosted migration, deploy, tester exposure, or merge would be needed to
  continue without separate founder approval.

## Sources

### Argus authority

- `docs/PRODUCT.md` — Product Truth, Recents Surface, Object Management,
  Continuity, Product Experience Standards, and Golden Path.
- `docs/ARCHITECTURE.md` — Frontend Responsibilities, Communication Protocols,
  Durable Chat-Turn Lifecycle Ownership, Backtest Job Status, Failure Handling,
  and frontend-renders/backend-owns separation.
- `docs/API_CONTRACT.md` — durable ordinary turn lifecycle, stable Run action
  reconciliation, message hydration, chat SSE, backtest-job polling, and
  History/Recents contracts.
- `docs/DATA_MODEL.md` — conversations, messages, chat-turn lifecycles,
  backtest jobs, RLS, History, and indexing boundaries.
- `.agent/designs/argus/DESIGN.md` — calm progress, no fake timers, Recents
  continuity, 44px targets, accessibility baseline, motion restraint, and
  mobile web.
- `docs/specs/private-alpha-interim-roadmap.md` — Always Progresses standing
  bar, PR #299 switching, PR #302 Recents, PR #315 rail, PR #317 shortcuts, and
  exact-head QA discipline.
- `docs/specs/private-alpha-next-decision-memo.md` section 15.2 — Recents stays
  scan-first chat navigation, contextual owner actions use overflow/right
  surfaces, and press-and-hold is not the primary web action.
- `docs/superpowers/specs/2026-07-31-recents-quick-jump-attention-marker.md` —
  accepted left marker lane and right trailing-slot coexistence.
- `docs/superpowers/specs/2026-07-31-conversation-activity-rail.md` — distinct
  current-conversation landmark navigation ownership.
- `web/lib/chat-attention-state.ts` — current session-local settle/open Set.
- `web/components/chat/ChatInterface.tsx` — current single stream state,
  navigation retirement, viewport control, and active transcript ownership.
- `web/lib/chat-run-reconciliation.ts` — current message-owned job polling.
- `web/components/chat/useChatScrollControls.ts` — current 240px navigation
  threshold.
- `web/components/sidebar/ChatSidebar.tsx`,
  `web/components/sidebar/RecentChatActions.tsx`, and
  `web/components/chat/ChatHeaderMenu.tsx` — current marker lane, trailing
  menu, and owner action surfaces.
- `web/e2e/issue-245-recents-progressive-disclosure.spec.ts` — current settle-
  elsewhere/open-to-clear browser lifecycle.

### External inspiration

- [OpenAI: Introducing the Codex app](https://openai.com/index/introducing-the-codex-app/)
  — parallel task supervision and work continuing independently.
- [OpenAI Help: Deep research](https://help.openai.com/en/articles/10500283-deep-research)
  — in-product progress and completion notification pattern.
- [Anthropic: Using extended thinking](https://support.anthropic.com/en/articles/10574485-using-extended-thinking)
  — visible ongoing model work.
- [Google: Use Deep Research in Gemini Apps](https://support.google.com/gemini/answer/15719111?hl=en)
  — progress visibility for longer research actions.
- [Perplexity: Advanced Deep Research](https://www.perplexity.ai/help-center/en/articles/13600190-what-s-new-in-advanced-deep-research)
  — explicit progress for long-running work.
- [Microsoft Teams: Mark a chat as unread](https://support.microsoft.com/en-us/teams/chat/hide-unhide-mute-add-a-chat-to-favorites-or-mark-a-chat-as-unread-in-microsoft-teams)
  — reminder semantics and More-options placement.
- [W3C: ARIA status role](https://www.w3.org/WAI/WCAG21/Techniques/aria/ARIA22)
  — polite status announcements.
- [W3C: Animation from interactions](https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions)
  — reduced-motion considerations.

External products are inspiration, not Argus authority. The convergence is the
useful part: long-running work needs an in-thread status, a persistent list
signal, and a meaningful terminal transition. Argus's canonical lifecycle,
chat-first surface, and calm design system determine the implementation.

### Inference

- A two-axis operation/attention model is inferred as the smallest structure
  that prevents one spinner/dot from lying about several different states.
- A server-issued cursor is inferred as necessary to prevent a late mark-read
  request from consuming a newer unseen terminal event.
- A narrow read-state table is inferred as safer than placing read mutations on
  `conversations.updated_at`, which currently participates in Recents order and
  cursors.
- Reusing the existing Jump-to-latest control is inferred as the least-cluttered
  way to represent work below the viewport while preserving one obvious scroll
  action.
