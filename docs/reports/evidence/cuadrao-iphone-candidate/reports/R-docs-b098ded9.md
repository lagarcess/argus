# R-docs review: `a8c37d3a...b098ded9` (claude/cuadrao-docs-issues-batch)

Read-only review at head `b098ded9cf6a29f3027361c9da1887d5ded8f855`, base `a8c37d3a182fbdb3228f6003272418e65286bc1a`. Docs only, 8 files, +151 / -29. Paths below are relative to the repo root.

**Verdict: no P1. Five P2, four P3.** No changed claim would send a builder or operator the wrong way on its own. The P2s are two stale copies left beside edited text, two wrong statements in the new hidden-rows file, and one wrong table attribution in DATA_MODEL.

## Findings

### P2-1. Stale "Apple revoke uses the recording fake" copies contradict the edited step 2
- **Where:** `docs/specs/lanes/mvee-five-lane-handoff.md:85` ("Off hides the button and the deletion step uses the fake"), `:188` ("Lane 6's Apple revocation uses the recording fake"), `:571` ("the Apple token revoke with its recording fake").
- **What is wrong:** the diff rewrote `:520` to say capture stays off, no token is stored, and an unconfigured process keeps the revoke pending (`apple_unconfigured`). The three older lines still say the deletion step goes to a fake. The edited line is the correct one.
- **Evidence:** `src/argus/domain/account_deletion/service.py:717-721` (no Apple service means `pending`, `apple_unconfigured`); `src/argus/api/apple_sign_in.py:85-88` (the service is not built while the flag is off); `src/argus/api/routers/account.py:85` passes that service to deletion. No Apple recording fake exists under `src/argus/domain/apple_sign_in/` or `src/argus/domain/account_deletion/`.
- **Smallest fix:** replace the fake wording on `:85` and `:188` with the `:520` wording (or a link to step 2), and drop "with its recording fake" on `:571`.

### P2-2. "Still open" item 2 still says web deletion is a support request
- **Where:** `docs/specs/lanes/mvee-five-lane-handoff.md:175`.
- **What is wrong:** it says the web dialog "still sends `account_deletion_request`", "Web will use the same Lane 6 deletion command", and "Only that retirement waits". The diff rewrote `:559` to say web is on the command since #801 and dropped the pointer to this item, but left the item itself.
- **Evidence:** `web/lib/account-deletion-api.ts:79-85` (calls the command, falls back to the ticket only on 404); `web/components/sidebar/ProfileMenu.tsx:856`.
- **Smallest fix:** rewrite `:175` to match `:559`, or close the item with a link to it.

### P2-3. Hidden-rows file: "Argus reads `auth.sessions` in one place" is wrong
- **Where:** `docs/specs/lanes/cuadrao-profile-hidden-rows-backend.md:38`.
- **What is wrong:** it names `src/argus/api/account_deletion_auth.py` as the only reader. The ordinary session check for every authenticated request also reads `auth.sessions`.
- **Evidence:** `src/argus/api/auth_sessions.py:45` and `:84` (the `from auth.sessions` queries), used by `src/argus/api/dependencies.py:17` and `:482`.
- **Smallest fix:** "Argus reads `auth.sessions` only to check that the caller's own session is live (`src/argus/api/auth_sessions.py`); it never lists sessions."

### P2-4. Hidden-rows file: "every endpoint" needs the role and returns 404 is not true for `GET /memory/availability`
- **Where:** `docs/specs/lanes/cuadrao-profile-hidden-rows-backend.md:44`.
- **What is wrong:** the same sentence lists `GET /memory/availability` and then says every endpoint returns `404 personalization_memory_unavailable` to ordinary accounts. Availability answers `200` with `available: false` for a registered account without the role. That is the probe a native client would use to hide the row.
- **Evidence:** `src/argus/api/routers/personalization_memory.py:108-127` (depends on `current_user` only, returns `available=personalization_memory_exposed(user)`); the 404 gate is `src/argus/api/personalization_memory.py:221-239`.
- **Smallest fix:** "every endpoint except `GET /memory/availability`, which answers `available: false`".

### P2-5. DATA_MODEL puts the placeholder map in the wrong table and restates the census's retention rule
- **Where:** `docs/DATA_MODEL.md:2477-2481`.
- **What is wrong:** it says `argus_private.account_deletion_runs` holds the placeholder map. The map is its own table, `argus_private.account_deletion_placeholders`. The paragraph also repeats the census's "run record" retention rule (two unsalted hashes, what survives completion) in detail, so two files now carry it. The run row also keeps its timestamps, which "keeps only its random id, status, step outcomes and counts" omits (same wording as the census).
- **Evidence:** `supabase/migrations/20261004090000_account_deletion.sql:234-252` (runs columns, no map; `created_at`, `updated_at`, `completed_at`), `:261-271` (placeholder map table). Census owner text: `docs/specs/lanes/account-deletion-fk-census.md:190`.
- **Smallest fix:** name the three tables (`account_deletion_runs`, `account_deletion_placeholders`, `account_deletion_revocations`), say they hold identifying data only while a run is in flight, and link the census for what is kept.

### P3-1. DATA_MODEL: new paragraph renders as a heading
- **Where:** `docs/DATA_MODEL.md:2489-2490`.
- **What is wrong:** the paragraph's last line is followed directly by `---`, which Markdown reads as a setext H2 underline, so the whole 13-line paragraph renders as a heading. The base had the same pattern on the one-line Archive sentence; the diff moved it onto the new paragraph.
- **Smallest fix:** add a blank line before `---`.

