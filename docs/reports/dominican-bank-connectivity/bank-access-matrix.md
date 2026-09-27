# Bank access matrix

This file records public evidence on how Argus could obtain user-authorized balances and transactions from five Dominican institutions and from aggregators. Every row was seen on 2026-09-27. Nobody signed in, enrolled, submitted a form, installed an app, or contacted a bank. Marketing pages never count as proof of an authenticated capability.

Each finding carries one label.

- **Verified through documentation.** An official help page, manual, FAQ, terms, fee schedule, contract template, or regulator page states it concretely.
- **Observed on public pages.** A public product, marketing, app-store, or technical page shows it without concrete documentation.
- **Vendor claim only.** A third party says it, and the institution has not confirmed it.
- **Unknown.** No public evidence either way.
- **Requires an authorized account test.** Only a consenting holder's own session can settle it.

The research notes for each bank re-read the decision-relevant clauses in the original documents, including Popular's Convenio Único and BHD's contract clauses 71, 73, and 105.

## Summary

| Institution | Share of system assets | Consumer account API | Best public file path | Credential terms | Aggregator coverage |
| --- | --- | --- | --- | --- | --- |
| Banreservas | 33.2%, first | None found | Monthly statements and on-screen movements. Only 2021 and 2022 third parties show an export button or CSV. | Legal notice forbids routines that interfere with the service. Contracts are image-only scans, not read. | Named by no aggregator page. One directory claims a Spanish aggregator connects to it. |
| Banco Popular Dominicano | 21.6%, second | None. A company-only API Portal returns rates, locations, and a true-or-false account check. | Fee schedule effective 2026-09-27 lists free in-app statement generation covering four years and free automatic delivery by email or SFTP | Convenio forbids letting third parties know or use credentials and presumes instructions valid even under fraud | Named by no aggregator page. The same directory claims the Spanish aggregator connects to it. |
| Banco BHD | 14.5%, third | None found | The contract approved on 2026-06-24 names statement download in digital channels. Email statements on request. | Contract forbids sharing digital-channel credentials and puts losses from shared credentials on the client | Named by no aggregator page |
| APAP | 4.2%, fifth, the largest savings and loan association | None found | Web history filters back 12 months. Only the business portal exports PDF or Excel. | Tells customers never to share credentials. No public copy of the personal online-banking terms. | Named by no aggregator page |
| Scotiabank República Dominicana | 3.9%, sixth | None. The group developer portal serves business APIs and lists open banking as coming soon, without mentioning the Dominican Republic. | Free statements in online banking and the app, format undocumented. Free email or push alerts for purchases, withdrawals, transfers, and balances. | Online-banking terms hold the customer responsible for access by anyone given the username or password | Named by no aggregator page |

