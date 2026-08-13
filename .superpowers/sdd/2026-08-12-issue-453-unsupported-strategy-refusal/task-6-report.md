# Task 6 report: controlled bilingual guest browser proof

## Outcome

Captured durable controlled guest-browser proof for all four issue #453 defects
in English and es-419. The evidence set contains 16 screenshots at `1440x1000`,
two rendered-text receipt files with 8 records each, and one controlled-evidence
manifest.

- Exact historical base: `8025672924d1c74eb80cc926c72b5d8574b613d7`
- Reviewed product source: `d87d5d6524e0af89d99dab26cc3e4b6f56c24742`
- Evidence storage commit:
  `d5b0d6ecbde32f0bdf94945f99a9dce4b925057e`
- Exact route: `/chat`
- Account contract: `account_kind: "guest"`
- Evidence class: controlled, not live

## Approach

1. Created an isolated detached worktree at
   `/private/tmp/argus-453-browser-proof/base` for the exact historical base.
2. Used the repository-pinned `web/node_modules/.bin/playwright` runner.
3. Ran the real Next.js guest `/chat` shell at the base and candidate SHAs.
4. Intercepted every `/api/v1/**` browser request with deterministic local
   responses. No real API, LLM, Supabase, market-data provider, or workflow was
   called.
5. Asserted the guest account response and visible sign-in and temporary-chat
   affordances before each screenshot.
6. Captured one screenshot for each phase, locale, and scenario.
7. Recorded rendered request text, assistant text, forbidden-string results,
   guest proof, prompt source, evidence class, viewport, SHA, and transcript
   provenance in JSON receipts.
8. Opened and read representative original-resolution English and Spanish
   before and after frames.

The exact-base raw-summary case exercised the old degraded raw-value rendering
key. The other base cases used clearly labeled controlled pre-fix persisted
prose because those failures begin at backend admission and cannot be produced
by a provider-free frontend fixture. Candidate raw-summary, capital-bounds, and
acknowledgment cases exercised typed degraded metadata. Candidate DCA exercised
a typed supported `dca_accumulation` amount clarification.

## Commands and results

Exact-base setup:

```bash
git worktree add --detach /private/tmp/argus-453-browser-proof/base \
  8025672924d1c74eb80cc926c72b5d8574b613d7
ln -s /Users/garces/.codex/worktrees/3842/private-alpha-next/web/node_modules \
  /private/tmp/argus-453-browser-proof/base/web/node_modules
```

The initial Next dev attempt used Turbopack, which rejected the temporary
dependency symlink because it points outside that worktree root. The ignored
harness was changed to Next webpack mode. The exact-base app then started and
the exact-base requirement remained satisfied.

Baseline capture:

```bash
EVIDENCE_PHASE=baseline \
EVIDENCE_SHA=8025672924d1c74eb80cc926c72b5d8574b613d7 \
EVIDENCE_OUTPUT_ROOT=/Users/garces/.codex/worktrees/3842/private-alpha-next/docs/reports/evidence/453/browser \
EVIDENCE_APP_WEB_DIR=/private/tmp/argus-453-browser-proof/base/web \
EVIDENCE_PORT=3453 \
web/node_modules/.bin/playwright test \
  --config=web/temp/issue-453-browser-proof/playwright.config.ts
```

Final baseline result: `8 passed`.

A preliminary harness run rejected `/api/v1/memory/availability` because that
read had not yet received a controlled response. The harness added the standard
disabled response `{ "available": false, "reason": "disabled" }`. The final
baseline run above then passed all eight cases. This was a fixture-completeness
failure, not a product failure.

Candidate capture:

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

All eight candidate PNGs were recaptured at the reviewed product source. Their
bytes match the prior deterministic captures, so Git records no PNG content
delta. The refreshed receipt carries the new product-source SHA, and all guest,
visible-copy, forbidden-copy, console-error, and page-error assertions ran
again.

Artifact verification:

```bash
find docs/reports/evidence/453/browser -maxdepth 1 -name '*.png' \
  -type f -exec file {} \;
find docs/reports/evidence/453/browser -maxdepth 1 -name '*.png' \
  -type f -size 0 -print
```

Result: 16 non-empty PNG files, all `1440x1000`; the zero-size query returned
no paths.

## Browser results

- Raw summary: visible before in both locales, absent after in both locales.
- Coca-Cola DCA: refused before, routed to a typed recurring monthly amount
  clarification after.
- NFLX `$500`: described as something Argus cannot run before, rendered with
  the precise `$1,000` to `$100,000,000` range after.
- Premature acknowledgment: visible before, absent after, with typed bounds
  rendered instead.
- Guest shell: `/api/v1/me` observed with `account_kind: "guest"`, localized
  sign-in visible, temporary-chat notice visible, and guest expiry attribute
  visible before every screenshot.
- Browser errors: zero console errors and zero page errors across all 16
  captures.

The runner printed local Node deprecation and color-mode warnings. These were
tooling warnings only and did not enter the browser console or page.

## Artifact inventory

Tracked browser evidence under `docs/reports/evidence/453/browser/`:

- 8 baseline controlled PNG screenshots
- 8 candidate controlled PNG screenshots
- `receipts-baseline-controlled.json`, 8 records
- `receipts-after-controlled.json`, 8 records
- `manifest-controlled.md`

Total browser artifacts: 19.

The detailed filename inventory is in `manifest-controlled.md`.

## Visual inspection

Opened and read at original resolution:

- `baseline-controlled-en-raw-summary.png`
- `after-controlled-en-raw-summary.png`
- `baseline-controlled-es-419-premature-acknowledgment.png`
- `after-controlled-es-419-premature-acknowledgment.png`
- `after-controlled-en-supported-dca.png`
- `after-controlled-es-419-capital-bounds.png`

Each inspected frame showed the full guest shell, localized sign-in action,
conversation, composer, safety copy, and temporary-session notice. The
assistant text matched the receipts. No clipping, overlays, secrets, email
addresses, or user identifiers appeared.

## Controlled versus live limits

This proves deterministic browser projection and guest-shell behavior at the
two recorded SHAs. It does not prove a live provider turn, production
deployment, live Supabase persistence, or replay of the production
transcripts. Transcript identifiers are provenance only. The browser manifest
explicitly pairs this controlled proof with the exact-base backend RED evidence
in `docs/reports/evidence/453/baseline.md`.

## Temporary helpers

The exact ignored helper directory
`web/temp/issue-453-browser-proof/` was deleted after the final-head refresh.
Its Playwright config, spec, and local result diagnostics no longer exist. No
environment file was created or edited. The exact-base temporary worktree
directory had already been removed and its Git worktree metadata was pruned.

## Self-review

- No production code, tests, locales, API contract, environment, release, or
  other tracked surface was edited.
- All authored evidence prose avoids em dashes.
- Every durable browser artifact is labeled `controlled` in its filename or
  document heading and carries `evidence_class: "controlled"` where
  structured.
- Original transcript identifiers are labelled provenance only.
- The guest account payload and visible shell affordances are asserted for
  every screenshot.
- Candidate forbidden strings are checked against the complete rendered page.
- The final scope audit contains only the two assigned tracked paths.
- The final post-commit audit compares the evidence commit with
  `d87d5d6524e0af89d99dab26cc3e4b6f56c24742` while excluding the assigned
  evidence and report paths. It returned no product-source path after the
  evidence storage commit. The same check is repeated after this
  provenance-only follow-up commit.

## Concerns

No product concern. This evidence remains intentionally controlled and must not
be promoted as live hosted acceptance.
