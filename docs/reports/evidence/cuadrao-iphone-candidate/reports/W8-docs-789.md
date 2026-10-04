# W8 report: deletion fallback docs on #808, and #789 closed

## Unit 1. PR #808 docs

- Branch `claude/cuadrao-docs-issues-batch`. Old head `876c2f8a6f7bedce6d8a61807ad65bc131315114`, new head `a1ebf4b4f24e2778b2e9501aa3ab8d1cb8bd8c1e` (one commit, pushed fast-forward `876c2f8a6..a1ebf4b4f`, no force).
- One file, `docs/specs/lanes/mvee-five-lane-handoff.md`, +4/-4.

Code checked first, at the docs head (src identical to integration `a8c37d3a`):
- `web/lib/account-deletion-api.ts:66-93`: calls `POST /account/delete`; on `404` files `type: "account_deletion_request"` through `postFeedback` and returns `"requested"`.
- `src/argus/api/routers/account.py:4-5,92-95`: off unless `ARGUS_ACCOUNT_DELETION_ENABLED`, answers 404 before auth.
- `src/argus/api/schemas.py:954-956` and `src/argus/api/routers/feedback.py:28-31`: the type is still accepted as the flag-off fallback.
- `web/components/sidebar/ProfileDeleteRequestDialog.tsx`: the `requested` state says "Request sent. Support will delete your account and follow up by email." (not "deleted").

Lines changed (all in the Lane 6 section):
- L559 (paragraph after "Steps, in order", the owner sentence): replaced "The acceptance item below that says it is no longer accepted holds only once the flag is on." with the dialog wording fact and the decision: `account_deletion_request` stays accepted while the flag is off, retired only once the flag is on everywhere and a later change removes the fallback (Lucas, October 4).
- L579 "What is new": now "Moving web onto the deletion command, with `account_deletion_request` kept as its flag-off fallback", linking to the paragraph after the steps for when it retires.
- L588 "Allowed files": dropped "retiring `account_deletion_request` together with" (same retired reading, not named in the brief, found by the grep).
- L622 Acceptance: flag on, web uses the command; flag off, web files the support request, the API accepts it, and the dialog says a support request was sent, not that the account was deleted; retiring the fallback is a later change, linked.

Other copies found by `grep -rnE "account_deletion_request|no longer accepted|Account deletion is manual|deletion (stays|is) a support|support (request|ticket)" docs` (excluding archive and evidence dirs). None states the retired reading, so none changed:
- `docs/API_CONTRACT.md:6952` already calls it the fallback while the command is off.
- `docs/DATA_MODEL.md:2442,2453` list the feedback type, still accepted.
- `docs/specs/argus-execution-board.md:79` "while it is off, login deletion stays a support request".
- `docs/specs/argus-minimum-viable-ecosystem-experience.md:731` same.
- `docs/GUEST_PUBLIC_LAUNCH_SAFETY.md:159` "Account deletion is manual", true for hosted while the flag is off; also test-pinned by `tests/test_private_alpha_release_docs.py:1085`, left.
- `docs/PRIVATE_LAUNCH_RUNBOOK.md`: no mention of the feedback type.
- Handoff L175 and L505 consistent (L505 is the pre-Lane 6 "What exists today").
- `docs/reports/native-readiness-audit.md:122` is a dated report; `docs/api/openapi.yaml:12362` is the generated enum.

Founder-locked copy block (`### Copy (founder-locked, Iris's wording)`) untouched.

