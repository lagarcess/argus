# Recents Quick-Jump Attention Preservation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Recents quick-jump hints into right-aligned exact-chord keycaps
without changing the existing attention marker, numbering, or attention
lifecycle.

**Architecture:** Reuse the shared `QuickJumpBadge` exact-chord presentation in
both Recents surfaces. Expanded Recents keeps its left marker gutter and gives
the hint the existing trailing action slot; the actions component owns
menu/focus precedence. Recents Quick Peek removes its badge-only leading column
and adds the same trailing keycap.

**Tech Stack:** Next.js 16, React 19, TypeScript, Tailwind CSS, Bun tests,
Playwright.

## Global Constraints

- Preserve pinned-first numbering, the nine-item cap, and physical
  `KeyboardEvent.code` matching.
- Preserve `Cmd+Option+1-9` on Mac and `Ctrl+Shift+1-9` on Windows/Linux.
- Do not modify attention state, shortcut bindings, Omnisearch, API contracts,
  persistence, schema, or locale copy.
- Keep shortcut keycaps `aria-hidden` and the conversation row interactive.
- An open or keyboard-focused chat action trigger has precedence over the hint.
- Stop at a Draft PR targeting `codex/private-alpha-next`; do not merge or
  deploy.

---

### Task 1: Lock the presentation contract with failing tests

**Files:**
- Modify: `web/__tests__/keyboard-shortcuts-overlay.test.ts`
- Modify: `web/__tests__/chat-sidebar-attention.test.ts`

- [ ] Require expanded Recents and Recents Quick Peek to use
  `presentation="shortcut_hint"` with `usesCommandKey`.
- [ ] Require the left `w-11` lane to remain badge-free and the exact-chord hint
  to render through a separate trailing slot.
- [ ] Require `RecentChatActions` to accept a hint and give an open or focused
  trigger precedence.
- [ ] Run the focused Bun tests and verify failure against the current left
  numeric badge implementation.

### Task 2: Implement the two right-aligned Recents presentations

**Files:**
- Modify: `web/components/sidebar/ChatSidebar.tsx`
- Modify: `web/components/sidebar/RecentChatActions.tsx`
- Modify: `web/components/sidebar/RecentsQuickPeek.tsx`

**Interfaces:**
- `RecentChatActionsProps.quickJumpHint?: ReactNode`
- Both surfaces expose `data-quick-jump-hint="<number>"` on the non-interactive
  trailing wrapper for browser assertions.

- [ ] Calculate each row number once and construct the shared exact-chord
  `QuickJumpBadge` with the current platform mode.
- [ ] Leave expanded Recents' `w-11` marker lane empty and render the keycap in
  the absolute right-side action slot.
- [ ] Clear only right-side text space while the longer keycap is visible; do
  not move the title/subtitle left edge or change row height.
- [ ] Let `RecentChatActions` show the supplied hint only while its menu is
  closed and trigger is unfocused. Keep the real trigger mounted when it owns
  precedence and keep `data-actions` on that trigger.
- [ ] Remove Quick Peek's leading badge-only column, make its text block
  flexible, and right-align the same exact-chord keycap.
- [ ] Run the focused Bun tests and verify the presentation contract is green.

### Task 3: Prove combined attention, layout, and menu behavior in a browser

**Files:**
- Modify: `web/e2e/issue-245-recents-progressive-disclosure.spec.ts`

- [ ] Add fixture support for dark mode plus Mac and non-Mac user agents.
- [ ] Extend the settled-turn scenario to record row/title/subtitle bounds,
  reveal the keycap, verify attention-left and chord-right separation, release
  without clearing attention, then execute the quick jump and verify the
  existing open path clears attention.
- [ ] Add coverage that an open or keyboard-focused ellipsis keeps the trailing
  slot while modifier hints are active.
- [ ] Add Quick Peek coverage for unchanged title coordinates, exact-chord
  presentation, right alignment, and selection.
- [ ] Run English/Mac and Spanish/non-Mac variants so `⌘⌥1` and
  `Ctrl+Shift+1` both exercise the layout.

### Task 4: Close documentation and verification gates

**Files:**
- Modify: `docs/superpowers/specs/2026-07-31-keyboard-shortcuts-overlay.md`

- [ ] Add a pointer to the corrective spec and record the right-aligned exact
  chord as the accepted endpoint.
- [ ] Capture dark-mode evidence for Recents at rest, combined attention plus
  hint, Quick Peek, Settings comparison, and Spanish/non-Mac combined state.
- [ ] Run `bun test`, `bun run lint`, and `bun run build` from `web`.
- [ ] Run `poetry run python scripts/check_modularity_budget.py` and
  `git diff --check` from the repository root.
- [ ] Audit the final diff against every locked decision and protected surface.
- [ ] Commit implementation, tests, and the historical pointer as
  `fix(web): align Recents quick-jump hints`.
- [ ] Push the worker branch and open a Draft PR targeting
  `codex/private-alpha-next` with exact-SHA evidence. Do not merge or deploy.
