# Private Launch Runbook

> [!NOTE]
> Current operational gate for Private Alpha candidate validation. Use
> `docs/specs/private-alpha-next-roadmap.md` and
> `docs/specs/private-alpha-next-decision-memo.md` for product sequencing; use
> this runbook with `docs/specs/private-alpha-ci-cd-sota.md` and
> `docs/release-manifests/TEMPLATE.md` for release gating.
> For CI/CD promotion decisions, the decision memo is a later-context document, not part of this release gate.

> [!NOTE]
> The validated 2026-07-14 private-alpha checkpoint is recorded in
> [`docs/release-manifests/2026-07-14-private-alpha-release-integrity.md`](release-manifests/2026-07-14-private-alpha-release-integrity.md)
> and [#197's closure evidence](https://github.com/lagarcess/argus/issues/197#issuecomment-4965556704).
> It validates the existing branch-deployed private-alpha Render surface; it did
> not merge `main`, deploy production, enable automatic production deployment,
> invite testers, or expose testers.

This runbook is for the first trusted-user internet tests on Render.

## Launch URLs

- App: `https://argus-app-suz5.onrender.com`
- API: `https://argus-ohr5.onrender.com`

## Before Tester Sessions

The promotion target is `main`, but `codex/private-alpha-next` remains the
integration staging branch until the founder approves promotion. Do not merge to
`main`, open a release PR, or deploy production automatically; after founder
approval, promotion still follows the gate below. Every candidate needs a
release manifest before testers are invited; start from
`docs/release-manifests/TEMPLATE.md` and fill it with the exact candidate SHA,
API/web env fingerprint, workflow-service proof, canary evidence, rollback
target, and approver.

Local preflight doctrine:

- Run `.github/setup.sh` first and confirm `poetry run python --version` reports
  the `.python-version` runtime (`3.10.x`; currently `3.10.20`). Python 3.14
  green runs are non-canonical for deployed-runtime proof.
- Do local candidate work from sibling worktrees only, never nested inside
  another Argus checkout, so dotenv cannot inherit a parent `.env` and turn a
  mocked run into a live-provider run.
- For deterministic agent-runtime sweeps, blank live provider keys and set
  `ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture`. A clean mocked sweep
  is seconds-scale; minutes means stop and investigate live-call leakage.

1. Confirm the local checkout is the candidate commit you intend to promote:

```bash
git status --short
git rev-parse HEAD
```

2. Run the local predeploy smoke gate before any internet-facing canary:

```bash
.github/local-smoke.sh --expected-sha "$(git rev-parse HEAD)"
```

3. In Render, sync the Blueprint from `render.yaml` only when service config
   drift needs reconciliation.
4. Confirm Render is updating the existing `argus-app` and `argus-api` services.
   Stop if Render proposes duplicate services.
5. Confirm both services still have manual deploys enabled.
6. Export local ops and canary secrets, or keep these in the root `.env` file
   and let the scripts load them:

```bash
export ARGUS_OPS_TOKEN="..."
export ARGUS_CANARY_EMAIL="..."
export ARGUS_CANARY_PASSWORD="..."
export ARGUS_CANARY_SUPABASE_URL="https://lgdhvepyrzbnscqssgqq.supabase.co"
export ARGUS_CANARY_SUPABASE_SERVICE_ROLE_KEY="..."
```

For local founder/operator runs, `.github/canary-render.sh` also accepts
`MOCK_USER_EMAIL` / `MOCK_USER_PASSWORD` and `SUPABASE_URL` /
`SUPABASE_SERVICE_ROLE_KEY` from the root `.env`. The `ARGUS_CANARY_*` names
remain the preferred GitHub Actions secret names.

7. Confirm the API is in real-workflow private-alpha validation mode. This mode
   keeps the API lean and sends `Run backtest` through the durable Render
   Workflow job path:

```bash
.github/render-env-sync.sh api-real-workflow-on
```

Restart `argus-api` after changing Render env values.

8. Manually deploy **all three live services** from the candidate commit:
   `argus-api`, then `argus-app`, then **`argus-backtests`**.

   **`argus-backtests` is the easiest one to forget and the one that breaks the
   canary.** It is the Render Workflow service that actually runs backtests, it
   is not declared in `render.yaml`, and it was missing from this step until
   2026-08-11. On that promotion the API and web shipped while the workflow
   service stayed a week behind, and the canary stopped at
   `workflow_commit_mismatch` before spending money on a paid journey. Deploy it
   every time, and never let a promotion finish with the three on different
   commits.

   Do not create or deploy `argus-maintenance`. The cron remains deliberately
   absent until a separate founder decision applies the blueprint.

9. Confirm the live `argus-api`, `argus-app`, and `argus-backtests` deploy
   commits match the candidate commit you intend to test and that the latest
   deploys are `live`. Also confirm the deliberately unapplied cron is still
   absent:

```bash
ARGUS_RELEASE_SHA="$(git rev-parse HEAD)"
.github/render-env-sync.sh api-deploy-status
.github/render-env-sync.sh web-deploy-status
.github/render-env-sync.sh cron-deploy-status
```

If any of the three deployed commits is not `ARGUS_RELEASE_SHA`, stop and deploy
that stale service before running the strict canaries. The canary script
enforces the same deployed SHA/status check with `ARGUS_CANARY_SHA`, and its
resolver compares all three, which is what caught the workflow service running
behind on 2026-08-11.

For the current promotion, `cron-deploy-status` must report `status=absent`. Any
other cron status is a finding and a stop: do not deploy it as part of this
promotion. A failed Render lookup is also a real failure, never proof of
absence.

10. Run the product warmup script and verify the API stayed in real workflow
   mode. When Supabase verifier credentials are present, this also runs the
   stale queued/running job scan:

```bash
.github/warmup-render.sh --expect-mode real-workflow
```

Render workflow dispatch is ceremony-gated spend: the hosted product (real
users), the scheduled Private Alpha Canary workflow, and these promotion steps
are the only paths that run paid `workflow_proof` / `run_backtest_job` tasks.
Local and dev-agent work runs backtests in-process on local compute; the mode
scripts pin dispatch off (dev hard-off, QA default-off with explicit
pre-export opt-in).

11. Run the authoritative Spanish release journey with privacy-safe evidence.
This is the only release canary: it checks the exact deployed SHA, the real
Render workflow, finalized evidence identity, explicit decision capture, reload
hydration, Omnisearch provenance, and the deployed Spanish signup/login browser
path. It uses `ARGUS_CANARY_*` credentials when set and otherwise the local
`MOCK_USER_EMAIL` / `MOCK_USER_PASSWORD` aliases.

The requested-access denial check runs at the API layer, not in the browser.
`.github/canary-requested-signup-denial.py` posts the pinned signup address to
`POST /api/v1/auth/signup` with a placeholder captcha token and requires
`400 auth_signup_failed`. The deployed handler rejects a requested-role email
before it consults the captcha, so the probe proves the denial without a
solvable challenge, and `verify_no_signup_auth_identity` still proves through
the service role that no auth identity was created. Do not move this check back
into Playwright and do not weaken Turnstile anywhere deployed: Cloudflare
refuses tokens to headless automation by design, and that refusal is the
control working.

```bash
cd web && bun install --frozen-lockfile && bunx playwright install chromium
cd ..
mkdir -p temp/release-evidence
ARGUS_CANARY_SHA="$(git rev-parse HEAD)" \
ARGUS_CANARY_EVIDENCE_PATH=temp/release-evidence/canary-es-419.json \
ARGUS_CANARY_CAPTURE_PATH=temp/release-evidence/canary-es-419-capture.json \
.github/canary-render.sh
```

If a canary fails after warmup passed, do not redeploy one-off fixes in a loop.
The first authoritative run writes the sanitized capture beside the human-safe
evidence. Do not rerun the charged journey to collect a capture. When that
capture contains a final response, replay it locally before redeploying:

```bash
poetry run python scripts/ops/canary_capture_replay.py \
  temp/release-evidence/canary-es-419-capture.json
```

If the failure happened before any final response existed, keep the capture as
diagnostic evidence and inspect the hashed labels, failure stage, API logs, and
route-receipt summary instead of forcing a replay or spending a second journey.

Read the failure stage and reason before treating a canary red as a product
regression. `browser_auth` / `captcha_challenge_timeout` means the rendered
client never reached the auth API because the Turnstile challenge did not
complete, which is a harness limit on headless runners, not a product defect.
`browser` / `rendered_golden_path_failed` is the journey itself failing after
auth succeeded. Do not retry a challenge timeout: a headless runner cannot
solve it, so a retry only doubles the run.

If the exact candidate reaches the API but returns the normal interpreter
recovery response, keep the failed capture and evidence. Record the safe HTTP
status, route-receipt task/outcome summary, and environment fingerprint first;
do not increase token budgets or switch models as a speculative fix.

Use the replay to identify the macro-pattern and make one coherent fix.
Docker is optional for this step unless the production release path moves to
container images; prefer the local smoke gate plus canary replay first.

Before treating local UI changes as launch-ready, also run the browser recovery
spec against the local app/API environment:

```bash
cd web && bun run test:e2e e2e/chat-action-recovery.spec.ts --project=chromium
```

Only send the app URL to testers after API deploy-status, app deploy-status,
local smoke, warmup, the authoritative Spanish release canary, and the release
manifest all pass against the intended candidate commit. If either deploy-status
reports a different commit, deploy the candidate branch before continuing. If
warmup fails, do not invite testers yet. Check Render service status and redeploy
only if the service is stuck. If warmup passes but the canary fails, treat it as
an Argus product-path regression and inspect the failed-capture replay, API logs,
Supabase messages, backtest runs, and route receipts using the hashed labels and
internal access controls from the canary evidence.

For the daily automated gate, configure GitHub repository secrets with the same
canary variables above plus `RENDER_API_KEY` and `ARGUS_WORKFLOW_DATABASE_URL`,
then use the scheduled or manually dispatched `Private Alpha Canary` workflow.
Set `ARGUS_WORKFLOW_DATABASE_URL` from the `.env`/`.env.example` mapping to
`SUPABASE_POSTGRES_TRANSACTION_POOLER_URL`; do not use the session pooler for
short-lived workflow tasks. That workflow runs the local smoke gate, warmup,
and the authoritative Spanish release journey. The real backtest in that journey
is the live-provider drift check: it runs on `argus-backtests`, while
`release-config-audit --expect-mode real-workflow` proves the workflow env itself
is using `live_provider`. Warmup then runs the deployed `workflow_proof` task and requires
`workflow_runtime_provider_mode=live_provider` and
`workflow_runtime_proof=ready`, proving effective workflow runtime rather than
only saved Render env vars. It uploads the `private-alpha-canary-evidence`
artifact containing Spanish release evidence plus its exit-code file, and it does
not deploy or configure analytics. On failure it also uploads
`private-alpha-canary-failure-capture` and `private-alpha-canary-browser-context`,
the second holding Playwright's error context for the browser phase. The canary
script masks its own credentials out of those browser files before it exits,
because Playwright's error context records every rendered input value. Secrets
are scoped to the operational steps that need them; install and artifact upload
steps do not receive canary credentials or service-role keys.

The canary runs in two halves, and which half a file lands in decides whether a
fix to it is already live.

Everything up to and including the resolver runs from the ref the run started
on: Checkout, Set up Python, Set up Bun, Install Render CLI, and the first part
of "Resolve deployed canary release". That step runs
`.github/render-env-sync.sh`, which sources `.github/argus-env.sh`, then
`.github/canary-deployed-sha.py`, and only after that does it
`git checkout --detach` onto the deployed SHA. The other pre-detach steps pin
their versions inline and read no repo file.

Everything after the detach runs from the deployed release: the dependency
installs, the Spanish static UI assertions, `.github/local-smoke.sh`,
`.github/warmup-render.sh`, `.github/canary-render.sh` and everything it calls
(`.github/canary-browser.sh`, `.github/canary-requested-signup-denial.py`,
`.github/private-alpha-release-profile.py`), and the `web/e2e` specs.

`.github/render-env-sync.sh` is in both halves. The resolver calls it directly
before the detach, and `warmup-render.sh` and `canary-render.sh` call it again
after, so one job runs that same file from two different trees.

The starting ref depends on the trigger. A scheduled run takes the workflow YAML
and the initial checkout from `main`, because cron only executes the default
branch's YAML. A manual dispatch takes both from the ref selected for the
dispatch, because the Checkout step uses `github.sha`. The detach happens either
way.

So a resolver or workflow-YAML fix is live on the next scheduled run as soon as
it is on `main`, and can be exercised before that by dispatching the workflow
from its own branch. A fix to any post-detach script, which is most of the
canary harness, changes nothing until `main` is deployed to Render. Check which
half a file is in before reading a merge as a fix.

After the gate passes, copy the relevant command output and canary evidence into
a candidate manifest based on `docs/release-manifests/TEMPLATE.md`. The
`env_fingerprint` emitted by `.github/render-env-sync.sh release-config-audit`
remains the API/web environment fingerprint; record it as
`api_web_env_fingerprint` and keep the raw script output for traceability. The
workflow proof is recorded separately as `workflow_env_fingerprint` and
`workflow_env_status`. The workflow env proof must show
`workflow_env_status=ready`, `ARGUS_MARKET_DATA_PROVIDER_MODE=live_provider`,
redacted-present required workflow secrets,
`workflow_runtime_provider_mode=live_provider`, and
`workflow_runtime_proof=ready` before tester exposure. The manifest must also
name the candidate SHA, deployed API/web SHAs, `workflow_task`,
`real_workflow_task`, backtest service mode, workflow-service proof for
`argus-backtests`, canary evidence, rollback target, and approver.

The stale job scan is a manual step today. The `argus-maintenance` cron service
that would run it every fifteen minutes is declared in `render.yaml` and
deliberately not created (see Scheduled Maintenance), so nothing runs this scan
automatically.

**Destructive ops jobs refuse to guess their target.** `DATABASE_URL`,
`SUPABASE_URL` (or `SUPABASE_PROJECT_URL`), and `SUPABASE_SERVICE_ROLE_KEY`
must be set explicitly in the process environment. Dotenv discovery is disabled,
so a job with none of them set exits 2 rather than resolving whatever `.env`
happens to sit above it. Each job prints the resolved database and Supabase host,
without credentials, before doing anything destructive; read that line and
confirm it is the environment you meant.

```bash
DATABASE_URL=… SUPABASE_URL=… SUPABASE_SERVICE_ROLE_KEY=… \
  .github/stale-backtest-jobs.sh --json
```

For privacy-safe aggregate job health over the existing Supabase
`backtest_jobs.execution_metadata` records:

```bash
poetry run python scripts/ops/alpha_readiness_metrics.py --json
```

This report is operational only. It summarizes job statuses, readout provenance,
and timings without emitting user ids, conversation ids, prompt text, or product
analytics events.

## Backtest Workflow Modes

The permanent Render Workflow service is `argus-backtests`. It owns multiple
tasks:

- `argus-backtests/workflow_proof`: proof/canary task for API -> Render Workflow
  -> Supabase lifecycle validation.
- `argus-backtests/run_backtest_job`: real backtest execution task.

Use explicit API modes instead of editing individual flags by hand:

```bash
.github/render-env-sync.sh api-safe-off
.github/render-env-sync.sh api-proof-shadow-on
.github/render-env-sync.sh api-real-workflow-on
```

`api-real-workflow-on` is the controlled private-alpha validation mode: `Run
backtest` creates a durable real job and the UI reads queued/running/succeeded/
failed state from Supabase. `api-proof-shadow-on` is only for proof dispatch
validation. `api-safe-off` is the emergency rollback mode that disables workflow
dispatch/execution and removes the Render API key from `argus-api`.

## Render Environment Ownership

`render.yaml` is allowed to sync non-secret launch configuration: mode flags,
public service URLs, public Supabase URL/anon key values, feature flags, paper
trading mode, CORS origins, and model routing IDs.

Both `argus-app` and `argus-api` must set the server-only `ARGUS_APP_ORIGIN` to
the exact HTTPS app origin. The web service uses it for password-recovery
redirects; the API uses it for approval signup links. It must never use a
`NEXT_PUBLIC_` name. Local development may use the documented localhost
origins; production must not use HTTP.

### Auth Email Deliverability

Supabase Auth sends transactional email as `noreply@get-argus.com` through
Resend. Cloudflare DNS must keep one SPF record at the root,
`v=spf1 include:_spf.mx.cloudflare.net ~all`, for inbound
`support@get-argus.com` forwarding, while Resend's verified custom MAIL FROM
uses `send.get-argus.com` with `v=spf1 include:amazonses.com ~all` for outbound
SPF; DKIM at `resend._domainkey.get-argus.com` authenticates Resend's signature;
and DMARC at `_dmarc.get-argus.com` monitors strict alignment with aggregate
reports sent to `support@get-argus.com`. Start DMARC at `p=none`; after one week
of clean aggregate reports, moving it to `p=quarantine` is a founder decision.

Keep true secrets manual in Render:

- `DATABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_JWT_SECRET`
- `OPENROUTER_API_KEY`
- `ALPACA_API_KEY`
- `ALPACA_SECRET_KEY`
- `ARGUS_OPS_TOKEN`
- `ARGUS_APPROVAL_EMAIL_SMTP_PASSWORD`
- `POSTHOG_PROJECT_TOKEN`
- `PERPLEXITY_API_KEY`
- `ARGUS_VISITOR_KEY_SECRET`

Keep `NEXT_PUBLIC_POSTHOG_KEY` present but empty. Product analytics capture is
server-side only through the sanitized observability envelope.

Set `POSTHOG_REGION="US Cloud"` (or normalized `us`) for US Cloud unless the
founder explicitly changes the analytics data-region posture. US Cloud is a
compliance-posture choice for the current private alpha, not an accidental
default. Do not enable frontend PostHog, autocapture, session replay, or person
profiles.

Set `ARGUS_OPS_TOKEN` manually in Render for `argus-api`; it is intentionally
`sync: false`. Keep `ARGUS_OPS_TOKEN` out of frontend environment variables.

## Scheduled Maintenance

**The `argus-maintenance` service is declared but deliberately not created.**
At current scale there is no accumulated guest data to delete and no stranded
job to rescue, so an always-on paid service would buy nothing. Until it is
created, every recurring janitor runs when an operator runs it, and the
retention windows documented in `DATA_MODEL.md` hold exactly that often.

Create it when running the scripts by hand becomes impractical, which is a
guest-volume question rather than a date. Everything below describes the service
as defined, so it is accurate the moment a blueprint sync creates it.

It is declared in `render.yaml` and runs one entry point:

```bash
poetry run python scripts/ops/scheduled_maintenance.py
```

That pass runs guest workspace retention first, then stale and stranded backtest
job reconciliation, in that order. Every job runs even when an earlier one
fails, so one failure never hides another.

| Field | Value |
| --- | --- |
| Service | `argus-maintenance` (Render cron, `region: virginia`, `plan: starter`) |
| Schedule | `*/15 * * * *`, UTC |
| Owner | Render workspace owner for `lagarcess/argus` |
| Alert destination | `support@get-argus.com`, via Render service notifications for `argus-maintenance` set to notify on failure |
| Env contract | `ARGUS_RENDER_CRON_ENV` in `.github/argus-env.sh`, cron surface of `.github/private-alpha-release-profile.json` |

Every fifteen minutes, not daily, because the reconciler's own stale thresholds
are fifteen minutes (`DEFAULT_STALE_QUEUED_SECONDS` and
`DEFAULT_STALE_RUNNING_SECONDS`). A slower schedule would mean a user whose job
was stranded by a deploy waits the threshold plus the schedule gap. The same
cadence raises the retention ceiling from one bounded batch per day to ninety
six, so the seven-day guest window in `DATA_MODEL.md` holds under load instead
of only at low volume. Both jobs are no-ops on an empty window and safe to run
twice, so a retry costs a few cheap Supabase queries.

This runs on Render, not as a GitHub Actions cron, because the job deletes
production rows. Actions would put a production service-role key in a CI runner
and make write access to a workflow file equal to production delete access.
Render keeps the destructive step inside the boundary where that key already
lives.

The pass exits nonzero if any job fails, and prints a final JSON summary line
with `status`, `failed_count`, and `failed_jobs`. Alert on a nonzero exit or on
`"status": "degraded"`. Keep the per-job output: guest cleanup prints its
`selected`/`auth_deleted`/`auth_delete_failed`/`purge_failed` counts, and the
reconciler prints its scan report.

Secrets stay manual on this service, same as `argus-api`: `DATABASE_URL`,
`SUPABASE_SERVICE_ROLE_KEY`, `RENDER_API_KEY`, and `POSTHOG_PROJECT_TOKEN` are
`sync: false` and must be set in Render before the first run. `RENDER_API_KEY`
is what lets the reconciler read terminal task runs; without it the stale scan
reports errors instead of reconciling.

For the current promotion, the cron is deliberately absent and is not deployed.
Both the canary and `release-config-audit` verify that absence:
`cron-deploy-status` must report `status=absent`, and `cron_env_status` must be
`absent`. Those values are read back from the Render API rather than assumed.

If a later founder decision applies the blueprint and creates the service, it
becomes a deployed release surface. From that point onward, promotions must
verify its candidate SHA, live deploy state, and ready environment contract. To
close such a later promotion, record one real scheduled run: the run timestamp,
the summary line, and either nonzero selected/purged counts or documented zeros
on an empty window. While the service remains absent, record the two absent
statuses and the manual operator-job evidence instead.

## Runtime Tuning Flags

These are optional runtime knobs (not secrets). Defaults are safe for
private-alpha launch; record any override in the release manifest.

- `ARGUS_ENABLE_EXECUTION_REALISM` — models trading fees + slippage end to end.
  The capability is active by default, but modeled costs remain opt-in per
  idea. Runs without stated fees or slippage stay idealized and retain the "No
  fees/slippage" assumptions footer. Set the flag explicitly to
  `false|0|off|no` only as a kill switch; that restores the pre-realism path
  byte-for-byte. Record any kill-switch override in the release manifest.
- `ARGUS_STRUCTURED_REASONING_EFFORT` / `ARGUS_CAPABILITY_REASONING_EFFORT` —
  per-tier OpenRouter reasoning-effort overrides for the structured
  interpretation and capability-conflict calls
  (`xhigh|high|medium|low|minimal|none`). Unset uses the profile default. Lower
  effort saves cost in dev; run production at full effort. Invalid values are
  ignored with a warning.
- Prompt caching is automatic: structured-artifact calls
  (interpretation/repair/field-fidelity/capability-conflict) send a stable
  prefix so OpenRouter can cache it. No env toggle; it activates for those tasks.
- `ARGUS_RUN_LIVE_EVALS=1` — runs the live eval suite under `tests/evals/` (real
  model spend). Unset/`0` keeps evals mocked. Set it for the pre-merge
  landing-gate run and every `main` promotion candidate.

## Guest Staged Rollout

The operational security checklist for later internet-facing Guest exposure is
[Guest Public Launch Safety](GUEST_PUBLIC_LAUNCH_SAFETY.md). It is a promotion
and traffic-exposure gate, not a prerequisite for merging the Guest
implementation into the internal integration branch.

Product defaults:

```bash
ARGUS_GUEST_ACCESS_ENABLED=true
ARGUS_PUBLIC_ACCOUNT_ACCESS_ENABLED=false
NEXT_PUBLIC_GUEST_ACCESS_ENABLED=true
ARGUS_VISITOR_KEY_SECRET=<unique high-entropy environment secret>
ARGUS_DISCOVERY_GLOBAL_DAILY_CEILING=500
```

Guest access is part of the normal product shape. The two Guest flags are
default-on emergency kill switches; explicit `false` activates rollback. The
frontend flag controls presentation only and the API remains authoritative.
Public-account access remains off, permanent signup/login stays
allowlist-gated, existing admin/developer behavior is unchanged, and no Create
account promise is shown.

Hosted Supabase prerequisites are external operations and must be recorded in
the release manifest: anonymous Auth enabled, approved CAPTCHA configuration,
`NEXT_PUBLIC_ARGUS_TURNSTILE_SITE_KEY` present in the web build, provider
anonymous-sign-in limits, Argus origin enforcement and per-IP attempt limits,
no direct anonymous-role access to product tables, migrations applied through
`20260727230000_add_visitor_usage_counters.sql`, and a founder-approved
`ARGUS_DISCOVERY_GLOBAL_DAILY_CEILING`. Generate a unique
`ARGUS_VISITOR_KEY_SECRET` for each deployed environment so visitor identifiers
remain opaque and cannot be correlated across environments. Without the public
site key, non-loopback production preserves the auth landing rather than
beginning an unusable Guest bootstrap. Do not mutate hosted Auth configuration
as part of a code promotion.

Guest cleanup is a manual step today. The `argus-maintenance` cron service that
would run a bounded batch every fifteen minutes is declared in `render.yaml` but
deliberately not created at current scale, so nothing runs this deletion
automatically. Its owner, schedule, and alert destination are recorded under
Scheduled Maintenance and take effect the moment the service is created.

Until then the at-least-daily floor is an operator's responsibility, and the
retention windows in `DATA_MODEL.md` hold exactly as often as someone runs the
command below.

To inspect what the next scheduled pass would select, without deleting:

```bash
DATABASE_URL=… SUPABASE_URL=… SUPABASE_SERVICE_ROLE_KEY=… \
  poetry run python scripts/ops/cleanup_expired_guest_workspaces.py --dry-run --limit 25
```

Run the deleting form by hand only to drain a backlog faster than the schedule,
and only against an environment you intend to delete rows in:

```bash
DATABASE_URL=… SUPABASE_URL=… SUPABASE_SERVICE_ROLE_KEY=… \
  poetry run python scripts/ops/cleanup_expired_guest_workspaces.py --limit 25
```

Record the selected/deleted/preserved/failed counts and oldest eligible expiry
in the release manifest. A nonzero `auth_delete_failed` result or a failed
cleanup transaction must alert and retry; never compensate by deleting product
rows manually.

The same run is the retention boundary for the visitor-keyed tables, which are
deliberately not foreign-key bound and so have no owner to cascade from. It
reports `visitor_usage_purged`, `funnel_milestones_purged`, and `purge_failed`.
A nonzero `purge_failed` also exits nonzero and must alert: while it persists,
IP-derived visitor digests are being retained past their stated window. A dry
run deletes nothing and always reports zero for all three. Product deletion, anonymous-identity
revalidation, and Auth-row deletion are one database transaction. Claimed
source identities use a fifteen-minute reconciliation grace; incomplete
bootstrap identities use five minutes.

Conversion safety is non-negotiable: new accounts link the anonymous identity
in place; existing accounts use the email-hash-bound one-time handoff that
login claims before returning a permanent session. Guest
usage never merges into registered hour/day counters. Cleanup re-verifies
anonymous and unclaimed truth and must not delete a converted or permanent
account.

Guest funnel capture uses the shared metadata-only server envelope. Only the two
typed browser-owned facts cross `POST /api/v1/analytics/guest-events`; PostHog
keys, autocapture, session replay, prompts, assistant prose, exact
capital/dates, email, Auth material, private titles/previews, provider/model
names, and raw transcripts stay out.

Rollback order:

1. set `NEXT_PUBLIC_GUEST_ACCESS_ENABLED=false`;
2. set `ARGUS_GUEST_ACCESS_ENABLED=false`;
3. keep `ARGUS_PUBLIC_ACCOUNT_ACCESS_ENABLED=false`;
4. verify the preserved centered auth landing path;
5. stop new guest creation while retaining existing rows for safe expiry,
   conversion, or bounded cleanup.

Step 2 is a drain, not an active-session kill switch: already-verified guests
remain usable until their fixed policy boundary.

Do not roll back by reversing migrations or deleting anonymous users in bulk.
Authentication continues to land both guest and registered identities directly
in ordinary chat. Guest behavior differs through verified identity,
persistence, allowances, and conversion policy, not through onboarding.

### Paid waitlist rollback controls

The live `argus-api` plan is `standard`. The live `argus-app` plan is
`starter`. The requested-role migration and access-request exposure are
complete after the paid-plan readback and maintenance/private-health probes in
`docs/release-evidence/public-alpha-readiness.md`. Public account creation is
still allowlist-gated; `ARGUS_PUBLIC_ACCOUNT_ACCESS_ENABLED` remains `false`.
The evidence records the paid API instance type plus the maintenance and
private/SSH/local verification controls.

The paid controls must remain available for rollback. If any control becomes
unavailable, rollback below `061ba50e` remains forbidden until the maintenance,
quiescence, and private route-absence proof can be completed.

### Waitlist rollback floor

The durable waitlist rollback procedure is
`docs/release-evidence/public-alpha-readiness.md`. Commit `061ba50e` is the
fail-closed floor while the schema can contain active `requested` rows. Prefer
a forward fix. Before any authorized rollback below that commit:

1. read back `serviceDetails.maintenanceMode.enabled=true` out of band and
   require the exact maintenance status and page fingerprint on the onrender
   URL and every configured custom domain;
2. complete a same-SHA restart and prove Render's old-instance shutdown/drain
   finished with no pre-maintenance worker left;
3. only then take the `ACCESS EXCLUSIVE` lock, disable active requested rows,
   read back and assert zero, then commit;
4. deploy under maintenance and verify the exact rollback SHA from Render
   metadata;
5. require a private invalid-body route-absence probe to return HTTP `404`;
6. re-verify the maintenance configuration and response signature;
7. disable maintenance last, then require the public invalid-body readback to
   return HTTP `404` on every public API surface.

Generic error statuses are not maintenance proof. If control-plane state,
response fingerprint, restart drain, exact SHA, or a private verification
surface cannot be verified, rollback below the floor is forbidden; stop and
forward-fix. Never execute the production cleanup SQL during local repository
verification.

## Smoke Test

Use an allowlisted account and verify:

- Login succeeds.
- A new conversation can be created.
- Cold-start starter chips are visible, feel current, and do not reference 2024
  by default.
- Clicking a cold-start starter chip submits a natural-language prompt into the
  normal chat runtime.
- A Spanish prompt reaches confirmation without coaching or manual translation.
- The confirmation card shows exactly three card-scoped, structured actions:
  - `Run backtest` starts the supported job path.
  - `Change assumptions` is the single editing entry point. Single-field and
    compound edits preserve every explicit assumption the user did not change.
  - `Cancel` marks the draft canceled and removes the executable action.
- `Change dates` and `Change asset` do not render as separate actions.
- With `ARGUS_IN_PLACE_CARD_EDITS_ENABLED=false`, the capital and dates drawers
  do not render. Capital and date changes continue through the conversational
  `Change assumptions` path.
- A supported backtest completes and shows a result card.
- The result includes a readable Quick take.
- Explain result opens a deeper card-scoped explanation without replacing the
  Quick take.
- Retry preserves the failed setup and recovers through a structured action, not
  duplicated user text.
- Reloading the page preserves the conversation, job state, and result.
- Feedback can be submitted.

## Founder-Facing Tester Notes

Before sending the URL, make sure tester instructions say:

- Argus Alpha provides educational historical simulations only, not investment,
  tax, legal, brokerage, or execution advice.
- Alpha backtests are intentionally narrow: same-asset runs only, long-only,
  equal-weight multi-symbol logic, max 5 symbols, and daily bars.
- Market or benchmark data can be unavailable. If that happens, retry the same
  setup, change the dates, or choose a different supported asset/benchmark.
- Feedback buttons and the feedback dialog are the primary first-session
  listening channel. PostHog is limited to the approved server-side product
  events and must not receive raw prompts, credentials, balances, holdings,
  audio, route receipts, provider/model metadata, or frontend session data.
- Terms, Privacy Policy, and explicit alpha consent remain a founder-owned gate
  before inviting users outside the private circle.

## Supabase Persistence Check

Before the smoke test, capture current counts:

```sql
select
  (select count(*) from public.conversations) as conversations_total,
  (select count(*) from public.messages) as messages_total,
  (select count(*) from public.backtest_runs) as backtest_runs_total,
  (select count(*) from public.route_receipts where run_id is not null) as run_receipts_total,
  (select count(*) from public.feedback) as feedback_total;
```

After the smoke test, run the same query. A completed backtest should increase
`backtest_runs_total`, and the related route receipts should include a `run_id`.

## Data Cleanup Boundary

Do not delete Supabase profiles, conversations, messages, runs, or receipts as
part of the launch deploy. Cleanup should be a separate task with a dry-run count
and explicit deletion criteria.
