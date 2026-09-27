# Bank access matrix for Popular, Banreservas and BHD

This file records public evidence on how Argus could obtain user-authorized balances and transactions from three Dominican banks before they offer consumer APIs. Every row was seen on 2026-09-27. The research used public pages only. Nobody signed in, enrolled, submitted a form, installed an app, or contacted a bank.

## Evidence labels

Each row carries exactly one label.

- Verified through documentation. An official bank help page, manual, FAQ, terms, fee schedule, contract template, or regulator page describes the point concretely.
- Observed on public pages. A public product, marketing, app-store, or technical page shows it without concrete documentation. Robots files and bot blocks use this label.
- Vendor claim only. A third party says it and the bank has not confirmed it. In this file the label covers every third party: aggregators, software vendors, brokers and the press.
- Unknown. No public evidence was found either way.
- Requires an authorized account test. Public evidence cannot settle it and a logged-in session would.

## Decision summary

- The Superintendencia de Bancos (SB) ranks Banreservas first by total assets (33.2%), Popular second (21.6%) and BHD third (14.5%).
- None of the three offers a consumer account API. Popular's API Portal serves companies under a license and returns reference data plus a true-or-false account check.
- Popular and BHD contracts forbid letting third parties know or use banking credentials, and both presume instructions valid even when fraud produced them. Banreservas' legal notice forbids routines that interfere with its service, and its contracts are image-only scans.
- Bridge is the only aggregator that claims Dominican coverage. It names no bank and logs in with the user's own credentials, which conflicts with the Popular and BHD terms.
- The SB lists open-banking regulation as a project in progress for the second half of 2026. No rule text is published.
- Popular is the best first candidate for a user-downloaded file import. Its fee schedule, effective 27 September 2026, offers free in-app statement generation covering four years and free automatic statement delivery by email or SFTP. BHD comes second. Its SB-stamped contract names digital download as a statement channel, but it states no history depth. Banreservas is the largest bank, but only third parties from 2021 and 2022 show an export button or a CSV file.
- No public source confirms any bank's file format, PDF text layer, password, or history window. One consenting-account session per bank would settle all four.

## Banco Popular Dominicano

