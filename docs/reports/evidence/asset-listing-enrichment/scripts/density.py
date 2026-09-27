"""Model-level and sector-level listing density from the cached sitemaps only."""

import collections
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
THRESHOLDS = (10, 30, 100, 300)
RESIDENTIAL = ("apartamentos", "casas", "villas", "penthouse", "townhouse", "aparta")
out = {}
for site in ("supercarros", "supercasas"):
    raw = Path(
        "cache",
        site,
        hashlib.sha256(f"https://m.{site}.com/sitemap.xml".encode()).hexdigest()[:24]
        + ".body",
    ).read_bytes()
    slugs = []
    for u in ET.fromstring(raw).findall("s:url", NS):
        segs = [
            s
            for s in re.sub(
                r"https?://[^/]+", "", u.find("s:loc", NS).text.strip()
            ).split("/")
            if s
        ]
        if len(segs) == 2 and segs[1].isdigit():
            slugs.append(segs[0])
    if site == "supercasas":
        slugs = [s for s in slugs if s.split("-")[0] in RESIDENTIAL]
    cells = collections.Counter(slugs)
    total = sum(cells.values())
    out[site] = {
        "cell": "make-model slug"
        if site == "supercarros"
        else "residential type-sector slug (sale and rent mixed)",
        "listings": total,
        "cells": len(cells),
        "cells_at_or_above": {
            n: sum(1 for c in cells.values() if c >= n) for n in THRESHOLDS
        },
        "share_of_listings_in_cells_at_or_above": {
            n: round(sum(c for c in cells.values() if c >= n) / total, 3)
            for n in THRESHOLDS
        },
        "median_cell_size": sorted(cells.values())[len(cells) // 2],
    }
print(json.dumps(out, indent=1))
profile = json.loads(Path("evidence_out/sitemap-profile.json").read_text())
profile["density"] = out
Path("evidence_out/sitemap-profile.json").write_text(
    json.dumps(profile, indent=1, ensure_ascii=False) + "\n"
)
