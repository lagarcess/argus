SUPABASE: see line 1 of reports/W4.md (owned by candidate-verifier during this run)

# Candidate verification: claude/cuadrao-iphone-candidate at 4af8fced6021b3581ea2a62e482eaf8231d5c58b

Status: DONE 02:05 CDT 2026-10-04 (started 00:31). Verifier only: no product change, no commit, no push.

Summary. Backend, real Postgres, web, builds, Release gating and config defaults all pass on this head. The full UI suite ran once alone on iPhone 18 Pro: 167 tests, 116 passed, 48 skipped, 3 failed, 15 never-idle waits, 65.4 min. Of the 3 failures, one is NEW and reproduces (`CuadraoProfileFollowupUITests/testFeedbackPreservesKindsAndPartialDrafts`), one is environment (receipt location; passes with a simulator location set) and one is a flake (voice lock; passes alone). All five baseline failures are gone (four pass, one now skips without its backend). The connected walk passed every journey except one message: a member whose account grant is revoked stays a member (B1 fixed) but sees no "permissions changed" message; it also found a stale review card when reopening the join step. Lag is unchanged on this Mac. The iPhone 15 was unavailable; a signed build 3421 is ready with install commands.

Worktree `/Users/garces/Documents/projects/repos/argus/.claude/worktrees/cuadrao-candidate`, clean, no product change, no commit. All logs under `~/.claude/orchestrate/cuadrao-iphone-candidate/candidate-4af8fced/` (written below as `$R`). Baseline logs untouched.

## Stage table

