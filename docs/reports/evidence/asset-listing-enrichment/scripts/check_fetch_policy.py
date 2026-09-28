"""Offline checks that no caller input bypasses the fetch policy and no seller data reaches disk.

Runs the real fetcher against a fake network in a temporary study directory.
Uses only the standard library and sends no request. Run it with
`python3 check_fetch_policy.py`.
"""

import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
FIXTURES = SCRIPTS.parent / "fixtures"
sys.path.insert(0, str(SCRIPTS))

import fetch_ledger  # noqa: E402
import retention  # noqa: E402

HOST = "https://m.supercarros.com"
ROBOTS = (
    b"# questions: webmaster@example.invalid\n"
    b"User-agent: *\nDisallow: /buscar/\nDisallow: /carros/\nDisallow: /Motos/\n\n"
    b"Sitemap: https://m.supercarros.com/sitemap.xml\n"
)
SITEMAP = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    f"<url><loc>{HOST}/marca-ejemplo-modelo-x/0000001/</loc><lastmod>2026-09-20</lastmod></url>\n"
    f"<url><loc>{HOST}/dealers/vendedor-ficticio/</loc><lastmod>2026-09-20</lastmod></url>\n"
    "</urlset>\n"
).encode()
SEARCH_VALUES = b'var SearchBrands = ["27|Marca Ejemplo|1|16|0|0"];\n'
DETAIL = (FIXTURES / "vehicle-detail.html").read_bytes()
SELLER_START = DETAIL.index(
    b'<h1 class="content-block">', DETAIL.index(b'<h1 class="content-block">') + 1
)
NO_SELLER_BOUNDARY = DETAIL[:SELLER_START] + b"</div></body></html>\n"
PHONE_IN_TITLE = DETAIL.replace(
    b"2021 Marca Ejemplo Modelo X EX</h1>",
    b"2021 Marca Ejemplo Modelo X EX 809-000-0000</h1>",
)
PHONE_IN_SPEC = DETAIL.replace(
    b"<br>4 cilindros</li>", b"<br>4 cilindros, llamar 305-555-0000</li>"
)
ENCODED_EMAIL_IN_TITLE = DETAIL.replace(
    b"2021 Marca Ejemplo Modelo X EX</h1>",
    b"2021 Marca Ejemplo Modelo X EX vendedor&#64;example.invalid</h1>",
)
MARKUP_SPLIT_PHONE = DETAIL.replace(
    b"2021 Marca Ejemplo Modelo X EX</h1>",
    b"2021 Marca Ejemplo Modelo X EX <span>305</span>-555-0000</h1>",
)
DEALER_REDIRECT = "/Dealers/Vendedor-Ficticio/"
SAFE_ROBOTS_REDIRECT = "https://m.supercarros.com/robots.txt"
PAGES = {
    f"{HOST}/robots.txt": ROBOTS,
    f"{HOST}/sitemap.xml": SITEMAP,
    f"{HOST}/assets/js/searchvalues.js?20260927053": SEARCH_VALUES,
    f"{HOST}/marca-ejemplo-modelo-x/0000001/": DETAIL,
    f"{HOST}/marca-ejemplo-modelo-x/0000002/": NO_SELLER_BOUNDARY,
    f"{HOST}/marca-ejemplo-modelo-x/0000003/": PHONE_IN_TITLE,
    f"{HOST}/marca-ejemplo-modelo-x/0000004/": PHONE_IN_SPEC,
    f"{HOST}/marca-ejemplo-modelo-x/0000005/": ENCODED_EMAIL_IN_TITLE,
    f"{HOST}/marca-ejemplo-modelo-x/0000006/": MARKUP_SPLIT_PHONE,
}
REDIRECTS = {
    f"{HOST}/marca-ejemplo-modelo-x/0000007/": (302, DEALER_REDIRECT, b""),
}
PHONE_SHAPES = (
    "8090000000",
    "(809) 000-0000",
    "+1 (829) 000 0000",
    "1-849-000-0000",
    "809.000.0000",
    "305-555-0000",
    "+52 55 0000 0000",
    "vendedor&#64;example.invalid",
    "<span>305</span>-555-0000",
)
LISTING_VALUES = (
    "US$ 43,900",
    "RD$ 1,695,000",
    "US$ 1,500/Mes",
    "#1632511",
    "var adPriceMainCurrency = '2638390.0000';",
    "var adKey = '639238608000000000';",
    "<lastmod>2026-09-20</lastmod>",
    "2026-09-28T21:32:19.123456+00:00",
)
REFUSED_AFTER_ROBOTS = {
    "robots.txt disallows the path": f"{HOST}/carros/0000009/",
    "a case variant of a disallowed path": f"{HOST}/CARROS/0000009/",
    "a percent-encoded disallowed path": f"{HOST}/%63arros/0000009/",
    "a double percent-encoded disallowed path": f"{HOST}/%2563arros/0000009/",
    "a semicolon path parameter": f"{HOST}/carros;jsessionid=x/0000009/",
    "a mixed-case robots rule": f"{HOST}/motos/0000009/",
    "an uppercase listing slug": f"{HOST}/Marca-Ejemplo-Modelo-X/0000001/",
    "dot segments": f"{HOST}/robots.txt/../carros/0000009/",
    "percent-encoded dot segments": f"{HOST}/x/%2E%2E/carros/0000009/",
    "a backslash": f"{HOST}/x%5C..%5Ccarros/0000009/",
    "robots.txt with a query": f"{HOST}/robots.txt?next=/carros/0000009/",
    "a search values query that is not a build number": (
        f"{HOST}/assets/js/searchvalues.js?redirect=//evil.invalid/x"
    ),
    "plain http": "http://m.supercarros.com/marca-ejemplo-modelo-x/0000001/",
    "an explicit port": "https://m.supercarros.com:8443/marca-ejemplo-modelo-x/0000001/",
    "an explicit default port": "https://m.supercarros.com:443/marca-ejemplo-modelo-x/0000001/",
    "a malformed port": "https://m.supercarros.com:abc/marca-ejemplo-modelo-x/0000001/",
    "userinfo": "https://user@m.supercarros.com/marca-ejemplo-modelo-x/0000001/",
    "the home page": f"{HOST}/",
    "a dealer page": f"{HOST}/dealers/vendedor-ficticio/",
    "a search page": f"{HOST}/buscar/?q=1",
    "an unaudited host": "https://example.invalid/robots.txt",
}


