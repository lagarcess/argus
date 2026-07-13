# Issue 196 Spanish Static i18n Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove English static fallback from the Pinned and Sidebar Preferences
surfaces, make the pin icon depend on typed state, and make the existing
private-alpha canary run the regression alarm.

**Architecture:** The locale dictionaries remain the source of static UI copy.
The existing Bun Spanish smoke test becomes the explicit required-key and
source-guard contract, and the scheduled canary invokes that focused contract
before its Render probes. The sidebar retains display labels but adds a typed
`isPinned` property for the pin-icon branch.

**Tech Stack:** Next.js/React, react-i18next, Bun test, GitHub Actions, JSON
locale bundles.

## Global Constraints

- Target `codex/private-alpha-next`; do not merge the PR.
- Do not deploy, run the full authenticated Render journey, or modify #197's
  release-profile ownership.
- Do not modify `docs/PRODUCT.md` or
  `docs/specs/private-alpha-next-decision-memo.md`.
- Keep display labels presentation-only; stable typed values drive behavior.
- Keep the change limited to #196's static UI, tests, and reusable canary
  assertion.

---

### Task 1: Define failing static UI and canary regressions

**Files:**
- Modify: `web/__tests__/spanish-ui-smoke.test.ts`
- Modify: `tests/test_render_canary_script.py`

**Interfaces:**
- Consumes: `web/public/locales/{en,es-419}/common.json`,
  `SidebarPreferenceModal.tsx`, `ChatSidebar.tsx`, and the private-alpha
  canary workflow.
- Produces: a required-key regression contract for the Pinned heading and all
  Sidebar Preferences copy, plus a contract that the canary invokes it.

- [ ] **Step 1: Write the failing required-key and source-guard tests**

  Add these paths to `requiredSmokeKeys`:

  ```ts
  "chat.history.pinned",
  "settings.sidebar.title",
  "settings.sidebar.description",
  "settings.sidebar.expanded",
  "settings.sidebar.collapsed",
  "settings.sidebar.hover",
  "settings.sidebar.close",
  ```

  Extend the source test with assertions that `SidebarPreferenceModal.tsx`
  uses `settings.sidebar.close`, does not call `t` with English default values
  for the modal keys, and that `ChatSidebar.tsx` renders the pin icon from
  `group.isPinned` rather than `group.label === t("chat.history.pinned", ...)`.
  Add a Python assertion that `.github/workflows/private-alpha-canary.yml`
  contains the named Spanish static UI canary step and runs:

  ```text
  cd web && bun test __tests__/spanish-ui-smoke.test.ts
  ```

- [ ] **Step 2: Run the focused tests to verify the expected failures**

  Run:

  ```bash
  cd web && bun test __tests__/spanish-ui-smoke.test.ts
  poetry run pytest tests/test_render_canary_script.py -q
  ```

  Expected: the Bun suite reports the absent `chat.history.pinned` and
  `settings.sidebar.*` keys; the canary-script test reports the missing
  workflow step. The typed-state source assertion also fails on the current
  translated-label comparison.

### Task 2: Add locale keys, typed pin state, and canary invocation

**Files:**
- Modify: `web/public/locales/en/common.json`
- Modify: `web/public/locales/es-419/common.json`
- Modify: `web/components/settings/SidebarPreferenceModal.tsx`
- Modify: `web/components/sidebar/ChatSidebar.tsx`
- Modify: `.github/workflows/private-alpha-canary.yml`

**Interfaces:**
- Consumes: Task 1's required key and source-guard contract.
- Produces: localized Sidebar Preferences copy, a stable recents-group state
  flag, and a scheduled canary invocation of the focused regression suite.

- [ ] **Step 1: Add the matching locale values**

  Add the following English values:

  ```json
  "pinned": "Pinned"
  ```

  under `chat.history`, and:

  ```json
  "sidebar": {
    "title": "Sidebar preference",
    "description": "Choose how the sidebar behaves.",
    "expanded": "Expanded",
    "collapsed": "Icons only",
    "hover": "On hover",
    "close": "Close sidebar preference modal"
  }
  ```

  under `settings`. Add the same paths in `es-419` with:

  ```json
  "pinned": "Anclados"
  ```

  and:

  ```json
  "sidebar": {
    "title": "Preferencia de barra lateral",
    "description": "Elige cómo se comporta la barra lateral.",
    "expanded": "Expandida",
    "collapsed": "Solo iconos",
    "hover": "Al pasar el cursor",
    "close": "Cerrar modal de preferencias de la barra lateral"
  }
  ```

- [ ] **Step 2: Remove the modal's English fallback path**

  Replace the modal's hard-coded close label with:

  ```tsx
  aria-label={t("settings.sidebar.close")}
  ```

  and use the five remaining `settings.sidebar.*` keys without English
  default-value arguments.

- [ ] **Step 3: Make the pin-icon branch typed**

  Give every recents group an `isPinned: boolean` property. The pinned group
  is created with `isPinned: true`; date groups are created with
  `isPinned: false`. Replace:

  ```tsx
  group.label === t("chat.history.pinned", "Pinned")
  ```

  with:

  ```tsx
  group.isPinned
  ```

- [ ] **Step 4: Invoke the static regression from the canary workflow**

  After frontend dependencies are installed in
  `.github/workflows/private-alpha-canary.yml`, add:

  ```yaml
  - name: Run Spanish static UI canary assertions
    run: cd web && bun test __tests__/spanish-ui-smoke.test.ts
  ```

- [ ] **Step 5: Re-run the focused tests**

  Run:

  ```bash
  cd web && bun test __tests__/spanish-ui-smoke.test.ts
  poetry run pytest tests/test_render_canary_script.py -q
  ```

  Expected: both commands pass, and deleting any one required locale key would
  make the Bun command fail.

### Task 3: Verify the real local Spanish surface and review the slice

**Files:**
- Verify only: the files in Tasks 1 and 2.

**Interfaces:**
- Consumes: the corrected locale bundles, modal, typed sidebar grouping, and
  workflow assertion.
- Produces: focused test, browser, and diff evidence suitable for a draft PR.

- [ ] **Step 1: Run focused frontend verification**

  Run:

  ```bash
  cd web && bun test __tests__/spanish-ui-smoke.test.ts
  cd web && bun test
  cd web && bun run lint
  poetry run pytest tests/test_i18n_coverage.py tests/test_render_canary_script.py -q
  ```

- [ ] **Step 2: Run the local Spanish browser check**

  Start the documented synthetic local backend and frontend with Spanish
  enabled. In the local browser, set the app language to Spanish, open the
  profile menu, select **Preferencias**, then **Barra lateral**, and verify:

  ```text
  Preferencia de barra lateral
  Elige cómo se comporta la barra lateral.
  Expandida
  Solo iconos
  Al pasar el cursor
  Cerrar modal de preferencias de la barra lateral
  ```

  Also verify the Pinned recents heading renders `Anclados` for a pinned chat.

- [ ] **Step 3: Review scope and publish**

  Run:

  ```bash
  git diff --check
  git diff -- docs/PRODUCT.md docs/specs/private-alpha-next-decision-memo.md
  git status --short
  ```

  Expected: no whitespace errors, no changes to the locked documents, and only
  issue #196 sources, tests, workflow assertion, and process records changed.
  Commit with a conventional `fix(i18n): ...` message, push the branch, and
  open a draft PR targeting `codex/private-alpha-next`.
