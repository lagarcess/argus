# Issue 422 Breakpoint Audit Fixes

Repair findings 2 through 8 from the committed breakpoint audit without
changing product contracts, backend run accounting, or the visual harness
tolerance.

Founder-locked 2026-08-11 from issue #422 and the delivery instructions for
this lane.

## 1. Lane boundary

- **Integration base:** fetched `origin/codex/private-alpha-next` at
  `360d7bc6c93ab4b90c1b58ab08fd8a68553500a5`.
- **Worker branch:** `codex/issue-422-breakpoint-audit`.
- **Delivery:** a reviewed pull request targeting
  `codex/private-alpha-next`. Do not merge or deploy.
- **No-touch surfaces:** `.env`, `web/.env.local`, backend run-consumption
  accounting from #437, API contracts, persistence, and market-data or model
  paths.
- **Harness lock:** `maxDiffPixels: 100` remains unchanged. Baselines move only
  when the corrected rendering legitimately moves pixels.

Before opening `StrategyConfirmationCard.tsx`, the lane confirmed that #437 is
an open backend run-consumption issue. Its declared files and behavior do not
include the confirmation card. Changes to that card since the audit head came
from the merged confirmation editing lane, not #437.

## 2. Branch-point reproduction

The issue evidence at `d9e8a3c5` was read before source inspection. The same
surfaces were then rendered at the lane base in a real 390 by 844 viewport with
the deterministic breakpoint fixture.

1. **Finding 2 still reproduces.** The current title receives 92px for 191px of
   text and renders as `Apple vs SP...`. The intervening merges improved the
   original `Ap...`, but the row is still not identifiable by its full title.
2. **Finding 3 is partially masked, not closed.** The exact glyph overdraw from
   the audit frame is now a 4px gap: the date ends at x=317 and the 44px menu
   target starts at x=321. The same one-line competition still owns both
   finding 2 and the unsafe menu spacing, so this lane keeps the confirmed
   finding in scope and gives metadata deliberate room.
3. **Finding 4 still reproduces.** The rendered card text contains `AAPL`
   twice and the frame shows the entity chip immediately beside the same bare
   heading.
4. **Finding 5 still reproduces.** The current catalog resolves count 1 as
   `Quedan 1 hoy` and `1 disponibles esta hora ...`.
5. **Finding 6 still reproduces.** The rendered email and password placeholders
   and password-toggle accessible name omit their diacritics. The other three
   approved values remain unaccented in the same live catalog.
6. **Finding 7 still reproduces.** The mobile dossier dialog contains the exact
   conversation title twice.
7. **Finding 8 still reproduces.** The 390px result card canvas cuts the leading
   `2` from the first `2023` time-axis label.

## 3. Locked fixes

### 3.1 Omnisearch row at 390

Below the 720px tablet breakpoint, the conversation title gets its own line. Status
and type badges plus the relative date move to a compact metadata line. The
date must remain outside the row-menu hit target with at least 8px of visible
separation. The full fixture title must fit at 390 without horizontal clipping.

The 720 and 1024 layouts retain their existing information and interaction
model. Rename, row activation, keyboard behavior, and the explicit touch menu
remain unchanged.

### 3.2 Confirmation asset heading

Keep `AssetSymbols` and its `EntityToken` chips. When a localized strategy
label exists, it remains the heading. When the fallback would merely restate
one or two displayed symbols, omit that redundant heading. Three or more assets
retain the existing count heading, and an asset-free fallback retains the
existing title behavior.

This keeps `chat.confirmation.asset_count` reachable only above two. It does not
change that excluded plural key.

### 3.3 Spanish count agreement

Add singular and plural variants only for:

- `settings.data.usage_panel.left_today`
- `settings.data.usage_panel.hourly_available`

Count 1 uses `Queda`, `disponible`, and their singular agreement. Other counts
retain the current plural copy. Do not change:

- `command_palette.decision_note_count`
- `feedback.attachments_with_count`
- `chat.confirmation.asset_count`

English stays count agnostic.

### 3.4 Spanish auth diacritics

Change exactly these six `es-419` values:

- `Correo electrónico`
- `Contraseña`
- `Inicia sesión para continuar`
- `Iniciando sesión...`
- `Mostrar contraseña`
- `Ocultar contraseña`

Do not change any occurrence of `periodo`.

### 3.5 Mobile dossier title

Keep the sheet's accessible name while visually hiding its primitive heading.
The dossier's existing `h1` remains the single visible conversation title. The
desktop dossier pane stays unchanged.

### 3.6 Chart edge room

The chart adapter, not the fixture, owns the repair. Add visual logical-range
room at the leading edge for ALL, preset, custom, restored, and reset views so
the first time-axis label fits inside a 390px canvas. Semantic range summaries
remain clamped to real observations, and every real data point remains visible.

The behavior must cover sparse annual fixtures, dense series, intraday data,
and existing marker/range exploration without inventing observations.

## 4. Acceptance evidence

Commit seven before and seven after frames under
`docs/reports/evidence/422/`, one pair for each numbered finding. Findings 2 and
3 may originate from the same Omnisearch row but each gets its own labeled
frame so its acceptance claim is explicit.

Every capture must:

- use a real 390 by 844 viewport or a real element within that viewport;
- use deterministic fixture data and no live provider calls;
- include a rendered-text or geometry assertion before the screenshot;
- be visually inspected after capture;
- be regenerated and re-read at the exact final head.

Update only the breakpoint baselines whose intended text or layout changed.
Record each changed baseline and why. Run the visual suite with
`maxDiffPixels: 100`; never raise the budget.

## 5. Verification and release gates

- Focused red-green Bun and Playwright coverage for all seven findings.
- Full web test suite and ESLint.
- Full backend test suite, Ruff lint, and Ruff format check.
- Breakpoint visual suite at the fixed 100-pixel budget.
- Modularity budget on the would-be merged tree after final reconciliation.
- One bounded local review pass, then the pull-request review loop until the
  latest delta is clean and unresolved review-thread count is zero.
- Terminal CI at the exact pull-request head.

## 6. Stop conditions

- Stop if any repair requires an API, database, run-consumption, or provider
  behavior change.
- Stop if visual proof would spend a real model turn, market-data request, or
  backtest.
- Stop and report if integration advances with semantic overlap that
  invalidates accepted evidence.
- Stop after the clean reviewed pull request. Do not merge or deploy.

## Sources

- GitHub issue #422
- `docs/evidence/breakpoint-audit/`
- `docs/BREAKPOINTS.md`
- `.agent/designs/argus/DESIGN.md`, section 8
- `docs/PRODUCT.md`
- `docs/ARCHITECTURE.md`
- `docs/API_CONTRACT.md`
- `docs/DATA_MODEL.md`
- `docs/specs/argus-active-roadmap.md`
