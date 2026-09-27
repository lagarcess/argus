# U1. Plaid and early account aggregation, checked against primary sources

Research unit for Argus. Scope is the early credential-based aggregation model (Plaid and its predecessors), what changed, and which lessons matter for an app whose first users live in the Dominican Republic and whose banks do not yet offer APIs. Dominican law and Dominican bank specifics belong to other units; this file only uses one Dominican bank contract as an example in section E.

All sources were accessed on 2026-09-27. Every claim carries a source ID (S1, S2, ...). The full source list, with URL, publisher, title, publication date and effective date, is at the end.

## Labels

- VERIFIED. I read the primary source: a court order or court-approved notice, a statute or gazette, a regulator's publication, or a company's own document for what that company itself did or announced.
- COMPANY CLAIM. A company's statement about its own scale, performance or motives that no independent source confirms.
- SECONDARY. Press, law-firm or tracker reporting. Used only where no primary source was reachable, and marked.
- ALLEGATION. What a complaint alleged. A ruling on a motion to dismiss assumes the allegations are true and decides nothing about them.
- INFERENCE. My own reasoning from the cited facts.
- UNKNOWN. I could not establish it.

## Method notes and blocks

- The session's shared web-search budget ran out after this unit's fifth query. Everything after that came from direct navigation of primary publishers (official APIs, sitemaps and document indexes), not from a search engine.
- CourtListener and Justia dockets returned HTTP 403, so docket entries after the published orders could not be read. The court's own opinions came from GovInfo.
- EUR-Lex returned an empty anti-bot response (HTTP 202). EU texts were read from the EU Publications Office (CELLAR), which serves the same Official Journal text.
- The ACCC website returned HTTP 403. The Plaid settlement website (plaidsettlement.com) no longer resolves in DNS; its court-approved notice survives on the administrator's file host (S7).
- Colombia's Decree 1297 of 2022 is a scanned PDF with no text layer, so I verified its date and title but not its contents.
- No sign-ins, forms, account creation or downloads of executables. PDFs were streamed and read, apart from one notice the fetch tool cached on its own.

## A. Verified timeline

| Date | Event | Label | Source |
|---|---|---|---|
| 1999-02 | Yodlee is incorporated in Delaware as Yodlee.com, Inc. | VERIFIED (company filing) | S67 |
| 2007-09 | Mint.com launches. | VERIFIED (Intuit) | S68 |
| 2009-09-14 | Intuit agrees to buy Mint.com for about USD 170 million; Mint has over 1.5 million users. Press reports Mint relied on Yodlee for much of its bank data. | VERIFIED; SECONDARY (Yodlee role) | S68, S69 |
| 2013-03-25 | Plaid's Node client library repository is created on GitHub, so a Plaid API existed in early 2013. Plaid says it launched in 2013. | VERIFIED (metadata); COMPANY CLAIM (launch year) | S39, S29 |
| 2014-06-30 | Yodlee files its S-1. Over 75 percent of its data comes through structured feeds under contracts with its bank customers; elsewhere it uses its own gathering techniques and names scraping as a costlier fallback. | VERIFIED (company filing) | S67 |
| 2015-04-10 to 2015-06-05 | Plaid's Link repository is created (2015-04-10). An invitation-only beta called "Project CSA" sends credentials straight to Plaid and handles MFA (README 2015-04-16); by 2015-06-05 it is named Plaid Link. This corroborates Plaid's statement that Link was introduced in 2015. | VERIFIED | S39, S70, S1, S2 |
| 2015 (late) | Several large US banks take actions that temporarily disrupt screen scraping, per the CFPB. | VERIFIED (CFPB statement) | S74 |
| 2016 (about) | Plaintiffs later allege that for Plaid's first years, apps collected users' bank logins and passed them to Plaid, and that around 2016 Plaid moved to a Managed OAuth flow with login screens that looked like each bank's. | ALLEGATION | S4 |
| 2016-10-19 | Plaid publishes a primer separating data transmission (screen scraping, OFX) from authentication (OAuth). | VERIFIED (company document) | S37 |
| 2017-01-25 | JPMorgan Chase and Intuit announce a data-sharing agreement. | VERIFIED (title and date from Chase newsroom listing; body not read) | S28 |
| 2017-02-02 | UK CMA publishes the Retail Banking Market Investigation Order 2017, which set the open banking timetable for the largest banks. | VERIFIED | S47 |
| 2017-10-18 | CFPB publishes consumer protection principles for consumer-authorized data sharing and aggregation, after a 2016 request for information. | VERIFIED | S17 |
| 2017-11-27 | European Commission adopts the RTS on strong customer authentication and secure communication (Delegated Regulation (EU) 2018/389), published in the Official Journal on 2018-03-13 and applicable from 2019-09-14. | VERIFIED | S41 |
| 2018-01-13 | PSD2 transposition deadline. Its account-access security articles apply 18 months after the RTS entered into force. | VERIFIED | S42 |
| 2018-03-09 | Mexico publishes the Ley para Regular las Instituciones de Tecnologia Financiera, whose article 76 requires standardized APIs. | VERIFIED | S56 |
| 2018-10-22 | JPMorgan Chase and Plaid announce a data agreement. Plaid is to reach Chase data through Chase's API with tokens instead of stored credentials, with migration from the first half of 2019. | VERIFIED | S24, S25 |
| 2019-08-12 | Australia's Consumer Data Right Act is made (Treasury Laws Amendment (Consumer Data Right) Act 2019). | VERIFIED | S51 |
| 2019-12-05 | JPMorgan Chase and Envestnet Yodlee announce a data agreement. | VERIFIED (title and date from Chase newsroom listing) | S28 |
| 2020-01-13 | Visa announces its plan to acquire Plaid for USD 5.3 billion. | VERIFIED (as reported by DOJ) | S8 |
| 2020-02-04 | Australia's CDR Rules 2020 are made. | VERIFIED | S51 |
| 2020-05-04 | Brazil's central bank and National Monetary Council adopt Joint Resolution No. 1 on open banking (published 2020-05-05). | VERIFIED | S55 |
| 2020-07 | Five putative class actions against Plaid are consolidated in N.D. Cal. (case 4:20-cv-03056). | VERIFIED | S4 |
| 2020-10-14 | TD Bank announces a trademark counterfeiting and infringement suit against Plaid (cited by the CFPB). | VERIFIED (citation); ALLEGATION (content) | S74 |
| 2020-11-05 | DOJ sues to block Visa's acquisition of Plaid in N.D. Cal. The complaint describes Plaid logging in to banks with the credentials consumers give apps. | VERIFIED; ALLEGATION (complaint) | S8, S71 |
| 2020-11-19 | Plaid sets a goal of 75 percent of its traffic on APIs by the end of 2021. | COMPANY CLAIM (goal) | S29 |
| 2020-12-23 | American Banker reports that PNC sued Plaid for trademark infringement (cited by the CFPB). | SECONDARY, cited by CFPB | S74 |
| 2021-01-12 | Visa and Plaid terminate the merger agreement. | VERIFIED | S8 |
| 2021-04-30 | Court rules on Plaid's motion to dismiss in Cottle v. Plaid. Privacy, anti-phishing, deceit and unjust enrichment claims survive; federal computer and stored-communications claims, the UCL claim, the state computer-access claim and the claim for declaratory and injunctive relief are dismissed with prejudice. | VERIFIED | S4 |
| 2021-07-09 | Executive Order 14036 encourages the CFPB to consider a Section 1033 rulemaking. | VERIFIED | S18 |
| 2021-11-19 | Court grants preliminary approval of the USD 58 million Plaid settlement. | VERIFIED | S5 |
| 2021-11-29 | UK FCA publishes PS21/19, replacing bank re-authentication every 90 days with third-party reconfirmation and mandating dedicated interfaces for key accounts. | VERIFIED | S46 |
| 2021-12-09 | FTC amends the GLBA Safeguards Rule (86 FR 70272). | VERIFIED | S20 |
| 2022-01-25 | Plaid announces Plaid Portal (my.plaid.com), where US users can see connected apps and data types, disconnect apps and delete data. | VERIFIED (company announcement) | S85, S36 |
| 2022-03-26 | UK SCA-RTS amendments for account information (new exemption and 90-day third-party reconfirmation) come into force. | VERIFIED | S46 |
| 2022-07-20 | Court grants final approval of the Plaid settlement. | VERIFIED | S6 |
| 2022-07-25 | Colombia issues Decree 1297 of 2022 on open finance ("finanzas abiertas"). | VERIFIED (date and title only) | S57 |
| 2022-09-29 | Australia releases the statutory review of the CDR, which recommends banning screen scraping where the CDR is a viable alternative. | VERIFIED | S52 |
| 2023-01-04 | Chile publishes Ley 21.521 (Ley Fintec), which creates an open finance system (promulgated 2022-12-22). | VERIFIED | S58 |
| 2023-01-12 | UK CMA publishes its decision on completion of the open banking roadmap. | VERIFIED | S48 |
| 2023-01-25 | Plaid tells the CFPB that more than 60 percent of its traffic is on APIs, and asks that third parties be allowed to fall back to scraping during bank API outages. | COMPANY CLAIM; VERIFIED (letter content) | S73, S30 |
| 2023-05-11 | Plaid says 75 percent of connections run over APIs and that all of its traffic for Capital One, JPMorgan Chase, USAA and Wells Fargo has moved to APIs. | COMPANY CLAIM | S31 |
| 2023-05-26 | UK dedicated-interface mandate (amended SCA-RTS article 31) comes into force. | VERIFIED | S46 |
| 2023-06-07 | Australian Government "notes" the scraping-ban recommendation and commits to consult on regulating screen scraping. | VERIFIED | S53 |
| 2023-06-09 | Main new FTC Safeguards Rule requirements take effect. | VERIFIED | S20 |
| 2023-06-28 | European Commission proposes PSD3, the Payment Services Regulation and FIDA. | VERIFIED | S44, S45 |
| 2023-07-25 | EU amendment replacing 90-day bank re-authentication for account information with a 180-day cycle applies. | VERIFIED | S43 |
| 2023-10-19 | CFPB releases the 1033 proposal with aggregator data: scraping fell from 80 to 50 percent of access attempts between 2019 and 2022, and only 5 to 10 percent of data providers offered credential-free APIs at the end of 2022. | VERIFIED | S74 |
| 2023-12-21 | Plaid says American Express and TD Bank signed data access partnerships with it. | COMPANY CLAIM | S32 |
| 2024-01-02 | Plaid says about 75 percent of its traffic is "on or committed to" APIs, a wider measure than its 2023 figure. | COMPANY CLAIM | S76 |
| 2024-02-07 | Colombia's Superintendencia Financiera launches the second phase of its open finance model under Circular Externa 004 of 2024. | VERIFIED (SFC description; circular text not read) | S66 |
| 2024-05-13 | FTC Safeguards Rule breach-notification requirement takes effect. | VERIFIED | S20 |
| 2024-06 | Canada's first Consumer-Driven Banking Act passes. | VERIFIED (per Finance Canada) | S60 |
| 2024-07-03 | Chile's CMF issues NCG 514, the implementing rule for the open finance system. | VERIFIED | S59 |
| 2024-09-10 | Plaid says 80 percent of its traffic is on or committed to APIs and that it completed migrations with Citi and Navy Federal in 2024. | COMPANY CLAIM | S76 |
| 2024-10-22 | CFPB issues the Section 1033 final rule. Banks and trade groups sue the same day in E.D. Ky. Plaid says 80 percent of its network is on or committed to APIs. | VERIFIED; COMPANY CLAIM (80 percent) | S9, S12, S33 |
| 2024-12-10 | Plaid completes the rollout of passkeys for returning Link users on iOS. | VERIFIED (company docs) | S77 |
| 2025-01-08 | CFPB approves the Financial Data Exchange (FDX) as a recognized standard setter. | VERIFIED | S16 |
| 2025-04-25 | FDX reports 114 million customer connections over FDX-aligned APIs and says tens of millions of people still share login credentials. | COMPANY CLAIM (FDX) | S40 |
| 2025-05-14 | The Kentucky court lets the Financial Technology Association intervene to defend the 1033 rule, after staying the case while the CFPB reviewed its position. | VERIFIED | S11 |
| 2025-06-19 | UK Data (Use and Access) Act 2025 is enacted. | VERIFIED | S50 |
| 2025-07-29 | CFPB asks the Kentucky court to stay the case because it will reconsider the rule; it had earlier told the court the rule is unlawful. | VERIFIED | S12 |
| 2025-08-13 | Executive Order 14337 revokes Executive Order 14036. | VERIFIED | S19 |
| 2025-08-22 | CFPB publishes an advance notice of proposed rulemaking to reconsider the 1033 rule, including whether data access costs can be shared. | VERIFIED | S10, S12 |
| 2025-09-16 | JPMorganChase and Plaid announce an extension of their data access agreement that includes a pricing structure; terms are not disclosed. | VERIFIED | S26 |
| 2025-10-21 | Plaid files its ANPR comment, arguing that Section 1033 does not allow banks to charge for data access. | VERIFIED (company position) | S34 |
| 2025-10-29 | E.D. Ky. enjoins the CFPB from enforcing the 1033 rule until it completes its reconsideration. | VERIFIED | S12 |
| 2025-11-06 | Finance Canada publishes the Budget 2025 framework. The Bank of Canada is to oversee consumer-driven banking, and a screen-scraping ban is to take effect once the framework is fully operational. | VERIFIED | S61 |
| 2026-02 to 2026-10 | Bank of America moves Plaid to a new API. New connections use it from February to mid-March 2026; existing connections are cut over from mid-March to late October 2026 and must be reconnected by the user. | VERIFIED (company docs) | S75, S77 |
| 2026-03-26 | Canada's Budget 2025 Implementation Act, No. 1 (Bill C-15) receives Royal Assent. It enacts a new Consumer-Driven Banking Act, most of it in force the same day. Its screen-scraping prohibition (section 171) is still not in force as of the 2026-09-03 consolidation. | VERIFIED | S62, S64 |
| 2026-05-05 | European Parliament committee approves the texts agreed with the Council for PSD3 and the Payment Services Regulation. Plenary vote is forecast for 2026-12-14. | VERIFIED | S45 |
| 2026-06-05 to 2026-09-26 | Plaid's status page records 25 incidents, ten naming a single institution, including major disruptions at Bank of America, Wells Fargo and Chase connections. | VERIFIED | S82 |
| 2026-06-24 | Dominican Superintendencia de Bancos approves the Banco BHD personal account contract model used as the example in section E. | VERIFIED | S23 |
| 2026-08-06 | A law-firm blog reports that the CFPB sent a 1033 reconsideration proposal to OIRA for review. | SECONDARY | S15 |
| 2026-08-14 | CFPB's regulatory agenda lists a rulemaking to reconsider the 1033 rule. No proposed rule appears in the Federal Register as of 2026-09-27. | VERIFIED | S13, S14 |
| 2026-09-25 | Chase launches a Data Security Center where customers see and unlink connected apps. | VERIFIED | S27 |

