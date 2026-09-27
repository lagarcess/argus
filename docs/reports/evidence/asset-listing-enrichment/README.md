# Listing sample run record, 2026-09-27

This folder is the run record for [the listing enrichment feasibility report](../../asset-listing-enrichment-feasibility.md). It holds sanitized aggregates and the scripts that produced them. It holds no listing text, listing identifier, listing URL, seller field, or photograph.

## Run facts

- Repository commit read for the audit: `f0a90763b79e5625ac0a4789cdfa171cda023963`, the tip of `origin/codex/private-alpha-next` fetched on 2026-09-27.
- Sampling window: 2026-09-27 from 21:32:19 to 21:44:02 UTC.
- Fetcher: `scripts/fetch_ledger.py`, Python standard library `urllib` only, run on Python 3.14.7.
- User agent: `ArgusFeasibilityAudit/0.1 (one-time manual research sample; at most 20 requests per site; 4s spacing)`.
- Parsers: Python 3.10.20, the version in `.python-version`, in two isolated `uv` environments outside the repository. One held `beautifulsoup4` 4.15.0 with `lxml` 6.1.3. The other held `scrapling` 0.4.15 core, without extras. `parser-comparison.json` lists each package version. Parse timings varied by about 20 percent between two runs on the same laptop.
- No Argus lockfile, application code, or environment changed.

## Rules the fetcher enforces

- It sends at most 20 requests per site. The count covers every host of the brand and includes `robots.txt`.
- It sends one request at a time, at least 4 seconds after the previous one. The assignment's floor was 3 seconds.
- It fetches `robots.txt` for a host before any other page on that host, and refuses any URL that file disallows.
- It follows no redirect by itself.
- It stops a site after a 401, 403, 407, 429, or 503 status, or after a known bot-check page marker. The stop is a file that later calls respect.
- It replays a cached URL instead of fetching it again.
- It never logs in, reuses cookies, rotates proxies, imitates a browser, or runs JavaScript.

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
- `scripts/` holds the code that produced those files.
- `canon-map.md` maps the canon on assets, ownership, valuation, currency, evidence, and open decisions. Its quote-check script matched all 272 quotes to their cited lines.
- `code-reuse-map.md` maps reusable code with a path and line for each claim.
- `web-research.md` records public facts about both sites, Dominican law, Scrapling, and other value sources. It lists every URL it read. None was on either site.

## How the sample was drawn

`scripts/select_sample.py` draws only from each site's `sitemap.xml`, with the seed `20260927`. It takes these strata:

- SuperCarros: 5 `honda-crv` pages with `lastmod` at most 30 days old, 1 `honda-crv` page older than 365 days, 3 other models at most 90 days old, and 1 other model between 91 and 365 days old.
- SuperCasas: 5 `apartamentos-ensanche-naco` pages at most 30 days old, 1 older than 365 days, 2 `casas-*` pages and 1 `villas-*` page at most 90 days old, and 1 apartment in Bávaro, Cap Cana, or Punta Cana at most 90 days old.

`honda-crv` and `apartamentos-ensanche-naco` were the largest slugs in each sitemap. The clusters show how comparable a set of same-model or same-sector ads is. Ten pages per site cannot show market coverage, long-term reliability, or valuation accuracy.

## Sanitization

- The extraction reads the listing block. From the seller block it reads three things. It keeps the location line's last comma-separated part, the heading word such as "Vendedor" or "Inmobiliaria", and whether a dealer inventory link exists. The page variables that identify the seller are dropped.
- Free text is reduced to keyword flags, numbers, and a count of lost characters. No sentence leaves the parser.
- The committed files hold aggregates and value shapes, where every digit prints as `9`. They hold no per-listing row.
- During manual markup inspection, a phone-number mask missed the `+1809` format. One dealer name and two contact names appeared in the audit session's terminal output. None of it was written to this folder or to the report.

## Reproduce

`scripts/fetch_ledger.py` and `scripts/fetch_sample.py` send real requests. Run them only under an assignment that authorizes live sampling, and read each site's current `robots.txt` and terms first. Every other script replays the local cache and sends nothing. A new run samples the listings of its own day, so its numbers differ from the committed files.

Run these from a scratch directory outside the repository. The fetcher refuses to run inside the repository. The first command assumes the repository root is in `REPO`.

```bash
mkdir -p ~/listing-audit && cp "$REPO"/docs/reports/evidence/asset-listing-enrichment/scripts/*.py ~/listing-audit/ && cd ~/listing-audit
python3 fetch_ledger.py https://m.supercarros.com/robots.txt --label robots
python3 fetch_ledger.py https://m.supercasas.com/robots.txt --label robots
python3 fetch_ledger.py https://m.supercarros.com/sitemap.xml --label sitemap
python3 fetch_ledger.py https://m.supercasas.com/sitemap.xml --label sitemap
python3 fetch_ledger.py "https://m.supercarros.com/assets/js/searchvalues.js?20260927053" --label taxonomy
python3 select_sample.py
python3 fetch_sample.py
uv venv --python 3.10 venv-simple
uv pip install --python venv-simple/bin/python beautifulsoup4==4.15.0 lxml==6.1.3
uv venv --python 3.10 venv-scrapling
uv pip install --python venv-scrapling/bin/python scrapling==0.4.15
venv-simple/bin/python run_parse.py bs4
venv-scrapling/bin/python run_parse.py scrapling
python3 mutate.py
venv-simple/bin/python resilience_bs4.py
venv-scrapling/bin/python resilience_scrapling.py
python3 summarize.py
python3 density.py
python3 compare.py
```

The `?20260927053` suffix on the search values script was the build string on 2026-09-27. Copy the current one from the home page. The audit also fetched both home pages, both terms pages, and `https://m.supercasas.com/apartamentos/` once each with `fetch_ledger.py`.

`run_parse.py` writes a local `out/*.raw.local.json` file that holds free text and the seller location line. Never commit that file.

## Cleanup

The raw page cache, the per-listing extraction, the listing salt, both environments, and the `uv` cache stayed in a local scratch directory. They were deleted after the evidence in this folder was written.
