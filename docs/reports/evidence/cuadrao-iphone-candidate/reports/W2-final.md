# W2-final: Household invitations final pass

**Branch:** `claude/cuadrao-household-invites-ios`. **Final head:** `aeaf1bca5` (evidence README only). **Code head:** `a10f6b5c46b21d7c6dd21a8c63fb71e1ba5a38d5`. Pushed without force: `4932251c1..a10f6b5c4`, then `a10f6b5c4..aeaf1bca5`.

**#790 merged:** `origin/codex/cuadrao-release-ui` at `3370ba509`, plain merge `a10f6b5c4`.

## Commits

- `52ef82737` fix(household): one membership read decides every Household-scoped not-found. Covers findings 1, 2 and 5.
- `2788adc36` fix(invitations): count the group-link label in code points like the server. Covers finding 3.
- `c31e2dcc3` test(invitations): use failure shapes and link kinds the server produces. Covers finding 4.
- `a10f6b5c4` is the merge of #790 `3370ba509`.
- `aeaf1bca5` docs(evidence): household invitations final pass at a10f6b5c4.

## Findings

| # | Finding | Status |
| --- | --- | --- |
| 1 | `open(_:)` reload overwrote the message | **Fixed.** Confirmed first: the old line set "permissions changed" after `refresh()` with no re-check. Now "household.changed" is written only if the reload left `errorKey` nil, for the same session and selection. New test `testTheReloadAfterAnAccountRefusalKeepsItsOwnMessage` covers two cases: the reload ends membership (`household.accessEnded`) and the reload gets no answer (`household.loadError`). Both cases failed on the old model. |
| 2 | `refreshSearch` bypassed the membership re-read (B1 class) | **Fixed structurally.** Confirmed, and there were two more bypasses the review missed: `HouseholdActivityEditor.load()` and `review()` (`HouseholdActivityEditor.swift:57,72`) also called the synchronous handler directly. The old `handleAccessFailure` is now `private applyMembershipAnswer`, so nothing outside `HouseholdModel` can end membership from a raw error. `resolveAccessFailure` is the single entry for every Household-scoped failure. It and `handlePlanAccessFailure` share one `rereadMembership`, and only that membership read (or the list read) can end membership on `household_not_found`. The code match is now on the code, not on status 404 alone. Tests came first: `testAnAccountScopedNotFoundFromAnyEntryKeepsMembershipWhenTheMembershipReadAnswers` covers six entries (detail, history, search, editorLoad, editorReview, activityWrite). Also added `testAnAccountNotFoundWithoutAMembershipAnswerKeepsTheHousehold` (offline re-read) and `HouseholdPlanModelTests.testSearchReloadNotFoundAfterAPlanWriteKeepsMembershipWhenTheMembershipReadAnswers` (the `refreshSearch` caller). |
| 3 | Label counted graphemes, server counts code points | **Fixed.** Confirmed against `invite_schemas.py:36` (`max_length=80` on the stripped str). Now uses `name.unicodeScalars.count`. Test: one family emoji is 1 character but 7 scalars. 11 families plus "abc" (80 scalars) is accepted, and 12 families (84 scalars) is refused. A mutation back to `name.count` fails `InvitationsTests` (1 failure). |
| 4 | Stub shapes the server does not produce | **Fixed.** `InvitationsModelTests` `.rejected(status: 500/503, code: nil)` is replaced with `.unauthorized`. That is what `SessionController` throws when `/invites/access` stays 401 after a refresh (run3 seq 121, `401 unauthorized`); any 5xx is already `.unavailable`. The harness preview and redeem now answer `kind: "group_link"` for `FULL` and `-LINK` secrets (seq 50, 51, 53, 61, 63), `beta` otherwise. |
| 5 | Hand-off preview was claimed model-tested but triggered from view code | **Fixed by moving the trigger, and the claim is corrected.** `HouseholdModel.beginJoin` now runs `previewInvitation(input)`. `HouseholdIntroduction.onAppear` only shows the handed-over text. `testAnOpenedLinkReachesTheJoinStepOnlyWhileHouseholdsAreAvailable` asserts the preview name and the exact preview request (`{"token": "link-token-123456"}`), and it failed on the old model. The evidence README says the earlier claim was not true when made. The real join sheet over the gate is still not driven by a UI test, because the harness stands in for it (`harness.household.opened`). |

