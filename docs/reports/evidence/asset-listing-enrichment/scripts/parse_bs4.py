from bs4 import BeautifulSoup
from common import VISITS, js_vars, squash


def own_text(node):
    return squash(" ".join(node.find_all(string=True, recursive=False)))


def extract(html: str, site: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    h1s = soup.select("h1.content-block")
    js = js_vars(script.get_text() for script in soup.find_all("script"))
    prices, features = [], []
    for li in soup.select("ul.feature-list li"):
        label = li.find("label")
        if "notable" in (li.get("class") or []):
            prices.append((squash(label.get_text()) if label else None, own_text(li)))
        else:
            features.append(squash(li.get_text()))
    specs = {
        squash(li.label.get_text()): own_text(li)
        for li in soup.select("ul.spec-list li")
        if li.label
    }
    visits = next(
        (
            int(m.group(1))
            for li in soup.select("ul.spec-list li.full-line")
            if (m := VISITS.search(li.get_text()))
        ),
        None,
    )
    ad_text = soup.select_one("p.ad-text")
    meta = soup.select_one('meta[name="description"]')
    city = None
    for li in soup.select("ul.contact-list li.label"):
        if squash(li.get_text()) == "Ciudad:":
            nxt = li.find_next_sibling("li")
            city = squash(nxt.get_text()) if nxt else None
            break
    return {
        "site": site,
        "listing_id": js.get("adId"),
        "title": squash(h1s[0].get_text()) if h1s else None,
        "seller_kind": squash(h1s[1].get_text()) if len(h1s) > 1 else None,
        "prices": prices,
        "features": features,
        "specs": specs,
        "amenities": [
            squash(li.get_text()) for li in soup.select("ul.component-list li")
        ],
        "visits": visits,
        "ad_text": ad_text.get_text("\n") if ad_text else None,
        "meta_description": meta.get("content") if meta else None,
        "js": js,
        "seller_city": city,
        "dealer_link": soup.select_one('a[href^="/Dealers/"]') is not None,
    }
