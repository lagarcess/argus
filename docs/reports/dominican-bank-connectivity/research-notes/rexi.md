# Rexi as a source of Dominican product facts

The research date is 2026-09-27. The scope is public pages of rexi.do, plus official pages of the institutions and regulators named below. No form was submitted, no "solicitar" link was followed, no account was created, and no personal data was entered. All rexi.do reads used WebFetch, one request at a time. The built-in browser never opened rexi.do. It was used only on official sites whose pages need JavaScript.

Rexi values below are recorded only as a comparison sample for this internal assessment. They are paraphrased, limited to the fields the task names, and are not a data source for Argus (see section 1).

## 1. Robots and terms summary

### robots.txt allows every path

- The file has one group, `User-agent: *`, with no `Disallow` or `Allow` lines. Every path is open to crawlers.
- It sets no `Crawl-delay`.
- It declares one sitemap, `https://www.rexi.do/sitemap.xml`. Per extraction, the sitemap lists 1,151 URLs with `lastmod` values. The newest is 2026-09-16T11:17:47+00:00. Category result pages carry a `lastmod` of 2021-09-07. The card detail pages sampled carry 2026-08-18 or 2026-09-16. The sitemap also lists application pages of the form `/solicitud/<product id>/0`. None of those was opened.

### The terms reserve every reuse of the site's information

The legal notices page (`/avisos-legales`) holds the terms of use and the privacy policy in one document. Its last update is dated 2018-10-05.

- The operator is Fintech Dominicana, S.R.L. The page gives no RNC, address, or governing law. There is no cookie policy.
- Reproduction, copying, use, distribution, or any communication of the portal's information needs Fintech's written authorization. The clause ends "deberá ser autorizada por escrito por Fintech".
- The Rexi name, marks, logos, and domain are registered property. Users may not use them without prior written consent.
- No clause mentions scraping, crawling, bots, data mining, framing, or automated collection. No attribution or licence path exists other than written authorization.
- Information is supplied without any warranty, and the user bears the risk of using it. The page makes no promise about data sources or update frequency.
- The privacy text covers collection, confidentiality, and security. The page has no sentence about sharing personal data with institutions or other third parties. The FAQ, however, says an application's data goes to the institution, which then contacts the applicant.

### Rexi earns from institutions, not users

The about page (`/nosotros`), the partners page (`/socios-financieros`), the FAQ (`/preguntas-frecuentes`), and the quality policy (`/politica-de-calidad`) describe the business model the same way.

- Authorized institutions list products free of charge. Users pay nothing.
- Institutions may pay advertising fees for services of higher added value. The pages name receiving applications (lead generation) and showing complementary product information.
- Institutions may also buy spaces that highlight products or promotional offers. The about page says these spaces will be "clara y explícitamente identificados".
- Rexi states that buying or not buying services does not change a product's position under its proprietary evaluation and weighting logic.
- No prices are published. No affiliate commission is mentioned. The partners page sections for partner lists were empty, next to a note saying the partners could not be retrieved.
- Rexi serves entities authorized by the Superintendencia de Bancos, the Superintendencia del Mercado de Valores, and the Banco Central. It states no registration or supervision of its own. The footer suggests operation since 2016.

### How rankings and sponsored placements appear in practice

- Every listing sorts by the "Reximetro" by default, from highest to lowest. The Reximetro is Rexi's own 1 to 5 star score. A tooltip says it weighs the main product features for the chosen category. No method is published.
- The personal-loan listing also offers sorting by interest rate.
- On the four listing pages read, no product carried a "Destacado", "Patrocinado", "Publicidad", or similar label, and no banner ads appeared.

### Data sourcing and freshness, as Rexi describes them

- Institutions supply data, or Rexi staff collect it. Rexi says it watches institutions' tariff sheets and websites, reviews data against public sources from time to time, and takes user reports of inconsistencies. No interval is given.
- Rates in the investment and loan comparators are called reference rates, open to revision and to negotiation between client and institution.
- Each detail page ends with a provenance line. It reads either "Información pública ingresada por la entidad" (entered by the institution) or "recopilada por Rexi" (collected by Rexi). Detail pages also show a rate update date and a general update date.

