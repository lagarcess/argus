"""Offline checks on the synthetic fixtures: one parser, normalization, and markup changes.

Run it with the environment of the parser it names, for example
`venv-simple/bin/python check_fixtures.py bs4` or
`venv-scrapling/bin/python check_fixtures.py scrapling`. It sends no request.
"""

import importlib
import json
import sys
import tempfile
from pathlib import Path

from mutate import rename_classes, restructure_specs
from normalize import normalize

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
CASES = {"supercarros": "vehicle-detail.html", "supercasas": "property-detail.html"}
SALT = "fixture"
MUTATIONS = {"m1": rename_classes, "m2": restructure_specs}


def recovered(base, got):
    return [sum(1 for key, value in base.items() if got.get(key) == value), len(base)]


def resilience(parser_name, parser, site, html, base):
    results = {}
    for name, mutate in MUTATIONS.items():
        mutated = mutate(html)
        if parser_name == "bs4":
            from resilience_bs4 import label_anchored_specs

            results[name] = {
                "class_selectors": recovered(
                    base, parser.extract(mutated, site)["specs"]
                ),
                "label_lookup": recovered(base, label_anchored_specs(mutated)),
            }
        else:
            from resilience_scrapling import adaptive_relocation

            with tempfile.TemporaryDirectory() as scratch:
                specs, relocated = adaptive_relocation(
                    html,
                    mutated,
                    f"https://fixture.invalid/{site}",
                    str(Path(scratch, "adaptive.db")),
                )
            results[name] = {
                "adaptive_recovered": recovered(base, specs),
                "adaptive_relocated_to": relocated,
            }
    return results


def main(parser_name):
    parser = importlib.import_module(f"parse_{parser_name}")
    expected = json.loads((FIXTURES / "expected.json").read_text())
    failures = []
    for site, fixture in CASES.items():
        html = (FIXTURES / fixture).read_text()
        raw = parser.extract(html, site)
        record = normalize(raw, SALT)
        if record != expected["normalized"][site]:
            failures.append(f"{site}: normalized record differs from expected.json")
        leaked = [
            text
            for text in expected["seller_strings"]
            if text in json.dumps(record, ensure_ascii=False)
        ]
        if leaked or "adCustomerId" in raw["js"]:
            failures.append(f"{site}: seller data reached the output: {leaked}")
        got = resilience(parser_name, parser, site, html, raw["specs"])
        if got != expected["resilience"][parser_name][site]:
            failures.append(f"{site}: markup-change result {got}")
    for failure in failures:
        print("FAIL", failure)
    print(
        f"{parser_name}: {len(CASES) - len({f.split(':')[0] for f in failures})} of {len(CASES)} fixtures pass"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
