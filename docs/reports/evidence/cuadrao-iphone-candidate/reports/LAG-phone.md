# LAG-phone: measured performance on the iPhone 15 (part 1, unattended)

Worker: lag. Date: October 4. Branch `claude/cuadrao-lag-fixes`, base `329fd00d`, head **`20f31941b`** (pushed, no force, no PR).
Status: one demonstrated bottleneck fixed and re-measured. Idle Home is healthy. Part 2 (interactions) waits for Lucas; see `LAG-needs-founder.md`.

## Device and build

- iPhone 15 "Sr.Garces i15" (iPhone15,4), iOS 27.0.1 (24A446), 60 Hz, 00008120-001428C90E04201E. Unlocked and connected for every step. No trust or Developer Mode prompt was needed.
- Release configuration, `-sdk iphoneos`, xcconfig `baseline/device-build/device-preview.xcconfig`, `INFOPLIST_FILE=candidate-04084692/device/device-Info.plist`, derived data `/private/tmp/claude-501/cuadrao-lag-dd/release`. Bundle `local.cuadrao.design.47R3855RTJ`, display name "Cuadrao Preview", `CUADRAO_DESIGN_PREVIEW=true`, `ARGUS_AUTH_ENABLED=false`. `codesign --verify --strict` passes.
- Release preview opens straight into the populated Home with sample data (`CuadraoDesignPreview.standalone`), so every number below is Release, not Debug.
- Build **3424** = `329fd00d` unchanged (baseline). Build **3425** = the same tree plus the fix (built from the working tree before the commit; the Swift content equals `20f31941b`). 3425 is what is on the phone now. Copies with dSYMs: `lag-phone/build-3424/`, `lag-phone/build-3425/`.
- All builds, installs and recordings ran under `lockf -k mac-sim.lock`, one hold per step.

## Method

- `lag-phone/tools/part1.sh <out dir>`: 5 cold launches with the App Launch template (10 s each), then 40 s recordings launched by xctrace with Time Profiler, Animation Hitches, Activity Monitor and SwiftUI. Nobody touched the phone. Idle numbers read seconds 10 to 40.
- `lag-phone/tools/xt.py`: reads `xctrace export` tables (`lifecycle`, `tp`, `hitches`, `rows`). `lag-phone/tools/build-install.sh <build number>`: signed Release build plus install.
- Attach does not work on this phone: `--attach` by name or pid answers "Cannot find process" although `devicectl` lists the process and the build has `get-task-allow`. Every recording therefore uses `--launch`.
- The App Launch template samples every 5 ms with 1 ms weights (xctrace warns about it), so CPU totals come from the 1 ms Time Profiler trace, and launch phases from the App Launch life-cycle table.
- Power Profiler recorded but failed to save (exit 70, no trace). Energy at idle is not measured; idle CPU and display swaps stand in for it.

## Measurements

Traces: `lag-phone/baseline-3424/` and `lag-phone/fix1-3425/` (`launch-1..5.trace`, `idle-tp.trace`, `idle-hitches.trace`, `idle-activity.trace`, `idle-swiftui.trace`, plus `*.txt` summaries).

| Measurement | Baseline 3424 | Fix 3425 |
| --- | --- | --- |
| Initial Frame Rendering, 5 cold launches | 1.12, 1.09, 1.09, 1.09, 1.09 s | 209, 192, 192, 191, 191 ms |
| Launch phases before first frame (system init + UIKit init + scene), typical | about 120 ms | about 120 ms |
| Main thread CPU, first 3 s | 1509 ms | 385 ms |
| Process CPU, first 3 s | 1744 ms | 692 ms |
| `CanvasBalanceHistory.points` inclusive, first 3 s | 1177 ms (78% of main thread) | 26 ms |
| Launch hitch | 1133 ms ("21 offscreen passes") | 250 ms |
| Second hitch at 2.98 s | 16.6 ms (same chart code) | none |
| Hang at launch | 342 ms microhang | 35 ms potential interaction delay |
| Hitch time ratio, whole 40 s | 28.1 ms/s | 6.1 ms/s |
| SwiftUI: `CuadraoHomeBalanceChart.body` | 11 passes, 571 ms | 11 passes, 29 ms |
| SwiftUI: chart content collection | 10 passes, 393 ms | below the top 8 |
| SwiftUI: range button rows | 60 passes, 258 ms | below the top 8 |
| Idle Home, process CPU, seconds 10 to 40 | 5 ms | 1 ms |
| Idle Home, main thread CPU, seconds 10 to 40 | 1 ms | 0 ms |
| Idle Home, display surface swaps per second from second 4 | 0 (one single swap at second 36) | 0 |
| Idle Home, SwiftUI updates after second 10 | 0 | 0 |
| Memory footprint at idle (41 s) | 35.7 MiB, 3 threads | 35.6 MiB, 4 threads |

Idle Home is truly idle on the device. No TimelineView, running animation or glass recomposition shows up: zero commits, zero view updates and about 0.01% CPU. The simulator's never-idle waits do not reproduce as work on the phone.

