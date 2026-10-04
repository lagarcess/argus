# W7 report: Household and beta invitations against a real local backend

## Refs

- Backend under test: `src/` of `claude/cuadrao-household-invites-ios` at `6fb15a017b77e0337322c4133f1412cce40da059`. `git diff a8c37d3a 6fb15a01 -- src supabase/migrations pyproject.toml poetry.lock` is empty, so this is the integration backend at `a8c37d3a`. The fix worker's commits since (`254da9dc6`, `4fd1d3432`, `b9e5c7d69`) touch only `ios/` (`git diff --stat 6fb15a01 b9e5c7d69 -- src` is empty).
- Part 1 run3 read Python from `.claude/worktrees/cuadrao-household` (src identical to 6fb15a01, checked above). Part 2 and everything after run3 read Python from W7's own detached copy `.claude/worktrees/cuadrao-w7` at `6fb15a01` (created on the lead's order; no commits in it).
- Client compared: `ios/Packages/ArgusSession/Sources/ArgusSession/Invitations.swift` and `Household.swift` at `6fb15a01`, plus the same payloads decoded against the fix head `b9e5c7d69`.
- Local Supabase `argus-qa` (CLI 2.109.0 images, 111 migrations, max 20261004090000), owned by W7 for this run.
- API: `cuadrao-py310-runner` container, uvicorn on `127.0.0.1:18790`, process environment only (no `.env`), flags on: `ARGUS_HOUSEHOLDS_ENABLED`, `ARGUS_FINANCIAL_ACCOUNTS_ENABLED`, `ARGUS_BETA_INVITES_ENABLED`, `ARGUS_BETA_INVITE_GATE_ENABLED`; `ARGUS_INVITE_UNIVERSAL_LINK_ENABLED` unset (off); throwaway `ARGUS_INVITE_CODE_SECRET` from `openssl rand -base64 48` (never printed; file `baseline/w7-live/.invite-secret`, mode 600); `ARGUS_INVITE_FOUNDER_USER_ID` = local user A; `ARGUS_WAITLIST_URL=https://waitlist.example.test/join`; `ARGUS_TESTFLIGHT_PUBLIC_URL=https://testflight.example.test/join/W7`; every provider key empty. No paid provider was called.
- Users: real local GoTrue sign-ups (`POST /auth/v1/signup`), `w7-<role>-<time>@example.test`. Tokens, codes and links are redacted in every saved file.

## Tools (rerunnable)

All under `~/.claude/orchestrate/cuadrao-iphone-candidate/probes/`:

- `w7-api.sh start <founder id> | stop`: starts the API container as above. `W7_WT` picks the worktree (default `cuadrao-w7`).
- `w7_live_invites.py signup` then `W7_RUN=<dir> w7_live_invites.py run`: the whole Part 1 journey list, 122 requests, one verdict per check. Writes `baseline/w7-live/<dir>/exchanges.jsonl` (every request and response, redacted), `checks.json`, and `decode/NNN-<SwiftType>.json` / `decode/NNN-problem-<status>.json`.
- `w7-decode/run.sh <worktree> <decode dir>`: copies the client's own Decodable types verbatim out of the given worktree (everything in `Invitations.swift` except the transport and client, and `Household.swift` up to `HouseholdFinancialCommand`), compiles them with `swiftc`, decodes every live body with the same decoders the app uses (`InvitationDates.decoder()` for invites, plain `JSONDecoder()` for Household), and maps every live problem body through a copy of `SessionController.problem(_:status:)` + `bounded` and the real `InvitationProblem.init`.
- `w7_tcp_proxy.py`: a TCP forwarder used once to cut only the API's database connection (for a real 5xx).

Commands actually run, with results:

```
w7_live_invites.py signup; w7-api.sh start <A>; W7_RUN=run3 w7_live_invites.py run   -> 112 pass, 1 fail, 122 requests (baseline/w7-live/run3.log)
w7-decode/run.sh cuadrao-w7 (6fb15a01) run3/decode        -> exit 0, "decode failures: 0 of 101 files" (run3/swift-decode-6fb15a01.log)
w7-decode/run.sh cuadrao-household (b9e5c7d69) run3/decode -> exit 0, 0 of 101 (run3/swift-decode-b9e5c7d69.log)
```

