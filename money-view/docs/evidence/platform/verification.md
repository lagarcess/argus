# Local verification checkpoint

Captured September 21, 2026, before the expanded platform's GitHub review.
This is local implementation evidence, not a deployment or hosted-readiness claim.

Implementation commits: `f127e800` (domains/runtime) and `0ac3c411` (interface).
Private integration base: `d48249dc8f0fd955fa6ee16c11d99d4eb111aedb`.
Only `codex/money-placement-pilot` is an authorized PR/merge destination.

| Check | Result | Evidence |
| --- | --- | --- |
| Complete Python suite | 367 passed | [Backend log](backend-verification.log) |
| Ruff, server/tests/scripts | Passed | [Lint log](lint-verification.log) |
| TypeScript and production build | Passed; entry JS 98.05 kB gzip | [Build log](frontend-build.log) |
| Real-API browser journeys | 26 passed, 0 failed | [Browser log](browser-acceptance.log), [summary](browser-acceptance-summary.json) |
| Browser source continuity | 115 files unchanged during verification and checked again before packaging | [SHA-256 manifest](browser-source-hashes.json) |
| Capacity | 14,400 successful requests, all 10,000 identities, 5 million generated ledger rows | [Measured workload and limits](../../SCALE_EVIDENCE.md) |
| Final capacity source continuity | Fresh 400-request probe, no source drift | [Probe receipt](../scale/final-source-probe-5m.json) |
| Backup/restore | 2.56 GiB database, integrity/ownership/source checks passed | [Backup receipt](../scale/backup-5m.json) |

Browser coverage includes Spanish and English, 1440/1024/768/390/320 widths,
money views, CSV/edit persistence, planning/bill/goal/scenario receipts,
simulation and insufficient funds, services, settings, role isolation,
new-member login, deliberate reset, session revocation during export,
pending notice navigation, overlapping publication jobs, and immutable
before/after answers. The tests use isolated local databases. Test servers
and the capacity fixture files were cleaned up.

The laptop workload is 20 requests/second for ten minutes and 40 for one
minute. It does not qualify a 4-vCPU/8-GiB host, 38.4 million retained rows,
the longer design duration, real provider latency, live model behavior,
pricing, hosted identity, off-host backups or a production SLA.

## Independent review closure

Every finding was addressed at its shared owner and received an explicit
clean scoped follow-up. Reports distinguish inspection from tests actually run.

| Scope | Closure | Report |
| --- | --- | --- |
| Ledger and financial totals | Clean | [Ledger](reviews/ledger-review.md) |
| Identity lifecycle | Clean after final-membership cleanup | [Identity](reviews/identity-review.md) |
| Planning | Clean after expense-category validation and bounded scenario history | [Planning](reviews/planning-review.md) |
| Services | Clean after subscription-table ownership, calendar renewal, replay and dated evidence fixes | [Services](reviews/services-review.md) |
| Investing | Clean after settlement rounding and recurring-worker fencing | [Investing](reviews/investing-review.md) |
| Assistant | Clean after preflight target validation and shared export authentication | [Assistant](reviews/assistant-review.md) |
| Frontend boundaries | Clean after local-member login, authenticated downloads, pending navigation and visible form errors | [Frontend](reviews/frontend-review.md) |
| Runtime/scale | Clean after retained admission truth and total model deadlines | [Runtime](reviews/scale-review.md) |
| Deposit ingestion/jobs | Clean after shared CLI lease renewal | [Deposit jobs](reviews/deposit-scale-review.md) |

The original private PR #657 also reached explicit reviewer-clean acknowledgment
and zero unresolved threads before merge. The [prior-PR audit](../../PR_REVIEW_AUDIT.md)
contains its exact reviewed head, timestamps, links and findings.

GitHub Codex review and required CI for this expansion follow this checkpoint.
The final PR audit records their terminal state. No production changes,
Supabase migrations, protected-branch merges or deployments were performed.
