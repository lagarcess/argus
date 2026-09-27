# Web research for the SuperCarros and SuperCasas feasibility audit

Researched 2026-09-27. Labels:

- [VERIFIED] means I read the cited URL (or the GitHub/PyPI/registry API record) this session.
- [SNIPPET] means the claim comes only from search-engine result text. The search tool returns titles, URLs and a generated summary, so wording is paraphrased, not verbatim.
- [INFERRED] means my reasoning from the evidence. Treat it as a hypothesis.

No request went to any host under supercarros.com or supercasas.com, and no archive copy was fetched. GitHub code I read contains URLs for those sites as strings. I executed none of it.

## 1. Operators, age, apps, programs, and terms

**Operator and shared ownership.**

- [SNIPPET] The SuperCarros terms page names Cibermercado S.R.L. as the site owner, with RNC 1-01-87712-1. Source: search results for https://www.supercarros.com/informacion/terminos-y-condiciones.
- [SNIPPET] The SuperCasas terms page names the same entity, the same address and the same RNC. It says the terms are registered with Pro Consumidor under number 046/2019. The live page read on 2026-09-27 shows 139/2023. Source: search results for https://www.supercasas.com/informacion/terminos-y-condiciones.
- [SNIPPET] A 2024 SuperCasas blog post reports that Cibermercado held its annual sales convention, and a SuperCasas Instagram post speaks as "CiberMercado". Sources: blog.supercasas.com/2024/04/cibermercado-celebro-su-convencion-anual-de-ventas-del-2024/ and instagram.com/supercasas.comrd/p/CyE986Dtk2j/ (neither fetched).
- [VERIFIED] Both .com domains use registrar GoDaddy and the same Cloudflare nameserver pair (EVELYN.NS.CLOUDFLARE.COM, MOURA.NS.CLOUDFLARE.COM). Sources: https://rdap.verisign.com/com/v1/domain/supercarros.com and https://rdap.verisign.com/com/v1/domain/supercasas.com.
- [INFERRED] One operator runs both sites. Cloudflare assigns nameserver pairs per account, so the identical pair suggests one Cloudflare account. The nameservers alone do not prove that traffic is proxied or that bot rules are active.
- [INFERRED] Public scrapers show the two sites share one page template. Both use `#detail-ad-header`, `#detail-ad-info-specs`, `.detail-ad-info-specs-block`, `#bigsearch-results-inner-*` and the `PagingPageSkip` parameter (see section 2).

**Age.**

- [VERIFIED] supercarros.com was registered 2001-09-30 and supercasas.com 2002-09-21 (same RDAP records).
- [SNIPPET] SuperCasas pages carry copyright notices back to 2001. A cutestat.com result dates supercarros.com.do to 2014-04-02 (not fetched).

**Self-reported scale.** These are marketing numbers.

- [SNIPPET] SuperCarros claims more than 1,250,000 monthly visits and more than 15,000 listings. SuperCasas claims 65,000 to 75,000 monthly buyers and more than 10,000 listings.

**Mobile apps.**

- [SNIPPET] Searches restricted to apps.apple.com and play.google.com found no SuperCarros or SuperCasas app. Both brands run mobile web hosts, m.supercarros.com and m.supercasas.com. The "SUPERCASA" app (id1575765638, com.janeladigital.supercasamobile) belongs to Janela Digital, which is Portugal's supercasa.pt and is unrelated.
- [INFERRED] There is probably no native app. This rests on absence of evidence.

**API, feed, export, and data licensing.**

- [SNIPPET] Searches for an API, an XML feed, bulk inventory import, or data licensing turned up nothing for either brand.
- [VERIFIED] AlterEstate, a Dominican real estate CRM, lists Proppit, Mercado Libre, Corotos, Propiedades.com and Properstar as synced portals. SuperCasas is not on the list. Source: https://alterestate.com/do/productos/crm-inmobiliario/.
- [VERIFIED] Obrien CRM advertises automatic portal publication without naming portals. Source: https://www.obriencrm.com/software-crm-inmobiliario-republica-dominicana/.
- [INFERRED] No public inbound or outbound integration program is documented. Any data deal would need direct contact with Cibermercado.

**Dealer and agency programs.** All found by search only. Paths are listed so the parent can decide what to fetch.

