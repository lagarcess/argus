# Listing sample run record, 2026-09-27

This folder is the run record for [the listing enrichment feasibility report](../../asset-listing-enrichment-feasibility.md). It holds sanitized aggregates, the scripts that produced them, and two synthetic fixtures with offline checks. It holds no real listing text, listing identifier, listing URL, seller data, or photograph. The fixtures' seller fields are invented placeholders.

## Run facts

- Repository commit read for the audit: `f0a90763b79e5625ac0a4789cdfa171cda023963`, the tip of `origin/codex/private-alpha-next` fetched on 2026-09-27.
- Sampling window: 2026-09-27 from 21:32:19 to 21:44:02 UTC.
- Fetcher: `scripts/fetch_ledger.py`, Python standard library `urllib` only, run on Python 3.14.7.
- User agent: `ArgusFeasibilityAudit/0.1 (one-time manual research sample; at most 20 requests per site; 4s spacing)`.
- Parsers: Python 3.10.20, the version in `.python-version`, in two isolated `uv` environments outside the repository. One held `beautifulsoup4` 4.15.0 with `lxml` 6.1.3. The other held `scrapling` 0.4.15 core, without extras. `parser-comparison.json` lists each package version. Parse timings varied by about 20 percent between two runs on the same laptop.
- No Argus lockfile, application code, or environment changed.

## Rules the fetcher enforces

These rules describe `scripts/fetch_ledger.py` at this commit. Review rounds on 2026-09-28 added the URL, header, and retention rules after the sample ran.

- It sends at most 20 requests per site. The count covers every host of the brand and includes `robots.txt`.
- It sends one request at a time, at least 4 seconds after the previous one. The assignment's floor was 3 seconds.
- It decides the page kind and the robots exemption from the URL alone. It takes no caller label.
- It accepts exactly four URL shapes, on each brand's bare, `m.`, and `www.` hosts. They are `/robots.txt` and `/sitemap.xml` with no query, `/assets/js/searchvalues.js` with an optional numeric build query, and detail pages shaped `/<slug>/<digits>/`. The slug may use only lowercase letters, digits, commas, and hyphens. Any other shape is refused, including percent-encoding, dot segments, backslashes, semicolon parameters, and uppercase letters.
- It refuses a URL that is not plain https, or that carries a port, userinfo, or a fragment. It also refuses a detail URL whose slug holds a contact detail, because the ledger records every URL it requests. The slug is the only free text in an accepted URL. The host, the listing ID, and the build number are declared tokens, so a ten-digit ID is not read as a phone number.
- `page_kind` in `scripts/retention.py` holds these URL rules. The same rules decide which sitemap rows and redirect targets are kept.
- It fetches `robots.txt` for a host before any other page on that host. It refuses any URL that file disallows. It checks the rules as written, and again with both rules and path lowercased, because these sites serve paths in any case.
- It follows no redirect by itself. It records a redirect target only when the target is a URL it may request, and `undeclared` otherwise. The robots gate follows a `robots.txt` redirect only to another `robots.txt` on the same site.
- It stops a site after a 401, 403, 407, 429, or 503 status, or after a known bot-check page marker. The stop is a file that later calls respect.
- It replays a cached URL instead of fetching it again.
- It never logs in, reuses cookies, rotates proxies, imitates a browser, or runs JavaScript.
- It holds each response in memory and writes only what `scripts/retention.py` keeps. The rules are described under Sanitization.
- Its ledger records the content type and the server only when each fits a declared shape, and `undeclared` otherwise. Besides those and the redirect target, it records only whether a cookie was set.
- Its ledger, cache, budget, and stop files live in the directory it runs from. A new directory starts a new budget and needs its own authorization.

A robots.txt allowance only lets the fetcher read a page. It grants no right to reuse what the page contains. The report treats reuse under the sites' terms as a separate question.

## Requests

| Site | robots.txt | Sitemap | Home | Terms | Search values script | Category page | Detail pages | Total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SuperCarros | 2 | 1 | 1 | 1 | 1 | 0 | 10 | 16 |
| SuperCasas | 2 | 1 | 1 | 1 | 1 | 1 | 10 | 17 |