run1 aborted on a local DB check constraint in the probe (`expires_at > created_at`; fixed by moving `created_at` back too). run2 completed but its saved problem bodies had the problem `code` redacted by a probe bug; both are kept, unused. run3 is the evidence.

## Journeys

Part 1 is HTTP against the real API and real local GoTrue users. Part 2 is the Debug app on iPhone 17e `8B7975F1-1338-4966-90E2-770416CAF174` against the same live backend. Check numbers refer to `baseline/w7-live/run3/checks-table.md` (all 113 checks with evidence); request numbers refer to `run3/exchanges.jsonl` `seq`.

| Journey | Part 1 (HTTP) | Part 2 (simulator) | Evidence |
| --- | --- | --- | --- |
| Beta access before admission: `{gate_enabled:true, admitted:false, waitlist_url, testflight_url}` | PASS | PASS (gate shown from live `/invites/access`) | checks 1 to 2; `sim/02-gate-from-live-access.png` |
| Founder is admitted without a code | PASS | not driven | checks 3 to 4 |
| Gated person cannot send a beta invite (`403 beta_invite_required`) | PASS | not driven | check 5; decodes to `.invitationRequired` |
| Personal invite create: code and token once, `link: null` (universal flag off), quota 9 of 10 | PASS | PASS (10 of 10 became 9 of 10, code shown once) | checks 11 to 12, seq 9; `sim/07`, `sim/08` |
| Replay with same `Idempotency-Key`: same id, `replayed:true`, no secrets, still 201 | PASS | n/a | checks 13 to 14, seq 10; client `hasSecrets` false |
| Sent list: `pending`, then `accepted` with `accepted_at` after a second user redeems | PASS | partly (hub shows empty list for a new sender; accepted state not viewed in the app) | checks 15 to 16, 25 to 27 |
| Gate code valid: preview `beta available`, redeem lowercased without dashes, access flips to admitted | PASS | PASS (typed code, `POST /invites/redeem 200`, app opened) | checks 17 to 24; `sim/03`, `sim/04` |
| Same person redeems again: `200 replayed:true`, not a second use | PASS | n/a | checks 21 to 22 |
| Gate code used: `409 invitation_consumed` + `context.waitlist_url`; preview `200 available:false` | PASS | not driven | checks 28 to 30, seq 17 |
| Gate code invalid: unknown well-formed and malformed 4-char both `404 invitation_not_found`; too short or both secrets `422 validation_error` | PASS | not driven | checks 31 to 34 |
| Gate code expired: preview `200 available:false`, redeem `409 invitation_expired`, sent row `expired` | PASS | not driven | checks 35 to 38 (expiry set in the local DB) |
| Gate code revoked: `POST /invites/{created id}/revoke` 204, preview `200 available:false`, redeem `409 invitation_revoked`, row `revoked`; revoking an accepted invite `409 invitation_consumed` | PASS | not driven | checks 39 to 44 |
| Rate limit: ten `404` then `429 invite_rate_limited` with `Retry-After: 3582`; a real code is also refused while limited | PASS | not driven | checks 110 to 111, seq 119 to 120 |
| Quota out of ten for an ordinary user: 9..0, eleventh `409 beta_invite_quota_exhausted`, sent quota `{10,10,0}` | PASS | n/a | checks 45 to 47 |
| Founder group link: create with label, cap 1, expiry; preview by token; redeem to cap; next redeem `409 group_link_full` + waitlist context; list `state:full redeemed:1 overflow:1`; overflow person stays gated | PASS | not driven (founder screens not walked) | checks 52 to 62, seq 52 |
| Group link non-founder list or create `403 founder_required`; blank label 422; past expiry `422 invite_request_invalid` | PASS | PASS (non-founder hub calls `GET /invites/group-links` 403 and shows no founder section) | checks 48 to 51; `sim/06`, `sim-api-access.log` |
| Group link expired (real 15 s expiry) and revoked: preview `200 available:false`, redeem `409 invitation_expired` / `409 invitation_revoked`, list states `expired` / `revoked` with `revoked_at` | PASS | not driven | checks 65 to 70 |
| Group link grants beta admission only, no household membership (`GET /households` empty, 0 `household_members` rows) | PASS | n/a | checks 63 to 64 |
| Household invitation create (admin): `invitation.code`, `token`, `link` = `argus-household://invite#<token>` | PASS | not driven (created by API for the app pass) | checks 71 to 74 |
| Gated person's household code at the beta gate: `409 household_invitation_requires_accept`; `/invites/preview` says `kind:household` with name | PASS | PASS (gate handed the code to the Household join sheet, which showed "Casa Simulador") | checks 75 to 78; `sim/16`, `sim/17` |
| Household preview and accept by code; joining admits to the beta; household invite does not charge beta quota; sent list shows it `accepted` | PASS | PASS twice: admitted user joined by code (`sim/11` to `sim/15`); gated user joined by code, gate re-read access and opened the app (`sim/18`, `sim/19`) | checks 79 to 86; `sim-verify-2.jsonl` |
| Accept by link token (fragment of the legacy link) | PASS | not driven (universal links need AASA) | checks 88 to 90 |
| Non-admin member cannot invite: `403 household_admin_required` | PASS | not driven | check 87 |
| Household used, expired, revoked: both previews `200 available:false`, accept `409 invitation_consumed` / `invitation_expired` / `invitation_revoked`; refused person stays gated | PASS | not driven | checks 91 to 101 |
| Membership grants no account access until an explicit grant; grant shows exactly that account; an ungranted member still sees none | PASS | PASS (gated user joined, household shows no shared accounts; API `accounts: []`) | checks 102 to 109; `sim/19`, `sim-verify-2.jsonl` |
| Server failure shape | see finding B2 | not driven | `run3-outage.log` |

