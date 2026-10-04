# R-household-6fb15a01: independent review of `claude/cuadrao-household-invites-ios`

Head `6fb15a017`. Diff reviewed: `origin/codex/cuadrao-release-ui...HEAD`, excluding `docs/reports/evidence` (23 files, +1693 / -46).
Read-only. Nothing was built, run, or simulated; every finding comes from reading the client against `docs/api/openapi.yaml`, `docs/API_CONTRACT.md` and the backend in `src/argus`.

Paths below are relative to the checkout `/Users/garces/Documents/projects/repos/argus/.claude/worktrees/cuadrao-household`.

## Verdict

One P1, four P2, seven P3. The wire contract is faithful. The defects are in the client state machine around the gate and the link intent.

Reachability note that applies to F2, F3 and F9: no build registers the `argus-household` URL scheme or an Associated Domains entitlement (`ios/Config/Info.plist` has only the Google scheme; the two `.entitlements` files have no `applinks`). So iOS delivers no invitation link to the app today. Those findings are reachable now only through the DEBUG harness (`--harness-open-url`), and go live the day the scheme or entitlement is added, which is the lane's stated next step.

## Findings

### F1 (P1) The beta gate opens on any failed access check, including for a person the server already said is not admitted

- `ios/ArgusFoundation/Invitations/InvitationsModel.swift:80` and `ios/ArgusFoundation/Invitations/InvitationViews.swift:26`.
- `refreshAccess()` sets `admission = .unknown` on every error other than `invites_unavailable`, and `InvitationGateHost` renders the app for `.unknown`. It runs on every foreground (`InvitationViews.swift:31`), and it overwrites a previous `.required`.
- Reach: a signed-in, non-admitted person on a gate-on server puts the phone in airplane mode and foregrounds the app (or launches offline, or hits one 5xx). The gate disappears and the full shell mounts. The server does not enforce the gate on any other route (`BetaInviteRequired` is raised only in `create_beta`, `src/argus/domain/household/invites.py:164`; the contract says "The gate is read by the native app"), so the app then works normally once the network is back, until the next successful refresh.
- This contradicts decision 4 in `docs/specs/lanes/mvee-five-lane-handoff.md` ("The in-app code is the real gate") and infers admission from the absence of an answer. The code comment calls the gate "advisory"; no authority document does.
- Only matters when `ARGUS_BETA_INVITE_GATE_ENABLED` is on (default off).
- Smallest safe fix: on a failed refresh keep the previous `admission` when it was `.required` or `.admitted`; for a first check that fails, show a retry state instead of `content()`. If fail-open on first check is a deliberate product choice it needs the founder's decision recorded, since it defeats the gate.
- No test covers a failed access check.

### F2 (P2, latent, see note) A link redeems without confirmation, and the intent is not cleared after a failed redeem

- `InvitationsModel.swift:130-135` (`open`), `:147-148` (`continuePendingLink` calls `redeem` for `.required`), `:104-109` (redeem failure leaves `pendingLink` set), `:59-66` (`bind` never clears `pendingLink`).
- Three consequences, all from the same mechanism:
  1. A signed-in, not-yet-admitted person who opens any well-formed link has `POST /invites/redeem` sent at once. The handoff says the link "routes ... to the existing preview". A crafted link therefore chooses whose invitation admits the person (the who-invited-whom record and the sender's "accepted" notice follow the attacker's invite).
  2. After a definite failure (`invitation_not_found`, expired, revoked, consumed, full, 429) `pendingLink` stays. Every later `refreshAccess()` (each foreground) calls `continuePendingLink()` and redeems again. For an unknown token each retry keeps one failure in the server's budget (`src/argus/api/invite_limits.py`: 10 per hour per account), so a dead link foregrounded ten times locks the person out of typing a good code with `429 invite_rate_limited`.
  3. The intent survives sign-out. `InvitationPendingNotice` keeps saying "Your invitation is saved" for a link that already failed, and the next account to sign in on the device has it redeemed automatically.
- The household path is fine: it only previews, and accept needs a name and a tap.
- Smallest safe fix: in `redeem`'s failure branch clear `pendingLink` for every problem except `.unavailable`; clear `pendingLink` in `bind` when the previous identity was non-nil; for `.required` put the link's token into the gate for the person to submit (or preview first) instead of calling `redeem` directly.
- `testAFailedLinkShowsWhyAndKeepsManualCodeRecovery` passes with the bug because the manual success clears the intent.

### F3 (P2, latent, see note) "Flag off means the handler does nothing" holds only for the https link

- `InvitationsModel.swift:132`: the flag check is `isUniversal(url) && !universalLinksEnabled`. `argus-household://invite#...` is always accepted, and it now feeds beta redeem (F2) as well as the Household join.
- With the invites surface off (server default) `continuePendingLink` goes straight to `handToHousehold` (`:149-151`) with no server check of the token.
- Smallest safe fix: return false from `open` for every link while the flag is off, or state in the flag's comment that the legacy scheme is intentionally always on and restrict it to the Household preview.

