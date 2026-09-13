# Registry declaration acceptance evidence

The declaration-only source at `b17d25775028b7d7e2ea2f30ab35348291c973cc`
was reconciled with integration `3ceada309a450c12335ad6e1048ab141ce1680bb`
by normal merge `6b8d846e8543d532ecbfac73b9d744a3b1ac1ec2`.
The original lane base was `9e8b59b23f29d432ec7603c42f7362137b1ee21f`.

The [boundary record](boundary-verification.json) preserves the full interpreter
prompt/schema comparison, frozen-file hashes, serializer classes, protected
dispatcher/recompute hashes, excluded sharing paths, test counts and local
environment controls. All 17 fingerprinted files, the fingerprint itself and
the serializer remain byte-identical to integration. No public receipt or
excerpt implementation or migration is part of this lane.

The [integration audit](reconciliation-6b8d846e.json) records the incoming
profile-save changes. The chat shell and its contract test overlap; incoming
settings removal and registry behavior both survived the merge. Backend,
workflow, script and Python test files did not change, so their evidence is
retained. Frontend checks and browser acceptance were repeated.

| Evidence | Result | Source |
| --- | --- | --- |
| Complete backend suite | 6,908 passed; 585 existing opt-in skips; zero failures | `b17d2577`, backend unchanged after merge |
| Complete frontend suite | 1,691 passed; zero failures | `6b8d846e` |
| Frontend lint and production build | Passed; lint has eight nonblocking warnings | `6b8d846e` |
| Fingerprint, import boundaries and Lane C | 101 passed, including 31 fresh-process probes | `6b8d846e` |
| Modularity budget | No violations in the reconciled tree | `6b8d846e` |
| Bilingual fixture browser matrix | Results, screenshots and provenance in [post-merge bundle](6b8d846e/browser/README.md) | `6b8d846e` |

The [earlier browser bundle](b17d2577/browser/README.md) remains immutable,
including the disclosed correction to inconsistent authored financial fixtures.
Browser fixtures prove rendering and frontend continuity. They do not exercise
the interpreter, providers, backtest engine or a real API. No new live eval,
paid provider request or fingerprint reset was performed. Additional provider
cost: **$0**.

The unfinished interpreter rewrite and all six snapshots are preserved on
[`codex/registry-interpreter-rewrite` at `dcde9aff`](https://github.com/lagarcess/argus/tree/dcde9affb92abd16488310ac44e91ef9d5f7c6dc).
Its [one-page findings note](../../registry-interpreter-rewrite.md) reports the
historical measurements and regressions for roadmap decision 9.

These artifacts do not declare the lane ready. The final published-head CI,
review outcome, unresolved-thread count and evidence revalidation belong in
the terminal PR audit after the final Codex review returns.
