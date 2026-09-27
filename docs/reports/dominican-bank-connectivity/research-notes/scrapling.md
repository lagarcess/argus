# Scrapling relevance for Argus bank data

Research unit U6, written 2026-09-27. Argus needs user-authorized, read-only balances and transactions from Dominican banks that offer no APIs. This unit asks whether Scrapling (https://github.com/D4Vinci/Scrapling) helps with any of the options under review.

**Pinned sources.** Scrapling code was read at release v0.4.15, commit `333fa22b7a5821194ce66b59b11f4b16a6484f02`, published 2026-08-23. The README, docs, and CHANGELOG were read at `main` commit `e0d4d7563207b70c2cb38487c4e0dcbe0e2f04ca`, dated 2026-09-25. The 13 commits between the two change only README and docs files, images, `.gitignore`, `CONTRIBUTING.md`, and the site config `zensical.toml`, so the package code on `main` equals v0.4.15. A reference such as `scrapling/parser.py:77` means `https://github.com/D4Vinci/Scrapling/blob/333fa22b7a5821194ce66b59b11f4b16a6484f02/scrapling/parser.py#L77`. A reference to `README.md`, `CHANGELOG.md`, or `docs/` means that path at `e0d4d756`. Nothing was installed and nothing ran against a website. One script, in appendix A, reads Scrapling's source from GitHub and lists the parser's imports.

## Verdict

Scrapling is a scraping framework built to get past anti-bot systems and to scale crawls. For Argus's bank-data problem, only its HTML parser is usable, and `lxml` or BeautifulSoup already does that job. Scrapling has no reader for CSV, Excel, OFX, or PDF statements. It provides none of the consent, vaulting, MFA, monitoring, or reconciliation work an aggregation platform needs. Its stealth browser, Cloudflare solver, fingerprint spoofing, and proxy rotation are on Argus's out-of-bounds list, and even its plain HTTP fetcher copies a Chrome TLS fingerprint by default.

**Recommendation.** Do not adopt Scrapling for bank data. Its parser is acceptable for HTML the user saved or forwarded, if the team prefers its selector API, with `adaptive` off and the encoding passed explicitly. For public product pages, an HTTP client with an honest User-Agent plus `lxml` is enough. Use Scrapling spiders there only under a pinned configuration that turns off every evasion default.

## 1. What Scrapling is

### Project facts

| Fact | Value | Source |
| --- | --- | --- |
| Positioning | An adaptive scraping framework for anything from one request to a full crawl. The README says its fetchers "bypass anti-bot systems like Cloudflare Turnstile out of the box". | `README.md` lines 64-66 |
| License | BSD-3-Clause, copyright 2024 Karim Shoair | `LICENSE`; PyPI metadata |
| Latest release | v0.4.15, published 2026-08-23 on GitHub and on PyPI | GitHub releases API; https://pypi.org/project/scrapling/0.4.15/ |
| Status and runtime | PyPI classifier `Development Status :: 4 - Beta`; Python 3.10 or later | PyPI JSON API |
| Release cadence | 30 releases from v0.3.1 (2025-09-02) to v0.4.15 (2026-08-23), 16 of them since v0.4 (2026-02-15) | GitHub releases API |
| Commits on `main` | 313 since 2026-03-31, 132 since 2026-06-29, 11 since 2026-08-28 (docs and sponsor changes only) | GitHub commits API |
| Contributors | 31 listed. The maintainer, `D4Vinci`, has 1,548 commits. The next contributor has 15. | GitHub contributors API |
| Issues and pull requests | 1 open issue and 1 open pull request. Since 2026-06-29, 37 issues closed and 35 pull requests merged. 164 issues all time. | GitHub search API |
| Adoption | 84,048 stars, 8,596 forks | GitHub repository API |
| Security advisories | None published | GitHub security advisories API |
| Sponsors | Mostly residential, mobile, and datacenter proxy vendors, plus a vendor of anti-bot bypass tokens and a proxy vendor that advertises automatic CAPTCHA solving | `README.md` lines 94-259 |

All GitHub API figures were read on 2026-09-27. The project is active and popular. It is also a beta project with one dominant maintainer, and it ships breaking changes in patch releases. For example, v0.4.15 renamed the MCP `get` tool to `make_request`. If Argus uses any part of it, pin the exact version.

### Parser and adaptive element relocation

`scrapling.parser.Selector` wraps an `lxml` tree built from HTML passed as `str` or `bytes` (`scrapling/parser.py:77-194`). It supports CSS selectors with Scrapy-style `::text` and `::attr()` pseudo-elements, XPath, BeautifulSoup-style `find_all`, text and regex search, DOM navigation, and selector generation. `find_similar` returns elements that share an example element's depth, tag, parent tag, and grandparent tag, then filters them by attribute similarity. That fits repeated rows such as transactions (`scrapling/parser.py:1030-1090`). `Selectors` is the list type (`scrapling/parser.py:1217`).

Adaptive relocation works in two phases (`docs/parsing/adaptive.md` lines 104-130):

1. Save. On a `Selector` built with `adaptive=True`, a selection called with `auto_save=True` stores a fingerprint of the first matched element. The fingerprint holds the tag, attributes, own text, DOM path, parent tag, parent attributes, parent text, and sibling and child tag names (`scrapling/core/utils/_utils.py:84-109`).
2. Match. When that selector or `identifier` later matches nothing and the call passes `adaptive=True`, Scrapling scores every element on the page against the stored fingerprint with `difflib.SequenceMatcher` ratios. It returns the top scorers if they reach `percentage`, which defaults to 40 (`scrapling/parser.py:530-577` and `:822-887`).

Storage is pluggable through `StorageSystemMixin`. The default `SQLiteStorageSystem` writes `elements_storage.db` inside the installed package directory and keys rows only by the site's registered domain and the identifier (`scrapling/parser.py:47`; `scrapling/core/storage.py:73-145`).

Two properties matter for money data. Relocation runs only when the selector finds nothing, so a redesign that makes the old selector hit a different element returns that element with no signal. A successful relocation logs only at debug level, and a warning appears only when no element clears the threshold (`scrapling/parser.py:560-576`).

### Fetchers

The fetchers need the `fetchers` extra, which pulls in `curl_cffi`, `playwright`, `patchright`, `browserforge`, `apify-fingerprint-datapoints`, `msgspec`, `anyio`, `protego`, and `click` (PyPI `requires_dist`). They also need `scrapling install`, which downloads Chromium, runs Playwright's system-dependency installer, and refreshes the public suffix list (`scrapling/cli.py:110-142`).

- **Plain HTTP.** `Fetcher` and `AsyncFetcher` use `curl_cffi`. By default, `impersonate="chrome"` copies Chrome's TLS and HTTP/2 fingerprint, and `stealthy_headers=True` adds generated browser headers and a Google referer. A request gets up to 3 attempts on connection errors. HTTP/3 and a `ProxyRotator` are optional (`scrapling/engines/static.py:36-47`, `:70-92`, `:168-192`, `:224-274`).
- **Playwright-based dynamic fetcher.** `DynamicFetcher` drives Playwright's Chromium, an installed Chrome (`real_chrome`), or a running browser over CDP (`cdp_url`). Options include `page_action` callbacks, selector and network-idle waits, domain and ad blocking, `capture_xhr` to collect the page's XHR and fetch responses, and `user_data_dir` persistence. It sets a Google referer by default through `google_search=True` (`scrapling/engines/_browsers/_validators.py:70`; `scrapling/engines/_browsers/_controllers.py:130-131`).
- **Stealth browser.** `StealthyFetcher` runs Chromium through `patchright`, a patched Playwright (`scrapling/engines/_browsers/_stealth.py:8-9`). It replaced Camoufox in v0.3.13 on 2026-01-01 (`CHANGELOG.md` lines 566-570). It adds `solve_cloudflare`, `hide_canvas`, `block_webrtc`, and `allow_webgl` to the dynamic options (`docs/fetching/stealthy.md` lines 26-35 and 85).

### Sessions

`FetcherSession` keeps one `curl_cffi` session with its cookies and impersonation settings. `DynamicSession`, `StealthySession`, and their async versions keep one browser open across requests. Since v0.4.15 they also keep tabs open and reuse them from a pool sized by `max_pages` (v0.4.15 release notes). A `user_data_dir` switches a browser session to Playwright's `launch_persistent_context`, which keeps cookies and local storage on disk (`scrapling/engines/_browsers/_controllers.py:86-88`).

### Spiders

Spiders arrived in v0.4 on 2026-02-15. `scrapling.spiders.Spider` is an async, Scrapy-like crawler with `start_urls`, async `parse` callbacks, `Request` objects, several sessions per spider, 4 concurrent requests by default, per-domain limits, download delay, AutoThrottle, a development-mode response cache, checkpoint pause and resume through `crawldir`, streaming, and link extraction. Templates cover rule-based crawls, sitemaps, XML and CSV feeds, Shopify stores, and whole-site Markdown export (`README.md` lines 271-283 and 305).

Two defaults matter. The spider checks robots.txt with Protego only when it sets `robots_txt_obey = True`, and the default is `False` (`scrapling/spiders/spider.py:76`). Responses with status 401, 403, 407, 429, 444, 500, 502, 503, or 504 count as blocked and are retried up to 3 times. Each retry drops the request's proxy so that the rotator assigns a new one (`scrapling/spiders/spider.py:16`, `:86`, `:204-212`; `scrapling/spiders/engine.py:247-265`; `docs/spiders/proxy-blocking.md` lines 138-151). When AutoThrottle is on, it doubles a domain's delay after a blocked or non-2xx response (`docs/spiders/advanced.md` line 74).

### MCP server

The MCP server arrived in v0.3 on 2025-09-01, and v0.4.15 reworked it with breaking changes. `scrapling mcp` serves 13 tools over stdio by default: `open_session`, `open_request_session`, `close_session`, `list_sessions`, `make_request`, `bulk_get`, `fetch`, `bulk_fetch`, `stealthy_fetch`, `bulk_stealthy_fetch`, `session_fetch`, `session_make_request`, and `screenshot` (`scrapling/core/ai.py:1069-1188`). The `open_session` docstring presents the `stealthy` session type as the option that spoofs fingerprints to get past anti-bot systems (`scrapling/core/ai.py:259`). With `--http`, the server requires a bearer token by default, and the docs state that one shared token serves every client (`docs/ai/mcp-server.md` line 277). Returned pages can be narrowed with a CSS selector, and the server strips hidden content that could carry prompt injections (`docs/ai/mcp-server.md` lines 428-432).

### CLI

The CLI needs an extra because it imports `click` (`scrapling/cli.py:13-19`). It has four commands:

- `scrapling install` sets up Chromium and its system dependencies.
- `scrapling shell` opens an IPython console with fetch shortcuts and curl-command conversion.
- `scrapling extract get|post|put|delete|fetch|stealthy-fetch` saves a page as HTML, Markdown, or text. `stealthy-fetch` takes `--solve-cloudflare`, `--block-webrtc`, and `--hide-canvas` (`scrapling/cli.py:627-647`).
- `scrapling mcp` starts the MCP server.

### Features that exist to evade anti-bot defenses

These are findings. This unit does not evaluate how well any of them works.

1. TLS and HTTP/2 fingerprint impersonation in `Fetcher`, on by default as Chrome, with a random pick when given a list of browsers (`scrapling/engines/static.py:36-47`, `:73`).
2. Generated browser headers and a `https://www.google.com/` referer in `Fetcher`, on by default (`scrapling/engines/static.py:74`, `:168-192`; `scrapling/engines/toolbelt/fingerprints.py:66-93`). With stealth headers off, the default User-Agent is still a generated browser string (`scrapling/engines/static.py:187-189`; `scrapling/engines/toolbelt/fingerprints.py:93`).
3. A Google referer on browser navigation, on by default (`scrapling/engines/_browsers/_validators.py:70`).
4. In both browser fetchers, removal of Chromium's `--enable-automation` flag, and a dark color scheme that a code comment ties to a check in the creepjs fingerprinting test (`scrapling/engines/constants.py:15-22`; `scrapling/engines/_browsers/_base.py:443-447`).
5. `patchright` in `StealthyFetcher`, plus launch flags that include `--disable-blink-features=AutomationControlled` and `--start-maximized`, which a code comment labels a headless-check bypass (`scrapling/engines/constants.py:39-97`).
6. Canvas noise (`hide_canvas`), WebRTC leak blocking (`block_webrtc`), and WebGL left on because WAFs check it (`scrapling/engines/_browsers/_base.py:559-577`; `scrapling/fetchers/stealth_chrome.py` docstring).
7. Browser-wide locale flags so that workers and headers agree, which a code comment ties to Cloudflare's mismatch check (`scrapling/engines/_browsers/_base.py:491-500`).
8. A Cloudflare Turnstile and interstitial solver, `solve_cloudflare`, which detects the challenge and clicks it at a randomized position after a randomized delay (`scrapling/engines/_browsers/_stealth.py:108-193` and `:393-480`). The docs say it also handles custom pages with embedded CAPTCHAs (`docs/fetching/stealthy.md` line 118). This is CAPTCHA solving.
9. `ProxyRotator`, with cyclic or custom strategies for every session type, and spider retries that switch proxy after a block (`scrapling/engines/toolbelt/proxy_rotation.py:39-88`; `scrapling/spiders/engine.py:254-255`). This is proxy rotation to evade restrictions.
10. DNS-over-HTTPS through Cloudflare, documented as preventing DNS leaks when using proxies (`scrapling/engines/_browsers/_base.py:485`; `README.md` line 292).
11. Real Chrome, remote or managed browsers over CDP, and custom Chromium builds (`README.md` line 293).
12. MCP tools that give the stealth fetchers and the Cloudflare solver to any connected AI agent (`scrapling/core/ai.py:734-916` and `:1151-1163`).

The stealth path also has security-relevant defaults that are not evasion by themselves. Its browser context sets `ignore_https_errors=True`, so it accepts invalid TLS certificates (`scrapling/engines/_browsers/_base.py:551`). Playwright's own default is false. Its launch flags include `--disable-cookie-encryption` and `--use-mock-keychain`, and the shared defaults include `--password-store=basic` (`scrapling/engines/constants.py:32`, `:50`, `:71`). Chromium's switch list describes these as controlling profile cookie encryption, a test keychain, and the password storage backend. A persistent `user_data_dir` under these flags would hold session cookies with less protection than a normal browser profile.

## 2. The parser works standalone

Yes. The module is `scrapling/parser.py` and the class is `Selector` (`scrapling/parser.py:77`). `scrapling.Selector` resolves lazily to the same class (`scrapling/__init__.py`).

The evidence comes from source:

1. The constructor takes `content` as `str` or `bytes`, plus `url=""`, `encoding="utf-8"`, `huge_tree=True`, `keep_comments=False`, `keep_cdata=False`, `adaptive=False`, `storage`, and `storage_args` (`scrapling/parser.py:93-106`). It parses with `lxml.html.HTMLParser(recover=True, ...)` and `lxml.etree.fromstring` (`scrapling/parser.py:155-166`). It has no file-path argument, so the caller reads the file and passes bytes or text.
2. The import closure, computed by the appendix A script, is eight Scrapling modules, including `scrapling.parser` itself, plus `lxml`, `cssselect`, `orjson`, `w3lib`, and `typing_extensions`. The only import inside a function is `tld`, in the adaptive storage's domain lookup (`scrapling/core/storage.py:24-40`). No `curl_cffi`, `playwright`, `patchright`, or `browserforge` import is reachable. `scrapling/__init__.py` resolves names lazily, and `scrapling/core/__init__.py` is empty.
3. `pip install scrapling` installs only the parser dependencies. The README says that importing fetchers or spiders after that install raises `ModuleNotFoundError` (`README.md` lines 539-548).
4. The parse path makes no network calls. `url` only sets lxml's `base_url` and the adaptive storage key. With `adaptive=True` and a `url`, `tld` reads the public suffix file bundled with it, and `tld` downloads the list only when that file is missing (tld 0.13.2, commit `f5d3ccf2`, `src/tld/utils.py` lines 177-245).
5. With the default `adaptive=False`, the parser writes nothing to disk. With `adaptive=True`, the constructor opens or creates `elements_storage.db` in the package directory unless `storage_args` names another file (`scrapling/parser.py:47` and `:176-194`).
6. The project's own tests build `Selector` from inline HTML strings (`tests/parser/test_general.py:83`; `tests/parser/test_adaptive.py:46-47`).

Nothing here was executed, because the task forbids installs. The claim rests on source reading and the appendix A script.

A saved statement page would load like this:

```python
from pathlib import Path

from scrapling.parser import Selector

page = Selector(Path("estado-de-cuenta.html").read_bytes(), encoding="windows-1252")
rows = page.css("table tr")
```

Three details matter for Argus:

- `Selector` passes `encoding` to lxml's `HTMLParser`, and lxml documents that option as overriding the document's declared encoding. Bytes from a Windows-1252 page decode wrongly unless the caller passes the right encoding. BeautifulSoup instead detects the encoding with its Unicode, Dammit component.
- Keep `adaptive` off for user financial pages. The stored fingerprint includes element text and parent text, so balances and descriptions would land in the SQLite file. The table keys rows by domain and identifier and writes with `INSERT OR REPLACE`, so on a multi-user server every user of one bank reads and overwrites the same rows (`scrapling/core/storage.py:95-145`).
- If Argus ever used relocation, it would have to record each time relocation fires and fail closed on money fields, because an element can clear the 40 percent threshold and still be the wrong one.

## 3. Comparison with simpler tools

Scrapling reads none of the statement file formats. Its own `CSVFeedSpider` passes fetched text to the standard library's `csv.DictReader` (`scrapling/spiders/templates/feed.py:106-130`). The same standard library module is the right tool for an uploaded CSV file.

The simpler tools are listed below, with versions and licenses read from PyPI on 2026-09-27.

- **CSV.** The standard library `csv` module, with `csv.Sniffer` to detect the dialect. Parse amounts with `decimal.Decimal`.
- **Excel.** `openpyxl` 3.1.5 (MIT, 2024-06-28) reads `.xlsx` and `.xlsm`. `xlrd` 2.0.2 (BSD, 2025-06-14) reads only legacy `.xls`. `python-calamine` 0.8.2 (MIT, 2026-07-13) reads both.
- **OFX and QFX.** `ofxtools` 1.1.1 (GPL-3.0-only, 2026-06-12) is maintained. `ofxparse` 0.21 (MIT) has had no release since 2021-05-31.
- **PDF.** `pdfplumber` 0.11.10 (MIT, 2026-06-15) is built on `pdfminer.six` and extracts characters, lines, and tables. Its README says it works best on machine-generated PDFs, not scans. Poppler's `pdftotext` is a fast text option, and the Python binding `pdftotext` 4.0.0 (MIT, 2026-06-26) needs the Poppler system library. Scanned statements need OCR, and none of these tools performs it.
- **Saved HTML.** `lxml` 6.1.3 (BSD-3-Clause, 2026-09-02) or BeautifulSoup 4.15.0 (MIT, 2026-06-07). The standard library `html.parser` works with no dependencies.
- **Forwarded e-statements.** The standard library `email` package extracts the HTML body or the PDF attachment, and the tools above parse it.

**Browser automation with the user present.** Where Playwright runs decides the risk. On the user's own device, the user logs in and completes MFA, and the script reads the page or clicks the bank's own export button, so Argus never sees the password. On Argus servers with a streamed browser, the user types credentials into a browser that Argus controls. That setup is server-side credential handling, with every obligation in section 4. Playwright 1.63.0 (Apache-2.0, 2026-09-15) covers headed mode and persistent contexts directly, and its authentication docs warn that a saved browser state file can be used to impersonate the user. Scrapling's `DynamicFetcher` adds a Google referer and removes the automation flag by default, so Argus would have to turn both off. `StealthyFetcher` is out of bounds. Scrapling is a Python library, so it cannot run inside a browser extension. Attaching it to the user's everyday Chrome through `cdp_url` needs a remote-debugging port, and Chrome 136 and later ignore that port on the default profile because attackers used it to extract cookies (Chrome for Developers blog, 2025-03-17).

**Aggregator APIs.** An aggregator returns JSON over HTTPS, which the vendor SDK or any HTTP client reads. Scrapling adds nothing. Which aggregators cover Dominican banks is outside this unit.

| Input or task | Simplest adequate tool | Scrapling adds | Risk or boundary |
| --- | --- | --- | --- |
| CSV statement | Standard library `csv` with `Sniffer`; amounts as `Decimal` | Nothing. `CSVFeedSpider` wraps `csv.DictReader` for feeds fetched over HTTP. | Delimiter, decimal comma, date order, and encoding vary by bank. |
| Excel statement | `openpyxl` for `.xlsx`; `xlrd` 2.x or `python-calamine` for `.xls` | Nothing | Merged header cells, dates as text or Excel serial numbers, and formula cells whose cached values must be read. |
| OFX or QFX | `ofxtools`, or `ofxparse` | Nothing | OFX 1.x SGML versus 2.x XML. `ofxtools` is GPL-3.0-only and `ofxparse` is unmaintained. Deduplicate on `FITID`. |
| PDF statement | `pdfplumber`, or Poppler `pdftotext -layout` | Nothing. Scrapling has no PDF support. | Scans need OCR. Layouts change between template versions. Files may be encrypted. |
| Saved HTML page | `lxml.html` or BeautifulSoup; `html.parser` with no dependencies | One object with CSS and XPath, `::text`, `find_similar` for repeated rows, regex text helpers, adaptive relocation | Bytes decode as UTF-8 unless `encoding` is passed. Adaptive mode stores element text in shared rows and can relocate silently to a wrong element. Saved pages can hold session tokens and other accounts, so strip them. |
| Forwarded e-statement | Standard library `email`, then the HTML or PDF tools | The same parser as the saved-page row | An inline forward is a new message from the user, so the bank's DKIM signature does not carry over. |
| Public product and rate pages | An HTTP client with an honest User-Agent, `lxml`, and `urllib.robotparser` | Spiders, Protego robots.txt support, AutoThrottle, caching, pause and resume, Markdown export (`rag` extra) | Defaults conflict with Argus bounds: Chrome impersonation, generated headers, Google referer, robots.txt off, and proxy switching after blocks. Needs a pinned configuration and review. |
| JavaScript-rendered public pages | Playwright | Session wrappers, tab reuse, `capture_xhr` | Google referer and a removed automation flag by default. |
| Extraction in the user's authenticated session | A browser extension that reads the page, or headed Playwright on the user's device with the user logging in | The parser only | Needs consent per capture. Only the needed fields should leave the page, and no credentials should be stored. Bank terms apply. Since Chrome 136, CDP attach to the default Chrome profile is refused. |
| Server-side credential aggregation | A contracted aggregator or bank API where one covers the bank; otherwise, do not build it | Stealth browser, Cloudflare solver, fingerprint spoofing, proxy rotation | Out of bounds for Argus. Provides none of the section 4 platform needs. |
| Aggregator API | The vendor SDK or any HTTPS client | Nothing | Coverage, price, and contract terms, outside this unit. |
| Web access for Argus's model | Not needed for bank data | 13 MCP tools, including `stealthy_fetch` | Hands evasion tools to an agent. Out of bounds. |

## 4. What an aggregation platform needs that a scraping library does not provide

Scrapling fetches pages and parses HTML. Each item below is work outside that scope.

1. **Authentication and MFA orchestration.** A platform runs a state machine per connection. It submits credentials, detects the challenge type, relays the challenge to the user, waits inside the bank's expiry window, resumes the same bank session, and handles later password changes. Belvo returns HTTP 428 `token_required` with a session ID and an expiry, and its docs note that codes can last 30 to 60 seconds depending on the institution. Plaid raises `ITEM_LOGIN_REQUIRED` when a password changes or consent lapses, and it sends the user through Link update mode. Scrapling has `page_action` callbacks and a form-login spider example (`docs/spiders/advanced.md` lines 308-316), and nothing for challenge relay or expiry.
2. **Consent capture and revocation.** The platform records which accounts, which data, for how long, and when the user agreed. It shows that record, lets the user revoke it, stops access and deletes data on revocation, and keeps an audit trail. Scrapling has no concept of a user.
3. **Credential and session vaulting and isolation.** Credentials and session state need encryption at rest with managed keys, per-user isolation, exclusion from logs, and expiry. Scrapling persists browser state as a plain directory. Its stealth flags turn off cookie encryption, its stealth context accepts invalid TLS certificates, its adaptive storage has no tenant key, and its MCP HTTP transport uses one shared token.
4. **Per-institution adapters and breakage monitoring.** Each bank needs its own login flow, navigation, parser, and field mapping. The platform also needs synthetic checks, success rates per bank, and alerts when a layout changes. Adaptive relocation works against this goal, because it hides layout drift instead of reporting it.
5. **Normalization.** One schema has to cover every bank: account types, DOP and USD amounts, debit and credit signs, `DD/MM/YYYY` dates, decimal separators, time zone, and merchant text. Scrapling returns strings.
6. **Deduplication and reconciliation.** The platform assigns stable transaction IDs, from OFX `FITID` when present and from a documented hash otherwise. It merges overlapping statement periods, separates pending from posted, and checks that transactions add up to the statement's opening and closing balances. Scrapling's request fingerprints deduplicate URLs, not transactions.
7. **Rate limits and bank relationships.** Refresh schedules have to fit what each bank tolerates, and negotiated access means the bank expects the traffic. Scrapling's crawl features aim to keep going when a site pushes back, through blocked-request retries and proxy switching. AutoThrottle does slow down after blocks.
8. **Incident response.** The platform detects credential misuse, disables a connector per bank, notifies users and regulators when the law requires it, and keeps forensic logs. Scrapling writes log lines.
9. **Legal agreements.** The platform needs user terms and a privacy notice, data-processing agreements with vendors, bank data-access agreements, and a reading of each bank's terms on credential sharing and automated access. Scrapling's README disclaimer puts compliance with law, site terms, and robots.txt on the user (`README.md` lines 604-607).
10. **User support.** Staff and flows explain failures in plain terms, run reconnection, handle disputes about wrong numbers, and process deletion requests.

## 5. Where Scrapling is relevant

Scrapling is relevant in two narrow cases:

- **Parsing HTML that Argus already holds with the user's consent.** This covers a page the user saved, the HTML body of a forwarded e-statement, or HTML that an extension captured. `scrapling.parser.Selector` works offline for this. It is optional, because `lxml` and BeautifulSoup do the same job. If Argus uses it, pin the version, leave `adaptive` off, pass the encoding, and validate every amount.
- **Crawling public product, rate, and fee pages for discovery where terms and robots.txt allow.** Scrapling spiders can do this only with `robots_txt_obey = True`, `max_blocked_retries = 0` so that a block stops the request, a User-Agent header that names Argus, `impersonate=None` and `stealthy_headers=False` on HTTP sessions, `google_search=False` on any browser session, no proxy rotator, and no `StealthyFetcher`. For a small set of pages, an HTTP client plus `lxml` is simpler to audit.

Scrapling is not relevant to these inputs and tasks:

- **CSV, Excel, OFX, and PDF statements.** Scrapling has no reader for any of them.
- **User-present browser automation.** Plain Playwright or a browser extension does this, and Scrapling's browser wrappers add evasion defaults.
- **Server-side credential aggregation.** What sets Scrapling apart on protected sites is the out-of-bounds feature set, and it supplies none of the platform work in section 4.
- **Aggregator integrations.** These are JSON over HTTPS.
- **The MCP server and the CLI.** Neither touches a bank-data path, and the MCP server would give Argus's model evasion tools.

## Sources

All sources were read on 2026-09-27.

Scrapling:

- Repository, releases, commits, contributors, issues, and advisories, through the GitHub REST API: https://github.com/D4Vinci/Scrapling
- Source at v0.4.15: https://github.com/D4Vinci/Scrapling/tree/333fa22b7a5821194ce66b59b11f4b16a6484f02
- Parser: https://github.com/D4Vinci/Scrapling/blob/333fa22b7a5821194ce66b59b11f4b16a6484f02/scrapling/parser.py
- Adaptive storage: https://github.com/D4Vinci/Scrapling/blob/333fa22b7a5821194ce66b59b11f4b16a6484f02/scrapling/core/storage.py
- HTTP engine: https://github.com/D4Vinci/Scrapling/blob/333fa22b7a5821194ce66b59b11f4b16a6484f02/scrapling/engines/static.py
- Browser launch flags: https://github.com/D4Vinci/Scrapling/blob/333fa22b7a5821194ce66b59b11f4b16a6484f02/scrapling/engines/constants.py
- Browser session base: https://github.com/D4Vinci/Scrapling/blob/333fa22b7a5821194ce66b59b11f4b16a6484f02/scrapling/engines/_browsers/_base.py
- Stealth session and Cloudflare solver: https://github.com/D4Vinci/Scrapling/blob/333fa22b7a5821194ce66b59b11f4b16a6484f02/scrapling/engines/_browsers/_stealth.py
- Spider and engine: https://github.com/D4Vinci/Scrapling/blob/333fa22b7a5821194ce66b59b11f4b16a6484f02/scrapling/spiders/spider.py and https://github.com/D4Vinci/Scrapling/blob/333fa22b7a5821194ce66b59b11f4b16a6484f02/scrapling/spiders/engine.py
- MCP server: https://github.com/D4Vinci/Scrapling/blob/333fa22b7a5821194ce66b59b11f4b16a6484f02/scrapling/core/ai.py
- CLI: https://github.com/D4Vinci/Scrapling/blob/333fa22b7a5821194ce66b59b11f4b16a6484f02/scrapling/cli.py
- README, docs, and CHANGELOG at `main`: https://github.com/D4Vinci/Scrapling/tree/e0d4d7563207b70c2cb38487c4e0dcbe0e2f04ca
- Docs site: https://scrapling.readthedocs.io/en/latest/
- Release notes: https://github.com/D4Vinci/Scrapling/releases/tag/v0.4.15, https://github.com/D4Vinci/Scrapling/releases/tag/v0.4, and https://github.com/D4Vinci/Scrapling/releases/tag/v0.3
- PyPI: https://pypi.org/project/scrapling/0.4.15/

Parser dependencies and simpler tools:

- tld 0.13.2: https://github.com/barseghyanartur/tld/blob/f5d3ccf2220116948f367502a5cd3a8d525efe96/src/tld/utils.py
- lxml parser options: https://lxml.de/parsing.html
- BeautifulSoup encodings: https://www.crummy.com/software/BeautifulSoup/bs4/doc/
- Python `csv`: https://docs.python.org/3/library/csv.html
- Python `html.parser`: https://docs.python.org/3/library/html.parser.html
- Python `email`: https://docs.python.org/3/library/email.html
- openpyxl: https://openpyxl.readthedocs.io/en/stable/ and https://pypi.org/project/openpyxl/
- xlrd: https://pypi.org/project/xlrd/
- python-calamine: https://pypi.org/project/python-calamine/
- ofxtools: https://ofxtools.readthedocs.io/en/latest/ and https://pypi.org/project/ofxtools/
- ofxparse: https://pypi.org/project/ofxparse/
- pdfplumber: https://github.com/jsvine/pdfplumber and https://pypi.org/project/pdfplumber/
- pdftotext: https://pypi.org/project/pdftotext/
- Poppler: https://poppler.freedesktop.org/

Browsers and aggregators:

- Playwright authentication: https://playwright.dev/python/docs/auth
- Playwright `BrowserType.launch_persistent_context`: https://playwright.dev/python/docs/api/class-browsertype
- Playwright `Browser.new_context` and `ignore_https_errors`: https://playwright.dev/python/docs/api/class-browser
- Chrome remote-debugging change, 2025-03-17: https://developer.chrome.com/blog/remote-debugging-port
- Chromium command-line switches: https://peter.sh/experiments/chromium-command-line-switches/
- Plaid Item errors: https://plaid.com/docs/errors/item/
- Belvo MFA handling: https://developers.belvo.com/docs/handling-2-factor-authentication

## Appendix A. Parser import check

This script reads Scrapling's source at the pinned commit from GitHub and walks the imports of `scrapling.parser`. It needs Python 3.10 or later and network access to `raw.githubusercontent.com`. It installs nothing and writes nothing.

```python
import ast
import sys
import urllib.request

BASE = "https://raw.githubusercontent.com/D4Vinci/Scrapling/333fa22b7a5821194ce66b59b11f4b16a6484f02/"

def fetch(module):
    path = module.replace(".", "/")
    for candidate in (path + ".py", path + "/__init__.py"):
        try:
            return candidate, urllib.request.urlopen(BASE + candidate).read().decode()
        except OSError:
            continue
    raise SystemExit(f"not found: {module}")

seen, eager, nested = set(), set(), set()
queue = ["scrapling.parser"]
while queue:
    module = queue.pop()
    if module in seen:
        continue
    seen.add(module)
    path, code = fetch(module)
    tree = ast.parse(code)
    package = module if path.endswith("__init__.py") else module.rpartition(".")[0]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                parts = package.split(".")[: len(package.split(".")) - node.level + 1]
                base = ".".join(parts + ([base] if base else []))
            names = [base]
        else:
            continue
        for name in names:
            top_level = node in tree.body
            if top_level and name.startswith("scrapling"):
                queue.append(name)
            elif top_level:
                eager.add(name.split(".")[0])
            else:
                nested.add(name if name.startswith("scrapling") else name.split(".")[0])

stdlib = set(sys.stdlib_module_names)
print("modules:", sorted(seen))
print("third-party at import time:", sorted(eager - stdlib))
print("imports inside functions or blocks:", sorted(nested - stdlib))
```

Output on 2026-09-27:

```text
modules: ['scrapling.core._types', 'scrapling.core.custom_types', 'scrapling.core.mixins', 'scrapling.core.storage', 'scrapling.core.translator', 'scrapling.core.utils', 'scrapling.core.utils._utils', 'scrapling.parser']
third-party at import time: ['cssselect', 'lxml', 'orjson', 'typing_extensions', 'w3lib']
imports inside functions or blocks: ['tld']
```
