# Cuadrao marketing launch record

Status record for [#880](https://github.com/lagarcess/argus/issues/880) and its children. The [launch runbook](../runbooks/cuadrao-marketing-launch.md) owns settings and procedure, the [forms contract](../specs/cuadrao-marketing-forms-contract.md) owns the endpoints and data, and the [evidence folder](evidence/cuadrao-marketing-launch/README.md) holds the proof. This page only says where the launch stands. It authorizes nothing.

## Landing

PR [#895](https://github.com/lagarcess/argus/pull/895) merged into `codex/private-alpha-next` as `fbb6bb447` (squash, PR head `d0447a7da`); integration then stood at `5def72db1` after #899 and #894. The merged diff equals the PR diff, `marketing/` and the signup migration are byte-identical to the PR head, `web/` equals its pre-website state, and #895 shares no file with #899 or #894. Nothing is promoted, deployed, applied or sent; the signup migration is in the repository only. The issue comments on #880 record the landing in full.

## Lineage

- Lane base: `93571e593e1677561e1dd38f63b6475574942e2d` (`origin/codex/private-alpha-next`, fetched 2026-10-07).
- Worker branch: `codex/cuadrao-marketing-launch`.
- Candidate, reconciliation and CI state are filled in at READY (see the PR).

## Landed in #895

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
- **Direct API readback (2026-10-07, later).** The Management API (read-only GET with the account token from the integration worktree's local `.env`, never printed) lists exactly two branches: the production `main` record with an empty Git branch and status `MIGRATIONS_FAILED`, and `codex/cuadrao-marketing-launch` (PR 895, `FUNCTIONS_DEPLOYED`). The two integration toggles ("Automatic branching", "Deploy to production") are dashboard-only; the platform API returned 401 for the token, so they still need one look in the dashboard.
- **Lifetime.** A non-persistent branch is removed when its PR is closed or merged, and preview branches auto-pause after inactivity.
- **Outcome.** The branch was removed after #895 merged (a non-persistent branch goes with its PR); no one in this lane deleted it. Automatic previews are not part of the agreed spending plan and no paid upgrade is authorized, but the toggle cannot be changed on Free, so the plan is to watch rather than disable (below). The earlier "disable and delete" steps were withdrawn.

### Automatic Supabase behavior (founder dashboard readback, then evidence)

The founder read the integration page directly. Supabase stays on the Free plan and no paid upgrade is authorized.

| Behavior | State | How known |
| --- | --- | --- |
| Deploy to production from `main` | **Off** | Founder, in the dashboard. Consistent with the API: the production branch record has no Git branch. |
| Automatic branching | **Cannot be changed on Free.** The control is disabled behind a Pro upgrade and the branch limit reads 0 | Founder, in the dashboard |

**An unexplained mismatch, to be investigated rather than worked around.** A preview branch was created for PR 895 seven seconds after it opened (17:27:22Z, 2026-10-07) although the limit now reads 0 and the organization reports the Free plan. It has since been removed. Whether branching was enabled earlier and the entitlement later lapsed, or the limit is read differently, is not known from here. The cost exposure of that one branch is unconfirmed (the connector quoted `0.01344` USD per branch-hour; the usage page's "Branching Compute Hours" would settle it).

**Standing check, no setting to change.** After the first Business PR that changes `supabase/migrations`, read the project's branch list (read-only Management API). If only the production `main` record is listed, the control is inert on Free and migration PRs are safe. If a preview appears, treat it as a mismatch to investigate (what created it, which entitlement allows it, what it costs) before further migration PRs, and do not ask for a toggle that does not exist. Deleting such a branch, or any other hosted change, still needs the founder's go.

**Effect on CI.** `Supabase Preview` is not a required check anywhere (integration requires no checks; `main` requires only `ci`; there are no rulesets). A skipped or absent Preview check cannot block a merge. The repository's own `guest-release-gates` already replays every migration on a disposable local Supabase stack on the pinned and latest CLI and runs all `test_*_postgres.py` proofs, which is the coverage the founder's merge decision rests on.

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
