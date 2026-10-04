# W2-last: PR #810 last fix pass (Household invitations)

Final head: `18b4919192a44df508a5f7a7841f80199a3be2d1` on `claude/cuadrao-household-invites-ios`, pushed without force (`aeaf1bca5..a02e7d3ec`, then `a02e7d3ec..18b491919`). Code head is `a02e7d3ec294d9dbac7e49c8a38c3f5efaa24985`; `18b491919` changes only the evidence README. No simulator was booted or driven, and no `xcodebuild test` ran.

## Commits

| SHA | What |
| --- | --- |
| `06c7d7ef8` | Plain merge of `origin/codex/cuadrao-release-ui` at `cc68b341e`. No conflict. The only lane-path change it brought is #790's own "1. Trust and profile, 13 to 14" board row. |
| `eea13c654` | A-1, A-2 |
| `2ba466923` | A-3, A-6 |
| `1b8298eb8` | A-4 |
| `fde60b0b6` | A-5 |
| `a02e7d3ec` | Board row 4, one sentence |
| `18b491919` | Evidence README section "Last fix pass at `a02e7d3ec`" |

## Per finding

- **A-1 (P2): fixed.** I confirmed it in the code first. `open(_:)` reloads, the bumped version makes `refresh()` call `clear()`, the generation rotates and `current(ticket, …)` drops the message. I wrote the test first: `testAnUnsharedAccountLeavesTheListAndSaysPermissionsChanged` (`revokeAccount()`, then the account 404, then `open`). It failed at head with `errorKey` nil (log `household-red.log`: 47 tests, 1 failure). The fix compares the session (new `private sameSession`, which `current` also uses), plus `selectedId`, `errorKey == nil` and `isAvailable`. I added `isAvailable` beyond the review's proposal. With the ticket gone, a reload that answers `households_unavailable` (suspend `.disabled`, selection kept, errorKey nil) would otherwise show "household.changed" over a surface that is off. A "disabled" case in `testTheReloadAfterAnAccountRefusalKeepsItsOwnMessage` covers it. A mutation that removes `isAvailable` fails exactly that case. A more specific message from the reload still wins: the departed and offline cases pass.
- **A-2 (P3): fixed.** `accessEnded()` is now `private`. The tree has no caller outside the model.
- **A-3 (P3): fixed.** The `showManagement` didSet now also calls `cancelInvitationReview()` on close. That covers the close button, "Not now", `accessEnded` and `suspend`, so I deleted the explicit cancel calls from the last two. `previewInvitation` takes a review ticket (`invitationReview`) that cancel and every newer preview rotate. A success or an invitation-outcome answer for a stale ticket is dropped. Errors that are not invitation outcomes still go to `failed`, because they speak about the surface and not about the review. `testClosingTheJoinStepEndsItsReview` covers an in-flight preview (a new `holdPreview` gate in the test server) and a landed one. Accept afterwards sends no request. It failed before the fix in both cases.
- **A-4 (P3): fixed, view code only.** `HouseholdIntroduction` adopts the handed-over code in `.onChange(of: model.pendingInvitationToken)` as well as `onAppear`, through one `adoptHandedOver()`. The token's own onChange compares against `handedOver`, which is set first, so adopting does not cancel the review. No host test exists for this. It needs the UI run below.
- **A-5 (P3): fixed.** The harness `kind()` answers `group_link` only for secrets that start with `FULL`. Household secrets are answered before `kind()` runs (`secret.contains("household") || hasPrefix("HOME")`). No client branch reads `beta` against `group_link`; `InvitationsModel.swift:207` only tests `.household`.
- **A-6 (P3): fixed.** `beginJoin` returns `isAvailable` after its preview. `testAHandOffWhosePreviewTurnsHouseholdsOffIsNotOpened` failed before the fix.
- **Board (B-2): done.** Row "2. Access and Household | 4" in "Cuadrao release UI landing order" got one appended sentence: the connected iPhone invitation client for items 4 to 8 is built default-off behind `ARGUS_BETA_INVITES_ENABLED` and `ARGUS_INVITE_UNIVERSAL_LINK_ENABLED` (#810), verified against a local backend (linked evidence README) and enabled nowhere, and universal links wait on AASA and Associated Domains. No other line changed in my commit.

## Commands and results

Logs are in my scratchpad `…/scratchpad/w2/`.

- `python3 ios/FinancialModelTests/run_household.py`. At head plus the probe: 47 tests, 1 failure (the A-1 probe, as expected). After A-1: 47 of 47. After the A-3 and A-6 tests: 49 tests, 5 failures, all in the two new tests. Final at the code head: 49 of 49 (29 Household, 20 plan).
- Mutation: with `isAvailable` removed from the A-1 condition, 1 failure ("disabled" case). The file was restored from a copy, and `git diff` was confirmed.
- `python3 ios/FinancialModelTests/run_invitations.py`: 21 of 21.
- `swift test --package-path ios/Packages/ArgusSession --scratch-path ios/.build/argus-session-tests --disable-sandbox`: 104 tests, 4 skipped, 0 failures.
- `SIMULATOR_ID=8B7975F1-1338-4966-90E2-770416CAF174 ios/scripts/verify.sh build`: `** BUILD SUCCEEDED **` (Debug, compile only).
- `xcodebuild build -project ios/ArgusFoundation.xcodeproj -scheme ArgusFoundation -configuration Release -destination "platform=iOS Simulator,id=8B7975F1-…" -derivedDataPath ios/.build/DerivedData-release CODE_SIGNING_REQUIRED=NO CODE_SIGNING_ALLOWED=NO`: `** BUILD SUCCEEDED **` (compile only).
- Both builds and the host runners ran on the `fde60b0b6` source tree, which is byte-identical in `ios/` to `a02e7d3ec` and `18b491919`.
- `git diff --check`: clean, both the working tree and `a8c37d3a…HEAD`.
- `uv run --with markdown-it-py python scripts/check_docs_links.py --base a8c37d3a182fbdb3228f6003272418e65286bc1a`: "Checked local links in 6 changed document(s)", exit 0, run twice. I deleted the `uv.lock` it wrote both times. uv also recreated the gitignored `.venv` in the worktree.

## UI tests for the lead to run focused on the simulator (under the Mac lock)

1. `-only-testing:ArgusFoundationUITests/InvitationsUITests`, all 18. The harness `kind()` change touches every harness preview and redeem. The ones that matter most are `testHouseholdCodesAndLinksGoToTheHouseholdJoinStep`, `testLinkIntentSurvivesCancelledSignInAndAdmitsAfterSignIn`, `testAnAdmittedPersonReturnsToTheAppFromABetaLink` and `testAFailedLinkShowsWhyAndKeepsManualCodeRecovery`.
2. `-only-testing:ArgusFoundationUITests/HouseholdUITests/testHouseholdTwoUsersConsentEditingRevocationAndSpanishRelaunch`. It drives "Not now" and then a fresh join and accept (lines 197 to 208), which is the path A-3 changed. It needs its seeded local backend.
3. `-only-testing:ArgusFoundationUITests/HouseholdUITests/testHouseholdConfirmedResponseLossCreateAndAcceptRecoverAfterRelaunch`. It drives the typed preview and accept on the join step. It needs its seeded local backend.

No UI test covers A-4 (a link arriving while the introduction is already on screen), because the harness stands in for the real join sheet (`harness.household.opened`). Proving A-4 would need a manual pass or a new UI test.

## Not done, follow-ups

- UI tests were not run in this pass (simulators reserved).
- No screenshot was re-exported.
- B-1 and B-3 (docs outside this lane's scope) are untouched.
