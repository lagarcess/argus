# Issue 422 Breakpoint Audit Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task by task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove all seven confirmed breakpoint-audit defects while preserving
the fixed visual-diff budget, backend contracts, and existing interaction
semantics.

**Architecture:** Responsive row ownership stays in `ChatCommandPalette`; the
confirmation card removes only headings that repeat its entity tokens; i18next
owns Spanish agreement and diacritics; `BottomSheet` keeps the accessible
dossier name; and the chart adapter applies one reusable logical-range padding
rule. A focused Playwright matrix asserts rendered text and geometry before it
writes paired evidence.

**Tech Stack:** TypeScript, React, Tailwind CSS v4, i18next, Bun test, Next.js,
Playwright 1.59.1, Lightweight Charts 5.2.0, Python 3.10, Poetry, pytest, Ruff.

## Global constraints

- Base is `360d7bc6c93ab4b90c1b58ab08fd8a68553500a5` from
  `origin/codex/private-alpha-next`.
- Do not modify `.env` or `web/.env.local`, use git stash, merge, or deploy.
- Do not touch #437 backend run-consumption surfaces.
- Do not change API, persistence, market-data, model, or backtest behavior.
- Keep `maxDiffPixels: 100`; never replace it with a ratio or raise it.
- Do not add em dashes to user-facing copy in either language.
- Use the repository-pinned Playwright executable through `bun run`.

---

### Task 1: Commit the locked lane contract

**Files:**

- Create: `docs/superpowers/specs/2026-08-11-issue-422-breakpoint-audit-fixes.md`
- Create: `docs/superpowers/plans/2026-08-11-issue-422-breakpoint-audit-fixes.md`

- [ ] **Step 1: Self-review scope and reproduction facts**

Confirm the spec records the exact base, the partial masking of finding 3, the
#437 ownership check, the two approved plural keys, the three excluded keys,
the six approved auth strings, and the fixed screenshot budget.

- [ ] **Step 2: Commit docs before production changes**

```text
docs(web): lock issue 422 breakpoint repair lane
```

### Task 2: Add the focused red acceptance matrix and before evidence

**Files:**

- Create: `web/e2e/issue-422-breakpoint-regressions.spec.ts`
- Create: `docs/reports/evidence/422/before/*.png`
- Test: `web/e2e/issue-422-breakpoint-regressions.spec.ts`

**Acceptance interfaces:**

- Omnisearch title `scrollWidth <= clientWidth` at 390.
- Date-to-menu horizontal gap is at least 8px.
- Single and double asset confirmations render every symbol exactly once.
- Spanish count 1 renders singular daily and hourly agreement.
- The six approved auth values render with exact diacritics, including both
  password-toggle accessible names.
- The dossier title appears once visibly while the dialog retains its accessible
  name.
- The first chart-axis label is visible in the 390px screenshot.

- [ ] **Step 1: Add deterministic fixtures and assertion-first screenshots**

Reuse `installBreakpointFixture`, override only the mocked usage response needed
to make both approved count keys render with count 1, and target the committed
result-card playground for the canvas case. The evidence output path is enabled
only by an explicit capture environment variable.

- [ ] **Step 2: Capture the seven before frames**

Run the matrix with before capture enabled while production code is unchanged.
Read the rendered text and inspect every image.

- [ ] **Step 3: Run the desired assertions and verify red**

```bash
cd web
PLAYWRIGHT_BASE_URL=http://127.0.0.1:3195 \
  bun run playwright test e2e/issue-422-breakpoint-regressions.spec.ts \
  --project=chromium --workers=1
```

Expected failures map to findings 2 through 8. Finding 3 may fail its deliberate
8px safety gap rather than the already-masked literal overlap.

### Task 3: Repair Omnisearch findings 2 and 3

**Files:**

