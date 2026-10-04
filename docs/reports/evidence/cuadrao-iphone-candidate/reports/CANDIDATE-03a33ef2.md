# Candidate verification: claude/cuadrao-iphone-candidate at 03a33ef2be86cd86f4ad65c51d3e95a08a0e7ba8

Status: DONE 13:50 CDT 2026-10-04 (started 12:31), except one open item: a helper's by-eye classification of about 80 non-target differing screenshots had not returned when this was written (see Not verified). Verifier only: no product change, no commit, no push.

Summary. Every stage passes on this head. The full UI suite ran once, alone: 167 tests, 119 passed, 48 skipped, 0 failed, 0 never-idle waits, 46.2 min, `** TEST SUCCEEDED **`. Both earlier in-suite failures passed in-suite (Group 63.4 s, Voice lock 29.2 s). `testFirstUseSavedChatAppearsInSearch` took 22.1 s. Money strings match the 2520da49 run on every Home, chart, highlights and Search screenshot I compared. One difference is not run-to-run noise: after the same first drag on Home, this head settles in about 0.8 s where 4af8fced and 2520da49 took about 2.8 s, and the screen ends at a different scroll offset. Signed build 3428 is saved and was not installed.

Worktree `/Users/garces/Documents/projects/repos/argus/.claude/worktrees/cuadrao-candidate`. Logs under `~/.claude/orchestrate/cuadrao-iphone-candidate/candidate-03a33ef2/` (written below as `$N`). Earlier logs untouched.

## Scope proof

`git diff --name-only 0408469..03a33ef2 -- . ':!docs/reports/evidence'` (`$N/s1-static/changed-files.txt`):

```
docs/specs/lanes/mvee-five-lane-handoff.md
ios/ArgusFoundation/Cuadrao/CanvasMoney.swift
ios/ArgusFoundation/Cuadrao/CuadraoBalanceHistory.swift
ios/ArgusFoundation/Cuadrao/CuadraoBalancePeriod.swift
ios/ArgusFoundation/Cuadrao/CuadraoHomeBalanceChart.swift
ios/ArgusFoundation/Cuadrao/CuadraoHomeInsights.swift
ios/ArgusFoundation/Cuadrao/CuadraoSearchCanvas.swift
ios/ArgusFoundation/Cuadrao/CuadraoSpendingHighlights.swift
ios/ArgusFoundationUITests/CuadraoGroupDesignUITests.swift
ios/ArgusFoundationUITests/CuadraoVoiceDesignUITests.swift
ios/DesignPreviewTests/HomeBalanceChecks.swift
ios/DesignPreviewTests/MoneyFormatChecks.swift
ios/DesignPreviewTests/run_money_format.py
ios/scripts/cuadrao-design-mac-pass.sh
```

Outside `ios/` and evidence, only `docs/specs/lanes/mvee-five-lane-handoff.md` changed. Against 4af8fced (the last head with backend results) the files outside `ios/` and evidence are `.agent/designs/cuadrao/DESIGN.md`, `docs/specs/argus-execution-board.md` and that handoff doc. No backend, web, migration or `scripts/` file changed, so the 4af8fced backend full suite (10231 passed), real Postgres (605), auth matrix (13), web (2207) and OpenAPI results stand and were not rerun. The host check group has three changed files, not two (`run_money_format.py` is the third).

## Stage table

