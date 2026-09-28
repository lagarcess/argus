# Dominican bank connectivity feasibility

**Date.** 2026-09-27.
**Inspected base.** `origin/codex/private-alpha-next` at `f0a90763b79e5625ac0a4789cdfa171cda023963`. Integration later advanced to `3b9313f3dcf80e3ff9eddfcce8818a829a081225` with pull request 721, a logging fix that touches no file this report depends on except one test it cites by name.
**Status.** Research report for founder review. It is not a product decision, not a legal opinion, and not an implementation. It serves sections 4.4 to 4.7, 5, 9, and 12 of the [minimum viable ecosystem experience](../../specs/argus-minimum-viable-ecosystem-experience.md) (MVEE), the founder-approved product direction.

## Recommendation

Build the bridge on files people download from their own bank, starting with the bank that the first consenting testers use. Do not build or buy credential-based access now. Put the boundary in place so a bank API can later replace the file without replacing anyone's records.

**What can Argus plausibly offer now?** Manual, chat, and voice entry, which MVEE section 4 already approves, plus import of statements and transaction files a person downloads from their own bank. Accounts shows each imported balance as of its statement date. Argus should make no claim of live bank sync. A forwarded e-statement and a purchase alert that starts a draft can follow as conveniences.

**Which access method first, and for which institution?** Statement and file import, options B and C in the [options comparison](options-comparison.md), starting with the bank that the first consenting testers use. The public evidence barely separates the candidates. None offers a consumer account API. Popular, BHD, and Scotiabank all document statements in their digital channels and delivery by email, and the Superintendencia de Bancos' 2025 digitalization ranking reports statement generation at 90% of intermediaries. If the testers' bank is undecided, Popular is a slight favorite. Its fee schedule is the only document found that lists automatic statement delivery by SFTP, and its line "Generación estados de cuentas desde App (primeros 4 años)" may mean four years of history. Both lines already appear in its schedule effective 2026-04-13, so they are not new. The report author re-read both schedules. Neither names a file format, and neither says whether a personal client can point SFTP delivery at a server of their choice. None of the five institutions states a statement or export file format, PDF text layer, file password, or history window on the public pages the research checked. That is an absence finding, not proof. Popular's online-banking FAQ answers sit behind click controls the research did not open, and Banreservas' contracts are image-only scans. So the first step is a consenting holder's own format test.

**Is credential-based aggregation worth pursuing?** Not now. Popular's Convenio and BHD's 2026 contract forbid letting third parties use online-banking credentials and put losses from shared credentials on the customer. The regulator's consumer office tells people never to share passwords. The only Dominican rule that defines a third-party access role forbids payment-initiation providers from storing user credentials. Criminal provisions on unauthorized access and on usernames and passwords exist, and nobody has settled how they apply to consented access. The options comparison lists five conditions that must all hold before this changes. Bridge, the one Dominican provider, uses credential-based access under its own terms and names no supported bank, so buying it inherits the same questions.

**Is user-assisted import a better bridge?** Yes. It needs no credential, no bank agreement, and no provider. It uses statements that the candidate banks document for their own customers. Which file formats those statements take is unverified until a consenting holder's test. It fits the approved ingestion flow and the synthetic kit. Its weakness is freshness, so it complements manual entry rather than replacing it.

**What requires institutional access or Dominican legal advice?** Legal advice is needed for credential-based access, including through Bridge, for extraction inside the person's own session, for the consent form and transfer basis under Ley 172-13 when data is stored in the United States, for article 30 of Ley 172-13 and the 2026 credit-information instructivo, and for access-log duties under Ley 53-07. Institutional access is needed for any bank API, any bank push of statements to Argus, any tokenized access, and any pilot under Circular SB 004/23. The [legal and regulatory matrix](legal-regulatory-matrix.md) lists the questions in priority order.

**What architecture can later accept bank APIs cleanly?** A connection boundary where the retrieval method is the only replaceable part. Observations become proposals, the person confirms them, and confirmed records keep a provenance list. The [connector lifecycle experiment](connector-lifecycle-experiment.md) passes 22 synthetic checks, including a move of a card account from CSV files to an aggregator feed that ends with the same 4 records. The [integration map](integration-map.md) proposes the boundaries and maps the existing code that can carry them.

**Does the connectivity business have supporting evidence?** No. Argus has no bank agreement, no connector, and no demand data. A local credential-based competitor exists. The European Union, the United Kingdom, Australia, Brazil, Chile, and Canada register or accredit whoever receives account data, so a future Dominican framework may do the same. The [partnership evidence proposal](partnership-evidence.md) keeps the idea separate and names the conditions to revisit it.

## The evidence in one place

