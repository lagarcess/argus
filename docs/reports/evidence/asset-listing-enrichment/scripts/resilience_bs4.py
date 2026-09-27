import json
from pathlib import Path

import parse_bs4
from bs4 import BeautifulSoup
from common import squash


def label_anchored_specs(html):
    soup = BeautifulSoup(html, "lxml")
    specs = {}
    for node in soup.find_all(["label", "span", "dt", "th"]):
        key = squash(node.get_text())
        if key.endswith(":") and 2 < len(key) < 30 and node.parent is not None:
            rest = squash(node.parent.get_text(" ").replace(node.get_text(), "", 1))
            specs.setdefault(key, rest)
    return specs


def recovered(base, got):
    return [sum(1 for k, v in base.items() if got.get(k) == v), len(base)]


def main():
    sample = json.loads(Path("sample.json").read_text())
    baseline = json.loads(Path("out/bs4.raw.local.json").read_text())
    result = {}
    idx = 0
    for site, rows in sample.items():
        for i, _ in enumerate(rows):
            base = baseline[idx]["specs"]
            idx += 1
            for m in ("m1", "m2"):
                html = Path("mutated", f"{site}-{i}-{m}.html").read_text()
                class_specs = parse_bs4.extract(html, site)["specs"]
                for name, got in (
                    ("bs4_class", class_specs),
                    ("bs4_label", label_anchored_specs(html)),
                ):
                    result.setdefault(f"{name}:{m}", []).append(recovered(base, got))
    totals = {k: [sum(a for a, _ in v), sum(b for _, b in v)] for k, v in result.items()}
    Path("out/resilience_bs4.json").write_text(json.dumps(totals, indent=1) + "\n")
    print(json.dumps(totals))


if __name__ == "__main__":
    main()
