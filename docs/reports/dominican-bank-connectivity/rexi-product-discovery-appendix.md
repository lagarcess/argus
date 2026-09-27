# Rexi and product-discovery appendix

This appendix is separate from private account connectivity. It asks whether Argus could keep Dominican product facts current for future discovery in Search, and whether Rexi could supply them. It does not delay or condition the connectivity recommendation.

No form was submitted, no application link was followed, no account was created, and no personal data was entered. No institution or Rexi was contacted. All sources were read on 2026-09-27.

## Rexi's terms close the door that its robots file opens

Rexi (`rexi.do`) is operated by Fintech Dominicana, S.R.L. Its `robots.txt` has one `User-agent: *` group with no `Disallow` line and no crawl delay. It declares a sitemap of 1,151 URLs.

The legal notices page, last updated 2018-10-05, requires Fintech Dominicana's written authorization for any reproduction, copy, use, distribution, or communication of the portal's information. It says nothing about crawling or bots. It offers no attribution or licence path other than written authorization.

Reading public pages to track them is therefore not permission to reuse their content. Tracking also never authorizes advertising use, lead sharing, or disclosure of anyone's financial records.

## Rexi earns from institutions

Rexi's about, partners, FAQ, and quality-policy pages describe the same model. Institutions list products for free. They may pay for applications from users, richer product information, and highlighted spaces that Rexi says it labels. Rexi says paid services do not change its ranking. It publishes no prices and no partner list. The partners page failed to load its partner sections.

Every listing sorts by default on the "Reximetro", Rexi's own 1-to-5 star score, whose method is not published. On the four listing pages read, no product carried a sponsored or featured label.

## What was inspected

The inspection stayed within the ten-page cap. It read 9 distinct product pages serially. Timestamped requests were at least 10 seconds apart, and timestamped product-page requests at least 17 seconds apart. Two repeat reads carry no timestamp, and each started only after the previous call returned. No request met a block page, a CAPTCHA, HTTP 403, HTTP 429, or a rate-limit message. The tool repeated 4 reads of already-fetched product URLs inside its 15-minute cache window. Whether its cache answered those repeats is not observable.

| Page | Product | What it showed |
| --- | --- | --- |
| P1 | Savings listing, RD$25,000 average balance | 52 DOP accounts with annual rate, monthly fees, opening amount, and minimum balance per row |
| P2 | Certificate listing, RD$50,000 for 360 days | 45 DOP certificates with rate and minimum per row |
| P3 | Card listing, "viajes" category | 99 cards with DOP and USD rates, annual charges, and minimum income |
| P4 | Personal loan listing, RD$100,000 over 36 months | 54 loans with reference rate, insurance, and commissions |
| P5 | Banco BDI, Cuenta Digital BDI | Rate, fees, eligibility, minimums, rate date 2023-09-01, general update 2026-07-27 |
| P6 | Banco Popular, Visa Infinite Prestige | Rates, charges, minimum income, general update 2026-07-27, no rate date |
| P7 | Banco Popular, Certificado Financiero en Pesos | Reference rate, minimum, terms, rate date 2024-05-01 |
| P8 | Banco BHD, Préstamo Personal | Reference rate, penalties, minimums, rate date 2022-05-17 |
| P9 | Banreservas, Certificado de Depósito en Pesos | Rate, minimum, terms, rate date 2026-07-10, and a link to the bank's page that returned HTTP 404 |

Each detail page names its provenance as either entered by the institution or collected by Rexi.

## Rexi against the institutions' own documents

The comparison used each institution's current public tariff or rate document: [BDI's digital-account tariff](https://www.bdi.com.do/media/lddlvfmn/tarifario-cuentas-digitales-bdi.pdf), [Popular's tariff effective 2026-09-27](https://popularenlinea.com/Personas/Documents/Tarifas/Tarifas-de-productos-y-servicios.pdf), [BHD's September 2026 tariff](https://static.bhd.com.do/B_Tarifario_Banco_BHD_Septiembre_2026_ae2ead8a2e.pdf), and [Banreservas' 2026 reference rates](https://cdnebrpeastus.azureedge.net/banreservas/media/tfmdazag/tasas-de-referencia_2026.pdf).

Fields with a firm official value gave 9 matches, one of them partial, and 5 mismatches. Rexi also omitted or only partly stated 5 fields the official source states.

- **Mismatches.** BDI labels its digital-account rate by minimum balance, where Rexi says average balance. Popular's current Prestige theft-or-loss insurance is RD$1,200, where Rexi shows the RD$1,000 of the 2026-04-13 tariff. Popular's current Prestige overdraft fee is RD$1,500 or US$50, and Rexi's RD$800 or US$25 matches a different card's column. Popular's certificate page allows terms up to 6 years, where Rexi says 1 to 2 years. BHD's tariff sets a 3% penalty for personal-loan prepayment in months 0 to 24, where Rexi shows 2.5% and 1.5%.
- **Headline rates.** Of six headline rates compared, two match. Popular negotiates certificate rates and publishes no point value. BHD publishes no personal-loan rate. Banreservas publishes floors ("desde"). The other four therefore have no official point value to check.

A recent "general update" date on a Rexi page does not mean its rate was re-checked. Rate dates on the same pages ran from 2022-05-17 to 2026-07-10.

## What official sources can and cannot keep current

| Source | What it gives | Limits |
| --- | --- | --- |
| Institution tariffs and rate sheets | Fees, and some rates, per product | Formats vary. Banreservas' rate sheet has no text layer. BHD's tariff is 44.9 MB. Popular reuses one URL for successive versions. Many deposit and loan rates are negotiated, floors, or absent. |
| Superintendencia de Bancos SIMBAD dashboard "Tasas y Comisiones", linked from ProUsuario | Card rates and charges by entity, currency, and card type | Cards only. Weighted averages of what was charged, not offers. About four months behind. |
| Superintendencia de Bancos API "Estadísticas del Sistema Financiero v2" | Groups include rates and commissions and deposits | Needs registration and an API key. No licence text found. Not tested. |
| Banco Central daily rates files | Weighted average rates by term and sector | By entity type, not institution. Benchmarks only. |
| Superintendencia de Bancos terms of use | Reference-only disclaimer | No open-data or reuse licence found |

These are public financial statistics. None of them is access to anyone's bank account.

## How discovery could stay honest

Four rules would let Argus compare products without importing someone else's ranking or hiding a commercial tie.

1. Store each product fact with its official source document, the document's hash, its printed effective date, the HTTP `Last-Modified` header, and the retrieval time. Snapshot every fetch, because institutions overwrite stable URLs.
2. Store a qualifier with every rate: a point value, a floor, or negotiated. Show it to the person.
3. Order products by a published rule computed from official facts, for example rate and then fees. Never import a third party's order, scores, or badges, including the Reximetro.
4. Record any commercial relationship per institution and product from a signed agreement, never by inference, and label the product wherever it appears. Keep the order independent of that record. MVEE section 3 already forbids fictional offers and implied shopping capabilities.

Coverage stays partial. No official catalog covers product-level offers for deposits and loans. Discovery should say which institutions and product types it covers and when each fact was last checked.

## Open questions

1. Would Fintech Dominicana license its data in writing, and would a licence tie Argus to Rexi's lead business?
2. Does a Rexi rate date mark the institution's change or Rexi's last check?
3. Which rule requires institutions to publish tariffs, and does it require a printed effective date and an archive?
4. What do the Superintendencia de Bancos API's rate and commission endpoints return, with what lag, and under what licence? Registration needs founder approval.
5. What are Banco Central's reuse terms for its statistics files?
