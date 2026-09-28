"""Decide whether native-auth evidence is complete, expected, and current.

`expectations.json` declares every check a suite must produce and the only
failures that are documented. Anything it does not describe fails the gate: a
missing, extra, or repeated check; an unexpected failure; a documented failure
that now passes; a partial iOS run; an app log that departs from the declared
steps; or a capture taken from a dirty tree or from code that differs from HEAD.

Usage: evidence_gate.py <evidence-dir> [--scope automated|app|all] [--only FILE ...]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Callable, Iterable
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
EXPECTATIONS = HERE / "expectations.json"
# Anything that can change what a capture observed: the probes and the Argus
# API, its schema, and its packaged contract. Prose cannot, so Markdown is out.
RUNTIME_PATHS = (
    "probes/native-auth",
    "src",
    "supabase",
    "web/argus_display_contract",
    "pyproject.toml",
    "poetry.lock",
    ":(exclude,glob)**/*.md",
)
APP_RUN_RECORD = "app/run.json"

ChangedSince = Callable[[str], list[str]]


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True)


def capture_identity() -> dict[str, object]:
    """Head and cleanliness to record in every evidence file at capture time."""
    head = git("rev-parse", "HEAD").stdout.strip()
    dirty = git("status", "--porcelain", "--", *RUNTIME_PATHS).stdout.strip()
    return {"argus_source_head": head, "source_dirty": bool(dirty)}


def runtime_changes_since(head: str) -> list[str]:
    if git("merge-base", "--is-ancestor", head, "HEAD").returncode != 0:
        return [f"<{head} is not an ancestor of HEAD>"]
    diff = git("diff", "--name-only", head, "HEAD", "--", *RUNTIME_PATHS)
    return [line for line in diff.stdout.splitlines() if line]


def load_expectations(path: Path = EXPECTATIONS) -> dict:
    return json.loads(path.read_text())


def capture_problems(name: str, doc: dict, changed_since: ChangedSince) -> list[str]:
    head = str(doc.get("argus_source_head") or "")
    if not head:
        return [f"{name}: no argus_source_head recorded"]
    problems = []
    if doc.get("source_dirty") is not False:
        problems.append(f"{name}: captured from a dirty or unrecorded tree")
    changed = changed_since(head)
    if changed:
        problems.append(
            f"{name}: runtime changed since capture at {head[:9]}: {', '.join(changed[:5])}"
        )
    return problems


def suite_problems(
    name: str, doc: dict, checks: list[str], documented: set[str]
) -> list[str]:
    results = doc.get("results")
    if not isinstance(results, list):
        return [f"{name}: no results list"]
    ids = [str(r.get("id")) for r in results]
    problems = []
    repeated = sorted(i for i, n in Counter(ids).items() if n > 1)
    missing = [c for c in checks if c not in ids]
    extra = sorted(set(ids) - set(checks))
    if repeated:
        problems.append(f"{name}: repeated checks {repeated}")
    if missing:
        problems.append(f"{name}: missing checks {missing}")
    if extra:
        problems.append(f"{name}: undeclared checks {extra}")
    for result in results:
        check, verdict = str(result.get("id")), result.get("verdict")
        if check in documented and verdict == "pass":
            problems.append(
                f"{name}: documented failure {check} now passes; update expectations and the report"
            )
        elif check in documented and verdict != "fail":
            problems.append(f"{name}: {check} has verdict {verdict!r}")
        elif check not in documented and verdict != "pass":
            problems.append(f"{name}: unexpected {verdict!r} for {check}")
    return problems


def ios_run_problems(
    name: str, doc: dict, checks: list[str], documented: set[str]
) -> list[str]:
    """xcodebuild's own count must agree, so a crashed or partial run cannot pass."""
    expected_failures = len([c for c in checks if c in documented])
    summary = str(doc.get("xcodebuild_summary") or "")
    match = re.search(r"Executed (\d+) tests?, with (\d+) failures?", summary)
    if not match:
        return [f"{name}: no xcodebuild summary"]
    executed, failures = int(match.group(1)), int(match.group(2))
    if (executed, failures) != (len(checks), expected_failures):
        return [
            f"{name}: xcodebuild executed {executed} with {failures} failures, "
            f"expected {len(checks)} with {expected_failures}"
        ]
    return []


def app_problems(root: Path, name: str, spec: dict) -> list[str]:
    path = root / name
    if not path.is_file():
        return [f"{name}: missing"]
    problems = [
        f"{spec['id']} {shot}: missing"
        for shot in spec["screenshots"]
        if not (root / shot).is_file()
    ]
    log = json.loads(path.read_text())
    declared = [s["step"] for s in spec["steps"]]
    relevant = [e for e in log if e.get("step") in set(declared)]
    if [e["step"] for e in relevant] != declared:
        problems.append(
            f"{spec['id']} {name}: steps {[e['step'] for e in relevant]} differ from declared {declared}"
        )
    else:
        for want, got in zip(spec["steps"], relevant, strict=True):
            for key, value in want["observed"].items():
                if got.get("observed", {}).get(key) != value:
                    problems.append(
                        f"{spec['id']} {name}: {want['step']} {key}={got.get('observed', {}).get(key)!r}, expected {value!r}"
                    )
    forbidden = sorted({e.get("step") for e in log} & set(spec["forbidden_steps"]))
    if forbidden:
        problems.append(f"{spec['id']} {name}: forbidden steps present {forbidden}")
    return problems


def verify(
    root: Path,
    scope: str = "all",
    only: Iterable[str] = (),
    expectations: dict | None = None,
    changed_since: ChangedSince = runtime_changes_since,
) -> list[str]:
    spec = expectations or load_expectations()
    documented = set(spec["documented_failures"])
    only = set(only)
    problems: list[str] = []
    if scope in ("automated", "all"):
        for name, checks in spec["automated"].items():
            if only and name not in only:
                continue
            path = root / name
            if not path.is_file():
                problems.append(f"{name}: missing")
                continue
            doc = json.loads(path.read_text())
            problems += capture_problems(name, doc, changed_since)
            problems += suite_problems(name, doc, checks, documented)
            if name == "ios-simulator.json":
                problems += ios_run_problems(name, doc, checks, documented)
        unknown = only - set(spec["automated"])
        problems += [f"{name}: no declared expectations" for name in sorted(unknown)]
    if scope in ("app", "all"):
        record = root / APP_RUN_RECORD
        if not record.is_file():
            problems.append(f"{APP_RUN_RECORD}: missing")
        else:
            problems += capture_problems(
                APP_RUN_RECORD, json.loads(record.read_text()), changed_since
            )
        for name, app_spec in spec["app"].items():
            problems += app_problems(root, name, app_spec)
    return problems


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--scope", choices=("automated", "app", "all"), default="all")
    parser.add_argument("--only", nargs="*", default=[])
    args = parser.parse_args()
    problems = verify(args.root, args.scope, args.only)
    for problem in problems:
        print(f"EVIDENCE GATE: {problem}", file=sys.stderr)
    print(f"evidence gate: {len(problems)} problem(s) in {args.root} ({args.scope})")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