- [SNIPPET] SuperCarros /vender/dealers-1/ and /vender/dealers-2/ describe plans for professionals and companies that manage inventory online.
- [SNIPPET] SuperCarros prices seen in results: RD$3,250 for a featured 30-day ad with 12 photos and 7 days of priority, and RD$7,000 for 7 days on the homepage as a "SuperCarro". SuperCasas prices: RD$1,600 for 30 days with 10 photos, RD$3,200 for 90 days, and RD$2,600 for a featured ad.
- [SNIPPET] Client and business logins sit on separate hosts: clientes.supercarros.com/Login, clientes.supercasas.com/Login and empresas.supercasas.com/Login.
- [SNIPPET] SuperCarros directories and programs: /directorio/dealers/, /Directorio/Financiamiento/, /financiamiento (bank payment calculator), /garantizados, and bank or association fair pages (/feria-bancosantacruz, /feria-motorcredito, /feria-asocivu).
- [SNIPPET] SuperCasas directories and programs: /Directorio/Inmobiliarias/, /oficinas/, /financiamiento, and agency storefronts under /Propiedades/{agency}/.

**Terms and policy URLs** for the parent's budgeted fetch.

- [SNIPPET] https://www.supercarros.com/informacion/terminos-y-condiciones (page title "Condiciones de Uso y Política de Privacidad"). Terms and privacy appear to share one page.
- [SNIPPET] https://www.supercasas.com/informacion/terminos-y-condiciones (same title pattern). Also /informacion/politica-devoluciones-cancelaciones and /contacto on both hosts, and /informacion/consejos-venta on SuperCarros.
- [INFERRED] The parent should also read /robots.txt on each host it samples. I have no evidence about its contents.

**What the terms say about reuse.** All paraphrased from search results. No snippet surfaced an explicit robots, scraping or automated-access clause, so the full page must be read before concluding either way.

- [SNIPPET] Section 4.1 of the SuperCarros terms has Cibermercado claim intellectual and industrial property over its pages and their elements. The elements named include images, texts, logos, structure and design, selection of materials, and computer programs.
- [SNIPPET] The same section prohibits reproduction, distribution and public communication of all or part of the contents for commercial purposes, by any means, without Cibermercado's authorization. SuperCasas results show the same clause.
- [SNIPPET] Cibermercado disclaims any guarantee against fraudulent access to data by third parties or by automated computer systems. This is a security disclaimer, not a prohibition.
- [SNIPPET] Advertisers are responsible for the accuracy of what they post. Changes to the terms require prior Pro Consumidor approval and 24 hours' notice to users. The terms also include a cookies notice.

**Look-alike domains.** I did not fetch any of these.

- [SNIPPET] supercarros1.com is an aggregator that claims 25,000 vehicles, and supercarros2.yolasite.com also exists. cibermercado.com.do shows the page title "SuperCarros.com".
- [INFERRED] cibermercado.com.do and supercarros.com.do may point at the same operator's servers. The parent should treat them as in scope for its request ledger.

## 2. Public scrapers (secondary evidence of page structure and fragility)

All repositories below were read through the GitHub API [VERIFIED]. "Pushed" is the last push date.

| Repo | Site | Pushed | Tooling | Fields | Access notes |
|---|---|---|---|---|---|
| formulard/webscraping_inmobiliario | SuperCasas | 2026-09-25, data commit | R, rvest 1.0.4, daily GitHub Actions cron | id, operation type, property type, price with currency, bedrooms, baths, parking, address, area, amenities | No custom User-Agent, no delay, no proxy, no browser. See the logs below. |
| vladimircuriel/inmo-insight | SuperCasas, Santiago rentals | 2026-01-18 | Python requests + BeautifulSoup, Airflow | rent, furnished rent, rooms, baths, parking, location, condition, construction m2, floor, land m2, elevators, year built, amenities, observations | Honest User-Agent "(compatible; InmoInsight/1.0)". Hard-coded USD to DOP rate of 64. |
| Rockman67/real-estate-crawler | SuperCasas, Corotos | 2025-04-29 | Scrapy 2.11.2 + scrapy-playwright, DOWNLOAD_DELAY 3, AutoThrottle | title, price line, location, detail fields | Its site audit marks Corotos as blocked by captcha and Cloudflare geo-blocking (needs a VPN or proxy). SuperCasas is not flagged. |
| Johan-rosa/webscraping-supercasas | SuperCasas | 2023-09-01, created 2020 | R, rvest + a patched `polite::bow` that reads robots.txt but forces a 0.01 s delay | Same selectors as formulard | Selectors match 2026 code. |
| zabdielmaestre/supercarrosrd | SuperCarros, one dealer's own inventory | 2026-06-09 | TypeScript, fetch + cheerio on Vercel, daily cron, concurrency 3 | title, year, make, model, price with RD$ or US$, photos, specs, accessories, description, dealer name, phone, WhatsApp, email, address | Self-identifying User-Agent. It also proxies images and strips the SuperCarros watermark. |
| DryFernandez/Scraper-supercarros | SuperCarros | 2026-01-14 | Python. Playwright headless Chromium with a spoofed Chrome UA for listing pages, plain requests for detail pages | specs, accessories, seller name, seller type, phones, mobile, email, city, WhatsApp, address | Commits a `supercarros.xlsx` that includes seller contact data. Delay 0.5 s. |
| Cferrer08/Automotive-Market-Price-Analysis | SuperCarros | 2025-10-02 | Selenium, Power BI | price, brand, model, odometer, fuel | Strips "US$" when cleaning prices. |
| robocot20/carprice-api | SuperCarros, CarrosRD, DGII, BCRD | 2026-04-29 | FastAPI, requests + BeautifulSoup, spoofed Chrome UA, 1.5 s delay | price assumed to be USD | Uses guessed fallback selectors, so it is weak evidence of structure. |
| formula-consulting/supercarros | SuperCarros | 2020-08-08 | R, rvest | listing links, header title and price | 2020 selectors match 2026 code. |
| RealEstateWebTools/property_web_scraper (MIT, 132 stars) | SuperCasas mapping `config/scraper_mappings/do_supercasas.json` | mapping added 2026-02-22 | Generic config | JSON-LD paths with CSS fallbacks | [INFERRED] Its CSS class names do not match the working scrapers above, so it is probably unverified (it declares an expected extraction rate of 0.55). |

