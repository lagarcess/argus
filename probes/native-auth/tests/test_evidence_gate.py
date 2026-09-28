"""The evidence gate refuses every false-green shape the runners can produce."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import evidence_gate
import pytest

SPEC = evidence_gate.load_expectations()
DOCUMENTED = set(SPEC["documented_failures"])
HEAD = "a" * 40
CLEAN = {"argus_source_head": HEAD, "source_dirty": False}


def unchanged(_: str) -> list[str]:
    return []


def write(root: Path, name: str, doc: object) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc))


def suite_doc(name: str, checks: list[str]) -> dict:
    doc = {
        **CLEAN,
        "results": [
            {"id": c, "verdict": "fail" if c in DOCUMENTED else "pass"} for c in checks
        ],
    }
    if name == "ios-simulator.json":
        failures = len([c for c in checks if c in DOCUMENTED])
        doc["xcodebuild_summary"] = (
            f"Executed {len(checks)} tests, with {failures} failures (0 unexpected)"
        )
    return doc


def app_log(spec: dict) -> list[dict]:
    return [{"step": s["step"], "observed": dict(s["observed"])} for s in spec["steps"]]


@pytest.fixture
def complete(tmp_path: Path) -> Path:
    for name, checks in SPEC["automated"].items():
        write(tmp_path, name, suite_doc(name, checks))
    write(tmp_path, evidence_gate.APP_RUN_RECORD, CLEAN)
    for name, spec in SPEC["app"].items():
        write(tmp_path, name, app_log(spec))
        for shot in spec["screenshots"]:
            (tmp_path / shot).write_bytes(b"png")
    return tmp_path


def problems(root: Path, **kwargs) -> list[str]:
    return evidence_gate.verify(root, changed_since=unchanged, **kwargs)


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
            "documented failure A14 now passes",
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
        (lambda log: log[3]["observed"].update(result="refused"), "result='refused'"),
        (lambda log: log.pop(), "differ from declared"),
        (
            lambda log: log.insert(2, {"step": "callback.completed", "observed": {}}),
            "differ from declared",
        ),
    ],
)
def test_app_log_departures_are_refused(complete: Path, change, expected: str) -> None:
    edit_callbacks(complete, change)
    assert any(expected in p for p in problems(complete, scope="app"))


def test_forbidden_app_step_and_missing_screenshot_are_refused(complete: Path) -> None:
    path = complete / "app/turnstile-cancelled.json"
    log = json.loads(path.read_text())
    log.append({"step": "guest.start", "observed": {"result": "ok"}})
    path.write_text(json.dumps(log))
    (complete / "app/turnstile-test-interactive.png").unlink()
    found = problems(complete, scope="app")
    assert any("forbidden steps present ['guest.start']" in p for p in found)
    assert "T3, T4 app/turnstile-test-interactive.png: missing" in found


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