Totals for run3: 112 PASS, 1 FAIL (the DB-paused 5xx expectation; finding B2). Every 2xx body (65 files) decodes with the client's own types at 6fb15a01 and at b9e5c7d69: `decode failures: 0 of 101 files`.

## Answers the lead asked for (from real responses)

1. Preview of expired, used, revoked and full secrets is `200` with `available:false`, never a 409. Seen for beta codes (used, expired, revoked), group links (full, expired, revoked), and household codes on both `POST /invites/preview` (`kind:"household"`, `household_name`) and `POST /household-invitations/preview` (`name`, `available:false`). Only `redeem` and `accept` return the 409 codes. The iOS stubs throw 409 on preview instead: `InvitationsHarness.outcome(_:)` for `/preview`, and `HouseholdModelTests.testPreviewOutcomesExplainTheInvitationWithoutEndingMembership` (409 `invitation_expired` / `invitation_consumed` / `invitation_revoked` on preview). See mismatch M1.
2. A 5xx through the real transport (API database cut, GoTrue up): `503` with `{"type":".../auth-session-verification-unavailable","title":"Session Verification Unavailable","status":503,"detail":"Argus could not verify this session. Please try again.","code":"auth_session_verification_unavailable","request_id":"..."}`. It comes from `current_user`, so every authenticated route answers it, invites included. The client maps any status >= 500 to `.unavailable` before reading the code. With the whole database paused, the API answers `401 unauthorized` instead (finding B2).
3. A created beta invite returns `link: null` by default (universal link flag off). Group links also return `link: null`. Household invitations return `link: "argus-household://invite#<token>"`. The client shows the code only for beta (W2's design), confirmed live in `sim/08`.
4. The beta gate is enforced on no route except beta invite creation. With `ARGUS_BETA_INVITE_GATE_ENABLED=true`, non-admitted user B got `GET /households` 200, `GET /financial-accounts` 200, `GET /me` 200, `GET /conversations` 200, `POST /financial-accounts` 201 (checks 6 to 10). The only refusal is `POST /invites` `403 beta_invite_required`. The gate is a client-side screen over a server-owned fact.

## Contract mismatches (client or stub versus real server)

M1 (medium, user-visible). Preview outcomes. Real preview of an expired, used, revoked or full secret is `200 available:false`; the stubs answer 409. Effects at 6fb15a01:
- Household join step (`HouseholdManagement.swift:177`) shows the generic `household.inviteUnavailable` text. The specific "expired", "used", "revoked" explanations that W2's table lists for the join step are reachable only after the person also taps accept and gets the 409. The test that claims them on preview passes only against the stub.
- Beta link for an admitted person (`InvitationsModel.continuePendingLink`, `.admitted` case): a used, expired or revoked beta link previews `200 available:false kind:beta` and the app says "You already have access". Harmless for an admitted person, but it never says the link was bad.
- For a gated person the gate redeems directly, so the 409s reach the gate correctly (verified live for redeem).
Smallest fix: drive the stubs with the real shape (`200 available:false`) and decide in the join step whether `available:false` should name a reason (the server's preview gives no reason field, so naming one needs either a server `reason` field or an accept attempt).

M2 (low). `invite_request_invalid` (422, group link expiry out of range) and `household_admin_required` (403) map to `.unavailable` at 6fb15a01 and to `.refused` at b9e5c7d69. The founder form's picker starts a week ahead, so this needs a date over a year out. Payload: `{"status":422,"code":"invite_request_invalid","detail":"The expiry date must be in the future and within a year."}`.

M3 (info, matches). Everything else matches the client decoders: all 65 success bodies decode (dates arrive as `2026-10-11T02:39:17.250992Z`, six fractional digits, accepted by `InvitationDates`); every problem body is top-level (`code` at the root, not under `detail`), so `SessionController.problem` reads it; `validation_error` is the real 422 code; `context.waitlist_url` arrives on `invitation_consumed`, `invitation_expired`, `invitation_revoked`, `invitation_not_found` and `group_link_full` redeem failures (the client does not read `context`; it uses `waitlist_url` from `/invites/access`). `Retry-After` on 429 is about one hour (3582 s), from the hourly per-account failure budget; the client does not show it.

## Backend and cross-fact defects

B1 (medium, three-facts separation). A member whose account grant is absent or revoked gets `404 household_not_found` ("No such household.") from `GET /households/{id}/accounts/{account_id}`, while `GET /households/{id}` still answers 200 for the same member. Repro (run3, `run3-grant-revoke.log`): D granted view, `GET .../accounts/{acct}` 200; A `PUT .../accounts/{acct}/grants {"recipients":[]}` 200; D `GET .../accounts/{acct}` 404 `household_not_found`; D `GET /households/{id}` 200. The same 404 code is returned for an account id that does not exist. The client treats that code as loss of membership: `HouseholdModel.open(_:)` (`HouseholdModel.swift:96-103`) routes the error to `handleAccessFailure`, whose `household_not_found` case calls `accessEnded()` (clears the selected household, shows `household.accessEnded`). The plan path re-checks the household first (`handlePlanAccessFailure`), the account path does not. So losing account access, or opening a stale account row, would read as being removed from the household. The client effect is from code reading at 6fb15a01, not driven in the simulator. Smallest fix: either an account-scoped code from the server (for example `account_grant_not_found`, which already exists in `errors.py`) or the plan path's re-check in `open(_:)`.

B2 (low to medium, all authenticated routes). When the auth provider times out, the API answers `401 unauthorized "Invalid or expired access token."`. Repro: `docker pause supabase_db_argus-qa`; GoTrue `GET /auth/v1/user` and refresh both return `504 request_timeout`; the API's `GET /invites/access` returns 401. Cause: `current_user` in `src/argus/api/dependencies.py` wraps every exception from `get_auth_user_from_token` as 401. The iOS client then refreshes; refresh gets 504 (`AuthError.api` with 504 is not in `[400, 401, 403]`), so the session survives this run of events, but a refresh that succeeds while the API still sees GoTrue failing would end in `suspendUsableSession()`. Not invites-specific; filed here as a follow-up, not fixed.

B3 (info). Quota counts only live invites: a revoked invite, and an expired unused one, give the slot back (`_quota` in `invites.py`, `revoked_at is null and (use_count>0 or expires_at>now)`). Founder quota after three creates with one revoked and one expired read `used:1`. Intended or not, the Sent list shows those rows while the counter does not count them.

B4 (info). The rate limiter is per process and per IP plus per account. All local traffic shares one IP, so a full journey run spends the 30 lookups a minute and 20 failures an hour per-IP budgets; the probe paces itself and restarts the API between runs.

## Simulator pass (Part 2): what was run

- Built Debug from W7's detached worktree `cuadrao-w7` at `6fb15a01`, derived data `baseline/w7-derived`, configuration only through an out-of-tree `-xcconfig baseline/w7-live/sim.xcconfig` (bundle id `local.argus.w7invites` so the founder's installed `local.argus.foundation` was not touched; `ARGUS_AUTH_ENABLED=true`; API `http://127.0.0.1:18790`; Supabase `http://127.0.0.1:54331` and its public local anon key; web and captcha `http://127.0.0.1:18795`, serving the repo's `ios/scripts/auth/captcha.html` in `pass` mode, which uses Cloudflare's published always-pass test key; local GoTrue has captcha off). `** BUILD SUCCEEDED **` (`sim-build.log`, anon key redacted). Nothing in any worktree was changed or committed.
- Install, launch and all driving ran inside one `lockf -k mac-sim.lock` holder: acquired 21:55:51, released 22:04:27 (`sim-lock.log`); it waited about 6 minutes behind another worker's `xcodebuild test-without-building`. The test app was uninstalled before release.
- Journeys driven (es-419): sign in as non-admitted `w7sima` and see the gate; type a valid code and get in; Profile, Invitaciones, Invitar a la beta, create, quota 10 of 10 to 9 of 10 with the code shown once; Hogar, join by code, preview "Casa Simulador", accept, member list Ana (admin) and Simona; sign out; sign in as non-admitted `w7simb`, type a Household code at the gate, the gate hands it to the Household join sheet, accept, access re-read, app opens on the Household with no shared accounts. Server state confirmed after each (`sim-verify-1.jsonl`, `sim-verify-2.jsonl`), and the app's own requests are in `sim-api-access.log` (paths and statuses only).
- Observations from the pass, not fixed: (a) the hand-off from the gate filled the code but did not preview it automatically; no preview request was sent until "Revisar invitación" was tapped (`sim/16`, at 6fb15a01; b9e5c7d69 changed this flow). (b) With the keyboard up on the gate, the "Cerrar sesión" label draws over the Continuar button (`sim/03`). (c) "Crear invitación" reads dark on the pine button, the same contrast W2 noted for the gate (`sim/07`). (d) Profile still says the financial screens show local examples, not your finances (`sim/05`), while the connected app is showing real local data. (e) The simulator types through a US key map, so `@` and `-` came out wrong on the es-419 keyboard; test emails without a hyphen and codes without dashes were used (the server folds dashes).

## Not provable here

- Universal links (`https://cuadrao.ai/invite#...`): need the AASA file, the Associated Domains entitlement on a signed App ID and `ARGUS_INVITE_UNIVERSAL_LINK_ENABLED` on server and app. Locally the flag is off and beta and group links come back `link: null`. The `argus-household://` scheme was proven only at the API level (accept by the link's token), not by opening the URL on a device.
- TestFlight install and the TestFlight-then-invite path; a physical iPhone; hosted GoTrue confirmation settings, hosted Turnstile, hosted rate limiting behind Render's proxy (the API logged "Trusted client-IP header missing; using socket peer" locally, so per-IP limits on hosted depend on the proxy header configuration).
- Founder group-link screens, the accepted notice in the Sent list, and every refusal state were proven over HTTP only, not walked in the app.

## Housekeeping

- API containers `w7-api` and `w7-api-deaddb`, the DB proxy `w7-dbproxy` and the captcha server are stopped.
- Local Supabase `argus-qa` left running and reset (`supabase db reset` from `cuadrao-w7`: 111 migrations, max 20261004090000, 0 auth users). Line 1 of `reports/W4.md` is back to `SUPABASE: free (last owner W7)`.
- Throwaway secrets (invite code secret, test user passwords, sim codes) deleted after the reset made them meaningless. Screenshots show local-only test codes from the now-reset database.
- `.claude/worktrees/cuadrao-w7` (detached at 6fb15a01, clean) is left in place for reruns; remove with `git worktree remove` when no longer needed.

## Follow-ups (not in scope, not done)

1. M1: align stubs with `200 available:false` and decide what the join step should say (may need a server reason field).
2. B1: account-scoped code or a household re-check before `accessEnded()` on an account 404.
3. B2: map auth-provider timeouts to 503 in `current_user` instead of 401.
4. B3: confirm that revoked and expired invites should return to the quota.
5. The gate hand-off auto-preview and the three layout notes in Part 2.
