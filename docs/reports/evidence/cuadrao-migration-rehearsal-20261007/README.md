# Migration rehearsal evidence (October 7, 2026)

Local only, synthetic data, throwaway databases on the Supabase CLI's local Postgres 17.6. No hosted system was written to. `rehearsal-output.txt` is the retained output of `rehearse_migration_upgrade.py` on this branch.

## What was proven

| Test | Result |
| --- | --- |
| Clean install: all 114 migration files at the candidate, empty database, each file recorded | Applies; 114 ledger rows |
| Production-equivalent fixture: `main`'s 79 files minus the one missing in production (78, effects only, no ledger rows) plus production's actual 81 ledger rows (74 mapped to files, 7 legacy) | The gate reports `blocked` only by `missing_candidate_migrations` (35), the same as the production ledger read |
| Upgrade with `apply_approved_migrations.py`: 1 `--unrecorded` (`20260505000001`) and the 35 Cuadrao versions, 5 s lock timeout per file | 36 steps applied; the gate then reports `pass`, 0 missing, 0 content drift, 0 name drift; ledger 116 rows |
| The same command run again | Refused: version already in the ledger |
| Catalog comparison, clean install against upgraded fixture | 0 differences in columns (857), constraints (628), indexes (289), triggers (67), functions (102), policies (77), table grants (452), RLS flags (96) |

## Count reconciliation

114 files at the candidate = 79 on `main` + 35 Cuadrao. Production ledger 81 = 74 of `main`'s files + 7 legacy rows with no file. The other 5 `main` files have no ledger row: four with their effects already in the schema, one (`20260505000001`) genuinely missing. Real actions: 36 (35 recorded, 1 unrecorded). Ledger afterwards: 116.

## The production ledger input

`production_ledger_hashes.py` holds, for each of the 81 production ledger rows, the version, name, statement count and statement hash. They were read from production with catalog `SELECT`s on October 7 (no statements text, no user rows). Run through the gate's own logic they reproduce its pinned hand-reconciliation hash `e352a2c003572611f0fb201305e085e3736eefbfae0d62ef29f4322a18062032` exactly. `offline-gate-summary.json` is the resulting offline report for candidate `93571e593`: blocked only by the 35 missing migrations.

## What this does not prove

Real production row counts and lock durations (the databases are empty); hosted Supabase behavior (grants, extensions, pooler, Auth); the official gate run with the database URL, which only the operator can do.