| Question | Finding | Where |
| --- | --- | --- |
| Is there a Dominican open-finance rule? | None in force or in consultation. A Superintendencia de Bancos project page is labelled "S2 2026" with no draft. | [Legal matrix](legal-regulatory-matrix.md) |
| Do the candidate banks offer consumer account APIs? | No. Popular's API Portal returns reference data and a true-or-false account check. | [Bank matrix](bank-access-matrix.md) |
| Does any aggregator confirm Dominican coverage? | No provider's own pages name a Dominican bank today. Bridge claims coverage without names, and Prometeo lists the country as planned. Salt Edge listed screen-scraping connectors for Popular and Banreservas from 2017 and for BHD by 2019, and had dropped every Dominican connector by July 2022. | [Bank matrix](bank-access-matrix.md) |
| What did Plaid's history show? | Credential access was a bootstrap that took about a decade to leave. Liability followed interface design and data scope. | [Plaid lessons](plaid-lessons.md) |
| Can the lifecycle absorb retries, pending holds, revisions, and a method change? | Yes in synthetic form. Weekly batch review needs 12 owner actions in 60 days, against 88 for confirming each row alone. | [Experiment](connector-lifecycle-experiment.md) |
| Can Rexi supply product facts? | No. Its terms require written authorization for any reuse. Official tariffs contradicted Rexi on 5 of 14 firm fields. | [Rexi appendix](rexi-product-discovery-appendix.md) |
| Is Scrapling relevant? | Only its HTML parser, which `lxml` already covers. Its distinguishing features are out of bounds. | [Options comparison](options-comparison.md) |

## Verified, inferred, and unknown

**Verified directly by the report author.** Penal Code Ley 74-25 articles 188, 198, 199, and 393 in the Poder Judicial PDF. Article 39 of the 2025 payments reglamento in the Banco Central PDF. Bridge's Connect terms and revocation endpoint. Rexi's legal notice. The Plaid final approval order and JPMorgan Chase's 2018 announcement. Every code link in the integration map at the inspected base, and eight sampled line references.

**Verified by the research notes from primary documents.** Every row labelled "Verified through documentation" in the bank matrix, and every enacted instrument in the legal matrix. The research notes re-read the decision-relevant bank clauses in the original documents.

**Inferred.** Every legal reading marked "Inference" in the legal matrix. The ratings in the options comparison. The cost model's structure.

**Unknown until a test or an agreement.** Each bank's file format, text layer, password, and history window. Bridge's real coverage, refresh cadence, and reconnection rate. Demand, support load, and prices.

## Decisions for the founder

1. Reconcile archived decision 8, which keeps typed figures in the conversation only, with MVEE section 4, which makes the confirmed record the durable fact. The next contract depends on it.
2. Run, or ask another consenting holder to run, the statement format test at the bank the first testers use, as listed in the bank matrix. Popular breaks a tie if that bank is undecided.
3. Decide whether Argus may ever hold revocable bank secrets, directly or through a provider such as Bridge.
4. Decide whether pending holds count toward "what remains", whether any trusted feed may skip review, and what deleting imported data removes. The experiment measures these choices and settles none of them.
5. Engage Dominican counsel with the legal matrix's questions.
6. Decide whether to ask Popular about SFTP delivery for personal clients and BHD about its portability right, using the partnership evidence proposal and sharing no person's data.
7. Decide whether to consult the Hub de Innovación Financiera about read-only aggregation.

The [next assignment](next-assignment.md) is independent of all seven and can start now.

## How this lane stayed within its bounds

- Public sources only. Nobody signed in, enrolled, submitted a form, installed an app, or contacted a bank, Bridge, or Rexi. No credential, one-time code, session cookie, or customer record was requested, entered, or stored.
- Popular's websites refuse non-browser clients. Its public pages were read in an ordinary browser session, and no verification challenge was solved.
- Rexi's robots file and terms were read first. The inspection covered 9 distinct product pages, serially, at least 10 seconds apart.
- The experiment uses fictional data from the synthetic ingestion kit and Faker. It makes no network call and imports nothing from `src/argus`.
- No paid service, no paid evaluation, and no broad runtime suite ran.
- The session's shared web-search allowance ran out partway through. Later research used direct fetches of known official pages.
- The assignment names a balance-reconciliation handoff. No such document, issue, or pull request exists on the inspected base. The closest material is the "Decisions exposed, not settled" section of `tests/synthetic_ingestion/README.md` and the two reports merged on 2026-09-27, [synthetic-ingestion-evaluation.md](../synthetic-ingestion-evaluation.md) and [payment-ledger-reuse-assessment.md](../payment-ledger-reuse-assessment.md).

## Files

| File | Contents |
| --- | --- |
| [plaid-lessons.md](plaid-lessons.md) | Early aggregation checked against primary sources, and ten lessons |
| [legal-regulatory-matrix.md](legal-regulatory-matrix.md) | Dated Dominican legal and regulatory matrix and questions for counsel |
| [bank-access-matrix.md](bank-access-matrix.md) | Five institutions and the aggregators, every finding labelled |
| [options-comparison.md](options-comparison.md) | Options A to G, the decision matrix, Scrapling, and the cost model |
| [connector-lifecycle-experiment.md](connector-lifecycle-experiment.md) | Synthetic experiment results and rerun instructions |
| [connector_lifecycle.py](connector_lifecycle.py) | The experiment script |
| [connector-lifecycle-report.json](connector-lifecycle-report.json) | The committed experiment output |
| [integration-map.md](integration-map.md) | Journey, diagram, proposed boundaries, code reuse map, and unresolved contracts |
| [partnership-evidence.md](partnership-evidence.md) | Bank partnership evidence and the connectivity-business question |
| [rexi-product-discovery-appendix.md](rexi-product-discovery-appendix.md) | Rexi and official product-fact sources |
| [next-assignment.md](next-assignment.md) | The bounded next assignment |
| [research-notes/](research-notes/README.md) | The dated research notes behind the matrices, with every source |
| [decision-trail.tsv](decision-trail.tsv) | One row per decision and verification in this lane |
