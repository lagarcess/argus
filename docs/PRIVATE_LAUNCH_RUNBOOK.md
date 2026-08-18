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

- App: `https://arguschat.ai`
- API: `https://api.arguschat.ai`, moved 2026-08-13 and live. It must stay on a
  subdomain of the app's registrable domain: the guest handoff cookie is
  `SameSite=Lax`, so on `onrender.com` it was third-party and every iOS browser
  dropped it, which broke guest conversion for every user until the move.
  `test_api_and_app_share_a_registrable_domain` pins the two hosts together.
  Changing the host requires an `argus-app` rebuild, because
  `NEXT_PUBLIC_ARGUS_API_URL` is baked into the web bundle at build time.

## Before Tester Sessions

The promotion target is `main`, but `codex/private-alpha-next` remains the
integration staging branch until the founder approves promotion. Do not merge
to `main` or open a release PR before that approval. Use the live Render deploy
mode the founder deliberately approved. Manual deployment remains valid until
the founder explicitly enables `checksPass` for all three services. Every
candidate still follows the gate below and needs a release manifest before
testers are invited; start from
`docs/release-manifests/TEMPLATE.md` and fill it with the exact candidate SHA,
API/web env fingerprint, workflow-service proof, canary evidence, rollback
target, autodeploy proof for all three services, and approver.

The candidate below must be the exact would-be `main` promotion commit: the
immutable commit produced from current `main` and the approved integration tree
that will actually land and deploy. A worker or integration head is not
sufficient when the landing method creates a different commit. If the landing
method cannot preserve a pre-gated SHA, keep all three live autodeploy triggers
manual through step 4 and gate the landed SHA before any deploy-capable action.

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
git status --short --untracked-files=no
git rev-parse HEAD
```

The status command must show no tracked changes, and the SHA must be the exact
candidate. The migration gate enforces both before it opens a database
connection.

2. Run the local predeploy smoke gate before any internet-facing canary:

```bash
.github/local-smoke.sh --expected-sha "$(git rev-parse HEAD)"
```

3. After selecting production as the target and recording the intended config
   and deploy mode without changing it, run the production migration gate
   before any operation that can deploy a service, including a Blueprint sync
   or a change to autodeploy configuration. Export the production direct or
   session-pooler URL from the operator secret store under the gate-only name
   below. The URL must not contain query parameters or a fragment because libpq
   can use them to override the validated host or user. Do not put it on the
   command line or rely on a dotenv file. Download the current production
   project's root CA from Supabase Database Settings and provide its absolute
   path. The gate forces `sslmode=verify-full`; it cannot fall back to a
   plaintext connection.

```bash
export ARGUS_PRODUCTION_DATABASE_URL="<production direct or session-pooler URL>"
export ARGUS_PRODUCTION_DATABASE_SSL_ROOT_CERT="<absolute path to production Supabase CA>"
ARGUS_CANDIDATE_SHA="$(git rev-parse HEAD)"
poetry run python scripts/ops/production_migration_gate.py \
  --candidate-sha "$ARGUS_CANDIDATE_SHA" \
  --output temp/release-evidence/production-migration-gate.json