All 33 responses were HTTP 200. None met a stop condition. The smallest gap between two requests was 4 seconds. Detail pages took a median of 156.5 ms on SuperCarros and 146 ms on SuperCasas, with a slowest single response of 1,127 ms. `request-ledger.json` lists every request. Detail paths show `<listing-id>` in place of the number.

## Files

- `request-ledger.json` lists each request with its status, size, and time.
- `sitemap-profile.json` counts listing URLs, slug words, `lastmod` ages, and listings per model or per property type and sector.
- `field-summary.json` counts field completeness and value shapes over the 20 detail pages, per site. It holds counts, not rows.
- `parser-comparison.json` holds parse times, the output comparison, and the markup-change test.
- `fixtures/` holds two synthetic detail pages and `expected.json`, the hand-reviewed output that `scripts/check_fixtures.py` asserts.
- `scripts/` holds the code that produced the files above, the retention rules, and the offline checks.
- `canon-map.md` maps the canon on assets, ownership, valuation, currency, evidence, and open decisions at the audited commit. Its quote-check script reads that commit with `git show` and matched all 272 quotes to their cited lines.
- `code-reuse-map.md` maps reusable code with a path and line for each claim.
- `web-research.md` records public facts about both sites, Dominican law, Scrapling, and other value sources. It lists every URL it read. None was on either site.

## How the sample was drawn

`scripts/select_sample.py` draws only from each site's `sitemap.xml`, with the seed `20260927`. It takes these strata:

- SuperCarros: 5 `honda-crv` pages with `lastmod` at most 30 days old, 1 `honda-crv` page older than 365 days, 3 other models at most 90 days old, and 1 other model between 91 and 365 days old.
- SuperCasas: 5 `apartamentos-ensanche-naco` pages at most 30 days old, 1 older than 365 days, 2 `casas-*` pages and 1 `villas-*` page at most 90 days old, and 1 apartment in Bávaro, Cap Cana, or Punta Cana at most 90 days old.

`honda-crv` and `apartamentos-ensanche-naco` were the largest slugs in each sitemap. The clusters show how comparable a set of same-model or same-sector ads is. Ten pages per site cannot show market coverage, long-term reliability, or valuation accuracy.

## Sanitization

The committed sample evidence came from the audit's first pipeline. That pipeline cached whole pages, and the cache was deleted after the evidence was written. The current fetcher keeps these projections instead, built in memory before any write:

- `robots.txt` keeps its rules without comments.
- `sitemap.xml` keeps each row whose URL is a detail page the fetcher may request on the same site, with its `lastmod` date when that date is in W3C format. It drops every other row, including dealer, agency, and directory pages and rows with a query, another host, or a contact detail.
- The search values script keeps only its brand list, `SearchBrands`, which is the only part the summary reads.
- A detail page is rebuilt from decoded text in fixed markup. It keeps the title, the price and feature list, the specification list, and the accessories list in the shape the parsers read them. It also keeps the meta description, the listing page variables whose values are numbers, keyword flags and numbers computed from the free text, the seller heading word such as "Vendedor" or "Inmobiliaria", a location reduced to its last comma-separated part when that part is plain place text, and whether a dealer link exists. It copies no other attribute, link, or image from the page.
- A detail page drops the seller block, the free text, photos, maps, and the page variables that identify the seller.

A page the rules cannot project keeps nothing. Every value the fetcher writes is either free text or a declared token. Free text is a listing slug, a title, a list item, the meta description, the `robots.txt` rules, a search values entry, or a fact drawn from the ad text. A page keeps nothing when any of its free text holds a phone-shaped digit group from any country, an email address, a WhatsApp, tel, or mailto link, map coordinates, or a dealer name in a link. The guard reads each kept item with entities decoded, and with its text joined both with and without spaces, so a contact detail split by markup is caught. A declared token, such as a host, a listing ID or listing number, a build number, a date, or a page variable, is kept only when it fits its shape, and is never read as free text. The guard matches shapes, so it cannot recognize a number spelled in words or broken by unusual separators. Keeping only the fields the parsers read is the main control.