Commands and results:
- Doc-coupled Python tests in `cuadrao-py310-runner` (venv volume of `cuadrao-verify` mounted read-only; poetry.lock identical to `a8c37d3a`): `pytest tests/test_retention_purges_are_wired.py tests/test_versioning_boundary.py tests/test_alpha_artifacts.py tests/test_public_excerpt_api.py tests/test_private_alpha_release_docs.py tests/test_render_workflow_proof.py tests/test_render_release_profile_contract.py tests/research/test_research_contract_example.py tests/agent_runtime/test_post_result_edit_routing.py tests/test_account_deletion_fk_census_postgres.py -q --no-cov`: 144 passed, 3 skipped (census real-PG, no database). Log `~/.claude/orchestrate/cuadrao-iphone-candidate/w8-docs/pytest-docs.log`.
- `cd web && bun test __tests__/account-deletion-api.test.ts __tests__/chat-next-move-rows.test.ts`: 46 pass, 0 fail (the first reads the locked copy from the handoff).
- `uv run --with markdown-it-py python scripts/check_docs_links.py --base a8c37d3a...`: "Checked local links in 8 changed document(s)." exit 0. It wrote `uv.lock` (deleted) and replaced the gitignored `.venv` that W3's poetry install had made in this worktree (uv printed "Removed virtual environment at: .venv").
- `git diff --check`: clean.
- `git fetch origin && git merge-tree --write-tree HEAD origin/codex/cuadrao-release-ui` (#790 at `4bb1696a`): one conflict, `docs/specs/argus-execution-board.md`, the known board row. Same conflict set as `876c2f8a6`. No new conflict; #790 does not touch the handoff.
- `gh pr edit 808 --body-file`: Status line now names head `a1ebf4b4f...`, CI pending on this head, review PASS through `876c2f8a6`, delta review of `a1ebf4b4f` pending. Rest of the body unchanged (diffed before writing).
- PR comment: https://github.com/lagarcess/argus/pull/808#issuecomment-5981262375
- Not checked: CI on `a1ebf4b4f` (just pushed), rendered Markdown on GitHub.

## Unit 2. Issue #789

Re-verified against `a8c37d3a` (worktree `cuadrao-verify`, read only). `1478957e` is an ancestor of `a8c37d3a`.

| Requirement | Code at `a8c37d3a` | Tests | Met |
| --- | --- | --- | --- |
| HMAC-SHA-256 under a server secret, not in DB | `CodeKey.digest` (`invite_codes.py:120-126`), domain-separated message; secret via `InviteCodeSecretSettings`. Only other SHA-256 in the household domain: `hash_token` (`repository.py:59`), link tokens only (`locate_secret`). No `code_hash` reader left in `src/` | `test_digest_is_keyed_versioned_and_names_its_key`, `test_secrets_load_through_pydantic_settings_and_never_show`, `test_hasher_reads_only_the_settings_model` | Yes |
| Versioned digest | `v2.<key id>.<hex>`; DB check in `20261003150100` | same | Yes |
| Link tokens decided | stay plain SHA-256 of 256-bit tokens (docstring, API_CONTRACT) | n/a | Yes |
| Fail closed | `_code_secret_ready` (`api/households.py:78`), readiness (`routers/ops.py:158-162`), 503 at runtime, placeholder floor | `test_missing_or_short_secret_fails_closed`, `test_placeholder_secrets_are_refused`, `test_households_stay_off_without_the_secret`, `test_beta_invites_start_closed_without_the_secret`, `test_readiness_fails_when_a_code_flag_is_on_without_the_secret`, `test_secret_removed_after_start_answers_503` | Yes |
| Rotation via `_PREVIOUS` | `CodeHasher.candidates`, `find_code` re-hash with `rehashed_at` | `test_rotation_looks_up_under_current_then_previous`, PG `test_rotation_finds_old_codes_and_rehashes_them_on_use` | Yes |
| Entropy decided, generator | `CODE_LENGTH = 12`, Crockford alphabet, `new_code` uses `secrets.choice`; API_CONTRACT L7578 "Why 12 characters" | `test_code_has_sixty_bits_in_a_typeable_shape` | Yes |
| Rate limits on preview, redeem, accept | `api/invite_limits.py` (existing helpers, keys `invite-code:ip:`/`invite-code:user:`, 429 + Retry-After); `routers/households.py:157,176,464,479` = household preview, household accept, beta preview, beta redeem | `test_failed_guesses_trip_the_account_limit_with_retry_after` [accept, preview], `test_failed_guesses_trip_the_ip_limit_and_spare_other_ips`, `test_beta_lookups_are_limited_with_no_founder_bypass` [preview, redeem], `test_limiter_keys_use_the_trusted_client_ip_helper`, `test_concurrent_guesses_cannot_run_past_the_failure_budget` | Yes. Per-IP trip has its own test on household accept only; the other paths share `invite_limits.attempt` |
| No founder bypass | none | `test_beta_lookups_are_limited_with_no_founder_bypass` | Yes |
| Migration drops old columns | `20261003150100_invite_code_digests_private.sql:45-47` drops the index and `code_hash` on both tables | PG `test_no_client_role_can_ever_read_a_code_digest` | Yes |
| Real PG: other secret does not find code | | PG `test_codes_are_keyed_and_unknown_under_another_secret` | Yes |
| Valid code after unrelated failures | | `test_failed_guesses_trip_the_ip_limit_and_spare_other_ips` (200 from another IP) | Yes |
| Env docs list the secret, flags off | `.env.example:256-257`, `render.yaml:72,74`, release profile `:93-94`, `.github/argus-env.sh:71-72` | | Yes, with the two #804 gaps below |

Real-PG cases from `candidate-4af8fced/s1-s2-backend/pg-junit.xml` (suite 605 tests, 0 failures, 0 errors, 0 skipped, 2026-10-04T05:33:47Z). `git diff a8c37d3a 4af8fced` is empty for the invite module, limiter, router, household domain, migration and both test files.
- `test_codes_are_keyed_and_unknown_under_another_secret` passed
- `test_rotation_finds_old_codes_and_rehashes_them_on_use` passed
- `test_without_a_secret_nothing_is_written_and_codes_are_refused` passed
- `test_no_client_role_can_ever_read_a_code_digest` passed
- `test_single_use_claim_checks_its_row_count_even_without_the_lock` passed
- `test_revoke_in_flight_on_a_full_link_is_not_counted_as_overflow` passed
- `test_household_accept_refuses_an_invitation_revoked_under_it[row_lock]` passed
- `test_household_accept_refuses_an_invitation_revoked_under_it[guard_only]` passed

CI: run 37118780125 at head `a8c37d3a...`, conclusion success; job `guest-release-gates` 111192423989 success; its log shows `tests/test_invite_code_security_postgres.py ........` and "605 passed", "required pytest gate passed: 605 tests, zero skips".

Rerun today, container, code identical to integration: `pytest tests/household/test_invite_code_security.py tests/test_invite_code_security_postgres.py -q --no-cov`: 35 passed, 8 skipped (PG, no database). Log `w8-docs/pytest-invite.log`.

Live: W7 run3 checks 110 and 111, seq 110 to 120, `POST /invites/redeem`: ten 404 then 429 with `Retry-After: 3582`, and a real code refused while limited.

GitHub writes:
- #804 comment (runbook step for the secret; declare both beta flags `"false"` in `render.yaml` and the release profile): https://github.com/lagarcess/argus/issues/804#issuecomment-5981281332
- #789 closing comment (requirement table, rename `ARGUS_INVITE_CODE_PEPPER` to `ARGUS_INVITE_CODE_SECRET`, evidence, remaining items in #804, standing gates): https://github.com/lagarcess/argus/issues/789#issuecomment-5981282292
- #789 state: CLOSED, reason COMPLETED.

Follow-up observation, not filed: W7 notes the local API logged "Trusted client-IP header missing; using socket peer". Hosted per-IP invite limits depend on the proxy sending `CF-Connecting-IP`; worth a line on #804 next to the `WEB_CONCURRENCY` check if the lead agrees.