```

The gate reads every migration from the exact candidate Git tree, verifies the
production Supabase project, opens a read-only database session, and compares
the full candidate list with the version, name, and parsed statement arrays in
`supabase_migrations.schema_migrations`. Read the candidate, applied, missing,
unexpected, name-drift, and content-drift lists in the JSON. Candidate and
applied records expose statement counts and statement-array SHA-256 digests.
`status=pass` is required before continuing. A missing migration is a stop even
when its safety classification is additive. An unreadable ledger, unexpected
production migration, duplicate version, name mismatch, missing statement
history, or statement content drift is also a stop.

The gate never applies migrations. If it reports a gap, stop the promotion. A
human reviews the exact pinned SQL and classification. The automated
classification is conservative: ambiguous top-level SQL becomes
`contract-replacing`, and the report does not replace inspection of the live
objects the migration will touch. Use these requirements:

- `additive` may be considered for live application after rollback review;
- `contract-replacing` needs an expand/contract compatibility plan or a
  maintenance window;
- `destructive` needs a maintenance window, backup/readback plan, and explicit
  founder approval.

Apply only approved files out of band, in repository order. Record the file
hash, ledger before and after, and affected-object readback in the release
manifest. Then rerun the same gate. Do not deploy until the rerun reports
`status=pass`, and attach its JSON as durable release evidence.

**Migrations that create functions the shipping code calls must be applied
before the deploy, not after.** A deploy that lands first runs new code against
a schema that lacks the objects it calls, and the failure surfaces as production
behavior rather than a gate result. The first promotion carrying PR #476 is the
live case: `.github/canary-render.sh` and the ops approve route call five
functions created by
`20260816150000_scope_access_welcome_enforcement.sql` and its two predecessors,
including `delete_private_alpha_access_welcome_artifacts`, which is how the
daily canary tears down the allowlist and delivery rows it creates. Deploy
before applying and the canary creates rows it cannot delete, on every run,
in production.

State the intended order explicitly in the manifest for any promotion carrying
a migration, so the operator cannot get it backwards from the checklist alone.

4. Land or read back the candidate on `main` without rewriting the gated
   commit. Keep the checkout on the gated candidate and rerun the same
   executable gate in landed-ref mode:

```bash
poetry run python scripts/ops/production_migration_gate.py \
  --candidate-sha "$ARGUS_CANDIDATE_SHA" \
  --verify-landed-ref origin/main \
  --output temp/release-evidence/production-migration-gate.json
