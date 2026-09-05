# Issue #531 browser evidence

This directory proves the persisted-result language defect before the fix and
the matching reader-boundary behavior after the fix.

## Before

`before-en-authored-es-workspace.png` is an unedited Playwright screenshot of
the real Argus UI at integration baseline
`5761dd417429895a24037df8231528c759af4179`. The card was authored in English,
then loaded through the normal memory-persistence conversation reader and the
workspace language was changed to Spanish through Settings.

The browser shows Spanish result chrome, including `LECTURA RÁPIDA`, while the
saved Quick Take remains English. The replay input is the already-recorded real
META result in `docs/reports/evidence/411/browser/en-discovery-messages.json`;
no model, market-data provider, hosted database, merge, or deployment was used
for this hydration reproduction.

See `before-provenance.json` for the sanitized environment record and
`before-visible-text.txt` for the decisive visible text.

## After

`after-en-authored-es-workspace.png` is an unedited headed Playwright capture
at candidate `79c8d78eee3af878b9cc52247bb1da28e7dc90a5`. It reuses the same recorded
real English-authored META result as the before case. The workspace language
was changed through Settings and the page was fully reloaded before capture.

After reload, the result chrome and typed-fact Quick Take are Spanish. The
saved English result body is absent. `after-visible-text.txt` records the
decisive text and `after-provenance.json` records the exact source hashes and
browser steps. This replay made no model or market-data provider calls and no
hosted database reads or writes.

The copy check in `after-copy-handler.txt` proves the Spanish text produced by
the product copy handler. Because the visually hidden copy control was blocked
by pointer hit-testing in this layout, QA installed a temporary browser-only
`navigator.clipboard.writeText` spy and invoked the real DOM click handler. It
does not claim that the operating-system clipboard persisted the text.

`after-es-recents-preview.png` and `after-es-search-preview.png` cover the same
persisted result in Spanish Recents and Search. Search used the prefix
`A simple buy-and-hold` from the privately retained English result body. The
reader-facing preview stayed `Resultado de simulación · META · Comprar y
mantener`; the retained sentence did not render. The English conversation
title remains as saved artifact identity under the reviewed contract. See
`after-previews-provenance.json` and `after-previews-visible-text.txt`.

## DCA acceptance blocker

The requested non-buy-and-hold DCA browser acceptance did not complete. One
provider-backed UI turn was submitted, but the QA driver allowed shell
expansion to remove literal `$500` and `$0` before Playwright received the
prompt. The product correctly asked for the missing amount, and no Run action
was clicked. This is a harness failure, not a product finding.

The corrective prompt was then filled through shell-free subprocess arguments
and asserted byte-for-byte in the real browser before Send. Its screenshot and
readback are `dca-corrective-prompt-unsent.png` and
`dca-corrective-prompt-readback.json`. The execution gate rejected a second
paid provider turn pending direct user approval, so QA did not submit it or
route around the gate. `dca-blocker-provenance.json` records one submitted
provider-backed UI turn, zero backtests, and zero Run clicks. Raw provider
receipts remain private in temporary storage and are not included here.

## After reconciliation

`after-reconciliation-en-authored-es-workspace.png` repeats the provider-free
hydration proof at merge head
`5b3f020be8b2a42621c1d8bf0d26f5f3306d2d4f`, whose parents are the evidenced
lane candidate `79c8d78eee3af878b9cc52247bb1da28e7dc90a5` and integration
`dcbc7af5420d5d5dc41371bc1add9fef57c4582c`.

The capture came from a git archive of that exact merge head. QA loaded the
same recorded English-authored META artifact, selected Spanish through
Settings, and reloaded the page. `LECTURA RÁPIDA`, the typed-fact result body,
chart context, and next actions remained Spanish; the saved English result
body did not render. The replay loaded no credential file and made no model,
market-data provider, hosted-database, DCA, or backtest call.

`after-reconciliation-provenance.json` records the screenshot digest, exact
commit parents, recorded-source digest, replay-harness adjustment, and hashes
for the reader-boundary source files used by the archived application.