### A.2 How the connections worked, and how they break

Access methods:
- Yodlee, incorporated in February 1999, told investors in 2014 that over 75 percent of its data came through structured feeds under contracts with its bank customers, that it used its own "information-gathering techniques" elsewhere, and that if sources restricted access it might have to fall back on costlier user-permissioned scraping. It added that some airline and international sites had blocked it or asked it to stop scraping (S67, company filing). Its model therefore rested on contracts with the banks it sold to, unlike Plaid's (INFERENCE).
- Mint launched in September 2007 and had over 1.5 million users when Intuit agreed to buy it for about USD 170 million on 2009-09-14 (S68, VERIFIED). Press reported that Yodlee supplied much of Mint's bank data (S69, SECONDARY).
- Plaid's first Link module ("Project CSA", invitation-only beta, README of 2015-04-16) sent bank credentials from the user straight to Plaid over HTTPS and returned a token to the app; it was renamed Plaid Link by 2015-06-05 (S70, VERIFIED).
- DOJ's 2020 complaint states that when a consumer gives a Plaid-supported app her bank log-in credentials, Plaid uses them to access the bank and retrieve data. It counts over 2,600 apps, more than 11,000 US institutions and over 200 million accounts (S71, allegation-level description in a complaint).
- Plaid's current End User Privacy Policy (effective 2025-12-08) lists "login data" it may collect (username and password, account and routing number, or a security token) plus security questions, answers and one-time passwords, and says providing them authorizes Plaid to act on the user's behalf. It does not say whether or how Plaid stores credentials (S72, VERIFIED).
- The court-approved settlement notice separates three methods. In credential access Plaid logs in with the user's credentials. In Managed OAuth Plaid receives credentials but trades them for a token under a bank agreement and does not store them. In OAuth the user logs in on the bank's own domain and Plaid never sees the credentials (S7, VERIFIED).
- CFPB data from large aggregators show the shift. Screen scraping fell from 80 percent of access attempts in 2019 to 50 percent in 2022, credential-based APIs rose from 20 to 27 percent, and credential-free APIs rose from under 1 percent (2019 and 2020) to 9 percent (2021) and 24 percent (2022). At the end of 2022 only 5 to 10 percent of all data providers offered credential-free APIs (S74, VERIFIED).
- Plaid's OAuth guide today says OAuth is universal in the UK and EU, used by a number of mostly larger US institutions, and not used in Canada. Its docs still describe credential-based Items (S75, S80, VERIFIED).
- Plaid reports moving all traffic for Capital One, JPMorgan Chase, USAA and Wells Fargo to APIs by May 2023 and for Citi and Navy Federal in 2024 (S31, S76, COMPANY CLAIM). Bank of America is moving Plaid to a new API during 2026, and existing connections are being disconnected from mid-March to late October 2026 unless users reconnect (S75, S77, VERIFIED).

MFA:
- Plaid's legacy API answered HTTP 201 when a bank demanded MFA and supported three types: security questions, a list of devices to send a code to, and selections. Apps relayed answers through `connect_step` (S78, VERIFIED).
- From 2015, Link handled MFA inside Plaid's own module (S70). Plaid still lists MFA-related errors such as `INVALID_MFA`, `MFA_NOT_SUPPORTED` and `ITEM_LOCKED`, and warns that banks may lock an account after three to five failed attempts (S79, VERIFIED).

Reconnection today (Plaid docs, read 2026-09-27, VERIFIED):
- `ITEM_LOGIN_REQUIRED` fires when, at a non-OAuth bank, the user changed the password or MFA settings or MFA expired; when the bank moved to OAuth; when OAuth consent expired or was revoked; or when a duplicate Item was created (S79).
- Update mode repairs those states without changing the access token, uses an abbreviated re-authentication where it can, and resets the consent expiry as if the connection were new (S80).
- `PENDING_EXPIRATION` warns seven days before consent expires for UK and EU banks; `PENDING_DISCONNECT` does the same for US and Canadian banks. `LOGIN_REPAIRED` fires when the user fixed the connection in another app. `USER_PERMISSION_REVOKED` and `NEW_ACCOUNTS_AVAILABLE` report consent changes (S81). Chase stopped supporting account-level revocation events in September 2025 (S77).
- European consent typically lasts 180 days. In the US, American Express, Bank of America (new API), Capital One, Charles Schwab, Chase (user picks 6 months, 1 year or always), Citibank, Fidelity, Navy Federal, PNC and TD Bank require renewal every 12 months, with Brex and Revolut at 3 months and USAA at 18 months (S75).
- Re-consent costs users. In the CFPB's 2023 proposal, one small firm reported that only 0.32 percent of users asked to reconnect did so, and UK trade associations estimated 20 to 40 percent and 35 to 87 percent attrition under the UK's old 90-day rule (S74, figures reported to the CFPB by commenters).