| # | Stage | Command | Result | Wall | Log |
|---|---|---|---|---|---|
| 1 | ruff | `verify-candidate.sh ... ruff` (container) | All checks passed | 1 s | $R/s1-s2-backend/ruff.log |
| 1 | modularity | `scripts/check_modularity_budget.py` | no violations | 1 s | $R/s1-s2-backend/modularity.log |
| 1 | OpenAPI | `generate_openapi_artifact.py` + `git diff --exit-code docs/api/openapi.yaml` | no diff | 4 s | $R/s1-s2-backend/openapi.log |
| 1 | docs | `check_docs_links.py --base a8c37d3a...` + `git diff --check a8c37d3a...HEAD` | 11 changed docs checked, pass; diff --check clean | 1 s | $R/s1-s2-backend/docs.log |
| 1 | backend | `pytest tests -q --no-cov` (container, full suite; reason: cheapest proof nothing outside the gate script moved) | **10231 passed, 1081 skipped, 0 failed** = baseline 10216 + 15 new `test_assert_pytest_gate.py` tests; skips identical to baseline | 352 s | $R/s1-s2-backend/pytest.log, pytest-junit.xml |
| 1 | web | lint, `bun test`, guest web tests, `bun run build`, Playwright storage spec (host bun 1.4.2) | lint 0 errors (8 warnings); **2207 pass 0 fail**; guest pass; build pass; Playwright 2 passed | 28 s | $R/s1-s2-backend/web.log, web-bun-test.log, web-build.log |
| 1 | deps (setup) | container `poetry install` + `bun install` into the new per-worktree volumes | poetry ok; container `bun install` failed "Fail extracting tarball for next" (Linux web node_modules volume left partial). Did not affect any result: pytest 0 failed with the same 1081 skips as baseline | 23 s | $R/s1-s2-backend/deps.log |
| 2 | real Postgres | CLI 2.109.0 `supabase start` + `db reset`, then `pytest tests/test_*_postgres.py` gated by THIS tree's `scripts/qa/assert_pytest_gate.py` | 111 migrations, max 20261004090000; **605 passed**; gate: "passed: 605 tests, 605 passed, 0 failed, 0 errors, 0 skipped", exit 0; guest backend 135 passed | 299 s (stage) | $R/s1-s2-backend/pg.log, pg-junit.xml |
| 2 | auth matrix | `pytest tests/test_guest_auth_local_supabase.py` + same gate | **13 passed**; gate "13 tests, 13 passed, 0 failed", exit 0 | 10 s | $R/s1-s2-backend/pg.log, auth-junit.xml |
| 3 | iOS Debug build | `SIMULATOR_ID=8AFB... ios/scripts/verify.sh build` | BUILD SUCCEEDED, 0 errors, 1 warning (ImplicitStrongCapture, ConnectedCuadraoRoot.swift:27) | 32 s | $R/s3-ios-build/debug-build.log |
| 3 | iOS Release build | `xcodebuild build ... -configuration Release -destination 'generic/platform=iOS Simulator' -derivedDataPath /private/tmp/claude-501/cuadrao-candidate-dd/release CODE_SIGNING_REQUIRED=NO` | BUILD SUCCEEDED | 118 s | $R/s3-ios-build/release-build.log |
| 3 | Release strings | `strings -a` over every Mach-O in the .app | Release (1 Mach-O): `--cuadrao-release-gates` 0, `--cuadrao-release-ui` 0, `--invitations-harness` 0, `InvitationsHarness` 0, `InvitationsStubServer` 0, `ReleaseUIReview` 0. Debug control (3 Mach-O): 1, 1, 1, 5, 2, 4 | | $R/s3-ios-build/strings-check.txt |
| 3 | Config defaults | `ios/Config/Development.xcconfig` and built Info.plist | `ARGUS_APPLE_SIGN_IN_ENABLED`, `ARGUS_GOOGLE_SIGN_IN_ENABLED`, `ARGUS_BETA_INVITES_ENABLED`, `ARGUS_INVITE_UNIVERSAL_LINK_ENABLED` all `false` in the xcconfig and in both built Info.plists (`ARGUS_AUTH_ENABLED` also false) | | $R/s3-ios-build/strings-check.txt |
| 5 | Mac pass checks | `OUT_DIR=$R/s5-macpass-checks lockf -k mac-sim.lock ios/scripts/cuadrao-design-mac-pass.sh checks` | `== checks: ok`, all 8 runners pass including `run_home_balance` (failed to compile at baseline) and the new `run_release_updates`, `run_release_identity` | 19 s | $R/s5-macpass-checks/run.log |
| 5 | auth-on welcome check (the only part of mac-pass `tests` not in the full suite) | the script's own second command: `TEST_RUNNER_ARGUS_TEST_AUTH_UI_ENABLED=true SIMULATOR_ID=8AFB... RESULT_DIR=$R/s5-auth-on lockf -k mac-sim.lock ios/scripts/verify.sh test -collect-test-diagnostics never -only-testing:ArgusFoundationUITests/CuadraoSignInPresentationUITests/testDefaultLaunchOffersNoAppleSignIn ARGUS_AUTH_ENABLED=true ARGUS_API_URL=http://127.0.0.1:9 ... ARGUS_APPLE_SIGN_IN_ENABLED=false ARGUS_GOOGLE_SIGN_IN_ENABLED=false` | **passed** (14.4 s), TEST SUCCEEDED | 22 s | $R/s5-auth-on/driver.log |
| 4 | full iOS UI suite | `cd <candidate> && SIMULATOR_ID=8AFB6084-8918-416E-9164-E21061306BEC RESULT_DIR=$R/s4-ios-test lockf -k ~/.claude/orchestrate/cuadrao-iphone-candidate/mac-sim.lock ios/scripts/verify.sh test -collect-test-diagnostics never` (verify.sh passes extra arguments to xcodebuild, so the flag went in directly) | **167 executed: 116 passed, 48 skipped, 3 failed**; `** TEST FAILED **`, exit 65; **15** never-idle waits | **65.4 min** (00:33:22 to 01:38:43; xcodebuild 3908 s) | $R/s4-ios-test/driver.log, test-20261004T053322Z.xcresult, per-class.txt |
| 4 | focused rerun of the 3 failures, once | same command with `-only-testing:` the three tests | 1 passed (Voice), **2 failed again** (Profile feedback, receipt location) | 118 s | $R/s4b-focused/driver.log |

Observation from stage 3 (not a listed requirement): Release still contains `--cuadrao-design` and `--design-gallery`. `CuadraoDesignPreview.isActive` (ios/ArgusFoundation/Cuadrao/CuadraoDesignPreview.swift:10) reads `--cuadrao-design` without a `#if DEBUG`, so a Release build opens the sample-data design canvas when launched with that argument. A shipped app cannot be given launch arguments by a user, so this is reachable only from Xcode or `simctl`/`devicectl`. W4's note that "the preview host is DEBUG-only" is true for `--cuadrao-release-ui` and the harnesses, not for the design canvas.

## Stage 4: UI suite failures, classified

Contention during the suite: the candidate Release build (118 s), the two walk builds (76 s), the backend container stages (pytest 352 s, real-PG 299 s) and the baseline trace extraction ran beside it in the first 15 minutes, as the brief allowed. No other simulator or UI test ran (the Mac lock was held by the suite throughout). From about 00:50 to 01:38 nothing else ran.