- Modify: `web/components/sidebar/ChatCommandPalette.tsx`
- Test: `web/e2e/issue-422-breakpoint-regressions.spec.ts`
- Test: `web/__tests__/mobile-shell-layout.test.tsx`

- [ ] **Step 1: Keep the failing 390px title and gap assertions isolated**

Confirm the full fixture title is clipped and the date-to-menu gap is below the
locked floor before changing layout.

- [ ] **Step 2: Give title and metadata separate mobile rows**

Below the desktop stop, let the title own one full line. Group badges and date
on a compact second line that ends at least 8px before the explicit menu target.
Keep desktop positioning, rename behavior, row activation, and keyboard paths.

- [ ] **Step 3: Verify focused green at 390, 720, and 1024**

Run the focused Bun layout test and the Omnisearch Playwright cases. Confirm
there is no new truncation or action collision at the wider bands.

### Task 4: Repair confirmation finding 4

**Files:**

- Modify: `web/components/chat/StrategyConfirmationCard.tsx`
- Test: `web/__tests__/strategy-confirmation-card.test.tsx`
- Test: `web/e2e/issue-422-breakpoint-regressions.spec.ts`

- [ ] **Step 1: Add failing one-asset and two-asset render tests**

Render the real component with no strategy type and assert each entity symbol
appears once. Add a typed strategy case proving `Buy and hold` remains beside
the entity token, plus a three-asset case proving the count heading remains.

- [ ] **Step 2: Omit only redundant fallback headings**

Return no fallback heading when one or two chips already carry the same symbol
truth. Keep the `EntityToken` chips, localized strategy heading, count heading,
and asset-free fallback.

- [ ] **Step 3: Run focused component and browser tests**

Verify the real rendered card, not source text, and inspect the 390px frame.

### Task 5: Repair Spanish findings 5 and 6

**Files:**

- Modify: `web/public/locales/es-419/common.json`
- Modify: `web/public/locales/en/common.json` only if matching plural key shape
  is required by the locale-parity guard
- Test: `web/__tests__/usage-allowance.test.ts`
- Test: `web/__tests__/spanish-ui-smoke.test.ts`
- Test: `web/e2e/issue-422-breakpoint-regressions.spec.ts`

- [ ] **Step 1: Add failing runtime localization tests**

Resolve both approved usage keys through a real i18next instance at counts 1
and 2. Assert the exact six auth values. Assert the three excluded count keys
and every `periodo` occurrence remain untouched.

- [ ] **Step 2: Add only the approved singular/plural and auth values**

Use i18next `_one` and `_other` variants for the two usage keys. Correct exactly
the six auth values from issue #422.

- [ ] **Step 3: Run focused unit and rendered browser checks**

Drive both password-toggle states so `Mostrar contraseña` and
`Ocultar contraseña` are observed through their accessible names. Capture the
usage sheet with both approved count keys at 1.

### Task 6: Repair dossier finding 7

**Files:**

- Modify:
  `web/components/sidebar/command-palette/CommandPaletteDossierSheet.tsx`
- Test: `web/__tests__/mobile-shell-layout.test.tsx`
- Test: `web/e2e/issue-422-breakpoint-regressions.spec.ts`

- [ ] **Step 1: Add the failing visible-title count assertion**

Open the real 390px dossier sheet and prove the exact title renders twice while
the dialog has an accessible name.

- [ ] **Step 2: Hide the primitive heading visually**

Use `BottomSheet`'s existing `titleHidden` contract. Do not remove the title
prop, alter the dossier `h1`, or change desktop pane rendering.

- [ ] **Step 3: Verify one visible title and preserved accessibility**

Assert one visible title, the same dialog accessible name, and the pinned Open
conversation action.

### Task 7: Repair chart finding 8

**Files:**

- Modify: `web/components/chat/ResultEquityChart.tsx`
- Test: `web/__tests__/result-equity-chart.test.ts`
- Test: `web/e2e/issue-422-breakpoint-regressions.spec.ts`