| # | Stage | Command | Result | Wall | Log |
|---|---|---|---|---|---|
| 1 | docs links | `uv run --with markdown-it-py python scripts/check_docs_links.py --base a8c37d3a182fbdb3228f6003272418e65286bc1a` (host). uv wrote `uv.lock` and `.venv/`; both deleted, ignored-file listing matches the one taken before | "Checked local links in 14 changed document(s).", exit 0 | under 1 s | $N/s1-static/docs.log |
| 1 | diff check | `git diff --check a8c37d3a...HEAD` | clean, exit 0, 0 lines | | $N/s1-static/diff-check.log |
| 1 | modularity | container `python scripts/check_modularity_budget.py` | Budget violations: none | 3 s | $N/s1-static/modularity.log |
| 1 | doc-reading Python tests (container) | the same ten files as at 2520da49 | 144 passed, 3 skipped (census real-PG, no database), same as 2520da49 | 26 s | $N/s1-static/doc-pytest.log |
| 1 | doc-reading web tests (host bun) | `bun test __tests__/account-deletion-api.test.ts __tests__/chat-next-move-rows.test.ts` | 46 pass, 0 fail | under 1 s | $N/s1-static/web-doc-tests.log |
| 2 | iOS Debug build | `SIMULATOR_ID=8AFB... ios/scripts/verify.sh build` | BUILD SUCCEEDED | 14 s | $N/s2-ios-build/debug-build.log |
| 2 | iOS Release build | `xcodebuild build ... -configuration Release -destination 'generic/platform=iOS Simulator' -derivedDataPath /private/tmp/claude-501/cuadrao-candidate-dd/release CODE_SIGNING_REQUIRED=NO` | BUILD SUCCEEDED | 57 s | $N/s2-ios-build/release-build.log |
| 2 | Release strings | `$N/s2-ios-build/strings-check.sh` (`strings -a` over every Mach-O) | Release (1 Mach-O): `--cuadrao-release-gates` 0, `--cuadrao-release-ui` 0, `--invitations-harness` 0, `InvitationsHarness` 0, `InvitationsStubServer` 0, `ReleaseUIReview` 0, `--cuadrao-design` 0. Debug control (3 Mach-O): 1, 1, 1, 5, 2, 4, 1. `--design-gallery` still 2 in Release, as at 2520da49 | | $N/s2-ios-build/strings-check.txt |
| 2 | Client flags | `ios/Config/Development.xcconfig` and both built Info.plists | `ARGUS_AUTH_ENABLED`, `ARGUS_APPLE_SIGN_IN_ENABLED`, `ARGUS_GOOGLE_SIGN_IN_ENABLED`, `ARGUS_BETA_INVITES_ENABLED`, `ARGUS_INVITE_UNIVERSAL_LINK_ENABLED` all false in the xcconfig and in the Release and Debug Info.plists | | $N/s2-ios-build/strings-check.txt |
| 3 | Mac pass checks | `OUT_DIR=$N/s3-macpass-checks ios/scripts/cuadrao-design-mac-pass.sh checks` (swiftc only, no simulator, no lock) | `== checks: ok`, 10 of 10 runners pass. `run_tap_targets`: "plain-style statements: 127, without a content shape: 44, reviewed: 44, unreviewed: 0, stale entries: 0". New `run_money_format`: "Passed 12157 money format checks" for the default locale and each of en_US, es_419, es_DO, es_US, ja_JP, de_CH, ar_KW, en_US@currency=JPY (9 runs) | 42 s | $N/s3-macpass-checks/run.log, design-preview-checks.log |
| 4 | full iOS UI suite (reason for a full run: seven app files on the most-used screens changed, and the voice and group test fixes are only proven in-suite) | `$N/s4-ios-test/run.sh`: inside one `lockf -k mac-sim.lock` holder, `simctl location 8AFB... set 18.4861,-69.9312`, `SIMULATOR_ID=8AFB6084-8918-416E-9164-E21061306BEC RESULT_DIR=$N/s4-ios-test ios/scripts/verify.sh test -collect-test-diagnostics never`, `simctl location ... clear` | **167 executed: 119 passed, 48 skipped, 0 failed**. `** TEST SUCCEEDED **`, exit 0. **0** never-idle waits. Per-class counts identical to 2520da49. Nothing else heavy ran on the Mac. No focused rerun needed | **46.2 min** (12:38:17 to 13:24:27; xcodebuild 2758 s) | $N/s4-ios-test/driver.log, test-20261004T173817Z.xcresult, per-class.txt, durations-vs-2520da49.txt |
| 5 | suite screenshots vs 2520da49 | `xcresulttool export attachments`, then `$N/s5-attachments/compare.py`, `metrics.py`, `ocr-compare.sh` (Vision OCR of both sides), `sidebyside.py` | 273 pairs: 181 byte-identical, 92 differ. See Screenshot comparison | | $N/s5-attachments/compare.tsv, metrics.tsv, ocr-diff.txt, ocr-summary.tsv, comp/ |
| 6 | device build 3428 | see Device | BUILD SUCCEEDED, signed, verified, not installed | 12 s | $N/device/build.log, readback.txt |
| 7 | worktree clean | `git status --porcelain --ignored` at the end equals the listing taken before stage 1 | clean at 03a33ef2, up to date with origin, no untracked file | | $N/s1-static/status-before.txt |

## Device (stage 6)

Not installed, by instruction: the phone carries build 3427 for a pending profiling recording.

Built before the suite so nothing ran beside it. The build held the Mac lock for 12 s (12:37:57 to 12:38:09, `$N/device/lock.log`) because standing order 18 puts device builds under the lock.

