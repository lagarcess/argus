# W1b report: PR #790 second worker (units A to E8)

Branch `codex/cuadrao-release-ui`, worktree `/Users/garces/.codex/worktrees/cuadrao-release-ui/private-alpha-next`.
Start head `e9195b58`. Final pushed head: see "Head" at the bottom.
Simulator iPhone 18 Pro Max `0335699A-…`. Every UI run was `xcodebuild test-without-building -only-testing:…`
under `lockf -k …/mac-sim.lock` (script `ios/.build/w1b/focused.sh`, logs in `ios/.build/w1b/runs/<name>/`).
No full suite was run. Summaries of each run are committed under
`docs/reports/evidence/cuadrao-release-ui/2026-10-03-w1b/`.

## Commits (in order)

| SHA | Unit | What |
| --- | --- | --- |
| `26055a28` | E1 + F2 | `CuadraoFirstRelease.editsAvatar` replaces `showsPersonalPhoto`; release hides the avatar editor entry (connected Profile, review host) and the preview avatar picker, so no photo picker or Reposition in release. DEBUG unchanged. |
| `a488a1c6` | A1 attempt | Inbox value routing. Did not fix the failure. |
| `8bd88ae6` | E2 / F3 | `ReleaseRecordedMonth.noRecords` -> `missingCoverage`; shares Home's missing-coverage copy through `CuadraoMissingCoverage`; gallery heading reuses "Historial incompleto". |
| `6bd93b85` | integration defect | Design gallery "month without records" sample said Sin datos; now Home's "Sin gastos". |
| `36cafb10` | E5 / F6 | Restores "Covered zero months stay in the average denominator" (81 Home checks pass). |
| `69f5ebef` | E6 / F7 | `--cuadrao-release-ui` read only in DEBUG. Release binary contains neither preview argument (strings check). |
| `26b3e1ab` | E7 / F8 | `profile.preferences` and `sheet.close` identifiers restored; dead compactMap guard removed; English locked deletion copy pinned verbatim (byte-compared with the handoff doc; test passes). |
| `5130c02d` | E4 / F5 | Mac pass adds `ReleaseUIJourneyTests`, `run_release_updates`, new `run_release_identity.py`. `cuadrao-design-mac-pass.sh checks`: all 8 runners pass. |
| `81076e6e` | A1 | Reverts `a488a1c6` with the reason. |
| `00b5be65` | B, integration defect | Money fields drop keystrokes; see B. |
| `c6b63c31` | B, integration test defect | Scan parity journey waits for receipt capture. |
| `300abf54` | E8 | Invitation prominent labels use the on-accent ink. |
| `030f2c5e`, `7df801f8`, `3370ba50` | E3 + evidence | README dated correction of the old "Updates/no-data/read-only" claim, Review fixes section, run summaries and screenshots. |

Integration-defect commits for the lead (defects present on integration `a8c37d3a`):
`6bd93b85` (gallery empty-month copy), `00b5be65` (money keystrokes, app), `c6b63c31` (stale scan test).

## A. #790-area failures

### `ReleaseUIJourneyTests.testUpdatesNoDataAndReadOnlyHistory`: reproduced, not fixed

- Reproduced alone at `e9195b58` (run A1) and on the routed build (batch1).
- The README and W1 cause ("back lands on the review root") is a symptom. A trace test
  (`W1bDiagnosticUITests.testUpdatesBackTrace`, diag2) shows that after tapping
  `updates-row-0` and waiting 1 s, the only navigation bar is still titled "Novedades"
  (the gallery), not "Novedad" (the notice). The notice is not on screen when the test
  taps back, so back pops the gallery and lands on the root. The test's `bill-notice-es`
  capture is therefore of the gallery, not the notice.
- So the defect is "opening a notice does not stay open". Value routing (`a488a1c6`) did
  not change it; reverted in `81076e6e`.
- `markRead` ruled out: an experiment build with the notice's `onAppear { markRead }`
  removed (no other change, run `updates-nomarkread`) gives the same result, bar still
  "Novedades" after the tap.
- Shared pattern with the Home activity failure below: both are `NavigationLink` rows with
  `.buttonStyle(.plain)` inside a `ScrollView`, and in both the XCUITest tap lands on the
  row and nothing is pushed. Next step: tap the same rows by hand in the simulator (the
  lock queue left no window for it) to decide app versus XCUITest.
- Reach: DEBUG review gallery only (the connected inbox shows the unavailable state).

### `CuadraoSupportUITests.testHomeActivityReturnsToSameRow`: reproduced, different failure, not fixed

- Reproduced alone at `e9195b58` (A2) and on the review-fix tree (batch1), both at line
  104: tapping the Home activity row does not open the detail (`activity-detail-title`
  never appears), not W1's "row under the tab bar".
