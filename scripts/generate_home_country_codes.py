"""Regenerate web/lib/home-country-codes.json from the backend's owner.

The Settings picker offers exactly the codes an edit may name, and the backend
decides which those are (``argus.domain.home_country``). The checked file is a
projection of that owner, not a second list; tests/test_home_country.py fails
when it drifts.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "web" / "lib" / "home-country-codes.json"


def build_artifact_text() -> str:
    from argus.domain.home_country import country_codes, currency_codes

    document = {
        "countries": sorted(country_codes()),
        "currencies": sorted(currency_codes()),
    }
    return json.dumps(document, indent=2) + "\n"


def main() -> int:
    ARTIFACT.write_text(build_artifact_text(), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
