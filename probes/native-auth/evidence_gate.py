"""Decide whether native-auth evidence is complete, expected, and current.

`expectations.json` declares every check a suite must produce, the only
failures that are expected, and the exact fields of every evidence document.
A conditional failure is expected only against an API whose source lacks the
named fix, and must pass against one that has it. Anything the declaration
does not describe fails the gate: an undeclared, missing, or mistyped field; a
missing, extra, or repeated check; an unexpected failure; an expected failure
that now passes; a partial iOS run; an app log step that is not declared; an
API version the gate cannot determine; or a capture taken from a dirty tree
or from code that differs from HEAD.

Usage: evidence_gate.py <evidence-dir> [--scope automated|cross|suites|app|all] [--only FILE ...]
(`suites` is automated plus cross.)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Callable, Iterable
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
EXPECTATIONS = HERE / "expectations.json"
# Anything that can change what a capture observed: the probe producers and
# the Argus API, its schema, and its packaged contract. Prose cannot, so
# Markdown is out. The gate, its declaration, and its tests only judge
# captures; the judgment is re-run at every head, so they are out too.
RUNTIME_PATHS = (
    "probes/native-auth",
    "src",
    "supabase",
    "web/argus_display_contract",
    "pyproject.toml",
    "poetry.lock",
    ":(exclude,glob)**/*.md",
    ":(exclude)probes/native-auth/evidence_gate.py",
    ":(exclude)probes/native-auth/expectations.json",
    ":(exclude,glob)probes/native-auth/tests/**",
)
API_PATHS = (
    "src",
    "supabase",
    "web/argus_display_contract",
    "pyproject.toml",
    "poetry.lock",
)
APP_RUN_RECORD = "app/run.json"

ChangedSince = Callable[[str], list[str]]
# (api head, path, text) -> whether that file at that head contains the text,
# or None when the head or the file cannot be read.
ApiContains = Callable[[str, str, str], "bool | None"]

FIELD_TYPES: dict[str, Callable[[object], bool]] = {
    "str": lambda v: isinstance(v, str),
    "bool": lambda v: isinstance(v, bool),
    "sha": lambda v: isinstance(v, str) and re.fullmatch(r"[0-9a-f]{40}", v) is not None,
    "count": lambda v: isinstance(v, int) and not isinstance(v, bool) and v >= 0,
    "list": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict),
    "observed": lambda v: isinstance(v, dict)
    and all(isinstance(k, str) and isinstance(x, str) for k, x in v.items()),
    "verdict": lambda v: v in ("pass", "fail"),
}


def schema_problems(label: str, doc: object, schema: dict[str, str]) -> list[str]:
    """Every field must be declared, present unless marked optional, and typed."""
    if not isinstance(doc, dict):
        return [f"{label}: not a JSON object"]
    fields = {key.rstrip("?"): (kind, key.endswith("?")) for key, kind in schema.items()}
    problems = [
        f"{label}: undeclared field {key!r}" for key in sorted(set(doc) - set(fields))
    ]
    for key, (kind, optional) in fields.items():
        if key not in doc:
            if not optional:
                problems.append(f"{label}: missing field {key!r}")
        elif not FIELD_TYPES[kind](doc[key]):
            problems.append(f"{label}: {key}={doc[key]!r} is not {kind}")
    return problems


def git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd or REPO, capture_output=True, text=True)


def capture_identity() -> dict[str, object]:
    """Probe and API identity to record in every evidence file at capture time.

    The API tree comes from NATIVE_AUTH_API_ROOT, which stack/api.sh also uses.
    """
    api_root = Path(os.environ.get("NATIVE_AUTH_API_ROOT") or REPO)
    source_dirty = git("status", "--porcelain", "--", *RUNTIME_PATHS).stdout.strip()
    api_dirty = git(
        "status", "--porcelain", "--", *API_PATHS, cwd=api_root
    ).stdout.strip()
    return {
        "argus_source_head": git("rev-parse", "HEAD").stdout.strip(),
        "source_dirty": bool(source_dirty),
        "argus_api_head": git("rev-parse", "HEAD", cwd=api_root).stdout.strip(),
        "api_dirty": bool(api_dirty),
    }


def api_contains(
    head: str,
    path: str,
    text: str,
    *,
    evidence_root: Path | None = None,
) -> bool | None:
    """Whether `path` at `head` contains `text`.

    Prefer `git show`. When that object is absent from the local clone (a
    cross-version capture against another PR's API head), fall back to a
    committed extract under `<evidence>/api-heads/<head>/<path>` so the gate
    stays re-verifiable without fetching foreign commits.
    """
    shown = git("show", f"{head}:{path}")
    if shown.returncode == 0:
        return text in shown.stdout
    if evidence_root is not None:
        cached = evidence_root / "api-heads" / head / path
        if cached.is_file():
            return text in cached.read_text(encoding="utf-8")
    return None


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


def expected_failures(
    name: str, doc: dict, spec: dict, contains: ApiContains
) -> tuple[set[str], list[str]]:
    """Failures this file must show, derived from the API version it tested."""
    expected = set(spec["documented_failures"])
    head = str(doc.get("argus_api_head") or "")
    if not head:
        return expected, [
            f"{name}: no argus_api_head recorded, so the API version is unknown"
        ]
    problems = []
    if doc.get("api_dirty") is not False:
        problems.append(f"{name}: API captured from a dirty or unrecorded tree")
    for check, condition in spec.get("conditional_failures", {}).items():
        marker = condition["fails_unless_api_contains"]
        present = contains(head, marker["path"], marker["text"])
        if present is None:
            problems.append(
                f"{name}: cannot read {marker['path']} at API head {head[:9]}"
            )
        elif not present:
            expected.add(check)
    return expected, problems


def suite_problems(
    name: str,
    doc: dict,
    checks: list[str],
    expected: set[str],
    result_schema: dict[str, str],
) -> list[str]:
    results = doc.get("results")
    if not isinstance(results, list):
        return [f"{name}: no results list"]
    problems = []
    for index, result in enumerate(results):
        check = result.get("id", index) if isinstance(result, dict) else index
        problems += schema_problems(f"{name} result {check}", result, result_schema)
    results = [r for r in results if isinstance(r, dict)]
    ids = [str(r.get("id")) for r in results]
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
        if check in expected and verdict == "pass":
            problems.append(
                f"{name}: expected failure {check} passes against this API; "
                "update expectations and the report"
            )
        elif check in expected and verdict != "fail":
            problems.append(f"{name}: {check} has verdict {verdict!r}")
        elif check not in expected and verdict != "pass":
            problems.append(f"{name}: unexpected {verdict!r} for {check}")
    return problems


def ios_run_problems(
    name: str, doc: dict, checks: list[str], expected: set[str]
) -> list[str]:
    """xcodebuild's own count must agree, so a crashed or partial run cannot pass."""
    failures_expected = len([c for c in checks if c in expected])
    summary = str(doc.get("xcodebuild_summary") or "")
    match = re.search(r"Executed (\d+) tests?, with (\d+) failures?", summary)
    if not match:
        return [f"{name}: no xcodebuild summary"]
    executed, failures = int(match.group(1)), int(match.group(2))
    if (executed, failures) != (len(checks), failures_expected):
        return [
            f"{name}: xcodebuild executed {executed} with {failures} failures, "
            f"expected {len(checks)} with {failures_expected}"
        ]
    return []


def app_problems(root: Path, name: str, spec: dict, expectations: dict) -> list[str]:
    """The log must be exactly the declared steps plus declared incidental ones."""
    path = root / name
    if not path.is_file():
        return [f"{name}: missing"]
    problems = [
        f"{spec['id']} {shot}: missing"
        for shot in spec["screenshots"]
        if not (root / shot).is_file()
    ]
    log = json.loads(path.read_text())
    if not isinstance(log, list):
        return problems + [f"{spec['id']} {name}: not a list of steps"]
    entry_schema = expectations["documents"]["app_log_entry"]
    for index, entry in enumerate(log):
        problems += schema_problems(
            f"{spec['id']} {name} entry {index}", entry, entry_schema
        )
    incidental = set(expectations["app_incidental_steps"])
    flow = [e for e in log if isinstance(e, dict) and e.get("step") not in incidental]
    declared = [s["step"] for s in spec["steps"]]
    if [e.get("step") for e in flow] != declared:
        problems.append(
            f"{spec['id']} {name}: steps {[e.get('step') for e in flow]} "
            f"are not exactly the declared {declared}"
        )
        return problems
    for want, got in zip(spec["steps"], flow, strict=True):
        for key, value in want["observed"].items():
            seen = got.get("observed", {}).get(key)
            if seen != value:
                problems.append(
                    f"{spec['id']} {name}: {want['step']} {key}={seen!r}, expected {value!r}"
                )
    return problems


def verify(
    root: Path,
    scope: str = "all",
    only: Iterable[str] = (),
    expectations: dict | None = None,
    changed_since: ChangedSince = runtime_changes_since,
    contains: ApiContains | None = None,
) -> list[str]:
    spec = expectations or load_expectations()
    cross = spec.get("cross_version", {})
    only = set(only)
    problems: list[str] = []
    suites: dict[str, list[str]] = {}
    if contains is None:
        contains = lambda head, path, text: api_contains(
            head, path, text, evidence_root=root
        )
    if scope in ("automated", "suites", "all"):
        suites.update(spec["automated"])
    if scope in ("cross", "suites", "all"):
        suites.update({name: entry["checks"] for name, entry in cross.items()})
    for name, checks in suites.items():
        if only and name not in only:
            continue
        path = root / name
        if not path.is_file():
            problems.append(f"{name}: missing")
            continue
        doc = json.loads(path.read_text())
        problems += schema_problems(name, doc, spec["documents"]["suite"])
        if not isinstance(doc, dict):
            continue
        problems += capture_problems(name, doc, changed_since)
        expected, api_problems = expected_failures(name, doc, spec, contains)
        problems += api_problems
        fix = cross.get(name, {}).get("api_must_contain_fix_for")
        if fix and fix in expected:
            problems.append(
                f"{name}: the API it tested does not contain the fix for {fix}"
            )
        problems += suite_problems(
            name, doc, checks, expected, spec["documents"]["result"]
        )
        if name == "ios-simulator.json":
            problems += ios_run_problems(name, doc, checks, expected)
    if scope in ("automated", "cross", "suites", "all"):
        problems += [
            f"{name}: no declared expectations" for name in sorted(only - set(suites))
        ]
    if scope in ("app", "all"):
        record = root / APP_RUN_RECORD
        if not record.is_file():
            problems.append(f"{APP_RUN_RECORD}: missing")
        else:
            run = json.loads(record.read_text())
            problems += schema_problems(APP_RUN_RECORD, run, spec["documents"]["app_run"])
            if isinstance(run, dict):
                problems += capture_problems(APP_RUN_RECORD, run, changed_since)
                if run.get("api_dirty") is not False:
                    problems.append(
                        f"{APP_RUN_RECORD}: API captured from a dirty or unrecorded tree"
                    )
        for name, app_spec in spec["app"].items():
            problems += app_problems(root, name, app_spec, spec)
    return problems


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument(
        "--scope", choices=("automated", "cross", "suites", "app", "all"), default="all"
    )
    parser.add_argument("--only", nargs="*", default=[])
    args = parser.parse_args()
    problems = verify(args.root, args.scope, args.only)
    for problem in problems:
        print(f"EVIDENCE GATE: {problem}", file=sys.stderr)
    print(f"evidence gate: {len(problems)} problem(s) in {args.root} ({args.scope})")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
