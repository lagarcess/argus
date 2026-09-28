# Argus iPhone foundation

An offline SwiftUI foundation with Home, Accounts, Argus, Plan and Search in
the approved order. It runs as **Argus Sample**. Navigation, local search and
Light / Dark / System appearance work. Financial figures are immutable display
fixtures. There is no working backend, authentication, financial persistence,
calculation, voice, sharing, monitoring or provider integration.

## Run in Simulator

1. Install Xcode with an iOS Simulator runtime through **Xcode > Settings >
   Components**. Select that Xcode in **Settings > Locations > Command Line Tools**.
   This project requires Xcode 16 or newer (synchronized source groups) and targets
   iOS 17 or newer. Acceptance used Xcode 27.0 / iOS 27.0; the deployment floor is
   not a claim that every older runtime was tested.
2. Open `ArgusFoundation.xcodeproj`, select the shared **ArgusFoundation** scheme,
   select an iPhone simulator and press Run. No account or development team needed.
3. For command-line verification from repository root:

   ```bash
   xcrun simctl list devices available
   SIMULATOR_ID=<iPhone-UDID> ios/scripts/verify.sh build
   SIMULATOR_ID=<iPhone-UDID> ios/scripts/verify.sh test
   ```

The test action also builds. Results and logs go to ignored `ios/.build/results/`;
set `RESULT_DIR` to choose another output directory. Extra Xcode options may
follow the action, for example `-only-testing:ArgusFoundationUITests/FoundationUITests/testNavigationAndHeaderReturn`.
Tests run serially on the selected simulator and change only this sample app's
appearance. They do not contact Argus or spend provider tokens.

To install and launch after a command-line build (substitute your simulator ID):

```bash
xcrun simctl boot <iPhone-UDID> # omit if already booted
xcrun simctl install <iPhone-UDID> ios/.build/DerivedData/Build/Products/Debug-iphonesimulator/ArgusFoundation.app
xcrun simctl launch <iPhone-UDID> local.argus.foundation
```

Use a separate simulator when other work is active. The checked-in configuration
supports Simulator only, device family 1 (iPhone), no Catalyst or iPad target.
Signing is disabled. Production bundle identity, team, provisioning, physical
device distribution and release OS support remain unresolved.

## Local configuration and future owners

`Config/Development.xcconfig` owns development settings. Its
`local.argus.foundation` bundle identifier is a replaceable simulator placeholder.
Optional `Config/Local.xcconfig` is ignored; copy the neighboring example to
give a second installation a different local identity. Changing identity creates
a separate preference container. Do not place credentials in either file.

No endpoint configuration or network client exists yet because this lane is
sample-only. Future service configuration needs an explicit consuming contract;
adding an unused URL would imply a connection that does not exist.

[#726](https://github.com/lagarcess/argus/pull/726) owns auth/session evidence,
not this app. Before adding authentication, coordinate SDK/session ownership,
server session isolation, storage, handoff/cookies, CAPTCHA and callback/recovery
behavior with that lane. Do not copy its probes or synthetic adapter into the
app. The foundation deliberately has no auth, ledger or provider SDK dependencies.
Financial rules and calculations remain backend responsibilities.

## Reference and shared owners

The committed [lane spec](../docs/superpowers/specs/2026-09-28-ios-foundation.md)
defines ownership and acceptance. The experience reference is
[PR #727 at a1c294319a2c047623b9bbe5bedd36155d2e931d](https://github.com/lagarcess/argus/tree/a1c294319a2c047623b9bbe5bedd36155d2e931d/docs/reports/evidence/mobile-design-lock-2026-09-28),
archive `mobile-2026-09-28`, SHA-256
`c55e565aa142e38eec61b570510af1c4c2cb9629c24f3ce2d01387639f0ea0e6`.
The latest inspected reference is `d7faac770369242436a5e108bb557ba0bae893d3`:
one review correction removes the contradictory universal-pill instruction;
the archive is unchanged. That PR was open and in review at lane start. Its canonical documentation was
neither copied nor merged into this lane. The archive's finance JavaScript is
not used. The locked template owns interactions; this lane adds native shell
behavior and explicitly labeled sample destinations within its assigned scope.

Shared semantic tokens and controls live in `ArgusFoundation/`. The shell owns
destination selection; individual views own transient presentation state.
Appearance is the only app preference persisted by this foundation, using
UserDefaults through SwiftUI AppStorage. Removing the app resets it. System
appearance follows the OS, while Light and Dark override it. Appearance does
not synchronize with a server profile. Static copy is localized for English and
Latin American Spanish using native resources and the device language.

Bundled fonts derive from the existing `web/app/fonts/` WOFF2 sources under their
included SIL Open Font licenses. Static Inter 400/500 and Space Grotesk 500 TTFs
are committed so app builds require no download/conversion. To regenerate them
after an intentional canonical font change, create a temporary Python environment,
install `fonttools==4.65.0` and `brotli==1.2.0`, and run
`python ios/scripts/derive_fonts.py`. The Argus mark derives from the existing
angular A geometry; no replacement logo is designed here.

## Acceptance and evidence

The UI tests cover tab order/selection/targets, header sheets and return, sample
disclosure, all appearance choices across process relaunch, retained search state,
keyboard, Spanish, enlarged Dynamic Type and accessibility labels/traits/targets.
Screenshots attach to the `.xcresult`. Manual simulator checks additionally inspect
actual theme resolution, two iPhone sizes, safe areas and layout.

Durable acceptance captures and their exact source/head boundaries live in
[`docs/reports/evidence/ios-foundation/`](../docs/reports/evidence/ios-foundation/).
Simulator accessibility checks are a basic foundation check; they do not claim
physical-device VoiceOver, production financial journeys or backend acceptance.