Health reporting and outages:
- Plaid's public status page listed 25 incidents between 2026-06-05 and 2026-09-26. Ten name a single institution: Bank of America twice (both "major"), Wells Fargo three times (two "major"), Chase once ("major"), Navy Federal twice, Chime once, and delayed Capital One transaction updates once (S82, VERIFIED). Most of these banks are ones Plaid says it reaches through APIs (S31, S75, S76), so API connections also fail (INFERENCE).
- The Institutions API still returns a per-institution status for logins, transaction updates and other products. It breaks each down into success, Plaid-error and institution-error rates plus a refresh interval, and lists health incidents; the older HEALTHY, DEGRADED and DOWN field is deprecated (S83, VERIFIED). Error codes separate a bank that is down, one that is responding partially, and planned downtime on Plaid's side (S84, VERIFIED). Plaid reworked the Dashboard's institution status page in June 2026 (S77).
- Scraping is less reliable. In 2022, 40 percent of first connection attempts made by scraping succeeded, against 51 percent through bank interfaces for third parties (S74, VERIFIED).
- Keeping scrapers alive is recurring work. An MX post (2020-08-04) says firms that scrape must constantly fix connections broken by website updates and lose connectivity when the site is down (S88, COMPANY CLAIM). Bank commenters told the CFPB that detecting and blocking scraping takes significant resources even for large banks (S9). Several large US banks disrupted scraping in late 2015 (S74, VERIFIED as a CFPB statement). Plaid asked the CFPB to set a 99.9 percent uptime safe harbor for bank APIs and to allow fallback to scraping during API outages (S73, VERIFIED).
- I collected no forum or user anecdotes; every item above is documentary.

## B. Claims in the three supplied Plaid pages

The three pages are Plaid's own publications: S2 (2021-07-15), S1 (2025-05-22) and the homepage S3 (read 2026-09-27). Each claim was checked against a source Plaid does not control where one exists.