```

The option fetches `origin/main` inside the gate and blocks before database
access if the fetch, ref resolution, or exact-SHA comparison fails. It then
repeats schema parity and records the landing proof in the final JSON. Do not
continue on any nonzero result. A squash, rebase, conflict edit, new merge
commit, or concurrent `main` update invalidates the earlier report. Keep all
three live triggers manual, check out the exact landed commit, rerun steps 1 and
2, then rerun the gate against the landed SHA as described in step 3 and replace
the manifest evidence. When `checksPass` is already live, use only a landing
method that preserves the pre-gated commit SHA; otherwise code can deploy before
the landed tree is verified.

> [!WARNING]
> **A Blueprint sync enables autodeploy after #470.** The repository declares
> `autoDeployTrigger: checksPass`, but live Render was returned to manual
> (`off`) for `argus-api`, `argus-app`, and `argus-backtests` on 2026-08-12
> while the active promotion completes. After #470 is promoted, a Blueprint
> sync directly turns `checksPass` on for the API and app even if the operator
> intended only to reconcile unrelated configuration. The companion Workflow
> API sync reads the same target from the release profile and turns it on for
> `argus-backtests`. The normal three-service configuration sync can therefore
> enable autodeploy for all three as a side effect of syncing configuration,
> not as the result of a fresh deployment decision. Before step 5, obtain an
> explicit founder decision to enable autodeploy. Without that decision, keep
> all three live triggers manual and deploy all three services explicitly.

5. In Render, sync the Blueprint from `render.yaml` only when `argus-api` or
   `argus-app` config drift needs reconciliation. Render Blueprints cannot
   declare the `argus-backtests` Workflow service. Its release contract is held
   in four separate places that must agree:

   - the release profile declares the Workflow runtime and deploy target;
   - `.github/render-env-sync.sh workflow-runtime` applies that target through
     the Render Workflow API;
   - `release-config-audit` reads the live Workflow configuration back;
   - steps 10 and 11 deploy `argus-backtests` and prove its ready version matches
     the same candidate as the API and app.

   If any one of these four controls drifts, `argus-backtests` can stay stale
   even while the API and app advance, which is the failure caught on
   2026-08-11.
6. Confirm Render is updating the existing `argus-app` and `argus-api` services.
   Stop if Render proposes duplicate services.
7. Confirm the live deploy mode matches the deliberate founder decision and is
   uniform across `argus-api`, `argus-app`, and the Git-linked
   `argus-backtests` Workflow: either all three are manual (`off`) or all three
   use `checksPass`. Never enable autodeploy for only a subset of the three.
   The repository target is not proof that live enablement was approved.
8. Export local ops and canary secrets, or keep these in the root `.env` file
   and let the scripts load them:

```bash
export ARGUS_OPS_TOKEN="..."
export ARGUS_CANARY_EMAIL="..."
export ARGUS_CANARY_SUPABASE_URL="https://lgdhvepyrzbnscqssgqq.supabase.co"
export ARGUS_CANARY_SUPABASE_SERVICE_ROLE_KEY="..."
```

For local founder/operator runs, `.github/canary-render.sh` also accepts
`MOCK_USER_EMAIL`, `SUPABASE_URL`, and `SUPABASE_SERVICE_ROLE_KEY` from the root
`.env`. The `ARGUS_CANARY_*` names remain the preferred GitHub Actions names.

9. Confirm the API is in real-workflow private-alpha validation mode. This mode
   keeps the API lean and sends `Run backtest` through the durable Render
   Workflow job path:

```bash
.github/render-env-sync.sh api-real-workflow-on
```

Restart `argus-api` after changing Render env values.

10. Deploy **all three live services** from the candidate commit:
   `argus-api`, then `argus-app`, then **`argus-backtests`**.

   When all three live triggers use `checksPass`, a commit on the configured
   deployment branch deploys after its checks pass. In manual mode, explicitly
   deploy the candidate using the same three-service order.

   **`argus-backtests` is the easiest one to forget and the one that breaks the
   canary.** It is the Render Workflow service that actually runs backtests, it
   is not declared in `render.yaml`, and it was missing from this step until
   2026-08-11. On that promotion the API and web shipped while the workflow
   service stayed a week behind, and the canary stopped at
   `workflow_commit_mismatch` before spending money on a paid journey. Deploy it
   every time, and never let a promotion finish with the three on different
   commits.

11. Confirm the live `argus-api`, `argus-app`, and `argus-backtests` deploy
   commits match the candidate commit you intend to test and that their latest
   versions are ready:

```bash
ARGUS_RELEASE_SHA="$(git rev-parse HEAD)"
.github/render-env-sync.sh api-deploy-status
.github/render-env-sync.sh web-deploy-status
.github/render-env-sync.sh workflow-version-status
```

If any of the three deployed commits is not `ARGUS_RELEASE_SHA`, stop and deploy
that stale service before running the strict canaries. The canary script
enforces the same deployed SHA/status check with `ARGUS_CANARY_SHA`, and its
resolver compares all three, which is what caught the workflow service running
behind on 2026-08-11.

For `argus-backtests`, Render exposes the deployed Git commit as the ready
Workflow version name, currently a seven-character SHA prefix. The status and
canary resolvers require that prefix to match the exact API/web commit. They do
not trust mutable workflow env markers, so checks-passing and manual releases
use the same version-owned proof.

12. Run the product warmup script and verify the API stayed in real workflow
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

13. Run both authoritative canary surfaces with privacy-safe evidence. They are
separate fail-red jobs, so one cannot hide or relabel a failure in the other.

- **Release coherence** checks the exact deployed SHA across API, app, and
  `argus-backtests`; runs the release-config audit, warmup, and live-provider
  workflow proof; and keeps the direct API signup-denial probe plus the
  access-approval welcome-email proof.
- **Authenticated browser journey** starts from a private Playwright storage
  state, loads the Spanish chat directly, completes one real backtest, records
  the decision, reloads the result, and reopens it through Omnisearch. It never
  visits the signup or login page. It rechecks three-service deployed-SHA
  coherence immediately before minting the session and after the canonical
  postconditions, so a rollout during the journey cannot inherit the earlier
  release label.

The disabled-email denial check belongs only to release coherence. The runner
creates a `user` allowlist row with `disabled_at` set, then
`.github/canary-requested-signup-denial.py` sends that address to the
ops-authenticated route owned by `REQUESTED_SIGNUP_DENIAL_PATH` in
`src/argus/api/ops_contract.py` and requires `200 {"denied": true}`. This proves
the disabled row is blocked with public access on and with the allowlist-only
emergency rollback. The probe never calls the signup provider or CAPTCHA, so it
cannot create an auth identity. `verify_no_signup_auth_identity` asserts that
none exists before the canary stages the same row as an active `requested` row
and calls the protected access-approval operation. That operation sends the real
localized welcome, records the provider-accepted delivery, and promotes the row
to `user` atomically; the canary then reads the delivery row back and requires
a provider receipt stamped inside this run, so a stopped-sending regression
cannot score green. A unique generated address scoped to the run identity
forces every canary attempt through the first-send path instead of delivery
replay. The exit trap deletes any resulting auth identity and allowlist row,
removes the run's claim and delivery rows through the service-reachable
`delete_private_alpha_access_welcome_artifacts` cleanup, then reads back that
no matching auth identity remains. If an approval fails after its claim is
written, the claim blocks that address's SMTP for 24 hours and the daily
maintenance pass releases it after 48; an operator can release immediately with
`release_expired_private_alpha_access_welcome_claims()`. Do not move this probe
into Playwright, enable its temporary identity for browser use, or weaken
Turnstile anywhere deployed.

For a local release-coherence run, generate a fresh non-secret nonce for every
attempt. Local mode is available only when both GitHub run identity variables
are absent. Do not combine the local nonce with GitHub identity variables or
override the generated signup email.

```bash
mkdir -p temp/release-evidence
ARGUS_CANARY_SURFACE=release-coherence \
ARGUS_CANARY_LOCAL_RUN_NONCE="$(poetry run python -c 'import secrets; print(secrets.token_hex(12))')" \
ARGUS_CANARY_SHA="$(git rev-parse HEAD)" \
ARGUS_CANARY_HARNESS_SHA="$(git rev-parse HEAD)" \
ARGUS_CANARY_EVIDENCE_PATH=temp/release-evidence/release-coherence.json \
ARGUS_CANARY_CAPTURE_PATH=temp/release-evidence/release-coherence-capture.json \
.github/canary-render.sh
```

For a local authenticated-browser run, install the pinned browser dependencies
first and use the dedicated canary identity described below:

```bash
cd web && bun install --frozen-lockfile && bunx playwright install chromium
cd ..
ARGUS_CANARY_SURFACE=authenticated-browser-journey \
ARGUS_CANARY_SHA="$(git rev-parse HEAD)" \
ARGUS_CANARY_HARNESS_SHA="$(git rev-parse HEAD)" \
ARGUS_CANARY_EVIDENCE_PATH=temp/release-evidence/authenticated-browser.json \
ARGUS_CANARY_CAPTURE_PATH=temp/release-evidence/authenticated-browser-capture.json \
.github/canary-render.sh
```

### Canary identity, session rotation, and revocation

`ARGUS_CANARY_EMAIL` must identify a dedicated Supabase Auth user. It must never
be an admin, developer, employee account, or real user. Its enabled
`private_alpha_allowlist` row must have exactly `role=user`, and its Auth user
app metadata must contain `source=private-alpha-canary`. Its exact `profiles`
row must also have `is_admin=false`; changing an allowlist role does not prove
that a previously elevated profile lost its privilege. App metadata is
operator-owned; do not use user-editable metadata for this marker. The canary
fails closed if any of those facts are not true.

Provisioning is a one-time manual action for identity rotation. Generate a new
address matching
`private-alpha-canary+<32-lowercase-hex>@get-argus.com`, write it directly to
the GitHub `ARGUS_CANARY_EMAIL` secret without echoing it, and dispatch the
candidate branch with `canary_identity_action=provision`. That action is never
available to the schedule. It accepts only the canary-specific address shape,
refuses to relabel an existing unknown user, creates a confirmed non-anonymous
Auth user with app metadata `source=private-alpha-canary`, records Spanish in
Auth user metadata, and creates the enabled `role=user` allowlist row. For a new
identity, it then mints a one-time session and calls Argus's authenticated
`GET /api/v1/me` endpoint so the normal backend profile owner creates the
profile. The setup session is revoked before the action requires the exact
profile row to have `is_admin=false`. It prints no email, user id, token, or
service-role value. Later manual and scheduled runs use the default
`canary_identity_action=validate` and fail closed on drift.

After the new identity completes a normal browser canary, revoke the prior
identity using the emergency sequence below. Do not leave two active canary
identities as an informal fallback.

No long-lived browser state or password is stored in GitHub. On every browser
run, the service-role step generates and verifies a one-time magic link for the
dedicated identity, serializes the resulting least-privilege session to a mode
`0600` Playwright storage-state file, and passes only that file and the expected
user id into the browser process. The browser process explicitly has the
service-role variables removed. This is the routine rotation: every run gets a
fresh session.

The browser surface revokes that session with local scope before it records
success. The exit trap retries revocation on every earlier failure path, then
deletes both the storage-state file and its private token handoff. Argus also
checks the Supabase session id on authenticated API requests, so a removed
session stops being an active Argus session. A revocation failure is an
`Authenticated browser journey` failure, never a passed artifact with a red
process exit.

For emergency revocation:

1. Disable the canary allowlist row.
2. In Supabase Auth, revoke every session for the dedicated user and confirm no
   `auth.sessions` row remains for its user id.
3. Delete the dedicated Auth user only after session revocation is confirmed.
4. Remove or replace `ARGUS_CANARY_EMAIL` in GitHub Actions.
5. Provision a new dedicated `role=user` identity with
   Auth app metadata `source=private-alpha-canary`, update the GitHub value, and
   run a manual canary before restoring the schedule.

Do not use deletion alone as immediate revocation. A previously issued access
token can remain cryptographically valid until expiry even after its Auth user
is deleted.

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

Read the job name, failure stage, and reason before treating a canary red as a
product regression. `Release coherence` owns deployment, config, warmup,
provider, and API signup-denial failures. `Authenticated browser journey` owns
session creation, the rendered Golden Path, the real backtest, and browser/API
postconditions. A browser job must never report a Turnstile challenge timeout,
because it does not cross an auth form.

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
workflow version status, local smoke, warmup, both canary surfaces, and the
release manifest all pass against the intended candidate commit.
If any service reports a different commit, deploy the candidate branch before
continuing. If
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
short-lived workflow tasks. The two jobs report independently. Release
coherence owns warmup and the provider/config proof. The real backtest in the
browser journey runs on `argus-backtests`, while
`release-config-audit --expect-mode real-workflow` proves the workflow env itself
is using `live_provider`. Warmup then runs the deployed `workflow_proof` task and requires
`workflow_runtime_provider_mode=live_provider` and
`workflow_runtime_proof=ready`, proving effective workflow runtime rather than
only saved Render env vars. The jobs upload
`private-alpha-release-coherence-evidence` and
`private-alpha-authenticated-browser-evidence`, each with its own exit file.
Their failure captures are separate. The browser job can also upload
`private-alpha-authenticated-browser-context` after its redaction sentinel is
present.

The canary script masks the email, any legacy password present in an operator
environment, the session access and refresh tokens, serialized auth-cookie
values, and the artifact probe value before it creates
`web/temp/playwright-results/.redacted`. The workflow keeps the sentinel gate:
if redaction did not run or failed, it logs
`browser_context_upload=skipped_unredacted` and does not upload browser context.
The storage state and private handoff are temporary files outside the artifact
paths and are deleted on exit.

To prove this control, manually dispatch from the candidate branch twice. Use
`browser_artifact_probe=redacted` first. The browser job must fail deliberately,
the probe value must be masked in its context, and the sentinel-gated context
upload must occur. Then use `browser_artifact_probe=unredacted`. Redaction fails
deliberately, no sentinel is written, and the context upload must be skipped.
Both are expected red proof runs. Never use a real credential as the probe.

Trigger choice controls which harness is exercised:

- A schedule checks out `main`, resolves the coherent production SHA, and
  detaches to that deployed commit. The harness SHA and deployed SHA must match.
- A `workflow_dispatch` keeps the selected branch checked out while the resolver
  records the exact coherent production SHA separately. Only dispatch may run a
  branch harness against a different deployed target, and both SHAs are written
  to the evidence.

This means a branch dispatch can prove a canary-harness fix before promotion,
while still testing the exact production deployment. Merging the fix only into
`codex/private-alpha-next` does not change scheduled runs. The scheduled canary
uses the fix only after the production promotion reaches `main`; a still-red
schedule before that promotion is the old deployed harness, not evidence that
the branch fix failed.

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

The stale job scan is an operator-run step. It is not a deployed release
surface, and nothing runs it automatically.

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
Supabase Authentication URL Configuration must set Site URL to
`https://arguschat.ai` and allow the exact recovery redirects
`https://arguschat.ai/auth/recovery` and
`https://argus-app-suz5.onrender.com/auth/recovery`; keep the Render origin
during the transition, because an unlisted redirect silently falls back to Site
URL instead of returning an error.