| Test | First assertion | Full suite | Focused rerun | Baseline (integration a8c37d3a) | Class |
|---|---|---|---|---|---|
| `CuadraoProfileFollowupUITests/testFeedbackPreservesKindsAndPartialDrafts` | `CuadraoProfileFollowupUITests.swift:226: XCTAssertTrue failed` (the `reveal` helper's final `XCTAssertTrue(element.isHittable)`: after typing the bug title and swiping, `cuadrao.feedback.save` never became hittable in 10 drags) | failed, 34 s | **failed**, 33 s | passed (50 s) in the baseline full suite | **NEW on this candidate.** Reproduces alone. Neither `CuadraoFeedbackPage.swift` nor this test's body changed versus integration (`git diff a8c37d3a...HEAD` on the page is empty), so the cause is in a shared path the candidate changed (Profile canvas and rows in DEBUG, `fd408c62c`/`26055a281`, or the whole-row tap change `feaca9bf7`), or the keyboard and scroll interaction. W1 recorded the same test failing twice at 860a6044 and later passing (`docs/reports/evidence/cuadrao-release-ui/2026-10-03-w1/focused-pickup-items.txt`, `focused-feedback.txt`), so it is timing-sensitive; on this head it fails every time it ran (2 of 2). User impact unproven: a person who cannot scroll Save above the keyboard would feel it. Not root-caused here. |
| `CuadraoReceiptPermissionUITests/testAllowedLocationCanBeRemoved` | `CuadraoReceiptPermissionUITests.swift:21: XCTAssertTrue failed` (`Remove location` did not appear within 15 s after "Allow While Using App") | failed, 44 s | **failed**, 44 s | passed in the baseline full suite | **Environment (confirmed).** W1 and the #790 evidence README record that this test needs a simulator location and passes once one is set; no candidate change touches location (the only receipt change is the currency row's tap area). One extra run with the location set, under the lock: `xcrun simctl location 8AFB... set 18.4861,-69.9312`, then `verify.sh test -collect-test-diagnostics never -only-testing:.../testAllowedLocationCanBeRemoved`, then `simctl location ... clear`: **passed (43.6 s)**, `$R/s4c-location/driver.log`. This is an environment-controlled run, not a flake retry. |
| `CuadraoVoiceDesignUITests/testLockedRecordingAndCleanAttachments` | `CuadraoVoiceDesignUITests.swift:155: XCTAssertTrue failed` (`voice-message-stop` not within 3 s of locking a recording) | failed, 14 s | **passed**, 31 s | passed | **Flake.** Passes alone; W2 listed it among contended-window failures earlier. |

The baseline's five failures, on this head:

| Baseline failure | Candidate full suite | Note |
|---|---|---|
| `CuadraoConsistencyUITests/testMoneyEntryAndBlankCreationSpanish` | **passed** (26 s) | fixed since baseline (`00b5be65a` money fields keep every keystroke) |
| `CuadraoGroupDesignUITests/testSharedJourneySpanish` | **passed** (62 s) | fixed (`3842099a6`, `92fa37bc1`) |
| `CuadraoHistoryDesignUITests/testScanAndEnglishParity` | **passed** (28 s) | fixed (`c6b63c310`) |
| `CuadraoReceiptUITests/testReceiptShowsYouOweWhenAnotherPersonPaid` | **passed** (38 s) | fixed (`2351ea3b1` picks Ana from the payer menu) |
| `FinancialLoopUITests/testSharedPlanningFourKindsPrivateContributionsCorrectionsAndReopen` | **skipped** | now skips without its seeded backend (`0083a7c88`); not run, so not proven fixed |

No fixed-since-baseline test fails on this head.

Never-idle ("App animations complete notification not received"): **15**, all in one test, `CuadraoContextUITests/testGroupContextPreservesDraftAttachmentsAndReturn` (after `typeText` into `chat-composer`; the test still passed). Baseline: 49 (31 in `CuadraoHistoryDesignUITests/testRecentsActionsAndRecovery`, 10 in `CuadraoVoiceDesignUITests/testVoiceStaysAvailableAcrossSheetsAndSurfaces`, 7 in `CuadraoSupportUITests/testFirstUseSavedChatAppearsInSearch`, 1 in `FoundationUITests/testAppearancePersistsAcrossRelaunch`), and 0 in the Context test. On this head those three baseline tests had no waits (Recents passed in 43 s versus about 30 min). The Context test's 15 waits are new on this head; each costs 60 s, so about 15 of the 65 minutes.

Comparison with the contended baseline: 135 tests, 82 passed, 48 skipped, 5 failed, 49 waits, 89.5 min. This head: 167 tests (+18 `InvitationsUITests`, +13 `ReleaseUIJourneyTests`, +1 `CuadraoProfileFollowupUITests/testReleaseGatesHideUnfinishedRowsAndPhotos`; per-class diff in $R/s4-ios-test/per-class.txt versus baseline-per-class.txt), 116 passed, 48 skipped, 3 failed, 15 waits, 65.4 min. Because the baseline ran contended and this run was mostly alone, the wall-time difference is not a performance claim.

## Stage 6: connected walk (iPhone 17e 8B7975F1, live local backend)

Method, as W7 ran it: API in the `cuadrao-py310-runner` container from THIS worktree's `src/` (read-only mount; venv `cuadrao-py310-venv-75e2998a73` built from this tree's lock file), flags on (`ARGUS_HOUSEHOLDS_ENABLED`, `ARGUS_FINANCIAL_ACCOUNTS_ENABLED`, `ARGUS_BETA_INVITES_ENABLED`, `ARGUS_BETA_INVITE_GATE_ENABLED`; universal link off), throwaway invite secret, founder = local user A, provider keys empty. Script: `$R/s6-walk/walk-api.sh`, a copy of `probes/w7-api.sh` with only the worktree, container name, log dir and venv changed (diff in the run log). Local Supabase `argus-qa`, CLI 2.109.0, reset before the walk. Users created through real local GoTrue sign-up by `$R/s6-walk/walk_setup.py`, which imports W7's `w7_live_invites.py` helpers (same `http`, `redact`, `Probe` sign-in) and writes redacted exchanges to `$R/s6-walk/exchanges.jsonl`.