### F4 (P2) With every flag off, the signed-in shell now waits behind a spinner for `/invites/access`

- `ios/ArgusFoundation/Connected/ConnectedCuadraoRoot.swift:14-17`, `InvitationViews.swift:21-23`, `ios/ArgusFoundation/Auth/ProfileAuthModel.swift:49`.
- `InvitationsModel` is always created and `InvitationGateHost` always wraps the authenticated shell. `bind` sets `.checking`, which renders only a `ProgressView` until the request answers. On the default server that answer is `404 invites_unavailable`, so behaviour ends the same, but each launch and each sign-in adds one round trip before `ConnectedCuadraoShell` mounts and starts its own loads. On a hung connection the wait is the session's 30 second request timeout (`SessionTransport.swift:28`). Before this lane the shell mounted at once.
- There is no client flag for the gate; `ARGUS_INVITE_UNIVERSAL_LINK_ENABLED` covers only the https link.
- Smallest safe fix: put the gate host behind a default-off client flag (same pattern as the universal-link flag) so flag-off is today's root view.
- Checked and clean: `SessionSnapshot.revision` is the vault epoch and changes only when the account epoch ends, so the shell is not torn down on token refresh.

### F5 (P2) Stub and test shapes the real backend cannot produce

- `ios/ArgusFoundation/Invitations/InvitationsHarness.swift:63-68`: the stub's `/preview` throws `409 invitation_expired / invitation_consumed / invitation_revoked / group_link_full`. Real `preview` (`invites.py`, `PostgresInviteStore.preview`) answers 200 with `available:false` for all of these; its only failures are `404 invitation_not_found`, `429 invite_rate_limited` and the 5xx.
- `ios/FinancialModelTests/HouseholdModelTests.swift:452` (`testPreviewOutcomesExplain...`) feeds `409 invitation_expired / consumed / revoked` to `household-invitations/preview`. Real `preview_invitation` (`src/argus/domain/household/postgres.py:199-219`) never raises them. The `expired`, `revoked` and `used` texts in `HouseholdInvitationOutcome.swift` are reachable only from accept.
- `InvitationsHarness.swift:106`: `rejected(status: 503, code: "invite_codes_unavailable")`. The real transport turns every status >= 500 into `SessionFailure.unavailable` with no code (`SessionController.swift:301`). Same end state, wrong shape. The unit case `(503, "invite_codes_unavailable")` in `InvitationsTests.swift:149` has the same issue.
- `InvitationsHarness.swift:60`: a beta create always returns `link`. The server returns `link: null` for beta invites unless `ARGUS_INVITE_UNIVERSAL_LINK_ENABLED` is on (`invite_codes.py`, `invite_link`). The default production shape (code only, no QR, no link) is decoded in a unit test but never driven through the screens.
- The stub has no `POST /group-links/{id}/revoke`, so the revoke swipe is untested.
- Smallest safe fix: make stub preview return 200 `available:false`; drop the three unreachable preview cases; throw `SessionFailure.unavailable` for DOWN; add one harness scenario with `link` null.

### F6 (P3) Group-link create can wedge on `idempotency_conflict`

- `InvitationsModel.swift:252`. The key is kept whenever the problem is `.unavailable`, and `idempotency_conflict` (409) maps to `.unavailable` (`Invitations.swift:189`). If a create commits but its response is lost, and the founder then changes any field (or leaves and returns, which resets the default expiry), every retry sends the old key with a new body and gets 409 until sign-out or relaunch. Founder only, needs a lost response.
- Fix: keep the key only for transport failures and 5xx, or map `idempotency_conflict` to a definite problem that retires it.

### F7 (P3) Group-link form errors show invitation-code copy

- `Invitations.swift:177` maps `validation_error` to `.invalid`; `invite_request_invalid` (422) is unmapped. The form does not enforce the server limits (`cap <= 10000`, label <= 80, expiry within a year; `invite_schemas.py`, `invites.py` `create_group_link`). A cap of 20000 shows "We don't recognize that code"; an expiry past a year shows "We couldn't check your invitation. Try again later."
- Fix: bound the three fields in the form.

### F8 (P3) Founder status and "nothing sent" are inferred from missing answers

- `InvitationsModel.swift:226` sets `groupLinks = nil` on any error and `InvitationViews.swift:235` reads nil as "not the founder". A transient failure of the list refresh that follows a successful create replaces the one-time link and code with "Only Lucas can create group links", and re-entering the screen drops them (`startGroupLink`). Fix: set nil only for `.founderOnly`.
- `InvitationViews.swift:124`: "You haven't sent any invitations yet." shows while the list is loading and after it failed, because `sent` starts empty. Fix: show it only when `personal` is `.ready`.
- `InvitationsModel.swift:57`: the Invitations row shows in `.unknown`, so a failed access check exposes the entry even when the server surface is off.

