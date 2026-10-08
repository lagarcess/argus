# Cuadrao marketing launch record

Status record for [#880](https://github.com/lagarcess/argus/issues/880) and its children. The [launch runbook](../runbooks/cuadrao-marketing-launch.md) owns settings and procedure, the [forms contract](../specs/cuadrao-marketing-forms-contract.md) owns the endpoints and data, and the [evidence folder](evidence/cuadrao-marketing-launch/README.md) holds the proof. This page only says where the launch stands. It authorizes nothing.

## Lineage

- Lane base: `93571e593e1677561e1dd38f63b6475574942e2d` (`origin/codex/private-alpha-next`, fetched 2026-10-07).
- Worker branch: `codex/cuadrao-marketing-launch`.
- Candidate, reconciliation and CI state are filled in at READY (see the PR).

## Prepared in this PR

| Child | State |
| --- | --- |
| #887 independent package | `marketing/` builds from a clean frozen install with Bun 1.3.14 on Node 24.21.0, starts with an empty environment, and renders byte-identical screenshots to the legacy pages in Chromium and WebKit at 1440 and 390 pixels, in both languages. |
| #888 identity and metadata | One route owner drives canonical, hreflang, sitemap, redirects and navigation. Provisional Cuadrao icons replace the inherited Argus icon. Founder review of the mark is pending. |
| #881 Business inquiries | Implemented and covered by unit and browser tests against a recording mock. The destination is now configurable (`CUADRAO_INQUIRY_TO`, no default); real receipt waits for the founder to choose it. |
| #882 Personal signups | Implemented. Table contract proven against real Postgres and PostgREST locally. Hosted storage, removal and notice are not yet proven. |
| #889 transactional email | Plan and records procedure written. Nothing read or changed in Resend or Cloudflare yet. |
| #890 promotion and Render | Promotion diff measured and a bounded option prepared. Render settings written. Service not created. |
| #891 domain | Procedure written. Nothing changed. |
| #892 app and news | Deferred. No change. |

## Hosted readback (read-only, 2026-10-07)

Through the Supabase connector, with no row data read:

- Project `Argus` (`us-east-2`, Postgres 17) reported `INACTIVE` at the first read and `ACTIVE_HEALTHY` minutes later. No activation or plan change was requested by this lane.
- The production migration ledger has 81 entries. The latest is `20260914120000_share_plain_answer_receipts`, identical to `main`'s newest migration file. The signup migration (`20260920000000`) therefore sorts after everything production has applied and before the 35 integration migrations production lacks.

## Render, Resend and DNS readback (read-only, 2026-10-07)

Through the connected Render and Resend tools and public DNS lookups. Nothing was changed and no secret or setting value was read.

- **Render.** Three workspaces: `argus-prod`, `payment-ledger`, `rag-lens`. Only `argus-prod` holds Argus: `argus-app` (Node, `web`, Starter, branch `main`, Auto-Deploy off, build `npm install -g bun && bun install --frozen-lockfile && bun run build`, start `bun run start -- -p $PORT`, no health check path) and `argus-api` (Python, Standard, Auto-Deploy off). No `cuadrao-marketing` service exists, so there is no name collision. `argus-app` shows Bun installed during build is usable at start, so either start command would work; the runbook keeps `npm run start`.
- **Resend.** Two domains, both verified with sending enabled and receiving disabled: `cuadrao.ai` (created 2026-09-29) and `get-argus.com`. `notify.cuadrao.ai` is not registered, so nothing about it exists yet. `cuadrao.ai` lists a DKIM TXT at `resend._domainkey` and two CNAMEs, `send` and `rsend`, all marked verified.
- **DNS, and a contradiction to resolve before any email test.** `cuadrao.ai` is registered at Cloudflare (active, expires 2028-09-29) with Cloudflare name servers, and its SOA answers. But public lookups, from two resolvers and from Cloudflare's authoritative server, show **no records for the apex** (no MX, TXT or A) and **NXDOMAIN for `resend._domainkey`, `send` and `rsend`**, although Resend reports those records verified. Cloudflare's authoritative server also answers `REFUSED` for apex record types other than SOA, which is unusual and suggests the zone is not in a normal active state. Two consequences follow if this is real: the Resend records Resend calls verified are not published, and **`hola@cuadrao.ai` has no mail route at all (no MX)**, so an inquiry addressed to it would have nowhere to be delivered. The Cloudflare connector available here covers Workers, KV, R2 and D1 only, not DNS, so the zone itself has not been read. A read of the Cloudflare DNS and Email Routing pages (or a founder readback) settles it. Inquiry delivery cannot be proven, and the Business form must not be published, until `hola@cuadrao.ai` demonstrably receives mail.

## Supabase preview branch for #895 (read-only, 2026-10-07)

- **What exists.** One branch on project `qzylwjabjfophhipzoev`, name and Git branch `codex/cuadrao-marketing-launch`, PR 895, parent `lgdhvepyrzbnscqssgqq`, `persistent: false`, `with_data: false`, preview project `ACTIVE_HEALTHY`. A second branch record is the production project itself (`main`, status `MIGRATIONS_FAILED`, last updated 2026-06-04).
- **How it was created.** Not by this lane's tools. Its creation time (17:27:22Z) is seven seconds after PR 895 was opened (17:27:15Z), and it carries the Git branch and PR number. That is the Supabase GitHub integration's automatic preview branching, which also produces the `Supabase Preview` check. The check ran schema-only: it replayed the repository's migration chain (it lists this migration at its proper place) and no production data was copied. Earlier PRs show the same check. This lane created no hosted resource.
- **Charges.** Supabase documents no fixed fee for a branch, only usage. The connector quotes `0.01344` USD per hour for a branch (the default Micro compute), about $0.32 a day or $9.68 for a month if it ran continuously, plus egress and disk beyond the plan quota. Branch usage is not covered by the Spend Cap, and Compute Credits do not apply to it. Branching is documented as a Pro Plan feature, yet the organization (`ARGUS QUANTITATIVE`) reports the `free` plan, and the repository notes elsewhere that preview branches have hit plan quota. The connector exposes no invoice, so whether this branch is billed, and how much, is not confirmed. The Supabase usage page shows "Branching Compute Hours" and settles it.
- **Lifetime.** A non-persistent branch is removed when its PR is closed or merged, and preview branches auto-pause after inactivity.
- **Decision.** Automatic previews are not part of the agreed spending plan. The steps below disable them and remove this branch. They have not been run; each is a hosted write that needs the founder's go.

### Automatic Supabase behavior before promotion (read-only evidence, 2026-10-07)

The integration's settings page cannot be read from here, so each finding rests on what the integration did.

| Behavior | State | Evidence |
| --- | --- | --- |
| Automatic production migrations from `main` | **Off, as far as the evidence shows** | The production branch record has no Git branch (`git_branch` is empty). The `Supabase Preview` check on `main`'s promotion commit (2026-09-18) and on integration's head reads "skipped: this git branch is not associated with any Supabase Branch". The record's status has not changed since 2026-06-04 although `main` was promoted since. So a push to `main` is not wired to production migrations. |
| Automatic preview branching | **On** | A branch was created for PR 895 seven seconds after it opened, and the check says "open a PR to create a new branch". |

Promotion therefore waits on the founder disabling previews (steps below). Founder confirmation of the production-deploy setting in the dashboard is still worth one look, because the evidence is indirect.

### Disable automatic previews and remove this preview

Disable first, then delete. Deleting first lets the next push recreate the branch; disabling first leaves this branch running only until step 2.

1. **Disable automatic creation.** Supabase dashboard, project `Argus` (`lgdhvepyrzbnscqssgqq`), Project Settings, Integrations, GitHub. Turn off branching ("Enable branching" in current documentation; confirm the label in the UI, which this lane has not seen). Leave the repository connection itself alone for now; see the production-deploy check below. The same effect is available from the Management API as `DELETE /v1/projects/{ref}/branches` ("Disables preview branching"), which also needs the founder's authorization.
2. **Remove this preview.** Dashboard, branch selector, Manage Branches, `codex/cuadrao-marketing-launch`, Delete. Equivalent: the connector's `delete_branch` for branch `4796aa2f-9428-4b26-80c5-b48c2f0da29e`. The branch holds no production data (`with_data: false`), so nothing is lost beyond its schema replay.
3. **Verify.** Manage Branches lists only the production branch. The next push to #895 must not create a branch. Branching Compute Hours on the organization usage page stops accruing.
4. **Check the production-deploy setting before any promotion to `main`.** The integration's production branch record has read `MIGRATIONS_FAILED` since 2026-06-04. If the integration's "Deploy to production" is on, a push to `main` can make it try to apply migrations to production on its own. Confirm it is off (or intentionally set) before any promotion, and treat that as separate from step 1.

**Effect on CI.**
- `Supabase Preview` is not a required check anywhere. Branch protection on `codex/private-alpha-next` requires no checks, `main` requires only `ci`, there are no rulesets, and the aggregate `ci` job does not list it. Disabling previews therefore cannot block a merge. The check simply stops appearing on new pushes; the already-posted result stays on old commits.
- What is lost is a hosted replay of the migration chain. The repository's own `guest-release-gates` job already replays every migration on a disposable local Supabase stack, on both the pinned and the latest CLI, and runs all `test_*_postgres.py` proofs, including this table's. That is the coverage the founder's merge decision rests on, and it is unchanged.
- `supabase/config.toml` carries a comment about preview branches failing on a Pro-only setting. It becomes stale and can be edited in a later change; it is not needed for this one.
- If the branch is deleted without step 1, the next push or a reopened PR recreates it.

## Not yet true

- Nothing is deployed. No Render service exists, no DNS or Resend record was changed, no migration was applied, no test email was sent.
- Render, Resend and Cloudflare state was not read: the Render CLI token is expired, the Claude in Chrome extension is not connected, and those dashboards need a signed-in session.
- Spanish copy, the privacy text facts and the provisional icon await founder review.

## Copy awaiting founder review

Spanish first, English follows. Only strings whose meaning changed with real delivery or storage are new. Everything else is the approved copy, unchanged.

| Where | Spanish | English |
| --- | --- | --- |
| Contact, send button | Enviar mensaje | Send message |
| Contact, while sending | Enviando… | Sending… |
| Contact, sent title | Recibimos tu mensaje. | We received your message. |
| Contact, sent body | Te responderemos al correo que escribiste. | We'll reply to the email address you entered. |
| Contact, failure | No pudimos enviar tu mensaje. Lo que escribiste sigue aquí. Inténtalo de nuevo o escríbenos a hola@cuadrao.ai. | We couldn't send your message. What you wrote is still here. Try again or email us at hola@cuadrao.ai. |
| Contact, too many attempts | Hiciste varios intentos seguidos. Espera unos minutos e inténtalo de nuevo. | You made several attempts in a row. Wait a few minutes and try again. |
| Contact, field problem from the server | Revisa los campos marcados e inténtalo de nuevo. | Check the marked fields and try again. |
| Contact, no JavaScript | Activa JavaScript para enviar este formulario o escríbenos a hola@cuadrao.ai. | Enable JavaScript to send this form or email us at hola@cuadrao.ai. |
| Contact, under the form | Usamos tu nombre, correo y mensaje solo para responderte. Política de privacidad | We use your name, email and message only to reply to you. Privacy policy |
| Personal, under the form | Usaremos tu correo solo para avisarte sobre el acceso anticipado a Cuadrao. Para retirar tu registro, escríbenos a hola@cuadrao.ai. Política de privacidad. | We'll use your email only to tell you about Cuadrao early access. To remove your signup, email hola@cuadrao.ai. Privacy policy. |
| Personal, too many attempts | Hiciste varios intentos seguidos. Espera unos minutos e inténtalo de nuevo. | You made several attempts in a row. Wait a few minutes and try again. |
| Footer link (new) | Privacidad | Privacy |
| Privacy page | [privacy-copy.ts](../../marketing/components/privacy-copy.ts), both languages | same file |

Removed: the "Vista local" notices and "no se envía nada" lines on contact, and "El registro aún no está conectado" on Personal. Each stated that nothing was sent or stored, which stops being true.

The privacy text states facts only the founder can confirm: the project is "en preparación de Lucas Garcés" (legal entity not named), contact messages stay in the mailbox as long as needed to reply, early-access signups stay until removal is requested, Cloudflare is named as domain manager, and Supabase is in the United States (Ohio). Confirm or correct each before publication.

## Founder inputs and approvals needed

Listed with the exact request in the PR. In short: Option B promotion exception, a signed-in way for read-only inspection of Render, Resend and Cloudflare (or the founder reads them back), the existing Supabase project reactivated, approved test addresses, the copy and privacy facts above, and review of the provisional icon.
