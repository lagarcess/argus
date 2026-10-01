# Collection gesture checkpoint — October 1, 2026

UI-only source: `0cba90ba277e55c48147a170b3bf9be2e67b0ab7` (main implementation
`a136c0afebffb994101b052a24477055590dacea`). The following evidence commit changes
documentation/images only. Provider integration, payment execution and shared
permissions were not enabled.

## Verification

- Ten distinct native UI tests passed across `CuadraoPolishUITests` and
  `CuadraoCollectionUITests`. Covered account drag, both swipe actions, undo,
  all-archived recovery, currency search, English accessibility text size/dark mode,
  forecast scope versus explicit creation scope, plan edit/archive/restore,
  People owner/member controls, blocked outstanding-balance removal, settled guest
  removal, group drag/relaunch persistence and archive/restore.
- 50 group state checks and 58 Plan state checks passed. New checks preserve
  historical entries through member removal, block unsettled removal, and persist
  viewer order/removal. Existing fixed-currency and cent-conservation checks pass.
- Xcode 27 / iOS 27 simulator: `8AFB6084-8918-416E-9164-E21061306BEC`.
- Final signed phone build 3404: iPhone 15, iOS 27.0.1. Installed successfully (sequence 2088); final launch was blocked by the locked
  phone. Build 3403 launched before the final icon-only correction. Physical touch/VoiceOver were not
  observed by automation. Deployment minimum stays iOS 17.

## Evidence lineage

The final icon-only swipe change was rerun through both Home drag/edit/archive/undo
and Plan edit/archive/restore; their final screenshots are included. Earlier
People, scope, large-text and group-order screenshots were revalidated by diff:
those surfaces and state owners are unchanged by the final swipe-label correction.
The Home divider correction was separately reverified in the final Home journey.
`manifest.json` identifies each capture and its originating test.

First test iterations caught test-coordinate overshoot and a doubled accessibility
label. Both were corrected; the affected journeys subsequently passed. A group drag
initially dropped outside the visible collection; the test now drops within the
second card and proves changed order after relaunch. Final native drag run returned
no warnings. The forced legacy branch was exercised on iOS 27 for member-control
visibility; it is not a claim of an actual iOS 17 runtime test.

## Review images

- [Plan scope](plan-local-forecast-scope-es.png)
- [Plan archive gesture](plan-swipe-archive.png)
- [Home inline order](home-inline-reorder-es.png)
- [Home archive gesture](home-swipe-archive-es.png)
- [People organizer](group-people-owner.png)
- [People member](group-people-member-en.png)
- [Removal review](group-outstanding-removal-review.png)
- [Group order](groups-reordered.png)
- [Large-text Plan](plan-all-spaces-dark-large-en.png)

Future work remains in `docs/specs/argus-execution-board.md`; this folder records
acceptance evidence only.
