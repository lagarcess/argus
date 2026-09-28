"""Offline checks on the synthetic fixtures for one parser.

Each fixture is parsed twice: as the raw page, and as the projection the
fetcher would keep. Both must give the reviewed record in expected.json. The
parse and resilience scripts then run in a temporary study directory, and no
file they write may hold seller data. Run it with the environment of the
parser it names, for example `venv-simple/bin/python check_fixtures.py bs4`.
It sends no request.
"""

import contextlib
import hashlib
import importlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path

from common import recovered
from mutate import MUTATIONS
from normalize import normalize
from retention import CONTACT, retain

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
CASES = {
    "supercarros": (
        "vehicle-detail.html",
        "https://m.supercarros.com/marca-ejemplo-modelo-x/0000001/",
    ),
    "supercasas": (
        "property-detail.html",
        "https://m.supercasas.com/apartamentos-sector-ejemplo/0000002/",
    ),
}
SALT = "fixture"


def leaks(text, seller_strings):
    found = [value for value in seller_strings if value in text]
    match = CONTACT.search(text)
    return found + ([match.group(0)] if match else [])


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


@contextlib.contextmanager
def study_directory():
    previous = Path.cwd()
    with tempfile.TemporaryDirectory() as scratch:
        os.chdir(scratch)
        try:
            yield Path(scratch)
        finally:
            os.chdir(previous)


def pipeline(parser_name, expected):
    import run_parse

    failures = []
    with study_directory() as root:
        sample = {}
        for site, (fixture, url) in CASES.items():
            kept, _ = retain("detail", 200, (FIXTURES / fixture).read_bytes())
            key = hashlib.sha256(url.encode()).hexdigest()[:24]
            page = Path("cache", site, key + ".body")
            page.parent.mkdir(parents=True)
            page.write_bytes(kept)
            sample[site] = [{"url": url, "stratum": "fixture", "age": 0}]
        Path("sample.json").write_text(json.dumps(sample))
        Path("salt.txt").write_text(SALT)
        with contextlib.redirect_stdout(io.StringIO()):
            run_parse.main(parser_name)
            importlib.import_module(f"resilience_{parser_name}").main()
        for record in json.loads(
            Path("out", f"{parser_name}.normalized.json").read_text()
        ):
            core = {
                k: v
                for k, v in record.items()
                if k not in ("stratum", "sitemap_lastmod_age_days")
            }
            if core != expected["normalized"][record["site"]]:
                failures.append(
                    f"{record['site']}: pipeline record differs from expected.json"
                )
        for path in sorted(root.rglob("*")):
            if path.is_file():
                found = leaks(
                    path.read_text("utf-8", "replace"), expected["seller_strings"]
                )
                if found:
                    failures.append(
                        f"pipeline file {path.relative_to(root)} holds {found}"
                    )
    return failures


def main(parser_name):
    parser = importlib.import_module(f"parse_{parser_name}")
    expected = json.loads((FIXTURES / "expected.json").read_text())
    failures = []
    for site, (fixture, _) in CASES.items():
        raw_bytes = (FIXTURES / fixture).read_bytes()
        html = raw_bytes.decode()
        raw = parser.extract(html, site)
        record = normalize(raw, SALT)
        if record != expected["normalized"][site]:
            failures.append(f"{site}: raw-page record differs from expected.json")
        found = leaks(json.dumps(record, ensure_ascii=False), expected["seller_strings"])
        if found or "adCustomerId" in raw["js"]:
            failures.append(f"{site}: seller data reached the record: {found}")
        kept, note = retain("detail", 200, raw_bytes)
        if kept is None:
            failures.append(f"{site}: the fetcher would keep nothing ({note})")
        else:
            found = leaks(kept.decode(), expected["seller_strings"])
            if found:
                failures.append(f"{site}: the kept projection holds {found}")
            if (
                normalize(parser.extract(kept.decode(), site), SALT)
                != expected["normalized"][site]
            ):
                failures.append(
                    f"{site}: kept-projection record differs from expected.json"
                )
        got = resilience(parser_name, parser, site, html, raw["specs"])
        if got != expected["resilience"][parser_name][site]:
            failures.append(f"{site}: markup-change result {got}")
    failures += pipeline(parser_name, expected)
    for failure in failures:
        print("FAIL", failure)
    print(
        f"{parser_name}: {'all checks pass' if not failures else f'{len(failures)} failures'}"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
