# Usage Allowance Meter Colors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Color each existing message and backtest allowance gauge from its own lowest normalized active-window capacity while retaining exact count and reset truth.

**Architecture:** `web/lib/usage-allowance.ts` owns one pure classifier over the typed API windows. `UsageModal.tsx` maps the returned semantic tone to the existing gauge fill, while `web/app/globals.css` defines the three binding design tokens. Existing backend fields and localized count/reset copy remain unchanged.

**Tech Stack:** TypeScript, React, Tailwind CSS v4, Bun test, Next.js, Playwright.

## Global Constraints

- Messages and backtests classify independently.
- Teal applies at `remaining / limit >= 0.30`.
- Warning applies at `0.10 < remaining / limit < 0.30`.
- Danger applies at `remaining / limit <= 0.10`, including exhaustion.
- Use the lowest normalized ratio across active `hour` and `day` windows.
- Preserve exact remaining counts and backend-owned reset timestamps.
- No pulse, flashing, terminal treatment, invented quota data, or em dash in user-facing copy.
- Browser evidence uses mocked API routes and spends no real turns or backtests.

---

### Task 1: Pure allowance tone classifier

**Files:**
- Modify: `web/lib/usage-allowance.ts`
- Test: `web/__tests__/usage-allowance.test.ts`

**Interfaces:**
- Consumes: `UsageAllowance` with active `hour` and `day` `UsageWindow` values.
- Produces: `allowanceMeterTone(allowance: UsageAllowance): "teal" | "warning" | "danger"`.

- [ ] **Step 1: Write the failing boundary and independence tests**

Add table-driven expectations proving exactly 30% is teal, 29% is warning,
exactly 10% is danger, exhaustion is danger, and the lower hourly ratio wins
when the daily ratio is healthier. Invoke the function independently for
message and backtest fixtures with different ratios.

- [ ] **Step 2: Run the focused unit test and verify red**

Run: `cd web && bun test __tests__/usage-allowance.test.ts`

Expected: fail because `allowanceMeterTone` is not exported.

- [ ] **Step 3: Implement the minimal classifier**

For each non-null active window, calculate:

```ts
const normalized =
  window.limit <= 0
    ? 0
    : Math.max(0, Math.min(1, window.remaining / window.limit));
```

Use `Math.min` across active windows. Return `danger` at `<= 0.10`, `warning`
at `< 0.30`, and `teal` otherwise.

- [ ] **Step 4: Run the focused unit test and verify green**

Run: `cd web && bun test __tests__/usage-allowance.test.ts`

Expected: all focused tests pass.

### Task 2: Render semantic gauge colors without losing truth

**Files:**
- Modify: `web/app/globals.css`
- Modify: `web/components/settings/UsageModal.tsx`
- Test: `web/__tests__/usage-allowance.test.ts`
- Test: `web/e2e/usage-allowance.spec.ts`

**Interfaces:**
- Consumes: `allowanceMeterTone` from Task 1.
- Produces: existing progressbar fill using `--rui-color-teal`,
  `--rui-color-warning`, or `--rui-color-danger`.

- [ ] **Step 1: Write failing token and browser-behavior tests**

Assert the three root custom properties exist with the binding muted values.
In the browser harness, provide daily fixtures at 30%, 29%, and 10% remaining,
then assert the computed fill color, exact visible remaining count, and exact
`time[datetime]` reset element. Include a case where messages and backtests use
different tones.

- [ ] **Step 2: Run focused unit and Playwright tests and verify red**

Run:

```bash
cd web
bun test __tests__/usage-allowance.test.ts
bunx playwright test e2e/usage-allowance.spec.ts --project=chromium
```

Expected: fail because semantic tokens and tone-driven fills are absent.

- [ ] **Step 3: Add the semantic tokens and tone mapping**

Define in `:root`:

```css
--rui-color-teal: #5ba897;
--rui-color-warning: #c2a44d;
--rui-color-danger: #d66d75;
```

Map all literal tone branches in `UsageModal.tsx` so Tailwind emits the three
`background-color: var(...)` utilities. Keep the progressbar ARIA values,
remaining copy, `<time dateTime>`, and hourly disclosure intact. Support guest
daily-only data by excluding the null hourly window.

- [ ] **Step 4: Run focused unit and Playwright tests and verify green**

Run the same commands from Step 2. Expected: pass.

### Task 3: Durable bilingual and theme evidence

**Files:**
- Modify: `web/e2e/usage-allowance.spec.ts`
- Create: `docs/reports/evidence/usage-allowance-meter/*.png`

**Interfaces:**
- Consumes: mocked `/api/v1/me/usage` fixtures and the existing profile-menu route.
- Produces: six deterministic screenshots, three English light-theme thresholds
  and three Spanish dark-theme thresholds.

- [ ] **Step 1: Add the six-case capture matrix**

Use exact daily boundary fixtures: 30% remaining for teal, 29% for warning,
and 10% for danger. Set `argus-theme` before navigation, assert the root theme,
the visible count, the backend timestamp, and the computed RGB color before
capturing.

- [ ] **Step 2: Capture the six evidence images**

Run:

```bash
cd web
ARGUS_CAPTURE_USAGE_METER_EVIDENCE=1 bunx playwright test e2e/usage-allowance.spec.ts --project=chromium
```

Expected: six PNG files under
`docs/reports/evidence/usage-allowance-meter/`.

- [ ] **Step 3: Verify evidence inventory and image dimensions**

Run `file docs/reports/evidence/usage-allowance-meter/*.png` from the repository
root and confirm exactly six non-empty PNGs.

### Task 4: Exact-head verification and delivery

**Files:**
- Modify: `.agent/designs/argus/DESIGN.md`
- Modify: `docs/specs/argus-active-roadmap.md`
- Verify all changed files and evidence.

**Interfaces:**
- Consumes: the complete implementation tree.
- Produces: a pushed worker branch with no merge or deploy.

- [ ] **Step 1: Align binding documentation**

Document teal at least 30% remaining, warning above 10% and below 30%, and
danger at 10% or less. Retain the lowest-normalized-window and supporting-color
rules.

- [ ] **Step 2: Run required frontend verification**

From `web`, run:

```bash
bun test __tests__
bun run lint
bun run build
```

- [ ] **Step 3: Verify the would-be merged tree modularity budget**

Fetch `origin/codex/private-alpha-next`, generate or inspect the merged result,
and run `python scripts/check_modularity_budget.py` against that result using
the script's supported merged-tree mode.

- [ ] **Step 4: Commit implementation and evidence**

Use a Conventional Commit such as:

```text
feat(settings): color usage allowance meters by capacity
```

- [ ] **Step 5: Re-run the six browser cases at the exact commit**

Overwrite the evidence through the capture matrix and confirm `git status`
stays clean, proving the committed files match the exact-head render.

- [ ] **Step 6: Push without merging**

Push `codex/usage-allowance-meter-colors` to origin. Do not merge, deploy, or
open a pull request.