| Dimension | Finding | Evidence label | Source URL | Date seen |
|---|---|---|---|---|
| 1 Name | The API Portal terms name the bank Banco Popular Dominicano, S. A., Banco Múltiple. The consumer brand is Popular. | Verified through documentation | https://www.apiportal.popularenlinea.com/tsandcs | 2026-09-27 |
| 1 Size | The SB list of supervised entities shows Banco Popular with RD$961,454.06 million in total assets and a 21.6% share, second of the three banks. | Verified through documentation | https://sb.gob.do/supervisados/entidades-de-intermediacion-financiera/ | 2026-09-27 |
| 2 API catalog | The API Portal sandbox lists five products, all reference data: loan and deposit rates, USD and EUR exchange rates in DOP, and sub-agent, branch and ATM locations. None returns balances, transactions or statements. | Verified through documentation | https://www.apiportal.popularenlinea.com/product | 2026-09-27 |
| 2 Account check | The portal terms, updated 14 Aug 2024, describe an account-confirmation API where "La API devuelve TRUE o FALSE" for an account and ID-number match. The bank approves each subscription, and the sandbox holds fictitious data. | Verified through documentation | https://www.apiportal.popularenlinea.com/tsandcs | 2026-09-27 |
| 2 Redistribution | The same terms say the bank has not authorized any third party to commercialize, distribute or transmit the bank's data on its own account. They set no caching or storage rule. | Verified through documentation | https://www.apiportal.popularenlinea.com/tsandcs | 2026-09-27 |
| 2 API access | Production access needs sandbox validation, a support ticket with the company RNC, legal name, use case and API list, and a bank API license agreement. The program serves companies, not consumers. | Verified through documentation | https://www.apiportal.popularenlinea.com/support | 2026-09-27 |
| 2 Open banking | A 30 June 2025 press release presents the portal as open banking for "filiales, socios estratégicos y desarrolladores". It announces no consumer data-sharing API. | Observed on public pages | https://popularenlinea.com/Personas/sala-de-prensa/Pages/Popular-lanza-API-Portal-plataforma-pionera-open-banking-pais.aspx | 2026-09-27 |
| 3 Statements | The personal fee schedule effective 27 Sep 2026 lists "Generación estados de cuentas desde App (primeros 4 años)" and automatic statement delivery by email or SFTP as free. Printed monthly statements at a branch cost RD$150 after the first month. No file format is named. | Verified through documentation | https://popularenlinea.com/historicotarifa/Documents/personal/vigente/tarifario-web-cambios-vigentes-al-27-de%20septiembre-2026-banca-personas.pdf | 2026-09-27 |
| 3 Statements | The Convenio Único, updated August 2026, says an account may or may not generate monthly statements, and clients can review movements in Internet Banking, mobile banking and other designated channels. Checking accounts and credit cards get monthly statements by physical or electronic means. | Verified through documentation | https://popularenlinea.com/Personas/Documents/Convenio-Unico.pdf | 2026-09-27 |
| 3 Export | No public page names a CSV, Excel, OFX or TXT export, or a history window, for personal Internet Banking or the app. The Internet Banking FAQ answers open only through click controls, which this research did not use. | Requires an authorized account test | https://popularenlinea.com/Personas/Paginas/ibPopularEnLinea/index.aspx | 2026-09-27 |
| 3 Old platform | A broker's client guide with 2021 screenshots shows the previous Internet Banking on bpd.com.do searching transactions by date range and printing the list to PDF through the browser. No export button appears. | Vendor claim only | https://parval.com.do/wp-content/uploads/2024/05/06-2023-Guia-de-Moviemiento-de-Bancos.pdf | 2026-09-27 |
| 3 Email notices | The security help page says purchase notices come by email without links, and "Las notificaciones llegan de notificaciones@popularenlinea.com". It does not list their fields. | Verified through documentation | https://popularenlinea.com/Personas/Paginas/nosotros/pistas-de-seguridad.aspx | 2026-09-27 |
| 3 SMS notices | The fee schedule charges RD$2.50 for each SMS sent, so SMS notices exist. Their triggers and content are not described. | Verified through documentation | https://popularenlinea.com/historicotarifa/Documents/personal/vigente/tarifario-web-cambios-vigentes-al-27-de%20septiembre-2026-banca-personas.pdf | 2026-09-27 |
| 3 Business files | Extracto Bancario is a business service that reports every account movement daily for automated reconciliation. The page names no file format and no personal eligibility. | Observed on public pages | https://popularenlinea.com/empresarial/paginas/pagos-y-recaudos/extracto-bancario.aspx | 2026-09-27 |
| 3 App | The Google Play listing, updated 1 Sep 2026 with over 1 million downloads, describes queries, payments and transfers in DOP, USD or EUR and a digital Token Popular. It names no statement or export feature. | Observed on public pages | https://play.google.com/store/apps/details?id=com.popular.app.android&hl=es | 2026-09-27 |
| 4 Token | The Convenio defines Token Digital Popular as an app function that generates one-time keys for access, instructions and transactions. The bank may require it as a condition to log in. | Verified through documentation | https://popularenlinea.com/Personas/Documents/Convenio-Unico.pdf | 2026-09-27 |
| 4 Login and device | The app terms keep username and password login, make biometric login optional, and collect hardware ID, device model and OS data to create the session. Their digital-sales section lists fingerprint, Face ID or a 4-digit PIN, and customer-set security questions. | Verified through documentation | https://popularenlinea.com/Personas/Paginas/nosotros/tcAPP.aspx | 2026-09-27 |
| 4 Onboarding | The App Gnial onboarding terms describe a username and password, a 6-digit code sent by email, fingerprint registration, and token installation before any transaction. | Verified through documentation | https://popularenlinea.com/Personas/Paginas/cuentas/content-sections/cuenta-ahorro-gnial/Terminos-Condiciones-servicio-Onboarding-Digital.pdf | 2026-09-27 |
| 4 Token cost | The fee schedule issues a physical or digital token free and charges RD$500 to replace a lost or stolen physical token. | Verified through documentation | https://popularenlinea.com/historicotarifa/Documents/personal/vigente/tarifario-web-cambios-vigentes-al-27-de%20septiembre-2026-banca-personas.pdf | 2026-09-27 |
| 4 Session | No public page states a session timeout, SMS one-time codes for personal login, or an anti-phishing image. | Unknown | https://popularenlinea.com/Personas/Paginas/nosotros/content-sections/Pistas-seguridad-landings/pista-de-seguridad-canales.aspx | 2026-09-27 |
| 5 Accounts | The fee schedule covers checking, DOP savings, USD and EUR savings, credit cards, loans, and time deposits in DOP, USD and EUR. | Verified through documentation | https://popularenlinea.com/historicotarifa/Documents/personal/vigente/tarifario-web-cambios-vigentes-al-27-de%20septiembre-2026-banca-personas.pdf | 2026-09-27 |
| 5 Cards | The Convenio allows card limits in RD$ or US$, lets the bank move the cut date with 30 days' notice, and gives clients 120 days from the cut date to dispute a charge. | Verified through documentation | https://popularenlinea.com/Personas/Documents/Convenio-Unico.pdf | 2026-09-27 |
| 6 Credentials | The Convenio makes identification and authentication means personal and forbids storing them on any device "ni permitir que terceros lo conozcan o utilicen". | Verified through documentation | https://popularenlinea.com/Personas/Documents/Convenio-Unico.pdf | 2026-09-27 |
| 6 Liability | The Convenio makes the client responsible for custody of the user ID, access code and password. Instructions are presumed valid even when a fraudulent maneuver by related or unrelated persons produced them. | Verified through documentation | https://popularenlinea.com/Personas/Documents/Convenio-Unico.pdf | 2026-09-27 |
| 6 Site terms | The website terms, updated 26 Jun 2017, make users responsible for password confidentiality and forbid reproducing or transmitting content without written permission. They say nothing about bots or scraping. | Verified through documentation | https://popularenlinea.com/Personas/Paginas/nosotros/aviso-legal.aspx | 2026-09-27 |
| 6 Automated access | Keyword searches of the Convenio and the app terms found no clause on automated access, bots or screen scraping. | Unknown | https://popularenlinea.com/Personas/Documents/Convenio-Unico.pdf | 2026-09-27 |
| 6 robots.txt | The main site's robots.txt disallows only the SharePoint paths /_layouts/, /_vti_bin/ and /_catalogs/. | Observed on public pages | https://popularenlinea.com/robots.txt | 2026-09-27 |
| 6 robots.txt | The online-banking host ib.popularenlinea.com answered a plain client's robots.txt request with an Imperva Incapsula block page (HTTP 403), and another client got HTTP 503 and then a redirect loop. | Observed on public pages | https://ib.popularenlinea.com/robots.txt | 2026-09-27 |
| 6 robots.txt | The registration and password-reset hosts bpd.com.do and www.bpd.com.do disallow every path for all agents. | Observed on public pages | https://www.bpd.com.do/robots.txt | 2026-09-27 |
| 6 Bot protection | www.popularenlinea.com showed a human-verification check in the browser, which this research did not solve. WebFetch received empty bodies from every popularenlinea.com HTML page, and plain HTTP clients received 403 or timeouts. | Observed on public pages | https://www.popularenlinea.com/ | 2026-09-27 |
| 7 Bank on sharing | The app terms keep customer data in internal databases that "no son compartidas con ninguna entidad tercera", and allow sharing with a third party only on the customer's express authorization. | Verified through documentation | https://popularenlinea.com/Personas/Paginas/nosotros/tcAPP.aspx | 2026-09-27 |
| 7 Bank on sharing | The privacy policy, approved under SB Oficio 000329 of 28 Jan 2020, bars disclosing confidential data to third parties without the customer's express authorization or a legal order. | Verified through documentation | https://popularenlinea.com/Personas/Paginas/nosotros/politicas-de-seguridad.aspx | 2026-09-27 |
| 7 Bank on aggregators | No Popular page read mentions aggregators, screen scraping or fintech access to customer accounts. | Unknown | https://popularenlinea.com/Personas/sala-de-prensa/Pages/Popular-lanza-API-Portal-plataforma-pionera-open-banking-pais.aspx | 2026-09-27 |
| 7 Bridge | Bridge claims coverage of supported Dominican institutions but names no bank on any public page, so its coverage of Popular is unknown. | Unknown | https://bridge.com.do/ | 2026-09-27 |
| 7 Other aggregators | Belvo, Salt Edge and Plaid publish coverage lists without the Dominican Republic. Prometeo and Envestnet Yodlee publish no list that could be checked. | Observed on public pages | https://www.saltedge.com/products/account_information/coverage | 2026-09-27 |

