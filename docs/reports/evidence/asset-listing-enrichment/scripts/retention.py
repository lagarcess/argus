"""Decide what the listing proof may request, record, or keep on disk.

`page_kind` is the one list of URLs the proof may request, record, or keep.
The fetcher holds each response in memory. It records response headers only in
the shapes `header_facts` declares, and writes a body only as the projection
`retain` returns. A projection writes decoded text into fixed markup. Of the
page's attributes it keeps only the meta description. `retain` keeps nothing
when the projection, or any text a reader could take from the page elements it
keeps, holds a contact detail.
"""

from __future__ import annotations

import html
import json
import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from common import JS_VAR, squash
from normalize import text_facts

SITES = {"supercarros": "supercarros.com", "supercasas": "supercasas.com"}
DETAIL_PATH = re.compile(r"/[a-z0-9,-]+/\d+/")
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
W3C_DATE = re.compile(
    r"\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?"
)
MEDIA_TYPE = re.compile(r"[a-z0-9.+-]+/[a-z0-9.+-]+(?:; ?charset=[a-z0-9_.-]+)?")
PRODUCT = re.compile(r"[a-z0-9._-]+(?:/[a-z0-9._-]+)?")
REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
HEADING = '<h1 class="content-block"'
LISTS = ("feature-list", "spec-list", "component-list")
VOID = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "source",
        "track",
        "wbr",
    }
)
LISTING_VARS = frozenset(
    {
        "adId",
        "adKey",
        "adIsNew",
        "adCarAge",
        "adPriceMainCurrency",
        "adBrand",
        "adModel",
        "adFuel",
        "adCategory",
        "adObjectType",
    }
)
SEARCH_VARS = ("SearchBrands",)
SELLER_KINDS = frozenset({"Vendedor", "Inmobiliaria", "Particular"})
PLACE = re.compile(r"[^\W\d_](?:[^\W\d_]|[ .'-]){1,39}")
CONTACT = re.compile(
    r"(?<!\d)\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)"
    r"|\+\d{1,3}[\s.-]?(?:\d[\s.-]?){7,12}\d"
    r"|[\w.+-]+@[\w-]+\.[A-Za-z]{2,}"
    r"|wa\.me/|tel:|mailto:|data-cfemail"
    r"|-?\d{1,3}\.\d{5,}\s*,\s*-?\d{1,3}\.\d{5,}"
    r"|/Dealers/[^\s\"'/]",
    re.I,
)


def holds_contact(text: str) -> bool:
    decoded = html.unescape(text)
    views = (
        text,
        decoded,
        re.sub(r"<[^>]*>", "", decoded),
        re.sub(r"<[^>]*>", " ", decoded),
    )
    return any(CONTACT.search(view) for view in views)


def page_kind(url: str) -> tuple[str, str] | None:
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return None
    host = (parts.hostname or "").lower()
    site = next(
        (
            key
            for key, domain in SITES.items()
            if host == domain or host.endswith("." + domain)
        ),
        None,
    )
    if (
        site is None
        or parts.scheme != "https"
        or parts.username
        or parts.password
        or port is not None
        or parts.fragment
        or holds_contact(url)
    ):
        return None
    path, query = parts.path, parts.query
    if path == "/robots.txt" and not query:
        return site, "robots"
    if path == "/sitemap.xml" and not query:
        return site, "sitemap"
    if path == "/assets/js/searchvalues.js" and re.fullmatch(r"\d*", query):
        return site, "search-values"
    if DETAIL_PATH.fullmatch(path) and not query:
        return site, "detail"
    return None


