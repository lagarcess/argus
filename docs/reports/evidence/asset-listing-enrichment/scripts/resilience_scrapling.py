import hashlib
import json
from pathlib import Path

from common import squash
from scrapling.parser import Selector

DB = str(Path("adaptive.db").resolve())
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


sample = json.loads(Path("sample.json").read_text())
baseline = json.loads(Path("out/bs4.raw.local.json").read_text())
result = {}
idx = 0
for site, rows in sample.items():
    for i, row in enumerate(rows):
        base = baseline[idx]["specs"]
        idx += 1
        args = {"storage_file": DB, "url": row["url"]}
        original = Path(
            "cache",
            site,
            hashlib.sha256(row["url"].encode()).hexdigest()[:24] + ".body",
        ).read_text("utf-8", "replace")
        Selector(original, url=row["url"], adaptive=True, storage_args=args).css(
            "ul.spec-list", auto_save=True
        )
        for m in ("m1", "m2"):
            page = Selector(
                Path("mutated", f"{site}-{i}-{m}.html").read_text(),
                url=row["url"],
                adaptive=True,
                storage_args=args,
            )
            found = page.css("ul.spec-list", adaptive=True)
            got = specs_from(found[0]) if found else {}
            ok = sum(1 for k, v in base.items() if got.get(k) == v)
            result.setdefault(m, {"recovered": 0, "total": 0, "relocated_to": set()})
            result[m]["recovered"] += ok
            result[m]["total"] += len(base)
            for percentage in PERCENTAGES:
                for element in page.css(
                    "ul.spec-list", adaptive=True, percentage=percentage
                ):
                    result[m]["relocated_to"].add(
                        f"{element.tag}.{element.attrib.get('class', '')}"
                    )
report = {
    m: {**v, "relocated_to": sorted(v["relocated_to"]), "percentages": PERCENTAGES}
    for m, v in result.items()
}
Path("out/resilience_scrapling.json").write_text(json.dumps(report, indent=1) + "\n")
print(json.dumps(report))
