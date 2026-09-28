"""Replay the kept sample through one parser; never touches the network.

Writes normalized records, timings, and package versions to out/. It writes no
raw extraction, so free text and seller fields never reach disk here.
"""

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

REPEATS = 30
PACKAGES = {
    "bs4": ["beautifulsoup4", "lxml", "soupsieve"],
    "scrapling": ["scrapling", "lxml", "cssselect", "orjson", "tld", "w3lib"],
}


def kept_page(site, url):
    key = hashlib.sha256(url.encode()).hexdigest()[:24]
    path = Path("cache", site, key + ".body")
    return path.read_text("utf-8", "replace") if path.exists() else None


def main(parser_name):
    parser = importlib.import_module(f"parse_{parser_name}")
    salt_file = Path("salt.txt")
    if not salt_file.exists():
        salt_file.write_text(secrets.token_hex(16))
    salt = salt_file.read_text()
    sample = json.loads(Path("sample.json").read_text())
    records, timings, skipped = [], [], 0
    for site, rows in sample.items():
        for row in rows:
            page = kept_page(site, row["url"])
            if page is None:
                skipped += 1
                continue
            samples = []
            for _ in range(REPEATS):
                started = time.perf_counter()
                raw = parser.extract(page, site)
                samples.append((time.perf_counter() - started) * 1000)
            timings.append(
                {"site": site, "median_ms": round(statistics.median(samples), 2)}
            )
            records.append(
                normalize(raw, salt)
                | {"stratum": row["stratum"], "sitemap_lastmod_age_days": row["age"]}
            )
    Path("out").mkdir(exist_ok=True)
    Path(f"out/{parser_name}.normalized.json").write_text(
        json.dumps(records, indent=1, ensure_ascii=False)
    )
    Path(f"out/{parser_name}.timings.json").write_text(json.dumps(timings, indent=1))
    meta = {
        "python": platform.python_version(),
        "packages": {
            name: importlib.metadata.version(name) for name in PACKAGES[parser_name]
        },
        "repeats_per_page": REPEATS,
        "pages_not_kept": skipped,
    }
    Path(f"out/{parser_name}.meta.json").write_text(json.dumps(meta, indent=1))
    print(parser_name, "pages parsed", len(records), "pages not kept", skipped)


if __name__ == "__main__":
    main(sys.argv[1])
