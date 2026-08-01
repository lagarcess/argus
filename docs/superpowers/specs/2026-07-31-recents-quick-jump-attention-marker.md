# Recents quick-jump hint alignment + attention-marker preservation

Status: **DELIVERED** by PR #324, merged into `codex/private-alpha-next` as
`812c8fef`. Retained as the presentation and attention-preservation record.

Make Recents quick-jump hints match Settings without obscuring the existing
out-of-focus conversation attention marker or moving conversation-row content.

Founder-locked 2026-07-31, after visual review of merged PR #317 exposed a
presentation gap between Recents and Settings and a same-gutter collision with
the existing Recents attention marker.

## 1. Why

`docs/PRODUCT.md` defines Recents as a continuity surface whose purpose is to
help users resume prior work and reduce navigation friction. The current
quick-jump behavior works, but its presentation weakens that job:

- Settings shows the exact quick-jump chord in a compact, right-aligned keycap.
- Expanded Recents and the temporary Recents peek show only a number on the
  left, even though the real Mac chord is `Cmd+Option+1-9` and the real
  Windows/Linux chord is `Ctrl+Shift+1-9`.
- Expanded Recents uses that same left region for the session-local attention
  dot shown when an out-of-focus conversation finishes and needs the user's
  attention. When Command is held, the centered number badge can overlap that
  dot.

This is a narrow trust-and-continuity correction to PR #317, which the active
roadmap records as the centralized keyboard overlay and quick-navigation
system. It does not reopen the shortcut map or the broader sidebar design.

### Alternatives considered

1. **Right-aligned full chord -- selected.** Reuses the Settings convention,
   tells the truth about the executable command, and leaves the attention lane
   alone.
2. **Right-aligned number only -- rejected.** Avoids the marker but still hides
   required modifiers and preserves the Recents/Settings inconsistency.
3. **Redesign or remove the left gutter -- rejected for this lane.** The gutter
   predates the attention marker, but the marker now relies on that protected
   space. Changing it adds risk without being necessary to fix the shortcut
   hint.

## 2. Locked decisions

1. **Quick-jump behavior does not change.** Visible targets remain capped at
   nine. Pinned visible chats keep number priority over unpinned chats. The
   approved shortcuts remain `Cmd+Option+1-9` on Mac and `Ctrl+Shift+1-9` on
   Windows/Linux, matched through physical `KeyboardEvent.code` values.
2. **Both Recents surfaces use the exact-chord keycap.** Expanded Recents and
   `RecentsQuickPeek` must render the full platform-specific chord through the
   existing shared keycap/registry display path. They must not render a bare
   `1-9` badge or hardcode a second display map.
3. **The keycap is right-aligned.** It occupies a stable trailing command slot,
   following the existing Settings and sidebar-command convention. Appearing or
   disappearing must not change row height, the conversation title's left
   position, or the subtitle's left position.
4. **The attention marker and its lane are protected.** Do not change
   `attentionConversationIds`, `attentionAfterTurnSettled`,
   `attentionAfterConversationOpen`, `data-has-attention`, the localized
   accessible "New activity" label, or the teal dot's left-side presentation.
   The existing left gutter remains in place.
5. **Combined state is required.** A row may simultaneously show its attention
   dot on the left and its exact quick-jump chord on the right. The two must be
   visually separate, and the row's accessible name must continue to announce
   new activity.
6. **Opening the conversation remains the clear action.** Revealing or using a
   quick-jump hint must not clear attention early. The attention marker clears
   only through the existing conversation-open path.
7. **The trailing-slot precedence is deterministic.** At rest, the existing
   Recents hover/ellipsis actions behave exactly as they do today. While
   quick-jump hints are active, the exact-chord keycap owns that trailing slot.
   Releasing the modifier restores the normal action affordance. If a chat
   action menu is already open, that open menu keeps precedence and quick-jump
   hints must not cover or dismiss it.
8. **No title realignment in this lane.** The permanent left indentation is not
   introduced by the quick-jump reveal and is part of the protected marker
   lane. Any future change to that baseline alignment requires its own visual
   review with the attention marker present.
9. **Presentation remains non-interactive and accessible.** Shortcut keycaps
   remain `aria-hidden`; the conversation row remains the interactive target
   with its existing focus, selection, and attention semantics.
10. **Use one presentation rule.** Extend the existing shared
    `QuickJumpBadge`/`KeyboardShortcutKeycap` path rather than creating a
    Recents-only keycap component or duplicating platform-display logic.

## 3. Reserved / parked scope

- **Shortcut remapping or new bindings** -- PR #317's approved registry remains
  authoritative; this lane changes presentation only.
- **F2 rename follow-up** -- remains the separate unresolved item recorded in
  the PR #317 scope note.
- **Persistent notifications or cross-session attention state** -- the Recents
  marker remains session-local; no backend or database model is added.
- **Conversation activity rail changes** -- PR #315's transcript-edge turn map
  is a different feature and is untouched.
- **Attention-marker redesign** -- no new color, icon, animation, placement, or
  clearing behavior.
- **Broad Recents-row or hover-menu redesign** -- only the command-slot
  coexistence needed for this correction is in scope.
- **Baseline conversation-title indentation changes** -- parked because they
  would require redesigning the protected attention lane.
- **Omnisearch or typed-action behavior** -- remains completely untouched.

## 4. Contract gates

