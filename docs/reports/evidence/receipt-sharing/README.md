# Evidence receipts: browser evidence

Captured at lane head with `ARGUS_EVIDENCE_RECEIPT_SHARING_ENABLED=true` and
`NEXT_PUBLIC_EVIDENCE_RECEIPT_SHARING_ENABLED=true` against a local memory-mode
backend with no provider keys. Phone width first, both languages.

Enabling sharing is a separate founder decision. Both flags default to false and
these captures exist only to show what the surface does once it is turned on.

## Files

| File | What it shows |
| :--- | :--- |
| `01-receipt-phone-en.png` | A buy-and-hold receipt at 375x812, English. Provenance mark, not-advice framing above the numbers, result metrics, frozen chart, what was tested, assumptions, owner note, frozen-on date, Try Argus. |
| `02-receipt-phone-en-indicator.png` | An indicator receipt. Shows the parameters that actually decided the trades: indicator, period, buy and sell thresholds, direction. Without them two RSI runs with different settings would render as the same strategy with different numbers. |
| `03-receipt-phone-en-recurring.png` | A recurring-buy receipt, whose cadence is what defines it. |
| `04-receipt-phone-es.png` | A Spanish receipt. Chrome in the viewer's language, frozen prose in its own. |
| `05-tombstone-phone-en.png` | A revoked receipt. Honest tombstone, not a 404, still offers Try Argus. |
| `06-tombstone-phone-es.png` | The tombstone in Spanish. |
| `07-receipt-phone-es-indicator.png` | The indicator receipt in Spanish. The strategy labels translate while the frozen values do not, which is why the keys are a closed enum rather than frozen English labels. |
| `08-data-controls-phone-en.png` | The receipt list at phone width, inside the responsive shell: a bottom sheet with a `Data Controls` back row, matching every sibling panel in that submenu. |
| `09-data-controls-en.png` | The receipt list at desktop width, a centred dialog with no back row, which is the same rule the shared panel applies to its siblings. Every receipt, when it was shared, what it shows, every receipt, when it was shared, what it shows, revoke in one action, the automatic revocation reason on the revoked row, and the cached-preview limit stated plainly. |
| `10-receipt-desktop-en-indicator.png` | The indicator receipt at 1280x900, scaling up from the phone. |
| `11-preview-card-en.png` | The real preview image a platform fetches, 1200x630, rendered server side from the frozen payload. |
| `12-preview-card-es.png` | The card for a Spanish receipt, following the receipt's own language because a crawler fetching it has none. |
| `13-preview-card-indicator.png` | The card for the indicator receipt. |
| `14-preview-card-revoked.png` | The card for a revoked receipt. |
| `15-receipt-phone-en-crossover.png` | A moving average crossover receipt. Both windows are named, fast average and window beside slow average and window, plus the direction. A crossover previously rendered with neither, so a 20/50 and a 5/200 crossover were indistinguishable. |
| `16-receipt-phone-es-crossover.png` | The crossover receipt in Spanish. The window labels translate, the frozen values do not. |
| `17-preview-card-crossover.png` | The crossover receipt's preview card. |
| `18-data-controls-phone-es.png` | The receipt list in Spanish inside the mobile sheet. |
| `19-receipt-phone-en-crossover-exit.png` | A crossover whose exit windows differ from its entry windows, which the rule compiler allows. Entry sma 20/50, then ema 9/21 on exit. Reading the windows from the entry rule alone would have stated an exit that never ran. |
| `20-receipt-phone-es-crossover-exit.png` | The same receipt in Spanish. The exit labels translate, the frozen values do not. |
| `21-preview-card-crossover-exit.png` | Its preview card. |
| `crossover-differing-exit-rendered-text.json` | The rendered body text of both, so the entry and exit values can be compared without opening an image. |
| `crossover-rendered-text.json` | The crossover receipt's rendered body text in both languages, so the parameter labels and frozen values can be read without opening an image. |
| `data-controls-capture-steps.json` | The click path each Data Controls capture actually took, and the rendered text at the end of it. |
| `flag-off-byte-identity.json` | Nine flag-off probes with status, header names and body, and the digest they hash to. The same digest comes out at base `01044cda`, where no receipt code exists at all. |
| `og-and-robots-meta.json` | The head metadata a scraper actually reads, captured from the live page, plus the rendered body text. |
| `preview-card-headers.json` | The preview image's response headers. |
| `preview-card-outage-response.json` | The card during a real outage: 503, zero bytes, `Retry-After`, `no-store`. Platforms cache nothing and ask again, instead of pinning a revoked-looking card to a live receipt. |
| `outage-page-text.json` | The outage page's title and text, showing a neutral title rather than a permanent-sounding one. |

