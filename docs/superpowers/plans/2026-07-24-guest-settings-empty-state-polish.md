# Guest Settings and Empty-State Polish Implementation Plan

Status: **COMPLETED HISTORICAL EXECUTION RECORD — INCLUDED IN PR #279,
LANDED AS `53e812e9`**

This plan is retained for evidence lineage, not active dispatch. Its historical
flag assumptions are superseded by current canon: Guest server and presentation
flags default on with explicit-off rollback.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the approved compact guest settings menu and one surgical guest empty-state hierarchy correction without changing guest policy, registered chat behavior, starter actions, or backend/runtime behavior.

**Architecture:** Keep presentation ownership in the existing guest components. Reuse the shared centered `LanguageModal` with an explicit profile-persistence policy, keep `GuestLegalFooter` as the only visible expiry owner, and remove expiry plumbing from `ChatSidebar`. `ChatInterface` selects a guest-only empty placeholder while leaving registered copy and all send/hydration owners unchanged.

**Tech Stack:** Next.js 16, React 19, TypeScript, Tailwind CSS, i18next, next-themes, Lucide React, Bun tests, Playwright.

## Global Constraints

- Preserve every existing commit and working-tree change; never reset, stash, revert, or broadly reformat.
- Keep `ARGUS_GUEST_ACCESS_ENABLED`, `ARGUS_PUBLIC_ACCOUNT_ACCESS_ENABLED`, and `NEXT_PUBLIC_GUEST_ACCESS_ENABLED` false in checked-in defaults.
- Do not change backend, API, accounting, runtime, auth, persistence, onboarding, starter payloads, or Block 3 behavior.
- Keep the centered Argus wordmark, existing guest headline, starter chips, Terms/Privacy copy, and pre/post-message legal states.
- Visible expiry copy is exactly `Temporary chat · available until {localized date}` in English and `Chat temporal · disponible hasta {localized date}` in Spanish.
- Guest empty placeholder is exactly `What do you want to test?` in English and `¿Qué quieres probar?` in Spanish.
- Preserve exact server expiry timestamp and existing local-timezone formatting behavior in accessible metadata.
- Do not push, deploy, or mutate GitHub or hosted Supabase.

---

### Task 1: Compact Guest Settings Popover and Centered Language Modal

**Files:**
- Modify: `web/__tests__/guest-shell.test.tsx`
- Modify: `web/e2e/guest-entry.spec.ts`
- Modify: `web/components/guest/GuestSettingsMenu.tsx`
- Modify: `web/components/settings/LanguageModal.tsx`

**Interfaces:**
- Consumes: `LanguageModal({ onClose, persistProfile? })`, `onFeedback()`, `i18n.changeLanguage`, and `setTheme`.
- Produces: `LanguageModal` with `persistProfile?: boolean` defaulting to `true`; guest settings pass `false`.

- [ ] **Step 1: Write the failing settings contract tests**

Add source-contract assertions proving:

```ts
expect(settings).not.toContain('"settings.appearance.title"');
expect(settings).toContain("<LanguageModal");
expect(settings).toContain("persistProfile={false}");
expect(settings).toContain('role="group"');
expect(settings.match(/role="menuitem"/g)?.length).toBe(2);
expect(languageModal).toContain("persistProfile = true");
expect(languageModal).toContain("if (persistProfile)");
```

Update the Playwright flow to click `Language`, assert the centered dialog is
visible, select `Español`, assert no `PATCH /me`, and prove Escape returns focus
to the guest settings trigger.

- [ ] **Step 2: Run the focused tests to verify red**

Run:

```bash
cd web
bun test __tests__/guest-shell.test.tsx
```

Expected: FAIL because the current menu renders the Theme heading and inline
language radio rows, and `LanguageModal` has no persistence policy.

- [ ] **Step 3: Implement the minimal compact popover**

In `GuestSettingsMenu`:

- keep the 44-pixel gear button but render `Settings` at 18 pixels;
- remove the Theme heading;
- render one compact three-button group using the existing Sun, Moon, and
  Monitor icons;
- render exactly two menu rows, Language and Feedback;
- open `LanguageModal` from Language after closing the popover;
- pass `persistProfile={false}`;
- restore focus to the gear trigger when the modal closes;
- keep outside-click and Escape behavior.

In `LanguageModal`:

```ts
type LanguageModalProps = {
  onClose: () => void;
  persistProfile?: boolean;
};

export default function LanguageModal({
  onClose,
  persistProfile = true,
}: LanguageModalProps) {
  // existing selection behavior
  if (persistProfile) {
    await patchMe({ language: nextLanguage, locale: localeForLanguage(nextLanguage) });
  }
}
```