### Notes on Popular

- Popular documents the strongest statement-file path of the three. Its current fee schedule offers in-app statement generation covering four years and automatic delivery by email or SFTP, all free.
- The personal fee schedule lists SFTP delivery, which is unusual for consumers. Whether a personal client can point SFTP delivery at a server they choose is unknown. If they can, that is a bank-sanctioned push channel worth more than manual downloads.
- The only API program is a company-facing portal with reference data and an account check. Its terms deny third parties any authorization to redistribute the bank's data.
- Credential-based aggregation is barred by the Convenio and blocked in practice. The bank may require the app-bound token at login, and the token lives on the customer's phone.
- Purchase notices come from one fixed email sender, so user-configured forwarding to a parser is a second path to test.
- The public site sits behind Imperva Incapsula and a human-verification check. Evidence came through a normal browser session, and plain HTTP clients were refused.

## Banreservas

| Dimension | Finding | Evidence label | Source URL | Date seen |
|---|---|---|---|---|
| 1 Name | The statutes dated 30 Aug 2024 under Ley 13-24 give the legal name Banco de Reservas de la República Dominicana, Banco Múltiple, an autonomous state-owned financial intermediary. The brand is Banreservas. | Verified through documentation | https://cdnebrpeastus.azureedge.net/banreservas/media/yu1plpzq/estatutos-actual.pdf | 2026-09-27 |
| 1 Old name form | The privacy policy, last revised 4 Aug 2020, still uses the older form Banco de Servicios Múltiples. | Verified through documentation | https://www.banreservas.com/pages/politica-de-privacidad/ | 2026-09-27 |
| 1 Size | The SB list shows Banreservas with RD$1,473,424.85 million in total assets and a 33.2% share, first of the three banks. The SB entity page says its data was updated 1 Sep 2026. | Verified through documentation | https://sb.gob.do/supervisados/entidades-de-intermediacion-financiera/banreservas/ | 2026-09-27 |
| 2 API | The channels index lists ten channels, and none is an API, developer or open-banking program. The business section and its Convenios page describe no API, host-to-host or file integration. | Unknown | https://www.banreservas.com/canales-banreservas/ | 2026-09-27 |
| 2 API | A text search of the 2024 sustainability report found no mention of APIs, fintechs, open banking or aggregators. | Unknown | https://www.banreservas.com/media/zobd3vzb/informe-de-sostenibilidad-2024-banco-de-reservas.pdf | 2026-09-27 |
| 2 Business files | The fee schedule, last revised 10 Apr 2026, prices account statements sent by SWIFT at USD 20. No consumer data channel appears. | Verified through documentation | https://cdnebrpeastus.azureedge.net/banreservas/media/nwkhak3h/tarifario-web-abril-2026-3-1.pdf | 2026-09-27 |
| 3 Statements | The personal checking page promises monthly statements delivered to home, office, email or a branch, plus "consulta e impresión de movimientos en TuBanco". It names no file format. | Observed on public pages | https://www.banreservas.com/personal/cuentas/cuenta-corriente-personal/ | 2026-09-27 |
| 3 Movements | The FAQ PDF, created in December 2016, says online banking shows balances and movements for DOP and USD savings, checking, credit cards, loans and certificates. It says nothing about downloads, formats or history depth. | Verified through documentation | https://www.banreservas.com/media/ynld3grh/faq.pdf | 2026-09-27 |
| 3 Reprints | The fee schedule charges RD$100 to reprint statements and account movements, without naming the channel. | Verified through documentation | https://cdnebrpeastus.azureedge.net/banreservas/media/nwkhak3h/tarifario-web-abril-2026-3-1.pdf | 2026-09-27 |
| 3 Export | A Dominican software vendor's knowledge base, dated 18 Aug 2022, says internet banking exports account movements as CSV from Consulta, then Cuentas, then Consultar. | Vendor claim only | https://ec-tek-srl.helpscoutdocs.com/article/77-descargar-datos-desde-el-banreservas | 2026-09-27 |
| 3 Export | A broker's client guide with 2021 screenshots shows the TuBanco Consulta screen with a date range and an Exportar button, and tells clients to export a PDF. | Vendor claim only | https://parval.com.do/wp-content/uploads/2024/05/06-2023-Guia-de-Moviemiento-de-Bancos.pdf | 2026-09-27 |
| 3 Export | No Banreservas page confirms an export option, its format or the history window. | Requires an authorized account test | https://www.banreservas.com/canales-banreservas/tubanco-personas/ | 2026-09-27 |
| 3 Notices | A bank security post tells clients "Activa notificaciones en tiempo real desde la app". No page names the notice channels or fields. | Observed on public pages | https://www.banreservas.com/articulos/alertas-falsas-banreservas/ | 2026-09-27 |
| 3 Other channels | The FAQ PDF lists a balance glance in the app without signing in, and a *960# USSD channel that shows balances and movements behind a PIN. | Verified through documentation | https://www.banreservas.com/media/ynld3grh/faq.pdf | 2026-09-27 |
| 4 Login | The site terms say clients sign in with a self-chosen username and password after a one-time registration. | Verified through documentation | https://www.banreservas.com/pages/terminos-y-condiciones/ | 2026-09-27 |
| 4 Transactions | The FAQ PDF ties app and online-banking transactions to the physical code card with "Recuerda tener tu tarjeta de código a mano". The app accepts fingerprint login. | Verified through documentation | https://www.banreservas.com/media/ynld3grh/faq.pdf | 2026-09-27 |
| 4 Token | The Google Play listing, updated 14 Sep 2026, offers transaction authorization with Token Digital and biometric sign-in. Its data-safety summary says the app may share app activity and device IDs with third parties. | Observed on public pages | https://play.google.com/store/apps/details?id=com.banreservas.tubancoappmobile&hl=es | 2026-09-27 |
| 4 Token cost | The fee schedule issues the code card free and charges RD$250 to replace it. The token is free for the first two and costs RD$2,250 from the third. | Verified through documentation | https://cdnebrpeastus.azureedge.net/banreservas/media/nwkhak3h/tarifario-web-abril-2026-3-1.pdf | 2026-09-27 |
| 4 Phone channel | The contact center authenticates callers by voiceprint, and its automated menu answers balance and movement queries. | Observed on public pages | https://www.banreservas.com/canales-banreservas/centro-de-contacto/ | 2026-09-27 |
| 4 Session | No page describes session timeouts, security questions, device registration or an anti-phishing image. | Unknown | https://banreservas.com/programas/tu-seguridad/ | 2026-09-27 |
| 5 Accounts | Personal accounts include DOP savings, checking, Cuenta Digital and the MIO e-wallet, plus USD and EUR savings. Digital time deposits come in DOP, USD and EUR. | Observed on public pages | https://www.banreservas.com/personal/cuentas/ | 2026-09-27 |
| 5 Currencies | The transfer-limits sheet sets per-type limits in DOP, USD and EUR for TuBanco and the app, and keeps international and brokerage transfers on TuBanco only. | Verified through documentation | https://cdnebrpeastus.azureedge.net/banreservas/media/kgikmvb0/limites-en-portal-web-banreservas-personas-11-1.pdf | 2026-09-27 |
| 5 Cards | Credit cards bill in pesos (multimoneda) or carry separate peso and dollar limits (doble saldo). | Observed on public pages | https://www.banreservas.com/personal/tarjetas/ | 2026-09-27 |
| 5 Card cycle | The February 2025 card-fees guide says the cut date is monthly and the statement details at least a month of transactions. It does not say how statements are delivered. | Verified through documentation | https://www.banreservas.com/media/ybshtlsn/instructivo-prousuario-web-br-feb-2025.pdf | 2026-09-27 |
| 6 Automated access | The legal notice forbids storing any part of the service in an information-retrieval system and using "ningún dispositivo, programa informático o rutina para interferir" with it. No clause names bots, scraping or credential sharing. | Verified through documentation | https://www.banreservas.com/pages/aviso-legal/ | 2026-09-27 |
| 6 Liability | The credit-card summary sheet holds the cardholder liable for all use after activation, barring bank fault, until they report a loss or data exposure. | Verified through documentation | https://cdnebrpeastus.azureedge.net/banreservas/media/dvib45rd/hoja-de-resumen-tarjeta-de-cre-dito.pdf | 2026-09-27 |
| 6 Codes | A bank post calls the one-time code "personal e intransferible" and says never to share it. Another post treats apps that ask for bank credentials as fraud. | Observed on public pages | https://www.banreservas.com/articulos/por-que-nunca-debes-compartir-tu-codigo-de-verificacion/ | 2026-09-27 |
| 6 Contracts | The banking services contract (4 pages), its operations manual (44 pages) and the digital services terms (13 pages) are image-only scans without a text layer. Their credential, third-party and automated-access clauses were not read. | Unknown | https://www.banreservas.com/sobre-nosotros/contratos-de-adhesion/ | 2026-09-27 |
| 6 robots.txt | No robots file exists on www.banreservas.com (302 to /404), www.banreservas.com.do (404), tubanco.banreservas.com (301 into the app) or the document CDN (400). Nothing is disallowed. | Observed on public pages | https://www.banreservas.com/robots.txt | 2026-09-27 |
| 7 Bank on sharing | The privacy policy limits third-party sharing to agents, providers, regulators, courts, collectors and debt buyers. It grants access, rectification, opposition and cancellation rights, with no client-directed sharing or portability. | Verified through documentation | https://www.banreservas.com/pages/politica-de-privacidad/ | 2026-09-27 |
| 7 Bank on apps | A September 2025 bank post says "Muchas apps se sincronizan con tus cuentas bancarias y tarjetas" and names Mint and Fintonic. It never says Banreservas accounts can be linked. | Observed on public pages | https://www.banreservas.com/articulos/herramientas-digitales-para-llevar-un-control-de-gastos/ | 2026-09-27 |
| 7 Bridge | Bridge names no bank on any public page, so its coverage of Banreservas is unknown. | Unknown | https://bridge.com.do/ | 2026-09-27 |
| 7 Other aggregators | Belvo, Salt Edge and Plaid publish coverage lists without the Dominican Republic. Prometeo and Envestnet Yodlee publish no list that could be checked. | Observed on public pages | https://www.saltedge.com/products/account_information/coverage | 2026-09-27 |

