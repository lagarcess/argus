# Evidence receipts: browser evidence

Captured at lane head with `ARGUS_EVIDENCE_RECEIPT_SHARING_ENABLED=true` and
`NEXT_PUBLIC_EVIDENCE_RECEIPT_SHARING_ENABLED=true` against a local memory-mode
backend with no provider keys. Phone width first, both languages.

Enabling sharing is a separate founder decision. Both flags default to false and
these captures exist only to show what the surface does once it is turned on.

## Files

| File | What it shows |
| :--- | :--- |
| `01-receipt-phone-en.png` | The receipt at 375x812, English. Provenance mark, not-advice framing above the numbers, result metrics, frozen chart, what was tested, assumptions, owner note, frozen-on date, Try Argus. |
| `02-receipt-phone-es.png` | The same surface in Spanish. The chrome is the viewer's language; the frozen prose keeps the language it was authored in. |
| `03-tombstone-phone-en.png` | A revoked receipt. Honest tombstone, not a 404, and it still offers Try Argus. |
| `04-tombstone-phone-es.png` | The tombstone in Spanish. |
| `05-receipt-desktop-en.png` | The same page at 1280x900, scaling up from the phone. |
| `06-data-controls-shared-links-phone-en.png` | The receipt list in Data Controls at phone width. |
| `07-data-controls-shared-links-en.png` | The receipt list at desktop width: every receipt, when it was shared, what it shows, revoke in one action, the automatic revocation reason on the revoked row, and the cached-preview limit stated plainly. |
| `09-preview-card-en.png` | The real preview image a platform fetches, 1200x630, rendered server side from the frozen payload. |
| `10-preview-card-es.png` | The card for a Spanish receipt. It follows the receipt's own language, not a viewer's, because a crawler fetching it has no language and the frozen facts on it are already Spanish. |
| `11-preview-card-revoked.png` | The card for a revoked receipt. |
| `og-and-robots-meta.json` | The head metadata a scraper actually reads, captured from the live page, plus the rendered body text. |
| `preview-card-headers.json` | The preview image's response headers. |

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
