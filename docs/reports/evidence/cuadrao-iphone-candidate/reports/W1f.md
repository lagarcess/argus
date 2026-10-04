# W1f: feedback Save under the keyboard, Context never-idle, Release preview argument

Branch `codex/cuadrao-release-ui`, worktree `/Users/garces/.codex/worktrees/cuadrao-release-ui/private-alpha-next`.
Start head `e694d5da249147c67ea7333b28b6204fd95bb5df`. Final head `706e118cd76d09f9684bd08aed5d34ba1cb9da1e`, pushed without force.
Simulator: iPhone 18 Pro Max `0335699A-C522-492B-A8C3-8FD3D7CAC06A` only. Every simulator run was under `lockf -k mac-sim.lock` with `-collect-test-diagnostics never`. No full suite.
Untracked `todo.md` and `W1bDiagnosticUITests.swift` untouched. No Invitations, Household or ArgusSession file touched.
Raw logs, result bundles and scripts: `~/.claude/orchestrate/cuadrao-iphone-candidate/w1f/`. Committed evidence: `docs/reports/evidence/cuadrao-release-ui/2026-10-04-w1f/`.

Commits:
- `620d6a39a` test(ios): Profile reveal helper starts its drag above the keyboard's prediction bar
- `3ed8dae0a` fix(ios): only DEBUG builds read the --cuadrao-design launch argument
- `706e118cd` docs(cuadrao): evidence and dated README note

## Problem 1: it is a test-helper defect, not an app defect

Two premises in the brief did not hold.
- The test file did change in this PR. `fd408c62c` rewrote the `reveal` helper to be keyboard-aware (`git log -S"keyboard.frame.minY"` names that commit only). The test method body is unchanged.
- The baseline pass never exercised the keyboard. The baseline `feedback-partial-bug-saved` screenshot (exported from `baseline/run1/ios-results/test-20261004T012300Z.xcresult`, copy at `w1f/base-saved.png`) shows no software keyboard on screen. The baseline log shows the old helper doing 10 drags that revealed nothing, then passing on the final `isHittable` because nothing covered Save.

No bisect was run. The cause was found directly, so a bisect would have added nothing.

Root cause. The helper takes `app.keyboards.firstMatch.frame.minY` as the top of the keyboard and starts its drag 5% of the screen height above it. The keyboard element's frame begins below the 44 pt "Typing Predictions" bar, and a drag that starts on that bar does not scroll the form.
- iPhone 18 Pro (874 pt, the candidate device `8AFB6084`): the log shows the drag at `[0.50, 0.63]`, so keyboard minY was 594 and the drag began at y 551. The bar spans 550 to 594. The drag began 1 pt inside the bar, the form never moved, Save stayed under the keyboard, and the helper's final `XCTAssertTrue(element.isHittable)` failed at line 226. The candidate screen recording frame shows it: `2026-10-04-w1f/candidate-4af8fced-pro-save-under-keyboard.png`.
- iPhone 18 Pro Max (956 pt): keyboard minY 653, bar 609 to 653, drag began at y 602, 7 pt above the bar. It passes there. That is why this lane's own focused runs passed and the candidate's did not.

Measured evidence (probe `2026-10-04-w1f/keyboard-geometry-probe.swift.txt`, output `feedback-keyboard-geometry.txt`, Pro Max):
```
keyboard-settled keyboard=(0,653,440,245) save.frame=(20,845.7,400,52) save.hittable=false
bar=(0,609,440,44)                      <- Other, label 'Typing Predictions'
drag startY=643 (keyboard.minY-10) save moved up by 0.0
drag startY=623 (keyboard.minY-30) save moved up by 0.0
drag startY=610 (keyboard.minY-43) save moved up by 0.0
drag startY=602 (keyboard.minY-51) save moved up by 250.3
drag startY=563 (keyboard.minY-90) save moved up by 84.0
after-drags save.frame=(20,511.3,400,52) save.hittable=true
```
A person can scroll the form with the keyboard up and reach Save (`save-above-keyboard-pro-max.png`). None of the suspected app changes (settings clearance, hidden tab bar, content shapes, toolbar) is involved.

Fix `620d6a39a`, helper only: `let floor = keyboard.exists ? keyboard.frame.minY - 44 : app.frame.maxY - 100`. On the Pro the drag now starts at y 506, 44 pt above the bar. On the Pro Max it starts at y 561 (log shows `[0.50, 0.59]`).