Asset shares come from the Superintendencia de Bancos [list of supervised intermediaries](https://sb.gob.do/supervisados/entidades-de-intermediacion-financiera/).

Three conclusions follow.

1. No candidate offers consumer account data through an API, and no aggregator publicly names a Dominican bank it supports.
2. Popular and BHD contracts forbid sharing online-banking credentials with third parties. Credential-based access, whether Argus builds it or buys it, runs against those contracts.
3. Popular documents the strongest statement path. No bank publishes its file format, PDF text layer, file password, or history window. One consenting holder's session per bank settles all four.

## Banco Popular Dominicano

| Dimension | Finding | Label | Source |
| --- | --- | --- | --- |
| Name | Banco Popular Dominicano, S. A., Banco Múltiple. Brand Popular. | Verified through documentation | [API Portal terms](https://www.apiportal.popularenlinea.com/tsandcs) |
| Account API | The API Portal's five sandbox products are reference data: loan and deposit rates, exchange rates, and branch, ATM, and sub-agent locations. An account-confirmation API returns TRUE or FALSE for an account and ID match. Nothing returns balances, transactions, or statements. | Verified through documentation | [API products](https://www.apiportal.popularenlinea.com/product), [terms](https://www.apiportal.popularenlinea.com/tsandcs) |
| Partner program | Production access needs the company's RNC, the Dominican taxpayer number, plus a use case and a bank API license. The terms say the bank authorizes no third party to commercialize, distribute, or transmit its data. | Verified through documentation | [API support](https://www.apiportal.popularenlinea.com/support) |
| Statements | Free in-app statement generation covering four years, and free automatic statement delivery by email or SFTP. No file format is named. | Verified through documentation | [Fee schedule effective 2026-09-27](https://popularenlinea.com/historicotarifa/Documents/personal/vigente/tarifario-web-cambios-vigentes-al-27-de%20septiembre-2026-banca-personas.pdf) |
| Export and history | No public page names a CSV, Excel, OFX, or TXT export or a history window. | Requires an authorized account test | [Internet Banking page](https://popularenlinea.com/Personas/Paginas/ibPopularEnLinea/index.aspx) |
| Notices | Purchase notices come by email from `notificaciones@popularenlinea.com`, without links. Their fields are not listed. SMS notices exist. | Verified through documentation | [Security tips](https://popularenlinea.com/Personas/Paginas/nosotros/pistas-de-seguridad.aspx) |
| Authentication | Username and password. The bank may require the app-based Token Digital Popular to log in. Biometric login is optional. The app collects device identifiers to create the session. | Verified through documentation | [Convenio Único](https://popularenlinea.com/Personas/Documents/Convenio-Unico.pdf), [app terms](https://popularenlinea.com/Personas/Paginas/nosotros/tcAPP.aspx) |
| Accounts and currencies | Checking, DOP savings, USD and EUR savings, credit cards with RD$ or US$ limits, loans, and time deposits in DOP, USD, and EUR | Verified through documentation | Fee schedule, Convenio |
| Restrictions | Identification and authentication means are personal. The customer may not let third parties know or use them. Instructions are presumed valid even when fraud produced them. No clause names bots or scraping. | Verified through documentation | [Convenio Único](https://popularenlinea.com/Personas/Documents/Convenio-Unico.pdf) |
| Access controls | The online-banking host answers plain clients with an Imperva Incapsula block. The public site showed a human-verification check, which the research did not solve. | Observed on public pages | `ib.popularenlinea.com`, `www.popularenlinea.com` |

Whether a personal client can point SFTP delivery at a server of their choice is unknown. If so, it is a bank-sanctioned push channel worth more than manual downloads.

## Banreservas

| Dimension | Finding | Label | Source |
| --- | --- | --- | --- |
| Name | Banco de Reservas de la República Dominicana, Banco Múltiple, a state-owned intermediary under statutes of 2024-08-30. Brand Banreservas. | Verified through documentation | [Statutes](https://cdnebrpeastus.azureedge.net/banreservas/media/yu1plpzq/estatutos-actual.pdf) |
| Account API | No API, developer, or open-banking program appears among its ten listed channels. | Unknown | [Channels](https://www.banreservas.com/canales-banreservas/) |
| Statements | Monthly statements to home, office, email, or branch, plus on-screen consultation and printing of movements in TuBanco. No file format is named. | Observed on public pages | [Personal checking](https://www.banreservas.com/personal/cuentas/cuenta-corriente-personal/) |
| Export and history | A software vendor's 2022 article says online banking exports movements as CSV. A broker's 2021 guide shows an Exportar button. No bank page confirms either. | Vendor claim only. The current state requires an authorized account test. | [Vendor article](https://ec-tek-srl.helpscoutdocs.com/article/77-descargar-datos-desde-el-banreservas) |
| Notices | The bank tells clients to turn on real-time notifications in the app. No page names channels or fields. | Observed on public pages | [Security post](https://www.banreservas.com/articulos/alertas-falsas-banreservas/) |
| Authentication | Username and password. Transactions need the code card or Token Digital. Fingerprint login in the app. | Verified through documentation | [FAQ](https://www.banreservas.com/media/ynld3grh/faq.pdf), [terms](https://www.banreservas.com/pages/terminos-y-condiciones/) |
| Accounts and currencies | DOP savings, checking, digital accounts, the MIO wallet, USD and EUR savings, time deposits in DOP, USD, and EUR, and cards billed in pesos or with separate peso and dollar limits | Observed on public pages | [Accounts](https://www.banreservas.com/personal/cuentas/) |
| Restrictions | The legal notice forbids storing the service in a retrieval system and using any device, program, or routine to interfere with it. The contracts are image-only scans, so their credential clauses were not read. | Verified through documentation | [Legal notice](https://www.banreservas.com/pages/aviso-legal/), [contracts](https://www.banreservas.com/sobre-nosotros/contratos-de-adhesion/) |

A person reading or running OCR on the 61 scanned pages would settle the credential clauses without an account.

## Banco BHD

| Dimension | Finding | Label | Source |
| --- | --- | --- | --- |
| Name | Banco Múltiple BHD, S. A. Brand Banco BHD, formerly BHD León. | Verified through documentation | [Terms of use](https://bhd.com.do/homepage-personal/otros-servicios/calificaciones-de-riesgo/34) |
| Account API | No developer portal, API catalog, or open-banking page | Unknown | [Sitemap](https://bhd.com.do/sitemap.xml) |
| Partner program | Business clients can buy automatic movement files by SFTP and SWIFT MT940 statements. This is a precedent for machine-readable delivery, not a consumer program. | Verified through documentation | [Fee schedule, September 2026](https://static.bhd.com.do/B_Tarifario_Banco_BHD_Septiembre_2026_ae2ead8a2e.pdf) |
| Statements | The personal contract approved on 2026-06-24 offers branch pickup or download in digital channels. Checking statements go by email on request. | Verified through documentation | [Personal contract](https://static.bhd.com.do/Hoja_Resumen_Manu_Contrato_Manual_Operativo_Persona_Fisica_b56b68e42f.pdf) |
| Export and history | A broker's 2021 guide shows a movements screen with a three-month filter and a download button. No bank page states the format or window. | Vendor claim only. The current state requires an authorized account test. | [Broker guide](https://parval.com.do/wp-content/uploads/2024/05/06-2023-Guia-de-Moviemiento-de-Bancos.pdf) |
| Notices | The contract lets the bank notify by platform, email, or SMS of up to 160 characters. | Verified through documentation | Personal contract |
| Authentication | Username or ID number plus an access code. Fund movements need a key card code, an OTP by email or SMS, or a soft token. The bank may collect IP, IMEI, device model, and GPS. Sessions end after 15 minutes idle. | Verified through documentation | Personal contract clause 71, [privacy policy](https://bhd.com.do/homepage-personal/politica-de-privacidad) |
| Accounts and currencies | Savings and checking in RD$, US$, or EUR, term deposits, cards billed in RD$ and US$ with separate columns on statements | Verified through documentation | Personal contract, [card statement guide](https://static.bhd.com.do/WEB_Como_leer_el_estado_de_cuenta_tarjeta_de_credito_BHD_bd7d29a066.pdf) |
| Restrictions | Clause 73 makes authentication mechanisms personal and makes the client responsible for any operation made with them, even by an unauthorized third person, until the client notifies the bank. Clause 105 commits the client not to share digital-channel credentials with third parties. The online-banking host's robots file disallows every path except the login page. | Verified through documentation | Personal contract, `ibp.bhd.com.do/robots.txt` |
| Data rights | The privacy policy lists a data-portability right under Ley 172-13, exercised through Internet Banking, a branch, or email | Verified through documentation | [Privacy policy](https://bhd.com.do/homepage-personal/politica-de-privacidad) |

BHD's portability right is an untested, bank-sanctioned way for a person to request their own data. Its scope and format are unknown.

## Scotiabank República Dominicana

| Dimension | Finding | Label | Source |
| --- | --- | --- | --- |
| Name and status | Scotiabank República Dominicana, S. A., Banco Múltiple, operating, a subsidiary of The Bank of Nova Scotia. No sale, merger, or conversion was found for 2024 to 2026. | Verified through documentation | [Superintendencia de Bancos entity page](https://sb.gob.do/supervisados/entidades-de-intermediacion-financiera/scotiabank/) |
| Account API | No developer portal or open-banking page on the Dominican site. The group developer portal offers business payment and account-information APIs and lists open banking as coming soon, without mentioning the Dominican Republic. | Unknown for the Dominican Republic | [Group developer portal](https://developer.scotiabank.com/) |
| Statements | Online banking and the Scotia Caribbean app let the user download statements. Statements in both channels are free under the self-service tariff updated 2025-07-31. No file format is documented. | Verified through documentation | [Self-service tariff](https://do.scotiabank.com/banca-personal/tarifas/tarifas-canales-de-autoservicio.html) |
| Export and history | No CSV, Excel, or OFX export and no history window is documented. | Requires an authorized account test | [FAQ](https://do.scotiabank.com/acerca-de-scotiabank/tutoriales/preguntas-frecuentes.html) |
| Notices | Free alerts by email or app push for ATM withdrawals, purchases above a chosen amount, purchases abroad, third-party transfers, bill payments, and daily or weekly balances. Alerts never carry account numbers or passwords. Their fields are undocumented. | Observed on public pages. Fields require an authorized account test. | [Alerts](https://do.scotiabank.com/banca-personal/campaigns/alertas.html) |
| Authentication | Card number and access code, or username and password. Multi-factor enrollment is mandatory, an access code goes to the customer's email, at most three computers stay registered, and sessions close after 10 idle minutes. | Verified through documentation | [Security FAQ](https://do.scotiabank.com/acerca-de-scotiabank/conectate-con-scotia/seguridad/preguntas-mas-frecuentes.html) |
| Accounts and currencies | Savings in DOP, USD, and EUR. Checking in DOP. Certificates in DOP and USD. Cards with peso and dollar lines. | Observed on public pages | [Deposit accounts](https://do.scotiabank.com/banca-personal/cuentas-de-depositos.html) |
| Restrictions | The online-banking terms make keeping credentials safe the customer's duty, forbid disclosing them, and hold the customer responsible for access by anyone given the username or password until the bank is notified. No clause names scraping or automated access. | Verified through documentation | [Scotia en Línea terms](https://do.scotiabank.com/banca-personal/canales-alternos/Scotia-En-linea.html) |

Scotiabank placed 11th of 14 multiple banks in the personal segment of the Superintendencia de Bancos [digitalization ranking 2025](https://sb.gob.do/media/fegbathn/ranking-digitalizacio-n-2025.pdf), with 64.95 points. Popular scored 99.38, Banreservas 96.66, and BHD 96.37.

## APAP

| Dimension | Finding | Label | Source |
| --- | --- | --- | --- |
| Name and status | Asociación Popular de Ahorros y Préstamos, a mutualist savings and loan association under Law 5897 of 1962 and Ley 183-02, operating, with 454,054 members on 2025-12-31. It has not converted into a bank. | Verified through documentation | [Superintendencia de Bancos entity page](https://www.sb.gob.do/supervisados/entidades-de-intermediacion-financiera/asociacion-popular/), [2025 governance report](https://www.apap.com.do/wp-content/uploads/2026/03/APAP-GOBIERNO_2025.pdf) |
| Account API | No developer portal, API documentation, or open-banking page among the 913 URLs in its sitemaps | Unknown | [Sitemap index](https://www.apap.com.do/sitemap_index.xml) |
| Statements and history | Web banking filters movements for the last 12 months. Older movements need a branch visit. No help page describes a statement download or its format. | Verified through documentation for the 12 months. The download requires an authorized account test. | [Help FAQ](https://www.apap.com.do/guia-autoayuda-preguntas-frecuentes-apapenline-apapmovilapap-com-do/) |
| Export | Only the business portal exports history, to PDF or Excel, with date, type, description, amount, currency, and status | Verified through documentation | [Business portal guide](https://www.apap.com.do/wp-content/uploads/2024/02/Guia-de-Uso-En-Linea-Empresas-apap.pdf) |
| Notices | Card pages promise an in-app HolAPAP notice for every transaction. The channel and fields are undocumented. | Observed on public pages | [Card page](https://www.apap.com.do/productos/tarjeta-de-credito-visa-infinite/) |
| Authentication | One username and password for web and app. Linking a device needs a one-time code and a PIN. Mi Llave approves transfers on one device only. | Verified through documentation | Help FAQ |
| Accounts and currencies | Personal deposit accounts priced in RD$ only. International credit cards carry a US$ balance. Foreign currency is otherwise a branch exchange service. | Verified through documentation | [Tariff updated 2026-08-24](https://www.apap.com.do/wp-content/uploads/2021/05/Tarifario-Productos-y-Servicios-vigente-al-de-24-agosto-2026-R.pdf) |
| Restrictions | The site notice makes each user responsible for their password, and the security page tells customers never to share credentials. The public terms page holds placeholder text, and users accept the channel terms at first login. | Verified through documentation for the notice. The channel terms require an authorized account test. | [Security tips](https://www.apap.com.do/tips-de-seguridad/) |

APAP placed first of 9 savings and loan associations in the personal segment of the same digitalization ranking, with 86.61 points.

## Other institutions checked

No other institution showed a materially better entry point. Each was checked for a developer program, a consumer data API, or an unusually structured export.

| Institution | What the public pages show | Label |
| --- | --- | --- |
| Qik Banco Digital, part of Grupo Popular | Its help page says "Solicitar documentos" generates a statement for any time range the user chooses. No format or maximum depth is named. | Verified through documentation |
| Banco Santa Cruz, 5.0% of assets | Guides for statements and movements. No format, depth, API, or export is named. | Observed on public pages |
| Banco BDI | Statements by email or in BDI Digital. No format or API. | Verified through documentation |
| Banesco, Banco Promerica, Banco Vimenca, Asociación Cibao, Asociación La Nacional | No API, export format, or aggregator clause found | Observed on public pages or verified through documentation |
| Banco Caribe | Its robots file and homepage returned HTTP 403. The research recorded the block and did not work around it. | Unknown |
| tPago | A payments app that shows balances and history for nine institutions after branch enrollment. It offers no third-party access. | Vendor claim only |
| MIO and Billet, the Banreservas and BHD e-money products | Merchant reports and three months of movements. No export or API. | Verified through documentation |

Two industry signals matter for a partnership conversation. The same digitalization ranking reports that statement generation is available at 90% of intermediaries in 2025, and that 71.1% have API connections, a third of them used externally. A November 2025 press column reports that Adofintech, Banreservas, Popular, and BHD set up an industry sandbox, Fintech Laboratory RD, in June 2025. No primary source for that sandbox was found.

## Aggregators

| Provider | Dominican institutions named | Access method | Label | Source |
| --- | --- | --- | --- | --- |
| Bridge (Bridge Labs, S.R.L.) | None publicly. Its pages use placeholder banks. It claims one integration reaches every supported Dominican institution. | The user authorizes Bridge as a limited agent to log in on the user's behalf. Bridge stores encrypted session tokens and says no bank sponsors it. | Verified through documentation for the method. Vendor claim only for coverage. | [Connect terms, updated 2025-10-10](https://bridge.com.do/terminos-uso-bridge-connect), [docs](https://docs.bridge.com.do/guides/connect) |
| Prometeo | None. A January 2026 roadmap names the Dominican Republic as a planned market. Its docs now require a password. | Unknown | Vendor claim only | [Prometeo](https://prometeoapi.com/) |
| Belvo, Finerio Connect, Syncfy, Fintoc, Pluggy | None. Coverage is Brazil, Mexico, Colombia, or Chile. Finerio's "Banco Popular" and "Scotiabank" are the Colombian and Mexican banks. Syncfy's and Paybook's robots files disallow Anthropic's agents, so the research did not read their main sites. | Unknown | Observed on public pages | Provider sites and documentation |
| Salt Edge | Its Dominican Republic coverage page shows 0 connections today. Archived copies of its Dominican country page, read by the research note, list screen-scraping connectors for Banco Popular Dominicano and Banreservas from 2017, BHD León and Banco Dominicano del Progreso by 2019, three still listed in October 2021, and none from July 2022. The reason for dropping them is unknown. The report author could not re-read the archived copies because the page renders its list by script. | Screen scraping with the user's credentials, and one Excel file import | Observed on public pages for today. Archived history from the research note. | [Salt Edge coverage](https://www.saltedge.com/products/account_information/coverage/do), [archived country page](https://web.archive.org/web/20211020071324/https://www.saltedge.com/products/spectre/countries/do) |
| Plaid | Coverage is the United States, Canada, and the United Kingdom and Europe. | Not applicable | Observed on public pages | [Plaid institutions](https://plaid.com/docs/institutions/) |
| Envestnet Yodlee | Publishes no country breakdown | Unknown | Unknown | [Yodlee](https://www.yodlee.com/) |
| Wealthreader | Open Banking Tracker lists it as connected to Banreservas and Banco Popular. Neither bank confirms it. | Unknown | Vendor claim only | [Open Banking Tracker](https://www.openbankingtracker.com/country/dominican-republic/aggregators) |
| tPago | A payments app that lists nine institutions in its ecosystem, including Scotiabank, and shows their balances and history in its own app. It offers no third-party API. | Bank-activated service | Vendor claim only | [tPago](https://tpago.com/) |

"Supports Latin America" appears on several provider sites. None of them names a Dominican institution.

### Bridge in detail

Bridge is the only provider built for the Dominican market. Its evidence matters because Argus could integrate it without building credential custody.

- **Company.** Bridge Labs, S.R.L., constituted under Dominican law, founders presented at ADOFINTECH's Fintech Market on 2025-07-03.
- **Product.** A read-only REST API for connections, accounts, and transactions, a Connect widget that handles credentials, MFA, and account selection, React and React Native SDKs with native SDKs in progress, a sandbox with fictional banks, and a developer dashboard. Transaction status is `pending`, `posted`, or `void`.
- **Access method.** Credential-based. The user makes Bridge a limited agent to log in on the user's behalf. The privacy policy lets Bridge process username, password, and MFA codes when no alternative such as OAuth exists. The terms disclaim any bank affiliation.
- **Credentials and sessions.** The privacy policy says credentials are not stored and are deleted after first authentication. The Connect terms say session tokens are stored encrypted for continued access. Ongoing refresh therefore depends on stored bank sessions.
- **Revocation.** An integrating app revokes with `DELETE /connections/{connectionId}`. Data stays available for 30 days after revocation, then Bridge deletes it. End users revoke by writing to Bridge's privacy address.
- **Security and assurance.** No SOC 2, ISO 27001, PCI DSS, or penetration-test attestation is claimed.
- **Subprocessors.** Bright Data proxies in the United Kingdom, the United States, and Israel, PostHog, Clerk, Loops, Sentry, and OpenAI for personalization. Whether bank traffic goes through the proxies is unknown.
- **Terms.** Liability is capped at the last month billed. End users indemnify Bridge, including for obligations toward their own bank. Dominican law and courts govern.
- **Pricing.** A free Developer plan with unlimited sandbox connections and 3 active live personal connections. Paid plan prices are unpublished.
- **Use by Argus.** Designed for third-party developers after Bridge approves a registration with a tax ID. Argus would have to store a per-user scoped token that Bridge returns once.
- **Regulatory status.** No claim of Superintendencia de Bancos authorization, supervision, or sandbox participation.
- **AI connectors.** The homepage claims an MCP server for Claude and ChatGPT. No public documentation for it exists, and it is not listed in either public directory.

## What only an authorized account test can settle

Each test uses a consenting holder's own account, run by that holder on their own device. No test shares credentials with Argus.

| Test | Who | What it establishes |
| --- | --- | --- |
| Generate and download statements for each product in each bank's app and website | The founder or another consenting holder | File type, PDF text layer, file password, history window, and which products and currencies produce statements |
| Use each bank's movements export | Same | CSV, Excel, TXT, or OFX availability, columns, and the longest date range |
| Enroll in email statements, and ask Popular whether a personal client can use SFTP delivery | Same | Attachment or link, password, format, and whether a push channel to a chosen server exists |
| Make a card purchase and read the notice | Same | Notice fields, latency, and sender stability, which decide whether forwarding can draft entries |
| Log in from a new device | Same | Whether login alone needs a token or key card, device binding, and idle timeout |
| File BHD's data-portability request | Same | Whether a Ley 172-13 request returns transactions, in what format, and how fast |
| Open Bridge Connect's bank picker in a free developer account | The founder, after legal review | Which banks Bridge actually lists |
| Link a real account through Bridge for two to four weeks | The founder, only after counsel reviews the credential-sharing questions | MFA handling, history depth, refresh cadence, reconnection frequency, and bank security alerts. This test shares credentials with a third party, which Popular's and BHD's terms forbid. |

## Method and limits

- Popular's websites refuse non-browser HTTP clients through Imperva Incapsula. Popular evidence came from an ordinary browser session on its public host. No verification challenge was solved, and nothing was automated against online banking.
- Banreservas' key contracts are image-only scans, and no OCR engine was available.
- The session's shared web-search allowance ran out partway through. Later discovery used site navigation, sitemaps, and linked documents.
- Search-result snippets never served as evidence in any row.
