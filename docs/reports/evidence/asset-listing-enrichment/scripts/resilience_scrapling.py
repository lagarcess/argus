import hashlib
import json
from pathlib import Path

from common import squash
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
    db = str(Path("adaptive.db").resolve())
    sample = json.loads(Path("sample.json").read_text())
    baseline = json.loads(Path("out/bs4.raw.local.json").read_text())
    result = {}
    idx = 0
    for site, rows in sample.items():
        for i, row in enumerate(rows):
            base = baseline[idx]["specs"]
            idx += 1
            key = hashlib.sha256(row["url"].encode()).hexdigest()[:24]
            original = Path("cache", site, key + ".body").read_text("utf-8", "replace")
            for m in ("m1", "m2"):
                mutated = Path("mutated", f"{site}-{i}-{m}.html").read_text()
                got, relocated = adaptive_relocation(original, mutated, row["url"], db)
                ok = sum(1 for k, v in base.items() if got.get(k) == v)
                entry = result.setdefault(
                    m, {"recovered": 0, "total": 0, "relocated_to": set()}
                )
                entry["recovered"] += ok
                entry["total"] += len(base)
                entry["relocated_to"].update(relocated)
    report = {
        m: {**v, "relocated_to": sorted(v["relocated_to"]), "percentages": PERCENTAGES}
        for m, v in result.items()
    }
    Path("out/resilience_scrapling.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
