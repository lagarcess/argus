# W1h: diagnosis of the two in-suite UI failures on PR #790

Branch `codex/cuadrao-release-ui`, worktree `/Users/garces/.codex/worktrees/cuadrao-release-ui/private-alpha-next`.
Start head `4bb1696a3df3dcd72f652fc5ddcefd27e721c292`. **Final head `c2b47c661`** (three commits, pushed without force):

- `a72c3033b` test(cuadrao): press the voice entry only after the attachment tray has closed (Voice fix)
- `211b3d732` test(cuadrao): read back every money field the group journeys replace (Group guard, not a fix)
- `c2b47c661` docs(cuadrao): record the diagnosis of the two in-suite UI failures (README section + `2026-10-04-w1h/`)

No app code changed. Untracked `todo.md` and `W1bDiagnosticUITests.swift` untouched (the latter is compiled into every
build-for-testing of this tree, as before). Simulator: iPhone 18 Pro `8AFB6084-...` only. Every simulator run was
`lockf -k .../mac-sim.lock` with `-collect-test-diagnostics never`, one xcodebuild per hold. Run logs and xcresults:
`~/.claude/orchestrate/cuadrao-iphone-candidate/w1h/`.

## A. `CuadraoVoiceDesignUITests/testLockedRecordingAndCleanAttachments` line 155: TEST DEFECT, FIXED

Evidence from the artifacts. Decoded the synthesized-event records of both suite bundles (`4af8fced` s4-ios-test,
`2520da49` s4-attachments/new). The first lock press on `chat-composer-entry` landed at (201, 527.6) and (201, 509.8).
In every passing run it lands at (201, 662). 509.8 is the entry's centre with the attachment tray open. The UI
hierarchy at failure shows the tray closed and the chat idle; the recording shows nothing reacting to the press.
Predecessor in suite order: `testHoldComposerAndWaveformWithoutStartingLiveVoice`.

Mechanism (from dense recording frames). Failing pair: close tap synthesized at t 9.62, coordinate read at 9.99, tray
still fully open at 10.00, closed by 10.20. Passing alone: close tap at 9.30, read at 9.60, tray already closing. The
test resolves the press coordinate right after the close tap; XCUITest's idle wait returned before the app applied the
close (0.2 s eased animation), so the press hit empty space above the composer and no recording started.

Reproduction at 4bb1696a: Hold+Locked in one run failed 1 of 5 (r1 unloaded failed with the same y 509.8; r2 unloaded
and 3 runs under 14 `yes` processes passed). Locked alone passed 2 of 2; after an unrelated predecessor
(`testSampleCardAtLargeTextEnglish`) passed; Hold then Locked as two separate xcodebuild runs passed. So the trigger is
in-run state after Hold that slows the app's handling of the close; what that state is was not identified. CPU load did
not raise the rate.

Fix (`a72c3033b`, test only, no assertion weakened): after closing the tray wait for `Escanear` to not exist; before
every lock gesture wait until the target is hittable and its frame is unchanged between two reads 0.2 s apart (3 s
budget, fails loudly); after Descartar wait for `voice-message-status` to not exist (same hazard for the second press).

Proof: Hold+Locked passed 3 of 3 at the fix, first press at (201, 662) each time (decoded). Note: the run helper's
`seq 1 0` bug started 2 busy processes during those three runs; corrected afterwards. The Escanear wait adds about 1 s
(XCUITest polls non-existence about once a second); Locked now takes 35 to 37 s instead of 32 to 33 s.
Build-for-testing (Debug) succeeded. Not run: a full suite (rule 16); the next full suite is the real confirmation.

## B. `CuadraoGroupDesignUITests/testSharedJourneySpanish` line 48: NOT REPRODUCED, CAUSE NARROWED

Evidence from the `2520da49` suite artifacts. Hierarchy at failure: Tú 500.00, **Ana 40,300.00**, Leo/Sol/Mar 400.00,
"Hay DOP 40,000 de más.", all five members "incluido", `group-expense-save` Disabled. Events: Ana's field got six
deletes (`\x7f` x6, typing speed 60/s) then "300". Recording frames: Ana's field "400.00" -> "400.0" (t 44.0) -> "40"
(t 44.1), stays "40" until "3" arrives, then "40,300". Two of six deletes had no net effect. Save was correctly
disabled; the defect is upstream at the keystrokes.

