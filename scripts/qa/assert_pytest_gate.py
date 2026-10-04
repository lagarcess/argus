"""Fail a required pytest gate unless every collected test ran and passed."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

_OUTCOME_LABELS = {"failure": "failed", "error": "error", "skipped": "skipped"}


@dataclass(frozen=True)
class GateReport:
    tests: int
    failures: int
    errors: int
    skipped: int
    not_passed: tuple[str, ...]

    @property
    def passed(self) -> int:
        return self.tests - self.failures - self.errors - self.skipped

    @property
    def clean(self) -> bool:
        return not (self.failures or self.errors or self.skipped)

    @property
    def counts(self) -> str:
        return (
            f"{self.tests} tests, {self.passed} passed, {self.failures} failed,"
            f" {self.errors} errors, {self.skipped} skipped"
        )


def _read(path: Path) -> GateReport:
    root = ElementTree.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))

    def total(attribute: str) -> int:
        return sum(int(suite.attrib.get(attribute, "0")) for suite in suites)

    not_passed = tuple(
        f"  {_OUTCOME_LABELS[outcome.tag]}:"
        f" {case.attrib.get('classname', '')}::{case.attrib.get('name', '')}"
        for suite in suites
        for case in suite.iter("testcase")
        for outcome in case
        if outcome.tag in _OUTCOME_LABELS
    )
    return GateReport(
        tests=total("tests"),
        failures=total("failures"),
        errors=total("errors"),
        skipped=total("skipped"),
        not_passed=not_passed,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("junit_xml", type=Path)
    args = parser.parse_args()
    report = _read(args.junit_xml)
    if report.tests <= 0:
        raise SystemExit("required pytest gate collected zero tests")
    if not report.clean:
        raise SystemExit(
            "\n".join(
                [f"required pytest gate failed: {report.counts}", *report.not_passed]
            )
        )
    print(f"required pytest gate passed: {report.counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
