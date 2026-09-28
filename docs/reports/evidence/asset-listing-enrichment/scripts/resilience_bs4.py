import json
from pathlib import Path

import parse_bs4
from bs4 import BeautifulSoup
from common import recovered, squash
from mutate import MUTATIONS
from run_parse import kept_page


def label_anchored_specs(html):
    soup = BeautifulSoup(html, "lxml")
    specs = {}
    for node in soup.find_all(["label", "span", "dt", "th"]):
        key = squash(node.get_text())
        if key.endswith(":") and 2 < len(key) < 30 and node.parent is not None:
            rest = squash(node.parent.get_text(" ").replace(node.get_text(), "", 1))
            specs.setdefault(key, rest)
    return specs


def main():
    sample = json.loads(Path("sample.json").read_text())
    result = {}
    for site, rows in sample.items():
        for row in rows:
            page = kept_page(site, row["url"])
            if page is None:
                continue
            base = parse_bs4.extract(page, site)["specs"]
            for name, mutate in MUTATIONS.items():
                mutated = mutate(page)
                for label, got in (
                    ("bs4_class", parse_bs4.extract(mutated, site)["specs"]),
                    ("bs4_label", label_anchored_specs(mutated)),
                ):
                    result.setdefault(f"{label}:{name}", []).append(recovered(base, got))
    totals = {k: [sum(a for a, _ in v), sum(b for _, b in v)] for k, v in result.items()}
    Path("out").mkdir(exist_ok=True)
    Path("out/resilience_bs4.json").write_text(json.dumps(totals, indent=1) + "\n")
    print(json.dumps(totals))


if __name__ == "__main__":
    main()