### F9 (P3, latent) Opening a Household link deselects the current Household before anything is confirmed

- `ios/ArgusFoundation/Household/HouseholdModel.swift:162-168`. `beginJoin` calls `select(nil)`, which clears the selection and writes nil to UserDefaults. A member of Household A who opens a link (valid or not) and taps "Not now" is left with no Household selected. Membership is untouched.

### F10 (P3) Smaller state races

- Concurrent `refreshAccess` calls (task, foreground, Household watcher) have no ordering guard beyond identity; a stale `admitted:false` that lands after a redeem's refresh puts the gate back until the next foreground.
- A second link opened while the first is mid-preview is dropped: the first call clears `pendingLink` when it returns (`InvitationsModel.swift:157`).

### F11 (P3) Client states with no server source

- `ReleaseInviteGateState.waitlist` via `.invitationRequired`: redeem never returns `beta_invite_required`; only `POST /invites` does, and that goes to an alert.
- Household preview `expired / revoked / used` (see F5).

### F12 (P3) Test gaps that let the above pass

- No test for a failed access check (F1), for the intent after a failed redeem or after sign-out (F2), or for the legacy scheme with the flag off (F3).
- `InvitationsModel` has no unit test; it is covered only through the UI harness.

## Verified clean

1. **Contract.** Paths, methods and bodies match `openapi.yaml` and `src/argus/api/routers/households.py`: `GET /invites/access`, `GET /invites`, `POST /invites` (`{}` plus `Idempotency-Key`), `POST /invites/preview` and `/redeem` (exactly one of `token` or `code`, no key), `GET` and `POST /invites/group-links` (`source_label`, `cap`, `expires_at` with zone, key), `POST /invites/group-links/{id}/revoke` (204). Household preview and accept send exactly one secret plus `display_name` on accept, which passes `extra="forbid"`. Every decoded field of `BetaAccess`, `SentInvitesResponse`, `BetaInviteCreatedResponse`, `InvitePreview`, `RedeemResult`, `GroupLinkView` and the Household `InvitationCreated` (`code`, `link`) matches name, type and nullability. Mapped codes match the backend: `invitation_not_found`, `invitation_expired`, `invitation_revoked`, `invitation_consumed`, `group_link_full`, `invite_rate_limited`, `household_invitation_requires_accept`, `beta_invite_quota_exhausted`, `founder_required`, `beta_invite_required`, `invites_unavailable`, `households_unavailable`, `account_conversion_required`, `verified_user_required`. Unmapped and falling to generic "unavailable": `invite_request_invalid`, `idempotency_conflict`, `idempotency_key_required`, `invite_codes_unavailable`.
2. **Three facts.** Apart from F1, nothing infers one from another. A group link or beta code only ever reaches `/invites/redeem`; Household membership comes only from `household-invitations/accept` after preview, a name and a tap; nothing in the lane touches account grants. After a Household accept the gate re-reads `/invites/access` instead of assuming admission. Copy on the personal, group and Household share screens states the separation.
3. **Honesty and secrets.** Quota, sent states, group usage and admission all come from server answers. A replayed create (no secrets) says so and does not invent a link. The full-link copy offers the waitlist and does not claim enrollment. No `print`, logger, analytics, pasteboard or UserDefaults use in the new files; secrets live in memory and leave only through `ShareLink` or text selection; tokens stay in the URL fragment and links with a query are rejected.
4. **Link validation.** `InvitationLink.token` checks scheme, host (`cuadrao.ai` exact, no port), path (`/invite`), non-empty fragment and no query; lookalike hosts, http and other paths are rejected, with unit tests.
5. **Release gating.** `InvitationsHarness.swift` is wholly inside `#if DEBUG` and its only reference in `ArgusFoundationApp.swift` is inside `#if DEBUG`. With the server surface off the Invitations row and gate do not appear. The new public `SessionSnapshot.init` weakens nothing: `financialRequest` is internal and requires the snapshot to equal the controller's own phase, revision and profile id, plus the vault epoch. The four ReleaseUI files still compile against the gallery (closure arity updated, `showsWaitlist` defaults true, `url` optional handled); `ReleaseUIJourneyTests` touches only `inviteGate.status.full`, `inviteGate.waitlist` and `personalInvites.remaining`, all unchanged; `HouseholdUITests` still gets the `argus-household://invite#` prefix from the server's `link`.
6. **Concurrency.** Gate submit is disabled while checking; personal create hides its button while loading and reuses one idempotency key for a lost response; every async result is dropped when the identity generation changed, and `bind` resets the gate so no spinner outlives a sign-out. Server-side redeem is idempotent per user.
7. **Copy.** Every new string has English and Spanish; no em dash in added lines.
8. **Tests.** The UI tests drive the real `InvitationsModel` and views and would fail if either were stubbed; the session unit tests assert exact request route, body, key and bearer.
