# R-household-3c7d7f27: independent delta review of the R-household-6fb15a01 fixes

Pinned to code head `3c7d7f2710b01a3a799714b1e7f8d6bec8e6e41a` on `claude/cuadrao-household-invites-ios`. The worktree head is `4932251c1`, which adds only evidence docs. Every file read and every command used `git show 3c7d7f27:` or `git archive 3c7d7f27`.

Scope: `git diff 6fb15a01..3c7d7f27 -- ios ':!ios/ArgusFoundation/ReleaseUI' ':!ios/ArgusFoundation/Cuadrao'` (15 files, +1015 / -204). The merge `3c7d7f271` adds no `ios/` change outside the excluded trees (`git diff --stat 3c7d7f27^1 3c7d7f27 -- ios ...` is empty). `ConnectedCuadraoRoot.swift` is not in the delta; I read it only to trace the mount and bind paths.

This review is read-only. Nothing in the repo was edited, committed or pushed. No simulator was run and nothing was posted on GitHub. The host tests ran from a `git archive` copy in my scratchpad, using a copied dependency cache.

Paths below are relative to the repo root at `3c7d7f27`.

## Verdict

**CLEAN for P1 and P2.** The P1 (F1), every P2 (F2 to F5), the P3s and M1, M2 and B1 are fixed. Each fix is backed by tests that fail when the fix is reverted (mutation runs below). I found five P3s, all small. None blocks the lane.

## Commands run (pinned tree in scratchpad)

- `python3 ios/FinancialModelTests/run_invitations.py`: 21 tests, 0 failures.
- `python3 ios/FinancialModelTests/run_household.py`: 42 tests, 0 failures.
- Mutation runs on the production `InvitationsModel.swift`. Each one reverts a single fix, and every one fails at least one test:

  | Mutation | Tests that fail |
  | --- | --- |
  | Failed check opens the app (`failed()` sets `.off`) | 5, including `testAFirstCheckWithoutAnAnswerStaysClosedUntilARetryIsAnswered` and `testAFailedRefreshNeverReplacesTheServersAnswer` |
  | Ordering guard removed | `testAnOlderAccessReadCannotLandOverANewerOne`, `testARedeemedCodeAdmits...` |
  | `bind` no longer clears the link | `testALinkEndsWithTheSessionAndNeverReachesTheNextAccount` |
  | `guard flags.links` removed | `testWithTheLinkFlagOffNoLinkOfAnySchemeIsHandled` |
  | Group key reused across drafts | `testAGroupLinkKeyBelongsToOneDraft` |
  | `personal.fail()` replaced by `= .failed` | 2 tests |
  | `groupLinks.fail()` replaced by `= .failed` | `testANewGroupLinksSecretsSurviveAFailedListReload` |
  | `guard flags.surface` removed | 2 tests |
  | Link at the gate auto-submits | `testALinkAtTheGateFillsTheCode...`, `testALinkWaitsForSignIn...` |

- Mutation runs on `HouseholdModel.swift`:
  - `resolveAccessFailure` short-circuited to `handleAccessFailure` (B1 reverted): `testAnAccountRouteNotFoundNeverEndsMembershipOnItsOwn` fails. Selection becomes nil and the message becomes `household.accessEnded`.
  - `select(nil)` restored in `beginJoin` (F9 reverted): `testAnOpenedLinkReachesTheJoinStepOnlyWhileHouseholdsAreAvailable` fails.
- UI tests: not run here (no simulators). The author's run `scratchpad/fix-focused-3/test-20261004T040154Z.log` shows 18 of 18 `InvitationsUITests` passed and `** TEST SUCCEEDED **`.

## 1. Admission state machine (`ios/ArgusFoundation/Invitations/InvitationsModel.swift`)

Verified. No path shows the app to a person the server has not admitted while the client flag is on.

