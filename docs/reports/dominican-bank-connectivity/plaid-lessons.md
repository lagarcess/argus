# What Plaid's history teaches Argus

This file checks the early account-aggregation story against primary sources and keeps only the lessons that change Argus's plan. It is not a history of Plaid. Sources were read on 2026-09-27. Court orders, statutes, regulator publications, and a company's own announcements of its own actions count as verified. A company's statements about its scale or motives count as company claims. What a complaint alleged counts as an allegation, and a settlement is not a finding.

The report author re-read the final approval order in Cottle v. Plaid and JPMorgan Chase's 2018 announcement directly. The rest comes from the research note's reading of the cited primary sources.

## The supplied narrative, checked

The three supplied pages are Plaid's own: [the 2021 post on safe data access](https://plaid.com/blog/setting-the-standard-for-safe-and-secure-data-access/), [the 2025 post on ten years of Link](https://plaid.com/blog/ten-years-plaid-link/), and [the homepage](https://plaid.com/).

- **Link dates from 2015.** Verified. The original Link repository on GitHub was created on 2015-04-10.
- **Plaid spared developers from storing credentials.** Partly verified. Credentials moved from each app to Plaid, not out of the chain. The settlement class covers people whose credentials Plaid obtained through Link from 2013-01-01 to 2021-11-19, about 98 million people. The security benefit is a company claim.
- **Link gave consumers choice and transparency.** Disputed. Plaintiffs alleged that Link's credential screens used bank logos and colors so people thought they were logging in to their bank. The court let an anti-phishing claim proceed on those allegations. The settlement requires the credential screen to say credentials go to Plaid and forbids the bank's color scheme. No court found wrongdoing.
- **Scale figures.** Company claims. "Half of Americans", "12,000 institutions", and "one million daily connections" have no independent source. The court notice's figure of about 5,000 apps probably came from Plaid.
- **Open-banking rules were on the horizon in 2021.** Verified that a rule came. The US Section 1033 rule issued on 2024-10-22, a federal court enjoined its enforcement on 2025-10-29, and the regulator's August 2026 agenda still lists a reconsideration with no proposed rule.

## What the history shows

