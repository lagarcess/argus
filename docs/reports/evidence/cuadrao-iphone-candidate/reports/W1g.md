# W1g: split member row overlay removed (PR #790)

Branch `codex/cuadrao-release-ui`, worktree `/Users/garces/.codex/worktrees/cuadrao-release-ui/private-alpha-next`.
Start head `9493ea575045e4e6be3b273abecdee244245c143`. Final head `4bb1696a3df3dcd72f652fc5ddcefd27e721c292`, pushed fast-forward (`9493ea575..4bb1696a3`), no force.
Untracked `todo.md` and `ios/ArgusFoundationUITests/W1bDiagnosticUITests.swift` left alone. Simulator iPhone 18 Pro `8AFB6084-8918-416E-9164-E21061306BEC` only.

## Change

- `ios/ArgusFoundation/Cuadrao/Planning/CuadraoGroupExpenseEditor.swift` restored from `cc68b341` (`git restore --source=cc68b341`). This removes the Spacer overlay, the one-caller `toggle` helper and the label `contentShape` added by 567f59819.
- Row diff against `cc68b341`: **empty** (`git diff cc68b341 HEAD -- <file> | wc -l` gives 0). The file is identical to `cc68b341`. That row matches integration `a8c37d3a`.
- I did not keep a label `contentShape`. The checker counts any statement with `contentShape` as shaped and fails on stale review entries, so a shaped label could not also carry the review entry the brief asked for. The byte-identical revert gives exactly the integration behavior.
- `ios/DesignPreviewTests/tap_targets_reviewed.txt` gains `874c103f38a3  ...CuadraoGroupExpenseEditor.swift: split member toggle, deliberately label-only and not hittable across the row: it sits beside the amount and share fields, so a near-miss must not change who is in the split; widening it is a design decision`. `run_tap_targets.py` is unchanged.
- The evidence README adds the dated section "Correction: split member row tap area, October 4, 2026". It says the W1e "32 pt" claim was wrong on iOS (16 pt measured) and that the overlay was removed. Nothing was deleted. New evidence is in `docs/reports/evidence/cuadrao-release-ui/2026-10-04-w1g/`.
- Commit `4bb1696a3` is titled "revert(ios): split member row toggles only on its drawn label again".

## Probe (testSplitBoundaryProbe, adapted)

The probe started from `candidate-2520da49/s5-tapproof/ZZTapProofUITests.v2.swift`, copied in as untracked `ios/ArgusFoundationUITests/ZZSplitRowProbeUITests.swift`. It runs both split modes. After the runs I deleted it and confirmed with `git status` before the final build and runs. Committed copy: `2026-10-04-w1g/split-row-boundary-probe.swift.txt`, output `split-row-boundary-probe.txt`.

- **Run 1** (exit 65) asserted that no tap anywhere in the gap toggles. It failed only on taps 2, 6 and 12 pt past the label's right edge (label maxX 133.3), in both modes. Every tap 4 to 44 pt before the field did not toggle. Label taps at dx 0.1, 0.5 and 0.9 toggled.
- **Run 2** (exit 0, passed in 134.9 s) mapped the edge. Taps at label edge +2 to +20 pt toggle and taps at +22 pt and beyond do not, in both modes. I read this as the system touch tolerance around the button's drawn label, not app code, because the source is byte-identical to integration. The assertion was narrowed to "no toggle within 44 pt of the money field", which is the money-safety property, plus "label taps toggle". It held.
  - Equal mode: amount at x 306. Closest toggling tap x 153.3, which is 152.7 pt before the amount.
  - Exact mode: share field at x 238. Closest toggling tap x 153.3, which is 84.7 pt before the field. The overlay had toggled down to 16 pt before.
- The brief expected that no gap tap toggles. Read strictly, that does not hold for the first 20 pt past the label. That band comes from the system, matches integration, and sits more than 80 pt from any money field.

## Focused runs

Each run used `lockf -k ~/.claude/orchestrate/cuadrao-iphone-candidate/mac-sim.lock xcodebuild test-without-building -xctestrun ios/.build/DerivedData/Build/Products/ArgusFoundation_iphonesimulator27.0-arm64.xctestrun -destination "platform=iOS Simulator,id=8AFB6084-..." -only-testing:<test> -collect-test-diagnostics never -resultBundlePath ~/.claude/orchestrate/cuadrao-iphone-candidate/w1g/<name>.xcresult`. The xctestrun was rebuilt after the probe was deleted.

| Run | Result |
|---|---|
| `CuadraoGroupDesignUITests/testSharedJourneySpanish` #1 | passed, 62.4 s |
| `CuadraoGroupDesignUITests/testSharedJourneySpanish` #2 | passed, 62.5 s |
| `CuadraoGroupDesignUITests/testSharedJourneySpanish` #3 | passed, 61.7 s |
| `CuadraoReceiptUITests/testExpenseEditsSurviveReceiptCapture` | passed, 43.7 s |

On the earlier failure at line 48, a link to the row is possible but not proven. The test's `reveal` calls `app.swipeUp()`, which starts at the screen centre. On an exact-split row that point lies between the label and the share field (x 133 to 238), where the removed overlay took taps. If a swipe under load registered as a tap, it would drop a member and leave Save disabled. Three passes in a row on the reverted row do not reproduce contention, so the failure stays unexplained.

## Compiles and checks (no lock, plain compiles)

- `xcodebuild build -project ios/ArgusFoundation.xcodeproj -scheme ArgusFoundation -configuration Debug -destination ... -derivedDataPath ios/.build/DerivedData CODE_SIGNING_REQUIRED=NO` gave BUILD SUCCEEDED.
- The same command with `-configuration Release` gave BUILD SUCCEEDED.
- `xcodebuild build-for-testing` (Debug) gave TEST BUILD SUCCEEDED. It ran three times: with the probe twice, then without it.
- `ios/scripts/cuadrao-design-mac-pass.sh checks` gave `checks: ok`. Tap targets: 127 statements, 44 without a shape, 44 reviewed, 0 unreviewed, 0 stale.
- `git diff --check a8c37d3a...HEAD` is clean at `4bb1696a3`.

Raw logs and xcresults are in `~/.claude/orchestrate/cuadrao-iphone-candidate/w1g/`.

## Not done / follow-ups

- No full UI suite was run (standing order 16). One more in-suite observation of `testSharedJourneySpanish` at the next candidate would settle the line 48 question.
- A widened member row that stays safe beside money fields is a design decision. It is not attempted here.