| # | Claim (page) | Independent check | Status |
|---|---|---|---|
| B1 | Early fintech required consumers to give their online banking passwords to every app, and Plaid spared developers from storing or managing credentials (S2). | Court records show Plaid itself received users' bank credentials at scale. The settlement class covers US residents whose accounts Plaid accessed or whose credentials Plaid obtained through Link from 2013-01-01 to 2021-11-19, about 98 million people (S6, S7). DOJ described Plaid logging in with the credentials users gave apps (S71), and Plaid's privacy policy still lists passwords, security answers and one-time passwords among the data it may collect (S72). | Verified that credentials moved from apps to Plaid, not out of the chain. The security benefit is a company claim. |
| B2 | Plaid Link was created in 2015 (S2, S1). | GitHub metadata shows the original Link repository created 2015-04-10 (S39). | Verified. |
| B3 | In 2021 Plaid connected over 11,000 institutions to more than 5,000 apps in the US, Canada, the UK and Europe (S2). | DOJ's complaint of 2020-11-05 counted more than 11,000 US institutions, over 2,600 apps and over 200 million accounts (S71). The court-approved notice of late 2021 says about 5,000 apps (S7). | Consistent with DOJ and the court notice, though both figures likely came from Plaid (INFERENCE). The app count roughly doubled between November 2020 and July 2021 if both are right. |
| B4 | A July 2021 Executive Order opened a new era for US digital finance (S2). | EO 14036 (signed 2021-07-09) encouraged the CFPB to consider a 1033 rulemaking (S18). EO 14337 revoked it on 2025-08-13 (S19). | Verified for 2021, since superseded. |
| B5 | Open banking rules were coming soon (S2). | The CFPB issued the rule in October 2024 (S9), but a court enjoined enforcement on 2025-10-29 and the CFPB is rewriting it (S12, S13). | Verified that a rule came; as of 2026-09 it has no force. |
| B6 | Link gave consumers choice and transparency and set a new expectation about how and with whom data is shared (S2). | Plaintiffs alleged that Link's credential screens used bank logos and colors so users thought they were logging in to their bank (S4). The court let an anti-phishing claim proceed on those allegations (S4). The settlement, which contains no finding, requires the credential pane to say credentials are provided to Plaid and not to use the bank's color scheme (S7). | Company claim, disputed by allegations. No court finding either way. |
| B7 | Venmo, Betterment and Microsoft Money in Excel use Plaid Link (S2). | Court orders recite, as plaintiffs' allegations, that Venmo, Coinbase, Cash App and Stripe use Plaid (S4). Betterment and Money in Excel not checked. | Venmo corroborated at allegation level; the rest unknown. |
| B8 | Link has been used by more than half of Americans with bank accounts (S1). The homepage says 1 in 2 banked US adults use Plaid (S3). | A September 2025 Plaid post says over 150 million consumers (S35). The only court figure is about 98 million class members through 2021 (S6). | Company claim only. |
| B9 | 7,000+ companies connect to 12,000+ institutions (S1); 12,000 institutions across 20 countries (S3). | None found. | Company claim only. |
| B10 | Link starts 750,000 connections a day (S1, May 2025); homepage says over one million daily connections (S3, 2026). | None found. The two figures differ by date and possibly by definition. | Company claim only. |
| B11 | 76 percent of consumers prefer apps they can sign up for instantly (S1). | Source is Plaid's own report, The Fintech Effect. | Company claim (company-commissioned survey). |
| B12 | Opted-in returning users convert 11 percent higher; phone pre-fill, skip-to-OTP and a combined consent and phone pane are live; pre-initialized Link loads up to 5x faster (S1). | None found. | Company claim only. |
| B13 | Plaid blocked nearly 3 million fraudulent requests in 2024 and uses device, SIM and carrier signals (S1). | None found. | Company claim only. |
| B14 | Link now supports passkeys (S1). | Plaid's docs record full rollout on 2024-12-10 for returning users on iOS, who can use Face ID or Touch ID after an earlier bank login through Link (S77, S87). No independent source. | Company documentation only. These passkeys sign the user in to Plaid's returning-user flow, not to the bank (INFERENCE from the docs' wording). |
| B15 | Link analytics show funnel steps including institution search and a "Submit Credentials" step (S1). | The CFPB found that about half of third-party access attempts in its 2022 aggregator data used screen scraping (S9). FDX said in April 2025 that tens of millions still share credentials (S40). | Verified that a credential-submission step still exists in Link in 2025 (company document). That it is common is an INFERENCE supported by S9 and S40. |
| B16 | Users control who has access, and Plaid Portal lets them manage connections and delete data (S3). | The court-approved notice describes Portal at my.plaid.com with views of shared data types, disconnection and deletion, and the settlement required a prominent homepage reference (S7). The homepage links to Portal today (S3). | Portal features verified as of 2022. "In control" is a company claim. |
| B17 | 25 percent higher onboarding conversion (S3). | Baseline not stated. | Company claim only. |
| B18 | Core Exchange offers institutions API connectivity aligned with industry standards (S3). | Plaid describes it as FDX-aligned (S31, S38). The CFPB recognized FDX as a standard setter on 2025-01-08 (S16). | FDX alignment is a company claim; FDX recognition is verified. |

## C. Litigation and privacy: facts versus allegations

### C1. Cottle et al. v. Plaid Inc. (In re Plaid Inc. Privacy Litigation), N.D. Cal. No. 4:20-cv-03056-DMR

Facts from court records (VERIFIED):

- Court and judge. Northern District of California, Magistrate Judge Donna M. Ryu. Five separately filed putative class actions, consolidated in July 2020, with eleven named plaintiffs from five states and the District of Columbia (S4, S6).
- Motion to dismiss. Heard 2021-02-11, decided 2021-04-30 (Dkt. 125, reported at 536 F. Supp. 3d 461). Claims that survived: intrusion into private affairs, the California constitutional right to privacy, the California Anti-Phishing Act of 2005, deceit under California Civil Code 1709 and 1710, and unjust enrichment as quasi-contract. Dismissed with prejudice: the Computer Fraud and Abuse Act, the Stored Communications Act, the Unfair Competition Law (no lost money or property alleged), California's computer data access law, and the claim for declaratory and injunctive relief (S4).
- Preliminary approval. Hearing 2021-09-30, order 2021-11-19 (Dkt. 153) (S5).
- Final approval. Fairness hearing 2022-05-12, order 2022-07-20 (Dkt. 184) (S6).
- Money. USD 58 million, non-reversionary. About 98 million class members received notice. 1,256,738 claim forms by 2022-05-04, a claims rate of 1.28 percent. 1,768 exclusions and five objections. The court awarded class counsel 19 percent of the fund (S6).
- Class. US residents whose financial accounts Plaid accessed, or whose login credentials Plaid obtained through Link, between 2013-01-01 and 2021-11-19. Accounts connected only through OAuth or Managed OAuth are excluded (S7).
- Business-practice terms (S5, S7). Plaid must delete Transactions data for users whose apps never requested it, and data for users whose credentials no longer work, under its deletion policies. It must store only the data categories the requesting app needs unless the user expressly consents to more. The credential pane must keep saying credentials are "provided to Plaid" and must not use the bank's color scheme. A separate pane must name Plaid, link its End User Privacy Policy and require affirmative agreement. Plaid must promote Plaid Portal on its homepage and remind Portal users of their controls, keep telling apps about its `/item/remove` endpoint, expand its privacy policy, and keep a security practices page. New practices start within 180 days of the settlement's Effective Date, and all commitments run three years from that date.
- No finding. The notice says Plaid denies the allegations and any wrongdoing, and that no court has found against Plaid or found a violation of law (S7).
- Appeal and distribution. UNKNOWN. The dockets that would show a notice of appeal or the post-distribution accounting were blocked (HTTP 403). The Effective Date, and so the end of the three-year commitments, is also unknown. If no appeal was filed, the commitments would have ended around 2025 (INFERENCE).

Allegations (ALLEGATION, as recited in S4 and S7):

- Plaid's Link screens carried bank logos and colors, so users believed they were logging in to their bank while their credentials went to Plaid.
- Plaid collected more data than the user's app needed, including transaction history for apps that asked only for account verification.
- Plaid used credentials to "harvest and sell" financial data without consent.
- Plaid did not run a true OAuth flow. In its first years apps passed credentials to Plaid; from about 2016 Plaid ran Managed OAuth screens that imitated banks.

What this means for Argus (INFERENCE). The claims that survived dismissal attach to interface design and data scope, not to the use of credentials as such. A bank-imitating login screen supported an anti-phishing theory at the pleading stage, and collecting more than the feature needed supported privacy theories.

### C2. United States v. Visa Inc. and Plaid Inc. (N.D. Cal.)

Only one part bears on aggregation. The complaint says that when a consumer gives a Plaid-supported app her bank log-in credentials, Plaid uses them to reach the bank and retrieve her data, and that Plaid served over 2,600 apps, more than 11,000 US institutions and over 200 million accounts, a base it could use for pay-by-bank debit (S71, ALLEGATION in a complaint). DOJ sued on 2020-11-05; the parties terminated the deal on 2021-01-12 (S8, VERIFIED).

### C3. Envestnet Yodlee

Clark (formerly Wesch) v. Yodlee, Inc., N.D. Cal. No. 3:20-cv-05991-SK, before Magistrate Judge Sallie Kim, was still active on 2025-03-05, when the court ruled on sealing figures for purported class members and PayPal user accounts (S63, VERIFIED). I could not read the complaint or later docket entries, so its allegations and outcome as of 2026-09 are UNKNOWN. For context, Yodlee's own 2014 prospectus describes selling analytics built on anonymized data derived from user-permissioned transaction data (S67, VERIFIED company filing).

### C4. Other disputes

- JPMorgan fees. The 2025-09-16 extension of the JPMorganChase and Plaid agreement includes an undisclosed pricing structure and, per the release, does not change Plaid's existing customer pricing (S26, VERIFIED). Plaid's October 2025 ANPR comment argues that Section 1033 forbids charging consumers or their agents for data access (S34). The CFPB's ANPR asks whether data access costs may be shared (S10, S12). The reporting that JPMorgan first announced aggregator fees in mid-2025 is SECONDARY and was not verified here. Whether other banks charge fees is UNKNOWN.
- Bank suits over how Plaid solicited credentials. The CFPB's 2023 proposal cites, as examples of litigation over aggregators' methods, the Plaid class action, TD Bank's trademark counterfeiting and infringement suit against Plaid announced 2020-10-14, and PNC's trademark suit reported by American Banker on 2020-12-23. It also cites press on a December 2019 Venmo disruption and on large banks disrupting scraping in late 2015 (S74, VERIFIED as citations). The suits' contents are ALLEGATION and their outcomes are UNKNOWN; TD's press release now redirects elsewhere. TD Bank later signed a data access partnership with Plaid, per Plaid in December 2023 (S32, COMPANY CLAIM).

### C5. Regulator views on privacy and security risk

- The CFPB's 2024 final rule states that credential-based screen scraping creates security, privacy and accuracy risks, cites exposure of credentials in third-party breaches, and notes the widespread storage of credentials and downstream data sales in today's market (S9, VERIFIED).

## D. Regulatory regimes

Status is as of 2026-09-27. "Scraping" means credential-based screen scraping by a third party.

| Jurisdiction | Instrument | Key dates | Status 2026-09 | Treatment of scraping | Licensing or registration | Citation |
|---|---|---|---|---|---|---|
| United States | CFPB Personal Financial Data Rights rule, 12 CFR part 1033 | Issued 2024-10-22; effective 2025-01-17; compliance from 2026-04-01 to 2030-04-01 by size | Enjoined since 2025-10-29 until the CFPB finishes reconsideration; ANPR 2025-08-22; no proposed rule published | Not banned. Banks cannot satisfy the rule by letting third parties scrape and must not let third parties use consumer credentials on the developer interface. Third parties using the rule cannot keep consumers' credentials, the rule provides no scraping fallback, and the CFPB warned that scraping where a safer interface exists might be an unfair, deceptive or abusive practice. | No licence. Third parties certify obligations (data minimization, one-year reauthorization, GLBA or FTC Safeguards security). | S9, S10, S12, S13 |
| European Union | PSD2 and RTS (EU) 2018/389; PSD3 and PSR pending; FIDA pending | PSD2 applies 2018-01-13; RTS applies 2019-09-14; 180-day SCA cycle from 2023-07-25 | PSD2 in force. PSR and PSD3 texts agreed with Council and approved in committee 2026-05-05; plenary forecast 2026-12-14. FIDA awaiting Parliament's first reading. | Not banned outright. Banks provide a dedicated interface or open their customer interface to identified providers; providers must identify themselves in every session, which rules out unidentified scraping (INFERENCE). Where a bank has a dedicated interface, use of the customer interface survives as a fallback while that interface fails, with identification and logging. | AISPs must register with a national authority and hold professional indemnity insurance. | S41, S42, S43, S44, S45 |
| United Kingdom | CMA Order 2017; UK SCA-RTS as amended by FCA PS21/19; PSRs 2017; Data (Use and Access) Act 2025 | Order 2017-02-02; 90-day third-party reconfirmation from 2022-03-26; dedicated interface mandate from 2023-05-26; DUA Act 2025-06-19 | In force. No open banking regulations under the DUA Act found by title search. | Dedicated interfaces required for personal and SME payment accounts and credit cards; the FCA says an interface that requires screen scraping is not a dedicated interface. | AISP registration with the FCA. | S46, S47, S48, S49, S50 |
| Australia | Consumer Data Right (Competition and Consumer Act Part IVD; CDR Rules 2020) | Act made 2019-08-12; Rules made 2020-02-04 | In force. No scraping ban found; the government noted the ban recommendation on 2023-06-07 and said it would consult. Later status UNKNOWN. | Not banned as of the latest primary source I reached (2023). | ACCC accreditation of data recipients. | S51, S52, S53, S54 |
| Brazil | BCB/CMN Joint Resolution No. 1 of 2020, as amended through 2025 | 2020-05-04 | In force. Joint Resolution No. 15 (2025-11-28, in force on publication 2025-12-01) adds a definition of data aggregation and credit portability through Open Finance. | Not addressed in the resolution text. | Only BCB-authorized institutions participate; the largest (S1 and S2 segments) must. | S55, S65 |
| Mexico | Ley Fintech, article 76 | DOF 2018-03-09; last reform DOF 2025-11-14 | In force. The law gave regulators 24 months for article 76 rules. Whether rules for personal transactional data exist is UNKNOWN. | Not addressed in article 76. | Article 76 requires APIs that connect regulated entities and specialized IT third parties; transactional data need the customer's prior express authorization. Who may receive data under secondary rules is UNKNOWN. | S56 |
| Colombia | Decree 1297 of 2022 (amends Decree 2555 of 2010 on open finance); Superintendencia Financiera Circular Externa 004 of 2024 | Decree 2022-07-25; circular issued by 2024-02-07 | In force. The SFC says the circular began a second phase in which third-party recipients may access data the consumer authorized its financial entity to share. Whether participation is voluntary or mandatory, and any later decree, UNKNOWN (both documents are scanned). | UNKNOWN | UNKNOWN; the SFC names "terceros receptores" but their eligibility rules were not read. | S57, S66 |
| Chile | Ley 21.521 (Ley Fintec), Title III; CMF NCG 514 | Law 2023-01-04; NCG 514 2024-07-03, in force 24 months after issuance, then phased API deadlines of 6 to 36 months | Law in force. NCG 514 as issued would take effect around July 2026, with bank transaction APIs about 15 months later (INFERENCE from its schedule). Later amendments UNKNOWN. | No general ban in the law. Payment initiators already using customer credentials had to register within 12 months and could keep operating meanwhile. | Registration with the CMF for information-based and payment-initiation providers. | S58, S59 |
| Canada | Consumer-Driven Banking Act (2024), replaced by a new Act in Bill C-15 | 2024-06; C-15 Royal Assent 2026-03-26 | New Act (S.C. 2026, c. 3, s. 224) mostly in force since 2026-03-26; Bank of Canada oversees. Section 171 is marked not in force in the consolidation current to 2026-09-03. | Statutory prohibition (section 171, subject to regulations) on using a consumer's authentication information to access their data to serve them. Not yet in force; the government says it starts once the framework is fully operational. | Accreditation, including national security screening. | S60, S61, S62, S64 |

Notes, two to four sentences each:

- United States. The CFPB's own 2022 data showed about half of third-party access attempts used screen scraping, down about one third since 2019 (S9). The final rule chose not to ban scraping, accepted that it may be the only practical route for data outside the rule or at banks without an interface, and warned banks to be careful when blocking it outside the rule's coverage; it also warned third parties that scraping where a safer interface exists might be an unfair, deceptive or abusive practice (S9). During a 2025 stay the Kentucky court had already moved the first compliance date from 2026-04-01 to 2026-06-30, and on 2025-10-29 it enjoined enforcement until the CFPB finishes reconsideration (S12). The CFPB's August 2026 agenda still lists that reconsideration, with no proposed rule published (S13, S14).
- European Union. RTS article 31 lets a bank choose a dedicated interface or open its customer interface to identified third parties; article 33 requires a contingency plan and lets third parties fall back to the customer interface only while the dedicated interface is down, with identification and logging (S41). National authorities, after consulting the EBA, exempt a bank from that fallback once its dedicated interface meets the performance conditions and has been widely used for three months, and revoke the exemption after two consecutive weeks of failure (S41, article 33(6) and (7)). PSD2 article 67 requires explicit consent, identification in every session and use limited to the requested service, and bars conditioning access on a contract with the bank (S42). The Commission's 2023 PSR proposal would require a dedicated interface, drop the permanent fallback except in exceptional cases, and require bank permission dashboards (S44); the agreed text had not been adopted by 2026-09 (S45).
- United Kingdom. PS21/19 moved the 90-day reconfirmation to the third party from 2022-03-26 and required dedicated interfaces from 2023-05-26 (S46). The CMA recorded completion of the roadmap on 2023-01-12 and still corresponds with Open Banking Limited on remaining items (S48).
- Australia. The 2022 review found businesses kept scraping despite the CDR because it was cheaper and easier, and recommended a ban where the CDR is a viable alternative (S52). The government's 2023 response did not adopt a ban and called scraping unsafe while promising consultation (S53).
- Brazil. The resolution defines open banking as standardized sharing among participating authorized institutions and excludes authentication credentials from the data to be shared (S55). Since December 2025 it also defines data aggregation as consolidating data shared under the resolution to serve the institution's own clients, which places aggregation inside the licensed perimeter (S65; the placement is an INFERENCE).
- Mexico. Article 76 splits data into open, aggregated and transactional, and requires access to stop as soon as the customer withdraws consent (S56).
- Colombia. The SFC describes Circular Externa 004 of 2024 as the rules for open finance and the start of a second implementation phase, with access by third-party recipients subject to security, cybersecurity and personal data protection law (S66). The decree and the circular are scanned images, so their text was not verified.
- Chile. Article 23 requires consent that is free, informed, express and specific as to data type, purpose and maximum validity (S58). Article 25 bars data holders from charging information-based providers except for incremental costs above CMF volume thresholds (S58).
- Canada. Finance Canada says about nine million Canadians share banking credentials today and that the ban will start only once the framework is fully operational (S60, S61).

## E. Five things to keep distinct

(a) A consumer authorizing access. This is the user's permission to a specific app, for a stated scope, purpose and period.
- Plaid's settlement requires a separate pane in Link that names Plaid, links its privacy policy and requires affirmative agreement (S7). Since 2024-10-31, new US and Canadian Plaid customers must also declare a use case, which Link shows beside the data types requested (S86).
- The 1033 rule required an authorization disclosure and limited collection to one year after the latest authorization (S9, 12 CFR 1033.401, 1033.411, 1033.421(b)).
- Chile's Ley Fintec article 23 requires specific consent naming data type, purpose and maximum validity (S58).
- A consumer's permission does not create a right against the bank and does not waive the bank's contract terms (INFERENCE from items b and c).

(b) A statutory right to access or portability. This is a law that obliges the data holder to release data to the consumer or the consumer's agent.
- PSD2 article 67 gives payment service users the right to use account information services and bars banks from requiring a contract with the provider (S42).
- Section 1033 of the Dodd-Frank Act and the 2024 rule would have required US data providers to share with authorized third parties at no charge; enforcement is enjoined (S9, S12).
- Canada's new Consumer-Driven Banking Act and Chile's Ley Fintec create participation duties for data holders (S58, S62).
- Where no statute exists, access rests only on (a) and on whatever the bank tolerates under (c) (INFERENCE).

(c) A bank's contractual conditions. These are the account and online-banking terms between the user and the bank, including who bears losses.
- Banco BHD (Dominican Republic). The approved 2026 contract model makes the access code and code card personal and non-transferable, makes the customer responsible for their custody, and treats instructions given with them as valid even if they result from fraud, unless the customer had already reported loss or suspected third-party use. A card clause also commits the customer not to share digital-channel credentials so that third parties gain access (S23, VERIFIED; parts of the scan are garbled).
- Wells Fargo (United States). The customer must keep the username and password confidential, the bank may rely on instructions given under them, and the customer may be liable for losses from unauthorized use to the extent the law allows (S22, version effective 2026-05-21).
- Regulation E. A transfer by a person to whom the consumer furnished the access device is not "unauthorized" until the consumer tells the bank that person's authority has ended, and the consumer is fully liable if that person exceeds the authority given (S21). Whether an aggregator holding online-banking credentials falls within this rule was not resolved in any source I read (UNKNOWN).

(d) Authorization or licensing to operate an aggregation service. This is the state's permission for the aggregator itself.
- In the EU, an account information provider registers with a national authority and holds professional indemnity insurance (S42, article 33 and article 5(3)).
- In the UK, it registers with the FCA as an account information service provider (S49).
- Australia requires ACCC accreditation (S54), Brazil admits only BCB-authorized institutions (S55), Chile requires CMF registration (S58, S59), and Canada requires accreditation with national security screening (S61).
- In the United States the 1033 rule used third-party certification rather than a licence (S9). I found no federal aggregator licence (UNKNOWN whether state licences apply to a given model).

(e) Legal obligations for handling credentials and financial data. These apply whether or not a statutory access right exists.
- The FTC Safeguards Rule (16 CFR part 314) requires a written information security program; its main new elements took effect 2023-06-09 and breach reporting to the FTC for events involving 500 or more consumers took effect 2024-05-13 (S20).
- Coverage turns on being a "financial institution" engaged in activities that are financial in nature. The rule's examples include finders and financial advisory services but do not name aggregators (S20). The CFPB stated in 2024 that all or most third parties seeking consumer-authorized data are already subject to the GLBA safeguards framework, and the 1033 rule required them to apply it (S9, 12 CFR 1033.421(e)).
- PSD2 article 67 requires account information providers to keep users' security credentials from other parties and to transmit them only over safe channels (S42). RTS article 33 requires identification and access logs when a provider uses the fallback customer interface (S41).
- Plaid's settlement added contractual duties on top of statute: data minimization, deletion and disclosure (S7).

## F. Lessons that materially affect Argus

Each lesson names the evidence it rests on. How it applies to Argus is INFERENCE unless stated otherwise.

- F1. Asking a Dominican user for bank passwords likely breaks the user's bank contract and moves fraud losses onto the user. Banco BHD's 2026 contract, approved by the Superintendencia de Bancos, makes credentials personal and non-transferable, holds the customer responsible for their custody, and presumes instructions given with them valid even if fraudulent unless the customer had already reported suspected third-party use (S23). US terms and Regulation E point the same way (S21, S22). Any credential flow needs a plain risk disclosure, and file or statement import deserves to be the default path until banks offer something better.
- F2. The legal pressure in the Plaid case fell on the screen, not on credential use as such. Anti-phishing and privacy claims survived dismissal on allegations that Link imitated bank login screens (S4), and the settlement requires saying credentials go to Plaid, forbids the bank's colors, and requires a separate consent pane (S7). Argus should never imitate a bank's interface, should name every party that will receive the credentials, and should take consent before the credential field appears.
- F3. Collect only what the feature needs, and make deletion real. The settlement forced deletion of data apps never asked for and limited storage to requested categories (S7). The 1033 rule, though enjoined, treats targeted advertising, cross-selling and sale of data as outside what is reasonably necessary and caps collection at one year without reauthorization (S9). Argus should record per connection what was requested, why, and until when.
- F4. Users expect one place to see and cut off connections. Plaid Portal became a settlement obligation (S7, S36), the EU payment services proposal requires bank-side permission dashboards (S44), and Chase launched one on 2026-09-25 (S27). A connections page with revoke and delete belongs in Argus's first version, and revocation must stop collection at the source.
- F5. Moving off credentials took the US market close to a decade and bank-by-bank deals. Chase signed with Plaid in 2018 (S24), Plaid reached 75 percent of connections on APIs only in May 2023 against its own goal of end-2021 (S29, S31), the CFPB still saw about half of access attempts scraped in 2022 (S9), and FDX said tens of millions still shared credentials in 2025 (S40). Argus should store the access method per connection so one bank can move from files or credentials to a token or API without changing the rest of the system.
- F6. An API is not free access. JPMorganChase's 2025 renewal with Plaid includes a pricing structure (S26), US fee rules are under reconsideration (S10, S12), and Chile lets data holders recover incremental costs above set volumes (S58). Argus's economics should allow for per-bank fees once Dominican banks open interfaces.
- F7. Regimes differ, so no single foreign model predicts the Dominican outcome. Canada enacted a scraping ban that is not yet in force (S62, S64), the EU requires provider identification and dedicated interfaces (S41, S42), the UK mandates dedicated interfaces (S46), the US rule does not ban scraping and is enjoined (S9, S12), Australia has not banned it (S53), and Brazil's and Mexico's texts are silent on it (S55, S56). The requirements every regime shares are explicit scoped consent, provider identification, a security program and revocation. Building those now makes a future Dominican regime a smaller step.
- F8. Licensing follows the data recipient. The EU, UK, Australia, Brazil, Chile and Canada each require registration, accreditation or authorization of the party receiving account data (S42, S49, S54, S55, S59, S61). Argus should plan for a registration requirement if the Dominican Republic adopts open finance, and should confirm current Dominican requirements with the regulatory units of this research.
- F9. Security duties attach to holding the data, with or without an access right. The FTC Safeguards Rule requires a written security program and breach reporting (S20), the 1033 rule tied third parties to it (S9), and PSD2 requires account information providers to keep credentials from other parties (S42). The CFPB named credential exposure in third-party breaches as a core risk of scraping (S9). If Argus ever handles credentials, they need the strongest protection it has, access logs of the kind the EU fallback requires (S41), and a tested breach response.
- F10. A broken connection is a normal state, and so is a failing bank API. Plaid's docs treat password changes, MFA expiry, bank migrations and consent expiry as routine reasons a connection stops (S79, S80, S81); US banks impose 3 to 18 month re-consent cycles and the EU 180 days (S75, S43); ten of Plaid's last 25 public incidents named one institution, several of them API banks (S82); and re-consent loses users, from a reported 0.32 percent reconnect rate to 20 to 87 percent attrition estimates in the UK (S74). Argus needs per-connection states (active, needs re-login, expiring, revoked, institution down), should show users how old their data is, and should track success rates per bank, as Plaid's status breakdown does (S83).

## G. Open questions and what I could not verify

Litigation:
- Whether anyone appealed the Plaid final approval, the settlement's Effective Date, and so when the three-year business-practice terms ended. Docket pages returned HTTP 403. Tracker sites report payments of about USD 36 per claimant; I did not verify that.
- The allegations and outcome of Clark (Wesch) v. Yodlee after March 2025.
- The contents and outcomes of TD Bank's and PNC's 2020 suits against Plaid, and of PNC's December 2019 blocking episode. The CFPB cites them (S74), but I read no court record.

Bank agreements and fees:
- Dates and terms of Plaid's agreements with Wells Fargo, Capital One, Citi, U.S. Bank, PNC, Bank of America and Schwab. I found only Plaid's 2023 claim that Capital One, Chase, USAA and Wells Fargo traffic had moved fully to APIs and that RBC, Citibank and M&T had signed (S31).
- What JPMorgan first announced about aggregator fees in 2025, the fee levels, and whether other banks charge. Only the undisclosed pricing structure in the 2025-09-16 renewal is verified (S26).
- FDX's founding date. FDX calls itself an independent subsidiary of FS-ISAC (S40); I did not find a dated primary source for its founding.

Regulation:
- United States. The content and timing of the 1033 reconsideration proposal (reported at OIRA in August 2026, S15) and the Kentucky case's next steps.
- European Union. The date of the PSD3 and PSR provisional agreement, the final text on account information access, fallback and dashboards, and whether FIDA survives.
- United Kingdom. Whether regulations under the Data (Use and Access) Act 2025 will cover open banking, and when.
- Australia. Whether any screen-scraping policy was adopted after the June 2023 statement. Treasury and ACCC pages beyond S52 to S54 were not reachable without search.
- Mexico. Which secondary rules under article 76 exist, with their gazette dates, and whether rules for personal transactional data were ever issued.
- Colombia. The text of Decree 1297 of 2022 and of Circular Externa 004 of 2024 (both scanned), including whether participation is voluntary and who may receive data, and whether any later decree made open finance mandatory.
- Chile. Whether the CMF amended NCG 514's schedule after July 2024, and whether the registries for information-based providers are open.
- Canada. When section 171 will be brought into force and what the regulations will exempt.
- Dominican Republic. Out of scope for this unit. The BHD contract cites the Monetary and Financial Law 183-02 (article 56, bank secrecy) and the personal data law 172-13 (S23); their effect on third-party aggregation belongs to the Dominican regulatory units.

Plaid mechanics:
- When Plaid first supported bank OAuth. The earliest dated trace I found is Plaid's iOS SDK release of 2020-01-15, which fixes an already existing OAuth flow (S89); the Chase agreement planned token-based migration from the first half of 2019 (S24). No Plaid page states a start date.
- Whether and how Plaid stores credentials today, and for how long. The privacy policy is silent (S72).
- Earlier versions of Plaid's End User Privacy Policy and their dates.
- The full list of US institutions on OAuth (behind a Dashboard login).
- Plaid's actual share of live traffic on APIs after May 2023. Later figures count "on or committed to" APIs (S76).
- Mint's later switch away from Yodlee and its 2024 shutdown date; Finicity's and MX's early reliance on scraping.

Method gaps:
- The shared web-search budget ran out early, so some items above may be answerable with a search that I could not run.
- regulations.gov returned HTTP 403, so Plaid's formal comment letters of 2021, 2023 and 2025 were read only through Plaid's own summaries, except the 2023 SBREFA letter hosted by Plaid (S73).
- One delegated finding was wrong and is corrected here. A delegated researcher reported that Plaid's status page lists no bank incidents, but its incident history does list institution-specific disruptions (S82).

## Sources

All accessed 2026-09-27.

- S1. Plaid. "Plaid Link: A decade of innovation in connectivity & conversion." Hillary Ross, Matt Capers. Published 2025-05-22. https://plaid.com/blog/ten-years-plaid-link/
- S2. Plaid. "Setting the standard for safe and secure data access." John C. Pitts. Published 2021-07-15. https://plaid.com/blog/setting-the-standard-for-safe-and-secure-data-access/
- S3. Plaid. Homepage, "Plaid: Enabling all companies to build fintech solutions." Undated (footer 2026; sitemap lastmod 2026-09-25). https://plaid.com/
- S4. U.S. District Court, N.D. Cal. Cottle v. Plaid Inc., No. 4:20-cv-03056-DMR, Dkt. 125, "Order on Defendant's Motion to Dismiss the Consolidated Amended Class Action Complaint." Filed 2021-04-30. https://www.govinfo.gov/content/pkg/USCOURTS-cand-4_20-cv-03056/pdf/USCOURTS-cand-4_20-cv-03056-1.pdf
- S5. Same court and case, Dkt. 153, "Order on Motion for Preliminary Approval of a Class Action Settlement." Filed 2021-11-19. https://www.govinfo.gov/content/pkg/USCOURTS-cand-4_20-cv-03056/pdf/USCOURTS-cand-4_20-cv-03056-3.pdf
- S6. Same court and case, Dkt. 184, "Order Granting Final Approval of Class Action Settlement." Filed 2022-07-20. https://www.govinfo.gov/content/pkg/USCOURTS-cand-4_20-cv-03056/pdf/USCOURTS-cand-4_20-cv-03056-4.pdf
- S7. Settlement administrator (court-approved notice). "Notice of Class Action Settlement, In re Plaid Inc. Privacy Litigation." Undated; deadlines 2022-03-04 (opt-out) and 2022-04-28 (claims). https://angeion-public.s3.amazonaws.com/www.PlaidSettlement.com/docs/Long+Form+Notice.pdf
- S8. U.S. DOJ Antitrust Division. "Protecting Nascent Competition: Visa and Plaid Abandon Anticompetitive Merger." Division Update Spring 2021, updated 2023-06-15. https://www.justice.gov/atr/division-operations/division-update-spring-2021/protecting-nascent-competition-visa-and-plaid-abandon-anticompetitive-merger
- S9. CFPB. "Required Rulemaking on Personal Financial Data Rights," final rule, 89 FR 90838. Published 2024-11-18; effective 2025-01-17. https://www.federalregister.gov/documents/2024/11/18/2024-25079/required-rulemaking-on-personal-financial-data-rights
- S10. CFPB. "Personal Financial Data Rights Reconsideration," advance notice of proposed rulemaking, 90 FR 40986. Published 2025-08-22; comments closed 2025-10-21. https://www.federalregister.gov/documents/2025/08/22/2025-16139/personal-financial-data-rights-reconsideration
- S11. U.S. District Court, E.D. Ky. Forcht Bank, N.A. v. CFPB, No. 5:24-cv-304-DCR, Dkt. 56, memorandum order granting the Financial Technology Association's motion to intervene. Filed 2025-05-14. https://www.govinfo.gov/content/pkg/USCOURTS-kyed-5_24-cv-00304/pdf/USCOURTS-kyed-5_24-cv-00304-0.pdf
- S12. Same court and case, Dkt. 90, memorandum opinion and order enjoining enforcement of the rule. Filed 2025-10-29. https://www.govinfo.gov/content/pkg/USCOURTS-kyed-5_24-cv-00304/pdf/USCOURTS-kyed-5_24-cv-00304-1.pdf
- S13. CFPB. "Regulatory Agenda," 91 FR 53082. Published 2026-08-14. https://www.federalregister.gov/documents/2026/08/14/2026-16613/regulatory-agenda
- S14. Federal Register API, query for CFPB documents matching "Personal Financial Data Rights" and "1033," run 2026-09-27. Latest results were S13 and S10. https://www.federalregister.gov/api/v1/documents.json?conditions%5Bterm%5D=1033&conditions%5Bagencies%5D%5B%5D=consumer-financial-protection-bureau
- S15. SECONDARY. Ballard Spahr, Consumer Finance Monitor. "CFPB Sends New Section 1033 'Open Banking' Proposal to OIRA for Review." Alan S. Kaplinsky, Adam Maarec. Published 2026-08-06. https://www.consumerfinancemonitor.com/2026/08/06/cfpb-sends-new-section-1033-open-banking-proposal-to-oira-for-review/
- S16. CFPB (archived newsroom). "CFPB Approves Application from Financial Data Exchange to Issue Standards for Open Banking." Published 2025-01-08. https://www.consumerfinance.gov/about-us/newsroom/cfpb-approves-application-from-financial-data-exchange-to-issue-standards-for-open-banking/
- S17. CFPB (archived newsroom). "CFPB Outlines Principles For Consumer-Authorized Financial Data Sharing and Aggregation." Published 2017-10-18. https://www.consumerfinance.gov/about-us/newsroom/cfpb-outlines-principles-consumer-authorized-financial-data-sharing-and-aggregation/
- S18. Executive Order 14036, "Promoting Competition in the American Economy," 86 FR 36987, section 5(t). Signed 2021-07-09; published 2021-07-14. https://www.federalregister.gov/documents/2021/07/14/2021-15069/promoting-competition-in-the-american-economy
- S19. Executive Order 14337, "Revocation of Executive Order on Competition," 90 FR 40227. Signed 2025-08-13; published 2025-08-19. https://www.federalregister.gov/documents/2025/08/19/2025-15824/revocation-of-executive-order-on-competition
- S20. FTC. Standards for Safeguarding Customer Information: 86 FR 70272 (published 2021-12-09, effective 2022-01-10), 87 FR 71509 (published 2022-11-23, moving key provisions to 2023-06-09), 88 FR 77499 (published 2023-11-13, effective 2024-05-13). Current text 16 CFR 314.2 and 314.5. https://www.federalregister.gov/documents/2021/12/09/2021-25736/standards-for-safeguarding-customer-information ; https://www.federalregister.gov/documents/2022/11/23/2022-25201/standards-for-safeguarding-customer-information ; https://www.federalregister.gov/documents/2023/11/13/2023-24412/standards-for-safeguarding-customer-information ; https://www.ecfr.gov/current/title-16/chapter-I/subchapter-C/part-314
- S21. CFPB. Regulation E, 12 CFR 1005.2(m) and Supplement I, comment 2(m)-2 (current eCFR). https://www.ecfr.gov/current/title-12/chapter-X/part-1005
- S22. Wells Fargo. "Online Access Agreement." Version effective 2026-05-21 (a revised version is announced for 2026-11-24). https://www.wellsfargo.com/online-banking/online-access-agreement/
- S23. Banco BHD. "Hoja Resumen Contrato de Cuentas Pasivas Personales, Menu y su correspondiente Manual Operativo." Model approved by the Superintendencia de Bancos, oficio OFC-PRO-2026203630 of 2026-06-24; file last modified 2026-07-17. https://static.bhd.com.do/Hoja_Resumen_Manu_Contrato_Manual_Operativo_Persona_Fisica_b56b68e42f.pdf
- S24. JPMorgan Chase. "Plaid Signs Data Agreement with JPMorgan Chase." Published 2018-10-22. https://media.chase.com/news/plaid-signs-data-agreement-with-jpmc
- S25. Plaid. "Safe, convenient, and reliable data access for consumers." Sima Gandhi. Published 2018-10-22. https://plaid.com/blog/chase/
- S26. JPMorgan Chase. "JPMorganChase and Plaid Announce an Extension to their Data Access Agreement for Sharing of Consumer Permissioned Data." Published 2025-09-16. https://media.chase.com/news/jpmorganchase-plaid-extend-data-access-agreement
- S27. JPMorgan Chase. "Chase Launches Data Security Center to Help Customers Manage Connected Apps and Third-Party Data Sharing." Published 2026-09-25. https://media.chase.com/news/chase-launches-data-security-center
- S28. JPMorgan Chase newsroom listing, entries "Chase, Intuit to Give Customers Greater Control of Their Information" (2017-01-25) and "JPMorgan Chase, Envestnet | Yodlee Sign Agreement to Increase Customers' Control of Their Data" (2019-12-05). Titles and dates only. https://media.chase.com/news
- S29. Plaid. "Plaid's strategy to facilitate an API-based ecosystem." Ginger Baker, Niko Karvounis. Published 2020-11-19. https://plaid.com/blog/plaids-strategy-to-facilitate-an-api-based-ecosystem/
- S30. Plaid. "Plaid's support for a strong consumer financial data right." Ben White. Published 2023-01-25. https://plaid.com/blog/plaid-cfpb-1033-sbrefa-comment-letter/
- S31. Plaid. API progress update ("Bringing Open Finance to North America"). Published 2023-05-11. https://plaid.com/blog/api-progress-update/
- S32. Plaid. "An Update on our Open Finance Strategy." Cecilia Frew. Published 2023-12-21. https://plaid.com/blog/open-finance-strategy-update/
- S33. Plaid. "The CFPB's final 1033 rule and the future of open finance." John Pitts. Published 2024-10-22. https://plaid.com/blog/cfpb-open-banking-rule-announced/
- S34. Plaid. "Strengthening financial freedom & competition: Plaid's submission on the CFPB's 1033 ANPR." Danielle Aviles Krueger. Published 2025-10-21. https://plaid.com/blog/submission-on-cfpb-anpr/
- S35. Plaid. "Cutting Costs and Complexity in Open Finance with Plaid." Maurizio Di Gianluca, Brenna Ramsay. Published 2025-09-10. https://plaid.com/blog/open-finance-aggregator-token/
- S36. Plaid. "Put greater data privacy control into the hands of consumers with Plaid's Privacy Controls suite." Sheila Jambekar, Chandni Chopra. Published 2022-10-19. https://plaid.com/blog/introducing-privacy-controls/
- S37. Plaid. "Making sense of data access approaches." Eric Showen. Published 2016-10-19. https://plaid.com/blog/financial-data-access-methods/
- S38. Plaid. "Inside Plaid: How we are investing in reliable financial data access at scale." Published 2025-04-24. https://plaid.com/blog/reliable-financial-data-access-at-scale/
- S39. GitHub REST API repository metadata: `plaid/deprecated-link` (formerly `plaid/link`) created 2015-04-10; `plaid/plaid-node` created 2013-03-25. https://api.github.com/repos/plaid/deprecated-link ; https://api.github.com/repos/plaid/plaid-node
- S40. Financial Data Exchange (FDX). "114 Million Reasons to Keep Moving Forward on Industry-Led Standard for Secure Data Sharing." Published 2025-04-25. https://financialdataexchange.org/fdx-feed/114-million-reasons-to-keep-moving-forward-on-industry-led-standard-for-secure-data-sharing/
- S41. European Commission. Delegated Regulation (EU) 2018/389 of 27 November 2017 (RTS on SCA and common and secure communication), OJ L 69, 13.3.2018, p. 23; applies from 2019-09-14 (articles 30(3) and 30(5) from 2019-03-14). Read via the EU Publications Office. https://publications.europa.eu/resource/celex/32018R0389 ; https://eur-lex.europa.eu/eli/reg_del/2018/389/oj
- S42. European Parliament and Council. Directive (EU) 2015/2366 (PSD2), OJ L 337, 23.12.2015; articles 5(3), 33, 67, 115. https://publications.europa.eu/resource/celex/32015L2366 ; https://eur-lex.europa.eu/eli/dir/2015/2366/oj
- S43. European Commission. Delegated Regulation (EU) 2022/2360 of 3 August 2022 (90-day exemption for account access), OJ L 312, 5.12.2022; applies from 2023-07-25. https://publications.europa.eu/resource/celex/32022R2360
- S44. European Commission. Proposal for a Payment Services Regulation, COM(2023) 367, 2023-06-28; articles 35, 38 and 43 of the proposal. https://publications.europa.eu/resource/celex/52023PC0367
- S45. European Parliament Legislative Observatory. Procedure files 2023/0210(COD) (PSR), 2023/0209(COD) (PSD3) and 2023/0205(COD) (FIDA), read 2026-09-27. https://oeil.secure.europarl.europa.eu/oeil/en/procedure-file?reference=2023/0210(COD) ; https://oeil.secure.europarl.europa.eu/oeil/en/procedure-file?reference=2023/0209(COD) ; https://oeil.secure.europarl.europa.eu/oeil/en/procedure-file?reference=2023/0205(COD)
- S46. UK Financial Conduct Authority. PS21/19, changes to the SCA-RTS, the FCA Approach Document and the Perimeter Guidance Manual (title paraphrased). Published 2021-11-29; instrument FCA 2021/45 commencement 2021-11-30, 2022-03-26 and 2023-05-26. https://www.fca.org.uk/publications/policy-statements/ps21-19-changes-sca-rts-and-guidance-approach-document-and-perimeter-guidance-manual ; https://www.fca.org.uk/publication/policy/ps21-19.pdf
- S47. UK Competition and Markets Authority. "Retail Banking Market Investigation Order 2017." Published 2017-02-02. https://www.gov.uk/government/publications/retail-banking-market-investigation-order-2017
- S48. UK Competition and Markets Authority. Retail banking market investigation case page, updated 2026-01-20, including "CMA decision on Roadmap completion" (2023-01-12) and letters of 2024-09-09 and 2025-12-03. https://www.gov.uk/cma-cases/review-of-banking-for-small-and-medium-sized-businesses-smes-in-the-uk
- S49. UK. The Payment Services Regulations 2017 (SI 2017/752), regulations 17 and 18. https://www.legislation.gov.uk/uksi/2017/752/regulation/17
- S50. UK. Data (Use and Access) Act 2025 (c. 18), enacted 2025-06-19; legislation.gov.uk title search for 2025 to 2026 instruments, run 2026-09-27. https://www.legislation.gov.uk/ukpga/2025/18/contents
- S51. Australia. Treasury Laws Amendment (Consumer Data Right) Act 2019 (No. 63 of 2019), made 2019-08-12; Competition and Consumer (Consumer Data Right) Rules 2020, made 2020-02-04. Read via the Federal Register of Legislation API. https://www.legislation.gov.au/C2019A00063 ; https://www.legislation.gov.au/F2020L00094
- S52. Australian Treasury. "Statutory Review of the Consumer Data Right, Final Report." Elizabeth Kelly PSM. Published 2022-09-29. https://treasury.gov.au/publication/p2022-314513
- S53. Australian Government. "Government statement in response to the Statutory Review of the Consumer Data Right." Published 2023-06-07. https://treasury.gov.au/publication/p2023-404730
- S54. Australian Treasury. "Consumer Data Right" (roles of Treasury, ACCC, OAIC and the Data Standards Body). Undated. https://treasury.gov.au/consumer-data-right
- S55. Banco Central do Brasil and Conselho Monetario Nacional. Resolucao Conjunta No. 1, 2020-05-04, published DOU 2020-05-05, with amendment history through Resolucao Conjunta No. 15 of 2025. Read via the BCB normative API. https://www.bcb.gov.br/estabilidadefinanceira/exibenormativo?tipo=Resolu%C3%A7%C3%A3o%20Conjunta&numero=1
- S56. Mexico, Camara de Diputados. Ley para Regular las Instituciones de Tecnologia Financiera, published DOF 2018-03-09, last reform DOF 2025-11-14; article 76 and transitory provisions. https://www.diputados.gob.mx/LeyesBiblio/pdf/LRITF.pdf
- S57. Colombia, Presidencia de la Republica. Decree index for July 2022, entry "Decreto 1297 del 25 de julio de 2022, por medio del cual se modifica el Decreto 2555 de 2010 en lo relacionado con la regulacion de las finanzas abiertas en Colombia." https://dapre.presidencia.gov.co/normativa/decretos-2022/decretos-julio-2022 ; scanned decree: https://dapre.presidencia.gov.co/normativa/normativa/DECRETO%201297%20DEL%2025%20DE%20JULIO%20DE%202022.pdf
- S58. Chile. Ley 21.521 (Ley Fintec), promulgated 2022-12-22, published in the Diario Oficial 2023-01-04; Title III and transitory article 4. Read via the LeyChile XML service. https://www.bcn.cl/leychile/navegar?idNorma=1187323
- S59. Chile, Comision para el Mercado Financiero. Norma de Caracter General No. 514, "Norma que regula el Sistema de Finanzas Abiertas." Dated 2024-07-03; in force 24 months after issuance. https://www.cmfchile.cl/normativa/ncg_514_2024.pdf
- S60. Department of Finance Canada. "2024 Fall Economic Statement: Canada's complete framework for consumer-driven banking." Archived; date modified 2025-11-06. https://www.canada.ca/en/department-finance/programs/financial-sector-policy/open-banking-implementation/2024-fall-economic-statement-canadas-complete-framework-consumer-driven-banking.html
- S61. Department of Finance Canada. "Budget 2025: Canada's framework for consumer-driven banking." Published 2025-11-06. https://www.canada.ca/en/department-finance/programs/financial-sector-policy/open-banking-implementation/budget-2025-canadas-framework-for-consumer-driven-banking.html
- S62. Parliament of Canada. Bill C-15 (45th Parliament, 1st session), Budget 2025 Implementation Act, No. 1, Royal Assent 2026-03-26; Part 5, Division 9 enacts the new Consumer-Driven Banking Act (sections 2, 171, 181). https://www.parl.ca/legisinfo/en/bill/45-1/c-15 ; https://www.parl.ca/DocumentViewer/en/45-1/bill/C-15/royal-assent
- S63. U.S. District Court, N.D. Cal. Clark v. Yodlee, Inc., No. 3:20-cv-05991-SK, orders filed 2023-11-07 (Dkt. 381) and 2025-03-05 (Dkt. 697). https://www.govinfo.gov/app/details/USCOURTS-cand-3_20-cv-05991
- S64. Department of Justice Canada, Justice Laws Website. Consumer-Driven Banking Act (S.C. 2026, c. 3, s. 224), consolidation current to 2026-09-03, page modified 2026-09-22; XML in-force flags per section. https://laws-lois.justice.gc.ca/eng/acts/C-36.78/index.html ; https://laws-lois.justice.gc.ca/eng/XML/C-36.78.xml
- S65. Banco Central do Brasil and Conselho Monetario Nacional. Resolucao Conjunta No. 15, 2025-11-28, published DOU 2025-12-01, in force on publication; amends Joint Resolution No. 1. Read via the BCB normative API. https://www.bcb.gov.br/estabilidadefinanceira/exibenormativo?tipo=Resolu%C3%A7%C3%A3o%20Conjunta&numero=15
- S66. Superintendencia Financiera de Colombia. Event page "Lanzamiento de la segunda fase de implementacion del modelo de finanzas abiertas," dated 2024-02-07, describing Circular Externa 004 de 2024. https://www.superfinanciera.gov.co/calendario/6526/lanzamiento-de-la-segunda-fase-de-implementacion-del-modelo-de-finanzas-abiertas/ ; circular file (scanned, 3 pages, created 2024-02-07) archived at https://web.archive.org/web/20240207191632/https://www.superfinanciera.gov.co/descargas/institucional/pubFile1069630/ce004_24.pdf
- S67. Yodlee, Inc. Form S-1 registration statement (SEC EDGAR). Filed 2014-06-30. https://www.sec.gov/Archives/edgar/data/0001161315/000119312514255452/d684206ds1.htm
- S68. Intuit Inc. "Intuit to Acquire Mint.com." Published 2009-09-14. https://investors.intuit.com/news-events/press-releases/detail/1019/intuit-to-acquire-mint-com
- S69. SECONDARY. VentureBeat. "Finance startup Yodlee: We weren't screwed by Mint's acquisition." Published 2009-09-28. Read by a delegated researcher, not re-read by me. https://venturebeat.com/entrepreneur/finance-startup-yodlee-we-werent-screwed-by-mints-acquisition
- S70. Plaid on GitHub. `plaid/deprecated-link` README at commit 81ab6ee ("Project CSA", 2015-04-16) and at commit 7f6a83d ("Plaid Link", 2015-06-05). https://raw.githubusercontent.com/plaid/deprecated-link/81ab6ee0b5a2175fd2bc574076c2c1e934565cdd/README.md ; https://raw.githubusercontent.com/plaid/deprecated-link/7f6a83d30aaec84c42b1b826eeaaf7f040f37a2a/README.md
- S71. U.S. Department of Justice. Complaint, United States v. Visa Inc. and Plaid Inc. (N.D. Cal.), paragraphs 7, 33, 37 and 38. Filed 2020-11-05. https://www.justice.gov/d9/press-releases/attachments/2020/11/05/filed_visa_plaid_complaint_0.pdf
- S72. Plaid. "End User Privacy Policy." Effective 2025-12-08. https://plaid.com/legal/
- S73. Plaid. Letter to CFPB Director Rohit Chopra on the Section 1033 SBREFA outline. Dated 2023-01-25. https://plaid.com/documents/plaid-CFPB-1033-SBREFA-letter.pdf
- S74. CFPB. "Required Rulemaking on Personal Financial Data Rights," notice of proposed rulemaking. Released 2023-10-19; published 88 FR 74796, 2023-10-31. PDF of the released notice: https://files.consumerfinance.gov/f/documents/cfpb-1033-nprm-fr-notice_2023-10.pdf
- S75. Plaid Docs. "OAuth guide." Live page, undated, read 2026-09-27. https://plaid.com/docs/link/oauth/
- S76. Plaid. "A New Era for Open Finance," John C. Pitts, 2024-01-02, https://plaid.com/blog/a-vision-for-open-finance/ ; and "Progress in open finance: An update from Plaid," John Pitts, 2024-09-10, https://plaid.com/blog/updates-plaid-financial-institutions/
- S77. Plaid Docs. "Changelog," entries of 2024-12-10 (passkeys), September 2025 (Chase revocation events), February 2026 (Bank of America API migration) and June 2026 (Institution Status page). https://plaid.com/docs/changelog/
- S78. Plaid on GitHub. `plaid/plaid-python-legacy` README (repository created 2017-02-16), MFA handling for the legacy API. https://raw.githubusercontent.com/plaid/plaid-python-legacy/master/README.md
- S79. Plaid Docs. "Item errors" (`ITEM_LOGIN_REQUIRED`, `ITEM_LOCKED`, MFA errors). Live page, undated. https://plaid.com/docs/errors/item/
- S80. Plaid Docs. "Update mode." Live page, undated. https://plaid.com/docs/link/update-mode/
- S81. Plaid Docs. "Items" API reference (Item webhooks). Live page, undated. https://plaid.com/docs/api/items/
- S82. Plaid. Status page incident history through the public Statuspage API, 25 most recent incidents (2026-06-05 to 2026-09-26). https://status.plaid.com/ ; https://status.plaid.com/api/v2/incidents.json
- S83. Plaid Docs. "Institutions" API reference (institution status object). Live page, undated. https://plaid.com/docs/api/institutions/
- S84. Plaid Docs. "Institution errors." Live page, undated. https://plaid.com/docs/errors/institution/
- S85. Plaid. "Announcing Plaid Portal: An ongoing commitment to data privacy." Sheila Jambekar, Tara Jotwani. Published 2022-01-25. https://plaid.com/blog/data-privacy-week-2022/
- S86. Plaid Docs. "Link customization" (Data Transparency Messaging; use case required for new US and Canadian customers from 2024-10-31). Live page, undated. https://plaid.com/docs/link/customization/
- S87. Plaid Docs. "Returning user experience" (passkeys). Live page, undated. https://plaid.com/docs/link/returning-user/
- S88. MX. "Screen Scraping Vs. Bank APIs: What's the Difference?" Published 2020-08-04. https://www.mx.com/blog/screen-scraping-vs-bank-apis-whats-the-difference/
- S89. Plaid on GitHub. `plaid/plaid-link-ios` CHANGELOG, entries LinkKit 1.1.26 (2020-01-15) and 1.1.34 (2020-07-17). https://raw.githubusercontent.com/plaid/plaid-link-ios/master/CHANGELOG.md