- [ ] **Step 1: Add failing logical-range edge tests**

Define table-driven expectations for sparse, dense, preset, custom, and
restored windows. The visual range includes leading room while the semantic
window still resolves to real observation indexes.

- [ ] **Step 2: Add one shared visual-range helper**

Use the helper for ALL, reset, preset, custom, and restored ranges. Do not add
fake series points or change chart facts, marker selection, tooltip values, or
visible-summary truth.

- [ ] **Step 3: Verify the canvas at 390 and wider bands**

Inspect the first axis label in the result-card frame. Exercise range switches
and reset so padding is not lost after interaction or chart recreation.

### Task 8: Update intended baselines and capture after evidence

**Files:**

- Modify: affected files under `web/e2e/__screenshots__/darwin/`
- Create: `docs/reports/evidence/422/after/*.png`
- Create: `docs/reports/evidence/422/README.md`

- [ ] **Step 1: Refresh baselines without changing tolerance**

```bash
cd web
bun run test:e2e:breakpoints:update
```

Inspect the image diff and list every changed capture with its intended reason.
Confirm `maxDiffPixels: 100` is unchanged.

- [ ] **Step 2: Run the visual suite at the fixed budget**

```bash
cd web
bun run test:e2e:breakpoints
```

- [ ] **Step 3: Capture and inspect seven after frames**

Run the focused acceptance matrix with after capture enabled. Read rendered
text before trusting screenshots, inspect all fourteen before/after frames, and
record the exact capture head in the evidence README.

### Task 9: Full local verification and bounded review

**Files:** Verify the complete diff.

- [ ] **Step 1: Run focused and full web verification**

```bash
cd web
bun test __tests__
bun run lint
bun run build
```

- [ ] **Step 2: Run backend, Ruff, and format verification**

```bash
poetry run pytest
poetry run ruff check src tests workflows scripts
poetry run ruff format --check src tests workflows scripts
```

- [ ] **Step 3: Audit forbidden surfaces and user copy**

Confirm `.env` and `web/.env.local` remain absent and untouched, the visual
budget remains 100, the three excluded plural keys and `periodo` are unchanged,
and no new user-facing em dash was introduced.

- [ ] **Step 4: Request one bounded local review**

Review the exact base-to-head diff against issue #422, the lane spec, responsive
behavior, localization, accessibility, canvas truth, evidence integrity, and
scope. Address only validated findings, then rerun affected checks and recapture
evidence if pixels or rendered text changed.

### Task 10: Reconcile, open the pull request, and close the review loop

**Files:** Verify the would-be merged tree and pull-request head.

- [ ] **Step 1: Fetch integration and classify overlap**

Record the original base and current `origin/codex/private-alpha-next` SHA.
Compare runtime owners, contracts, UI state owners, environment variables, and
affected tests. If integration advanced, merge it one way into the worker branch
without rebasing.

- [ ] **Step 2: Run the merged-tree modularity budget and invalidated gates**

```bash
poetry run python scripts/check_modularity_budget.py
```

Rerun the normal exact-head deterministic gates. Repeat only evidence invalidated
by semantic overlap, but always re-run the focused acceptance matrix at final
head.

- [ ] **Step 3: Commit, push, and open the requested pull request**

Use atomic Conventional Commits. Push
`codex/issue-422-breakpoint-audit` and open a pull request targeting
`codex/private-alpha-next` with issue #422, exact evidence paths, test commands,
original/current integration SHAs, and rollback guidance.

- [ ] **Step 4: Run the pull-request review loop**

Request review once per changed head. Validate and address actionable findings,
recapture evidence after any rendering change, and stop re-requesting when one
latest-delta pass is clean and unresolved review-thread count is zero.

- [ ] **Step 5: Prove exact-head terminal state**

Re-run the evidence matrix against the exact final commit and confirm it leaves
the tree clean. Wait for terminal CI, report the exact PR head, and stop without
merging or deploying.

