# Evidence index

This file lets a reviewer verify where every finding in this report comes from. It lists the pull request and commits, then each class of evidence with how it was obtained and what it cannot show.

## Provenance

| Item | Value |
| --- | --- |
| Pull request | [lagarcess/argus#725](https://github.com/lagarcess/argus/pull/725), draft, base `codex/private-alpha-next` |
| Branch | `claude/dominican-bank-data-feasibility-214280` |
| Lane base | `f0a90763b79e5625ac0a4789cdfa171cda023963`, fetched 2026-09-27 |
| Integration at last reconciliation | `3b9313f3dcf80e3ff9eddfcce8818a829a081225`. The unpublished branch fast-forwarded to it before the first commit. |
| Head before the selected-file proof | `7a262986c4b02ec5d14a9e0caf24963d4228cb13` |
| Head the first automated review covered | `54a359dea7f332da3da80e81ef28a33e6b304a14` |
| Recording model the proof runs against | Pull request 724 at `8cdfc6a09e2fb1001b6a7c8694b67e3bd08fa491`, fetched 2026-09-28. The refresh started at `0df86aa8c7f4171331ec8319b8b771a577de42da`, the head the lane named, and gave the same observations there. The proof first ran at `720aad3fdee1357e3dbe5c928176a6e458b01b0d`. |
| Current head | Reported on the pull request. Every commit after `7a262986c` is listed there. |

Commits up to `7a262986c`, oldest first:

1. `41cea4197` adds the connector lifecycle experiment.
2. `f3093c9b5` adds the feasibility report.
3. `25cc007a0` adds the research notes and decision trail.
4. `b85dcb32a` quotes Popular's statement fees exactly.
5. `7a262986c` makes the testers' bank decide the first import.

## Primary sources the report author re-read directly

Each source below was opened by the report author, not only by a research agent. PDFs were read through `pdftotext` on the official file.

| Finding | Source | Read |
| --- | --- | --- |
| Penal Code article 188 lists a username or password, account numbers, and card numbers as identifying information. Article 198 punishes automated collection without prior consent. Article 393 sets effect 12 months after promulgation. | [Ley 74-25, Poder Judicial copy](https://transparencia.poderjudicial.gob.do/observatorio//documentos/PDF/normativas//NOR_enal_de_la_Republica_Dominicana.pdf) | 2026-09-27 |
| Payment-initiation providers may not store users' credential data. | [Resolución JM 250828-02, article 39(c)(ii)](https://cdn.bancentral.gov.do/documents/normativa/documents/2da-Res-JM-28-08-2025-Mod-Reglamento-SIPARD.pdf) | 2026-09-27 |
| Bridge logs in on the user's behalf, stores encrypted session tokens, claims no bank affiliation, and keeps data 30 days after revocation. | [Bridge Connect terms, updated 2025-10-10](https://bridge.com.do/terminos-uso-bridge-connect), [revoke endpoint](https://docs.bridge.com.do/api-reference/endpoint/revoke-connection) | 2026-09-27 |
| Rexi requires written authorization for any reuse of its information. | [Rexi legal notices, updated 2018-10-05](https://www.rexi.do/avisos-legales) | 2026-09-27 |
| Plaid's settlement received final approval on 2022-07-20 for USD 58 million with 1,256,738 claim forms. Chase's 2018 agreement used tokens without Plaid storing usernames and passwords. | [Final approval order, Dkt. 184](https://www.govinfo.gov/content/pkg/USCOURTS-cand-4_20-cv-03056/pdf/USCOURTS-cand-4_20-cv-03056-4.pdf), [Chase announcement](https://media.chase.com/news/plaid-signs-data-agreement-with-jpmc) | 2026-09-27 |
| Plaid's status history lists 25 incidents from 2026-06-05 to 2026-09-26, 10 naming one institution. | [Plaid status API](https://status.plaid.com/api/v2/incidents.json) | 2026-09-27 |
| Popular's personal fee schedules effective 2026-09-27 and 2026-04-13 both list in-app statement generation ("primeros 4 años") and automatic statement delivery by email or SFTP as free. Neither names a file format. | [Schedule effective 2026-09-27](https://popularenlinea.com/historicotarifa/Documents/personal/vigente/tarifario-web-cambios-vigentes-al-27-de%20septiembre-2026-banca-personas.pdf), [schedule effective 2026-04-13](https://popularenlinea.com/Personas/Documents/Tarifas/tarifario-productos-y-servicios-vigentes-al-13-04-2026.pdf) | 2026-09-27 and 2026-09-28 |
| Google Play restricts AccessibilityService use by apps that are not accessibility tools. | [Play Console Help](https://support.google.com/googleplay/android-developer/answer/10964491) | 2026-09-27 |
| Sign in with Apple shares a name and an email or relay address and no mailbox access. Reading Gmail needs Gmail API scopes, and `gmail.readonly` is restricted, with verification and a yearly independent assessment when data reaches a server. Gmail forwarding needs a confirmed address and can forward only filtered messages. | [Apple support](https://support.apple.com/en-us/102609), [Gmail API scopes](https://developers.google.com/workspace/gmail/api/auth/scopes), [restricted-scope verification](https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification), [Gmail forwarding](https://support.google.com/mail/answer/10957) | 2026-09-28 |

## Research notes

The [research notes](research-notes/README.md) hold every other source, each with a URL, the date seen, and an evidence label. Research agents wrote them from public sources on 2026-09-27. Their limits are stated inside each note.

| Note | Backs | Main limits |
| --- | --- | --- |
| Plaid and aggregation history | [Plaid lessons](plaid-lessons.md) | Dockets after the published orders returned HTTP 403 |
| Dominican financial regulation | [Legal matrix](legal-regulatory-matrix.md) | The Banco Central cybersecurity instructivo was too large to read |
| Dominican data protection and criminal law | [Legal matrix](legal-regulatory-matrix.md) | Bill texts, Ley 44-26, and official copies of Ley 53-07 and Ley 126-02 were not read |
| Banks: Popular, Banreservas, BHD | [Bank matrix](bank-access-matrix.md) | Popular's FAQ answers sit behind click controls. Banreservas' contracts are image-only scans. |
| Banks: Scotiabank, APAP, others | [Bank matrix](bank-access-matrix.md) | APAP's channel terms are not public |
| Aggregators and Bridge | [Bank matrix](bank-access-matrix.md) | Bridge's bank list needs a developer account. The Salt Edge archive was read by the note, not re-read by the author. |
| Rexi | [Rexi appendix](rexi-product-discovery-appendix.md) | 9 distinct product pages, 4 repeat reads inside the fetch cache |
| Scrapling | [Options comparison](options-comparison.md) | Source read at one pinned commit, nothing installed |
| Code reuse map | [Integration map](integration-map.md) | Read-only at the lane base |

## Executable evidence

| Evidence | Command | Result |
| --- | --- | --- |
| Connector lifecycle experiment | `poetry run python docs/reports/dominican-bank-connectivity/connector_lifecycle.py --report temp/connector-lifecycle-report.json` | 25 of 25 checks. Automated reviews of `54a359dea` and `47f7dbe68` found an unreadable balance escaping as an exception, deletion leaving proposals behind, a stale revision that could be reapplied, and values stored under an account of another currency. Each now has a check that failed before its fix. A malformed balance timestamp, a second finding on balance validation, is a stated limit awaiting a decision. Repeated runs write the committed [report](connector-lifecycle-report.json) byte for byte. |
| Selected-file import proof | `selected-file-import/proof.py` with and without pull request 724's reference model at `8cdfc6a09` on the path, as its [rerun steps](selected-file-import/README.md#rerun) list | With the model, 37 of 37 cases pass. Without it, 15 pass and 22 report blocked, which is not a pass. Both runs write their committed reports, [with](selected-file-import/proof-report.json) and [without](selected-file-import/proof-report-without-724.json), byte for byte. The committed [breakage check](selected-file-import/mutation_check.py) makes eleven deliberate breakages, and each fails its target cases. |
| Synthetic ingestion kit | `poetry run pytest tests/synthetic_ingestion --confcutdir=tests/synthetic_ingestion --no-cov -q` | 46 passed |
| Tests that walk the docs, source, or evidence trees | `poetry run pytest tests/test_private_alpha_release_docs.py tests/test_backtest_job_scopes.py tests/test_spine_guardrails.py tests/research/test_evidence_driver_calls.py -q --no-cov` | 72 passed |
| Docs gates | `git diff --check`, `scripts/check_docs_links.py --base origin/codex/private-alpha-next`, `.github/docs-only-changes.sh --from-git origin/codex/private-alpha-next` | Clean, `docs_only=true` |

## Repository evidence

The selected-file proof follows the lane text, the recording decision response, and the balance reconciliation handoff in pull request 727 at `a1c294319`, read on 2026-09-28. The three documents are unchanged at `d7faac770`. With pull request 724's model at `720aad3fd`, statement rows dated the day before a confirmed balance check confirmed without review. At `0df86aa8c` and `8cdfc6a09` they wait for the person's answer, and the proof now asserts that behavior as a regression case.

The integration map's 34 code links resolve at `f0a90763b`. Their cited line ranges are unchanged at `3b9313f3d`. Pull request 721 changed only the log-privacy test among the cited files, and the map's sentence about it was updated.

## Absence findings

These findings say that something was not found where the research looked. Each could be overturned by a source the research missed.

- No Dominican open-finance law, reglamento, instructivo, circular, or consultation draft was found on the official listings on 2026-09-27.
- No candidate bank publishes a consumer account API.
- No candidate institution states a statement or export file format, PDF text layer, file password, or history window on the public pages checked.
- No aggregator's own public pages name a Dominican bank today.

## What could not be verified

- The BHD contract model exceeds the fetch limit, and downloading it needs the founder's permission. The bank research re-read its clauses 71, 73, and 105.
- The Internet Archive refused the fetch tool and the browser pane, so the Salt Edge history rests on the research note.
- The session's shared web-search allowance ran out partway through the research. Later lookups used direct fetches of known official pages.

## Independent review

A second model (Sonnet) reviewed the report on 2026-09-27. It found no high or medium issues, matched 11 of 11 spot-checked claims to their sources, and re-ran the experiment byte for byte. Its 5 low findings were fixed. The [decision trail](decision-trail.tsv) records the review and the fixes.
