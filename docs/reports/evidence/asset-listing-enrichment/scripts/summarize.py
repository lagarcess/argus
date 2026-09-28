"""Write the committed, sanitized evidence: aggregates and value shapes only."""

import collections
import hashlib
import json
import re
import statistics
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path

from normalize import fold

OUT = Path("evidence_out")
OUT.mkdir(exist_ok=True)
TODAY = date(2026, 9, 27)
NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def body(site, url):
    key = hashlib.sha256(url.encode()).hexdigest()[:24]
    return Path("cache", site, key + ".body").read_bytes()


def shape(text):
    return re.sub(r"\d", "9", text) if text is not None else None


def count(values):
    return dict(collections.Counter(values).most_common())


ledger = []
for row in map(json.loads, Path("ledger.jsonl").read_text().splitlines()):
    path = re.sub(r"https?://[^/]+", "", row["url"])
    if row["label"] == "detail":
        path = re.sub(r"/\d+/$", "/<listing-id>/", path)
    ledger.append(
        {
            k: row[k]
            for k in (
                "site",
                "label",
                "fetched_at",
                "status",
                "elapsed_ms",
                "bytes",
                "content_type",
                "server",
                "wall_markers",
            )
        }
        | {"host": re.match(r"https?://([^/]+)", row["url"]).group(1), "path": path}
    )
(OUT / "request-ledger.json").write_text(
    json.dumps(ledger, indent=1, ensure_ascii=False) + "\n"
)

sitemaps = {}
for site in ("supercarros", "supercasas"):
    root = ET.fromstring(body(site, f"https://m.{site}.com/sitemap.xml"))
    listing, other, ages, lastmod_missing = [], 0, [], 0
    for u in root.findall("s:url", NS):
        segs = [
            s
            for s in re.sub(
                r"https?://[^/]+", "", u.find("s:loc", NS).text.strip()
            ).split("/")
            if s
        ]
        if len(segs) == 2 and segs[1].isdigit():
            listing.append(segs[0])
            lm = u.find("s:lastmod", NS)
            if lm is None:
                lastmod_missing += 1
            else:
                ages.append((TODAY - date.fromisoformat(lm.text.strip()[:10])).days)
        else:
            other += 1
    buckets = collections.Counter(
        "0-7"
        if a <= 7
        else "8-30"
        if a <= 30
        else "31-90"
        if a <= 90
        else "91-365"
        if a <= 365
        else "over 365"
        for a in ages
    )
    sitemaps[site] = {
        "listing_urls": len(listing),
        "other_urls": other,
        "distinct_slugs": len(set(listing)),
        "first_slug_token_top": dict(
            collections.Counter(s.split("-")[0] for s in listing).most_common(15)
        ),
        "largest_slugs": dict(collections.Counter(listing).most_common(5)),
        "lastmod_missing": lastmod_missing,
        "lastmod_age_days_buckets": {
            k: buckets[k] for k in ("0-7", "8-30", "31-90", "91-365", "over 365")
        },
        "lastmod_age_days_median": statistics.median(ages),
    }
(OUT / "sitemap-profile.json").write_text(
    json.dumps(
        {"as_of": TODAY.isoformat(), "sites": sitemaps}, indent=1, ensure_ascii=False
    )
    + "\n"
)

recs = json.loads(Path("out/bs4.normalized.json").read_text())
brands = {}
tax = body(
    "supercarros", "https://m.supercarros.com/assets/js/searchvalues.js?20260927053"
).decode("utf-8", "replace")
for entry in json.loads(
    re.search(r"var SearchBrands\s*=\s*(\[.*?\]);", tax, re.S).group(1)
):
    parts = entry.split("|")
    brands[parts[0]] = parts[1]


def lastmod_date(r):
    return (TODAY - timedelta(days=r["sitemap_lastmod_age_days"])).isoformat()


summary = {}
cars = [r for r in recs if r["site"] == "supercarros"]
trims = []
for r in cars:
    make = brands.get(r["site_taxonomy_ids"]["adBrand"], "")
    rest = fold(r["title"] or "")
    rest = re.sub(r"^\d{4}\s+", "", rest)
    rest = rest[len(fold(make)) :].strip() if rest.startswith(fold(make)) else rest
    tokens = rest.split(" ")
    trims.append(" ".join(tokens[1:]) if tokens else "")
