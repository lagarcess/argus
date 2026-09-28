"""Fetch the drawn detail pages through the budgeted fetcher, stopping on any refusal."""

import json
from pathlib import Path

from fetch_ledger import fetch

for site, rows in json.loads(Path("sample.json").read_text()).items():
    for row in rows:
        try:
            meta = fetch(row["url"])
        except SystemExit as refusal:
            print(site, "stopped:", refusal)
            break
        print(site, row["stratum"], meta["status"], meta["elapsed_ms"], "ms")
        if meta.get("stopped_site"):
            break