def declared(shape: re.Pattern[str], value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip().lower()
    return value if shape.fullmatch(value) and not holds_contact(value) else "undeclared"


def redirect_target(url: str, location: str) -> str:
    try:
        target = urljoin(url, location.strip())
    except ValueError:
        return "undeclared"
    return target if page_kind(target) else "undeclared"


def header_facts(url: str, headers) -> dict:
    get = headers.get if hasattr(headers, "get") else (lambda *_: None)
    location = get("Location")
    return {
        "content_type": declared(MEDIA_TYPE, get("Content-Type")),
        "server": declared(PRODUCT, get("Server")),
        "location": None if location is None else redirect_target(url, location),
        "set_cookie_present": bool(get("Set-Cookie")),
    }


def retain(url: str, status: int, body: bytes) -> tuple[bytes | None, str]:
    found = page_kind(url)
    if found is None:
        return None, "not kept: not a URL the proof may keep"
    if status != 200:
        return None, f"not kept: status {status}"
    site, kind = found
    projections = {
        "robots": lambda: (robots_rules(body), ()),
        "sitemap": lambda: (listing_sitemap(site, body), ()),
        "search-values": lambda: (search_lists(body), ()),
        "detail": lambda: project_detail(body) or (None, ()),
    }
    kept, texts = projections[kind]()
    if kept is None:
        return None, "not kept: expected structure not found"
    if any(holds_contact(text) for text in (kept.decode("utf-8", "replace"), *texts)):
        return None, "not kept: a contact detail survived the projection"
    return kept, "kept projection"


def robots_rules(body: bytes) -> bytes:
    lines = [
        line.split("#", 1)[0].rstrip()
        for line in body.decode("utf-8", "replace").splitlines()
    ]
    return ("\n".join(lines) + "\n").encode()


def listing_sitemap(site: str, body: bytes) -> bytes | None:
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return None
    rows = ['<?xml version="1.0" encoding="UTF-8"?>', f'<urlset xmlns="{SITEMAP_NS}">']
    for entry in root.findall(f"{{{SITEMAP_NS}}}url"):
        loc = (entry.findtext(f"{{{SITEMAP_NS}}}loc") or "").strip()
        if page_kind(loc) != (site, "detail"):
            continue
        lastmod = (entry.findtext(f"{{{SITEMAP_NS}}}lastmod") or "").strip()
        dated = f"<lastmod>{lastmod}</lastmod>" if W3C_DATE.fullmatch(lastmod) else ""
        rows.append(f"<url><loc>{html.escape(loc)}</loc>{dated}</url>")
    rows.append("</urlset>")
    return ("\n".join(rows) + "\n").encode()


def search_lists(body: bytes) -> bytes | None:
    script = body.decode("utf-8", "replace")
    kept = []
    for name in SEARCH_VARS:
        match = re.search(rf"\bvar\s+{name}\s*=\s*(\[.*?\])\s*;", script, re.S)
        try:
            values = json.loads(match.group(1)) if match else None
        except json.JSONDecodeError:
            values = None
        if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            return None
        kept.append(f"var {name} = {json.dumps(values, ensure_ascii=False)};\n")
    return "".join(kept).encode()


class Element:
    __slots__ = ("tag", "classes", "children")

    def __init__(self, tag: str, classes: frozenset[str]):
        self.tag, self.classes, self.children = tag, classes, []


class Tree(HTMLParser):
    """Parse markup into elements that keep only their tag, class tokens, and decoded text."""

    def __init__(self, markup: str):
        super().__init__(convert_charrefs=True)
        self.root = Element("", frozenset())
        self.stack = [self.root]
        self.feed(markup)
        self.close()

    def handle_starttag(self, tag, attrs):
        element = Element(tag, frozenset((dict(attrs).get("class") or "").split()))
        self.stack[-1].children.append(element)
        if tag not in VOID:
            self.stack.append(element)

    def handle_endtag(self, tag):
        for depth in range(len(self.stack) - 1, 0, -1):
            if self.stack[depth].tag == tag:
                del self.stack[depth:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def elements(node: Element, tag: str, token: str | None = None):
    for child in node.children:
        if isinstance(child, Element):
            if child.tag == tag and (token is None or token in child.classes):
                yield child
            yield from elements(child, tag, token)


def strings(node: Element):
    for child in node.children:
        if isinstance(child, str):
            yield child
        else:
            yield from strings(child)


def whole(node: Element) -> str:
    return squash("".join(strings(node)))


def list_item(name: str, li: Element) -> tuple[str, list[str]] | None:
    """Rebuild a list item the way both parsers read it, with every text it can yield."""
    label = next(elements(li, "label"), None)
    label_text = whole(label) if label is not None else None
    own = squash(" ".join(child for child in li.children if isinstance(child, str)))
    texts = [own, whole(li), squash(" ".join(strings(li)))]
    texts += [label_text] if label_text is not None else []
    head = f"<label>{html.escape(label_text)}</label>" if label_text is not None else ""
    if name == "feature-list" and "notable" in li.classes:
        return f'<li class="notable">{head}{html.escape(own)}</li>', texts
    if name == "spec-list" and label_text is not None:
        return f"<li>{head}<br>{html.escape(own)}</li>", texts
    if name == "spec-list" and "full-line" not in li.classes:
        return None
    visits = ' class="full-line"' if name == "spec-list" else ""
    return f"<li{visits}>{html.escape(whole(li))}</li>", texts


def first(pattern: str, text: str, group: int = 0) -> str | None:
    match = re.search(pattern, text, re.S)
    return match.group(group) if match else None


def plain(fragment: str | None) -> str:
    return squash(html.unescape(re.sub(r"<[^>]+>", " ", fragment or "")))


def project_detail(body: bytes) -> tuple[bytes, list[str]] | None:
    page = body.decode("utf-8", "replace")
    start = page.find(HEADING)
    boundary = page.find(HEADING, start + 1) if start >= 0 else -1
    if start < 0 or boundary < 0:
        return None
    listing, seller = Tree(page[start:boundary]).root, page[boundary:]
    title = next(elements(listing, "h1", "content-block"), None)
    lists = {name: next(elements(listing, "ul", name), None) for name in LISTS}
    if title is None or lists["spec-list"] is None:
        return None
    texts = [whole(title), squash(" ".join(strings(title)))]
    blocks = []
    for name, ul in lists.items():
        if ul is None:
            continue
        items = [item for li in elements(ul, "li") if (item := list_item(name, li))]
        texts += [text for _, item_texts in items for text in item_texts]
        blocks.append(
            f'<ul class="content-block {name}">'
            + "".join(markup for markup, _ in items)
            + "</ul>"
        )
    ad_text = next(elements(listing, "p", "ad-text"), None)
    facts = text_facts("\n".join(strings(ad_text)) if ad_text is not None else None)
    meta = first(r'<meta name="description" content="([^"]*)"', page, 1)
    description = html.unescape(meta) if meta is not None else None
    texts += [description] if description is not None else []
    variables = {}
    for name, value in JS_VAR.findall(page):
        if name in LISTING_VARS and re.fullmatch(r"[\w.-]*", value.strip()):
            variables.setdefault(name, value.strip())
    heading = plain(first(rf"{HEADING}.*?</h1>", seller))
    city = first(
        r'<li class="label">Ciudad:</li>\s*<li class="notable">(.*?)</li>', seller, 1
    )
    place = plain(city).split(",")[-1].strip()
    province = place if PLACE.fullmatch(place) else ""
    parts = [
        '<!DOCTYPE html>\n<html lang="es"><head><meta charset="utf-8">',
        f'<meta name="description" content="{html.escape(description)}" />'
        if description is not None
        else "",
        '</head><body><div id="content"><script type="text/javascript">\n',
        "".join(f"var {name} = '{value}';\n" for name, value in variables.items()),
        "</script>",
        f'<h1 class="content-block">{html.escape(whole(title))}</h1>',
        *blocks,
        '<p class="content-block ad-text" data-text-facts="',
        html.escape(json.dumps(facts, sort_keys=True), quote=True),
        '"></p>',
        f"{HEADING}>{heading if heading in SELLER_KINDS else ''}</h1>",
        '<ul class="content-block contact-list"><li class="label">Ciudad:</li>'
        f'<li class="notable">{html.escape(province)}</li></ul>'
        if province
        else "",
        '<a href="/Dealers/">Ver Inventario</a>' if 'href="/Dealers/' in seller else "",
        "</div></body></html>\n",
    ]
    return "".join(parts).encode(), texts