**SuperCasas page structure.** All from the code above [VERIFIED].

- Search URL form: `/buscar/?do=2&ObjectType=123&PriceType=401&Locations=10095&PriceFrom=..&PriceTo=..&PagingPageSkip=N`.
- Rockman67's audit maps ObjectType 123 to apartment and PriceType 400 to US$. [INFERRED] PriceType 401 is probably RD$.
- Location codes include 10005 (Santo Domingo Centro), 10347 (Santo Domingo Este), 10375 (Santo Domingo Norte), 10385 (Santo Domingo Oeste), 10008 (Bávaro, Punta Cana and La Altagracia) and 10095 (Santiago).
- Result cards are `#bigsearch-results-inner-results li` with `.title1` (area), `.title2` (price line such as "Venta: US$ ...") and `.type`. The pager is `#bigsearch-results-inner-lowerbar-pages`.
- The detail page has `#detail-ad-header h2` (type), `#detail-ad-header h3` (price) and `.secondary-info span` (bedrooms, baths, parking).
- The specs block `#detail-ad-info-specs` carries labeled rows: Alquiler, Alquiler Amueblado, Localización, Condición, Construcción, Nivel/Piso, Edificable, Uso Actual, Terreno, Ascensores, Año Construcción, Comodidades and Observaciones.
- [SNIPPET] Listing URLs look like `/apartamentos-venta-punta-cana/<id>/`, with a seven-digit numeric ID. IDs seen in 2026 run from about 1.26M to 1.43M.

**SuperCarros page structure.** All from the code above [VERIFIED].

- Search URLs look like `/buscar/?do=1&ObjectType=1&PriceFrom=0&PriceTo=50000000&PagingPageSkip=N`. Dealer pages are `/dealers/{slug}/?PagingPageSkip=N` with cards in `.generic-results-dealer ul > li`.
- The detail page has `#detail-ad-header h1` (title), `#detail-ad-header h3` (price starting RD$ or US$) and `#detail-ad-info-photos a[data-photo]`. Specs sit in `#detail-ad-info-specs table`. Seller data sits in `#detail-right`, labeled "Tel:", "WhatsApp:" and "Email:".
- Images are served from `img.supercarros.com/AdsPhotos/{WxH}/{n}/{photoId}.jpg` and carry a watermark.
- [SNIPPET] Listing URLs look like `/honda-accord/<id>/`, with a seven-digit numeric ID. IDs above 1.6M appear in June 2026.

**Fragility and blocking signals.**

- [VERIFIED] formulard's Actions job logs, read through the GitHub API, show plain rvest requests from GitHub-hosted (Azure) runners downloading 102 new SuperCasas listings on 2026-09-24, 536 on 09-25, 10 on 09-26 and 0 on 09-27. On 09-25 the 536 detail pages took about 107 s, and the roughly 210 search pages (5 locations times 42 pages) took about 55 s.
- [VERIFIED] The failed runs in September died on a missing R package ("there is no package called 'tidyr'") after the downloads had finished. They did not fail on HTTP errors.
- [INFERRED] SuperCasas did not block unthrottled, non-browser, datacenter traffic as of 2026-09-26.
- [INFERRED] The script wraps every request in `purrr::possibly`, which swallows errors. A zero-download day therefore cannot tell "no new listings" apart from "requests failed".
- [INFERRED] The HTML has been stable for about six years, because 2020 selectors still match 2026 code on both sites.
- [INFERRED] SuperCarros evidence is thinner. One 2026 scraper renders listing pages with Playwright, while two others (June 2026 and 2020) use plain HTTP fetches. No repo mentions Cloudflare, CAPTCHA or rate limits on either site.
- [INFERRED] Several repos publish seller phones and emails (the DryFernandez xlsx) or strip watermarks. That is exposure the audit should avoid copying.

