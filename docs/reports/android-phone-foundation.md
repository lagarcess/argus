# Android phone foundation acceptance

Development-only Kotlin/Compose shell; no production-auth or financial-runtime
readiness claim. See [setup](../../mobile/android/README.md) and the
[bounded lane spec](../superpowers/specs/2026-09-28-android-phone-foundation.md).

## Provenance and ownership

- Original integration base: `3b9313f3dcf80e3ff9eddfcce8818a829a081225`.
- Spec-first commit: `c5a1c644`.
- Implementation design reference: #727 `e29ee6f930a58d0eeca4ca49b2545a3cb63a1d43`.
- Later design readback: `802b82306cc29373d7e4dce44c17d33adb243e30`, still open.
  Its only intervening change limits the recording-lane handoff to contract work;
  archive, shell and design tokens are unchanged. No reference branch was merged.
- Design ZIP hash: `c55e565aa142e38eec61b570510af1c4c2cb9629c24f3ce2d01387639f0ea0e6`.
- iPhone lane #729 confirmed the same tab order and no networking/auth/domain
  rules; only appearance persists. Its files and canonical docs were untouched.
- #726 coordination request: [handoff comment](https://github.com/lagarcess/argus/pull/726#issuecomment-5876433004).
  Observed probe head `de61fd3e7d299fcd0c7fda24f3c95f5427822271`.
  Owner handoff remains pending; no probe compile/test result is claimed yet.

## Environment

Apple Silicon arm64, Android Studio 2026.1.4 build
`AI-261.26222.65.2614.16379836`, bundled JBR 25.0.3. Android Emulator 37.1.11.
AGP 9.1.1, Gradle 9.3.1 with verified distribution hash, Kotlin 2.2.10, Compose
BOM 2025.08.01, SDK/target API 36 and build-tools 36.0.0. ARM64 Google APIs API
36 image. Dedicated devices: Pixel 4 at 1080×2280/480dpi (360dp wide), Pixel 7
Pro at 1440×3120/560dpi (approximately 411dp wide).

Official compatibility sources:
[AGP](https://developer.android.com/build/releases/agp-9-1-0-release-notes),
[Gradle/JVM](https://docs.gradle.org/current/userguide/compatibility.html).
Lint retains warnings-as-errors, excluding only rolling upgrade notices
`OldTargetApi`, `AndroidGradlePluginVersion`, and `GradleDependency`; the lane
intentionally pins this verified API/toolchain instead of automatically upgrading.

## Acceptance record

Final candidate/device acceptance and durable captures are being gathered.
Initial runs built and launched both phones, passed 3 JVM tests and 8/9 device
checks on each; the sole failure was a stale test expecting “Argus” instead of
reference-owned “Ask Argus.” The expectation was corrected. Initial visual
inspection corrected the space pill, Home wordmark and uncontained tab ripple.
Those first captures are superseded and are not final acceptance evidence.

The required mocked backend harness was attempted once locally. Collection
failed in `scipy.linalg` importing `_spropack` with the Mach-O `__thread_bss`
zero-fill-section error. It did not execute and is not reported as passing.
No runtime code changed; repository CI is the remaining backend gate.

## Limits

- This sample app has no network permission. Composer input never dispatches a
  turn. Sample actions demonstrate registration boundaries, not server enforcement.
- Financial displays are localized fixtures, not financial calculations, records
  or API models. Only appearance is durable; settings cannot save product data.
- Active conversations, full temporary-chat behavior, voice, attachments, sharing,
  account setup and ecosystem writes are explicitly unavailable.
- Native navigation uses a floating tonal surface and Android ripple; no claim of
  platform backdrop-blur parity. Motion is instantaneous, so reduced-motion users
  receive no custom motion. System component animations follow Android settings.
- API 26 is the configured minimum, not a tested older-device promise. Physical
  phones, TalkBack, production lifecycle, signing and publishing remain unverified.
- No production URLs/keys, hosted configuration, paid calls, merge or deploy.
