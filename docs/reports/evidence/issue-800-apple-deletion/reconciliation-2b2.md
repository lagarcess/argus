# Deletion reconciliation after primary currency

PR #862 keeps its existing deletion admission and recovery contract. This checkpoint adds current integration through a normal merge and records the affected checks. The release captain owns independent context review, exact-head CI, and guarded merge.

## Lineage

- Original lane integration base is `f5c83cd88a0af56dc8154a89c6ea4f75d9c518ce`.
- Previous reviewed worker head is `d11390cd816688463f4669ad90471685d427c24d`.
- Previous integration context is `7018e0edebbc370b999005a857230bf3c3a1ad8b`.
- Fetched integration is `2b2d0d9e8ed311c11b7585fbd757fb37f915e12f`.
- Normal reconciliation merge is `a77ff236ecb2ae243c6fbb5d5204176a0f986ca3`.
- GitHub inspection and cancellation readback confirmed an open PR targeting `codex/private-alpha-next`, without auto-merge or queue membership.

Before this evidence-only addition, the old and reconciled base-to-head diffs have the same stable patch ID, `c4f0454e5c4d3df7d035d1f73f08a800d349be2d`. There was no conflict or runtime fix during reconciliation.

## Shared context and retained proof

PR #853 changes profile PATCH to write only requested columns. `SupabaseGateway.update_user` now updates an existing profile instead of upserting its entire stale row, then rereads the authoritative profile. Existing Auth profile bootstrap may call this helper for explicit email or administrator updates. Deletion uses the gateway's Auth client and existing verification path. It does not call `update_user`. Its admission, ban, durable run, provider receipt, credential removal, and lock owners are unchanged.

PR #863 changes a synthetic canary HTTP fixture to close each response explicitly. It does not change production Auth, deletion, configuration, migrations, or provider behavior. Native currency changes do not alter this backend-only slice.

Byte comparison against the previous reviewed head found no change in deletion and Apple runtime modules, the account route, deletion requester verification, ordinary Auth verification, or the previously exercised PostgreSQL test modules. The prior independent 148 unit, 62 PostgreSQL, and 9 end-to-end checks remain recorded proof at their original heads. This checkpoint does not claim fresh PostgreSQL execution. The earlier 66-test retry-header delta proof also remains applicable.

## Current checks

The locked Python 3.11.15 environment ran synthetic and mocked tests with `PYTHONPATH=web:src:.`. `DATABASE_URL` and `ARGUS_DISPOSABLE_DATABASE_URL` were unset. The canary fixture used Bun 1.3.14.

| Command inputs | Result |
| --- | --- |
| `test_account_deletion_api.py`, `test_account_deletion_auth.py`, `test_openapi_compatibility.py`, `test_apple_sign_in_client.py`, `test_resume_account_deletions.py`, `test_force_account_deletion_step.py`, `test_home_country.py`, `test_private_alpha_canary_split.py` | 177 passed, 0 failed, 0 skipped in 14.86 seconds |
| `test_alpha_api_supabase.py` | 108 passed, 0 failed, 0 skipped, 1 existing cookie deprecation warning in 3.98 seconds |
| Documented ten-file mocked command in `tests/evals/README.md`, with `--no-cov` | 272 passed, 0 failed, 0 skipped in 10.81 seconds |
| `scripts/check_modularity_budget.py` on the combined tree | 0 violations |
| `git diff --check` | Passed |

The focused command uses `python -m pytest` with the listed test paths and `--no-cov -q`. The gateway suite includes the six focused profile cases, so these counts must not be summed as unique tests. An earlier restricted run passed 166 cases but failed 11 canary cases at loopback socket binding with `PermissionError`. No application behavior ran in those cases. The authorized loopback rerun above passed all 177 cases without code changes.

## Boundaries and cleanup

No PostgreSQL lease, simulator, build, provider credentials, root `.env`, hosted service, real account, or paid model was used. Loopback fixture servers ended with their tests. No new background process remains. No migration, flag, provider request, native UI, financial semantics, or household ownership changed.

Sequence Work into Verifiable Units kept this reconciliation limited to the reviewed deletion slice. Prior evidence remains dated to its original head. Current CI and independent context review are still required. Real Apple authorization, revocation, phone recovery, hosted acceptance, activation, and unresolved product decisions remain open.
