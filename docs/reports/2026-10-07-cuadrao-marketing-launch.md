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
| #881 Business inquiries | Implemented and covered by unit and browser tests against a recording mock. Real receipt at `hola@cuadrao.ai` is not yet proven. |
| #882 Personal signups | Implemented. Table contract proven against real Postgres and PostgREST locally. Hosted storage, removal and notice are not yet proven. |
| #889 transactional email | Plan and records procedure written. Nothing read or changed in Resend or Cloudflare yet. |
| #890 promotion and Render | Promotion diff measured and a bounded option prepared. Render settings written. Service not created. |
| #891 domain | Procedure written. Nothing changed. |
| #892 app and news | Deferred. No change. |

## Hosted readback (read-only, 2026-10-07)

Through the Supabase connector, with no row data read:

- Project `Argus` (`us-east-2`, Postgres 17) reported `INACTIVE` at the first read and `ACTIVE_HEALTHY` minutes later. No activation or plan change was requested by this lane.
- The production migration ledger has 82 entries. The latest is `20260914120000_share_plain_answer_receipts`, identical to `main`'s newest migration file. The signup migration (`20260920000000`) therefore sorts after everything production has applied and before the 35 integration migrations production lacks.

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