Add Escape and body-scroll cleanup without changing registered/default
persistence behavior.

- [ ] **Step 4: Run focused unit and browser tests green**

Run:

```bash
cd web
bun test __tests__/guest-shell.test.tsx
PLAYWRIGHT_PORT=3124 \
NEXT_PUBLIC_GUEST_ACCESS_ENABLED=true \
NEXT_PUBLIC_PUBLIC_ACCOUNT_ACCESS_ENABLED=false \
NEXT_PUBLIC_MOCK_AUTH=true \
npx playwright test e2e/guest-entry.spec.ts
```

Expected: all tests pass; guest language selection makes zero profile patches.

- [ ] **Step 5: Commit the settings slice**

```bash
git add \
  web/__tests__/guest-shell.test.tsx \
  web/e2e/guest-entry.spec.ts \
  web/components/guest/GuestSettingsMenu.tsx \
  web/components/settings/LanguageModal.tsx
git commit -m "fix(web): polish guest settings menu"
```

### Task 2: Single Composer-Owned Expiry and Lean Guest Empty State

**Files:**
- Modify: `web/__tests__/guest-shell.test.tsx`
- Modify: `web/__tests__/chat-lifecycle-source.test.ts`
- Modify: `web/__tests__/spanish-ui-smoke.test.ts`
- Modify: `web/e2e/guest-entry.spec.ts`
- Modify: `web/components/guest/GuestLegalFooter.tsx`
- Modify: `web/components/guest/GuestHeader.tsx`
- Modify: `web/components/guest/GuestEmptyStateIntro.tsx`
- Modify: `web/components/sidebar/ChatSidebar.tsx`
- Modify: `web/components/chat/ChatInterface.tsx`
- Modify: `web/public/locales/en/common.json`
- Modify: `web/public/locales/es-419/common.json`

**Interfaces:**
- Consumes: `account.guest.expires_at`, `ChatLegalNotice`, `ChatInput`, and the existing `StarterActions(onSelect={handleSend})`.
- Produces: `formatGuestExpiryDate(expiresAt, language)` for visible date-only copy and `formatGuestExpiryTimestamp(expiresAt, language)` for accessible detail.

- [ ] **Step 1: Write failing hierarchy and localization tests**

Add assertions proving:

```ts
expect(sidebar).not.toContain("temporaryExpiresAt");
expect(sidebar).not.toContain("guest-sidebar-expiry");
expect(chat).not.toContain("temporaryExpiresAt={account?.guest?.expires_at");
expect(emptyIntro).not.toContain("value_body");
expect(en.guest.shell.input_placeholder).toBe("What do you want to test?");
expect(es.guest.shell.input_placeholder).toBe("¿Qué quieres probar?");
expect(en.guest.shell.temporary_until).toBe(
  "Temporary chat · available until {{date}}",
);
expect(es.guest.shell.temporary_until).toBe(
  "Chat temporal · disponible hasta {{date}}",
);
expect(footer).toContain("dateTime={expiresAt}");
```

In Playwright, assert:

- `[data-testid="guest-temporary-notice"]` has count one;
- `[data-testid="guest-sidebar-expiry"]` has count zero;
- the notice remains visible after expanding and collapsing the sidebar;
- English and Spanish visible copy use a date and omit a visible time;
- pre-message and post-message legal text remain correct;
- each starter still sends its existing localized payload.

- [ ] **Step 2: Run focused tests to verify red**

Run:

```bash
cd web
bun test \
  __tests__/guest-shell.test.tsx \
  __tests__/chat-lifecycle-source.test.ts \
  __tests__/spanish-ui-smoke.test.ts
```

Expected: FAIL because expiry is still rendered in the sidebar, the explanatory
paragraph remains, and the guest-specific placeholder/copy do not exist.

- [ ] **Step 3: Implement the minimal empty-state correction**

- Delete `temporaryExpiresAt` from `ChatSidebarProps`, its destructuring, import,
  and footer branch.
- Stop passing `temporaryExpiresAt` from `ChatInterface`.
- Remove the explanatory paragraph from `GuestEmptyStateIntro`.
- Select the empty placeholder with:

```ts
const chatInputPlaceholder =
  messages.length === 0
    ? isGuest
      ? t("guest.shell.input_placeholder", "What do you want to test?")
      : t("chat.input_placeholder")
    : t("chat.followup_placeholder", "Ask a follow-up...");
```

- Render the temporary notice only in `GuestLegalFooter`, below the existing
  legal line:

