# R-household-18b49191: independent delta review of PR #810's last fix pass

Pinned to `18b4919192a44df508a5f7a7841f80199a3be2d1` in `.claude/worktrees/cuadrao-household`. Every read used `git show` / `git diff` on SHAs. Nothing in the repo was edited, committed or pushed, nothing was posted on GitHub, no simulator was used and no `xcodebuild` ran. Host tests ran from a `git archive 18b491919 ios` copy in my scratchpad; mutations and probe tests were applied only to that copy and restored (diff against the SHA is empty).

Scope: `git diff aeaf1bca5..18b491919 -- ios/ArgusFoundation/Household ios/ArgusFoundation/Invitations ios/FinancialModelTests docs/specs/argus-execution-board.md` (5 files, +86 −23).

## Verdict

**No P1, no P2. Four P3.** Scope A of `R-candidate-4af8fced` (A-1 to A-6) is fixed as claimed, and every fix is held by a test except the two noted in F-3 and A-4 (view code). The P3s are one docs wording point, two leftover edges of the review-cancel fix, and one untested guard.

## Commands run

- `python3 ios/FinancialModelTests/run_household.py` at head: 49 tests, 0 failures.
- `python3 ios/FinancialModelTests/run_invitations.py` at head: 21 tests, 0 failures.
- Mutations on `HouseholdModel.swift`, one fix reverted each:

  | Mutation | Result |
  | --- | --- |
  | M1 `:113` back to `current(ticket, identity)` | fails `testAnUnsharedAccountLeavesTheListAndSaysPermissionsChanged` (`errorKey` nil) |
  | M2 `:34` close no longer cancels the review | fails `testClosingTheJoinStepEndsItsReview` (both cases) and `testSelectedHouseholdOffAcrossEntryPoints…` (7 entries) |
  | M3 `:160` landed preview ignores the review ticket | fails `testClosingTheJoinStepEndsItsReview` (in flight) |
  | M4 `:180` `beginJoin` returns `true` | fails `testAHandOffWhosePreviewTurnsHouseholdsOffIsNotOpened` |
  | M5 `:113` without `isAvailable` | fails `testTheReloadAfterAnAccountRefusalKeepsItsOwnMessage` ("disabled") |
  | M6 `:168` cancel does not rotate the ticket | fails `testClosingTheJoinStepEndsItsReview` (in flight) |
  | M7 `:164` stale invitation-outcome answer is written | **no test fails** (see F-3) |

- Four probe tests of mine (scratch only, with an extra request gate in the test server): a newer preview wins over an older one that lands later (pass, and fails under M3); an accept in flight survives a close and joins (pass); a refused accept that lands after a close; a failed preview that lands after a close (F-1, F-2 below).
- UI tests: not run. The harness is not compiled by either host runner, so item 5 is by inspection.

## What was verified

1. **A-1, unshare message.** `HouseholdModel.swift:113` is `sameSession(identity), isAvailable, self.selectedId == selectedId, errorKey == nil`.
   - Real unshare: the reload sees a new version, `refresh()` calls `clear()` (`:92-93`) and sets `errorKey = nil` (`:95`); the session is unchanged, so the message is written. The new test bumps the version (`revokeAccount()`), asserts version 2 and an empty account list, and fails under M1.
   - A more specific message wins: `accessEnded` (`:333`), `household.loadError` from `suspend(.unavailable)` (`:381`) and the membership mismatch (`:91`) all leave `errorKey` non-nil, so `:113` does not overwrite.
   - `isAvailable`: every reload path that leaves Households on ends with `availability == .available` (`:85`, `:95`, `accessEnded` `:329`). It is false only after `suspend(.disabled)` (no message is right, the surface is off), `suspend(.unavailable)` (already has a message) or a `bind` (`.discovering`, a new session state). So it cannot suppress the message while Households is on.
   - Identity: `sameSession` (`:327`) needs the same `revision` and the same `profile.id`. `revision` is the vault epoch (`SessionController.swift:141`), and `bind` clears `identity` for any non-authenticated phase (`:61`). A different signed-in person fails both comparisons. `current` uses the same function, so no other caller changed meaning.
2. **Close cancels the review.** `showManagement`'s `didSet` (`:34`) calls `cancelInvitationReview()` on every assignment of `false`: the Close button and "Not now" (`dismiss()` through the sheet binding, `HouseholdViews.swift:231`), swipe-down, `accessEnded` (`:331`), `suspend` (`:380`) and `bind` (`:64`). The two deleted explicit calls are covered by the didSet.
   - Stale answers: `previewInvitation` takes a ticket (`:155`); cancel (`:168`) and every newer preview rotate it; success (`:160`) and invitation outcomes (`:164`) are dropped for a stale ticket. My probe confirms the newer preview's secret is the one accepted.
   - In-flight accept: accept checks the reviewed secret once at `:186`, then runs from the journaled `pending` write and never reads `invitationReview` or `reviewedInvitation` again. Probe: close during an accept, the accept still joins, `pending` nil, `busy` false.
   - Spinner: `previewInvitation` never sets `busy`, and the view has no progress state for a preview, so a dropped answer leaves nothing spinning.
