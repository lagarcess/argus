# Consumer staging preflight: October 9, 2026

After Lucas approved PR #937, read-only checks against
`https://cuadrao-api-staging.onrender.com` found the manual-money surface disabled.
[Request results](preflight.json) contain no credentials or personal data.

- Health: HTTP 200, healthy.
- Accounts, Home, Plan and financial Search: HTTP 404,
  `financial_accounts_unavailable`.
- Render readback: live deploy `dep-db4ofq142hec73edibig`, backend
  `cad1cbe1ec27ff89c08eadbec31718a0e627383c`, automatic deployment off.
- `ARGUS_FINANCIAL_ACCOUNTS_ENABLED` is absent from the service environment.
  The deployed source defaults it off and checks it before authentication.
  Accounts, transactions, budgets, goals and financial Search share this gate.

These are unauthenticated feature-gate checks, not signed-in journey acceptance.
No hosted setting, schema, account, data, deployment or service was changed.
The native account, money, plan and Search transport files are unchanged between
the deployed backend's source commit and the merged native checkpoint. This
supports proceeding with compatibility tests; it does not prove them passed.

## Subsequently approved unblock

Lucas approved the bounded staging setup after reading this preflight: enable
the financial-accounts gate on `cad1cbe1e`, restart and obtain a synthetic test
login. The existing staging owner is assigned that work. The request results
above record the pre-activation state, not a claim about the later service.

The staging owner must enable only `ARGUS_FINANCIAL_ACCOUNTS_ENABLED=true` on
this service, retaining its currently pinned backend revision and applied C0/C1
schema. Do not deploy current integration, which needs later Business columns.
Applying the environment change requires a service restart or deploy using that
same pinned revision. No newer code, migrations, guest mode or production change
is authorized.

The staging owner's existing synthetic user's temporary credentials were removed
after its persistence probe. Arrange a dedicated signed-in test identity and
private credential handoff before native acceptance; do not reset a real user's
password. The approved synthetic setup does not authorize changes to real users.

Once available, use the dedicated Consumer simulator with sign-in enabled and
preview mode off. Check accounts, transactions, budgets, goals, search/find later,
per-currency totals, correction history and relaunch balances in English and
Spanish with large text. Retain the accepted #937 evidence. No guest, receipt,
shared-plan, redesign, RevenueCat, accessibility-tooling or phone-install work.