- No later script writes a raw page, free text, or a seller field. `run_parse.py` writes normalized records, timings, and versions. The resilience scripts mutate kept pages in memory, and Scrapling's adaptive storage lives in a temporary directory.
- The committed sample files hold aggregates and value shapes, where every digit prints as `9`. They hold no per-listing row.
- The fixtures are synthetic. Their markup follows the structure the audit observed, with class names and field labels, but every value is invented. Their seller fields are placeholders such as `Vendedor Ficticio`, `000-000-0000`, and `vendedor@example.invalid`.
- During manual markup inspection, a phone-number mask missed the `+1809` format. One dealer name and two contact names appeared in the audit session's terminal output. None of it was written to this folder or to the report.

## What was replayed and what a reviewer can rerun

### The audit's replay, before cleanup

Before deleting the raw page cache, the audit copied the scripts as first committed to a clean scratch directory and ran them against that cache. The run regenerated `request-ledger.json`, `sitemap-profile.json`, `field-summary.json`, and both parsers' normalized output byte for byte. Only parse timings changed. The cache was then deleted because it held seller data. Nobody can repeat that replay now.

### Rerun the offline checks

These checks need no site access. The fetch-policy check needs only Python 3.10 or later. The fixture checks also need two pinned packages. From the repository root, run:

```bash
python3 docs/reports/evidence/asset-listing-enrichment/scripts/check_fetch_policy.py
uv venv --python 3.10 /tmp/listing-fixtures/venv-simple
uv pip install --python /tmp/listing-fixtures/venv-simple/bin/python beautifulsoup4==4.15.0 lxml==6.1.3
uv venv --python 3.10 /tmp/listing-fixtures/venv-scrapling
uv pip install --python /tmp/listing-fixtures/venv-scrapling/bin/python scrapling==0.4.15
/tmp/listing-fixtures/venv-simple/bin/python docs/reports/evidence/asset-listing-enrichment/scripts/check_fixtures.py bs4
/tmp/listing-fixtures/venv-scrapling/bin/python docs/reports/evidence/asset-listing-enrichment/scripts/check_fixtures.py scrapling
```

Each command prints `all checks pass` and exits 0.

`check_fetch_policy.py` runs the real fetcher against a fake network in a temporary directory. It asserts these results:

- Each crafted URL is refused, and none of them sends a request. The list covers a caller label and a disallowed path. It also covers the path's uppercase, percent-encoded, and double-encoded spellings, a semicolon parameter, and a lowercase request against a mixed-case rule. Dot segments, backslashes, an uppercase slug, `robots.txt` with a query, and a non-numeric search values query are refused too. So are plain http, explicit, default, and malformed ports, userinfo, the home page, a dealer page, a phone number in a listing slug, a search page, a seller-named subdomain, and an unaudited host.
- Each kind keeps only its projection. A sitemap keeps only its declared listing rows, even when another row holds a contact detail. The search values script keeps only its brand list, not the seller list beside it.
- Ten-digit listing IDs and build numbers are accepted. A URL, a sitemap row, and a detail page that carry one are kept, and the page keeps its `#` listing number and `adId` variable.
- Eleven detail pages keep nothing. One lacks a seller boundary. The other ten hold a contact detail in a listing field or in the ad text. Two are plain phone numbers, in the title and in a specification. Four use entities: an email in the title, phone digits in a feature, a phone number in the meta description, and a WhatsApp link in the price. Three are phone numbers split by markup, in the title, a specification, and an accessory. One is a phone number written as a mileage in the ad text, which would otherwise reach the kept facts.
- Two pages keep their listing text without the attributes, links, and images inside their list items. One carries a seller attribute, an image, and a seller name in a page variable, which is dropped because page variables must be numbers. The other carries contact details in attributes and a dealer link.
- Seven redirects that name a seller are recorded as `undeclared`. They include a dealer page, a seller path with no contact shape, and percent-encoded forms up to nine layers deep. A redirect to another listing is recorded as that listing's URL. A `robots.txt` redirect to another `robots.txt` on the same site is recorded and followed, and the page behind it is kept.
- Header values outside their declared shapes are recorded as `undeclared`.
- The contact guard matches seven phone shapes, including Miami and Mexico numbers, plus an entity-encoded email and a phone split by markup. It flags none of eight normal listing values such as prices, IDs, and timestamps.
- No file the fetcher writes holds a placeholder seller value or a contact pattern, read raw, with entities decoded, or with tags removed.

`check_fixtures.py` asserts these results for each fixture:

