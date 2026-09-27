# Interim access options

This file compares seven ways Argus could obtain user-authorized balances and transactions before Dominican banks offer consumer APIs. It weighs each option on the same criteria and says what each option still needs. The [legal and regulatory matrix](legal-regulatory-matrix.md) and the [bank access matrix](bank-access-matrix.md) hold the evidence behind the ratings.

## The seven options

**A. Direct institutional API or licensed aggregator.** A bank API needs an agreement with the bank. No public evidence shows a consumer-account API at any of the five candidate banks. No Dominican licensing or registration regime for aggregators is in force. The only aggregator found with a Dominican focus, Bridge Labs, S.R.L., uses credential-based access under its own terms and names no supported bank publicly. No foreign aggregator's own coverage pages name a Dominican institution. One third-party directory lists a Spanish aggregator, Wealthreader, as connected to Banreservas and Banco Popular, and neither bank confirms it.

**B. Import a transaction file the person downloads.** The person exports transactions from online banking as CSV, Excel, or OFX, then uploads or shares the file. The person's own bank session does the authentication. Argus never sees a credential.

**C. Share a statement into Argus.** The person shares a PDF statement from the bank's app, a saved e-statement, a screenshot, or a photo of a paper statement. This is the document path of MVEE sections 4.4 and 4.5.

**D. Forward a selected e-statement or notice.** The person forwards one statement email or one transaction alert to a personal Argus address. Argus never reads the mailbox. A statement can populate an account. An alert can only start a draft, because alerts are not a complete ledger.

**E. Extract in the person's own authenticated session.** After the person logs in and completes MFA on their own device, a browser extension or on-device helper reads the page or presses the bank's own export button. Argus never receives the credential. On iOS, one app cannot read another app's screen. On Android, the accessibility service can, but Google Play restricts that use by apps that are not accessibility tools and prohibits autonomous actions through it ([Use of the AccessibilityService API](https://support.google.com/googleplay/android-developer/answer/10964491), read 2026-09-27). This option therefore reaches the bank's website, not its app.

**F. Server-side credential-based aggregation.** Argus, or a provider on Argus's behalf, receives the bank username, password, and MFA codes, logs in from a server, and keeps a session for later refreshes. This is how early aggregators, including Plaid, reached most banks.

**G. Bank-approved tokenized access or another transitional arrangement.** A bank sanctions a narrower channel before a full API. Examples include a read-only token, scheduled delivery of statements to an address the customer names, a sandbox pilot, or participation in an official open-finance pilot. Every form needs the bank's agreement.

## Decision matrix

Ratings are relative within this table. "Unknown" means the evidence does not exist yet, not that the option is poor.

| Criterion | A. API or aggregator | B. File import | C. Statement share | D. Forwarded e-statement | E. In-session extraction | F. Server-side credentials | G. Bank-approved channel |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Person's effort | Low after connecting | Medium, per export | Medium, per statement | Low to medium, per email | Medium, per visit | Low after connecting | Low after setup |
| Likely refresh | Daily or better | Monthly, or when the person bothers | Monthly | Monthly statements, per-event alerts | Per visit | Daily or better | Depends on the bank |
| Completeness | What the source exposes | Full for the exported range | Full for the period when every page arrives | Full for statements, fragments for alerts | What the page shows | What the session shows | Agreed scope |
| Phone fit (Swift, Kotlin, web) | Provider widget. Bridge ships React and React Native SDKs, native SDKs in progress. | Share sheet and upload | Share sheet, camera, upload | Email client forward | Web only | Provider or Argus widget | Unknown |
| Credential or session exposure | With the provider, and with Argus for a per-user token | None | None | None. An e-statement password may appear. | None to Argus. Page contents leave the device. | Highest: Argus or its provider holds bank secrets | Scoped token |
| MFA interruption and lockout risk | Provider-dependent, unknown per bank | None | None | None | Low: the person is present | High: expiring sessions and security alerts | Low if the bank designs for it |
| Revocation and deletion | Provider API and provider retention. Bridge keeps data 30 days after revocation. | Delete the file and the imported records | Same as B | Same as B, plus the forwarding address | Uninstall, plus deletion | Must purge credentials, sessions, and data | Bank and Argus both revoke |
| Maintenance burden | Provider fixes connectors. Argus maps fields. | One parser per format and layout version | Higher: PDF layouts, scans, OCR | Same as C, plus inbound mail | High: every bank page change | Highest: every login, MFA, and page change | Low per connection, high to negotiate |
| Platform and institution restrictions | Bank terms on credential sharing still bind the person | None known | None known | Forwarding breaks the bank's email signature | Extension-store rules, bank terms, automated-access questions | Bank terms, automated-access questions, possible blocking | The bank's third-party and cybersecurity rules |
| What can be tested now | Bridge sandbox with fictional banks only | Synthetic files now. Real formats need consented files. | Same as B | Synthetic emails now | Synthetic HTML only | Nothing, by this lane's rules | Nothing without a bank |
| What it still needs | A provider agreement, a data processing agreement, a founder decision on holding per-user tokens, and legal review | Consented sample files, a retention decision, and the import contract | Same as B, plus OCR provider choice | Same as C, plus an inbound-email design | Legal review, bank terms review, and a founder decision | Legal opinion, credential custody design, bank terms review, and a founder decision | A bank agreement |

## What the matrix says