**Not proven on iPhone 18 Pro.** I was assigned the Pro Max only, and installing a build on the Pro would replace the candidate's app there. The Pro result is arithmetic from the candidate log plus the measured bar. To close it, run on `8AFB6084-8918-416E-9164-E21061306BEC`:
`-only-testing:ArgusFoundationUITests/CuadraoProfileFollowupUITests/testFeedbackPreservesKindsAndPartialDrafts` at `706e118cd`.

Also not established: why the software keyboard was hidden at baseline and visible on the candidate run. That is simulator state (the baseline screenshot has no status-bar override, the candidate has 9:41), not source.

## Problem 2: Context never-idle does not reproduce alone

`CuadraoContextUITests/testGroupContextPreservesDraftAttachmentsAndReturn` alone at `e694d5da2`: passed, 52.8 s, **0** never-idle waits.

What the existing logs show:
- Candidate full run: all 15 waits start right after `typeText` into `chat-composer` and persist across the keyboard dismiss, attach sheet, tab switch and segmented control until `group-card-trip`.
- The baseline full run had 49 waits of the same kind in four other tests (31 `testRecentsActionsAndRecovery`, 10 `testVoiceStaysAvailableAcrossSheetsAndSurfaces`, 7 `testFirstUseSavedChatAppearsInSearch`, 1 `testAppearancePersistsAcrossRelaunch`). The class predates this PR and moves between tests from run to run.
- I saw it once myself: the first feedback run at `e694d5da2` (a build-and-install run) logged 5 waits, starting after text entry with the software keyboard up, and ran 336 s. Three later runs of the same test logged none.

No cause established, no commit identified, nothing changed. An lldb watcher was armed on every later run to dump Core Animation state at the first wait; it never fired. This matches W1b Unit C (UIKit glass and caret animations, intermittent). Options: (a) accept as a simulator-side cost, since tests still pass; (b) keep a watcher armed on the next full run to capture the dump when it happens (`w1f/watch.sh`, `w1f/dump.lldb`); (c) file it as a follow-up with the three data points above.

## Launch argument: gated behind DEBUG

No script or documented flow launches a Release build with `--cuadrao-design`. `cuadrao-design-mac-pass.sh` builds Debug, UI tests run Debug, and the device preview (build 3420) uses the build setting `CUADRAO_DESIGN_PREVIEW=true`. The one Release use was an October 3 evidence screenshot (`release-design-launch-light.png`), which the new README note marks as superseded.

`3ed8dae0a`: `CuadraoDesignPreview.isActive` reads the argument only under `#if DEBUG`; Release uses `standalone` alone. Proof on the Release simulator build: `strings` count for `--cuadrao-design` is 0, and a launch with `--cuadrao-design --cuadrao-home --home-populated` produced a screenshot byte-identical (`cmp`) to a default launch.

Left as is and reported: `--design-gallery` and `--home-populated` strings remain in the Release binary (1 each). They are read only inside the canvas, which Release now reaches only through the build setting.

## Verification actually run

| Check | Result |
| --- | --- |
| Feedback test alone, before fix, `e694d5da2` (`xcodebuild test`) | passed, 336 s, 5 never-idle |
| Context test alone, `e694d5da2` | passed, 52.8 s, 0 never-idle |
| Feedback test alone with fix, run 1 | passed, 36.6 s, 0 never-idle |
| Feedback test alone with fix, run 2 | passed, 38.5 s, 0 never-idle |
| `CuadraoProfileFollowupUITests` class with fix | 6 of 6 passed, 186.5 s, 0 never-idle |
| Debug build, sources `3ed8dae0a` | BUILD SUCCEEDED |
| Release build | BUILD SUCCEEDED |
| build-for-testing | TEST BUILD SUCCEEDED |
| `cuadrao-design-mac-pass.sh checks` | `== checks: ok` |
| `git diff --check` | clean |

Caveats.
- The three fixed-helper test runs used a build that also contained the temporary probe file and the DEBUG gate. The probe was removed before the final compiles and is committed only as `.swift.txt` evidence.
- The Context test was not rerun after the commits. Neither commit touches code it reaches in a Debug build.
- The Release app is now the installed build on the Pro Max simulator (from the launch check). The next test run reinstalls Debug.
- No scratch-bisect worktree was created.
- The `deslop`, `no-comments` and `technical-writing` skill passes were skipped for time. The diff is 12 changed lines of code.