### Requested Access Promotion

Promote an active `requested` row only through the ops route owned by
`ACCESS_REQUEST_APPROVE_PATH` in `src/argus/api/ops_contract.py`,
`POST /internal/access-requests/approve`. Never PATCH
`private_alpha_allowlist.role` to `user` directly. The protected operation sends
the localized access welcome, records the provider-accepted delivery, and then
activates access through the database completion boundary. This is the only
human promotion command:

```bash
(
set -euo pipefail
source .github/argus-env.sh
argus_load_root_env >/dev/null || true
REQUESTED_EMAIL="<requested email>"
OPS_CURL_CONFIG="$(mktemp)"
APPROVAL_REQUEST="$(mktemp)"
APPROVAL_RESPONSE="$(mktemp)"
trap 'rm -f "$OPS_CURL_CONFIG" "$APPROVAL_REQUEST" "$APPROVAL_RESPONSE"' EXIT
chmod 600 "$OPS_CURL_CONFIG" "$APPROVAL_REQUEST" "$APPROVAL_RESPONSE"
printf 'header = "Authorization: Bearer %s"\n' "$ARGUS_OPS_TOKEN" > "$OPS_CURL_CONFIG"
REQUESTED_EMAIL="$REQUESTED_EMAIL" python3 - "$APPROVAL_REQUEST" <<'PY'
import json
import os
import pathlib
import sys

email = os.environ["REQUESTED_EMAIL"].strip().casefold()
pathlib.Path(sys.argv[1]).write_text(
    json.dumps({"email": email}, separators=(",", ":")),
    encoding="utf-8",
)
PY
APPROVE_PATH="$(python3 -c 'import sys; sys.path.insert(0, "src"); from argus.api.ops_contract import ACCESS_REQUEST_APPROVE_PATH; print(ACCESS_REQUEST_APPROVE_PATH)')"
curl -q --fail --silent --show-error \
  --config "$OPS_CURL_CONFIG" \
  -X POST \
  -H "Content-Type: application/json" \
  --data-binary "@$APPROVAL_REQUEST" \
  "${ARGUS_PRIVATE_LAUNCH_API_URL}${APPROVE_PATH}" \
  > "$APPROVAL_RESPONSE"
python3 - "$APPROVAL_RESPONSE" <<'PY'
import json
import pathlib
import sys

try:
    payload = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError) as exc:
    raise SystemExit("access request promotion returned an invalid response") from exc
if (
    not isinstance(payload, dict)
    or set(payload) != {"approved"}
    or payload["approved"] is not True
):
    raise SystemExit("access request promotion was not approved")
PY
)
```

