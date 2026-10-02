# Receipt UI checkpoint — October 2, 2026

The private preview now captures receipt sources, saves local drafts and shares one
review identity between personal Chat, group Chat and Plan. Item corrections,
equal/item allocation, shared items, tax/service, optional tip and explicit
confirmation work locally. Capture alone does not post an expense.

App source: `1506899c2956076f5fccfcf746d53c54fa9914a4`.
Signed iPhone build: **3415**, bundle `local.cuadrao.design.47R3855RTJ`.
Device install succeeded and version readback returned 3415. Launch failed because
the phone was locked. Physical camera scanning and location permission/pin behavior
are therefore not claimed as exercised on the phone.

## Verification

- 30 receipt checks: exact cents, shared-item allocation, included charges, explicit
  account/currency, source retention, relaunch, repeated confirmation, interrupted
  posting, write failure, corrupt index and discard boundaries.
- 50 existing group checks passed.
- Six distinct native journeys passed for personal Chat, group Chat/Plan identity, save/later and
  relaunch, merchant/quantity correction, shared items, final confirmation, actual
  Photos import, the warm “You owe” state and visible participant names. Spanish/light and English/dark covered.
- The source viewer displayed the selected fictional receipt image. Arbitrary media
  remains a blank manual draft; it does not acquire the prepared sample's facts.
- Generic simulator build, XCTest build and signed phone build succeeded.
- `git diff --check` and the modularity budget checker passed.

The `core`, `photo`, `direction`, `layout` and `names` JSON summaries are exports from real
Xcode result bundles. Repeated runs cover fixes, not additional unique journeys.
The final item-editing/assignment/relaunch journey ran at the app source above.
Earlier personal, source-import and group-Chat evidence was retained after reviewing
the final delta: only the participant chip layout changed. That layout was rechecked
separately. Subsequent checkpoint changes are tests, documentation and evidence only.

The unlocated “Invalid frame dimension (negative or non-finite)” keyboard warning
still appears in the group journey. It predates this checkpoint and is retained in
roadmap C10; passing tests do not establish that it is resolved.

## Review the screens

- [Capture entry](receipt-capture-en.jpg)
- [Prepared receipt](receipt-prepared-es.png)
- [Readable item assignment](receipt-assignment-names-es.png)
- [Confirmed shared bill and money owed to you](receipt-confirmed-es.png)
- [Money you owe, dark mode](receipt-you-owe-en-dark.png)
- [Receipt saved in Chat](receipt-chat-card-en-dark.png)
- [Same receipt reached from Plan and Chat](receipt-plan-chat-same-record-en.png)
- [Original imported photo](receipt-import-original-en.png)
- [Imported draft without invented extraction](receipt-import-draft-en.png)
- [Personal confirmation after relaunch](receipt-personal-relaunch-en-dark.png)

## Reproduce

Use `ArgusFoundationUITests/CuadraoReceiptUITests` on the task simulator with
`CUADRAO_DESIGN_PREVIEW=true`, `ARGUS_AUTH_ENABLED=false` and
`ARGUS_LOCAL_BUNDLE_IDENTIFIER=local.cuadrao.design`. Run serially. The journey tests
reset only preview groups/receipts. Seed the simulator Photos library with the
committed `import-fixture.png` before the photo journey; use no personal photos.

Run `python3 ios/DesignPreviewTests/run_receipt_preview.py` and
`python3 ios/DesignPreviewTests/run_group_preview.py` for deterministic checks.

## Boundaries

This is local UI preview behavior. Real vision extraction, automatic categorization,
shared source access, canonical posting, cross-device continuity and payment rails
are not connected. Generic Chat Photos/Files still use their existing attachment
preview; receipt sources are reached through Scan or a group's receipt entry.

The existing account preview recreates its fixture accounts on launch; this work
replays confirmed receipts against those stable accounts. It does not make every
newly created preview account durable. Real financial ownership remains with D06/D07.

Current location is opt-in and labelled with its addition time. It is not inferred
to be the merchant's address or the original location of an older uploaded image.
The Files adapter compiles and source persistence is covered, but a complete Files
picker journey was not exercised in this checkpoint.

Approved interaction rules live in the Cuadrao design guide. Future connected work
remains in roadmap C01 under D08/D06/D07, rather than a new competing backlog.

## People polish and contextual-entry lock, build 3416

App source: `60aebb2a8f180d1d2e142378ac753540cebe33c9`.
Signed build **3416** installed on the same iPhone and version readback confirmed it.
The phone was locked during launch, so physical interaction remains unverified.

