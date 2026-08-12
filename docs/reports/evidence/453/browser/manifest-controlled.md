# Issue 453 controlled guest browser evidence

Date: 2026-08-12

Evidence class: **controlled**

- Historical base: `8025672924d1c74eb80cc926c72b5d8574b613d7`
- Reviewed product source: `d87d5d6524e0af89d99dab26cc3e4b6f56c24742`
- Evidence storage commit:
  `d5b0d6ecbde32f0bdf94945f99a9dce4b925057e`
- Browser path: the real Next.js guest `/chat` shell at each SHA
- Browser: repository-pinned Playwright Chromium
- Viewport: `1440x1000`, desktop, light color scheme
- Locales: `en` and `es-419`
- Captures: 16 PNG files, one per scenario, locale, and phase

## Evidence boundary

Every file in this directory is controlled evidence. Playwright intercepted
the browser API calls and returned local deterministic payloads. No real API,
LLM, market-data provider, Supabase project, or Render Workflow was called.
Workflow execution remained false and the market-data mode remained the
synthetic unit fixture.

The exact-base backend RED evidence in
[`../baseline.md`](../baseline.md) proves the underlying defects against
`8025672924d1c74eb80cc926c72b5d8574b613d7`. These browser artifacts show how
the corresponding controlled payloads render inside the real guest shell.
They do not claim a live replay of a production transcript. The production
transcript identifiers in the receipts are provenance only.

The exact-base raw-summary pair exercises the old degraded raw-value renderer.
The other base scenarios use controlled pre-fix persisted prose because their
bad admission paths originate in the backend and cannot be generated in a
provider-free frontend capture. The candidate raw-summary, capital, and
acknowledgment pairs use typed degraded metadata. The candidate DCA pair uses
a typed `dca_accumulation` amount clarification with monthly cadence and a
five-year rolling window in its sidecar.

## Commands

The exact base ran from an isolated detached worktree. Its temporary
`node_modules` symlink pointed to the repository installation and was not part
of the evidence commit. That temporary worktree was removed after the baseline
capture.

```bash
git worktree add --detach /private/tmp/argus-453-browser-proof/base \
  8025672924d1c74eb80cc926c72b5d8574b613d7
ln -s /Users/garces/.codex/worktrees/3842/private-alpha-next/web/node_modules \
  /private/tmp/argus-453-browser-proof/base/web/node_modules
```

The temporary ignored harness used Next webpack mode because Turbopack rejects
a dependency symlink that points outside the temporary worktree root.

```bash
EVIDENCE_PHASE=baseline \
EVIDENCE_SHA=8025672924d1c74eb80cc926c72b5d8574b613d7 \
EVIDENCE_OUTPUT_ROOT=/Users/garces/.codex/worktrees/3842/private-alpha-next/docs/reports/evidence/453/browser \
EVIDENCE_APP_WEB_DIR=/private/tmp/argus-453-browser-proof/base/web \
EVIDENCE_PORT=3453 \
web/node_modules/.bin/playwright test \
  --config=web/temp/issue-453-browser-proof/playwright.config.ts
```

Result: `8 passed`.

```bash
EVIDENCE_PHASE=after \
EVIDENCE_SHA=d87d5d6524e0af89d99dab26cc3e4b6f56c24742 \
EVIDENCE_OUTPUT_ROOT=/Users/garces/.codex/worktrees/3842/private-alpha-next/docs/reports/evidence/453/browser \
EVIDENCE_APP_WEB_DIR=/Users/garces/.codex/worktrees/3842/private-alpha-next/web \
EVIDENCE_PORT=3454 \
web/node_modules/.bin/playwright test \
  --config=web/temp/issue-453-browser-proof/playwright.config.ts
```

Final-head refresh result: `8 passed`.

The eight PNG files were recaptured at the reviewed product source. Their bytes
match the prior deterministic captures, so Git records no PNG content delta.
The refreshed candidate receipt records the new product-source SHA. All eight
guest, visible-copy, forbidden-copy, console-error, and page-error assertions
ran again and passed.

## Assertion summary

| Scenario | Controlled base | Controlled candidate |
| --- | --- | --- |
| Raw summary | The model summary `User wants to invest $500` is the grammatical subject in both locales. | The raw summary is absent. Typed generic rule copy renders in both locales. |
| Coca-Cola DCA | Monthly purchases over five years are refused and redirected to buy and hold. | The typed `dca_accumulation` trajectory asks for the recurring monthly amount and does not use capability-refusal copy. |
| NFLX `$500` bounds | `$500` is described as something Argus cannot run. | Typed numeric bounds render the exact `$1,000` to `$100,000,000` range without capability wording. |
| Premature acknowledgment | The assistant acknowledges `$500` and then rejects it. | The locale-matched acknowledgment is present only in hidden controlled metadata, remains absent from the page, and the typed bounds recovery renders instead. |

Before every screenshot, the harness asserted all of the following:

- `/api/v1/me` was requested and returned `account_kind: "guest"`.
- The visible guest header contained the localized sign-in action.
- The visible guest footer contained the temporary-chat expiry notice.
- The user request and expected assistant response were visible inside the
  localized conversation region.
- Candidate forbidden strings were absent from the full rendered page.
- Browser console errors and page errors were both empty.

All 16 PNG files are non-empty and report `1440x1000` dimensions. The runner
printed Node deprecation and color-mode warnings only. Those are local tooling
warnings and did not enter the browser console or page.

The ignored helper directory `web/temp/issue-453-browser-proof/` was deleted
after this refresh. No helper or local result artifact remains.

After the evidence storage commit, a path-excluded diff against reviewed
product source `d87d5d6524e0af89d99dab26cc3e4b6f56c24742` returned no product-source
path. This manifest line is stored in a follow-up provenance-only commit, so
the source SHA and evidence commit remain separate and inspectable.

## Artifact inventory

Rendered-text receipts:

- `receipts-baseline-controlled.json`, 8 receipts
- `receipts-after-controlled.json`, 8 receipts

English screenshots:

- `baseline-controlled-en-raw-summary.png`
- `after-controlled-en-raw-summary.png`
- `baseline-controlled-en-supported-dca.png`
- `after-controlled-en-supported-dca.png`
- `baseline-controlled-en-capital-bounds.png`
- `after-controlled-en-capital-bounds.png`
- `baseline-controlled-en-premature-acknowledgment.png`
- `after-controlled-en-premature-acknowledgment.png`

Spanish screenshots:

- `baseline-controlled-es-419-raw-summary.png`
- `after-controlled-es-419-raw-summary.png`
- `baseline-controlled-es-419-supported-dca.png`
- `after-controlled-es-419-supported-dca.png`
- `baseline-controlled-es-419-capital-bounds.png`
- `after-controlled-es-419-capital-bounds.png`
- `baseline-controlled-es-419-premature-acknowledgment.png`
- `after-controlled-es-419-premature-acknowledgment.png`

## Visual inspection

The following original-resolution files were opened and read after capture:

- English raw-summary base and candidate
- Spanish premature-acknowledgment base and candidate
- English candidate DCA clarification
- Spanish candidate capital bounds

The inspected frames show the full guest chat shell, the localized sign-in
action, the conversation, composer, safety copy, and temporary-session notice.
The visible assistant text matches the receipts. No clipping, overlays, user
identifiers, or secrets were observed.
