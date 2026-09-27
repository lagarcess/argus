"""Seeded, stratified detail-page sample drawn only from each site's sitemap."""

import hashlib
import json
import random
import re
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

SEED = 20260927
TODAY = date(2026, 9, 27)
NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def listings(site):
    key = hashlib.sha256(f"https://m.{site}.com/sitemap.xml".encode()).hexdigest()[:24]
    root = ET.fromstring(Path("cache", site, key + ".body").read_bytes())
    rows = []
    for u in root.findall("s:url", NS):
        loc = u.find("s:loc", NS).text.strip()
        lm = u.find("s:lastmod", NS)
        segs = [s for s in re.sub(r"https?://[^/]+", "", loc).split("/") if s]
        if len(segs) == 2 and segs[1].isdigit() and lm is not None and " " not in loc:
            rows.append(
                {
                    "url": loc,
                    "slug": segs[0],
                    "age": (TODAY - date.fromisoformat(lm.text[:10])).days,
                }
            )
    return sorted(rows, key=lambda r: r["url"])


def draw(rng, rows, n, pred):
    pool = [r for r in rows if pred(r)]
    return rng.sample(pool, n)


STRATA = {
    "supercarros": [
        ("cluster_recent", 5, lambda r: r["slug"] == "honda-crv" and r["age"] <= 30),
        ("cluster_stale", 1, lambda r: r["slug"] == "honda-crv" and r["age"] > 365),
        ("other_recent", 3, lambda r: r["slug"] != "honda-crv" and r["age"] <= 90),
        ("other_older", 1, lambda r: r["slug"] != "honda-crv" and 90 < r["age"] <= 365),
    ],
    "supercasas": [
        (
            "cluster_recent",
            5,
            lambda r: r["slug"] == "apartamentos-ensanche-naco" and r["age"] <= 30,
        ),
        (
            "cluster_stale",
            1,
            lambda r: r["slug"] == "apartamentos-ensanche-naco" and r["age"] > 365,
        ),
        ("house_recent", 2, lambda r: r["slug"].startswith("casas-") and r["age"] <= 90),
        ("villa_recent", 1, lambda r: r["slug"].startswith("villas-") and r["age"] <= 90),
        (
            "east_apartment",
            1,
            lambda r: r["slug"]
            in ("apartamentos-bavaro", "apartamentos-cap-cana", "apartamentos-punta-cana")
            and r["age"] <= 90,
        ),
    ],
}

sample = {}
for site, strata in STRATA.items():
    rng = random.Random(f"{SEED}-{site}")
    rows = listings(site)
    sample[site] = [
        dict(r, stratum=name)
        for name, n, pred in strata
        for r in draw(rng, rows, n, pred)
    ]
Path("sample.json").write_text(json.dumps(sample, indent=2))
for site, rows in sample.items():
    print(site, len(rows))
    for r in rows:
        print("  ", r["stratum"], r["slug"], "age", r["age"])