## Bottleneck 1 (fixed): the Home balance chart rebuilt its history hundreds of times per body pass

Main-thread stack of the 1133 ms launch hitch (`baseline-3424/idle-hitches.summary.txt`):

```
CA::Transaction::commit > CA::Layer::layout_and_display_if_needed > -[UIView layoutSublayersOfLayer:]
 > _UIHostingView.layoutSubviews > ViewGraphRootValueUpdater.render > AG::Graph::UpdateStack::update
 > CuadraoHomeBalanceChart.body.getter                         437 ms
   > CuadraoHomeBalanceChart.effectiveRange / points / bounds / shown / xDomain getters
     > CanvasBalanceHistory.points(accounts:observations:now:)  928 ms of the 1151 ms busy
       > NSDecimal._divide(by:) and friends (Foundation self time 1059 ms in the first 3 s)
```

`history`, `points`, `bounds`, `shown`, `selected`, `xDomain`, `availableRanges` and `effectiveRange` were computed properties and each one rebuilt the full history. `chartBase` read `bounds` once per plotted point and each range button read `effectiveRange` twice. One body pass cost 52 ms, one chart content pass 39 ms, each range button 4.3 ms.

Fix, commit `20f31941b` (`ios/ArgusFoundation/Cuadrao/CuadraoHomeBalanceChart.swift`): the body derives one private `Reading` from one history, and the marks, labels and buttons read it. Each derived value keeps its original expression, the view tree and modifiers are unchanged, so the output is the same. One history build now costs about 2.4 ms, once per body pass.

This is the same code that runs on every chart scrub frame, range tap and period swipe (each changes `selectedDate`, `compactRange` or `periodOffset` and re-evaluates the body). Before the fix that is roughly 90 to 130 ms of main-thread work per update against a 16.7 ms frame. That prediction is not measured yet; part 2 measures it.

Checks. Release device build succeeded and the fixed build ran on the phone for all recordings. No unit or host check was added: the cost was a view calling a pure function too often, and the pure function is unchanged and already covered by `DesignPreviewTests/HomeBalanceChecks.swift`. **Not run:** simulator UI tests. I have no assigned simulator; the lead should run `-only-testing:ArgusFoundationUITests/CuadraoHomeChartUITests` at `20f31941b`. **Not done:** a pixel comparison on the phone, which needs a person or a screenshot path I do not have.

Evidence in the branch: `docs/reports/evidence/cuadrao-lag/phone-launch-home-chart.md`.

## Not fixed, with measured cost

| Item | Measured cost | Why left |
| --- | --- | --- |
| Remaining launch hitch | 250 ms first frame, 263 ms main thread. Spread over first layout in SwiftUI and UIKit, Swift metadata and Objective-C method lookup (libswiftCore 68 ms, libobjc 67 ms self). No app frame above 30 ms | No single owner in the trace. First layout of a five-tab canvas |
| "21 offscreen passes" on the first frame | Reported by the hitch narrative on the baseline; the render server share is not separable from the 1.13 s app update in this trace | Shadows, masks or materials. This is the Liquid Glass and visual polish category. Deferred by the brief; measure under interaction in part 2 before deciding anything |
| Chart body evaluated 11 times at launch | 29 ms total after the fix | Too small to justify a change |
| One history build per body pass | about 2.4 ms | Fits a frame. Revisit only if part 2 shows scrubbing hitches |
| `CuadraoHomeInsights.history` and `CanvasBalancePeriod.init` call the same history builder | not on the launch or idle path, so no number yet | Needs the expanded chart in part 2 |

## Decision log

1. Profile Release, not Debug. Checked `CuadraoDesignPreview.standalone`: the build setting alone opens the populated Home in Release. Confirmed on the phone by the chart code appearing in the launch trace.
2. Attach failed twice (name, then pid). Did not loop. Switched all idle recordings to `--launch` and read a later time window.
3. Baseline before any change: 5 launches, 4 idle recordings on 3424.
4. Launch trace showed 78% of main-thread time in one function reached through the chart's computed properties. Read the source, confirmed the per-point and per-button recomputation, and the SwiftUI instrument gave the per-pass costs.
5. Chose deriving once per body pass over memoising inside `CanvasBalanceHistory.points` (inputs are not hashable and `now` changes per call) and over hoisting a few locals (would still leave about 30 history builds per pass).
6. One change, rebuilt as 3425, re-ran the same script. Numbers in the table. Committed and pushed.
7. After the fix, launch has no single app hotspot and idle is at rest, so no further fix was invented. Stopped part 1 here.
8. The first after-run was stretched past the tool's background limit by waiting on the shared lock; its SwiftUI recording was cut off and re-recorded separately (20 s instead of 30 s).
9. Power Profiler failed to save once; not retried.

## What still needs the founder

`reports/LAG-needs-founder.md` has the 80 s script and the single command (`lag-phone/tools/part2.sh run-1`). It records Animation Hitches plus the time profile for 90 s and prints hitch count, hitch time ratio, hangs and the main-thread stack at the worst hitches. The phone now has build 3425. The profile expires October 7, 19:57 CDT.
