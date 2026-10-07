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

## Not yet true

- Nothing is deployed. No Render service exists, no DNS or Resend record was changed, no migration was applied, no test email was sent.
- Hosted state was not read: the Render CLI token is expired, and Resend, Cloudflare and Render dashboards need a signed-in session. The existing Supabase project reports `INACTIVE`.
- Spanish copy, the privacy text facts and the provisional icon await founder review.

## Founder inputs and approvals needed

See the PR description for the current exact list.