Options B and C are the bridge Argus can build now. They need no credential, no bank agreement, and no provider. They fit the approved ingestion flow, the synthetic kit, and the connector lifecycle experiment. Their weakness is freshness. A monthly statement cannot tell a person what they spent yesterday, so they complement manual and chat entry rather than replace it.

Option D is a convenience on top of C, not a separate strategy. Treat alerts as drafts only.

Option A is worth a bounded, founder-run test through Bridge's free developer plan, because it is the only route to daily refresh without building credential custody. A Bridge connection is still credential-based access. Argus would inherit the legal and terms questions of option F through its provider, plus a per-user token to store.

Option E is worth a legal question, not an engineering sprint. It avoids credential custody, but it reaches only the web and still meets bank terms and automated-access questions.

Option F is not worth pursuing now. The next section lists the conditions that could change that. Dominican history already shows its fragility. Salt Edge, a foreign aggregator, listed screen-scraping connectors for Popular and Banreservas from 2017 and for BHD by 2019, and had dropped every Dominican connector by July 2022, for reasons nobody has published.

Option G is the long-term route. It depends on the founder's institutional conversations and on the open-finance framework.

## When credential-based aggregation could become worth pursuing

Revisit option F, built by Argus or bought from a provider, only when every condition below holds.

1. Dominican counsel has answered the credential-sharing, unauthorized-access, banking-secrecy, and data-protection questions in the legal matrix for the specific design.
2. The target bank's current online-banking terms do not prohibit the access, or the bank has agreed to it.
3. The founder has decided that Argus, or a named provider, may hold revocable bank secrets, and a custody design has passed security review.
4. File and statement imports show refresh demand they cannot meet. For example, people import statements repeatedly and ask for fresher data, as the partnership evidence proposal measures.
5. A support budget exists for reconnection, lockouts, and bank security alerts.

## Where Scrapling fits

Scrapling is a BSD-3-Clause Python scraping framework. Its latest release, v0.4.15, dates from 2026-08-23. It is popular and active, has one dominant maintainer, and ships breaking changes in patch releases. Its selling points are fetchers that get past anti-bot systems: TLS fingerprint impersonation on by default, a stealth browser, a Cloudflare Turnstile solver, fingerprint noise, and proxy rotation. Those features are out of bounds for Argus.

Scrapling is relevant in two narrow cases.

- **HTML Argus already holds with consent.** Its parser, `scrapling.parser.Selector`, works offline on a saved page or the HTML body of a forwarded e-statement. `lxml` and BeautifulSoup do the same job. If Argus uses Scrapling's parser, pin the version, leave `adaptive` off, pass the encoding, and validate every amount. Adaptive relocation hides layout drift that a bank parser should report.
- **Public product and rate pages, where terms and robots rules allow.** Its spiders can crawl with robots rules on, no retry after a block, an honest User-Agent, and every impersonation default off. For a few dozen pages, an HTTP client with `lxml` is simpler to audit.

Scrapling is not relevant to the rest.

- It has no reader for CSV, Excel, OFX, or PDF statements. The standard library `csv`, `openpyxl`, `ofxtools`, and `pdfplumber` or `pdftotext` cover those.
- It adds nothing to aggregator APIs, which return JSON.
- For in-session extraction on the person's device, Playwright or a browser extension is the tool. Scrapling's browser wrappers add evasion defaults.
- A scraping library is not an aggregation platform. It provides none of the connection state machine, MFA relay, consent and revocation, secret custody, per-bank monitoring, normalization, deduplication, reconciliation, rate agreements, incident response, legal agreements, or support that option F needs.

The research note for this section read Scrapling's source at commit `333fa22b7a5821194ce66b59b11f4b16a6484f02` and installed nothing.

## Cost model

This model names cost drivers and formulas. It does not invent prices or reliability. Parameters marked "measure" stay unknown until a test or an agreement supplies them.

| Driver | Symbol | Known today | Applies to |
| --- | --- | --- | --- |
| Active people who import or connect | `N` | 0 | All |
| Refreshes or imports per person per month | `R` | Monthly for B, C, and D. Daily or better for A and F. | All |
| Institutions supported | `I` | 0 | All |
| Formats or page layouts per institution | `L` | Measure from consented files | B, C, D, E, F |
| Layout or login changes per institution per year | `Δ` | Measure | B, C, D, E, F |
| Engineer days to repair one change | `d` | Measure | B, C, D, E, F |
| Support contacts per 100 imports or refreshes | `s` | Measure | All |
| Provider price per active connection per month | `p` | Bridge's Developer plan is free for 3 live personal connections. Paid prices are unpublished. | A |
| Compute and storage per refresh | `c` | Small next to the above for files. Measure for browser automation. | All |
| Secret custody and security review | `K` | Required before A with stored tokens, and before F | A, F |
| Legal review | `G` | Required before A, E, F, and G | A, E, F, G |

Monthly running cost is roughly `N × R × c + N × p + N × R × s ÷ 100 × support cost + I × L × Δ ÷ 12 × d × engineer day cost`, plus the one-time costs `K` and `G`.

The model makes three points without any price.

1. Refresh frequency multiplies compute and support, not review. The experiment shows that daily refresh with weekly review costs the person the same 12 actions over 60 days as weekly refresh.
2. For B, C, and D, the dominant cost is `I × L × Δ × d`, parser upkeep per format. Start with one institution and its most structured export.
3. For F, the same term applies to login flows and MFA, and `K`, `G`, and support for lockouts come on top. Plaid's history, summarized in the Plaid lessons, shows that this term does not shrink with scale. Institutional APIs replaced it.
