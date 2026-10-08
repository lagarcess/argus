# Cuadrao marketing launch runbook

Owns the release path for the independent `marketing/` package: promotion, the Render service, email DNS, domain cutover, verification and rollback. Parent issue [#880](https://github.com/lagarcess/argus/issues/880); children #887 to #892. The package, its forms and its data are documented in [marketing/README.md](../../marketing/README.md) and the [forms contract](../specs/cuadrao-marketing-forms-contract.md).

Nothing in this document is an approval. Each gated action below needs the founder's explicit yes in chat, with the exact candidate named.

## 1. Promotion path

Measured 2026-10-07 with `git fetch origin`:

| Ref | SHA |
| --- | --- |
| `origin/main` | `a9286b21886eb03df7a21f2f4b7d5e79af570679` |
| `origin/codex/private-alpha-next` (lane base) | `93571e593e1677561e1dd38f63b6475574942e2d` |

`main` is 144 commits behind integration, 8 ahead, with 3,188 changed files and 35 migrations production has not applied (financial accounts, households, Apple sign-in, account deletion, grants). Promoting integration to `main` to ship a website would release all of it, including those migrations, and would collide with the native lane.

**Option A, full promotion.** Rejected for this launch: it ships the whole integration backlog and 35 unapplied migrations.

**Option B, bounded promotion (recommended).** Land the marketing PR into `codex/private-alpha-next` under the normal rules, then open a second PR into `main` from a branch cut from `origin/main` that contains only the marketing change. Prepared and measured against `origin/main` (`a9286b21`) from this PR's content: **every file is new except two modified ones, and nothing is deleted.** The exact list and counts come from `git diff --name-status origin/main...<candidate>` on the candidate branch, regenerated on each refresh, so this page does not carry a number that goes stale.

- `marketing/**` (new)
- `supabase/migrations/20260920000000_cuadrao_early_access_signups.sql` and `tests/test_cuadrao_early_access_postgres.py` (new)
- `docs/specs/cuadrao-marketing-forms-contract.md`, this runbook, the launch record and its evidence folder (new)
- `.github/workflows/ci.yml` and `tests/test_ci_workflow.py` (the two modified files): a `marketing-checks` job and its entry in the aggregate `ci` job's `needs`, written for `main`'s simpler workflow, and the matching expectations in the workflow test, which asserts that exact `needs` list on `main`

It carries no change to `web/`, `src/`, `ios/`, `render.yaml` or any other migration. Left out because they only exist, or only make sense, on integration: the Cuadrao design guide (it links five integration-only documents), the documentation-authority row and the integration-report pointer. They arrive with the normal promotion, and the package README's link to the design guide is dead on `main` until then. The migration is dated between `main`'s latest (`20260914120000`) and integration's first newer one (`20260925120000`), so a fresh replay orders it correctly on both branches. Identical content merges cleanly when integration is later promoted. The candidate was built in a separate worktree from `origin/main`; its typecheck and 112 unit tests pass there.

### Production ledger and the signup migration

Production's newest migration (`20260914120000`) equals `main`'s newest file, but the ledgers do not match (read-only, 2026-10-07; 81 entries). 69 versions match by version and name. Production carries seven April entries `main` lacks, five entries recorded at different versions from the repo files, and lacks the ledger rows of five `main` migrations whose tables already exist. The Supabase GitHub integration's production branch record has read `MIGRATIONS_FAILED` since 2026-06-04. A `supabase db push` would try to replay migrations production already has, so it is never used.

The consumer lane's reviewed applier (PR #894) plans one ordered production batch: an unrecorded `20260505000001_add_currency_pair_asset_class`, then this lane's `20260920000000`, then the consumer's 35 files `20260925120000` to `20261005230000`. The applier refuses a skipped version, so this migration must be applied before theirs, not after. This lane does not apply it alone. The founder holds the only production DSN and runs the read-only gate (`scripts/ops/production_migration_gate.py`) and the applier; the gate report and backup precede the apply.

Option B departs from the usual "main is promoted from integration" practice. It needs the founder's approval as a workflow exception before the second PR is opened. The exact file list is regenerated from `git diff --name-status origin/main...<candidate>` and posted with the request.

### Can the signup migration ship independently of the consumer's 35?

Yes at the schema level, with one ordering rule and one shared-tool gap. Checked 2026-10-07.

- **No schema dependency.** The migration touches only `public.cuadrao_early_access_signups` and the roles `anon`, `authenticated`, `service_role`. It uses `sha256`, `convert_to` and `encode`, all built into Postgres 11 and later. It does not reference `auth.users`, any other table, function or extension, and none of the 35 consumer migrations references it. Its grants are stated explicitly, so it does not rely on the default-privilege change in the consumer's `20261005090000_explicit_client_grants.sql`.
- **Proof.** A throwaway Postgres 17 with the three roles, and CI on the full integration chain (35 newer migrations present). The bounded candidate branch also runs CI on `main`'s chain plus this migration only, which is the independent case.
- **Ordering rule (not a dependency).** The reviewed applier (PR #894) records versions as a strict prefix above the ledger head and refuses a skipped version. `20260920000000` is the next version above production's head (`20260914120000`), so it can be applied alone as the first prefix, in its own batch. Once any consumer file with a higher version is applied, `20260920000000` can no longer be applied, so it must go before them, not after.
- **Shared-tool gap.** The applier refuses hosted Supabase hosts today ("a hosted target needs its own reviewed change that adds the named project ref and the founder's approval record"). That gap blocks every production apply, this one included, and is owned by the consumer lane's tool, not by this migration.
- **No dependency on the unrecorded currency-pair migration.** The consumer plans to run `20260505000001` first, unrecorded, because production's asset-class checks lack currency pairs. That is a separate repair of production's history; this migration does not read `asset_class`.

The practical consequence: the signup table can go to production alone and early, or with the batch, as the founder prefers, provided it precedes the consumer files.

### Before any promotion

1. Automatic Supabase preview branching is off and the PR 895 branch is removed (launch record, "Disable automatic previews"). On 2026-10-07 it was on.
2. Automatic production migrations from `main` are off. The evidence says they are not wired (launch record); confirm the integration's deploy-to-production setting in the dashboard once.
3. Supabase stays on the Free plan; nothing here depends on a plan change.
4. CI is terminal and green on the exact candidate, and the signup migration is not applied by promotion: the consumer's applier is the only production path.

## 2. Render service

Create only after the candidate is on `main`, Section 4 is complete and the founder has approved cost and creation. Creating the service starts its first deploy.

| Setting | Value |
| --- | --- |
| Name | `cuadrao-marketing` |
| Type / runtime | Web Service, Node |
| Repository / branch | `https://github.com/lagarcess/argus`, `main` |
| Root directory | `marketing` |
| Region | Virginia |
| Instance type | Starter, 1 instance (about $7 per month; re-check at purchase) |
| Persistent disk | none |
| Build command | `npm install -g bun@1.3.14 && bun install --frozen-lockfile && bun run build` |
| Start command | `npm run start -- -p $PORT` (Node only; Bun is needed for install and build, not to serve) |
| Health check path | `/api/health` (needs no provider) |
| Auto-Deploy | **Off** |
| Environment group | none |
| Custom domains | none until Section 7 |

Bun 1.3.14 is the version CI pins. Node is pinned by `NODE_VERSION` below rather than left to the default.

### Environment

Set at creation. One owner each; nothing is inherited from an Argus group.

| Key | Value | Secret | Owner |
| --- | --- | --- | --- |
| `NODE_VERSION` | `24.21.0` | no | this runbook |
| `NEXT_TELEMETRY_DISABLED` | `1` | no | this runbook |
| `RESEND_API_KEY` | key restricted to sending from `notify.cuadrao.ai` | yes | Resend |
| `CUADRAO_INQUIRY_FROM` | `Cuadrao <website@notify.cuadrao.ai>` | no | #889 |
| `CUADRAO_INQUIRY_TO` | the mailbox the founder chooses for inquiries; set only after that mailbox is confirmed to receive mail | no | the founder |
| `SUPABASE_URL` | existing project URL | no | Supabase |
| `SUPABASE_SERVICE_ROLE_KEY` | service-role key of the existing project | yes | Supabase |
| `CUADRAO_SITE_INDEXING` | unset on the `onrender.com` address; `public` only at cutover | no | #891 |

Secrets are typed by the founder into Render; they are never pasted into chat, commits, logs or evidence. After creation, readback lists key names and non-secret values only. PostHog and any other analytics stay unset.

## 3. Optional later: After CI Checks Pass

Not part of this launch. If chosen later, switch Auto-Deploy to "After CI Checks Pass" and add build filters so only marketing changes deploy: included paths `marketing/**`, ignored paths none. That needs a separate decision.

## 4. Preconditions before creation

1. Candidate merged to `main` through the approved path; exact SHA and CI recorded.
2. The signup migration is applied as part of the consumer lane's ordered batch (above) by the founder with the reviewed applier, after a recorded gate report and backup, and `public.cuadrao_early_access_signups` reads back with RLS on, no `anon`, `authenticated` or `service_role` delete, and a ledger row. A repository migration file is not production proof.
2a. Supabase stays on the Free plan; no plan change is a precondition. Known limit: a Free project pauses when it is inactive, and while it is paused the Personal form answers its truthful unavailable state (503) and keeps the visitor's email. The operator restores the project from the Supabase dashboard. A restore is the only recovery, so check the project's state as part of hosted acceptance and before any announcement. The Business inquiry does not use Supabase.
3. `notify.cuadrao.ai` verified in Resend (Section 6), the founder has chosen the inquiry mailbox and set `CUADRAO_INQUIRY_TO`, and one approved test message is received at that mailbox.
4. The founder has typed the three provider values into the Render form, and the complete form has been read back to them before Create.
5. Rollback target named (Section 8). The first deploy has no earlier artifact, so a rollback cannot be exercised until a second deploy exists.

## 5. Hosted acceptance on the Render address

On `https://cuadrao-marketing.onrender.com` (or the address Render assigns), with indexing off:

- `/api/health` returns 200; deployed commit equals the approved SHA.
- The per-client limit keys on the visitor, not on a shared proxy address: from one network, a request that sends a spoofed leftmost `X-Forwarded-For` is limited exactly like one that does not, and two networks are limited independently. If every visitor shares one key, set `CUADRAO_TRUSTED_CLIENT_IP_HEADER`.
- Mixed-case URLs (`/EN`, `/en/Personal`) redirect to lowercase and leave `/en` at 200 after a restart.
- Every page loads in Spanish and English at 390 and 1440 pixels; titles, canonical, hreflang, icons and share images as in the browser specs; `X-Robots-Tag: noindex, nofollow` and a disallow-all `robots.txt`.
- Real inquiry from the form arrives at the configured `CUADRAO_INQUIRY_TO` mailbox with the visitor as Reply-To, using a founder-approved test address.
- Real signup is stored; repeating it creates no second row and looks identical; the restart persistence check redeploys with the manual deploy button and re-reads the row; operator removal erases the address and the same address then registers with an identical visitor-facing answer but no new active row.
- Provider-down and timeout recovery shown by disabling the Resend key in a throwaway state only if the founder approves; otherwise the recorded browser specs stand for recovery.
- Evidence is committed under `docs/reports/evidence/cuadrao-marketing-launch/` with raw addresses redacted.

## 6. Email (#889)

Read, then prepare, then apply only after approval. Do not change root MX, SPF or DKIM for `cuadrao.ai`, and never add a second SPF record.

1. Read Cloudflare DNS and Email Routing for `cuadrao.ai` and Resend's domain list. Save a sanitized before-state. On 2026-10-07 public DNS showed no apex records and no published Resend records although Resend listed `cuadrao.ai` as verified, and `hola@cuadrao.ai` had no MX route (see the launch record). Resolve that contradiction first; it may be a zone that is not active.
2. Add `notify.cuadrao.ai` to Resend. Resend returns the exact records (SPF `include`, DKIM key, return-path MX). Copy them verbatim; do not invent values.
3. Add a DMARC record for `_dmarc.notify.cuadrao.ai` (start at `p=none` with a report address the founder owns) unless one already covers the subdomain.
4. Apply only the named records after approval; wait for Resend to show Verified; send one test message to a founder-approved address; read the received headers for SPF, DKIM and DMARC pass.
5. The inquiry mailbox must actually receive mail. Verified sending does not prove a mailbox exists, so the test message is the proof. The public address `hola@cuadrao.ai` is shown on the pages and receives removal requests, so it needs a working route before publication whether or not it is also the inquiry mailbox.
6. Rollback removes only the added `notify` records.

Confirmation email for signups is not selected for launch (forms contract). The availability notice is sent through the operator tool, from a sender the founder chooses at that time.

## 7. Domain cutover (#891)

After hosted acceptance and the founder's publication approval, coordinating with #830 so the native and app setup does not overwrite these records.

1. Save a sanitized before-state of Cloudflare records and Render custom domains.
2. In Render add `cuadrao.ai`; Render adds `www.cuadrao.ai` and redirects it to the apex automatically. Use the exact DNS targets Render displays for the apex and `www`; do not assume an apex CNAME.
3. Keep the records DNS only (grey cloud) so Render issues and renews the certificate. If the domain has CAA records they must allow Let's Encrypt and Google Trust Services.
4. Set `CUADRAO_SITE_INDEXING=public` and restart. If the records were instead proxied through Cloudflare, also set `CUADRAO_TRUSTED_CLIENT_IP_HEADER=CF-Connecting-IP`; behind a proxy the rightmost `X-Forwarded-For` entry would be the proxy, not the visitor.
5. Verify HTTPS, certificate, apex/www redirect, language routes, old `/business` redirects, titles, favicon, canonical, hreflang, sitemap, robots and share previews on the public origin; repeat the inquiry and signup/removal journeys; verify Search Console ownership and submit `https://cuadrao.ai/sitemap.xml`. Record the submission; do not promise indexing.
6. Rollback: set `CUADRAO_SITE_INDEXING` back to unset, remove the two Render custom domains and restore the saved DNS records. Registrations and suppression records are untouched.

`app.cuadrao.ai` and `news.cuadrao.ai` are not part of this launch ([#892](https://github.com/lagarcess/argus/issues/892)).

## 8. Rollback

- **Code.** Render, Deploys tab, choose the last successful deploy, Rollback. It reuses that deploy's build artifact, start command, health check and the environment variables it had, and a Dashboard rollback turns Auto-Deploy off (it is already off). It does not change custom domains or the instance type. Because it restores that deploy's environment values, a key rotated since then comes back as the old key; rotate again if that matters.
- **Retention.** Render keeps artifacts according to the workspace plan, so only recent deploys are eligible. The first deploy cannot be rolled back to anything earlier.
- **Data.** Rollback does not undo DNS or database writes. Registrations and suppression records are preserved. Dropping the signup table is a separate migration that must first preserve registrations.
- **Extraction.** Reverting the extraction commits restores the pre-extraction `web/` routes and touches no data.
- **Forms.** To stop collecting without a rollback, remove `RESEND_API_KEY` or `SUPABASE_SERVICE_ROLE_KEY` in Render and restart. The affected form then shows its unavailable state and the direct email address.

## 9. Open founder inputs

Batched in the launch record: Spanish copy approvals, the privacy text facts (retention wording, legal entity, processors), the Option B exception, provider access for read-only inspection, and the approved test addresses.