### Notes on Banreservas

- Banreservas is the largest bank and has the weakest public documentation of a statement file. Its own pages promise monthly statements and on-screen or printed movements. Only third parties, in 2021 and 2022, show an Exportar button and a CSV export.
- The contract, operations manual and digital services terms that would settle the credential clauses are image-only scans. A human read or OCR pass of those 61 pages would close that gap without an account.
- The legal notice already rules out scraping. It bans storing the service in a retrieval system and running routines against it.
- Transactions need the code card or Token Digital. Public pages suggest login needs only a username and password, and a test must confirm it.
- The FAQ PDF dates from 2016 and describes the older online-banking name, so its feature list may be stale.

## Banco BHD

| Dimension | Finding | Evidence label | Source URL | Date seen |
|---|---|---|---|---|
| 1 Name | The terms of use and the personal accounts contract name the bank Banco Múltiple BHD, S. A., with RNC 1-01-13679-2. The brand is Banco BHD. | Verified through documentation | https://bhd.com.do/homepage-personal/otros-servicios/calificaciones-de-riesgo/34 | 2026-09-27 |
| 1 Name change | Diario Libre reported on 1 Jul 2022 that the bank "será solo Banco BHD" from that day. No bank page read states the change. | Vendor claim only | https://www.diariolibre.com/economia/finanzas/2022/07/01/banco-bhd-leon-cambia-de-nombre-desde-hoy/1923112 | 2026-09-27 |
| 1 Legacy names | www.bhdleon.com.do redirects to bhd.com.do, ib.bhd.com.do returns 404 with a meta refresh to bhdleon.com.do, and app-store slugs still read bhdleon. | Observed on public pages | https://www.bhdleon.com.do/ | 2026-09-27 |
| 1 Size | The SB list shows Banco BHD with RD$645,937.84 million in total assets and a 14.5% share, third of the three banks. | Verified through documentation | https://sb.gob.do/supervisados/entidades-de-intermediacion-financiera/ | 2026-09-27 |
| 2 API | Site navigation, a sample of the sitemap and the terms show no developer portal, API catalog or open-banking page. | Unknown | https://bhd.com.do/sitemap.xml | 2026-09-27 |
| 2 Business files | The September 2026 fee schedule prices automatic delivery of account movements by SFTP (monthly, up to RD$3,000, US$70 or EUR 70) and SWIFT MT940 statements (monthly, up to RD$6,000, US$100 or EUR 100), under Cash Management and business Internet Banking. | Verified through documentation | https://static.bhd.com.do/B_Tarifario_Banco_BHD_Septiembre_2026_ae2ead8a2e.pdf | 2026-09-27 |
| 2 SME site | open.bhd.com.do is an SME financing and content site with no API or developer program. | Observed on public pages | https://open.bhd.com.do/ | 2026-09-27 |
| 3 Statements | The personal accounts contract, which carries an SB approval stamp dated 24 Jun 2026, offers two statement options per account, branch pickup or "Descarga en canales digitales". The bank must provide monthly statements. | Verified through documentation | https://static.bhd.com.do/Hoja_Resumen_Manu_Contrato_Manual_Operativo_Persona_Fisica_b56b68e42f.pdf | 2026-09-27 |
| 3 Email statements | The personal checking page says monthly statements are "enviados por correo electrónico según solicitud del cliente". | Observed on public pages | https://bhd.com.do/homepage-personal/cuentas-e-inversion-personal/cuentas-corrientes/product-detail/28 | 2026-09-27 |
| 3 Statement fees | The fee schedule sends checking statements free and charges RD$100 for a copy of a checking statement or of savings movements. | Verified through documentation | https://static.bhd.com.do/B_Tarifario_Banco_BHD_Septiembre_2026_ae2ead8a2e.pdf | 2026-09-27 |
| 3 Export | A broker's client guide with 2021 screenshots shows the Ver movimientos screen with a three-month filter, a statement selector, and Descargar movimientos and Imprimir buttons. Its columns are date, reference number, description, voucher, debits, credits and balance. | Vendor claim only | https://parval.com.do/wp-content/uploads/2024/05/06-2023-Guia-de-Moviemiento-de-Bancos.pdf | 2026-09-27 |
| 3 Export | No BHD page states the download file format or the history window. | Requires an authorized account test | https://bhd.com.do/homepage-personal/faqs | 2026-09-27 |
| 3 Card statements | The 2024 card statement guide shows the cut date, due date, and separate PESOS and DÓLARES columns for previous balance, payments, purchases and balance at cut, plus the Cuotas BHD installment line. | Verified through documentation | https://static.bhd.com.do/WEB_Como_leer_el_estado_de_cuenta_tarjeta_de_credito_BHD_bd7d29a066.pdf | 2026-09-27 |
| 3 Card cycle | A card guide page defines the statement as a month of transactions and the cut date as the close of a 30 to 31 day cycle. It does not say how statements are delivered. | Verified through documentation | https://bhd.com.do/homepage-personal/otros-servicios/products-detail/110 | 2026-09-27 |
| 3 Notices | The contract lets the bank notify clients through the platform, email or SMS, and defines SMS alerts as messages of up to 160 characters about product status. | Verified through documentation | https://static.bhd.com.do/Hoja_Resumen_Manu_Contrato_Manual_Operativo_Persona_Fisica_b56b68e42f.pdf | 2026-09-27 |
| 3 Notices | The security page asks clients to keep their phone and email current to receive transaction notifications. It names no channel type and no fields. | Observed on public pages | https://bhd.com.do/homepage-personal/products-detail/109 | 2026-09-27 |
| 3 Other channels | The EVA assistant on WhatsApp shows a savings balance after a one-time code sent to the client's email. | Observed on public pages | https://bhd.com.do/homepage-personal/otros-servicios/eva | 2026-09-27 |
| 3 App | Google Play lists Móvil Banking Personal BHD, with over 1 million downloads and an update on 17 Sep 2026, for queries, transfers and payments with fingerprint, pattern or PIN login. It names no statement or export feature. | Observed on public pages | https://play.google.com/store/apps/details?id=com.artech.infocorp_bhd.bhd&hl=es_DO&gl=US | 2026-09-27 |
| 4 Login | Contract clause 71 has clients enter remote banking with a username or ID number plus an access code. For fund movements the bank asks, at its option, for a key from the TPC key card, an OTP sent by email or SMS, or a Soft Token. | Verified through documentation | https://static.bhd.com.do/Hoja_Resumen_Manu_Contrato_Manual_Operativo_Persona_Fisica_b56b68e42f.pdf | 2026-09-27 |
| 4 Device | Clause 71 lets the bank collect the IP address, IMEI, device make and model, and GPS coordinates of the device used for remote banking. | Verified through documentation | https://static.bhd.com.do/Hoja_Resumen_Manu_Contrato_Manual_Operativo_Persona_Fisica_b56b68e42f.pdf | 2026-09-27 |
| 4 Session | The privacy policy's security tips say a validation code under the PIN field changes at every Internet Banking login, and the session ends "al transcurrir 15 minutos sin actividad". The policy lists multifactor authentication among its controls. | Verified through documentation | https://bhd.com.do/homepage-personal/politica-de-privacidad | 2026-09-27 |
| 4 Token | Token Digital Personal lives in the mobile app, and activating it registers the device. Internet Banking users type the code the app shows. | Observed on public pages | https://bhd.com.do/homepage-personal/otros-servicios/token-digital-personal | 2026-09-27 |
| 4 Key card | A separate digital key card app, activated with a cédula, replaces the physical key card for Internet and mobile banking. | Observed on public pages | https://bhd.com.do/homepage-personal/otros-servicios/digital-key-card/1 | 2026-09-27 |
| 4 Other factors | No page mentions security questions or an anti-phishing image. | Unknown | https://bhd.com.do/homepage-personal/products-detail/109 | 2026-09-27 |
| 5 Accounts | The contract offers personal savings and checking in RD$, US$ or EUR, and physical or digital term deposits. | Verified through documentation | https://static.bhd.com.do/Hoja_Resumen_Manu_Contrato_Manual_Operativo_Persona_Fisica_b56b68e42f.pdf | 2026-09-27 |
| 5 Products | Euro savings use a passbook with a EUR 300 minimum, and US dollar savings use a passbook or a debit card. Cards bill in RD$ and US$, and the menu lists personal, mortgage and vehicle loans, Cuenta Móvil and Billet e-money. | Observed on public pages | https://bhd.com.do/homepage-personal/cuentas-e-inversion-personal/cuentas-de-ahorro-personal | 2026-09-27 |
| 6 Credentials | Contract clause 105, on debit card use, commits the client not to share digital-channel credentials in a way that gives third parties access to the virtual card. Clause 73 makes authentication mechanisms personal and requires keeping them from third persons. | Verified through documentation | https://static.bhd.com.do/Hoja_Resumen_Manu_Contrato_Manual_Operativo_Persona_Fisica_b56b68e42f.pdf | 2026-09-27 |
| 6 Liability | Clause 73 makes the client responsible for any operation made with their access code, key card or other mechanism, even by an unauthorized third person, unless they notified the bank first. | Verified through documentation | https://static.bhd.com.do/Hoja_Resumen_Manu_Contrato_Manual_Operativo_Persona_Fisica_b56b68e42f.pdf | 2026-09-27 |
| 6 Site terms | The terms of use say "No compartir sus credenciales con terceros" and presume all account activity is the user's. No clause names bots, scraping or automated access. | Verified through documentation | https://bhd.com.do/homepage-personal/otros-servicios/calificaciones-de-riesgo/34 | 2026-09-27 |
| 6 Security page | The security page tells clients never to share their PIN or access data, family included, and to reach Internet Banking only through bhd.com.do. | Verified through documentation | https://bhd.com.do/homepage-personal/products-detail/109 | 2026-09-27 |
| 6 Legal notice | The legal notice forbids using the services in ways that damage, disable or overload the bank's systems. | Verified through documentation | https://bhd.com.do/homepage-personal/avisos-legales | 2026-09-27 |
| 6 robots.txt | bhd.com.do/robots.txt disallows nothing. The personal online-banking host ibp.bhd.com.do disallows every path except the root login page. | Observed on public pages | https://ibp.bhd.com.do/robots.txt | 2026-09-27 |
| 7 Bank on sharing | Under bank secrecy, the bank gives deposit information only to the holder "o a la persona que éste autorice expresamente" by legally valid means. | Verified through documentation | https://bhd.com.do/homepage-personal/proteccion-al-usuario/preguntas-y-respuestas | 2026-09-27 |
| 7 Portability | The privacy policy lists a data-portability right under Ley 172-13, exercised through Internet Banking, a branch or email. It never mentions aggregators or fintechs. | Verified through documentation | https://bhd.com.do/homepage-personal/politica-de-privacidad | 2026-09-27 |
| 7 Third-party apps | The legal notice says the bank's confidentiality commitment does not cover data captured by third-party devices or applications. | Verified through documentation | https://bhd.com.do/homepage-personal/avisos-legales | 2026-09-27 |
| 7 Bridge | Bridge names no bank on any public page, so its coverage of BHD is unknown. | Unknown | https://bridge.com.do/ | 2026-09-27 |
| 7 Other aggregators | Belvo, Salt Edge and Plaid publish coverage lists without the Dominican Republic. Prometeo and Envestnet Yodlee publish no list that could be checked. | Observed on public pages | https://www.saltedge.com/products/account_information/coverage | 2026-09-27 |