## 3. Dominican legal context (not legal advice; counsel must review)

Access, commercial reuse, and legal interpretation are separate questions. The notes below restate the statute texts that were read. INFERRED marks the researcher's reading, which is not a legal conclusion. A robots.txt allowance is evidence about access only.

**Ley 172-13 on personal data.** [VERIFIED] Source: https://presidencia.gob.do/sites/default/files/statics/transparencia/marco-legal/leyes/Ley-172-13.pdf.

- Art. 2 applies the law to personal data in any data bank and to any later use, in both the public and private sectors.
- Art. 5, numeral 8, sets the purpose principle. Data must be adequate, relevant and not excessive for explicit, legitimate purposes.
- Art. 6 defines personal data as any numeric, alphabetic, graphic, photographic or other information about identified or identifiable natural persons.
- Art. 6, numeral 14, defines "fuentes accesibles al público" as files anyone may consult unless a limiting rule prevents it. It names phone directories, professional-group lists, official bulletins and "los medios de comunicación".
- Art. 27(1) says consent is not needed to process or transfer data obtained from sources of public access.
- The sanctions chapter (Arts. 81 to 87) targets credit bureaus (Sociedades de Información Crediticia) under the Superintendencia de Bancos. I found no general data protection authority in the law.
- [INFERRED] Seller names and phone numbers in ads are personal data. Whether a private classifieds site counts as a "fuente de acceso público" is an open question. **Counsel review.**

**Ley 74-25, the new Penal Code, now in force.** [VERIFIED] Source: https://transparencia.poderjudicial.gob.do/observatorio//documentos/PDF/normativas//NOR_enal_de_la_Republica_Dominicana.pdf. The in-force date of 2026-08-03 comes from Infobae [VERIFIED]: https://www.infobae.com/republica-dominicana/2026/08/03/el-sistema-judicial-dominicano-estrena-el-nuevo-codigo-penal-endureciendo-penas-y-sumando-nuevos-delitos/.

- Art. 198 criminalizes anyone who collects, stores or commercializes another person's data "mediante procedimientos automatizados", with intent and without prior consent (or after consent is withdrawn or opposed). It also covers anyone who accesses such data or discloses private information.
- The penalty is 1 to 2 years and 3 to 6 public-sector minimum salaries. A negligent version carries a fine of 1 to 3 minimum salaries.
- Art. 199 extends liability to legal persons. Prosecution requires a private complaint.
- Art. 391(7) repeals only the provisions of Ley 53-07 that are contrary to the code. Art. 392 keeps special laws in force for offenses the code does not define. Art. 393 sets entry into force 12 months after promulgation.
- [INFERRED] Art. 198 is the provision that bears most directly on automated collection of seller names and phones. How it interacts with the Ley 172-13 Art. 27 public-source exemption and with its intent requirement is untested. **Counsel review, high priority.**

**Ley 53-07 on high-technology crimes.** [VERIFIED] Source: https://www.oas.org/juridico/PDFs/repdom_ley5307.pdf.

- The law defines "Acceso Ilícito" as entering, or intending to enter, an information system without authorization.
- Art. 6 punishes accessing a system "excediendo una autorización" with 3 months to 1 year and a fine of 1 to 200 minimum salaries. Párrafo I raises this to 1 to 3 years when confidential data is revealed.
- Art. 10 covers copying or altering data with fraudulent purposes.
- Art. 11 (sabotage) covers hindering or causing malfunction of a system, which is relevant to request load.
- Art. 25 punishes copyright and industrial-property offenses committed through electronic means under those laws.
- [INFERRED] Whether terms of use or robots.txt define "authorization" for public pages is untested. **Counsel review.**

**Ley 65-00 on copyright.** [VERIFIED] Source: https://www.aduanas.gob.do/media/3yndr4ja/65-00_sobre_derecho_de_autor.pdf.

- Art. 2, numeral 12, protects databases and compilations whose selection or arrangement is an intellectual creation, but not the data or materials themselves.
- Art. 2, numeral 8, protects photographic works.
- Art. 169 sets 3 months to 3 years of prison and 50 to 1,000 minimum salaries for the listed infringements. I found no sui generis database right in the text.
- [INFERRED] Listing facts such as price, year and area are weakly protected. Photos and ad text are protected works. **Counsel should confirm** that no other law adds a database right.

