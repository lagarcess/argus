# iPhone chart validation evidence

This folder contains simulator evidence for the standalone chart prototype, not
physical-iPhone or production certification. The exact committed capture head is
in `captured-head.txt`; `source-identity.json` records every iOS source and shared
fixture SHA-256. Evidence-only follow-up commits preserve those tested inputs.

Final capture: **27a0b4e756057dadfc9c3ab6f1b4733fca683293**. Build and all six
UI tests passed, production-model checks passed, and every captured source/fixture
hash was revalidated equal. System Light/Dark screenshots were visually inspected.
Earlier local captures are superseded by this evidence.

## Environment and isolation

- Host: Mac17,9, Apple M5 Pro, 48 GiB RAM, macOS 27.0 (26A428).
  Shared development host, not an isolated physical-device benchmark.
- Xcode 27.0 (27A266a); Apple Swift 6.4; Swift 5 language mode; iOS 27 SDK.
- Swift Charts is the Apple system framework (no separate package version).
- iPhone 17e simulator, iOS 26.5 (23F77), 1170×2532 screenshot pixels.
- Dedicated instance `Argus Chart Validation 17e`, UDID
  `AAC78F82-61C2-4E51-A14C-4F341CD19A79`.
- Native-auth's running simulator and all shared devices/resources were untouched.
- iOS 17.0 configured deployment floor compiles. No local iOS 17 runtime exists;
  that minimum is **unverified at runtime**. No physical-device claim.

## Repeat and inspect

From repository root, with your owned device UDID and a new result bundle path:

```sh
prototypes/chart-validation/ios/capture-evidence.sh \
  AAC78F82-61C2-4E51-A14C-4F341CD19A79 \
  /tmp/argus-chart-ios-final.xcresult
```

The script runs build/UI tests, exports screenshots/test summary/performance,
runs production-model checks, launches System appearance, changes this simulator's
OS appearance Light→Dark while the app remains running, captures both, restores
Light, and records source identity. It leaves the dedicated simulator running for
inspection; shut down **only that instance** after proof:

```sh
xcrun simctl shutdown AAC78F82-61C2-4E51-A14C-4F341CD19A79
```

`attachments.json` maps exported screenshots to XCTest identifiers, device and
timestamps. `test-summary.json` is the machine-readable outcome and
`xcodebuild-test.log` is the build/test receipt. `model-checks.txt` records endpoint,
nearest/tie, explicit-null segment, missing-row selection and lifecycle checks.

## What the tests prove

- `testReadoutEndpointsMissingResetAndLocale`: shared-fixture first point, explicit
  missing row, last endpoint clamp, reset, English→es-419, Dark appearance.
- `testHorizontalReleaseAndVerticalScroll`: real injected horizontal drag updates
  readout; release retains it. A chart-originated vertical drag moves the chart's
  screen Y by more than 40pt **before** any other scroll action, keeping selection.
- `testNativeRecognizerCancellationRestoresSelection`: a real injected horizontal
  drag starts; the standalone test hook disables the active recognizer, causing
  UIKit to emit `.cancelled`. The prior selected date is restored. This proves
  native callback handling, not every possible OS interruption source.
- `testScenarioResetsSelection`: changing scenario clears selection and empty
  scenario disables point navigation.
- `testEmptySingleAndContribution`: empty state, single negative point with clamped
  navigation, and authored recurring-contribution readout in Spanish/Dark.
- `testLongSeriesInteractionPerformance`: five real automated scrubs over the
  2,000-row fixture, including resulting selection checks and screenshot.
- `system-light.png` and `system-dark.png`: app set to System responds to OS
  appearance change without relaunching between the two captures.

Accessible alternative proof is the visible date/value readout and labeled native
Previous/Next/Reset buttons exercised by accessibility-driven XCTest. No precision
dragging is required. This is not a full physical-device VoiceOver audit.

## Performance interpretation

`performance.json` contains every raw sample, including XCTest clock, application
CPU and physical memory measurements. An iOS26+ UI hitch metric was requested,
but this simulator exported no hitch samples; **unavailable is not zero hitches**. Clock includes touch injection
and automation overhead. CPU is application CPU time, memory is process footprint,
and no frame/hitch claim can be made from the absent hitch export. They are
not interchangeable with chart-only latency or physical-device FPS. There is no
accepted regression baseline or device FPS threshold in this prototype.

For five long-series scrubs, mean automated interaction clock was **1.280 s**,
mean application CPU time **1.009 s**, and mean peak physical memory **51,297 kB**.
Individual clock samples ranged **1.174–1.369 s**. These include automation and
injected drag duration; no chart-only latency or frame-rate conclusion follows.

## Recommendation and limits

**Adopt Swift Charts as the iPhone rendering direction for further bounded work.**
The framework builds with the actual native toolchain and renders shared facts,
explicit gaps, actual/projection styles and accessible selection with the required
native gesture coexistence. Keep the explicit selection lifecycle and shared data
contract; do not spread charts into production screens based on this prototype.

Remaining limits: unavailable simulator hitch/FPS measurements, iOS17 runtime,
physical-device performance/VoiceOver, broader
Dynamic Type/device sizes and exhaustive OS interruption scenarios were not
certified. Xcode27's documented conditional ChartContent issue for older deployment
targets is avoided by using ForEach mark arrays; no unsupported workaround or
alternative library was silently substituted.

Cleanup verified in `cleanup.txt`: the dedicated simulator is **Shutdown**. Its app/test
bundles remain inside it, alongside disposable `/tmp/argus-chart-ios*` build/result exports.
No provider keys, production accounts, hosted writes or shared resource restarts.
