# Keyboard Shortcuts Quick-Navigation Implementation Plan

Status: **COMPLETED HISTORICAL PLAN.** PR #317 merged into
`codex/private-alpha-next` as `2ff6f3c6`. Do not execute these tasks again;
the active roadmap owns any future shortcut follow-up.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Extend the existing overlay into localized quick navigation with real chat actions and one numbered quick-jump primitive shared by Recents and nested Settings.

**Architecture:** web/lib/keyboard-shortcuts.ts remains the only registry for handler matching and display. A useQuickJump hook and QuickJumpBadge are the shared primitive; Recents and ProfileMenu supply visible targets and their established click callbacks. ChatInterface continues to own mutation side effects, so keyboard delete retains its existing confirmation.

**Tech Stack:** Next.js 16, React 19, TypeScript, Bun tests, i18next, Playwright CLI.

## Global Constraints

- Preserve Command-K/Control-K Omnisearch and all existing typed-action behavior.
- Registry matching uses KeyboardEvent.code for shifted punctuation and jump digits, never locale-dependent KeyboardEvent.key.
- Bind new chat Command/Control-Shift-Period; Recents peek Command/Control-Shift-Comma; delete Command/Control-Shift-X; rename F2; sidebar + Recents Command/Control-Shift-Backslash; Settings Command/Control-Shift-Semicolon; pin toggle Command/Control-Shift-Quote; quick-jump Command-Option-1–9 on Mac and Control-Shift-1–9 on Windows/Linux.
- Number only rendered Recents rows, cap all surfaces at nine, and put pinned chats first without moving their visual order.
- Keyboard delete, rename, and pin call established header actions. No backend, schema, environment, remapping, or Omnisearch change.
- Localize every new static string in web/public/locales/en/common.json and web/public/locales/es-419/common.json.

---

### Task 1: Register all actions and physical-key gestures

**Files:**

- Modify: web/lib/keyboard-shortcuts.ts
- Modify: web/__tests__/keyboard-shortcuts.test.ts

**Interfaces:**

- Produces KeyboardShortcutId, KEYBOARD_SHORTCUTS, matchesKeyboardShortcut, keyboardShortcutDisplay, and quickJumpIndexForEvent.
- Extends the keyboard-event input with altKey, code, ctrlKey, key, metaKey, and shiftKey.

- [ ] **Step 1: Write the failing registry test**

~~~ts
expect(KEYBOARD_SHORTCUTS.map(({ id }) => id)).toEqual([
  "omnisearch", "keyboard_shortcuts", "new_chat", "open_recents",
  "delete_focused_chat", "rename_focused_chat", "expand_sidebar_recents",
  "open_settings", "toggle_pin_focused_chat", "quick_jump",
]);
expect(matchesKeyboardShortcut("open_recents", {
  code: "Comma", key: "<", metaKey: true, ctrlKey: false,
  shiftKey: true, altKey: false,
})).toBe(true);
expect(quickJumpIndexForEvent({
  code: "Digit2", key: "@", metaKey: false, ctrlKey: true,
  shiftKey: true, altKey: false,
}, false)).toBe(1);
~~~

- [ ] **Step 2: Run the test and verify expected red**

Run: cd web && bun test __tests__/keyboard-shortcuts.test.ts

Expected: the new actions and quick-jump matcher are absent.

- [ ] **Step 3: Implement the smallest typed matcher**

~~~ts
export function quickJumpIndexForEvent(event: KeyboardShortcutEvent, mac: boolean) {
  const prefix = mac
    ? event.metaKey && event.altKey && !event.ctrlKey && !event.shiftKey
    : event.ctrlKey && event.shiftKey && !event.metaKey && !event.altKey;
  const match = /^Digit([1-9])$/.exec(event.code);
  return prefix && match ? Number(match[1]) - 1 : null;
}
~~~

Keep the existing two actions on their current Command-or-Control path. Shifted actions require exact Shift and the declared physical code.

- [ ] **Step 4: Re-run focused test and commit**

Run: cd web && bun test __tests__/keyboard-shortcuts.test.ts

Expected: PASS for registry IDs, display tokens, and Digit1–Digit9 matching.

~~~bash
git add web/lib/keyboard-shortcuts.ts web/__tests__/keyboard-shortcuts.test.ts
git commit -m "feat(web): register keyboard quick-navigation bindings"
~~~

### Task 2: Build one reusable quick-jump primitive

**Files:**

- Create: web/components/keyboard/useQuickJump.ts
- Create: web/components/keyboard/QuickJumpBadge.tsx
- Create: web/__tests__/quick-jump.test.ts