| Date | Event | Evidence |
| --- | --- | --- |
| 2013 | Plaid's API exists. Early apps collected bank logins and passed them to Plaid, according to later allegations. | GitHub metadata. [Order on the motion to dismiss](https://www.govinfo.gov/content/pkg/USCOURTS-cand-4_20-cv-03056/pdf/USCOURTS-cand-4_20-cv-03056-1.pdf), allegations only |
| 2016-10-19 | Plaid publishes a primer that separates screen scraping and OFX from OAuth. | Plaid's own document |
| 2018-10-22 | JPMorgan Chase and Plaid agree on a token-based API, so Plaid downloads data without storing usernames and passwords. | [Chase announcement](https://media.chase.com/news/plaid-signs-data-agreement-with-jpmc), re-read by the report author |
| 2020-07 | Five class actions against Plaid are consolidated as Cottle v. Plaid. | Court order |
| 2021-04-30 | Privacy, anti-phishing, deceit, and unjust-enrichment claims survive dismissal. Federal computer-fraud and stored-communications claims are dismissed. | [Order on the motion to dismiss](https://www.govinfo.gov/content/pkg/USCOURTS-cand-4_20-cv-03056/pdf/USCOURTS-cand-4_20-cv-03056-1.pdf) |
| 2022-07-20 | Final approval of a USD 58 million non-reversionary settlement, with 1,256,738 claim forms and a claims rate of 1.28%. Plaid denies wrongdoing. | [Final approval order, Dkt. 184](https://www.govinfo.gov/content/pkg/USCOURTS-cand-4_20-cv-03056/pdf/USCOURTS-cand-4_20-cv-03056-4.pdf), re-read by the report author. [Court-approved notice](https://angeion-public.s3.amazonaws.com/www.PlaidSettlement.com/docs/Long+Form+Notice.pdf) |
| 2023-05-11 | Plaid says 75% of connections run over APIs, and all traffic for Capital One, Chase, USAA, and Wells Fargo. | [Plaid update](https://plaid.com/blog/api-progress-update/), company claim |
| 2024-10-22 | The US regulator issues the Section 1033 rule. Its 2022 data showed about half of third-party access attempts still used screen scraping. | [Final rule, 89 FR 90838](https://www.federalregister.gov/documents/2024/11/18/2024-25079/required-rulemaking-on-personal-financial-data-rights) |
| 2025-04-25 | The Financial Data Exchange reports 114 million connections over its API standard and says tens of millions of people still share login credentials. | [FDX post](https://financialdataexchange.org/fdx-feed/114-million-reasons-to-keep-moving-forward-on-industry-led-standard-for-secure-data-sharing/), industry claim |
| 2025-09-16 | JPMorganChase and Plaid extend their agreement with an undisclosed pricing structure. | [Chase announcement](https://media.chase.com/news/jpmorganchase-plaid-extend-data-access-agreement) |
| 2025-10-29 | A federal court enjoins enforcement of the Section 1033 rule until the regulator finishes reconsidering it. | [E.D. Ky. order](https://www.govinfo.gov/content/pkg/USCOURTS-kyed-5_24-cv-00304/pdf/USCOURTS-kyed-5_24-cv-00304-1.pdf) |
| 2026-03-26 | Canada enacts a new Consumer-Driven Banking Act with a screen-scraping prohibition that starts by order. | [Bill C-15](https://www.parl.ca/legisinfo/en/bill/45-1/c-15) |
| 2026-09-25 | Chase launches a page where customers see and unlink connected apps. | [Chase announcement](https://media.chase.com/news/chase-launches-data-security-center) |

## Regimes differ, so no foreign model predicts the Dominican one

| Jurisdiction | Treatment of credential-based scraping on 2026-09-27 | Who may receive account data |
| --- | --- | --- |
| United States | Not banned. The 2024 rule, now enjoined, barred banks from meeting it through scraping. | No licence. The rule relied on third-party certification. |
| European Union | Not banned outright. Providers must identify themselves in every session, and customer-interface access survives only as a fallback when a bank's dedicated interface fails. | Registered account-information providers with indemnity insurance |
| United Kingdom | Dedicated interfaces are mandatory for key accounts. | Registered account-information providers |
| Australia | Not banned. A 2022 review recommended a ban. The 2023 government response did not adopt it. | Accredited data recipients |
| Brazil | The open-finance resolution does not address scraping. | Authorized institutions only |
| Mexico | Article 76 of the Ley Fintech requires APIs and does not address scraping. | Unknown under secondary rules |
| Chile | No general ban. Existing credential-based payment initiators had to register. | Registered providers |
| Canada | Enacted prohibition, starting once the framework operates | Accredited participants |
| Dominican Republic | No rule on account information. Payment-initiation providers may not store users' credentials. | No role defined for account information |

The legal and regulatory matrix holds the Dominican sources.

## Lessons that change Argus's plan

1. **Credential access was a bootstrap, and leaving it took about a decade.** Chase signed a token API with Plaid in 2018. Plaid claimed 75% API traffic only in 2023. The US regulator still saw about half of access attempts scraped in 2022. Argus should record the access method per connection, so one bank can move from files to a token or API without touching records. The experiment's `retrieval_method_migration` check shows that move.
2. **Liability followed the screen and the data scope, not credential use alone.** The claims that survived dismissal attached to a login screen that allegedly imitated banks and to collecting more than apps needed. Argus must never imitate a bank's interface, must name every party that receives a credential, and must take consent before any credential field appears.
3. **Collect only what the feature needs, and make deletion real.** The settlement forced deletion of data apps never requested and limited storage to requested categories. Argus should record, per connection, what was requested, why, and until when.
4. **People expect one place to see and cut off connections.** Plaid's data-control portal became a settlement term, and Chase launched a connected-apps page on 2026-09-25. A connections page with revoke and delete belongs in the first version of any connection feature, and revocation must stop collection at the source.
5. **The person may carry the loss when credentials are shared.** Banco BHD's 2026 contract model makes access codes personal and non-transferable, and US Regulation E treats transfers by someone the consumer gave an access device to as authorized. Argus cannot quietly move that risk onto users. File import avoids it.
6. **An API is not free access.** Chase's 2025 renewal with Plaid includes pricing. The US regulator is asking whether banks may charge. Chile lets banks recover incremental costs above volume thresholds. A Dominican bank partnership may carry fees.
7. **Consent needs scope and an expiry from day one.** The US rule capped collection at one year without reauthorization. The UK moved re-confirmation to the third party every 90 days. The EU uses a 180-day cycle. Chile requires consent that names data type, purpose, and maximum validity.
8. **Licensing follows the data recipient.** The European Union, the United Kingdom, Australia, Brazil, Chile, and Canada register or accredit whoever receives account data. The United States relied on certification instead, and its rule is enjoined. If the Dominican Republic adopts open finance, Argus should expect a registration duty. Nothing requires one today.
9. **Security duties come with holding data.** The US Safeguards Rule requires a written security program and breach reporting, and the US regulator names credential exposure in third-party breaches as the core risk of scraping. Before Argus holds any bank secret, it needs custody design, access logs, and a tested breach response.
10. **A broken connection is a normal state, even on APIs.** Plaid's [public status history](https://status.plaid.com/api/v2/incidents.json) lists 25 incidents from 2026-06-05 to 2026-09-26, and 10 of them name a single institution, including banks Plaid reaches by API. Re-consent also loses people. In the US regulator's 2023 proposal, a commenter reported that only 0.32% of users asked to reconnect did so. Argus needs per-connection states, visible data age, and success rates per institution before it runs any connection. The experiment's state machine and freshness checks model that.

## Open questions the research could not settle

- Whether anyone appealed the Plaid settlement, and when its three-year business-practice terms ended. The dockets returned HTTP 403.
- The outcome of Clark v. Yodlee after March 2025.
- The content and timing of the US Section 1033 reconsideration, the final EU payment-services texts, and whether Canada's prohibition is in force.
- The contents of Colombia's Decree 1297 of 2022, which is a scan without a text layer.
