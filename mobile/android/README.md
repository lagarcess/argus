# Argus Android foundation

Open this directory in Android Studio. This is a native Kotlin/Compose **sample
application**, package `ai.argus.foundation.sample`. An explicitly configured
local debug build connects registered Accounts to the existing financial API.
Other financial destinations remain illustrative. Registered authentication is
disabled by default and in release builds.
The Light/Dark/System preference uses local app storage. The unsent sample
draft uses Android saved UI state to survive activity recreation. Other content is
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
./gradlew :app:assembleDebug :app:assembleDebugAndroidTest
ANDROID_SERIAL=emulator-5580 scripts/device-test.sh /tmp/argus-android-evidence
# Or use :app:connectedDebugAndroidTest for Gradle reports; AGP uninstalls
# the app afterward, removing app-scoped screenshots. The script retains them.
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

Production application identity, signing, Play enrollment, publishing,
production authentication exposure, domain persistence, voice and sharing
remain separate assignments. Do not distribute this development shell as a
working financial app.

See the [acceptance report](../../docs/reports/android-phone-foundation.md) for
exact device evidence, source revisions and remaining limitations.

## Local registered-session development

The [session spec](../../docs/superpowers/specs/2026-09-28-android-registered-session.md)
owns this continuation. The five-tab sample remains available without sign-in.
An enabled build adds Account under Profile & settings. Argus owns password
validation and profile truth through `/api/v1/auth/login` and bearer `/api/v1/me`.
The pinned Supabase Kotlin SDK 3.2.6 owns refresh and provider logout. Ktor 3.3.1
matches that SDK's declared dependency. The Accounts continuation below reuses
this session owner for every financial request.

Set these variables only for a disposable, CAPTCHA-disabled local stack:

```text
ARGUS_ANDROID_LOCAL_AUTH=true
ARGUS_ANDROID_API_URL=http://10.0.2.2:59400
ARGUS_ANDROID_SUPABASE_URL=http://10.0.2.2:59401
ARGUS_ANDROID_SUPABASE_ANON_KEY=<generated local public anon key>
ARGUS_ANDROID_CAPTCHA_TOKEN=<nonempty local test token>
ARGUS_ANDROID_RECOVERY_URL=http://127.0.0.1:3000/auth/forgot-password
```

Then run the ordinary Gradle commands above. Configuration accepts only explicit
localhost, 127.0.0.1 or emulator 10.0.2.2 URLs with ports, without credentials,
queries or fragments. Missing/invalid configuration disables auth. Release
builds always have empty configuration and auth disabled. Cleartext permission
is restricted to those exact hosts in debug. Never provide a service-role key
to the app or enable this test CAPTCHA mode against a hosted service.

Recovery opens the existing browser forgot-password page. For an emulator,
reverse its local browser ports to the dedicated host stack:
`adb -s <dedicated-device> reverse tcp:3000 tcp:3000` and
`adb -s <dedicated-device> reverse tcp:59401 tcp:59401`.
The existing browser flow owns recovery from start to finish; sign in afresh
in Android afterward. Local recovery web origins remain limited to the existing
3000/3001 contract. Coordinate port ownership before starting any service.

Sessions are encrypted with a device-only Android Keystore AES-GCM key, written
atomically under `noBackupFilesDir`. Backup is disabled. Passwords are ephemeral
form values; profiles stay in memory. The stored record contains only session
credentials, expiry, minimal identity and lifecycle markers; provider profile
metadata and unused provider credentials are excluded. One controller serializes SDK mutations
and ignores responses belonging to a retired identity. Foreground/relaunch
verification refreshes expiring sessions before loading `/me`. Network or
verification failures retain a retry path while hiding the profile. Explicit
session rejection clears the invalid session. Logout hides the profile at once,
records pending revocation durably, and reports success only after provider
revocation and local cleanup. The SDK's ordinary signOut helper suppresses some
HTTP errors, so its explicit-bearer `auth.admin.signOut(..., LOCAL)` wrapper is
used for the same logout endpoint with the user's bearer and public anon key.
It uses no privileged credential or user-administration endpoint.

Account switching completes logout before another login. A restored guest
session remains preserved behind a continuity notice; this slice neither
bootstraps nor converts guests. Production CAPTCHA, app identity, signup,
native recovery callbacks and financial APIs remain separate assignments.
In the local-auth build, composer drafts remain in memory only: same-owner
refresh retains them, unverified sessions hide them, and account retirement or
activity/process recreation discards them. Default-off sample drafts retain
their existing saved-state behavior.