- **States and rendering.** `Admission` has five states: `off`, `checking`, `unanswered`, `required`, `admitted` (`:39-65`). `InvitationGateHost` renders `content()` only for `.admitted` and `.off` (`InvitationViews.swift:21-31`). `.checking` shows a spinner. `.unanswered` shows a closed retry screen with sign-out (`InvitationViews.swift:38-53`).
- **Where `.admitted` and `.required` come from.** They are built in two places only, both server answers:
  - `answered(BetaAccess)` (`:57-60`);
  - a redeem answer with `admitted: true` (`:158-162`).
- **Where `.off` comes from.**
  - The client flag (`:108`, `:119`).
  - The server's own `404 invites_unavailable` (`:63`, `:170-171`). Only `require_invites_surface` raises that code (`src/argus/api/households.py:221-230`), so nothing on the client can produce it.
- **First check unanswered.** `failed()` moves `.checking` to `.unanswered` and leaves every other state alone (`:62-64`). A transport error, a 5xx (`SessionFailure.unavailable`), a 401 and an unknown 4xx (now `.refused`) all keep the app closed.
- **Refresh failure after `required`.** The state is kept (`:62-64`). Covered by `testAFailedRefreshNeverReplacesTheServersAnswer`.
- **Out-of-order reads.**
  - `accessIssued` and `accessApplied` (`:130-139`) ensure only a newer answer applies.
  - A failure never advances `accessApplied`, so a late older success can still replace `.unanswered`. That is correct.
  - A redeem bumps the sequence (`:160`), so a read that started earlier cannot close the gate again.
- **Sign-out, then sign-in as another user.** `bind` resets `admission`, issues a new `generation`, and clears the link once a signed-in identity ends (`:113-123`). Every async result checks `ticket == generation`. `ProfileAuthModel.accept` binds the invitations model on every snapshot (`ProfileAuthModel.swift:165-167`), so the sign-out path reaches it through `perform` even though `signOut()` itself does not call `invitations?.bind(nil)`. `ConnectedCuadraoRoot` unmounts the gate host on sign-out, so its `.task` runs again on the next sign-in.
- **Backgrounding.** A foreground triggers `refreshAccess`, and a failure there keeps the answer.
- **Client flag off.**
  - `admission` is `.off` from `init` and from `bind`.
  - `refreshAccess` returns before any request (`:128`), and `retryAccess` cannot leave `.off`.
  - `submitCode` requires `.required`, and the Invitations row requires `.admitted` (`:111`).
  - Covered by `testTheClientFlagOffSendsNoRequestAndNeverWaits`, which asserts zero calls. There is no spinner, because `.off` renders content on the first frame.
- **One flag reader.** `InvitationFlags.load` (`:12-18`) is the only reader of `ARGUS_BETA_INVITES_ENABLED` and `ARGUS_INVITE_UNIVERSAL_LINK_ENABLED` in `ios/`. The other matches are config files only. `ProfileAuthModel.swift:49` uses `.load()`. The DEBUG harness builds its flags from launch arguments.

**Facts for the lead (accepted default-off states, not findings):**

- **Client flag off, server gate on.** The client has no gate, so a person the server has not admitted uses the whole app. Per W7 answer 4, the server refuses only `POST /invites` (`403 beta_invite_required`). No UI copy claims a gate in this state; the only text is the `Development.xcconfig:39-40` comment, which is accurate. Running the gate needs both the client flag and the server flag on.
- **Client flag on, server without the invites routes.** If the server is older than the invites routes, every signed-in person stays on the retry screen. Any 404 whose code is not `invites_unavailable` maps to `.refused`, and then to `.unanswered`. This is fail-closed by design. Turn the client flag on only against a server that serves `/invites/access`; a surface-off server answers `404 invites_unavailable`, which correctly becomes `.off`.

## 2. Link intent

Verified.