### Gate decision for step 2

robots.txt allows all paths. The terms do not forbid viewing public pages and say nothing about automated access. They do forbid reuse of the information without written authorization. Inspection therefore went ahead at a low volume, and only the fields the task lists were recorded. Using Rexi data in Argus, in any form, needs a written licence from Fintech Dominicana, S.R.L.

## 2. Request log

Times are UTC on 2026-09-27, stamped with `date -u` immediately before each call. WebFetch does not expose the HTTP status of a successful fetch. "OK" means content came back with no block page, CAPTCHA, 403, 429, or rate-limit message. WebFetch caches each URL for 15 minutes. Rows marked "re-read" repeated an already fetched URL inside that window, so no new page was inspected. The tool output does not say whether the cache actually answered.

The log shows 9 distinct product pages (P1 to P9), within the cap of ten.

| # | Time (UTC) | URL | Kind | Product page | Outcome |
|---|---|---|---|---|---|
| 1 | 21:51:50 | https://www.rexi.do/robots.txt | robots | no | OK |
| 2 | 21:52:16 | https://www.rexi.do/sitemap.xml | sitemap | no | OK |
| 3 | 21:52:41 | https://www.rexi.do/avisos-legales | legal | no | OK |
| 4 | 21:53:03 | https://www.rexi.do/avisos-legales | legal, re-read | no | OK |
| 5 | 21:53:26 | https://www.rexi.do/nosotros | about | no | OK |
| 6 | 21:53:37 | https://www.rexi.do/socios-financieros | about | no | OK, partner lists empty |
| 7 | 21:53:53 | https://www.rexi.do/preguntas-frecuentes | about | no | OK |
| 8 | 21:54:03 | https://www.rexi.do/politica-de-calidad | about | no | OK |
| 9 | 21:54:21 | https://www.rexi.do/sitemap.xml | sitemap, re-read | no | OK |
| 10 | 21:55:33 | https://www.rexi.do/cuentas-de-ahorros/resultados?p=1&ido=true&o=0&iw=false&pq=1&a=25000&t=0&at=1&rgch=1&c=0&ab=25000 | savings listing | P1 | OK |
| 11 | 21:56:11 | same URL as row 10 | re-read | P1 again | OK |
| 12 | 21:56:36 | https://www.rexi.do/certificados-de-deposito/resultados?p=1&ido=true&o=0&iw=false&pq=1&a=50000&t=360&aec=1&pfec=1&capI=true&c=0 | certificate listing | P2 | OK |
| 13 | 21:57:06 | https://www.rexi.do/tarjetas-de-credito/resultados?p=1&ido=true&o=0&iw=false&pq=1&a=50000&t=360&dc=1&c=3 | card listing | P3 | OK |
| 14 | 21:57:36 | https://www.rexi.do/prestamos-personales/resultados?p=1&ido=true&o=0&iw=false&pq=1&a=100000&t=36&fr=1&pfcs=1&pfeb=1&rw=1&c=0 | personal loan listing | P4 | OK |
| 15 | 22:00:59 | https://www.rexi.do/cuentas-de-ahorros/resultados/25101?p=1&ido=true&o=0&iw=false&pq=1&a=25000&t=0&at=1&rgch=1&c=0&ab=25000 | savings detail | P5 | OK |
| 16 | 22:01:16 | https://www.rexi.do/tarjetas-de-credito/resultados/1689?p=1&ido=true&o=0&iw=false&pq=1&a=50000&t=360&dc=1&c=3 | card detail | P6 | OK |
| 17 | between 22:01:16 and 22:02:26 | same URL as row 16 | re-read | P6 again | OK |
| 18 | 22:02:26 | https://www.rexi.do/certificados-de-deposito/resultados/11802?p=1&ido=true&o=0&iw=false&pq=1&a=50000&t=360&aec=1&pfec=1&capI=true&c=0 | certificate detail | P7 | OK |
| 19 | 22:06:30 | https://www.rexi.do/prestamos-personales/resultados/22745?p=1&ido=true&o=0&iw=false&pq=1&a=100000&t=36&fr=1&pfcs=1&pfeb=1&rw=1&c=0 | loan detail | P8 | OK |
| 20 | 22:09:12 | https://www.rexi.do/certificados-de-deposito/resultados/11801?p=1&ido=true&o=0&iw=false&pq=1&a=50000&t=360&aec=1&pfec=1&capI=true&c=0 | certificate detail | P9 | OK |
| 21 | between 22:10:14 and 22:12:11 | same URL as row 14 | re-read | P4 again | OK |
| 22 | 22:12:11 | https://www.rexi.do/nosotros | about, fetched again after the cache expired | no | OK |
| 23 | 22:14:04 | same URL as row 15 | re-read | P5 again | OK |

