# W5: facts for PR #781 item P7 (BCRD terms and retention numbers)

Research date: 2026-10-03. Read-only. Repo read at integration `a8c37d3a1`.
PR #781 head read: `b9a695d7` (`docs/legal-cuadrao-deletion`).
Line numbers below are lines of `docs/legal/cuadrao-terms-privacy-draft.md`
at `b9a695d7`. The file is new, so in `gh pr diff 781` output the same line
sits 203 lines lower (file line 21 is diff line 224).

Quoting note: vendor wording is paraphrased. Numbers are given as facts with
their URL. One direct quote is kept (BCRD), under 15 words. Read the exact
wording at each URL before copying anything into the legal text.

---

## 1. BCRD terms of use

**Source.** BCRD "Términos y condiciones de uso", portal and App BCRD.
Page: https://bancentral.gov.do/a/d/3894 (fetched 2026-10-03; the text loads
from the page's own content call, article id 3894). The article's
publication date field is 2019-03-19.

What it says, in short:

- **Ownership.** All text, information, data, graphics, code and logos on the
  site belong to BCRD unless stated otherwise. "Data" is named explicitly.
- **Allowed use.** Free use only for informational or educational,
  non-commercial purposes: "para fines informativos o educativos no comerciales".
- **Prohibited without prior authorization.** Commercializing, distributing,
  circulating, transmitting or disseminating the site's content in any format.
  The page cites Ley 65-00 (copyright) and Ley 20-00 (industrial property).
- **Any other use** needs BCRD's express authorization.
- **Attribution.** Users may rely on the legal exceptions in Ley 65-00, and
  those exceptions make citing the source mandatory. So any use under an
  exception must name BCRD as the source.
- **No endorsement.** BCRD says it has never sponsored or authorized third
  parties to commercialize or redistribute its data on their own account.
- **No warranty, indemnity.** Information is offered free and for information
  only. The user indemnifies BCRD for misuse, including legal costs.
- **Access.** BCRD may block access from origins with anomalous traffic.
- **Disputes.** Dominican law governs.

**BCRD API.** https://apibcrd.bancentral.gov.do/ (fetched 2026-10-03) is a
login wall with a "Solicitar acceso" form (user type, entity, ID document,
country, captcha). No terms are visible before registering. The API's own
terms are UNKNOWN. I did not submit the form.