Success is exactly `{"approved":true}`. Missing or invalid ops authorization
remains route-indistinguishable `404`. Missing configuration, ineligible state,
email-provider failure, delivery persistence failure, and completion failure
remain generic errors. Do not expose provider detail or infer approval from an
error response.

Support may read only the private
`private_alpha_access_welcome_deliveries` record through existing privileged
operational access. Its support-readable fields are `recipient_email`,
`language`, `content_version`, `subject`, `provider_receipt`, `sent_at`, and
`created_at`. Browser roles have no access to this table. The record is delivery
evidence; the guarded completion operation remains access truth.

**Consent scope: transactional only.** The requested access grant does not
authorize product updates, tips, re-engagement, follow-up mail, broadcasts,
campaigns, onboarding sequences, or any other marketing email.

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

## Operator-Run Maintenance

Maintenance is not a Render service and is not part of the deployed release
topology. An operator runs the retained entry point from a laptop against an
explicit target:

```bash
poetry run python scripts/ops/scheduled_maintenance.py
```

That pass runs guest workspace retention first, then stale and stranded
backtest job reconciliation. Every job runs even when an earlier one fails, so
one failure never hides another. The retention windows in `DATA_MODEL.md` hold
only as often as an operator runs this command.

The pass exits nonzero if any job fails, and prints a final JSON summary line
with `status`, `failed_count`, and `failed_jobs`. Alert on a nonzero exit or on
`"status": "degraded"`. Keep the per-job output: guest cleanup prints its
`selected`/`auth_deleted`/`auth_delete_failed`/`purge_failed` counts, and the
reconciler prints its scan report.