This rules out: the removed overlay dropping a member (all included), Save enablement lag (the split was really over),
keyboard covering a field (would fail at line 45). The reviewer opinion R-790-4bb1696a.md was used; its hypothesis 1
(`CanvasMoneyValueInput` re-sync) is the right class, but by reading its re-sync writes `CanvasMoney.format` (two
decimals), which explains "40.00" or "400.00", not the plain "40" seen, unless the rewrite happened after the second
delete to "400.00" (consistent with the frames at 10 fps, but no code path found that re-syncs at "400.", where value
and raw agree). Remaining candidates: (a) a SwiftUI update rewrote the field from a stale binding mid-burst;
(b) two synthesized deletes were not delivered under load.

Tried, all passed: predecessor pair (`testSampleCardSaveImage` then the journey) twice under 14 busy processes (the first
also beside my concurrent build); the whole Group class once at 211b3d732; a throwaway probe
(`W1hSplitDiagnosticUITests`, built in separate derived data, deleted from the tree, copy in evidence) that replaced
and read back Tú's and Ana's shares 48 times, 24 under load, 0 mismatches.

Guard (`211b3d732`): the Group tests' `replace()` now waits up to 3 s for the field to hold exactly the typed amount
(commas aside), so a recurrence fails at the field with the held value instead of at Save. Group class 6 of 6 passed
with it. Next step to discriminate (a) from (b): a DEBUG-only log of each `shouldChangeCharactersIn` and each
`updateUIView` rewrite in `CanvasDecimalInput`, streamed during a full suite. Not made: app change without a
reproduction is out of the brief.

## Pending checks

- `ReleaseUIJourneyTests` as a class, at 211b3d732 content: **13 of 13 passed** (190 s).
- Mac pass auth-on welcome check (`CuadraoSignInPresentationUITests/testDefaultLaunchOffersNoAppleSignIn`, build with
  the `run_tests` auth-on loopback settings and social flags off, `TEST_RUNNER_ARGUS_TEST_AUTH_UI_ENABLED=true`):
  **passed** (14.6 s, executed, not skipped). Built with build-for-testing outside the lock, run with
  test-without-building inside it, rather than through `verify.sh test`.
- CI on `4bb1696a`: `gh pr checks 790` / check-runs API: all completed success (ci x2, backend-checks x2,
  frontend-checks x2, guest-release-gates x2, local-smoke, docs-change-gate x3, ownership-gate x2); docs-checks and
  Supabase Preview skipped. CI on the final head `c2b47c6612d6639f393c76520d902bc67255e387` (PR head confirmed):
  all pass (ci x2, backend-checks x2, frontend-checks x2, guest-release-gates x2, local-smoke, docs-change-gate x3,
  ownership-gate x2); docs-checks x2 and Supabase Preview skipped. Checked 10:47 CDT.
- `git diff --check a8c37d3a...HEAD`: clean at c2b47c661.

## Commands (representative)

- Build: `xcodebuild build-for-testing -project ArgusFoundation.xcodeproj -scheme ArgusFoundation -configuration Debug -destination 'platform=iOS Simulator,id=8AFB...' -derivedDataPath .build/DerivedData-w1h CODE_SIGNING_REQUIRED=NO` (exit 0 at 4bb1696a, a72c3033b, 211b3d732).
- Run: `lockf -k mac-sim.lock w1h/pair-under-load.sh <xctestrun> <name> <load> <Class/test>...` (xcodebuild test-without-building, `-collect-test-diagnostics never`, `-parallel-testing-enabled NO`). A `keep.xctestrun` copy with `SystemAttachmentLifetime keepAlways` was used to read event coordinates of passing runs.
- Artifacts: `xcrun xcresulttool export attachments`, then `decode.py` (plutil on synthesized-event plists) and AVFoundation frame extraction.

## Follow-ups (not done)

- Why Hold leaves in-run state that delays the app's tray close (A's trigger). Not needed for the fix.
- The `CanvasDecimalInput` keystroke log above if line 48 or the new `replace` read-back ever fires.
