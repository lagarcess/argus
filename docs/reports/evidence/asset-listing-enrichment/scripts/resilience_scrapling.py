import json
import tempfile
from pathlib import Path

import parse_scrapling
from common import recovered, squash
from mutate import MUTATIONS
from run_parse import kept_page
from scrapling.parser import Selector

PERCENTAGES = [0, 20, 40, 60, 80]


def specs_from(ul):
    out = {}
    for li in ul.css("li"):
        label = li.css("label")
        if label:
            out[squash(label[0].get_all_text())] = squash(
                " ".join(li.xpath("./text()").getall())
            )
    return out


def adaptive_relocation(original, mutated, url, storage_file):
    args = {"storage_file": storage_file, "url": url}
    Selector(original, url=url, adaptive=True, storage_args=args).css(
        "ul.spec-list", auto_save=True
    )
    page = Selector(mutated, url=url, adaptive=True, storage_args=args)
    found = page.css("ul.spec-list", adaptive=True)
    relocated = {
        f"{element.tag}.{element.attrib.get('class', '')}"
        for percentage in PERCENTAGES
        for element in page.css("ul.spec-list", adaptive=True, percentage=percentage)
    }
    return (specs_from(found[0]) if found else {}), sorted(relocated)


def main():
    sample = json.loads(Path("sample.json").read_text())
    result = {}
    with tempfile.TemporaryDirectory() as scratch:
        db = str(Path(scratch, "adaptive.db"))
        for site, rows in sample.items():
            for row in rows:
                page = kept_page(site, row["url"])
                if page is None:
                    continue
                base = parse_scrapling.extract(page, site)["specs"]
                for name, mutate in MUTATIONS.items():
                    got, relocated = adaptive_relocation(
                        page, mutate(page), row["url"], db
                    )
                    entry = result.setdefault(
                        name, {"recovered": 0, "total": 0, "relocated_to": set()}
                    )
                    hits, total = recovered(base, got)
                    entry["recovered"] += hits
                    entry["total"] += total
                    entry["relocated_to"].update(relocated)
    report = {
        m: {**v, "relocated_to": sorted(v["relocated_to"]), "percentages": PERCENTAGES}
        for m, v in result.items()
    }
    Path("out").mkdir(exist_ok=True)
    Path("out/resilience_scrapling.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