class FakeResponse:
    def __init__(self, status, body, headers=None):
        self.status, self.headers, self._body = status, headers or {}, body

    def read(self):
        return self._body


class FakeOpener:
    def __init__(self):
        self.calls = []

    def open(self, request, timeout):
        self.calls.append(request.full_url)
        if request.full_url in REDIRECTS:
            status, location, body = REDIRECTS[request.full_url]
            return FakeResponse(status, body, {"Location": location})
        if request.full_url not in PAGES:
            return FakeResponse(404, b"")
        return FakeResponse(200, PAGES[request.full_url])


def refused(call):
    try:
        with (
            contextlib.redirect_stderr(io.StringIO()),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            call()
    except SystemExit:
        return True
    except Exception:
        return False
    return False


def main():
    expected = json.loads((FIXTURES / "expected.json").read_text())
    failures = []

    def check(condition, message):
        if not condition:
            failures.append(message)

    previous = Path.cwd()
    os.chdir(SCRIPTS)
    check(refused(fetch_ledger.study_root), "the fetcher ran inside the repository")
    for shape in PHONE_SHAPES:
        check(
            retention.holds_contact(shape),
            f"the contact guard missed {shape}",
        )
    for value in LISTING_VALUES:
        check(
            not retention.holds_contact(value),
            f"the contact guard flagged {value}",
        )
    check(
        retention.sanitize_location(DEALER_REDIRECT) is None,
        "a dealer Location was allowed through sanitize_location",
    )
    check(
        retention.sanitize_location(SAFE_ROBOTS_REDIRECT) == SAFE_ROBOTS_REDIRECT,
        "a safe robots Location was dropped",
    )
    with tempfile.TemporaryDirectory() as scratch:
        os.chdir(scratch)
        try:
            opener = FakeOpener()
            fetch_ledger.OPENER, fetch_ledger.MIN_SPACING_S = opener, 0
            check(
                refused(
                    lambda: fetch_ledger.fetch(f"{HOST}/marca-ejemplo-modelo-x/0000001/")
                ),
                "a detail page was fetched before robots.txt",
            )
            check(
                refused(
                    lambda: fetch_ledger.main(
                        [f"{HOST}/carros/0000009/", "--label", "robots"]
                    )
                ),
                "a caller label was accepted",
            )
            check(opener.calls == [], f"requests sent before robots.txt: {opener.calls}")
            fetch_ledger.fetch(f"{HOST}/robots.txt")
            for reason, url in REFUSED_AFTER_ROBOTS.items():
                check(
                    refused(lambda url=url: fetch_ledger.fetch(url)),
                    f"not refused: {reason}",
                )
            check(
                opener.calls == [f"{HOST}/robots.txt"],
                f"a refused URL was requested: {opener.calls}",
            )
            for url in list(PAGES)[1:]:
                fetch_ledger.fetch(url)
            check(
                opener.calls == list(PAGES), f"unexpected request order: {opener.calls}"
            )

            def kept(url):
                body_path, meta_path = fetch_ledger.cache_paths(url)
                meta = json.loads(meta_path.read_text())
                return (body_path.read_bytes() if body_path.exists() else None), meta[
                    "retention"
                ]

            body, _ = kept(f"{HOST}/robots.txt")
            check(
                body == retention.robots_rules(ROBOTS),
                "robots.txt was not reduced to its rules",
            )
            body, _ = kept(f"{HOST}/sitemap.xml")
            check(
                body is not None and b"0000001" in body and b"dealers" not in body,
                "the sitemap kept more than listing URLs",
            )
            body, _ = kept(f"{HOST}/assets/js/searchvalues.js?20260927053")
            check(body == SEARCH_VALUES, "the search values script was not kept whole")
            body, _ = kept(f"{HOST}/marca-ejemplo-modelo-x/0000001/")
            check(
                body == retention.project_detail(DETAIL)
                and b"Provincia Ficticia" in body,
                "the detail page was not kept as its projection",
            )
            for url, reason in (
                (
                    f"{HOST}/marca-ejemplo-modelo-x/0000002/",
                    "a page without a seller boundary",
                ),
                (
                    f"{HOST}/marca-ejemplo-modelo-x/0000003/",
                    "a page with a phone in its title",
                ),
                (
                    f"{HOST}/marca-ejemplo-modelo-x/0000004/",
                    "a page with a foreign phone number in a specification",
                ),
                (
                    f"{HOST}/marca-ejemplo-modelo-x/0000005/",
                    "a page with an HTML-encoded email in its title",
                ),
                (
                    f"{HOST}/marca-ejemplo-modelo-x/0000006/",
                    "a page with a markup-split phone in its title",
                ),
            ):
                body, note = kept(url)
                check(
                    body is None and note.startswith("not kept"), f"kept {reason}: {note}"
                )
            redirect_url = f"{HOST}/marca-ejemplo-modelo-x/0000007/"
            redirect_meta = fetch_ledger.fetch(redirect_url)
            check(
                redirect_meta["status"] == 302
                and redirect_meta["location"] is None
                and redirect_meta["retention"].startswith("not kept"),
                "a dealer Location was persisted on a detail redirect",
            )
            _, redirect_disk = fetch_ledger.cache_paths(redirect_url)
            disk_meta = json.loads(redirect_disk.read_text())
            check(
                disk_meta["location"] is None
                and DEALER_REDIRECT not in redirect_disk.read_text()
                and DEALER_REDIRECT
                not in (Path(scratch) / "ledger.jsonl").read_text(),
                "a dealer Location reached the cache or ledger",
            )
            written = [path for path in Path(scratch).rglob("*") if path.is_file()]
            for path in written:
                text = path.read_text("utf-8", "replace")
                found = [value for value in expected["seller_strings"] if value in text]
                match = retention.CONTACT.search(retention.contact_surfaces(text))
                found += [match.group(0)] if match else []
                check(not found, f"{path.relative_to(scratch)} holds {found}")
        finally:
            os.chdir(previous)
    for failure in failures:
        print("FAIL", failure)
    print(
        "fetch policy:",
        "all checks pass" if not failures else f"{len(failures)} failures",
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
