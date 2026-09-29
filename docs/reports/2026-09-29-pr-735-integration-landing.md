# PR #735 integration landing

## Landed change

- PR: [#735](https://github.com/lagarcess/argus/pull/735)
- Approved PR head: `a2f53c16fefee352f256632bc657550311cd6e19`
- Integration parent at squash: `e3f9db651ade97512107e835dbf442aacf637641`
- Squash merge: `296195e86c972e846c251d256b3cc211975bfd57`
- Merge time: September 29, 2026, 02:56 UTC (approx)

## Outcome and remaining work

Financial accounts first slice behind `ARGUS_FINANCIAL_ACCOUNTS_ENABLED`
(default-off). Registered users can create, list, reopen, edit, and write or
correct an opening balance with revision history. Opening writes require
caller-visible `expected_version` (stale-opening hold fix on tip `a2f53c16`).
While the flag is off, every route answers `404 financial_accounts_unavailable`
before authentication.

No hosted feature enablement. No production deployment. No `main` promotion.
[#732](https://github.com/lagarcess/argus/pull/732) design hold untouched.

## Accepted evidence

- Pre-merge worker gates on `a2f53c16`: tip CI SUCCESS (10 checks; docs-checks
  skipped), Codex Completed clean (“Didn't find any major issues”), **0**
  unresolved review threads, behind_by **0** vs `e3f9db65`, modularity clean on
  reconciled tree, fixer re-READY after stale-opening HOLD.
- Durable evidence under `docs/reports/evidence/financial-accounts-first-slice/`.
- Contract: `docs/API_CONTRACT.md` §17.3, OpenAPI, lane spec, DATA_MODEL.

## Documentation and environment audit

Flag already declared in product squash (`.env.example`, `render.yaml`,
`.github/argus-env.sh`, release profile) as default `false`. This register adds
the landing report and ledger entry only. No secrets rewritten. Hosted
`ARGUS_FINANCIAL_ACCOUNTS_ENABLED` remains unchanged / default-off.

Direct push to integration is expected to be rejected (branch protection),
so this register ships through a docs-only PR (same pattern as #734 / #736 /
#737 / #740 / #741).

## Authority boundary

This checkpoint stops at `codex/private-alpha-next`. No main promotion,
deployment, hosted Blueprint sync, tester exposure, or merge of #732.
[#732](https://github.com/lagarcess/argus/pull/732) remains design hold.
#646 and #634 were not touched.
