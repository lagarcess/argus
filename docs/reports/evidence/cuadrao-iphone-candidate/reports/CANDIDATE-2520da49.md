# Candidate verification: claude/cuadrao-iphone-candidate at 2520da495734baab045ca887ad95e34b296743fa

Status: DONE 03:39 CDT 2026-10-04 (started 02:30). Verifier only: no product change, no commit, no push.

Summary. Everything that changed since 4af8fced holds on this head. The full UI suite ran once: 167 tests, 117 passed, 48 skipped, 2 failed, 0 never-idle waits, 49.9 min. Both failures pass when run alone. `CuadraoProfileFollowupUITests/testFeedbackPreservesKindsAndPartialDrafts`, which failed 2 of 2 times at 4af8fced, passed (37.1 s), so the helper fix works on this device. Release no longer contains `--cuadrao-design`. Every sampled off-centre tap did its action. One claim did not hold: the split member row toggles up to 16 pt before the amount, not 32 pt. The connected walk passed all four journeys. The revoked member now sees "Los permisos del hogar cambiaron", and the join step no longer shows a stale review card. The iPhone 15 was unavailable. A signed build 3422 named "Cuadrao Preview" is saved with install commands.

Worktree `/Users/garces/Documents/projects/repos/argus/.claude/worktrees/cuadrao-candidate`, clean at 2520da49, no untracked file. Logs under `~/.claude/orchestrate/cuadrao-iphone-candidate/candidate-2520da49/` (written below as `$N`). The 4af8fced logs are untouched.

## Stage table