- The raw page and the kept projection give the same normalized record, equal to `fixtures/expected.json`.
- No placeholder seller value, contact pattern, or seller page variable reaches that record or the projection.
- After the class rename and after the restructure, class selectors recover no specification value. Label lookup recovers 14 of 14 on the vehicle page and 9 of 10 on the property page, where the search form repeats `Condición:`.
- Scrapling's adaptive mode recovers no value and relocates to the accessories list.
- The real fetcher keeps both fixtures from a fake network, and `run_parse.py` and the resilience script run on what it kept, in a temporary directory. Both fixtures reach the normalized output, and no file written there holds seller data, read raw, with entities decoded, or with tags removed.

The fetcher before the first fix requested a disallowed path when called with `--label robots`, and its cache held 13 of the placeholder seller values. The check at `7d9be18f4` reports 26 failures against `8e31032f1`, the head before the round that moved every write behind `scripts/retention.py`. Eight files written there hold placeholder seller values. They carry a phone number and a dealer path from listing URLs, seller text from response headers, and a redirect target that names a seller. They also carry sitemap rows with another host, a query, or free text in the date, the seller list in the search values script, and a seller attribute and an image address kept inside list items. The current check reports 13 failures against `7d9be18f4` and 4 against `944bcff5a`. At `7d9be18f4`, ten-digit listing IDs and build numbers are read as phone numbers. At both heads, a seller-named subdomain passes as an audited host, and a page variable keeps a seller name. At `944bcff5a`, a sitemap with a ten-digit listing row is dropped whole, and a detail page with a ten-digit listing ID keeps nothing. The fixture check also fails when retention keeps raw pages, when an expected value changes, when the normalizer leaks the seller location line, and when a parser returns no specifications.

The fixtures do not reproduce every real-page result. On real pages, Scrapling's adaptive mode sometimes relocated to the seller contact list. On the fixtures it relocated only to the accessories list. The fixtures cannot reproduce the sample's counts, dates, or prices.

### Collect a new sample

`scripts/fetch_ledger.py` and `scripts/fetch_sample.py` send real requests. Run them only under an assignment that authorizes live sampling, and read each site's current `robots.txt` and terms first. Every other script reads the local cache and sends nothing. A new run samples the listings of its own day, so its numbers differ from the committed files. Its markup-change results also differ, because kept projections drop the search form that caused the label collision.

Run these from a scratch directory outside the repository. The fetcher refuses to run inside the repository. The first command assumes the repository root is in `REPO`.

```bash
mkdir -p ~/listing-audit && cp "$REPO"/docs/reports/evidence/asset-listing-enrichment/scripts/*.py ~/listing-audit/ && cd ~/listing-audit
python3 fetch_ledger.py https://m.supercarros.com/robots.txt
python3 fetch_ledger.py https://m.supercasas.com/robots.txt
python3 fetch_ledger.py https://m.supercarros.com/sitemap.xml
python3 fetch_ledger.py https://m.supercasas.com/sitemap.xml
python3 fetch_ledger.py "https://m.supercarros.com/assets/js/searchvalues.js?20260927053"
python3 select_sample.py
python3 fetch_sample.py
uv venv --python 3.10 venv-simple
uv pip install --python venv-simple/bin/python beautifulsoup4==4.15.0 lxml==6.1.3
uv venv --python 3.10 venv-scrapling
uv pip install --python venv-scrapling/bin/python scrapling==0.4.15
venv-simple/bin/python run_parse.py bs4
venv-scrapling/bin/python run_parse.py scrapling
venv-simple/bin/python resilience_bs4.py
venv-scrapling/bin/python resilience_scrapling.py
python3 summarize.py
python3 density.py
python3 compare.py
```

The `?20260927053` suffix on the search values script was the build string on 2026-09-27. Read the current one from the home page in a browser. The audit also fetched both home pages, both terms pages, and `https://m.supercasas.com/apartamentos/` once each. The current fetcher refuses those pages, because it has no rule for keeping them.

## Cleanup

The raw page cache, the per-listing extraction, the listing salt, both environments, and the `uv` cache stayed in a local scratch directory. They were deleted after the evidence in this folder was written. The environments used for the offline checks were recreated in scratch and deleted after the checks.
