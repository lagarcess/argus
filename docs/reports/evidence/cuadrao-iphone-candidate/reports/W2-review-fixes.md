# W2 review fixes: Household and beta invitations on iPhone

## Refs

- Branch `claude/cuadrao-household-invites-ios`, worktree `/Users/garces/Documents/projects/repos/argus/.claude/worktrees/cuadrao-household`.
- Started at `6fb15a017`. Code head `3c7d7f2710b01a3a799714b1e7f8d6bec8e6e41a` (pushed). Branch head `4932251c155ebaa43698cd90c780324a36c3b518` (pushed) adds only `docs/reports/evidence/cuadrao-household-invites/**` on top of it.
- Commits, oldest first:
  1. `254da9dc6` fix(ios): separate a refused invite request from no answer and hold group links to server limits
  2. `4fd1d3432` fix(ios): open the Household join step without deselecting the current Household
  3. `b9e5c7d69` fix(ios): fail the beta gate closed and consume an invitation link once, on the person's confirmation
  4. `a617aebb2` fix(ios): end Household membership only when the membership read says so (B1, plus the join-step auto preview and the `household_admin_required` mapping)
  5. `41e4d9eae` fix(ios): keep sign-out clear of the gate keyboard and give the retry label its on-accent colour
  6. `dbb76620b` test(ios): drive invitation screens over real response shapes, the retry state and revoke
  7. `3c7d7f271` plain merge of `origin/codex/cuadrao-release-ui` at `e9195b587` (docs and evidence only, no `ios/` change)
- No file under `ios/ArgusFoundation/ReleaseUI/**` was edited. No backend, web or spec doc was edited.

## State types introduced

All in `ios/ArgusFoundation/Invitations/InvitationsModel.swift` unless noted. The model no longer imports SwiftUI or any ReleaseUI type, so it compiles and is tested on the host.

- `Admission`: `off | checking | unanswered | required(InviteDestinations) | admitted(InviteDestinations)`. `required` and `admitted` are built only by `answered(_ BetaAccess)` or by a redeem answer with `admitted: true`. `failed(_:)` moves `checking` to `unanswered` and leaves every other state alone, except the server's own `404 invites_unavailable`, which is an answer and becomes `off`. There is no "unknown, so show the app" state any more.
- Access ordering: every `/invites/access` read takes a sequence number. An answer applies only if it is newer than the last applied one. A redeem answer bumps the sequence, so a read that started before it can never put the gate back.
- Link intent: `pendingLink: InviteSecret?`, written only by `open(_:)` and taken only by `routeLink()`, which sets it to nil before doing anything. It is also cleared by `discardPendingLink()` and by `bind` when a signed-in identity ends. `routeLink` never redeems or accepts: at the gate it fills the code field, for an admitted person it previews, with the surface off it opens the Household join step.
- `InvitationFlags { surface, links }` with `load(bundle:)`, the single reader of `ARGUS_BETA_INVITES_ENABLED` and `ARGUS_INVITE_UNIVERSAL_LINK_ENABLED`.
- `Loaded<Value>`: `loading | failed | ready(Value)`. `fail()` only moves `loading` to `failed`, so a failed reload keeps the last answer. Used for the Sent list (`Loaded<SentInvites>`) and for founder links (`Loaded<FounderLinks>`, `FounderLinks = notFounder | links([GroupLink])`).
- `InvitationGate`: `ready | checking | problem(InvitationProblem)`. `GroupLinkCreation`: `draft | creating | created(CreatedInvite, used:)`.
- `GroupLinkDraft` (package, `Invitations.swift`): a validated form value holding the server limits (label 1 to 80, cap 1 to 10000, expiry in the future and within 365 days). The idempotency key is stored with the draft it was issued for.
- `InvitationProblem.refused` (package): a 4xx the screens do not name. `unavailable` now means only "no answer" (transport, 5xx, undecodable body).
- `HouseholdModel.joiningByInvitation`: the join step is open over the current Household. It resets whenever the management sheet closes.