```bash
cd /Users/garces/Documents/projects/repos/argus/.claude/worktrees/cuadrao-candidate
lockf -k ~/.claude/orchestrate/cuadrao-iphone-candidate/mac-sim.lock xcodebuild build -project ios/ArgusFoundation.xcodeproj \
  -scheme ArgusFoundation -configuration Debug -sdk iphoneos \
  -derivedDataPath /private/tmp/claude-501/cuadrao-candidate-dd/device-final \
  -xcconfig ~/.claude/orchestrate/cuadrao-iphone-candidate/baseline/device-build/device-preview.xcconfig \
  CURRENT_PROJECT_VERSION=3428 INFOPLIST_FILE=$N/device/device-Info.plist
```

Artifact: `$N/device/ArgusFoundation.app` (70 MB, `ditto` copy of `/private/tmp/claude-501/cuadrao-candidate-dd/device-final/Build/Products/Debug-iphoneos/ArgusFoundation.app`). `codesign --verify --strict` passes on both ("valid on disk", "satisfies its Designated Requirement"). Read back (`$N/device/readback.txt`): display name "Cuadrao Preview", bundle `local.cuadrao.design.47R3855RTJ`, build 3428, version 0.1.0, `CUADRAO_DESIGN_PREVIEW` true, `ARGUS_AUTH_ENABLED` false, `ARGUS_BETA_INVITES_ENABLED` false, universal link, Apple and Google sign-in false. Signed by "Apple Development: garceslg3@icloud.com", team 47R3855RTJ, profile "iOS Team Provisioning Profile: local.cuadrao.design.47R3855RTJ", expires 2026-10-08T00:57:13Z (Oct 7, 19:57 CDT). `device-Info.plist` is the 04084692 copy. Its only difference from `ios/Config/Info.plist` at this head is `CFBundleDisplayName` "Argus Sample" to "Cuadrao Preview". The build log compiled this head's changed sources (`CanvasMoney.swift`, `CuadraoHomeInsights.swift`).

Install later, when the recording is done:

```bash
lockf -k ~/.claude/orchestrate/cuadrao-iphone-candidate/mac-sim.lock xcrun devicectl device install app \
  --device 00008120-001428C90E04201E ~/.claude/orchestrate/cuadrao-iphone-candidate/candidate-03a33ef2/device/ArgusFoundation.app
```

## UI suite across baseline, 2520da49 and this head

| | Baseline a8c37d3a | 2520da49 | 03a33ef2 |
|---|---|---|---|
| Tests | 135 | 167 | 167 |
| Passed / skipped / failed | 82 / 48 / 5 | 117 / 48 / 2 | **119 / 48 / 0** |
| Never-idle waits | 49 | 0 | **0** |
| Wall | 89.5 min, contended | 49.9 min, contended in the first 10 min | **46.2 min**, alone |
| `CuadraoVoiceDesignUITests/testLockedRecordingAndCleanAttachments` | passed | failed in suite (`:155`), passed alone | **passed in suite, 29.2 s** |
| `CuadraoGroupDesignUITests/testSharedJourneySpanish` | failed | failed in suite (`:48`), passed alone | **passed in suite, 63.4 s**. No field value to quote, because no read-back failed |
| `CuadraoSupportUITests/testFirstUseSavedChatAppearsInSearch` | passed, 7 waits | passed, 24.0 s | **passed, 22.1 s**. The 441 s focused run earlier today did not recur |

All 167 tests pair by name with the 2520da49 run. The only status changes are the two tests above, failed to passed. Largest duration changes are those two (they now run to the end) and drops of 5 to 6 s in five tests. Sum of test durations: 2984 s then, 2758 s now. The 2520da49 run was contended at its start, so the wall difference is not a performance claim.

## Screenshot comparison with the 2520da49 suite (stage 5)

273 pairs: 181 byte-identical, 92 differ. 6 are new-only (the last shots of the Group and Voice tests, which failed before reaching them at 2520da49). The 4af8fced to 2520da49 comparison had 71 differing. 24 pairs differ now that were identical then (`$N/s5-attachments/now-differs.txt` against `prev-differs.txt`).

Target screens (Home, expanded chart, Insights and highlights, Search). 51 of the 75 pairs whose test or name matches Home, chart, Search, story, activity or distribution are byte-identical, including `quiet-home-es`, `home-type-es`, `search-type-es`, all five `story-*-es` highlight shots, `balance-change-breakdown-es`, `history-year-es`, `interactive-paging-balance-es`, `search-first-use-saved-chat-es` and every `search-*` shot from the Support tests. I opened the old, new and diff composite for each of these differing pairs:

