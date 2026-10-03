# Issue #784 Cuadrao design graft: Mac pass checklist

This is the checklist for the Mac pass over the four-PR graft of design checkpoint
`codex/cuadrao-design-scan-recents` @ `2558f866`. Every PR in the series was written on a
Linux box without Xcode. This pass is the first time the series builds, runs in a simulator
and is compared against integration before the graft. Tracking issue: #784.

| PR | Scope | State |
| --- | --- | --- |
| #783 | Shared foundation | Landed as `5dd2e36d` |
| #785 | Plans, groups, receipts, chat and voice | Landed as `900178b3` |
| #786 | Home, Search, Updates, Profile, Settings | Landed as `0ea81a20` |
| PR 4 | Design tests, launch arguments, this checklist | Open against `codex/private-alpha-next` |

The baseline is `2185aefe`, integration just before #783.

## Before you start

- Xcode 27 with an iOS 27 iPhone simulator. `CuadraoOrderedCollection` uses the iOS 27
  swipe and reorder APIs, so older Xcode releases will not build it.
- Note the simulator UDID: `xcrun simctl list devices available`.
- Two receipt journeys import a photo
  (`CuadraoReceiptUITests.testPhotoImportKeepsOriginalWithoutInventedItems`,
  `testGroupPhotoImportInheritsFixedCurrency`). Seed the simulator with one fictional
  receipt photo first: `xcrun simctl addmedia <UDID> <photo>`.
- Optional: `brew install imagemagick` to count differing pixels between screenshots.

## Run

From the repository root, on the PR 4 branch:

```bash
SIMULATOR_ID=<UDID> ios/scripts/cuadrao-design-mac-pass.sh all
```

The steps can also run separately as `checks`, `tests` or `screens`. Output goes to
`ios/.build/mac-pass/<UTC stamp>/`, which git ignores. The
[script](../../../../ios/scripts/cuadrao-design-mac-pass.sh) only builds, runs tests and
takes screenshots. It doesn't sign, upload or call a backend.

### 1. Preview state checks (`checks`)

The script runs every `ios/DesignPreviewTests/run_*.py` with `xcrun swiftc`. On the box,
`run_linux.py` already ran the same checks with Swift 6.3.3 for Linux. These are the
counts the Mac run should match:

| Runner | Expected |
| --- | --- |
| `run_plan_preview.py` | Passed 58 Plan preview checks |
| `run_group_preview.py` | Passed 50 group preview checks |
| `run_home_balance.py` | Passed 78 Home balance projection checks |
| `run_receipt_preview.py` | Receipt preview checks passed: 44 |
| `run_avatar_crop.py` | Avatar crop checks passed: 213 |
| `run_temporary_chat.py` | 10 `PASS:` lines, Spanish and English |

### 2. Design UI tests (`tests`)

The script runs `CuadraoHomeChartUITests` and the 13 design UI test classes through
`ios/scripts/verify.sh test`. It then exports their screenshot attachments to
`ui-attachments/`. Every design launch now passes
`--cuadrao-design --cuadrao-home --home-populated` (`CuadraoPreviewLaunch.arguments`),
which is what a standalone `CUADRAO_DESIGN_PREVIEW = true` build implied on the design
branch. Without those arguments the tests open the Connected app.

These tests are expected to skip:

- `CuadraoProfileFollowupUITests.testPhotoPickerSaveCancelAndRemove` and
  `testPhotoCropCancelPanZoomAndReedit`. The first release hides the personal-photo
  option (`CuadraoFirstRelease.showsPersonalPhoto = false`).
- `CuadraoVoiceDesignUITests.testVoiceChoiceAndProposalHandoff`. Voice selection needs
  `--cuadrao-voice-selection` and the sample clips, which stay out while their licensing
  is unsettled. `testVoiceProposalHandoffWithoutVoiceSelection` covers the rest of that
  journey and checks that no picker is offered.

Location, camera and photo-save prompts come from the simulator. The permission journeys
answer them through Springboard.

### 3. Before/after screenshots (`screens`)

The script builds `BASELINE` (default `2185aefe`) in a temporary worktree, then this tree.
Each build gets a clean install and a fixed status bar. It takes these screenshots in
`screens/`:

| Screenshot | Launch arguments | Expected difference from baseline |
| --- | --- | --- |
| `before/after-default-light` | none | None. Connected keeps its fixed tokens. |
| `before/after-default-dark` | none | None. |
| `before/after-design-light` | `--cuadrao-design` | Welcome only. Separator and border use the system separator inside the preview. |
| `before/after-design-dark` | `--cuadrao-design` | The baseline forced light. After, the preview's dark tokens apply. |
| `after-design-home-light/dark` | `--cuadrao-design --cuadrao-home --home-populated` | New in #786 |
| `after-design-gallery-light/dark` | `--cuadrao-design --design-gallery` | New in #786 |

`compare.txt` lists each before/after pair. Any difference in a `default` pair is a
regression in the live app.

## Manual checks

The automation doesn't cover these. Record each result in #784.

1. **Connected, signed in, against the baseline.** Check Priya's shared-code value swaps
   from #783: `WelcomePalette.pine`/`sage`/`separator`, the Registration heading, button
   and field, the navigation bar's glass tint and the Home section font.
2. **Release gate for the permission keys.** Camera (receipt scan), location (receipt
   place) and photo-add (save the sample group card) are requested only inside the design
   preview. Before any TestFlight or App Store build, those requests must be reachable in
   the shipped app, or `NSCameraUsageDescription`, `NSLocationWhenInUseUsageDescription`
   and `NSPhotoLibraryAddUsageDescription` come out. The photo-add strings are marked
   `REWORD` for when group cards are real.
3. **First-release presentation (#787).** Profile shows no Personalization, Security,
   Shared conversations, Removed activity, Memory, Usage, More options or photo option.
   Search has no Memory perspective, through the same `CuadraoFirstRelease.shows(.memory)`
   gate. Notifications has no "Por correo". The preview sign-up and sign-in screens show no Apple
   or Google button, and password-recovery help doesn't mention Apple.
4. **Chart truth (founder decision, Oct 2).** A month with confirmed coverage and no spending
   is a known zero. It shows "0.00" and "Sin gastos", and a comparison against it is an amount
   difference, never a percent. Only missing coverage shows "Sin datos" and "—". First use keeps
   "Tu historia empieza aquí". `CuadraoHomeChartUITests.testSpendingEmptyAndUnavailable` and
   `testComparisonAgainstCoveredZeroMonth` cover this (`--insights-empty-month`,
   `--insights-empty-previous-month`, `--insights-no-coverage`).
5. **Physical device (optional).** Scan, save for later and reopen a receipt. The design
   branch's founder check covered this on build 3419. This graft hasn't been on a device.

## Sign-off

Comment on #784 with the PR 4 head SHA, Xcode and simulator versions, the check counts,
UI test pass/skip/fail counts with failing test names, `compare.txt`, and the manual
check results. Attach or commit the screenshots you want to keep next to this README.

The design branch's own verification for the checkpoint is
[continuity-2026-10-02 at `2558f866`](https://github.com/lagarcess/argus/blob/2558f86666d2c9a0fb2336225a02aed4f18077b2/docs/reports/evidence/cuadrao-native-design/continuity-2026-10-02/README.md).
It is the founder's evidence for the design branch, not for integration. This checklist
doesn't copy it.