The shortest gap between two stamped rexi.do calls was 10 seconds (rows 7 and 8). Gaps between stamped product-page calls were 17 seconds or more. Rows 17 and 21 carry no stamp. Each one started only after the previous call had returned.

## 3. Product facts

### What each product page shows

Values come from WebFetch extraction. For P5 to P9, the fields were requested as verbatim lines. Listing rows below are limited to the products compared later. Rexi prints dates as day/month/year, and they are converted to ISO dates here.

| Page | Identity | Rate | Fees | Eligibility | Minimums | Dates on page | Promotions | Official link |
|---|---|---|---|---|---|---|---|---|
| P1 savings listing | 52 DOP savings accounts for an RD$25,000 average balance, 20 per page | Annual rate per row, for example BDI Cuenta Digital 7.00% | Monthly fees per row, RD$0 in the rows read | Not shown | Opening amount and minimum balance per row | None per product. A page note says values are a reference and may change without notice | None seen | A few rows link to institution sites or files (Banco Ademi file, Adopem and Abonap pages). Others show only a logo |
| P2 certificate listing | 45 DOP certificates, RD$50,000 for 360 days | Annual rate per row, for example Banco Popular 8.35%, Banreservas 2.32% | Not shown | Not shown | Popular RD$5,000, Banreservas RD$10,000 | None per product. Page note says the rate may change without notice | None seen | None recorded |
| P3 card listing | 99 cards, query category "viajes" | RD$ and US$ annual rates, for example Popular Visa Infinite Prestige 60% and 60% | Annual fixed charges, for example RD$11,000 | Minimum income, for example RD$500,000 | Not applicable | None per product | Rewards per row. No promotional conditions noted | None |
| P4 personal loan listing | 54 personal loans, RD$100,000 over 36 months | Annual reference rate, for example BHD 15.27%, Banreservas Préstamo de Consumo 19.56% | Types of insurance and commissions per row | Not shown | Not shown | None per product | None seen | None |
| P5 detail | Banco BDI, Cuenta Digital BDI, DOP | 7.00% annual, paid monthly, on the average balance | Fixed charges, below-minimum charge, and inactivity charge all RD$0. No debit card | Says a good credit history is not required | Opening RD$0, minimum balance RD$0 | Rate updated 2023-09-01. General update 2026-07-27 | None | None. Has an apply button (not followed) |
| P6 detail | Banco Popular, Visa Infinite Prestige | 60% RD$, 60% US$, annual | Fixed charges RD$11,000: issuance RD$10,000, annual renewal RD$10,000, theft or loss insurance RD$1,000. Overdraft RD$800 or US$25. Cash advance 6.25%. 22 days to pay after the statement | Minimum monthly income RD$500,000 | Not applicable | General update 2026-07-27. No rate date | Rewards and travel benefits listed | None |
| P7 detail | Banco Popular, Certificado Financiero en Pesos | 8.35%, marked as a reference that varies with term and amount | Early cancellation allowed with a penalty, amount not given | Not shown | Minimum RD$5,000. Term 1 to 2 years | Rate updated 2024-05-01. General update 2026-07-27 | None | None |
| P8 detail | Banco BHD, Préstamo Personal | 15.27% reference, revised quarterly | Prepayment and early payoff penalty 2.5% in months 0 to 12 and 1.5% in months 13 to 24. No closing or legal costs. Life insurance optional | Minimum income RD$20,000. No collateral required, guarantor or vehicle accepted | Minimum RD$20,000, no maximum. Term 6 to 60 months | Rate updated 2022-05-17. General update 2026-06-25 | None | None |
| P9 detail | Banreservas, Certificado de Depósito en Pesos | 2.32% for RD$50,000 at 360 days | Early cancellation allowed with a penalty, amount not given | Not shown | Minimum RD$10,000. Term 30 days to 1 year | Rate updated 2026-07-10. General update 2026-08-18 | None | Links to banreservas.com/products/certificados-financieros-en-pesos-0, which returned HTTP 404 on 2026-09-27 |