Provide `DATABASE_URL`, `SUPABASE_URL` or `SUPABASE_PROJECT_URL`,
`SUPABASE_SERVICE_ROLE_KEY`, and `RENDER_API_KEY` only in the operator process.
Do not copy production deletion credentials into CI. Record the command target,
timestamp, final summary line, and selected or purged counts in operator
evidence.

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

### Live eval is a comparison, not a scoreboard

**Founder-locked 2026-08-13.** A red live eval does not by itself block a
promotion. The question a promotion asks is *"is this worse than what users
have right now"*, and a suite scored against frozen expectations cannot answer
it. Expectations drift as decisions land, so a failing check may be a
regression, a superseded expectation, or model variance, and the three are
indistinguishable from one run.

So a red candidate run requires a **baseline run at the deployed production
SHA**, with identical provider modes, and the two are compared:

- **Candidate fails only what production already fails** → not a regression.
  Promote, and record every failure with its owner in the manifest.
- **Candidate fails anything production passes** → that is a regression.
  Do not promote.
- **Candidate passes what production fails** → an improvement, record it.

Run the baseline from a detached worktree at `origin/main` so the candidate
tree is untouched, and commit both scorecards as durable evidence.

Why this rule exists: on 2026-08-13 a candidate carrying five user-visible
fixes was held by twelve failures that all turned out to live in code already
deployed. The gate was measuring the wrong thing. Twelve failures nobody had
reported were outranking five defects real users had hit.

