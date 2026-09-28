"""Offline checks that no caller input bypasses the fetch policy and no seller data reaches disk.

Runs the real fetcher against a fake network in a temporary study directory,
then reads every file it wrote raw, entity-decoded, and with tags removed. Uses
only the standard library and sends no request. Run it with
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
from offline import FakeOpener, leaks_in_directory  # noqa: E402

CARS = "https://m.supercarros.com"
HOMES = "https://m.supercasas.com"
HTML = {"Content-Type": "text/html; charset=utf-8", "Server": "cloudflare"}
ROBOTS = (
    b"# questions: webmaster@example.invalid\n"
    b"User-agent: *\nDisallow: /buscar/\nDisallow: /carros/\nDisallow: /Motos/\n\n"
    b"Sitemap: https://m.supercarros.com/sitemap.xml\n"
)
SELLER_SUBDOMAIN = (
    "https://vendedor-ficticio.supercarros.com/marca-ejemplo-modelo-x/0000009/"
)
TEN_DIGIT_ID = "1234567890"
TEN_DIGIT_BUILD = "2026092705"
SEARCH_URL = f"{CARS}/assets/js/searchvalues.js?{TEN_DIGIT_BUILD}"
KEPT_SITEMAP_ROWS = [
    f"<url><loc>{CARS}/marca-ejemplo-modelo-x/0000001/</loc>"
    "<lastmod>2026-09-20</lastmod></url>",
    f"<url><loc>{CARS}/marca-ejemplo-modelo-x/0000008/</loc></url>",
    f"<url><loc>{CARS}/marca-ejemplo-modelo-x/{TEN_DIGIT_ID}/</loc>"
    "<lastmod>2026-09-21</lastmod></url>",
]
SITEMAP = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    f"{KEPT_SITEMAP_ROWS[0]}\n"
    f"<url><loc>{CARS}/dealers/vendedor-ficticio/</loc></url>\n"
    f"<url><loc>{SELLER_SUBDOMAIN}</loc></url>\n"
    "<url><loc>https://vendedor-ficticio.example.invalid/marca-ejemplo-modelo-x/0000006/"
    "</loc></url>\n"
    f"<url><loc>{CARS}/marca-ejemplo-modelo-x/0000007/?ref=vendedor-ficticio</loc></url>\n"
    f"<url><loc>{CARS}/marca-ejemplo-modelo-x/0000008/</loc>"
    "<lastmod>Vendedor Ficticio</lastmod></url>\n"
    f"{KEPT_SITEMAP_ROWS[2]}\n"
    "</urlset>\n"
).encode()
KEPT_HOMES_SITEMAP_ROWS = [
    f"<url><loc>{HOMES}/apartamentos-sector-ejemplo/0000002/</loc></url>",
]
HOMES_SITEMAP = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    f"{KEPT_HOMES_SITEMAP_ROWS[0]}\n"
    f"<url><loc>{HOMES}/apartamentos-809-000-0000/0000003/</loc></url>\n"
    "</urlset>\n"
).encode()
SEARCH_BRANDS = b'var SearchBrands = ["27|Marca Ejemplo|1|16|0|0"];\n'
SEARCH_VALUES = SEARCH_BRANDS + b'var SearchDealers = ["41|Vendedor Ficticio"];\n'
DETAIL = (FIXTURES / "vehicle-detail.html").read_bytes()
PROPERTY = (FIXTURES / "property-detail.html").read_bytes()
SELLER_START = DETAIL.index(
    b'<h1 class="content-block">', DETAIL.index(b'<h1 class="content-block">') + 1
)
TITLE = b"2021 Marca Ejemplo Modelo X EX</h1>"
MOTOR = b"<br>4 cilindros</li>"


def edit(*changes):
    page = DETAIL
    for old, new in changes:
        if old not in page:
            raise ValueError(f"the vehicle fixture no longer holds {old!r}")
        page = page.replace(old, new, 1)
    return page


KEEPS_NOTHING = {
    "a page without a seller boundary": DETAIL[:SELLER_START] + b"</div></body></html>\n",
    "a phone number in the title": edit(
        (TITLE, b"2021 Marca Ejemplo Modelo X EX 809-000-0000</h1>")
    ),
    "a foreign phone number in a specification": edit(
        (MOTOR, b"<br>4 cilindros, llamar 305-555-0000</li>")
    ),
    "an entity-encoded email in the title": edit(
        (TITLE, b"2021 Marca Ejemplo Modelo X EX vendedor&#64;example.invalid</h1>")
    ),
    "a phone split by markup in the title": edit(
        (TITLE, b"2021 Marca Ejemplo Modelo X EX <span>305</span>-555-0000</h1>")
    ),
    "a phone split by markup in a specification": edit(
        (MOTOR, b"<br>4 cilindros, <span>305</span>-555-0000</li>")
    ),
    "a phone with entity-encoded digits in a feature": edit(
        (b"<li>Color Gris</li>", b"<li>Color Gris 8&#48;9-000-0000</li>")
    ),
    "a phone split across elements in an accessory": edit(
        (b"<li>Alarma</li>", b"<li>Alarma <b>809</b><i>000</i>0000</li>")
    ),
    "an entity-encoded phone in the meta description": edit(
        (b'0.00 Mi." />', b'0.00 Mi. Llamar 809&#45;000&#45;0000" />')
    ),
    "a WhatsApp link written with an entity in the price": edit(
        (
            b'<li class="notable">US$ 25,000</li>',
            b'<li class="notable">US$ 25,000 wa&period;me/18090000000</li>',
        )
    ),
    "a phone number read as a mileage in the ad text": edit(
        (b"con 40,000 km.", b"con 8095550000 km.")
    ),
}
TEN_DIGIT_DETAIL = edit(
    (b"var adId = '0000001';", f"var adId = '{TEN_DIGIT_ID}';".encode()),
    (b"<br>#0000001</li>", f"<br>#{TEN_DIGIT_ID}</li>".encode()),
)
SELLER_ATTRIBUTES = edit(
    (b"var adModel = 130;", b"var adModel = 'Vendedor-Ficticio';"),
    (b"<li>Gasolina</li>", b'<li data-seller="Vendedor Ficticio">Gasolina</li>'),
    (b"<li>Alarma</li>", b'<li><img src="https://img.example.invalid/1.jpg">Alarma</li>'),
)
CONTACT_ATTRIBUTES = edit(
    (
        b"<li>Gasolina</li>",
        b'<li title="809-000-0000" data-phone="8090000000">Gasolina</li>',
    ),
    (
        b"<li>Color Gris</li>",
        b'<li><a href="/Dealers/vendedor-ficticio/">Color Gris</a></li>',
    ),
)
SELLER_HEADERS = {
    "Content-Type": "text/html; name=vendedor@example.invalid",
    "Server": "Vendedor Ficticio 809-000-0000",
}
SELLER_REDIRECTS = (
    "/Dealers/Vendedor-Ficticio/",
    "/vendedores/vendedor-ficticio/",
    "/%44ealers/Vendedor-Ficticio/",
    "/contacto/vendedor%40example.invalid",
    "/%2544ealers/Vendedor-Ficticio/",
    "/contacto/vendedor%2540example.invalid",
    "/%252525252525252544ealers/Vendedor-Ficticio/",
)
LISTING_REDIRECT = "/apartamentos-sector-ejemplo/0000009/"


def listing(number):
    return f"{CARS}/marca-ejemplo-modelo-x/{number:07d}/"


def home(number):
    return f"{HOMES}/apartamentos-sector-ejemplo/{number:07d}/"


PAGES = {
    f"{CARS}/robots.txt": (200, ROBOTS, {"Content-Type": "text/plain"}),
    f"{CARS}/sitemap.xml": (200, SITEMAP, {"Content-Type": "text/xml"}),
    SEARCH_URL: (200, SEARCH_VALUES, {}),
    listing(1): (200, DETAIL, HTML),
    listing(int(TEN_DIGIT_ID)): (200, TEN_DIGIT_DETAIL, HTML),
    listing(2): (200, SELLER_ATTRIBUTES, HTML),
    listing(3): (200, CONTACT_ATTRIBUTES, SELLER_HEADERS),
    **{
        listing(10 + n): (200, page, HTML)
        for n, page in enumerate(KEEPS_NOTHING.values())
    },
    f"{HOMES}/robots.txt": (
        301,
        b"",
        {"Location": "https://www.supercasas.com/robots.txt"},
    ),
    "https://www.supercasas.com/robots.txt": (200, ROBOTS, {}),
    "https://www.supercasas.com/sitemap.xml": (200, HOMES_SITEMAP, {}),
    home(2): (200, PROPERTY, HTML),
    **{
        home(10 + n): (302, b"", {"Location": location})
        for n, location in enumerate(SELLER_REDIRECTS)
    },
    home(20): (301, b"", {"Location": LISTING_REDIRECT}),
}
PLANTED = ("305-555-0000", "8090000000")
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
    "robots.txt disallows the path": f"{CARS}/carros/0000009/",
    "a case variant of a disallowed path": f"{CARS}/CARROS/0000009/",
    "a percent-encoded disallowed path": f"{CARS}/%63arros/0000009/",
    "a double percent-encoded disallowed path": f"{CARS}/%2563arros/0000009/",
    "a semicolon path parameter": f"{CARS}/carros;jsessionid=x/0000009/",
    "a mixed-case robots rule": f"{CARS}/motos/0000009/",
    "an uppercase listing slug": f"{CARS}/Marca-Ejemplo-Modelo-X/0000001/",
    "a phone number in a listing slug": f"{CARS}/marca-ejemplo-809-000-0000/0000009/",
    "a seller-named subdomain": SELLER_SUBDOMAIN,
    "dot segments": f"{CARS}/robots.txt/../carros/0000009/",
    "percent-encoded dot segments": f"{CARS}/x/%2E%2E/carros/0000009/",
    "a backslash": f"{CARS}/x%5C..%5Ccarros/0000009/",
    "robots.txt with a query": f"{CARS}/robots.txt?next=/carros/0000009/",
    "a search values query that is not a build number": (
        f"{CARS}/assets/js/searchvalues.js?redirect=//evil.invalid/x"
    ),
    "plain http": "http://m.supercarros.com/marca-ejemplo-modelo-x/0000001/",
    "an explicit port": "https://m.supercarros.com:8443/marca-ejemplo-modelo-x/0000001/",
    "an explicit default port": "https://m.supercarros.com:443/marca-ejemplo-modelo-x/0000001/",
    "a malformed port": "https://m.supercarros.com:abc/marca-ejemplo-modelo-x/0000001/",
    "userinfo": "https://user@m.supercarros.com/marca-ejemplo-modelo-x/0000001/",
    "the home page": f"{CARS}/",
    "a dealer page": f"{CARS}/dealers/vendedor-ficticio/",
    "a search page": f"{CARS}/buscar/?q=1",
    "an unaudited host": "https://example.invalid/robots.txt",
}


def quiet():
    stack = contextlib.ExitStack()
    stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
    stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
    return stack


def refused(call):
    try:
        with quiet():
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
        check(retention.holds_contact(shape), f"the contact guard missed {shape}")
    for value in LISTING_VALUES:
        check(not retention.holds_contact(value), f"the contact guard flagged {value}")
    for url, kind in (
        (listing(int(TEN_DIGIT_ID)), "detail"),
        (SEARCH_URL, "search-values"),
    ):
        check(
            retention.page_kind(url) == ("supercarros", kind),
            f"a declared URL with a ten-digit token was refused: {url}",
        )
    check(
        retention.page_kind(SELLER_SUBDOMAIN) is None,
        "a seller-named subdomain was treated as an audited host",
    )
    with tempfile.TemporaryDirectory() as scratch:
        os.chdir(scratch)
        try:
            opener = FakeOpener(PAGES)
            fetch_ledger.OPENER, fetch_ledger.MIN_SPACING_S = opener, 0
            check(
                refused(lambda: fetch_ledger.fetch(listing(1))),
                "a detail page was fetched before robots.txt",
            )
            check(
                refused(
                    lambda: fetch_ledger.main(
                        [f"{CARS}/carros/0000009/", "--label", "robots"]
                    )
                ),
                "a caller label was accepted",
            )
            check(opener.calls == [], f"requests sent before robots.txt: {opener.calls}")
            with quiet():
                fetch_ledger.fetch(f"{CARS}/robots.txt")
            for reason, url in REFUSED_AFTER_ROBOTS.items():
                check(
                    refused(lambda url=url: fetch_ledger.fetch(url)),
                    f"not refused: {reason}",
                )
            check(
                opener.calls == [f"{CARS}/robots.txt"],
                f"a refused URL was requested: {opener.calls}",
            )
            for url in list(PAGES)[1:]:
                try:
                    with quiet():
                        fetch_ledger.fetch(url)
                except (SystemExit, Exception) as error:
                    failures.append(f"a valid request was not sent: {url}: {error}")
            check(
                opener.calls == list(PAGES), f"unexpected request order: {opener.calls}"
            )

            def kept(url):
                try:
                    body_path, meta_path = fetch_ledger.cache_paths(url)
                except SystemExit:
                    return None, {}
                if not meta_path.exists():
                    return None, {}
                meta = json.loads(meta_path.read_text())
                return (body_path.read_bytes() if body_path.exists() else None), meta

            def sitemap_rows(url):
                body, _ = kept(url)
                lines = (body or b"").decode().splitlines()
                return [line for line in lines if line.startswith("<url>")]

            body, _ = kept(f"{CARS}/robots.txt")
            check(
                body is not None and b"#" not in body and b"Disallow: /carros/" in body,
                "robots.txt was not reduced to its rules",
            )
            rows = sitemap_rows(f"{CARS}/sitemap.xml")
            check(rows == KEPT_SITEMAP_ROWS, f"the sitemap kept these rows: {rows}")
            rows = sitemap_rows("https://www.supercasas.com/sitemap.xml")
            check(
                rows == KEPT_HOMES_SITEMAP_ROWS,
                f"a sitemap with a contact detail in one row kept these rows: {rows}",
            )
            body, _ = kept(SEARCH_URL)
            check(body == SEARCH_BRANDS, f"the search values script kept {body!r}")
            body, meta = kept(listing(1))
            check(
                body is not None
                and b'<h1 class="content-block">2021 Marca Ejemplo Modelo X EX</h1>'
                in body
                and b"<li><label>Motor:</label><br>4 cilindros</li>" in body
                and b"Provincia Ficticia" in body,
                "the detail page was not kept as its projection",
            )
            check(
                meta.get("content_type") == "text/html; charset=utf-8"
                and meta.get("server") == "cloudflare",
                f"declared headers were not recorded: {meta}",
            )
            body, meta = kept(listing(int(TEN_DIGIT_ID)))
            check(
                body is not None
                and f"<li><label>Anuncio:</label><br>#{TEN_DIGIT_ID}</li>".encode()
                in body
                and f"var adId = '{TEN_DIGIT_ID}';".encode() in body,
                f"a detail page with a ten-digit listing ID was not kept: {meta.get('retention')}",
            )
            body, _ = kept(listing(2))
            check(
                body is not None
                and b"<li>Gasolina</li>" in body
                and b"<li>Alarma</li>" in body,
                "a page with seller attributes and an image was not kept as text",
            )
            body, meta = kept(listing(3))
            check(
                body is not None
                and b"<li>Gasolina</li>" in body
                and b"<li>Color Gris</li>" in body,
                "a page with contact attributes and a dealer link was not kept as text",
            )
            check(
                meta.get("content_type") == "undeclared"
                and meta.get("server") == "undeclared",
                f"undeclared headers were recorded: {meta}",
            )
            for n, reason in enumerate(KEEPS_NOTHING):
                body, meta = kept(listing(10 + n))
                note = meta.get("retention", "")
                check(
                    body is None and note.startswith("not kept"), f"kept {reason}: {note}"
                )
            _, meta = kept(f"{HOMES}/robots.txt")
            check(
                meta.get("location") == "https://www.supercasas.com/robots.txt",
                f"a declared robots.txt redirect was not recorded: {meta}",
            )
            body, meta = kept(home(2))
            check(
                body is not None and meta.get("retention") == "kept projection",
                "a page behind a declared robots.txt redirect was not kept",
            )
            for n, location in enumerate(SELLER_REDIRECTS):
                body, meta = kept(home(10 + n))
                check(
                    body is None
                    and meta.get("location") == "undeclared"
                    and meta.get("retention") == "not kept: status 302",
                    f"the redirect to {location} was recorded as {meta.get('location')}",
                )
            _, meta = kept(home(20))
            check(
                meta.get("location") == f"{HOMES}{LISTING_REDIRECT}",
                f"a redirect to a listing was not recorded: {meta.get('location')}",
            )
            planted = [*expected["seller_strings"], *PLANTED]
            allowed = (TEN_DIGIT_ID, TEN_DIGIT_BUILD)
            for path, found in leaks_in_directory(scratch, planted, allowed).items():
                failures.append(f"{path} holds {found}")
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