**Court decisions and regulator guidance.**

- [SNIPPET] Three searches found no Dominican decision or regulator guidance on web scraping. Constitutional Court habeas data rulings exist (TC/0204/13, TC/0420/16, TC/0551/24 and others), but none is about scraping.
- [INFERRED] Spanish and EU commentary that appears in results is not Dominican law.

**Counsel checklist.**

1. Does Penal Code Art. 198 reach a price aggregator that stores no seller identity?
2. Is a private classifieds site a "fuente accesible al público" under Ley 172-13?
3. Does a breach of the terms of use equal "excediendo una autorización" under Ley 53-07 Art. 6?
4. Is Cibermercado's compilation protected by Ley 65-00 Art. 2(12)?
5. Can Cibermercado enforce its commercial-reuse clause against non-users of the site?

## 4. Scrapling

**Release, Python and license.** Sources: https://pypi.org/pypi/scrapling/json and the GitHub API for D4Vinci/Scrapling.

- [VERIFIED] The latest version is 0.4.15, uploaded 2026-08-23. GitHub release v0.4.15 is dated the same day. It requires Python 3.10 or later.
- [VERIFIED] The license is BSD-3-Clause, copyright 2024 Karim Shoair. The PyPI classifier is "Development Status 4 - Beta".

**Dependencies.** [VERIFIED] Per-version PyPI JSON.

- Core: lxml>=6.1.1, cssselect>=1.5.0, orjson>=3.11.8, tld>=0.13.2, w3lib>=2.4.1 and typing_extensions.
- The `fetchers` extra adds click, curl_cffi>=0.16.1, playwright>=1.62.0, patchright>=1.62.1, browserforge>=1.2.4, apify-fingerprint-datapoints>=0.15.0, msgspec, anyio and protego (a robots.txt parser).
- The `ai` extra adds mcp>=2.0.0. The `rag`, `ai` and `shell` extras all pull `scrapling[fetchers]`, and `all` combines ai and shell.
- History: in 0.2.99 through 0.3.1, playwright, rebrowser-playwright and camoufox were core dependencies. They moved into the `fetchers` extra in 0.3.2 (2025-09-15). Camoufox was dropped in 0.3.13 (2026-01-01).

**Parser without a browser.**

- [VERIFIED] The README says a plain `pip install scrapling` installs only the parser engine. Importing `scrapling.fetchers` or `scrapling.spiders` without the extra raises ModuleNotFoundError.
- [VERIFIED] `scrapling.parser` and `scrapling.core` import only the standard library and the core dependencies. `from scrapling import Selector` is lazy. `Adaptor` remains an alias of `Selector`.
- [INFERRED] The parser works without any browser download. I read the source but did not execute it.

**What `scrapling install` downloads.** [VERIFIED] `scrapling/cli.py`.

- It runs `python -m playwright install chromium` and `python -m playwright install-deps chromium`. The second installs OS packages.
- It refreshes the public-suffix list through `tld` and writes a marker file into the package directory.

**Stealth defaults in the plain Fetcher.** [VERIFIED] `engines/static.py` and `toolbelt/fingerprints.py`.

- Stealth is on by default. The Fetcher uses `impersonate="chrome"`, a curl_cffi browser TLS fingerprint, and `stealthy_headers=True`.
- With stealthy headers on, it sets `referer: https://www.google.com/` whenever none is given. If impersonation is off, it also adds browserforge-generated browser headers.
- Even with stealth off, the fallback User-Agent is a browserforge-generated browser string. Retries default to 3.
- [INFERRED] An honest client must pass `impersonate=None`, `stealthy_headers=False` and an explicit User-Agent.

**StealthyFetcher defaults.** [VERIFIED] `_browsers/_validators.py` and `_stealth.py`.

- `google_search=True` (Google referer) is on by default.
- `solve_cloudflare=False` by default. When enabled, it detects Turnstile and interstitial challenges, retries up to 3 times, and requires a timeout of at least 60 s.
- `hide_canvas` and `block_webrtc` default to False. `allow_webgl` defaults to True.

**Other README features.** [VERIFIED]

- The README advertises that its fetchers bypass Cloudflare Turnstile and interstitial pages without extra setup.
- It also lists ProxyRotator (cyclic or custom rotation), optional DNS-over-HTTPS through Cloudflare, remote CDP browsers, XHR capture, blocked-request detection with retry, and spider AutoThrottle.
- `robots_txt_obey` is optional and defaults to False (`spiders/spider.py`).
- The README sponsor block is mostly proxy vendors, plus an anti-bot bypass API for Akamai, DataDome, Incapsula and Kasada.