- **Taken exactly once.** `routeLink` sets `pendingLink = nil` before any await (`:192-196`). Only `open(_:)` writes it (`:182-186`). A second link opened during a preview is handled on its own (test `testASecondLinkOpenedWhileTheFirstIsBeingPreviewedIsNotDropped`).
- **Never redeems or accepts.**
  - At the gate, the link fills `gateCode` (`:198-199`). `ReleaseInviteGate` submits only on Continue or Go (`ReleaseInviteGate.swift:56,66,86-89`). Tokens are 43 characters (`secrets.token_urlsafe(32)`), so `InviteSecret(input:)` sends them as `token`, not `code` (`Invitations.swift:8-19`).
  - For an admitted person, the link is previewed only (`:202-212`).
  - With the surface off, it goes to `handToHousehold`. The join step previews on entry (`HouseholdManagement.swift:187-193`); joining still needs a name and a tap.
- **Cleared on discard and when the identity ends.** `discardPendingLink` (`:189`) clears it, and so does `bind` when `identity != nil` (`:117`). A link opened while signed out survives the first sign-in, as intended.
- **Flag off.** `open` returns false for every scheme (`:183`). The only other `onOpenURL` in `ios/` is Google Sign-In (`NativeProviderSignIn.swift:105`).

## 3. B1 (`ios/ArgusFoundation/Household/HouseholdModel.swift`)

Verified, with one residual caller (P3-2).

- **The check.** `resolveAccessFailure` (`:359-373`) takes `404 household_not_found` for the selected Household and re-reads `GET /households/{id}`.
  - If the re-read returns 200: `household.changed`, and membership is kept.
  - If the re-read is refused: `handleAccessFailure` runs on that membership answer, so `404 household_not_found` or `403 not_a_member` ends access.
  - If the re-read gets no answer (offline): `handleAccessFailure` returns false, `errorKey = household.loadError`, and selection, household and snapshot are untouched.
- **No loop.** The re-read calls the controller directly, not through `failed` or `resolve`.
- **No mask of a real end.** A real end makes the re-read answer 404 or 403, which ends access.
- **Callers of `accessEnded()`.** Every one now rests on a membership answer:
  - `refresh` `:85` (the list read).
  - `handleAccessFailure` `:351`, reached from:
    - `handlePlanAccessFailure` (`:328` for non-404 codes, `:340` after its own re-read);
    - `resolveAccessFailure` (`:361` for other codes or a non-selected Household, `:370` after the re-read);
    - `refreshSearch` `:279`, directly (P3-2).
- **Account-scoped server cause.** `require_edit`, `detail` and `history` raise `household_not_found` for an ungranted or unknown account (`src/argus/domain/household/access.py:120-127`, `financial.py:96-124`). Activity writes (`retry`, `:236`), history (`:126`) and detail (`:106`) now go through the re-read.

## 4. Stub and harness shapes against `run3/exchanges.jsonl`

Verified, with two cosmetic gaps (P3-4).

- **Preview.** `200 available:false` for expired, used, revoked and full (`InvitationsHarness.swift:74-76`, `lookup` `:116-125`). Matches seq 18, 24, 29, 53, 61 and 63.
- **Redeem refusals.** The 409 codes match seq 17, 25, 30, 52 and 62.
- **Lookups.** Unknown returns `404 invitation_not_found` (seq 19); rate limited returns `429 invite_rate_limited` (seq 119).
- **Codeless 5xx.** `SessionFailure.unavailable` (`:54`, `:121`), which is what `SessionController.swift:73,301` produces for any status of 500 or more.
- **Link.** `link: null` on beta and group creates by default (`:68`, `:97`), matching seq 9 and 49.
- **Revoke route.** `POST /group-links/{id}/revoke` returns 204, `403 founder_required` or `404 invitation_not_found` (`:100-107`). This matches seq 60 and the server (`invites.py:530-539`, idempotent `coalesce`).
- **Household test server.** Preview answers `available:false`. Failures carry `type`, `status` and `code` (`HouseholdModelTests.swift`, `HouseholdServer`). The unreachable 409-on-preview cases are gone.