### Notes on BHD

- BHD publishes the most readable contract of the three. The June 2026 contract names digital download as a statement channel, bans credential sharing, and puts losses from shared credentials on the client.
- The online-banking robots file disallows everything but the login page, and the terms bar credential sharing, so a user-downloaded file is the clean path.
- BHD already sells machine-readable movement files to business clients by SFTP and MT940. That is a concrete precedent for a partnership conversation.
- The privacy policy's portability right is an untested, bank-sanctioned way for a user to request their own data. Its scope and file format are unknown.
- The 2021 screenshots show a three-month default range on the movements screen. The real history window needs a test.

## Aggregators and regulation for all three banks

| Topic | Finding | Evidence label | Source URL | Date seen |
|---|---|---|---|---|
| Bridge coverage | Bridge (Bridge Labs, S.R.L.) says it connects apps and AI agents to accounts, balances and transactions at "todas las instituciones financieras soportadas en República Dominicana". Its examples use made-up banks and name no real one. | Vendor claim only | https://bridge.com.do/ | 2026-09-27 |
| Bridge method | The Bridge Connect terms, updated 10 Oct 2025, have users enter their bank credentials and appoint Bridge as a limited agent to "iniciar sesión en su nombre cuando aplique". Bridge stores encrypted session tokens, makes no payments, and says no bank sponsors or partners with it. | Vendor claim only | https://bridge.com.do/terminos-uso-bridge-connect | 2026-09-27 |
| Bridge API | Bridge's OpenAPI spec is read-only, covering connections, accounts, balances, transactions and categorization, and it lists no institutions. | Vendor claim only | https://docs.bridge.com.do/api-reference/openapi.json | 2026-09-27 |
| Prometeo | Prometeo's public pages mention no Dominican bank, and its docs are password protected. | Unknown | https://prometeoapi.com/bancos | 2026-09-27 |
| Belvo | Belvo's developer docs cover Brazil and Mexico only. | Observed on public pages | https://developers.belvo.com/ | 2026-09-27 |
| Salt Edge | Salt Edge lists 46 countries, and its coverage in the Americas is Argentina, Brazil, Canada, Mexico and the United States. | Observed on public pages | https://www.saltedge.com/products/account_information/coverage | 2026-09-27 |
| Plaid | Plaid's docs cover the United States and Canada, and its European explorer lists only the United Kingdom. | Observed on public pages | https://plaid.com/docs/institutions/ | 2026-09-27 |
| Yodlee | Envestnet Yodlee claims more than 19,000 data sources and publishes no country breakdown. | Unknown | https://www.yodlee.com/ | 2026-09-27 |
| Local fintechs | The ADOFINTECH personal-finance directory lists no member that aggregates accounts at these banks. | Observed on public pages | https://www.adofintech.org/directorio-categoria/gestion-de-finanzas-personales-y-asesoria-fianciera/ | 2026-09-27 |
| Regulation | The SB innovation page lists "Open Banking (Banca abierta)" as its one project in progress, marked S2 2026, with the goal of writing regulation. No rule text or bank API mandate is published. | Observed on public pages | https://www.sb.gob.do/innovacion/innovacion-financiera/ | 2026-09-27 |
| Regulation | The first page of the SB regulation index, through a circular dated 17 Sep 2026, has nothing on open banking, APIs or third-party data access. | Observed on public pages | https://sb.gob.do/regulacion/normativas-sb/ | 2026-09-27 |
| Regulation | A November 2025 Acento column says the country still lacks a specific open-banking framework. | Vendor claim only | https://acento.com.do/economia/open-banking-nueva-frontera-de-competencia-financiera-en-republica-dominicana-9573531.html | 2026-09-27 |