The corollary is the more important half: **run the eval before merging**
anything that touches the interpreter or the edit spine, not only before
promoting. PR #431 shipped compound editing on 2026-08-11 without one. The
suite already contained the cases that would have caught it, and had scored
them 14/14 eight days earlier. That is [#498](https://github.com/lagarcess/argus/issues/498).

### What the run costs, measured

One full 60-case suite is **$1.33** and **29 minutes** (2026-08-14, `eaf5d52b`).
Confirmation-edit cases are the expensive ones at ~$0.05 each against a $0.022
mean, because they burn the tier-3 interpreter across multiple turns.

That price is low enough to gate on the full suite directly rather than
maintain a cheaper subset, so there are no coverage gaps to reason about.

**Two runs of the same commit produced identical failure sets**, 17 of 60, with
no case differing in either direction. Treat a single flipped case as signal
and re-run to confirm rather than assuming variance.

### Model-facing text is frozen against a scorecard

`tests/test_interpreter_prompt_freeze.py` fingerprints every piece of text the
interpretation model reads: prompt builders and Pydantic
`Field(description=...)` across the eval-reachable tree. It costs nothing and
runs in about a second, so it is the cheap layer that decides when the paid one
has to run.

Changing that text requires a live eval on the branch, its scorecard committed
under `docs/reports/evidence/`, a case-by-case comparison against the scorecard
named in `.agent/interpreter_prompt_fingerprint.json`, and a regenerated
fingerprint. Because the fingerprint is a single file recording one measured
state, **only one lane may hold this surface at a time**; two concurrent prompt
lanes conflict on it and neither measures the combined result.

Why this exists: PR #491 rewrote the shared prompt for a DCA change on
2026-08-14. Its own tests passed, CI went 6/6 green, and it regressed asset
extraction, start-date preservation, and discovery routing in three unrelated
places. No unit test sends a message through a model, so nothing but the paid
eval could have caught it, and that ran after the merge.

## Guest Staged Rollout

The operational security checklist for later internet-facing Guest exposure is
[Guest Public Launch Safety](GUEST_PUBLIC_LAUNCH_SAFETY.md). It is a promotion
and traffic-exposure gate, not a prerequisite for merging the Guest
implementation into the internal integration branch.

Product defaults:

```bash
ARGUS_GUEST_ACCESS_ENABLED=true
ARGUS_PUBLIC_ACCOUNT_ACCESS_ENABLED=true
NEXT_PUBLIC_GUEST_ACCESS_ENABLED=true
ARGUS_VISITOR_KEY_SECRET=<unique high-entropy environment secret>
ARGUS_DISCOVERY_GLOBAL_DAILY_CEILING=500
```

Guest access is part of the normal product shape. The two Guest flags are
default-on emergency kill switches; explicit `false` activates rollback. The
frontend flag controls presentation only and the API remains authoritative.
Public-account access is open as of 2026-08-12: permanent signup and login
admit any email without an explicitly disabled allowlist row, the guest surface
offers account creation, and existing admin/developer behavior is unchanged
because opening the gate grants no role. That third flag is the one that fails
closed when unset, so it must be set explicitly on every service that reads it;
omitting it denies registration rather than opening it.

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

Guest cleanup is an operator-run step, and nothing runs this deletion
automatically. The at-least-daily floor is an operator's responsibility, and the
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

Conversion safety is non-negotiable: new accounts use ordinary signup to create
a different permanent Auth identity, then claim the complete guest graph
through the workspace-lifetime, email-hash-bound handoff. Existing accounts use
the short-lived handoff that login claims before returning a permanent session.
Guest usage never merges into registered hour/day counters. Cleanup
re-verifies anonymous source truth and must not delete a permanent account or
the transferred graph.

Guest funnel capture uses the shared metadata-only server envelope. Only the two
typed browser-owned facts cross `POST /api/v1/analytics/guest-events`; PostHog
keys, autocapture, session replay, prompts, assistant prose, exact
capital/dates, email, Auth material, private titles/previews, provider/model
names, and raw transcripts stay out.

Rollback order:

1. set `NEXT_PUBLIC_GUEST_ACCESS_ENABLED=false`;
2. set `ARGUS_GUEST_ACCESS_ENABLED=false`;
3. leave `ARGUS_PUBLIC_ACCOUNT_ACCESS_ENABLED=true` untouched, because rolling
   guest access back does not close public registration;
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
open: the founder set `ARGUS_PUBLIC_ACCOUNT_ACCESS_ENABLED=true` live on
2026-08-12, recorded in
`docs/release-manifests/2026-08-12-main-production-promotion-716221f.md`, so
anyone may register and the allowlist blocks only explicitly disabled rows.
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