`SessionDeviceContractTest` and `RegisteredSessionLocalTest` are opt-in device
checks; they skip without the local build and synthetic instrumentation inputs.
Use only disposable credentials and keep input files restricted. The former
proves encrypted storage, expired-token refresh, server rejection after logout,
and separate-process restoration. The latter drives the real bilingual UI and
checks the browser handoff. Default builds run the ordinary sample/UI tests.


## Local financial Accounts

The [Accounts spec](../../docs/superpowers/specs/2026-09-29-android-financial-accounts.md)
binds this client to API_CONTRACT 17.3. Accounts supports create, read, metadata
edit, opening corrections, archive and restore. Other destinations remain
samples. All financial responses are refetched after process restart; drafts
are memory-only and retire on identity changes. No transactions, totals,
delete, offline sync or cross-surface synchronization are claimed.

### Dedicated local setup

Inventory containers/ports and select a free, uniquely named stack first. The
example below reserves API59400, gateway59401, DB59402, mail59403/59404 and
shadow59406. Do not stop/reset a shared stack or the shared adb daemon.
Prerequisites: the repository's Python dependencies, Docker, Supabase CLI and
the pinned Android toolchain. No hosted project is used.

```bash
# From repository root. Refuses to overwrite an existing config.
python3 mobile/android/tools/local_accounts.py prepare /tmp/android-accounts-local
supabase start --workdir /tmp/android-accounts-local -x studio,imgproxy,edge-runtime,logflare,vector,supavisor
umask 077
supabase status --workdir /tmp/android-accounts-local -o json > /tmp/android-accounts-stack-private.json
export ARGUS_ANDROID_STACK_JSON=/tmp/android-accounts-stack-private.json
export ARGUS_ANDROID_PYTHON=/absolute/path/to/argus-venv/bin/python
python3 mobile/android/tools/local_accounts.py api
```

`prepare` derives configuration from the repo and copies current migrations;
seeds are disabled. Set `ARGUS_ANDROID_STACK_NAME=android-accounts-<unique>` and
`ARGUS_ANDROID_PORT_BASE` before preparation to reserve a different range.
Set matching `ARGUS_ANDROID_API_PORT` for both API and build. The launcher
accepts loopback stack URLs only, uses durable Supabase persistence, enables
Accounts only locally and builds a clean environment without model credentials.
The API launcher runs in the foreground: stop/restart that owned process to
exercise durable readback; never reset its database for a restart check.
`ARGUS_ANDROID_TEST_ACCOUNTS_ENABLED=false` provides a local flag-off probe;
`ARGUS_ANDROID_TEST_GUEST_ENABLED=true` permits a real local guest bootstrap
for denial checks. Neither changes hosted configuration.

In a second terminal with the same stack/API environment and configured
`JAVA_HOME`, `ANDROID_HOME`, `GRADLE_USER_HOME`:

```bash
python3 mobile/android/tools/local_accounts.py build
```

This builds the opt-in app, JVM tests, lint and instrumentation APK. The
emulator uses 10.0.2.2 to reach the host API/auth gateway. The existing recovery
URL is retained; this Accounts recipe does not start a browser recovery server.
For shared-backend cross-surface validation, point the existing auth build
variables at the captain's approved local API and auth gateway; use the same
registered identity deliberately. Independent fixture runs do not prove sync.

### Native acceptance and restart

Generate two disposable registered `@example.test` identities through the local
`POST /api/v1/auth/signup` with generated passwords, local nonempty CAPTCHA
placeholder and languages `en` and `es-419`. Store only `email`/`password` in a
0600 JSON array outside Git; never paste them into reports or logs.

```bash
export ARGUS_ANDROID_IDENTITIES_JSON=/absolute/private/identities.json
export ARGUS_ANDROID_EVIDENCE_DIR=/tmp/android-accounts-evidence
export ARGUS_ANDROID_TEST_DEVICE=emulator-5584 # confirmed dedicated to this run
python3 mobile/android/tools/device_accounts.py install
python3 mobile/android/tools/device_accounts.py ui 0 # English/light
# Pull screenshots before the next mode clears the app fixture.
# /sdcard/Android/data/ai.argus.foundation.sample/files/evidence/accounts-<width>x<height>/
python3 mobile/android/tools/device_accounts.py ui 1 # Spanish/dark
python3 mobile/android/tools/device_accounts.py core
python3 mobile/android/tools/device_accounts.py save
# Stop/restart the owned API process, preserving DB; restore force-stops only the app.
python3 mobile/android/tools/device_accounts.py restore
```

The UI/core/save modes clear only this application on the selected emulator;
restore preserves app data and verifies a durable server record after session
restoration. Use phone-size viewports and 130% font scale on the owned emulator.
Emulator evidence is not physical-device acceptance. Review the final PR audit
for exact source/evidence SHAs, retained evidence and test outcomes.
