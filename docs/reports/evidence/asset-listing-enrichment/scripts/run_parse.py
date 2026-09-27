"""Replay the cached sample through one parser; never touches the network."""

import hashlib
import importlib
import importlib.metadata
import json
import platform
import secrets
import statistics
import sys
import time
from pathlib import Path

from normalize import normalize

parser_name = sys.argv[1]
parser = importlib.import_module(f"parse_{parser_name}")
salt_file = Path("salt.txt")
if not salt_file.exists():
    salt_file.write_text(secrets.token_hex(16))
salt = salt_file.read_text()
sample = json.loads(Path("sample.json").read_text())
REPEATS = 30
records, raws, timings = [], [], []
for site, rows in sample.items():
    for row in rows:
        body = (
            Path(
                "cache",
                site,
                hashlib.sha256(row["url"].encode()).hexdigest()[:24] + ".body",
            )
            .read_bytes()
            .decode("utf-8", "replace")
        )
        samples = []
        for _ in range(REPEATS):
            started = time.perf_counter()
            raw = parser.extract(body, site)
            samples.append((time.perf_counter() - started) * 1000)
        timings.append({"site": site, "median_ms": round(statistics.median(samples), 2)})
        record = normalize(raw, salt) | {
            "stratum": row["stratum"],
            "sitemap_lastmod_age_days": row["age"],
        }
        records.append(record)
        raws.append(raw)
Path("out").mkdir(exist_ok=True)
Path(f"out/{parser_name}.normalized.json").write_text(
    json.dumps(records, indent=1, ensure_ascii=False)
)
Path(f"out/{parser_name}.raw.local.json").write_text(
    json.dumps(raws, indent=1, ensure_ascii=False)
)
Path(f"out/{parser_name}.timings.json").write_text(json.dumps(timings, indent=1))
PACKAGES = {
    "bs4": ["beautifulsoup4", "lxml", "soupsieve"],
    "scrapling": ["scrapling", "lxml", "cssselect", "orjson", "tld", "w3lib"],
}
meta = {
    "python": platform.python_version(),
    "packages": {
        name: importlib.metadata.version(name) for name in PACKAGES[parser_name]
    },
    "repeats_per_page": REPEATS,
}
Path(f"out/{parser_name}.meta.json").write_text(json.dumps(meta, indent=1))
for site in sample:
    ms = [t["median_ms"] for t in timings if t["site"] == site]
    print(
        parser_name,
        site,
        "pages",
        len(ms),
        "median parse ms",
        statistics.median(ms),
        "max",
        max(ms),
    )
