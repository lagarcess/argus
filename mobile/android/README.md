# Argus Android foundation

Open this directory in Android Studio. This is a native Kotlin/Compose **sample
application**, package `ai.argus.foundation.sample`. It has no network permission,
backend connection, authentication, financial calculations or record storage.
Only the Light/Dark/System preference is saved locally. All other content is
explicitly illustrative. A UI registration notice is not server authorization.

## Build and test

Pinned: AGP 9.1.1, Gradle 9.3.1 (wrapper + SHA-256), Kotlin/Compose compiler
2.2.10, Compose BOM 2025.08.01, compile/target API 36, build tools 36.0.0.
Minimum Android API is 26; device acceptance currently covers API 36 only.
The verified Mac uses Studio 2026.1.4's bundled JBR 25.0.3. Gradle 9.3.1 can
run with Java 25; AGP 9.1.1's minimum Java is 17. Java bytecode targets 17.

```bash
# From the repository root; on macOS the script locates Studio's bundled JBR
# and ~/Library/Android/sdk. Elsewhere set JAVA_HOME and ANDROID_HOME.
mobile/android/scripts/verify.sh

# With a booted emulator; ANDROID_SERIAL selects one device when several run.
cd mobile/android
ANDROID_SERIAL=emulator-5580 ./gradlew :app:connectedDebugAndroidTest
"$ANDROID_HOME/platform-tools/adb" -s emulator-5580 install -r app/build/outputs/apk/debug/app-debug.apk
"$ANDROID_HOME/platform-tools/adb" -s emulator-5580 shell am start -n ai.argus.foundation.sample/ai.argus.foundation.MainActivity
```

The wrapper needs internet for its first dependency download. No keys, `.env`,
production URLs or account credentials are required. Keep local SDK paths in
ignored `local.properties`, or use `ANDROID_HOME`; never commit machine paths.
The CI workflow builds, runs JVM tests and lint. Instrumented acceptance runs
on dedicated local ARM64 emulators; CI does not claim those checks.

## Apple Silicon emulator setup

Install Android SDK Platform 36, Build Tools 36.0.0, Platform Tools, Android
Emulator and `system-images;android-36;google_apis;arm64-v8a` with Android Studio's
SDK Manager. Create Pixel 4 and Pixel 7 Pro virtual devices in Device Manager.
Use ARM64 images on Apple Silicon, not x86 images. The lane names are
`Argus_Foundation_Small` and `Argus_Foundation_Large`.

Equivalent commands after the SDK licenses have been accepted:

```bash
export JAVA_HOME='/Applications/Android Studio.app/Contents/jbr/Contents/Home'
export ANDROID_HOME="$HOME/Library/Android/sdk"
SDK_TOOLS="$ANDROID_HOME/cmdline-tools/19.0/bin"
"$SDK_TOOLS/sdkmanager" 'platforms;android-36' 'build-tools;36.0.0' 'system-images;android-36;google_apis;arm64-v8a'
"$SDK_TOOLS/avdmanager" create avd -n Argus_Foundation_Small -k 'system-images;android-36;google_apis;arm64-v8a' -d pixel_4
"$SDK_TOOLS/avdmanager" create avd -n Argus_Foundation_Large -k 'system-images;android-36;google_apis;arm64-v8a' -d pixel_7_pro
"$ANDROID_HOME/emulator/emulator" -avd Argus_Foundation_Small -port 5580 -no-snapshot -gpu swiftshader
```

Command-line tools 19.0 were used because the downloaded `latest` package at
setup time contained an x86-only native launcher. Tools 19.0 run through Java;
place them under the SDK's `cmdline-tools/19.0` so avdmanager resolves the SDK.
Its XML-version warning did not prevent creation/boot. Android Studio Device
Manager is an alternative. Do not overwrite another lane's AVD.

## Design and future integration

The first commit's [lane spec](../../docs/superpowers/specs/2026-09-28-android-phone-foundation.md)
records ownership, exact design source and exclusions. #727 at
`e29ee6f930a58d0eeca4ca49b2545a3cb63a1d43` was open/unmerged when implementation
started. Its archive owns the visual reference; this project does not import
its disposable financial logic. Fonts and logo provenance are in `licenses/`.

Navigation starts at Argus and preserves Home / Accounts / Argus / Plan / Search.
Native Back closes the top surface, then returns to Argus, then lets Android
leave the activity. Guests can explore the app and use existing finance chat
under server quotas once a real client is integrated. All ecosystem actions,
including actions requested in chat, require registration. Here, both direct and
typed sample chat actions show that boundary without dispatching any request.

The iPhone foundation lane #729 shares this reference and the same sample/API
boundaries. Each platform uses native controls and back behavior. Future API
adapters must consume server-owned identity, capabilities, quotas and artifacts;
these display fixtures are not proposed API models. #726's isolated auth proof
is evidence only and is not included in this application.

Production application identity, signing, Play enrollment, publishing, real
session lifecycle, server enforcement, domain persistence, voice and sharing
remain separate assignments. Do not distribute this development shell as a
working financial app.

See the [acceptance report](../../docs/reports/android-phone-foundation.md) for
exact device evidence, source revisions and remaining limitations.
