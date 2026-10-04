# R-candidate-4af8fced: independent delta review of the combined iPhone candidate

Pinned to `4af8fced6021b3581ea2a62e482eaf8231d5c58b` on `claude/cuadrao-iphone-candidate`. Every read used `git show` / `git diff` on SHAs. Nothing in the repo was edited, committed or pushed, no simulator was used and nothing was posted on GitHub. Host model tests ran from a `git archive 4af8fced6 ios` copy in my scratchpad (`run_household.py`, own scratch build path).

`git diff --stat a10f6b5c 4af8fced6` over the scope A paths is empty, so the Household code in the candidate is byte-identical to the reviewed lane head.

## Verdict

- **Scope A (Household invitations final pass): one P2, five P3.** The structural membership rule, the hand-off preview, the label limit, the stub kinds and the merge resolution all hold. The P2 is a regression introduced by the reload-message fix itself.
- **Scope B (candidate merges): CLEAN for P1 and P2, three P3 (docs only).** The only hand resolution is the board row, and it is correct.

## Commands run

- Baseline `run_household.py` at `4af8fced6`: 46 tests, 0 failures (26 Household, 20 plan).
- Mutations on the production files, one fix reverted each, every one fails a new test:

  | Mutation | Test that fails |
  | --- | --- |
  | `open(_:)` writes "household.changed" unconditionally after the reload | `testTheReloadAfterAnAccountRefusalKeepsItsOwnMessage` (both cases) |
  | `refreshSearch` uses the raw answer | `HouseholdPlanModelTests.testSearchReloadNotFoundAfterAPlanWrite...` |
  | `find` uses the raw answer | `testAnAccountScopedNotFoundFromAnyEntry...` (search) |
  | Editor `load()` uses the raw answer | same test (editorLoad) |
  | Editor `review()` uses the raw answer | same test (editorReview) |
  | `beginJoin` without the preview | `testAnOpenedLinkReachesTheJoinStepOnlyWhileHouseholdsAreAvailable` |
  | Unanswered re-read ends access | `testAnAccountNotFoundWithoutAMembershipAnswerKeepsTheHousehold` |

- Label test not run (separate package build). By inspection it fails on `name.count`: 12 family emoji are 12 characters (accepted by `count`) and 84 scalars, and the test expects `.label`.
- Probe test for A-1 (below): fails at head, passes with the one-line fix, and the other 46 tests still pass with the fix.
- `git diff --check a8c37d3a...4af8fced6`: clean (also clean two-dot).
- UI tests: not run (no simulator).

## Scope A

### What was verified

1. **Membership rule is structural.**
   - `accessEnded()` has two callers in the whole `ios/` tree: the list read (`HouseholdModel.swift:85`) and `private applyMembershipAnswer` (`:367`).
   - `applyMembershipAnswer` is reached only from `resolveAccessFailure` (`:345`), `handlePlanAccessFailure` (`:333`) and the membership re-read's own catch (`:357`). A raw `household_not_found` for the selected Household can never reach its `accessEnded()` branch from the first two, because their guards take that case to the re-read.
   - Every `catch` in `ios/ArgusFoundation/Household/` was read. The ones that touch access go through `failed` → `resolveAccessFailure`, `resolveAccessFailure` directly (find, refreshSearch, retry, editor load and review) or `handlePlanAccessFailure`. The rest only set a message.
   - Selection is cleared only by `accessEnded()`, `bind`, and the person's own `select(nil)`. `suspend` keeps it.
   - No loop: `rereadMembership` calls the controller directly and its catch is synchronous.
   - Unanswered re-read: selection, household and snapshot are unchanged; only `errorKey = household.loadError` (mutation-tested).