## Findings

| Finding | Status | What changed, and the test |
| --- | --- | --- |
| F1 (P1) gate opens on a failed check | Fixed | Confirmed at `InvitationsModel.swift:80` (old). A failed read never replaces an answer; a first check with no answer shows a closed retry screen with sign-out. `testAFirstCheckWithoutAnAnswerStaysClosedUntilARetryIsAnswered`, `testAFailedRefreshNeverReplacesTheServersAnswer`, UI `testAnAccessCheckWithoutAnAnswerKeepsTheAppClosed`. |
| F2 (P2) link auto-redeems, intent never cleared | Fixed | A link at the gate fills the code field and waits for Continue. The intent is taken once and ends with the session. `testALinkAtTheGateFillsTheCodeAndRedeemsOnlyWhenThePersonSubmits` (one redeem after three later refreshes), `testALinkEndsWithTheSessionAndNeverReachesTheNextAccount`, `testALinkWaitsForSignInAndForTheServersAnswer`, UI `testLinkIntentSurvivesCancelledSignInAndAdmitsAfterSignIn`, `testALinkIsForgottenWhenThePersonSignsOut`. |
| F3 (P2) flag off still handled the legacy scheme | Fixed | With `ARGUS_INVITE_UNIVERSAL_LINK_ENABLED` off, `open` returns false for both shapes. Legacy behaviour before this lane: on `origin/codex/cuadrao-release-ui` nothing handled an `argus-household://` URL (the only `onOpenURL` was Google Sign-In, no scheme is registered, and nothing wrote `pendingInvitationToken`). The only legacy path was pasting the link into the Household join field, which still works. `testWithTheLinkFlagOffNoLinkOfAnySchemeIsHandled`, UI `testNoLinkOfEitherShapeIsHandledWhileTheLinkFlagIsOff`. |
| F4 (P2) spinner and request with all flags off | Fixed | New default-off `ARGUS_BETA_INVITES_ENABLED` in `ios/Config/Development.xcconfig`, `Local.xcconfig.example` and `Info.plist`. Off means `Admission.off` from the first frame, no `/invites/access` request, no gate, no Invitations row. `testTheClientFlagOffSendsNoRequestAndNeverWaits`, UI `testWithTheClientFlagOffTheAppOpensAtOnceWithoutInvitations`. To run the gate, this client flag must be on as well as the server's. |
| F5 (P2) stub shapes the server cannot produce | Fixed | Harness preview answers `200 available:false` for expired, used, revoked, full; redeem answers the 409s; a server failure is `SessionFailure.unavailable`; beta and group creates return `link: null` unless `--harness-server-links`; `POST /group-links/{id}/revoke` exists and the swipe is tested. The Household test server previews `available:false`. All match W7 run3 (checks 30, 36, 40, 59, 66, 68, 12, 53, 65, 91 to 101). |
| F6 (P3) group create wedges on `idempotency_conflict` | Fixed | The key is reused only for the same draft and only when no answer arrived; any server answer retires it. `testAGroupLinkKeyBelongsToOneDraft`, `testAPersonalCreateWithoutAnAnswerAsksAgainWithTheSameKeyAndADefiniteRefusalRetiresIt`. |
| F7 (P3) form errors show code copy | Fixed in the model, not the form | The form is a ReleaseUI file (#790), so the limits are enforced by `GroupLinkDraft` before any request, with one message per field. A server 422 shows "We couldn't complete that request. Check the details and try again." `testAGroupLinkOutsideTheServersLimitsIsExplainedWithoutARequest`, package `testAGroupLinkDraftHoldsTheServersLimits`. |
| F8 (P3) founder and "nothing sent" inferred | Fixed | Founder status is `notFounder` only on `403 founder_required`. The Sent section shows loading, failed, or the list. A failed reload keeps the created secrets. The Invitations row needs `admitted`. `testFounderStatusComesOnlyFromTheServersRefusal`, `testAnEmptySentListALoadingOneAndAFailedOneAreDifferent`, `testANewGroupLinksSecretsSurviveAFailedListReload`. Kept on purpose: tapping "New group link" again starts a new draft and drops the previous secrets. |
| F9 (P3) join step deselects the Household | Fixed | `beginJoin` no longer calls `select(nil)`. Selection changes only when accept succeeds. `testAnOpenedLinkReachesTheJoinStepOnlyWhileHouseholdsAreAvailable` (also checks a fresh model still restores the selection). |
| F10 (P3) races | Fixed | Sequence guard on access reads; links are taken before the await so a second link is not dropped. `testAnOlderAccessReadCannotLandOverANewerOne`, `testARedeemedCodeAdmitsEvenWhenAnOlderReadAndTheFollowUpReadDisagreeOrFail`, `testASecondLinkOpenedWhileTheFirstIsBeingPreviewedIsNotDropped`. |
| F11 (P3) states with no server source | Fixed in the lane's files | The gate no longer maps anything to `waitlist`. The `waitlist` case itself lives in `ReleaseInviteGate.swift` (#790) and is now unused by the connected app. Household `expired / revoked / used` texts stay because accept really returns those 409s (W7 checks 91 to 101); they are no longer claimed for preview. |
| F12 (P3) test gaps | Fixed | `ios/FinancialModelTests/InvitationsModelTests.swift`, 21 host tests through the model's public surface, run by `ios/FinancialModelTests/run_invitations.py`. Mutation check: reverting four fixes (downgrade on failure, ordering guard, link cleared on sign-out, key per draft) made 8 assertions fail. |

Lead's added items:

| Item | Status | Notes |
| --- | --- | --- |
| M1 preview is 200 `available:false` | Fixed | Stubs as above. The preview body carries no reason, so the Household join step shows the single existing `household.inviteUnavailable` text ("This invitation is no longer available. Ask the administrator for another."). `testPreviewOutcomesExplainTheInvitationWithoutEndingMembership` now feeds only the real preview failures (404, 429), and `testAnExpiredUsedOrRevokedInvitationPreviewsAsUnavailable` covers the 200. |
| M2 mappings | Fixed | `invite_request_invalid` maps to `.refused` and shows "We couldn't complete that request. Check the details and try again." `household_admin_required` maps to `.refused` in the package; in the Household it reaches `HouseholdModel`, which keeps membership and shows `household.changed` ("Household permissions changed. Reload and review again."). Package `testEveryProblemCodeBecomesTheOutcomeTheScreensExplain`, model `testAGroupLinkOutsideTheServersLimitsIsExplainedWithoutARequest`, Household `testANonAdminInvitationRefusalKeepsMembershipAndSaysPermissionsChanged`. |
| B1 account 404 ended membership | Fixed, test first | The new tests failed at the old code (selection cleared, "access ended"). Every `404 household_not_found` for the selected Household now goes through one check that re-reads `GET /households/{id}`. Membership ends only if that read says so; otherwise the person stays, sees `household.changed`, and the snapshot reloads. Applies to account detail, history, search, snapshot and management writes. `testAnAccountRouteNotFoundNeverEndsMembershipOnItsOwn`, `testAnAccountRouteNotFoundEndsMembershipOnlyWhenTheMembershipReadAgrees`. Backend follow-up stays open: an account-scoped code. |
| 4a sign-out over Continuar | Fixed | Sign-out hides while the keyboard is up. Not screenshot-verified. |
| 4b "Crear invitación" dark on pine | Declined, out of scope | The label is inside `ReleasePersonalInvitationsView` (`ReleaseInvitationSenders.swift`), and the cause is `ReleaseInvitationPage`'s `.foregroundStyle(WelcomePalette.ink)` in `ReleaseInvitationShare.swift`. Both are #790 files this lane may not edit, and an inner `.buttonStyle(.borderedProminent)` cannot be restyled from outside. Fix for #790: `.foregroundStyle(WelcomePalette.onAccent)` on the three prominent labels (gate Continue, Create invitation, Create group link). My own retry button uses `onAccent`. |
| 4c hand-off should preview | Fixed | The join step previews the handed-over code as it appears. The old `onChange` trigger never fired because the field was created with the text already set. Preview only; joining still needs a name and a tap. Covered by model tests, not by a UI run (needs a live session). |
| 5 copy about the gate | Checked | No string in the lane says the gate protects data. The new retry text says only that beta access could not be checked. |

## Commands and results

- `swift test --package-path ios/Packages/ArgusSession --scratch-path ios/.build/argus-session-tests`: 104 tests, 4 skipped, 0 failures (at `b9e5c7d69`); `--filter InvitationsTests` 9 of 9 after the last package edit.
- `python3 ios/FinancialModelTests/run_invitations.py`: 21 tests, 0 failures.
- `python3 ios/FinancialModelTests/run_household.py`: 42 tests, 0 failures (23 Household, 19 plan). Before the B1 fix the same run had 7 failures in the new tests.
- `SIMULATOR_ID=8B79… ios/scripts/verify.sh build` at `3c7d7f271`: BUILD SUCCEEDED.
- `xcodebuild build -configuration Release -destination 'generic/platform=iOS Simulator'` (own derived data) at `3c7d7f271`: BUILD SUCCEEDED. `strings` over the Release app finds 0 of `invitations-harness`, `InvitationsStubServer`, `harness-`, `DEMO-ONLY`. Both flags read `false` in the built Info.plist.
- `git diff --check origin/codex/cuadrao-release-ui...HEAD`: clean.
- Merge: `origin/codex/cuadrao-release-ui` moved to `e9195b587` (docs and evidence only). Plain merge `3c7d7f271`, compiled after.
- Focused UI run: `lockf -k ~/.claude/orchestrate/cuadrao-iphone-candidate/mac-sim.lock env SIMULATOR_ID=8B7975F1-1338-4966-90E2-770416CAF174 RESULT_DIR=<scratchpad>/fix-focused-3 ios/scripts/verify.sh test -only-testing:ArgusFoundationUITests/InvitationsUITests` at `3c7d7f271`: 18 tests, 0 failures, `** TEST SUCCEEDED **`, exit 0. Queued 22:11, got the lock about 23:01, tests ended 23:10, xcodebuild held the lock until 23:20 collecting simulator diagnostics. Log and xcresult in `/private/tmp/claude-501/-Users-garces-Documents-projects-repos-argus--claude-worktrees-canary-core-checks-4f5d0f/78382341-c9b6-421e-b5aa-d9a65dc9b367/scratchpad/fix-focused-3/`.
- Two earlier attempts did not finish and are not evidence: `fix-focused-1` was stopped by my own 10 minute command limit after 8 tests had passed (it had waited on the lock), and `fix-focused-2` was withdrawn by me while still queued so that it would not build a tree I was editing.
- The two Household `FinancialLoopUITests` W2 listed were not rerun: they skip without a live backend.
- TDD note: the B1 tests were written first and failed. The invitations model tests were written with the rewrite, because the old model could not compile on the host; a mutation run stands in for the red step.

## Contract facts still open for the live verifier

- A real 5xx body on an invites route was not captured cleanly (W7 B2 got a 401 with the database paused). The client maps any status of 500 or more to "no answer" before reading the body, so the shape does not change behaviour.
- The connected app was not walked against a live backend at this head. In particular: the gate with the new client flag on, the Household join step opened over an existing Household, and B1 with a real revoked grant.
- Universal links and the `argus-household://` scheme still cannot be delivered by iOS to any build (no scheme, no entitlement).

## Follow-ups, not done

- #790: on-accent label colour for the three prominent buttons; remove the unused `ReleaseInviteGateState.waitlist`; bound the group form fields in the form itself.
- Backend: an account-scoped code instead of `household_not_found` on account routes (B1); 503 instead of 401 when the auth provider times out (B2).
- An admitted person who opens a dead beta link is told "You already have access. This invitation was not used." It is true but does not say the link is dead.
