"""Assemble parser-comparison.json from the outputs of run_parse.py and the resilience scripts."""

import json
import statistics
from pathlib import Path

PARSERS = ("bs4", "scrapling")
SITES = ("supercarros", "supercasas")


def load(name):
    return json.loads(Path("out", name).read_text())


normalized = {p: load(f"{p}.normalized.json") for p in PARSERS}
differences = sum(
    1
    for a, b in zip(normalized["bs4"], normalized["scrapling"], strict=False)
    for key in a
    if a[key] != b.get(key)
)
bs4_resilience = load("resilience_bs4.json")
scrapling_resilience = load("resilience_scrapling.json")
report = {
    "environments": {p: load(f"{p}.meta.json") for p in PARSERS},
    "median_parse_ms_per_page": {
        p: {
            site: statistics.median(
                t["median_ms"] for t in load(f"{p}.timings.json") if t["site"] == site
            )
            for site in SITES
        }
        for p in PARSERS
    },
    "pages": len(normalized["bs4"]),
    "normalized_field_differences_between_parsers": differences,
    "markup_change_resilience": {
        name: {
            "spec_values_total": bs4_resilience[f"bs4_class:{m}"][1],
            "bs4_class_selectors": bs4_resilience[f"bs4_class:{m}"][0],
            "bs4_label_lookup": bs4_resilience[f"bs4_label:{m}"][0],
            "scrapling_adaptive": scrapling_resilience[m]["recovered"],
            "scrapling_adaptive_relocated_to": scrapling_resilience[m]["relocated_to"],
            "scrapling_percentages_tried": scrapling_resilience[m]["percentages"],
        }
        for m, name in (("m1", "class_rename"), ("m2", "class_rename_and_restructure"))
    },
}
Path("evidence_out").mkdir(exist_ok=True)
Path("evidence_out/parser-comparison.json").write_text(
    json.dumps(report, indent=1, ensure_ascii=False) + "\n"
)
print(json.dumps(report["markup_change_resilience"], indent=1))