**Adaptive relocation.** [VERIFIED] `core/storage.py`, `core/utils/_utils.py` and `parser.py`.

- It is off by default (`adaptive=False`, `auto_save=False`).
- When enabled, it writes SQLite rows `storage(url, identifier, element_data)` keyed by the site's base domain and the selector.
- `element_data` stores the tag, cleaned attributes, the element's text, its DOM path, the parent's tag, attributes and text, and sibling and child tags.
- The default database file is `elements_storage.db` inside the installed package directory.
- [INFERRED] Auto-saving an element that contains a seller name or phone would persist that text. Pass an explicit `storage_file`.

**Maintenance.** [VERIFIED] GitHub API on 2026-09-27.

- 25 releases in the last 12 months, from v0.3.6 (2025-10-01) to v0.4.15. 1 open issue, 1 open PR and 163 closed issues.
- 31 contributors. D4Vinci has 1,548 commits and the next contributor has 15, so in effect there is one maintainer.
- 84,046 stars, 8,596 forks, last push 2026-09-27.

**Stated terms.** [VERIFIED] The README Disclaimer calls the library "for educational and research purposes only". It tells users to comply with scraping and privacy laws and to respect site terms and robots.txt, and it disclaims responsibility for misuse.

## 5. Alternative Dominican value sources

**DGII vehicle values.**

- [VERIFIED] The public ASP.NET form `vehiculosLivianos.aspx` has Marca, Modelo, Categoría and Año dropdowns (years 1972 to 2026) and returns values in RD$. It has no export option. Source: https://dgii.gov.do/app/WebApps/ConsultasWeb2/ConsultasWeb/consultas/vehiculosLivianos.aspx.
- [VERIFIED] DGII's help article describes the lookup by make, model and year. Source: https://ayuda.dgii.gov.do/conversations/vehculos-de-motor-informacin-general/ca2087-qu-debo-hacer-para-acceder-a-la-tabla-de-valores-de-vehculos-livianos-vehculos-pesados-camiones-y-autobuses-de-la-dgii/5f3c175e8cd858ce8799c7cd.
- [VERIFIED] Norma General 03-2025 replaces 06-2013. It sets the 2% transfer tax on the greater of the declared price and DGII's "valores fidedignos" table, and owners can request a table review with documentation. Source: https://www.diariolibre.com/economia/negocios/2025/03/25/dgii-actualiza-norma-sobre-traspasos-y-endosos-de-vehiculos/3046910.
- [VERIFIED] The marbete is a fixed fee, not a share of value: RD$1,500 for models through 2019 and RD$3,000 for 2020 and later. Source: https://dgii.gov.do/vehiculosMotor/Paginas/impuestoCirculacionVehiculos.aspx.
- [SNIPPET] Separate forms exist for heavy vehicles and for trucks and buses. They are named in robocot20's code.
- [INFERRED] These are fiscal floor values, not market prices. The data is public but has no API or bulk download.

**Catastro Nacional.**

- [VERIFIED] The "Índice de Precios" page publishes cadastral land values per m2 by province and municipality as downloadable documents, under Ley 150-14 and Decreto 550-03. Some are marked 2024. No API is mentioned. Source: https://www.catastro.gob.do/index.php/indice-de-precios.
- [SNIPPET] The Catastro offers an owner-requested "avalúo" service, an online office, and an ArcGIS geoportal with land-value layers.
- [VERIFIED] A DGII IPI property-value lookup page exists, but its inputs were not visible. Source: https://dgii.gov.do/herramientas/consultas/Paginas/Valor-de-inmueble-(IPI).aspx.

**Bank appraisals.** [VERIFIED] Superintendencia de Bancos asset evaluation regulation (REA), 2017 text, Art. 68. Source: https://www.sb.gob.do/media/xnanx3o3/reglamento_de_evaluacion_de_activos_rea_28_09_2017.pdf.

- Guarantees are valued at market (realization) value by an independent appraiser or a bank employee.
- Commercial real estate is reappraised at least every 24 months, or the insured value is used. Residential real estate uses the insured value.
- Used vehicles take a professional appraisal or the insured amount, updated annually. New vehicles take the dealer quote.
- Real estate appraisers must be registered with ITADO, CODIA or a UPAV-accredited guild.
- [INFERRED] Appraisals are private documents. There is no public dataset. Later amendments to the REA may exist, so check before relying on these rules.

**Corotos.**