- `docs/superpowers/specs/2026-07-31-keyboard-shortcuts-overlay.md` -- add a
  short follow-up pointer when the correction lands so the historical PR #317
  record does not imply that the left number badge remains the accepted visual
  endpoint.
- `docs/API_CONTRACT.md` -- no change expected. Stop if an API change appears
  necessary.
- `docs/DATA_MODEL.md` -- no change expected. Stop if durable attention or
  schema work appears necessary.
- `docs/api/openapi.yaml` -- no change expected because no request or response
  contract changes.
- EN/es-419 locale files -- no new copy is expected because the chord comes
  from the registry, but both languages remain required browser-QA surfaces.

## 5. Execution contract

- **Delivery mode:** `normal_feature_branch` from the current
  `codex/private-alpha-next` integration head. This lane started from
  `379e9f49be230105c9a04a42ce6624eac21a3c58`.
- **PR shape:** one frontend/docs/test-only PR targeting
  `codex/private-alpha-next`. Keep the spec as the first lane commit and the
  implementation as a later reversible commit.
- **Expected implementation surfaces:**
  `web/components/sidebar/ChatSidebar.tsx`,
  `web/components/sidebar/RecentsQuickPeek.tsx`, the existing shared keyboard
  presentation component only if needed, and focused tests. A minimal
  Recents-action integration change is allowed only to enforce the locked
  trailing-slot precedence.
- **Protected surfaces:** `web/lib/chat-attention-state.ts`, the attention-state
  ownership in `web/components/chat/ChatInterface.tsx`, shortcut matching and
  bindings in `web/lib/keyboard-shortcuts.ts`, Omnisearch, backend routes,
  database models, and migrations.
- **Focused automated proof:**
  - Preserve the existing quick-jump tests for pinned-first numbering, the
    nine-item cap, and physical digit matching.
  - Preserve `web/__tests__/chat-attention-state.test.ts` and
    `web/__tests__/chat-sidebar-attention.test.ts` unchanged in meaning.
  - Assert that expanded Recents and `RecentsQuickPeek` both use the shared
    exact-chord keycap presentation.
  - Add a combined-state browser test: settle a turn outside its conversation,
    verify the attention marker, hold the platform modifier to reveal the
    right-side chord, verify both remain present and separate, use quick-jump to
    open the conversation, then verify attention clears through the existing
    path.
  - Measure the row and text bounding boxes before and during modifier hold;
    row height and title/subtitle left positions must not change.
- **Visual proof:** capture, from the exact candidate SHA:
  1. Expanded Recents with an attention marker at rest.
  2. The same row with the modifier held, showing the left attention marker and
     right exact-chord keycap together.
  3. Temporary Recents peek with right-aligned exact-chord keycaps.
  4. Nested Settings quick-jump beside Recents as the visual-convention
     comparison.
  Run the combined-state review in EN and es-419 and verify dark mode, which is
  the surface where the gap was reported.
- **Hermetic gates:** from `web`, run `bun test`, `bun run lint`, and
  `bun run build`; then run `poetry run python
  scripts/check_modularity_budget.py` and `git diff --check` from the repository
  root.
- **Where it stops:** a Draft or posted PR with the named screenshots and exact
  test evidence. The founder reviews and merges. No deploy or tester exposure
  is authorized by this spec.

## 6. Stop conditions

- If the correction requires moving, resizing, recoloring, hiding, or changing
  the clearing semantics of the attention marker or its left gutter, stop and
  report to the founder.
- If the right-side keycap cannot coexist with the existing chat action menu
  without disabling, covering, or unexpectedly dismissing that menu, stop and
  report instead of weakening either affordance.
- If the keycap text would differ from the central registry's executable chord,
  stop and fix the shared display path rather than hardcoding Recents copy.
- If holding or releasing modifiers changes row height or the left position of
  the title/subtitle, stop and treat it as a failed acceptance gate.
- If a row cannot visibly retain both attention and quick-jump state, stop; do
  not choose one signal to hide the other.
- If implementation requires changing quick-jump numbering, pinned priority,
  shortcut bindings, Omnisearch, typed-action semantics, backend contracts,
  persistence, or schema, stop and return for a separate scope decision.

## Sources

### Argus authority

- `docs/PRODUCT.md`, "Recents Surface" -- continuity, fast resumption, and
  reduced navigation friction.
- `.agent/designs/argus/DESIGN.md`, "Recents, Collections, and Search" and
  "Accessibility Baseline" -- Recents continuity and non-color/accessibility
  requirements.
- `docs/specs/private-alpha-next-roadmap.md` -- PR #317 is the landed keyboard
  overlay and quick-navigation checkpoint.
- `docs/superpowers/specs/2026-07-31-keyboard-shortcuts-overlay.md` -- shared
  quick-jump behavior, pinned priority, existing-action coexistence, and the
  frontend-only boundary.
- `web/lib/chat-attention-state.ts` and
  `web/components/sidebar/ChatSidebar.tsx` -- current attention lifecycle and
  left marker presentation.
- `web/e2e/issue-245-recents-progressive-disclosure.spec.ts` -- current browser
  contract for marking an out-of-focus settled turn and clearing it on open.

### External inspiration

- None. The accepted Settings keycap convention already exists inside Argus.

### Inference

- The historical gutter was not introduced specifically for the attention
  marker, but the current marker uses that protected visual lane. Preserving
  the lane is the smallest safe correction.
- The current centered number badge and the attention dot can overlap because
  both occupy the same left region; moving only the shortcut presentation to a
  stable trailing slot removes that collision without changing behavior.
