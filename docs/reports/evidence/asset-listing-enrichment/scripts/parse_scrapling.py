import json

from common import VISITS, js_vars, squash
from scrapling.parser import Selector


def own_text(node):
    return squash(" ".join(node.xpath("./text()").getall()))


def extract(html: str, site: str, page: Selector | None = None) -> dict:
    page = page or Selector(html)
    h1s = page.css("h1.content-block")
    js = js_vars(page.css("script::text").getall())
    prices, features = [], []
    for li in page.css("ul.feature-list li"):
        label = li.css("label")
        if "notable" in (li.attrib.get("class") or "").split():
            prices.append(
                (squash(label[0].get_all_text()) if label else None, own_text(li))
            )
        else:
            features.append(squash(li.get_all_text()))
    specs = {
        squash(li.css("label")[0].get_all_text()): own_text(li)
        for li in page.css("ul.spec-list li")
        if li.css("label")
    }
    visits = next(
        (
            int(m.group(1))
            for li in page.css("ul.spec-list li.full-line")
            if (m := VISITS.search(li.get_all_text()))
        ),
        None,
    )
    ad_text = page.css("p.ad-text")
    meta = page.css('meta[name="description"]')
    city = None
    for li in page.css("ul.contact-list li.label"):
        if squash(li.get_all_text()) == "Ciudad:":
            nxt = li.next
            city = squash(nxt.get_all_text()) if nxt is not None else None
            break
    return {
        "site": site,
        "listing_id": js.get("adId"),
        "title": squash(h1s[0].get_all_text()) if h1s else None,
        "seller_kind": squash(h1s[1].get_all_text()) if len(h1s) > 1 else None,
        "prices": prices,
        "features": features,
        "specs": specs,
        "amenities": [
            squash(li.get_all_text()) for li in page.css("ul.component-list li")
        ],
        "visits": visits,
        "ad_text": ad_text[0].get_all_text("\n") if ad_text else None,
        "ad_text_facts": json.loads(ad_text[0].attrib["data-text-facts"])
        if ad_text and "data-text-facts" in ad_text[0].attrib
        else None,
        "meta_description": meta[0].attrib.get("content") if meta else None,
        "js": js,
        "seller_city": city,
        "dealer_link": bool(page.css('a[href^="/Dealers/"]')),
    }