## Red step (tests first)

The new test files were run against `git archive HEAD` of `4932251c1` (old model) in my scratchpad: 46 tests, 17 failures. The failing tests were editorLoad, editorReview, the Search reload, both reload-message cases and the hand-off preview. The detail, history, search, activity-write and offline re-read cases passed on the old code: they are coverage for paths that were already right (review P3-5).

## Merge of #790

There was one conflict, in `ReleaseUI/Invitations/ReleaseInvitationShare.swift` (the Share button). This lane had already made `url` optional with a code fallback, because the default server returns `link: null`. #790 added `.modifier(ReleaseProminentLabel())`. I kept this lane's optional-URL guard and applied #790's modifier. Every other #790 change auto-merged unchanged, including `ReleaseInvitationSenders.swift`, which keeps this lane's label field and #790's on-accent modifier. No file in this lane's scope uses `showsPersonalPhoto` or `editsAvatar`.

**Note for the lead:** this lane still carries edits in two #790 files from before this pass: `ReleaseInvitationShare.swift` (optional `url`) and `ReleaseInvitationSenders.swift` (group-link label field, 3-argument `onCreate`). Taking #790's versions wholesale would break the build and the server contract (`source_label` is required). #790 should absorb them, or they need an owner decision.

## Commands and results (all at `a10f6b5c4` unless noted)

- `python3 ios/FinancialModelTests/run_household.py`: 46 tests, 0 failures. That is 26 Household and 20 plan tests; it was 42 at `3c7d7f27`.
- `python3 ios/FinancialModelTests/run_invitations.py`: 21 tests, 0 failures.
- `swift test --package-path ios/Packages/ArgusSession --scratch-path ios/.build/argus-session-tests`: 104 tests, 4 skipped, 0 failures.
- `SIMULATOR_ID=8B7975F1-1338-4966-90E2-770416CAF174 RESULT_DIR=<scratch>/w2final/debug-build ios/scripts/verify.sh build`: BUILD SUCCEEDED.
- `xcodebuild build -configuration Release -destination 'generic/platform=iOS Simulator' -derivedDataPath ios/.build/ReleaseDerivedData CODE_SIGNING_REQUIRED=NO`: BUILD SUCCEEDED. `strings` over the Release binary finds 0 of `invitations-harness`, `InvitationsStubServer`, `harness-`, `DEMO-ONLY`.
- `lockf -k ~/.claude/orchestrate/cuadrao-iphone-candidate/mac-sim.lock sh -c "SIMULATOR_ID=8B7975F1-1338-4966-90E2-770416CAF174 RESULT_DIR=<scratch>/w2final/ui-focused ios/scripts/verify.sh test -only-testing:ArgusFoundationUITests/InvitationsUITests -collect-test-diagnostics never"`: 18 tests, 0 failures, `** TEST SUCCEEDED **`, exit 0. Lock held 05:05:01Z to 05:10:29Z.
- `git diff --check` on each commit and the merge: clean.
- Logs: `/private/tmp/claude-501/-Users-garces-Documents-projects-repos-argus--claude-worktrees-canary-core-checks-4f5d0f/78382341-c9b6-421e-b5aa-d9a65dc9b367/scratchpad/w2final/` (`household-red-old-model-2.log`, `household-head.log`, `invitations-head.log`, `package-head.log`, `package-label-mutation.log`, `debug-build.log`, `release-build.log`, `ui-focused/test-20261004T050501Z.log` and `.xcresult`).

## Not done

- No screenshot was re-exported. After the #790 merge, prominent invitation labels use the on-accent ink, so `gate-*` and `personal-invitation-created-*` show the older darker label. The README says so.
- No full suite was run (rule 16). The two Household `FinancialLoopUITests` still need a live backend and were not run.
- No CI job runs the host runners; this follows the existing pattern.