### P3-2. DATA_MODEL: "held exactly as long as nobody runs the sweep"
- **Where:** `docs/DATA_MODEL.md:2486`.
- **What is wrong:** the sentence before it says the person's retry also finishes the run, and a sweep can leave a step pending (`docs/PRIVATE_LAUNCH_RUNBOOK.md:823-826`).
- **Smallest fix:** "so a pending deletion waits until the person retries or an operator runs the sweep".

### P3-3. MVEE: "until every outside service confirms its revocation"
- **Where:** `docs/specs/argus-minimum-viable-ecosystem-experience.md:733`.
- **What is wrong:** PostHog person deletion is one of the awaited steps and is not a revocation; the lock also holds while the data step itself is being retried (`docs/API_CONTRACT.md:3227-3233`).
- **Smallest fix:** "until every outside service has confirmed".

### P3-4. Hidden-rows file: stated ordering rule does not match the order
- **Where:** `docs/specs/lanes/cuadrao-profile-hidden-rows-backend.md:21`.
- **What is wrong:** "The order puts the smallest backend gap first", but Personalization (no storage, model-facing change) is 5 and Shared conversations (API exists, flag decision only) is 6.
- **Smallest fix:** swap rows 5 and 6, or say what else the order weighs.

## Verified clean

1. **Sign-in.** `ARGUS_APPLE_SIGN_IN_ENABLED` and `ARGUS_GOOGLE_SIGN_IN_ENABLED` are `false` in `ios/Config/Development.xcconfig:32-33` and read in `ios/ArgusFoundation/Auth/NativeProviderSignIn.swift:35,42`. `ARGUS_APPLE_REVOCATION_CAPTURE_ENABLED` is `"false"` in `render.yaml:94-95` and gates capture in `src/argus/api/apple_sign_in.py:38`; the revoke service is built only when it is on, so "capture and revocation sit behind it" holds. Table `apple_sign_in_credentials` exists (`20261003150000`). `[auth.external.apple]` is disabled (`supabase/config.toml:337-338`). `auth.confirmation.detail` still ends on the emailed link. #793, #795, #802 are on the base; #800 and #784 are open with matching titles.
2. **Standalone shared group.** The definition matches `deletion_placeholder_units` (`...account_deletion.sql:859-915`): both "more than one owner" branches, the exclusion by `financial_plan_links` with a binding, `household_plan_archived_claims` and `household_plan_archived_activities` (`deletion_activity_household`, `:827-850`), scope id is the group's own id, `scope_kind` is `household` or `group` (`:264`). The oldest-claim rule and the re-pointed `activity_owner_id` references match `deletion_place_unit` (`:1147-1158`) and `counts.cross_scope_references` (`service.py:668-699`). `test_an_activity_two_households_pin_goes_with_the_oldest_claim` (`tests/test_account_deletion_guards_postgres.py:266`) asserts the same, including read-only for the losing household. The reworded placeholder sentence keeps the same meaning.
3. **Lane 6 text in MVEE, DATA_MODEL and the board.** Agrees with `docs/API_CONTRACT.md:3185-3255` and `docs/PRIVATE_LAUNCH_RUNBOOK.md:786-880`: default-off flag, 404 while off, web falls back to the support ticket, lock until third parties confirm, finish on retry or operator sweep. All three say the sweep is operator-run with no cron by the founder's October 3 decision. MVEE and the board link the owners; DATA_MODEL is the one that restates (P2-5). No native deletion flow exists in `ios/` (the Profile button only shows a notice). #805 and #806 are open.
4. **Hidden-rows file.** The seven routes match `CuadraoFirstRelease.hiddenProfileRoutes` (`ios/ArgusFoundation/Cuadrao/CuadraoProfileCanvas.swift:73-75`) exactly. Quoted screen copy matches `CuadraoProfilePage.swift`. Every cited route and table exists: `GET /me/usage`, `PATCH /me` (fields match `ProfilePatch`, `schemas.py:241-248`), `POST /feedback`, `POST /auth/logout`, all listed `/memory/*` routes, `GET /public-excerpts`, `DELETE /public-excerpts/{snapshot_id}`, the three `/conversations/{id}/public-excerpt*` routes; tables `usage_counters`, `feedback`, `memory_settings`, `memory_consent_actions`, `memory_records`, `public_excerpt_snapshots`. Sharing flag is `"false"` here and `"true"` on local `origin/main` (`a9286b21`). Memory flag is `"true"` in `render.yaml:128-129`. The API contract quote is at `docs/API_CONTRACT.md:7156`. Nothing unshipped is presented as shipped. All link anchors resolve.
5. **#791.** `1de71a6d` is an ancestor of the base. No "not yet on integration" or "on that PR's branch" text remains under `docs/`. The census test runs in CI through the `tests/test_*_postgres.py` glob in `guest-release-gates`.
6. **Locks.** The founder-locked copy block in the handoff (34 lines) is byte-identical to base. In the decision log, only the "Implementation note, not a new decision" bullet changed: "No placeholder spans more than one household or group" became "owns rows in one household or group only", with decision (c) references allowed. That matches the code and Lucas's October 3 decision (c) in the handoff; no October 2 lock text changed. Row 18's decision column is unchanged; only its "today" column was updated.

Not checked: whether the iOS code compiles (the docs say it has not been compiled on a Mac), and `origin/main` freshness beyond the local ref.