```tsx
<time
  data-testid="guest-temporary-notice"
  dateTime={expiresAt}
  title={expiresAt}
  aria-label={accessibleExpiry}
>
  {t("guest.shell.temporary_until", { date: visibleDate })}
</time>
```

- Remove the duplicate screen-reader temporary copy from `GuestHeader` while
  preserving `data-guest-expires-at`.
- Update only the guest locale keys named in the global constraints.

- [ ] **Step 4: Run focused unit and browser tests green**

Run:

```bash
cd web
bun test \
  __tests__/guest-shell.test.tsx \
  __tests__/chat-lifecycle-source.test.ts \
  __tests__/guest-starter-actions.test.tsx \
  __tests__/spanish-ui-smoke.test.ts
PLAYWRIGHT_PORT=3125 \
NEXT_PUBLIC_GUEST_ACCESS_ENABLED=true \
NEXT_PUBLIC_PUBLIC_ACCOUNT_ACCESS_ENABLED=false \
NEXT_PUBLIC_MOCK_AUTH=true \
npx playwright test e2e/guest-entry.spec.ts
```

Expected: all tests pass, one temporary notice remains under the composer, and
starter payload tests remain unchanged.

- [ ] **Step 5: Commit the hierarchy slice**

```bash
git add \
  web/__tests__/guest-shell.test.tsx \
  web/__tests__/chat-lifecycle-source.test.ts \
  web/__tests__/spanish-ui-smoke.test.ts \
  web/e2e/guest-entry.spec.ts \
  web/components/guest/GuestLegalFooter.tsx \
  web/components/guest/GuestHeader.tsx \
  web/components/guest/GuestEmptyStateIntro.tsx \
  web/components/sidebar/ChatSidebar.tsx \
  web/components/chat/ChatInterface.tsx \
  web/public/locales/en/common.json \
  web/public/locales/es-419/common.json
git commit -m "fix(web): simplify guest empty state"
```

### Task 3: Regression and Visual Verification

**Files:**
- No production file changes expected.
- Create: `design-qa.md`
- Create screenshots only outside committed source.

**Interfaces:**
- Consumes: the exact committed candidate from Tasks 1 and 2.
- Produces: desktop/mobile and EN/ES light/dark browser evidence with open/closed menu and expanded/collapsed sidebar states.

- [ ] **Step 1: Run deterministic frontend regression**

Run:

```bash
cd web
bun test __tests__
bun run lint
NEXT_PUBLIC_GUEST_ACCESS_ENABLED=false \
NEXT_PUBLIC_PUBLIC_ACCOUNT_ACCESS_ENABLED=false \
NEXT_PUBLIC_MOCK_AUTH=false \
bun run build
```

Expected: full frontend suite, ESLint, TypeScript, and production build pass.

- [ ] **Step 2: Run repository hygiene gates**

Run:

```bash
poetry run python scripts/check_modularity_budget.py
git diff --check
git status --short
```

Expected: modularity passes, diff check is clean, and only intended UI files are
modified before the final commit.

- [ ] **Step 3: Inspect the live browser matrix**

Use `http://localhost:3000/chat` and verify:

- desktop light English: collapsed and expanded sidebar;
- desktop dark Spanish: open settings popover and centered language modal;
- 390-pixel mobile light English: composer, notice, legal copy, and closed menu;
- 390-pixel mobile dark Spanish: open popover, centered modal, and expanded
  sidebar;
- empty and populated conversation states;
- no Next.js overlay or relevant console error;
- one visible temporary notice and zero sidebar notices in every guest state.

Save screenshots outside the repo.

- [ ] **Step 4: Record the source-to-implementation comparison**

Compare the provided settings-menu reference and the rendered implementation at
matching menu states. Record the source path, screenshot paths, viewports,
focused-region evidence, responsive-state evidence, and final result in
project-root `design-qa.md`. The final result must be `passed` only when no
actionable P0/P1/P2 mismatch remains.

- [ ] **Step 5: Confirm no forbidden surfaces changed**

Run:

```bash
git diff --name-only ce0564a124ffdd94597cfaef9900ee8c7e7fa69a..HEAD
git diff --quiet ce0564a124ffdd94597cfaef9900ee8c7e7fa69a..HEAD -- \
  src supabase docs/api docs/API_CONTRACT.md
```

Expected: only directly related frontend tests/components/locales and the local
design/plan documentation changed.

- [ ] **Step 6: Stop with a clean local branch**

Run:

```bash
git status --porcelain
git log -4 --oneline
```

Expected: no output from status. Do not push, deploy, or mutate GitHub.