People now shows identities, money direction, invitations and former members.
Receipt entry and saved receipt cards appear only under Expenses. The group's
existing menu exposes **Preguntar a Cuadrao / Ask Cuadrao** using the existing
callback. No shared context chip or new assistant presentation is implemented.
Owner-only removal is a trailing swipe on iOS 27 and a context menu on older
systems, plus a VoiceOver action. Full swipe cannot remove someone; the existing
review preserves the outstanding-balance restriction and past records.

Six native journeys passed in [the first run](people-polish-journeys.json).
After screenshot review exposed an empty swipe on ineligible rows, the modifier
was removed for those rows. The two affected owner/member journeys passed again
at the final source in [the final run](people-polish-final-journeys.json).
This includes blocked removal, cancel, a zero-balance guest's confirmed removal,
non-owner restrictions, the legacy UI branch, receipt tab placement, saved-source
relaunch, and the relocated Chat entry reopening the same receipt.
The remaining four results are retained because the final delta only changes
native People swipe eligibility. The retained receipt screenshot below was
revalidated against that delta; its static owner layout is unchanged.

- [Owner People screen, Spanish](people-polish-owner-es.png).
- [Member People screen, English and dark](people-polish-member-en-dark.png).
- [Outstanding balance blocks removal](people-polish-removal-review-es.png).
- [People remains clear with a saved receipt](people-polish-receipt-hidden-es.png).
- [Phone delivery readback](people-polish-device.json).

The previous unchanged-code removal test reached its review but failed while
looking for the invitation-preview control. The updated owner journey completed
that invitation and removal sequence in both verification runs; no separate
invitation-code fix was made or claimed. The existing receipt keyboard frame
warning remains recorded under C10. VoiceOver actions were inspected in code;
VoiceOver interaction and a physical legacy-OS run were not performed.

Build, diff and modularity checks passed. Independent scoped review and its final
swipe delta returned no findings; comment review required no deletions. Decisions
and Mobbin references live in the existing Cuadrao guide; outstanding context-chip,
return/draft continuity and direct-capture work remain in roadmap C01/C04.

## Direct capture, build 3417

App source: `84c7c8add595ff141a3314055566dbc0a858fbb7`.
Signed build **3417** installed on the same iPhone, with independent installed
version readback. Launch was blocked by the locked phone; physical interaction
remains unverified. See [delivery evidence](direct-device.json).

Receipt source choice happens once. Chat Scan opens the native scanner; Plan
Expenses and the existing Saved receipts view offer Scan, Photos and Files.
The repeated landing page and pre-capture currency form are removed. Canceling
before acquisition creates no receipt. Successful acquisition persists the
original before review, and Later keeps the draft. Personal imports can remain
without currency, then choose it once during review. Group currency stays fixed.
Generic Chat Photo/File attachments retain their separate preview behavior.

Verification at this source:

- **44 receipt checks and 50 group checks passed.** These include persistence,
  unknown-currency restrictions, one-time currency locking, missing-group rejection
  and source cleanup after an index-save failure.
- **10 native receipt journeys passed**, split into the
  [personal photo-import run](direct-personal-import.json) and the [remaining nine journeys](direct-final-journeys.json). Coverage includes picker cancellation, scanner-unavailable recovery,
  generic attachment routing, Plan/Chat receipt identity, fixed group currency,
  Later/relaunch, item assignment, confirmation and money direction.
- Actual native Photos import used the committed fictional receipt. The original
  source and unknown currency survive relaunch. Files picker open/cancel passed;
  actual Files import and physical camera capture were not exercised.
- Signed device build, diff check and modularity budget passed. Independent scoped
  review and the final Menu delta review returned no findings.

The first native run exposed a Menu label tap-area failure in Saved receipts.
Making the label fill its row with a 44-point minimum height and using borderless
Menu styling fixed it. Screenshot review also caught a truncated empty-state
heading, now shortened. The aborted first run is not acceptance evidence; the
final personal and group saved-list journeys passed after the correction.

- [Receipt source menu](direct-receipt-source-menu-en.png).
- [Saved original, currency can wait](direct-receipt-saved-currency-later-en.png).
- [Imported draft](direct-receipt-import-draft-en.png).
- [Group review, Spanish](direct-receipt-prepared-es.png).
- [Same group receipt reopened from Chat](direct-receipt-plan-chat-same-record-en.png).

Xcode delayed finalizing the second result bundle while collecting simulator
diagnostics. Stopping only that post-test diagnostic collector allowed normal
completion with exit code 0 and a Passed result; no tests were interrupted.

The existing receipt keyboard frame warning remains under C10. Vision extraction,
automatic categorization, connected financial posting and shared source access
remain future connected work in the main roadmap. Context-chip and return/draft
continuity work remains under C01/C04; this checkpoint does not implement it.