2. **Hand-off preview.** `beginJoin` previews once (`:175`); `HouseholdIntroduction.onAppear` (`HouseholdManagement.swift:187-192`) only fills the field, and setting `token` there does not cancel the review because `handedOver` is set first. `previewInvitation` posts `/invitations/preview` only; accept still needs a name and the Accept tap, and `command` refuses a secret that is not the reviewed one (`:182`). A leftover `pendingInvitationToken` can no longer trigger a request, because the view no longer previews. See A-3 and A-4 for two edges.
3. **Reload message.** Kept only for the same session, selection and a nil `errorKey` (`:110`). But see A-1.
4. **Label length.** `name.unicodeScalars.count <= 80` matches Pydantic `max_length=80` on `str` (`src/argus/domain/household/invite_schemas.py:36`, code points). The client sends the trimmed label, so the server's later `strip()` cannot change the count.
5. **Stub shapes.** Preview and redeem answer `kind: "group_link"` for group secrets, matching run3 seq 50, 51, 53, 61, 63. `.unauthorized` is a shape the transport produces. The Household test server's preview body (`name`, `expires_at`, `available`) matches seq 74, 82, 84. One cosmetic gap, A-5.
6. **Tests bite.** See the mutation table.
7. **Merge resolution in `ReleaseInvitationShare.swift`.** Correct. `--remerge-diff a10f6b5c` shows the lane's `if let item = invitation.url?.absoluteString ?? invitation.code` kept and #790's `.modifier(ReleaseProminentLabel())` applied; `ReleaseProminentLabel` is defined once. With a nil `url` and a code, the QR and link text are skipped and `ShareLink` shares the code string, so a person can still share. With neither, the button is absent. The only caller that can pass nil is `InvitationViews.swift:319`.

The author's account (`W2-final.md`) is accurate except that finding 1 is described as fixed without noting A-1.

### Findings

**A-1 (P2). The reload-message fix drops "permissions changed" in the real unshare case.**
- Where: `ios/ArgusFoundation/Household/HouseholdModel.swift:110`.
- Evidence: every Household command on an existing Household bumps `households.version` (`src/argus/domain/household/commands.py:62-65`), and that is the snapshot's `authorization_version`. So after a grant is removed, the reload inside `open(_:)` sees a new version, `refresh()` calls `clear()` (`:90-92`), and `clear()` rotates `generation`. `current(ticket, identity)` on `:110` is then false and the message is never written; `refresh()` already set `errorKey = nil` (`:93`). The account leaves the list with no explanation. At `3c7d7f27` the message was shown.
- Proof: a probe test (`server.revokeAccount()` then the account 404, then `open`) fails at head with `errorKey == nil`. The new tests miss it because they refuse the account read without bumping the version.
- Smallest fix: on `:110` compare the session, not the generation ticket: `if self.identity?.revision == identity.revision, self.identity?.profile?.id == identity.profile?.id, self.selectedId == selectedId, errorKey == nil { errorKey = "household.changed" }`. Verified: probe passes and all 46 tests pass. Add the probe as a test case.

**A-2 (P3). `accessEnded()` is still internal.**
- Where: `HouseholdModel.swift:323`. No outside caller exists today, but the "one private function" claim is only true by convention.
- Smallest fix: `private func accessEnded()`.

**A-3 (P3). A preview can outlive the join step it was for.**
- Where: `HouseholdModel.swift:32`, `:156`, `HouseholdManagement.swift:183`.
- Closing the sheet (or "Not now") resets `joiningByInvitation` but not the review, and a preview still in flight lands after the close. The next time the join step opens, the old Household name and an enabled Accept show under an empty code field. Accept joins the Household that is named on screen, so nothing is accepted unseen. The "Not now" half predates this delta.
- Smallest fix: in the `showManagement` `didSet`, also call `cancelInvitationReview()` when it closes, and have `previewInvitation` drop an answer whose secret is no longer the one being reviewed.

**A-4 (P3). A link that arrives while the introduction is already on screen previews without filling the field.**
- Where: `HouseholdManagement.swift:187-192` adopts `pendingInvitationToken` only in `onAppear`. `beginJoin` now previews regardless, so the preview can sit under another typed code, and the token stays pending until the next appear.
- Smallest fix: run the same adoption in `.onChange(of: model.pendingInvitationToken)`.