## What requires an authorized account test

Each test uses a consenting holder's own account, run by that holder. No test shares credentials with Argus or any third party.

### Popular

1. Generate statements in App Popular for each product. This establishes the file type, whether the PDF has a text layer or a password, which products and currencies get statements, and whether four years are really available.
2. Open the movements screens in the app and in Internet Banking. This establishes whether a CSV, Excel, TXT or OFX export exists, the longest date range, and the columns.
3. Enroll in automatic statement delivery by email, and check whether SFTP is offered to a personal client. This establishes attachment or link, password, format, and whether a user can point SFTP at a server of their choice.
4. Make a card purchase and read the notice from notificaciones@popularenlinea.com, plus any SMS or push. This establishes the fields (amount, currency, merchant, card digits, date, time, balance), latency, and whether debit and credit cards both trigger it.
5. Log in from a new device. This establishes whether the token is required at login, what a new device triggers, the idle timeout, and whether security questions appear.
6. Check each savings product for monthly statements. This establishes which accounts produce a statement file and which show movements only on screen.
7. Download a credit card statement. This establishes where the cut date appears and how RD$ and US$ balances appear.

Two non-customer accounts would settle further items. An API Portal developer account would show the full catalog and the license agreement's redistribution terms. A business account would show the Extracto Bancario file format.