## 5. Group-link idempotency after a lost response

Verified against the server.

- **Server.** `keyed()` hashes `body.model_dump(mode="json")` (`src/argus/api/routers/households.py:409-411`). `_replay` returns `replayed:true` with no secrets for the same key and hash, and raises `IdempotencyConflict` (409 `idempotency_conflict`) for the same key with a different hash (`invites.py:180-197`). The replay check runs before the expiry check (`invites.py:482-488`). OpenAPI lists no 409 for this route; that gap predates this delta.
- **Client.**
  - The key is stored with its `GroupLinkDraft` and reused only for an equal draft (`InvitationsModel.swift:289-290`).
  - The draft holds the label already trimmed and the expiry string already formatted, so a retry sends a body with the same hash.
  - The key is kept only for `.unavailable`, meaning no answer (`:304`). `idempotency_conflict` now maps to `.refused` (`Invitations.swift:211`), so it retires the key and the wedge is gone.
  - A replay shows `secretsShownOnce` and invents no link (`:296-300`).
- **Behavior to know (not a finding).** If the founder leaves and returns, the form's default expiry changes and the next tap uses a new key. After a lost response that creates a second open link. The orphaned first link appears in the founder list and can be revoked.

## 6. `Loaded<Value>`, the Sent list and founder lists

Verified.

- `fail()` moves only `loading` to `failed` (`:75-80`). The Sent section renders loading, failed and empty differently (`InvitationViews.swift:147-160`).
- `notFounder` comes only from `403 founder_required` (`:276`). `GroupLinkScreen` is reachable only from `.ready(.links)`.
- `createdPersonal` and `.created(invite, used:)` live outside the lists. A reload failure keeps `.ready`, so the secrets stay visible.
- The create button exists only in `.ready` (`ReleaseInvitationSenders.swift:21-43`), so a create can only start with a list value, and `fail()` cannot hide its result.

## 7. Tests

Verified. Reverting any fix fails at least one test (see the mutation table above).

- `run_invitations.py` copies `ios/ArgusFoundation/Invitations/InvitationsModel.swift` from the tree byte for byte at run time (`:16`) and compiles it with the test file against the real `ArgusSession` package. It is not a maintained copy: my mutations of the production file changed the results.
- The model no longer imports SwiftUI or ReleaseUI. The gate-state mapping moved to `InvitationCopy` in the views, so that mapping is covered only by the UI tests.
- No CI job runs `run_invitations.py`. Neither `run_household.py` nor `run.py` runs in CI either, so this follows the existing pattern; the evidence is the author's local run and mine.

## 8. Regressions and new wrong facts

- **Contract.** The group-link body is still `source_label`, `cap`, and `expires_at` with a zone; `SentInvites.init` is additive.
- **Secrets.** Added lines contain no `print`, logger, `UserDefaults` or pasteboard use.
- **Release gating.** The harness is still wholly `#if DEBUG` (`InvitationsHarness.swift:1`, last line; `ArgusFoundationApp.swift:34-44`).
- **Copy.** Every new string has English and Spanish, and the added lines contain 0 em dashes.
- **Comments.** The comments on `InvitationFlags` and `Admission` match the code.
- **Author's report.** It is accurate except for two points:
  - The B1 row says the re-read "applies to ... search". `find` does use it, but `refreshSearch` (`HouseholdModel.swift:279`) does not (P3-2).
  - Item 4c says the hand-off preview is "covered by model tests". The trigger is view code (`HouseholdManagement.swift:187-193`) and no test drives it.

## Findings

### P3-1. After an account 404, `open(_:)` overwrites whatever the reload decided

