# Full-migration PostgreSQL repair proof

The registry fixture independently generated the Auth email and profile email.
The existing `validate_profile_auth_identity` trigger correctly rejected their
mismatch. The fixture now generates one email and reuses it.

An isolated local Supabase stack applied all 71 committed migrations and the
repository seed, then ran the CI-equivalent local reset. Before editing, all
nine registry cases failed at fixture setup. After the fixture-only correction:

- Registry cases: **9 passed**, zero failures, errors, or skips.
- Full `tests/test_*_postgres.py` matrix: **352 passed**, zero failures, errors,
  or skips.
- Both JUnit reports passed `scripts/qa/assert_pytest_gate.py`.
- Ruff and `git diff --check` passed.

The [sanitized receipt](full-migration-receipt.json) records the clean source
SHA, before/after fixture hashes, red/green counts and JUnit hashes. The
[source manifest](source-hashes.json) binds all 71 migrations. Green reports
are retained for the [registry](registry-green.xml) and
[full matrix](matrix-green.xml), with [exact-copy hashes](preservation-manifest.json).

This measures the fixture patch on `262d670f`, not a later clean PR head. No
schema or migration changed. There were no hosted operations or provider calls.
The owned stack and volumes were removed; the pre-existing stack was untouched.
