# R-docs delta review, PR #808, pinned to a1ebf4b4f24e2778b2e9501aa3ab8d1cb8bd8c1e

Verdict: **CLEAN**. No blocking findings. Two non-blocking notes at the end.

Scope: `git diff 876c2f8a..a1ebf4b4`, one file, four lines changed in
`docs/specs/lanes/mvee-five-lane-handoff.md` (L559, L579, L588, L622).
Read-only: nothing edited, committed, pushed or commented. Every claim below
was checked against code at a1ebf4b4 with `git show`, not against other prose.

## Each changed sentence against the code

### L559, the owner paragraph

| Claim | Code at a1ebf4b4 | Result |
|---|---|---|
| The dialog calls `POST /api/v1/account/delete` through `web/lib/account-deletion-api.ts` | `ProfileMenu.tsx:857` calls `requestAccountDeletion`; `account-deletion-api.ts:16` posts `/account/delete` | True |
| With the flag off the route answers `404` | `src/argus/api/routers/account.py`: `_deleting_user` raises 404 `not_found` before `deletion_requester(request)`; `FLAG = "ARGUS_ACCOUNT_DELETION_ENABLED"` (L31); `render.yaml:66` sets it `"false"` | True |
| The web then files `type: "account_deletion_request"` through `POST /api/v1/feedback` | `account-deletion-api.ts:80-89`: any non-404 rethrows or maps to `in_progress`; on 404 it calls `postFeedback({type: "account_deletion_request", ...})` and returns `"requested"` | True |
| That type is still accepted | `schemas.py:956` `Literal["bug","feature","general","account_deletion_request"]`; `routers/feedback.py:28` enriches the context; `tests/test_alpha_api_supabase.py:1073` and `tests/test_account_deletion_api.py:171` | True, in both flag states |
| The dialog says a support request was sent, not that the account was deleted | `ProfileDeleteRequestDialog.tsx:121-140`: state `requested` renders `settings.profile.request_deletion.requested`, "Request sent. Support will delete your account and follow up by email." (en and es-419 `common.json:1052`); `deletionEndsSession("requested")` is false, so no sign-out | True |
| Retired only once the flag is on everywhere and a later change removes the fallback | Forward-looking rule (Lucas, October 4). Nothing in the tree contradicts it: the type, the fallback branch and the copy are all present | Consistent |

### L579 (scope bullet)
"Moving web onto the deletion command, with `account_deletion_request` kept as
its flag-off fallback", then a link to the owner paragraph. Matches the code
and defers the retirement rule instead of restating it.

### L588 (allowed files)
The clause "retiring `account_deletion_request` together with" is removed; the
file list is otherwise unchanged. It no longer states any retirement rule, so
nothing here can disagree with L559.

### L622 (acceptance)
- Flag on: "web deletion uses the deletion command". True (`deleteAccount()`
  returns `done` or `in_progress`; the fallback branch is reached only on 404).
  It makes no claim that the type is rejected, which would be false.
- Flag off: web files the request, the API accepts it, the dialog says a
  support request was sent. True, and already tested:
  `web/__tests__/account-deletion-api.test.ts:74-80` (404 gives `requested`),
  `:192` (copy), `tests/test_alpha_api_supabase.py:1073` (API accepts and
  enriches).
- Retirement is deferred to the owner paragraph by link. Testable and true in
  both flag states.

## Single owner of the rule
The retirement condition ("flag on everywhere and a later change removes the
fallback") appears only at L559. L579 and L622 link to it. L175 (unchanged)
says the ticket is filed "only while the flag is off" and links to the same
paragraph. No conflicting restatement.

## No remaining "retired" statement in docs/
Grepped `account_deletion_request`, "support request", "support ticket",
"retir", "no longer accepted" across `docs/` at a1ebf4b4. No sentence says the
support request is retired or no longer accepted. Consistent with the fallback:
`docs/API_CONTRACT.md:6952`, `docs/DATA_MODEL.md:2453`,
`docs/api/openapi.yaml:12362`, `docs/specs/argus-execution-board.md:79`,
`docs/specs/argus-minimum-viable-ecosystem-experience.md:731`. Handoff L505 says
"There is no in-app deletion function", but it sits under "What exists today",
which L501 labels as the state before Lane 6 landed; not a contradiction.

## Founder-locked copy block
`### Copy (founder-locked, Iris's wording)` (L630 to the next `###`) has the
same sha256 at both commits:
`6775bb82a04cfad6c290743da6389bdda09c8659245e22620462d612c0ba5ed4`. Byte-identical.

## Anchors and whitespace
- `#steps-in-order` resolves to `### Steps, in order` (L512), the only heading
  with that slug.
- `git diff --check 876c2f8a..a1ebf4b4`: clean, exit 0.

## Non-blocking notes (no change required)

1. Low, `docs/specs/lanes/mvee-five-lane-handoff.md:579` and `:622`. "The
   paragraph after the steps" is the third paragraph after the list (L555
   idempotency, L557 ship gates, L559 web). The anchor lands on the heading, so
   a reader has to scan. L175 already uses the same phrasing, so this is
   consistent with the file. Smallest fix if wanted: "the web paragraph after
   the steps".
2. Low, `:622`. "The API accepts it" is true of the type. A submission can
   still be refused for quota (guest allowance gives 403
   `account_conversion_required`, `routers/feedback.py:55-62`; registered 50 a
   day, 20 an hour) or fail on the network; the web then returns `unavailable`
   and the dialog shows "Deleting in the app isn't available here yet. Support
   can delete your account for you." with an email link
   (`ProfileDeleteRequestDialog.tsx:187`). That copy also does not say the
   account was deleted, so the line's point holds. The doc does not describe
   this branch; it is tested at `web/__tests__/account-deletion-api.test.ts:93-96`.
