"""The evidence gate refuses every false-green shape the runners can produce."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import evidence_gate
import pytest

SPEC = evidence_gate.load_expectations()
UNFIXED_API = "b" * 40
FIXED_API = "c" * 40
# Against an API without the A14 fix, A14 joins the unconditional failures.
DOCUMENTED = set(SPEC["documented_failures"]) | set(SPEC["conditional_failures"])
HEAD = "a" * 40
CLEAN = {"argus_source_head": HEAD, "source_dirty": False}
IDENTITY = {
    **CLEAN,
    "argus_api_head": UNFIXED_API,
    "api_dirty": False,
    "captured_at": "2026-09-28T00:00:00+00:00",
    "client": "test",
    "environment": "test",
}


def unchanged(_: str) -> list[str]:
    return []


def fix_only_in_fixed_api(head: str, path: str, text: str) -> bool | None:
    return {UNFIXED_API: False, FIXED_API: True}.get(head)


def write(root: Path, name: str, doc: object) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc))


def suite_doc(name: str, checks: list[str], fixed: bool = False) -> dict:
    expected = set(SPEC["documented_failures"]) if fixed else DOCUMENTED
    doc = {
        **IDENTITY,
        "argus_api_head": FIXED_API if fixed else UNFIXED_API,
        "results": [
            {
                "id": c,
                "area": "a",
                "scenario": "s",
                "path": "p",
                "evidence_level": 3,
                "expected": "e",
                "observed": {"status": 200},
                "verdict": "fail" if c in expected else "pass",
                "note": "",
            }
            for c in checks
        ],
    }
    if name == "ios-simulator.json":
        failures = len([c for c in checks if c in DOCUMENTED])
        doc["xcodebuild_summary"] = (
            f"Executed {len(checks)} tests, with {failures} failures (0 unexpected)"
        )
    return doc


def app_log(spec: dict) -> list[dict]:
    steps = [{"step": "launch", "observed": {"configured": "true"}}] + [
        {"step": s["step"], "observed": dict(s["observed"])} for s in spec["steps"]
    ]
    return [{"id": str(index), **step} for index, step in enumerate(steps)]


@pytest.fixture
def complete(tmp_path: Path) -> Path:
    for name, checks in SPEC["automated"].items():
        write(tmp_path, name, suite_doc(name, checks))
    for name, entry in SPEC["cross_version"].items():
        write(tmp_path, name, suite_doc(name, entry["checks"], fixed=True))
    write(
        tmp_path, evidence_gate.APP_RUN_RECORD, {**IDENTITY, "scheme_prompts_accepted": 0}
    )
    for name, spec in SPEC["app"].items():
        write(tmp_path, name, app_log(spec))
        for shot in spec["screenshots"]:
            (tmp_path / shot).write_bytes(b"png")
    return tmp_path


def edit(root: Path, name: str, change) -> None:
    path = root / name
    doc = json.loads(path.read_text())
    change(doc)
    path.write_text(json.dumps(doc))


def problems(root: Path, **kwargs) -> list[str]:
    return evidence_gate.verify(
        root, changed_since=unchanged, contains=fix_only_in_fixed_api, **kwargs
    )


def test_complete_expected_current_evidence_passes(complete: Path) -> None:
    assert problems(complete) == []


def edit_session(root: Path, change) -> None:
    path = root / "http-session.json"
    doc = json.loads(path.read_text())
    change(doc)
    path.write_text(json.dumps(doc))


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (lambda d: d["results"].pop(0), "missing checks ['A1']"),
        (
            lambda d: d["results"].append({"id": "A1", "verdict": "pass"}),
            "repeated checks ['A1']",
        ),
        (
            lambda d: d["results"].append({"id": "A99", "verdict": "pass"}),
            "undeclared checks ['A99']",
        ),
        (lambda d: d["results"][0].update(verdict="fail"), "unexpected 'fail' for A1"),
        (
            lambda d: next(r for r in d["results"] if r["id"] == "A14").update(
                verdict="pass"
            ),
            "expected failure A14 passes against this API",
        ),
        (lambda d: d.update(source_dirty=True), "dirty"),
        (lambda d: d.pop("argus_source_head"), "no argus_source_head"),
        (lambda d: d.update(results=None), "no results list"),
    ],
)
def test_suite_false_greens_are_refused(complete: Path, change, expected: str) -> None:
    edit_session(complete, change)
    assert any(expected in p for p in problems(complete, scope="automated"))


def test_missing_suite_file_is_refused(complete: Path) -> None:
    (complete / "http-guest.json").unlink()
    assert "http-guest.json: missing" in problems(complete, scope="automated")


def test_capture_from_code_that_changed_since_is_refused(complete: Path) -> None:
    found = evidence_gate.verify(
        complete,
        "automated",
        changed_since=lambda head: ["src/argus/api/routers/auth.py"],
        contains=fix_only_in_fixed_api,
    )
    assert any("runtime changed since capture" in p for p in found)


@pytest.mark.parametrize(
    "summary",
    [
        "Executed 7 tests, with 1 failure (0 unexpected)",
        "Executed 11 tests, with 2 failures (1 unexpected)",
        "missing",
    ],
)
def test_partial_or_crashed_ios_run_is_refused(complete: Path, summary: str) -> None:
    path = complete / "ios-simulator.json"
    doc = json.loads(path.read_text())
    doc["xcodebuild_summary"] = summary
    path.write_text(json.dumps(doc))
    assert any(
        p.startswith("ios-simulator.json: ")
        for p in problems(complete, scope="automated")
    )


def test_undeclared_evidence_file_is_refused(complete: Path) -> None:
    write(complete, "http-extra.json", suite_doc("http-extra.json", ["X1"]))
    found = problems(complete, scope="automated", only=["http-extra.json"])
    assert found == ["http-extra.json: no declared expectations"]


def edit_callbacks(root: Path, change) -> None:
    path = root / "app/callback-delivery.json"
    log = json.loads(path.read_text())
    change(log)
    path.write_text(json.dumps(log))


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (
            lambda log: next(e for e in log if e["step"] == "callback.completed")[
                "observed"
            ].update(result="refused"),
            "result='refused'",
        ),
        (lambda log: log.pop(), "are not exactly"),
        (
            lambda log: log.insert(
                2, {"id": "x", "step": "callback.completed", "observed": {}}
            ),
            "are not exactly",
        ),
    ],
)
def test_app_log_departures_are_refused(complete: Path, change, expected: str) -> None:
    edit_callbacks(complete, change)
    assert any(expected in p for p in problems(complete, scope="app"))


def test_missing_screenshot_is_refused(complete: Path) -> None:
    (complete / "app/turnstile-test-interactive.png").unlink()
    assert "T3, T4 app/turnstile-test-interactive.png: missing" in problems(
        complete, scope="app"
    )


def append_step(step: str):
    return lambda log: log.append({"id": "extra", "step": step, "observed": {}})


@pytest.mark.parametrize(
    ("name", "change", "expected"),
    [
        (
            "app/callback-delivery.json",
            append_step("callback.crashed"),
            "are not exactly",
        ),
        ("app/turnstile-cancelled.json", append_step("guest.start"), "are not exactly"),
        ("app/turnstile-test-pass.json", lambda log: log.pop(0), None),
        ("app/turnstile-test-pass.json", append_step("launch"), None),
        (
            "app/turnstile-test-pass.json",
            lambda log: log[1].update(extra="x"),
            "undeclared field 'extra'",
        ),
        (
            "app/turnstile-test-pass.json",
            lambda log: log[1].pop("id"),
            "missing field 'id'",
        ),
        (
            "app/turnstile-test-pass.json",
            lambda log: log[1].update(observed={"n": 1}),
            "is not observed",
        ),
        (
            "app/turnstile-test-pass.json",
            lambda log: log.append("text"),
            "not a JSON object",
        ),
    ],
)
def test_app_logs_allow_only_declared_and_incidental_steps(
    complete: Path, name: str, change, expected: str | None
) -> None:
    edit(complete, name, change)
    found = problems(complete, scope="app")
    if expected is None:
        assert found == []
    else:
        assert any(expected in p for p in found), found


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (lambda r: r.update(scheme_prompts_accepted="unknown"), "is not count"),
        (lambda r: r.update(scheme_prompts_accepted="0"), "is not count"),
        (lambda r: r.update(scheme_prompts_accepted=-1), "is not count"),
        (lambda r: r.update(scheme_prompts_accepted=True), "is not count"),
        (
            lambda r: r.pop("scheme_prompts_accepted"),
            "missing field 'scheme_prompts_accepted'",
        ),
        (lambda r: r.update(note="x"), "undeclared field 'note'"),
        (lambda r: r.update(argus_api_head="short"), "is not sha"),
        (lambda r: r.update(api_dirty=True), "API captured from a dirty"),
    ],
)
def test_app_run_record_fields_are_declared_and_typed(
    complete: Path, change, expected
) -> None:
    edit(complete, evidence_gate.APP_RUN_RECORD, change)
    assert any(expected in p for p in problems(complete, scope="app"))


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (lambda d: d.update(unexpected=1), "undeclared field 'unexpected'"),
        (lambda d: d.pop("captured_at"), "missing field 'captured_at'"),
        (lambda d: d.update(source_dirty="no"), "is not bool"),
        (lambda d: d["results"][0].update(verdict="skipped"), "is not verdict"),
        (lambda d: d["results"][0].pop("observed"), "missing field 'observed'"),
        (lambda d: d["results"][0].update(extra=True), "undeclared field 'extra'"),
        (lambda d: d["results"][0].update(evidence_level="3"), "is not count"),
    ],
)
def test_suite_document_fields_are_declared_and_typed(
    complete: Path, change, expected
) -> None:
    edit(complete, "http-guest.json", change)
    assert any(expected in p for p in problems(complete, scope="suites"))


def test_command_line_exits_nonzero_on_any_problem(tmp_path: Path) -> None:
    gate = Path(evidence_gate.__file__)
    result = subprocess.run(
        [sys.executable, str(gate), str(tmp_path), "--scope", "automated"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "http-session.json: missing" in result.stderr


def test_staleness_follows_runtime_code_not_prose(tmp_path: Path, monkeypatch) -> None:
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=tmp_path, capture_output=True, text=True, check=True
        ).stdout.strip()

    git("init", "-q")
    git("config", "user.email", "gate@example.test")
    git("config", "user.name", "gate")
    probe = tmp_path / "probes/native-auth/probe.py"
    notes = tmp_path / "probes/native-auth/README.md"
    probe.parent.mkdir(parents=True)
    probe.write_text("v1\n")
    notes.write_text("v1\n")
    git("add", ".")
    git("commit", "-qm", "capture")
    captured = git("rev-parse", "HEAD")
    monkeypatch.setattr(evidence_gate, "REPO", tmp_path)

    notes.write_text("v2\n")
    git("commit", "-qam", "prose only")
    assert evidence_gate.runtime_changes_since(captured) == []
    assert evidence_gate.capture_identity()["source_dirty"] is False

    probe.write_text("v2\n")
    assert evidence_gate.capture_identity()["source_dirty"] is True
    git("commit", "-qam", "code")
    assert evidence_gate.runtime_changes_since(captured) == [
        "probes/native-auth/probe.py"
    ]


def a14(doc: dict) -> dict:
    return next(r for r in doc["results"] if r["id"] == "A14")


@pytest.mark.parametrize(
    ("name", "api", "a14_verdict", "expected"),
    [
        ("http-session.json", FIXED_API, "fail", "unexpected 'fail' for A14"),
        ("http-session.json", UNFIXED_API, "pass", "expected failure A14 passes"),
        ("http-session-fixed-api.json", FIXED_API, "fail", "unexpected 'fail' for A14"),
        (
            "http-session-fixed-api.json",
            UNFIXED_API,
            "fail",
            "does not contain the fix for A14",
        ),
    ],
)
def test_a14_expectation_follows_the_api_version_tested(
    complete: Path, name: str, api: str, a14_verdict: str, expected: str
) -> None:
    def change(doc: dict) -> None:
        doc["argus_api_head"] = api
        a14(doc)["verdict"] = a14_verdict

    edit(complete, name, change)
    assert any(expected in p for p in problems(complete, scope="suites"))


def test_session_suite_is_clean_against_a_fixed_api_when_a14_passes(
    complete: Path,
) -> None:
    def fixed(doc: dict) -> None:
        doc["argus_api_head"] = FIXED_API
        a14(doc)["verdict"] = "pass"

    edit(complete, "http-session.json", fixed)
    assert problems(complete, scope="suites") == []


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (lambda d: d.pop("argus_api_head"), "API version is unknown"),
        (
            lambda d: d.update(argus_api_head="d" * 40),
            "cannot read src/argus/domain/supabase_gateway.py",
        ),
        (lambda d: d.update(api_dirty=True), "API captured from a dirty"),
    ],
)
def test_unknown_or_dirty_api_is_refused(complete: Path, change, expected: str) -> None:
    edit(complete, "http-guest.json", change)
    assert any(expected in p for p in problems(complete, scope="suites"))


def test_fix_marker_is_read_from_the_api_head(tmp_path: Path, monkeypatch) -> None:
    marker = SPEC["conditional_failures"]["A14"]["fails_unless_api_contains"]

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=tmp_path, capture_output=True, text=True, check=True
        ).stdout.strip()

    git("init", "-q")
    git("config", "user.email", "gate@example.test")
    git("config", "user.name", "gate")
    source = tmp_path / marker["path"]
    source.parent.mkdir(parents=True)
    source.write_text("auth_client=create_client(url, key)\n")
    git("add", ".")
    git("commit", "-qm", "unfixed")
    unfixed = git("rev-parse", "HEAD")
    source.write_text(f"{marker['text']}url, key):\n")
    git("commit", "-qam", "fixed")
    fixed = git("rev-parse", "HEAD")
    monkeypatch.setattr(evidence_gate, "REPO", tmp_path)

    assert evidence_gate.api_contains(unfixed, marker["path"], marker["text"]) is False
    assert evidence_gate.api_contains(fixed, marker["path"], marker["text"]) is True
    assert evidence_gate.api_contains("e" * 40, marker["path"], marker["text"]) is None


def test_api_head_extract_resolves_when_git_object_is_absent(tmp_path: Path) -> None:
    """Cross-version captures must stay re-verifiable without fetching #728."""
    marker = SPEC["conditional_failures"]["A14"]["fails_unless_api_contains"]
    foreign = "a" * 40
    cached = tmp_path / "api-heads" / foreign / marker["path"]
    cached.parent.mkdir(parents=True)
    cached.write_text(f"prelude\n{marker['text']}url, key):\n")
    assert (
        evidence_gate.api_contains(
            foreign, marker["path"], marker["text"], evidence_root=tmp_path
        )
        is True
    )
    assert (
        evidence_gate.api_contains(
            foreign, marker["path"], "missing-marker", evidence_root=tmp_path
        )
        is False
    )
    assert (
        evidence_gate.api_contains(
            "b" * 40, marker["path"], marker["text"], evidence_root=tmp_path
        )
        is None
    )


def test_judge_files_do_not_make_captures_stale(tmp_path: Path, monkeypatch) -> None:
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=tmp_path, capture_output=True, text=True, check=True
        ).stdout.strip()

    git("init", "-q")
    git("config", "user.email", "gate@example.test")
    git("config", "user.name", "gate")
    probes = tmp_path / "probes/native-auth"
    (probes / "tests").mkdir(parents=True)
    judges = [
        probes / "evidence_gate.py",
        probes / "expectations.json",
        probes / "tests/t.py",
    ]
    producer = probes / "run-all.sh"
    for path in [*judges, producer]:
        path.write_text("v1\n")
    git("add", ".")
    git("commit", "-qm", "capture")
    captured = git("rev-parse", "HEAD")
    monkeypatch.setattr(evidence_gate, "REPO", tmp_path)

    for path in judges:
        path.write_text("v2\n")
    git("commit", "-qam", "judges only")
    assert evidence_gate.runtime_changes_since(captured) == []

    producer.write_text("v2\n")
    git("commit", "-qam", "producer")
    assert evidence_gate.runtime_changes_since(captured) == [
        "probes/native-auth/run-all.sh"
    ]
