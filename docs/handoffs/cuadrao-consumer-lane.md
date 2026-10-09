# Cuadrao Consumer lane: handoff (paused October 9, 2026)

**Status: paused by the founder at a usage limit.** This document and the GitHub records it links let another agent resume. No private notes, chat transcripts or scratch folders are needed.

**The successor's first action:** read section 1 (holds), then run the two read-only checks in section 3.1 (integration head, and CI plus mergeability of [PR #937](https://github.com/lagarcess/argus/pull/937)). Then report to the founder: what is merged, what #937 still needs, and the state of the two unmerged lane branches. Do not start anything in section 5.B without the founder's approval.

## 1. Scope and decisions

### Scope
The Consumer lane owns the free-tier iPhone app (`ios/ArgusFoundation`, bundle `local.argus.founder.47R3855RTJ` for the founder's phone) under issue [#877](https://github.com/lagarcess/argus/issues/877). Contracts to read first: [DESIGN.md](../../.agent/designs/cuadrao/DESIGN.md) (note the "Sheet controls" and brand sections), [the master plan](../specs/cuadrao-master-plan.md), [the integration ledger](../specs/private-alpha-next-integration.md), [`ios/README.md`](../../ios/README.md). Launch tracker: [#817](https://github.com/lagarcess/argus/issues/817), build issues [#833](https://github.com/lagarcess/argus/issues/833) and [#818](https://github.com/lagarcess/argus/issues/818).

### Approved by the founder and landed (integration `codex/private-alpha-next`)
| PR | Merged as | What |
| --- | --- | --- |
| [#919](https://github.com/lagarcess/argus/pull/919) | `31a73c501` | The + menu: anchored card with a nub when the bar is open, labeled round buttons stacked when it is folded |
| [#921](https://github.com/lagarcess/argus/pull/921) | `826ace6d4` | Marketing's approved mark as app icon, welcome screen lockup, shared brand component |
| [#931](https://github.com/lagarcess/argus/pull/931) | `86f8e4f6e` | + then Transaction opens the editor on the primary-currency account (no list of accounts) |
| [#934](https://github.com/lagarcess/argus/pull/934) | `e9d9fa4a1` | The bar folds into the + on Plan, Search and Profile as on Home |
| [#930](https://github.com/lagarcess/argus/pull/930) | `b8f1dc7c1` | Business lane's #928 backend fix, consumer-reviewed |
| [#935](https://github.com/lagarcess/argus/pull/935) | `8a14aad25` | Saved receipts client, **default off** (`CuadraoFirstRelease.savedReceipts`, false in Release) |
| [#936](https://github.com/lagarcess/argus/pull/936) | `bbf4da23f` | One Cancel / check / Done rule for every sheet, plus the ledger entry for the landings above |

### Implemented, reviewed, not merged
- [PR #937](https://github.com/lagarcess/argus/pull/937), branch `codex/cuadrao-no-floating-done`: no control above the keyboard anywhere (the blue Done pill), one tap-away rule (`KeyboardTapAway`), a guard script, 19 updated test steps. One independent review was fixed in the head commit. Open items for it are in section 3.3.

### Built on branches, not merged, no PR (founder reviews before any PR)
- `codex/cuadrao-guest-book`: guest mode, "Probar sin cuenta". Slices 0 to 3 (package, welcome entry, empty book, accounts, movements and chart) built and tested; slices 4 and 5 were in progress. See section 2.2 for the pushed head.
- `codex/cuadrao-transaction-sheet`: keypad-first transaction sheet mock (Robinhood and Wise style). **Local-only, unreported**; see section 2.2.

### Founder permissions and holds, in force
- **No hosted change** of any kind: no migration, deployment, flag, Supabase or Render change. Read-only hosted inspection is its own approval. Repository migration files are not proof of production state.
- **No install on the founder's phone** without an explicit "install" and an unlocked phone.
- **Merges are the founder's.** The founder authorized landing the four PRs named in October 9 session ([#930, #931, #934, #935](https://github.com/lagarcess/argus/issues/877#issuecomment-6074214780)) and #936. That is not a standing permission: confirm the exact PRs before any merge.
- **Spanish (es-419) first.** Every user-facing word is approved in Spanish first; English follows. No em dash in user copy. Keep approved labels such as En grupo / Together.
- **No paid or live-AI tests.** Households stay off. The Updates bell stays hidden: no consumer notification source exists yet.
- **Hosted storage and deletion smoke test** is a separate approval before saved receipts are enabled anywhere.
- Apple organization enrollment (decision D1 in #818) is pending the founder's LLC. Do not enroll as an individual or invent company details.

### Latest UI, wording and interaction decisions (accepted unless marked experiment)
Accepted by the founder (evidence: the founder's acceptance comments on [#877](https://github.com/lagarcess/argus/issues/877) and the phone builds 3451 to 3453):
- **Navigation:** Home, Plan, +, Search, Profile; no assistant tab in Release. The bar is a pill that folds to the + on the right when scrolling down on **every** tab and expands when scrolling up. Collapsed + centered opens manual entry.
- **+ menu:** open bar shows an anchored card with a nub above the bar (rows: Account, Transaction, Plan; file rows Scan with camera, Choose a photo, Choose a file only when receipts are on); folded bar shows labeled round buttons stacked up from the +. Transaction opens the editor on the primary-currency account; there is no account list.
- **Sheet controls (DESIGN.md "Sheet controls"):** plain-text Cancel on the left, no oval or underline; a check on the right only when the sheet has no primary button of its own; plain "Done" only on view-only sheets. **Nothing sits above the keyboard** (no Done pill); keyboards close by tapping away, scrolling or Return. The last rule is in #937, not yet merged.
- **Brand and welcome:** Marketing's "Lean, calm" mark as the app icon (full-bleed 1024), one lockup (268 pt) on the welcome screen with two native actions, light `#fafbf8`, dark `#172b26`; the same shared brand component on the invitation card and chat empty state.
- **Copy:** Spanish (es-419) first, English follows, no em dash in user copy. Approved words include "En grupo / Together", "Escanear o subir archivo", the saved-receipts alert words ("Receipt saved", "You already had this receipt saved."), the delete confirmation ("It is deleted from your account and our servers. Your activity does not change.") and "No pudimos eliminar el recibo." / "We could not delete the receipt."
- **Hidden until real:** Updates bell, Files and Conversations pages, households, assistant, extra spaces. Do not hide records a person already owns.
- **Reorder:** hold and drag reorders Home accounts (verified in the simulator October 9).

Experiments, not accepted, no PR: the keypad-first transaction sheet (`codex/cuadrao-transaction-sheet`), guest mode "Probar sin cuenta" (`codex/cuadrao-guest-book`; its new Spanish-first strings live in the branch's `ios/ArgusFoundation/Guest*` files and `GuestAccountPresentation.swift`, none approved; defaults proposed in its plan, founder replied "all good, go on" but has not approved strings or a PR), and Build 3454's sample-receipts demo.

### Branding, welcome, tray and typography: sources and acceptance evidence
- Source assets are Marketing's pinned SVGs: lockups at `acf1b180a`, other marks at `73286f8ca`, handoff commit `9349037be8920a5a5914a76c2ae3e73ea7e4b56d`, approved artwork in [#906](https://github.com/lagarcess/argus/pull/906). In the app they live in `ios/ArgusFoundation/Cuadrao/Brand.xcassets` and `ios/ArgusFoundation/Cuadrao/CuadraoBrand.swift`.
- Acceptance and landing evidence: [#919](https://github.com/lagarcess/argus/pull/919), [#921](https://github.com/lagarcess/argus/pull/921), the ledger entry dated October 8 in [the integration ledger](../specs/private-alpha-next-integration.md), and DESIGN.md (brand identity, welcome screen, add tray, "Intentional native exceptions" for native typography).
- Preserve all of it. Typography stays native (system and the documented serif display font for headings); do not restyle.

### What the successor must not infer or start
- Do not enable saved receipts, guest mode or any flag in Release. Both are default off and must stay so.
- Do not open PRs for the guest-book or transaction-sheet branches, and do not treat their strings as approved copy.
- Do not decide dark or tinted app icon variants; that is an open founder decision.
- Do not resume the Business or Marketing lanes; see [their handoffs](cuadrao-business-lane.md) and [the marketing handoff](cuadrao-marketing-launch-lane.md).
- Do not infer product direction from the founder's tone in earlier chats. The only product decisions are the ones linked above.

## 2. Exact work state

### 2.1 Integration and open PR (read live; values below were read October 9, 2026 with `git ls-remote` and `gh pr view`)
- Integration `codex/private-alpha-next` head: **`bbf4da23f`** (#936).
- [#937](https://github.com/lagarcess/argus/pull/937): base integration, branch `codex/cuadrao-no-floating-done`, head **`8066c9b66`**, mergeable clean when read. CI on that exact head was not re-read before the pause.
- Dependencies: #937 touches shared files that the guest-book branch also touches (`CanvasDecimalInput`, the amount fields, the toolbars). Land #937 first, then merge integration into the guest-book branch.

### 2.2 Lane branches (all pushed unless noted)
| Branch | Head | State |
| --- | --- | --- |
| `codex/cuadrao-no-floating-done` | `8066c9b66` | [#937](https://github.com/lagarcess/argus/pull/937); includes `ConsumerWalkUITests` (capture journeys used for the feedback audit) |
| `codex/cuadrao-guest-book` | `245703206` | Guest mode, no PR. Slices 0 to 4 built and verified (package tests 83, 16 journeys after merging integration `bbf4da23f` as `abe84c666`, slice 4 journeys `testGuestGoalProgressComesFromContributionsTypedByHand`, `testGuestBudgetCountsThisMonthsExpensesInItsScope`, `testGuestPlansInSpanish`, `testGuestPlansAtLargeText`). Slice 5 (search, what-if, totals) is a **WIP commit**: it compiles, but `GuestSearchUITests` has never run and its element ids are guesses; large-text and es-419 screenshots and the full regression were not done. It still has its own Done controls in the shared plan editor and decimal input that #937 removes, so merge #937 first. |
| `codex/cuadrao-transaction-sheet` | **not pushed** | Transaction sheet mock, no PR. **Local-only.** The agent building it was still running when the lane paused and did not report or push. The branch exists only in the worktree `/Users/garces/Documents/projects/repos/argus/.claude/worktrees/agent-accef4746fb45a304` (its HEAD is unknown to this document; read it with `git -C <that path> log --oneline -5` and `git -C <that path> status`). Mock screenshots are untracked in `<that path>/transaction-sheet-mock/` (`normal-text/`, `accessibility-large-text/`). Verification status of the mock is unknown. First step for a successor: read that worktree, push the branch if its tests pass, and record the head here; do not delete it. |
| `codex/cuadrao-consumer-handoff` | this PR | Documentation only |

Older merged branches (`codex/cuadrao-saved-receipts`, `-fold-everywhere`, `-add-transaction-default`, `-consistency-walk`) are history; do not reuse them.

### 2.3 Local-only material (worktrees preserved, nothing deleted)
All under `/Users/garces/Documents/projects/repos/argus/.claude/worktrees/` on the founder's Mac:
- `cuadrao-release-surface`: this lane's main worktree.
- `agent-a3ea4bb6855947c8f`: guest-book worktree, including an untracked `guest-mode-evidence/` (41 screenshots, `RESULTS.txt` mapping tests to xcresults).
- `agent-accef4746fb45a304`: transaction-sheet worktree, including its untracked `transaction-sheet-mock/` screenshots.
- `cuadrao-r1-recovery/ios/Config/Device.local.xcconfig` (ignored by git): phone signing and API configuration. Copy it into `ios/Config/` only for a device build, and delete the copy after (`phone-build-candidate` style scripts do this).
- Optional, not needed to resume: the other `agent-*` and `cuadrao-*` worktrees and the `ios/.build` result bundles.

### 2.4 Builds
| | Installed on the founder's phone | Prepared, not installed |
| --- | --- | --- |
| Build number | **3453** | **3454** |
| Configuration | Release | Debug (sample saved receipts; needs launch arguments) |
| Source SHA | `e9d9fa4a1` (integration at #934) | worktree `codex/cuadrao-consistency-walk` at `a018eb298` (before the #936 squash) |
| App identifier | `local.argus.founder.47R3855RTJ` (development team `47R3855RTJ`) | same |
| Signing expiry | **2026-10-13 22:03:32 UTC** (development provisioning profile; re-sign by rebuilding before then) | same profile, same expiry |
| Remaining device checks | Home and + menu on the phone were accepted. Not checked on the phone: #936 sheet controls, #937 keyboard rule, saved receipts, dictation, backup and restore. | Not installed; superseded by a fresh build from integration |
Installation permission: only on the founder's explicit "install" with the phone unlocked. Neither build is a TestFlight or App Store candidate.

### 2.5 Shared ingestion: ownership and conflicts
One shared ingestion system exists (Business-owned server pipeline: [#905](https://github.com/lagarcess/argus/pull/905), [#908](https://github.com/lagarcess/argus/pull/908), [#909](https://github.com/lagarcess/argus/pull/909), [#913](https://github.com/lagarcess/argus/pull/913)). Do not create a second one.
- **Consumer changed (merged in #935, `8a14aad25`):** iOS client only. `ios/Packages/ArgusSession/Sources/ArgusSession/FinancialDocuments.swift` (+ its tests `FinancialDocumentTests.swift`), a content-type and header option in `SessionController.swift`, and the app's `SavedReceipts*` files plus `ReceiptNativePicker` use. It calls the existing `/api/v1/financial-documents` routes and sends no extraction consent header.
- **Consumer owns no server module, contract or migration.** Migrations in order, all Business-owned and not applied in hosted: Marketing C0 `20260920000000` first, then B1 `20261008100000`, B2 `20261008110000`, B3 `20261008130000`; see the [Business handoff](cuadrao-business-lane.md) section on release gates for B4 and the rollback rule.
- **Frozen candidates:** Consumer Build 1 freeze `cad1cbe1ec27ff89c08eadbec31718a0e627383c`; Build 2 candidate `64833f6d2` (#905), both recorded on [#833](https://github.com/lagarcess/argus/issues/833).
- **Rollback limit:** a minimum compatible code version, not a revert. Once documents are stored in hosted, #905's code is the minimum version that can read and delete them.
- **Receipt-storage deletion checks:** the hosted storage and deletion smoke test is a separate founder approval and must pass before saved receipts are enabled. Evidence of the local rehearsal is on [#914](https://github.com/lagarcess/argus/pull/914) and [PR #916](https://github.com/lagarcess/argus/pull/916).
- **Pending shared-file changes that could conflict with Business (none touch server or web code):**
  - `docs/specs/private-alpha-next-integration.md`: both lanes append; each handoff or landing PR adds a dated entry. Merge integration before editing.
  - `.agent/designs/cuadrao/DESIGN.md`: #937 (`8066c9b66`) and `codex/cuadrao-guest-book` (`245703206`) add sections; Business web design edits elsewhere do not overlap.
  - iOS shared files (`CanvasDecimalInput.swift`, amount fields, `ConnectedBalanceHistory.swift`) are touched by #937 and the guest-book branch; Business does not edit consumer iOS.
  - `ios/FinancialModelTests/run.py` and `ios/DesignPreviewTests/`: #937 adds the keyboard guard.
- **Business sandbox:** Business is active in an isolated sandbox. Do not alter its worktrees, processes or services.

## 3. Verification

### 3.1 Read-only checks to run first
```bash
git fetch origin
git rev-parse --short origin/codex/private-alpha-next      # expect bbf4da23f or newer
gh pr view 937 --json headRefOid,mergeStateStatus
gh pr checks 937
```

### 3.2 Commands and environment
- Model tests: `python3 ios/FinancialModelTests/run.py`. Expected: **6 baseline failures** tracked in [#898](https://github.com/lagarcess/argus/issues/898), 0 unexpected. On the #937 branch it also runs the keyboard guard `ios/DesignPreviewTests/run_no_keyboard_accessory.py` (that file exists only there until #937 merges).
- Session package: `swift test --package-path ios/Packages/ArgusSession --skip Live` (178 pass at `2af026434`).
- UI journeys (simulator iPhone 18 Pro `8AFB6084-8918-416E-9164-E21061306BEC`, any free port base): `python3 ios/scripts/auth/run-ui.py <simulator> --accounts --port-base <PORT> --only ArgusFoundationUITests/<Class>/<test>`. The script starts a local synthetic API and Supabase stack and supplies `ARGUS_TEST_EMAIL`, `ARGUS_TEST_PASSWORD`, the `_B` variants and `ARGUS_TEST_ACCOUNTS_UI_ENABLED`. Pick one test per run.
- **Traps:** most UI tests are `extension FinancialLoopUITests`, so `--only ArgusFoundationUITests/FinancialLoopUITests/<test>`; a wrong class runs zero tests and still prints exit 0. Always read `xcrun xcresulttool get test-results summary --path <bundle>` and require `totalTestCount` 1 and `Passed`. Never `pkill run-ui.py`: several agents may share the Mac.
- Phone build: copy `Device.local.xcconfig` (section 2.3), then `xcodebuild build ... -destination 'id=<device>' CURRENT_PROJECT_VERSION=<n>`; install with `xcrun devicectl device install app`; check `xcrun devicectl device info lockState`.

### 3.3 Results and which commit they cover
| Check | Result | Covers |
| --- | --- | --- |
| `#919`, `#921`, `#931`, `#934`, `#930`, `#935`, `#936` exact-head CI | green before each merge | each PR's head, recorded on [#877](https://github.com/lagarcess/argus/issues/877#issuecomment-6074214780) and in the ledger |
| 16 typing journeys (`testSharedDollarSplitAndRepaymentSpanish`, `testPersonalEuroCreationAndLockEnglish`, `testSharedJourneySpanish`, `testGroupCreationSavingsEnglishDark`, `testCreateMonthlyAndDebtPlans`, `testCreationEditingArchiveAndRecovery`, `testMoneyEntryAndBlankCreationSpanish`, `testSheetsCancelAndConfirmTheSameWay`, `testSpanishConnectedCheckReview`, `testConnectedProfileUsesRealIdentityAndApprovedDestinations`, `testConnectedReceiptDraftSurvivesRelaunchWithoutPosting`, `testPersonalPlanSwipeEditArchiveRestore`, `testHomeNativeSwipeDragAndArchiveRecovery`, `testSearchPlansChatReturnAndRecovery`, plus two more) | 16 of 16 passed on `c57c7bf72` (one passed only on rerun) | #937 before its review fixes |
| Same journeys after the review fixes | **11 of 13 passed** before the pause; `testAccountEntryKeepsUnknownAndSignedBalances` failed with an unlabeled `XCTAssertTrue`; `testDistributionAccountRoundTrip` crashed with "signal term" (likely killed by another process); the rest were not run | `78b043484` |
| Guest-book journeys (16) and package tests (64) | passed per the guest agent's report | guest-book head of that report, not `245703206` |

### 3.4 Known failures and unresolved findings
- The two failures in the table above are unresolved on #937's head. Rerun them alone first; a rerun-pass pattern was seen on `testConnectedProfileUsesRealIdentityAndApprovedDestinations`. No baseline comparison on integration was made for the flakes in `testSharedJourneySpanish` and `testSharedDollarSplitAndRepaymentSpanish` (each failed some earlier runs and passed on the final ones): measure them on integration before calling them known flakes.
- #937 review items not done: a UI test for "type the debt interest rate, tap Create plan, rate is kept" (the fix, binding the rate through a `String` on every keystroke, has no end-to-end test); a VoiceOver and Switch Control walk of decimal pads (no dedicated dismiss control remains); a check that the system edit menu (Paste, Select All) does not close the keyboard.
- Saved receipts have never run against a real server; only the debug sample transport.
- Open copy: guest-mode and transaction-sheet strings are unapproved (lists are in the guest and transaction branches' PR-ready notes below).

## 4. Operational context
- **Local stacks** (read October 9, 2026, `lsof`): a uvicorn API on `127.0.0.1:58900` (pinned for the phone), a TLS proxy on `*:58950` that the phone reaches at the Mac's LAN address, and Docker Supabase ports in the 58901 to 59211 range used by the test harness. These are the founder's Mac services; do not stop them.
- **Configuration names, no values:** `ios/Config/Device.local.xcconfig` keys include `ARGUS_API_URL`, `ARGUS_AUTH_ENABLED`, `ARGUS_LOCAL_BUNDLE_IDENTIFIER`, `DEVELOPMENT_TEAM`, `CUADRAO_DESIGN_PREVIEW`. Credentials for synthetic test users are generated by `run-ui.py`; real credentials come only from an authorized operator.
- **Hosted facts:** none were verified by this lane after October 8, 2026. The October 8 compatibility-matrix evidence is [PR #916](https://github.com/lagarcess/argus/pull/916) (branch `codex/cuadrao-compat-matrix`, head `70c8eb9c4`, open, docs and evidence only, not on integration); treat it as old.
- **Connectors:** GitHub (`gh`) and the Mac's Xcode, `xcrun simctl` and `xcrun devicectl`. No other access is required.

### 4.1 Keeping the founder's phone app working (verified October 9, 2026 with `ps` and `lsof`)
The phone build talks to the founder's Mac through two **detached** processes (parent process 1), so closing a Claude session does **not** stop them. They stop on a Mac restart or if someone kills them. Do not stop them while a build is on the phone.
1. **Phone API:** `uvicorn argus.api.main:app --host 127.0.0.1 --port 58900`, started from the worktree `/Users/garces/Documents/projects/repos/argus/.claude/worktrees/cuadrao-pin-5def72` (the pinned tested candidate). It uses the local Docker Supabase stack on ports 58901 to 58911.
2. **TLS forwarder:** `~/.cuadrao-local-tls/tls_forward.py` (maps 58950 to 58900, 58951 to 58901, 58955 to 58905; certificates and keys stay in that folder and must never be copied into Git). The phone's `ARGUS_API_URL` is the Mac's LAN address on port 58950, set in the ignored `ios/Config/Device.local.xcconfig`. If the Mac's LAN address changes, the phone build must be rebuilt.
- Check: `lsof -nP -iTCP:58900 -sTCP:LISTEN` and `lsof -nP -iTCP:58950 -sTCP:LISTEN`.
- Restart (unverified commands, check `--help` first): forwarder `cd ~/.cuadrao-local-tls && nohup python3 tls_forward.py >> forward.log 2>&1 &`. API: from the pin worktree, `python3 ios/scripts/auth/local_stack.py api --accounts --port-base 58900 --accounts-enabled on --python "$PWD/.venv/bin/python"` (the same pattern the guest-book agent used for port 59200). The Docker Supabase stack must already be up.
- Saved receipts in the phone's real (non-demo) mode only work if that API has receipt storage and the documents flags enabled; this was not verified. Treat a failed save there as "server not enabled", not as an app bug, until checked.

## 5. Next steps
### A. The successor can do these
1. Run section 3.1, then report to the founder.
2. Rerun the two unresolved journeys alone on `codex/cuadrao-no-floating-done`; fix or document each.
3. Add the three missing #937 checks from section 3.4; push to the #937 branch (it is the lane's branch), then ask the founder for the merge decision.
4. After #937 lands: merge integration into `codex/cuadrao-guest-book` and `codex/cuadrao-transaction-sheet`, rerun their own journeys, and update their notes. No PR yet.

### B. These need the founder's approval first
1. Merging #937 or any PR.
2. Opening PRs for guest mode or the transaction sheet, and every new Spanish string (approve in Spanish first).
3. Installing any build on the phone (say "install", phone unlocked).
4. Hosted work: the storage and deletion smoke test, enabling saved receipts, migrations, anything on Render or Supabase, Apple enrollment (D1), TestFlight.
5. Dark and tinted app icons; whether guest mode claims into an account later ([#883](https://github.com/lagarcess/argus/issues/883) covers sharing plans without a household).
