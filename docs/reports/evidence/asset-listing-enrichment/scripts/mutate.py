"""Write two synthetic markup changes of every cached detail page (offline)."""

import hashlib
import json
import re
from pathlib import Path


def rename_classes(html):
    return (
        html.replace('class="content-block spec-list"', 'class="block specs"')
        .replace('class="content-block feature-list"', 'class="block features"')
        .replace('<h1 class="content-block"', '<h1 class="block"')
    )


def restructure_specs(html):
    html = rename_classes(html)

    def spec(match):
        items = re.findall(
            r"<li><label>(.*?)</label><br>(.*?)</li>", match.group(1), re.S
        )
        rows = "".join(
            f'<div class="row"><span class="k">{k}</span><span class="v">{v}</span></div>'
            for k, v in items
        )
        return f'<section class="block specs">{rows}</section>'

    return re.sub(r'<ul class="block specs">(.*?)</ul>', spec, html, flags=re.S)


def main():
    sample = json.loads(Path("sample.json").read_text())
    out = Path("mutated")
    out.mkdir(exist_ok=True)
    for site, rows in sample.items():
        for i, row in enumerate(rows):
            key = hashlib.sha256(row["url"].encode()).hexdigest()[:24]
            body = Path("cache", site, key + ".body").read_text("utf-8", "replace")
            renamed, restructured = rename_classes(body), restructure_specs(body)
            assert renamed != body and restructured != renamed, (site, i)
            (out / f"{site}-{i}-m1.html").write_text(renamed)
            (out / f"{site}-{i}-m2.html").write_text(restructured)
    print("mutations written", len(list(out.glob("*.html"))))


if __name__ == "__main__":
    main()
