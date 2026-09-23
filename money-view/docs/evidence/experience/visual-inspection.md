# Argus finance visual inspection

Captain inspection resumed September 23, 2026. This record separates visual
judgment from automated overflow checks. Evidence under `final/` captures the frozen application after the delivery and
currency provenance fixes.

Reviewed actual frames of the guest, money, settings, Omnisearch, statement intake
and chat surfaces in English and Spanish, including 320, 390, 768, 1024 and 1440
pixel examples. The final matrix covers each locale at each width.

- Money uses a readable single column on phones. Balance, currency and dated
  source remain together; account actions and the composer fit the viewport.
- Guest entry retains the Argus wordmark, restrained typography and a full-width
  composer. Quick questions form a horizontal rail on narrow screens rather
  than squeezing labels into tiny buttons.
- Settings uses separate section and detail views on narrow screens, and a
  two-column view where space permits. Dark-mode controls and focus indicators
  remain legible. Long labels wrap inside controls.
- Omnisearch has a selected result and adjacent record preview on desktop. The
  mobile preview has an explicit Back action and reachable Open record action.
  Both languages retain record identity, currency, dates and sources.
- Statement intake fits narrow screens, keeps the file/account decision first,
  and discloses CSV/TSV bounds and unsupported formats. The file picker uses the
  browser's native file control, whose language follows the browser.
- Settled 320px chat frames show both send and attachment controls inside the
  viewport. Earlier apparent clipping was caused by capturing before font and
  layout settling, not a reproduced CSS defect. Capture waits for fonts plus
  two animation frames; it now also waits for the recent-history loading state.

No speculative layout rewrite is justified by these frames. Interaction tests
still own keyboard/focus recovery, navigation, draft lifecycle and canonical
record recall. Live mobile keyboards, screen-reader usability and target-device
performance are not established by desktop browser viewport testing.

The final recapture also waits for lazy-loaded recent history before taking the
money view. Its desktop frame now shows the settled empty-history state. The
application source did not change during this evidence correction. Final EN/ES
money, chat, settings, import and search frames were sampled visually again; no
new clipping, overlap or unreadable primary action was found. Desktop and mobile
source details remain accessible beside their figures.
