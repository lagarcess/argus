# Five-lane MVEE delivery handoff

**Status:** Lane contract. Founder decisions of 2 October 2026 are written in as contract and acceptance. This file assigns no worker, merge, hosted change, or deployment.
**Integration:** `codex/private-alpha-next` at `d9a7acfcfc9970edb07fee2cbbd1c21e19536772`, 2 October 2026. That commit is `d9a7acfc`, which includes landed PR #776. Remote integration matched this SHA at the time of writing.
**Decisions:** [decision log, October 2 lane locks](../argus-decision-log.md#october-2-2026-cuadrao-lane-locks). That section arrives with PR #780. This file links there and does not restate the rationale.
**Design checkout to preserve:** `codex/cuadrao-design-scan-recents` at `8f521518`. That branch owns Cuadrao UI chrome and has already diverged from integration. Delivery lanes do not edit its files and do not merge it.
**Product owner:** [MVEE](../argus-minimum-viable-ecosystem-experience.md). This handoff links to that owner. It does not copy a second scope list.
**Execution map:** [execution board](../argus-execution-board.md).

The lanes below land on integration one at a time, in the order under [Landing order](#landing-order), through one integration captain. The team is small, so lanes are built one after another, not in parallel.

## Decisions this handoff implements

Lucas locked rows 1 to 10 on 2 October 2026. Row 11 and the extras listed under the table are Head of Engineering delivery decisions, not founder locks. The reasons and wording for the founder locks live in the [decision log](../argus-decision-log.md#october-2-2026-cuadrao-lane-locks). The right column says where each one lands and what the code has today.

| # | Decision | Lane | Today on `d9a7acfc` |
| --- | --- | --- | --- |
| 1 | An invite is a cuadrao.ai universal link plus a code plus a QR. Household email is out of scope for this pass | Household | Share link only, with the unregistered `argus-household://invite#` scheme. No code, no QR, no universal link |
| 2 | Each code works once and records who sent it. The inviter gets an "invitation accepted" notice | Household, then Updates | Single use exists (`invitation_consumed`). Sender is `created_by`. No notice |
| 3 | On account deletion, keep an anonymous record that an invite was sent and accepted, with no name or user id | Household | Not there. `created_by` and `accepted_by` are set to null on delete, so the count of people is lost |
| 4 | 3 invites per user to start, more at Lucas's discretion. The in-app code is the real gate. A TestFlight public link only installs the app. No code means the cuadrao.ai waitlist | Household | No quota, no code gate, no TestFlight link |
| 5 | Three network numbers from day one: invites sent per user, share of invites accepted, share of invitees who invite someone | Household | No event and no durable record |
| 6 | A comparison against a zero month shows the amount difference, not a percent. A month with no records shows as no data | Home | No series on the API. `financial-home` returns zero strings for a month with no records |
| 7 | A bill appears in Updates 3 days before its due date and on the due date | Updates | No inbox, no trigger |
| 8 | Updates go to the in-app inbox, plus push for people who turn it on. Push never shows amounts. No email for updates | Updates | No inbox, no push code |
| 9 | Joint-plan export waits until after TestFlight | None in this pass | The read-only departure archive from #773 stays |
| 10 | When a member leaves, their account goes with them. The household keeps that account's history up to the move, greyed out and read-only, with the state at the move recorded. Moves are idempotent events and never rewrite past balances or settlements. Home recomputes from history. Explicit per-role access rules in RLS and API checks | Account moves | Leave revokes grants and the household sees nothing afterward. No move command, no locked history |
| 11 (HoE) | Landing order: Household, space list on its own, Search, Home series, account moves, Updates | All | Not applicable |

Head of Engineering delivery decisions that go with decision 10. These are not founder locks:

- Locked history is read-only for everyone, the owner included. The one exception is the account-deletion path in lane 2.
- Account moves need a manual Codex review plus a dedicated eval before landing.
- A member, including the household admin, reads a departed member's locked history only if they had an explicit grant to that account at the cut-off.
- The departure event is written by the system when a member leaves or is removed, not by the admin or the member.

Already locked before today and still in force: the [Household permission policy](household-permission-policy.md) of 1 October, except where decision 10 narrows what happens on departure. Also still in force: the MVEE visibility rules, and the rule that a plan stays in the space where it was created.

## Build environment and how iOS lands

The current build box is Linux with no Swift and no Xcode. CI has no macOS job. Backend, database, and docs pieces are built and tested here. iOS pieces are not compiled here.

iOS pieces still land. The rule is:

- Each lane's iOS work goes in its own small PR, separate from that lane's backend PR.
- The iOS PR is behind a default-off flag and its body says it was not compiled on a Mac.
- The captain lands it as **landed unverified, Mac pass by Lucas's local agent**.
- Lucas's local Mac agent builds and verifies the landed commit. If it needs a fix, it returns a fix PR, and this team takes that PR over and lands it.
- If an iOS PR breaks the build, revert only that PR. The backend PR stays.

Each lane below marks its iOS parts this way. None of them is described as blocked.

## Outside services: fakes behind default-off flags

Lucas supplies some outside pieces later. The wiring lands now. Each outside piece sits behind an adapter with a fake, and a flag that defaults off. Turning a piece on later is configuration plus the real adapter, not a rewrite.

Flag convention to follow: backend flags are `ARGUS_<SURFACE>_ENABLED`, read once and treated as on only for `1`, `true`, `yes`, or `on`, as `households_enabled()` in `src/argus/api/households.py` does. Unset means off, and an off surface answers `404` before auth. iOS flags are xcconfig keys copied into `Info.plist` and read with `Bundle.object(forInfoDictionaryKey:)`, as `ARGUS_AUTH_ENABLED` does in `ios/Config/Development.xcconfig`, `ios/Config/Info.plist`, and `ios/ArgusFoundation/Auth/NativeAuthConfiguration.swift`.

The flag names below are proposals. The captain confirms the final name in the lane PR.

| Outside piece | Lucas supplies | Lands now | Proposed flag or setting |
| --- | --- | --- | --- |
| cuadrao.ai universal link | AASA file on cuadrao.ai and the Associated Domains entitlement | Server link builder for `https://cuadrao.ai/...`, iOS link handling | `ARGUS_INVITE_UNIVERSAL_LINK_ENABLED`, backend and iOS. Off keeps today's share link |
| TestFlight public link | The link itself | A setting the app reads and shows with the invite | `ARGUS_TESTFLIGHT_PUBLIC_URL`. Unset means no install link is shown |
| Code gate and waitlist | The cuadrao.ai waitlist page | Code check and the redirect to the waitlist | `ARGUS_BETA_INVITE_GATE_ENABLED` and `ARGUS_WAITLIST_URL` |
| Push | APNs key | Device registration, a push sender interface, and a recording fake that keeps payloads for tests | `ARGUS_UPDATES_PUSH_ENABLED`. Off uses the fake and sends nothing |
| Email | A cuadrao.ai sending domain in Resend | Nothing. Household email delivery and update email are out of scope for this pass | None |

Lane surfaces with no outside piece also start default-off, one flag each: `ARGUS_FINANCIAL_SPACES_ENABLED` for the space list, `ARGUS_ACCOUNT_MOVES_ENABLED` for moves, `ARGUS_HOME_SERIES_ENABLED` for the series, and `ARGUS_UPDATES_ENABLED` for the inbox. Search documents stay behind the existing `ARGUS_DOCUMENT_EXTRACTION_ENABLED`.

**Email.** Household email delivery is out of scope for this pass. A Resend adapter already exists: `send_resend_email` in `src/argus/domain/resend_email.py`, sending through Resend SMTP from `noreply@get-argus.com` with `ARGUS_APPROVAL_EMAIL_SMTP_PASSWORD`. It is used by `src/argus/api/feedback_notification.py` and `src/argus/domain/access_approval_email.py`. What is missing is a cuadrao.ai sending domain. When Household email comes back, it reuses this adapter with that domain and does not add a second mail client.

**Push today.** No APNs, `UNUserNotificationCenter`, or device-push code exists under `src/` or `ios/`. `financial_shortcut_device_tokens` stores Shortcuts enrollment tokens for ingestion. It is not a push token table and is not reused for push. `reminders_opted_in` and `reminders_opted_out` in `src/argus/observability/analytics_events.py` are analytics events only.

**Universal link today.** No `CFBundleURLSchemes`, associated domain, `applinks:` entry, or `onOpenURL` handler exists under `ios/`. The string `cuadrao.ai` appears nowhere in code or config.

## Contracts between lanes

Household owns permission rules. Other lanes call that owner. They do not store a second grant, a second membership, or a client-side allow list.

Account moves own what a move does to history, plans, Home, and Search. The account id stays the same. Current assignment changes by `space_id`. Historical balances, corrections, and settlements are not rewritten and are not copied onto the destination. The move is an idempotent event. Budget and goal rows stay in the space where they were created. Their inclusion of the account's activity changes with `space_id`. Home and Search read the same `space_id` and recompute from canonical history. They do not keep a private copy of which space an account is in, and they do not keep a copied series.

Updates consumes events from the lane that owns the fact. It stores read state and a source link. It does not copy the amount, the draft, or the invitation token into the inbox row. Display text is read from the current source at open time, so a revoked grant, an approved draft, or a paid bill cannot leave a stale private fact in the inbox.

### Source link

This shape is a technical contract for these lanes. It reuses ids that already exist.

```json
{"kind":"account|activity|expectation|budget|goal|debt|bill|document|conversation|invitation","id":"<uuid>","household_id":"<uuid or null>"}
```

| `kind` | `id` is | Open with |
| --- | --- | --- |
| `account` | `financial_accounts.id` | Existing account detail |
| `activity` | Logical activity id, never a leg or an old revision | Existing activity detail |
| `expectation` | Personal expectation id | Existing Plan expectation editor |
| `budget`, `goal`, `debt` | That plan's id | The existing Search open path in `FinancialSearchModel.open` |
| `bill` | Shared plan id whose `PlanRef.kind` is `bill`, or a personal expectation whose kind is `bill` | The owner already used by Household plan detail or the personal expectation editor. `household_id` is set only for the shared plan |
| `document` | `connection_id` from `/api/v1/financial-documents` | `GET /api/v1/financial-documents/{connection_id}` and, for bytes, `GET /api/v1/financial-documents/{connection_id}/source` |
| `conversation` | `conversations.id`, the same id `GET /api/v1/search` returns as `SearchItem.conversation_id` | The existing conversation reader. There is no native conversation screen in the connected shell today. Chat on that shell is still `ChatSampleView` |
| `invitation` | `household_invitations.id` | Household. Used only for the inviter's "invitation accepted" row. The token is not part of the link |

`household_id` is null for a personal record. It is set only for a household-authorized projection. Opening the link rechecks current Household permission. Failure uses the same unavailable destination Search already shows. A document link never carries `source_bytes`, a storage object key, or a bucket path.

Personal financial search and conversation search stay separate HTTP APIs. `GET /api/v1/search` returns conversation dossiers. `GET /api/v1/financial-search` returns financial records. The client can show them in one list. The server does not merge those stores.

## Landing order

One integration captain lands one lane at a time onto `codex/private-alpha-next`. The captain reconciles the current integration into the worker branch by merge, never by rebase, then lands the worker through its PR. Each lane may land as a backend PR and a separate iOS PR.

1. **Household.** Universal link, code, QR, single-use code with sender, the anonymous invite record, quota, code gate, and the three numbers. No email.
2. **Space list on its own.** Space rows, unique names, archive, and a new account choosing a space. No move of an existing account. This is the one `space_id` writer later readers use.
3. **Search.** Document and conversation hits and opens, so Updates has real destinations.
4. **Home series.** Derived from canonical history, filtered by the account's current space, with decision 6 for comparisons.
5. **Account moves.** Leaving a household with locked history, and moving an account between spaces. Manual Codex review and the dedicated eval before landing.
6. **Updates.** Inbox, bill rows, draft-ready rows, the inviter's accepted notice, and opt-in push without amounts.

A lane does not wait on an outside piece Lucas supplies later. It lands with the fake and the flag off.

## Codex review

Codex review is not a merge gate except where this file says so. Request it for work that changes durable money, authorization, or schema.

| Lane | Review |
| --- | --- |
| Household | Yes. The code store, the anonymous record, and the quota are schema and authorization work |
| Spaces list | Yes. The space table is migration and authorization work |
| Search | Yes if a query can return another owner's document or conversation. No for a read-only adapter that calls the existing document and conversation owners and adds no table |
| Home | Yes if the series is a new stored table. No if it is derived inside the existing financial-home read from canonical activity and balance observations |
| Account moves | Required. A manual Codex review plus the dedicated eval in that lane, both before landing |
| Updates | Yes for the inbox table, its RLS, the device token table, and any trigger |

## Shared file ownership

| Files | Writer | Rule |
| --- | --- | --- |
| `ios/ArgusFoundation/Cuadrao/**`, `ios/DesignPreviewTests/**`, `ios/ArgusFoundationUITests/Cuadrao*Design*`, `ios/ArgusFoundationUITests/CuadraoHomeChartUITests.swift`, navigation icons, `.agent/designs/cuadrao/` | Design lane on `codex/cuadrao-design-scan-recents` | Do not edit. `CuadraoUpdatesCanvas.swift` exists only on that branch |
| `ios/ArgusFoundation/Connected/ConnectedCuadraoShell.swift`, `FoundationShell.swift`, `CuadraoNavigationBar.swift`, `AppDestination` | One native navigation writer, assigned by the captain for the landing that changes tabs or the bell | Other lanes add a destination handler beside these files and hand the wiring to that writer |
| `docs/API_CONTRACT.md`, `docs/api/openapi.yaml`, `ios/Packages/ArgusSession/Sources/ArgusSession/*.swift` public types | The lane that owns the contract, one landing at a time | Swift types match the contract. No second client model of money or permissions |
| `ios/ArgusFoundation/Resources/en.lproj/Localizable.strings` and `es-419.lproj/Localizable.strings` | Captain, at the landing | The design branch has already diverged both files. Lane PRs list new keys in the PR. They do not edit the strings files |
| `supabase/migrations/*.sql` | The domain owner, one new file per landing, version assigned by the captain | Latest on this tip is `20261003130000_financial_document_drafts.sql`. New files sort after it. Do not edit a migration that is already on integration |
| `ios/Config/*.xcconfig`, `ios/Config/Info.plist`, entitlements | Captain, at the iOS landing | New flags and the Associated Domains entry are added once, by the captain |
| `docs/specs/argus-execution-board.md` | Captain | Lane PRs do not rewrite historical landing records |
| `docs/specs/argus-decision-log.md` | Docs seat | Lane PRs link to it. They do not edit it |

## Still open

These are not founder locks yet. Each one blocks only the piece named. Everything else in this file can be built.

1. **Is the beta invite the same code as a household invite?** Today a household invitation can only be created by the household admin, and accepting it grants household membership and nothing else (1 October policy). Decision 4 gives every user 3 invites and makes the code the gate into the app. Someone can be invited into the beta without joining a household. The recommended reading is two kinds of invite that share the same link, code, QR, and who-invited-whom record: a beta invite any user can send, inside the quota, that admits a person to the app; and the existing household invitation, admin-only and membership-only. Iris and Lucas confirm before the quota and gate are coded. The link, code, and QR presentation for household invitations does not wait.
2. **Locked household history when the owner later deletes their account.** Decision 10 keeps a read-only copy of a departed member's pre-move history for the household. Decision 3 and Apple's rule say deleting an account actually removes it. The recommended reading is that deletion removes the locked copy too, and the household sees that a former member's account was removed. The Head of Engineering has written that reading into lane 2 as the delivery contract, through a dedicated deletion path, so the departure piece can be built. Lucas can still reverse it. If he does, only the deletion path changes.
3. **How the code gate fits the existing access gate.** `ARGUS_PUBLIC_ACCOUNT_ACCESS_ENABLED` and the `private_alpha_allowlist` table already decide who can sign up and sign in, and the [API contract](../../API_CONTRACT.md) says public registration has been open in production since 12 August 2026. Turning that flag off to gate the beta would also close web registration. The code gate gets its own flag and does not flip the existing one. The exact way a redeemed code admits a person is a technical design item in the Household PR, under Codex review.

## Next steps for Lucas

These are the pieces only Lucas can hand over. Each lane lands without them, with the fake and the flag off. Turning a piece on is a separate, explicit step after he supplies it.

1. **A cuadrao.ai sending domain in Resend.** The Resend adapter already exists and sends from `noreply@get-argus.com`. The domain is needed only when Household email comes back into scope. Nothing in this pass sends email.
2. **The cuadrao.ai universal link.** Host the `apple-app-site-association` file on cuadrao.ai and confirm the app's Team ID and bundle id for its `applinks` entry. The captain then adds the Associated Domains entitlement in the iOS PR. Until both exist, `ARGUS_INVITE_UNIVERSAL_LINK_ENABLED` stays off.
3. **APNs key** for push. Until then `ARGUS_UPDATES_PUSH_ENABLED` stays off and the recording fake is used.
4. **The TestFlight public link.** Until then `ARGUS_TESTFLIGHT_PUBLIC_URL` stays unset and no install link is shown.
5. **Schedule Apple's first external beta review.** Apple must approve the first build for external testing before the TestFlight public link works for outside testers. Put that review on the calendar before the first distribution.

Also needed later, not secret: the cuadrao.ai waitlist page URL for `ARGUS_WAITLIST_URL`. The waitlist page itself is not in this repository.

## Lane 1. Household invitations

**MVEE:** [section 12](../argus-minimum-viable-ecosystem-experience.md#12-household-collaboration-approved-minimum-capacity), invitation delivery, and the [permission policy](household-permission-policy.md). Board rows for #763, #766, and #773. Decisions 1 to 5.

### Journey and completion

A registered admin creates a household and shares one invitation. It shows as a cuadrao.ai link, a short code, and a QR of that link. All three resolve to the same invitation. The recipient, on their own sign-in, opens the link, scans the QR, or types the code, previews, and accepts. They see no accounts until an owner shares one. The code works once. A second use fails with the existing `invitation_consumed` error. Revoke and expiry fail with the existing `invitation_revoked` and `invitation_expired` errors. The same acceptance retried with the same idempotency key does not create a second membership. The inviter later gets an "invitation accepted" row in Updates, once that lane lands.

The beta gate, once open item 1 is confirmed: each user starts with 3 invites. Lucas can add more. A person without a valid code who installs from the TestFlight public link is sent to the cuadrao.ai waitlist. The TestFlight link only installs the app.

Completion is the link, the code, and the QR against Postgres, English and Spanish, relaunch, and a third registered user who gets `404` for the household. No email is sent.

### What exists and is reused

| Piece | Where | Reuse |
| --- | --- | --- |
| Membership API | PR #763 `fbcc399b`. Flag `ARGUS_HOUSEHOLDS_ENABLED` in `src/argus/api/households.py`. Routes in `src/argus/api/routers/households.py` | Reused as is. Code and QR are a presentation of the same invitation |
| Invitation table | `household_invitations` in `supabase/migrations/20261001090000_household_membership.sql`: `token_hash` unique, `created_by`, `expires_at`, `revoked_at`, `accepted_by`, `accepted_at`. `accepted_membership_id` added in `20261001120000_household_consent_recovery.sql` | Reused. `created_by` is the sender for decision 2 |
| Token | `secrets.token_urlsafe(32)`, stored as a hash, returned once. TTL seven days, `INVITE_TTL` in `src/argus/domain/household/repository.py` | Reused for the link. The token is too long to type, so the code is new |
| Single use | `accept_invitation` in `src/argus/domain/household/postgres.py` locks the household and the invitation row `for update`. `invitation_consumed`, `invitation_revoked`, `invitation_expired` in `errors.py` | Reused |
| Idempotent commands | `household_command_receipts` keyed by actor, operation, and idempotency key, in `20261001120000_household_consent_recovery.sql`, used by `src/argus/domain/household/commands.py` | Reused for code redemption and quota grants |
| Access rules | RLS is on for all four household tables. `20261001090000` defines `households_member_select`, `household_members_peer_select`, `household_invitations_admin_select`, and `household_account_grants_member_select` with `is_active_household_member`. `20261001120000` then revokes all client privileges on those tables, so only the API service reads and writes them | Same pattern for new tables: RLS on, client privileges revoked, service writes, API checks the role |
| Native share | `ShareLink` in `ios/ArgusFoundation/Household/HouseholdManagement.swift` shares `argus-household://invite#` plus the token and shows it at `household.invite.link`. Paste-to-preview at `household.invite.input`. `ios/ArgusFoundationUITests/HouseholdUITests.swift` expects the `argus-household://invite#` prefix | Kept while the universal-link flag is off |
| Existing access gate | `ARGUS_PUBLIC_ACCOUNT_ACCESS_ENABLED` in `src/argus/api/guest_access.py`, the `private_alpha_allowlist` table, and `POST /api/v1/auth/access-requests` | See open item 3. Not flipped by this lane |

Not there, on integration or on the design branch at `8f521518`: a household invite code, a household QR (the only QR is the plan-group sample in `CuadraoGroupCodeCard.swift` on the design branch, which says it joins no real group), a universal link, a quota, a durable who-invited-whom record, and any network event. The `cohort` string on `signed_in`, `session_started`, `landing_viewed`, and `first_answer_shown` in `src/argus/observability/analytics_events.py` is a campaign code. It is not a person and is not the referral record.

### What is new

- **Code.** A short human-typeable code for each invitation, stored only as a hash beside `token_hash`, unique while the invitation is live, single use, with the same expiry and revoke rules. New migration.
- **Universal link.** The server builds `https://cuadrao.ai/invite#<secret>` when `ARGUS_INVITE_UNIVERSAL_LINK_ENABLED` is on. The secret stays in the URL fragment, as today's link does, so it never reaches a web server log. Off keeps today's link.
- **QR.** The QR encodes the same link. It is drawn on the device. No QR image is stored.
- **Who-invited-whom record.** One row per invitation that records send and accept, and the invitation that brought the sender in, if any. Live sender and acceptor user ids are kept beside it and cleared on account deletion. The row itself keeps no name, email, or user id once that happens. That keeps decision 3: counts and the "invitee invited someone" chain survive, and the deleted person is gone. New migration.
- **Quota.** 3 invites per user to start, with a grant command Lucas uses to add more. Counted from the who-invited-whom record, not from PostHog.
- **Code gate.** Behind `ARGUS_BETA_INVITE_GATE_ENABLED`, after open item 1. With the gate on, a signed-in user with no redeemed code gets the waitlist response, using `ARGUS_WAITLIST_URL`.
- **Three numbers.** Invites sent per user, share accepted, and share of invitees who send an invite of their own. Computed in SQL from the who-invited-whom record. A PostHog event, if added, goes through the closed registry in `analytics_events.py` and carries no person id.

### iOS parts: landed unverified, Mac pass by Lucas's local agent

- Code and QR screens beside the existing share link in `ios/ArgusFoundation/Household/`.
- Code entry on the recipient preview.
- Universal-link handling that routes `https://cuadrao.ai/invite#...` to the existing preview, behind the iOS flag. The Associated Domains entitlement waits for Lucas's AASA file (next step 2).
- Showing the TestFlight public link from `ARGUS_TESTFLIGHT_PUBLIC_URL` and the waitlist hand-off.

### Allowed files

`src/argus/domain/household/`, `src/argus/api/routers/households.py`, `src/argus/api/households.py`, one new migration, `ios/ArgusFoundation/Household/`, `ios/Packages/ArgusSession/Sources/ArgusSession/Household.swift`, `tests/household/`, and the Household section of the API contract and OpenAPI when this lane is landing.

No-touch: grant semantics in `_end_membership` (account moves owns the departure change), `CuadraoHousehold*.swift`, `CuadraoGroupInvitation.swift`, `CuadraoGroupCodeCard.swift`, financial account ownership, Plan math, `resend_email.py`, and email templates.

### Acceptance

Backend, on this box: two real users and a third who is denied, against Postgres. Create, then preview and accept by link token and by code for the same invitation. A second use of the code fails with `invitation_consumed`. Revoke and expire fail with the existing errors. Retry a lost accept response and get one membership. The who-invited-whom row records sender and accept. Delete the acceptor's auth user, then the sender's: the counts and the chain are unchanged and no row holds either user id, name, or email. A fourth invite beyond the quota is refused, and a grant from Lucas allows it. With `ARGUS_BETA_INVITE_GATE_ENABLED` on, a user without a code gets the waitlist response. With it off, behavior is today's. With `ARGUS_HOUSEHOLDS_ENABLED` off, `404 households_unavailable` before auth. No email is sent.

iOS, by Lucas's local agent after landing: share, code, and QR show the same invitation in English and Spanish. Code entry and QR scan reach the existing preview. Relaunch both clients. With the universal-link flag off, the existing `HouseholdUITests` prefix test still passes.

## Lane 2. Spaces

**MVEE:** [Financial spaces](../argus-minimum-viable-ecosystem-experience.md#financial-spaces), [managing private spaces](../argus-minimum-viable-ecosystem-experience.md#managing-private-spaces), and [reassigning accounts](../argus-minimum-viable-ecosystem-experience.md#reassigning-accounts-between-spaces). Board row D04. Decision 10 and 11.

Spaces lands in two separate slots: the space list in slot 2, and account moves in slot 5. They are described together here because they share the table.

### Space list, slot 2

Personal already exists for every account because `space_id` defaults to `personal`. The person creates one named private Business space and one named Custom space. Names are unique among their spaces, including archived ones. A new account chooses a space. Archive keeps the records. Delete is only for an empty private space. Personal cannot be renamed, archived, or deleted. An archived space cannot be the source or the destination of a move. Unarchive it first. This slot ships one Business and one Custom space per user, archive, and restore. It does not ship a purge job or an unlimited entitlement. It does not move an existing account.

### Account moves, slot 5

Two kinds of move, both under decision 10.

**Leaving a household.** When a member leaves or is removed, the accounts they own go with them, as today. That includes an account they had shared with the household: it moves with its owner. New: a server-side function runs when a member leaves or is removed. It writes the departure event, keyed for idempotency, and records the cut-off before grants are revoked. Neither the admin nor the member writes move events directly. The cut-off is the account, each grant that existed at that moment, and the exact activity and balance revisions those grants could see. The household keeps a locked, read-only, greyed-out copy only for the members who had an explicit grant to that account at the cut-off. Nobody gets locked history they could not see at the cut-off. That keeps rule 3 of the 1 October policy: an account is visible only through an explicit grant. Nobody can create, edit, or delete locked history, including the owner and the admin. The only exception is account deletion, below. The owner keeps editing their own account. A later correction to an old record is a new revision in the owner's history and does not change the household's locked view.

**Account deletion.** When the owner deletes their account, a dedicated server-side deletion function removes that user's rows and the household's locked copy of that history. This follows the recommendation in open item 2 and Apple's account-deletion rule. The household then sees that a former member's account was removed. This function is new. Today a registered user asks for deletion through `account_deletion_request` on `POST /api/v1/feedback`, and no in-app deletion function exists.

**Moving between spaces.** The person moves a standalone account from Personal to Business. The account id is unchanged. Opening balance, activity, corrections, and notes still load. No new transaction appears. A budget that included the account stops including it in Personal and the budget row does not move. A goal or debt plan linked to the account still opens and points at the same account id. Household grants on that account are unchanged. An account with a transfer, payment, cross-account refund, loan link, or unfinished document draft cannot be moved, and the screen explains the link.

### Move invariants

- Do not rewrite historical balances, opening balances, corrections, or settlements. Do not copy them onto the destination.
- Each move is an event: account id, kind (space or departure), source, destination, actor, time, and an idempotency key. The owner creates space moves through the move command. Departure events come only from the system departure function. The account id does not change. `space_id` is the current assignment only.
- The same idempotency key replayed is a no-op that returns the first result. A failed move leaves one end state, source or destination, with history intact.
- Home series and comparisons are recomputed from canonical history. They are not a snapshot copied onto the new space.
- Locked household history pins revisions. It never references a revision written after the cut-off.

### Access rules per role

New tables follow the household pattern: RLS on, all client privileges revoked, the API service writes, and the API checks the role on every route. Locked history and move events are append-only. The service role gets select and insert only on them. A trigger rejects update and delete for every role, ordinary service-role writes included, because the service role bypasses RLS. The trigger's one exception is the new account-deletion function, which removes the deleting user's rows and the household's locked copy of their history. Nothing else can change or remove them.

| Role | Move events | Locked household history | Live account |
| --- | --- | --- | --- |
| Account owner | Create own space moves through the move command. Read own. No departure events | Read. No create, edit, or delete. Removed only by the account-deletion function | Full owner rights, unchanged |
| Household admin | Read departure events for the household. Never writes them | Read only if the admin had an explicit grant to that account at the cut-off. Otherwise none. No create, edit, or delete | Only what a live grant allows |
| Member who had an explicit grant at the cut-off | None. Never writes them | Read. No create, edit, or delete | None after departure |
| Member with no grant at the cut-off | None | None | None |
| Anyone else | None, `404` | None, `404` | None |
| System departure function | Insert the departure event once per idempotency key | Insert at the cut-off only | None |
| Account-deletion function, new | Remove the deleting user's events | Remove the household's locked copy of that user's history | Remove that user's rows |
| Other service-role writes | Insert space moves once per idempotency key. No update or delete | No update or delete | Existing writes |

Reused: `financial_accounts_owner_select`, `financial_records_owner_select`, and `financial_record_revisions_owner_select` in `supabase/migrations/20260928200000_financial_accounts_first_slice.sql`; `is_active_household_member` and `household_account_grants_member_select` in `20261001090000_household_membership.sql`; the client-privilege revoke in `20261001120000_household_consent_recovery.sql`; `household_command_receipts` for idempotency; and the revision-pinning pattern of `household_plan_archived_activities` in `20261002020000_shared_plan_retained_revision_scope.sql`, which already pins exact activity revisions when a shared plan's owner departs.

### Reconciliation cases the lane must test

- Opening balance and later corrections stay the same rows and revisions. The move does not write a new opening balance.
- Recorded activity amounts and dates are unchanged. A month with no records stays no data.
- A settlement between two accounts, including a transfer or a payment, is not rewritten. Moving one account in a linked pair is blocked, and both histories stay put. The same block covers a cross-account refund, a loan link, and an unfinished document draft.
- Backfill after the move: a correction or an activity dated before the move appends to canonical history. It does not create a destination copy, does not rewrite the pre-move revision, and does not change locked household history.
- Repeating the same move with the same key is a no-op: one event, one assignment.
- An interrupted move retries to the same end state. Never in both spaces, and history is never half-copied.
- Home series and the comparison read after the move match a fresh computation from canonical history for the destination space.
- Household grants, budget rows, and goal rows keep their ids.
- After a departure, an update or delete on locked history fails for the owner, the admin, and ordinary service-role writes.
- After a departure, a member or admin who had no grant to the account at the cut-off reads no locked history for it.
- Replaying the departure with the same key writes no second event and no second cut-off.
- The owner's account deletion removes their rows and the household's locked copy, and nothing else.
- A move from or to an archived space is rejected.

### Dedicated eval

The move needs a manual Codex review and a dedicated eval before landing. The eval runs the cases above against Postgres. It fails if any historical balance, correction, or settlement row changes, if a move event is missing or duplicated, if locked history can be changed by anyone other than the account-deletion function, if anyone reads locked history they could not see at the cut-off, or if the Home series differs from a fresh read of canonical history.

### What exists and is reused

| Piece | Where |
| --- | --- |
| Column | `financial_accounts.space_id text not null default 'personal'` in `supabase/migrations/20260928200000_financial_accounts_first_slice.sql`. The [first-slice spec](financial-accounts-first-slice.md) says no route reads or writes it |
| Domain | `PERSONAL_SPACE = "personal"` in `src/argus/domain/recording/accounts.py`. `AccountFacts` has no space field. Household grants must not rewrite `space_id` |
| Departure today | `_end_membership` in `src/argus/domain/household/postgres.py` revokes grants in both directions in the same transaction as `left_at`. Remaining members then see nothing of the leaver's accounts. Plans the leaver shared become the archived read-only projection from #773 |
| Canvas | `CuadraoSpacesPreview.swift`, `CuadraoSpacesSheet.swift`, `CuadraoSpaceSelector.swift` on the design branch. In-memory spaces. No move action |

### What is new

- A space table owned by the user, with the account's `space_id` pointing at it. Personal is the default row and cannot be deleted. Slot 2.
- A move command, a move event table, the link check, and the budget-inclusion update. Slot 5.
- The locked household history table, the system departure function that records the cut-off before grants are revoked, and the dedicated account-deletion function. Slot 5. The API contract and data model departure paragraphs change in the same PR, because today they say remaining members lose access.

### iOS parts: landed unverified, Mac pass by Lucas's local agent

- Space picker on new-account entry and the space list screens. Slot 2.
- Move review and blocked-link explanation on Manage account. Slot 5.
- Greyed-out, read-only rendering of locked household history. Slot 5.

### Allowed files

`src/argus/domain/recording/accounts.py` and the account repository that writes `financial_accounts`, a new space module beside it, `src/argus/api/routers/financial_accounts.py`, `src/argus/domain/household/postgres.py` and `repository.py` for the departure cut-off only, one new migration per slot, the account and Household departure sections of the API contract and data model when landing, and the account and household tests.

Budget inclusion changes go through the existing budget reader, which already filters by `account_ids`. Spaces does not fork budget math.

No-touch: `CuadraoSpaces*.swift`, document storage, the chart canvas.

### Acceptance

Slot 2: Postgres. Create Business and Custom, relaunch, and see the same names. A second user cannot list the spaces. Delete is rejected while the space has an account. Personal delete and rename are rejected. `ARGUS_FINANCIAL_ACCOUNTS_ENABLED` off still `404`s the new routes, and the new space flag off does too.

Slot 5: the reconciliation cases and the eval pass. Move a standalone account, relaunch, and read the same activity on the same account id in the new space. A linked transfer blocks the move and leaves every row in place. After a departure, members who had a grant at the cut-off read the locked history greyed out and cannot change it. Members without one see nothing of it. iOS screens are checked in English and Spanish by Lucas's local agent after landing.

## Lane 3. Search coverage

**MVEE:** [Search](../argus-minimum-viable-ecosystem-experience.md#search-find-what-i-already-know). Board lane for #751. Documents are the #776 contract. Conversations stay on `GET /api/v1/search`.

### Journey and completion

The person searches from the connected Search tab. Existing results still open account, activity, expectation, budget, goal, and debt detail, and Back returns to the same query, filters, and scroll origin. A saved document and an existing conversation also appear. Opening the document loads it from the document API and shows the draft, not a filename with only Delete. Opening the conversation loads that conversation. A document or conversation owned by someone else is absent. A household member does not find another member's private document or chat. Relaunch restores the search origin and refetches.

### What exists and is reused

| Piece | Where | PR |
| --- | --- | --- |
| Financial search | `GET /api/v1/financial-search`. `src/argus/domain/financial_search.py` kinds `account`, `activity`, `expectation`, `budget`, `goal`, `debt`. Native `FinancialSearch.swift`, `FinancialSearchModel.swift`, `FinancialSearchView.swift` | #751, then #753, #755, #757 for the later kinds |
| Household financial search | `GET /api/v1/households/{id}/search`. Hit shape in `financial_schemas.SearchHit`, with `plan_ref` for shared plans | #766, #773 |
| Conversation search | `GET /api/v1/search` in `src/argus/api/routers/search.py`. Items are `type: conversation` with `conversation_id` | Existing Omnisearch, not the iPhone financial tab |
| Documents | `src/argus/api/routers/financial_documents.py`. List, get, source download, proposal patch. `require_document_surface` in `src/argus/api/documents.py` requires the ingestion gate and `ARGUS_DOCUMENT_EXTRACTION_ENABLED`, which defaults off. Bytes in `financial_document_extractions.source_bytes` via `src/argus/domain/ingestion/documents/store_postgres.py` | #776 |
| Design Search chrome | `CuadraoSearchCanvas.swift` has sample sections for plans, chats, files, and memory | Design canvas |

Reuse `financial_search.search` for financial rows, the document service's list and get for documents, and `GET /api/v1/search` for conversations. [Issue #778](https://github.com/lagarcess/argus/issues/778) plans to move retained document source bytes into a private Supabase Storage bucket before documents are enabled. Search uses the document API and never storage internals, so that move does not affect Search.

### What is new

- Document and conversation hits in the connected Search results, through the existing owners. Documents stay behind `ARGUS_DOCUMENT_EXTRACTION_ENABLED`.
- Household search keeps omitting documents and chats. No document-sharing grant exists, and this lane does not invent one.

### iOS parts: landed unverified, Mac pass by Lucas's local agent

- Document and conversation rows and their open paths in `FinancialSearchModel.open`. The assistant tab is still `ChatSampleView`, so the conversation open needs a reader destination the navigation writer adds.

### Allowed files

`src/argus/domain/financial_search.py`, `src/argus/api/routers/financial_search.py`, the connected search Swift files named above, `ArgusSession` search types, and the connected financial Search section of the API contract when this lane is landing. Conversation hits call the existing search reader. They do not copy its SQL.

No-touch: `store_postgres.py` except a bugfix the document owner makes, `CuadraoSearchCanvas.swift`, interpreter prompts, `GET /api/v1/search` ranking.

### Acceptance

Backend: Postgres with one saved document and one conversation for user A, and the same kinds for user B. A finds only A's rows. B's queries do not include A's ids. A household member without a document grant does not see the other member's draft. Document flag off: financial search still returns the existing kinds and returns no document hits. No test reads `source_bytes` from the Search package.

iOS, by Lucas's local agent: A opens the document through the document API and the conversation through its id. Back restores the query. Relaunch refetches. English and Spanish filters once the captain adds the strings.

## Lane 4. Home series

**MVEE:** [Home](../argus-minimum-viable-ecosystem-experience.md#home-understand-where-i-stand), populated summary, and [charts](../argus-minimum-viable-ecosystem-experience.md#13-complete-scope-checklist) row D05. Decision 6.

### Journey and completion

A signed-in person opens Home in Personal, then in a private space once the space list has landed. The balance chart and the activity insights use that space's recorded accounts and activity, one currency at a time. A month with no records is no data. It is not a zero balance and not zero spending. A month that has records adding up to zero is a real zero. A comparison against a real zero month shows the amount difference, not a percent. A comparison with a no-data month is not shown. Unknown balances stay out of the known total. The person can open the account or activity behind a point. Relaunch shows the same series. Household Home includes only accounts that live grants allow, plus locked history after slot 5, and drops an account the moment its grant is revoked.

Completion is a real Postgres read, an app relaunch, a second user who cannot see the first user's series, and the same screen in English and Spanish. The design canvas sample series is not completion.

### What exists and is reused

| Piece | Where | PR |
| --- | --- | --- |
| Connected Home position, one reporting month, five recent activities, and the Plan forecast | `GET /api/v1/financial-home` and `GET /api/v1/financial-plan`. Built by `home_response` in `src/argus/domain/recording/loop_reads.py`. Month window is `period` in `src/argus/domain/recording/money_home.py` | #745, #747, #749 |
| Connected Cuadrao Home | `ios/ArgusFoundation/Connected/ConnectedCuadraoHome.swift` renders text, accounts, coming up, and recent activity. It does not construct `CuadraoHomeBalanceChart` or `CuadraoHomeInsights` | #760 |
| Chart and insight chrome, sample data | `CuadraoHomeOverview.swift`, `CuadraoHomeInsights.swift`, `CuadraoHomeBalanceChart.swift`, `CuadraoBalanceHistory.swift`, `CuadraoSpendingHistory.swift`, `CuadraoSpendingStory.swift`. `CanvasBalanceHistory.examples` and `CanvasSpendingHistory.examples` invent history | #775, #777, design canvas |

Reuse `home_response`, `spending`, and the Plan forecast. Do not add a second balance.

Today `home_response` returns zero minor-unit spending strings for a currency that has accounts and no expenses in the month. Under decision 6 that month has no records, so the series shows it as no data. Those strings are the current-month totals, not a series, and must not be copied into the chart. The canvas `CanvasSpendingStory.comparison` compares against a previous period inside coverage and can show a zero difference, which is close to decision 6. The connected path must not show a percent change against a zero month.

### What is new

- A multi-month balance and spending series on the API, derived from canonical account observations and current logical activity, filtered by current `space_id`. Behind a default-off flag. Each month is marked as having records or not.
- The comparison rule of decision 6 in that series.

### iOS parts: landed unverified, Mac pass by Lucas's local agent

- Binding the connected Home to the chart and insight views with the API series, instead of `CanvasBalanceHistory.examples`. This waits until the captain can touch `ConnectedCuadraoHome.swift` without colliding with the design branch, which also edits the chart files.

### Allowed files

`src/argus/domain/recording/loop_reads.py`, `money_home.py`, a new series module next to them, `src/argus/api/routers/financial_loop.py`, the financial-home section of `docs/API_CONTRACT.md` and `docs/api/openapi.yaml` when this lane is landing, and the tests that already cover `home_response`.

No-touch: `ios/ArgusFoundation/Cuadrao/**`, design preview tests, and `ConnectedCuadraoHome.swift` while the design branch still differs on it. Household grant tables. Plan definition tables.

### Acceptance

Backend: Postgres. An account with an unknown balance does not become zero. A month with accounts and no records is no data, not the current zero string. A previous month with records summing to zero gives an amount difference and no percent. A no-data month gives no comparison. Household series hides an account the moment its grant is revoked. `ARGUS_FINANCIAL_ACCOUNTS_ENABLED` unset still returns `404` on the financial routes.

iOS, by Lucas's local agent: relaunch reads the same points. English and Spanish strings for no data and for the amount comparison.

## Lane 5. Updates

**MVEE:** [Updates](../argus-minimum-viable-ecosystem-experience.md#updates-tell-me-when-something-deserves-attention). Decisions 2, 7, and 8. The broader MVEE list, including budget thresholds, goal milestones, and scheduled summaries, stays on the board. This lane does not close it.

### Journey and completion

The person taps the bell and sees a persistent inbox. Rows in this pass:

- **Bill.** A personal or shared bill makes one row 3 days before its due date and one on the due date. Each row is written once per bill, due date, and offset, so a rerun does not duplicate it.
- **Draft ready.** A document whose status becomes `review_ready`.
- **Invitation accepted.** The inviter gets a row when someone accepts their invitation. There is no "invitation received" row, because an invitation has no named recipient before acceptance.

The row says what happened and opens the source through the source link. Opening marks it read. Read state survives relaunch. Another user does not see the row. After a grant is revoked, a household row disappears or opens as unavailable. Amounts, when the source still has them, appear only inside this signed-in inbox.

A person who turns on push also gets a push for each new row. A push never contains an amount, a balance, a merchant, or a document name. It says something needs a look and opens the app. There is no email for updates.

### What exists and is reused

- Connected shell: `ConnectedCuadraoHome` calls `showUpdates`, and `ConnectedCuadraoShell` presents `FoundationSheet.updates`.
- `FoundationSheets.swift` renders a sample page. Copy key `sheet.updates.detail` says delivery is not connected, in `en` and `es-419`.
- Bill facts: personal expectations of kind `bill`, and shared plans of kind `bill`, already have dates.
- Draft facts: document `status` includes `review_ready`, behind `ARGUS_DOCUMENT_EXTRACTION_ENABLED`, default off. PR #776.
- Invitation facts: `household_invitations.accepted_at` and the sender from lane 1.
- `conversation_read_states` is chat read state. It is not this inbox and is not reused.
- No push code exists. See [Outside services](#outside-services-fakes-behind-default-off-flags).

### What is new

- Inbox table with read state, RLS on, client privileges revoked, the service writes. New migration.
- A trigger writer for the three row kinds, idempotent per source and offset.
- Device-token registration for push, a push sender interface, and the recording fake. `ARGUS_UPDATES_PUSH_ENABLED` off uses the fake. The real APNs sender waits for the key.

### iOS parts: landed unverified, Mac pass by Lucas's local agent

- The inbox screen behind the bell, through the navigation writer. `CuadraoUpdatesCanvas.swift` stays on the design branch.
- The push opt-in prompt, device-token registration, and opening the app from a push.

### Allowed files

A new Updates package under `src/argus/domain/` and one router, a new migration assigned by the captain, `FoundationSheets.swift` only through the navigation writer, and tests that create a bill, a document draft, and an accepted invitation and then read the inbox as that user and as someone else.

The document service keeps owning draft status. The Plan service keeps owning due dates. The Household service keeps owning invitations. Updates reads those rows. It does not add a status column to them.

No-touch: `CuadraoUpdatesCanvas.swift`, `source_bytes`, invitation token storage, `resend_email.py`.

### Acceptance

Backend: Postgres. A bill due in 3 days makes one row, and the due date makes a second. Running the trigger again adds nothing. A draft reaching `review_ready` makes one row. An accepted invitation makes one row for the inviter only. Mark one read and read it back as read. A second user gets an empty inbox. Revoke a household grant and the related row is gone or unavailable. A document row's open path uses `connection_id`. With the document flag off, no draft row appears and the document routes still `404`. Every payload the push fake records has no amount. No email is sent.

iOS, by Lucas's local agent: relaunch shows the same unread and read rows. English and Spanish for the inbox and the push text. Push opt-in off sends nothing.

## Lane status

| Lane | Backend can be built and tested here now | iOS: landed unverified, Mac pass by Lucas's local agent | Waits on |
| --- | --- | --- | --- |
| Household | Code, who-invited-whom record, anonymous record on deletion, link builder, quota, gate, the three numbers | Code and QR screens, code entry, universal-link handling, TestFlight link and waitlist hand-off | Open item 1 for quota and gate only. Lucas's AASA file before the link flag turns on |
| Space list | Space table and routes | Space picker and space list | Nothing |
| Search | Document and conversation hits | Rows and open paths | Nothing. Issue #778 does not block it |
| Home series | Series and the decision 6 comparison | Binding the connected Home to the series | The design-branch collision on `ConnectedCuadraoHome.swift` for the iOS binding |
| Account moves | Move command, events, locked history, RLS, eval | Move review and greyed-out locked history | The Home series reader, then manual Codex review and the eval. Linked moves stay blocked |
| Updates | Inbox, three triggers, device tokens, push fake | Inbox screen, push opt-in and handling | Lucas's APNs key before the push flag turns on |

No lane is dispatched by this document.