3. **`beginJoin`.** Returns `isAvailable` after the preview (`:180`). One production caller, `ConnectedCuadraoRoot.swift:27` (`== true`), feeding `InvitationsModel.handToHousehold` (`InvitationsModel.swift:217`), which shows `.householdUnavailable` on anything but `true`. A preview that turns the surface off or changes the session now gives that notice; an invitation outcome or a transport failure keeps `true` with the join step open and its own message. If the person closes the sheet during the preview it returns `true` and no notice, which is right.
4. **Link over the introduction.** `HouseholdManagement.swift:187-197`: `adoptHandedOver()` runs on appear and on change of `pendingInvitationToken`; it only fills the field. `handedOver` is set before `token`, so the field's own `onChange` (`:170`) does not cancel the review. The only preview is the one in `beginJoin` (`:179`); accept still needs a name and the Accept tap (`:179` of the view, `:186` of the model). Clearing the token re-fires the handler, which returns at the guard. No host test (view code), as the author says.
5. **Harness kind.** `InvitationsHarness.swift:128-130`: `group_link` only for a `FULL` prefix. Household secrets return before `kind()` (`:72`, `:78`). `lookup` (`:116-125`) is unchanged, so `expd-link-…`, `beta-link-…` and the code cases behave as before. The only client branch on preview kind is `.household` (`InvitationsModel.swift:207`).
6. **`accessEnded()`** is `private` (`:328`), with two callers, both in the file (`:87`, `:372`). No other reference in `ios/`.
7. **Board.** `a02e7d3ec` changes one line (row "2. Access and Household | 4", `argus-execution-board.md:82`), appending one sentence. No other lane commit touches the board. Both flags are `false` in `Development.xcconfig:42,45`, `Local.xcconfig.example:16-17` and `.env.example:224,230`, and absent from `render.yaml`. No Associated Domains entitlement or AASA file exists in the tree. Rows 4, 5–6, 7 and 8 are the "items 4 to 8". See F-4 for "verified against a local backend".
8. **Merge `06c7d7ef8`.** First parent is `aeaf1bca5`. In this lane's paths it changes only the board's "1. Trust and profile | 13–14" row, which is #790's own text. Household, Invitations and FinancialModelTests are untouched by the merge.

The author's account (`W2-last.md`) matches what I found. Its statement that non-outcome errors still go to `failed` after a cancel is accurate and is F-1.

## Findings

**F-1 (P3). A cancelled or superseded preview that fails for another reason still writes "household.loadError".**
- Where: `ios/ArgusFoundation/Household/HouseholdModel.swift:165`.
- Evidence: probe, preview held, sheet closed, then a 500: `invitationProblem` nil, `errorKey == "household.loadError"`, `showManagement` false. The person closed the join step and then sees a load error on the Household surface for a request they abandoned. Access answers (`households_unavailable`, a session change) should still apply, and do.
- Smallest fix: for a stale ticket keep only the access answer: `guard invitationReview == review else { _ = await resolveAccessFailure(error, householdId: nil); return }` before `:165` (this skips the session re-read in `failed`; if that matters, clear the `loadError` it wrote instead).

**F-2 (P3). A refused accept that lands after the close leaves its problem for the next join step.**
- Where: `HouseholdModel.swift:247` (line not changed in this delta; it is the remaining gap in "closing ends the review"). The Close button and swipe-down stay usable during an accept, because `.disabled(model.busy)` is on the Form only (`HouseholdManagement.swift:83-85`).
- Evidence: probe, accept held, sheet closed, then `409 invitation_consumed`: `invitationProblem == .used`, `errorKey` nil. Nothing is shown now, and the next time the join step opens it shows "already used" under an empty field.
- Smallest fix: at `:247` set `invitationProblem` only while `showManagement` is true; the existing `explained` logic then falls back to "household.changed" on the surface.

**F-3 (P3). The stale-outcome guard has no test, and the newer-preview case has no test of its own.**
- Where: `HouseholdModel.swift:164`; `HouseholdModelTests.swift:563-566` (the test server refuses before it reaches `previewGate`, so a failing preview cannot be held).
- Evidence: M7 passes all 49 tests. M3 is caught only through the close test.
- Smallest fix: let the gate run before the refusal in the test server, and add one case each for "refused after close" and "older answer after a newer preview" (my two probes do this in 20 lines).

**F-4 (P3). The board says "verified against a local backend" and links evidence that says the opposite.**
- Where: `docs/specs/argus-execution-board.md:82` links `docs/reports/evidence/cuadrao-household-invites/README.md`, whose lines 80-82 say "They do not prove a round trip against a local or hosted API. No local backend was started for this lane".
- Evidence: the claim is true in substance. `W7-live-invites.md` records a live local run at `6fb15a01` (HTTP journeys 112 of 113, every body decoded with the client's types, and a partial simulator pass with many journeys "not driven"). But that report is outside the repository, the README cites it only for stub shapes, and the run predates this head.
- Smallest fix: in the README, replace lines 80-82 with two sentences: the screenshots are simulated, and a separate live local run at `6fb15a01` checked the wire shapes and a partial app pass. Or soften the board to "wire shapes checked against a local backend at `6fb15a01`".

## Not verified

- UI tests and the two builds (not run here by instruction). Item 4 and item 5 rest on reading the code.