**Same data under an open licence.** datos.gob.do lists BCRD's
"Histórico Tasa del Dólar, 1985-2021" under ODbL (Open Data Commons Open
Database License), files hosted on cdn.bancentral.gov.do, last modified
2021-09-03. Source: https://datos.gob.do/api/3/action/package_show?id=serie-historica-dolar_
(fetched 2026-10-03). ODbL allows commercial use with attribution and
share-alike on public derived databases. It covers that frozen 1985-2021
series only. Current daily rates (for example the 2 October 2026 notice at
https://cdn.bancentral.gov.do/documents/estadisticas/mercado-cambiario/documents/tasaus_mc.pdf)
are on the BCRD site under the site terms above.

**How the repo uses BCRD today.** No product code reads BCRD.
`git grep -i bcrd` in `src/` finds nothing. Wave 1 shows no exchange rates
and never combines pesos and dollars (`docs/specs/wave-1/00-shared-rules.md`
R2 and RM-9, lines 30 and 427-446). The only `BCRDProvider` is a placeholder
on an unmerged pilot branch that always raises `bcrd_schema_unverified`
(RM-15, line 537). The research path can cite a bancentral.gov.do page as a
source (`tests/research/test_research_answer.py:790`). The archived pivot
strategy already recorded this conflict and sent it to counsel
(`docs/archive/2026-09-26-argus-pivot-strategy.md:160`), and the archived
roadmap said both BCRD and the Superintendencia need written permission
before display (`docs/archive/2026-09-26-argus-answers-that-stay-true-roadmap.md:80`).

**Reading for Cuadrao (not legal advice).** Cuadrao is a commercial app.
Showing BCRD's current rate inside it is a commercial use and a transmission
of site content. On the plain text of the site terms, that needs BCRD's
prior written authorization. Citing BCRD as the source is required in any
case. The 1985-2021 ODbL series is usable with attribution and share-alike.

**Open for counsel:**

- Whether a bare published number (an official exchange rate) is protected at
  all under Ley 65-00, or whether the site terms bind by contract alone.
- Whether the ODbL listing of BCRD data on datos.gob.do extends to current
  rates, or only to the snapshot files listed there.
- Whether the API (behind registration) carries its own licence, and whether
  it is open to a foreign or not-yet-formed entity (P4).
- Whether citing a BCRD page inside a research answer is fair quotation or
  "transmission".

---

## 2. Retention table

"Configured value" is this project's actual setting. A vendor default is
never shown as the configured value.

| System | Data kind | Configured value | How known | Source URL |
| --- | --- | --- | --- | --- |
| Supabase (project `lgdhvepyrzbnscqssgqq` "Argus", region us-east-2) | Plan | **Free** (`plan: free`, `tier_free`), org "ARGUS QUANTITATIVE" | Supabase MCP `get_project` and `get_organization`, read 2026-10-03. Also `docs/specs/argus-execution-board.md:2477` ("current Free plan") and the MVEE lock on the current plan (`docs/specs/argus-minimum-viable-ecosystem-experience.md:124`) | MCP read |
| Supabase | Automatic daily database backups | **None.** Free plan has no automatic backups | Plan from MCP plus vendor pricing (Free: automatic backups not included). Docs: Pro 7 days, Team 14, Enterprise up to 30; Free projects are told to export their own dumps | https://supabase.com/pricing ; https://supabase.com/docs/guides/platform/backups (both fetched 2026-10-03) |
| Supabase | Point-in-time recovery (PITR) | **Off / not available** on Free | Vendor docs: PITR is an add-on for Pro, Team and Enterprise only, with 7, 14 or 28 day windows | https://supabase.com/docs/guides/platform/backups |
| Supabase | Platform logs (API and database) | **1 day** | Plan from MCP plus pricing table (Free 1 day; Pro 7; Team 28; Enterprise 90) | https://supabase.com/pricing |
| Supabase | Log drains (copies of logs elsewhere) | **None possible** on Free | Pricing: log drains not included in Free | https://supabase.com/pricing |
| Supabase | Auth audit log in `auth.audit_log_entries` (user id, IP, user agent per auth event) | **UNKNOWN.** Depends on the dashboard toggle "Write audit logs to the database" | Vendor doc. The deletion census leaves the `auth` schema out of its sweep (`docs/specs/lanes/account-deletion-fk-census.md:135`) | https://supabase.com/docs/guides/auth/audit-logs |
| Supabase | Storage objects | Not covered by database backups. No bucket on this base yet (#778) | Vendor doc; census lines 135 and 140 | https://supabase.com/docs/guides/platform/backups |
| Supabase | Vendor-internal infrastructure copies outside project control | **UNKNOWN** | Not stated in the backup docs | Needs Supabase DPA / privacy policy |
| Operator copies | Manual `pg_dump` or exported files | **UNKNOWN.** No dump procedure in repo (`git grep pg_dump` finds none) | Repo search | n/a |
| Render | Workspace plan | **UNKNOWN** | Render MCP `list_workspaces` returned `unauthorized` on 2026-10-03. `render.yaml` `plan: standard` (argus-api) and `plan: starter` (argus-app) are instance types, not the workspace plan | `render.yaml` lines 9 and 208 |
| Render | Service logs (argus-api, argus-app, workflow task runs) | **UNKNOWN; 7, 14 or 30 days** by workspace plan: Hobby 7, Pro 14, Scale/Enterprise 30 | Vendor doc | https://render.com/docs/logging (fetched 2026-10-03) |
| Render | HTTP request logs (method, status, host, path) | Only on Pro workspace or higher; same retention as above. **UNKNOWN** whether on | Vendor doc | https://render.com/docs/logging |
| Render | Log streams to a third party | **UNKNOWN.** None configured in `render.yaml`; it is a workspace dashboard setting | Repo plus vendor doc | https://render.com/docs/log-streams |
| PostHog | Region | **US Cloud** (`POSTHOG_REGION: us`, host `https://us.i.posthog.com`) | `render.yaml:124`; `src/argus/observability/envelope.py:149`; runbook line 777; `docs/API_CONTRACT.md:6394` | repo |
| PostHog | Whether capture is on in production | Token was present at the 2026-08-05 promotion; current state **UNKNOWN** | `docs/release-manifests/2026-08-05-main-production-promotion.md:41`; token is `sync: false` | repo |
| PostHog | What is sent | Server-side only, personless (`$process_person_profile: false`), `distinct_id` = unsalted SHA-256 of the user id (`argus_actor_` + 32 hex). No session replay, no autocapture, no web SDK | `src/argus/observability/envelope.py:320-340`; `src/argus/observability/product_events.py:114-118`; runbook lines 774-781 | repo |
| PostHog | Event retention | **UNKNOWN; 1 year (Free) or 7 years (any paid plan).** Cannot be shortened to remove data | Vendor doc | https://posthog.com/docs/data/events-retention ; https://posthog.com/pricing (fetched 2026-10-03) |
| PostHog | Session recordings | **Not used** (runbook forbids replay). Vendor values for reference: Free 1 month, pay-as-you-go 90 days | Repo plus vendor pricing FAQ | https://posthog.com/pricing |
| PostHog | Deletion on account delete | **Not implemented.** Only a recording fake exists; `ARGUS_ANALYTICS_DELETION_ENABLED` raises if turned on; real adapter is #806; `ARGUS_ACCOUNT_DELETION_ENABLED=false` until #806 and #805 | `src/argus/observability/analytics_deletion.py:1-60`; `.env.example:240-245`; runbook lines 857-860 | repo |
| PostHog | Deletion timing once built | Asynchronous. Event data is cleared in off-peak batches, weekends on PostHog Cloud. Person delete with `delete_events=true` deletes events. Our events are personless, so the code notes a person bulk delete finds nobody and events must be deleted by distinct id | Vendor doc plus code docstring | https://posthog.com/docs/privacy/data-deletion (fetched 2026-10-03) |

Two side facts worth knowing:

- **Render log content.** Loguru uses the default format
  (`src/argus/log_sink.py:12`), so keyword fields such as `user_id=` are not
  printed. The uvicorn start command has no `--no-access-log`
  (`render.yaml:12`), so access lines with request paths reach Render logs.
  I did not audit every message string for identifiers.
- **Free plan means no database backup at all.** Deleted data is not held in
  Supabase backups. The same fact means the production database has no
  restore point, which is an operational risk outside this PR.

---

## 3. What these facts do to the #781 draft

File: `docs/legal/cuadrao-terms-privacy-draft.md` at `b9a695d7`.

**Supported**

- L21 (P7 row): "depends on each plan". The plans are now known for Supabase
  (Free). Render and PostHog plans remain open.
- L73-75 / L213-215 "deletion is final". Consistent with Supabase Free: there
  is no backup or PITR to restore from.
- L96-97 / L236-237 "logs and error diagnostics". Render and Supabase do keep
  logs, so the collection list is right.
- L139-141 / L277-279 "We keep your data while your account is active.
  [Pending P7]". True for the database. The P7 slot can now name
  numbers, as below.

**Contradicted or needs rewording**

- L130 / L269 "PostHog: analítica de producto en nuestros servidores" /
  "product analytics on our servers". Capture starts on our servers, but
  PostHog stores the events on PostHog US Cloud for 1 or 7 years. "On our
  servers" reads as self-hosted. Suggested meaning: "PostHog (US):
  product analytics sent from our servers, without your name or email."
- L155-156 / L293-294 "también borramos ... tu actividad registrada en la
  analítica de producto" / "delete your activity in product analytics".
  Not true in code today: the PostHog step is a fake and stays pending
  (#806). Even once built, PostHog deletes events asynchronously (weekend
  batches). The sentence can ship only with #806, and should say deletion
  there finishes later, not at once.
- L151-154 / L289-292 "When you delete your account, we delete ...". True
  for live tables. It does not mention copies outside the database: Render
  logs (7 to 30 days), Supabase platform logs (1 day), and possibly the
  Supabase auth audit table if its toggle is on. The P7 slot should state
  these windows.

**Left open**

- Render retention: needs the workspace plan (section 4).
- PostHog retention: needs the PostHog plan (section 4).
- Data location: Supabase us-east-2, Render Virginia, PostHog US. The draft
  says nothing about storage country or cross-border transfer. That is a
  P4/P8 counsel point (DR Ley 172-13), not a P7 number.
- BCRD: the draft (L120-132, L259-271 providers; L69-71, L209-211 third
  parties) never mentions BCRD or exchange rates. That is correct for wave
  1, which shows no rates. If a later slice shows BCRD rates, the Terms need
  a source line ("Fuente: Banco Central de la República Dominicana") and a
  no-warranty note, and BCRD's written authorization must exist first.
  BCRD is a data source, not a processor, so it does not belong in the
  privacy providers list.

**Draft P7 sentence once the unknowns are filled (for Yelena to adapt):**
"After deletion, copies can remain for a short time in server logs (up to
[7/14/30] days at Render, 1 day at Supabase) and in product analytics until
PostHog finishes its deletion. Supabase keeps no backups of our database."
Fill the brackets from section 4 before use.

---

## 4. Unknowns the founder must read

1. **Render workspace plan.** Render Dashboard, Workspace Settings, Billing
   (plan name). Hobby means 7-day logs; Pro 14; Scale or Enterprise 30.
   Pro or higher also turns on HTTP request logs.
2. **Render log streams.** Workspace Settings, Log Streams. Any destination
   listed there keeps its own copy under its own retention.
3. **PostHog plan.** PostHog, Organization settings, Billing. Free means
   events kept 1 year; any paid plan means 7 years. The window cannot be
   shortened.
4. **PostHog is capturing in production now?** Render Dashboard, argus-api,
   Environment: is `POSTHOG_PROJECT_TOKEN` non-empty.
5. **Supabase auth audit table.** Supabase Dashboard, Authentication,
   Configuration, Audit Logs: is "Write audit logs to the database" on. If on,
   rows with user id and IP stay in `auth.audit_log_entries` after deletion
   unless purged.
6. **Any manual database dumps** an operator keeps (laptop, drive). Not in
   the repo.
7. **Supabase internal copies** beyond the plan's backups. Not in public docs;
   read the Supabase DPA or ask Supabase.
8. **Plan change before launch.** If Supabase moves to Pro, backups become
   7 days (Team 14, Enterprise up to 30), PITR becomes possible (7, 14 or
   28 days), and platform logs become 7 days. P7 text must change with it.
9. **BCRD API terms.** Visible only after registering at
   apibcrd.bancentral.gov.do.
10. **BCRD authorization.** Whether Cuadrao has asked for or holds BCRD's
    written permission to show rates.

---

## 5. Status

The Terms and Privacy text in #781 stays a draft. These facts fill most of
P7, but P4 (entity and law), P5 (contact), P6 (publication) and P8 (counsel)
remain open. Counsel should review the retention wording, the data-location
gap and the BCRD question before anything is published. This report is not
legal advice.
