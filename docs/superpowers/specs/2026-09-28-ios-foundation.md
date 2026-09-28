# iPhone SwiftUI foundation

## 1. Why and authority

Deliver a runnable, reusable iPhone client foundation for the ecosystem in
[PRODUCT](../../PRODUCT.md) and the [MVEE](../../specs/argus-minimum-viable-ecosystem-experience.md).
This is the founder's explicit September 28 assignment, not authorization to
implement the entire ecosystem.

- Original freshly fetched integration base: `3b9313f3dcf80e3ff9eddfcce8818a829a081225`.
- Worker: `codex/ios-foundation`, isolated checkout `8be2/private-alpha-next`.
- Experience reference: [PR #727](https://github.com/lagarcess/argus/pull/727),
  open/non-draft and under review when inspected, exact commit
  `a1c294319a2c047623b9bbe5bedd36155d2e931d`.
- Frozen archive: `mobile-2026-09-28`, SHA-256
  `c55e565aa142e38eec61b570510af1c4c2cb9629c24f3ce2d01387639f0ea0e6`.
  Its HTML, CSS and images are experience references; its JavaScript financial
  models are not production contracts. Do not merge its branch or copy canonical
  documentation into this lane.

## 2. Locked decisions

1. iPhone only. SwiftUI app and shared, committed Xcode project/scheme. Simulator
   build requires no developer team or provisioning. Initial deployment floor
   iOS 17 is a replaceable engineering choice, not a supported-device release promise.
2. Primary order: Home, Accounts, Argus, Plan, Search. Floating rounded material
   navigation, icon-only accessible controls, visible selected state, Argus mark
   in the center. Header Updates/Profile stay outside primary navigation.
   Empty chat preserves Recents left and Temporary right; no duplicate title.
3. Shared semantic light/dark colors, Space Grotesk display/Inter body typography,
   spacing, pill controls, rows, quiet search and sample-state treatment derive
   from the lock. Preserve readable Dynamic Type, safe areas, >=44pt targets,
   reduced motion and reduced transparency. No new design exploration.
4. Appearance offers Light, Dark, System under Profile > App > Preferences;
   persists only this local preference across process relaunch and follows OS
   changes in System mode. Localization covers English and es-419.
5. Each destination contains clearly labeled local sample/empty presentation.
   Navigation and appearance work. Financial data, chat answers, auth, monitoring,
   and saves do not. Excluded controls give an honest sample explanation or are
   visibly unavailable; never simulate a successful backend operation.
6. Keep display fixtures immutable and separate from shell state. No money math,
   domain rules, ledger, network client, tokens, analytics or financial persistence.
7. Development configuration is local and replaceable, with no secrets. Bundle
   identifier is explicitly simulator-only; signing is disabled and no team set.

## 3. Ownership, dependencies and unresolved choices

- This lane owns `ios/` (project, SwiftUI sources, resources, tests, runner and
  focused README), this spec, and `docs/reports/evidence/ios-foundation/`.
- Parent owns spec, project integration, simulator acceptance, PR/review and
  reconciliation. Bounded implementation/review assistance may own named files;
  collaborators must preserve concurrent edits and finish with a handoff.
- No-touch: canonical docs, backend, web, migrations, model instructions,
  existing probes, CI workflows and hosted configuration. No shared document edits.
- [#726](https://github.com/lagarcess/argus/pull/726), inspected at
  `de61fd3e7d299fcd0c7fda24f3c95f5427822271`, owns native auth/session proof.
  Its probes and synthetic handoff adapter are evidence, not the app. Future auth
  must resolve server refresh/session isolation, secure SDK storage, cookie
  isolation, CAPTCHA and callback/recovery contracts with that owner. This lane
  neither imports the probe nor creates an auth abstraction claiming those solved.
- Production bundle identity, signing team, distribution, release minimum OS,
  native email/recovery destination and guest financial persistence stay unresolved.
  None blocks a local, offline simulator foundation.

## 4. Contract gates

No API, data, auth or canonical architecture contract changes. Focused `ios/README.md`
owns setup, local configuration, dependency provenance, sample boundaries and
future integration points. The committed project is buildable without a generator.
No third-party runtime SDK is needed for this foundation.

## 5. Execution and acceptance contract

One labeled PR targets `codex/private-alpha-next`. Commit this spec before app
implementation. Commit coherent implementation/test/evidence checkpoints. Move
completed work from draft to ready to trigger Codex review; address reachable,
in-scope findings and inspect unresolved inline threads. Founder alone merges.

Acceptance:

- Repeatable `ios/scripts/verify.sh` builds/tests the committed project using a
  caller-selected available simulator; document Xcode/runtime setup and launch.
- XCTest/XCUITest exercises all five destinations, selected state, header entry
  and return, sample disclosure, Light/Dark/System preference and relaunch.
- Two dedicated simulator sizes: compact iPhone 17e and large iPhone 18 Pro Max
  on available iOS 27 (equivalent sizes may substitute with recorded device IDs).
  Check all destinations, keyboard/search, light/dark, enlarged Dynamic Type,
  labels/targets, no clipping and no safe-area overlap. Check es-419 on device.
- Capture durable unedited simulator images plus test results and observed
  accessibility/layout limits under the evidence directory. Record candidate
  SHA, Xcode/runtime/device, commands and sample-only scope. Later doc/evidence
  commits require explicit source-equivalence revalidation.
- Fetch current integration, inspect semantic overlap (runtime, API/data, UI owner,
  migration, environment, tests), merge it one-way if advanced, run merged-tree
  modularity check and exact-head applicable CI. Never rebase this evidenced lane.
- Final report names original/current integration, reconciliation SHA, overlap,
  retained/invalidated evidence, PR head, CI and final review outcome. Do not claim
  READY while review or required acceptance is incomplete.

## 6. Stop conditions and rollback

Stop dependent work if reference review changes an implemented locked interaction,
a competing agent owns these new iOS files, or acceptance requires auth, financial
rules, provider calls, production signing or hosted changes. Continue independent
foundation work and report the concrete dependency. Toolchain failures remain
unverified checks, never passing evidence. No merge or deployment is authorized.

Rollback: revert this isolated project/docs PR. There is no backend or hosted state
to undo; local simulator preference can be removed by uninstalling the sample app.
