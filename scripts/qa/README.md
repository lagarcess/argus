# Issue-248 real-auth QA harness

End-to-end account-recovery and session-control QA against real Supabase Auth.
Everything here targets the worktree-local Supabase stack (or one approved QA
branch) and is blocked from production by `assert-nonprod-target.sh`.

## One-shot run

```bash
supabase start -x vector,edge-runtime,functions,imgproxy   # once per machine boot
supabase db reset --local                                  # migrations from zero + seed
bash scripts/qa/write-local-env.sh                         # untracked .env + web/.env.local
bash scripts/qa/run-local-auth-qa.sh                       # guard -> backend -> identities -> journeys
```

The runner executes four Playwright phases from `web/e2e/qa-248/`:

1. `1-recovery.spec.ts` — enumeration safety, Mailpit delivery, single PKCE
   exchange, reset, reuse/malformed/expired links, wrong/correct current
   password.
2. `2-sessions.spec.ts` — two-context revoke-others/revoke-all, ordinary
   logout scope, stale-token rejection, partial cookie-cleanup honesty.
3. `3-es-mobile.spec.ts` — Spanish + mobile surfaces, cross-user isolation.
4. `4-verification-outage.spec.ts` — retryable 503 while the verification
   database is down and the auth provider stays healthy (runner-orchestrated).

Evidence (screenshots, HTML report, backend log, current-password state) lands
in `temp/qa-evidence-248/`.

## Product limits the harness must respect

- Argus login limiter: 8 attempts per email and per IP per 10 minutes. The
  runner restarts the backend between spec files; each file stays within one
  identity's budget.
- Argus recovery limiter: 5 requests per email and per client address per 10
  minutes. Specs use run-unique `x-forwarded-for` addresses; sends to the
  recovery identity stay at 3 per run, so leave ~10 minutes between full runs
  against a still-running server (fresh servers reset the in-memory buckets).
- GoTrue `max_frequency` (1s between sends per user): specs call
  `respectSendWindow()` before repeat sends.
- `supabase/config.toml` pins `otp_expiry = 60` so the expired-link journey
  completes in-band. Production keeps its own expiry.

## Identities

`setup-local-identities.sh` creates two disposable users through the real
Argus signup path (allowlist rows come from `supabase/seed.sql`), verifies
login, and writes runtime credentials to untracked `.qa-identities.env`.
`--teardown` removes users, profiles, and the credential file. Passwords are
generated per setup run and never committed; recovery journeys persist the
current password in `temp/qa-evidence-248/qa-state.json`.

## Hosted QA branch mode

Export `ARGUS_QA_APPROVED_SUPABASE_REF=<branch project ref>` and point the
generated env files at that branch before running; the guard then admits
exactly that ref and still hard-fails on any production reference.
Mailpit-dependent recovery specs skip in hosted mode — hosted recovery
delivery stays gated on sandbox SMTP.

## Backend tests

The focused backend matrix must run hermetically, per `AGENTS.md`:

```bash
OPENROUTER_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest tests/test_auth_sessions.py tests/test_alpha_api_supabase.py \
  tests/test_alpha_artifacts.py tests/test_environment_scripts.py -q --no-cov
```
