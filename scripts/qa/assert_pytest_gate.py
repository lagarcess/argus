"""Fail a required pytest gate when it collected nothing or skipped proof."""

from __future__ import annotations

import argparse
from pathlib import Path
from xml.etree import ElementTree


def _counts(path: Path) -> tuple[int, int]:
    root = ElementTree.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    tests = sum(int(suite.attrib.get("tests", "0")) for suite in suites)
    skipped = sum(int(suite.attrib.get("skipped", "0")) for suite in suites)
    return tests, skipped


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("junit_xml", type=Path)
    args = parser.parse_args()
    tests, skipped = _counts(args.junit_xml)
    if tests <= 0:
        raise SystemExit("required pytest gate collected zero tests")
    if skipped:
        raise SystemExit(
            f"required pytest gate skipped {skipped} of {tests} collected tests"
        )
    print(f"required pytest gate passed: {tests} tests, zero skips")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