On P5, P8, and P9, the provenance line says the institution entered the information. On P6 and P7, it says Rexi collected it.

### Elements that belong to Rexi and are not reusable product facts

- The Reximetro stars on every listing, and the default order they produce.
- The category filters and tooltips that shape the order, for example the "viajes" card category.
- Rexi's own calculations, such as the annual return (RD$1,750 on P5), the gain at maturity (RD$4,339 on P7, RD$1,172 on P9), and the monthly payment (RD$3,480 on P8). These depend on Rexi's assumptions, such as monthly compounding.
- The risk grades shown on certificate pages (AA+ by Feller Rate on P7, AA+ by Fitch on P9) are third-party ratings of the institution. They are not Rexi's, but they are also not product facts. Argus would need them from the rating agency with a date.

### Rexi compared with official sources

| Product | Field | Rexi value and date | Official value, source, and date | Result |
|---|---|---|---|---|
| BDI Cuenta Digital BDI | Rate at an RD$25,000 balance | 7.00%, rate dated 2023-09-01 | 7.00% from RD$0 to RD$5,000,000, 7.50% above. [BDI tarifario](https://www.bdi.com.do/media/lddlvfmn/tarifario-cuentas-digitales-bdi.pdf), no date printed | Match |
| BDI Cuenta Digital BDI | Balance the rate applies to | Average balance | The tarifario labels the rate by minimum balance | Mismatch in basis. Needs confirmation from BDI |
| BDI Cuenta Digital BDI | Opening amount, minimum balance, fees | RD$0 | RD$0.00, and digital transfers free | Match |
| BDI Cuenta Digital BDI | Maximum balance | Not shown | RD$10,000,000, per the tarifario and the [product page](https://www.bdi.com.do/cuentas/cuenta-digital-bdi/) | Rexi omits |
| BDI Cuenta Digital BDI | Eligibility | Good credit history not required | Age 18 or older, Dominican nationality or permanent residence, one account per currency (product page) | Rexi incomplete |
| Popular Visa Infinite Prestige | Interest rate | 60% RD$, 60% US$ | 60% and 60%. [Popular tariff](https://popularenlinea.com/Personas/Documents/Tarifas/Tarifas-de-productos-y-servicios.pdf) effective 2026-09-27, and the same in the [2026-04-13 tariff](https://popularenlinea.com/Personas/Documents/Tarifas/tarifario-productos-y-servicios-vigentes-al-13-04-2026.pdf) | Match |
| Popular Visa Infinite Prestige | Issuance charge | RD$10,000 | RD$10,000 per year over the card's 5-year life, RD$50,000 in total (both versions) | Annual amount matches. Rexi omits the 5-year total |
| Popular Visa Infinite Prestige | Renewal charge | RD$10,000 per year | RD$10,000 per year from card expiry, RD$50,000 in total (both versions) | Match |
| Popular Visa Infinite Prestige | Theft or loss insurance | RD$1,000 | RD$1,200 effective 2026-09-27. RD$1,000 effective 2026-04-13 | Mismatch with the current tariff. Rexi matches the older one |
| Popular Visa Infinite Prestige | Overdraft fee | RD$800 or US$25 | RD$1,500 or US$50 effective 2026-09-27. RD$1,000 or US$35 effective 2026-04-13. RD$800 or US$25 is the Titanium Doble Saldo column in both versions | Mismatch |
| Popular Visa Infinite Prestige | Late fee | Not shown | RD$1,200 or US$35 (both versions) | Rexi omits |
| Popular Visa Infinite Prestige | Cash advance fee | 6.25% | 6.25% | Match |
| Popular Visa Infinite Prestige | Minimum income | RD$500,000 per month | Not in the tariff | Not verifiable |
| Popular Certificado Financiero en Pesos | Rate | 8.35% reference, rate dated 2024-05-01 | Not published. The [product page](https://popularenlinea.com/Personas/Paginas/inversiones/deposito-a-plazo.aspx) and the 2026-09-27 tariff say branch rates are negotiated and digital rates depend on the chosen term | Not verifiable. For context, the Banco Central weighted average for bancos múltiples certificates of 181 to 360 days was 6.32% on 2026-09-23 (preliminary) |
| Popular Certificado Financiero en Pesos | Minimum amount | RD$5,000 | RD$5,000 (tariff 2026-09-27 and product page) | Match |
| Popular Certificado Financiero en Pesos | Terms | 1 to 2 years | Terms up to 6 years (product page) | Mismatch |
| Popular Certificado Financiero en Pesos | Early cancellation penalty | Yes, no amount | 3.00% of the certificate's interest for the days left to maturity | Rexi incomplete |
| BHD Préstamo Personal | Rate | 15.27% reference, rate dated 2022-05-17 | No personal loan rate in the [BHD tariff](https://static.bhd.com.do/B_Tarifario_Banco_BHD_Septiembre_2026_ae2ead8a2e.pdf), a file named September 2026 whose first page prints modification and effective dates of 2026-04-01 | Not verifiable. For context, the Banco Central weighted average for bancos múltiples consumer and personal loans was 18.81% on 2026-09-23 (preliminary) |
| BHD Préstamo Personal | Prepayment and early payoff penalty | 2.5% in months 0 to 12, 1.5% in months 13 to 24 | 3% of the prepaid capital in months 0 to 24 for consumer loans. A later section lists 3% for both prepayment and early cancellation of personal loans in months 0 to 24 | Mismatch |
| BHD Préstamo Personal | Fee per overdue installment | Not shown | RD$100 per month | Rexi omits |
| BHD Préstamo Personal | Minimum amount, term, minimum income | RD$20,000. 6 to 60 months. RD$20,000 | Not in the tariff | Not verifiable |
| Banreservas Certificado de Depósito en Pesos | Rate, RD$50,000 for 360 days | 2.32%, rate dated 2026-07-10 | 12 months at a floor ("desde") of 2.07% for amounts from RD$10,000 (6 months 2.05%, 1 month 1.90%). [Banreservas reference rates](https://cdnebrpeastus.azureedge.net/banreservas/media/tfmdazag/tasas-de-referencia_2026.pdf), last modified 2026-06-29 | Differs. The official figure is a floor, so a higher tier is possible. Not resolvable from public data |
| Banreservas Certificado de Depósito en Pesos | Minimum amount | RD$10,000 | From RD$10,000 | Match |
| Banreservas Certificado de Depósito en Pesos | Term range | 30 days to 1 year | 1 to 12 months | Match |
| Banreservas Certificado de Depósito en Pesos | Link to the official page | banreservas.com/products/certificados-financieros-en-pesos-0 | HTTP 404 | Broken link |
| Banreservas Préstamo de Consumo (P4 listing only) | Rate | 19.56%, no rate date on listings | Personal loans at a floor of 19.27%, TAE 21.37% (reference rates, 2026-06-29) | Differs. The official figure is a floor. Inconclusive |

Fields with a firm official value give 9 matches, one of them partial, and 5 mismatches. The mismatches are the BDI interest basis, the Popular card insurance and overdraft fees, the Popular certificate term, and the BHD prepayment penalty. Rexi also omits, or only partly states, 5 fields that the official source states. Of the six headline rates compared, two match. The other four have no official point value to check against. Popular and BHD publish none, and Banreservas publishes only floors.

### Official aggregated sources

| Source | What it gives | Granularity | Latest period seen | Access | Limits |
|---|---|---|---|---|---|
| Superintendencia de Bancos, SIMBAD dashboard "Tasas y Comisiones", linked from [ProUsuario](https://prousuario.gob.do/) as its rates and fees tool ([dashboard 78](https://simbad.sb.gob.do/superset/dashboard/78/)) | Card interest rate, cash advance, late, overdraft, renewal, issuance, and insurance charges | Entity type, entity, currency, card type, plastic type, and brand. Weighted by approved amount across normal and preferential clients. Built from regulatory reports TC01 and TC02 | May 2026 | Public dashboard with a "Datos para descarga" tab (not opened) | Cards only. Averages of what is charged, not offers. About four months behind |
| SB API, "Estadísticas del Sistema Financiero v2" ([list](https://desarrollador.sb.gob.do/apis)) | REST and JSON. Groups include TasasComisiones and Captaciones. The Captaciones endpoint returns weighted average deposit rates by entity and month | Entity, month | Not tested | Registration, a plan, and an API key are required | Not tried, since that needs an account. No licence text found |
| SIMBAD, update practice ([about](https://simbad.sb.gob.do/superset/dashboard/acerca_de)) | Statistics refresh weekly through an automated process as regulatory reports arrive | Not applicable | Not applicable | Public | A press report of August 2026 also describes a new dashboard of rates on newly disbursed loans, filterable by entity, term, amount, and currency. It was not opened |
| SB [terms of use](https://sb.gob.do/terminos-de-uso/) | Information is for reference only, with no guarantee of accuracy, timeliness, or completeness | Not applicable | No date | Public | No open-data or reuse licence found |
| Banco Central, daily rates "por entidad" ([bank file](https://cdn.bancentral.gov.do/documents/estadisticas/sector-monetario-y-financiero/documents/tasas_diariasBM-2026.xlsx)), with sister files for savings and loan associations and savings and credit banks | Weighted average active and passive rates by term and sector, savings deposits, and general versus preferential clients | Entity type, not institution | 2026-09-23, marked preliminary | Public XLSX, also weekly and monthly series | Benchmarks only. No per-institution values |
| Institution tariffs and rate sheets | Fees, and some rates | Product | Popular 2026-09-27, BHD file of September 2026, Banreservas 2026-06-29, BDI undated | Public PDFs | Formats vary. Many deposit and loan rates are missing, negotiated, or floors |

## 4. Assessment and open questions

### Rexi data can be read easily but cannot be used

Technically, extraction is easy. Product data arrives in the server HTML without JavaScript, product IDs are stable integers, the sitemap enumerates detail pages with `lastmod` dates, robots.txt allows everything, and nine product pages returned with no block, CAPTCHA, 403, or 429. Contractually, extraction is closed. Every reproduction, copy, use, distribution, or communication of the site's information needs Fintech Dominicana's written authorization. Reading pages to track them does not grant that authorization. It also does not authorize advertising use, lead sharing, or disclosure of anyone's financial records.

Keeping Rexi facts current would also inherit Rexi's lag. Four of the five detail pages show a rate update date, and those dates range from 2022-05-17 to 2026-07-10. Every general update date on the same pages falls in June to August 2026. A recent general update date does not mean the rate was re-checked. Fees drift after tariff revisions. The Popular card page matches the April 2026 insurance charge, not the one effective today, and its overdraft fee does not match the Prestige column in either tariff.

In my view, Rexi is not a viable source for Argus. At most, a person can browse it to spot institutions and products, then read the facts at the official source.

### Official sources give provenance, with gaps

The official route supports provenance better than Rexi does, but it needs a document pipeline.

- Printed effective dates exist but are inconsistent. Popular prints "vigentes a partir del 27 de septiembre de 2026". Banreservas prints a last modification date of 2026-06-29. BHD prints 2026-04-01 on page 1 of a file named September 2026 and last modified on 2026-09-17. BDI prints no date.
- Stable URLs get overwritten. Popular's current tariff URL showed a 2026-06-13 title in a search index and a 2026-09-27 document today. Argus must snapshot each document when fetched and store its hash, the printed effective date, the HTTP `Last-Modified` header, and the retrieval time. BHD and Banreservas keep archives (BHD monthly back to September 2024, Banreservas yearly 2023 to 2025). Popular keeps some dated copies.
- Formats vary. Popular's PDF has extractable text. Banreservas' rate sheet is drawn as vector shapes with no text layer, so it needs OCR or visual reading. BHD's tariff is 44.9 MB, over WebFetch's 10 MB limit.
- Deposit and loan rates are often absent at the product level. Popular negotiates certificate rates in branch. BHD publishes no personal loan rate. Banreservas publishes floors ("desde"). Argus should store a qualifier with each rate (point value, floor, or negotiated) and show it to the user.
- SB and Banco Central data are weighted averages of executed operations, not offers. They work as market benchmarks and sanity checks, for example flagging a stored certificate rate far from the market average for its term.

### Telling sponsored placements from independent comparisons

Rexi says featured spaces are labelled and that paid services do not move rankings. On four listing pages no label appeared. The default order, however, rests on an undisclosed score. Two paid services can still shape what users see. First, paid complementary information gives paying institutions richer product cards. Second, the application form is itself a paid service (receiving applications), so an apply button or a `/solicitud/<id>/0` URL in the sitemap likely marks a paying institution. That second point is an inference to confirm with Rexi.

Argus should never import a third party's order, scores, or badges. It should order products by a published rule computed from official facts, such as rate, then fees. It should record any commercial relationship per institution and product from signed agreements, never by inference, and label it where the product appears. The ordering must stay independent of that record.

### Coverage limits

- Rexi's default queries returned 52 savings accounts, 45 certificates, 99 cards, and 54 personal loans. It also covers vehicle and mortgage loans, investment funds, structured products, bonds, pensions, and trusts. Results depend on the amount, term, category, and income entered, so a full matrix needs many parameterized requests. The terms do not allow collecting those results anyway.
- Rexi's coverage of cooperatives and fintechs was not checked. Its partner list failed to load, so its commercial relationships are not public.
- Officially, no single catalog covers product-level offers for deposits and loans. SIMBAD's fees tool covers cards only and runs about four months behind. The SB API needs an account. Banco Central data stops at the entity type.

### Open questions

1. Would Fintech Dominicana license its data in writing, with attribution, caching, display, and commercial terms? Would a licence tie Argus to Rexi's lead business?
2. Does Rexi's "tasa actualizada" date mark the day the institution changed the rate, or the day Rexi last checked it?
3. Does an application form reliably mark a paying institution? Do the paid complementary information fields feed the Reximetro?
4. Which rule requires institutions to publish tariffs, and does it require a printed effective date and an archive? The Reglamento de Protección al Usuario was not checked in this pass.
5. What do the SB API's TasasComisiones endpoints return, at what granularity and lag, and under what licence? Answering needs a founder-approved registration.
6. What does SIMBAD's "Datos para descarga" tab provide? The new dashboard of rates on newly disbursed loans was not opened.
7. Does BDI pay interest on the average balance, as Rexi says, or on the minimum balance, as its tarifario label says?
8. Popular's site footer links an API portal, and Banco Central's footer links an API page. Does either one expose product or rate data? Neither was explored.
9. What are Banco Central's reuse terms for its statistics files? They were not read.
