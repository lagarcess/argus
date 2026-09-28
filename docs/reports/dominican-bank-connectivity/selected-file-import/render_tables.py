from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
README = HERE / "README.md"
STATUS = {
    "passed": "Passed",
    "failed": "Failed",
    "error": "Error",
    "blocked": "Blocked, needs 724",
}
QUESTIONS = {
    "source_file_retention": "Retention of source files",
    "password_entry": "Password entry",
    "upload_limit_bytes": "Upload limit",
    "pdf_open_time_limit_seconds": "Time limit for opening an encrypted PDF",
    "household_source_file_visibility": "Household visibility of source files",
}
UNITS = {
    "upload_limit_bytes": lambda value: f"{value / 2**20:g} MiB",
    "pdf_open_time_limit_seconds": lambda value: f"{value:g} seconds",
}


def matrix(with_model: dict, without_model: dict) -> list[str]:
    head = with_model["provenance"]["recording_model"]["commit"][:9]
    without = {case["case"]: case["status"] for case in without_model["cases"]}
    lines = [
        f"| Case | Group | Claim | With 724 at `{head}` | Without 724 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for case in with_model["cases"]:
        lines.append(
            f"| `{case['case']}` | {case['group']} | {case['claim']} | "
            f"{STATUS[case['status']]} | {STATUS[without.pop(case['case'])]} |"
        )
    if without:
        raise SystemExit(f"cases only in the report without 724: {sorted(without)}")
    return lines


def assumptions(report: dict) -> list[str]:
    choices = {
        key: value for key, value in report["assumptions"].items() if key != "status"
    }
    if choices.keys() != QUESTIONS.keys():
        raise SystemExit(
            f"assumptions without a question: {sorted(choices.keys() ^ QUESTIONS.keys())}"
        )
    lines = ["| Question | The proof's assumption | Status |", "| --- | --- | --- |"]
    for key, question in QUESTIONS.items():
        lines.append(f"| {question} | {UNITS.get(key, str)(choices[key])} | Unresolved |")
    return lines


def render(readme: str, tables: dict[str, list[str]]) -> str:
    for name, lines in tables.items():
        start, end = f"<!-- rendered {name} start -->", f"<!-- rendered {name} end -->"
        before, rest = readme.split(start)
        _, after = rest.split(end)
        readme = f"{before}{start}\n\n" + "\n".join(lines) + f"\n\n{end}{after}"
    return readme


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check the README's matrix and assumptions tables against the committed proof reports."
    )
    parser.add_argument(
        "--write", action="store_true", help="rewrite both tables from the reports"
    )
    args = parser.parse_args()
    with_model = json.loads((HERE / "proof-report.json").read_text())
    without_model = json.loads((HERE / "proof-report-without-724.json").read_text())
    current = README.read_text()
    rendered = render(
        current,
        {
            "matrix": matrix(with_model, without_model),
            "assumptions": assumptions(with_model),
        },
    )
    if args.write:
        README.write_text(rendered)
    elif rendered != current:
        sys.stdout.writelines(
            difflib.unified_diff(
                current.splitlines(True),
                rendered.splitlines(True),
                "README.md",
                "rendered",
            )
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