**Interfaces:**

- Produces numberQuickJumpItems(items) and useQuickJump({ enabled, items, onSelect }) returning { isQuickJumpActive, numberFor }.
- Each item is { id: string; pinned?: boolean }; selection receives that item id.

- [ ] **Step 1: Write failing ordering tests**

~~~ts
expect(numberQuickJumpItems([
  { id: "recent", pinned: false },
  { id: "pinned", pinned: true },
  { id: "another-pinned", pinned: true },
])).toEqual([
  { id: "pinned", pinned: true, number: 1 },
  { id: "another-pinned", pinned: true, number: 2 },
  { id: "recent", pinned: false, number: 3 },
]);
expect(numberQuickJumpItems(
  Array.from({ length: 11 }, (_, index) => ({ id: String(index) })),
)).toHaveLength(9);
~~~

- [ ] **Step 2: Run the test and verify expected red**

Run: cd web && bun test __tests__/quick-jump.test.ts

Expected: the shared primitive module is unresolved.

- [ ] **Step 3: Implement hook and passive badge**

~~~ts
export function numberQuickJumpItems(items: readonly QuickJumpItem[]) {
  return [...items]
    .sort((left, right) => Number(Boolean(right.pinned)) - Number(Boolean(left.pinned)))
    .slice(0, 9)
    .map((item, index) => ({ ...item, number: index + 1 }));
}
~~~

The hook owns one document keydown/keyup listener, calls the registry matcher, shows badges while required modifiers are held, and resets on window blur. QuickJumpBadge is aria-hidden, non-interactive, and never removes existing hover actions.

- [ ] **Step 4: Re-run focused test and commit**

Run: cd web && bun test __tests__/quick-jump.test.ts

Expected: PASS for pin priority, nine-item limit, and physical digit selection.

~~~bash
git add web/components/keyboard/useQuickJump.ts web/components/keyboard/QuickJumpBadge.tsx web/__tests__/quick-jump.test.ts
git commit -m "feat(web): add shared numbered quick-jump primitive"
~~~

### Task 3: Consume the primitive in Recents and nested Settings

**Files:**

- Modify: web/components/sidebar/ChatSidebar.tsx
- Modify: web/components/sidebar/ProfileMenu.tsx
- Create: web/components/sidebar/RecentsQuickPeek.tsx
- Modify: web/__tests__/chat-recents.test.ts
- Modify: web/__tests__/keyboard-shortcuts-overlay.test.ts

**Interfaces:**

- ChatSidebar accepts settingsOpenRequest: number and opens its existing ProfileMenu when it increments.
- RecentsQuickPeek accepts loaded history, active id, onOpenItem, and onClose; it does not mutate data.
- ProfileMenu supplies top-level categories or the active submenu's enabled buttons to useQuickJump; selected number uses the button's existing callback.

- [ ] **Step 1: Write failing integration/source tests**

~~~ts
expect(source("components/sidebar/ChatSidebar.tsx")).toContain("useQuickJump");
expect(source("components/sidebar/ChatSidebar.tsx")).toContain("QuickJumpBadge");
expect(source("components/sidebar/ProfileMenu.tsx")).toContain("useQuickJump");
expect(source("components/sidebar/ProfileMenu.tsx")).toContain("QuickJumpBadge");
~~~

- [ ] **Step 2: Run focused tests and verify expected red**

Run: cd web && bun test __tests__/chat-recents.test.ts __tests__/keyboard-shortcuts-overlay.test.ts

Expected: neither Recents nor ProfileMenu has consumed the primitive.

- [ ] **Step 3: Implement all three consumers**

~~~tsx
const { isQuickJumpActive, numberFor } = useQuickJump({
  enabled: isOpen && isRecentsExpanded,
  items: visibleRecents.map((item) => ({
    id: historyConversationId(item), pinned: item.pinned,
  })),
  onSelect: (id) => {
    const item = visibleRecents.find((row) => historyConversationId(row) === id);
    if (item) onOpenItem(item);
  },
});
~~~

Build visibleRecents exclusively from getVisibleRecentChats, render the badge in the existing left gutter, and keep RecentChatActions intact. The distinct Recents action opens a small dismissible RecentsQuickPeek; the sidebar action opens the persistent sidebar + accordion. ProfileMenu numbers Profile, Data Controls, Preferences, Help & Legal, and Feedback at top level; a nested menu numbers only enabled buttons at that depth.

- [ ] **Step 4: Re-run focused tests and commit**

Run: cd web && bun test __tests__/chat-recents.test.ts __tests__/keyboard-shortcuts-overlay.test.ts

