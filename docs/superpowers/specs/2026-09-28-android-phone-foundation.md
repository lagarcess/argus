# Android phone foundation

Runnable native Kotlin/Compose development shell with honest sample states,
shared controls, and a durable local appearance preference. Founder assignment:
September 28, 2026. This is a foundation, not a financial-record implementation.

## 1. Why

MVEE sections 2–3 approve native Android and five connected destinations while
preserving finance chat. This lane establishes their phone navigation and native
interaction foundation without inventing the pending ecosystem contracts.

## 2. Locked decisions

1. Worker: `codex/android-phone-foundation`. Original fetched integration and
   actual starting HEAD: `3b9313f3dcf80e3ff9eddfcce8818a829a081225`.
2. Design: [#727](https://github.com/lagarcess/argus/pull/727), reference SHA
   `e29ee6f930a58d0eeca4ca49b2545a3cb63a1d43`, OPEN/unmerged when read.
   Archive SHA-256: `c55e565aa142e38eec61b570510af1c4c2cb9629c24f3ce2d01387639f0ea0e6`.
   Read its archive and documents at that SHA; do not merge its branch or copy
   its canonical documentation. Later merge status must be checked at closeout.
3. Tabs in reference order: Home, Accounts, Argus, Plan, Search. Initial tab is
   Argus. Updates and profile/settings sit outside the tab bar. Native Android
   Back dismisses overlays first, returns secondary destinations to their source,
   then returns other primary tabs to Argus; Back at Argus leaves the activity.
4. Kotlin with Jetpack Compose, single activity, minimum API 26, compile/target
   API 36. Pin compatible AGP, Gradle, Kotlin and Compose dependencies; include
   the Gradle wrapper. Use Studio's bundled Java after actual compatibility proof.
5. Light/Dark/System is one local preference owner, defaults to System, follows
   system changes, and survives recreation and process restart. No product data
   is persisted. Static copy supports English and es-419 through Android resources.
6. Space Grotesk headings and Inter body, restrained semantic colors, flat
   content and floating navigation, pill actions and quiet icon controls; at least
   48dp targets, scalable text, selected semantics and safe-area/IME handling.
7. Development application identity visibly says Sample. All financial content
   and chat examples are explicitly sample-only, with no API dispatch, secrets,
   quota simulation or manufactured assistant execution. The guest sample can
   enter finance chat; ecosystem actions, including a typed sample action offered
   in chat, show the same registration boundary. This demonstrates policy, not
   server enforcement or production authentication. Never classify typed prose.
8. Header geometry preserves Recents/New on the left and Temporary controls on
   the right. Unsupported production actions disclose their unavailable state.
   Settings uses identity then App / Account / Support. Spaces are separate.

## 3. Reserved / parked scope

Financial arithmetic and posting, real accounts/transactions, server guest
enforcement, production auth, product/domain persistence, chat streaming/runtime,
voice, sharing, providers, Play registration/payments, signing/publishing,
hosted configuration, migrations and canonical-document edits remain outside
scope. The only durable app value is appearance. No paid turns or real backtests.

## 4. Contract gates and ownership

- Own `mobile/android/**`, this spec, `docs/reports/android-phone-foundation.md`,
  and `docs/reports/evidence/android-phone-foundation/**`. A dedicated Android
  workflow may be added if existing CI cannot verify the new project.
- No API/data contract changes. Future clients consume server-owned session,
  capability, quota and artifact truth; sample models cannot become those schemas.
- Coordinate the iPhone lane on tab order, design reference and sample boundaries;
  leave its project, branch and docs untouched.
- #726 owns its probe and active fixes. Coordinate before compiling a frozen
  isolated export, record exact SHA and actual results, and send findings back
  without importing its authentication code into this app.

## 5. Execution contract

One labeled PR targeting `codex/private-alpha-next`; spec is the first commit.
Build an ARM64 emulator for this Apple Silicon Mac. Verify wrapper build, local
tests, Android lint, launch, all destinations, guest boundary through direct and
chat actions, overlay/Back behavior, theme persistence and live System changes,
English/es-419, keyboard, accessible labels/targets and two phone sizes (small
and large). Commit unedited emulator screenshots and sanitized test/toolchain
evidence. State unverified physical-device/TalkBack behavior honestly.

Reconcile current integration with a normal merge, assess semantic overlap,
run merged-tree modularity checks and applicable exact-head gates. Take the PR
out of draft and complete review-exhaust: validate findings, fix confirmed bug
classes, reply/react/resolve, and obtain clean latest-delta review with zero
unresolved threads and passing applicable CI. Revalidate retained evidence after
head changes. The founder owns merge and deployment; this lane stops at the PR.

## 6. Dependencies, unresolved choices and stop conditions

- Toolchain downloads and ARM64 image installation are prerequisites, not product
  decisions. Choose pinned compatible versions based on official documentation
  and actual build results; record them in project setup documentation.
- #727 is a reference dependency while unmerged. Recheck changed reference
  surfaces if its head moves; do not silently claim it has landed.
- #726's current probe uses an older Java/Gradle baseline. Preserve its exact
  source and coordinate any compatibility findings with its owner. A build failure
  is evidence, not permission to fix the other lane.
- Production auth/recovery, domain APIs, shared financial rules and permissions
  remain unresolved dependencies for later work and do not block the sample shell.
- Stop dependent work for conflicting ownership, any need for a new production
  contract, real credentials/paid providers, hosted mutations, or unsupported
  device execution. Continue independent checks and report the exact limitation.

## Sources

- [Authority](../../DOCUMENTATION_AUTHORITY.md), [MVEE](../../specs/argus-minimum-viable-ecosystem-experience.md),
  [Architecture](../../ARCHITECTURE.md), [API](../../API_CONTRACT.md),
  [Data model](../../DATA_MODEL.md), [Design](../../../.agent/designs/argus/DESIGN.md).
- #727 exact reference above supersedes older experience prose for this explicit
  assignment. #726 is a proof dependency, not production-auth authorization.
- [AGP compatibility](https://developer.android.com/build/releases/agp-9-1-0-release-notes)
  and [Gradle Java compatibility](https://docs.gradle.org/current/userguide/compatibility.html).
- Implementation choices: API 26 minimum and Android-native Back rules are
  bounded engineering choices; neither changes shared product or API contracts.