### Banreservas

1. Look for statement downloads per account and card in TuBanco and the app. This establishes whether a statement file exists, its format, password and months of history.
2. Use the Exportar option on the movements screen. This establishes today's formats against the third-party CSV (2022) and PDF (2021) claims, the columns, and the date-range and history limits.
3. Receive an emailed monthly statement. This establishes attachment or link, password, and which products can opt in.
4. Turn on real-time notifications in the app. This establishes the channels, enrollment steps and fields.
5. Log in from a new device. This establishes whether login alone asks for the code card or Token Digital, device binding, and the session timeout.
6. Read the click-through terms shown during TuBanco enrollment. This establishes the credential-sharing, third-party and automated-access clauses that the scanned contracts hide. A human read or OCR of the scans would also settle this without an account.
7. Download statements for USD, EUR and doble-saldo card products. This establishes whether each currency comes as a separate file and the gap between cut date and due date.

### BHD

1. Download a statement for each account type in Internet Banking Personal and the app. This establishes whether the contract's digital-download option produces a PDF, how many months are available, and whether the file has a text layer or a password.
2. Use Descargar movimientos. This establishes the file format, the longest date range beyond the three-month default, and the columns.
3. Receive an emailed checking statement. This establishes sender, attachment or link, password, and layout stability month to month.
4. Trigger a card purchase and a transfer. This establishes the notice channel, fields and latency.
5. Log in and move funds. This establishes the login factors, what the changing validation code is, when the key card, OTP or Soft Token is required, and device-binding limits.
6. Download a credit card statement. This establishes that the PESOS and DÓLARES layout in the 2024 guide matches real files.
7. File a data-portability request under the privacy policy. This establishes whether a Ley 172-13 request returns transaction data, in what format, and how fast.