- [VERIFIED] The legal page names Domino Capital S.R.L. as operator. It explicitly prohibits scraping and crawling, sets a penalty of up to RD$1,000 per scraped image, and mentions no API. Source: https://www.corotos.com.do/legals.
- [VERIFIED] Corotos was founded in 2011 by Schibsted and sold to local investors in 2020. Source: https://es.wikipedia.org/wiki/Corotos.com.do.
- [VERIFIED] An inbound publishing integration with AlterEstate exists (post dated 2025-01-13). Source: https://www.corotos.com.do/blog/integracion-corotos-y-alterestate-publica-tus-propiedades-con-un-solo-clic.

**Facebook Marketplace.**

- [VERIFIED] Meta's Automated Data Collection Terms (effective 2024-10-07) forbid automated collection without Meta's express written permission. Source: https://www.facebook.com/legal/automated_data_collection_terms.
- [SNIPPET] There is no public Marketplace listings API.

**Encuentra24.**

- [SNIPPET] Encuentra24 operates in the Dominican Republic and accepts XML imports for publishing listings.
- [VERIFIED] The armla/encuentra24-feed repo points a feed at Encuentra24's "automated import". Source: https://github.com/armla/encuentra24-feed.
- [SNIPPET] No read API was found. [VERIFIED] https://www.encuentra24.com/dominicana-es/autos-usados returned 403 to WebFetch.

**Real estate brokerages and associations.**

- [SNIPPET] RE/MAX portals exist (remaxrd.com, remaxm.net, remaxhome.do), and Century 21 operates in the country. One search found no API or data licensing for either.
- [SNIPPET] portalinmobiliariord.com claims to aggregate RE/MAX, Century 21 and other agencies.
- [SNIPPET] AEI (aei.com.do, founded 1989, 289 member firms) runs a members-only MLS.

## 6. Market-structure facts affecting comparability

**Vehicle currency.**

- [VERIFIED] The carrosrd.com homepage on 2026-09-27 showed 16 prices in US$ and 12 in RD$, for example "US$23,900" and "RD$930,000".
- [VERIFIED] zabdielmaestre's SuperCarros parser matches prices starting with either RD$ or US$.
- [SNIPPET] A SuperCarros Jeep Commander 2024 was listed at US$49,900.
- [INFERRED] Both currencies are common on vehicle ads, so normalize with a dated exchange-rate series.

**Financing and "inicial".**

- [SNIPPET] SuperCarros has a financing calculator and bank fair pages. TuVehiculo.do lets buyers adjust the down payment.
- [VERIFIED] carrosrd.com listing cards showed no "inicial" or monthly-payment prices.
- [INFERRED] No evidence shows headline prices quoted as down payments. Free-text mentions of "inicial" are likely, so flag them as text rather than treating them as prices.

**Property currency.**

- [VERIFIED] Listín Diario (2025-02-21) reports rising US$ pricing of sales and rentals in Santo Domingo. It gives rents such as US$2,000 in Las Praderas and sale prices of US$1,500 to 2,800 per m2 in the central polygon. It notes that Ley 183-02 does not expressly prohibit pricing in foreign currency. Source: https://listindiario.com/economia/bolsillo/20250221/e_846493.html.
- [SNIPPET] SuperCasas sale listings in Punta Cana are priced in US$ with areas in "Mt2". A furnished rental in Ciudad Real II was RD$45,000 a month for 83.10 m2.
- [VERIFIED] inmo-insight parses rents such as "Alquiler: RD$ 25,000" and hard-codes USD to DOP at 64.
- [INFERRED] Sales are mostly in US$. Rents are mixed, with RD$ common and US$ at the high end. Always parse the currency token.

**Pre-construction ("en planos").**

- [SNIPPET] SuperCasas Punta Cana listings carry an "En Planos" condition, US$2,000 separation deposits, US$500 monthly payments, and delivery dates such as November 2025 and October 2027.
- [VERIFIED] inmobiliario.do (2026-05-14) calls buying off-plan one of the most demanded options, cites appreciation claims of 15 to 30%, and quotes prices in US$. Source: https://inmobiliario.do/comprar-inmuebles-en-plano-puede-generar-plusvalia-de-hasta-un-30-afirman-especialistas/.
- [SNIPPET] Trusts under Ley 189-11 (fideicomiso) are voluntary except for incentivized low-cost housing.
- [INFERRED] Use the "Condición:" field to separate off-plan from resale.

**Area units.**

