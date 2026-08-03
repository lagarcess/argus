# Responsive Keyboard Shortcuts Sheet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fit the complete Argus shortcut reference above the fold on desktop while preserving a readable mobile list and preventing blank translated labels.

**Architecture:** Keep `KEYBOARD_SHORTCUTS` as the canonical behavior-and-display registry. Add an English fallback label to each definition, then render Navigation and Chat as sibling columns at the desktop breakpoint with Quick Jump spanning the full width; mobile remains a single column. Reorder only the help presentation so destructive Delete appears last—handler behavior and shortcut chords remain unchanged.

**Tech Stack:** React, TypeScript, Tailwind CSS, i18next, Bun tests, Next.js.

## Global Constraints

- Preserve `⌘K` / `Ctrl+K`, `⌘/` / `Ctrl+/`, management bindings, and quick-jump behavior exactly.
- Keep one shortcut set across languages; localize labels, never chords.
- English and Spanish (`es-419`) labels must remain complete.
- Use Argus flat surfaces, zero shadows, existing fonts, and theme-aware colors.
- Desktop uses two columns; mobile uses one column.
- Delete is the final Chat row and remains visually neutral in this informational sheet.
- Keep the visual iteration local until founder approval; publish only after the
  founder explicitly approves the rendered result.

---

### Task 1: Lock the responsive and fallback-label contract

**Files:**
- Modify: `web/__tests__/keyboard-shortcuts.test.ts`
- Modify: `web/__tests__/keyboard-shortcuts-overlay.test.ts`

**Interfaces:**
- Consumes: `KEYBOARD_SHORTCUTS`, `KeyboardShortcutsOverlay` source.
- Produces: assertions for `defaultLabel`, presentation order, responsive grid, and mobile fallback.

- [x] **Step 1: Write the failing registry test**

```ts
expect(KEYBOARD_SHORTCUTS.every((shortcut) => shortcut.defaultLabel)).toBe(true);
```

- [x] **Step 2: Write the failing layout test**

```ts
expect(overlay).toContain("md:grid-cols-2");
expect(overlay).toContain("md:col-span-2");
expect(overlay).toContain("defaultValue: shortcut.defaultLabel");
expect(chatIds.at(-1)).toBe("delete_focused_chat");
```

- [x] **Step 3: Run the focused tests and confirm they fail**

Run: `cd web && bun test __tests__/keyboard-shortcuts.test.ts __tests__/keyboard-shortcuts-overlay.test.ts`

Expected: failures for missing `defaultLabel`, responsive classes, and Chat presentation ordering.

### Task 2: Implement the approved shortcut sheet

**Files:**
- Modify: `web/lib/keyboard-shortcuts.ts`
- Modify: `web/components/sidebar/KeyboardShortcutsOverlay.tsx`

**Interfaces:**
- Consumes: `KeyboardShortcutDefinition` and its canonical groups.
- Produces: `defaultLabel: string` and a responsive group renderer.

- [x] **Step 1: Add complete English fallbacks to the registry**

```ts
type KeyboardShortcutDefinition = {
  defaultLabel: string;
  // existing fields remain unchanged
};
```

- [x] **Step 2: Separate behavioral registry order from help presentation order**

```ts
const HELP_GROUPS = [
  { id: "navigation", className: "" },
  { id: "chat", className: "" },
  { id: "quick_jump", className: "md:col-span-2" },
] as const;

const CHAT_HELP_ORDER = [
  "new_chat",
  "rename_focused_chat",
  "archive_focused_chat",
  "toggle_read_focused_chat",
  "toggle_pin_focused_chat",
  "delete_focused_chat",
] as const;
```

- [x] **Step 3: Render the responsive desktop grid and mobile stack**

```tsx
<div className="mt-6 grid grid-cols-1 gap-5 md:grid-cols-2">
  {/* Navigation and Chat columns; Quick Jump spans both columns. */}
</div>
```

- [x] **Step 4: Render translations with registry fallbacks**

```tsx
{t(shortcut.labelKey, { defaultValue: shortcut.defaultLabel })}
```

- [x] **Step 5: Run focused tests until green**

Run: `cd web && bun test __tests__/keyboard-shortcuts.test.ts __tests__/keyboard-shortcuts-overlay.test.ts`

Expected: all focused tests pass.

### Task 3: Verify behavior and visual evidence

**Files:**
- Modify: `web/e2e/issue-334-omnisearch-shortcut-legend.spec.ts` only if the locked visual assertions need coverage.

**Interfaces:**
- Consumes: the existing issue #334 browser fixture.
- Produces: desktop and mobile evidence that labels, grouping, chords, and scrolling are correct.

- [x] **Step 1: Run the focused shortcut and activity tests**

Run: `cd web && bun test __tests__/keyboard-shortcuts.test.ts __tests__/keyboard-shortcuts-overlay.test.ts __tests__/toggle-conversation-unread.test.ts __tests__/chat-header-menu.test.tsx`

- [x] **Step 2: Run lint, production build, and modularity guard**

Run: `cd web && bunx eslint components/sidebar/KeyboardShortcutsOverlay.tsx lib/keyboard-shortcuts.ts __tests__/keyboard-shortcuts.test.ts __tests__/keyboard-shortcuts-overlay.test.ts`

Run: `cd web && bun run build`

Run: `poetry run python scripts/check_modularity_budget.py --top 3`

- [x] **Step 3: Inspect desktop and narrow mobile states in the in-app browser**

Expected: desktop shows Navigation and Chat side by side with Quick Jump below; mobile stacks all groups; Archive and Read/Unread always have visible names; Delete is last.

- [x] **Step 4: Confirm the work remains uncommitted until founder approval**

Run: `git status --short`

Expected at the visual-review gate: local modifications only. Publication is a
separate founder-authorized step after the rendered result is approved.