## What the metadata capture proves

From `og-and-robots-meta.json`:

- `robots: noindex, nofollow, nocache` and
  `googlebot: noindex, nofollow, noimageindex`.
- The Open Graph title and description are built from the frozen payload only,
  and the description ends in the not-advice framing, so even a bare card carries
  it.
- `bodyText` contains no UUID and none of the never-expose markers.

From `preview-card-headers.json`:

- `x-robots-tag: noindex, nofollow, noimageindex` on the image itself.
- `cache-control: no-store, max-age=0`, so a revoked receipt stops serving its old
  card on the next request. Platforms that already cached it are the limit the
  product states rather than hides.

## Not captured, and why

- **The share action on a result card.** Reaching it needs a completed chat turn,
  which needs a live provider. Its behaviour is covered by
  `web/__tests__/evidence-receipts.test.ts`, and the same copy-link primitive is
  visible in the receipt-list captures.
- **The outage state by request interception.** An earlier attempt intercepted the
  read in the browser, which does nothing to a server-rendered page, and produced
  a normal receipt. Those captures were discarded and retaken with the backend
  process actually stopped.
- **The outage page screenshots.** `preview-card-outage-response.json` and
  `outage-page-text.json` record that state instead, captured with the backend
  process stopped. They were retaken from an earlier invalid attempt that
  intercepted the read in the browser, which does nothing to a server-rendered
  page.
- **A view-count screenshot.** Views are reported by a beacon from the rendered
  page rather than counted when the receipt is read, because the read endpoint also
  answers the metadata pass and the preview image. That is proven by
  `test_reading_a_receipt_never_counts_a_view`, which reads a receipt three times
  and asserts no event, then posts the page's beacon and asserts exactly one.
- **The receipt list in Spanish.** The list is an in-app surface, and selecting the
  app's language is pre-existing client i18n behaviour this lane does not change.
  The receipt page itself is server rendered per request, which is why its Spanish
  capture above is real evidence. The Spanish strings are proven complete by a test
  that compares the whole `receipt` namespace key for key across both bundles.
- **A light-scheme capture.** `ThemeProvider` pins the app's dark theme regardless
  of the operating system preference, so a light capture is a byte-identical
  duplicate rather than evidence.
- **The "Show older links" control.** It only appears past one page of receipts,
  which the rate limit makes slow to reach by hand. Pagination is proven instead by
  `test_the_receipt_list_pages_instead_of_hiding_older_live_links`, which walks
  every page and asserts each receipt appears exactly once.

## The mobile shell, after reconciliation

The incoming responsive-shell lane moved every settings panel onto one shared
panel component that owns the sheet-or-dialog rule. The receipt list still drew
its own centred overlay, so it merged cleanly and rendered a desktop card at
phone width. `08` and `18` show it as a sheet with a back row, and `09` shows the
same panel as a centred dialog with no back row, which is the rule applied rather
than restated.

## Not captured, and why (continued)

- **The Spanish app shell by `Accept-Language` alone.** The signed-in app follows
  the profile's language, so `18` sets it through `PATCH /me` the way the language
  picker does. The receipt page itself is server-rendered from the request header,
  so `04`, `07` and `16` are genuine header-driven captures.

## Fail closed, and what is therefore not capturable

A receipt now either states the strategy in full or is never created. There is no
screenshot of a partially described receipt because that state no longer exists: a
generic `rule_spec` condition tree, or any shape without a projection, answers `422`
`receipt_source_unsupported` and nothing is persisted. That refusal is covered by
`tests/test_public_excerpt_api.py`, which asserts the status, the code, the
owner-facing wording, and that no snapshot was written.

Every screenshot in this directory was verified by reading its rendered text, not by
looking at the file. Two capture attempts in this lane produced plausible-looking
images that were wrong, one from intercepting a request that a server-rendered page
never makes and one from pointing the web server at the wrong API variable, so the
text is the check and the image is the illustration.