### Aggregators

1. Open the Bridge Connect bank picker in a developer account. This establishes which of the three banks Bridge lists.
2. Link a real account through Bridge. This would establish multi-factor handling, account types, history depth and reconnect frequency. It would also share credentials with a third party, which Popular's Convenio and BHD's contract forbid, so it needs legal review before anyone runs it.

## Method and limits

- Four research agents read the three banks and the cross-bank questions in parallel. The coordinator then re-read the decision-relevant sources directly: the SB asset figures, BHD's contract clauses 71, 73 and 105, BHD's terms of use, privacy policy, card statement guide and September 2026 fee schedule, Popular's September 2026 fee schedule, Convenio Único, API catalog and terms, and notice sender, Banreservas' legal notice, FAQ, fee schedule, checking page and card summary, the Bridge Connect terms, the SB innovation page, and every robots file cited above.
- PDFs were read into memory without saving a file, through curl piped to pdftotext or a same-origin fetch in a browser tab.
- Popular's sites refuse plain HTTP clients through Imperva Incapsula, and www.popularenlinea.com showed a human-verification check. Popular evidence came from a normal browser session on the apex host. No check was solved.
- Banreservas' key contracts are image-only scans, and no OCR engine was available.
- The session's web-search budget ran out partway through. Later discovery used site navigation, sitemaps and linked documents, so the API and aggregator dimensions for Banreservas and BHD rest on a few searches plus navigation.
- Search-result snippets were not used as evidence in any table row.
