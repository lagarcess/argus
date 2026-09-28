"""Decide what the fetcher may keep on disk for each kind of page.

The fetcher holds every response in memory and writes only what `retain`
returns. A non-200 response, an unknown page kind, a page without the expected
listing and seller boundaries, and any kept text that still contains a contact
detail all keep nothing.
"""

from __future__ import annotations

import html
import json
import re
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit

from common import JS_VAR, squash
from normalize import text_facts

LISTING_PATH = re.compile(r"^/[^/]+/\d+/?$")
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
HEADING = '<h1 class="content-block"'
LISTS = ("feature-list", "spec-list", "component-list")
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
SELLER_KINDS = frozenset({"Vendedor", "Inmobiliaria", "Particular"})
PLACE = re.compile(r"[^\W\d_](?:[^\W\d_]|[ .'-]){1,39}")
CONTACT = re.compile(
    r"(?<!\d)(?:\+?1[\s.-]?)?\(?8[024]9\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)"
    r"|[\w.+-]+@[\w-]+\.[A-Za-z]{2,}"
    r"|wa\.me/|tel:|mailto:|data-cfemail"
    r"|-?\d{1,3}\.\d{5,}\s*,\s*-?\d{1,3}\.\d{5,}"
    r"|/Dealers/[^\s\"'/]",
    re.I,
)


def retain(kind: str, status: int, body: bytes) -> tuple[bytes | None, str]:
    if status != 200:
        return None, f"not kept: status {status}"
    builders = {
        "robots": robots_rules,
        "sitemap": listing_sitemap,
        "search-values": lambda raw: raw,
        "detail": project_detail,
    }
    if kind not in builders:
        return None, f"not kept: no rule for {kind}"
    kept = builders[kind](body)
    if kept is None:
        return None, "not kept: expected structure not found"
    if CONTACT.search(kept.decode("utf-8", "replace")):
        return None, "not kept: a contact detail survived the projection"
    return kept, "kept whole" if kind == "search-values" else "kept projection"


def robots_rules(body: bytes) -> bytes:
    lines = [
        line.split("#", 1)[0].rstrip()
        for line in body.decode("utf-8", "replace").splitlines()
    ]
    return ("\n".join(lines) + "\n").encode()


def listing_sitemap(body: bytes) -> bytes | None:
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return None
    rows = ['<?xml version="1.0" encoding="UTF-8"?>', f'<urlset xmlns="{SITEMAP_NS}">']
    for entry in root.findall(f"{{{SITEMAP_NS}}}url"):
        loc = (entry.findtext(f"{{{SITEMAP_NS}}}loc") or "").strip()
        if not LISTING_PATH.match(urlsplit(loc).path):
            continue
        lastmod = (entry.findtext(f"{{{SITEMAP_NS}}}lastmod") or "").strip()
        dated = f"<lastmod>{html.escape(lastmod)}</lastmod>" if lastmod else ""
        rows.append(f"<url><loc>{html.escape(loc)}</loc>{dated}</url>")
    rows.append("</urlset>")
    return ("\n".join(rows) + "\n").encode()


def first(pattern: str, text: str, group: int = 0) -> str | None:
    match = re.search(pattern, text, re.S)
    return match.group(group) if match else None


def plain(fragment: str | None) -> str:
    return squash(html.unescape(re.sub(r"<[^>]+>", " ", fragment or "")))


def project_detail(body: bytes) -> bytes | None:
    page = body.decode("utf-8", "replace")
    start = page.find(HEADING)
    boundary = page.find(HEADING, start + 1) if start >= 0 else -1
    if start < 0 or boundary < 0:
        return None
    listing, seller = page[start:boundary], page[boundary:]
    title = first(r'<h1 class="content-block">.*?</h1>', listing)
    lists = [
        first(rf'<ul class="content-block {name}">.*?</ul>', listing) for name in LISTS
    ]
    if title is None or lists[1] is None:
        return None
    ad_text = first(r'<p class="content-block ad-text">(.*?)</p>', listing, 1)
    facts = text_facts(
        html.unescape(re.sub(r"<[^>]+>", "\n", ad_text)) if ad_text is not None else None
    )
    meta = first(r'<meta name="description" content="([^"]*)"', page, 1)
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
        f'<meta name="description" content="{meta}" />' if meta is not None else "",
        '</head><body><div id="content"><script type="text/javascript">\n',
        "".join(f"var {name} = '{value}';\n" for name, value in variables.items()),
        "</script>",
        title,
        *(block or "" for block in lists),
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
    return "".join(parts).encode()