- Trace (diag2): after the test's reveal drag the row is at y 731 to 771 of 956 pt,
  hittable, the tab bar at y 862. The tap lands on the row; the screenshot after the tap
  (`home-after-tap` in diag2's result bundle) still shows Home with the row fully
  visible. So the row is not under the bar; the tap does not navigate.
- Root cause not established. Candidates: the tap arrives while the scroll view is still
  decelerating from the 0.01 s press-and-drag (a tap on a moving list only stops it), or
  the `NavigationLink(value: HomeRoute.activity)` push is lost. A person would feel the
  second; the first is test-only. Not decided, not fixed.

## B. Uninvestigated failures, one uncontended run at `e9195b58` (run B, 7 tests)

| Test | Alone | Classification | Fix |
| --- | --- | --- | --- |
| `CuadraoConsistencyUITests.testMoneyEntryAndBlankCreationSpanish` | fails ("125") | Real app defect (below) | `00b5be65`, passes after |
| `CuadraoGroupDesignUITests.testSharedJourneySpanish` | fails (line 48: split save disabled) | Line 48 is the same money defect; after `00b5be65` it passes line 48 and fails at line 56 | Line 56 not fixed (below) |
| `CuadraoHistoryDesignUITests.testScanAndEnglishParity` | fails | Stale test: #785 routes Scan to receipt capture (simulator shows "Probar un recibo de ejemplo"); #792's test waited for the old example sheet | `c6b63c31`, passes |
| `CuadraoPlanDesignUITests.testExactAmountsDarkModeAndVoiceContinuity` | passes | Contention flake in the full suite | none |
| `CuadraoReceiptUITests.testPhotoImportKeepsOriginalWithoutInventedItems` | fails at "USD" | The "Choose currency" Menu did not open after the tap (recording frames show the review sheet with no menu); the helper's reveal loop then swipes. Cause not established | not fixed |
| `CuadraoReceiptUITests.testReceiptShowsYouOweWhenAnotherPersonPaid` | fails | Test ambiguity: `app.buttons["Ana"]` matches two elements after opening the payer picker | not fixed (test scoping) |
| `FinancialLoopUITests.testSharedPlanningFourKinds…` | fails in 0.05 s | Environment: needs `ARGUS_TEST_SHARED_PLAN_*` from a seeded local backend; it hard-fails instead of skipping | not fixed (should XCTSkip like auth tests) |

Money defect, evidence (runs `money-diag-before`, `money-after`):
- Old code, one character per `typeText` (hand-paced 0.35 s, and no pause): both give
  `1,250.5`. Trail: `1, 12, 125, 1,250, 1,250., 1,250.5`.
- Old code, `typeText("1250.5")` in one burst: `150.5` (B run: `125`, W4: `1`), and SwiftUI
  logs "Modifying state during view update" only in this case.
- Cause: `CanvasDecimalInput`'s delegate wrote `raw`/`error` bindings synchronously.
  Keystrokes delivered while SwiftUI is updating write state inside the update; SwiftUI
  drops those writes, and the next `updateUIView` saw field text != stale `raw` and reset
  the field. A person typing quickly while the main thread is busy hits the same path.
- Fix `00b5be65`: the coordinator owns the field text, defers binding writes to the main
  queue, and `updateUIView` rewrites the field only when no write is in flight. Grouping,
  caret placement and the grouping fade unchanged. After: burst typing gives `1,250.5`
  with no warning; the money journey, the plan exact-amount journey and both per-character
  checks pass.

Group line 56 (`group-repayment-amount` still shown after Save): the screenshot before
Save shows "Registrar reembolso" visibly disabled with DOP 500. Save is disabled when the
amount exceeds `min(-balance(sender), balance(receiver))`
(`CuadraoGroupExpenseEditor.swift` repayment `maximum`). The journey first edits the split
to Tú 500 / Ana 300, so Ana probably owes less than 500. Likely a test-data defect; the
arithmetic was not proven.

## C. Never-idle Recents: diagnosis, not fixed

- Not the rename Save. In run batch1 the full-prefix variant (pin, mark unread, rename,
  Save) reached idle in 0.07 s after Save. The minimal variant (rename as the first
  context-menu action in the process) went non-idle at the tap on "Cambiar nombre",
  that is, when the rename alert is presented from the context-menu action: five 60 s
  "App animations complete notification not received" waits in a row. A second minimal
  run (diag2) did not stall. So it is intermittent and starts at alert presentation from
  a context menu, not after Save.
- App code on that path has no `repeatForever`, phase animator, symbol effect or
  `withAnimation` (`CuadraoChatHistory.swift`); the only timer is `CuadraoChatDate`'s
  60 s periodic `TimelineView`, which is also present in the runs that idle.
- lldb dump of live Core Animation animations 3 s after presenting the alert (diag2,
  `recents-rename-live-animations.txt`): two UIKit `_UILiquidLensView.punchout.matchPosition`
  `CAMatchMoveAnimation`s with infinite duration, a glass `CASDFElementLayer` with match
  animations, and the text caret blink (`_uitcvba`, repeat forever). All are UIKit's, none
  authored by the app. I could not dump a stalled state (the first attempt's lldb
  expression failed on a symbol clash; fixed for the second run, which did not stall).
- Reading: the likely cause is UIKit's context-menu dismissal or glass lens animation
  left running when an alert is presented in the same turn as the menu action. This
  costs XCTest idle, not CPU (W4 measured about 1 ms). I found no evidence that it causes
  the founder's lag.
- Options, not taken (would need a stalled-state dump to prove first): present the rename
  alert after the menu finishes dismissing (next run loop), or present rename as a sheet
  (a design change; founder call).

## D. Mac pass screens

Not run. `baseline/run7-macpass-screens/` did not exist, but the lock was held by other
workers for most of the window (including another `cuadrao-design-mac-pass.sh screens`
run from the `cuadrao-verify` worktree), and the head kept moving. The `checks` step was
run (all 8 runners pass).

## E. Review fixes (R-790-e9195b58)

| Finding | Status | Evidence |
| --- | --- | --- |
| F1 photos in connected release Profile | Fixed `26055a28` | `testReleaseGatesHideUnfinishedRowsAndPhotos` (adds `avatar.moon`/photo absent in release, editor present in DEBUG) and new `testReleaseGatesHideAvatarEditingAndPhotos` (review host: no `release.profile.avatar` entry, display `Alex` and tab present, no `release.avatar.photo`; DEBUG keeps photos) pass. Connected surface: no signed-in UI run possible here; it reads the same rule. |
| F2 session-local Save | Fixed per founder decision in `26055a28` | Same rule; entry removed in release, no new copy. Sweep: Profile header tap (connected, review host), preview identity form picker; no other entry (no context menu, no SceneStorage, tab only selects Profile). |
| F3 noRecords | Fixed `8bd88ae6` | 25 Updates checks pass. |
| F4 / E3 Updates journey | Not fixed (see A); README corrected with a dated note | README "Verification and evidence" note and new "Review fixes" section. |
| F5 Mac pass coverage | Fixed `5130c02d` | `checks` step: all 8 runners pass. |
| F6 average denominator | Fixed `36cafb10` | 81 Home checks pass. |
| F7 release-ui argument | Fixed `69f5ebef` | Release build succeeds; binary has no preview argument strings. |
| F8 small items | Fixed `26b3e1ab` | English deletion copy test passes. |
| F8 board queue contradiction | Left, follow-up | docs |
| F8 hand-drawn Apple button | Left, follow-up | DEBUG gallery only |
| Camera glyph in release default icon | Left on purpose | Founder: keep the default icon unchanged |
| E8 invitation prominent labels | See E8 | |

### E8

`WelcomePalette.onAccent` is the existing on-accent token (`CuadraoCanvas.swift:34`), used
the same way by `RegistrationButton`, which pairs it with `WelcomePalette.disabledInk` when
disabled. `ReleaseProminentLabel` (in `ReleaseInvitationShare.swift`) applies that pair from
`isEnabled`. Applied to every `.borderedProminent` label under `ReleaseInvitationPage`'s ink:
personal "Crear invitación", "Crear enlace de grupo", gate "Continuar", share "Compartir
invitación", and the gallery's "Explorar invitaciones personales". No other restyling.
Focused runs `e8-invites` (with `testInviteFullStateAndQRSharing`, passes) and
`e8-invites-2` (new `testInvitationProminentLabelsLightAndDark`, passes). Screenshots in
`2026-10-03-w1b/`: `invitation-create-light-es.png` shows white labels on pine for
"Compartir invitación" and "Crear invitación"; `invitation-create-dark-es.png` shows the
dark on-accent ink on the light pine fill; `invitation-group-link-*.png` show the disabled
"Crear enlace de grupo" in `disabledInk`.

## Verify

- Debug build-for-testing: succeeded at each step. Release simulator build: succeeded
  (`ios/.build/w1b/release-build.log`).
- `git diff --check e9195b58..HEAD`: clean. `scripts/check_modularity_budget.py`: no violations.
- Lock-time finding for the lead: `xcodebuild test` runs `simctl diagnose` (up to 600 s)
  after any failure while still holding the Mac lock. Pass `-collect-test-diagnostics never`
  for focused runs; mine did after 22:26.

## Not done

- A1 and A2 root causes; C fix; receipt currency menu; Ana ambiguity; FinancialLoop skip;
  group repayment arithmetic; D screens.
- The temporary diagnostic file `ios/ArgusFoundationUITests/W1bDiagnosticUITests.swift`
  stays untracked (not committed).

## Head

Final pushed head: `3370ba509ef2059c75aac80ebc369a425b75996f` on `origin/codex/cuadrao-release-ui`.
Focused runs that vouch for it (all under the lock): batch1 (release gates, avatar, deletion,
invitations and photo journeys pass; Updates and Home activity fail as described), money-after
(money journey, plan exact amounts, burst typing pass; group fails at line 56), diag2 (scan
parity passes), e8-invites and e8-invites-2 (pass). Builds used separate derived-data folders
per experiment; the gallery copy commit `6bd93b85` was compiled but has no UI assertion.