Expected: PASS with the single hook named in both consumers.

~~~bash
git add web/components/sidebar/ChatSidebar.tsx web/components/sidebar/ProfileMenu.tsx web/components/sidebar/RecentsQuickPeek.tsx web/__tests__/chat-recents.test.ts web/__tests__/keyboard-shortcuts-overlay.test.ts
git commit -m "feat(web): add Recents and Settings quick-jump"
~~~

### Task 4: Route real actions through the chat shell and localize

**Files:**

- Modify: web/components/chat/ChatInterface.tsx
- Modify: web/components/sidebar/KeyboardShortcutsOverlay.tsx
- Modify: web/public/locales/en/common.json
- Modify: web/public/locales/es-419/common.json
- Modify: web/__tests__/keyboard-shortcuts-overlay.test.ts

**Interfaces:**

- ChatInterface dispatches only existing requestNewChat and header delete/rename/pin callbacks plus local peek/sidebar/settings state.

- [ ] **Step 1: Write failing copy and handler tests**

~~~ts
expect(en.keyboard_shortcuts.shortcuts).toMatchObject({
  new_chat: "New chat", open_recents: "Open Recents",
  delete_focused_chat: "Delete current chat", rename_focused_chat: "Rename current chat",
  expand_sidebar_recents: "Expand sidebar and Recents", open_settings: "Open Settings",
  toggle_pin_focused_chat: "Pin or unpin current chat", quick_jump: "Quick-jump visible items",
});
expect(es.keyboard_shortcuts.shortcuts.quick_jump).toBe("Saltar a elementos visibles");
expect(source("components/chat/ChatInterface.tsx")).toContain(
  'matchesKeyboardShortcut("delete_focused_chat", event)',
);
~~~

- [ ] **Step 2: Run the test and verify expected red**

Run: cd web && bun test __tests__/keyboard-shortcuts-overlay.test.ts

Expected: action labels and dispatcher branches are absent.

- [ ] **Step 3: Implement dispatcher and registry-driven overlay**

~~~ts
if (matchesKeyboardShortcut("delete_focused_chat", event) && conversationId) {
  event.preventDefault();
  handleRequestHeaderDelete();
  return;
}
~~~

Add equivalent branches for the six other actions. Do nothing while Omnisearch, the shortcut overlay, or confirmation is open. Management actions need canManageConversation and a focused conversation. Delete only enters existing pending-header state; it never calls deleteConversation directly. Add Navigation, Chat, and Quick jump registry groups to the overlay, preserving Escape/click-away/re-trigger behavior. Add English/Spanish action labels and Recents-peek title/empty copy.

- [ ] **Step 4: Re-run focused tests and commit**

Run: cd web && bun test __tests__/keyboard-shortcuts-overlay.test.ts __tests__/keyboard-shortcuts.test.ts

Expected: PASS for every handler and locale string.

~~~bash
git add web/components/chat/ChatInterface.tsx web/components/sidebar/KeyboardShortcutsOverlay.tsx web/public/locales/en/common.json web/public/locales/es-419/common.json web/__tests__/keyboard-shortcuts-overlay.test.ts
git commit -m "feat(web): add keyboard quick-navigation actions"
~~~

### Task 5: Verify and publish one Draft PR

**Files:**

- Read: web/__tests__/keyboard-shortcuts.test.ts
- Read: web/__tests__/quick-jump.test.ts
- Read: web/__tests__/chat-recents.test.ts
- Read: web/__tests__/keyboard-shortcuts-overlay.test.ts

- [ ] **Step 1: Run hermetic checks**

~~~bash
cd web && bun test
cd web && bun run lint
~~~

Expected: all frontend tests pass; identify any warning existing at the integration base.

- [ ] **Step 2: Run headed acceptance without rewriting linked environment files**

~~~bash
bash .github/setup-worktree-env.sh --check "$PWD"
.github/dev.sh
cd web && bun run dev
~~~

Verify Command-K, overlay open/dismiss, existing delete confirmation, pinned-first Recents badges, and nested Settings badges. Capture overlay-open, overlay-dismissed, Recents, and nested-Settings screenshots.

- [ ] **Step 3: Inspect, push, and create only a Draft PR**

~~~bash
git diff --check origin/codex/private-alpha-next...HEAD
git status --short
git push -u origin codex/keyboard-shortcuts-overlay
gh pr create --draft --base codex/private-alpha-next --head codex/keyboard-shortcuts-overlay
~~~

Expected: frontend/docs/test-only diff and a Draft PR; founder retains merge authority.