**A-5 (P3). The harness names a personal link a group link.**
- Where: `ios/ArgusFoundation/Invitations/InvitationsHarness.swift:127-131`. Any `-LINK` secret answers `group_link`, including `beta-link-token-…`, which the UI tests use as a personal invitation link (`InvitationsUITests.swift:6`). The server would answer `beta`. No client branch reads it.
- Smallest fix: answer `group_link` for `FULL` only (the one group-only refusal), or name group secrets with their own prefix.

**A-6 (P3). `beginJoin` returns true even when its preview turned the surface off.**
- Where: `HouseholdModel.swift:175-176`. A `households_unavailable` answer to the preview suspends the surface and closes the sheet, but the invitations model gets `true` and shows no "Household unavailable" notice.
- Smallest fix: `return isAvailable` after the preview.

## Scope B

### What was verified

- `git show --cc` and `--remerge-diff` are empty for `8745126d8` and `4af8fced6`. For `ef361e3d3` the only conflict is the "1. Trust and profile | 13–14" row of `docs/specs/argus-execution-board.md` (now `:88`).
- That row has no conflict marker. It keeps #790's text in full (avatar-editing entry, the October 3 decision link, "shows every row, including the avatar editor, in development builds (#790)") and adds #808's sentence with the link to `lanes/cuadrao-profile-hidden-rows-backend.md`. Dropped from #808's side: "photo avatars, retain initials/themes", "photos" and "Today `CuadraoFirstRelease` hides them in every build". All three are superseded by the October 3 decision and by the code (`CuadraoProfileCanvas.swift:74-81`), so no true fact is lost.
- Sign-in: #808's board text (Apple and Google built, default-off, none enabled) has no opposing statement left in the board, MVEE, design guide or decision log.
- Deletion: #808's model (default-off flag, lock until confirmed, operator-run sweep) is not contradicted by #790, whose deletion screens are gallery fixtures that call no route.
- Avatar rule: MVEE `:685-688`, board `:88`, decision log `:353` and the code's `editsAvatar` agree. "in every build" no longer appears anywhere.
- Hidden rows: the seven routes in the lane doc equal `CuadraoFirstRelease.unfinishedProfileRoutes` exactly.
- Decision log: #808's in-place edits and #790's "October 3, 2026: avatar editing in release" section are both present, and that section is last, in date order.
- No doc says the invitation client is shipped or enabled. Both iOS flags are `false` in `Development.xcconfig:42,45` and `Local.xcconfig.example`.
- Headings: no duplicate heading was added to the board, MVEE, decision log, data model or lane handoff (the duplicates present are the same set as at `a8c37d3a`). Every anchor the merged text links to resolves to exactly one heading.

### Findings

**B-1 (P3). The hidden-rows doc names a symbol that no longer exists.**
- Where: `docs/specs/lanes/cuadrao-profile-hidden-rows-backend.md:7` says `CuadraoFirstRelease.hiddenProfileRoutes` "hides seven Profile rows". #790 renamed it to `unfinishedProfileRoutes` and hides the rows in release builds only.
- Smallest fix: rename the symbol in that sentence and add "in release builds".

**B-2 (P3). The board does not record the connected invitation client this tree builds.**
- Where: `docs/specs/argus-execution-board.md:2829-2831` (from #790) lists admission among operations that "still require their service owners", and rows `:89` onward carry no status. The candidate builds the connected gate, personal invitations and group links behind default-off `ARGUS_BETA_INVITES_ENABLED` and `ARGUS_INVITE_UNIVERSAL_LINK_ENABLED`. Only the evidence README says so.
- Smallest fix: one sentence in row `:89` stating the iPhone client is built default-off, with a link to `docs/reports/evidence/cuadrao-household-invites/README.md`.

**B-3 (P3). "No native flow is on integration" reads oddly beside #790's deletion screens.**
- Where: board `:85`, MVEE `:734`. #790 adds native deletion screens as review fixtures.
- Smallest fix: "no connected native flow".

Observation, not from the merges: board rows C07 and C08 (`:2849-2850`, #790) still say release hides "personal-photo selection", narrower than the October 3 decision to hide the whole avatar-editing entry. They do not contradict it.
