# Android native auth probe (unverified)

This Kotlin probe mirrors the Swift probe in `../ios/ArgusNativeAuth`. It was
written on a Mac with no Android SDK, emulator, or JDK, so it has never been
compiled or run. Treat every Android row in the report as unverified until
someone completes the steps below and commits the result.

## What it contains

- `ArgusNativeClient.kt` sends entry calls through Argus and hands the returned
  session to supabase-kt with `importSession`. It refreshes through a single
  app-owned mutex, revokes with `signOut(SignOutScope.LOCAL)`, and handles
  PKCE recovery callbacks.
- `Transport.kt` uses OkHttp with `CookieJar.NO_COOKIES`, so Argus's `sb-*`
  cookies are never stored.
- `SecureStore.kt` encrypts values with a non-exportable Android Keystore AES
  key. It stores both the Supabase session and the guest handoff.
- `GuestHandoff.kt` implements the scoped-cookie transport (unchanged Argus)
  and the header transport (the synthetic adapter).
- `AccountBoundary.kt` drops responses that arrive after sign-out or an
  account switch.
- `NativeAuthScenarioTest.kt` holds instrumented tests K1, K3, K4, K6, K7, and
  K8. They match iOS I1, I3, I4, I6, I7, and I8.

## Prerequisites

- JDK 17.
- Android SDK with platform 35, build-tools, platform-tools, and an emulator
  system image (API 35, x86_64 or arm64 to match the host).
- Android Gradle Plugin 8.7.x. The first sync may need a Gradle wrapper, which
  is not committed. Run `gradle wrapper --gradle-version 8.10.2` once.

## Run

1. Start the lane stack, API, and adapter from the repository root:

   ```bash
   bash probes/native-auth/stack/up.sh off
   ```

   ```bash
   bash probes/native-auth/run-all.sh temp/native-auth-proof/final
   ```

   `run-all.sh` leaves the API on port 57460 and the adapter on port 57461.
   The emulator reaches them at `10.0.2.2`.

2. Boot an emulator:

   ```bash
   emulator -avd <name> -no-snapshot
   ```

3. Run the instrumented tests. Pass the local stack's public keys from
   `supabase status` as instrumentation arguments:

   ```bash
   cd probes/native-auth/android && ./gradlew :argus-native-auth:connectedAndroidTest \
     -Pandroid.testInstrumentationRunnerArguments.anonKey="$ANON_KEY" \
     -Pandroid.testInstrumentationRunnerArguments.serviceKey="$SERVICE_ROLE_KEY"
   ```

4. Collect the `NATIVE_PROBE_RESULT` lines from `adb logcat` or the Gradle test
   report. Commit them under
   `docs/reports/evidence/native-auth-session-proof/android-emulator.json`.

## Checks this probe cannot make yet

- Whether supabase-kt 3.8 single-flights refresh on its own. The probe adds its
  own mutex, so K3 passes either way. Check the SDK source before removing the
  mutex.
- Whether supabase-kt's `importSession` accepts the GoTrue session JSON that
  Argus returns without extra fields.
- Turnstile in an Android `WebView`, and delivery of the
  `argusnativeproof://auth-callback` intent to an Activity. Both need an app
  module, which this library-only probe does not include.
- Android App Links. They need a signing certificate SHA-256 and a hosted
  `assetlinks.json`.
