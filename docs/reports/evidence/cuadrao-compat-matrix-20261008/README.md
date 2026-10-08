# Compatibility matrix (October 8, 2026)

Local, synthetic, nothing hosted. Throwaway databases on the Supabase CLI's local Postgres 17.6. Candidate `cad1cbe1ec27ff89c08eadbec31718a0e627383c` (the Build 1 freeze). Previous production code is `main` `a9286b21886eb03df7a21f2f4b7d5e79af570679`.

`compat_matrix.py` builds three schema states from a production-equivalent fixture (effects of `main`'s files plus production's 81 ledger rows), each through the real applier, then runs each code version's real-Postgres test files (`tests/*postgres*.py`) against a fresh copy of each state.

| Schema state | Previous production code (34 files) | Build 1 code (73 files) |
| --- | --- | --- |
| **S0** today | 379 passed, 27 skipped, 1 failed | 409 passed, 227 failed, 304 errors (needs the new tables) |
| **S1** after C0 (website migration alone) | 379 passed, 27 skipped, 1 failed | 420 passed, 216 failed, 304 errors (still needs C1) |
| **S2** after C1 (consumer files, plus the unrecorded `20260505000001`) | 379 passed, 27 skipped, 1 failed | **722 passed, 31 skipped, 1 failed, 0 errors** |

## After the first Business step (B1, `20261008100000`), Build 2 candidate `64833f6d284d60562829c0545dc413d5324c9d5a`

Applied on top of C1 with the real applier (`ARGUS_COMPAT_TAIL`), then the same suites:

| Code | Result on C1 + B1 |
| --- | --- |
| Previous production code (`main` `a9286b21`) | 379 passed, 27 skipped, 1 failed |
| Build 1 (`cad1cbe1e`) | 722 passed, 31 skipped, 1 failed, 0 errors |
| Build 2 (`64833f6d2`) | 727 passed, 52 skipped, 1 failed, 0 errors |

The one failure is the same scipy import trap in every run. Build 2 skips 21 more tests than Build 1: they need a running local Storage service, which a plain database does not have, so Storage behavior itself (bucket limits, object delete on disconnect and on account deletion) is **not** exercised here; Business proved it against a local Storage stack (#905, #914 evidence). The rehearsal databases get the `storage` schema from the local container, as hosted always has it.

## After all four Business steps (B1 to B4), final integration code `f5a2007cd6f8e169a27cb1e6e3827ccbaa1bfb9a`

C1 plus `20261008100000`, `20261008110000`, `20261008130000` and `20261008140000`, each through the real applier, then the same suites (`results_tail_b1_b4.json`; the "build2" row in that file is the final integration code, not the earlier Build 2 candidate):

| Code | Result on C1 + B1 to B4 |
| --- | --- |
| Previous production code (`main` `a9286b21`) | 379 passed, 27 skipped, 1 failed |
| Build 1 (`cad1cbe1e`) | 720 passed, 31 skipped, 3 failed |
| Final integration (`f5a2007cd`) | 771 passed, 84 skipped, 2 failed |

Failures, all read:
- `test_asset_rollup_pair_symbol_normalization_matches_memory_contract` fails in every row: the local `scipy` import trap (#852).
- Build 1 also fails `test_account_deletion_fk_census_postgres.py::test_sweep_names_every_user_reference_and_the_census_document_matches_it` and `test_client_grants_postgres.py::test_every_relation_is_listed_exactly_once`. Both compare Build 1's own documented table lists with the live schema and fail because B2 to B4 added tables (`spaces`, `whatsapp_*`, and user-referencing rows keyed by `owner_space_id`). They are currency checks, not a broken behavior, and the final code's versions of them pass. They are one more reason Build 1 code is not the runtime once B2 to B4 are applied: the minimum compatible code version is Build 2 or later.
- Final integration also fails `test_document_jobs_postgres.py::test_two_running_instances_recover_a_dead_worker_without_restart` (`needs_attention` instead of `review_ready`). It passes when run alone on the same database and fails again in a full-suite run on a fresh copy, so it is order-dependent in this local macOS run. The same commit's CI is green on Linux. Cause not found; reported to Business.

## What it shows

- **Deploy order.** Build 1 code needs C1 first. On today's schema, or after C0 only, it fails on the missing tables. C1 must be applied and verified before Build 1 deploys.
- **Old code on the new schema.** Previous production code gives the same result on S0, S1 and S2: C0 and C1 do not break what it already did, in these suites. Reverting the application code after C1 is therefore possible at the database level, until new-format data is written (the minimum compatible code version applies from the first hosted financial write).
- **Client grants.** Comparing `anon` and `authenticated` grants between S0 and S2 on tables, columns and routines: 0 removed. 19 table grants, 161 column grants and 1 routine grant added, all on the new financial tables and `is_active_household_member`. Old code reaching the database as a client sees no lost access.
- **The one failing test**, in all six runs, is `tests/test_search_postgres.py::test_asset_rollup_pair_symbol_normalization_matches_memory_contract`. It fails with a local `scipy` import error (`dlopen ... _spropack`), the macOS arm64 runtime trap tracked in #852. It is an environment failure, not a schema one.

## What it does not show

- These are database-level suites. They do not drive the old or new API end to end, and they do not cover the web client.
- B1 to B4 (Business) are not in this table. Their compatibility, including B4's effect on Personal, is Business's evidence on #914.
- Hosted behavior (pooler, extensions, Auth) is not covered.
