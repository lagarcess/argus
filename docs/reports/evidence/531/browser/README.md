# Issue #531 browser evidence

This directory proves the persisted-result language defect before the fix and
will hold the matching exact-head after capture.

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