summary["supercarros"] = {
    "pages": len(cars),
    "title_year_make_model_parsed": sum(1 for r in cars if r["year_in_title"]),
    "make_resolved_from_site_brand_id": sum(
        1 for r in cars if brands.get(r["site_taxonomy_ids"]["adBrand"])
    ),
    "trim_text_after_model": {
        "present": sum(1 for t in trims if t),
        "absent": sum(1 for t in trims if not t),
    },
    "price_shapes": count(shape(p["raw_shape"]) for r in cars for p in r["prices"]),
    "price_currencies": count(
        p["parsed"]["currency"] for r in cars for p in r["prices"] if p["parsed"]
    ),
    "site_main_currency_amount_present": sum(
        1 for r in cars if r["site_main_currency_amount_present"]
    ),
    "implied_usd_rate_values": count(
        r["implied_usd_to_main_rate"] for r in cars if r["implied_usd_to_main_rate"]
    ),
    "mileage": {
        "present": sum(1 for r in cars if r["mileage"]["value"] is not None),
        "missing_marker_N/D": sum(1 for r in cars if r["mileage"].get("missing_marker")),
        "units_shown": count(r["mileage"]["unit"] for r in cars),
        "meta_description_shows_0.00_when_missing": sum(
            1
            for r in cars
            if r["mileage"].get("missing_marker")
            and (r["meta_mileage"] or "").startswith("0.00")
        ),
    },
    "condition": count(r["condition"] for r in cars),
    "condition_matches_is_new_flag": sum(
        1 for r in cars if (r["condition"] == "Nuevo") == (r["is_new_flag"] == "1")
    ),
    "car_age_negative": sum(
        1 for r in cars if r["car_age_years"] and int(r["car_age_years"]) < 0
    ),
    "fuel": count(r["fuel"] for r in cars),
    "transmission": count(r["transmission"] for r in cars),
    "traction": count(r["traction"] for r in cars),
    "import_spec_accessory_checked": sum(1 for r in cars if r["import_spec_accessory"]),
    "damage_or_title_field": 0,
    "seller_location_present": sum(1 for r in cars if r["province"]),
    "seller_location_granularity_examples": sorted(
        {r["province"] for r in cars if r["province"]}
        & {"Distrito Nacional", "Santo Domingo Este", "La Vega", "Duarte"}
    ),
    "dealer_inventory_link": sum(1 for r in cars if r["dealer_inventory_link"]),
    "free_text_present": sum(1 for r in cars if r["text"]["present"]),
    "free_text_keyword_flags": {
        k: sum(1 for r in cars if r["text"]["flags"][k]) for k in cars[0]["text"]["flags"]
    },
    "visible_listing_date": 0,
    "ad_key_date_equals_sitemap_lastmod": sum(
        1 for r in cars if r["ad_key_utc"] and r["ad_key_utc"][:10] == lastmod_date(r)
    ),
    "visit_counter_present": sum(1 for r in cars if r["visits"] is not None),
}
homes = [r for r in recs if r["site"] == "supercasas"]


def title_op(r):
    if " en Alquiler" in r["title_shape"]:
        return "alquiler"
    if " en Venta" in r["title_shape"]:
        return "venta"
    return None


summary["supercasas"] = {
    "pages": len(homes),
    "title_shapes": count(r["title_shape"] for r in homes),
    "price_labels": count(p["label"] for r in homes for p in r["prices"]),
    "price_shapes": count(p["raw_shape"] for r in homes for p in r["prices"]),
    "price_currencies": count(
        p["parsed"]["currency"] for r in homes for p in r["prices"] if p["parsed"]
    ),
    "pages_with_more_than_one_price": sum(1 for r in homes if len(r["prices"]) > 1),
    "pages_with_a_price_label_contradicting_title_operation": sum(
        1
        for r in homes
        if title_op(r)
        and any((p["label"] or "").split()[0] != title_op(r) for p in r["prices"])
    ),
    "implied_usd_rate_values": count(
        r["implied_usd_to_main_rate"] for r in homes if r["implied_usd_to_main_rate"]
    ),
    "built_area": {
        "positive": sum(1 for r in homes if r["built_area"]["value"] not in (None, "0")),
        "zero": sum(1 for r in homes if r["built_area"]["value"] == "0"),
        "units": count(r["built_area"]["unit"] for r in homes),
    },
    "land_area": {
        "positive": sum(1 for r in homes if r["land_area"]["value"] not in (None, "0")),
        "zero": sum(1 for r in homes if r["land_area"]["value"] == "0"),
    },
    "condition": count(r["condition"] for r in homes),
    "current_use": count(r["current_use"] for r in homes),
    "year_built_missing": sum(1 for r in homes if r["year_built"] in (None, "N/D")),
    "floor_zero_or_missing": sum(1 for r in homes if r["floor"] in (None, "0", "")),
    "rooms_present": {
        k: sum(1 for r in homes if r["rooms"][k])
        for k in ("bedrooms", "bathrooms", "parking")
    },
    "location_shape": count(
        re.sub(r"[^>]+>[^>]+", "<region> > <sector>", r["location"] or "") for r in homes
    ),
    "free_text_present": sum(1 for r in homes if r["text"]["present"]),
    "free_text_bedroom_count_disagrees_with_field": sum(
        1
        for r in homes
        if r["text"]["room_counts"]
        and int(r["rooms"]["bedrooms"] or 0) not in r["text"]["room_counts"]
    ),
    "free_text_area_disagrees_with_positive_field": sum(
        1
        for r in homes
        if r["text"]["areas"]
        and r["built_area"]["value"] not in (None, "0")
        and r["built_area"]["value"] not in r["text"]["areas"]
    ),
    "free_text_lost_characters": sum(
        1 for r in homes if r["text"]["replacement_char_runs"]
    ),
    "free_text_keyword_flags": {
        k: sum(1 for r in homes if r["text"]["flags"][k])
        for k in homes[0]["text"]["flags"]
    },
    "same_price_different_units_in_one_sector": sum(
        1
        for v in collections.Counter(
            (r["location"], p["parsed"]["amount"])
            for r in homes
            for p in r["prices"]
            if p["parsed"] and p["label"] == "venta"
        ).values()
        if v > 1
    ),
    "visible_listing_date": 0,
    "ad_key_date_equals_sitemap_lastmod": sum(
        1 for r in homes if r["ad_key_utc"] and r["ad_key_utc"][:10] == lastmod_date(r)
    ),
    "visit_counter_present": sum(1 for r in homes if r["visits"] is not None),
}
(OUT / "field-summary.json").write_text(
    json.dumps(summary, indent=1, ensure_ascii=False) + "\n"
)
print(json.dumps(summary, indent=1, ensure_ascii=False))