- **Where:** `ios/ArgusFoundation/Household/HouseholdModel.swift:108`, `await refresh(); errorKey = "household.changed"`.
- **What happens:** the line sets the message unconditionally after `refresh()` and does not re-check `current(ticket, identity)`. If the reload ends membership (list without the Household, `:85`), the state is correct (selection nil) but "access ended" is replaced by "permissions changed". If the reload has no answer, `suspend(.unavailable)` runs and its `loadError` is replaced the same way. If the session changed during the reload, the message is written onto the new session.
- **Impact:** wrong message only, in a narrow race or offline. Membership state is right.
- **Smallest fix:** `await refresh(); if current(ticket, identity), self.selectedId == selectedId, errorKey == nil { errorKey = "household.changed" }`.

### P3-2. One account-scoped caller still bypasses the membership re-read

- **Where:** `HouseholdModel.swift:279` (`refreshSearch` catch): `handleAccessFailure(error, householdId: selectedId)`.
- **What happens:** the same `/search` route is routed through `resolveAccessFailure` in `find` (`:144`). Search is membership-scoped today (`financial.py:139-141` goes through `snapshot`), so the practical risk is low. Still, the class fix is incomplete, and the author's account claims full coverage.
- **Smallest fix:** `_ = await resolveAccessFailure(error, householdId: selectedId)`.

### P3-3. The label limit counts characters, but the server counts code points

- **Where:** `ios/Packages/ArgusSession/Sources/ArgusSession/Invitations.swift:173` (`name.count <= 80`).
- **What happens:** Swift's `count` counts grapheme clusters. Pydantic's `max_length=80` (`src/argus/domain/household/invite_schemas.py:36`) counts code points. A founder label with multi-scalar emoji passes the client and gets `422 validation_error`, which shows the generic "refused" text.
- **Impact:** founder only, cosmetic.
- **Smallest fix:** `name.unicodeScalars.count <= Self.labelLimit`.

### P3-4. Two stub shapes the real server does not produce

- **Model tests.** `ios/FinancialModelTests/InvitationsModelTests.swift:80` and `:97` feed `.rejected(status: 500/503, code: nil)`. The real transport never produces this; any status of 500 or more is `SessionFailure.unavailable`. The tests pass through the mapping fallback and prove nothing extra. Fix: use `.unavailable`.
- **Harness.** `InvitationsHarness.swift:76` answers preview `kind: "beta"` for group-link secrets (`FULL`, `-LINK`). The real answer is `kind: "group_link"` (seq 50, 53, 61, 63). No client branch reads anything but `household`, so this does not change behavior. Fix: answer `group_link` for the `FULL` and `-LINK` cases.

### P3-5. B1 tests cover only the account-detail route

- **Where:** `HouseholdModelTests.swift`. The B1 tests drive only `open(_:)`.
- **Gaps:**
  - History (`:126`) and activity writes (`retry`, `:236`) also reach the new path untested; `require_edit` is the most likely real source of an account-scoped `household_not_found`.
  - No test covers a re-read with no answer, which should keep selection and set `household.loadError`.
- **Smallest fix:** add one activity-write case and one offline re-read case to the existing B1 tests.

## Notes (not findings)

- **A link opened during a code submit.** A link opened while a typed code is being redeemed replaces `gateCode` (`InvitationsModel.swift:199`). A successful redeem then clears it, so the link is consumed silently. A refusal shows the typed code's error next to the link's token. Reaching this needs an incoming link during the request.
- **Sign-out hidden while typing.** Sign-out is hidden while the keyboard is up on the gate (`InvitationViews.swift:67-69`), and the retry screen always shows it. This is the intended answer to W7 note (b); it was not screenshot-verified.
- **Flag comment omits the URL scheme.** `Development.xcconfig:43` says the link flag "stays off until cuadrao.ai serves the AASA file". The `argus-household://` shape would also need a `CFBundleURLTypes` entry, which no build has (unchanged reachability note from R-household-6fb15a01).
- **Opening the join step keeps the Household.** `beginJoin` no longer deselects (F9). `HouseholdManagement` hides the current Household section only while `joiningByInvitation` is true, and that flag resets when the sheet closes (`HouseholdModel.swift:32`) and after a successful accept (`:207`).