| # | Stage | Command | Result | Wall | Log |
|---|---|---|---|---|---|
| 1 | scope proof | `git diff --name-only 4af8fced..2520da49 -- . ':!docs/reports/evidence' ':!ios'` | only `.agent/designs/cuadrao/DESIGN.md` and `docs/specs/argus-execution-board.md`. No backend, web, migration or script file changed, so the 4af8fced backend full suite, real Postgres, auth matrix, web and OpenAPI results stand | | $N/s1-static/changed-files.txt |
| 1 | docs + diff check | `BASE=a8c37d3a... verify-candidate.sh <wt> <udid> $N/s1-static/vc docs modularity` (`check_docs_links.py --base a8c37d3a182fbdb3228f6003272418e65286bc1a`, `git diff --check a8c37d3a...HEAD`) | 11 changed docs checked, pass. diff --check clean | 1 s | $N/s1-static/vc/docs.log |
| 1 | modularity | same run, `scripts/check_modularity_budget.py` | Budget violations: none | 1 s | $N/s1-static/vc/modularity.log |
| 1 | doc-reading Python tests (container) | the ten files W3 lists (`tests/test_retention_purges_are_wired.py` ... `tests/test_account_deletion_fk_census_postgres.py`) | 144 passed, 3 skipped (census real-PG, no database), same as W3 | 28 s | $N/s1-static/doc-pytest.log |
| 1 | doc-reading web tests (host bun) | `bun test __tests__/account-deletion-api.test.ts __tests__/chat-next-move-rows.test.ts` | 46 pass, 0 fail | 1 s | $N/s1-static/web-doc-tests.log |
| 2 | iOS Debug build | `SIMULATOR_ID=8AFB... ios/scripts/verify.sh build` | BUILD SUCCEEDED. 1 warning (ImplicitStrongCapture, ConnectedCuadraoRoot.swift:27, same as 4af8fced) | 12 s | $N/s2-ios-build/debug-build.log |
| 2 | iOS Release build | `xcodebuild build ... -configuration Release -destination 'generic/platform=iOS Simulator' -derivedDataPath /private/tmp/claude-501/cuadrao-candidate-dd/release CODE_SIGNING_REQUIRED=NO` | BUILD SUCCEEDED | 57 s | $N/s2-ios-build/release-build.log |
| 2 | Release strings | `strings -a` over every Mach-O (`$N/s2-ios-build/strings-check.sh`) | Release (1 Mach-O): `--cuadrao-release-gates` 0, `--cuadrao-release-ui` 0, `--invitations-harness` 0, `InvitationsHarness` 0, `InvitationsStubServer` 0, `ReleaseUIReview` 0, **`--cuadrao-design` 0** (was 2 at 4af8fced). Debug control (3 Mach-O): 1, 1, 1, 5, 2, 4, 1. `--design-gallery` is still 2 in Release, but only `CuadraoCanvas` reads it, and Release reaches that view only when `CUADRAO_DESIGN_PREVIEW` is true | | $N/s2-ios-build/strings-check.txt |
| 2 | Config defaults | `ios/Config/Development.xcconfig` and both built Info.plists | `ARGUS_AUTH_ENABLED`, `ARGUS_APPLE_SIGN_IN_ENABLED`, `ARGUS_GOOGLE_SIGN_IN_ENABLED`, `ARGUS_BETA_INVITES_ENABLED`, `ARGUS_INVITE_UNIVERSAL_LINK_ENABLED` all false in the xcconfig and in the Release and Debug Info.plists | | $N/s2-ios-build/strings-check.txt |
| 3 | full iOS UI suite (second full run because about 30 hit areas across most screens changed after the 4af8fced run) | `$N/s3-ios-test/run.sh`: inside one `lockf -k mac-sim.lock` holder, `xcrun simctl location 8AFB... set 18.4861,-69.9312`, then `SIMULATOR_ID=8AFB6084-8918-416E-9164-E21061306BEC RESULT_DIR=$N/s3-ios-test ios/scripts/verify.sh test -collect-test-diagnostics never`, then `simctl location ... clear` | **167 executed: 117 passed, 48 skipped, 2 failed**. `** TEST FAILED **`, exit 65. **0** never-idle waits. Per-class counts identical to 4af8fced | **49.9 min** (02:31:46 to 03:21:41; xcodebuild 2984 s) | $N/s3-ios-test/driver.log, test-20261004T073146Z.xcresult, per-class.txt |
| 3 | never-idle watcher | `$N/s3-watch/watch.sh` (copy of `w1f/watch.sh` with only the simulator UDID and dump script path changed), armed on the suite log for "App animations complete notification not received" | never fired, because no wait happened. It exited when the suite wrote `exit=` (03:21:42). lldb never attached, so timing was untouched | | $N/s3-watch/watch.log |
| 3 | focused rerun of the 2 failures, once | `SIMULATOR_ID=8AFB... RESULT_DIR=$N/s3b-focused lockf -k ... verify.sh test -collect-test-diagnostics never -only-testing:` the two tests | **both passed**: Group 61.8 s, Voice 30.8 s | 103 s | $N/s3b-focused/driver.log |
| 4 | Mac pass checks | `OUT_DIR=$N/s4-macpass-checks ios/scripts/cuadrao-design-mac-pass.sh checks`. These are swiftc state checks with no simulator, so they ran beside the suite without the lock | `== checks: ok`, 9 of 9 runners pass. New `run_tap_targets`: "plain-style statements: 127, without a content shape: 43, reviewed: 43, unreviewed: 0, stale entries: 0, container styles: 0, helpers without a shape: 0" | 16 s | $N/s4-macpass-checks/run.log, design-preview-checks.log |
| 4 | Mac pass screens | `SIMULATOR_ID=8AFB... OUT_DIR=$N/s4-macpass-screens lockf -k ... cuadrao-design-mac-pass.sh screens` | `== screens: ok`, exit 0. The script's own verdicts are the same as at 4af8fced (default identical, design differs from 2185aefe). **All 12 PNGs are byte-identical to the 4af8fced run's** | 110 s | $N/s4-macpass-screens/run.log, vs-4af8fced.txt |
| 4 | suite screenshots, 4af8fced vs this head (added because the 12 launch screens do not show most changed controls) | `xcresulttool export attachments` on both suite xcresults. `$N/s4-attachments/compare.py` pairs them by test and name, and `bbox.py` measures each diff | 270 pairs: **199 byte-identical, 71 differ, 0 visible changes**. A subagent opened an old, new and diff crop for all 71 and classified 70 as nondeterministic (random QR codes, system photo grid, live waveform and glow, tab glass pill at delta 1 to 13, slider drag landing, sheets or keyboard mid-presentation, scroll offsets, invitation timestamps). The 71st differs by 2 pixels at delta 1. I checked `locked-english` myself: "Cancel" and "Stop" look the same. The recording Cancel label, the one control whose button style changed, was measured: glyph range identical, no pixel off by more than 8 to 24 levels. 2 old-only shots are the Group test's last two, which never ran because that test failed. 3 new-only shots are tests that failed at 4af8fced | | $N/s4-attachments/compare.tsv, compare-summary.txt, bbox.tsv, comp/ |
| 5 | off-centre tap proof | Throwaway `ZZTapProofUITests.swift` (copies `$N/s5-tapproof/ZZTapProofUITests.v1.swift`, `.v2.swift`). The synchronized test group compiles only files inside the tree, so the file was copied into `ios/ArgusFoundationUITests/` only for `xcodebuild build-for-testing` into out-of-tree derived data (`/private/tmp/claude-501/cuadrao-candidate-dd/tapproof-default`, `tapproof-auth` with the mac-pass auth-on settings), then deleted. Runs used `test-without-building -xctestrun ... -collect-test-diagnostics never` under the lock | see the off-centre table. Pass 1: 6 passed, 2 failed (split dead zone, and my voice blank check that read whole columns). Pass 2: both rewritten checks passed | 103 s + 11 s + 105 s | $N/s5-tapproof/default.log, auth.log, v2.log, *.xcresult |
| 6 | connected walk | iPhone 17e 8B7975F1, same method as 4af8fced (see stage 6) | 4 of 4 journeys pass | 03:29:34 to 03:36:52 lock held | $N/s6-walk/ |
| 7 | device build | `lockf -k ... xcodebuild build ... -configuration Debug -sdk iphoneos -derivedDataPath /private/tmp/claude-501/cuadrao-candidate-dd/device -xcconfig .../baseline/device-build/device-preview.xcconfig CURRENT_PROJECT_VERSION=3422 INFOPLIST_FILE=$N/s7-device/device-Info.plist` | BUILD SUCCEEDED (compiled this head's sources: `CuadraoGroupExpenseEditor.swift`, `CuadraoVoiceMessagePanel.swift` in the log) | 12 s | $N/s7-device/build.log, readback.txt |

## UI suite across baseline, 4af8fced and this head

| | Baseline a8c37d3a | 4af8fced | 2520da49 |
|---|---|---|---|
| Tests | 135 | 167 | 167 |
| Passed / skipped / failed | 82 / 48 / 5 | 116 / 48 / 3 | **117 / 48 / 2** |
| Never-idle waits | 49 (31 Recents, 10 Voice surfaces, 7 Support search, 1 Appearance) | 15, all in `CuadraoContextUITests/testGroupContextPreservesDraftAttachmentsAndReturn` | **0** (the Context test passed in 53.6 s) |
| Wall | 89.5 min, contended | 65.4 min, mostly alone | 49.9 min. Contended in the first 10 min by the Release, tap-proof and walk builds, a Supabase reset and the API start |
| `CuadraoProfileFollowupUITests/testFeedbackPreservesKindsAndPartialDrafts` | passed | failed 2 of 2 (`:226`, Save not hittable) | **passed (37.1 s)** |
| `CuadraoReceiptPermissionUITests/testAllowedLocationCanBeRemoved` | passed | failed without a location, passed with one | **passed (43.8 s)**, location set for the run |
| `CuadraoVoiceDesignUITests/testLockedRecordingAndCleanAttachments` | passed | failed in suite, passed alone | failed in suite, **passed alone** (30.8 s) |
| `CuadraoGroupDesignUITests/testSharedJourneySpanish` | failed | passed (62 s) | failed in suite, **passed alone** (61.8 s) |

Failures on this head, first assertion line:

| Test | First assertion | Suite | Alone | Class |
|---|---|---|---|---|
| `CuadraoGroupDesignUITests/testSharedJourneySpanish` | `CuadraoGroupDesignUITests.swift:48: XCTAssertTrue failed - A split that adds up can be saved` (Save did not enable within 2 s after typing 500 and 300 into the exact split) | failed, 49.1 s, about 02:40 | passed, 61.8 s | Timing under contention, not proven. It failed while I was running builds, a Supabase reset and the API container start beside the suite. The steps logged match the passing 4af8fced run step for step. The split row changed on this head (Spacer tap overlay), but the overlay ends left of the share field. The focused pass and the tap probe both typed in, and toggled next to, these fields without trouble. No failure screenshot exists (`-collect-test-diagnostics never`). |
| `CuadraoVoiceDesignUITests/testLockedRecordingAndCleanAttachments` | `CuadraoVoiceDesignUITests.swift:155: XCTAssertTrue failed` (`voice-message-stop` not within 3 s of locking) | failed, 14.0 s | passed, 30.8 s | Same flake and same line as at 4af8fced. |

Baseline failures on this head: `testMoneyEntryAndBlankCreationSpanish` passed (25.8 s), `testScanAndEnglishParity` passed (28.6 s), `testReceiptShowsYouOweWhenAnotherPersonPaid` passed (38.7 s). The baseline's wait-heavy tests also passed with no waits: `testRecentsActionsAndRecovery` (43.2 s), `testVoiceStaysAvailableAcrossSheetsAndSurfaces` (22.5 s), `testFirstUseSavedChatAppearsInSearch` (24.0 s), `testAppearancePersistsAcrossRelaunch` (47.7 s). `FinancialLoopUITests/testSharedPlanningFourKinds...` still skips without its seeded backend.

## Off-centre tap proof (iPhone 18 Pro, Debug)

Each tap point was chosen from the control's own screenshot. The test found the widest ink-free run of columns (or checked a ±3 pt box) and tapped in its middle, so every tap landed on blank space inside the frame, away from text and glyphs. Ink runs and tap points are logged per control in the `TAPPROOF` lines.

| Control | Where the tap landed | Expected action | Result |
|---|---|---|---|
| Updates notice row (`updates-row-0`, release review host, es) | x 270 of a 354 pt row; blank run 194 to 347 between the text and the trailing edge | opens the notice | **PASS**, row left, nav bar "Novedad" |
| Home activity row (`home-activity.*`, design preview) | x 217; blank run 166 to 268 between the title and the amount | opens the activity detail | **PASS**, `activity-detail-title` shown |
| Receipt "Choose currency" (`receipt-currency`, photo import, en) | x 333 of 370; text ends at 202 | opens the currency menu | **PASS**, `USD` option shown |
| Split member toggle (Ana, group "trip", new expense, es) | from 44 down to 4 pt before the trailing element, both split modes (`testSplitBoundaryProbe`) | toggles from the name to 32 pt before the amount; no toggle in the last 32 pt (claim of 567f59819 and the W1e README) | **Toggle area PASS, dead zone FAIL.** Equal mode (amount "DOP 500" at x 306): toggles at 44, 36, 32, 28, 24, 20 and 16 pt before; no toggle at 12, 8 and 4. Exact mode (share field at x 238): same, toggles to 16 pt before, no toggle and no keyboard at 12, 8 and 4. The no-toggle band is about 12 pt (the HStack spacing), not 32. The macOS probe that backed the 32 pt claim used synthesized mouse clicks; on iOS, touch hit-testing is wider. A thumb 13 to 31 pt short of the share field excludes the member instead of doing nothing. Pass 1 at 18 pt before also toggled |
| Manage spaces (`Gestionar espacios`, spaces sheet) | x 288 of 340; text ends at 167 | opens Manage spaces | **PASS**, nav bar "Gestionar espacios" |
| Voice recording Cancel (`voice-message-cancel`, 80 x 48) | (40, 4) pt: 4 pt below the frame's top edge; glyph rows 16 to 30; box ink 0 | cancels the recording | **PASS** (pass 2), back to chat, `header.profile` shown. Pass 1 tapped at x 5 and was refused by my own blank check: "Cancelar" glyphs span x 3 to 77 of the 80 pt frame, so no column is blank. It never tapped |
| Outlined Sign in (`cuadrao.welcome.signin`, auth-on build, en) | x 17 of 346 (blank between the stroke at 0 to 2 and the text at 144); y 20% | opens sign-in | **PASS**, `cuadrao.signin.emailChoice` shown |

Also seen in passing during the walk: the connected Profile "Invitaciones" row opened from a tap at x 253 (right of its text), and a tap in the gap between "Cuenta Ana" and its amount on the connected Household row opened the account.

## Connected walk (iPhone 17e 8B7975F1, live local backend)

Method as at 4af8fced. API from this worktree's `src/` in `cuadrao-py310-runner` (venv `cuadrao-py310-venv-75e2998a73`, unchanged lock file) on 18791. `access_fault_proxy.py` on 18790 records the app's requests, and no fault flag was used. Captcha page on 18795. Flags on: households, financial accounts, beta invites, beta gate. Universal link off. Throwaway invite secret; founder = local user A. Scripts `$N/s6-walk/walk-api.sh` and `walk_setup.py` are copies of the 4af8fced ones with only the log directory and docstring changed. Server-side setup calls went straight to 18791, so the proxy log holds only the app's requests. Local Supabase `argus-qa`, CLI 2.109.0, reset before (111 migrations, max 20261004090000, 0 users). Users came from local GoTrue sign-up. App: Debug, bundle `local.argus.w7invites`, out-of-tree `sim.xcconfig`, built to `/private/tmp/claude-501/cuadrao-candidate-dd/walk-on` and `walk-off`; built Info.plists read `ARGUS_BETA_INVITES_ENABLED` true and false. Launched with `-AppleLanguages (es-419)`. Driven with the simulator control tool and captured with `simctl io screenshot`. One lock holder, 03:29:34 to 03:36:52 (`sim-lock.log`).

| Journey | Result | Evidence ($N/s6-walk/sim/) |
|---|---|---|
| (c) Sign in, gate, code | **PASS.** `POST /auth/login 200`, `/me`, `GET /invites/access` showed the gate "Tu invitación a Cuadrao." Typed the beta code without dashes, `POST /invites/redeem 200`, access re-read, Home opened | `09-gate.png`, `10-gate-code-typed.png`, `11-after-code.png` |
| (c) Personal invite | **PASS.** Profile, Invitaciones, Invitar a la beta: "Te quedan 10 de 10" became "Te quedan 9 de 10" with the code shown after `POST /invites 201` | `13`, `14`, `15-personal-invite-created.png` |
| (c) Join a Household by code | **PASS.** Hogar, Administrar espacios, Unirte con una invitación, code, Revisar invitación (`POST /household-invitations/preview 200`, "Casa Candidata"), name Gabi, Aceptar (`POST .../accept 200`); members Ana (Administrador) and Gabi | `17` to `24-after-accept.png` |
| (b) Join step over an existing Household | **PASS (fixed).** "+" menu listed Crear hogar, Unirte con una invitación and Casa Candidata. The join step opened with an empty field and **no review card** (at 4af8fced it still showed the accepted "Casa Candidata" card) | `30-plus-menu.png`, `31-join-step-over-existing.png` |
| (a) Revoked account grant | **PASS (fixed).** A granted G view of "Cuenta Ana" (row "USD 250.00, Ana · Solo lectura"), then revoked it by API (`g account detail 404`, `g household 200`). Tapping the row: `GET .../accounts/{id} 404`, `GET /households/{id} 200`, Household reload. G stayed on Casa Candidata as a member, the account left the list, and the screen shows **"Los permisos del hogar cambiaron. Recarga y revisa otra vez."** with Reintentar | `34-hogar-with-shared-account.png`, `35-open-revoked-account.png`, `36-after-revoke-settled.png` |
| (d) Client flag off | **PASS.** Same bundle and session, `ARGUS_BETA_INVITES_ENABLED=false`. The signed-in Household shell was on screen at the first capture, 2 s after launch. The app sent 7 requests (`/me`, `/households`, `/financial-accounts`, `/financial-plan` x2, snapshot, plan), **0 to `/invites`**. Profile had no Invitaciones row | `37-flag-off-2s.png`, `38-flag-off-shell.png`, `39-flag-off-profile.png`, `$N/s6-walk/proxy-flag-off.log` |

Full app request log: `$N/s6-walk/proxy-full.log`. Event log: `walk-events.log`. Viewable 1000 px copies: `view/`.

## Device

`xcrun devicectl list devices` at 03:37: "Sr.Garces i15" (00008120-001428C90E04201E) **unavailable** (`$N/s7-device/devices-1.txt`). Nothing was installed and no launch was attempted, so there is no device result to report and no journey is claimed.

Artifact: `/private/tmp/claude-501/cuadrao-candidate-dd/device/Build/Products/Debug-iphoneos/ArgusFoundation.app`, copied with `ditto` to **`$N/s7-device/ArgusFoundation.app`** (70 MB). `codesign --verify --strict` passes on both. Read back: display name **"Cuadrao Preview"**, bundle `local.cuadrao.design.47R3855RTJ`, build **3422**, version 0.1.0, `CUADRAO_DESIGN_PREVIEW` true, `ARGUS_AUTH_ENABLED` false, `ARGUS_BETA_INVITES_ENABLED` false. Signed by "Apple Development: garceslg3@icloud.com", team 47R3855RTJ, profile "iOS Team Provisioning Profile: local.cuadrao.design.47R3855RTJ", **expires 2026-10-07 19:57 CDT**. The display name comes from build 3420's method: a device-only copy of `ios/Config/Info.plist` at `$N/s7-device/device-Info.plist`, passed as `INFOPLIST_FILE` on the command line. Its only semantic difference from the canonical plist is `CFBundleDisplayName` "Argus Sample" to "Cuadrao Preview" (`device-Info.plist.semantic-diff`). No repo file, production configuration, provisioning or trust setting changed.

When the phone is connected, unlocked and trusted:

```bash
xcrun devicectl list devices    # expect "Sr.Garces i15" available
lockf -k ~/.claude/orchestrate/cuadrao-iphone-candidate/mac-sim.lock xcrun devicectl device install app \
  --device 00008120-001428C90E04201E ~/.claude/orchestrate/cuadrao-iphone-candidate/candidate-2520da49/s7-device/ArgusFoundation.app
xcrun devicectl device info apps --device 00008120-001428C90E04201E --bundle-id local.cuadrao.design.47R3855RTJ
lockf -k ~/.claude/orchestrate/cuadrao-iphone-candidate/mac-sim.lock xcrun devicectl device process launch \
  --device 00008120-001428C90E04201E local.cuadrao.design.47R3855RTJ
```

This is the standalone design preview with sample data and auth off (as at 4af8fced). It can show artwork, gestures, sheets, the Plan, Group, Receipt and History design surfaces and the DEBUG Profile. It cannot exercise sign-in, the gate, invitations, Household join or grants.

## Cleanup

- API container `cand-api` removed. Proxy and captcha server stopped (their background tasks report exit 144 because I killed them). Ports 18790, 18791 and 18795 are free.
- Local Supabase `argus-qa` reset at 03:38 (111 migrations, max 20261004090000, 0 auth users; `$N/s6-walk/supabase-reset-after.log`). Line 1 of `reports/W4.md`: `SUPABASE: free (last owner candidate-verifier, reset 03:38 CDT 2026-10-04)`.
- Walk bundle `local.argus.w7invites` uninstalled. iPhone 17e holds only `local.argus.foundation` and its UI test runner. The iPhone 18 Pro location was set for the suite and cleared after it.
- Throwaway secrets deleted (`.invite-secret`, `.users.json`, `.secrets.json`). Codes visible in screenshots belonged to the now-reset database.
- `ZZTapProofUITests.swift` was removed from the worktree after each of its two builds. `git status` is clean at 2520da49 and `ios/ArgusFoundationUITests/` has no ZZ file. Copies kept as evidence: `$N/s5-tapproof/ZZTapProofUITests.v1.swift`, `.v2.swift`.
- Derived data outside the repo: `/private/tmp/claude-501/cuadrao-candidate-dd/{release,walk-on,walk-off,tapproof-default,tapproof-auth,device}`.

## Findings for the lead (not fixed; verifier changes no code)

1. **Split member row dead zone is about 12 pt on iOS, not 32 pt.** Commit 567f59819 and the W1e README say the overlay "stops 32 pt before the amount". On the iPhone 18 Pro simulator, taps 16 to 44 pt before the amount or share field toggle the member, and only the last 12 pt do not, in both equal and exact modes. The macOS probe used mouse clicks; iOS touch hit-testing reaches further. Impact: a tap just short of a share field excludes that person instead of doing nothing. The person can see it and undo it, but the documented guard is not real. Smallest fixes: either correct the claim, or widen the overlay's trailing inset by the measured margin and re-measure on the simulator with `$N/s5-tapproof/ZZTapProofUITests.v2.swift` `testSplitBoundaryProbe`.
2. `CuadraoGroupDesignUITests/testSharedJourneySpanish` failed once in the suite at `:48` (Save not enabled within 2 s) while the Mac was busy with my builds, and passed alone. This is the screen whose row changed, so it is worth one more full-suite observation. Not root-caused.
3. The Voice lock flake (`:155`) repeats in the full suite at both heads and passes alone.
4. Release still contains `--design-gallery` (read only inside `CuadraoCanvas`, which needs the preview build flag in Release). Not reachable in a production build.
5. The screenshot comparison found four large scroll offsets (`receipt-shared-items-es` about 135 pt, three `gallery-*-dark-large-en` 70 to 79 pt) with the same content. They are classed as variance, but a changed tap area moving where a test's taps land was not ruled out. `gallery-unavailable-dark-large-en` is byte-identical to `gallery-loading-dark-large-en` in both runs, so that test does not capture an "unavailable" state (pre-existing).
6. Carried from 4af8fced and not rechecked: the Profile footer still says the financial screens show local examples (seen again in `39-flag-off-profile.png`); personal invite copy mentions a link.

## Not verified

- No phone install, launch or journey: the iPhone 15 was unavailable.
- Off-centre taps were sampled on 7 controls (plus 2 seen in the walk), not all of the roughly 30. The rest rest on the `run_tap_targets` static check and the unchanged screenshots.
- Root cause of the in-suite Group failure. No failure screenshot exists.
- The flag-off "no spinner" claim rests on a capture at 2 s after launch, not on a recording.
- Universal links, AASA, TestFlight, hosted GoTrue, Turnstile and rate limits: not provable locally.
- `FinancialLoopUITests/testSharedPlanningFourKinds...` skips without its seeded backend.
- Animation hitches: the simulator does not support the template. Lag was not re-measured (no change since 4af8fced touches launch or rendering cost beyond hit areas).
- TestFlight readiness is not claimed.