| Screenshot | What differs | Class | Money strings |
|---|---|---|---|
| `home-inline-reorder-es`, `home-swipe-archive-es` (Polish) | Same layout, scrolled about 275 pt less at this head | **Not run-to-run noise.** See below | match where both show the row: 1,500.00, 3,020.00, 39,400.00, 68,000.00. New also shows DOP 153,920.00, 165,000, 153,000 (chart, scrolled off in old) |
| `activity-home-return-es` (Support) | Same layout, scrolled about 72 pt less | **Same cause** | match: 39,400.00, 3,020.00, 68,000.00, 18,500.00, 25,000.00, -2,450.00, -180.00 |
| `context-chart-selection-en` (and `chat-type-es`) | The "Tap to converse · Hold to record" hint under the composer is absent at this head | Persisted simulator state, not this diff. The hint is hidden once `@AppStorage("cuadrao.design.voice-entry-learned")` is true (`CuadraoChatCanvas.swift:17, 349`), no test resets it, and that file did not change since 2520da49. Focused voice runs earlier today are the likely setter. Not proven | none on screen |
| `story-highlight-dark-large-en` | about 2 pt scroll offset | noise | match: DOP 7,989.56, DOP 3,980.00, DOP 45,094.83 |
| `activity-dark-large-axis-en` | about 5 pt scroll offset | noise | match: 71,145.00, 12,388.00, 168,200.00, 24,726.00 and the four percentages |
| `distribution-dark-large-expanded-en` | "Peace of mind 44.2%" row brightness (press highlight fading) | noise | match: 3,020.00, 57,900.00, 93,000.00, 68,000.00 |
| `activity-year-es`, `activity-dark-large-en` | selected-period pill mid-animation in old, settled in new | animation timing | match: DOP 425,726.00, DOP 38,812.00, 149,267.00, 50,000 / 25,000 axis |
| `quiet-home-household-es` | "Hogar" label colour mid-transition in old | animation timing (differed at the last comparison too) | match: DOP 43,500.00, 47,000, 43,000, 18,500.00 |
| `activity-distribution-es`, `distribution-account-return-es` | one label colour, close-button ring | noise | match: DOP 40,502.00, DOP 1,769.00, 18,418.00, 2,210.00, 2,574.00; 3,020.00, 57,900.00, 39,400.00, 18,500.00, 93,000.00 |
| `distribution-dark-large-en`, `activity-week-es`, `story-empty-month-es`, `distribution-checking-es` | max delta 8 to 14 levels at the period control | sub-visible glass noise (metrics only, not opened) | OCR text identical |
| `dark-home`, `dark-search`, `search`, `spanish-large-home`, `spanish-large-search` (Foundation) | max delta 2 to 4 levels at the tab bar | tab glass noise (metrics only) | OCR text identical |

No money string differs in format (code, separators, decimals, sign) on any target screen I compared.

**The Home scroll difference.** Both tests use a `reveal` helper that drags from 65% to 40% of the screen until the row is hittable. The test logs show the same single drag at all three heads. Time from that drag to the next step: 2.77 s at 4af8fced, 2.77 s at 2520da49, **0.79 s at 03a33ef2**, in both tests. First element lookup after launch moved from about 5.8 to 6.2 s to about 4.3 to 4.4 s. So the first drag on Home now settles about 2 s sooner and the list travels less far. This is an effect of the app changes, consistent with their intent, and it changes where the screen rests after an identical gesture. I did not determine whether the old extra travel was a fling or a late layout. Layout and strings are otherwise the same.

OCR text differences elsewhere (`ocr-diff.txt`) that I read: `plan-forecast-experiment` (DOP 350 vs 400, 15,200 vs 14,250, 26,000 vs 25,400) and `plan-refined-goal-change-es` (12,038 vs 12,018) follow a slider drag landing on a different value, a class already recorded at the last comparison. Plan screens are outside the changed files.

## Not verified

- **About 80 non-target differing screenshots were not classified by eye.** A Fable helper was reviewing `comp/` when this report was due and had not returned. For those pairs only the measurements exist (`metrics.tsv`, `ocr-diff.txt`). Many match classes recorded last time (QR codes, photo grid, waveform, tab glass, sheets mid-presentation), but I did not confirm each. `money-valid-plan-es`, `money-precision-error-es`, `gallery-money-dark-en`, `plan-create-es` and the three `currency-*-choice` shots are newly differing with large boxes and were not opened by me.
- Why the first Home drag used to travel further (fling or late layout). Only the timing and the resting offset were measured.
- That leftover app defaults explain the missing composer hint. It rests on code reading.
- Backend, real Postgres, auth matrix, web and OpenAPI were not rerun. They rest on 4af8fced and the scope proof.
- No phone install, launch or journey for build 3428, by instruction. Installation alone would not prove a journey.
- Connected walk, tap proof, lag traces and mac-pass `screens` were not repeated on this head.
- `FinancialLoopUITests/testSharedPlanningFourKinds...` still skips without its seeded backend.
- TestFlight readiness is not claimed.