App: Debug from the candidate worktree, derived data `/private/tmp/claude-501/cuadrao-candidate-dd/walk-on` and `walk-off` (outside the repo), configured only by the out-of-tree `$R/s6-walk/sim.xcconfig` (W7's, bundle `local.argus.w7invites`, auth on, API 127.0.0.1:18790, local Supabase, captcha page in pass mode on 18795) plus the build setting `ARGUS_BETA_INVITES_ENABLED=true` (or `false`) on the `xcodebuild` command line. Both BUILD SUCCEEDED; built Info.plists read `ARGUS_BETA_INVITES_ENABLED` true and false. No repo file was written. Launched with `-AppleLanguages (es-419)`. All driving ran inside one lock holder: acquired 01:46:31, released 01:59:19 (`$R/s6-walk/sim-lock.log`). The test app was uninstalled before release.

One harness addition: to make only the first `/invites/access` check fail while sign-in and `/me` work, the API ran on 18791 behind `$R/s6-walk/access_fault_proxy.py` on 18790, which closes the connection for that one route while a flag file exists and forwards everything else (its request log, `proxy-flag-on.log` and `proxy-flag-off.log`, is the app's request record). Reason: with the whole API stopped, the app cannot reach the gate at all (see the first two rows), so a stopped API cannot exercise the gate's retry state.

| Journey | Result | Evidence ($R/s6-walk/sim/) |
|---|---|---|
| Sign in with the API stopped | App stays on the sign-in screen with "No pudimos conectar" and Reintentar; login goes through the API (`POST /api/v1/auth/login`), so no GoTrue call is made. Not the app. | `02-api-stopped-first-check.png` |
| Relaunch, already signed in, API stopped | App shows the signed-out welcome (Crear cuenta / Iniciar sesión) because session restore needs `/me`; no spinner, not the app. With the API back and a relaunch, the same session opens straight to the gate, so the session was kept | `04-relaunch-api-stopped.png`, `05-api-back-no-relaunch.png`, `06-relaunch-api-up.png` |
| Gate shown to a non-admitted user | PASS. "Tu invitación a Cuadrao." from live `GET /invites/access` (`admitted:false`) | `03-gate-non-admitted.png` |
| First access check fails (connection closed), `/me` works | PASS. Closed retry screen "No pudimos comprobar tu acceso a la beta. Revisa tu conexión e intenta de nuevo." with Reintentar and Cerrar sesión; the app did not open. Three failed `/invites/access` attempts logged. Reintentar after the fault was cleared showed the gate | `07-first-access-check-fails.png`, `08-retry-shows-gate.png` |
| Valid code admits | PASS. Typed the beta code from A (without dashes), `POST /invites/redeem 200`, access re-read, the app opened on Home. Server: `admitted:true` | `09-gate-code-typed.png`, `10-after-code.png` |
| Personal invite quota 10 to 9, code shown once, no link | PASS. "Te quedan 10 de 10" then `POST /invites 201` and "Te quedan 9 de 10" with the code; the share sheet carries the code text only; the server's create response for beta invites has `link: null` (A's create in the same run, `exchanges.jsonl` seq 1); server sent list `{limit 10, used 1, remaining 9}`, one `beta` row `pending`. Reopening the screen in the same app session still shows the code; after a relaunch it shows no code and the Create button again | `13`, `14`, `15`, `16-share-sheet.png`, `17-hub-after-create.png`, `18-personal-invite-reopened.png`, `32-invite-screen-after-relaunch.png` |
| Join a Household by code | PASS. Hogar, Administrar espacios, Unirte con una invitación, code, Revisar invitación (`POST /household-invitations/preview 200`, "Casa Candidata"), name, Aceptar (`POST /household-invitations/accept 200`); members Ana (Administrador) and Gabi | `19` to `24` |
| Open the join step over an existing Household | PASS with a finding. The menu lists Crear hogar, Unirte con una invitación and Casa Candidata. The join step opens with an empty code field, but **still shows the previous review card** ("Casa Candidata", name field, Aceptar invitación greyed) from the invitation just accepted. Typing a new code cleared it; reviewing it showed "Casa Segunda" (not accepted) | `25-join-step-over-existing.png`, `26`, `27` |
| Member whose account grant is revoked opens that account | **Membership: PASS. Message: FAIL.** Granted G view of "Cuenta Ana" (row showed "USD 250.00, Solo lectura"), revoked by API (`GET .../accounts/{id}` now 404, `GET /households/{id}` 200), then tapped the row. The app re-read the Household (200), stayed on Casa Candidata as a member, and the account left the list. No message appeared; `household.changed` ("Los permisos del hogar cambiaron. Recarga y revisa otra vez.") was not shown. Cause, from code: revoking the grant bumps the snapshot's authorization version, so `refresh()` calls `clear()`, which replaces `generation`; `open(_:)` then fails `current(ticket, identity)` (HouseholdModel.swift:108 to 110, 66 to 67) and never sets the message. A person sees the account vanish without being told why | `28-hogar-with-shared-account.png`, `29-open-revoked-account.png`, `30-after-revoke-settled.png` |
| Profile in this DEBUG build | PASS for what the connected Profile has: Apariencia, Privacidad y términos, Invitaciones, and "Editar avatar" opening the editor with "Elegir foto" and the avatar list (Icono de perfil, Iniciales, Sol, Hoja, Luna, Estrella). The connected Profile has only these three rows by design (ConnectedCuadraoProfile.swift); the unfinished rows (personalization, security, usage and others) live in the design-canvas Profile, which `CuadraoProfileFollowupUITests/testReleaseGatesHideUnfinishedRowsAndPhotos` covers and which passed in stage 4. The design canvas could not be opened from this auth-on build (`--cuadrao-design` showed the welcome screen) | `11-profile.png`, `31-avatar-editor.png` |
| Client flag off | PASS. Same bundle and session, `ARGUS_BETA_INVITES_ENABLED=false`: the signed-in shell (Hogar, Casa Candidata) was on screen at the first capture about 3.5 s after launch, and the app sent `/me`, `/households`, `/financial-accounts`, `/financial-plan` and Household reads, **no `/invites` request of any kind** (0 in `proxy-flag-off.log`). Profile has no Invitaciones row. A spinner shorter than 3.5 s could not be excluded by screenshots; by code the gate host and its ProgressView are not mounted when `auth.invitations` is nil | `33-flag-off-first-frame.png`, `34-flag-off-shell.png`, `35-flag-off-profile.png` |

Other observations from the walk: the Profile footer still says "Las pantallas financieras siguen mostrando ejemplos locales, no tus finanzas" in the connected app (W7 note (d), unchanged). The personal invite screen says "Compartir el enlace no significa que la persona ya aceptó" while no link exists (beta invites are code only). The es-419 hardware key map still turns `@` into `"` when typed by automation; the email was fixed with the on-screen `@` key.

## Stage 7: lag, before and after (Debug, iPhone 18 Pro simulator; these are not iPhone 15 numbers)

Baseline: `baseline/run8-lag` did complete (W4's queued job, 22:02), so it was not rerun. Its summaries were empty because `probes/summarize_time_profile.py` reads a `backtrace` column and searched for the display name "Argus Sample", while Xcode 27 exports `tagged-backtrace` and the process is named `ArgusFoundation`. Both trace sets were re-summarized with the same fixed reader: `$R/s7-lag/lag-extract.sh` and `$R/s7-lag/summarize_tp2.py` (baseline output in `$R/s7-lag/baseline-resummarized/`, candidate in `candidate-summarized/`; the first attempt with empty frames is kept as `baseline-resummarized-v1-emptyframes/`). Candidate run: `lockf -k mac-sim.lock lag-measure.sh <candidate> 8AFB6084-... $R/s7-lag/candidate`, exit 0, 285 s.

| Measure | Baseline a8c37d3a | Candidate 4af8fced |
|---|---|---|
| xctrace App Launch wall (8 s window + tool overhead), 5 runs | 19.72, 18.76, 17.77, 16.92, 18.19 s | 20.26, 18.04, 19.44, 17.53, 17.51 s |
| `simctl launch` round trip (spawn only), 5 runs | 132, 124, 132, 129, 131 ms | 134, 132, 133, 132, 131 ms |
| Main-thread busy span at cold launch (first to last main-thread sample), 5 runs | 1379, 2827, 2942, 2965, 2858 ms (median 2858) | 2810, 3266, 2815, 2844, 1872 ms (median 2815) |
| Idle populated Home, 20 s Time Profiler, app main thread | 2 ms (rests) | 2 ms (rests) |
| Interactions (same 4 UI tests under Time Profiler), app main thread | 37.4 s over a 92.4 s span; Plan test failed | 38.9 s over a 79.1 s span; all 4 passed |
| Potential hangs in the interactions trace | 32 | 37 |
| Top named main-thread frames (interactions) | run loop 28.0 s; `__CFRunLoopDoBlocks` 15.4 s; `CA::Layer::perform_update_` / `-[CALayer layoutSublayers]` 11.6 s; `CA::Transaction::flush()` 10.6 s | run loop 29.6 s; `__CFRunLoopDoBlocks` 13.9 s; `CA::Layer::update_if_needed_` / `-[CALayer layoutSublayers]` 12.6 s |
| Animation Hitches template on the simulator | unsupported (exit 19) | unsupported (exit 19) |

Reading: no measurable change between the two heads on this Mac. Cold launch is dominated by simulator dyld preparation (`_dyld_sim_prepare` holds about 6.9 s of launch 1's weighted samples in both). In interactions, the heaviest named main-thread work is Core Animation layout (`layoutSublayers`, about 12 s of 38 s in both); most SwiftUI and UIKit frames are unsymbolicated addresses in this export, and no frame from the app's own binary reached the top 20, so no app function is implicated. The per-sample weights in the App Launch traces are not physically consistent (main-thread totals above the sample span), so only the span and the shapes are compared. Simulator Debug numbers do not represent the iPhone 15.

## Stage 8: device

`xcrun devicectl list devices`: "Sr.Garces i15" (00008120-001428C90E04201E) **unavailable** (also iWatch Ultra). Nothing was installed and no journey is claimed.

Signed build produced anyway, as W4 describes, under the lock (`$R/sim-chain.sh`, first step), exit 0, 31 s, BUILD SUCCEEDED:

```bash
cd /Users/garces/Documents/projects/repos/argus/.claude/worktrees/cuadrao-candidate
lockf -k ~/.claude/orchestrate/cuadrao-iphone-candidate/mac-sim.lock xcodebuild build -project ios/ArgusFoundation.xcodeproj \
  -scheme ArgusFoundation -configuration Debug -sdk iphoneos \
  -derivedDataPath /private/tmp/claude-501/cuadrao-candidate-dd/device \
  -xcconfig ~/.claude/orchestrate/cuadrao-iphone-candidate/baseline/device-build/device-preview.xcconfig \
  CURRENT_PROJECT_VERSION=3421
```

Artifact: `/private/tmp/claude-501/cuadrao-candidate-dd/device/Build/Products/Debug-iphoneos/ArgusFoundation.app`, copied with `ditto` to `$R/s8-device/ArgusFoundation.app` (70 MB) so a cleared /private/tmp does not lose it; `codesign --verify --strict` passes on both. Read back: bundle `local.cuadrao.design.47R3855RTJ`, build **3421**, version 0.1.0, display name "Argus Sample" (W4's shape; build 3420 used a device-only Info.plist copy to show "Cuadrao Preview", which this did not reproduce, so the home-screen label would change from Cuadrao Preview to Argus Sample), `CUADRAO_DESIGN_PREVIEW` true, `ARGUS_AUTH_ENABLED` false, `ARGUS_BETA_INVITES_ENABLED` false. Signed by "Apple Development: garceslg3@icloud.com", team 47R3855RTJ, embedded profile "iOS Team Provisioning Profile: local.cuadrao.design.47R3855RTJ", **expires 2026-10-08T00:57:13Z (Oct 7, 19:57 CDT)**. No provisioning or trust change.

When the phone is connected, unlocked and trusted:

```bash
xcrun devicectl list devices    # expect "Sr.Garces i15" available
lockf -k ~/.claude/orchestrate/cuadrao-iphone-candidate/mac-sim.lock xcrun devicectl device install app \
  --device 00008120-001428C90E04201E ~/.claude/orchestrate/cuadrao-iphone-candidate/candidate-4af8fced/s8-device/ArgusFoundation.app
xcrun devicectl device info apps --device 00008120-001428C90E04201E --bundle-id local.cuadrao.design.47R3855RTJ
lockf -k ~/.claude/orchestrate/cuadrao-iphone-candidate/mac-sim.lock xcrun devicectl device process launch \
  --device 00008120-001428C90E04201E local.cuadrao.design.47R3855RTJ
# optional arguments: --cuadrao-release-ui (DEBUG release-flow review host), --cuadrao-release-gates (release Profile set)
```

What a phone test with this bundle can and cannot exercise. This is the standalone design preview (`CUADRAO_DESIGN_PREVIEW=true`) with auth disabled, so it opens straight into the populated sample-data canvas. It can show: the Cuadrao artwork, typography, Home chart swipes and periods, tabs, sheets, transitions, the Plan, Group, Receipt and History design surfaces with sample data, the full DEBUG Profile (every unfinished row and the avatar editor with photos), and, launched with `--cuadrao-release-ui`, the DEBUG release-flow review host with fixture outcomes (gate states, invitations, deletion copy, Updates). Feel and frame pacing on real hardware are the main things only the phone gives. It cannot exercise anything connected: no sign-in, no beta gate from a real server, no invitation create or redeem, no Household join, no grants, no account deletion, no real accounts, because there is no session and no API. A connected phone build would need: `ARGUS_AUTH_ENABLED=true` and `CUADRAO_DESIGN_PREVIEW=false`; an API base URL the phone can reach (not 127.0.0.1: the Mac's LAN address with the API bound to 0.0.0.0 and the port open, or a hosted URL); a Supabase URL and anon key the phone can reach (the local stack on the Mac's LAN address, or hosted); a captcha or web URL reachable from the phone; `ARGUS_BETA_INVITES_ENABLED=true` for the gate; and an App Transport Security allowance for plain http on a LAN address, or https. Universal links additionally need the AASA file and Associated Domains on a signed App ID, which the free team cannot provide. Any of these is a configuration change the founder would need to approve; none was made.

## Stage 5: Mac pass screens

`SIMULATOR_ID=8AFB... OUT_DIR=$R/s5-macpass-screens lockf -k mac-sim.lock ios/scripts/cuadrao-design-mac-pass.sh screens`: `== screens: ok`, exit 0, 107 s; baseline 2185aefe build and head build both BUILD SUCCEEDED; the script's temporary worktree was removed (`git worktree list` shows no `baseline-src`). 12 launch screenshots plus `compare.txt` in `$R/s5-macpass-screens/screens/`:

```
default-light: identical files
default-dark: identical files
design-light: files differ; compare by eye (install ImageMagick for a pixel count)
design-dark: files differ; compare by eye (install ImageMagick for a pixel count)
```

Same verdicts as the baseline run (run7). Against the baseline run's own screenshots (`$R/s5-macpass-screens/vs-baseline-run7.txt`), 10 of 12 files are byte-identical; only `after-design-home-light/dark` differ, and by eye the only difference is the sample chart's date range (3 sept to 3 oct at baseline, 7 sept to 4 oct today), because the sample data is relative to today.

## Housekeeping (stage 9)

- API containers stopped (`cand-api` on 18790 and on 18791 both removed); fault proxy and captcha server stopped.
- Local Supabase `argus-qa` reset from the candidate worktree with CLI 2.109.0 at 02:00: 111 migrations, max 20261004090000, 0 auth users (`$R/s6-walk/supabase-reset-after.log`). Line 1 of `reports/W4.md` reads `SUPABASE: free (last owner candidate-verifier, reset 02:00 CDT 2026-10-04)`.
- Walk bundle `local.argus.w7invites` uninstalled from iPhone 17e; that simulator holds only `local.argus.foundation` and its UI test runner, as before. The simulator location on iPhone 18 Pro was set for the one location run and cleared after it.
- Throwaway secrets deleted (`.invite-secret`, `.users.json`, `.secrets.json`). Test codes visible in screenshots belonged to the now-reset database.
- Candidate worktree clean at 4af8fced. Derived data left outside the repo: `/private/tmp/claude-501/cuadrao-candidate-dd/{release,walk-on,walk-off,device}`.
- One unplanned pull: `docker run alpine` (official image from Docker Hub) to list the web node_modules volume. Nothing else was downloaded.

## Comparison with baseline (integration a8c37d3a)

| Area | Baseline | Candidate 4af8fced |
|---|---|---|
| Backend full suite | 10216 passed, 1081 skipped, 0 failed | 10231 passed (+15 gate tests), 1081 skipped, 0 failed |
| Real PG (CLI 2.109) / auth matrix | 605 / 13, gate passed | 605 / 13; gate now prints passed/failed/error/skip counts, exit 0 |
| Web | 2207 pass, build, Playwright 2 | same |
| Mac pass checks | 5 of 6 runners (home balance did not compile) | 8 of 8 runners |
| UI suite | 135 tests: 82 passed, 48 skipped, 5 failed; 49 never-idle; 89.5 min contended | 167 tests: 116 passed, 48 skipped, 3 failed; 15 never-idle; 65.4 min mostly alone |
| Lag | see stage 7 | no measurable change |

## Findings for the lead (not fixed; verifier changes no code)

1. NEW UI failure, reproduces 2 of 2: `CuadraoProfileFollowupUITests/testFeedbackPreservesKindsAndPartialDrafts` (`CuadraoProfileFollowupUITests.swift:226`, Save not hittable after scrolling with the keyboard up). Passed at baseline. Not root-caused.
2. Revoked-grant message missing (connected walk): after `open(_:)` meets a 404 for a revoked account, the membership re-read keeps the person in the Household, but the grant revocation changes the authorization version, `refresh()` calls `clear()`, the generation changes, and `open(_:)` no longer sets `household.changed`. Smallest fix: set the message from the refresh result instead of the stale ticket, or keep the ticket across the version-change `clear()`. The B1 fix itself (membership kept) works.
3. Stale review card when reopening the join step over an existing Household (shows the just-accepted "Casa Candidata" review until a new code is typed).
4. Never-idle moved: 15 waits now all in `CuadraoContextUITests/testGroupContextPreservesDraftAttachmentsAndReturn` (0 at baseline); about 15 minutes of suite time.
5. Release builds still honour `--cuadrao-design` (design canvas not DEBUG-gated). Not user-reachable without launch arguments.
6. Personal invite screen keeps showing the code when reopened in the same app session (gone after relaunch); copy mentions "el enlace" though beta invites have no link. Profile footer still says the financial screens show local examples.
7. `probes/summarize_time_profile.py` cannot read Xcode 27 exports (`tagged-backtrace`) and `lag-measure.sh` passes the display name, so baseline main-thread tables were empty; `$R/s7-lag/summarize_tp2.py` and `lag-extract.sh` fix it out of tree.
8. Container `bun install` into the per-worktree web node_modules volume failed extracting `next`; pytest was unaffected this time.

## Not verified

- No phone journey: the iPhone 15 was unavailable; nothing was installed on it. Installation alone would not prove a journey either.
- The design-canvas Profile's unfinished rows were not walked by hand in the connected build (the auth-on build shows the welcome for `--cuadrao-design`); they rest on the passing UI test `testReleaseGatesHideUnfinishedRowsAndPhotos`.
- The flag-off "no spinner" claim is from a screenshot about 3.5 s after launch plus code reading; a sub-3.5 s spinner was not excluded by recording.
- The "offline at first check" journey used a fault proxy that closes only `/invites/access`; a real network loss with `/me` cached was not simulated. With the whole API stopped the app shows the sign-in error or the welcome, never the app.
- Universal links, AASA, TestFlight, hosted GoTrue/Turnstile/rate limits: not provable locally (as W7).
- `FinancialLoopUITests/testSharedPlanningFourKindsPrivateContributionsCorrectionsAndReopen` now skips without its seeded backend, so it is not proven fixed.
- Root cause of finding 1 and of the Context never-idle waits.
- Animation hitches: the simulator does not support the template; device-only.
- TestFlight readiness is not claimed.