- [VERIFIED] 1 tarea is 628.86 m2, 1 square vara castellana is 0.698 m2, and 1 square vara conuquera is 6.289 m2. Metric is the only legal standard. Source: https://mipais.jmarcano.com/varios/medidas/medidas2/.
- [VERIFIED] SuperCasas labels "Construcción:" and "Terreno:" hold metric values (inmo-insight code).
- [SNIPPET] No square-foot units appeared in SuperCasas results.
- [INFERRED] Expect m2 for buildings and m2 or tareas for land (fincas, solares). Square feet should be rare.

## Request log

**WebFetch calls, in order.** None went to supercarros.com, supercasas.com, their subdomains, or archives.

1. https://apps.apple.com/us/app/supercasa/id1575765638 (429, no content)
2. https://www.dnb.com/business-directory/company-profiles.cibermercado_srl.8f8b0f2f32b0a189fd75d4eec382dcb7.html (403)
3. https://es.wikipedia.org/wiki/Corotos.com.do
4. https://rdap.verisign.com/com/v1/domain/supercarros.com (Verisign registry, not the site)
5. https://rdap.verisign.com/com/v1/domain/supercasas.com (Verisign registry, not the site)
6. https://alterestate.com/do/productos/crm-inmobiliario/
7. https://www.obriencrm.com/software-crm-inmobiliario-republica-dominicana/
8. https://www.corotos.com.do/blog/integracion-corotos-y-alterestate-publica-tus-propiedades-con-un-solo-clic
9. https://github.com/formulard/webscraping_inmobiliario
10. https://presidencia.gob.do/sites/default/files/statics/transparencia/marco-legal/leyes/Ley-172-13.pdf
11. https://www.oas.org/juridico/PDFs/repdom_ley5307.pdf
12. https://www.aduanas.gob.do/media/3yndr4ja/65-00_sobre_derecho_de_autor.pdf
13. https://www.infobae.com/republica-dominicana/2026/08/03/el-sistema-judicial-dominicano-estrena-el-nuevo-codigo-penal-endureciendo-penas-y-sumando-nuevos-delitos/
14. https://transparencia.poderjudicial.gob.do/observatorio//documentos/PDF/normativas//NOR_enal_de_la_Republica_Dominicana.pdf
15. https://dgii.gov.do/vehiculosMotor/consultas/Paginas/default.aspx
16. https://ayuda.dgii.gov.do/conversations/vehculos-de-motor-informacin-general/ca2087-qu-debo-hacer-para-acceder-a-la-tabla-de-valores-de-vehculos-livianos-vehculos-pesados-camiones-y-autobuses-de-la-dgii/5f3c175e8cd858ce8799c7cd
17. https://www.catastro.gob.do/index.php/indice-de-precios
18. https://dgii.gov.do/herramientas/consultas/Paginas/Valor-de-inmueble-(IPI).aspx
19. https://dgii.gov.do/app/WebApps/ConsultasWeb2/ConsultasWeb/consultas/vehiculosLivianos.aspx
20. https://wasi.zendesk.com/hc/es/articles/4411276989079--C%C3%B3mo-vincular-y-publicar-tus-inmuebles-en-Encuentra-24 (403)
21. https://www.corotos.com.do/legals
22. https://www.facebook.com/legal/automated_data_collection_terms
23. https://github.com/armla/encuentra24-feed
24. https://www.sb.gob.do/media/xnanx3o3/reglamento_de_evaluacion_de_activos_rea_28_09_2017.pdf
25. https://dgii.gov.do/vehiculosMotor/Paginas/impuestoCirculacionVehiculos.aspx
26. https://dgii.gov.do/app/WebApps/Calculadoras/transferenciaVehiculos/Default.aspx
27. https://www.diariolibre.com/economia/negocios/2025/03/25/dgii-actualiza-norma-sobre-traspasos-y-endosos-de-vehiculos/3046910
28. https://alterestate.com/publica-tus-inmuebles-en-el-portal-de-la-aei-desde-alterestate/ (404)
29. https://listindiario.com/economia/bolsillo/20250221/e_846493.html
30. https://www.encuentra24.com/dominicana-es/autos-usados (403)
31. https://inmobiliario.do/comprar-inmuebles-en-plano-puede-generar-plusvalia-de-hasta-un-30-afirman-especialistas/
32. https://carrosrd.com/
33. https://mipais.jmarcano.com/varios/medidas/medidas2/

**Other network reads through Bash.**

- `curl` to pypi.org: `/pypi/scrapling/json` plus per-version JSON for 0.2.99, 0.3, 0.3.1 to 0.3.5, 0.3.8 to 0.3.14, 0.4 and 0.4.10.
- `curl` to rdap.verisign.com for the same two registry records as above.
- `gh api` and `gh search` to api.github.com for the repos named in sections 2 and 4. Actions job logs came through GitHub's log redirect.
